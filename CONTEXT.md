# X Scraper Terminal

Terminal de inteligencia de noticias financieras y globales, alimentada por contenido scrapeado de X. Incluye un chatbot RAG para consultas por ticker, resúmenes y análisis sobre ese corpus.

## Language

**Terminal**:
La interfaz principal del producto: un workspace tipo Bloomberg con paneles de noticias, filtros y chat RAG.
_Avoid_: Dashboard, app, portal

**Corpus**:
El conjunto acumulado de contenido scrapeado de X (tweets, artículos enlazados, metadata) que alimenta el feed y el RAG.
_Avoid_: Database, dataset, dump

**Signal**:
Una unidad de contenido del Corpus con relevancia potencial para el usuario, _source-agnostic_: una noticia (artículo), un tweet o un hilo, sin importar de qué fuente venga (X, RSS, News API). Es lo que aparece en el feed de la Terminal. Un Source Adapter la normaliza a la misma forma.
_Avoid_: Post, item, entry, tweet (un tweet es solo un tipo de Signal)

**News Source**:
Un medio o API de noticias que alimenta el Corpus: feeds RSS de medios abiertos (globales y Argentina: Ámbito, La Nación, Infobae, Google News AR), Marketaux, Alpha Vantage `NEWS_SENTIMENT`, GDELT. Fuente primaria del Corpus; X pasa a complemento de reacción/chatter. Flag `RSS_AR_FEEDS_ENABLED` activa los feeds argentinos en el adapter RSS.
_Avoid_: Feed provider, news feed

**Source Adapter**:
Código en `scraper/` que conecta con una fuente concreta (`x`, `alpha_vantage`, `marketaux`, `rss`, `gdelt`) y normaliza su contenido a Signals con la misma forma. El Worker orquesta todos los Adapters.
_Avoid_: Connector, plugin, driver

**Article Body**:
Cuerpo completo del artículo de una noticia, extraído best-effort con trafilatura/readability desde medios abiertos (fallback a summary cuando hay paywall). Alimenta el Embedding Document para dar profundidad al Research Chat.
_Avoid_: Full text, content, article scraping

**Relevance Score**:
Puntaje 0–1 asignado por un pase LLM barato en la Ingestion, usado para rankear y filtrar el Signal Feed (baja el ruido). Complementa al Signal Filter por reglas.
_Avoid_: Priority, ranking, quality score

**Story Cluster**:
Agrupación de Signals que son la misma noticia llegada por distintas fuentes (URL canónica + near-duplicate por similitud de embedding). Se muestra una sola vez, guardando de qué fuentes vino.
_Avoid_: Group, duplicate group, merge

**Ticker**:
Un símbolo de activo financiero (ej. $AAPL, $SPY) usado para filtrar y consultar el corpus. En el MVP es una etiqueta de contexto, no una fuente de precios en vivo.
_Avoid_: Symbol, stock, cashtag

**Market Data**:
Datos de mercado (precio, variación %) vía Finnhub con fallback Alpha Vantage y yfinance. Alimenta la Quote Strip y el enriquecimiento de Signal Detail. Gráficos vía TradingView (embed). Delay ~15 min.
_Avoid_: Quotes, live prices

**Quote**:
Cotización de un Ticker: precio actual, cambio absoluto y porcentual. Se obtiene vía Finnhub `/quote` (fallback: Alpha Vantage GLOBAL_QUOTE).
_Avoid_: Price, tick, quote data

**Quote Strip**:
Barra bajo el header de la Terminal que muestra Quotes de la Watchlist fija en carrusel continuo. Clic en un Ticker abre su gráfico (TradingView). Datos con delay ~15 min.
_Avoid_: Ticker tape, price bar, market strip

**Watchlist**:
Lista fija de tickers configurada en `.env` (`WATCHLIST`) cuyas Quotes aparecen en la Quote Strip. Los cashtags del Signal seleccionado se enriquecen con Quote en Signal Detail.
_Avoid_: Portfolio, favorites, bookmarks

## Terminal Layout

