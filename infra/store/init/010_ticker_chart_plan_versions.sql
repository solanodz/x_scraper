-- infra/store/init/010_ticker_chart_plan_versions.sql
-- Versiones persistentes de Chart Plan por Operator + Ticker (local, sin auth.users FK).
-- En Supabase: infra/supabase/migrations/010_ticker_chart_plan_versions.sql (UUID + RLS).

CREATE TABLE IF NOT EXISTS ticker_chart_plan_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    content             JSONB NOT NULL,
    dossier_version_id  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticker_chart_plan_versions_user_symbol_created
    ON ticker_chart_plan_versions (user_id, symbol, created_at DESC);
