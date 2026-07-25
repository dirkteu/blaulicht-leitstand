# -*- coding: utf-8 -*-
"""
scheduler/main.py  —  Ingest-Zeitplan (Team 2)
==================================================

Dauerprozess (APScheduler BlockingScheduler, siehe docker-compose.yml,
Dienst 'scheduler'): reiht zu den Zeiten aus core.supa.get_config()
['ingest_times'] (Default '07:00,19:00') je einen 'rss'- und einen
'mail'-Ingest-Job in die RQ-Queue 'ingest' ein. workers/ingest.py fuehrt
den eigentlichen Job aus.

Start:  python -m scheduler.main
(TZ des Containers bestimmt die lokale Bedeutung von "07:00" — bei Bedarf
TZ=Europe/Berlin in .env/docker-compose setzen, wird hier bewusst nicht
hart codiert, um keine zusaetzliche tzdata-Abhaengigkeit zu erzwingen.)
"""
from __future__ import annotations

import os
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from redis import Redis
from rq import Queue

from core.contracts import Queue as QueueName, Source
from core.supa import get_config

DEFAULT_INGEST_TIMES = "07:00,19:00"


def _parse_times(raw: str) -> list[tuple[int, int]]:
    """'07:00,19:00' -> [(7, 0), (19, 0)]. Ungueltige Eintraege werden mit
    einer Warnung uebersprungen; ist am Ende nichts uebrig, gilt der Default."""
    out: list[tuple[int, int]] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            h, m = part.split(":")
            out.append((int(h), int(m)))
        except ValueError:
            print(f"[scheduler] ungueltige Ingest-Zeit ignoriert: {part!r}", file=sys.stderr)
    return out or _parse_times(DEFAULT_INGEST_TIMES)


def enqueue_ingest() -> None:
    """Wird zu jeder konfigurierten Uhrzeit ausgefuehrt: reiht je einen
    Ingest-Job pro Quelle (rss, mail) in die Queue 'ingest' ein."""
    redis_conn = Redis.from_url(os.environ["REDIS_URL"])
    q = Queue(QueueName.INGEST.value, connection=redis_conn)
    for source in (Source.RSS.value, Source.MAIL.value):
        job = q.enqueue("workers.ingest.ingest", source)
        print(f"[scheduler] Ingest-Job eingereiht: source={source} job_id={job.id}")


def build_scheduler() -> BlockingScheduler:
    config = get_config()
    times = _parse_times(config.get("ingest_times", DEFAULT_INGEST_TIMES))

    scheduler = BlockingScheduler()
    for h, m in times:
        scheduler.add_job(
            enqueue_ingest,
            CronTrigger(hour=h, minute=m),
            id=f"ingest_{h:02d}{m:02d}",
            replace_existing=True,
        )
        print(f"[scheduler] Ingest-Job geplant: {h:02d}:{m:02d}")
    return scheduler


def main() -> None:
    scheduler = build_scheduler()
    print("[scheduler] laeuft (BlockingScheduler) ... Strg+C zum Beenden.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
