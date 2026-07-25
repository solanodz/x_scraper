# Article Body — cobertura y límites (F38)

## Qué es

**Article Body** = texto completo del artículo (best-effort trafilatura) en Signals de noticia (`rss`, `marketaux`, `alpha_vantage`). Alimenta el Embedding Document y el Research Chat.

Si no hay body usable → **summary + link** (honesto; no se inventa texto).

## Env (defaults F38)

| Variable | Default | Rol |
|----------|---------|-----|
| `ARTICLE_BODY_ENABLED` | `true` | On/off enrichment |
| `ARTICLE_BODY_MAX_PER_INGEST` | `150` | Cap de fetches en una ingesta |
| `ARTICLE_BODY_BACKFILL_LIMIT` | `100` | Cap post-ingest / ciclo de backfill |
| `ARTICLE_BODY_MIN_CHARS` | `200` | Body “usable” mínimo |
| `ARTICLE_BODY_FETCH_DELAY` | `0.5` | Segundos entre fetches |

## SKIP_DOMAINS (no se pelean)

En `scraper/article_enrichment.py`:

- `news.google.com` (wrappers)
- `marketwatch.com` (paywall / bot-block frecuente)

El backfill SQL también excluye esas URLs para no gastar cupo.

## Expectativa de cobertura

- Sube con caps más altos + cola de backfill más grande.
- **No** se promete cobertura de paywalls ni de Google News.
- Medios abiertos (Yahoo Finance, CNBC, BBC, Ámbito, etc.) tienen mejor hit-rate.

## Operación

- Ingesta normal ya corre enrichment + `backfill_article_bodies()`.
- Worker Railway: mismos env en el servicio worker.
- Métrica rápida:  
  `SELECT count(*) FROM signals WHERE body IS NOT NULL AND length(trim(body)) >= 200 AND body IS DISTINCT FROM summary;`
