# -*- coding: utf-8 -*-
"""
core/mail.py  —  IMAP-Quelle: Google-Alert-Mails (Team 2: Ingest)
=====================================================================

Liest ungelesene **Google-Alert-Mails** (Absender googlealerts-noreply@google.com)
per IMAP (stdlib imaplib — keine Extra-Abhaengigkeit) und extrahiert je Mail ALLE
Treffer: Titel, echte Artikel-URL und den Snippet. Eine Alert-Mail enthaelt i. d. R.
mehrere Treffer → jeder Treffer wird zu EINEM Kandidaten.

Warum kein „MELDUNG ÖFFNEN"-Parser mehr:
Google-Alerts haben keinen solchen Button. Ihre Links sind Google-Weiterleitungen
der Form `https://www.google.com/url?…&url=<echte-URL>&…` (HTML-Entity `&amp;`!),
daneben Google-interne Links (`/alerts`, `/alerts/share`, `/alerts/feedback`). Der
Parser packt die Weiterleitung aus (unescape + `url=`-Param) und verwirft alles
Google-Interne.

Wichtig — GLEICHE Infos, GLEICHE DB wie der RSS/Presseportal-Weg:
Diese Datei liefert nur Rohkandidaten (title/text/link/region) im selben Format wie
core.presseportal.fetch_candidates(). Score/Dedup macht workers/ingest.py, die Anlage
in `blaulicht.cases` core.supa.insert_case (source='mail'). Die Fakten-Extraktion
(Claude) macht spaeter workers/extract.py — dieselbe Pipeline, dieselben Facts.

Volltext schon beim Ingest (empirisch begruendet):
Anders als beim RSS-Weg (dort ist der RSS-Anriss lang genug fuers Scoring) sind die
Google-Snippets zu kurz — reine Snippet-Bewertung liess selbst „Automat gesprengt"-
Faelle unter die Schwelle fallen. Deshalb holt fetch_candidates() pro Treffer den
Artikel-Volltext (core.presseportal.fetch_fulltext, generisch: Artikelbereich, sonst
ganze Seite) und bewertet darauf — so erreichen die dramatischen Faelle die Schwelle
(getestet: „Zigarettenautomat gesprengt" -> Score 50–65). Faellt der Volltext duenn
aus (JS-Seite/Paywall), wird auf den Snippet zurueckgefallen.

Gegen den Alert-Backlog (Postfach kann tausende alte Alerts enthalten) werden pro
Lauf nur die neuesten MAX_MAILS_PER_RUN ungelesenen Alert-Mails verarbeitet.

Die Artikel-Links zeigen auf beliebige News-Seiten (nicht nur Presseportal);
fetch_fulltext traegt die Mehrheit (getestet ~13/19 Links mit brauchbarem Text).

ENV: IMAP_HOST, IMAP_USER, IMAP_APP_PW  (siehe .env.example)
"""
from __future__ import annotations

import email
import html as htmlmod
import imaplib
import os
import re
from datetime import datetime, timedelta
from email.header import decode_header
from email.message import Message
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs, unquote

from . import presseportal

# Absender aller Google-Alert-Mails.
GOOGLE_ALERT_SENDER = "googlealerts-noreply@google.com"

# NUR Alerts zu diesen Themen verarbeiten (Teilstring im Betreff, z. B. das
# Wort im Betreff „Google Alert – zigarettenautomat gesprengt"). Es gibt i. d. R.
# mehrere Alert-Themen im Postfach (Einbruch, Überfall, …) — ohne diesen Filter
# wuerden ALLE abgeholt.
#
# KOMMAGETRENNTE LISTE (ENV ALERT_SUBJECT_FILTER), es genuegt EIN Treffer:
# „zigaretten" deckt beide Zigaretten-Alerts ab („zigarettenautomat gesprengt"
# und „diebstahl zigaretten"), „geldautomat" den Alert „Geldautomat Sprengung".
# Frueher war das ein einzelner Begriff — dadurch fielen alle Alerts durchs
# Raster, die dieses eine Wort nicht im Betreff hatten. Leer = alle Alerts.
ALERT_SUBJECT_FILTERS = [
    s.strip()
    for s in os.environ.get("ALERT_SUBJECT_FILTER", "zigaretten,geldautomat").split(",")
    if s.strip()
]

