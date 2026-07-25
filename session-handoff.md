# Session handoff

## Verified now

- F38 local: `verify_f38` OK (MAX=150, BACKFILL=100, SKIP_DOMAINS, docs).
- Programa web: F51 → F52 → F53 (grill confirmado).

## Changed this session

- Article enrichment defaults + `ARTICLE_BODY_BACKFILL_LIMIT`
- Backfill SQL omite Google News / MarketWatch
- `docs/ops/article-body.md`, `verify_f38.py`
- feature_list: F38 passing; F51–F53 pending

## Blockers

- Redeploy Worker para caps en prod.

## Next

F51 — Feed toggle Mis tickers (API multi-ticker).

## Do not touch

- Root `package-lock.json`.
- No empezar F52/F53 hasta cerrar F51.
