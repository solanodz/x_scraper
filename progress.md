# Progress

## Estado actual

**F47 `passing`.** Paper Bot listo para Railway (`xscraper-trader`), UI sin demo, paper live autónomo.

## Próximo paso

1. Push `main` + deploy Vercel
2. Railway: crear `xscraper-trader`
   - Start: `python -m backend.scripts.run_paper_bot`
   - Env: `BOT_ENABLED=true`, `BOT_VENUE=paper`, `BOT_OPERATOR_ID=<supabase user uuid>`, `DATABASE_URL`, `FINNHUB_API_KEY`
3. En `/bot` → **Armed**
4. Logs: ticks cada 30s; opens solo con breakout Donchian 30m

## Notas

- 2026-07-23 — Removido demo UI. Trader resuelve operator vía `BOT_OPERATOR_ID` / `LOCAL_OPERATOR_ID` / única fila `bot_config`.
- 2026-07-23 — F47 PASSING (verify_f47 + /bot UI).

## Roadmap Paper Bot

- **F47** Paper Bot (`passing`)
