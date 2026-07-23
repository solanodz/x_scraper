# Paper Bot (BTC/ETH) — Hyperliquid-ready — Design

**Date:** 2026-07-23  
**Status:** Draft for review  
**ADR:** ADR-0015 (to be written at implementation)  
**Related:** Market Data, Ticker Chart (Donchian on FE today), Railway deploy (API + Worker + **Trader**)

## Goal

Always-on **Paper Bot** that autonomously opens/closes long and short positions on **BTC and ETH** from a deterministic **Donchian Breakout** strategy, manages **TP/SL** in the background, and exposes Operator config + status in the Terminal. Execution goes through an **Execution Venue** port: **`PaperVenue` now**, **`HyperliquidVenue` stub** for a future live path. This is **not investment advice**; paper fills ≠ real exchange fills.

## Non-goals (MVP)

- Live Hyperliquid trading or storing private keys in MVP
- LLM / Chart Agent deciding entries (Strategy is deterministic)
- Manual “market order” UI beyond close-position and arm/pause
- Fancy equity curve / multi-strategy marketplace
- Real liquidation / funding-rate engine
- Tickers beyond BTC and ETH
- More than **10** simultaneous open positions (hard cap)

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Mode | Always-on bot (armed/paused), not one-click-per-signal |
| Money | Paper fills now; venue contract ready for Hyperliquid |
| Sides | Long and short |
| Universe | BTC + ETH |
| Entry | Donchian breakout + filters (cooldown; respect max positions) |
| Risk | Operator-configurable size, leverage, TP, SL (defaults; per-position fields stored) |
| Concurrency | Up to **10** open positions (Operator sets 1–10) |
| Runtime | Dedicated Railway service **`xscraper-trader`** (not API lifespan, not ingest worker) |
| Architecture | Strategy engine + Risk Policy + Execution Venue adapters |

## Domain (canonical terms)

Add to `CONTEXT.md` at implementation:

- **Paper Bot** — Always-on process that trades an allowed universe under a Strategy + Risk Policy via an Execution Venue.
- **Strategy** — Deterministic entry/exit rules. MVP: **Donchian Breakout**.
- **Risk Policy** — Size (notional or qty), leverage, take-profit, stop-loss. MVP: Operator config (static). Later: may incorporate Corpus sentiment / other variables without changing the Venue port.
- **Trade Signal** — Internal entry event `{symbol, side, reason, bar_ts, meta}`. **Not** a Corpus Signal.
- **Position** — Open or closed paper/live position with entry, size, leverage, TP, SL, PnL.
- **Fill** — Execution record from a Venue.
- **Execution Venue** — Port for open/close/marks. Implementations: `PaperVenue`, `HyperliquidVenue` (stub).
- **Bot Config** — Armed flag, symbols, max positions, Donchian params, risk defaults, active venue.

Avoid: “algo trading tip”, “signal tip” as synonyms for Trade Signal; do not call paper fills “on-chain”.

## Strategy (MVP)

**Donchian Breakout** (per symbol):

- Compute Donchian upper/lower over configurable period on a configurable OHLC interval (defaults aligned with chart: e.g. period 20, interval `1h` or `4h` — exact defaults in plan).
- **Long entry:** close (or high) breaks above upper band; no duplicate open for same symbol+side while one exists (policy: at most one open position per symbol+side unless config says otherwise — **MVP: at most one open position per symbol** to keep risk simple, while total open across BTC+ETH ≤ max_positions).
- **Short entry:** close (or low) breaks below lower band.
- **Filters:** cooldown after close for that symbol; skip if at `max_positions`; skip if bot paused/disarmed; skip duplicate bar signal (idempotent on `symbol+side+bar_ts`).
- **Exit:** TP or SL hit on mark (PaperVenue mark = Market Data last/close); optional Operator forced close via API.

Backend must compute Donchian (today it exists only in `frontend/src/lib/chartIndicators.ts`).

## Risk Policy (MVP)

Operator configures via API/UI:

- `max_positions` ∈ [1, 10]
- Default **size** (notional USD *or* qty — pick one primary in plan; store both fields if needed for Hyperliquid later)
- Default **leverage**
- Default **TP** and **SL** (percent from entry *or* absolute price — MVP: **percent** for simplicity; store resolved absolute levels on the Position at open)
- Per-symbol enable flags within `{BTC, ETH}`

Later (explicitly deferred): TP/SL/size modulated by Corpus sentiment and other variables — same Risk Policy interface, new inputs.

## Execution Venue

```text
open(symbol, side, size, leverage, tp, sl, meta) → Fill + Position
close(position_id, reason) → Fill
get_mark_price(symbol) → Decimal
list_open_positions() → list  # optional sync helper for live venue
```

