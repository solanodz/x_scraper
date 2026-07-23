---
status: accepted
---

# Paper Bot: Execution Venue (paper → Hyperliquid stub)

El Terminal necesita un **Paper Bot** always-on que abra/cierre long y short en **BTC y ETH** con una Strategy determinística (**Donchian Breakout**), gestione TP/SL en background y deje un puerto de ejecución listo para Hyperliquid sin trading live en el MVP.

## Considered Options

- **Órdenes manuales one-click desde el Chart** — rechazado: no cubre always-on ni gestión de riesgo en background.
- **LLM / Chart Agent decide entradas** — rechazado: no determinístico; fuera de scope del Paper Bot.
- **Paper fills + puerto Execution Venue (PaperVenue ahora, HyperliquidVenue stub)** — elegido: misma interfaz para paper y live futuro; fail-closed si `BOT_VENUE=hyperliquid` sin credenciales.
- **Loop en lifespan del API o en el Worker de Ingestion** — rechazado: el trader es un proceso dedicado (**Railway `xscraper-trader`**) con start command `python -m backend.scripts.run_paper_bot`.

## Decisiones asociadas

- **Universe MVP**: BTC + ETH únicamente.
- **Concurrency**: máximo **10** posiciones abiertas; Operator configura `max_positions` ∈ [1, 10]; **una sola posición open por símbolo**.
- **Size**: notional USD (`size_usd`); TP/SL en percent → precios absolutos persistidos en la Position al abrir.
- **Donchian**: defaults period `20`, interval `30m`.
- **Paused/disarmed**: no nuevas entradas; **sí** se siguen gestionando TP/SL de posiciones open.
- **Trade Signal** ≠ Corpus **Signal**; paper fills ≠ fills on-chain / exchange reales.
- **Env**: `BOT_ENABLED=false`, `BOT_TICK_SECONDS=30`, `BOT_VENUE=paper` (default). Secretos Hyperliquid documentados aquí para el futuro; no requeridos en MVP.
- **Deploy**: servicio Railway `xscraper-trader` (misma imagen que API/Worker; distinto start command).

## Consequences

- Tablas `bot_config`, `bot_positions`, `bot_fills`, `bot_events` (migrations twin store + supabase).
- Módulos `donchian`, `bot_strategy`, `bot_venue`, `paper_bot` + API `/bot/*`.
- CONTEXT.md: términos Paper Bot, Strategy, Risk Policy, Trade Signal, Position, Fill, Execution Venue, Bot Config.
- Verificación: `backend/scripts/verify_f47_paper_bot.py`.
