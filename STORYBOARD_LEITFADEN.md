# Storyboard-Blätter mit gpt_image_2 — Leitfaden

Das Konstante beim Blattbau. Die fünfzehn Panel-Beschreibungen entstehen pro
Motiv neu und stehen in der Blatt-Datei
([Streifenfahrt](STORYBOARD_STREIFENFAHRT.md) · [Tatort](STORYBOARD_TATORT.md));
dort auch die Befunde und Belege zu jedem Lauf.

Zusätzlich gilt [`CLAUDE.md`](CLAUDE.md): §1 Datenschutz, §2 keine
Nachahmungs-Anleitung, §6 Ton, §7 Ship-Gate.

```
Referenzbild (Objekt-Sheet oder echtes Foto)   gpt_image_2 t2i / vorhanden
        │  medias[role=image]
        ▼
Storyboard-Blatt  15 Panels, 5×3, 2:3          gpt_image_2 t2i
        │  Abnahme nach §7
        ▼
Ein Videolauf, 15 s                            seedance_2_0, image_references
        ▼
Schnitt in Einzeleinstellungen → Bucket
```

---

## 1. Aufbau

Modell: **`gpt_image_2`** („GPT Image 2", OpenAI). Kein anderes — Nano Banana
kann die Typografie nicht.

| | Wert |
|---|---|
| Panels | **15**, Raster **5 Spalten × 3 Zeilen**, Lesefolge zeilenweise von oben links |
| Blattformat | `aspect_ratio: "2:3"` (ergibt Panels ≈ 9:16) |
| Auflösung | `resolution: "4k"` |
| Qualität | `quality: "high"` |
| Zeitraster | **1 Sekunde je Panel**, 00:00–00:15 |
| Referenz | `medias: [{role: "image", value: "<job_id>"}]`, Pflicht (§4) |
| Kosten | ~12 Credits je Blatt |

⚠️ **`resolution` und `quality` müssen gesetzt werden.** Die Defaults sind `1k`
und `low` — damit wird die Beschriftung unlesbar und das Blatt ist Ausschuss.

Wer weniger Einstellungen braucht, **streicht Panels — er baut kein neues
Raster.**

---

## 2. Look und Umfeld

Ein Blatt trägt **genau einen** Look, niemals eine Mischung.

| Look | erlaubt für |
|---|---|
| **NACHT** | c1 Polizei, c3 Täter — im Zweifel alles |
| **DÄMMERUNG** | nur c2 Tatobjekt |
| **TAG** | nur c2 Tatobjekt („der Morgen danach") |

Die Blöcke werden **wörtlich** übernommen, nie umformuliert.

**NACHT**
```
Night. Wet asphalt, cold colour temperature, harsh overhead street lamps, deep shadows, high contrast. Gritty photojournalistic aesthetic, documentary still, 35mm lens, authentic Germany, photorealistic 4k. Every panel has a visible light source inside the frame and the main subject stays clearly readable — never a subject that is only a black silhouette against darkness. Blue light reflections appear only in panels where a blue light source is actually visible in the frame.
```

**DÄMMERUNG**
```
Blue hour shortly before sunrise. Overcast sky, wet ground, street lamps still lit, no sun, no hard shadows. Gritty photojournalistic aesthetic, documentary still, 35mm lens, authentic Germany, photorealistic 4k. Every panel has a visible light source inside the frame and the main subject stays clearly readable.
```

**TAG**
```
Overcast grey daylight, the morning after. Wet ground, flat soft light, no sun, no hard shadows, no blue light anywhere. Gritty photojournalistic aesthetic, documentary still, 35mm lens, authentic Germany, photorealistic 4k. The main subject stays clearly readable in every panel.
```

**Umfeld** — kein Panel zeigt dieselbe Straße wie das vorige. Parkbuchten mal
belegt, mal leer; Fassaden wechseln; mal ein Ladenlokal, mal nur Hauseingänge.
Das Umfeld passt zur Tageszeit des Looks. Tageszeit-Satz entsprechend wählen:

```
ENVIRONMENT — the street is alive and never repeats. Every panel shows a different stretch of a German city street: parking bays sometimes filled with parked German cars and sometimes empty, building fronts changing from panel to panel between 19th century apartment houses, plain post-war blocks and modern facades, here and there a small shop front or a bakery, elsewhere only residential entrances. Add trees, hedges, front gardens, bicycle stands, wheelie bins, a bus stop, tram tracks or road works. German street furniture only: German kerbs, German traffic signs, German parked cars. Never repeat a facade, never a regular pattern of identical windows, never the same stretch of street in two panels.
AT NIGHT: roller shutters closed, most windows dark and only a few lit, shops unlit, nobody on the street.
IN DAYLIGHT: roller shutters up, more parked cars, a delivery van, a few distant people too far away to be recognizable.
```

---

## 3. Beschriftung

Englisch, **immer außerhalb der Panels**. Je Panel: Nummer oben links ·
Einstellungsgröße in Großbuchstaben (WIDE SHOT, MEDIUM SHOT, CLOSE-UP, MACRO,
DETAIL, LOW ANGLE, INTERIOR, POV, TRACKING, AERIAL) · ein bis zwei Zeilen
Beschreibung mit **ausgeschriebener Kamerabewegung** · Timecode rechtsbündig.
Unten Titelblock und NOTES-Kasten.

**Keine Legende, keine Symbole, keine Pfeile.** Information steht unter dem
Panel, nie im Panel — alles im Panel ist Bildinhalt und landet im Video.

**Der Wortlaut jeder Beschriftung wird vorgegeben**, nicht dem Modell
überlassen: Er steht im `Caption:`-Teil der Panel-Zeile (§6).

```
A professional storyboard sheet printed on slightly aged off-white paper with a thin dark border, five columns by three rows, fifteen numbered portrait film frames in a clean grid with thin gutters. A small number badge sits in the top left corner of every frame. Underneath each frame, on the sheet and never inside the picture: the shot size in bold capitals, one or two lines of description in normal sentence case, and the timecode right-aligned. At the bottom of the sheet a title block reading "<TITEL>" above "15-SECOND SHORT · STORYBOARD SHEET" and "FORMAT: 9:16 · STYLE: PHOTOREALISTIC DOCUMENTARY", beside it a NOTES box with three short production notes. Spell every word on the sheet correctly. No legend, no icons, no arrows, no symbols anywhere.
```

---

## 4. Referenzbild — Pflicht

Zulässig: **Objekt-Sheet** (3×3, neun Ansichten, neutraler Hintergrund, ohne
jede Beschriftung) oder **echtes Foto**. Bindung direkt nach dem Blatt-Block:

```
Use the <Objekt> from the reference image in every panel: identical model, identical shape, identical colour, identical markings and identical proportions in every frame.
```

### Register der gültigen Referenzen

| Referenz | job_id / Pfad | gilt für | Stand |
|---|---|---|---|
| Fahrzeug-Sheet 3×3, dt. Streifenwagen (Mercedes E-Klasse T-Modell) | `4ff8bf51-eb8d-489d-9de1-01b5d45c69a3` | `blaulicht` | 06.08.2026, abgenommen |
| Automat gesprengt, echtes Foto, freigestellt, Typenschild retuschiert | `broll/master/master_automat_gesprengt.png` | `effekt` (nur i2v, nie im Blatt) | 06.08.2026 |

Neue Referenzen **vor** dem ersten Blatt hier eintragen.

---

## 5. Verbote

### 5.1 Lesbare Schrift

Kennzeichen und Displays sind **verpixelt**, nicht leer. Schilder sind echte
deutsche DIN-Schilder, generisch und unscharf. Einzige Ausnahme: **POLIZEI** auf
Polizeifahrzeug oder Uniform.

```
TEXT RULES, two levels, both mandatory.
SHEET LEVEL: the sheet itself is a printed page and carries lettering — panel numbers, shot sizes, descriptions, timecodes, title block, notes. Spell all of it correctly.
PANEL LEVEL: inside the film frames there is no readable text at all. License plates, dashboard displays, radio displays and any other screen are pixelated the way a television documentary anonymizes them — a visible mosaic patch, never an empty plate and never a blank screen. Road signs are authentic German DIN traffic signs with correct shapes and colours, but generic and out of focus. Posters, shopfronts, stickers and labels are tiny, generic and blurred beyond legibility. Do not invent any words. The only exception: the word "POLIZEI" on a police vehicle or a police uniform, and nowhere else.
```

**Der Ausnahmesatz wird gestrichen, wenn kein Polizeifahrzeug und keine Uniform
auf dem Blatt vorkommt** — ohne Träger im Bild liest das Modell die Wortliste
als Bestellung.

### 5.2 Objekte mit echter Schrift

**Automat, Absperrband, Werbetafel, Ladenfront gehören nie in ein Blatt.** Sie
kommen aus dem echten Foto per Bild-zu-Video.

### 5.3 Personen

```
PEOPLE: no recognizable faces anywhere. People are seen from behind, in half profile turned away, or in shadow. No regional coat of arms, no state emblem and no unit patch on any uniform sleeve — the only marking on a uniform is the word "POLIZEI". When two people get into or out of a car, they use opposite sides — driver on the left, passenger on the right — never the same door.
```

### 5.4 Der Vorgang der Tat

**Das Ergebnis darf ins Bild, der Vorgang nicht** (CLAUDE.md §2).

| erlaubt | verboten |
|---|---|
| Aufgebogene Klappe, Brandfleck, leeres Fach | Hand mit Werkzeug am Schloss |
| Trümmer und Splitter am Boden | Jemand bringt etwas am Automaten an oder führt etwas ein |
| Absperrband, Spurensicherung, leerer Tatort | Flasche, Schlauch, Kanister, Kabel am Tatobjekt |
| Täter-Silhouetten beim Weglaufen | Zündung, Explosion, Nahaufnahme des Aufbrechens |

### 5.5 Sprache des Prompts

Kein Reißer-Vokabular („masterpiece quality", „epic", „dramatic action").
Keine Wörter aus `ANIM_VERBOTEN` — Feuer, Flammen, Funken, Explosion —
**auch nicht verneint**, der Moderationsfilter wertet ohne Verneinung.

---

## 6. Prompt-Bauplan

**Der Prompt ist EIN durchgehender englischer Text**, keine Liste von
Einzelprompts, keine deutschen Reste. Reihenfolge verbindlich:

1. **Blatt-Block** (§3), Titel eingesetzt
2. **Referenzbindung** (§4)
3. **Die fünfzehn Panels** — fallweise, im Muster unten
4. **Look-Block** (§2), genau einer
5. **Umfeld-Block** (§2) mit passendem Tageszeit-Satz
6. **Textregel-Block** (§5.1), Ausnahmesatz je nach Motiv
7. **Personenregel** (§5.3), wenn Menschen vorkommen

### Muster einer Panel-Zeile

```
Panel <n> (<Position>) — <SHOT SIZE>: <Motiv und Handlung in einem Satz>, <Umfeld dieses Panels>, <Kamerabewegung>. Caption: "<SHOT SIZE>" / "<ein bis zwei Zeilen Beschreibung>" / "<00:0n - 00:0n+1>".
```

Beispiel:

```
Panel 4 (row 1, column 4) — LOW ANGLE: the patrol car passes an empty parking bay in front of a plain post-war apartment block, a hedge and two wheelie bins at the kerb, camera static at knee height. Caption: "LOW ANGLE" / "The car passes an empty parking bay, blue light sweeping the facade." / "00:03 - 00:04".
```

`Position` wird für alle fünfzehn Panels ausgeschrieben (`row 1, column 1` bis
`row 3, column 5`), damit Nummerierung und Lesefolge nicht auseinanderlaufen.

### Regeln für die Panel-Liste

- Keine zwei ähnlichen Kompositionen hintereinander.
- Erkennbare Dramaturgie: Anfang, Zuspitzung, Ende.
- **Jedes Panel nennt sein eigenes Umfeld** — der Umfeld-Block allein reicht
  nicht, er sagt nur, *dass* sich etwas ändern soll.
- Einstellungsgrößen mischen, nie zweimal dieselbe hintereinander.

---

## 7. Abnahme

**Vor dem Videolauf**, Panel für Panel. Blatt 12 Credits, Videolauf 117–135.

- [ ] Lesbare Schrift **in** einem Bild? Displays, Schilder, Plakate, Aufkleber.
- [ ] Kennzeichen und Displays verpixelt — nicht leer, nicht lesbar?
- [ ] Zeigt ein Panel den Vorgang statt des Ergebnisses? (§5.4)
- [ ] Wiederholt sich eine Fassade, eine Parkbucht, dieselbe Straße? Passt das
      Umfeld zur Tageszeit? (§2)
- [ ] Gesicht erkennbar? Wappen oder Abzeichen auf einem Ärmel?
- [ ] Steigen zwei Personen auf **derselben** Seite ein oder aus?
- [ ] Hauptmotiv in **jedem** Panel klar erkennbar — auf dem Handy prüfen.
- [ ] Objekt in allen fünfzehn Panels identisch (Modell, Form, Farbe, Beklebung)?
- [ ] Zwei ähnliche Kompositionen hintereinander?
- [ ] Beschriftung korrekt geschrieben — Wörter **und** Timecodes?
- [ ] Nur ein Look auf dem Blatt?
- [ ] Ein schrifttragendes Objekt versehentlich im Bild gelandet?

**Ein Blatt wird neu gezogen, nie editiert** — ein Edit zerstört die Typografie
und die Auflösung.

### Protokollpflicht

Jedes gezogene Blatt bekommt einen Eintrag in seiner Blatt-Datei:

```markdown
**Blatt vom <Datum> — `job_id <…>`**
Parameter: gpt_image_2 · 2:3 · 4k · quality high · Referenz `<job_id>` · <n> Credits
Befund: <was sitzt, was nicht>
Status: abgenommen | Auflage: <vor dem Videolauf zu tun> | verworfen
```

---

## 8. Übergabe an Seedance

```
Turn this storyboard into one continuous photo-realistic cinematic sequence, following the panels in order from top left to bottom right. Read the sheet as instructions only: do not show panels, frames, grids, paper, numbers, captions or timecodes. Documentary handheld feel, cold colour grade, deep shadows. No music, no titles, no captions, no on-screen text and no readable text of any kind. Keep <das Objekt> identical in every shot.
```

| Parameter | Wert |
|---|---|
| Modell | `seedance_2_0` |
| Referenz | `medias: [{role: "image_references", value: "<Blatt-job_id>"}]` |
| Format / Dauer | `9:16` · `15` s |
| Qualität | `1080p` · `mode: std` · `bitrate: high` |
| Ton | **`generate_audio: false`** (Default ist `true`) |
| Genre | `drama` |
| Preset | **keins** |
| vorher | `get_cost: true` · `pruefe_anim_prompt()` über den Text |

**Nach dem Lauf erneut prüfen:** Kennzeichen, Gesichter, Schrift. Im Render
prüfen, nicht im Prompt hoffen. Mit Ausschuss ist zu rechnen — Panels fallen
aus oder kommen doppelt.

---

## 9. Werkzeugregeln

| nie | stattdessen |
|---|---|
| Beschriftetes Blatt editieren | neu ziehen (§7) |
| `gpt_image_2` zum Freistellen | `remove_background` oder `tools/freistellen.py` (SAM 2) |
| Schrifttragende Objekte im Blatt | echtes Foto per i2v mit Schutzformel (§5.2) |
| US-Fahrzeuge | deutsche Modelle, auch im parkenden Hintergrund |
| Preset im Videolauf | nichts (§8) |

---

## Offen

- **Prüfskript** (Texterkennung über die Panel-Flächen, Helligkeits-Median je
  Panel) — nicht gebaut, CLAUDE.md §7.
- **Basis-Look als Code-Konstante** in `core/broll_prompts.py`, sobald ein
  Blatt-Bauer entsteht. Bis dahin ist dieser Leitfaden die Wahrheit.
- Blaulicht-spezifisch. Für andere Kanäle taugt die Mechanik, nicht die Regeln.
