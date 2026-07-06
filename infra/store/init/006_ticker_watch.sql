-- infra/store/init/006_ticker_watch.sql
-- Lista personal de tickers por Operator (local, sin auth.users FK).
-- En Supabase: infra/supabase/migrations/007_ticker_watch.sql (UUID + RLS).

CREATE TABLE IF NOT EXISTS ticker_watch (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    note       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_ticker_watch_user ON ticker_watch (user_id, created_at);
