# -*- coding: utf-8 -*-
"""
tools/kader.py  —  Start- und Endkader fuer Bild-zu-Video schneiden
====================================================================

Schneidet aus einem fertigen Komposit die beiden Kader, die Seedance als
`start_image` und `end_image` bekommt. Damit bestimmt der Mensch die
Kamerafahrt, statt sie dem Modell zu ueberlassen.

    python tools/kader.py assets/master/master_gesprengt.png --modus seit
    python tools/kader.py assets/master/master_gesprengt.png --modus push --zoom 1.44

ZWEI MODI, und der Unterschied ist der zwischen Vielfalt und Einerlei:

  seit   Zwei GLEICH GROSSE Kader, nur seitlich versetzt -> echte Seitwaertsfahrt,
         der Massstab bleibt konstant.
  push   Voller Master als Start, engerer Ausschnitt als Ende -> Push-in.

Wer beim Endkader gleichzeitig verkleinert UND verschiebt, bekommt wieder einen
Push-in — die seitliche Bewegung geht im Zoom unter. Genau deshalb sind es zwei
getrennte Modi.

LANDEGENAUIGKEIT — der Endkader ist ein ZIEL, keine Fessel, und die Abweichung
ist NICHT vorhersagbar. Belege (1080p/5 s, seedance_2_0): eine Zoomfahrt landete
~20 % zu eng; von drei Seitwaertsfahrten lag eine ~10 % zu kurz, eine praktisch
exakt, eine deutlich zu weit.

Die frueher hier stehende Faustregel („seit faehrt ca. 10 % zu kurz") beruhte auf
einem einzigen Clip und ist damit widerlegt — sie steht bewusst nicht mehr drin,
damit niemand danach vorhaelt. Was bleibt: Ergebnis pruefen, nicht vorhersagen.

AUFLOESUNG: Die Platte ist mit 1152 px das begrenzende Glied — jeder Kader wird
darauf hochskaliert. Ab HOCHSKALIERUNG_WARNUNG meldet das Skript sich, weil der
Hintergrund dann sichtbar weich wird. Bei 1,34x war es im Bewegtbild
unauffaellig.

Abhaengigkeiten: numpy, Pillow. Laeuft auf dem Host, nicht im Container.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

# ---------------------------------------------------------------------------
# STELLSCHRAUBEN
# ---------------------------------------------------------------------------

# seit: Kaderbreite und seitlicher Versatz (Pixel im Master)
SEIT_BREITE, SEIT_VERSATZ, SEIT_MITTE_Y = 860, 280, 1250

# push: Zoomfaktor des Endkaders und dessen Mittelpunkt
PUSH_ZOOM, PUSH_ZIEL = 1.44, (700, 1330)

HOCHSKALIERUNG_WARNUNG = 1.4

# Kein Korrekturfaktor je Modus: die Landung streut (siehe Docstring). Der
# Hinweis erinnert deshalb ans Nachpruefen statt eine Zahl vorzugaukeln.
LANDUNG_HINWEIS = ("Endkader ist ein Ziel, keine Fessel. Die Abweichung streut "
                   "(gemessen bis ca. 20 % in beide Richtungen). Letzten Frame "
                   "gegen den Sollkader pruefen.")


def _ziel(text: str) -> tuple[int, int]:
    x, y = (int(t) for t in text.replace(" ", "").split(","))
    return x, y


def schneide(master: Image.Image, breite: int,
             mitte: tuple[int, int]) -> Image.Image:
    """Kader mit fester Breite um einen Mittelpunkt, auf Masterformat gebracht.

    Die Box wird ins Bild geschoben statt beschnitten — ein an den Rand
    gerutschter Kader waere sonst schmaler und der Massstab nicht mehr konstant.
    """
    W, H = master.size
    hoehe = int(breite * H / W)
    cx, cy = mitte
    x1 = min(max(cx - breite // 2, 0), W - breite)
    y1 = min(max(cy - hoehe // 2, 0), H - hoehe)
    return master.crop((x1, y1, x1 + breite, y1 + hoehe)).resize((W, H), Image.LANCZOS)


def kader(pfad: Path, modus: str, breite: int, versatz: int,
          zoom: float, ziel: tuple[int, int],
          mitte_y: int | None = None) -> tuple[Image.Image, Image.Image]:
    """Start- und Endkader liefern.

    `mitte_y` bestimmt bei `seit`, auf welcher Hoehe die Fahrt liegt. Damit
    lassen sich zwei Seitwaertsfahrten aus demselben Master unterscheiden —
    eine ueber das Objekt, eine tiefer ueber den Boden. Ohne diese Angabe
    saehen zwei seit-Clips nahezu gleich aus.
    """
    master = Image.open(pfad).convert("RGB")
    W = master.size[0]          # die Hoehe rechnet schneide() selbst aus
    if mitte_y is None:
        mitte_y = SEIT_MITTE_Y

    if modus == "seit":
        mitte_x = W // 2 - versatz // 2
        start = schneide(master, breite, (mitte_x, mitte_y))
        ende = schneide(master, breite, (mitte_x + versatz, mitte_y))
        skalierung = W / breite
        print(f"Seitwaertsfahrt: Kader {breite} px, Versatz {versatz} px "
              f"({versatz / breite * 100:.0f} % der Kaderbreite)")
    else:
        start = master.copy()
        eng = int(W / zoom)
        ende = schneide(master, eng, ziel)
        skalierung = W / eng
        print(f"Push-in: Zoom {zoom:.2f}x auf {ziel}")

    # ASCII-rein ausgeben: die Windows-Konsole laeuft auf cp1252 und bricht
    # sonst mit UnicodeEncodeError ab.
    print(f"Hochskalierung {skalierung:.2f}x", end="")
    if skalierung > HOCHSKALIERUNG_WARNUNG:
        print(f"  ACHTUNG: ueber {HOCHSKALIERUNG_WARNUNG}x, Hintergrund wird weich")
    else:
        print("  (unauffaellig)")
    print(f"Hinweis: {LANDUNG_HINWEIS}")
    return start, ende


def main() -> None:
    p = argparse.ArgumentParser(description="Start-/Endkader fuer Bild-zu-Video")
    p.add_argument("master", type=Path, help="fertiges Komposit")
    p.add_argument("--modus", choices=("seit", "push"), default="seit")
    p.add_argument("--breite", type=int, default=SEIT_BREITE,
                   help=f"seit: Kaderbreite, Default {SEIT_BREITE}")
    p.add_argument("--versatz", type=int, default=SEIT_VERSATZ,
                   help=f"seit: seitlicher Versatz, Default {SEIT_VERSATZ}")
    p.add_argument("--zoom", type=float, default=PUSH_ZOOM,
                   help=f"push: Zoomfaktor des Endkaders, Default {PUSH_ZOOM}")
    p.add_argument("--ziel", type=_ziel, default=PUSH_ZIEL, metavar="x,y",
                   help=f"push: Mittelpunkt des Endkaders, Default {PUSH_ZIEL}")
    p.add_argument("--mitte-y", type=int, default=None, dest="mitte_y",
                   help=f"seit: Hoehe der Fahrt im Master, Default {SEIT_MITTE_Y}")
    p.add_argument("--praefix", type=Path, default=None,
                   help="Ausgabepraefix (Default: neben dem Master)")
    a = p.parse_args()

    start, ende = kader(a.master, a.modus, a.breite, a.versatz, a.zoom, a.ziel,
                        a.mitte_y)

    praefix = a.praefix or a.master.with_suffix("")
    praefix.parent.mkdir(parents=True, exist_ok=True)
    ps, pe = Path(f"{praefix}_start.png"), Path(f"{praefix}_ende.png")
    start.save(ps)
    ende.save(pe)
    print("gespeichert:", ps.name, "+", pe.name, start.size)


if __name__ == "__main__":
    main()
