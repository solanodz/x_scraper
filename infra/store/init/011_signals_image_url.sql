-- infra/store/init/011_signals_image_url.sql
-- Additive: optional hero image URL (hotlink) on Signals for Signal Detail.
-- Run after 010_ticker_chart_plan_versions.sql on local Docker Store.

ALTER TABLE signals ADD COLUMN IF NOT EXISTS image_url TEXT;
