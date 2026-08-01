# Projektbuch B-Roll — 31.07.2026

Wie der B-Roll-Engpass gefallen ist, was dabei schiefging und was am Ende steht.
Ein Tag, zwei Sackgassen, ein tragfähiger Weg.

**Gilt zusammen mit:** [`BROLL_PLAN.md`](BROLL_PLAN.md) (Beschlüsse, teilweise überholt) ·
[`BETRIEB.md`](BETRIEB.md) (Änderungshistorie) · [`CLAUDE.md`](CLAUDE.md) (harte Regeln)

---

## 1. Die Ausgangslage

Seit dem 26.07. stand Blaulicht still an einem Punkt: **B-Roll mit konsistentem
Automaten.** Zwei Higgsfield-Läufe mit *wörtlich identischem* `AUTOMAT_FIX`-Block
lieferten zwei verschiedene Automaten. Der Befund war eindeutig — Text erzwingt
keine Objektkonstanz.

Der beschlossene Ausweg (Masterbild-Kette) war unumgesetzt und hing selbst
wieder an einem **generierten** Master. Im Bucket lagen 5 Clips, die Pools in
`core/script.py` standen auf 1: jedes Video zeigte dieselben Bilder.

## 2. Der Leitsatz

> **Konsistenz kommt aus Pixeln, nicht aus Prompts.**

Alles, was gleich bleiben muss, wird als echtes Bildmaterial durchgereicht. Das
Modell darf ausschließlich die Bewegung erfinden. Daraus folgen zwei Wege.

## 3. Die zwei Wege

### Weg A — umfärben (Standard)

```
echtes Tagfoto → gpt_image_2 (Nacht + Hintergrund ersetzt)
               → 9:16 beschneiden → tools/kader.py → seedance_2_0 → Clip
```

Die Perspektive **kann nicht kippen, weil sie nie verlassen wird.** Kosten
~3 Credits je Bildversuch.

### Weg B — komposit (nur wenn das Objekt an einen *anderen* Ort soll)

```
echtes Foto → tools/freistellen.py → PNG mit Alpha
            → soul_location (LEERE Platte, ohne Objekt)
            → tools/komposit.py → tools/kader.py → seedance_2_0 → Clip
```

Aufwendiger, verlangt einen passenden Blickwinkel, aber ersetzt den Ort
vollständig.

**Bedient wird beides über den Slash-Command `/broll`.**

## 4. Die Werkzeuge

| Datei | Aufgabe |
|---|---|
| `tools/freistellen.py` | SAM-2-Freisteller. `--gitter`, `--box` (Einzelteile), `--nest` (Streugut per Farbtrennung im Bodenring) |
| `tools/komposit.py` | Objekt einsetzen. Misst Lichtfarbe und Pegel **aus der Platte**, Kontakt-/Wurfschatten, Lichtpfütze |
| `tools/kader.py` | Start-/Endkader. `seit` (konstanter Maßstab) und `push`, warnt ab 1,4× Hochskalierung |
| `core/broll_prompts.py` | Single Source of Truth: `ORT`, `BLICKWINKEL`, `LEER_FIX`, `SCHUTZFORMEL`, `ANIM_VERBOTEN`, `TEXT_REGEL_ECHTFOTO` + die `build_*`-Funktionen |
| `~/.claude/commands/broll.md` | Der Ablauf mit den Halten und der Kostenbremse |

Abhängigkeiten der Skripte (numpy, opencv, ultralytics) bewusst **nicht** in
`requirements.txt` — sie laufen auf dem Host, nicht in den neun Containern.

## 5. Sieben Erkenntnisse, jede an einem Fehlschlag bezahlt

1. **Nacht-Platten sind reines Natriumlicht, kein „dunkles Blau".**
   Messung `szene_b.png`: R 0,133 / G 0,095 / **B 0,012**. Kühle Schatten ergaben
   braune Pampe. → Lichtfarbe **messen**, nicht annehmen.

2. **Helligkeit nimmt zur Kamera hin zu**, nicht zur sichtbaren Lampe hin.
   Gras vorn 0,096–0,128, Asphalt Mitte 0,052.

3. **i2v-Zielkonflikt** (dreimal reproduziert): nur `start_image` → Atmosphäre,
   unkontrollierte Kamera. `start_image`+`end_image` → kontrollierte Kamera,
   **kein** Rauch. Voreinstellung ist Kontrolle: eine Fahrt aus dem Bild heraus
   ist Ausschuss, fehlender Dunst nur weniger Stimmung.

