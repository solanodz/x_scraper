# Session handoff

Compact restart path for the next agent/session. Keep this current when work is mid-flight.

## Verified now

- F48 Research Chat Fast Path — `verify_f48_fast_chat` OK (incluye casos mixed-intent tras F49).
- F49 mixed-intent Fast Path — `resolve_fast_path` no toma news-only cuando hay precio / conviene comprar; `precios` plural matchea.
- Harness: `scripts/verify_active.sh` + `init.sh` lo invoca; `session-handoff.md` + `AGENTS.md` verification table.
- Paper Bot `/bot`: marks live con `?fresh=true` cada ~3s (en `main` desde `e2511ab`).

## Changed this session

- Code: `backend/services/research_fast_path.py`, `backend/scripts/verify_f48_fast_chat.py`
- Harness: `scripts/verify_active.sh`, `init.sh`, `AGENTS.md`, `feature_list.json` (rules + F49), `progress.md`

## Blockers

- Ninguno de código. Prod: redeploy API para que F49 se vea en Research Chat público.

## Next (una sola cosa)

1. Push `main` (`3e458ad`) + deploy API (Railway).
2. Smoke prod: `ultima noticia de msft? y como esta de precios? conviene comprar ahora?` debe traer precio (no “no disponible”).
3. Confirmar vars: `RESEARCH_ENGINE=langgraph`, `RESEARCH_PARALLEL_ENABLED=true`.

## Do not touch

- Root `package-lock.json` (basura; no commitear).
- No abrir F38 hasta cerrar smoke prod de F49.
