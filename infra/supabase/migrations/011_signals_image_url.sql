-- infra/supabase/migrations/011_signals_image_url.sql
-- Additive: optional hero image URL (hotlink) on Signals for Signal Detail.

ALTER TABLE signals ADD COLUMN IF NOT EXISTS image_url TEXT;