# Zusaetzlicher Themen-Filter je EINZELNEM Treffer: Google packt in eine
# Zigaretten-Alert-Mail teils lose verwandte Artikel (Einbruch, EC-Karten …).
# Ein Treffer zaehlt nur, wenn Titel/Snippet eines dieser Woerter enthaelt —
# oder nach „Automat … gesprengt" aussieht (Zigarettenautomat-Sprengung, auch
# verkuerzt „Automat gesprengt"). Ueber ENV ALERT_TOPIC_KEYWORDS aenderbar;
# leer = kein Treffer-Filter (dann zaehlt nur der Betreff-Filter oben).
ALERT_TOPIC_KEYWORDS = [
    k.strip().lower()
    for k in os.environ.get("ALERT_TOPIC_KEYWORDS", "zigaret,tabak,kippen,raucherwaren,geldautomat,bankautomat,ec-automat").split(",")
    if k.strip()
]

# Pro Lauf nur die neuesten N ungelesenen Alert-Mails (begrenzt Laufzeit +
# verhindert, dass ein riesiger Alt-Backlog auf einmal verarbeitet wird).
MAX_MAILS_PER_RUN = 25

# Nur Alert-Mails aus den letzten N Tagen (IMAP SINCE, server-seitig). Verhindert,
# dass alte, laengst liegengebliebene Alerts als „neue" Faelle reinkommen.
# 0/leer = keine Altersgrenze. Ueber ENV ALERT_MAX_AGE_DAYS aenderbar.
try:
    ALERT_MAX_AGE_DAYS = int(os.environ.get("ALERT_MAX_AGE_DAYS", "14"))
except ValueError:
    ALERT_MAX_AGE_DAYS = 14

# Englische Monatskuerzel fuer das IMAP-Datumsformat (locale-unabhaengig).
_IMAP_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _imap_since_date(days: int) -> str:
    """Datum vor `days` Tagen im IMAP-Format 'DD-Mon-YYYY' (z. B. 11-Jul-2026)."""
    d = datetime.now() - timedelta(days=days)
    return f"{d.day:02d}-{_IMAP_MONTHS[d.month - 1]}-{d.year}"


def _subject_criteria(terms: list[str]) -> list[str]:
    """IMAP-Suchkriterium „Betreff enthaelt EINEN der Begriffe".

    IMAP kennt kein IN, nur das praefix-notierte `OR <a> <b>` fuer je ZWEI
    Ausdruecke — mehrere Begriffe werden daher geschachtelt:
        1 Begriff : SUBJECT "a"
        2 Begriffe: OR SUBJECT "a" SUBJECT "b"
        3 Begriffe: OR OR SUBJECT "a" SUBJECT "b" SUBJECT "c"
    Begriffe werden gequotet, damit auch mehrwortige funktionieren.
    """
    if not terms:
        return []
    crit = ["SUBJECT", f'"{terms[0]}"']
    for t in terms[1:]:
        crit = ["OR"] + crit + ["SUBJECT", f'"{t}"']
    return crit


def matches_subject(subject: str) -> bool:
    """True, wenn der Betreff einen der konfigurierten Begriffe enthaelt
    (Gegenprobe zur IMAP-Suche). Leere Liste = alles durchlassen."""
    if not ALERT_SUBJECT_FILTERS:
        return True
    s = (subject or "").lower()
    return any(t.lower() in s for t in ALERT_SUBJECT_FILTERS)

# Ab so vielen Zeichen gilt ein gefetchter Volltext als brauchbar; sonst
# faellt fetch_candidates auf den Snippet zurueck (Scoring-Text).
_MIN_FULLTEXT = 300