**Signal Feed**:
Panel superior de la Terminal. Muestra un representante por Story Cluster, ordenado por fecha de publicación (más reciente primero, sin importar la fuente), filtrable por fuente, ticker o tema. Indica las fuentes del cluster cuando la misma noticia llegó por varios canales. Aplica Signal Filter por reglas y umbral de Relevance Score (`RELEVANCE_SCORE_MIN`).
_Avoid_: Timeline, news list, stream

**Signal Filter**:
Reglas de relevancia en `.env` (`SIGNAL_FILTER`, `SIGNAL_KEYWORDS`, `SIGNAL_BLOCKLIST`, `SIGNAL_TOPIC_BLOCKLIST`, `SIGNAL_TRUSTED_SOURCES`, `X_INCLUDE_SEARCH`). News Sources pasan por título/resumen salvo `SIGNAL_TOPIC_BLOCKLIST` (humanitario sin keyword de mercado). X solo si `$TICKER` o cuenta trusted con keyword financiera explícita.
_Avoid_: Content moderation, spam filter

**Signal Detail**:
Panel inferior izquierdo. Muestra el contenido completo del Signal seleccionado: tweet, artículo enlazado, engagement y metadata.
_Avoid_: Preview, sidebar, drawer

**Research Chat**:
Panel inferior derecho. Chatbot RAG donde el Operator consulta el Corpus por ticker, pide resúmenes o hace preguntas analíticas.
_Avoid_: Assistant, copilot, chatbot

## Data Pipeline

**Ingestion**:
Proceso que corre los Source Adapters (News Sources + X), normaliza el contenido a Signals, los enriquece (Relevance Score, tópico, tickers), los persiste en Postgres, los embebe en el Vector Index (best-effort + backfill) y aplica la Retention Window. Corre en cron (cada 15-30 min) y puede forzarse manualmente con "Refresh".
_Avoid_: Sync, import, fetch

**Retention Window**:
Ventana temporal (default 60 días, configurable con `RETENTION_DAYS`; `0` la desactiva) más allá de la cual un Signal se elimina del Store. Como el embedding vive en la misma fila que el Signal, el borrado limpia también el Vector Index. Se mide sobre `published_at` (edad del contenido) para mantener el Corpus fresco y acotado. Corre al final de cada Ingestion y como comando standalone.
_Avoid_: TTL, expiry, purge, archivado

**Store**:
Base de datos Postgres donde vive el Corpus estructurado: tweets, metadata, engagement, links, artículos.
_Avoid_: Database, DB

**Vector Index**:
Índice de embeddings vía pgvector dentro del Store (mismo Postgres). Alimenta el Research Chat con búsqueda semántica sobre el Corpus. A futuro puede migrar a un motor dedicado (Qdrant) si la escala lo justifica.
_Avoid_: Vector DB, embeddings table

**Embedding Document**:
Unidad de texto que se vectoriza y almacena en el Vector Index. Combina title + summary + Article Body del Signal cuando existe (fallback a rawContent + card en Signals de X sin cuerpo).
_Avoid_: Chunk, document, entry

**Article Enrichment**:
Paso de la Ingestion que extrae el Article Body best-effort (trafilatura, medios abiertos; fallback a summary en paywalls) y lo agrega al Embedding Document. Mejora la profundidad del Research Chat.
_Avoid_: Article scraping, content extraction, full-text fetch

## AI

**LLM Provider**:
Proveedor de modelos de IA. OpenAI para embeddings y generación. Modelos específicos pendientes de definir.
_Avoid_: AI provider, model vendor

## Repository

**Web**:
App Next.js en `frontend/`. Renderiza la Terminal: Signal Feed, Signal Detail y Research Chat.
_Avoid_: Client, UI, app

**API**:
Servicio FastAPI en `backend/`. Expone endpoints REST para Signals, Ingestion y Research Chat.
_Avoid_: Server, service

**Worker**:
Proceso de ingesta en `scraper/`. Orquesta los Source Adapters, persiste en Store e indexa en Vector Index.
_Avoid_: Cron job, ingester, collector

