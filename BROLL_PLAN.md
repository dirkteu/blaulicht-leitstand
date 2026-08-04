# B-Roll — geltende Beschlüsse

Beschlossen am 26.07.2026 (/grill-me), fortgeschrieben 31.07. und 01.08.,
eingedampft am 03.08.2026 auf das, was **heute gilt**.

**Diese Datei ist der Beschluss-Stand, nicht die Geschichte.** Die
Beschluss-Nummern sind Anker: `core/script.py` und `core/broll_prompts.py`
verweisen im Klartext auf sie, deshalb bleiben Nummerierung und Dateiname stabil.

| Wo steht was |  |
|---|---|
| **Wortlaute aller Prompts** | `core/broll_prompts.py` (Single Source of Truth) |
| **Lehren, was schiefging und warum** | [`PROJEKTBUCH_BROLL.md`](PROJEKTBUCH_BROLL.md) |
| **Änderungshistorie mit Datum** | [`BETRIEB.md`](BETRIEB.md) |
| **Harte Regeln** | [`CLAUDE.md`](CLAUDE.md) |

---

## Der Leitsatz

> **Konsistenz kommt aus Pixeln, nicht aus Prompts.**

Zwei Higgsfield-Läufe mit wörtlich identischem `[Automat]`-Block lieferten zwei
verschiedene Automaten (`hf_20260726_195621…` = kompakter Pfosten-Automat ✅,
`hf_20260726_194251…` = bodenstehender Innenraum-Automat ❌). Text allein
erzwingt keine Objektkonstanz. Alles, was gleich bleiben muss, wird als echtes
Bildmaterial durchgereicht; das Modell darf ausschließlich die Bewegung erfinden.

## Die zwei Betriebsarten

```
STANDARD — umfärben:
echtes Foto → gpt_image_2 (Nacht + Hintergrund ersetzt) → 9:16 beschneiden
            → tools/kader.py → seedance_2_0 i2v → Clip

NUR wenn das Objekt an einen ANDEREN Ort soll — komposit:
echtes Foto → tools/freistellen.py → soul_location (LEERE Platte)
            → tools/komposit.py → tools/kader.py → seedance_2_0 i2v → Clip
```

Der Umfärb-Weg ist günstiger und trifft die Perspektive zwangsläufig, weil er sie
nie verlässt. Bedient wird beides über den Slash-Command **`/broll`**.

---

## Beschlüsse

1. **Kategorien:** `blaulicht`, `kulisse`, `cctv`, `effekt`, `strasse`.
   `wetter` ist ersatzlos gestrichen — Preset, Bucket-Kategorie und Doku.
   *(umgesetzt 01.08.2026, siehe `core/contracts.py`)*

2. **Nur `kulisse` (Automat intakt) und `effekt` (Automat gesprengt) zeigen den
   Automaten.** Sonst niemand.

3. **Block c3 = die Täter:** Silhouetten im Überwachungs-Look — **ohne Automat**,
   **nie Gesichter**, und **nie die Tat selbst**: nur Ankunft, Bewegung, Flucht.
   Die Guardrail „Kategorie ja, Rezept nein" gilt auch für Bilder.

   **Verschärft am 04.08.2026: keine Fahrzeuge.** Sobald ein Motiv ein
   Fluchtmittel zeigt, behauptet das Bild etwas, das die Meldung oft anders
   nennt — in Glinde flüchten die Täter „auf Fahrrädern", angeboten wurden ein
   Auto und ein Roller. Übrig bleiben Motive mit Menschen zu Fuß.
   *(Pool in `script.TAETER_MOTIVE`)*

4. **Der Master kommt aus einem echten Foto.** Der ursprünglich beschlossene Weg
   (Master generieren, „ACHTUNT"→„ACHTUNG" per Bild-Edit korrigieren,
   gesprengt-Master daraus ableiten) ist seit 31.07.2026 **überholt** — der
   *Mechanismus* „Konsistenz über ein Masterbild" hat sich dagegen bestätigt.
   Ein echtes Foto hat keine Halluzinations-Schrift, der Edit entfällt.

