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
    4. Doppler entfernen — quellen- UND laufuebergreifend (siehe _dedup):
       a) globale Titel-Aehnlichkeit >= DEDUP_RATIO (wie ranking.py), zusaetzlich
       b) Block-Dedup: gleicher Ort (Stadt) + Tat + Kalenderwoche und beide OHNE
          Serien-Marker → gleiche Story aus einer anderen Quelle (niedrigere
          Schwelle). Serien-Folgefaelle („wieder"/„erneut") bleiben eigenstaendig.
       Verglichen wird gegen den aktuellen Lauf UND die lebenden Faelle der
       letzten Tage (supa.recent_cases) — so faengt der Mail-Lauf Doppler des
       RSS-Laufs und umgekehrt.
    5. Jeden verbleibenden Fall als state='neu' anlegen (core.supa.insert_case)
       — Duplikate ueber den Link werden dort per unique-upsert ignoriert.

WICHTIG: Es wird hier NUR der Kandidat (Titel/Link/Score/Region/Hits) angelegt.
Volltext + Fakten holt die Analyse-Stufe (Team 3) spaeter selbst; das Werkzeug
dafuer (fetch_fulltext) liegt bereits in core/presseportal.py bereit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from core import mail, parse, presseportal, scoring, supa
from core.contracts import Source, State

DEDUP_RATIO = 0.72        # globale Titel-Aehnlichkeit ab der zwei Faelle gleich sind (wie ranking.py)
CROSS_BLOCK_RATIO = 0.55  # niedrigere Schwelle INNERHALB gleichem (ort+tat+woche)-Block


def _iso_week(dt: datetime) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}-{w:02d}"


def _week_of(created_at: str | None) -> str:
    """ISO-Woche aus einem ISO-Zeitstempel; faellt auf 'jetzt' zurueck."""
    if not created_at:
        return _iso_week(datetime.now(timezone.utc))
    try:
        return _iso_week(datetime.fromisoformat(created_at.replace("Z", "+00:00")))
    except ValueError:
        return _iso_week(datetime.now(timezone.utc))


def _same_story(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True, wenn a und b denselben Vorfall meinen (Doppler). Erwartet je
    Dict mit title/ort/tat/week."""
    ta, tb = a["title"], b["title"]
    # a) global: hohe Titel-Aehnlichkeit reicht (auch ohne Ort/Tat)
    if SequenceMatcher(None, ta.lower(), tb.lower()).ratio() >= DEDUP_RATIO:
        return True
    # b) Block: gleicher Ort (Stadt, nicht Bundesland) + Tat + Woche, beide
    #    OHNE Serien-Marker → gleiche Story aus anderer Quelle, mildere Schwelle.
    if (parse.is_blockable_ort(a.get("ort", "")) and a.get("ort") == b.get("ort")
            and a.get("tat") and a.get("tat") == b.get("tat")
            and a.get("week") == b.get("week")
            and not parse.is_serial(ta) and not parse.is_serial(tb)):
        if SequenceMatcher(None, parse.norm_title(ta), parse.norm_title(tb)).ratio() >= CROSS_BLOCK_RATIO:
            return True
    return False


def _dedup(cases: list[dict[str, Any]],
           existing: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Doppler entfernen — gegen den aktuellen Lauf UND bereits vorhandene Faelle
    (`existing`, andere Quelle / frueherer Lauf). Behaelt je Story den hoechsten
    Score. Gibt (behaltene, anzahl_gegen_bestand_verworfen) zurueck."""
    kept: list[dict[str, Any]] = []
    dropped_vs_existing = 0
    for c in sorted(cases, key=lambda x: x["score"], reverse=True):
        if any(_same_story(c, k) for k in kept):
            continue
        if any(_same_story(c, e) for e in existing):
            dropped_vs_existing += 1
            continue
        kept.append(c)
    return kept, dropped_vs_existing


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
    now_week = _iso_week(datetime.now(timezone.utc))

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
        region = c.get("region") or c.get("station") or ""
        # Vorparser aus dem Titel (kein Claude): Ort (Stadt-Ebene) + Tat.
        # Findet er nichts -> "" , der Fall laeuft ganz normal weiter.
        scored.append({
            "title": c["title"],
            "region": region,
            "ort": parse.parse_ort(c["title"], fallback_region=region),
            "tat": parse.parse_tat(c["title"]),
            "link": c["link"],
            "score": score,
            "hits": hits,
            "week": now_week,
        })

    # Bestand fuer den quellen-/laufuebergreifenden Abgleich (Woche vorberechnen).
    existing = supa.recent_cases(days=10)
    for e in existing:
        e["week"] = _week_of(e.get("created_at"))
    deduped, dropped_vs_existing = _dedup(scored, existing)

    created = 0
    for c in deduped:
        row = supa.insert_case({
            "source": source,
            "region": c["region"],
            "ort": c["ort"],
            "tat": c["tat"],
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
        "doppler_gg_bestand": dropped_vs_existing,
        "angelegt": created,
        "min_score": min_score,
    }
    print(f"[ingest] {result}")
    return result
