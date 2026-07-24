# Progress

## Estado actual

**F48 `passing`.** Research Chat Fast Path listo: Quote/FX/última noticia evitan ReAct completo, y Parallel Research streamea steps en vivo.

## Próximo paso

1. Push `main` + deploy API
2. Railway API: setear/confirmar
   - `RESEARCH_ENGINE=langgraph`
   - `RESEARCH_PARALLEL_ENABLED=true`
   - `RESEARCH_MAX_TURNS=6`
   - `CHAT_HISTORY_MAX_MESSAGES=10`
3. Smoke `/research`:
   - `precio BTC` debe responder rápido vía Quote
   - `dólar blue hoy` vía FX
   - `última noticia de MSFT` vía Signals recientes
   - `compará NVDA vs AMD` muestra steps paralelos

## Notas

- 2026-07-23 — Removido demo UI. Trader resuelve operator vía `BOT_OPERATOR_ID` / `LOCAL_OPERATOR_ID` / única fila `bot_config`.
- 2026-07-23 — F47 PASSING (verify_f47 + /bot UI).
- 2026-07-24 — F48 PASSING (`verify_f48_fast_chat`): fast paths + live Parallel Research steps.

## Roadmap Paper Bot

- **F47** Paper Bot (`passing`)