5. **Vielfalt nur über komplette Sätze, nie über Einzelclip-Würfeln.**
   Innerhalb eines Videos darf nur EIN Tatort vorkommen — zwei verschiedene
   Automaten in einem Clip zerstören genau die Konsistenz, für die der ganze
   Aufwand betrieben wird. *(umgesetzt als `script.EFFEKT_SAETZE`)*
   **Aufgehoben am 31.07.2026:** das Einfrieren von Ort und Beleuchtung. Das war
   nötig, solange Textprompts den Automaten nicht stillhalten konnten. Er kommt
   jetzt als Foto ins Bild und *kann* nicht mehr variieren — Ort und Beleuchtung
   dürfen deshalb wieder frei wechseln.

6. **Prompt-Typen** (alle in `core/broll_prompts.py`):

   | Typ | Wann | Eingabe → Ausgabe | Funktion |
   |---|---|---|---|
   | Szenen-Prompt | pro Clip | Text → Video | `build_prompt()` · `build_kategorie_prompt()` |
   | Umfärb-Prompt | je Master | Foto + Text → Bild | `build_umfaerben_prompt()` |
   | Platten-Prompt | je Master (Komposit) | Text → Bild | `build_platte_prompt()` |
   | Anim-Prompt | pro Clip | Bild + Text → Video | `build_anim_prompt()` |

   **Eiserne Regel Anim-Prompt:** Er beschreibt den Automaten mit keinem Wort —
   der steht ja im Startbild. Nur Kamerabewegung, optional Atmosphäre, plus die
   Schutzformel. `build_anim_prompt()` hängt sie an und prüft gegen
   `ANIM_VERBOTEN` (die Filter-Wörter greifen **auch verneint**).

7. **Generierung läuft über den Higgsfield-MCP**, Modell **Seedance 2.0** (i2v).
   Connector ist autorisiert.

8. **Runden bleiben klein, danach Stopp und Review.** Nichts wird automatisch
   veröffentlicht; die Publish-Guardrails sind davon unberührt.
   **Seit 01.08.2026 zusätzlich das Ship-Gate (CLAUDE.md §7):** keine neue
   Generierungsrunde, solange die laufende Woche ihre 3 Veröffentlichungen
   nicht hat.

---

## Sichtung der sechs `cctv`-Clips — erledigt 04.08.2026

Die Runde vom 01.08. lief noch mit der alten Whitelist-Textregel; alle sechs
zeigen Kauderwelsch-Schilder („ACHEUT ab 18", „POLIZAI") und unsinnige
Zeitstempel — einer läuft rückwärts, einer steht still. Der Pool wurde nach dem
Befund nie zurückgerollt (git: `bb9dfbf`, dann `8902d96`).

**Im Topf bleiben zwei**, und zwar aus einem zweiten Grund — sie zeigen kein
Fahrzeug und können deshalb keiner Meldung widersprechen:

| Clip | Motiv | Stand |
|---|---|---|
| `_03` | einzelne Gestalt rennt | **im Topf** |
| `_04` | zwei Gestalten mit Beutetasche | **im Topf** |
| `_02` | Täter-Vorfahrt | raus — ankommendes Auto |
| `_05` | Flucht-Roller | raus — behauptet einen Roller |
| `_06` | Fluchtwagen | raus — behauptet ein Auto |
| `_07` | leere Straße | raus — weder Täter noch Flucht, dazu Schnee |

Alle bleiben im Bucket, nur in keinem Topf.

## Offen

- **c3 hat nur noch zwei Motive.** Bis der Topf wächst, sehen alle Videos an
  dieser Stelle sehr ähnlich aus. Neue Motive müssen ohne Fahrzeug auskommen
  und die fünf Austauschbarkeits-Bedingungen erfüllen (Dokument im Drive).
- **c4 ist gestalterisch offen** — die Bilanz steht aktuell 12 Sekunden als
  fast leere dunkle Fläche.
