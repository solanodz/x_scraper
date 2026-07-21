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
Datos de mercado (precio, variación %, historial OHLC, logo del Ticker) vía Finnhub con fallback Alpha Vantage y yfinance. Logos: Finnhub `profile2` (equities) y CDN coin-logos (BTC/ETH/SOL); cache en proceso. Alimenta la Quote Strip, Signal Detail, Ticker Watch y el **Ticker Chart**. Delay ~15 min en quotes.
_Avoid_: Quotes, live prices

**Quote**:
Cotización de un Ticker: precio actual, cambio absoluto y porcentual. Se obtiene vía Finnhub `/quote` (fallback: Alpha Vantage GLOBAL_QUOTE).
_Avoid_: Price, tick, quote data

**Quote Strip**:
Barra bajo el header de la Terminal que muestra Quotes de la Watchlist en carrusel continuo. Clic en un Ticker abre el **Ticker Chart** (mismo control Operator-first que en `/dossier`). Datos con delay ~15 min.
_Avoid_: Ticker tape, price bar, market strip

**Watchlist**:
Tickers mostrados en la Quote Strip y usados para Market Data del carrusel. Se derivan dinámicamente del Corpus (cashtags/tickers más activos en Signals recientes) más anclas fijas en código (BTC, ETH, SPY, QQQ). No hay lista fija en `.env`. `get_quotes` acepta cualquier símbolo bajo demanda.
_Avoid_: Portfolio, favorites, bookmarks

## Terminal Layout

**Signal Feed**:
Panel superior de la Terminal. Muestra un representante por Story Cluster, ordenado por fecha de publicación (más reciente primero, sin importar la fuente), filtrable por fuente, ticker o tema. Indica las fuentes del cluster cuando la misma noticia llegó por varios canales. Aplica Signal Filter por reglas y umbral de Relevance Score (`RELEVANCE_SCORE_MIN`).
_Avoid_: Timeline, news list, stream

**Signal Filter**:
Reglas de relevancia en `.env` (`SIGNAL_FILTER`, `SIGNAL_KEYWORDS`, `SIGNAL_BLOCKLIST`, `SIGNAL_TOPIC_BLOCKLIST`, `SIGNAL_TRUSTED_SOURCES`, `X_INCLUDE_SEARCH`). News Sources pasan por título/resumen salvo `SIGNAL_TOPIC_BLOCKLIST` (humanitario sin keyword de mercado). X solo si `$TICKER` o cuenta trusted con keyword financiera explícita.
_Avoid_: Content moderation, spam filter

**Signal Detail**:
Panel inferior izquierdo de la Terminal. Muestra el contenido completo del Signal seleccionado en el Feed.
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
El agente que responde una Query orquestando herramientas sobre el Corpus y el Market Data antes de sintetizar la respuesta. Elige el camino de research según la Query: **Parallel Research** cuando hay Tickers claros o un **Research Plan** de follow-up; **ReAct** secuencial para el resto. Produce una respuesta grounded con Citations obligatorias derivadas de los Signals que las herramientas devolvieron. Recuerda el hilo de la Chat Session para responder follow-ups. Ver ADR-0006 y ADR-0008.
_Avoid_: Bot, assistant, copilot, chain

**Research Plan**:
Paso de planificación estructurada (salida JSON) que resuelve la intención de una Query cuando no hay Tickers explícitos en el texto pero sí contexto conversacional — típicamente follow-ups (*"¿y AMD?"*). Define qué Tickers investigar y qué dimensiones cubrir antes de ejecutar **Parallel Research**. No reemplaza la síntesis final ni genera la respuesta al Operator.
_Avoid_: Planner agent, query parser, intent classifier

**Parallel Research**:
Ejecución concurrente y determinística del bundle de research por Ticker: cotizaciones (`get_quotes` batcheado), Signals recientes (`get_recent_signals` por Ticker) y búsqueda semántica (`search_corpus` scoped por Ticker). Garantiza cobertura en comparaciones multi-Ticker y en cruces precio + narrativa. Máximo cuatro Tickers por Query. Un solo sintetizador cierra la respuesta; no son agentes LLM en competencia.
_Avoid_: Parallel agents, sub-agents, worker pool, map-reduce

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

## Ticker Watch & Briefing

**Ticker Watch**:
Lista personal del Operator de Tickers que sigue deliberadamente. Distinta de la Watchlist (carrusel derivado dinámicamente del Corpus, no personal): el Ticker Watch lo arma el Operator a mano y se persiste por usuario. Alimenta el Briefing. Los símbolos se guardan canónicos (mayúsculas, sin `$`, resueltos desde nombres de empresa: Intel → INTC). Cada Ticker puede tener una **Thesis** opcional del Operator.
_Avoid_: Watchlist, favorites, portfolio, following

**Thesis**:
Hipótesis de inversión del Operator sobre un Ticker en su Ticker Watch: por qué lo sigue y qué riesgos tiene en mente. Una oración corta, opcional. El Briefing evalúa **alineación** (refuerza / neutral / tensiona) entre la Thesis y los Signals recientes.
_Avoid_: Note, watch note, investment thesis document, conviction score

