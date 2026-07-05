-- infra/supabase/migrations/002_operator_data.sql
-- Datos del Operator (por usuario). Ejecutar después de 001_init.sql.
-- Corpus (signals) es compartido; estas tablas son preferencias e historial.

-- Preferencias: watchlist, filtros UI, layout, etc.
CREATE TABLE IF NOT EXISTS operator_settings (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    settings   JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

-- Sesiones de Research Chat
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions (user_id, created_at DESC);

-- Mensajes con Citations serializadas en JSONB
CREATE TABLE IF NOT EXISTS chat_messages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content      TEXT NOT NULL,
    citations    JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages (session_id, created_at);

-- RLS: cada Operator solo ve sus filas
ALTER TABLE operator_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY operator_settings_own ON operator_settings
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY chat_sessions_own ON chat_sessions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY chat_messages_own ON chat_messages
    FOR ALL USING (
        session_id IN (SELECT id FROM chat_sessions WHERE user_id = auth.uid())
    );

-- signals: sin RLS en MVP (Operator único; API/Worker usan connection string con permisos de escritura)
