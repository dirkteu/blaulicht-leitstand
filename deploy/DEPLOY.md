# Blaulicht-Leitstand — Deployment auf dem IONOS-VPS

Kurz & praktisch, analog zum bewährten Vorgehen bei `admin.videowachmann.de`
(selber Server, selbes Muster: Plesk-Subdomain + nginx-Reverse-Proxy + Docker
daneben). Ziel-Subdomain hier: **`leitstand.videowachmann.de`**.

## 0. Voraussetzungen

- Server: IONOS-VPS **217.154.171.136** ("My VPS", Ubuntu 24.04), Plesk läuft
  bereits (nginx 80/443, Panel 8443) — **nicht anfassen**, nur Subdomain
  anlegen und Docker daneben betreiben (wie beim Wachmann-Admin-Deploy).
- Docker + Docker Compose Plugin auf dem Server installiert
  (`docker --version`, `docker compose version`; falls fehlt: `apt install
  docker.io docker-compose-plugin`).
- Kein GitHub-Zugang auf dem Server (private Repos) → Code kommt per
  **git bundle + scp**, genau wie beim Wachmann-Admin-Deploy.

## 1. Subdomain in Plesk anlegen

Plesk-Panel → Domains → Subdomain hinzufügen → `leitstand.videowachmann.de`
(unter der bestehenden `videowachmann.de`-Domain, DNS liegt schon im
Plesk-DNS des Servers, kein externer DNS-Eintrag nötig). Let's-Encrypt-SSL
in Plesk für die Subdomain aktivieren (SSL/TLS-Zertifikate → Let's Encrypt).

## 2. Code auf den Server bringen (Bundle-Methode)

Lokal (Windows, im Repo-Ordner):
```powershell
git bundle create blaulicht.bundle --all
scp blaulicht.bundle root@217.154.171.136:/opt/
```

Auf dem Server (SSH, Root-Passwort — kein Key hinterlegt):
```bash
cd /opt
git clone /opt/blaulicht.bundle blaulicht      # erster Deploy
# spätere Updates:
cd /opt/blaulicht
git pull /opt/blaulicht.bundle main            # oder Feature-Branch
```

**Diagnose-Trick (aus dem Wachmann-Admin-Vorfall gelernt):** nach jedem neuen
`scp` IMMER mit `git ls-remote /opt/blaulicht.bundle` prüfen, ob das Bundle
wirklich den erwarteten Commit enthält, BEVOR `git pull` läuft. `git pull`
muss `Updating <alt>..<neu> Fast-forward` melden — meldet es „Already up to
date", kam das neue Bundle nicht an (altes Bundle, scp fehlgeschlagen o. ä.).

## 3. `.env` auf dem Server anlegen (die 3 Secrets)

```bash
cd /opt/blaulicht
cp .env.example .env
nano .env
```

Eintragen (siehe `.env.example` — die 3 wirklich geheimen Werte, Rest ist
schon öffentlich/vorbefüllt oder Default):
- `SUPABASE_SERVICE_KEY` — service_role-Key aus dem Supabase-Dashboard
  (Projekt `ki_wn` / Blaulicht, ref `mzuyqhslpeaeoqxconzc`). **Niemals ins
  Repo committen**, `.env` ist gitignored.
- `ANTHROPIC_API_KEY` — Claude-API-Key (Fakten-Extraktion + Skript).
- `IMAP_APP_PW` — App-Passwort fürs Mail-Postfach (Google-Alert-Quelle),
  NICHT das normale Gmail-Passwort.

`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `REDIS_URL` etc. sind bereits in
`.env.example` vorbefüllt/mit sinnvollen Defaults versehen und können 1:1
übernommen werden.

## 4. Starten

```bash
cd /opt/blaulicht
docker compose up -d --build
docker compose ps          # alle Services "running"?
docker compose logs -f api # kurz mitlesen, ob FastAPI sauber hochfährt
```

Das startet `redis`, `api` (Port 8000, intern), `scheduler` und alle sechs
`worker-*`-Services (ingest/extract/script/tts/render/publish) aus dem
gemeinsamen Image. `api` bindet nur auf `127.0.0.1:8000` innerhalb des
Servers — nach außen geht nichts direkt über Docker-Ports, sondern nur über
den Plesk-nginx-Proxy (siehe unten). Falls `docker-compose.yml` `ports:
8000:8000` auf alle Interfaces bindet: in der IONOS-Firewall Port 8000
**geschlossen halten** (Zugriff nur lokal via Proxy), analog zum
Wachmann-Admin-Setup (dort war 3100 zwischenzeitlich offen und wurde wieder
geschlossen).

## 5. Reverse-Proxy einrichten

Siehe [`nginx.conf.example`](nginx.conf.example) für den fertigen Block.
Kurzfassung: Plesk-Panel → Domains → `leitstand.videowachmann.de` → Apache &
nginx-Einstellungen → „Zusätzliche nginx-Direktiven" → den `location ~ ^/`
-Block aus `nginx.conf.example` einfügen (proxy_pass auf
`http://127.0.0.1:8000`, WebSocket-Upgrade-Header für spätere Live-Updates,
großzügige Proxy-Buffer gegen 502 bei großen Cookies/Headern).

