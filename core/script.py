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

from . import parse

CHANNEL = "Nachtknall"
DURATION = 42  # Ziel-Länge in Sekunden (Richtwert, siehe durs unten)

# Steht unter jeder Video-Beschreibung (workers/publish.py baut sie aus
# spec.meta.caption). Signalisiert der Plattform-Moderation Dokumentation statt
# Verherrlichung — das ist die Achse, auf der TikTok/YouTube tatsaechlich
# pruefen. Deckt zugleich die Unschuldsvermutung nach aussen ab.
DISCLAIMER = (
    "Hinweis: Dieser Kanal dokumentiert Kriminalfälle sachlich auf Basis "
    "offizieller Polizeimeldungen und Medienberichte. Es gilt die "
    "Unschuldsvermutung. Nachahmung ist strafbar."
)

# ---------------------------------------------------------------------------
# B-ROLL-BIBLIOTHEK — PORTIERT aus script_gen.py (Dateinamen wie im Bucket `broll`)
# ---------------------------------------------------------------------------
# POOL-GROESSE: die obere Grenze je Zeile muss zu den Dateien im Bucket passen.
# Namen bleiben broll_<kategorie>_NN.mp4; der Picker waehlt deterministisch per
# Hash, damit derselbe Fall immer dieselben Clips bekommt.
#
# `effect` startet bewusst bei 2, nicht bei 1: broll_effekt_01.mp4 ist der
# GENERIERTE Clip vom 26.07. mit einem anderen Automaten. 02-08 sind die aus
# echten Tatortfotos gebauten Clips (31.07., siehe PROJEKTBUCH_BROLL.md) — sie
# zeigen drei reale Tatorte. Nimmt man 01 mit in den Pool, zeigt jedes achte
# Video wieder einen fremden Automaten, also genau die Inkonsistenz, gegen die
# das ganze Verfahren gebaut wurde.
#
# Die uebrigen Kategorien stehen weiter auf 1 — dort liegt je ein Clip.
ASSETS = {
    "street":    [f"broll_strasse_{i:02d}.mp4"   for i in range(1, 2)],
    "blaulicht": [f"broll_blaulicht_{i:02d}.mp4" for i in range(1, 2)],
    "cctv":      [f"broll_cctv_{i:02d}.mp4"      for i in range(1, 2)],
    "weather":   [f"broll_wetter_{i:02d}.mp4"    for i in range(1, 2)],
    "location":  [f"broll_kulisse_{i:02d}.mp4"   for i in range(1, 2)],
    "effect":    [f"broll_effekt_{i:02d}.mp4"    for i in range(2, 9)],
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


def _taeter(ungeloest: bool) -> str:
    """Unschuldsvermutung: nie schuld-behauptend. Bei flüchtigen/unbekannten
    Tätern 'die unbekannten Täter', sonst 'die mutmaßlichen Täter'."""
    return "die unbekannten Täter" if ungeloest else "die mutmaßlichen Täter"


def _line_eskalation(tat: str, first_sentence: str) -> str:
    if first_sentence:
        return first_sentence.rstrip(".") + "."
    return f"Die Lage eskaliert schnell — {(tat or 'der Vorfall').strip().lower()} sorgt für einen Großeinsatz."


def _line_story(werkzeug: Optional[str], rest_sentences: str, tat: str,
                ungeloest: bool, distanz_vorhanden: bool = False) -> str:
    """Werkzeug-Satz + restliche Fakten-Saetze.

    Die Unschuldsvermutung schuetzt PERSONEN, nicht Ereignisse — und greift erst,
    sobald jemand identifiziert ist. Deshalb drei Varianten:

    - `ungeloest=True` (Taeter unbekannt/fluechtig): INDIKATIV. Es gibt keine
      Person, die vorverurteilt werden koennte; Polizei und Presse schreiben an
      dieser Stelle selbst im Indikativ.
    - `ungeloest=False` (jemand gefasst/benannt) + `distanz_vorhanden=False`:
      Der Satz traegt die Distanzierung selbst („sollen ... vorgegangen sein").
    - `ungeloest=False` + `distanz_vorhanden=True` (`details` distanziert schon):
      agentloses Passiv, damit sich „sollen" nicht stapelt.
    """
    if werkzeug:
        if ungeloest:
            prefix = f"Mit {werkzeug} gingen {_taeter(ungeloest)} vor. "
        elif distanz_vorhanden:
            prefix = f"Mit {werkzeug} wurde offenbar vorgegangen. "
        else:
            prefix = f"Mit {werkzeug} sollen {_taeter(ungeloest)} vorgegangen sein. "
    else:
        prefix = ""
    rest = rest_sentences or f"Die Polizei ermittelt die Hintergründe der {tat or 'Tat'}."
    return (prefix + rest).strip()


def _eur(n: int) -> str:
    """Eurobetrag mit deutschem Tausenderpunkt (40000 -> „40.000")."""
    return f"{n:,}".replace(",", ".")


def _line_zahlen(beute: Optional[int], schaden: Optional[int]) -> str:
    """Beute/Schaden-Satz.

    WICHTIG: 0 ist eine AUSSAGE („keine Beute"), kein fehlender Wert — deshalb
    durchgehend `is not None` statt Truthiness. Sonst entsteht der Unsinnssatz
    „Die Beute wird auf rund 0 Euro geschätzt." (real aufgetreten bei einer
    Sprengung, bei der die Täter nicht an die Kassetten kamen).
    """
    kein_schaden = "Nennenswerter Sachschaden entstand nicht."
    keine_beute = "Beute wurde keine gemacht."

    if beute is not None and schaden is not None:
        b = keine_beute if beute == 0 else f"Die Beute: rund {_eur(beute)} Euro."
        s = kein_schaden if schaden == 0 else f"Der Schaden: etwa {_eur(schaden)} Euro."
        return f"{b} {s}"
    if schaden is not None:
        return (kein_schaden if schaden == 0
                else f"Der Sachschaden liegt bei etwa {_eur(schaden)} Euro.")
    if beute is not None:
        return (f"{keine_beute} Die genaue Schadenshöhe ist noch unklar." if beute == 0
                else f"Die Beute wird auf rund {_eur(beute)} Euro geschätzt.")
    return "Die genaue Schadenshöhe ist noch unklar."


# Distanz-Pruefung liegt in core.parse (dort wohnen die reinen Text-Regeln) —
# core.lektor braucht dieselbe Pruefung fuer die Nachkontrolle seiner Vorschlaege.
_distanz_fehlt = parse.distanz_fehlt


def _line_cliffhanger(ungeloest: bool) -> str:
    return ("Von den unbekannten Tätern fehlt bis heute jede Spur — die Polizei bittet um Hinweise."
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
    beute = facts.get("beute_eur")
    schaden = facts.get("schaden_eur")
    ungeloest = bool(facts.get("ungeloest"))

    # ZWEITES GATE gegen Nachahmungs-Anleitungen. core.extract.sanitize() saeubert
    # schon bei der Extraktion — hier nochmal, direkt vor dem Bau des gesprochenen
    # Textes. So sind auch Bestandsfaelle abgedeckt, deren Fakten vor dieser Regel
    # entstanden sind (kein erneuter Claude-Lauf noetig).
    werkzeug = parse.entschaerfe_methode(str(facts.get("werkzeug") or "")) or None
    details = parse.entschaerfe_methode((facts.get("details") or "").strip())
    sentences = _split_sentences(details)
    first_sentence = sentences[0] if sentences else ""
    rest_sentences = " ".join(sentences[1:]) if len(sentences) > 1 else ""

    # Steht in `details` schon Konjunktiv/„mutmaßlich"? Dann braucht der
    # Werkzeug-Satz seine eigene Distanzierung nicht zu wiederholen.
    distanz_in_details = not _distanz_fehlt(details)

    lines = {
        "hook": _line_hook(ort, zeit, tat),
        "eskalation": _line_eskalation(tat, first_sentence),
        "story": _line_story(werkzeug, rest_sentences, tat, ungeloest, distanz_in_details),
        "zahlen": _line_zahlen(beute, schaden),
        "cliffhanger": _line_cliffhanger(ungeloest),
    }

    # GUARDRAIL Unschuldsvermutung — greift NUR, wenn jemand identifiziert ist.
    # Bei unbekannten/fluechtigen Taetern (ungeloest=True) gibt es keine Person,
    # die vorverurteilt werden koennte; dort ist der Indikativ korrekt und wird
    # von Polizei und Presse selbst verwendet ("Unbekannte sprengten den
    # Automaten und fluechteten"). Ein Distanz-Zusatz waere dort vorsichtiger
    # als die Quelle — und damit unnoetig.
    # Bewusst JE ZEILE geprueft, nicht ueber beide zusammen: Sonst haette ein
    # „sollen" in der Werkzeug-Zeile eine Schuldbehauptung in der Eskalations-
    # Zeile verdeckt („Der Festgenommene sprengte den Automaten.").
    if not ungeloest:
        zusatz = (f"Nach bisherigen Erkenntnissen sollen {_taeter(ungeloest)} "
                  f"für die Tat verantwortlich sein.")
        for rolle in ("eskalation", "story"):
            if _distanz_fehlt(lines[rolle]):
                lines[rolle] = f"{zusatz} {lines[rolle]}".strip()
                break   # einmal reicht — der Hinweis gilt fuer den ganzen Block

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
            "caption": f"{ort}: {tat}. Was ist da los? 👇\n\n{DISCLAIMER}",
            "disclaimer": DISCLAIMER,
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
