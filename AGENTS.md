# AGENTS.md — X Scraper Terminal

Terminal de inteligencia de noticias financieras (Corpus de X) + Research Chat (RAG).
Dominio y lenguaje canónico en `CONTEXT.md`. Decisiones en `docs/adr/`.

## Startup flow (hacer al iniciar cada sesión)

1. Leer `progress.md` — estado actual y próximo paso.
2. Leer `feature_list.json` — feature activa y su verificación.
3. Leer `CONTEXT.md` — usar el lenguaje canónico (Signal, Corpus, Store, etc.).
4. Revisar `git log --oneline -10` — qué se hizo último.
5. Correr `./init.sh` — sincroniza dependencias y verifica baseline.

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
3. Commit seguro (solo si el usuario lo pide) con mensaje descriptivo.
4. Si el contexto queda a medias, dejar nota en `session-handoff.md`.

## Verification commands

Ver `init.sh`. Baseline actual: sintaxis del scraper + servicios de Docker Compose.
