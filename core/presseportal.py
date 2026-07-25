# -*- coding: utf-8 -*-
"""
core/presseportal.py  —  Presseportal-RSS + Volltext (Team 2: Ingest)
========================================================================

Port aus ranking.py (fetch_feed, fetch_fulltext) + discover_stations.py
(Dienststellen-Verzeichnis -> stations.json). RSS-Parsing laeuft ueber
feedparser statt xml.etree, Volltext-Extraktion ueber BeautifulSoup statt
Regex-Tag-Stripping — die Ranking-/Filter-Logik selbst bleibt unveraendert
(sie lebt jetzt in core/scoring.py).

URL-Struktur:
    Feed je Dienststelle:            /rss/dienststelle_{id}.rss2
    Volltext einer Meldung:          /pm/{id}/{meldung}
    Dienststellen-Verzeichnis:       /blaulicht/dienststellen  (discover_stations.py)

WICHTIG: Diese Datei liefert nur ROHE Kandidaten (Titel/Anriss/Link/Datum) plus
fetch_fulltext() als Werkzeug. Score + Kategorie vergibt core/scoring.py,
die Anlage in Supabase macht workers/ingest.py. Die vollstaendige
Volltext-Anreicherung + Fakten-Extraktion passiert spaeter in der
Analyse-Stufe (Team 3) — fetch_fulltext() steht dafuer hier bereit.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import feedparser
from bs4 import BeautifulSoup

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# stations.json liegt im Repo-Root (von discover_stations.py erzeugt).
_STATIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stations.json")

# Fallback, falls stations.json (noch) nicht existiert — wie in ranking.py.
_FALLBACK_STATIONS: dict[str, tuple[str, str]] = {
    "51056": ("Polizei Gelsenkirchen", "Ruhrgebiet"),
}

DAYS_BACK = 3           # nur Meldungen der letzten N Tage betrachten (wie ranking.py)
STATION_LIMIT: Optional[int] = None   # None = alle Dienststellen (Produktivbetrieb)

# Meldungs-URL -> Dienststellen-ID, z. B. https://www.presseportal.de/pm/51056/6012345
PM_LINK_RE = re.compile(r"presseportal\.de/pm/(\d+)/")


def load_stations() -> dict[str, tuple[str, str]]:
    """Dienststellen-IDs -> (Name, Region) laden.
    stations.json (von discover_stations.py erzeugt) wenn vorhanden, sonst
    derselbe Ein-Stationen-Fallback wie in ranking.py."""
    if os.path.exists(_STATIONS_FILE):
        with open(_STATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {sid: tuple(v) for sid, v in data.items()}
    return dict(_FALLBACK_STATIONS)


def station_for_link(link: str, stations: Optional[dict[str, tuple[str, str]]] = None
                      ) -> tuple[str, str]:
    """Dienststelle (Name, Region) anhand einer Meldungs-URL (.../pm/{id}/...)
    nachschlagen. Fuer die Mail-Quelle, die keine Dienststelle mitliefert."""
    stations = stations if stations is not None else load_stations()
    m = PM_LINK_RE.search(link or "")
    if m and m.group(1) in stations:
        return stations[m.group(1)]
    return ("", "")


def _clean(text: Optional[str]) -> str:
    """HTML-Reste entfernen, Entities sind bei feedparser/BeautifulSoup schon
    aufgeloest — hier nur noch Tag-Reste + Whitespace normalisieren
    (Aequivalent zu ranking.py:clean)."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_feed(station_id: str) -> list[dict[str, Any]]:
    """RSS-Feed einer Dienststelle holen (feedparser). Bei Fehler: leere Liste
    (Port von ranking.py:fetch_feed, feedparser statt ElementTree)."""
    url = f"https://www.presseportal.de/rss/dienststelle_{station_id}.rss2"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        parsed = feedparser.parse(raw)
    except Exception:
        return []

    items = []
    for entry in parsed.entries:
        dt = None
        if getattr(entry, "published_parsed", None):
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        summary = entry.get("summary", "") or ""
        content = ""
        if entry.get("content"):
            content = " ".join(c.get("value", "") for c in entry["content"])
        items.append({
            "title": _clean(entry.get("title", "")),
            "text": (_clean(summary) + " " + _clean(content)).strip(),
            "link": (entry.get("link") or "").strip(),
            "date": dt,
        })
    return items


def fetch_candidates(days_back: int = DAYS_BACK,
                      station_limit: Optional[int] = STATION_LIMIT) -> list[dict[str, Any]]:
    """Alle Dienststellen (oder die ersten N) abfragen -> rohe RSS-Kandidaten
    fuer den Ingest-Worker. Kein Scoring/Dedup hier (macht workers/ingest.py
    mit core/scoring.py). Port der Stufe-1-Schleife aus ranking.py:main()."""
    stations = load_stations()
    station_list = list(stations.items())
    if station_limit:
        station_list = station_list[:station_limit]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    candidates: list[dict[str, Any]] = []
    for sid, (name, region) in station_list:
        items = fetch_feed(sid)
        time.sleep(0.25)   # hoeflich zum Server bleiben (wie ranking.py)
        for it in items:
            if it["date"] and it["date"] < cutoff:
                continue
            candidates.append({
                "title": it["title"],
                "text": it["text"],
                "link": it["link"],
                "date": it["date"],
                "station": name,
                "region": region,
            })
    return candidates


def fetch_fulltext(url: str) -> str:
    """Komplette Meldungsseite holen und als reinen Text zurueckgeben.
    Port von ranking.py:fetch_fulltext — BeautifulSoup statt Regex, sonst
    gleiches Verhalten (Artikelbereich, sonst ganze Seite)."""
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "ignore")
    except Exception:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    article = soup.find("article") or soup
    return _clean(article.get_text(" "))
