# Paper Bot (BTC/ETH) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Always-on Paper Bot for BTC/ETH with Donchian entries, TP/SL management, PaperVenue + Hyperliquid stub, Railway trader service, and `/bot` UI.

**Architecture:** Strategy + Risk Policy + ExecutionVenue port; `xscraper-trader` loop writes positions/fills; API exposes config/status; FE `/bot` for Operator control.

**Tech Stack:** FastAPI, Postgres/Supabase, Next.js, existing Market Data (`get_price_history` / quotes), Railway.

**Spec:** `docs/superpowers/specs/2026-07-23-paper-bot-hyperliquid-ready-design.md`

## Global Constraints

- Canonical terms from CONTEXT / spec (Paper Bot, Trade Signal ≠ Corpus Signal, Execution Venue).
- Universe MVP: BTC + ETH only; max_positions 1–10; one open position per symbol.
- Size = USD notional; TP/SL = percent → absolute prices stored on open.
- Donchian defaults: period 20, interval `1h`.
- `BOT_VENUE=paper` default; Hyperliquid stub fail-closed.
- Paused/disarmed: no new entries; still manage TP/SL on open positions.
- Single Operator id pattern used elsewhere (`00000000-0000-0000-0000-000000000001` when auth off).
- No live HL keys; no LLM entries; no commits unless asked.

## Resolved leans

- USD notional primary size
- Donchian `1h` / period `20`
- One open position per symbol; total ≤ max_positions

---

## Task 1: Docs + migrations + repo

**Files:**
- Create `docs/adr/0015-paper-bot-execution-venue.md`
- Update `CONTEXT.md` (Paper Bot terms)
- Create `infra/store/init/014_paper_bot.sql` + `infra/supabase/migrations/014_paper_bot.sql`
- Create `backend/app/services/bot_repo.py`
- Update `.env.example` (`BOT_ENABLED`, `BOT_TICK_SECONDS`, `BOT_VENUE`)
- Update `feature_list.json` F47 in_progress; `progress.md`
- Update `docs/deploy/railway.md` (xscraper-trader start command)

**Tables:** `bot_config`, `bot_positions`, `bot_fills`, `bot_events` per spec.

**Verify:** SQL applies / py_compile bot_repo.

---

## Task 2: Strategy + venues + trader loop

**Files:**
- `backend/services/donchian.py` — pure Donchian from OHLC list
- `backend/services/bot_strategy.py` — DonchianBreakout signals + filters
- `backend/services/bot_venue.py` — Protocol + PaperVenue + HyperliquidVenue stub
- `backend/services/paper_bot.py` — one tick orchestration
- `backend/scripts/run_paper_bot.py` — loop (`BOT_ENABLED`, sleep `BOT_TICK_SECONDS`)
- `backend/scripts/verify_f47_paper_bot.py` — fixture breakout open + TP close + HL stub fail

**Verify:** `python -m backend.scripts.verify_f47_paper_bot`

---

## Task 3: API routes

**Files:**
- `backend/app/routes/bot.py`
- `backend/app/schemas.py` (BotConfig, Position, Fill, Event models)
- `backend/app/main.py` include router

**Endpoints:** GET/PATCH `/bot/config`, GET `/bot/positions`, POST `/bot/positions/{id}/close`, GET `/bot/fills`, GET `/bot/events`

**Verify:** TestClient or verify script hits with AUTH_ENABLED=false.

---

## Task 4: Frontend `/bot`

**Files:**
- `frontend/src/app/bot/page.tsx`
- `frontend/src/lib/api.ts` bot helpers
- `frontend/src/lib/types.ts`
- `frontend/src/components/TerminalHeader.tsx` / nav — link Bot
- `frontend/src/proxy.ts` if auth routes need `/bot`

**UI:** armed toggle, config fields, open positions, fills/events, Paper badge, disclaimer.

**Verify:** `npm run build` / tsc.

---

## Task 5: Integrate + evidence

- Wire verify into init or document command
- Mark F47 passing with evidence in feature_list + progress
