# -*- coding: utf-8 -*-
"""
tools/komposit.py  —  Freigestelltes Objekt in eine Nacht-Platte setzen
=======================================================================

Setzt ein freigestelltes PNG (mit Alphakanal) in ein Hintergrundbild und macht
es glaubhaft: Lichtfarbe und Pegel werden AUS DER PLATTE GEMESSEN, dazu kommen
Kontaktschatten, kurzer Wurfschatten und eine Lichtpfuetze am Boden.

Gebaut fuer den `effekt`-Master: das echte Wrackfoto (freigestellt) in eine per
Higgsfield erzeugte leere Nachtszene. Funktioniert aber fuer jedes Objekt in
jeder Platte — die Lichtfarbe wird nicht angenommen, sondern gemessen.

    python tools/komposit.py assets/master/wrack_freigestellt.png \
                             assets/master/szene_b.png \
                             assets/master/master_gesprengt.png

ZWEI ERKENNTNISSE, die hier fest verbaut sind — nicht wegoptimieren:

1.  Die Nacht-Platten sind KEIN "dunkles Blau". Messung von szene_b.png:
    R 0.133 / G 0.095 / B 0.012 — reines Natriumdampflicht, praktisch ohne
    Blauanteil. Wer dem Objekt kuehle Schatten gibt, bekommt braune Pampe.
    Deshalb kommt die Lichtfarbe aus dem Vordergrund der Platte.

2.  Die Helligkeit nimmt zur KAMERA hin zu (nach unten im Bild), nicht zur
    sichtbaren Lampe hin. Der Verlauf auf dem Objekt laeuft entsprechend.

Was das Skript NICHT kann: die Eigenschattierung des Objekts aendern. Ein bei
weichem Tageslicht fotografiertes Objekt bleibt flach modelliert — Farbe laesst
sich rechnen, Licht nicht. Und der Wurfschatten verpufft auf Asphalt, der schon
bei 0.05 liegt; die Verankerung tragen dort Kontaktschatten und Lichtpfuetze.

Abhaengigkeiten: numpy + opencv-python. Bewusst NICHT in requirements.txt —
das Skript laeuft auf dem Host, nicht in den Containern. opencv in alle neun
Images zu ziehen waere Verschwendung.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# STELLSCHRAUBEN
# ---------------------------------------------------------------------------

# Platzierung: Objektbreite als Anteil der Bildbreite, Mittelpunkt relativ.
RELW, CX, CY = 0.90, 0.49, 0.715

# Messfenster fuer die Lichtfarbe (y1, y2, x1, x2, relativ) — der beleuchtete
# Vordergrund-Boden der Platte. Nicht den Himmel oder dunkle Ecken messen.
MESSFENSTER = (0.82, 0.99, 0.02, 0.98)

TINT_MIN         = 0.12   # Farbkanal-Untergrenze, sonst kippt das Objekt monochrom
HELLIGKEIT       = 1.80   # Objektpegel als Vielfaches des gemessenen Vordergrunds

# Untergrenze fuer den gemessenen Vordergrund. Ohne sie rechnet das Skript ein
# Objekt auf einer Platte mit stockschwarzem Boden auf nahezu Null herunter und
# liefert stillschweigend eine schwarze Silhouette (gemessen: Vordergrund 0.002
# -> Objekt 0.004, 31.07.2026). Eine so dunkle Platte ist in aller Regel
# untauglich — die Klemme rettet das Bild nicht, sie macht den Fehler sichtbar.
VORDERGRUND_MIN  = 0.03
CHROMA_REST      = 0.15   # Rest Eigenfarbe (haelt z.B. ein rotes Warnband am Leben)
GAMMA            = 1.15   # >1 senkt die Tiefen ab

# Lichtverlauf auf dem Objekt: heller nach unten (= zur Kamera), leicht nach rechts.
GRAD_BASIS, GRAD_UNTEN, GRAD_RECHTS = 0.55, 0.40, 0.10

# Schatten. Licht steht hoch und hinter der Kamera -> kurzer Wurf nach oben.
WURF_SHEAR, WURF_SQUASH = -0.18, 0.22
WURF_WEICH, WURF_STAERKE = 22, 0.55
KONTAKT_WEICH, KONTAKT_STAERKE = 5, 1.00
PFUETZE_STAERKE = 0.085   # warme Lichtpfuetze am Fuss, 0 = aus

# Feinschliff
WEICHZEICHNEN, KORN = 0.7, 0.010


# ---------------------------------------------------------------------------
# BAUSTEINE
# ---------------------------------------------------------------------------

def miss_licht(bg: np.ndarray) -> tuple[np.ndarray, float]:
    """Lichtfarbe und Helligkeit aus dem Vordergrund der Platte lesen.

    Rueckgabe: (Tint als RGB mit Maximum 1.0, mittlere Helligkeit).
    """
    h, w = bg.shape[:2]
    y1, y2, x1, x2 = MESSFENSTER
    feld = bg[int(h * y1):int(h * y2), int(w * x1):int(w * x2)]
    mittel = feld.mean(axis=(0, 1))
    tint = np.clip(mittel / max(mittel.max(), 1e-6), TINT_MIN, 1.0)
    return tint, float(feld.mean())


def beleuchte(rgb: np.ndarray, maske: np.ndarray,
              tint: np.ndarray, ziel_lum: float) -> np.ndarray:
    """Objekt auf die Lichtfarbe und den Pegel der Platte bringen."""
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    grad = GRAD_BASIS + GRAD_UNTEN * (yy / h) + GRAD_RECHTS * (xx / w)

    lum = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)[..., None]
    lit = (lum * tint) * (1 - CHROMA_REST) + rgb * tint * CHROMA_REST
    lit = np.clip(lit * grad[..., None], 0, 1) ** GAMMA

    ist = lit[maske].mean() if maske.any() else 1.0
    return np.clip(lit * (ziel_lum / max(ist, 1e-6)), 0, 1)


def schatten(alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Wurfschatten (auf die Bodenebene projiziert) und Kontaktschatten."""
    h, w = alpha.shape
    proj = np.float32([[1, -WURF_SHEAR, WURF_SHEAR * h],
                       [0, WURF_SQUASH, h * (1 - WURF_SQUASH)]])
    wurf = cv2.warpAffine(alpha, proj, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    wurf = cv2.GaussianBlur(wurf, (0, 0), WURF_WEICH) * WURF_STAERKE

    kontakt = cv2.GaussianBlur(alpha, (0, 0), KONTAKT_WEICH) * 0.80
    kontakt = np.clip(kontakt - alpha * 0.55, 0, 1) * KONTAKT_STAERKE
    return wurf, kontakt


def _setze(ziel: np.ndarray, quelle: np.ndarray | None, alpha: np.ndarray,
           ox: int, oy: int, multiplizieren: bool = False) -> None:
    """Alphakanal-Montage mit Randbeschnitt. multiplizieren=True fuer Schatten."""
    H, W = ziel.shape[:2]
    h, w = alpha.shape
    xs, ys = max(0, ox), max(0, oy)
    xe, ye = min(W, ox + w), min(H, oy + h)
    if xe <= xs or ye <= ys:
        return
    a = alpha[ys - oy:ye - oy, xs - ox:xe - ox][..., None]
    if multiplizieren:
        ziel[ys:ye, xs:xe] *= (1 - a)
    else:
        q = quelle[ys - oy:ye - oy, xs - ox:xe - ox]
        ziel[ys:ye, xs:xe] = ziel[ys:ye, xs:xe] * (1 - a) + q * a


def komponiere(objekt_pfad: Path, platte_pfad: Path,
               relw: float = RELW, cx: float = CX, cy: float = CY) -> Image.Image:
    """Objekt in die Platte setzen. Liefert das fertige Bild."""
    bg = np.array(Image.open(platte_pfad).convert("RGB"), np.float32) / 255
    ob = np.array(Image.open(objekt_pfad).convert("RGBA"), np.float32) / 255
    H, W = bg.shape[:2]

    w = int(W * relw)
    h = int(ob.shape[0] * w / ob.shape[1])
    ob = cv2.resize(ob, (w, h), interpolation=cv2.INTER_AREA)
    rgb, alpha = ob[..., :3], ob[..., 3]
    x0, y0 = int(W * cx - w / 2), int(H * cy - h / 2)

    tint, gemessen = miss_licht(bg)
    vordergrund = max(gemessen, VORDERGRUND_MIN)
    if gemessen < VORDERGRUND_MIN:
        print(f"ACHTUNG: Vordergrund der Platte nur {gemessen:.3f}, nahezu "
              f"schwarz. Auf {VORDERGRUND_MIN} geklemmt, sonst waere das Objekt "
              f"eine schwarze Silhouette. Diese Platte ist vermutlich untauglich.")
    lit = beleuchte(rgb, alpha > 0.5, tint, vordergrund * HELLIGKEIT)
    if WEICHZEICHNEN > 0:
        lit = cv2.GaussianBlur(lit, (0, 0), WEICHZEICHNEN)
    wurf, kontakt = schatten(alpha)

    out = bg.copy()
    if PFUETZE_STAERKE > 0:
        gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((gx - (x0 + w * 0.46)) / (w * 0.72)) ** 2 +
                    ((gy - (y0 + h * 0.86)) / (h * 0.34)) ** 2)
        out += (np.clip(1 - d, 0, 1) ** 2.2)[..., None] * tint * PFUETZE_STAERKE

    _setze(out, None, wurf, x0 - int(w * 0.01), y0 - int(h * 0.02), multiplizieren=True)
    _setze(out, None, kontakt, x0, y0 + int(h * 0.008), multiplizieren=True)
    _setze(out, lit, alpha, x0, y0)

    if KORN > 0:
        out += np.random.default_rng(7).normal(0, KORN, out.shape)

    print(f"Licht gemessen: RGB {tint[0]:.2f}/{tint[1]:.2f}/{tint[2]:.2f}"
          f" | Vordergrund {gemessen:.3f} -> Objekt {vordergrund * HELLIGKEIT:.3f}")
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    p.add_argument("objekt", type=Path, help="freigestelltes PNG mit Alphakanal")
    p.add_argument("platte", type=Path, help="Hintergrundbild (leere Szene)")
    p.add_argument("ausgabe", type=Path, help="Zieldatei")
    p.add_argument("--relw", type=float, default=RELW, help=f"Objektbreite, Default {RELW}")
    p.add_argument("--cx", type=float, default=CX, help=f"Mitte waagerecht, Default {CX}")
    p.add_argument("--cy", type=float, default=CY, help=f"Mitte senkrecht, Default {CY}")
    a = p.parse_args()

    bild = komponiere(a.objekt, a.platte, a.relw, a.cx, a.cy)
    a.ausgabe.parent.mkdir(parents=True, exist_ok=True)
    bild.save(a.ausgabe)
    print("gespeichert:", a.ausgabe, bild.size)


if __name__ == "__main__":
    main()
