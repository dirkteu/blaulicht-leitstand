# -*- coding: utf-8 -*-
"""
workers/extract.py  —  RQ-Job der Queue 'extract'
====================================================

Ablauf: Fall laden -> Volltext holen -> Fakten extrahieren -> sanitize ->
Fall aktualisieren -> Folge-Job 'script' einreihen (core.contracts.NEXT_QUEUE).

Team-2-Abhängigkeit: `core.presseportal.fetch_fulltext` wird parallel von Team 2
gebaut und existiert zum Zeitpunkt dieses Commits ggf. noch nicht. Der Import
erfolgt trotzdem (wie vorgegeben) — solange das Modul fehlt, schlägt der Import
dieses Worker-Moduls fehl, bis Team 2 core/presseportal.py liefert.
"""

from __future__ import annotations

import os

from redis import Redis
from rq import Queue

from core import parse
from core.contracts import Queue as QueueName, queue_timeout
from core.extract import extract_facts, sanitize
from core.presseportal import fetch_fulltext  # Team 2 — siehe Docstring
from core.supa import get_case, update_case


def extract(case_id: str) -> None:
    case = get_case(case_id)
    if not case:
        return

    try:
        fulltext = fetch_fulltext(case["link"])
        facts = extract_facts(fulltext, case["link"])
        facts = sanitize(facts)
        # Halluzinations-Check: Claudes Ort (aus dem Volltext) gegen den beim
        # Ingest aus dem Titel geparsten Ort. Bei Widerspruch -> Warnung setzen,
        # die im Review sichtbar wird. "" (kein Konflikt) leert eine evtl. alte.
        warnung = parse.ort_conflict(case.get("ort", ""), facts.get("ort", ""))
        if warnung:
            print(f"[extract] ⚠ {case_id}: {warnung}")
        update_case(case_id, {"facts": facts, "fulltext": fulltext, "warnung": warnung})
    except Exception as exc:
        update_case(case_id, {"error": f"extract: {exc}"})
        raise

    redis_conn = Redis.from_url(os.environ["REDIS_URL"])
    queue = Queue(QueueName.SCRIPT.value, connection=redis_conn,
                  default_timeout=queue_timeout(QueueName.SCRIPT))
    queue.enqueue("workers.script.script", case_id)
