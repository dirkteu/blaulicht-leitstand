# Blaulicht-Leitstand

Automatisierte True-Crime-Clip-Produktion aus Polizei-Pressemeldungen, mit
menschlicher Freigabe an jeder Schaltstelle. Containerisierte Microservices.

> **Status: 🟢 LIVE** (Stand 25.07.2026) — voller Durchlauf Ingest → Fakten → Skript → Stimme → Review erfolgreich.
> Betrieb/Runbook: [`BETRIEB.md`](BETRIEB.md) · UI: http://localhost:8000 (Login-Passwort `blaulicht`).

- 📋 Pflichtenheft: Google-Doc im Drive-Ordner „Blaulicht – True-Crime Business"
- 🛠️ Umsetzung: [`UMSETZUNG.md`](UMSETZUNG.md) · Betrieb & Änderungshistorie: [`BETRIEB.md`](BETRIEB.md)

## Zwei Quellen — thematisch auf **Zigaretten** eingegrenzt
- **`rss`** — Presseportal-Feeds (~270 Polizei-Dienststellen).
- **`mail`** — **Google-Alert-Mails** (`googlealerts-noreply@google.com`): Redirect-Links werden ausgepackt,
  je Mail mehrere Treffer, Volltext generisch geholt.
- Beide Quellen laufen durch **dieselbe** Pipeline in **dieselbe** Tabelle `blaulicht.cases`
  (nur `source` unterscheidet sie) → identische `Facts` über dieselbe Claude-Extraktion.
- **Themenfilter** (in [`.env`](.env.example), zentral in `workers/ingest.py`): `ALERT_SUBJECT_FILTER`
  (Betreff), `ALERT_TOPIC_KEYWORDS` (Titel, gilt für rss + mail), `ALERT_MAX_AGE_DAYS` (nur letzte N Tage),
  plus Score-Bonus `🚬 Zigarettenautomat` in `core/scoring.py`. Leere Filter = alle Themen.
- In der Dashboard-Tabelle zeigt die Spalte **Quelle** je Fall ein RSS- bzw. Google-Symbol.

## Struktur
```
core/        gemeinsame Logik + Contracts (contracts.py = Verträge für alle Teams)
api/         FastAPI + HTMX (Leitstand-UI, Orchestrierung)      [Team 1]
workers/     ingest · extract · script · tts · render · publish  [Team 2–5]
scheduler/   2×/Tag Auto-Ingest                                  [Team 2]
supabase/    migrations/ (Schema blaulicht + RLS)                [Team 0]
Dockerfile · docker-compose.yml · requirements.txt · .env.example
```

## Start (Dev)
```bash
cp .env.example .env      # Keys eintragen
docker compose up --build
# UI: http://localhost:8000
```

## Regeln (nicht verhandelbar)
- **Datenschutz:** Ort nur Stadt-Ebene; nie Namen/Straße/PLZ/Koordinaten (`core.contracts.Facts`, `sanitize()`).
- **Datensicherheit:** B-Roll-Master liegen NUR im Storage-Bucket `broll`; `render` liest Kopien, schreibt nie.
- **Freigaben:** Produktion & Veröffentlichung nur nach Klick — nie automatisch.

## Contracts
Alle Services bauen gegen `core/contracts.py` (State-Enum, Queues, Job, Facts, Case, Buckets).
Ändert Team 0 dort etwas, betrifft es alle — Änderungen bewusst und abgestimmt.
