# Betriebshandbuch — Blaulicht-Leitstand

**Status (2026-07-26): 🟢 LIVE — kompletter Clip end-to-end (Ingest → Orus-Stimme → echtes B-Roll → Render → Publish) bewiesen.**
Gebaut von 5 Agent-Teams, containerisiert, an Supabase, verarbeitet echte Polizeimeldungen.

## Zugang
- **URL:** http://localhost:8000
- **Login-Passwort:** `blaulicht` (in `.env` bei `LEITSTAND_PASSWORD`, jederzeit änderbar)

## Infrastruktur
- **Docker Desktop** (WSL2-Backend) — 9 Container: `redis`, `api`, `scheduler`, `worker-ingest/extract/script/tts/render/publish`.
- **Supabase** (managed): Projekt „ki_wn", ref `mzuyqhslpeaeoqxconzc`, URL https://mzuyqhslpeaeoqxconzc.supabase.co
  - Schema **`blaulicht`**: Tabellen `cases`, `broll`, `config`
  - Storage-Buckets: `broll` (Master, nur lesen), `voice`, `renders`, `thumbs`

## Bedienung (Docker)
> **WICHTIG:** `docker` ist auf diesem PC nicht im Windows-PATH. In PowerShell vor jedem Befehl:
> `$env:Path="C:\Program Files\Docker\Docker\resources\bin;"+$env:Path`  (oder in WSL arbeiten).

| Aktion | Befehl (im Ordner `Desktop\blaulicht`) |
|---|---|
| Starten | `docker compose up -d` |
| Status | `docker compose ps` |
| Logs | `docker compose logs <service> --tail 30` |
| Stoppen | `docker compose down` (Container weg; Daten in Supabase bleiben) |
| Nach Code-Änderung | `docker compose up -d --build` |
| Nach `.env`-Änderung | `docker compose up -d` (Container werden mit neuer env neu erstellt) |
| Ingest manuell anstoßen | Dashboard-Button „Ingest RSS" — oder Job einreihen (siehe Diagnose) |

