-- infra/supabase/migrations/012_chat_messages_artifacts.sql
-- Additive: structured chat artifacts (e.g. price_chart) on assistant messages.

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS artifacts JSONB;
