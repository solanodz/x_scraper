# Progress

## Estado actual

**F50 `passing`.** Paper Bot: leverage real (`qty = size × lev / mark`) + skips `symbol_already_open` ya no se persisten.

## Próximo paso

1. Redeploy **xscraper-trader** (+ Vercel frontend para labels).
2. Smoke `/bot`: con lev 4 y size 50, notional ~200; Events sin spam de skips al tener posición open.
3. Seguir operando o elegir F38.

## Notas

- 2026-07-25 — F50 desde soak (432 skips + leverage engañoso).
- 2026-07-25 — Mark guardrail + soak; trader redeploy previo.
- 2026-07-24 — F49 smoke prod OK.

## Roadmap

- **F38** pending — Article Body
