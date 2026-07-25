# Session handoff

## Verified now

- F50 local: leverage × size → qty; `symbol_already_open` no se escribe en `bot_events` (`verify_f47` OK).
- F49 en prod; mark sanity en trader (redeploy previo).

## Changed this session

- `bot_venue.py` — notional = size_usd × leverage
- `paper_bot.py` — silent `symbol_already_open` skips
- `/bot` UI labels + notional hint in open table
- CONTEXT + ADR-0015 size semantics
- `feature_list` F50 passing

## Blockers

- Redeploy trader (y frontend) para F50 en prod.

## Next

Redeploy trader → smoke leverage/notional + Events limpios.

## Do not touch

- Root `package-lock.json`.
