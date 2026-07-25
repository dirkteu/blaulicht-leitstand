-- Blaulicht-Leitstand — Titel-Vorparser: Ort + Tat schon beim Ingest
-- Beide Spalten sind reine Vorab-Info aus der Schlagzeile (core/parse.py),
-- kein Claude. Leer ("") = im Titel nichts gefunden -> normale Analyse fuellt.

alter table blaulicht.cases add column if not exists ort text not null default '';
alter table blaulicht.cases add column if not exists tat text not null default '';
