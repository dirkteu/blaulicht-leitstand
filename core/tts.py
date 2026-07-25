# -*- coding: utf-8 -*-
"""
core/tts.py  —  Team 4: Vertonung (Gemini TTS / edge-tts) + Sync + Aussprache
==============================================================================

PORT aus dem Prototyp `tts.py` (Projektwurzel, Funktion `synth_per_scene`):
jede Szene einzeln vertonen, die echte Laenge messen, die Timecodes
(t_start/t_end) + Gesamtdauer in die Spec zurueckschreiben (Sync) und die
Szenen-Clips zu einer Gesamt-mp3 zusammenfuegen.

STIMME — umschaltbares Backend (ENV `TTS_BACKEND`):
  - `gemini` (Default): Google Gemini TTS (SDK `google-genai`). Nimmt eine
    natuerlichsprachige Regie-Anweisung (`TTS_STYLE`) fuer den duesteren
    True-Crime-Doku-Ton und eine vorgefertigte Stimme (`GEMINI_VOICE`,
    z. B. `Orus`). Liefert PCM 24 kHz/mono/16-bit — passt exakt in die
    Concat-Kette unten (die je Szene ohnehin `pcm_s16le` @ AR=24000 baut).
  - `edge` (Fallback): Microsoft `edge-tts` (Stimme `TTS_VOICE`). Bleibt als
    Notnagel erhalten, falls die Gemini-API mal klemmt.
Nur die szenenweise Vertonung (`_synth_scene_raw`) ist backend-abhaengig; die
Sync-/Timecode-/Concat-Logik in `synth()` ist fuer beide identisch.

NEU gegenueber dem Prototyp:
  - Aussprache-Woerterbuch (aus `core.supa.get_config()["aussprache"]`,
    Wort -> Ersatztext/Lautschrift) wird vor der Synthese angewendet.
  - "say-as"-Normalisierung fuer Zahlen/Uhrzeiten/Geldbetraege. Fuer edge-tts
    ist sie zwingend (kein SSML, s. u.); Gemini liest Zahlen auch selbst
    sauber, dort ist sie nur harmlose Vorverarbeitung.

Hinweis zu SSML (edge-Pfad): `edge_tts.Communicate()` escaped den kompletten
Eingabetext (`xml.sax.saxutils.escape`), bevor er ihn in sein eigenes
`<speak>`-Dokument einbettet. Eigene `<phoneme>`-/`<say-as>`-Tags wuerden also
nur als literaler Text gesprochen, NICHT als SSML interpretiert. Deshalb
arbeiten Aussprache-Woerterbuch und Zahlen-Normalisierung bewusst auf
Text-Ebene (Ersetzung VOR der Synthese). Gemini bekommt die Regie ueber den
`TTS_STYLE`-Prompt statt ueber SSML.
"""

from __future__ import annotations

import os
import re
import time
import wave
import shutil
import asyncio
import tempfile
import subprocess
from typing import Any, Optional

# Dependencies in requirements.txt: google-genai (Gemini), edge-tts (Fallback)

BACKEND = os.environ.get("TTS_BACKEND", "gemini").strip().lower()

VOICE_DEFAULT = "de-DE-ConradNeural"   # edge-Fallback-Stimme (wenn TTS_VOICE fehlt)
RATE = os.environ.get("TTS_RATE", "-8%")   # etwas langsamer = mehr Gewicht (edge)
GAP = 0.35            # kurze Atempause nach jeder Szene
END_BEAT = 0.7         # laengerer Beat vor dem Ende (Cliffhanger)
AR = "24000"           # einheitliche Audio-Parameter fuer sauberes Concat

# --- Gemini-TTS-Konfiguration (ENV) ---
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_VOICE = os.environ.get("GEMINI_VOICE", "Orus")   # feste, bestimmte Stimme
TTS_STYLE = os.environ.get(
    "TTS_STYLE",
    "Sprich als ruhiger, tiefer True-Crime-Doku-Erzähler: langsam, düster, "
    "mit Spannung — sachlich, nicht reißerisch.",
)
GEMINI_SR = 24000      # Gemini liefert PCM mono 16-bit @ 24 kHz (= AR)
GEMINI_MAX_RETRIES = 5     # Versuche bei 429 (Free-Tier: 3 Req/min)
GEMINI_RETRY_CAP = 65.0    # max. Wartezeit je Retry in Sekunden


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
# Gemini-TTS-Backend (google-genai): Szene -> WAV (PCM 24 kHz/mono/16-bit)
# ---------------------------------------------------------------------------
# Der Client wird lazy und nur einmal gebaut (Modul-Singleton), damit nicht je
# Szene ein neuer Client + Auth-Setup entsteht.
_GENAI_CLIENT = None


