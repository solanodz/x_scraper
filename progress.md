# Progress

## Estado actual

**F55** Operator Settings — `passing`. Branding producto: **MyTerm**.

Próxima feature grill: **F32** Provenance no-Signal (`pending`).

## Próximo paso

1. Redeploy API (Railway) + web (Vercel) para MyTerm + `/operator/settings` + `/settings`.
2. En Store local existente: aplicar `015_operator_settings.sql` si el volumen no se recreó.
3. Arrancar **F32** Provenance cuando quieras.

## Notas

- 2026-07-25 — F55 done: GET/PATCH `/operator/settings`, UI `/settings`, wire Daily PnL + Feed `watchOnly` + soft sync chart; rename → MyTerm.
- Verify: `python -m backend.scripts.verify_f55_operator_settings => OK`.
- F54 Paper Bot en soak.

## Roadmap

- F32 Provenance
- Soak Paper Bot
