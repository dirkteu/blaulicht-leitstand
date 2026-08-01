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

**Sieben Clips**, alle 1080×1920, 24 fps, 5,04 s, stumm, in `assets/master/`:

| Datei | Motiv | Weg |
|---|---|---|
| `effekt_01_pushin.mp4` | Wrack 1, Push-in **(Empfehlung)** | komposit |
| `effekt_02b_endbild.mp4` | Wrack 1, Push-in mit Endkader | komposit |
| `effekt_03_seitwaerts.mp4` | Wrack 1, Seitwärts **(Empfehlung)** | komposit |
| `visa_01_automat.mp4` | VISA-Automat, über den Automaten | umfärben |
| `visa_02_streugut.mp4` | VISA-Automat, über das Streugut | umfärben |
| `wand_01_automat.mp4` | Wandautomat mit Absperrband | umfärben |
| `wand_02_boden.mp4` | Wandautomat, tiefer | umfärben |

Drei verschiedene Tatorte für die Kategorie `effekt` — vorher gab es einen.

**Verworfen:** `effekt_02_tracking.mp4` (Kamera lief aus dem Bild) sowie zehn
Bild-Zwischenstände aus dem gescheiterten Komposit-Versuch.

## 8. Kosten

| Posten | Credits |
|---|---|
| Platten (`soul_location`, 6 Stück) | 0,36 |
| Bildbearbeitungen (`gpt_image_2`, 8 Stück) | 24 |
| Videoclips (`seedance_2_0`, 8 erzeugt, 1 erstattet) | 360 |
| **gesamt** | **~384** |

Stand: 1358 → **973,28**.

**Das Verhältnis bestimmt die Arbeitsweise:** Ein Videoclip kostet 45, ein
Bildversuch 3, eine Platte 0,06. Der komplette Bildteil eines Motivs liegt bei
~12 Credits — ein Viertel *eines* Clips. **Bei Bildern großzügig probieren, bei
Videos nicht.**

## 9. Offen

- [ ] Freigegebene Clips über die `/broll`-Seite des Leitstands in den Bucket
      laden (Regel 5: Master gehören **nur** dorthin, nicht ins Repo)
- [ ] Kategorie `kulisse` — **blockiert**, braucht Fotos eines *unbeschädigten*
      Automaten
- [ ] `wetter` aus `core/contracts.py` streichen (BROLL_PLAN Beschluss 1)
- [ ] `AUTOMAT_FIX` prüfen: beschreibt einen *wandmontierten* Automaten. Von drei
      Fotos passt nur eines dazu, die anderen sind bodenstehend
- [ ] VISA-Beklebung auf `master_visa.png` bleibt lesbar — bewusst so
      entschieden, nicht übersehen

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
