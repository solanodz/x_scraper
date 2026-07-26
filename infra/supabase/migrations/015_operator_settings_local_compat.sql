-- infra/supabase/migrations/015_operator_settings_local_compat.sql
-- operator_settings ya existe desde 002_operator_data.sql.
-- Esta migración es no-op documentada para alinear numeración con store/015.
-- Si la tabla faltara (entorno raro), la recreamos compatible con TEXT user_id
-- post-006 (FK drop). En prod normal: IF NOT EXISTS no cambia nada.

CREATE TABLE IF NOT EXISTS operator_settings (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    settings   JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_operator_settings_user
    ON operator_settings (user_id);
