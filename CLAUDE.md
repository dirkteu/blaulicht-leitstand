# Blaulicht-Leitstand — Arbeitsregeln

Automatisierte True-Crime-Clip-Produktion aus Polizei-Pressemeldungen, mit
menschlicher Freigabe an jeder Schaltstelle. Containerisierte Microservices,
Zustand ausschließlich in Supabase (Schema `blaulicht`).

**Diese Datei enthält die Regeln, die nicht verhandelbar sind.** Was WANN und
WARUM geändert wurde, steht in [`BETRIEB.md`](BETRIEB.md) — dort nachlesen,
bevor du etwas umbaust, das bereits einmal durchdacht wurde.

---

## Nicht verhandelbar

### 1. Datenschutz
Ort **nur auf Stadt-/Gemeindeebene**. Nie Namen (auch keine Initialen), nie
Straße, Hausnummer, PLZ, Koordinaten. Durchgesetzt an zwei Stellen:
`core.contracts.Facts.VERBOTEN` und `core.extract.sanitize()` — letztere
arbeitet bewusst **unabhängig vom Prompt**, weil Modellverhalten keine Garantie ist.

> **`case.title` ist ungefiltert.** Der Rohtitel der Pressemeldung läuft nie
> durch `sanitize()` — dort stehen Namen, Straßen und Quellenkürzel. Alles, was
> aus ihm gebaut wird (`tat` fällt notfalls darauf zurück), muss durch dieselbe
> Schranke. Er landet sonst in Bauchbinde und Schlagzeile, also im am besten
> **lesbaren** Text des Clips. Gefunden am 04.08.2026.

