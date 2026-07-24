# Progress

## Estado actual

**F49 `passing`.** Fast Path mixed-intent: noticia + precio / “conviene comprar” ya no usa el atajo news-only.

Harness audit follow-ups también aplicados: state fresco, `verify_active.sh`, `session-handoff.md`.

## Próximo paso

1. Deploy API (Railway) con F49 + harness.
2. Smoke prod:
   - `ultima noticia de msft? y como esta de precios? conviene comprar ahora?` → debe incluir precio
   - `precio BTC` / `dólar blue hoy` / `última noticia de MSFT` (sola) siguen en fast path
3. Confirmar Railway: `RESEARCH_ENGINE=langgraph`, `RESEARCH_PARALLEL_ENABLED=true`

## Notas

- 2026-07-24 — Harness audit ~72/100; top3: state + verify_active + session-handoff.
- 2026-07-24 — F49: bug Fast Path (MSFT noticia+precio → “precio no disponible”); fix + `verify_f48_fast_chat` casos mixtos.
- 2026-07-24 — F48 shipped (`e2511ab`): fast paths, live parallel steps, bot live marks (`?fresh=true`).
- 2026-07-23 — F47 Paper Bot passing; trader via `BOT_OPERATOR_ID` / `LOCAL_OPERATOR_ID`.

## Roadmap

- **F38** pending — Article Body enrichment (después del smoke F49)
- Paper Bot: usar 2–3 días → definir F50 desde dolor real
