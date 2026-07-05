-- infra/supabase/migrations/006_chat_drop_user_fk.sql
-- Permite Chat Session sin fila en auth.users (dev local contra Supabase, AUTH_ENABLED=false).
-- En producción con login, RLS sigue limitando por auth.uid() = user_id.

ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_user_id_fkey;
ALTER TABLE operator_settings DROP CONSTRAINT IF EXISTS operator_settings_user_id_fkey;
