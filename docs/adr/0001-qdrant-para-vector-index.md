---
status: superseded by ADR-0002
---

# Qdrant como Vector Index separado de Postgres

El Corpus vive en Postgres (Store) y el RAG del Research Chat necesita búsqueda semántica. En vez de usar pgvector sobre el mismo Postgres, adoptamos Qdrant como servicio dedicado para el Vector Index. Lo elegimos por su search vectorial dedicado, filtrado híbrido (metadata + vector) nativo, y la posibilidad de escalar el índice independientemente del Store a medida que crece el volumen de Signals.

## Considered Options

- **pgvector sobre el Postgres existente** — cero infra adicional, una sola base. Rechazado: acopla el escalado del search vectorial al del Store, y el filtrado híbrido y el rendimiento a gran volumen son inferiores a un motor dedicado.
- **Qdrant como servicio separado** — elegido.

## Consequences

- Hay que operar y desplegar un servicio más (incluido en el Docker Compose del MVP).
- La Ingestion debe escribir en dos destinos: Store (Postgres) y Vector Index (Qdrant). Esto introduce una sincronización que debe mantenerse consistente (mismo `id_str` como clave en ambos).
