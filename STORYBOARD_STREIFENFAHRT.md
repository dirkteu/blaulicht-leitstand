# Storyboard — Streifenfahrt bei Nacht · Higgsfield

Zwei Beamte, Einsatzfahrt unter Blaulicht durch eine deutsche Stadt bei Nacht,
mehrere Blickwinkel. Kategorie `blaulicht`, Block **c1**. Format **9:16**.

Diese Datei ist der **Bildplan dieses einen Motivs** — Panel-Liste, Prompts,
Protokoll der Läufe. Alles Konstante (Raster, Basis-Look, Beschriftung,
Verbote, Abnahme, Übergabe an Seedance) steht im
[**Leitfaden**](STORYBOARD_LEITFADEN.md) und wird hier nicht wiederholt.

---

## Was im Video steht — und was es hier ändert

**„I gave Seedance 2.0 my entire storyboard. Here's what happened."** (Edit
Illusions, 11:43). Der Kern in einem Satz:

> **Das Storyboard wird nicht abgearbeitet, sondern als EIN Bild abgegeben.**
> Ein einziges Panel-Raster (er nutzt 5×5, 15, 8 Panels) geht in Seedance 2.0,
> und heraus kommt ein durchgeschnittener Film — nicht Clip für Clip.

Belegstellen aus der Szenenanalyse:

