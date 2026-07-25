# Session handoff

Compact restart path for the next agent/session. Keep this current when work is mid-flight.

## Verified now

- F49 mixed-intent Fast Path **en prod** (Railway redeploy + smoke OK 2026-07-24).
- Paper Bot: trade contaminado BTC mark@$28 borrado; `assert_sane_mark` + verify_f47 OK local.
- Harness: `scripts/verify_active.sh`, `session-handoff.md`.

## Changed this session

- `backend/services/bot_venue.py` — mark sanity guard (floor BTC/ETH + max jump vs entry).
- `backend/scripts/verify_f47_paper_bot.py` — regresión mark $28.
- `/bot` UI labels: size notional; leverage display-only in paper.
- Store: deleted position `9739ed80-…` (+fills).

## Blockers

- Redeploy **xscraper-trader** (y API si sirve UI) para activar el guardrail en Railway.

## Next (una sola cosa)

Redeploy trader en Railway; confirmar que un mark basura ya no cierra posiciones.

## Do not touch

- Root `package-lock.json` (basura; no commitear).
