---
status: accepted
---

# Retention Window: 30 días sobre published_at

El Store acumula Signals sin límite; eso crece el Vector Index, el costo de embeddings y el ruido del RAG. Se adopta una **Retention Window** de **30 días** calculada sobre `published_at`, uniforme para todas las fuentes, que elimina filas vencidas al final de cada ciclo de Ingestion y también vía CLI standalone. El embedding vive en la misma fila que el Signal (columna `embedding` en `signals`); borrar la fila borra el embedding. Se agrega `ingested_at` solo para observabilidad (cuándo entró al Store), sin participar en la política de retención.

> **Amend 2026-07-22:** default bajó de 60 → 30 para alinear con la ventana narrativa del Dossier (7–30d) y el Chart Plan timeline; menos ruido en RAG y Store más chico.

## Considered Options

- **Retención por `ingested_at`** — rechazado: un backfill o re-ingesta de noticias antiguas las mantendría indefinidamente aunque su `published_at` sea viejo; el feed y el RAG deben reflejar relevancia temporal del contenido publicado.
- **Ventanas distintas por fuente** (p. ej. X 30 días, RSS 90 días) — rechazado: complejidad operativa y de configuración sin beneficio claro en MVP; una ventana uniforme simplifica razonamiento y documentación.
- **Archivar en lugar de borrar** (tabla fría / S3) — rechazado para MVP: el Corpus activo y el Vector Index deben mantenerse acotados; el costo de almacenamiento frío y re-hidratación no justifica el caso de uso actual.
- **Borrar por `published_at` + ventana configurable** — elegido.

## Decisiones asociadas

- **Criterio**: `published_at < now() - RETENTION_DAYS`. Misma regla para X, RSS, Alpha Vantage, GDELT y cualquier Source Adapter futuro.
- **Momento de ejecución**: al final de cada corrida del Worker de Ingestion y como comando CLI independiente (`retention` o equivalente) para mantenimiento manual o cron.
- **Embedding co-localizado**: no hay tabla separada de vectores; `DELETE` sobre `signals` elimina el embedding en la misma transacción.
- **`ingested_at`**: columna `TIMESTAMPTZ NOT NULL DEFAULT now()` con índice descendente; solo métricas y debugging (lag de ingesta, volumen por día), no input de retención.
- **Embeddings best-effort**: la ingesta intenta embedear al persistir; un job de backfill cubre filas sin embedding; la retención no distingue — si el Signal vence, se borra con o sin vector.
- **Citas rotas**: Research Chat y referencias a Signals eliminados pueden quedar huérfanas; trade-off aceptado a cambio de un Corpus acotado y RAG más fresco.
- **Configuración**: variable de entorno `RETENTION_DAYS` (default `30`). Valor `0` deshabilita la purga (comportamiento explícito para dev o conservación total).

## Consequences

- Migración `004_signals_ingested_at.sql` agrega `ingested_at` e índice; filas existentes reciben `now()` como default en el ALTER.
- El Worker y/o módulo de retención leen `RETENTION_DAYS` del entorno; sin valor o con `0`, no se ejecutan `DELETE`.
- Operadores deben asumir que Signals con más de 30 días de antigüedad (por fecha de publicación) desaparecen del feed, del detalle y del índice vectorial.
- Monitoreo posible vía `ingested_at` vs `published_at` para detectar retrasos de ingesta o backfills masivos.
