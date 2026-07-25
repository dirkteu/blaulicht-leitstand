# -*- coding: utf-8 -*-
"""
workers/script.py  —  RQ-Job der Queue 'script'
==================================================

Ablauf: Fall laden -> spec aus den (bereits extrahierten) Fakten bauen ->
Fall aktualisieren -> Folge-Job 'tts' einreihen (core.contracts.NEXT_QUEUE).
"""

from __future__ import annotations

import os

from redis import Redis
from rq import Queue

from core.contracts import Queue as QueueName, queue_timeout
from core.script import build_spec
from core.supa import get_case, update_case


def script(case_id: str) -> None:
    case = get_case(case_id)
    if not case:
        return

    try:
        facts = case.get("facts") or {}
        spec = build_spec(case, facts)
        update_case(case_id, {"spec": spec})
    except Exception as exc:
        update_case(case_id, {"error": f"script: {exc}"})
        raise

    redis_conn = Redis.from_url(os.environ["REDIS_URL"])
    queue = Queue(QueueName.TTS.value, connection=redis_conn,
                  default_timeout=queue_timeout(QueueName.TTS))
    queue.enqueue("workers.tts.tts", case_id)