4. **Die Landung streut, sie ist nicht systematisch.** Fünf Messungen: einmal
   ~10 % zu kurz, einmal exakt, dreimal ~20 % zu weit. Eine frühere Faustregel
   („seit fährt 10 % zu kurz") beruhte auf **einem** Clip und wurde widerlegt.
   → Prüfen statt vorhersagen.

5. **Der Moderationsfilter wertet ohne Verneinung.** „no fire, no flames, no
   sparks" ließ den Job als `nsfw` abbrechen; identisches Bildmaterial lief ohne
   diese Wörter durch. → `ANIM_VERBOTEN` + harte Prüfung in
   `pruefe_anim_prompt()`.

6. **Der Blickwinkel darf keine Konstante sein.** Ein Freisteller ist ein
   2D-Ausschnitt mit *eingebackenem* Blickwinkel — nicht drehbar, nicht kippbar.
   Eine feste 45°-Konstante, geschrieben nach Foto 1, machte Foto 2 (25–30°)
   unbrauchbar. → `BLICKWINKEL` ist Auswahlliste und **Pflichtparameter**.

7. **Die `STRICT TEXT RULE` schadet beim Umfärben.** Kontrolliert isoliert:
   identisches Foto, identische Anweisungen, einzige Änderung war die Textregel.

   | | Polizei-Absperrband im Ergebnis |
   |---|---|
   | mit `STRICT TEXT RULE` | „**ab 18**" und „**POLIZEI**" — neu beschriftet |
   | mit `TEXT_REGEL_ECHTFOTO` | echte Aufschrift „POLIZEIABSPERRUNG" erhalten |

   Die Regel war für **generierte** Bilder gedacht, wo Fantasieschrift das
   Risiko ist. Auf ein **bearbeitetes Echtfoto** angewendet kehrt sie sich um.
   Sie leerte außerdem eine beschriftete Werbetafel und dünnte das Streugut aus —
   obwohl der Prompt den Vordergrund dreimal als unantastbar bezeichnete.
   → Merksatz: **Echte Schrift auf einem echten Foto ist keine Halluzination,
   sondern Beleg.**

8. **„Keine Atmosphäre mit zwei Kadern" gilt nur für Hinzuerfundenes.**
   Rauch fehlte, weil er nicht im Bild war. **Vorhandene** Elemente lassen sich
   sehr wohl bewegen, wenn man sie im Prompt benennt. Gemessen an
   `bank_02_band.mp4` (Frames auf Helligkeit normiert, Kamerafahrt
   herausgerechnet): Absperrband-Bereich 0,104 · Bäume 0,033. Das Band flattert,
   das Laub kaum. Erkenntnis 3 oben ist damit präzisiert, nicht widerlegt.

9. **Der gegradete Endkader ist ein starker Hebel, kein feiner.**
   Um ein Blaulicht schwellen zu lassen, gradet man den Endkader blauer als den
   Startkader — das Modell muss dann zwischen zwei Lichtstimmungen überblenden.
   Es funktioniert, aber es **verstärkt**:

   | Gradierung | Ergebnis |
   |---|---|
   | +40 % Blaukanal | Szene ersäuft ab Sekunde 2,5, Kanten türkis. Unbrauchbar. |
   | +20 % | brauchbar, im Clip auf +29 % angewachsen |

   Bei ohnehin blaustichigem Ausgangsmaterial addiert es sich auf. Ein
   *periodisches* Blinken geht mit zwei Standbildern grundsätzlich nicht — nur
   eine Welle. Und: Wo stark umbeleuchtet wird, malt das Modell Oberflächen neu.

## 6. Grenzen des Verfahrens

- **Streugut freistellen braucht Farbkontrast zum Boden.** Metall auf Asphalt und
  Gras geht; grau auf grauem Pflaster nicht (574 bzw. 446 px Ausbeute). Keine
  Einstellungssache, sondern eine Bedingung.
- **Lichtrichtung lässt sich nicht rechnen.** `komposit.py` gleicht Farbe und
  Pegel an, die Richtung bleibt aus dem Quellfoto eingebacken. Beim Umfärb-Weg
  entfällt das Problem.
- **Auflösung.** Komposit-Weg: die Platte begrenzt mit 1152 px. Umfärb-Weg:
  `gpt_image_2` liefert 1744×2336, nach 9:16-Beschnitt 1314×2336 — für
  1080×1920 ausreichend, aber ohne Puffer.
- **`komposit.py` hatte eine stille Fehlerquelle:** Platte mit schwarzem Boden
  (Vordergrund 0,002) → Objekt auf 0,004 heruntergerechnet, kommentarlos eine
  schwarze Silhouette. Behoben mit `VORDERGRUND_MIN` samt Warnung.

## 7. Was entstanden ist

**Neun sendefähige Clips** aus **vier Tatorten**, alle 1080×1920, 24 fps,
5,04 s, stumm. Im Bucket `broll` als `broll_effekt_02` … `_10`:

| Bucket | lokal | Motiv | Weg |
|---|---|---|---|
| `_02` | `effekt_01_pushin` | Wrack 1, Push-in | komposit |
| `_03` | `effekt_03_seitwaerts` | Wrack 1, Seitwärts | komposit |
| `_04` | `visa_01_automat` | VISA-Automat, über den Automaten | umfärben |
| `_05` | `visa_02_streugut` | VISA-Automat, über das Streugut | umfärben |
| `_06` | `wand_01_automat` | Wandautomat mit Absperrband | umfärben |
| `_07` | `effekt_02b_endbild` | Wrack 1, Push-in mit Endkader | komposit |
| `_08` | `wand_02_boden` | Wandautomat, tiefer | umfärben |
| `_09` | `bank_02_band` | Tobaccoland am Zaun, Band flattert | umfärben |
| `_10` | `bank_01_zaun_v2` | Tobaccoland weiter, Blaulicht-Welle | umfärben |

`broll_effekt_01.mp4` ist der **generierte** Clip vom 26.07. mit einem fremden
Automaten und bleibt bewusst aus dem Pool — deshalb `range(2, 11)` in
`core/script.py`.

**Verworfen:** `effekt_02_tracking.mp4` (Kamera lief aus dem Bild),
`bank_01_zaun.mp4` (Blaulicht überzogen, ersetzt durch `_v2`), dazu die
Bild-Zwischenstände aus dem gescheiterten Komposit-Versuch.

## 8. Kosten

| Posten | Credits |
|---|---|
| Platten (`soul_location`, 6 Stück) | 0,36 |
| Bildbearbeitungen (`gpt_image_2`, 16 Stück) | 48 |
| Videoclips (`seedance_2_0`, 13 erzeugt, 1 erstattet) | 540 |
| **gesamt** | **~532** |

Stand: 1358 → **826,28**.

**Das Verhältnis ist die eigentliche Lehre:** Ein Videoclip kostet 45, eine
Bildbearbeitung 3, eine Platte 0,06. Der komplette Bildteil eines Motivs liegt
bei ~12 Credits — ein Viertel *eines* Clips. Jeder verworfene Clip kostet so viel
wie fünfzehn Bildversuche. **Bei Bildern großzügig probieren, bei Videos nicht.**

**Das Verhältnis bestimmt die Arbeitsweise:** Ein Videoclip kostet 45, ein
Bildversuch 3, eine Platte 0,06. Der komplette Bildteil eines Motivs liegt bei
~12 Credits — ein Viertel *eines* Clips. **Bei Bildern großzügig probieren, bei
Videos nicht.**

## 9. Offen

- [x] Clips in den Bucket geladen (9 Stück, `broll_effekt_02`…`_10`), Pool in
      `core/script.py` auf `range(2, 11)`, Verteilung über 90 simulierte Fälle
      geprüft — alle neun kommen dran
- [ ] Kategorie `kulisse` — **der einzige verbliebene Blocker.** Braucht Fotos
      eines *unbeschädigten* Automaten. Vier Fotos liegen vor, alle zeigen
      Wracks. Drei Wege stehen zur Wahl: selbst fotografieren (sauber, kostenlos),
      ein Wrack per Bild-Edit „reparieren" (3 Credits, Front wäre erfunden), oder
      rein generieren
- [ ] `wetter` aus `core/contracts.py` streichen (BROLL_PLAN Beschluss 1). Der
      Pool zeigt auf `broll_wetter_01.mp4`, **die Datei liegt nicht im Bucket**
- [ ] `AUTOMAT_FIX` prüfen: beschreibt einen *wandmontierten* Automaten. Von vier
      Fotos passt nur eines dazu, die anderen sind bodenstehend
- [ ] Marken bleiben lesbar (VISA, Tobaccoland) — bewusst so entschieden, nicht
      übersehen
- [ ] Automatische Tests gibt es weiterhin keine. Das ist der schwächste Punkt
      der ganzen Kette

## 10. Die Lehre, die über B-Roll hinausgeht

Zweimal an diesem Tag hat eine **Regel, die in ihrem ursprünglichen Kontext
richtig war**, in einem neuen Kontext Schaden angerichtet: der feste Blickwinkel
und die Textregel. Beide waren aus einem einzelnen Fall verallgemeinert worden.

Und zweimal wurde ein Fehler **zu spät angesprochen** — die Perspektive war nach
dem ersten Zwischenergebnis sichtbar, wurde aber als Randnotiz erwähnt statt als
Stopp. Deshalb steht jetzt am Ende von `/broll`:

> Wenn beim Zwischenergebnis etwas grundsätzlich nicht stimmt — Perspektive,
> Bodenebene, Lichtrichtung —, sag es und halte an, statt es als Randnotiz zu
> erwähnen und weiterzulaufen.
