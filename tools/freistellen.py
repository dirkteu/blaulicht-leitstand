# -*- coding: utf-8 -*-
"""
tools/freistellen.py  —  Objekt aus einem echten Foto freistellen (Alphakanal)
==============================================================================

Schneidet ein Objekt samt Umfeld aus einem Foto aus und liefert ein PNG mit
Alphakanal. Gebaut fuer den `effekt`-Master: das echte Wrackfoto des Users wird
freigestellt und mit `tools/komposit.py` in eine generierte Nachtszene gesetzt.

    # 1. Koordinatengitter zum Ablesen
    python tools/freistellen.py foto.jpg wrack.png --gitter

    # 2. Freistellen: --box fuer grosse Einzelteile, --nest fuer Streugut
    python tools/freistellen.py foto.jpg wrack.png \
        --box 140,260,1480,2820 --box 1430,1240,2920,2680 \
        --nest 1850,3240,2260,3510

ZWEI ARTEN VON AUSWAHL — der Unterschied ist wichtig:

  --box   SAM-2-Maske fuer die Box, direkt uebernommen. Fuer klar abgegrenzte
          Einzelteile (Gehaeuse, Frontplatte, Kassette). Verifiziert: bei einem
          gekippten Quader liefert SAM ~74 % der Box, das ist korrekt.

  --nest  SAM liefert nur den SUCHBEREICH; darin wird farblich gegen den Boden
          ringsum getrennt. Fuer Streugut. Grund: SAM auf ein Nest aus vielen
          Kleinteilen angesetzt liefert einen Klumpen samt Asphalt dazwischen —
          das klebt beim Compositing als grauer Fleck im Zielbild.

WAS HIER SCHON SCHIEFGING (nicht wegoptimieren):

1.  Loecher ZUERST fuellen, DANN den Gruensaum pruefen. Umgekehrt liegen die
    Lochraender mit im Pruefband, und die gruenen Platinen im Geraeteinneren
    werden als Hintergrund-Bluten weggeschnitten. Ist passiert.

2.  Ein rein automatischer Ansatz ueber Hintergrund-Differenz (grosser
    Medianfilter, Abweichung markieren) findet NUR Asphaltkoernung. Die
    Streugut-Teile sind groesser als das Filterfenster und landen selbst in der
    Hintergrund-Schaetzung. Deshalb SAM als Lokalisierer.

3.  EXIF-Orientierung aufrichten. Handyfotos liegen quer im Speicher
    (Orientation 6) — ohne `exif_transpose` stimmen alle Koordinaten nicht.

Abhaengigkeiten: numpy, opencv-python, ultralytics. Bewusst NICHT in
requirements.txt — das Skript laeuft auf dem Host, nicht in den Containern.
Das SAM-Modell (~74 MB) zieht ultralytics beim ersten Lauf selbst.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

# ---------------------------------------------------------------------------
# STELLSCHRAUBEN
# ---------------------------------------------------------------------------

MODELL = "sam2.1_t.pt"       # ultralytics laedt es beim ersten Lauf selbst

GITTER_SCHRITT = 100         # Rasterweite im Originalbild
GITTER_BREITE  = 750         # Breite des Gitterbilds

RING          = 61           # Breite des Bodenring um ein Nest (Pixel)
RING_SIGMA    = 3.0          # Abweichung vom Bodenmodell in robusten Sigma
NEST_MINDEST  = 200          # Kleinstteile im Nest verwerfen (Pixel)
STREU_MINDEST = 250          # Kleinstteile im Gesamt-Streugut verwerfen

GRUEN_BAND    = 11           # Breite des Randbands fuer die Gruensaum-Pruefung
GRUEN_A       = 123.0        # LAB-a darunter = gruen = Hintergrund-Bluten

KANTE_ZURUECK = 3            # Erosion vor dem Weichzeichnen (Pixel)
KANTE_WEICH   = 1.4          # Sigma der Alpha-Weichzeichnung


def _koordinaten(text: str) -> list[int]:
    """'x1,y1,x2,y2' -> [x1, y1, x2, y2]."""
    teile = [int(t) for t in text.replace(" ", "").split(",")]
    if len(teile) != 4:
        raise argparse.ArgumentTypeError(f"Box braucht x1,y1,x2,y2 — bekam {text!r}")
    return teile


def aufrichten(pfad: Path) -> Image.Image:
    """Foto laden und EXIF-Drehung anwenden."""
    return ImageOps.exif_transpose(Image.open(pfad)).convert("RGB")


def gitter(bild: Image.Image, ziel: Path) -> None:
    """Koordinatengitter ueber das Foto legen — Beschriftung = Originalpixel."""
    faktor = GITTER_BREITE / bild.width
    klein = bild.resize((GITTER_BREITE, int(bild.height * faktor)))
    d = ImageDraw.Draw(klein)
    for x in range(0, bild.width, GITTER_SCHRITT):
        px = x * faktor
        d.line([(px, 0), (px, klein.height)], fill=(255, 0, 0))
        d.text((px + 3, 3), str(x), fill=(255, 255, 0))
    for y in range(0, bild.height, GITTER_SCHRITT):
        py = y * faktor
        d.line([(0, py), (klein.width, py)], fill=(255, 0, 0))
        d.text((3, py + 3), str(y), fill=(0, 255, 255))
    klein.save(ziel)


def sam_masken(rgb: np.ndarray, boxen: list[list[int]]) -> np.ndarray:
    """SAM-2 auf mehrere Boxen ansetzen. Ein Bildencoder-Lauf fuer alle.

    Bekommt das AUFGERICHTETE Bild als Array, nicht den Dateipfad: ultralytics
    wuerde die Datei selbst laden und die EXIF-Drehung ignorieren — dann passen
    die abgelesenen Koordinaten nicht mehr. Numpy-Eingaben erwartet ultralytics
    in BGR.
    """
    from ultralytics import SAM
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ergebnis = SAM(MODELL)(bgr, bboxes=boxen, verbose=False)[0]
    return ergebnis.masks.data.cpu().numpy() > 0.5


def trenne_im_nest(lab: np.ndarray, bereich: np.ndarray,
                   belegt: np.ndarray) -> np.ndarray:
    """Im Suchbereich farblich gegen den Boden ringsum trennen.

    Bodenmodell = Median + robuste Streuung (MAD) der LAB-Werte im Ring um den
    Bereich. Alles, was in einem Kanal weiter als RING_SIGMA davon abweicht,
    gilt als Objekt. Passt sich damit an Gras UND Asphalt an, ohne dass eine
    Schwelle je Untergrund gepflegt werden muss.
    """
    ring = cv2.dilate(bereich.astype(np.uint8),
                      np.ones((RING, RING), np.uint8)).astype(bool)
    ring &= ~bereich & ~belegt
    if ring.sum() < 2000:
        return np.zeros_like(bereich)

    boden = lab[ring]
    median = np.median(boden, axis=0)
    mad = np.median(np.abs(boden - median), axis=0) * 1.4826 + 1e-3
    treffer = bereich & ((np.abs(lab - median) / mad).max(axis=2) > RING_SIGMA)

    treffer = cv2.morphologyEx(treffer.astype(np.uint8), cv2.MORPH_CLOSE,
                               np.ones((5, 5), np.uint8))
    treffer = cv2.morphologyEx(treffer, cv2.MORPH_OPEN,
                               np.ones((3, 3), np.uint8))
    return grossteile(treffer.astype(bool), NEST_MINDEST)


def grossteile(maske: np.ndarray, mindest: int) -> np.ndarray:
    """Zusammenhaengende Teile unterhalb der Mindestflaeche verwerfen."""
    anzahl, label, stats, _ = cv2.connectedComponentsWithStats(
        maske.astype(np.uint8), 8)
    behalten = np.zeros_like(maske)
    for i in range(1, anzahl):
        if stats[i, cv2.CC_STAT_AREA] >= mindest:
            behalten |= (label == i)
    return behalten


def freistellen(quelle: Path, boxen: list[list[int]],
                nester: list[list[int]]) -> Image.Image:
    """Objekt ausschneiden und als RGBA zurueckgeben (auf Inhalt beschnitten)."""
    bild = aufrichten(quelle)
    rgb = np.array(bild)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    H, W = rgb.shape[:2]

    # --- Hauptkoerper aus den Boxen ---
    haupt = np.zeros((H, W), bool)
    if boxen:
        for maske in sam_masken(rgb, boxen):
            haupt |= maske
        print(f"  {len(boxen)} Box(en) -> {haupt.sum()/1e6:.2f} Mpx")

    # --- Streugut aus den Nestern ---
    streu = np.zeros((H, W), bool)
    if nester:
        for i, bereich in enumerate(sam_masken(rgb, nester)):
            bereich &= ~haupt
            if bereich.sum() < 500:
                continue
            treffer = trenne_im_nest(lab, bereich, haupt)
            print(f"  Nest {i}: Suchbereich {bereich.sum():7d} px "
                  f"-> Streugut {treffer.sum():6d} px")
            streu |= treffer
        streu &= ~haupt

    # --- Loecher im Hauptkoerper fuellen (VOR der Gruensaum-Pruefung!) ---
    mm = haupt.astype(np.uint8) * 255
    mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8),
                          iterations=2)
    aussen = mm.copy()
    cv2.floodFill(aussen, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 255)
    mm |= cv2.bitwise_not(aussen)

    # --- Gruensaum nur am Aussenrand: Loecher sind gefuellt, Platinen sicher ---
    band = (mm > 127) & (cv2.erode(mm, np.ones((GRUEN_BAND,) * 2, np.uint8)) < 128)
    gruen = band & (lab[..., 1] < GRUEN_A)
    mm[gruen] = 0
    print(f"  Gruensaum entfernt: {gruen.sum()/1e3:.1f} kpx")

    # --- Streugut anfuegen, Kleinstteile raus ---
    db = cv2.morphologyEx(streu.astype(np.uint8) * 255, cv2.MORPH_CLOSE,
                          np.ones((5, 5), np.uint8))
    db = grossteile(db > 127, STREU_MINDEST).astype(np.uint8) * 255

    maske = np.maximum(mm, db)
    alpha = cv2.GaussianBlur(
        cv2.erode(maske, np.ones((KANTE_ZURUECK,) * 2, np.uint8)),
        (0, 0), KANTE_WEICH)

    rgba = Image.fromarray(np.dstack([rgb, alpha]))
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0:
        raise SystemExit("Nichts gefunden — Boxen pruefen (--gitter hilft).")
    beschnitten = rgba.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    deckung = (np.array(beschnitten)[..., 3] > 8).mean() * 100
    print(f"  Ergebnis {beschnitten.size}, Deckung im Rahmen {deckung:.1f} %")
    return beschnitten


def main() -> None:
    p = argparse.ArgumentParser(
        description="Objekt aus einem Foto freistellen (PNG mit Alphakanal)")
    p.add_argument("foto", type=Path, help="Quellfoto")
    p.add_argument("ausgabe", type=Path, help="Ziel-PNG (bzw. Gitterbild)")
    p.add_argument("--gitter", action="store_true",
                   help="nur Koordinatengitter schreiben und beenden")
    p.add_argument("--box", type=_koordinaten, action="append", default=[],
                   metavar="x1,y1,x2,y2",
                   help="Einzelteil: SAM-Maske direkt uebernehmen (mehrfach)")
    p.add_argument("--nest", type=_koordinaten, action="append", default=[],
                   metavar="x1,y1,x2,y2",
                   help="Streugut: SAM als Suchbereich, darin Farbtrennung (mehrfach)")
    a = p.parse_args()

    a.ausgabe.parent.mkdir(parents=True, exist_ok=True)

    if a.gitter:
        bild = aufrichten(a.foto)
        gitter(bild, a.ausgabe)
        print(f"Gitter: {a.ausgabe}  (Foto aufgerichtet: {bild.size})")
        print(f"Beschriftung = Koordinaten im Original, Raster {GITTER_SCHRITT} px")
        return

    if not a.box and not a.nest:
        raise SystemExit("Mindestens ein --box oder --nest angeben "
                         "(Koordinaten mit --gitter ablesen).")

    freistellen(a.foto, a.box, a.nest).save(a.ausgabe)
    print("gespeichert:", a.ausgabe)


if __name__ == "__main__":
    main()
