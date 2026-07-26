-- infra/store/init/015_operator_settings.sql
-- Preferencias del Operator (local Docker). En Supabase: 002_operator_data.sql.

CREATE TABLE IF NOT EXISTS operator_settings (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    settings   JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_operator_settings_user
    ON operator_settings (user_id);
