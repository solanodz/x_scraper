-- infra/store/init/003_signals_multisource.sql
-- Additive migration (ADR-0004): generalize signals for multi-source Corpus.
-- All new columns are nullable or have safe defaults; existing X rows are preserved.
-- Run after 002_signals.sql on local Docker Store.

ALTER TABLE signals ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'x';
ALTER TABLE signals ADD COLUMN IF NOT EXISTS canonical_url TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS tickers TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE signals ADD COLUMN IF NOT EXISTS sentiment TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS topic TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS relevance_score REAL;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS cluster_id TEXT;

-- Backfill legacy rows (no-op when DEFAULT already applied)
UPDATE signals SET source_type = 'x' WHERE source_type IS NULL;

CREATE INDEX IF NOT EXISTS idx_signals_source_type ON signals (source_type);
CREATE INDEX IF NOT EXISTS idx_signals_tickers ON signals USING GIN (tickers);
CREATE INDEX IF NOT EXISTS idx_signals_cluster_id ON signals (cluster_id) WHERE cluster_id IS NOT NULL;
