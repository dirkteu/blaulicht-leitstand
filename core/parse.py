# -*- coding: utf-8 -*-
"""
core/parse.py  —  Titel-Vorparser (Team 2: Ingest)
===================================================

Zieht **ohne** Claude/Volltext zwei Dinge aus der Schlagzeile, die dort fast
immer schon drinstehen: den **Ort** (Stadt-Ebene) und die **Tat** (grobe
Kategorie). Reine Regex, kein I/O. Genutzt in workers/ingest.py.

Design-Regel (bewusst): Findet der Parser nichts, gibt er "" zurueck — der Fall
laeuft dann voellig normal weiter, die spaetere Analyse-Stufe (Claude) fuellt
die Fakten. Es wird NIE geraten. Ort bleibt auf Stadt-/Kreis-Ebene, damit die
Datenschutz-Regel (core.contracts.Facts) eingehalten bleibt.

    ort = parse_ort(title, fallback_region=case_region)   # "" wenn unklar
    tat = parse_tat(title)                                 # "" wenn unklar
"""
from __future__ import annotations

import re

# --- Ort ---------------------------------------------------------------------

# Ein Stadtname: Großbuchstabe + Kleinbuchstaben, optional Bindestrich-Teil
# (Neustadt-Glewe), optional Umlaute.
_CITY = r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?"

# Groß geschrieben, aber KEIN Ort — verhindert Fehlgriffe im Titel.
_STOP = {
    "zeugenaufruf", "sprengung", "diebstahl", "bewaffneter", "versuchte", "versuchter",
    "unbekannte", "unbekannter", "wieder", "erneut", "nachtragsmeldung",
    "zigarettenautomat", "zigarettenautomaten", "tabakautomat", "geldautomat", "automat",
    "krach", "regionalnachrichten", "innerhalb", "mann", "frau", "polizei", "news",
    "der", "die", "das", "den", "dem", "nacht", "luft", "gesicht", "folge", "höhe",
    "raub", "tabak", "presseshop", "mit", "guten", "nachrichten", "panorama",
    "kriminalpolizei", "diebe", "täter", "verdächtige",
}

# Landes-Kürzel: gültige (grobe) Ortsangabe, aber kein Stadt-Niveau -> geflaggt.
_BUNDESLAND = {"mv", "nrw", "rlp", "bw", "by", "sh", "he", "ni", "sn", "st", "th", "bb", "hb", "hh", "sl"}


def parse_ort(title: str, fallback_region: str = "") -> str:
    """Ort (Stadt/Kreis) aus dem Titel; "" wenn nichts Verlaessliches gefunden.
    fallback_region: bei RSS steht hier die Dienststelle (z. B. Köln) — wird nur
    genutzt, wenn der Titel selbst keinen Ort hergibt."""
    ort, _ = parse_ort_ex(title, fallback_region)
    return ort


def parse_ort_ex(title: str, fallback_region: str = "") -> tuple[str, str]:
    """Wie parse_ort, gibt zusaetzlich die getroffene Methode zurueck
    ('in-muster', 'präfix', 'polizei-news', 'pol-präfix', 'kreis',
    'bundesland', 'region-fallback', '—'). Nützlich für Diagnose/Flagging."""
    t = title or ""

    # "Polizei-News <Stadt>,"
    m = re.search(r"Polizei-News\s+(" + _CITY + r")", t)
    if m:
        return m.group(1), "polizei-news"

    # "Kreis <X>"
    m = re.search(r"(Kreis\s+" + _CITY + r")", t)
    if m:
        return m.group(1), "kreis"

    # "POL-XX: <Stadt> -"  (evtl. Nummern-Token wie '260723-1-K' überspringen)
    m = re.search(r"POL-[A-Z]+:\s*(?:[\dA-Z][\dA-Z-]*\s+)?(" + _CITY + r")\s*-", t)
    if m and m.group(1).lower() not in _STOP:
        return m.group(1), "pol-präfix"

    # Präfix "<Stadt>:" oder "<Stadt>." am Zeilenanfang
    m = re.match(r"(" + _CITY + r")[.:]\s", t)
    if m and m.group(1).lower() not in _STOP:
        return m.group(1), "präfix"

    # "in <Stadt>"  (auch Landes-Kürzel wie MV)
    for mm in re.finditer(r"\bin\s+(" + _CITY + r"|[A-ZÄÖÜ]{2,})\b", t):
        cand = mm.group(1)
        if cand.lower() in _STOP:
            continue
        if cand.lower() in _BUNDESLAND:
            return cand, "bundesland"
        return cand, "in-muster"

    # Fallback: bekannte Region (RSS-Dienststelle)
    if fallback_region:
        return fallback_region, "region-fallback"

    return "", "—"