# Treffer-Link einer Alert-Mail: <a href="…google.…/url?…">Überschrift</a>.
# Nur diese Google-Weiterleitungen sind echte Treffer — Google-interne Links
# (/alerts, /alerts/share, /alerts/feedback) matchen dieses Muster NICHT.
_LINK_RE = re.compile(
    r'<a\s[^>]*href=["\']([^"\']*google\.[a-z.]+/url\?[^"\']*)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

# UI-Textbausteine, die kein Snippet sind — ab hier abschneiden.
_CRUFT_RE = re.compile(
    r"(Als nicht relevant markieren|Mehr Ergebnisse ansehen|Diesen Alert"
    r"|Alert bearbeiten|Sie haben diese|Sie erhalten diese|RSS-Feed"
    r"|Alle Benachrichtigungen|Flag as irrelevant|abbestellen)\b",
    re.IGNORECASE,
)


def _decode_header(raw: Optional[str]) -> str:
    if not raw:
        return ""
    out = []
    for text, enc in decode_header(raw):
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", "ignore"))
        else:
            out.append(text)
    return "".join(out)


def _html_body(msg: Message) -> str:
    """Den (bevorzugt) HTML-Teil einer (ggf. multipart) E-Mail zurueckgeben.
    Google-Alerts sind HTML; ohne HTML-Teil gibt es nichts zu parsen."""
    if msg.is_multipart():
        for part in msg.walk():
            if "attachment" in str(part.get("Content-Disposition") or ""):
                continue
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "ignore")
    elif msg.get_content_type() == "text/html":
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or "utf-8", "ignore")
    return ""


