-- Blaulicht-Leitstand — Grundschema (eigenes Schema, kollisionsfrei zu ki_wn)

create schema if not exists blaulicht;

-- Fälle: die Zustandsmaschine
create table if not exists blaulicht.cases (
  id            uuid primary key default gen_random_uuid(),
  source        text not null default 'rss',
  region        text not null default '',
  title         text not null default '',
  link          text not null default '',
  score         int  not null default 0,
  hits          text[] not null default '{}',
  state         text not null default 'neu',
  fulltext      text,
  facts         jsonb,
  spec          jsonb,
  voice_url     text,
  video_url     text,
  thumb_url     text,
  error         text,
  platform_ids  jsonb not null default '{}',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  published_at  timestamptz
);
create index if not exists cases_state_idx on blaulicht.cases(state);
create index if not exists cases_score_idx on blaulicht.cases(score desc);
create unique index if not exists cases_link_uidx on blaulicht.cases(link) where link <> '';

-- B-Roll-Bibliothek (Metadaten; Dateien liegen in Storage-Bucket 'broll')
create table if not exists blaulicht.broll (
  id           uuid primary key default gen_random_uuid(),
  kategorie    text not null,
  filename     text not null unique,
  storage_path text not null,
  uploaded_at  timestamptz not null default now()
);

-- Einstellungen (Singleton)
create table if not exists blaulicht.config (
  id           int primary key default 1,
  min_score    int  not null default 40,
  ingest_times text not null default '07:00,19:00',
  aussprache   jsonb not null default '{}',
  updated_at   timestamptz not null default now(),
  constraint config_singleton check (id = 1)
);
insert into blaulicht.config (id) values (1) on conflict (id) do nothing;

-- updated_at automatisch pflegen
create or replace function blaulicht.touch_updated_at() returns trigger as $$
begin new.updated_at = now(); return new; end;
$$ language plpgsql;

drop trigger if exists cases_touch on blaulicht.cases;
create trigger cases_touch before update on blaulicht.cases
  for each row execute function blaulicht.touch_updated_at();

-- Row Level Security: nur authentifizierte Nutzer (service_role umgeht RLS ohnehin)
alter table blaulicht.cases  enable row level security;
alter table blaulicht.broll  enable row level security;
alter table blaulicht.config enable row level security;

drop policy if exists cases_auth  on blaulicht.cases;
drop policy if exists broll_auth  on blaulicht.broll;
drop policy if exists config_auth on blaulicht.config;
create policy cases_auth  on blaulicht.cases  for all to authenticated using (true) with check (true);
create policy broll_auth  on blaulicht.broll  for all to authenticated using (true) with check (true);
create policy config_auth on blaulicht.config for all to authenticated using (true) with check (true);