### 2. Keine Nachahmungs-Anleitung
Die **Tat darf benannt** werden („gesprengt", „Sprengung", „Explosion",
„Winkelschleifer"). Das **WIE niemals**: keine Stoffarten, Mengen, Zuführung,
Zündmechanismen, Schrittfolgen. Durchgesetzt über `core.parse.hat_methode()` /
`entschaerfe_methode()` und `core.extract.pruefe_text()`.

> Kursierende „TikTok-Shadowban-Wortlisten" fordern, „Sprengstoff" durch
> „Gasgemisch" zu ersetzen. **Das ist geprüft und verworfen** — es benennt die
> Methode präziser und erhöht damit genau das Risiko, das es senken soll.
> Begründung samt Belegen in BETRIEB.md. Nicht neu aufrollen.

### 3. Unschuldsvermutung — sie schützt PERSONEN, nicht EREIGNISSE
Der häufigste Denkfehler. Die Unterscheidung:

| Situation | Richtig |
|---|---|
| **Die Tat** (dass gesprengt wurde) | **Indikativ.** Das ist Tatsache. |
| **Täter unbekannt/flüchtig** (`facts.ungeloest = true`) | **Indikativ.** Es gibt keine Person, die vorverurteilt werden könnte — Polizei und Presse schreiben selbst so. |
| **Jemand identifiziert/festgenommen/benannt** | **Distanz Pflicht** („soll … haben", „mutmaßlich"). |
| **Hergang unsicher** (nur Zeugenangaben) | Distanz — wegen der Quelle, nicht wegen der Schuld. |

Gesteuert über `facts.ungeloest`. Beim Distanzieren **Mittel abwechseln**
(Konjunktiv I, Quellenzuschreibung, „mutmaßlich", agentloses Passiv) — nicht
dreimal „sollen" hintereinander. Prüfungen: `parse.distanz_fehlt()`,
`parse.konjunktiv_bruch()`, Fallback in `script.build_spec()`.

### 4. Freigaben
Produktion und Veröffentlichung **nur nach Klick**, nie automatisch. Die drei
Gates: *Freigabe Analyse* → *Freigabe Clip* → *Freigabe Veröffentlichung*.
Zusätzlich Alters-Gate `MIN_PUBLISH_AGE_HOURS` (Default 48 h) in
`workers/publish.py`.

### 5. Datensicherheit
B-Roll-Master liegen **nur** im Storage-Bucket `broll`. `render` liest Kopien
und schreibt dort **nie** hinein. (2026-07-25 wurden so schon einmal 12 echte
Higgsfield-Clips vernichtet.)

### 6. Ton
Sachlich-dokumentarisch, nie reißerisch. Der Disclaimer in `script.DISCLAIMER`
läuft automatisch an jede Caption.

### 6a. Authentizität — die Plattformregel, die dieses Projekt am härtesten trifft
YouTube hat die alte „repetitious content"-Regel am **15.07.2025** in
**„inauthentic content"** umbenannt und am **16.07.2026** präzisiert. Drei
Kategorien: generisch-repetitive Inhalte mit minimalem kreativem Aufwand (KI,
CGI **oder Vorlagen**), verstörend-manipulative Inhalte, und KI-Personas zu
Gesundheit, Finanzen und Recht. Folge ist der YPP-Ausschluss, gestaffelt
Verwarnung → 90 Tage → dauerhaft.

**KI ist nicht verboten.** Der Regeltext nennt ausdrücklich als Rettung:
„Originalinhalte, authentische Erkenntnisse oder Perspektiven der Creatorin
oder des Creators". Das Kriterium ist Mehrwert, nicht Werkzeug.

**Warum uns das besonders trifft:** Vier fester Blöcke, ein gemeinsamer
B-Roll-Topf, eine Stimme, ein automatischer Disclaimer — „made with a template
with little to no variation across videos" beschreibt exakt unseren Aufbau.
Ein Format zu haben ist erlaubt (Nachrichtenformate sind auch Vorlagen).
Ausgeschlossen wird die **Kombination** aus Vorlage, fehlendem eigenem Beitrag
und Menge. An der Vorlage hängt unsere Wiedererkennung — also müssen die beiden
anderen Hebel gezogen werden.

Fünf harte Punkte:

1. **Jedes Video braucht mindestens einen Satz, der nicht in der Meldung
   steht.** Einordnung, Vergleichszahl, Fahndungsstand im Kontext — mit
   genannter Quelle. Das ist wörtlich das Kriterium, an dem die Regel die
   Grenze zieht. Platz ist da: c4 steht aktuell als fast leere Fläche.
2. **Oberfläche variieren, Struktur behalten.** Einstiegssatz, Länge, Stimme
   und Bildquelle dürfen wechseln. Die Blockfolge bleibt.
3. **Echtes Bildmaterial hat Vorrang vor generiertem.** Der Umfärb-Weg startet
   aus echten Fotos und ist damit unser stärkstes Unterscheidungsmerkmal
   gegenüber reinen Prompt-Kanälen (BROLL_PLAN, Betriebsart „Standard").
4. **Synthetische Szenen werden beim Upload offengelegt.** Fotorealistisch
   generierte Bilder zu einem realen Ereignis sind der ausdrückliche Auslöser
   („eine realistische Szene, die nie stattgefunden hat"). Das Häkchen in
   YouTube Studio bzw. der AIGC-Schalter bei TikTok ist **Pflicht** und wird
   durch `script.DISCLAIMER` in der Caption **nicht** ersetzt. Die Offenlegung
   allein kostet weder Reichweite noch Monetarisierung.
5. **Umsortiertes Material ist kein neues Video.** Gewürfelte Varianten aus
   einem Lauf (`tools/wuerfeln.py`) sind Vorrat für den Topf, aus dem pro Video
   *eine* Einstellung gezogen wird — nie mehrere Uploads aus demselben Lauf.

> **Offen:** Kategorie 3 nennt Gesundheit, Finanzen und Recht.
> Kriminalitätsberichterstattung steht nicht auf der Liste, liegt aber in der
> Nachbarschaft. Eine synthetische Stimme, die Polizeimeldungen vorträgt, ist
> im Blick zu behalten.

Belege: [YouTube-Hilfe, Monetarisierungsrichtlinien](https://support.google.com/youtube/answer/1311392?hl=de) ·
[TechCrunch, 20.07.2026](https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/)

### 7. Ship-Gate (Kurskorrektur 01.08.2026)
**Keine neue Produktionsqualitäts-Baustelle, solange die laufende Woche ihre
3 Veröffentlichungen nicht hat.** Das Ziel ist ein Kanal, keine Fabrik: Vom
25.07. bis 01.08. wurde ausschließlich Qualität gebaut und kein einziger Clip
veröffentlicht (Befund in BETRIEB.md, Kurskorrektur-Eintrag). Erst nach dem
Phase-1-Meilenstein (10 Shorts): Langform, Overlay-Feinschliff, B-Roll-Runden
über das Nötige hinaus. Woche 1 läuft nur auf TikTok, ab Woche 2 gleichrangig
TikTok + YouTube Shorts + Reels.

---

## Prinzip bei allen Guardrails

**Prompt-Regel + harte Prüfung + Warnung im Review.** Prompt-Regeln allein
haben in diesem Projekt mehrfach versagt (Claude ist nicht deterministisch).
Garantiert ist nur, was in Code geprüft wird. Warnungen landen im Feld
`cases.warnung` und erscheinen als ⚠ in der Fall-Tabelle.

Automatisch **korrigiert** wird nur, was sicher korrigierbar ist. Grammatik
umbauen gehört nicht dazu — dort nur warnen und den Menschen entscheiden lassen.

**Geprüft wird JEDE erzeugte Zeile, nie eine Auswahl.** Die
Unschuldsvermutungs-Prüfung lief bis 04.08.2026 nur über zwei von fünf
Abschnitten. Das ging gut, solange die Sätze immer an derselben Stelle standen —
und wurde in dem Moment gefährlich, in dem sie zwischen den Blöcken zu wandern
begannen. Wer die Verteilung ändert, muss die Prüfung mitziehen.

---

## Architektur

`core/contracts.py` ist der Vertrag für alle Services (State, Queue, Facts,
Case, Bucket, DB_SCHEMA). Ändert sich dort etwas, betrifft es alle — bewusst
und abgestimmt ändern.

```
core/      gemeinsame Logik: parse (reine Regex, kein I/O) · extract (Claude)
           script (Spec-Bau) · tts · render · lektor · broll_prompts · supa
api/       FastAPI + HTMX (Leitstand-UI)
workers/   ingest · extract · script · tts · render · publish   (RQ auf Redis)
scheduler/ 2×/Tag Auto-Ingest
```

Zustandsmaschine: `neu → in_analyse → review → in_produktion → fertig →
veroeffentlicht` (plus `verworfen`).

### Der Grundaufbau: vier Blöcke

Ein Clip besteht aus vier Blöcken. **Ein Block = ein Gedanke = eine Bildsorte.**
Definiert in `script.BLOECKE` — eine Tabelle, nicht verstreute Wörterbücher.

| Block | erzählt | Bild |
|---|---|---|
| **c1** | Einstieg: stärkster Fakt, dann Ort und Zeit | Polizei · trägt die Schlagzeile |
| **c2** | Die Tat | Tatobjekt |
| **c3** | Die Täter: Ankunft, Bewegung, Flucht | Täter — **nie ein Fahrzeug** |
| **c4** | Bilanz: Zahlen, Fahndungsstand, Spur | **keins** |

Vier Regeln, die zusammengehören:

1. **Die Reihenfolge steht fest, der Text wird auf die Blöcke verteilt** — nicht
   umgekehrt. Das macht einen Grundaufbau aus: Der Zuschauer erkennt die Form
   wieder.
2. **Die Länge ergibt sich aus dem gesprochenen Text.** `tts.synth()` misst und
   schreibt `t_start`/`t_end`/`duration` zurück. Es gibt keine Soll-Dauern mehr —
   kürzer wird ein Block nur, indem er weniger zu sagen bekommt. Gedeckelt wird
   in **Zeichen**, nicht in Sätzen (deutsche Polizeisätze reichen von 40 bis 200).
3. **Ein Block ohne Inhalt fällt weg.** Sagt eine Meldung nichts über die Täter,
   gibt es kein c3. Es wird kein Text erfunden, um eine Form zu füllen.
4. **Das Bild darf nie mehr behaupten als die Meldung.** Deshalb zeigt c3 kein
   Fluchtfahrzeug (die Meldung nennt oft ein anderes), und c4 gar kein Bild.

> **Der Clip beginnt am Ende der Geschichte.** Die Polizei kommt zuletzt, c2
> springt zurück zur Tat. Das ist der übliche True-Crime-Einstieg, muss aber
> sprachlich getragen werden — sonst wirkt der Sprung wie ein Fehler.

**HTMX-Fallstrick:** Liefert ein Partial seinen eigenen Container mit, muss
`hx-target="this"` + `hx-swap="outerHTML"` gesetzt sein. Mit `innerHTML`
verschachtelt sich der Container bei jedem Poll in sich selbst und die Poller
vervielfachen sich. Ist einmal passiert.

---

## Betrieb

```bash
powershell -ExecutionPolicy Bypass -File start_leitstand.ps1
```
Räumt verwaiste AF_UNIX-Sockets per WSL weg (**Windows kann sie nicht löschen,
sie blockieren sonst den Docker-Start**), startet Docker Desktop, wartet auf die
Engine, fährt den Stack hoch. Leitstand: http://localhost:8000, Passwort in `.env`.

**Das Skript baut das Image immer neu (`--build`).** Der Code hängt nicht als
Volume im Container — das Dockerfile backt ihn mit `COPY . .` ins Image. Ohne
Neubau läuft der Stand des letzten Builds weiter, und das merkt man erst, wenn
ein Fix scheinbar nicht wirkt. Der Neubau kostet kaum Zeit: `apt-get` und `pip`
hängen an früheren Schichten und bleiben im Cache, solange `requirements.txt`
unverändert ist.

⚠️ **Gemini-TTS: 100 Anfragen/Tag** trotz aktivem Billing (≈ 20 Vertonungen,
1 Anfrage je Szene). Beim Iterieren am Skripttext schnell erschöpft — dann
`TTS_BACKEND=edge`. Zeigt sich als `429 RESOURCE_EXHAUSTED`.

⚠️ Stürzt Docker Desktop mit einem Fehlerdialog ab: **nicht** auf „Reset to
factory defaults" klicken — das löscht alle lokalen Images und Container.

---

## Wo du weiterliest

- [`BETRIEB.md`](BETRIEB.md) — Änderungshistorie mit Begründungen, Diagnose-Schnipsel
- [`BROLL_PLAN.md`](BROLL_PLAN.md) — geltende B-Roll-Beschlüsse (Nummern sind Anker im Code)
- [`STORYBOARD_LEITFADEN.md`](STORYBOARD_LEITFADEN.md) — Storyboard-Blätter mit gpt_image_2: Basis-Look, Beschriftung, Verbote, Abnahme
- [`PROJEKTBUCH_BROLL.md`](PROJEKTBUCH_BROLL.md) — B-Roll-Lehren: was schiefging und warum
- [`UMSETZUNG.md`](UMSETZUNG.md) · [`README.md`](README.md) — Aufbau und Struktur