def _strip_tags(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _unwrap_google(href: str) -> str:
    """Google-Weiterleitung `…/url?…&url=<echt>` auspacken. Liefert die echte
    Artikel-URL, oder '' fuer eine Weiterleitung ohne Ziel. Direkte (nicht-
    Google-) Links werden unveraendert zurueckgegeben (defensiver Fallback)."""
    href = htmlmod.unescape(href)          # &amp; -> &  (sonst wird url= nicht gefunden)
    try:
        pr = urlparse(href)
    except ValueError:
        return ""
    if "google" in pr.netloc.lower() and "/url" in pr.path:
        q = parse_qs(pr.query)
        for key in ("url", "q"):
            if q.get(key):
                return unquote(q[key][0])
        return ""
    return href


def matches_topic(text: str) -> bool:
    """True, wenn der Text zum konfigurierten Thema passt (Zigaretten/Tabak
    bzw. Automaten-Sprengung). Bei leeren ALERT_TOPIC_KEYWORDS immer True."""
    if not ALERT_TOPIC_KEYWORDS:
        return True
    t = (text or "").lower()
    if any(k in t for k in ALERT_TOPIC_KEYWORDS):
        return True
    if "automat" in t and "spreng" in t:   # (Zigaretten-)Automat gesprengt
        return True
    return False


def _clean_snippet(text: str) -> str:
    m = _CRUFT_RE.search(text)
    if m:
        text = text[:m.start()]
    return text.strip(" -–|·")[:400].strip()


def extract_alert_results(html_body: str) -> list[dict[str, str]]:
    """Alle Treffer einer Google-Alert-Mail als [{title, url, snippet}].

    - Google-Weiterleitungen werden ausgepackt; Google-interne Links, leere
      Hosts, gstatic/youtube werden verworfen.
    - Der Snippet ist der Text zwischen diesem Treffer-Link und dem naechsten
      (Titel + Anriss), bereinigt um Google-UI-Texte.
    - Deduplizierung per echter URL (eine Mail listet Treffer teils mehrfach).
    """
    if not html_body:
        return []
    matches = list(_LINK_RE.finditer(html_body))
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, mt in enumerate(matches):
        url = _unwrap_google(mt.group(1))
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        if not host or "google." in host or "gstatic" in host or "youtube" in host:
            continue
        if url in seen:
            continue
        seen.add(url)
        title = _strip_tags(mt.group(2))
        start = mt.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html_body)
        snippet = _clean_snippet(_strip_tags(html_body[start:end]))
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def fetch_candidates(mark_seen: bool = True) -> list[dict[str, Any]]:
    """Ungelesene Google-Alert-Mails abholen und je Treffer einen Kandidaten
    im selben Format wie core.presseportal.fetch_candidates() liefern
    (title, text, link, date, station, region).

    Verarbeitet die neuesten MAX_MAILS_PER_RUN Alert-Mails zum Thema aus den
    letzten ALERT_MAX_AGE_DAYS Tagen (unabhaengig vom Gelesen-Status). Pro
    Treffer wird der Artikel-Volltext geholt (fuers Scoring; Snippet als Fallback
    bei duennem/blockiertem Volltext). Doppelte Faelle verhindert die Link-
    Deduplizierung in insert_case; Lese-Markierungen werden nicht veraendert.
    Der Parameter mark_seen wird aus Kompatibilitaet behalten, aber ignoriert."""
    host = os.environ.get("IMAP_HOST")
    user = os.environ.get("IMAP_USER")
    pw = os.environ.get("IMAP_APP_PW")
    if not (host and user and pw):
        raise RuntimeError(
            "Mail-Quelle nicht konfiguriert: IMAP_HOST/IMAP_USER/IMAP_APP_PW fehlen "
            "(siehe .env — Google App-Passwort bei IMAP_APP_PW eintragen).")

    stations = presseportal.load_stations()
    candidates: list[dict[str, Any]] = []
    fulltext_cache: dict[str, str] = {}   # URL -> Volltext (kein Doppel-Fetch pro Lauf)

    M = imaplib.IMAP4_SSL(host)
    try:
        M.login(user, pw)
        M.select("INBOX")
        # Suche: Absender Google-Alerts + (optional) Betreff-Thema + (optional)
        # nur der letzten N Tage. BEWUSST OHNE 'UNSEEN' — der Nutzer liest seine
        # Alerts selbst (sie werden dadurch gelesen); Idempotenz kommt stattdessen
        # ueber die Link-Deduplizierung in core.supa.insert_case (on_conflict).
        # Lese-Markierungen im Postfach werden nicht angefasst.
        criteria = ["FROM", GOOGLE_ALERT_SENDER]
        criteria += _subject_criteria(ALERT_SUBJECT_FILTERS)
        if ALERT_MAX_AGE_DAYS > 0:
            criteria += ["SINCE", _imap_since_date(ALERT_MAX_AGE_DAYS)]
        status, data = M.search(None, *criteria)
        if status != "OK" or not data or not data[0]:
            return candidates

        nums = data[0].split()[-MAX_MAILS_PER_RUN:]   # nur die neuesten N
        for num in nums:
            status, msg_data = M.fetch(num, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])

            # Betreff-Gegenprobe (falls der IMAP-Server unscharf sucht): nur
            # Alerts zu den konfigurierten Themen durchlassen.
            if not matches_subject(_decode_header(msg.get("Subject"))):
                continue

            results = extract_alert_results(_html_body(msg))
            if not results:
                continue   # keine Treffer -> nicht als gelesen markieren

            date = msg.get("Date", "")
            for r in results:
                # Pro-Treffer-Themenfilter auf den TITEL (nennt das Hauptthema).
                # Bewusst NICHT auf den Snippet: Polizei-Sammelmeldungen erwaehnen
                # Zigaretten oft nebenbei neben anderen Delikten — sonst kaemen
                # themenfremde Hauptfaelle (Diesel/E-Bike/…) durch. Vor dem
                # Volltext-Fetch -> spart HTTP fuer Ausreisser.
                if not matches_topic(r["title"]):
                    continue
                url = r["url"]
                if url not in fulltext_cache:
                    try:
                        fulltext_cache[url] = presseportal.fetch_fulltext(url)
                    except Exception:
                        fulltext_cache[url] = ""
                fulltext = fulltext_cache[url]
                # Scoring-Text: Volltext, wenn brauchbar; sonst Snippet
                text = fulltext if len(fulltext) >= _MIN_FULLTEXT else r["snippet"]

                name, region = presseportal.station_for_link(url, stations)
                candidates.append({
                    "title": r["title"] or (r["snippet"][:120] if r["snippet"] else url),
                    "text": text,
                    "link": url,
                    "date": date,
                    "station": name,
                    "region": region,
                })
            # Kein Setzen des Gelesen-Flags: Idempotenz laeuft ueber die
            # Link-Deduplizierung, und die Lese-Markierungen des Nutzers bleiben
            # unangetastet.
    finally:
        try:
            M.close()
        except Exception:
            pass
        try:
            M.logout()
        except Exception:
            pass

    return candidates
