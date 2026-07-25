# -*- coding: utf-8 -*-
"""
workers/tts.py  —  RQ-Job Queue.TTS
====================================

Laedt den Fall + seine Spec, vertont sie (`core.tts.synth`, mit dem
Aussprache-Woerterbuch aus `core.supa.get_config()`), laedt die
resultierende Voice-mp3 in `Bucket.VOICE` hoch, schreibt `voice_url` +
die (jetzt synchronisierte) `spec` in den Fall zurueck und setzt den
State auf `review`.

KEIN automatischer Folge-Job: `contracts.NEXT_QUEUE[Queue.TTS]` ist
`None` — das ist das Gate „Freigabe Clip", der naechste Job (`render`)
wird erst nach der menschlichen Freigabe ueber die API eingereiht.
"""

from __future__ import annotations

import os

from core.contracts import Bucket, State
from core.supa import get_case, get_config, update_case, set_state, upload
from core.tts import synth


def tts(case_id: str) -> None:
    case = get_case(case_id)
    if not case:
        raise ValueError(f"Fall {case_id} nicht gefunden.")

    spec = case.get("spec")
    if not spec:
        set_state(case_id, State.IN_ANALYSE.value,
                   error="tts: 'spec' fehlt (script-Stufe ist noch nicht gelaufen).")
        return

    voice_local_path = None
    try:
        aussprache = (get_config() or {}).get("aussprache") or {}
        voice_local_path, updated_spec = synth(spec, aussprache)

        storage_path = f"{case_id}/voice.mp3"
        upload(Bucket.VOICE, storage_path, voice_local_path, content_type="audio/mpeg")

        update_case(case_id, {"voice_url": storage_path, "spec": updated_spec})
        set_state(case_id, State.REVIEW.value)
    except Exception as e:
        set_state(case_id, State.IN_ANALYSE.value, error=f"tts: {e}")
        raise
    finally:
        if voice_local_path and os.path.exists(voice_local_path):
            try:
                os.remove(voice_local_path)
            except OSError:
                pass
