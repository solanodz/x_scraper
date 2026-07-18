-- infra/supabase/migrations/010_ticker_chart_plan_versions.sql
-- Versiones persistentes de Chart Plan por Operator + Ticker (UUID + RLS).
--
-- Si ticker_chart_plan_versions ya existe con user_id TEXT (p. ej. por infra/store/init/010
-- aplicada contra Supabase), se convierte a UUID antes de crear la policy.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'ticker_chart_plan_versions'
      AND column_name = 'user_id'
      AND udt_name = 'text'
  ) THEN
    ALTER TABLE ticker_chart_plan_versions DROP CONSTRAINT IF EXISTS ticker_chart_plan_versions_user_id_fkey;
    ALTER TABLE ticker_chart_plan_versions
      ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS ticker_chart_plan_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol              TEXT NOT NULL,
    content             JSONB NOT NULL,
    dossier_version_id  UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticker_chart_plan_versions_user_symbol_created
    ON ticker_chart_plan_versions (user_id, symbol, created_at DESC);

ALTER TABLE ticker_chart_plan_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ticker_chart_plan_own ON ticker_chart_plan_versions;
CREATE POLICY ticker_chart_plan_own ON ticker_chart_plan_versions
    FOR ALL USING (auth.uid() = user_id);
