# -*- coding: utf-8 -*-
"""
core/script.py  —  Stufe 3: Fakten -> Video-Bauanleitung (spec)
=================================================================

PORTIERT `assemble_spec` + `pick_broll` aus dem Prototyp `script_gen.py`,
speist aber echte Fakten (core.contracts.Facts) statt eines Claude-generierten
Zwischen-„script" ein:

    - echte Uhrzeit im Hook
    - Werkzeug in der Story-Szene
    - Beute/Schaden in der Zahlen-Szene
    - ungelöst-Status im Cliffhanger

    build_spec(case, facts) -> spec   # 5 Szenen: hook, eskalation, story, zahlen, cliffhanger

Deterministisch: B-Roll-Wahl hängt nur vom Titel/Link ab (hashlib.md5-Seed),
damit derselbe Fall bei erneutem Lauf dieselbe Bauanleitung erhält.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Optional

CHANNEL = "Nachtknall"
DURATION = 42  # Ziel-Länge in Sekunden (Richtwert, siehe durs unten)

# ---------------------------------------------------------------------------
# B-ROLL-BIBLIOTHEK — PORTIERT aus script_gen.py (Dateinamen wie im Bucket `broll`)
# ---------------------------------------------------------------------------
ASSETS = {
    "street":    [f"broll_strasse_{i:02d}.mp4"   for i in range(1, 9)],
    "blaulicht": [f"broll_blaulicht_{i:02d}.mp4" for i in range(1, 8)],
    "cctv":      [f"broll_cctv_{i:02d}.mp4"      for i in range(1, 7)],
    "weather":   [f"broll_wetter_{i:02d}.mp4"    for i in range(1, 8)],
    "location":  [f"broll_kulisse_{i:02d}.mp4"   for i in range(1, 9)],
    "effect":    [f"broll_effekt_{i:02d}.mp4"    for i in range(1, 8)],
}

# Welche B-Roll-Kategorie passt zu welcher Szenen-Rolle
ROLE_BROLL = {
    "hook":        "blaulicht",
    "eskalation":  "effect",
    "story":       "cctv",
    "zahlen":      "location",
    "cliffhanger": "street",
}

# Feste Szenen-Dauern (Summe ~ DURATION), wie im Prototyp
SCENE_DURATIONS = {"hook": 3, "eskalation": 7, "story": 18, "zahlen": 8, "cliffhanger": 6}
SCENE_SFX = {"hook": "boom", "eskalation": "sirene", "story": "herzschlag",
             "zahlen": "herzschlag", "cliffhanger": "stille"}


def pick_broll(role: str, seed: int) -> str:
    """Deterministisch aus der Bibliothek wählen (variiert pro Fall)."""
    cat = ROLE_BROLL.get(role, "street")
    pool = ASSETS[cat]
    return pool[seed % len(pool)]


# ---------------------------------------------------------------------------
# SZENEN-TEXTE — aus echten Fakten gebaut (keine Titel-Keyword-Heuristik mehr)
# ---------------------------------------------------------------------------
def _line_hook(ort: str, zeit: Optional[str], tat: str) -> str:
    when = f"Um {zeit} Uhr" if zeit else "Mitten in der Nacht"
    return f"{when} in {ort}: {tat or 'ein Einsatz, der die Polizei auf den Plan ruft'}."


def _split_sentences(details: str) -> list[str]:
    if not details:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", details) if s.strip()]


def _line_eskalation(tat: str, first_sentence: str) -> str:
    if first_sentence:
        return first_sentence.rstrip(".") + "."
    return f"Die Lage eskaliert schnell — {(tat or 'der Vorfall').strip().lower()} sorgt für einen Großeinsatz."


def _line_story(werkzeug: Optional[str], rest_sentences: str, tat: str) -> str:
    prefix = f"Mit {werkzeug} gehen die Täter vor. " if werkzeug else ""
    rest = rest_sentences or f"Die Polizei ermittelt die Hintergründe der {tat or 'Tat'}."
    return (prefix + rest).strip()


def _line_zahlen(beute: Optional[int], schaden: Optional[int]) -> str:
    if beute is not None and schaden is not None:
        return (f"Die Beute: rund {beute:,} Euro. Der Schaden: etwa {schaden:,} Euro."
                ).replace(",", ".")
    if schaden is not None:
        return f"Der Sachschaden liegt bei etwa {schaden:,} Euro.".replace(",", ".")
    if beute is not None:
        return f"Die Beute wird auf rund {beute:,} Euro geschätzt.".replace(",", ".")
    return "Die genaue Schadenshöhe ist noch unklar."


def _line_cliffhanger(ungeloest: bool) -> str:
    return ("Von den Tätern fehlt bis heute jede Spur — die Polizei bittet um Hinweise."
            if ungeloest else "Die Ermittlungen laufen — der Fall ist noch nicht abgeschlossen.")


def _caption(role: str, zeit: Optional[str], ungeloest: bool, tat: str) -> str:
    if role == "hook":
        return f"{zeit} Uhr" if zeit else "Mitten in der Nacht"
    if role == "eskalation":
        return "Großeinsatz"
    if role == "story":
        return (tat or "Tatgeschehen")[:40]
    if role == "zahlen":
        return "Beute vs. Schaden"
    if role == "cliffhanger":
        return "Spur: keine" if ungeloest else "Ermittlungen laufen"
    return ""


# ---------------------------------------------------------------------------
# SPEC ZUSAMMENBAUEN — PORTIERT aus assemble_spec(), gespeist mit echten Fakten
# ---------------------------------------------------------------------------
def build_spec(case: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    facts = facts or {}
    ort = (facts.get("ort") or case.get("region") or "unbekannter Ort").strip()
    tat = (facts.get("tat") or case.get("title") or "Vorfall").strip()
    zeit = facts.get("zeit")
    werkzeug = facts.get("werkzeug")
    beute = facts.get("beute_eur")
    schaden = facts.get("schaden_eur")
    ungeloest = bool(facts.get("ungeloest"))
    details = (facts.get("details") or "").strip()
    sentences = _split_sentences(details)
    first_sentence = sentences[0] if sentences else ""
    rest_sentences = " ".join(sentences[1:]) if len(sentences) > 1 else ""

    lines = {
        "hook": _line_hook(ort, zeit, tat),
        "eskalation": _line_eskalation(tat, first_sentence),
        "story": _line_story(werkzeug, rest_sentences, tat),
        "zahlen": _line_zahlen(beute, schaden),
        "cliffhanger": _line_cliffhanger(ungeloest),
    }

    # Deterministischer B-Roll-Seed (Titel + Quelle, damit derselbe Fall stabil bleibt)
    seed_src = f"{case.get('title', '')}|{facts.get('quelle_link') or case.get('link', '')}"
    seed = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest(), 16) % 997

    scenes: list[dict[str, Any]] = []
    t = 0
    for role in ("hook", "eskalation", "story", "zahlen", "cliffhanger"):
        d = SCENE_DURATIONS[role]
        overlay = ["timer", "progress"]
        if role in ("hook", "eskalation"):
            overlay.append(f"map:{ort}")
        if role in ("story", "eskalation"):
            overlay.append("warnbalken")
        if role == "hook" and zeit:
            overlay.append("zeit")
        if role == "zahlen":
            overlay.append("daten:beute_schaden")

        scenes.append({
            "t_start": t, "t_end": t + d, "role": role,
            "vo": lines[role],
            "caption": _caption(role, zeit, ungeloest, tat),
            "broll": pick_broll(role, seed + t),
            "overlay": overlay,
            "sfx": SCENE_SFX[role],
        })
        t += d

    voiceover = " ".join(lines[r] for r in ("hook", "eskalation", "story", "zahlen", "cliffhanger"))

    hashtags = ["#truecrime", "#deutschland", "#blaulicht", "#krimi", "#polizei", "#nachrichten"]
    tat_tag = re.sub(r"[^a-z0-9]+", "", tat.lower())[:20]
    if tat_tag:
        hashtags.append(f"#{tat_tag}")

    title_options = [
        f"{tat} in {ort}" + (f" — {zeit} Uhr" if zeit else ""),
        f"{ort}: {tat}" + (" — Täter flüchtig" if ungeloest else ""),
        f"So lief die {tat} in {ort}",
    ]

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "channel": CHANNEL,
        "duration": t,
        "case": {
            "id": case.get("id"),
            "title": case.get("title", ""),
            "region": case.get("region", ""),
            "score": case.get("score", 0),
            "link": case.get("link", ""),
        },
        "facts": facts,
        "meta": {
            "hook_line": lines["hook"],
            "title_options": title_options,
            "caption": f"{ort}: {tat}. Was ist da los? 👇",
            "hashtags": hashtags,
            "thumbnail_prompt": (
                f"dark night street in {ort}, red and blue police lights, dramatic, "
                "empty space on the left for bold text, true-crime style"
            ),
        },
        "voiceover": voiceover,
        "scenes": scenes,
        "mode": "facts",
    }
