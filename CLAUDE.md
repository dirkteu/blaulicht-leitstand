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
Sachlich-dokumentarisch, nie reißerisch. Nicht nur juristisch — YouTube geht
gegen „massenproduzierte, repetitive" KI-Inhalte vor. Der Disclaimer in
`script.DISCLAIMER` läuft automatisch an jede Caption.

---

## Prinzip bei allen Guardrails

**Prompt-Regel + harte Prüfung + Warnung im Review.** Prompt-Regeln allein
haben in diesem Projekt mehrfach versagt (Claude ist nicht deterministisch).
Garantiert ist nur, was in Code geprüft wird. Warnungen landen im Feld
`cases.warnung` und erscheinen als ⚠ in der Fall-Tabelle.

Automatisch **korrigiert** wird nur, was sicher korrigierbar ist. Grammatik
umbauen gehört nicht dazu — dort nur warnen und den Menschen entscheiden lassen.

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

⚠️ **Gemini-TTS: 100 Anfragen/Tag** trotz aktivem Billing (≈ 20 Vertonungen,
1 Anfrage je Szene). Beim Iterieren am Skripttext schnell erschöpft — dann
`TTS_BACKEND=edge`. Zeigt sich als `429 RESOURCE_EXHAUSTED`.

⚠️ Stürzt Docker Desktop mit einem Fehlerdialog ab: **nicht** auf „Reset to
factory defaults" klicken — das löscht alle lokalen Images und Container.

---

## Wo du weiterliest

- [`BETRIEB.md`](BETRIEB.md) — Änderungshistorie mit Begründungen, Diagnose-Schnipsel
- [`BROLL_PLAN.md`](BROLL_PLAN.md) — beschlossene B-Roll-Master-Kette (noch unumgesetzt)
- [`UMSETZUNG.md`](UMSETZUNG.md) · [`README.md`](README.md) — Aufbau und Struktur
