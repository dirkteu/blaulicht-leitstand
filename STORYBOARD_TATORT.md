# Storyboard — Tatort abgesperrt (Kategorie `kulisse` / `effekt`)

Ein Beamter sperrt den Tatort mit rot-weißem Flatterband ab. 15 Einstellungen,
je 1 Sekunde — Raster, Format und Parameter nach
[**Leitfaden**](STORYBOARD_LEITFADEN.md) §1. Diese Datei enthält nur, was für
dieses Motiv gilt: Panel-Liste, Sonderregeln, Protokoll.

⚠️ **Dieses Blatt verstößt gegen [Leitfaden](STORYBOARD_LEITFADEN.md) §5.2.**
Automat und Absperrband tragen echte Schrift und dürfen deshalb nicht mehr aus
einem Blatt kommen — genau daran ist der Lauf vom 06.08. gescheitert
(„SPERRS"). Die acht Automat-Panels sind damit hinfällig; die sieben
Beamten-Panels bleiben gültig. Der Umbau steht unten.

Grundlage ist **das echte Foto des Automaten**, nicht ein generiertes Motiv.
Der Weg dorthin, am 06.08.2026 gegangen:

```
Handyfoto  →  remove_background (Higgsfield)  →  Typenschild retuschiert (PIL)
           →  broll/master/master_automat_gesprengt.png
```

Warum nicht gpt_image_2 zum Freistellen: Es **malt neu, statt auszuschneiden**.
Im Versuch wurden aus „320059 / Telefon 0800 4403333" die Fantasiewerte
„2300059 / Bei Störungen (kostenlos)", dazu erfundene Zigarettenpreise. SAM2
(`tools/freistellen.py`) und `remove_background` erhalten die echten Pixel;
`remove_background` hatte die saubereren Kanten, SAM2 die höhere Auflösung.

**Retuschiert wurde die Automatennummer.** Sie ist über den Betreiber ein
Standortidentifikator — §1 hält den Ort auf Stadt-/Gemeindeebene. Überdeckt
wurde ein Rechteck von 131 × 68 px mit dem Medianton des Gehäuses; jeder andere
Pixel ist unverändert.

---

## Die zwei eisernen Regeln

**1 — Beamter und Automat sind nie zusammen im Bild.**
Jedes Panel zeigt entweder den einen oder den anderen. Das ist keine Marotte:
Sobald beide zusammen im Bild sind, behauptet das Bild, *dieser* Beamte habe
*diesen* Automaten abgesperrt. Die Meldung gibt das nicht her. Nebenbei
entsteht der Zusammenhang so erst im Kopf des Zuschauers — dramaturgisch die
bessere Lösung. (Dieselbe Logik wie Beschluss 3 im BROLL_PLAN: „Kategorie ja,
Rezept nein".)

**2 — Der Automat hängt, er steht nicht.**
Er sitzt auf einem schlanken Pfosten, Unterkante rund **1,50 m** über dem
Boden. Ohne diese Ansage im Prompt setzt das Modell ihn auf den Boden, und der
Fehler fällt sofort auf. Sichtbarer Luftspalt und Pfosten gehören in jede
Einstellung, die den Automaten aus der Distanz zeigt.

---

## Die 15 Einstellungen

Gültiges Blatt: **`job_id c594f29c-98f1-424a-bc06-d3aed5788d6d`**
(gpt_image_2, 2:3 · 4k · quality high, 12 Credits, Referenz = der Master oben).

| # | Wer | Einstellung | Bild | s |
|---|---|---|---|---|
| 1 | Beamter | CLOSE-UP | Behandschuhte Hand hält die Bandrolle | 1 |
| 2 | Automat | WIDE | Hängt hoch am Pfosten vor der dunklen Hecke | 1 |
| 3 | Beamter | LOW ANGLE | Stiefel auf nassem Boden, Rolle hängt herab | 1 |
| 4 | Automat | DETAIL | Aufgebogene Klappe und Brandfleck, kein Boden im Bild | 1 |
| 5 | Beamter | CLOSE-UP | Zwei Hände knoten das Band an einen Pfosten | 1 |
| 6 | Automat | MEDIUM | Erste Bahn Band quer durchs Bild | 1 |
| 7 | Beamter | OVER THE SHOULDER | Rücken, Lampenkegel ins Dunkel | 1 |
| 8 | Automat | MACRO | Band zittert im Wind, Wassertropfen | 1 |
| 9 | Beamter | CLOSE-UP | Hand zieht das Band lang, es strafft sich | 1 |
| 10 | Automat | DETAIL | Tastatur und Zigarettenfächer hinter dem Band | 1 |
| 11 | Beamter | MEDIUM | Abgewandt, spricht in den Schulterfunk | 1 |
| 12 | Automat | LOW ANGLE | Steil den Pfosten hinauf, Trümmer im Vordergrund | 1 |
| 13 | Beamter | CLOSE-UP | Hände knoten den letzten Knoten und lassen los | 1 |
| 14 | Automat | WIDE | Vollständig abgesperrt, Band im Wind | 1 |
| 15 | Automat | WIDE | Band im Vordergrund, Automat klein und unscharf, niemand da | 1 |

Acht Automat-Panels, sieben Beamten-Panels, streng abwechselnd. Gesichter sind
nie erkennbar; auf den Uniformen steht „POLIZEI" und **kein Landeswappen** —
ein Wappen benennt ein Bundesland und arbeitet gegen §1.

---

## Befund: Korrigieren oder neu ziehen?

Die Montagehöhe fehlte im ersten Blatt (`b496d554-…`). Beide Wege wurden
gefahren:

| Weg | Höhe | Schrift | Auflösung | übrige Panels |
|---|---|---|---|---|
| Edit mit Nano Banana | korrigiert | **zerstört** | 848 × 1264 | bleiben erhalten |
| Neu mit gpt_image_2 | korrigiert | **sauber** | 2336 × 3504 | **neu gewürfelt** |

Der Edit-Auftrag landete nicht auf `nano_banana_2`, sondern auf
`nano_banana_flash` mit 1k-Vorgabe. Ergebnis: „The **sending** machine alone",
„A **leend** pulls", Timecodes wie „00:03 – **00:64**".

> **Regel daraus: Ein Blatt, dessen halber Zweck die Beschriftung ist, wird
> neu gezogen, nicht editiert.** Sie steht jetzt als allgemeine Regel im
> [Leitfaden §7](STORYBOARD_LEITFADEN.md); hier bleibt der Beleg.

---

## Erster Lauf — 06.08.2026, `job_id f878bba0-47ff-4839-a781-0980dcc955bd`

Seedance 2.0, 9:16 · **13 s** · 1080p · `mode std` · `bitrate high` ·
`genre drama` · `generate_audio false`, Blatt als `image_references`.
**117 Credits.** Panel 12 und 15 ausgeschlossen — doppelt angesagt, einmal als
Positivliste (1–11, 13, 14), einmal als ausdrückliches „SKIP".

Was gehalten hat:

- **12 und 15 sind draußen.** Kein Blick den Pfosten hinauf, kein
  Band-im-Vordergrund-Schluss. Der Film endet mit Panel 14.
- **Die Trennungsregel hält in jeder Sekunde** — Beamter oder Automat, nie beide.
- **Die Montagehöhe sitzt**, der Automat hängt sichtbar am Pfosten.
- Kein Panelrahmen, kein Raster, keine Caption im Video.

Was nicht hält:

- **Das Absperrband liest sich „SPERRS" und „SPERRSS".** Erfundene Schrift,
  groß und zentral im Bild — genau die Sorte Befund, die am 01.08. sechs
  cctv-Clips gekostet hat. Auch die Plakate am Automaten sind zu Matsch
  geworden.
- Die Reihenfolge driftet: Der Film beginnt mit dem Makro (Panel 8) statt mit
  der Bandrolle, und der Knoten kommt dreimal. Von dreizehn angesagten
  Einstellungen sind etwa neun verschiedene angekommen.

> **Damit ist belegt, was unten als Aufteilung vorgeschlagen war.** Alles, was
> Schrift trägt — Automat und Absperrband —, darf nicht aus dem Blatt kommen.
> Aus diesem Befund ist [Leitfaden §5.2](STORYBOARD_LEITFADEN.md) geworden.

## Nächster Schritt — und die Aufteilung, die daraus folgt

Beim Seedance-Lauf **nicht** das ganze Blatt in einem Rutsch:

- **Beamten-Panels** über das Blatt (`image_references`) — dort ist generiert
  ohnehin die einzige Quelle.
- **Automat-Panels** aus dem **echten Master** per i2v — gpt_image_2 hat den
  Automaten auf dem Blatt neu gemalt (erkennbar an den erfundenen Preisen in
  Panel 10). Für Block c2, das Tatobjekt, wäre das ein Rückschritt hinter den
  Leitsatz „Konsistenz kommt aus Pixeln".

Die Trennungsregel erzwingt diese Aufteilung ohnehin: Weil kein Panel beide
zeigt, lässt sich jede Sorte aus der Quelle ziehen, die sie richtig macht.

⚠️ **Ship-Gate (CLAUDE.md §7):** Der Bildplan darf entstehen, die Clips warten,
bis die laufende Woche ihre 3 Veröffentlichungen hat.

Verwandt: [`STORYBOARD_STREIFENFAHRT.md`](STORYBOARD_STREIFENFAHRT.md) —
dieselbe Blatt-Mechanik für die Kategorie `blaulicht`.
