# Betriebshandbuch — Blaulicht-Leitstand

**Status (2026-07-25): 🟢 LIVE — erster voller Durchlauf erfolgreich.**
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

## Bekannte Punkte / TODO
- **B-Roll-Bucket leer** → Render nutzt Farb-Kulissen, bis echte Higgsfield-Clips über die
  `/broll`-Seite hochgeladen sind (gleiche Namen `broll_<kategorie>_NN.mp4`).
- **Ingest langsam** (~270 Dienststellen sequenziell, ~3 min) → später Threading/Limit.
- **Worker leeren `error`-Feld nicht bei Erfolg** (kosmetisch; Badge bleibt sonst stehen).
- **Noch nicht durchgetestet:** Render („Clip bauen"), Publish, VPS-Deploy (`deploy/DEPLOY.md`).
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
