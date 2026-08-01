# -*- coding: utf-8 -*-
"""
core/contracts.py  —  Die „Verträge" des Blaulicht-Leitstands
=============================================================

Zentrale Definitionen, gegen die ALLE Services (api + workers) bauen:
Zustände, Quellen, Queue-/Job-Namen, das Fakten-Schema und die Fall-Struktur.

Team 0 pflegt diese Datei. Ändert sich hier etwas, betrifft es alle Teams —
daher bewusst schlank und stabil halten.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Any


# ---------------------------------------------------------------------------
# Zustandsmaschine eines Falls (cases.state)
# ---------------------------------------------------------------------------
class State(str, Enum):
    NEU = "neu"                       # aus Ingest, Score >= Schwelle, in der Tabelle
    IN_ANALYSE = "in_analyse"         # Volltext -> Fakten -> Skript -> TTS laufen
    REVIEW = "review"                 # Text + Audio liegen vor, warten auf Freigabe
    IN_PRODUKTION = "in_produktion"   # Render läuft
    FERTIG = "fertig"                 # Clip fertig, Vorschau, wartet auf Freigabe
    VEROEFFENTLICHT = "veroeffentlicht"
    VERWORFEN = "verworfen"


class Source(str, Enum):
    RSS = "rss"
    MAIL = "mail"


# ---------------------------------------------------------------------------
# Queues (RQ auf Redis) — je Worker eine Queue
# ---------------------------------------------------------------------------
class Queue(str, Enum):
    INGEST = "ingest"
    EXTRACT = "extract"
    SCRIPT = "script"
    TTS = "tts"
    RENDER = "render"
    PUBLISH = "publish"


# Automatische Verkettung (welcher Job reiht welchen Folge-Job ein).
# None = Freigabe-Gate: die api reiht den nächsten Job erst nach dem Klick ein.
NEXT_QUEUE: dict[Queue, Optional[Queue]] = {
    Queue.INGEST:  None,            # danach: Fall wartet als NEU (Gate „Freigabe Analyse")
    Queue.EXTRACT: Queue.SCRIPT,
    Queue.SCRIPT:  Queue.TTS,
    Queue.TTS:     None,            # danach: REVIEW (Gate „Freigabe Clip")
    Queue.RENDER:  None,            # danach: FERTIG (Gate „Freigabe Veröffentlichung")
    Queue.PUBLISH: None,
}


# ---------------------------------------------------------------------------
# Fakten-Schema (Kern aus dem make.com-Flow, datenschutz-gehärtet)
# NIE: Namen, Straße, Hausnr., PLZ, Koordinaten. Ort nur Stadt-Ebene.
# ---------------------------------------------------------------------------
@dataclass
class Facts:
    tat: str = ""                       # z. B. „Automaten-Sprengung"
    datum: Optional[str] = None         # YYYY-MM-DD
    zeit: Optional[str] = None          # HH:MM
    ort: str = ""                       # nur Stadt
    taeter_anzahl: Optional[int] = None
    werkzeug: Optional[str] = None
    beute_eur: Optional[int] = None
    schaden_eur: Optional[int] = None
    details: str = ""                   # 1 Satz, ganze Sätze
    ungeloest: bool = False
    quelle_link: str = ""

    # Felder, die NIEMALS befüllt werden dürfen (Schranke in sanitize()).
    VERBOTEN = ("name", "strasse", "hausnummer", "plz", "lat", "lon", "latitude", "longitude")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Fall-Struktur (Spiegel der Supabase-Tabelle `cases`)
# ---------------------------------------------------------------------------
@dataclass
class Case:
    id: Optional[str] = None
    source: str = Source.RSS.value
    region: str = ""                    # Stadt/Dienststelle (RSS) bzw. leer (Mail)
    ort: str = ""                       # aus Titel vorgeparst (core.parse), "" = unklar
    tat: str = ""                       # aus Titel vorgeparst (core.parse), "" = unklar
    title: str = ""
    link: str = ""
    score: int = 0
    hits: list[str] = field(default_factory=list)
    state: str = State.NEU.value
    fulltext: Optional[str] = None
    facts: Optional[dict[str, Any]] = None   # Facts.to_dict()
    spec: Optional[dict[str, Any]] = None    # Video-Bauanleitung (Szenen)
    voice_url: Optional[str] = None
    video_url: Optional[str] = None
    thumb_url: Optional[str] = None
    error: Optional[str] = None
    warnung: str = ""                   # Halluzinations-Check: Titel-Ort ≠ Analyse-Ort (core.parse.ort_conflict)
    platform_ids: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Job-Payload — was in die Queue eingereiht wird
# ---------------------------------------------------------------------------
@dataclass
class Job:
    case_id: str                        # welcher Fall
    queue: str                          # Queue-Wert (z. B. „extract")
    reason: str = "auto"                # „auto" (Verkettung) oder „freigabe:<gate>"


# Job-Timeouts je Stufe (Sekunden). Der RQ-Default (180 s) ist fuer mehrere
# Stufen zu knapp und killt sonst laufende Jobs mitten in der Arbeit:
#   - TTS: Gemini-Gratis-Limit 3 Requests/Min + Backoff, mehrere Szenen.
#   - Render: ffmpeg-Compositing.
#   - Ingest: ~270 Dienststellen sequentiell (~3 min).
# Wird als default_timeout an die jeweilige RQ-Queue gehaengt (api, workers,
# scheduler) und beim Enqueue in den Job uebernommen.
QUEUE_TIMEOUTS: dict[Queue, int] = {
    Queue.INGEST:  900,
    Queue.EXTRACT: 300,
    Queue.SCRIPT:  300,
    Queue.TTS:     1200,
    Queue.RENDER:  900,
    Queue.PUBLISH: 300,
}


def queue_timeout(q: "Queue | str") -> int:
    """Job-Timeout (Sekunden) fuer eine Queue; grosszuegiger Fallback 600 s."""
    if isinstance(q, str):
        try:
            q = Queue(q)
        except ValueError:
            return 600
    return QUEUE_TIMEOUTS.get(q, 600)


# Storage-Buckets (Supabase Storage)
class Bucket(str, Enum):
    BROLL = "broll"       # Master-Clips (nur lesen im Render!)
    VOICE = "voice"
    RENDERS = "renders"
    THUMBS = "thumbs"


# B-Roll-Kategorien (Namensmuster: broll_<kategorie>_NN.mp4).
# `wetter` gestrichen per BROLL_PLAN Beschluss 1 (umgesetzt 01.08.2026).
BROLL_KATEGORIEN = ("strasse", "blaulicht", "cctv", "kulisse", "effekt")

# Schema in Postgres, in dem die Leitstand-Tabellen liegen (kollisionsfrei).
DB_SCHEMA = "blaulicht"
