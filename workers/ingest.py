# -*- coding: utf-8 -*-
"""
workers/ingest.py  —  Ingest-Job (Team 2)
=============================================

Wird per RQ in die Queue 'ingest' eingereiht (siehe scheduler/main.py und
core.contracts.Queue.INGEST): ingest("rss") bzw. ingest("mail").

Ablauf je Quelle:
    1. Rohe Kandidaten holen (core.presseportal bzw. core.mail)
    2. Score + Signale vergeben (core.scoring.score_case — Port aus ranking.py)
    3. Kandidaten unter der Schwelle (get_config()['min_score']) verwerfen
    4. Aehnliche Faelle entdoppeln (Titel-Aehnlichkeit, wie ranking.py:dedup)
    5. Jeden verbleibenden Fall als state='neu' anlegen (core.supa.insert_case)
       — Duplikate ueber den Link werden dort per unique-upsert ignoriert.

WICHTIG: Es wird hier NUR der Kandidat (Titel/Link/Score/Region/Hits) angelegt.
Volltext + Fakten holt die Analyse-Stufe (Team 3) spaeter selbst; das Werkzeug
dafuer (fetch_fulltext) liegt bereits in core/presseportal.py bereit.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from core import mail, presseportal, scoring, supa
from core.contracts import Source, State

DEDUP_RATIO = 0.72   # Titel-Aehnlichkeit ab der zwei Faelle als gleich gelten (wie ranking.py)


def _dedup(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aehnliche Faelle (gleiche Story, mehrere Quellen/Dienststellen)
    zusammenfassen; behaelt jeweils den Fall mit dem hoechsten Score.
    Port von ranking.py:dedup."""
    kept: list[dict[str, Any]] = []
    for c in sorted(cases, key=lambda x: x["score"], reverse=True):
        dup = False
        for k in kept:
            if SequenceMatcher(None, c["title"].lower(), k["title"].lower()).ratio() >= DEDUP_RATIO:
                dup = True
                break
        if not dup:
            kept.append(c)
    return kept


def ingest(source: str) -> dict[str, Any]:
    """Einen Ingest-Lauf fuer eine Quelle durchfuehren.
    source: 'rss' oder 'mail' (core.contracts.Source-Werte)."""
    if source == Source.RSS.value:
        raw = presseportal.fetch_candidates()
    elif source == Source.MAIL.value:
        raw = mail.fetch_candidates()
    else:
        raise ValueError(f"unbekannte Ingest-Quelle: {source!r}")

    min_score = int(supa.get_config().get("min_score", 40))

    scored: list[dict[str, Any]] = []
    for c in raw:
        if not c.get("link") or not c.get("title"):
            continue
        # Themenfilter fuer BEIDE Quellen (rss + mail): nur Faelle zum
        # konfigurierten Thema (Zigaretten) anhand des Titels. Beim Mail-Weg
        # ist das schon vorgefiltert (harmlos doppelt); beim RSS-Weg ist es DIE
        # Stelle, an der Presseportal auf „nur Zigaretten" eingegrenzt wird.
        # ALERT_TOPIC_KEYWORDS leer -> matches_topic() immer True (kein Filter).
        if not mail.matches_topic(c["title"]):
            continue
        full = f"{c['title']} {c.get('text', '')}"
        score, hits = scoring.score_case(full)
        if score < min_score:
            continue
        scored.append({
            "title": c["title"],
            "region": c.get("region") or c.get("station") or "",
            "link": c["link"],
            "score": score,
            "hits": hits,
        })

    deduped = _dedup(scored)

    created = 0
    for c in deduped:
        row = supa.insert_case({
            "source": source,
            "region": c["region"],
            "title": c["title"],
            "link": c["link"],
            "score": c["score"],
            "hits": c["hits"],
            "state": State.NEU.value,
        })
        if row:
            created += 1

    result = {
        "source": source,
        "candidates": len(raw),
        "ueber_schwelle": len(scored),
        "entdoppelt": len(deduped),
        "angelegt": created,
        "min_score": min_score,
    }
    print(f"[ingest] {result}")
    return result
