---
status: accepted
---

# Corpus multi-fuente: Signal source-agnostic + Source Adapters

El Corpus deja de depender exclusivamente de X (twscrape). Se adopta un modelo **multi-fuente** donde las noticias son la fuente primaria (RSS de medios abiertos + Alpha Vantage news) y X queda como complemento de reacción/chatter. Esto responde a dos problemas del MVP: **profundidad** (los Signals eran solo tweet + título de artículo, sin cuerpo para el RAG) y **ruido** (feed con demasiado contenido irrelevante). Un **Signal** pasa a ser una unidad de contenido *source-agnostic*, normalizada por un **Source Adapter** por cada fuente.

## Considered Options

- **Seguir solo en X mejorando sources/filtros** — rechazado: no resuelve profundidad (paywalls en Reuters/Bloomberg/WSJ/FT hacen inútil scrapear el cuerpo del artículo enlazado) y twscrape es frágil (cookies, rate limits, ToS).
- **Reemplazar X por completo** — rechazado: X aporta reacción temprana y voces fuera del mainstream; se degrada a complemento, no se elimina.
- **Tabla nueva `articles` separada de `signals`** — rechazado: duplica el pipeline (feed, RAG, embeddings ya leen de `signals`). Se generaliza la tabla existente.
- **News-first + X complemento, generalizando `signals`** — elegido.

## Decisiones asociadas

- **Presupuesto $0** inicial: RSS + Alpha Vantage `NEWS_SENTIMENT` (key ya existente) + GDELT. Se reevalúa pagar con evidencia.
- **Profundidad best-effort**: extraer Article Body con `trafilatura`/readability cuando el medio es abierto; fallback a summary en paywalls. Sources curadas hacia medios extraíbles.
- **Enriquecimiento híbrido liviano**: reusar tickers/sentiment que ya trae la fuente; un pase LLM barato solo para Relevance Score + tópico + tickers faltantes.
- **Dedup por Story Cluster**: URL canónica + near-duplicate por similitud de embedding; se muestra una vez, guardando de qué fuentes vino.

## Consequences

- La tabla `signals` se generaliza: se agregan `source_type`, `canonical_url`, `title`, `body`, `summary`, `tickers[]`, `sentiment`, `topic`, `relevance_score`, `cluster_id`. Lo específico de cada fuente queda en `payload jsonb`.
- El `Embedding Document` pasa a combinar title + summary + body (cuando existe), no solo rawContent + card.
- `scraper/` incorpora una capa de **Source Adapters** (`x`, `alpha_vantage`, `rss`, `gdelt`) que normalizan a Signal; el Worker orquesta todos.
- El `Signal Filter` sigue vigente, pero el ranking del feed usa además `relevance_score`.
- Implementación secuenciada por features observables (ver `feature_list.json`): Alpha Vantage news → RSS + body → Relevance Score → Story Cluster → X complemento.
