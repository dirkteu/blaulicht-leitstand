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
        roh = extract_facts(fulltext, case["link"])
        # VOR dem Saeubern pruefen, ob Claude Methoden-/Anleitungs-Details
        # geliefert hat — sanitize() entfernt sie, aber im Review soll sichtbar
        # sein, dass etwas herausgefallen ist (Text kann dadurch knapper wirken).
        methode_drin = any(parse.hat_methode(str(roh.get(f) or ""))
                           for f in ("details", "werkzeug", "tat"))
        facts = sanitize(roh)
        # Halluzinations-Check: Claudes Ort (aus dem Volltext) gegen den beim
        # Ingest aus dem Titel geparsten Ort. Bei Widerspruch -> Warnung setzen,
        # die im Review sichtbar wird. "" (kein Konflikt) leert eine evtl. alte.
        warnungen = [parse.ort_conflict(case.get("ort", ""), facts.get("ort", ""))]
        if methode_drin:
            warnungen.append("Methoden-Details entfernt (Nachahmungs-Schutz) — Text bitte gegenlesen.")
        # Konjunktiv-Bruch: Satz beginnt distanziert, faellt nach „und" in den
        # Indikativ. Nur relevant, wenn jemand IDENTIFIZIERT ist — bei
        # unbekannten Taetern ist der Indikativ ohnehin korrekt, dann waere die
        # Warnung ein Fehlalarm. Wird NICHT automatisch korrigiert (Grammatik-
        # Umbau per Regex ist nicht sicher) — der Mensch formuliert nach.
        if not facts.get("ungeloest") and parse.konjunktiv_bruch(facts.get("details") or ""):
            warnungen.append("Konjunktiv bricht im Satz ab (Unschuldsvermutung) — bitte nachziehen.")
        # Rechtlich der ernste Fall: Es ist jemand identifiziert/gefasst, und der
        # Text behauptet trotzdem ohne jede Distanz. Automatisch reparieren laesst
        # sich das nicht (der assertive Satz bliebe stehen) — hier MUSS der Mensch
        # gegenlesen. Bei unbekannten Taetern ist der Indikativ dagegen korrekt.
        if not facts.get("ungeloest") and parse.distanz_fehlt(facts.get("details") or ""):
            warnungen.append("Beschuldigter benannt, aber Text ohne Distanz — Unschuldsvermutung prüfen!")
        warnung = " · ".join(w for w in warnungen if w)
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
