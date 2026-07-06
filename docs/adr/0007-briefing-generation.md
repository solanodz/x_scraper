---
status: accepted
---

# Briefing: generación determinística sobre el Research Agent

El Briefing resume los Tickers del Ticker Watch del Operator: por cada Ticker con novedad, precio + Signals recientes + una interpretación "qué implica / qué mirar", grounded con Citations. Existe la tentación de generarlo con el Research Agent (LangGraph, ADR-0006) que ya orquesta tools y sintetiza respuestas. Se decide **no** hacerlo: el Briefing se arma con un servicio determinístico que recolecta datos por Ticker y hace una única pasada de síntesis grounded.

## Considered Options

- **Research Agent (LangGraph) con un prompt de Briefing** — rechazado: el agente ReAct decide qué tools llamar. Para un Briefing eso es un riesgo, no una ventaja: puede saltearse Tickers del Watch, gastar más tokens en planificación multi-ronda y producir orden/cobertura impredecibles. El Briefing tiene una obligación dura de cobertura (revisar todos los Tickers seguidos).
- **Servicio determinístico + síntesis única** — elegido: para cada Ticker del Ticker Watch se llaman directamente `get_recent_signals` (ventana default 24h) y `fetch_quotes`, sin planificación LLM. Los datos recolectados alimentan una sola pasada de síntesis grounded (reusa `stream_answer` + Citations) que escribe la interpretación por Ticker y ordena por relevancia.

## Decisiones asociadas

- **Cobertura garantizada**: la recolección itera el Ticker Watch en código, no vía LLM. Ningún Ticker seguido queda sin revisar.
- **Reuso de código**: `get_recent_signals`, `fetch_quotes`, `hits_to_citations` y la síntesis grounded ya existen; el servicio nuevo (`backend/services/briefing.py`) los orquesta.
- **El LLM solo interpreta**: la única llamada al modelo es la síntesis final, anclada en los Signals ya recolectados. Se preservan las Citations confiables (derivadas de los hits, no de lo que el modelo afirma).
- **Interpretación analítica**: el Briefing describe impacto probable y qué mirar; no da recomendaciones de compra/venta ni predice precios. Guardrail de decisión, no solo de estilo.
- **Entrega**: streaming SSE reusando el contrato del Chat Stream (pasos + tokens + Citations) y el `ResearchStepLoader` de F18. Se renderiza como mensaje del Research Chat, habilitando follow-up conversacional sobre el mismo hilo.
- **On-demand**: el Briefing se dispara a pedido (botón), no por cron. La generación programada/persistida y las notificaciones quedan para una feature posterior.

## Consequences

- La lógica del Briefing vive en su propio servicio, separada del Research Agent. Dos caminos de síntesis coexisten (chat libre vía agente; Briefing determinístico), ambos sobre las mismas funciones de datos y de Citations.
- Cambiar a generación vía agente más adelante implicaría reescribir el servicio; por eso se registra la decisión.
- El costo del Briefing es acotado y predecible (N recolecciones sin LLM + 1 síntesis), a cambio de menos flexibilidad que un agente que razona sobre qué mirar.
- La generación programada + persistida ("¿qué cambió vs ayer?") y las notificaciones push/email son extensiones naturales pero fuera de alcance de esta decisión.
