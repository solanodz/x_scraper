-- infra/supabase/migrations/008_ticker_watch_drop_user_fk.sql
-- Permite Ticker Watch sin fila en auth.users (dev local contra Supabase, AUTH_ENABLED=false).
-- En producción con login, RLS sigue limitando por auth.uid() = user_id.

ALTER TABLE ticker_watch DROP CONSTRAINT IF EXISTS ticker_watch_user_id_fkey;
