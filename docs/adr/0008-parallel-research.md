---
status: accepted
---

# Research Chat: Parallel Research para cobertura garantizada

El Research Agent (LangGraph ReAct, ADR-0006) responde Queries encadenando rondas secuenciales de tools. En comparaciones multi-Ticker, cruces precio + narrativa y follow-ups conversacionales, el ReAct suele cerrar antes de reunir todas las fuentes: cubre un Ticker o una dimensión (precio **o** noticias) y sintetiza. La prioridad de producto es **cobertura**, no latencia pura. Se adopta un camino híbrido: **Parallel Research** determinístico cuando hay Tickers claros o un **Research Plan** de follow-up; **ReAct** sin cambios para el resto.

El Briefing no participa de esta decisión: sigue determinístico (ADR-0007). Parallel Research aplica solo al Research Chat libre.

## Considered Options

- **Múltiples agentes LLM en paralelo** (sub-agentes Corpus + Market que compiten o debaten) — rechazado: multiplica costo y tokens, duplica retrieval, y complica las Citations confiables (ADR-0006: hits de tools, no afirmaciones del modelo). No son "agentes" en el sentido de varios loops ReAct; el producto necesita un solo sintetizador.
- **Planner LLM en toda Query** — rechazado para F24: gasta una llamada de planificación en cada turno sin ganancia de cobertura en Queries temáticas abiertas que ya funcionan con ReAct.
- **ReAct con tool-calling paralelo del SDK** — insuficiente: el modelo sigue decidiendo cuándo "alcanza"; no garantiza bundle completo por Ticker.
- **Híbrido: detección de Tickers + Research Plan en follow-ups + Parallel Research + ReAct fallback** — elegido.

## Decisiones asociadas

- **Objetivo**: cobertura completa en tres patrones de Query (prioridad): (1) multi-Ticker, (2) Ticker + Market Data + narrativa, (5) follow-ups conversacionales. Queries temáticas sin Ticker claro quedan en ReAct en F24.
- **Activación**:
  - Si la Query actual resuelve ≥1 Ticker (`ticker_catalog.resolve_ticker_input`, cashtags) → **Parallel Research** directo (sin Research Plan).
  - Si no hay Tickers en el texto pero hay historial de Chat Session → **Research Plan** (LLM liviano, JSON) → **Parallel Research**.
  - En cualquier otro caso → **ReAct** actual (`create_react_agent`).
- **Research Plan**: una llamada barata (`RESEARCH_MODEL`, default `gpt-4o-mini`) devuelve plan estructurado (Tickers, dimensiones). Solo resuelve intención en follow-ups; no sintetiza ni genera Citations.
- **Bundle Parallel Research** (concurrente, determinístico):
  - `get_quotes` batcheado con todos los Tickers detectados (máx. 4).
  - `get_recent_signals` por Ticker, en paralelo.
  - `search_corpus(query, ticker)` por Ticker, en paralelo (`limit` acotado por env).
  - Si hay más de 4 Tickers, se cubren los 4 primeros resueltos; la síntesis aclara cobertura parcial.
- **Topología**: evolucionar `backend/services/research_agent.py` de ReAct único a `StateGraph` custom (router → parallel gather | react gather → synthesis). El contrato SSE del Chat Stream y la derivación de Citations desde hits de tools se mantienen (ADR-0006).
- **UI**: `ResearchStepLoader` muestra pasos individuales en estado `running` en paralelo (ej. *"NVDA · señales"*, *"AMD · corpus"*), no un único paso colapsado.
- **Feature flag**: `RESEARCH_PARALLEL_ENABLED=true|false` (default `false` hasta verificar F24). Requiere `RESEARCH_ENGINE=langgraph`.
- **Lenguaje canónico**: ver `CONTEXT.md` — **Research Agent**, **Research Plan**, **Parallel Research**.

## Consequences

- Más llamadas a tools por Query en el camino paralelo (hasta ~9 con 4 Tickers: 1 quotes + 4 signals + 4 search). Costo acotado por el tope de 4 Tickers y `limit` por búsqueda.
- El ReAct sigue disponible como fallback; regresiones en Queries abiertas se mitigan acotando el híbrido a patrones 1, 2 y 5.
- F25 puede extender el Research Plan a Queries temáticas sin Ticker si el costo del plan resulta aceptable.
- Implementación en feature **F24**; verificación con script dedicado y regresión de `verify_f18`.