# --- Tat ---------------------------------------------------------------------

# Reihenfolge = Priorität. Erste passende Kategorie gewinnt. "" = unklar.
# Bewusst praeziser als scoring.classify(): "geschlagen" -> Körperverletzung,
# nicht faelschlich "Sprengung" nur weil das Wort "Automat" im Titel steht.
_TAT_PATTERNS: list[tuple[str, str]] = [
    ("Sprengung",       r"gesprengt|sprengung|sprengen|explosion|explodier|in die luft"),
    ("Raub",            r"überfall|raubüberfall|\braub\b|beraubt|ausgeraubt"),
    ("Körperverletzung", r"geschlagen|schläge|körperverletz|niedergeschlagen|attackiert|verletzt|ins gesicht"),
    ("Schusswaffe",     r"schüsse|erschoss|geschossen|schusswaffe|pistole"),
    ("Einbruch",        r"einbruch|einbrecher|eingebrochen|aufgebrochen"),
    ("Diebstahl",       r"diebstahl|gestohlen|entwendet|geklaut"),
    ("Brandstiftung",   r"brand|brandstiftung|feuer gelegt|in flammen"),
]


def parse_tat(title: str) -> str:
    """Grobe Tat-Kategorie aus dem Titel; "" wenn nichts Eindeutiges passt."""
    t = (title or "").lower()
    for label, pattern in _TAT_PATTERNS:
        if re.search(pattern, t):
            return label
    return ""


# --- Dedup-Helfer (quellen-uebergreifend, in workers/ingest.py genutzt) -------

# „Serien"-Marker: signalisiert einen EIGENEN Folgefall am selben Ort (z. B.
# zweite Sprengung binnen 24 h). Solche Faelle duerfen NICHT als Doppler eines
# anderen Berichts weggemergt werden — sonst geht der Serien-Aufhaenger verloren.
_SERIAL_RE = re.compile(
    r"\bwieder\b|\berneut\w*|\bweitere[rs]?\b|\bnächste[rs]?\b|in folge|tatserie|"
    r"innerhalb\s+(?:von\s+)?\d+\s+(?:stunden|tagen)|zum\s+\w+\s+mal",
    re.IGNORECASE,
)


def is_serial(title: str) -> bool:
    """True, wenn der Titel einen Serien-/Folge-Marker traegt (eigener Fall)."""
    return bool(_SERIAL_RE.search(title or ""))


def is_blockable_ort(ort: str) -> bool:
    """True, wenn `ort` fuer Block-Dedup taugt: nicht leer und kein grobes
    Bundesland-Kuerzel (bei 'MV' koennten zwei Staedte gemeint sein → zu grob)."""
    o = (ort or "").strip().lower()
    return bool(o) and o not in _BUNDESLAND


def is_precise_ort(ort: str) -> bool:
    """True, wenn `ort` eine praezise Stadt/Gemeinde ist (nicht leer, kein
    Bundesland-Kuerzel, kein 'Kreis …'). Nur solche eignen sich fuer den
    Halluzinations-Abgleich gegen Claudes Ort — grobe Angaben (MV, Kreis X)
    duerfen legitim von Claudes Stadt-Angabe abweichen."""
    o = (ort or "").strip().lower()
    if not is_blockable_ort(o):
        return False
    return not o.startswith(("kreis ", "landkreis "))