Danach:
```bash
plesk sbin httpdmng --reconfigure-domain leitstand.videowachmann.de
```

**Bei 502 Bad Gateway:** zuerst
`tail /var/www/vhosts/system/leitstand.videowachmann.de/logs/proxy_error_log`
prüfen (nicht blind neu starten). Häufigste Ursache laut Erfahrung beim
Wachmann-Admin: `upstream sent too big header` → Proxy-Buffer-Werte aus
`nginx.conf.example` fehlen oder wurden nicht übernommen.

## 6. Restart-Verhalten / einzelnen Worker neustarten

Alle Services haben `restart: unless-stopped` in `docker-compose.yml` —
überleben also Server-Reboots und Abstürze automatisch, sobald Docker selbst
beim Boot startet (`systemctl enable docker` einmalig prüfen).

Einzelnen Dienst neu starten (z. B. nach Code-Update nur den Publish-Worker):
```bash
cd /opt/blaulicht
docker compose restart worker-publish
```

Alle Worker neu starten (z. B. nach `git pull` + Rebuild):
```bash
docker compose up -d --build          # baut geändertes Image, startet nur
                                       # geänderte/neue Container neu
```

Logs eines einzelnen Dienstes verfolgen:
```bash
docker compose logs -f worker-publish
```

Kompletten Stack stoppen/starten:
```bash
docker compose down       # stoppt & entfernt Container (Redis-Daten bleiben im Volume)
docker compose up -d      # wieder hoch
```

## 7. Backup

**Kein eigenes Backup-Skript nötig** — die einzige nennenswerte
Zustandsdatenquelle ist Supabase (Postgres + Storage), und das ist ein
**managed Service** mit eigenem automatischem Backup (Supabase-Dashboard →
Project Settings → Backups, tägliche Point-in-Time-Snapshots je nach Plan).

Was wirklich lokal auf dem Server liegt und NICHT in Supabase ist:
- `.env` (Secrets) — manuell sichern (Passwort-Manager / verschlüsselte
  Kopie), nicht ins Repo.
- Das Redis-Volume (`redis-data`) — enthält nur die RQ-Job-Queue
  (transiente Warteschlange), kein Datenverlust-Risiko im eigentlichen
  Sinn: verlorene Jobs zeigen sich einfach als Fälle, die im Zustand
  „hängen" bleiben und über die UI erneut angestoßen werden können.

B-Roll-Master, Voice, Renders, Thumbs liegen ausschließlich in
Supabase-Storage-Buckets (`broll`/`voice`/`renders`/`thumbs`) — nicht auf
dem VPS-Dateisystem. Der Datenverlust-Vorfall vom 2026-07-25 (lokale
`broll_*.mp4` überschrieben) betrifft dieses Deployment also nicht: Team 0
hat das bewusst so gebaut, dass `render` den `broll`-Bucket nur liest.

## 8. Kurz-Checkliste für einen frischen Deploy

1. Subdomain `leitstand.videowachmann.de` in Plesk + Let's-Encrypt-SSL
2. `git bundle` → `scp` → `git clone`/`git pull` auf dem Server (`/opt/blaulicht`)
3. `.env` mit den 3 Secrets füllen
4. `docker compose up -d --build`
5. nginx-Block aus `nginx.conf.example` in Plesk eintragen + `httpdmng --reconfigure-domain`
6. Firewall: Port 8000 NICHT extern offen lassen
7. Aufruf prüfen: `https://leitstand.videowachmann.de`