- **`PaperVenue`:** fill at mark; persist Position/Fill; no slippage model in MVP (column reserved).
- **`HyperliquidVenue`:** same signatures; raises `VenueNotEnabled` / returns clear error until secrets + live ADR; no partial live behavior in MVP.
- Env: `BOT_VENUE=paper` (default). Setting `hyperliquid` without credentials must fail closed (bot stays paused or refuses opens).

## Trader loop (`xscraper-trader`)

Interval: `BOT_TICK_SECONDS` (default ~30s).

Each tick:

1. Load Bot Config for the Operator (MVP: single-operator deploy, same as rest of product).
2. If not armed → record heartbeat / idle; manage nothing new (still may MTM open positions if we want TP/SL while “paused” — **decision: paused = no new entries; still manage TP/SL on open positions** so risk is not abandoned).
3. For each enabled symbol: fetch OHLC → Donchian → Trade Signals.
4. For each open Position: refresh mark → if TP/SL hit → `venue.close`.
5. For each Trade Signal: if under caps/filters → apply Risk Policy → `venue.open`.
6. Append `bot_events` for signals, skips, opens, closes, errors.

Process start command (Railway): e.g. `python -m backend.scripts.run_paper_bot` (name finalized in plan).

## Store

Migrations (supabase + store/init twins):

- **`bot_config`** — operator_id PK/unique, armed, symbols[], max_positions, donchian_period, donchian_interval, size, leverage, tp_pct, sl_pct, venue, updated_at
- **`bot_positions`** — id, operator_id, symbol, side, size, leverage, entry_price, tp_price, sl_price, status (`open`|`closed`), opened_at, closed_at, close_reason, realized_pnl, venue, external_id nullable (HL)
- **`bot_fills`** — id, position_id, operator_id, symbol, side, price, qty, venue, created_at, raw jsonb
- **`bot_events`** — id, operator_id, kind, symbol nullable, payload jsonb, created_at

Indexes: open positions by operator; events by created_at.

## API (authenticated)

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/bot/config` | Current config |
| PATCH | `/bot/config` | Update armed, symbols, max_positions, risk, donchian, venue=`paper` only in MVP |
| GET | `/bot/positions` | Filter `status=open\|closed` |
| POST | `/bot/positions/{id}/close` | Manual close via active Venue |
| GET | `/bot/fills` | Recent fills |
| GET | `/bot/events` | Audit trail |

No public unauthenticated bot endpoints.

## UI

- Route **`/bot`** in Terminal nav (alongside terminal / research / dossier).
- Armed/Paused toggle; config form; open positions table; recent fills/events.
- Clear **Paper** badge; Hyperliquid shown as “ready / off”.
- Disclaimer: simulated trading; not investment advice.

## Flags / env

| Var | Default | Notes |
|-----|---------|-------|
| `BOT_ENABLED` | `false` | Trader process no-ops if false |
| `BOT_TICK_SECONDS` | `30` | Loop interval |
| `BOT_VENUE` | `paper` | `hyperliquid` rejected without creds |
| Future HL secrets | — | Documented in ADR-0015; not required for MVP |

## Deploy

- Railway service **`xscraper-trader`**: same Docker image as API/Worker; different start command.
- API remains source of config/read models; trader is the only writer of autonomous opens (API may write config + manual close).

## Verification (definition of done sketch)

1. With `BOT_ENABLED=true`, `BOT_VENUE=paper`, armed config for BTC: synthetic/fixture Donchian breakout opens ≤1 position per symbol and respects max_positions.
2. Mark moved through TP/SL closes position and writes Fill + event.
3. Paused: no new opens; existing positions still TP/SL-managed.
4. `HyperliquidVenue.open` fails closed when venue flag/credentials missing.
5. Frontend `/bot` shows config + open position after paper open (verify script + build).
6. `./init.sh` / targeted `verify_fXX` green.

## Open points (resolve in implementation plan, not blockers)

1. Primary size unit: **USD notional** vs base qty (lean: USD notional for paper UX).
2. Default OHLC interval for Donchian (lean: `1h`, period `20`).
3. Exact “one position per symbol” vs multiple same-symbol — **MVP lean: one open position per symbol**, total ≤ max_positions across universe.
4. Whether Research Chat may *display* bot state (out of scope unless trivial read).

## Implementation order (high level)

1. ADR-0015 + CONTEXT terms + feature_list entries  
2. Migrations + repos  
3. Donchian + Strategy + PaperVenue + loop script  
4. API routes  
5. `/bot` UI  
6. Railway service docs + verify scripts  
7. Hyperliquid stub only (no live)

---

**Review checklist for Operator:** universe BTC+ETH, max 10, configurable size/leverage/TP/SL, always-on Donchian, paper + HL port, separate trader service, `/bot` UI.
