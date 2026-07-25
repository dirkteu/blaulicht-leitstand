# -*- coding: utf-8 -*-
"""
core/render.py  —  Team 4: Video-Assembly (Pillow-Overlays + ffmpeg)
=======================================================================

PORT aus dem Prototyp `render.py` (Projektwurzel): pro Szene ein
Hintergrund (B-Roll skaliert/geloopt ODER Farb-Kulisse), transparente
Pillow-Overlay-Frames (Timer, Karte+Pin, Warnbalken, Untertitel,
Fortschrittsbalken), Grade/Vignette/Korn nur auf den Hintergrund,
Shake+Flash am Hook, Compositing + Tonspur per ffmpeg.

Angepasst gegenueber dem Prototyp (Ziel: Docker/Linux, nicht mehr
dateisystem-getrieben):
  - LINUX-FONT: statt Windows-Arial wird DejaVuSans-Bold verwendet
    (Systempaket `fonts-dejavu-core`, siehe Dockerfile), Pfad
    `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`.
    Fallback: `ImageFont.load_default()`.
  - Kein Zugriff mehr auf lokale `assets/`-B-Roll-Dateien — B-Roll kommt
    als Dict `{dateiname: lokaler_temp_pfad}` vom Worker (der es per
    `core.supa.download(Bucket.BROLL, ...)` NUR LESEND aus Storage zieht).
  - Alles laeuft in einem eigenen Temp-Arbeitsverzeichnis statt in
    `_bg/`/`_frames/`/`preview.mp4` im Projektordner; der Rueckgabewert ist
    der Pfad zu einer frisch angelegten Temp-mp4, die der Worker hochlaedt
    und danach aufraeumt.

NEU: Daten-Overlays aus `facts` (Case.facts, siehe `core.contracts.Facts`):
  - `facts['zeit']` (HH:MM)              -> echte Tatzeit-Anzeige am Hook.
  - `facts['beute_eur']`/`schaden_eur'`  -> Vergleichs-Karte
    "Beute X €" vs. "Schaden Y €" in der Zahlen-Szene (role "zahlen").
  Beide Overlays feuern automatisch anhand der Szenen-Rolle (hook/zahlen)
  UND zusaetzlich, falls eine Szene die Overlay-Tags "zeit" bzw.
  "daten:beute_schaden" explizit traegt (fuer Team 3/core.script, falls
  die Spec das spaeter selbst steuern will).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import subprocess
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS_OUT = 30
FRAMES_PER_SEC = 3          # gezeichnete Overlay-Frames/Sek.
DEBUG_LABEL = False          # B-Roll-Dateiname einblenden (nur zum Debuggen)
POLISH = True                # Cinematic-Feinschliff: Grade, Korn, Vignette, Shake, Flash

# Farb-Kulisse je Rolle (Platzhalter, wenn kein B-Roll vorliegt)
ROLE_TINT = {
    "hook": (13, 21, 38), "eskalation": (26, 15, 12), "story": (14, 19, 16),
    "zahlen": (16, 16, 18), "cliffhanger": (11, 13, 20),
}
RED = (225, 6, 0)
AMBER = (255, 206, 107)


# ---------------------------------------------------------------------------
# LINUX-FONT: DejaVuSans-Bold statt Windows-Arial
# ---------------------------------------------------------------------------
_DEJAVU_DIRS = [
    os.environ.get("FONT_DIR", ""),
    "/usr/share/fonts/truetype/dejavu",   # Debian/Ubuntu-Paket fonts-dejavu-core (siehe Dockerfile)
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in _DEJAVU_DIRS:
        if not d:
            continue
        try:
            return ImageFont.truetype(os.path.join(d, name), size)
        except Exception:
            pass
    try:
        # Falls Fontconfig/Pillow den Namen selbst aufloesen kann.
        return ImageFont.truetype(name, size)
    except Exception:
        pass
    return ImageFont.load_default()


F_TIMER = _font(58); F_SMALL = _font(34); F_WARN = _font(42); F_CAP = _font(74); F_PIN = _font(38)
F_META = _font(30); F_LABEL = _font(30); F_ZAHL = _font(46)


# ---------------------------------------------------------------------------
# ffmpeg-Helfer
# ---------------------------------------------------------------------------
def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "")[-500:])
    return r


def _scene_at(scenes: list[dict[str, Any]], t: float) -> dict[str, Any]:
    cur = scenes[0]
    for s in scenes:
        if t >= s["t_start"]:
            cur = s
    return cur


def _scene_dur(s: dict[str, Any]) -> float:
    return max(0.4, float(s["t_end"]) - float(s["t_start"]))


def _warn_tag(spec: dict[str, Any]) -> str:
    t = (spec.get("case", {}).get("title") or "").lower()
    if "spreng" in t or "automat" in t:
        return "Automat gesprengt"
    if "raub" in t or "berfall" in t:
        return "Raubüberfall"
    if "einbruch" in t:
        return "Einbruch"
    return "Tatverdacht"


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt, maxw: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _wants(s: dict[str, Any], tag: str) -> bool:
    return tag in (s.get("overlay") or [])


# ---------------------------------------------------------------------------
# NEU: Daten-Overlays aus facts
# ---------------------------------------------------------------------------
def _eur(n: Any) -> Optional[str]:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    return f"{n:,}".replace(",", ".") + " €"


def _draw_incident_time(d: ImageDraw.ImageDraw, facts: dict[str, Any]) -> None:
    """NEU: echte Tatzeit aus facts['zeit'] (HH:MM) als kleines Label,
    ergaenzend zum laufenden Timer aus dem Prototyp."""
    zeit = (facts or {}).get("zeit")
    if not zeit:
        return
    label = f"Tatzeit {zeit} Uhr"
    tw = d.textlength(label, font=F_META)
    x0, y0, pad = 56, 152, 16
    d.rounded_rectangle([x0, y0, x0 + tw + 2 * pad, y0 + 52], radius=10, fill=(0, 0, 0, 150))
    d.text((x0 + pad, y0 + 26), label, font=F_META, fill=(240, 240, 243, 255), anchor="lm")


def _draw_beute_schaden(d: ImageDraw.ImageDraw, facts: dict[str, Any]) -> None:
    """NEU: Vergleichs-Karte "Beute X €" vs. "Schaden Y €" aus
    facts['beute_eur']/facts['schaden_eur'] fuer die Zahlen-Szene."""
    beute = _eur((facts or {}).get("beute_eur"))
    schaden = _eur((facts or {}).get("schaden_eur"))
    if beute is None and schaden is None:
        return

    cx, y = W // 2, 420
    box_w, box_h, gap = 420, 220, 40
    x_left = cx - box_w - gap // 2
    x_right = cx + gap // 2

    d.rounded_rectangle([x_left, y, x_left + box_w, y + box_h], radius=18, fill=(20, 20, 24, 205))
    d.text((x_left + box_w // 2, y + 54), "BEUTE", font=F_LABEL, fill=AMBER + (255,), anchor="mm")
    d.text((x_left + box_w // 2, y + 138), beute or "—", font=F_ZAHL, fill=(240, 240, 243, 255), anchor="mm")

    d.rounded_rectangle([x_right, y, x_right + box_w, y + box_h], radius=18, fill=(40, 10, 10, 205))
    d.text((x_right + box_w // 2, y + 54), "SCHADEN", font=F_LABEL, fill=RED + (255,), anchor="mm")
    d.text((x_right + box_w // 2, y + 138), schaden or "—", font=F_ZAHL, fill=(240, 240, 243, 255), anchor="mm")

    d.text((cx, y + box_h + 30), "vs.", font=F_LABEL, fill=(200, 200, 205, 255), anchor="mm")


# ---------------------------------------------------------------------------
# 1) HINTERGRUND je Szene (B-Roll oder Platzhalter) -> ein Video
# ---------------------------------------------------------------------------
def _build_background(spec: dict[str, Any], broll_local_paths: dict[str, str], workdir: str) -> tuple[str, int]:
    bgdir = os.path.join(workdir, "_bg")
    os.makedirs(bgdir, exist_ok=True)
    parts, used_broll = [], 0

    for i, s in enumerate(spec["scenes"]):
        d = _scene_dur(s)
        out = os.path.join(bgdir, f"bg_{i:02d}.mp4")
        broll_name = s.get("broll") or ""
        broll_path = broll_local_paths.get(broll_name)

        if broll_path and os.path.exists(broll_path):
            _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", broll_path, "-t", f"{d:.3f}",
                  "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                         "crop=1080:1920,setsar=1,fps=30",
                  "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", out])
            used_broll += 1
        else:
            r = ROLE_TINT.get(s.get("role", ""), ROLE_TINT["story"])
            hexc = "0x%02X%02X%02X" % r
            _run(["ffmpeg", "-y", "-f", "lavfi",
                  "-i", f"color=c={hexc}:s=1080x1920:r=30:d={d:.3f}",
                  "-c:v", "libx264", "-pix_fmt", "yuv420p", out])
        parts.append(out)

    listfile = os.path.join(bgdir, "list.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '%s'\n" % p.replace("\\", "/"))
    bgv = os.path.join(workdir, "_bg.mp4")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
          "-c:v", "libx264", "-pix_fmt", "yuv420p", bgv])
    return bgv, used_broll


# ---------------------------------------------------------------------------
# 2) OVERLAY-Frame (transparent) je Zeitpunkt
# ---------------------------------------------------------------------------
def _draw_overlay(spec: dict[str, Any], facts: dict[str, Any], t: float, tag: str, frac: float) -> Image.Image:
    s = _scene_at(spec["scenes"], t)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Abdunklung unten (Lesbarkeit der Untertitel)
    d.rectangle([0, H - 640, W, H], fill=(0, 0, 0, 150))

    # Kopfzeile: Timer + live
    sec = int(t)
    d.text((56, 44), f"{sec // 60}:{sec % 60:02d}", font=F_TIMER, fill=(255, 59, 48, 255))
    d.ellipse([W - 210, 60, W - 190, 80], fill=(255, 59, 48, 255))
    d.text((W - 178, 52), "live", font=F_SMALL, fill=(255, 59, 48, 255))
    if DEBUG_LABEL:
        d.text((56, 132), s.get("broll", ""), font=F_SMALL, fill=(200, 200, 205, 220))

    # Karte + Pin
    if any(str(o).startswith("map") for o in s.get("overlay", [])):
        d.ellipse([W // 2 - 150, 360, W // 2 + 150, 660], outline=(255, 255, 255, 130), width=3)
        d.ellipse([W // 2 - 26, 470, W // 2 + 26, 522], fill=(255, 59, 48, 255))
        d.text((W // 2, 690), spec.get("case", {}).get("region", ""), font=F_PIN,
               fill=(240, 240, 243, 255), anchor="mm")

    # Warnbalken
    if "warnbalken" in s.get("overlay", []):
        y = 940
        d.rectangle([56, y, W - 56, y + 84], fill=(110, 12, 8, 205))
        d.rectangle([56, y, 66, y + 84], fill=RED + (255,))
        d.polygon([(92, y + 62), (128, y + 62), (110, y + 24)], outline=AMBER + (255,), width=4)
        d.text((110, y + 44), "!", font=F_SMALL, fill=AMBER + (255,), anchor="mm")
        d.text((150, y + 20), tag, font=F_WARN, fill=AMBER + (255,))

    # NEU: Daten-Overlays aus facts
    if s.get("role") == "hook" or _wants(s, "zeit"):
        _draw_incident_time(d, facts)
    if s.get("role") == "zahlen" or _wants(s, "daten:beute_schaden"):
        _draw_beute_schaden(d, facts)

    # Untertitel
    lines = _wrap(d, s.get("caption", ""), F_CAP, W - 130)
    cy = H - 340 - len(lines) * 88
    for ln in lines:
        d.text((60, cy), ln, font=F_CAP, fill=(243, 243, 244, 255))
        cy += 88

    # Fortschrittsbalken
    d.rounded_rectangle([60, H - 150, W - 60, H - 138], radius=6, fill=(255, 255, 255, 60))
    fillw = int((W - 120) * frac)
    d.rounded_rectangle([60, H - 150, 60 + fillw, H - 138], radius=6, fill=RED + (255,))

    # BOOM-Blitz zum Einstieg (nur Hook, erste ~0.6s)
    if POLISH and s.get("role") == "hook" and t < 0.45:
        a = int(max(0, 175 * (1 - t / 0.45)))
        if a > 0:
            d.rectangle([0, 0, W, H], fill=(255, 255, 255, a))
    return img


def _audio_input(voice_local_path: Optional[str], dur: float) -> tuple[list[str], str]:
    if voice_local_path and os.path.exists(voice_local_path):
        return ["-i", voice_local_path], f"voice: {os.path.basename(voice_local_path)}"
    return ["-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=44100:cl=stereo"], "Stille (keine Voice übergeben)"


# ---------------------------------------------------------------------------
# Kernfunktion
# ---------------------------------------------------------------------------
def render(spec: dict[str, Any],
           facts: Optional[dict[str, Any]],
           broll_local_paths: dict[str, str],
           voice_local_path: Optional[str]) -> str:
    """PORT aus `render.py:main()`.

    Rendert aus der Spec ein 9:16-MP4: Hintergrund je Szene (B-Roll oder
    Farb-Kulisse) + transparente Pillow-Overlays + Grade/Vignette/Korn +
    Shake/Flash am Hook + Tonspur.

    Args:
        spec: Video-Bauanleitung (`Case.spec`), MUSS `scenes` und
            `duration` enthalten (von `core.tts.synth` synchronisiert).
        facts: `Case.facts` (`Facts.to_dict()`) — Quelle fuer die
            Daten-Overlays (Tatzeit, Beute/Schaden). Darf `None`/leer sein.
        broll_local_paths: Dict `{dateiname_aus_spec: lokaler_temp_pfad}`.
            Vom Worker per `core.supa.download(Bucket.BROLL, ...)`
            NUR LESEND aus Storage gezogen. Fehlt ein Eintrag/Datei, faellt
            die Szene automatisch auf die Farb-Kulisse zurueck.
        voice_local_path: lokaler Pfad zur Voice-mp3 (vom Worker aus
            Bucket.VOICE geladen). Darf `None` sein (dann Stille).

    Returns:
        Pfad zu einer frisch angelegten lokalen Temp-mp4. Der Aufrufer
        (Worker) laedt sie hoch und raeumt sie danach auf.
    """
    if not spec or not spec.get("scenes"):
        raise ValueError("spec ohne 'scenes' — nichts zu rendern.")

    facts = facts or {}
    broll_local_paths = broll_local_paths or {}
    scenes = spec["scenes"]
    durf = float(spec.get("duration") or scenes[-1]["t_end"])
    tag = _warn_tag(spec)

    workdir = tempfile.mkdtemp(prefix="blaulicht_render_")
    try:
        bgv, used = _build_background(spec, broll_local_paths, workdir)

        frames_dir = os.path.join(workdir, "_frames")
        os.makedirs(frames_dir, exist_ok=True)
        total = max(1, int(round(durf * FRAMES_PER_SEC)))
        for k in range(total):
            t = k / FRAMES_PER_SEC
            frac = min((k + 1) / total, 1.0)
            _draw_overlay(spec, facts, t, tag, frac).save(os.path.join(frames_dir, f"f_{k:04d}.png"))

        audio_in, _desc = _audio_input(voice_local_path, durf)
        out_path = os.path.join(workdir, "out.mp4")
        cmd = ["ffmpeg", "-y", "-i", bgv,
               "-framerate", str(FRAMES_PER_SEC), "-i", os.path.join(frames_dir, "f_%04d.png")]
        cmd += audio_in
        if POLISH:
            # Grade/Vignette/Korn nur auf den Hintergrund (Overlays bleiben knackig);
            # Shake auf das Gesamtbild (Kamera-Wackler beim Hook).
            grade = "eq=contrast=1.12:saturation=1.2,vignette=PI/4,noise=alls=5:allf=t"
            shake = ("scale=iw*1.03:ih*1.03,"
                     "crop=1080:1920:x='(iw-1080)/2+if(lt(t,0.35),16*sin(t*95),0)'"
                     ":y='(ih-1920)/2+if(lt(t,0.35),14*cos(t*80),0)'")
            vchain = ("[1:v]fps=30,format=rgba[ov];"
                      f"[0:v]{grade}[bg];[bg][ov]overlay=format=auto[comp];"
                      f"[comp]{shake},format=yuv420p[v];[2:a]apad[a]")
        else:
            vchain = ("[1:v]fps=30,format=rgba[ov];"
                      "[0:v][ov]overlay=format=auto,format=yuv420p[v];[2:a]apad[a]")
        cmd += ["-filter_complex", vchain,
                "-map", "[v]", "-map", "[a]", "-r", str(FPS_OUT),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path]
        _run(cmd)

        final_fd, final_path = tempfile.mkstemp(suffix=".mp4", prefix="blaulicht_video_")
        os.close(final_fd)
        shutil.copyfile(out_path, final_path)
        return final_path
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
