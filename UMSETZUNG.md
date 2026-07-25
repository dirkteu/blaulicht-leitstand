# Blaulicht-Leitstand — Umsetzungs-Anleitung

> Konkrete Bau-Anleitung zum [Pflichtenheft](https://docs.google.com/document/d/1fx9vNgPkCVwNiTDFyhOHZtsysvSfllXlUB66hv-qmHQ/edit).
> Plan-Datei: `~/.claude/plans/ich-habe-das-schon-melodic-simon.md`. Stand: 25.07.2026 · freigegeben.

## Grundprinzip
Aus dem CLI-Prototyp (`ranking.py`, `script_gen.py`, `tts.py`, `render.py`) wird ein containerisiertes
Web-System. **Die Rechenlogik wird wiederverwendet** (ins `core/`-Paket), nur I/O wandert von lokalen
Dateien zu Supabase (Postgres + Storage). Menschliche Freigabe an jeder Schaltstelle.

## Repo-Struktur (Ziel)
```
blaulicht/
├─ core/                     # gemeinsame Logik (aus dem Prototyp)
│   ├─ scoring.py            # Drama-Score (aus ranking.py)
│   ├─ extract.py            # Claude-API-Fakten-Extraktion (+ sanitize)
│   ├─ script.py             # spec-Bau (aus script_gen.py)
│   ├─ tts.py                # edge-tts + Aussprache-Wörterbuch/say-as
│   ├─ render.py             # Pillow-Overlays + ffmpeg-Compositing
│   ├─ presseportal.py       # RSS/Volltext (fetch_fulltext), Dienststellen
│   ├─ mail.py               # IMAP + „MELDUNG ÖFFNEN"-Regex
│   ├─ supa.py               # Supabase-Client (DB + Storage-Helper)
│   └─ contracts.py          # Job-Payloads + State-Enum (die „Verträge")
├─ api/                      # FastAPI + HTMX (Leitstand-UI)
│   ├─ main.py  templates/  static/
├─ workers/
│   ├─ ingest.py  extract.py  script.py  tts.py  render.py  publish.py
├─ scheduler/                # APScheduler → reiht 2×/Tag „ingest" ein
├─ docker-compose.yml
├─ .env.example
└─ supabase/migrations/      # Schema + RLS
```

## Zustands-Enum (`core/contracts.py`)
`neu · in_analyse · review · in_produktion · fertig · veroeffentlicht · verworfen`

## Job-Flow (RQ auf Redis)
```
scheduler ─2×/Tag→ ingest ──▶ (pro Fall in DB als „neu")
api [Freigabe Analyse] ─▶ fulltext ─▶ extract ─▶ script ─▶ tts ─▶ state=review
api [Freigabe Clip]    ─▶ render ─▶ state=fertig
api [Freigabe Veröff.] ─▶ publish ─▶ state=veroeffentlicht
```
Worker-Regel: Job ziehen → rechnen → `cases`-Zeile updaten → Folge-Job einreihen (außer an Gates).

## Datenschutz (nicht verhandelbar)
- `core/extract.py`: Prompt verbietet Namen/Straße/PLZ/Koordinaten; `sanitize(facts)` als letzte Schranke.
- Ort immer nur Stadt. Kein Geocoding.

## Datensicherheit (nach dem Datenverlust)
- B-Roll-Master **nur** in Supabase Storage (`broll`-Bucket). `render` lädt Kopien nach `/tmp` im Container,
  fasst Storage nie schreibend an. **Kein `make_stub_broll.py` im System.**

## Externe Struktur (Ingest)
```
/dienststellen → IDs   |   /rss/dienststelle_{id} → Meldungs-IDs   |   /pm/{id}/{meldung} → Volltext
Nebenachsen: /l/{bundesland} · /regional/{stadt} · /st/{thema}
```

## ENV (`.env.example`)
`ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `REDIS_URL`,
`IMAP_HOST/USER/APP_PW`, `INGEST_TIMES=07:00,19:00`, Plattform-Tokens (später).

## Bau-Reihenfolge (Agent-Teams)
1. **Team 0 (zuerst):** `core/` + `contracts.py`, Supabase-Migration (Tabellen `cases`/`broll`/`config` + RLS,
   Buckets), `docker-compose.yml` + Redis. → definiert die Verträge, an denen alle anderen bauen.
2. **Parallel:** Team 1 (api/UI, videowachmann-Design), Team 2 (ingest+scheduler), Team 3 (extract+script),
   Team 4 (tts+render), Team 5 (publish+deploy). Jeder Service mit Dockerfile + Unit-Tests.
3. **Integrator:** compose verdrahten, End-to-End über alle Gates testen.
4. **Deploy:** IONOS-VPS, `docker compose up -d`, Subdomain hinter Plesk/nginx.

## Lokaler Start (Dev)
```bash
cp .env.example .env   # Keys eintragen
docker compose up --build
# Browser: http://localhost:8000
```

## Abnahme (Kurzform)
Ingest RSS → Tabelle · Freigabe Analyse → Fakten+Skript+Audio · Text ändern+neu vertonen ·
Freigabe Clip → Video mit Daten-Overlays · Datenschutz-Check · Deploy + Zugriff von 2. Gerät.

## Offene Defaults
Queue RQ/Redis · Ingest 07:00 & 19:00 · Veröffentlichung zuerst manueller Download.
