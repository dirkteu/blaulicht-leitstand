# -*- coding: utf-8 -*-
"""
workers/render.py  —  RQ-Job Queue.RENDER
===========================================

Laedt den Fall, zieht das in der Spec referenzierte B-Roll (NUR LESEN!)
sowie die Voice-mp3 per `core.supa.download` in lokale Temp-Dateien,
rendert per `core.render.render`, laedt das Ergebnis in `Bucket.RENDERS`
hoch, schreibt `video_url` in den Fall zurueck und setzt den State auf
`fertig` (Gate „Freigabe Veroeffentlichung" — kein automatischer
Folge-Job, `contracts.NEXT_QUEUE[Queue.RENDER]` ist `None`).

SICHERHEIT (nach dem Datenverlust): der `broll`-Bucket wird
AUSSCHLIESSLICH gelesen (`core.supa.download` -> Temp-Datei). Es gibt
hier keinen einzigen Schreib-/Loesch-Aufruf auf `Bucket.BROLL`. Alle
Temp-Dateien (B-Roll-Kopien, Voice-Kopie, gerendertes Video) werden im
`finally`-Block aufgeraeumt — unabhaengig davon, ob der Job erfolgreich
war oder fehlgeschlagen ist.
"""

from __future__ import annotations

import os

from core.contracts import Bucket, State
from core.supa import get_case, update_case, set_state, upload, download
from core.render import render as render_video


def render(case_id: str) -> None:
    case = get_case(case_id)
    if not case:
        raise ValueError(f"Fall {case_id} nicht gefunden.")

    spec = case.get("spec")
    if not spec:
        set_state(case_id, State.REVIEW.value,
                   error="render: 'spec' fehlt (tts-Stufe ist noch nicht gelaufen).")
        return

    facts = case.get("facts") or {}
    voice_url = case.get("voice_url")

    temp_files: list[str] = []
    broll_local_paths: dict[str, str] = {}
    voice_local_path = None

    try:
        # B-Roll je Szene NUR LESEND aus Storage ziehen (dedupliziert ueber
        # Dateiname, falls mehrere Szenen denselben Clip verwenden).
        # `broll` ist eine Clip-Liste; alte Specs tragen einen String.
        needed: set[str] = set()
        for s in spec.get("scenes", []):
            b = s.get("broll") or []
            needed.update([b] if isinstance(b, str) else b)
        for name in sorted(n for n in needed if n):
            try:
                local = download(Bucket.BROLL, name)
            except Exception:
                # Clip fehlt im Bucket -> core.render faellt automatisch auf
                # die Farb-Kulisse der Szenen-Rolle zurueck (kein harter Fehler).
                continue
            temp_files.append(local)
            broll_local_paths[name] = local

        if voice_url:
            voice_local_path = download(Bucket.VOICE, voice_url)
            temp_files.append(voice_local_path)

        video_local_path = render_video(spec, facts, broll_local_paths, voice_local_path)
        temp_files.append(video_local_path)

        storage_path = f"{case_id}/video.mp4"
        upload(Bucket.RENDERS, storage_path, video_local_path, content_type="video/mp4")

        update_case(case_id, {"video_url": storage_path})
        set_state(case_id, State.FERTIG.value)
    except Exception as e:
        set_state(case_id, State.REVIEW.value, error=f"render: {e}")
        raise
    finally:
        for p in temp_files:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
