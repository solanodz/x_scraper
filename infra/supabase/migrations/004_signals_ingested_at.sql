-- infra/supabase/migrations/004_signals_ingested_at.sql
-- Additive migration (ADR-0005): ingested_at for observability; retention uses published_at.

ALTER TABLE signals ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_signals_ingested_at ON signals (ingested_at DESC);
