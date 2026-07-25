-- Blaulicht-Leitstand — Halluzinations-Check: Warnung, wenn Claudes Ort aus dem
-- Volltext dem beim Ingest aus dem Titel geparsten Ort widerspricht.
-- "" = keine Warnung. Wird in der extract-Stufe gesetzt (workers/extract.py).

alter table blaulicht.cases add column if not exists warnung text not null default '';
