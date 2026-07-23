---
status: accepted
---

# Parallel Chart Gather para el Chart Plan

El Chart Agent (ADR-0010) recolecta con ReAct secuencial y luego sintetiza; con visión del Ticker Chart (post ADR-0011) el *Analizar gráficos* llega a ~5 minutos y profundiza poco por dimensión. Se adopta **Parallel Chart Gather**: gather concurrente + **Chart Interpreters** LLM en paralelo + un solo sintetizador. Misma filosofía de cobertura/latencia que Parallel Research (ADR-0008), scoped al Chart Plan — no son agentes LLM en competencia.

## Considered Options

- **Solo Parallel Gather determinístico (sin interpreters)** — rechazado: no entrega el “análisis más profundo” ni aprovecha la captura visual.
- **Varios agentes LLM autónomos que compiten/debaten** — rechazado (igual que ADR-0008): multiplica costo, contradicciones y complica un Chart Plan coherente.
- **Mantener ReAct + interpreters** — rechazado: el ReAct secuencial es el cuello de latencia.
- **Híbrido: Parallel Chart Gather + 4 Chart Interpreters + 1 síntesis; ReAct eliminado en ese camino** — elegido.

## Decisiones asociadas

- **Activación**: `CHART_PARALLEL_ENABLED` (default `false`); requiere `CHART_AGENT_ENABLED`. Con parallel off, el camino legacy ReAct puede permanecer hasta retirar tras verificación.
- **Gather concurrente (sin LLM)**: Market/TA stats, Corpus (`get_recent_signals` + `search_corpus`), sentimiento stats, excerpt de Dossier, captura PNG del Ticker Chart del Operator.
- **Chart Interpreters (4, en paralelo)**:
  1. Visión del Ticker Chart — `CHART_VISION_MODEL` / `gpt-4o`
  2. Narrativa Corpus — `gpt-4o-mini`
  3. Sentimiento vs precio — `gpt-4o-mini`
  4. TA multi-ventana — `gpt-4o-mini` sobre **`5d·15m`**, **`3mo·1d`**, **`1y·1d`**
- **Síntesis**: un solo modelo (`gpt-4o`) arma el Chart Plan; assessment enriquecido con secciones por dimensión (visual, narrativa, sentimiento↔precio, TA multi-ventana) + `conflicts` / `data_gaps` / `bias_check`.
- **Degradación**: lane o interpreter fallido → skip + `data_gaps`; sin captura → interpreter de visión omitido (resto sigue).
- **UI**: `ResearchStepLoader` (o equivalente) muestra pasos `running` en paralelo por lane/interpreter.
- **Lenguaje**: `CONTEXT.md` — **Parallel Chart Gather**, **Chart Interpreter**, **Chart Agent**, **Chart Plan**. Evitar “parallel agents”.

## Consequences

- Wall-clock ≈ max(interpreters) + síntesis (target orientativo 45–120s), no suma de rondas ReAct.
- Más llamadas LLM por analyze (4 + 1) pero acotadas y paralelas; costo > flujo texto-only, < ReAct largo + visión serial.
- Schema/UI del Chart Plan gana dimensiones en assessment; soft `suggested_view` se mantiene.
- Feature de implementación + verify dedicado; regresión `verify_f33` / camino legacy detrás del flag.
