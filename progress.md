# Progress

## Estado actual

**F18 `passing`.** Research Agent LangGraph verificado localmente. F9 `passing`. Próximo: cutover prod `RESEARCH_ENGINE=langgraph` en Railway API.

## Próximo paso

1. Railway API: `RESEARCH_ENGINE=langgraph` + redeploy
2. Probar follow-up en prod: "¿y comparado con el mes pasado?" tras una query de NVDA
3. Elegir siguiente feature (quick win UX o GDELT)

## Roadmap Corpus multi-fuente (ADR-0004)

- **F10** News Source: Alpha Vantage (`passing`)
- **F11** RSS + Article Body (`passing`)
- **F12** Relevance Score (LLM, baja ruido) (`passing`)
- **F13** Story Cluster (dedup cross-source) (`passing`)
- **F14** X como complemento (`passing`)
- **F15** Chat Session / historial Research Chat (`passing`)
- **F16** RSS noticias Argentina (`passing`)

## Roadmap Research Agent (ADR-0006)

- **F17** Acceso confiable al Corpus (retrieval) (`passing`)
- **F18** Research Agent con LangGraph (`passing`)

## Deploy F9 (`passing`)

Railway (API + Worker) + Vercel (frontend) + Supabase — prod operativo.

## Log

- 2026-07-06 — F18 PASSING. LangGraph ReAct (`research_agent.py`), 7 tools, memoria vía chat_messages, flag `RESEARCH_ENGINE`. Verificado: `python -m backend.scripts.verify_f18` OK; `./init.sh` OK.

- 2026-07-06 — F9 PASSING. Deploy prod confirmado: Vercel Terminal, Railway API/Worker, Supabase Store. Auth, Feed SSE, Chat, Quotes, ingesta Worker OK en producción.

- 2026-07-06 — Tickers dinámicos (`9a444ab`). Sin WATCHLIST: Quote Strip desde Corpus, resolve Intel→INTC, get_quotes cualquier símbolo. `verify_ticker_catalog` OK.

- 2026-07-06 — F17 PASSING. Acceso confiable al Corpus: `get_recent_signals` (por fecha, como feed), `search_by_keywords` fallback en `retrieve()`, `EMBEDDING_BACKFILL_LIMIT=200`, filtro ticker en title/summary. Verificado: `python -m backend.scripts.verify_f17` OK; `./init.sh` OK.

- 2026-07-05 — F16 PASSING. `ARGENTINA_FEEDS` en `scraper/adapters/rss.py` (Ámbito economía/finanzas, La Nación, Infobae, Google News AR). Flag `RSS_AR_FEEDS_ENABLED`. Verificado: `python -m backend.scripts.verify_f16` OK (25 signals, Ámbito body 2152 chars). Ingesta: 25 AR RSS en Store con body>=200 en medios directos. `./init.sh` OK.

- 2026-07-05 — F14 PASSING. `XComplementAdapter`: X secundario (news-first, graceful degradation), volumen de ingesta como antes. Feed prioriza noticias sobre X.

- 2026-07-05 — F15 PASSING. Chat Session: `chat_repo` + persist en `POST /chat`, `GET /chat/sessions`, `GET /chat/sessions/{id}/messages`. Frontend ResearchChat restaura historial, selector de sesiones, botón Nueva. Migración local `005_operator_chat.sql`; Supabase `006_chat_drop_user_fk.sql`. Verificado: `python -m backend.scripts.verify_f15` OK.

- 2026-07-05 — F13 PASSING. `scraper/story_cluster.py`: cluster_id por URL + merge por embedding similarity. `GET /signals` un representante por cluster; `cluster_sources` en API/Feed/Detail. Verificado: `python -m backend.scripts.verify_f13` OK (143 signals / 142 clusters). `./init.sh` + `npm run build` OK.

- 2026-07-05 — F12 PASSING. `scraper/relevance.py`: Relevance Score + tópico + tickers vía gpt-4o-mini en Ingestion. Feed: `ORDER BY relevance_score DESC`, filtro `RELEVANCE_SCORE_MIN=0.35`. AV/Marketaux dejan de usar sentiment como score. Verificado: `python -m backend.scripts.verify_f12` OK. `./init.sh` OK.

- 2026-07-05 — F11 PASSING. `scraper/article_enrichment.py` (trafilatura), integrado en `scraper/ingest.py` post-filtro. Feeds RSS: Yahoo Finance, CNBC, BBC (+ Google News metadata). `body` en API (`SignalDetail`) y frontend. Verificado: `python -m backend.scripts.verify_f11` => 12/12 Article Body, Embedding Document OK, Research Chat cita Signal con body. `./init.sh` OK.

- 2026-07-05 — Retention Window (ADR-0005): `scraper/retention.py`, `scraper/backfill.py`, `ingested_at` migración 004, pipeline ingest (embed best-effort + backfill + prune). Purge X: 191 Signals eliminados. Store: 49 rss + 3 marketaux. `./init.sh` OK.

- 2026-07-05 — Diseño Corpus multi-fuente cerrado (grill-with-docs). Decisiones: news-first + X complemento, $0 (RSS + Alpha Vantage news + GDELT), profundidad best-effort con trafilatura, enriquecimiento LLM híbrido liviano (relevance_score + tópico + tickers), dedup por Story Cluster (URL + near-dup embedding). Artefactos: ADR-0004, CONTEXT.md (Signal source-agnostic + News Source/Source Adapter/Article Body/Relevance Score/Story Cluster), feature_list F10–F14. F9 → blocked (deploy manual). F10 in_progress.

