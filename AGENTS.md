# AGENTS.md — X Scraper Terminal

Terminal de inteligencia de noticias financieras (Corpus de X) + Research Chat (RAG).
Dominio y lenguaje canónico en `CONTEXT.md`. Decisiones en `docs/adr/`.

## Startup flow (hacer al iniciar cada sesión)

1. Leer `progress.md` — estado actual y próximo paso.
2. Leer `feature_list.json` — feature activa y su verificación.
3. Leer `session-handoff.md` — si existe trabajo a medias.
4. Leer `CONTEXT.md` — usar el lenguaje canónico (Signal, Corpus, Store, etc.).
5. Revisar `git log --oneline -10` — qué se hizo último.
6. Correr `./init.sh` — sync deps, baseline compile, verify de feature `in_progress`.

No apilar trabajo nuevo sobre un baseline roto: si `init.sh` falla, arreglar eso primero.

## Working rules

- **Una feature a la vez.** Solo una con `status: in_progress` en `feature_list.json`.
- **No marcar `passing` sin evidencia.** Cada feature `passing` debe tener su `verification` ejecutada y el resultado en `evidence`.
- **Respetar el lenguaje de `CONTEXT.md`.** No introducir sinónimos listados en `_Avoid_`.
- **Respetar los ADR.** MVP: pgvector (no Qdrant), OpenAI, monorepo plano, sin auth local.
- **Cambios de dominio → actualizar `CONTEXT.md`** en el momento, no al final.
- **Decisiones difíciles de revertir → ADR** en `docs/adr/` (numeración secuencial).

## Stack (MVP)

- `frontend/` — Next.js (Terminal: Signal Feed / Signal Detail / Research Chat)
- `backend/` — FastAPI (REST + Feed Stream SSE + Chat Stream) sobre Core Services
- `scraper/` — Worker de Ingestion (twscrape → Store + Vector Index)
- Postgres + pgvector — Store y Vector Index
- OpenAI — embeddings + generación
- Docker Compose — orquesta todo en local

## Definition of done (por feature)

Una feature es `passing` solo si:

1. **Comportamiento**: el `user_visible_behavior` funciona de punta a punta.
2. **Verificación ejecutada**: se corrieron los pasos de `verification`.
3. **Evidencia registrada**: salida/observación concreta en `evidence` y nota en `progress.md`.

## End of session

1. Actualizar `progress.md`: qué se hizo, evidencia, próximo paso concreto.
2. Actualizar `feature_list.json`: status de la feature activa.
3. Actualizar `session-handoff.md` si el trabajo queda a medias (o vaciar "Next" si quedó limpio).
4. Commit seguro (solo si el usuario lo pide) con mensaje descriptivo.

## Verification

| Level | Command |
|-------|---------|
| Baseline | `./init.sh` |
| Feature activa | `./scripts/verify_active.sh` |
| Feature forzada | `VERIFY_FEATURE=F49 ./scripts/verify_active.sh` |
| Smoke prod (manual) | Ver `progress.md` → Próximo paso |

Baseline: `py_compile` scraper/backend + `docker compose config` + verify de `in_progress`.
Cada feature `passing` debe listar en `verification[]` un `python -m backend.scripts.verify_*` cuando exista script.
