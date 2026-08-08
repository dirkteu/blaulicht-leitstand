# -*- coding: utf-8 -*-
"""
tools/wuerfeln.py  —  aus EINEM Seedance-Lauf viele Varianten schneiden
===============================================================================

Ein Storyboard-Lauf liefert 15 Sekunden mit 15 Einstellungen (siehe
STORYBOARD_STREIFENFAHRT.md). Die Fahrt-Einstellungen sind untereinander
austauschbar — die Ankunft ist es nicht: Wer aussteigt, steigt am Ende aus.
Also wird der Fahrt-Teil gewuerfelt und die Ankunft bleibt fest angehaengt.

    python tools/wuerfeln.py schnittliste.json --anzahl 6 --ziel varianten/

Die Schnittliste ist bewusst eine JSON-Datei und keine Konstante im Code: Die
Zeitmarken kommen aus der SICHTUNG eines konkreten Laufs. Ein zweiter Lauf hat
andere. Gesperrte Segmente stehen mit Begruendung drin, damit niemand sie
spaeter "aus Versehen" wieder freischaltet — bei diesem Lauf sind es ein
lesbares Kennzeichen und ein Aermelwappen, beides Verstoesse gegen STIL_BASIS.

Braucht ffmpeg im PATH. Schneidet mit Neukodierung (frame-genau), setzt danach
per concat-Demuxer ohne weitere Kodierung zusammen.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path


def schneide(quelle: Path, start: float, dauer: float, ziel: Path) -> Path:
    """Ein Segment herausschneiden (Neukodierung, damit der Schnitt sitzt)."""
    if ziel.exists():
        return ziel
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-ss", str(start), "-i", str(quelle), "-t", str(dauer),
         "-an", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(ziel)],
        check=True)
    return ziel


def klebe(teile: list[Path], ziel: Path) -> None:
    """Segmente ohne Neukodierung aneinanderhaengen."""
    liste = ziel.with_suffix(".txt")
    liste.write_text("".join(f"file '{p.as_posix()}'\n" for p in teile),
                     encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(liste), "-c", "copy", str(ziel)],
        check=True)
    liste.unlink()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("schnittliste", type=Path)
    p.add_argument("--anzahl", type=int, default=6, help="Zahl der Varianten")
    p.add_argument("--laenge", type=int, default=5,
                   help="Fahrt-Einstellungen je Variante")
    p.add_argument("--ziel", type=Path, default=Path("varianten"))
    p.add_argument("--seed", type=int, default=None,
                   help="fuer reproduzierbare Laeufe")
    a = p.parse_args()

    plan = json.loads(a.schnittliste.read_text(encoding="utf-8"))
    quelle = (a.schnittliste.parent / plan["quelle"]).resolve()
    if not quelle.exists():
        print(f"Quelle fehlt: {quelle}", file=sys.stderr)
        return 1

    fahrt, ankunft = plan["fahrt"], plan["ankunft"]
    if a.laenge > len(fahrt):
        print(f"Nur {len(fahrt)} Fahrt-Einstellungen verfuegbar, "
              f"--laenge {a.laenge} geht nicht.", file=sys.stderr)
        return 1

    a.ziel.mkdir(parents=True, exist_ok=True)
    cache = a.ziel / "_segmente"
    cache.mkdir(exist_ok=True)

    # Jedes Segment genau einmal schneiden, danach nur noch kleben.
    def hole(seg: dict) -> Path:
        name = f"{seg['start']:05.1f}_{seg['dauer']:.1f}.mp4".replace(".", "-", 1)
        return schneide(quelle, seg["start"], seg["dauer"], cache / name)

    fahrt_teile = [hole(s) for s in fahrt]
    ankunft_teile = [hole(s) for s in ankunft]

    wuerfel = random.Random(a.seed)
    gesehen: set[tuple[int, ...]] = set()
    gebaut = 0
    versuche = 0

    while gebaut < a.anzahl and versuche < a.anzahl * 50:
        versuche += 1
        idx = tuple(wuerfel.sample(range(len(fahrt_teile)), a.laenge))
        if idx in gesehen:          # dieselbe Reihenfolge nie zweimal
            continue
        gesehen.add(idx)
        gebaut += 1
        ziel = a.ziel / f"variante_{gebaut:02d}.mp4"
        klebe([fahrt_teile[i] for i in idx] + ankunft_teile, ziel)
        folge = " → ".join(fahrt[i]["name"] for i in idx)
        print(f"{ziel.name}: {folge} → {ankunft[0]['name']} …")

    if gebaut < a.anzahl:
        print(f"Nur {gebaut} verschiedene Varianten moeglich.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
