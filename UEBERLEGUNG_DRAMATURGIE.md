# Überlegung: Vier Teile statt fünf — und der Loop darunter

**Status: ENTSCHIEDEN UND UMGESETZT (01.08.2026).** Alle drei Schritte sind in
`core/script.py` / `core/render.py` implementiert und an zwei Testrenderings
mit echten Bucket-Clips verifiziert — Details und Begründungen in
[`BETRIEB.md`](BETRIEB.md), Update 2026-08-01. Drei Abweichungen vom Papier:

1. **Story bekommt 4 Clips statt 3** — so loopt bei vollem Pool gar nichts
   mehr (4 × ~5 s ≥ 18 s).
2. **`zahlen` liegt auf `cctv`, nicht auf einer Fluchtwagen-Kategorie** — die
   existiert nicht; Fluchtfahrzeug/Roller sind Teil der cctv-Neudefinition
   aus BROLL_PLAN Beschluss 3.
3. **Tatort-Sätze kamen dazu** (`EFFEKT_SAETZE`): Die 9 effekt-Clips stammen
   aus 4 Tatorten; je Video wird EIN Satz gewählt, sonst zeigt ein Video zwei
   verschiedene Automaten. Das Papier hatte diesen Punkt übersehen — im
   ersten Testrendering war der Fehler sofort sichtbar.

Der Rest des Dokuments bleibt als Denkstand unverändert stehen.

---

## Der Ausgangsvorschlag (vom Nutzer)

Ein Clip in **vier** Teilen statt fünf:

1. **Polizei** — Blaulicht, Autos
2. **Die Tat** — der Automat
3. **Täter-Abgang** — schnelles Auto, Roller
4. **Nochmal der Automat**, so wie wir ihn jetzt gebaut haben

Der vierte Teil ist keine Wiederholung, sondern eine **Klammer**: Der Clip endet
dort, wo er hingehört — beim zerstörten Automaten.

## Der eigentliche Fund: eine Szene = ein Clip, geloopt

`core/render.py`, `_build_background()`:

```python
_run(["ffmpeg", "-stream_loop", "-1", "-i", broll_path, "-t", f"{d:.3f}", ...])
```

Jede Szene bekommt **genau einen** Clip, der über die Szenendauer **geloopt**
wird. Unsere Clips sind 5,04 s lang:

| Szene | Dauer | Loops desselben Clips |
|---|---|---|
| `story` | 18 s | **3,6 ×** |
| `zahlen` | 8 s | 1,6 × |
| `eskalation` | 7 s | 1,4 × |
| `cliffhanger` | 6 s | 1,2 × |
| `hook` | 3 s | — |

In der längsten Szene sieht der Zuschauer **dieselben fünf Sekunden dreieinhalb
Mal hintereinander**.

**Das ist die Wurzel, nicht die Kategorienzuordnung.** Selbst mit zwanzig
`cctv`-Clips liefe in jedem einzelnen Video einer davon 3,6 mal im Kreis. Mehr
Clips je Kategorie verringern die Wiederholung *zwischen* Videos, die
Wiederholung *innerhalb* eines Videos bleibt unberührt.

## Zwei Fehler in der ersten Überlegungsrunde

**1 · Die Klammer zerbrochen.** Ich hatte Teil 4 (Automat) auf den `zahlen`-Slot
gelegt und `cliffhanger` beim Fluchtwagen belassen. Der Clip hätte damit auf
einem wegfahrenden Auto geendet — genau das, was der Vorschlag vermeiden will.

**2 · Auf der falschen Ebene gearbeitet.** Ich habe an den Kategorien geschraubt,
obwohl das Problem eine Ebene tiefer liegt. Das wäre Symptombehandlung gewesen.

## Warum der Vorschlag trotzdem trägt

Er verteilt die Erzählung auf **vier Bilder statt fünf** und kehrt am Ende zum
Anfangsmotiv zurück. Das ist eine Klammer, keine Aufzählung — und es trägt über
42 Sekunden besser.

Nebeneffekt, der zwei offene Blocker erledigt:

- **`kulisse` fällt aus der Verwendung** → das fehlende Foto eines *intakten*
  Automaten blockiert nichts mehr.