**Briefing**:
Memo ejecutivo on-demand, grounded y con Citations, sobre los Tickers del Ticker Watch. Resume lo material del día (prioridad alta, delta vs Briefing anterior, temas cruzados, preguntas abiertas) y apunta al **Dossier** de cada Ticker para profundidad. Refresca Dossiers seleccionados antes de sintetizar (ADR-0009). Prioriza velocidad de lectura: el Operator entiende qué cambió y qué merece atención sin leer un informe completo. No reemplaza al Dossier. Analítico: sin recomendaciones de compra/venta ni predicción de precios; afirmaciones sobre el Corpus respaldadas por Signal. On-demand en Chat Session dedicada (permite follow-up). Ver ADR-0007 y ADR-0009.
_Avoid_: Digest, report, newsletter, resumen

**Dossier**:
Análisis integral persistente por Ticker del Ticker Watch. Estructura en seis bloques: (1) Panorama de mercado, (2) Narrativa del Corpus — ventana larga en dos subcapas: últimos 7 días (urgente) y 7–30 días (contexto), hilos materiales no headlines sueltos, (3) Sentimiento del Corpus — agregado híbrido: estadísticas determinísticas (conteos, tono, fuentes) más síntesis LLM anclada a esos números, (4) Contexto macro/sector, (5) Fundamentals (placeholder honesto hasta que haya fuente), (6) Lectura integrada con alineación a la **Thesis** y lagunas de datos declaradas. Pantalla dedicada `/dossier` (navbar); selector por Ticker del Watch; links desde el Briefing y el popover Watch. Ver ADR-0009. Cruza capas de evidencia con Citations donde aplique al Corpus. Se actualiza on-demand y se **refresca al generar un Briefing**: siempre los Tickers en **prioridad alta**; el resto solo si tuvieron Signals en la ventana del Briefing; los demás reutilizan la última versión. El Briefing consume Dossiers como contexto antes del memo ejecutivo. Conserva historial de versiones (últimas 10 o 30 días por Ticker, lo que ocurra primero). Analítico: sin recomendaciones de compra/venta. El **Chart Plan** es artefacto aparte, on-demand.
_Avoid_: Profile, ticker page, equity research PDF, one-pager

**Ticker Chart**:
Gráfico interactivo de precio del Ticker en `/dossier` (velas OHLC + indicadores). Lo controla el **Operator** (intervalo de vela, ventana de historial e indicadores); no requiere Chart Plan ni Chart Agent. Puede auto-actualizarse con Market Data. El Operator elige con presets combinados (intervalo + ventana) o modo advanced con ambos controles. Indicadores MVP (todos OFF por defecto; se eligen y parametrizan desde un desplegable): overlays en precio (SMA, Donchian, Fib), Volume (pane dentro del precio), y debajo del precio (panes separados, zoom sync): **Oracle Oscillator** (baseline fill verde/amarillo/rojo, niveles 75/25) y **RSI con divergencias** (señales Bull/Bear precio↔RSI). Se puede ampliar a un dialog grande.
_Avoid_: TradingView widget, price pane, chart widget, timeframe (usar intervalo + ventana)

**Chart Plan**:
Artefacto on-demand en `/dossier` producido por el **Chart Agent**: lecturas interpretativas de indicadores, assessment objetivo (incluye dimensiones visual, narrativa Corpus, sentimiento vs precio, TA multi-ventana) y gráficos del Corpus. No captura el control del **Ticker Chart**; puede ofrecer una sugerencia soft (“Aplicar vista del Chart Plan”) que el Operator acepta o ignora. Si la vista del Ticker Chart diverge de la del Plan, las lecturas se marcan desactualizadas. Persistente y versionado por Ticker, independiente del Dossier. Pine Script exportable queda fuera del MVP actual.
_Avoid_: Technical analysis report, trading setup, buy signal, Pine chart

**Chart Agent**:
Orquestador on-demand que genera un **Chart Plan**. Con **Parallel Chart Gather** activo: gather concurrente + **Chart Interpreters** en paralelo + una sola síntesis (sin ReAct secuencial). Captura el **Ticker Chart** real del Operator para el interpreter de visión; ancla números en stats determinísticas. Produce `indicator_readings` y assessment enriquecido (`conflicts`, `data_gaps`, `bias_check` + lecturas por dimensión). No bloquea ni reemplaza el control Operator-first del **Ticker Chart**. Ver ADR-0012.
_Avoid_: Trading bot, chart generator, TA guru, parallel agents

**Parallel Chart Gather**:
Ejecución concurrente del análisis del Chart Plan: lanes determinísticas (Market/TA, Corpus, sentimiento stats, Dossier, captura del Ticker Chart) más **Chart Interpreters** LLM en paralelo, cerradas por un único sintetizador. Sustituye el ReAct secuencial del Chart Agent cuando el flag de parallel está activo. Distinto de **Parallel Research** (Research Chat). Ver ADR-0012.
_Avoid_: Parallel agents, sub-agents, chart workers, map-reduce

**Chart Interpreter**:
Lectura LLM acotada a una dimensión del Chart Plan dentro del **Parallel Chart Gather**. Cuatro roles: (1) visión del Ticker Chart, (2) narrativa del Corpus, (3) sentimiento vs precio, (4) TA multi-ventana (`5d·15m`, `3mo·1d`, `1y·1d`). No genera el Chart Plan solo; alimenta al sintetizador. Ver ADR-0012.
_Avoid_: Sub-agent, specialist agent, vision bot, news bot

**Análisis integral**:
Síntesis multi-capa que alimenta un Dossier o una respuesta del Research Chat: no es una noticia aislada ni una sola tool, sino la combinación explícita de narrativa (Corpus), mercado, fundamentos y sentimiento con incertidumbre declarada donde falten datos.
_Avoid_: Deep dive, comprehensive report, full analysis
