-- infra/store/init/014_paper_bot.sql
-- Paper Bot: Bot Config, Positions, Fills, Events (F47 / ADR-0015).

CREATE TABLE IF NOT EXISTS bot_config (
  operator_id UUID PRIMARY KEY,
  armed BOOLEAN NOT NULL DEFAULT false,
  symbols TEXT[] NOT NULL DEFAULT '{BTC,ETH}',
  max_positions INT NOT NULL DEFAULT 2
    CHECK (max_positions >= 1 AND max_positions <= 10),
  donchian_period INT NOT NULL DEFAULT 20,
  donchian_interval TEXT NOT NULL DEFAULT '30m',
  size_usd NUMERIC NOT NULL DEFAULT 1000,
  leverage NUMERIC NOT NULL DEFAULT 1,
  tp_pct NUMERIC NOT NULL DEFAULT 2,
  sl_pct NUMERIC NOT NULL DEFAULT 1,
  venue TEXT NOT NULL DEFAULT 'paper',
  cooldown_seconds INT NOT NULL DEFAULT 3600,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id UUID NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('long', 'short')),
  size_usd NUMERIC NOT NULL,
  qty NUMERIC NOT NULL,
  leverage NUMERIC NOT NULL DEFAULT 1,
  entry_price NUMERIC NOT NULL,
  tp_price NUMERIC NOT NULL,
  sl_price NUMERIC NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
  opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ,
  close_reason TEXT,
  realized_pnl NUMERIC,
  venue TEXT NOT NULL DEFAULT 'paper',
  external_id TEXT,
  mark_price NUMERIC
);

CREATE TABLE IF NOT EXISTS bot_fills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  position_id UUID NOT NULL REFERENCES bot_positions (id),
  operator_id UUID NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  price NUMERIC NOT NULL,
  qty NUMERIC NOT NULL,
  venue TEXT NOT NULL DEFAULT 'paper',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  raw JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS bot_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id UUID NOT NULL,
  kind TEXT NOT NULL,
  symbol TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bot_positions_operator_status
  ON bot_positions (operator_id, status);

CREATE INDEX IF NOT EXISTS idx_bot_events_operator_created
  ON bot_events (operator_id, created_at DESC);
