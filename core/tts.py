# -*- coding: utf-8 -*-
"""
core/tts.py  —  Team 4: Vertonung (edge-tts) + Sync + Aussprache
==================================================================

PORT aus dem Prototyp `tts.py` (Projektwurzel, Funktion `synth_per_scene`):
jede Szene einzeln vertonen, die echte Laenge messen, die Timecodes
(t_start/t_end) + Gesamtdauer in die Spec zurueckschreiben (Sync) und die
Szenen-Clips zu einer Gesamt-mp3 zusammenfuegen.

NEU gegenueber dem Prototyp:
  - Aussprache-Woerterbuch (aus `core.supa.get_config()["aussprache"]`,
    Wort -> Ersatztext/Lautschrift) wird vor der Synthese angewendet.
  - "say-as"-Normalisierung fuer Zahlen/Uhrzeiten/Geldbetraege, damit
    edge-tts sie sauber ausspricht ("20:00" -> "zwanzig Uhr",
    "12345 €" -> "zwölftausendfünfhundertfünfundvierzig Euro").

Hinweis zu SSML (wichtig fuer spaetere Teams, die hier weiterbauen):
`edge_tts.Communicate()` escaped den kompletten Eingabetext
(`xml.sax.saxutils.escape`), bevor er ihn in sein eigenes
`<speak>`-Dokument einbettet (siehe `edge_tts.communicate.mkssml` /
`Communicate.__init__`). Eigene `<phoneme>`- oder `<say-as>`-Tags im
uebergebenen Text wuerden also nur als literaler Text
("&lt;phoneme...&gt;") gesprochen, NICHT als SSML interpretiert.
Deshalb arbeiten Aussprache-Woerterbuch und Zahlen-Normalisierung hier
bewusst auf Text-Ebene (Wort-/Muster-Ersetzung VOR der Synthese) statt
ueber SSML-Tags, die edge-tts ohnehin nicht durchreichen wuerde.
"""

from __future__ import annotations

import os
import re
import shutil
import asyncio
import tempfile
import subprocess
from typing import Any, Optional

# Dependency bereits in requirements.txt vorhanden: edge-tts

VOICE_DEFAULT = "de-DE-ConradNeural"   # dunkle Doku-Stimme (Fallback, wenn ENV fehlt)
RATE = os.environ.get("TTS_RATE", "-8%")   # etwas langsamer = mehr Gewicht
GAP = 0.35            # kurze Atempause nach jeder Szene
END_BEAT = 0.7         # laengerer Beat vor dem Ende (Cliffhanger)
AR = "24000"           # einheitliche Audio-Parameter fuer sauberes Concat


# ---------------------------------------------------------------------------
# ffmpeg/ffprobe-Helfer (1:1 aus dem Prototyp)
# ---------------------------------------------------------------------------
def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "")[-400:])
    return r


def _probe_dur(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip()
    return float(out)


def _edge_scene(text: str, path: str, voice: str, rate: str) -> None:
    import edge_tts

    async def go():
        await edge_tts.Communicate(text, voice, rate=rate).save(path)

    asyncio.run(go())


# ---------------------------------------------------------------------------
# NEU: Aussprache-Woerterbuch + Zahlen/Zeit/Geld-Normalisierung ("say-as")
# ---------------------------------------------------------------------------
_EINER = ["null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben",
          "acht", "neun", "zehn", "elf", "zwölf", "dreizehn", "vierzehn",
          "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn"]
_ZEHNER = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig",
           "siebzig", "achtzig", "neunzig"]


