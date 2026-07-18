-- infra/supabase/migrations/009_ticker_dossier_versions.sql
-- Versiones persistentes de Dossier por Operator + Ticker (UUID + RLS).
--
-- Si ticker_dossier_versions ya existe con user_id TEXT (p. ej. por infra/store/init/009
-- aplicada contra Supabase), se convierte a UUID antes de crear la policy.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'ticker_dossier_versions'
      AND column_name = 'user_id'
      AND udt_name = 'text'
  ) THEN
    ALTER TABLE ticker_dossier_versions DROP CONSTRAINT IF EXISTS ticker_dossier_versions_user_id_fkey;
    ALTER TABLE ticker_dossier_versions
      ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS ticker_dossier_versions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol     TEXT NOT NULL,
    content    JSONB NOT NULL,
    citations  JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticker_dossier_versions_user_symbol_created
    ON ticker_dossier_versions (user_id, symbol, created_at DESC);

ALTER TABLE ticker_dossier_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ticker_dossier_own ON ticker_dossier_versions;
CREATE POLICY ticker_dossier_own ON ticker_dossier_versions
    FOR ALL USING (auth.uid() = user_id);