## Workflow (Freigabe-Kette)
```
2×/Tag Auto-Ingest (07:00/19:00) → Tabelle (nur THEMA Zigaretten, Fälle ab Score-Schwelle)
  → [Freigabe Analyse] → Fakten (Claude) + Skript + Stimme → REVIEW (Text/Audio prüfen, „neu vertonen")
  → [Freigabe Clip] → Render → FERTIG (Vorschau)
  → [Freigabe Veröffentlichung] → Download/Upload
```
Nur der Ingest ist automatisch; alles Weitere hinter Freigabe-Klick.
Zwei Quellen, beide auf **Zigaretten** eingegrenzt (siehe „Themen-/Zeitfilter"):
`rss` (Presseportal-Feeds, ~270 Dienststellen) und `mail` (Google-Alert-Mails).
In der Dashboard-Tabelle zeigt die Spalte **Quelle** je Fall ein RSS- bzw. Google-Symbol.

## Themen-/Zeitfilter (nur Zigaretten, letzte 14 Tage)
Beide Quellen liefern nur Fälle zum konfigurierten Thema — gesteuert über `.env`:
- `ALERT_SUBJECT_FILTER=zigaretten` — nur Google-Alert-Mails mit diesem Wort im Betreff.
- `ALERT_TOPIC_KEYWORDS=zigaret,tabak,kippen,raucherwaren` — Treffer-Filter auf den **Titel**
  (greift für **rss UND mail**, zentral in `workers/ingest.py`); zusätzlich zählt „Automat … gesprengt".
- `ALERT_MAX_AGE_DAYS=14` — nur Alert-Mails der letzten N Tage (IMAP `SINCE`).
- Score-Bonus `🚬 Zigarettenautomat +15` (`core/scoring.py`) hebt die Automaten-Sprengungen über die Schwelle.
- Mail-Quelle verlangt **kein** „ungelesen" mehr (Nutzer liest Alerts selbst) — Idempotenz über Link-Dedup;
  Lese-Markierungen im Postfach werden nicht verändert.
Leere Filter = aus (alle Themen). Filter erweitern → Werte in `.env` ändern, `docker compose up -d` (kein Rebuild nötig, da nur env).

## Secrets (`.env`)
Gesetzt: `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_URL`, `ANTHROPIC_API_KEY`,
`LEITSTAND_PASSWORD=blaulicht`, `SESSION_SECRET`, `TZ=Europe/Berlin`,
`IMAP_APP_PW` (Google App-Passwort — **gesetzt**, Mail-Quelle live),
`ALERT_SUBJECT_FILTER`, `ALERT_TOPIC_KEYWORDS`, `ALERT_MAX_AGE_DAYS`.

## Beim ersten Lauf gefixt (alles Konfig/Konto — KEIN Logik-Bug der Teams)
1. **PostgREST-Schema-Freigabe:** `blaulicht` war für die REST-API nicht exponiert →
   `alter role authenticator set pgrst.db_schemas='public, graphql_public, blaulicht'` + Grants.
2. **Unique-Constraint:** Upsert `on_conflict(link)` brauchte einen vollen Unique-Constraint statt
   des partiellen Index → `cases_link_key unique (link)`.
3. **Anthropic 401:** API-Key war leer → gesetzt.
4. **Anthropic 400 „credit balance too low":** Konto-Guthaben → aufgeladen.

## Erster erfolgreicher Fall (Beleg)
Bremen „Raub auf Spielhalle": RSS-Ingest (7 Fälle, Score 40–50) → extract (Claude Haiku) →
Fakten **Zeit 01:10, Ort Bremen (nur Stadt!), Täter 1, ungelöst, Details** — datenschutzkonform,
keine Namen/Adresse → script → tts (`voice.mp3` in Storage) → `state=review`. Gesamt ~15 s.

## Update 2026-07-25 (Mail-Quelle live + Feinschliff)
- **Mail-Ingest live:** `core/mail.py` auf **Google-Alert-Format** umgebaut (Redirect-Links auspacken,
  je Mail mehrere Treffer). App-Passwort gesetzt, Login getestet. Quelle=`mail` landet in derselben
  `blaulicht.cases`-Tabelle wie `rss`, identische Facts über dieselbe Claude-Extraktion.
- **Nur Zigaretten** für beide Quellen (Betreff- + Titel-Filter, siehe „Themen-/Zeitfilter"). Beispiel-Lauf:
  RSS 1054 Meldungen → nur Zigaretten-Treffer; Mail 19 Treffer (14 Tage) → Automaten-Sprengungen Score 45–50.
- **TTS-„Knacken" behoben:** `core/tts.py` führt Szenen jetzt als WAV/PCM und kodiert nur einmal final nach
  MP3 (kein Encoder-Delay/Stottern mehr an Szenengrenzen).
- **Quelle-Symbol** in der Dashboard-Tabelle (RSS orange / Google-„G").

## Update 2026-07-25 (Voice-Engine: edge-tts → Gemini TTS)
- **Stimme getauscht:** `core/tts.py` vertont standardmäßig über **Google Gemini TTS**
  (SDK `google-genai`) statt edge-tts. Grund: edge klang monoton; Gemini nimmt eine
  natürlichsprachige Regie-Anweisung (`TTS_STYLE`) und trifft den düsteren True-Crime-Doku-Ton.
- **Umschaltbares Backend:** `TTS_BACKEND=gemini|edge` (Default `gemini`); edge-tts bleibt als
  Fallback. Nur die szenenweise Vertonung ist backend-abhängig — Sync/Timecodes/Concat unverändert
  (Gemini liefert PCM 24 kHz/mono/16-bit = bestehendes `AR`, slottet direkt in die Concat-Kette).
- **Neue `.env`-Variablen:** `TTS_BACKEND`, `GOOGLE_API_KEY` (Google AI Studio),
  `GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts`, `GEMINI_VOICE=Orus`, `TTS_STYLE` (Regie-Prompt).
  **Stimme wechseln = nur `GEMINI_VOICE` ändern** (z. B. `Charon`, `Iapetus`, `Algenib`), kein Code.
- **Gemini-Key-Format:** neue AI-Studio-Keys beginnen mit `AQ.Ab…` (nicht mehr `AIza…`, „Auth-Keys").
  Funktionieren am nativen Gemini-Endpunkt (den `google-genai` nutzt); alte `AIza`-Keys werden ab
  Sept. 2026 abgeschaltet.
- **Rate-Limit:** Gratis-Tier = **3 TTS-Requests/Min**. `_gemini_scene()` respektiert die vom Server
  gemeldete `retryDelay` (Backoff) → läuft durch, nur langsamer. Für Tempo Billing aktivieren.
- **Reset dieser Umstellung:** die 3 Fälle in `review` (alte edge-Stimme) auf `state=neu` gesetzt +
  `voice_url` geleert → per „Freigabe Analyse" neu mit Gemini/Orus vertonen.
- Betroffene Dateien: `core/tts.py`, `requirements.txt` (+`google-genai`), `.env.example`, `UMSETZUNG.md`.

## Update 2026-07-26 (Titel-Vorparser: Ort/Tat, Cross-Source-Dedup, Halluzinations-Check)
Neues Modul **`core/parse.py`** zieht schon beim Ingest — **ohne Claude, ohne Volltext**, reine Regex —
zwei Dinge aus der Schlagzeile, die dort fast immer stehen. Findet er nichts, bleibt das Feld leer und
der Fall läuft ganz normal weiter (kein Sonderpfad).
- **Ort + Tat vorgeparst:** `parse_ort()` (Muster `in <Stadt>`, `<Stadt>:`/`<Stadt>.`, `Polizei-News <Stadt>`,
  `POL-XX: <Stadt>`, `Kreis <X>`, sonst RSS-Region als Fallback) und `parse_tat()` (Sprengung/Raub/
  Körperverletzung/… — bewusst präziser als `scoring.classify()`). An 15 echten Fällen: Ort 15/15.
  Neue Spalten `cases.ort` + `cases.tat` (Migration `0002`), Dashboard zeigt Spalten **Ort | Tat**.
- **Cross-Source-Dedup** (`workers/ingest.py`): erkennt „gleiche Story, anderes Medium" jetzt auch
  quellen- UND laufübergreifend (Mail-Lauf sieht RSS-Fälle via `supa.recent_cases`). Zwei Stufen:
  globale Titel-Ähnlichkeit ≥ 0.72 (wie bisher) **plus** Block-Regel `(ort+tat+Kalenderwoche)` mit
  milderer Schwelle 0.55. **Serien-Schutz:** Titel mit „wieder/erneut/innerhalb N Stunden" gelten als
  eigener Folgefall und werden NIE weggemergt (Ahlen 4× bleibt Serie). Log-Feld `doppler_gg_bestand`.
- **Halluzinations-Check** (`workers/extract.py` + `core/parse.py:ort_conflict`): nach der Extraktion wird
  Claudes `facts.ort` gegen den Titel-`ort` geprüft. Bei echtem Widerspruch → Spalte `cases.warnung`
  (Migration `0003`), sichtbar als ⚠-Banner im Fall-Detail und ⚠ in der Ort-Spalte. **Konservativ:**
  flaggt nur, wenn der Titel-Ort präzise ist — Bundesland-Kürzel (`MV`) und `Kreis …` lösen bewusst
  nicht aus, da gröber als Claudes Stadt-Angabe. Deckt beide Fehlerrichtungen ab (Claude ODER Parser daneben).
- **Bereits eingelagerte Doppler aufgeräumt:** je 1× MV (Nordkurier) + Fachbach (56Aktuell) auf `verworfen`
  (schwächerer Score), die stärkeren Partner (SZ.de 50 / Radio Westerwald 45) bleiben.
- Betroffene Dateien: `core/parse.py` (neu), `core/contracts.py`, `core/supa.py`, `workers/ingest.py`,
  `workers/extract.py`, `api/templates/partials/cases_table.html`, `api/templates/case_detail.html`,
  `api/static/style.css`, `supabase/migrations/0002_ort_tat.sql` + `0003_warnung.sql`.
- **Nach dem Ziehen:** `docker compose up -d --build` (Code läuft in `worker-ingest`/`worker-extract`, Anzeige in `api`).

## Update 2026-07-26 (Job-Timeouts — TTS/Render/Ingest liefen in 180 s-Limit)
- **Symptom:** Fall hing in `in_analyse` mit `FEHLER: TTS: TASK EXCEEDED MAXIMUM TIMEOUT VALUE (180 SECONDS)`.
- **Ursache:** RQ-Default-Job-Timeout = 180 s. TTS läuft im Gemini-**Gratis-Tier (3 Req/Min)** mit
  Backoff; ein Skript mit mehreren Szenen überschreitet 180 s allein durchs Rate-Limit → RQ killt den Job.
  Dieselbe Falle drohte bei **Render** (ffmpeg) und **Ingest** (~270 Dienststellen, ~3 min).
- **Fix:** zentrale Timeout-Tabelle `core/contracts.QUEUE_TIMEOUTS` + `queue_timeout()`, als
  `default_timeout` an jede RQ-Queue gehängt (api-`queue()`, `workers/extract.py`→script,
  `workers/script.py`→tts, `scheduler/main.py`→ingest). Werte: tts 1200 s, render/ingest 900 s,
  extract/script/publish 300 s. Behebt das **Abbrechen** — TTS bleibt im Gratis-Tier aber langsam
  (Minuten); für Tempo Google-**Billing** aktivieren.
- Hängenden Ahlen-Fall: `error`-Feld geleert (State `in_analyse` belassen → nach Rebuild neu vertonen).

## Update 2026-07-26 (Fix: Audio-Wiedergabe brach nach ~6 s ab)
- **Symptom:** Vertonung im Fall-Detail spielte nur ~5 s, dann Stopp — obwohl die `voice.mp3`
  vollständig war (verifiziert: 33,4 s / 134 KB in Storage).
- **Ursache:** `partials/media_panel.html` pollte per HTMX `every 6s` mit `hx-swap="outerHTML"` und
  ersetzte dabei den kompletten Block **inkl. `<audio>`** → Wiedergabe startete bei jedem Refresh neu
  und stoppte nach ~6 s (= Poll-Intervall). Reines UI-Verhalten, kein TTS-/Datei-Problem.
- **Fix:** Auto-Refresh nur noch, solange Medien entstehen (`state in ('in_analyse','in_produktion')`).
  In `review`/`fertig` kein Polling → stabiles `<audio>`. Nach „Clip bauen" (→ `in_produktion`) pollt es
  wieder fürs Video und stoppt danach erneut. Verifiziert: Panel ohne `hx-trigger`, Audio-Dauer 33,4 s.

## Update 2026-07-26 (Strategie Phase 1 + erster kompletter Clip + Prompt-Generator)

### Strategie Phase 1 (per /grill-me abgestimmt, verbindlich)
| # | Thema | Entscheidung |
|---|---|---|
| 1 | Ziel | Ernsthaftes Content-Business (Reichweite → später Monetarisierung) |
| 2 | Nische | Zigaretten**automaten + Geldautomaten**-Sprengungen, bewusst eng |
| 3 | Kanäle | **YT Shorts primär + TikTok + Reels** (dieselbe 9:16-Datei), 1 Fall = 1 Clip |
| 4 | Recht | Volle Guardrails: 48–72 h Alter-Gate, „mutmaßlich/unbekannt", sachlicher Ton |
| 5 | Ausstoß | 3 Clips/Woche, Google-**Billing aktiv** |
| 6 | B-Roll | Higgsfield-Bibliothek (5–8 Kategorien) |
| 7 | Publish | Manueller Upload + KI-Textvorschläge je Plattform |
| 8 | Betrieb | Lokal, VPS später |
| 9 | Langform | Vorgezogen, aber erst NACH den ersten 10 Shorts |
| 10 | Meilenstein | 10 Shorts → 1. Langform → 1.000 Views |

**Einnahme-Realität:** Shorts-RPM winzig (~1–5 ct/1000) → Kurzform = Abo-Trichter, Phase 1 ≈ 0 €.
Echtes Geld erst über Langform (4.000-Watch-Std-Pfad). Sachlicher Ton ist auch Policy-Schutz
(YouTube 2025-Regeln gegen massenproduzierte/repetitive Inhalte).

### Umgesetzt (Code/Konfig)
- **Geldautomaten-Nische:** Score-Bonus `🏧 Geldautomat +15` (`core/scoring.py`); `ALERT_TOPIC_KEYWORDS`
  + Code-Default um `geldautomat,bankautomat,ec-automat` erweitert. RSS = Hauptweg (Mail-Betreff-Filter bleibt `zigaretten`).
- **Guardrail Sprache:** `core/script.py` → Konjunktiv + „mutmaßliche/unbekannte Täter" (Helper `_taeter()`);
  `core/extract.py`-Prompt erzwingt Unschuldsvermutung auch in `details`.
- **Guardrail Alter-Gate:** `workers/publish.py` blockiert Fälle < `MIN_PUBLISH_AGE_HOURS` (Default 48 h,
  facts.datum sonst created_at); Override `force=True`/ENV=0. Beide Richtungen getestet.
- **Google-Billing verifiziert:** 5/5 Burst-Requests ohne 429 (User musste neuen Key am bebillten Projekt
  ziehen — alter Key hing am Gratis-Projekt). `TTS_BACKEND=gemini`, Orus.
- **Oswald-Bold als Overlay-Font:** `assets/fonts/Oswald-Bold.ttf` (googlefonts, OFL) → Dockerfile kopiert
  nach `/usr/share/fonts/truetype/custom/`; `core/render.py:_font()` bevorzugt Oswald, DejaVu-Fallback.
  Hinweis: Overlays laufen über **Pillow**, nicht ffmpeg drawtext.

### Erstmals durchgetestet: Render + Publish (die letzten „nie gelaufen"-Stufen)
- **Render:** Ahlen-Fall `2a71fe18` → valides MP4 1080×1920 (9:16), H.264+AAC, ~92 s Renderzeit.
- **Publish:** Download-URL + Caption + Hashtags + 3 Titel-Vorschläge aus spec.meta; Alter-Gate greift korrekt.
- **Erster Clip mit echtem B-Roll:** 5 Higgsfield-Clips (je 1/Kategorie) über /broll hochgeladen,
  Pools in `core/script.py` temporär auf **1** (→ bei mehr Clips wieder erhöhen!), Fall mit
  **Gemini/Orus neu vertont** (Guardrail-Sprache im Voiceover) und gerendert — Vertical Slice OK.

### Prompt-Generator im Leitstand (User-Wunsch: „ins Programm einbauen")
- **`core/broll_prompts.py`** = Single Source of Truth. Fixe Blöcke als Konstanten (NIE umformulieren):
  `KAMERA_FIX`, `STIL_FIX`, `AUTOMAT_FIX` (der echte weiß-blaue dt. Automat von den User-Fotos).
  Auswahl-Dicts: BELEUCHTUNG/ZUSTAND/UMFELD/KAMERABEWEGUNG/SUBJEKT. `build_prompt()` + Master-Presets
  (`master_automat_neu/gesprengt`, isoliert) + **Kategorie-Presets** (je broll-Kategorie 1 Klick,
  passend zur Szenen-Rolle, mit Upload-Hinweis auf `broll_<kat>_NN.mp4`).
- **UI auf /broll:** Dropdowns + Master-/Kategorie-Buttons + Copy-Button
  (`GET /broll/prompt`, `partials/prompt_out.html`). Automat-Block byte-identisch in jedem Prompt (getestet).
- **Gelernte Fixes (in den fixen Blöcken verankert):**
  1. **Größe:** ohne Maße erzeugt die KI US-Standautomaten → `AUTOMAT_FIX` erzwingt „SMALL, COMPACT
     wall-mounted, ~80×90 cm, chest height, NEVER touches the ground".
  2. **Schreibfehler:** KI kann keinen Text → `STIL_FIX` mit STRICT TEXT RULE (nur ACHTUNG/ab 18/POLIZEI
     lesbar, alles andere unscharf; Marken-Tasten nur über Packungsfarben, keine lesbaren Namen).
- `broll_prompts.md` = Archiv; Quelle ist der Generator.
- **Higgsfield-MCP** eingerichtet (`claude mcp add --transport http --scope user higgsfield
  https://mcp.higgsfield.ai/mcp`) — **OAuth via /mcp noch offen**.

### Nächste Schritte (Reihenfolge)
1. Master-Bild „Automat NEU" in Higgsfield festlegen (Generator-Preset) → Anker für Bild→Video.
2. B-Roll-Bibliothek füllen (3–4 Clips/Kategorie über Kategorie-Presets) → Pools in `core/script.py` hochsetzen.
3. Overlay-Redesign (User: „Katastrophe"; Design soll via Higgsfield entstehen — Karten-Kreis entfernen).
4. Fakten-bewusster Render (B-Roll passend zum Fall-Text: E-Roller ≠ Auto; Zigaretten- vs. Geldautomat).
5. Geldautomat als zweiter fester Block (`AUTOMAT2_FIX`) + eigenes Masterbild.
6. Publish: Multi-Plattform-Textvorschläge (YT-Tags vs. TikTok/Reels-Hashtags) → dann 10-Shorts-Meilenstein.

## Update 2026-07-30 (Alert „Geldautomat Sprengung" wurde nie abgeholt · Datumsformat · Statusband)

**1. Google-Alert „Geldautomat Sprengung" kam nie an (Fehler gefunden).**
`ALERT_SUBJECT_FILTER` war ein **einzelner** Begriff (`zigaretten`) und wurde zweifach
angewandt: als IMAP-`SUBJECT`-Kriterium und als Gegenprobe im Code. Der Betreff
„Google Alert – Geldautomat Sprengung" enthält dieses Wort nicht → die Mail wurde
serverseitig gar nicht erst gefunden. Der Treffer-Filter `ALERT_TOPIC_KEYWORDS`
kannte `geldautomat` zwar längst, kam aber nie zum Zug.
→ `core/mail.py`: `ALERT_SUBJECT_FILTERS` ist jetzt eine **kommagetrennte Liste**
(ein Treffer genügt). Neuer Helfer `_subject_criteria()` baut das geschachtelte
IMAP-`OR` (`OR SUBJECT "a" SUBJECT "b"`), `matches_subject()` die Gegenprobe.
`.env`: `ALERT_SUBJECT_FILTER=zigaretten,geldautomat`.
**Beleg:** Mail-Ingest 30.07. → 55 Kandidaten / 30 über Schwelle / **15 neu angelegt**,
davon **13 mit Geld-/Bankautomat** (u. a. Glinde Score 90, Fürth 75). Vorher: 0.
Nebenbefund aus der Fehler-Queue: der letzte echte Mail-Lauf (25.07.) war zusätzlich
an `IMAP4.error: Invalid credentials` gescheitert — mit dem inzwischen eingetragenen
App-Passwort läuft er sauber durch.

**2. Datumsformat TT.MM.JJJJ statt ISO.**
Neue Jinja-Filter in `api/main.py`: `dt_de` (→ `30.07.2026 15:13`) und `datum_de`
(nur Datum). Rechnen UTC→`TZ` (Europe/Berlin) um und reichen Unparsbares
unverändert durch, statt zu knallen. Eingesetzt in `cases_table.html` (created_at),
`case_detail.html` (facts.datum), `status_badge.html` (updated_at).
`Dockerfile`: **tzdata** ergänzt — ohne die Zeitzonendatenbank konnte `zoneinfo`
`Europe/Berlin` nicht auflösen und die UI hätte UTC (2 h daneben) gezeigt.

**3. Statusband + kaputter Auto-Refresh.**
Neu: `GET /partials/status` + `partials/statusbar.html` — Lampe (Bereit/arbeitet/
Fehler), Queue-Chips je Stufe (laufend/wartend/fehlgeschlagen), Fallzahlen je
Zustand (klickbar als Filter), „Stand HH:MM:SS". Pollt sich alle 5 s selbst.
Redis- bzw. DB-Ausfall wird im Band gemeldet, statt das Dashboard mit 500 zu killen.
**Bugfix dahinter:** Tabelle und Filter ersetzten `#cases-table-wrap` per
`hx-swap="innerHTML"` — die Antwort enthält diesen Container aber selbst, also
verschachtelte er sich bei jedem Durchlauf ineinander (doppelte IDs, Poller
vervielfachten sich pro Zyklus). Jetzt durchgängig `hx-target="this"` +
`hx-swap="outerHTML"`. Verifiziert: beide Partials liefern den Container genau 1×.

## Update 2026-07-30 (TikTok-„Blacklist" geprüft und verworfen · Methoden-Sperre · Disclaimer)

Anlass: `True_Crime_TikTok_Automaten_Guide.pdf` fordert eine „Blacklist für
Shadowban-Vermeidung" — „gesprengt" → „detoniert / in die Luft gejagt",
„Sprengstoff" → „**Gasgemisch / pyrotechnischer Satz**".

**Die Blacklist wurde bewusst NICHT übernommen.** Begründung dokumentiert, damit
das nicht alle drei Monate neu diskutiert wird:
1. **Unbelegt.** TikTok-Wortfilter sind für **Kommentare** belegt (ARD-Test 2022:
   19 von 100 Wortkombinationen unterdrückt), „Algospeak" ist in der Forschung
   rund um Suizid/Sex/marginalisierte Gruppen dokumentiert — nicht bei
   Kriminalitätsberichten. TikTok liefert zu „geldautomaten gesprengt" selbst
   Suchergebnisse; deutsches True Crime hat >3 Mio. Beiträge.
2. **Kontraproduktiv.** Verboten sind laut Richtlinien *Anleitungen zu
   schädlichen Taten* und *Verherrlichung*. „Gasgemisch"/„pyrotechnischer Satz"
   benennen die Methode **präziser** — die Ersetzung senkt ein eingebildetes
   Risiko und erhöht das echte.
3. **Widerspruch zur Strategie.** Der PDF-Systemprompt fordert „extrem
   reißerisch"; Guardrail 4c legt sachlich-dokumentarischen Ton fest.

**Stattdessen umgesetzt — Methoden-Sperre („Kategorie ja, Rezept nein"):**
Das echte Loch war, dass `werkzeug` laut Prompt „Tatwerkzeug/**Vorgehen**"
liefern sollte und `core/script.py` das wörtlich ausspricht („Mit {werkzeug}
sollen die Täter vorgegangen sein"), ebenso das freie Feld `details`.
- **`core/parse.py`** (neu, passend zu „reine Regex, kein I/O"): `_METHODE_RE`,
  `hat_methode()`, `entschaerfe_methode()`. Gesperrt sind Stoffarten
  (Gasgemisch, Butan, Propan, Schwarzpulver …), Mengen, Zuführung
  („über einen Schlauch eingeleitet"), Zündmechanismen. **Erlaubt bleiben**
  „gesprengt", „Sprengung", „Sprengsatz", „Explosion", „Winkelschleifer" —
  das ist Kategorie, keine Anleitung.
  Wichtig: entfernt wird der **ganze Satz**, kein `[entfernt]`-Platzhalter —
  die Felder landen im Voiceover, die TTS würde den Platzhalter vorlesen.
- **`core/extract.py`**: neue harte Prompt-Regel + Aufruf in `sanitize()`.
  `werkzeug` wird jetzt als *Gegenstand* angefordert („einem Sprengsatz"), nicht
  als Vorgang — sonst entsteht „Mit Sprengung sollen die Täter vorgegangen sein".
- **`workers/extract.py`**: erkennt vor dem Säubern, ob Methoden-Details da
  waren, und hängt „Methoden-Details entfernt" an die `warnung` (⚠ im Review).
- **`core/script.py`**: zweites Gate in `build_spec()` → **Bestandsfälle sind
  ohne erneuten Claude-Lauf abgedeckt.**

**Disclaimer** (die brauchbare Idee aus der PDF): neue Konstante `DISCLAIMER` in
`core/script.py`, hängt an `spec.meta.caption` und läuft über
`workers/publish.py` auf alle Plattformen mit — „sachliche Dokumentation auf
Basis offizieller Polizeimeldungen, Unschuldsvermutung, Nachahmung strafbar".

**Nachgezogen (gleicher Tag, beide aus dem Live-Test entstanden):**

1. **`[entfernt]`-Platzhalter beseitigt.** `sanitize()` ersetzte Straßen/PLZ in
   `details`/`werkzeug`/`tat` durch `"[entfernt]"` — die TTS hätte das wörtlich
   vorgelesen („eckige Klammer entfernt"). Jetzt greift dieselbe satzweise Logik
   wie bei den Methoden-Details: neuer generischer Helfer
   `core.parse.drop_saetze(text, muster)`, den sowohl `entschaerfe_methode()`
   als auch das neue Sammelmuster `_PII_RE` (Koordinaten/PLZ/Straße) nutzen.
   Im `ort`-Feld bleibt es beim Herausschneiden der Fragmente — das ist kein
   gesprochener Satz, sondern ein Stadtname.
2. **Unschuldsvermutung abgesichert.** Die Distanz steckte bisher NUR im
   Vorspann der werkzeug-Zeile („sollen … vorgegangen sein"). Fällt die weg —
   kein Werkzeug bekannt oder vom Methoden-Filter entfernt — und formuliert
   Claude in `details` assertiv, ging der ganze Text als Tatsachenbehauptung
   raus. Neu in `core/script.py`: `_DISTANZ_RE` + `_distanz_fehlt()`; fehlt im
   erzählenden Teil (eskalation + story) jede Distanzierung, wird
   „Nach bisherigen Erkenntnissen sollen … für die Tat verantwortlich sein."
   ergänzt. Ist schon Distanz da, passiert nichts (keine Dopplung).
   **Wichtig:** „unbekannte Täter", „Ermittlungen" und „Zeugen" zählen bewusst
   NICHT als Distanz — „Zwei unbekannte Täter sprengten …" behauptet die Tat
   weiterhin als Tatsache. Genau dieser Fall war im ersten Anlauf durchgerutscht.

3. **Konjunktiv-Regel im Extract-Prompt verschärft.** Die alte Regel nannte
   ausgerechnet „unbekannte Täter" als zulässiges Distanzierungsmittel — Claude
   hat also mit „Zwei unbekannte Täter sprengten …" korrekt den Prompt befolgt.
   **Der Prompt selbst hat das falsche Muster beigebracht.** Neu: nur „sollen …
   haben/sein", „mutmaßlich" und „angeblich" gelten; „unbekannt" allein wird
   ausdrücklich als NICHT ausreichend bezeichnet. Dazu zwei FALSCH/RICHTIG-
   Beispielpaare und die Klarstellung, dass Sätze ohne handelnde Personen
   (Schäden, Behörden-Handeln) im Indikativ bleiben.
   **Wirkung (2 Fälle live):** `details` steht jetzt durchgängig im Konjunktiv,
   Schadenssätze bleiben normal — der Fallback-Satz aus Punkt 2 wurde in beiden
   Fällen nicht mehr gebraucht. Er bleibt als Netz für Ausreißer bestehen.

4. **Werkzeug-Satz stapelt kein „sollen" mehr.** `_line_story()` hat jetzt zwei
   Varianten, gesteuert über `distanz_vorhanden`: Steht `details` schon im
   Konjunktiv, kommt agentloses Passiv („Mit einem Sprengsatz wurde offenbar
   vorgegangen.") — ohne handelnde Personen ist das keine Schuldbehauptung.
   Nur wenn `details` assertiv ist, trägt der Werkzeug-Satz die Distanzierung
   selbst („… sollen die unbekannten Täter vorgegangen sein."). Alle vier
   Kombinationen (details distanziert/assertiv × werkzeug ja/nein) getestet,
   in jeder ist genau eine Distanzquelle aktiv.

5. **0-Euro-Bug in `_line_zahlen()` gefixt.** Die Funktion prüfte nur auf
   `None`, behandelte `0` also wie einen echten Betrag → „Die Beute wird auf
   rund **0 Euro** geschätzt." (real aufgetreten in Fürth: Täter kamen nicht an
   die Kassetten, Claude lieferte korrekt `beute_eur=0`). `0` ist eine AUSSAGE,
   kein fehlender Wert — jetzt durchgehend `is not None` plus eigene Texte
   („Beute wurde keine gemacht." / „Nennenswerter Sachschaden entstand nicht.").
   Alle 8 Kombinationen aus beute/schaden × {Wert, 0, None} getestet, die vier
   bisherigen Ausgaben unverändert. Neuer Helfer `_eur()` formatiert den
   Tausenderpunkt, damit `.replace(",", ".")` nicht mehr über ganze Sätze läuft.

**Beleg (Glinde, Score 90, live durchgelaufen bis `review`):** Claude lieferte
`werkzeug="Festsprengstoff"` → gefiltert auf `None`, ⚠-Warnung gesetzt,
Voiceover ohne Methoden-Detail, ohne Platzhalter, mit Distanz-Satz, `voice.mp3`
erzeugt. (Der erste Regex-Entwurf kannte nur „Feststoffsprengstoff" —
Typ-Bezeichnungen werden jetzt generisch über `\w+sprengstoff` erfasst, das
blanke „Sprengstoff" bleibt erlaubt.)

## Update 2026-07-30 (Lektor-Stufe: Sprechtexte glätten + Lesbarkeits-Ampel)

Anlass: Die Texte waren fachlich korrekt, aber schwer hörbar — Schachtelsätze,
Semikolons, Wortwiederholungen, gelegentlich Tippfehler des Modells
(„ein kleineres Feuer gelösch; es ist jedoch nicht einsturzgefährdet").

**Neues Modul `core/lektor.py`** — zwei Funktionen, beide ohne Seiteneffekt:
- `lesbarkeit(text)` → Wiener Sachtextformel (Schulstufe) + konkrete Marker
  (Satz > 20 Wörter, Semikolon, Mehrfach-Nebensätze, Wortwiederholung ≥ 3×).
  Reine Funktion, keine neue Abhängigkeit (Silben über Vokalgruppen genähert).
- `lektoriere(scenes)` → **ein** Claude-Aufruf (Haiku) für alle Szenen, damit
  der Lektor den Zusammenhang sieht. Prompt: kurze Hauptsätze, kein Semikolon,
  keine Relativsatzketten, Tippfehler raus, **Straffen erlaubt** — Kernfakten
  (Ort, Zeit, Tat, Beute, Schaden, Fahndung) sind Pflicht.

**Der Lektor kann die Guardrails nicht aushebeln.** Jeder Vorschlag läuft durch
`extract.pruefe_text()` (Adresse/PLZ/Koordinaten, Methoden-Details) und
`parse.distanz_fehlt()`. Fällt er durch, wird er **verworfen** — die Szene
behält ihren Originaltext, der Grund steht in der UI. Mit gefälschten Antworten
verifiziert: Distanzverlust, Methoden-Detail und Adresse werden alle drei
abgefangen, nur der saubere Vorschlag geht durch.

**Vorarbeit (geteilte Prüfungen):** `_DISTANZ_RE`/`_distanz_fehlt` aus
`core/script.py` nach `core/parse.py` verschoben und als `distanz_fehlt()`
öffentlich gemacht (dort wohnen die reinen Textregeln); neue
`extract.pruefe_text(text) -> list[str]` bündelt PII- und Methoden-Prüfung.

**Bedienung — nie automatisch.** Button „Text glätten (Lektor)" auf der
Fall-Seite. Das Ergebnis ist ein Vorher/Nachher-Panel mit Ampel auf beiden
Seiten. Das Panel ist **selbst ein Formular auf das bestehende `/retts`**
(Textareas vorbelegt und weiter editierbar, `caption` unverändert als hidden
input) — kein neuer Speicher-Endpunkt, kein JavaScript, kein neuer Zustand.
Absenden = speichern + neu vertonen wie gehabt. Zusätzlich zeigt jede Szene im
normalen Skript-Formular ihre Lesbarkeits-Ampel (Tooltip nennt die Marker).

**Beleg (Fürth-Fall, live):** Problemszene vorher **13,5 „schwer"** → nachher
**10,6 „mittel"**; Gesamttext nach Übernahme **7,7 „gut"**. Semikolon weg,
„gelösch" korrigiert, der Amsterdam-Schachtelsatz in zwei Sätze aufgelöst,
Konjunktiv überall erhalten, `voice.mp3` neu erzeugt. Drei bereits saubere
Szenen wurden korrekt als „unverändert" gemeldet.

**Grenzen, bewusst so:** Der Lektor ist nicht deterministisch — zwei Läufe auf
denselben Text liefern leicht unterschiedliche Vorschläge. Deshalb Vorschlag
statt Automatik. Die Marker melden weiterhin „sollen 3× wiederholt": Das ist
der Preis der Unschuldsvermutung und kein Fehler. Beim Straffen kann es zu
leichter Umdeutung kommen (im Test wurde aus „Bankfiliale im Erdgeschoss eines
Wohnhauses" ein „Wohnhaus mit Erdgeschoss-Laden") — deshalb steht das
Vorher/Nachher nebeneinander und wird gegengelesen.

## Update 2026-07-30 (Formregeln im Extract-Prompt — Ursache statt Symptom)

Erkenntnis aus dem Lektor-Einsatz: Alle Lesbarkeitsprobleme entstehen bei der
**Extraktion**, nicht danach. Der Prompt schrieb Claude bisher nur vor, *was* in
`details` stehen soll (Fakten, Konjunktiv, keine Methode) — nichts über die
*Form*. Neuer Abschnitt **SPRECHBARKEIT** im Prompt (`core/extract.py`):
kurze Hauptsätze, ein Gedanke pro Satz, max. ~20 Wörter, **kein Semikolon und
kein Gedankenstrich** (beim Hören nicht wahrnehmbar), keine angehängten
Relativsatz-Ketten — mit Gegenbeispiel. Feld-Beschreibung von „1-2 Sätze" auf
„2-4 kurze Sätze zum VORLESEN" geändert. Kostet nichts, ist deterministisch
verfügbar und greift bei jedem Fall, statt pro Klick einen Lektor-Aufruf.

**Wirkung (beide Testfälle neu extrahiert):**
- Fürth (der Problemfall): Semikolon und Gedankenstrich **weg**, Tippfehler weg,
  Voiceover gesamt **8,8** — vorher hatte eine einzelne Szene 13,5 „schwer".
  Ohne einen einzigen Lektor-Klick.
- Glinde: **keine Marker mehr**, Voiceover 9,0.

**Nicht vollständig gelöst:** Fürth enthält weiter einen 21-Wort-Satz mit genau
der Relativsatz-Kette, die im Prompt als Gegenbeispiel steht („…geflüchtet sein,
das später in Amsterdam …"). Der Konjunktiv verlängert Sätze zwangsläufig
(„geflüchtet sein, das … gewesen sein soll"). Genau dafür bleibt der Lektor als
Werkzeug für Ausreißer sinnvoll — er ist jetzt Ausnahme statt Regel.

**Nachgezogen: Konjunktiv-Bruch.** Claude mischte in einem Satz Konjunktiv und
Indikativ — „Sie sollen Geldkassetten mitgenommen und **sind** mit Fahrrädern
geflüchtet." Der zweite Teilsatz war damit wieder assertiv, und `distanz_fehlt()`
schlug nicht an, weil „sollen" ja im selben Satz steht.
- **Prompt:** neue Regel „Der Konjunktiv gilt bis zum Satzende — auch in
  angehängten Teilsätzen nach *und*" mit FALSCH/RICHTIG-Paar.
- **Prüfung** (nach dem etablierten Muster Prompt + harte Kontrolle + Warnung):
  `parse.konjunktiv_bruch()` erkennt „soll(en) … und {sind|ist|hat|haben|war|
  waren|wurde|wurden}" satzweise; `workers/extract.py` hängt daraus die Warnung
  „Konjunktiv bricht im Satz ab" ans ⚠-Flag. **Bewusst keine Auto-Korrektur** —
  Grammatik per Regex umzubauen ist nicht sicher, der Mensch formuliert nach.

**Endstand beider Testfälle nach Form- + Konjunktiv-Regeln (frisch extrahiert):**
- Glinde: „Sie sollen Geldkassetten mitgenommen und auf Fahrrädern geflüchtet
  **sein**." → Bruch behoben, Voiceover **7,8 „gut"**, keine Marker.
- Fürth: die Relativsatz-Kette ist weg, Claude macht daraus einen eigenen Satz
  („Das mutmaßliche Fluchtauto soll später in Amsterdam …"). Voiceover **8,9**,
  keine Marker — vorher hatte eine einzelne Szene 13,5 „schwer".
Damit ist der Lektor endgültig Ausnahme- statt Regelwerkzeug.

## Update 2026-07-30 (Ende der „sollen"-Party — Distanzierung mit Abwechslung)

Rückmeldung des Nutzers zum Text: drei „sollen" in vier Sätzen. **Ursache war
meine eigene Prompt-Regel**, die ausdrücklich vorschrieb: „Zulässig sind NUR
diese drei Mittel: sollen / mutmaßlich / angeblich." Damit war die Wiederholung
erzwungen. Deutsche Kriminalberichterstattung hat deutlich mehr Register.

**Neu im Prompt** — Palette statt Zwang, mit Abwechslungspflicht („sollen"
höchstens EINMAL pro details-Text, nie zweimal dasselbe Mittel hintereinander):
Konjunktiv I der indirekten Rede („hätten gesprengt", „seien geflüchtet"),
„sollen", „mutmaßlich"/„Tatverdächtige", Quellenzuschreibung („laut Polizei",
„nach Angaben der Ermittler", „den Ermittlern zufolge"), „angeblich"/„offenbar"
— und als beste Lösung, wo möglich: **Satz ganz ohne handelnde Person**
(„Der Geldautomat wurde gesprengt.") Ohne Täter-Subjekt gibt es nichts zu
behaupten und nichts zu distanzieren. Dazu ein Musterbeispiel mit vier Sätzen
und vier verschiedenen Mitteln.

**`parse._DISTANZ_RE` entsprechend erweitert** — sonst hätte die Distanz-Prüfung
die neuen Formen als fehlende Distanz missverstanden und den Fallback-Satz
gefeuert: Konjunktiv I (hätte/hätten/sei/seien/wäre/wären/habe),
„laut <Behörde>", „nach Angaben/Erkenntnissen", „zufolge", „offenbar".
Acht Positiv- und drei Negativfälle getestet.

**Wirkung (drei Fälle neu extrahiert):** „sollen" von 3× auf **0×, 0×, 1×**.
Beispiel Glinde: „In der Nacht zu Montag **wurde** ein Geldautomat gesprengt.
**Nach Angaben von Zeugen hätten** zwei Männer … die Flucht ergriffen." —
Passiv, Quellenzuschreibung und Konjunktiv I in zwei Sätzen.

**Zwei ehrliche Nebenwirkungen:**
1. **Die Lesbarkeitswerte STIEGEN** (Fürth 8,9 → 11,8; Bergstraße 13,3), obwohl
   der Text besser klingt. Grund: Die Wiener Sachtextformel bestraft lange
   Wörter, und „Nach bisherigen Erkenntnissen" ist nun mal länger als „sollen".
   Die Formel ist für geschriebene Prosa gemacht und straft deutsche Komposita
   generell ab. **Konsequenz: Die Marker sind für Sprechtexte das verlässlichere
   Signal als die Zahl** — sie blieben hier leer. Die Zahl bleibt als grober
   Trend nützlich, taugt aber nicht als Zielgröße.
2. Claude baut vereinzelt schwerfällige Konstruktionen („gelang es den Tätern
   nicht, … zu gelangen"). Dafür ist der Lektor da.

**Der Konjunktiv-Detektor hat sich im Echtbetrieb bewährt:** Bergstraße kam mit
„… sollen die Sprengung durchgeführt haben **und sind** anschließend geflüchtet"
zurück — Warnung „Konjunktiv bricht im Satz ab" steht am Fall. Die Prompt-Regel
allein reicht also nicht, die harte Prüfung fängt den Rest.

## Update 2026-07-30 (Unschuldsvermutung korrigiert — sie schützt Personen, nicht Ereignisse)

Einwand des Nutzers: „Unbekannte Täter **sollen** einen Geldautomaten gesprengt
haben" sei falsch — sie haben es ja getan, sonst gäbe es die Meldung nicht.
**Der Einwand ist berechtigt.** Beleg aus dem eigenen `fulltext` des
Bergstraße-Falls (Originalquelle, Medium zitiert die Polizei):

> „In Fürth ist der Geldautomat … von Unbekannten **gesprengt worden**. Die
> Täter **sind** flüchtig. […] Unbekannte Täter **machten sich** an dem
> Automaten zugange."

Kein einziger Konjunktiv. Wir formulierten also vorsichtiger als die Quelle,
aus der wir zitieren.

**Die Trennlinie, die vorher fehlte:**
- **Die Tat** (dass gesprengt wurde) ist Tatsache → **Indikativ**.
- **Die Täterschaft** ist das Angreifbare — und nur, wenn jemand IDENTIFIZIERT
  ist. Bei unbekannten/flüchtigen Tätern existiert keine Person, die
  vorverurteilt werden könnte → **Indikativ ist korrekt** (so schreiben Polizei
  und Presse selbst).
- **Distanz Pflicht**, sobald jemand festgenommen/benannt ist („der 24-Jährige",
  „die Festgenommenen") — dort greift die Unschuldsvermutung wirklich.
- **Distanz auch**, wenn der Hergang selbst unsicher ist (nur Zeugenangaben).

**Umgesetzt, gesteuert über das vorhandene `facts.ungeloest`:**
- `core/extract.py`: Prompt-Block (A)/(B) mit den drei Fällen und je einem
  Musterbeispiel für „unbekannte Täter" (Indikativ) und „identifiziert" (Distanz).
- `core/script.py`: `_line_story()` hat jetzt drei Varianten — bei `ungeloest`
  Indikativ („Mit einem Sprengsatz gingen die unbekannten Täter vor."), sonst wie
  bisher. Der Fallback-Satz feuert **nur noch bei identifizierten Personen**.
- **Loch dabei gefunden und geschlossen:** Der Fallback prüfte Eskalations- und
  Story-Zeile ZUSAMMEN — ein „sollen" aus der Werkzeug-Zeile verdeckte damit eine
  Schuldbehauptung wie „Der Festgenommene sprengte den Automaten." Jetzt wird
  **je Zeile** geprüft.
- `workers/extract.py`: neue Warnung „Beschuldigter benannt, aber Text ohne
  Distanz — Unschuldsvermutung prüfen!". Automatisch reparieren lässt sich das
  nicht (der assertive Satz bliebe stehen), hier muss der Mensch ran.

**Beleg (Bergstraße neu extrahiert, ungeloest=true):** „Ein Geldautomat in einer
Bankfiliale **wurde** am frühen Dienstagmorgen gesprengt. Unbekannte Täter
**flüchteten** vom Tatort, eine umfangreiche Fahndung **läuft**." — **0× „sollen"**,
kein Fallback-Zusatz, keine Warnung. Register identisch zur Quelle.

## Update 2026-07-31 (B-Roll aus echtem Bildmaterial — der Engpass ist gefallen)

**Problem seit dem 26.07.:** Text-Prompts erzwingen keine Objektkonstanz. Zwei
Läufe mit wörtlich identischem `AUTOMAT_FIX`-Block lieferten zwei verschiedene
Automaten. Der Ausweg aus BROLL_PLAN.md (Masterbild-Kette) war unumgesetzt und
hing selbst wieder an einem *generierten* Master.

**Der Weg jetzt: Konsistenz kommt aus Pixeln, nicht aus Prompts.** Der Automat
wird nie generiert, sondern aus einem echten Foto freigestellt und in eine
**leer** generierte Nachtszene gesetzt. Das Modell erfindet nur noch die
Bewegung. Kette und Kosten:

| Schritt | Werkzeug | Kosten |
|---|---|---|
| Freistellen (Alphakanal) | `tools/freistellen.py` | 0 |
| Leere Platte, **ohne** Objekt | `soul_location` | 0,06 |
| Einsetzen, Licht messen, Schatten | `tools/komposit.py` | 0 |
| Start-/Endkader schneiden | `tools/kader.py` | 0 |
| Bild→Video | `seedance_2_0` | 45 / Clip |

Bedient über den Slash-Command **`/broll`**. BROLL_PLAN.md ist entsprechend
als teilweise überholt markiert.

**Fünf Erkenntnisse, jede an einem Fehlschlag bezahlt:**

1. **Nacht-Platten sind reines Natriumlicht, kein „dunkles Blau".** Messung von
   `szene_b.png`: R 0,133 / G 0,095 / **B 0,012**. Der erste Kompositversuch gab
   dem Objekt kühle Schatten (Filmlehre: Tiefen blau) — Ergebnis war braune
   Pampe. Deshalb misst `komposit.py` die Lichtfarbe aus dem Vordergrund der
   Platte, statt sie anzunehmen. Nebeneffekt: bei einer `blaulicht`-Platte tönt
   sich das Objekt automatisch blau, ohne Codeänderung.
2. **Die Helligkeit nimmt zur KAMERA hin zu, nicht zur sichtbaren Lampe hin.**
   Gemessen: Gras vorn 0,096–0,128, Asphalt Mitte 0,052. Der Helligkeitsverlauf
   auf dem Objekt läuft entsprechend nach unten heller. Andersherum sieht es
   sofort falsch aus.
3. **Zielkonflikt bei Bild→Video, dreimal reproduziert:**
   nur `start_image` → Atmosphäre (Rauch), aber unkontrollierte Kamera;
   `start_image` + `end_image` → kontrollierte Kamera, aber **kein** Rauch.
   Voreinstellung ist Kontrolle: eine Fahrt, die aus dem Bild läuft, ist
   Ausschuss (so geschehen bei `effekt_02_tracking`), fehlender Dunst nur
   weniger Stimmung.
4. **Der Endkader ist ein Ziel, keine Fessel.** Gemessen an je einem Clip:
   Zoomfahrt landet ~20 % **zu eng**, Seitwärtsfahrt ~10 % **zu kurz**. Wer
   exakt ankommen will, gibt den Endkader entsprechend großzügiger vor.
   Seitwärtsfahrten trifft das Modell deutlich genauer als Zoomfahrten.
5. **Der Moderationsfilter wertet ohne Verneinung.** Der Prompt-Zusatz
   „no fire, no flames, no sparks" — gedacht, um eine Rauchsäule zu vermeiden —
   ließ den Job als `status: nsfw` abbrechen. **Identisches Bildmaterial lief
   ohne diese Wörter durch.** Feuer- und Sprengbegriffe in Anim-Prompts also
   komplett meiden, auch verneint. Hart geprüft in
   `broll_prompts.pruefe_anim_prompt()`; `build_anim_prompt()` wirft ValueError.
   Abgerechnet wird ein abgelehnter Lauf zunächst und dann erstattet (−45/+45).

**Weiteres:**
- **Higgsfield-Presets ablehnen** (`declined_preset_id`). Der Vorschlag
  „IN THE DARK" hätte eigene Kamera und Farbgebung mitgebracht.
- **Die Platte ist mit 1152 px das auflösungsbegrenzende Glied**, nicht das
  3000-px-Foto. Kader daraus werden hochskaliert; `kader.py` warnt ab 1,4×.
  Bei 1,34× war es im Bewegtbild unauffällig.
- **Grenze:** Die Lichtrichtung auf dem Objekt ist aus dem Quellfoto eingebacken.
  Farbe und Pegel lassen sich umrechnen, die Richtung nicht.

**Stand:** `effekt`-Runde 1 fertig, 4 Clips in `assets/master/`, 2 empfohlen.
Verbraucht 180,24 Credits (1358 → 1177,76). `kulisse` ist blockiert, solange
keine Original-Fotos des *unbeschädigten* Automaten vorliegen.

## Update 2026-07-31 abends (Umfärben schlägt Komposit — und drei Korrekturen)

Der Komposit-Weg von heute Nachmittag ist an einem **zweiten** Wrackfoto
gescheitert, und zwar an der Perspektive. Daraus ist ein besserer Weg entstanden.

**Der Fehler:** `BLICKWINKEL_FIX` war eine feste Konstante („steeply down,
roughly 45 degrees"), geschrieben nach dem ersten Wrackfoto. Das zweite Foto ist
mit 25–30 Grad deutlich flacher aufgenommen. Ein Freisteller ist ein 2D-Ausschnitt
mit **eingebackenem** Blickwinkel — er laesst sich weder drehen noch kippen. Die
Platte muss sich also nach dem Foto richten, nie umgekehrt. `BLICKWINKEL` ist
deshalb jetzt eine Auswahlliste und **Pflichtparameter** von
`build_platte_prompt()`; ohne Angabe wirft die Funktion.

**Der bessere Weg — umfaerben statt komponieren.** Statt das Objekt
freizustellen und in eine generierte Platte zu setzen, wird das **Originalfoto**
per `gpt_image_2` auf Nacht umgefaerbt und dabei nur der Hintergrund ersetzt:

```
FOREGROUND, keep completely untouched:  Wrack, Boden, Streugut
BACKGROUND, replace entirely:           Haus, Zaun, Poller -> dunkle Vegetation
Relight:                                Tag -> Nacht mit Blaulicht
```

Die Perspektive kann nicht kippen, weil sie nie verlassen wird. Gebaut als
`broll_prompts.build_umfaerben_prompt()`; die Reihenfolge (erst was bleiben MUSS,
dann was weg SOLL) ist Absicht — umgekehrt raeumt das Modell zu viel weg.

**Belegter Durchlauf** (Foto `1000004289.jpg`, Automat mit VISA-Beklebung auf
Gehweg): Haus, gruener Gartenzaun, Sichtschutzwand und Poller vollstaendig
ersetzt, Wrack samt Streugut und Metallschiene pixelgenau erhalten. Zwei Clips
`visa_01_automat.mp4` und `visa_02_streugut.mp4`.

**Kostenverhaeltnis, das die Arbeitsweise bestimmt:**

| Posten | Credits |
|---|---|
| 4 Platten (Komposit-Versuch) | 0,24 |
| 2 Umfaerbungen | 6 |
| 2 Hybriden (umfaerben + Hintergrundtausch) | 6 |
| 2 Videoclips | 90 |
| **gesamt** | **102,24** |

Der gesamte Bildteil kostet ein Viertel **eines** Clips. Bei Bildern also
grosszuegig probieren, bei Videos nicht.

### Drei Korrekturen an frueheren Eintraegen

1. **Die Landungs-Faustregel ist widerlegt.** Der Eintrag von heute Nachmittag
   („Zoom +20 %, Seitwaerts −10 %") beruhte auf je einem Clip. Von drei
   Seitwaertsfahrten lag eine ~10 % zu kurz, eine praktisch exakt, eine deutlich
   zu weit. Die Abweichung **streut** (bis ca. ±20 %), sie ist nicht
   systematisch. Der Korrekturfaktor ist aus `kader.py` entfernt; geblieben ist
   der Hinweis, den letzten Frame zu pruefen.
2. **Streugut freistellen braucht Farbkontrast zum Boden.** Beim ersten Foto lag
   es auf dunklem Asphalt und gruenem Gras — leicht trennbar. Beim zweiten auf
   **grauen Gehwegplatten**, und die Teile sind selbst grau-weiss: die
   Farbtrennung in `freistellen.py --nest` liefert dort fast nichts (574 bzw.
   446 px). Keine Einstellungssache, sondern eine Bedingung des Verfahrens.
3. **`komposit.py` hatte eine stille Fehlerquelle.** Bei einer Platte mit
   stockschwarzem Boden (gemessener Vordergrund 0,002) rechnete es das Objekt auf
   0,004 herunter und lieferte kommentarlos eine schwarze Silhouette. Neu:
   `VORDERGRUND_MIN = 0.03` samt Warnung, dass die Platte vermutlich untauglich ist.

### Die STRICT TEXT RULE schadet beim Umfaerben (kontrolliert nachgewiesen)

Am Wandautomaten mit Polizei-Absperrband (`1000001880.jpg`) aufgefallen und
anschliessend sauber isoliert: **identisches Foto, identische Vorder- und
Hintergrundanweisung, einzige Aenderung war die Textregel.**

| | Absperrband im Ergebnis |
|---|---|
| mit `STRICT TEXT RULE` (aus STIL_FIX) | „**ab 18**" und „**POLIZEI**" — neu beschriftet |
| mit `TEXT_REGEL_ECHTFOTO` | echte Aufschrift „POLIZEIABSPERRUNG" erhalten |

**Die Ursache:** Die Regel wurde fuer GENERIERTE Bilder geschrieben, wo erfundene
Fantasieschrift das Risiko ist. Auf ein **bearbeitetes Echtfoto** angewendet
kehrt sie sich um — das Modell sieht echte Schrift, haelt sie fuer verboten und
schreibt sie auf die erlaubte Wortliste um. Heraus kommt „ab 18" auf einem
Polizei-Absperrband.

**Der Schaden ging weiter als nur der Text.** Dieselbe Regel leerte die
beschriftete Werbetafel am Automaten zu einer weissen Platte und duennte das
Streugut aus — obwohl der Prompt den Vordergrund dreimal als unantastbar
bezeichnete. Die Textregel hat die Vordergrund-Anweisung ueberstimmt. Mit der
Erhaltungsregel ist die Werbetafel wieder da.

**Umgesetzt:** `STIL_FIX` ist aufgeteilt in `STIL_BASIS` + `TEXT_REGEL_GENERIERT`
und bleibt fuer alle bestehenden Aufrufer **byte-identisch** (geprueft).
`build_umfaerben_prompt()` nutzt stattdessen `STIL_BASIS` +
`TEXT_REGEL_ECHTFOTO`. Merksatz: Echte Schrift auf einem echten Foto ist keine
Halluzination, sondern Beleg.

### Wann welcher Weg

**umfaerben** ist der Standard. **komposit** ist richtig, wenn das Objekt an einen
*anderen* Ort soll — die Kette dafuer steht und ist verifiziert. Beides bedient
der Slash-Command `/broll`.

## Update 2026-08-01 (Tiefen-Debug des Stacks · .dockerignore · error-Feld gefixt)

Gruendlicher Durchgang durch alle neun Container. **Der Stack ist gesund** —
0 Neustarts, kein OOM, kein Fehler-Exit, kein Traceback in irgendeinem Log,
Scheduler mit genau zwei Jobs (07:00/19:00, keine Dubletten), Speicherverbrauch
26–70 MB je Container von 3,7 GB.

**Zwei Verdachtsfaelle geprueft und entkraeftet** — beide sind hier notiert,
damit sie nicht noch einmal untersucht werden:

1. **HTMX-Poller vervielfacht sich nicht.** Die Fall-Detailseite pollt
   `/cases/<id>/partials/status` mit **konstant 14 Anfragen/Minute** ueber acht
   Minuten gemessen — die in CLAUDE.md dokumentierte Verschachtelung tritt
   nicht auf.
2. **Redis laeuft nicht heiss.** Im Log stehen 113 BGSAVE-Vorgaenge, das sah
   nach einer Schleife aus. Sie verteilen sich aber ueber **6,7 Tage** (der
   redis-Container wird nur neu *gestartet*, nie neu *erstellt*, deshalb reicht
   sein Log weiter zurueck als der der uebrigen Dienste) — also ein
   Speichervorgang alle 86 Minuten, exakt wie die Policy `3600 1` es vorsieht.
   Live gemessen: **1 Kommando in 10 Sekunden**.

### Gefixt: `set_state` liess das `error`-Feld stehen

`core/supa.py:set_state()` schrieb `error` nur, wenn ein Fehler uebergeben wurde
(`if error is not None`). Bei Erfolg blieb die alte Meldung im Datensatz. Fall
`fcaa7933` stand deshalb in `review`, hatte eine Tonspur — und trug die
429-Meldung vom 30.07. weiter, was im Leitstand ein ⚠ ohne Anlass erzeugte.

Jetzt wird `error` **immer** mitgeschrieben, ohne Angabe also auf NULL gesetzt.
Alle Aufrufer ohne `error=` sind Erfolgspfade (geprueft in tts/render/publish).
Damit ist der alte TODO „Worker leeren error-Feld nicht bei Erfolg" erledigt —
er war nicht kosmetisch, sondern erzeugte Fehlalarme.

### Aufgeraeumt

- **Zwei Faelle** hingen seit dem 30.07. in `in_analyse` (Glinde Score 90,
  Kreis Bergstrasse Score 75) — Spec fertig, nur die Vertonung fehlte wegen der
  Gemini-Tagesquote. Neu eingereiht, beide in ~48 s durchgelaufen, jetzt in
  `review` mit Tonspur und leerem `error`-Feld.
- **Drei veraltete Eintraege** in der `FailedJobRegistry` der tts-Queue
  entfernt (einer davon gegenstandslos, sein Fall war laengst weitergelaufen).
  Alle sechs Queues jetzt komplett leer.
- **Build-Cache**: 8,11 GB → 1,01 GB, **7,1 GB zurueckgeholt** (`docker builder
  prune`). Die Images selbst sind nur 1,07 GB.

### Neu: `.dockerignore`

Der Build-Kontext war **259 MB**, allein 38 Sekunden reines Uebertragen bei
jedem Bau. Groesster Posten: `assets/master` (173 MB Videomaterial) und
`sam2.1_t.pt` (75 MB, das SAM-Modell der Host-Werkzeuge).

**Bauzeit ~60 s → 9 s.**

Zwei Dinge dabei beachten:
- **`assets/` darf NICHT komplett ausgeschlossen werden** — das Dockerfile
  kopiert `assets/fonts/Oswald-Bold.ttf` explizit, der Bau braeche. Deshalb
  gezielt nur `assets/master/`.
- **`.env` ist jetzt ausgeschlossen.** Sie wurde bisher von `COPY . .` ins Image
  kopiert, obwohl compose sie zur Laufzeit per `env_file` reicht und der Code
  ausschliesslich `os.environ` liest (geprueft). Fuer ein Image, das auf den
  VPS soll, ist das der wichtigere Teil der Aenderung.

## ⚠️ Gemini-TTS: 100 Anfragen pro Tag (2026-07-30 aufgelaufen)

Beim Testen erschöpft: `generate_requests_per_model_per_day, limit: 100,
model: gemini-2.5-flash-tts` → 429 RESOURCE_EXHAUSTED, Reset nach ~3 h.
**Die Billing-Notiz vom 26.07. ist damit unvollständig:** Das 3/Min- und das
10/Tag-Limit des Gratis-Tiers sind weg, ein **Tageslimit von 100 Anfragen
bleibt**. Ein Clip = 1 Anfrage je Szene (≈ 5) → rund **20 Vertonungen pro Tag**.
Für 3 Clips/Woche reichlich; beim Iterieren am Text (jedes „neu vertonen" zählt
voll) ist es schnell weg. Bei Bedarf `TTS_BACKEND=edge` als Ausweichstimme.

## Bekannte Punkte / TODO
- ~~Gemini-TTS Gratis-Quota~~ **GELÖST (2026-07-26): Google-Billing aktiv** (5/5 Burst-Test ohne 429).
  Historie: Gratis-Tier hatte 10 Req/Tag + 3 Req/Min; `TTS_BACKEND=edge` bleibt als Notfall-Fallback.
- **B-Roll-Bibliothek unvollständig:** 5 Test-Clips (je 1/Kategorie) im Bucket; Pools in `core/script.py`
  stehen temporär auf **1** — beim Füllen der Bibliothek (3–4/Kategorie via Prompt-Generator) wieder erhöhen.
- **Ingest langsam** (~270 Dienststellen sequenziell, ~3 min) → später Threading/Limit.
- **Worker leeren `error`-Feld nicht bei Erfolg** (kosmetisch; Badge bleibt sonst stehen).
- ~~Render/Publish nie getestet~~ **GELÖST (2026-07-26): beide end-to-end verifiziert.** Offen bleibt nur der VPS-Deploy (`deploy/DEPLOY.md`).
- **Overlay-Redesign offen** (Design via Higgsfield) · **fakten-bewusster Render offen** (B-Roll ↔ Fall-Text).
- **Fotos aus Artikeln:** bewusst NICHT genutzt (Urheberrecht + PII-Risiko) — B-Roll/KI bleibt.
- Alte themenfremde Fälle (vor dem Filter) wurden auf `verworfen` gesetzt, nicht gelöscht.

## Diagnose-Schnipsel (PowerShell, mit PATH-Fix)
```powershell
# API-Guthaben/Key testen
docker compose exec -T worker-extract python -c "import os,json,urllib.request,urllib.error as e; k=os.environ['ANTHROPIC_API_KEY']; b=json.dumps({'model':'claude-haiku-4-5-20251001','max_tokens':20,'messages':[{'role':'user','content':'ok'}]}).encode(); r=urllib.request.Request('https://api.anthropic.com/v1/messages',data=b,headers={'x-api-key':k,'anthropic-version':'2023-06-01','content-type':'application/json'}); print(urllib.request.urlopen(r).read()[:120])"

# RSS-Ingest manuell einreihen
docker compose exec -T api python -c "from redis import Redis; from rq import Queue; import os; print(Queue('ingest',connection=Redis.from_url(os.environ['REDIS_URL'])).enqueue('workers.ingest.ingest','rss').id)"

# Analyse für einen Fall neu einreihen
docker compose exec -T api python -c "from redis import Redis; from rq import Queue; import os; print(Queue('extract',connection=Redis.from_url(os.environ['REDIS_URL'])).enqueue('workers.extract.extract','<CASE_ID>').id)"
```