def _norm_ort(ort: str) -> str:
    o = (ort or "").strip().lower()
    o = re.sub(r"^(kreis|landkreis|stadt|gemeinde)\s+", "", o)
    o = re.sub(r"\s*\(.*?\)\s*", "", o)          # "Ahlen (Westf.)" -> "ahlen"
    return o.strip()


def ort_conflict(title_ort: str, claude_ort: str) -> str:
    """Vergleicht den beim Ingest aus dem Titel geparsten Ort mit dem Ort, den
    Claude aus dem Volltext gezogen hat. Gibt eine kurze Warnung zurueck, wenn
    beide praezise sind, aber NICHT zusammenpassen — sonst "".

    Bewusst konservativ (wenig Fehlalarme): flaggt nur, wenn der Titel-Ort
    praezise ist (is_precise_ort) und Claude ueberhaupt einen Ort geliefert hat,
    und weder der eine im anderen steckt (Stadtteil/Zusatz-Toleranz)."""
    co = (claude_ort or "").strip()
    if not co or not is_precise_ort(title_ort):
        return ""
    a, b = _norm_ort(title_ort), _norm_ort(co)
    if not a or not b or a == b or a in b or b in a:
        return ""
    return f"Ort-Konflikt: Titel „{title_ort.strip()}“ ≠ Analyse „{co}“ — bitte prüfen."


