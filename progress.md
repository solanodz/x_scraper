# Progress

## Estado actual

**F49 en prod — smoke OK.** Mixed-intent Fast Path verificado en Railway tras redeploy.

Harness en buen estado (~84/100 post-audit). Sin feature `in_progress`.

## Próximo paso

Elegir una línea (no las tres a la vez):

1. **Paper Bot** — usarlo 2–3 días armado → anotar dolores → F50
2. **F38** — más cobertura de Article Body
3. Pausar features y solo operar (Terminal + Research + Bot)

## Notas

- 2026-07-25 — Paper Bot: PnL falso por mark BTC@$28 (TP fantasma). Guardrail mark sane + borrado trade contaminado; leverage no multiplica notional en paper.
- 2026-07-24 — Smoke prod OK tras redeploy Railway: precio BTC, dólar blue, última noticia MSFT, mixed MSFT+precio+conviene, precios plural, NVDA vs AMD; `/bot` marks live.
- 2026-07-24 — F49 shipped + harness (`verify_active`, session-handoff); audit 72→84.
- 2026-07-24 — F48: fast paths, live parallel steps, bot `?fresh=true`.
- 2026-07-23 — F47 Paper Bot passing.

## Roadmap

- **F38** pending — Article Body enrichment
- Paper Bot → F50 desde uso real