def _zahl_zu_wort(n: int) -> str:
    """Ganzzahl in ein deutsches Zahlwort umwandeln. Deckt den Bereich ab,
    der fuer Uhrzeiten sowie Beute-/Schadenssummen im True-Crime-Kontext
    realistisch vorkommt; sehr grosse Zahlen fallen auf Ziffern zurueck
    (edge-tts liest dann selbst vor, statt dass wir raten)."""
    if n < 0:
        return "minus " + _zahl_zu_wort(-n)
    if n < 20:
        return _EINER[n]
    if n < 100:
        z, e = divmod(n, 10)
        if e == 0:
            return _ZEHNER[z]
        einer = "ein" if e == 1 else _EINER[e]   # "einundzwanzig", nicht "einsundzwanzig"
        return f"{einer}und{_ZEHNER[z]}"
    if n < 1000:
        h, rest = divmod(n, 100)
        prefix = "einhundert" if h == 1 else f"{_EINER[h]}hundert"
        return prefix if rest == 0 else prefix + _zahl_zu_wort(rest)
    if n < 1_000_000:
        t, rest = divmod(n, 1000)
        prefix = "eintausend" if t == 1 else f"{_zahl_zu_wort(t)}tausend"
        return prefix if rest == 0 else prefix + _zahl_zu_wort(rest)
    return str(n)


_RE_ZEIT = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(\s*Uhr)?\b")
_RE_GELD = re.compile(r"\b(\d{1,3}(?:[.\s]\d{3})*|\d+)\s?(€|EUR|Euro)\b", re.IGNORECASE)
_RE_ZAHL = re.compile(r"\b\d{1,6}\b")


def _say_as_zeit(m: "re.Match[str]") -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    if mi == 0:
        return f"{_zahl_zu_wort(h)} Uhr"
    return f"{_zahl_zu_wort(h)} Uhr {_zahl_zu_wort(mi)}"


def _say_as_geld(m: "re.Match[str]") -> str:
    raw = m.group(1).replace(".", "").replace(" ", "")
    try:
        n = int(raw)
    except ValueError:
        return m.group(0)
    return f"{_zahl_zu_wort(n)} Euro"


def _say_as_zahl(m: "re.Match[str]") -> str:
    try:
        n = int(m.group(0))
    except ValueError:
        return m.group(0)
    return _zahl_zu_wort(n)


def normalize_say_as(text: str) -> str:
    """Zahlen/Zeit/Geld in gesprochene Form ueberfuehren — die "say-as"-
    Normalisierung, die edge-tts (ohne echtes SSML) nicht selbst bekommt.
    Reihenfolge wichtig: erst Uhrzeit (HH:MM), dann Geld (Zahl + €/Euro),
    dann alle uebrigen nackten Zahlen — jede Stufe verbraucht ihre Ziffern,
    damit sie in der naechsten nicht doppelt angefasst werden."""
    if not text:
        return text
    text = _RE_ZEIT.sub(_say_as_zeit, text)
    text = _RE_GELD.sub(_say_as_geld, text)
    text = _RE_ZAHL.sub(_say_as_zahl, text)
    return text


def apply_aussprache(text: str, aussprache: Optional[dict[str, str]]) -> str:
    """Wort -> Ersatztext/Lautschrift aus dem Aussprache-Woerterbuch
    (`core.supa.get_config()['aussprache']`) anwenden. Ganzwort-Ersetzung
    (keine Teilwort-Treffer), gross-/kleinschreibungstolerant, laengste
    Begriffe zuerst (damit z. B. 'Zigarettenautomat' vor 'Automat' greift)."""
    if not text or not aussprache:
        return text
    for wort in sorted(aussprache.keys(), key=len, reverse=True):
        if not wort:
            continue
        ersatz = aussprache[wort]
        pattern = re.compile(r"(?<!\w)" + re.escape(wort) + r"(?!\w)", re.IGNORECASE)
        text = pattern.sub(lambda _m, r=ersatz: r, text)
    return text


def _prep_text(text: str, aussprache: Optional[dict[str, str]]) -> str:
    """Reihenfolge bewusst: erst Zahlen/Zeit/Geld normalisieren, DANACH das
    Aussprache-Woerterbuch anwenden — so kann das Woerterbuch auch auf
    bereits ausgeschriebene Zahlwoerter matchen, und Ziffern in
    Woerterbuch-Ersetzungen werden nicht versehentlich nochmal angefasst."""
    text = normalize_say_as(text)
    text = apply_aussprache(text, aussprache)
    return text