| Zeit | Befund |
|---|---|
| 0:21–0:57 | Das Rasterbild-Prompt lässt er sich von einem LLM schreiben („make me a storyboard of 5×5 panels"). Genau das ist diese Datei. |
| 0:57–1:45 | **GPT Image 2 gegen Nano Banana 2: Nano Banana wird cartoonig, GPT Image 2 bleibt fotorealistisch.** Für unseren dokumentarischen Look ist gpt_image_2 damit belegt richtig. |
| 1:45–2:55 | **Character-Sheet-Trick:** eigenes Foto → 9-Feld-Sheet → als Referenz an die Storyboard-Generierung. Danach trägt *jedes* Panel dieselbe Figur. |
| 4:39–5:39 | Seedance 2.0, „photo-realistic cinematic, no music", 14 s, ein Lauf für den ganzen Film. |
| 5:39 | Ehrliches Ergebnis: „It followed the storyboard nicely. We have all frames **except the last one**." |
| 6:22–9:15 | Übergänge einzeln nachgeneriert, mehrere Takes, teils zwei Figuren im Bild oder falsche Proportionen. |
| 9:35–11:07 | Der Rest ist Schnitt (DaVinci): Takes mischen, Teile wegschneiden. Der Gewinn ist **Zeit und Credits**, nicht Perfektion. |

**Das Character-Sheet ist unser Fahrzeug-Sheet.** Der Trick ist mechanisch
dasselbe, was in [`BROLL_PLAN.md`](BROLL_PLAN.md) unter „Konsistenz kommt aus
Pixeln, nicht aus Prompts" steht — nur eine Stufe früher angesetzt: nicht je
Clip ein Startbild, sondern **ein Referenzblatt, das alle Panels gleichzeitig
bindet**. Damit ist der zweistufige Master-und-Edit-Weg von vorhin überholt; er
bleibt unten als Weg B für Nachschüsse stehen.

**Was der Weg nicht liefert:** einen einzelnen sauberen B-Roll-Clip. Seedance
schneidet. Für den Topf werden die Einzeleinstellungen hinterher aus dem Ergebnis
**herausgeschnitten** — genau wie er es im Video macht. Die `SCHUTZFORMEL`
(„no cuts") gilt weiterhin für Weg B, nicht hier.

---

## Weg A — Panel-Raster (neu, primär)

```
Fahrzeug-Sheet (3×3)   gpt_image_2 t2i
        │  als image-Referenz
        ▼
Storyboard-Sheet       gpt_image_2 t2i + medias[role=image]
   (2×2 Panels, 9:16)
        ▼
seedance_2_0 i2v       medias[role=image_references], 15 s, 9:16, ohne Audio
        ▼
Schnitt: in Einzeleinstellungen zerlegen → Topf `blaulicht`
```

### Das Blatt sieht aus wie ein Blatt — Korrektur 06.08.2026

Die erste Fassung dieses Plans hat die Sheets ausdrücklich **ohne** Nummern,
Captions und Timecodes gebaut („no captions, no panel numbers, no text
anywhere"). Das war falsch. Ein Storyboard-Sheet im Sinne des Videos trägt
genau diese Schrift: nummerierte Panels, unter jedem Panel Einstellungsgröße
und ein Satz Beschreibung, rechts der Timecode, unten Titelblock, NOTES und
Legende. Die Textregeln aus CLAUDE.md gelten für das **Video**, nicht für das
Arbeitsblatt — deshalb muss der Seedance-Prompt das Blatt als Blatt lesen und
die Beschriftung nicht abbilden.

**Erzeugt: `job_id ffacbb77-1d9f-4a01-8f19-7857be7f577f`**, 2:3 · 4k · quality
high, 12 Credits. 15 Panels (5×3), 1 Sekunde je Panel, 15 Sekunden gesamt —
exakt das Maximum von Seedance. Alle Beschriftungen sind sauber gesetzt und
richtig geschrieben, das Fahrzeug ist über alle 15 Panels dasselbe.

Zwei Restpunkte:

- **Panel 7 zeigt „EINSATZ" im Funkgerätdisplay.** Erfundene Schrift, wenn auch
  korrekt geschrieben und passend. Für das Blatt harmlos, im Video wäre es
  lesbarer Text — der Seedance-Prompt muss ihn ausschließen.
- **Panel 6 (Beifahrer am Funk)** ist dunkler als der erste Versuch und ohne
  Ärmelwappen, das Profil bleibt aber ansatzweise erkennbar. Im Zweifel
  wegschneiden.

Die zwei 2×2-Sheets von vorhin (`834510f2…`, `84d4eea7…`) sind damit
**überholt**. Sie bleiben brauchbar, falls einzelne Einstellungen langsamer
laufen sollen — siehe die Rasterrechnung darunter.

### Korrektur 08.08.2026 — die alte Rasterrechnung war falsch

Hier stand, das Raster müsse **quadratisch** sein, damit jedes Panel 9:16
ergibt — daraus folgte die Empfehlung „zwei Blätter 2×2". Das galt für ein
9:16-**Blatt**. Auf einem **2:3-Blatt** ergibt 5×3 Panels von etwa 0,58, weil
die Beschriftungszeile die überschüssige Höhe frisst — praktisch 9:16. Genau
deshalb funktioniert das 15-Panel-Blatt oben.

**Gültig ist der [Leitfaden](STORYBOARD_LEITFADEN.md) §1:** immer 15 Panels,
5×3, Blatt 2:3. Dort stehen auch alle Parameter für Bild- und Videolauf.

`tools/kader.py` entfällt: gpt_image_2 liefert das Format direkt.

---

## Schritt 1 — Fahrzeug-Sheet (gpt_image_2, t2i)

Das Blatt, das alle Panels bindet. Wird **einmal** erzeugt und gesichtet.

```
A 3x3 grid character sheet of ONE single vehicle, nine views of the SAME car, thin white gutters between the cells, no captions, no numbers, no lettering of any kind on the sheet itself.

The vehicle: a German police patrol car, Mercedes-Benz C-Class estate, silver body with reflective blue side stripes and the word "POLIZEI" on the doors, a blue LED light bar across the roof, number plate not readable.

The nine views: front, three-quarter front left, side left, three-quarter rear left, rear, three-quarter rear right, side right, top-down, and a close-up of the roof light bar. Identical model, identical proportions, identical livery and identical colour in every cell.

Neutral dark grey studio background, even cold lighting, photorealistic, 4k, no people, no other vehicles.
```

**Erzeugt am 06.08.2026 — abgenommen.**
`job_id 4ff8bf51-eb8d-489d-9de1-01b5d45c69a3`, 1:1, 4k, quality high, 12 Credits.
Neun Zellen, ein durchgehend identisches Fahrzeug, „POLIZEI" in jeder Zelle
korrekt geschrieben (kein Kauderwelsch), Kennzeichenfelder leer.
**Abweichung:** Das Modell hat eine **E-Klasse T-Modell (W213)** gebaut, nicht
die C-Klasse. Bleibt deutsch, bleibt Mercedes, bleibt in allen neun Zellen
gleich — also angenommen statt nachgeneriert. Wer die C-Klasse zwingend will,
zahlt 12 Credits für einen zweiten Versuch.

Deutsch gleichwertig, falls das Modell die C-Klasse nicht trifft: BMW 3 Series
Touring, VW Passat Variant, Audi A4 Avant, Opel Astra Sports Tourer.
**Kein US-Modell** — ein Charger oder Explorer kippt den Clip ins
Amerikanische. Der parkende Verkehr im Hintergrund bleibt ebenfalls deutsch
(Golf, Passat, 3er, A4, Astra).

## Schritt 2 — Storyboard-Sheets (gpt_image_2, t2i + Referenz)

Beide Sheets mit dem Fahrzeug-Sheet als `medias[role=image]`.

### Sheet 1 — die Fahrt

```
A 2x2 storyboard grid, four cinematic film frames, thin white gutters, no captions, no panel numbers, no text anywhere.

Use the police patrol car from the reference image in every panel: identical model, identical body shape, identical silver-and-blue livery, identical "POLIZEI" lettering, identical roof light bar.

Panel 1 (top left): a wide view of an empty wet main road at night, camera 30 centimetres above the asphalt, the car entering from the right in the middle distance, street lamps receding into the depth, blue light reflecting far across the wet surface.
Panel 2 (top right): a head-on view from street level, the car centred and coming straight toward the camera, headlights flaring into the lens, the roof light bar lit.
Panel 3 (bottom left): the interior seen from the rear bench between the two front head restraints, two officers in dark blue uniform from behind, only the backs of their heads and shoulders, faces never visible, dashboard glowing, rain on the windscreen.
Panel 4 (bottom right): a close-up of the front passenger in half profile, the face turned away and mostly in shadow, one hand lifting a radio handset, alternating blue flashes across the features.

Style for all four panels: gritty photojournalistic aesthetic, documentary still, 35mm lens, cold and tense atmosphere, harsh overhead street lamp lighting, flickering blue light reflections on wet asphalt, high contrast, deep shadows, authentic Germany, photorealistic 4k.

STRICT TEXT RULE: the ONLY readable word allowed anywhere is "POLIZEI", and only on the police vehicle itself. Every other sign, poster, shopfront, sticker, label, dashboard display and license plate must be tiny, generic and blurred beyond legibility. Do not write any other words into the image.
```

### Sheet 2 — Fahrt und Ankunft

```
A 2x2 storyboard grid, four cinematic film frames, thin white gutters, no captions, no panel numbers, no text anywhere.

Use the police patrol car from the reference image in every panel: identical model, identical body shape, identical silver-and-blue livery, identical "POLIZEI" lettering, identical roof light bar.

Panel 1 (top left): a forward view from bonnet height along a wet German city street, white centre line markings running toward the camera, parked German cars along the kerb, blue light flickering across the building facades, the car itself not visible.
Panel 2 (top right): a side view of the car in motion, camera travelling alongside at the same speed, the "POLIZEI" lettering on the door sharp, the building facades behind it stretched into motion blur.
Panel 3 (bottom left): a high aerial view looking steeply down on a dark grid of German streets and rooftops at night, the car small in the frame as a single travelling point of blue light, wet roads reflecting the street lamps.
Panel 4 (bottom right): a wide view from behind as the car stands at the kerb of a dark residential street, tail lights glowing, both front doors open, two officers as dark silhouettes stepping out with their backs to the camera, faces never visible, the roof light bar still lit.

Style for all four panels: gritty photojournalistic aesthetic, documentary still, 35mm lens, cold and tense atmosphere, harsh overhead street lamp lighting, flickering blue light reflections on wet asphalt, high contrast, deep shadows, authentic Germany, photorealistic 4k.

STRICT TEXT RULE: the ONLY readable word allowed anywhere is "POLIZEI", and only on the police vehicle itself. Every other sign, poster, shopfront, sticker, label, dashboard display and license plate must be tiny, generic and blurred beyond legibility. Do not write any other words into the image.
```

**Erzeugt am 06.08.2026, je 9:16 · 4k · quality high, zusammen 24 Credits.**

| Sheet | `job_id` | Befund |
|---|---|---|
| 1 — die Fahrt | `834510f2-b378-4c80-95cc-f3d24b0ff6f6` | drei Panels sitzen, Panel 4 mit Auflage (unten) |
| 2 — Fahrt und Ankunft | `84d4eea7-7737-4354-bd21-ccad48475498` | **alle vier sitzen** |

Was durchgehend stimmt: Fahrzeug in allen Panels dasselbe, „POLIZEI" überall
korrekt geschrieben, Kennzeichenfelder leer, keine erfundene Schrift im
Hintergrund. Die harte `STRICT TEXT RULE` hat gehalten — anders als bei der
cctv-Runde vom 01.08.

**Eine Auflage: Sheet 1, Panel 4 (Beifahrer am Funk).** Zwei Befunde, beide
gegen `STIL_BASIS` („no recognizable faces"):

1. Das Profil ist deutlich ausgeleuchtet und **erkennbar** — gewollt war ein
   Gesicht im Schatten, abgewandt.
2. Auf dem Ärmel sitzt ein **Landeswappen**. Das benennt ein konkretes
   Bundesland und arbeitet damit gegen §1 Datenschutz, der den Ort bewusst auf
   Stadtebene hält.

Vor dem Seedance-Lauf entweder das Panel über Weg B neu ziehen (12 Credits,
Gesicht härter abwenden, Ärmel aus dem Bild) oder die Einstellung ganz fallen
lassen — dann trägt Sheet 1 nur drei Einstellungen.

**Zweiter Punkt, kein Fehler, aber eine Entscheidung:** Die Sheets sind sehr
dunkel. Auf einem Handydisplay bei Tageslicht säuft besonders die
Vogelperspektive ab. Entweder im Seedance-Prompt heller anlegen oder beim
Rendern anheben.

## Schritt 3 — Seedance 2.0, je Blatt ein Lauf

Übergabesatz und Parameter stehen im [Leitfaden §8](STORYBOARD_LEITFADEN.md).
Für dieses Motiv wird `<das Objekt>` durch `the vehicle` ersetzt.

Der Lauf vom 06.08. benutzte noch die alte Fassung ohne den Satz „Read the
sheet as instructions only" — nachträglich ergänzt, weil er kostenlos ist und
das einzige absichert, worauf hier alles beruht.

### Erster Lauf — 06.08.2026, `job_id a968b71d-8245-4b62-a5de-eaa19ffb94b6`

**Seedance 2.0** (ein „Seedance 2.5" gibt es im Katalog nicht; 1.5 Pro kennt nur
Start-/Endbild und kann mit einem Blatt nichts anfangen). 9:16 · 15 s · 1080p ·
`mode std` · `bitrate high` · `genre drama` · `generate_audio false` ·
`medias[image_references] = <Sheet>`. **135 Credits.** Das angebotene Preset
„IN THE DARK" wurde abgelehnt — es hätte seinen Look über das Storyboard gelegt.

**Der Kernbeweis steht: Das Blatt wurde als Anweisung gelesen, nicht als Bild.**
Kein Panelrahmen, kein Raster, kein Papier, keine Nummer, keine Caption im
Video. Die Reihenfolge stimmt weitgehend, das Fahrzeug bleibt über alle
Einstellungen dasselbe.

Vier Befunde aus der Sichtung (Kontaktabzug: `fps=1`, 15 Bilder):

1. **Lesbares Kennzeichen „RN · 65021" bei Sekunde 1.** Klarer Verstoß gegen
   `STIL_BASIS` („no readable license plates"). Der Prompt hatte es verboten —
   das Modell hat sich nicht daran gehalten. Muss maskiert werden oder die
   Einstellung fliegt. **Merksatz: Kennzeichen sind im Render zu prüfen, nicht
   im Prompt zu hoffen.**
2. **Ärmelwappen und erkennbares Profil** bei Sekunde 5 — derselbe Befund wie
   auf dem Blatt, unverändert ins Video durchgereicht.
3. **Zwei fast identische POV-Einstellungen** (Sekunde 6 und 7). Eine der
   fünfzehn Sekunden ist verschenkt.
4. **Panel 1 kam nicht** — statt der Totale mit einfahrendem Wagen beginnt der
   Film mit einer POV. Deckt sich mit dem Video („all frames except the last
   one"): ein Panel fällt, damit ist zu rechnen.

## Schritt 4 — Schnitt

Aus jedem 15-Sekünder die vier Einstellungen einzeln herausschneiden und als
`broll_blaulicht_NN.mp4` in den Bucket legen. Was unbrauchbar ist, fliegt raus —
im Video kam **eine von acht Panels gar nicht** im Ergebnis an, und mehrere
Läufe brauchten zwei bis drei Takes. Damit ist zu rechnen, nicht zu hadern.

---

## Würfeln — viele Videos aus einem Lauf

Die Fahrt-Einstellungen sind untereinander austauschbar. Die Ankunft ist es
nicht: **Wer aussteigt, steigt am Ende aus.** Also wird der Fahrt-Teil gewürfelt
und die Ankunft fest angehängt — [`tools/wuerfeln.py`](tools/wuerfeln.py).

```bash
python tools/wuerfeln.py schnittliste_streifenfahrt.json --anzahl 6 --laenge 5
```

Aus dem Lauf vom 06.08. bleiben nach der Sichtung **9 Fahrt-Einstellungen** und
**3 Ankunft-Einstellungen**; gesperrt sind drei (Kennzeichen, Ärmelwappen,
Dublette). Bei 5 gezogenen Fahrt-Einstellungen und fester Ankunft sind das
**9·8·7·6·5 = 15 120 mögliche Abfolgen** à 8 Sekunden.

Die Schnittliste ist bewusst eine JSON-Datei und keine Konstante im Code: Die
Zeitmarken kommen aus der Sichtung **eines konkreten Laufs**, ein zweiter Lauf
hat andere. Die gesperrten Segmente stehen mit Begründung darin, damit sie
niemand später versehentlich wieder freischaltet.

> **15 120 Abfolgen sind nicht 15 120 verschiedene Videos.** Es sind
> Umsortierungen derselben neun Sekunden. Wer drei Clips hintereinander sieht,
> erkennt das Material wieder — die Vielfalt liegt in der Reihenfolge, nicht im
> Bild. Gegen die YouTube-Regel zu „massenproduziert, repetitiv" (CLAUDE.md §6)
> hilft das Würfeln nicht; dafür braucht es weitere Läufe mit anderen Sheets.

## Weg B — Master und Edit (Rückfall)

Für einzelne Nachschüsse, wenn aus Weg A ein Motiv fehlt, und für die drei
Einstellungen, die im 2×2-Raster keinen Platz mehr hatten:
**Cockpit-Detail** (Hände am Lenkrad, Funkgerät), **Detail Dachbalken**
(Regentropfen, Blau ins Objektiv), **Radkasten bodennah** (Reifen durch die
Pfütze).

Ein gesichtetes Standbild aus Weg A dient als `medias[role=image]`, der
Edit-Prompt ist zweiteilig — **erst was bleiben muss, dann was sich ändert**
(dieselbe Reihenfolge wie `build_umfaerben_prompt()`; umgekehrt formuliert räumt
das Modell zu viel weg):

```
Two separate instructions, both mandatory.

VEHICLE, keep completely unchanged: identical car model, identical body shape, identical silver-and-blue livery, identical "POLIZEI" lettering, identical roof light bar, identical colour and proportions. Only the camera position and the surroundings change.

SCENE, change to: <die neue Einstellung in einem Satz>

<STIL_BASIS + TEXT_REGEL_SZENE bzw. …_POLIZEI>
```

Danach `seedance_2_0` als echtes i2v mit **einer** Kamerabewegung und der
Schutzformel — dort gilt „no cuts" weiter, weil das Ergebnis ein einzelner
Clip sein soll:

```
Keep the vehicle, its markings, its position and the entire scene exactly as in
the image. Do not add, remove or change any object. No cuts.
```

⚠️ Diese Fassung ist **nicht** die bestehende `SCHUTZFORMEL` — die spricht von
„the machine" und verbietet mit „no people" genau das, was bei der Ankunft
passieren soll (Beamte steigen aus).

---

## Offene Punkte

- **Ship-Gate (CLAUDE.md §7):** Der Bildplan darf jetzt entstehen, die
  Generierungsläufe warten, bis die laufende Woche ihre 3 Veröffentlichungen
  hat. Stand 01.08.: 1 von 10.
- **Erledigt am 06.08.:** `image_references` ist die richtige Referenzrolle für
  ein Blatt — der Lauf hat das Raster als Anweisung gelesen, nicht als Bild.
- **Drei Auflagen vor dem nächsten Lauf** (aus dem Blatt vom 06.08.): Panel 7
  ohne Display-Schrift, Panel 6 abgewandtes Gesicht ohne Ärmelwappen, Panel 12
  heller. Alle drei sind inzwischen Regel im
  [Leitfaden](STORYBOARD_LEITFADEN.md) §2, §5.1 und §5.3.
- **`SCHUTZFORMEL_FAHRZEUG`** (Variante ohne „no people", damit die Beamten
  aussteigen dürfen) nach `core/broll_prompts.py`, sobald Weg B gebraucht wird.
- Die Einstellungen behaupten nur Anfahrt und Ankunft — keinen Tatort, keine
  Täter, kein Fluchtfahrzeug. Damit sind sie zu jeder Meldung austauschbar.
