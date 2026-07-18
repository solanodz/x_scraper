-- infra/store/init/009_ticker_dossier_versions.sql
-- Versiones persistentes de Dossier por Operator + Ticker (local, sin auth.users FK).
-- En Supabase: infra/supabase/migrations/009_ticker_dossier_versions.sql (UUID + RLS).

CREATE TABLE IF NOT EXISTS ticker_dossier_versions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    content    JSONB NOT NULL,
    citations  JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticker_dossier_versions_user_symbol_created
    ON ticker_dossier_versions (user_id, symbol, created_at DESC);