## Realtime & Interfaces

**Feed Stream**:
Canal SSE (server → client) que empuja Signals nuevos al Signal Feed apenas el Worker los persiste.
_Avoid_: WebSocket, socket, live feed

**Chat Stream**:
Respuesta del Research Chat entregada token a token vía streaming HTTP, para UX incremental.
_Avoid_: Streaming response, SSE chat

**MCP Server** (fase 2):
Servidor Model Context Protocol que expone el Corpus y las capacidades de búsqueda/resumen como herramientas consumibles por agentes externos (ej. Cursor, Claude). Reutiliza los Core Services. Fuera del MVP.
_Avoid_: Tool server, agent API

**Core Services**:
Capa de lógica de negocio (search, summarize, ask) independiente de HTTP. La consumen el API REST, el Research Chat y —en fase 2— el MCP Server, evitando duplicación.
_Avoid_: Business logic, service layer, use cases

## Research Chat Behavior

**Query**:
Consulta en lenguaje natural del Operator al Research Chat. El Research Agent puede usar herramientas: búsqueda semántica en el Corpus (con filtros de ticker, tipo de fuente, ventana temporal y relevancia), noticias recientes por fecha, detalle de un Signal (Article Body), estadísticas/tendencias del Corpus, cotizaciones de Tickers e histórico de precios (Market Data), y la Watchlist. Cruza precios con Signals cuando aplica. Cubre preguntas abiertas, análisis por Ticker, research multi-paso, resúmenes temporales, tendencias y comparaciones.
_Avoid_: Prompt, question, command

**Research Agent**:
El agente que responde una Query orquestando herramientas sobre el Corpus y el Market Data antes de sintetizar la respuesta. Planifica qué herramientas usar, puede encadenar varias rondas (research multi-paso) y produce una respuesta grounded con Citations obligatorias derivadas de los Signals que las herramientas devolvieron. Recuerda el hilo de la Chat Session para responder follow-ups. Ver ADR-0006.
_Avoid_: Bot, assistant, copilot, chain

**Citation**:
Referencia a un Signal fuente que respalda una afirmación de la respuesta del Research Chat. Obligatoria en toda respuesta; clickeable, abre el Signal Detail.
_Avoid_: Reference, link

**Source**:
Cualquier fuente monitoreada por un Source Adapter para alimentar el Corpus: un feed RSS, un endpoint de News API, o una cuenta/query de X. Config estática del Worker; gestión dinámica queda para fase 2.
_Avoid_: Feed, account, channel

## Deployment & Auth

**Deployment Target**:
- **Producción:** Web en Vercel, API + Worker en Railway, Store + Vector Index + Auth en Supabase (Postgres + pgvector + Supabase Auth). Ver ADR-0003 y `docs/superpowers/specs/2026-07-04-operator-terminal-design.md`.
- **Desarrollo:** Docker Compose local (Postgres + pgvector en puerto 5433).
_Avoid_: Hosting, environment, infra

**Access Control**:
Supabase Auth protege la Terminal en producción (login del Operator). FastAPI valida JWT; Worker usa credenciales de servicio al Store. Signups públicos deshabilitados tras crear la cuenta Operator. Desarrollo local sin auth (opcional).
_Avoid_: Auth, login, security

## Operator Data (Supabase)

Datos por usuario del Operator, distintos del Corpus compartido.

**Operator Settings**:
Preferencias persistidas en Supabase (`operator_settings`): watchlist personalizada, filtros de Signal Feed, layout. Reemplaza progresivamente vars de `.env` para el Operator.
_Avoid_: User profile, preferences table, config

**Chat Session**:
Conversación del Research Chat guardada en Supabase (`chat_sessions` + `chat_messages`), con Citations serializadas por mensaje assistant.
_Avoid_: Thread, conversation history, chat log

**Corpus en Store**:
Los Signals (noticias filtradas) viven en `signals` en el mismo Postgres de Supabase; no son por usuario. El filtro `SIGNAL_FILTER=relevant` reduce ruido en Ingestion.
_Avoid_: News table, tweets table