- 2026-07-04 — F9 auth local verificada. `./init.sh` OK; `AUTH_ENABLED=true .venv/bin/python -m backend.scripts.verify_f9` => GET /health 200, GET /signals sin token 401. Deploy prod pendiente.

- 2026-07-04 — F9 IN_PROGRESS (Task 10 harness). Código: auth.py, login page, fetch-event-source SSE, Dockerfile, deploy docs. Verificado local: `./init.sh` OK, `verify_f9` OK (AUTH_ENABLED=false), `npm run build` OK. Deploy manual pendiente.

- 2026-07-04 — Spec Operator Terminal + ADR-0003 (Supabase/Railway/Vercel). Producto definido: herramienta personal (A). Roadmap F9–F12 documentado.

- 2026-07-04 — F8 PASSING. Research Chat agente: tools search_corpus, get_quotes, get_watchlist_quotes; gather_agent_context + síntesis con precios y Citations. Verificado: `.venv/bin/python -m backend.scripts.verify_f8` OK.

- 2026-07-04 — F7 PASSING. Migrado Finnhub → Alpha Vantage (`ALPHA_VANTAGE_API_KEY`). Caché 6h, límite 25 req/día, throttle 1 req/s. Frontend: poll 15 min + badge "15m delayed". Verificado: `.venv/bin/python -m backend.scripts.verify_f7` OK (6 watchlist, AAPL $308.63 +4.84%).

- 2026-07-04 — F7 IMPLEMENTADO (verificación live bloqueada). Market Data híbrido: Quote Strip (WATCHLIST fija) + enriquecimiento cashtags en Signal Detail vía Finnhub. Backend: `backend/services/market_data.py`, GET `/quotes/watchlist`, GET `/quotes?symbols=`. Frontend: `QuoteStrip.tsx` (poll 30s), mini quote cards en Signal Detail. Graceful degradation sin API key (endpoints 200 + lista vacía, UI "Market data unavailable"). Verificado: `./init.sh` OK, `npm run build` OK, F5 regression OK, verify_f7 SKIP (no FINNHUB_API_KEY), endpoints sin key => `[]`.

- 2026-07-04 — F6 PASSING. Web Next.js (`frontend/`): Terminal de 3 paneles (Signal Feed SSE, Signal Detail, Research Chat streaming + Citations clickeables), TerminalHeader con Refresh. Verificado con `frontend/scripts/verify-build.sh` (build OK). Manual: `npm run dev` en localhost:3000 con API en localhost:8000.

- 2026-07-04 — F5 PASSING. API FastAPI (`backend/app/`): GET /signals (paginado + filtros), GET /signals/{id_str}, GET /signals/stream (SSE heartbeat + eventos signal), POST /chat (stream tokens + event citations), POST /ingest/refresh (202 fire-and-forget worker --once). Core Services extendidos: `stream_answer`, `ask_stream`. Verificado con `python -m backend.scripts.verify_f5`.

- 2026-07-04 — F4 PASSING. Core Services (`backend/services/`): search semántico vía pgvector, summarize por Ticker/ventana temporal, ask RAG con Citations obligatorias (gpt-4o-mini). Verificado con `python -m backend.scripts.verify_f4`.

- 2026-07-04 — F3 PASSING. Worker verificado con OPENAI_API_KEY: 34 Signals con embedding en Store. Últimos ingestados tienen embedding; 43 legacy sin embedding (corridas previas sin API key).

- 2026-07-03 — F3 IMPLEMENTADO (verificación bloqueada). Worker (`scraper/worker.py`): `--once` (Refresh) y `--interval` (cron, default 1800s). Ingestion genera Embedding Documents y escribe Signal+embedding en misma transacción (`scraper/embeddings.py`, `store.upsert_signals(..., embeddings=...)`). `--skip-embeddings` para dev sin API key. **Blocker**: `.env` sin `OPENAI_API_KEY` válida — worker falla al embeddear; pgvector UPSERT validado con vector sintético; worker `--skip-embeddings` OK.

- 2026-07-03 — F2 PASSING. Tabla `signals` en Store (`infra/store/init/002_signals.sql`): dedup por `id_str`, UPSERT de engagement, `payload` jsonb, `embedding vector(1536)` nullable. Paquete `scraper/` (sources, serialize, store, ingest). Ingesta verificada: 54 Signals, re-ingesta sin duplicar.

- 2026-07-03 — F1 PASSING. Docker Compose con servicio `store` (pgvector/pgvector:pg16), puerto host 5433 (5432 estaba ocupado por un Postgres local). Extensión `vector` 0.8.4 habilitada vía `infra/store/init/001_extensions.sql`. Contenedor healthy.

- 2026-07-03 — Diseño cerrado vía grill-with-docs. Decisiones clave: terminal de noticias (Corpus X) para MVP con market data en fase 2; un solo Operator; layout de 3 paneles; ingesta cron+refresh; Postgres como Store; **pgvector** para Vector Index (ADR-0002 supersede ADR-0001/Qdrant); OpenAI; monorepo plano; SSE para feed + streaming para chat; Research Chat tipos 1-3 con Citations obligatorias; Sources estáticas; sin auth local.
- 2026-07-03 — Instaladas harness-skills. Scaffold creado: AGENTS.md, feature_list.json, progress.md, init.sh.