def _gemini_client():
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        from google import genai  # lazy: nur laden, wenn Backend wirklich genutzt wird
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY fehlt — fuer TTS_BACKEND=gemini in .env eintragen "
                "(Key aus Google AI Studio) oder TTS_BACKEND=edge setzen."
            )
        _GENAI_CLIENT = genai.Client(api_key=api_key)
    return _GENAI_CLIENT


def _write_wav(path: str, pcm: bytes, rate: int = GEMINI_SR) -> None:
    """PCM-Rohdaten (mono, 16-bit) als WAV schreiben — bewusst auf AR=24000,
    damit die Datei ohne Resampling in die Concat-Kette (`apad` -> pcm_s16le)
    passt."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(rate)
        wf.writeframes(pcm)


_RE_RETRY = re.compile(r"retry(?:Delay|\s+in)['\":\s]+(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def _retry_delay_seconds(err_msg: str, default: float) -> float:
    """Vom Server genannte Wartezeit aus einer 429-Fehlermeldung ziehen
    (`"retryDelay": "46s"` oder `retry in 46.3s`); sonst `default`."""
    m = _RE_RETRY.search(err_msg)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return default


def _gemini_scene(text: str, wav_path: str, voice: str, style: str) -> None:
    """Eine Szene mit Gemini TTS vertonen und als WAV ablegen.

    Die Regie-Anweisung (`style`) wird dem Sprechtext vorangestellt — Gemini
    nimmt sie als natuerlichsprachige Direktive (kein SSML). Rueckgabe ist
    base64-freies PCM in `inline_data.data` (Bytes) laut google-genai-SDK.
    Auf 429 (Free-Tier-RPM-Limit) wird mit kurzem Backoff neu versucht."""
    from google.genai import types

    client = _gemini_client()
    prompt = f"{style}\n\n{text}" if style else text
    cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )

    last_err: Optional[Exception] = None
    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            resp = client.models.generate_content(
                model=GEMINI_TTS_MODEL, contents=prompt, config=cfg
            )
            pcm = resp.candidates[0].content.parts[0].inline_data.data
            if not pcm:
                raise RuntimeError("Gemini-TTS-Antwort ohne Audiodaten.")
            _write_wav(wav_path, pcm)
            return
        except Exception as e:  # noqa: BLE001 — Retry nur bei Ratenlimit, sonst durchreichen
            last_err = e
            msg = str(e)
            if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                raise
            if attempt == GEMINI_MAX_RETRIES - 1:
                break
            # Der Free-Tier limitiert TTS hart (3 Req/min); der Server nennt im
            # Fehler die noetige Wartezeit ("retryDelay": "46s" / "retry in 46s").
            # Die respektieren wir, statt blind kurz zu warten.
            wait = _retry_delay_seconds(msg, default=20.0 * (attempt + 1))
            time.sleep(min(wait + 1.0, GEMINI_RETRY_CAP))
    raise RuntimeError(f"Gemini TTS nach Retries fehlgeschlagen: {last_err}")


def _synth_scene_raw(text: str, parts_dir: str, i: int,
                     voice_edge: str) -> str:
    """Vertont eine Szene mit dem aktiven Backend und gibt den Pfad der
    erzeugten "raw"-Datei zurueck (WAV bei gemini, MP3 bei edge). Der
    nachfolgende ffmpeg-`apad`-Schritt in `synth()` ist fuer beide gleich."""
    if BACKEND == "edge":
        raw = os.path.join(parts_dir, f"raw_{i:02d}.mp3")
        _edge_scene(text, raw, voice_edge, RATE)
        return raw
    # Default: gemini
    raw = os.path.join(parts_dir, f"raw_{i:02d}.wav")
    _gemini_scene(text, raw, GEMINI_VOICE, TTS_STYLE)
    return raw


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

    Vertont jede Szene aus `spec['scenes']` einzeln ueber das aktive Backend
    (`TTS_BACKEND`: gemini | edge, s. Modulkopf), misst die echte Laenge,
    schreibt `t_start`/`t_end` je Szene + `spec['duration']` zurueck (Sync)
    und fuegt alle Szenen-Clips zu einer Gesamt-mp3 zusammen.

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
    voice = os.environ.get("TTS_VOICE", VOICE_DEFAULT)   # edge-Fallback-Stimme

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
                # Backend-Dispatch: erzeugt raw_XX.wav (gemini) bzw. raw_XX.mp3
                # (edge). Der apad->pcm_s16le-Schritt ist fuer beide identisch.
                raw = _synth_scene_raw(text, parts_dir, i, voice)
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
