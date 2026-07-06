-- infra/supabase/migrations/007_ticker_watch.sql
-- Lista personal de tickers por Operator (UUID + RLS).
--
-- Si ticker_watch ya existe con user_id TEXT (p. ej. por infra/store/init/006
-- aplicada contra Supabase), se convierte a UUID antes de crear la policy.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'ticker_watch'
      AND column_name = 'user_id'
      AND udt_name = 'text'
  ) THEN
    ALTER TABLE ticker_watch DROP CONSTRAINT IF EXISTS ticker_watch_user_id_fkey;
    ALTER TABLE ticker_watch
      ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS ticker_watch (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol     TEXT NOT NULL,
    note       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_ticker_watch_user ON ticker_watch (user_id, created_at);

ALTER TABLE ticker_watch ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ticker_watch_own ON ticker_watch;
CREATE POLICY ticker_watch_own ON ticker_watch
    FOR ALL USING (auth.uid() = user_id);
