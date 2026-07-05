---
status: accepted
---

# pgvector sobre Postgres para el Vector Index del MVP

Supersedes [ADR-0001](./0001-qdrant-para-vector-index.md). A la escala del MVP (un solo Operator, ~200-500 Signals/día, del orden de 10^5 vectores en un año) la ventaja de un motor vectorial dedicado no es perceptible, mientras que su costo sí lo es. Usamos pgvector sobre el mismo Postgres del Store en vez de Qdrant.

## Considered Options

- **Qdrant como servicio separado** — mejor a gran escala (millones de vectores, alto QPS, quantization). Rechazado para el MVP: introduce un servicio extra a operar y obliga a sincronizar Store e Index manualmente por `id_str`.
- **pgvector sobre el Postgres existente** — elegido. El embedding es una columna en la tabla de Signals; Signal y embedding se escriben en la misma transacción (consistencia gratis, sin sincronización); el filtrado híbrido por ticker/fecha/fuente es SQL nativo (`WHERE` + operador de similitud).

## Consequences

- El Vector Index deja de ser un servicio aparte: es el índice HNSW de pgvector dentro del Store. Un servicio menos en el Docker Compose.
- Si a futuro se alcanza escala de millones de vectores o alto QPS concurrente (p. ej. fase SaaS), migrar a Qdrant es un trabajo acotado, justificado con datos reales en ese momento.