# ---------------------------------------------------------------------------
# Kernfunktion: pro Szene vertonen + Sync + Zusammenfuegen
# ---------------------------------------------------------------------------
def synth(spec: dict[str, Any],
          aussprache_dict: Optional[dict[str, str]] = None) -> tuple[str, dict[str, Any]]:
    """PORT aus `tts.py:synth_per_scene()`.

    Vertont jede Szene aus `spec['scenes']` einzeln (edge-tts, Stimme aus
    ENV `TTS_VOICE`), misst die echte Laenge, schreibt `t_start`/`t_end`
    je Szene + `spec['duration']` zurueck (Sync) und fuegt alle
    Szenen-Clips zu einer Gesamt-mp3 zusammen.

    NEU: wendet vor der Synthese Zahlen/Zeit/Geld-Normalisierung
    (`normalize_say_as`) und das Aussprache-Woerterbuch
    (`apply_aussprache`) auf den Sprechtext jeder Szene an.

    Args:
        spec: Video-Bauanleitung (`Case.spec`), MUSS `scenes` (Liste von
            Szenen-Dicts mit mind. `vo`) enthalten.
        aussprache_dict: Wort -> Ersatztext, i. d. R.
            `core.supa.get_config()["aussprache"]`.

    Returns:
        (voice_local_path, updated_spec)
        `voice_local_path` ist eine frisch angelegte lokale Temp-Datei
        (mp3) — der Aufrufer (Worker) laedt sie hoch und raeumt sie
        danach auf. `updated_spec` ist dieselbe Dict-Instanz wie `spec`
        (in-place um Timecodes/duration ergaenzt); der Worker schreibt
        sie per `update_case(..., spec=updated_spec)` zurueck.
    """
    voice = os.environ.get("TTS_VOICE", VOICE_DEFAULT)
    rate = RATE

    scenes = spec.get("scenes") or []
    if not scenes:
        raise ValueError("spec['scenes'] ist leer — nichts zu vertonen.")

    workdir = tempfile.mkdtemp(prefix="blaulicht_tts_")
    parts_dir = os.path.join(workdir, "_parts")
    os.makedirs(parts_dir, exist_ok=True)
    out_mp3 = os.path.join(workdir, "voice.mp3")

    try:
        parts, t = [], 0.0
        for i, sc in enumerate(scenes):
            raw_text = (sc.get("vo") or "").strip()
            text = _prep_text(raw_text, aussprache_dict)
            # Zwischendateien als WAV/PCM (kein MP3-Encoder-Delay je Szene ->
            # kein Knacken/Stottern an den Szenengrenzen beim Zusammenfuegen).
            part = os.path.join(parts_dir, f"part_{i:02d}.wav")
            gap = END_BEAT if i == len(scenes) - 1 else GAP

            if not text:
                _run(["ffmpeg", "-y", "-f", "lavfi", "-t", "0.6",
                      "-i", f"anullsrc=r={AR}:cl=mono", "-ac", "1",
                      "-c:a", "pcm_s16le", part])
            else:
                raw = os.path.join(parts_dir, f"raw_{i:02d}.mp3")
                _edge_scene(text, raw, voice, rate)
                _run(["ffmpeg", "-y", "-i", raw, "-af", f"apad=pad_dur={gap}",
                      "-ar", AR, "-ac", "1", "-c:a", "pcm_s16le", part])

            d = _probe_dur(part)
            sc["t_start"] = round(t, 2)
            sc["t_end"] = round(t + d, 2)
            t += d
            parts.append(part)

        # WAV-Teile luecken- und knackfrei zusammenfuegen, DANN EINMAL nach
        # MP3 kodieren (nur ein Encoder-Delay am Gesamtanfang statt je Szene).
        listfile = os.path.join(parts_dir, "list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in parts:
                f.write("file '%s'\n" % p.replace("\\", "/"))
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
              "-ar", AR, "-ac", "1", "-c:a", "libmp3lame", out_mp3])

        spec["duration"] = round(t, 2)

        # Endgueltige mp3 aus dem Arbeitsverzeichnis herausloesen, damit sie
        # das rmtree unten ueberlebt — der Worker raeumt sie nach dem Upload auf.
        final_fd, final_path = tempfile.mkstemp(suffix=".mp3", prefix="blaulicht_voice_")
        os.close(final_fd)
        shutil.copyfile(out_mp3, final_path)
        return final_path, spec
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
