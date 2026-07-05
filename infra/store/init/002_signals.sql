-- Corpus: Signals persistidos por Ingestion (dedup por id_str).
CREATE TABLE IF NOT EXISTS signals (
    id_str           TEXT PRIMARY KEY,
    published_at     TIMESTAMPTZ NOT NULL,
    username         TEXT NOT NULL,
    raw_content      TEXT NOT NULL,
    source           TEXT NOT NULL,
    cashtags         TEXT[] NOT NULL DEFAULT '{}',
    hashtags         TEXT[] NOT NULL DEFAULT '{}',
    article          JSONB,
    reply_count      INTEGER NOT NULL DEFAULT 0,
    retweet_count    INTEGER NOT NULL DEFAULT 0,
    like_count       INTEGER NOT NULL DEFAULT 0,
    quote_count      INTEGER NOT NULL DEFAULT 0,
    bookmarked_count INTEGER NOT NULL DEFAULT 0,
    payload          JSONB NOT NULL,
    embedding        vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_signals_published_at ON signals (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_cashtags ON signals USING GIN (cashtags);