- **`cctv` würde auf BROLL_PLAN Beschluss 3 umgestellt** (Täter-Silhouetten
  *ohne* Automat — beschlossen am 26.07., nie umgesetzt) → damit ebenfalls nicht
  mehr am intakten Automaten hängend und frei generierbar.

## Was zu tun wäre, in dieser Reihenfolge

**1 · Eine Szene muss mehrere Clips halten können.**
Statt `broll: "broll_effekt_04.mp4"` eine Liste, die `_build_background()`
aneinanderhängt statt zu loopen. Die 18-Sekunden-Szene zeigt dann drei
verschiedene Clips. Berührt **nicht** Text, Timing oder Guardrails — nur den
Hintergrundbau.
→ *Eingriff in `render.py`, die bisher am wenigsten angefasste Stelle.*

**2 · Der Picker muss die Rolle kennen.**
`pick_broll(role, seed)` bildet den Index allein aus dem Seed:
```python
return pool[seed % len(pool)]
```
Zwei Rollen mit derselben Kategorie bekommen deshalb **denselben Clip** —
vorgeführt: drei Slots auf `effect` lieferten dreimal `broll_effekt_08.mp4`.
Einzeiler, muss aber vor Schritt 3 passieren.

**3 · Erst dann die Zuordnung.**

| Slot | Dauer | Text sagt | Bild | Teil |
|---|---|---|---|---|
| `hook` | 3 s | Ort, Zeit, Tat | Polizei, Blaulicht | **1** |
| `eskalation` | 7 s | die Tat | der Automat | **2** |
| `story` | 18 s | Werkzeug, Details, Täter | Täter — 3 verschiedene Clips | **3** |
| `zahlen` | 8 s | Beute, Schaden | Fluchtwagen, Roller | **3** |
| `cliffhanger` | 6 s | ungelöst, Fahndung | **der Automat, letztes Bild** | **4** |

Der Text stützt die Klammer: „ungelöst, die Täter sind flüchtig" über dem
zerstörten Automaten ist ein stärkerer Schluss als ein wegfahrendes Auto.

**Wichtig:** Die fünf **Text**-Rollen bleiben unangetastet. Sie tragen die Fakten
und an zweien hängen die Guardrails (Unschuldsvermutung und Methoden-Sperre
werden für `eskalation` und `story` geprüft). Geändert wird nur, was man
**sieht** — der Vorschlag beschreibt Bilder, nicht Texte.

## Die offene Frage

Schritt 1 ist ein Eingriff in den Render — die Stelle, an der bisher nie etwas
kaputtgegangen ist, und die jeden künftigen Clip betrifft.

**Entweder** gleich richtig: Mehrfach-Clips je Szene, dann Picker, dann
Zuordnung.

**Oder** erst billig: nur Zuordnung und Picker ändern, den Loop vorerst
hinnehmen, und an einem echten Rendering sehen, ob die Wiederholung überhaupt
stört.

---

## Anhang: Bestand zum Zeitpunkt dieser Überlegung

| Kategorie | Automat im Bild? | Clips im Bucket | Anteil Laufzeit |
|---|---|---|---|
| `effekt` | ja, gesprengt | **10** (9 im Pool) | 7 s · 17 % |
| `cctv` | ja, **intakt** | 1 (vom 26.07.) | 18 s · 43 % |
| `kulisse` | ja, **intakt** | 1 (vom 26.07.) | 8 s · 19 % |
| `blaulicht` | nein | 1 (vom 26.07.) | 3 s · 7 % |
| `strasse` | nein | 1 (vom 26.07.) | 6 s · 14 % |
| `wetter` | nein | **0** | keiner Rolle zugewiesen |

In **80 % der Laufzeit** jedes Videos laufen dieselben vier Clips vom 26. Juli.
Nur die sieben Sekunden Eskalation variieren.

**Zwei BROLL_PLAN-Beschlüsse stehen auf dem Papier, aber nicht im Code:**
Beschluss 1 (`wetter` streichen) und Beschluss 3 (`cctv` = Täter-Silhouetten
ohne Automat).

**Stolperstein:** Die Schlüssel in `script.ASSETS` sind englisch (`street`,
`weather`, `location`, `effect`), die Bucket-Präfixe deutsch (`strasse`,
`wetter`, `kulisse`, `effekt`).