def norm_title(title: str) -> str:
    """Titel fuers Aehnlichkeits-Matching normalisieren: Behoerden-/Medien-Praefixe,
    Datums-/Aktenzeichen-Tokens und Sonderzeichen raus, damit derselbe Vorfall aus
    verschiedenen Quellen aehnlich aussieht."""
    t = (title or "").lower()
    t = re.sub(r"pol-\w+:|polizei-news|regionalnachrichten|nachtragsmeldung", " ", t)
    t = re.sub(r"\d{2}\.\d{2}\.\d{2,4}|\d{6}-\d-\w", " ", t)
    t = re.sub(r"[^a-zäöüß ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# METHODEN-SPERRE — keine Nachahmungs-Anleitung im gesprochenen Text
# ---------------------------------------------------------------------------
# Plattform-Richtlinien (TikTok/YouTube) verbieten ANLEITUNGEN zu schaedlichen
# Taten — nicht die Benennung der Tat. Deshalb bewusst zweigeteilt:
#
#   ERLAUBT (Kategorie, steht so auch in jeder Polizeimeldung):
#       „gesprengt", „Sprengung", „Sprengsatz", „Explosion", „Winkelschleifer",
#       „Aufbruchwerkzeug", „Brechstange"
#   GESPERRT (Rezept):
#       Stoffarten, Mengen, Zufuehrung, Zuendung, Schrittfolge
#
# Nicht zu verwechseln mit „Shadowban-Wortlisten", die kursieren: Begriffe wie
# „gesprengt" durch „Gasgemisch" zu ersetzen macht es SCHLIMMER — das benennt
# die Methode praeziser und rueckt damit erst recht Richtung Anleitung.
_METHODE_RE = re.compile(
    r"""(?ix)
    \b(?:
        gasgemisch | gasflasche[n]? | butan | propan | acetylen | sauerstoffflasche[n]?
      | schwarzpulver | nitropenta | nitrat(?:mischung)?
      # Typ-Bezeichnungen von Sprengstoff (Fest-, Feststoff-, Flüssig-,
      # Plastik-…). Das blosse "Sprengstoff" bleibt ERLAUBT — es ist der
      # Oberbegriff und steht so in jeder Polizeimeldung; erst die Typangabe
      # macht daraus eine Stoffart.
      | \w+sprengstoff
      | pyrotechnische[nrms]?\s+satz | blitzknallsatz
      | z(?:ü|u|ue)ndschnur | sprengschnur | z(?:ü|u|ue)nder | detonator
      | fernz(?:ü|u|ue)ndung
      | \d+\s*(?:gramm|g|kg|kilo|liter|l)\s+(?:spreng|gas|pulver)\w*
    )\b
    | \b(?:einge|zuge)leitet\b
    | \b(?:ü|ue)ber\s+(?:einen|ein|mehrere)\s+Schl(?:ä|a|ae)uch\w*
    """,
)

# Satzgrenzen fuer das gezielte Streichen (gleiche Logik wie core.script).
_SATZ_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def drop_saetze(text: str, muster: "re.Pattern[str]") -> str:
    """Alle Saetze entfernen, in denen `muster` trifft — bewusst KEIN Platzhalter.

    Warum satzweise statt Ersetzen: Diese Felder (`details`, `werkzeug`, `tat`)
    landen im Voiceover. Ein eingesetztes „[entfernt]" wuerde von der TTS
    woertlich vorgelesen („eckige Klammer entfernt"). Faellt dagegen der ganze
    Satz weg, bleibt gesprochener Text uebrig, der sich natuerlich anhoert.

    Trifft das Muster in JEDEM Satz (typisch bei kurzen Feldern wie `werkzeug`),
    bleibt "" zurueck — die aufrufende Stelle laesst die Zeile dann ganz weg.
    """
    t = (text or "").strip()
    if not t or not muster.search(t):
        return t
    saetze = [s.strip() for s in _SATZ_SPLIT_RE.split(t) if s.strip()]
    return " ".join(s for s in saetze if not muster.search(s)).strip()


def hat_methode(text: str) -> bool:
    """True, wenn der Text Methoden-/Anleitungs-Details enthaelt (Stoffart,
    Menge, Zufuehrung, Zuendung). Detektor fuer die Review-Warnung."""
    return bool(_METHODE_RE.search(text or ""))


def entschaerfe_methode(text: str) -> str:
    """Saetze mit Methoden-/Anleitungs-Details entfernen (siehe drop_saetze)."""
    return drop_saetze(text, _METHODE_RE)


# ---------------------------------------------------------------------------
# FAHNDUNGSSAETZE — gehoeren ans Ende des Clips, nicht in die Tat-Schilderung
# ---------------------------------------------------------------------------
# Saetze ueber Fahndung und Ermittlungsstand blaehen den laengsten Abschnitt auf
# (`story` lief dadurch 18,5 s) und bremsen die Erzaehlung genau dort, wo sie
# laufen soll. Inhaltlich gehoeren sie zum Schluss: „Fahndung erfolglos" und
# „von den Taetern fehlt jede Spur" sind dieselbe Aussage.
#
# BEWUSST NICHT im Muster: „fluechtig"/„floh"/„Flucht". Die Flucht IST das
# Tatgeschehen und muss in der Erzaehlung bleiben — nimmt man sie mit heraus,
# bleibt von der Story nichts uebrig.
_FAHNDUNG_RE = re.compile(
    r"\bfahndung\w*|\bermittl\w+|\bhubschrauber\w*|\bsp[üu]rhund\w*"
    r"|\bzeugen\s+(?:werden\s+)?gesucht|\bsachdienlich\w*"
    r"|\bhinweise?\s+(?:nimmt|an\s+die|erbeten)"
    r"|\bkriminalpolizei\b|\bkripo\b|\bpolizei\s+sucht\b",
    re.I,
)


def trenne_fahndung(text: str) -> tuple[str, str]:
    """Text in (Tathergang, Fahndung) zerlegen.

    Rueckgabe ist immer ein Paar; der zweite Teil ist "" wenn nichts passt.

    SICHERHEITSNETZ: Wuerde der Tathergang dabei komplett leer werden (alle
    Saetze sind Fahndungssaetze, typisch bei duennen Meldungen), bleibt der Text
    unveraendert und der zweite Teil leer. Lieber eine etwas laengere Story als
    eine leere.
    """
    t = (text or "").strip()
    if not t:
        return "", ""
    saetze = [s.strip() for s in _SATZ_SPLIT_RE.split(t) if s.strip()]
    rest = [s for s in saetze if not _FAHNDUNG_RE.search(s)]
    fahndung = [s for s in saetze if _FAHNDUNG_RE.search(s)]
    if not rest or not fahndung:
        return t, ""
    return " ".join(rest), " ".join(fahndung)


# ---------------------------------------------------------------------------
# UNSCHULDSVERMUTUNG — journalistische Distanz im erzaehlenden Text
# ---------------------------------------------------------------------------
# NUR echte Distanzierungen zur SCHULD zaehlen. Bewusst NICHT dabei:
# „unbekannte Taeter", „Ermittlungen", „Zeugen" — die sagen nur, dass jemand
# nicht identifiziert ist bzw. ermittelt wird. „Zwei unbekannte Taeter sprengten
# ..." behauptet die Tat weiterhin als Tatsache und darf NICHT als ausreichend
# gelten. (Genau dieser Fall war beim ersten Entwurf durchgerutscht.)
#
# Genutzt von core.script (Fallback-Satz bauen) und core.lektor (Nachkontrolle:
# ein Lektor-Vorschlag darf die Distanzierung nicht wegformulieren).
# Alle Mittel, die im Deutschen echte Distanz zur SCHULD herstellen. Bewusst
# breit, damit der Extract-Prompt abwechseln kann statt dreimal „sollen" zu
# schreiben — die Pruefung darf die Alternativen nicht als fehlende Distanz
# missverstehen.
_DISTANZ_RE = re.compile(
    r"mutmaßlich|angeblich|verdächtig|offenbar"
    r"|\bsollen\b|\bsoll\b"
    r"|\bhätten?\b|\bseien\b|\bsei\b|\bwären?\b|\bhabe\b"          # Konjunktiv I/II
    r"|\blaut\s+(?:der\s+|den\s+)?(?:polizei|ermittl|behörd|angaben|staatsanwalt)"
    r"|nach\s+(?:angaben|erkenntnis|ermittl)|zufolge",
    re.I,
)


def distanz_fehlt(*texte: str) -> bool:
    """True, wenn in KEINEM der Texte eine Distanzierung zur Schuld steht."""
    return not _DISTANZ_RE.search(" ".join(t for t in texte if t))


# Konjunktiv-Bruch: Ein Satz startet distanziert („sollen ... "), faellt aber
# nach einem „und" in den Indikativ zurueck — der zweite Teilsatz behauptet dann
# wieder als Tatsache. distanz_fehlt() greift hier NICHT, weil „sollen" im
# selben Satz ja vorkommt. Beispiel aus der Praxis:
#   „Sie sollen Geldkassetten mitgenommen und SIND mit Fahrraedern geflohen."
# Bewusst nur eine Warnung, keine automatische Korrektur: Grammatik umbauen ist
# per Regex nicht sicher moeglich — der Mensch entscheidet im Review.
_SOLL_RE = re.compile(r"\bsoll(?:en)?\b", re.I)
_INDIKATIV_ANHANG_RE = re.compile(
    r"\bund\s+(?:sind|ist|hat|haben|war|waren|wurde|wurden)\b", re.I)


def konjunktiv_bruch(text: str) -> bool:
    """True, wenn ein Satz mit „sollen" spaeter nach „und" in den Indikativ faellt."""
    for satz in _SATZ_SPLIT_RE.split(text or ""):
        m = _SOLL_RE.search(satz)
        if not m:
            continue
        if _INDIKATIV_ANHANG_RE.search(satz, m.end()):
            return True
    return False
