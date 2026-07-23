-- infra/store/init/012_chat_messages_artifacts.sql
-- Additive: structured chat artifacts (e.g. price_chart) on assistant messages.
-- Run after 011_signals_image_url.sql on local Docker Store.

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS artifacts JSONB;
