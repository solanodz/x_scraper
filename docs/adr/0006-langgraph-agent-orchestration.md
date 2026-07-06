---
status: accepted
---

# Research Chat: orquestación con LangGraph

El Research Chat usa hoy un loop de tool-calling escrito a mano sobre el SDK de OpenAI (`backend/services/agent.py`: `gather_agent_context`, `max_turns=6`) con tres tools (`search_corpus`, `get_quotes`, `get_watchlist_quotes`) y una síntesis final grounded con Citations obligatorias. Para habilitar research multi-paso, análisis de mercado y tendencias, y un set de tools más rico, se adopta **LangGraph** como motor de orquestación del agente, manteniendo la capa de datos (pgvector + embeddings) en código propio.

Prerrequisito duro: la brecha de acceso al Corpus (Signals sin embedding, ranking solo semántico, sin acceso por fecha) se arregla **antes** en una feature separada (F17). Ningún framework de orquestación compensa Signals que no están indexados.

## Considered Options

- **Seguir con el loop propio sobre OpenAI** — rechazado: agregar research multi-paso, memoria conversacional, branching y más tools sobre el loop manual duplica plumbing que LangGraph ya resuelve (estado, streaming de pasos, ReAct, evolución a plan-and-execute).
- **LangChain clásico (`AgentExecutor` / `create_tool_calling_agent`)** — rechazado: en camino de ser reemplazado por LangGraph; menos control sobre el grafo de estado y la evolución a topologías custom.
- **LangGraph + LangChain completo, incluyendo `VectorStore`/`Retriever` sobre pgvector** — rechazado: el retrieval propio (`backend/services/retrieval.py`) ya tiene SQL afinado con filtros por ticker/fecha, `relevance_score`, Story Clusters y `embedding IS NOT NULL`. Envolverlo en la abstracción de LangChain haría perder ese control y reimplementar lógica existente.
- **LangGraph + `langchain-core` + `langchain-openai`, retrieval propio en código directo** — elegido.

## Decisiones asociadas

- **Stack**: `langgraph` para la orquestación, `langchain-core` y `langchain-openai` para el modelo. Retrieval y embeddings de pgvector quedan en código propio; las tools de LangGraph llaman a `retrieve()` y funciones existentes.
- **Topología**: arrancar con el agente ReAct prebuilt (`create_react_agent`) para paridad rápida con el loop actual; dejar preparada la evolución a un `StateGraph` custom (planner → research → synthesis) sin cambiar el contrato externo.
- **Citations**: se derivan de los hits que devuelven las tools (acumulados en el estado del grafo), no de lo que el LLM afirma citar. Se preserva la garantía actual de Citations confiables.
- **Contrato de streaming**: el SSE del Chat Stream (`session`, tokens `data:`, `citations` final) se mantiene idéntico. F-langgraph es backend-only; el frontend no cambia.
- **Memoria conversacional**: se reusa `chat_messages` como historial (se cargan mensajes previos de la sesión y se pasan al grafo). No se adopta el checkpointer de LangGraph — una sola fuente de verdad, sin tablas ni migraciones nuevas. Arregla los follow-ups (hoy el agente solo recibe la query actual).
- **Tools** (7): `search_corpus` (ampliada con `source_type` + `min_relevance`), `get_recent_signals` (por fecha, de F17), `get_signal_detail` (Article Body para lectura profunda), `corpus_stats` (agregación/tendencias narrativas del Corpus), `get_quotes`, `get_watchlist_quotes`, `get_price_history` (yfinance, tendencias de precio). Ticker / tipo de noticia / fecha / período / relevancia son **parámetros**, no tools separadas.
- **Modelo**: configurable por env (`RESEARCH_MODEL` para el loop de tools, `SYNTHESIS_MODEL` para la síntesis); default `gpt-4o-mini` en ambos.
- **Observabilidad**: LangSmith opt-in por env (`LANGCHAIN_TRACING_V2` + `LANGSMITH_API_KEY`), apagado por default.
- **Deployment**: LangGraph corre como librería dentro del API FastAPI en Railway. No se adopta LangGraph Platform/Server ni infra nueva.
- **Migración**: feature flag `RESEARCH_ENGINE=langgraph|legacy` (default `legacy` hasta verificar paridad). Cutover a `langgraph` tras verificación; el motor viejo se elimina en una feature posterior.

## Consequences

- Nuevas dependencias en `requirements.txt`: `langgraph`, `langchain-core`, `langchain-openai` (y `langsmith` opcional). `yfinance` ya está presente.
- `backend/services/ask.py` gana una bifurcación por `RESEARCH_ENGINE`; el motor LangGraph vive en un módulo nuevo (ej. `backend/services/research_agent.py`) sin borrar `agent.py` hasta el cutover.
- El contrato del endpoint `/chat` y el frontend no cambian durante la migración.
- Las tools de mercado histórico dependen de yfinance (best-effort; puede fallar o throttlear — degradación elegante como el resto de Market Data).
- Costos de OpenAI pueden subir con research multi-paso (más rondas de tools); mitigable con `max_turns` y modelos configurables.
- La memoria vía `chat_messages` acopla la calidad del agente al historial persistido; sesiones sin persistencia (dev sin tablas) operan sin memoria, igual que hoy.
