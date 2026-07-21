---
status: accepted
---

# Chart Plan: Chart Agent on-demand en /dossier

Fase 2 del Dossier añade análisis visual y scripts Pine Script exportables. El Operator necesita vistas técnicas objetivas — timeframes, señales del Corpus alineadas en el tiempo, sentimiento — sin mezclarlas con el Refresh del Dossier textual (ADR-0009). Se adopta un artefacto aparte: el **Chart Plan**, generado on-demand por un **Chart Agent** autónomo pero acotado.

## Considered Options

- **Extender el Refresh del Dossier** (texto + gráficos + Pine en un solo flujo) — rechazado: rompe el contrato determinístico del Dossier, encarece cada Refresh y mezcla síntesis narrativa con decisión visual autónoma.
- **Chart Plan solo en Research Chat** — rechazado: no persistente ni acoplado a la pantalla `/dossier`; pierde versionado y UX de referencia por Ticker.
- **Pipeline fijo sin agente** (siempre mismos gráficos) — rechazado: no adapta timeframes ni omite Pine cuando no aporta; el producto pide criterio según situación del Ticker.
- **ReAct libre sin límite** — rechazado: costo impredecible y riesgo de loops; Parallel Research y Dossier ya demostraron valor de caminos acotados.
- **Chart Plan on-demand + Chart Agent ReAct acotado + panel dedicado** — elegido.

## Decisiones asociadas

- **Activación**: botón *Analizar gráficos* en `/dossier`; **no** corre al Refresh del Dossier textual.
- **Prerequisito**: existe al menos un Dossier para el Ticker (contexto mínimo: narrativa + `sentiment_stats`).
- **UI**: split horizontal en `/dossier` — Dossier texto (izquierda), **Chart Plan** (derecha): TradingView embed, gráficos propios, Pine, lectura objetiva.
- **Chart Agent**: ReAct acotado (LangGraph, ADR-0006) en el camino legacy; máximo de rounds configurable; tools sobre Market Data (`get_quotes`, `get_price_history`), Corpus (`get_recent_signals`, `search_corpus`, `corpus_stats`) y lectura del último Dossier. El camino preferido de latencia/profundidad es **Parallel Chart Gather** (ADR-0012).
- **Stats determinísticas** siempre inyectadas antes de la síntesis (sentimiento, retornos de precio, conteos); el LLM interpreta, no inventa números.
- **Visión del Ticker Chart real (post–ADR-0011)**: el frontend captura el stack de charts del Operator (PNG) y lo envía en `POST /chart-plan/{symbol}/analyze`; la síntesis usa modelo multimodal (`CHART_VISION_MODEL`, default `gpt-4o`) + stats. Sin captura → fallback texto+stats.
- **Salida JSON** persistida: timeframes, vistas (`tradingview`, `sentiment_bars`, `signals_timeline`), `pine_scripts` (0–3, opcional), `assessment` obligatorio (`conflicts`, `data_gaps`, `bias_check`).
- **Objetividad**: sin recomendaciones de compra/venta ni predicción de precio; debe declarar lecturas contradictorias y lagunas; Pine con `purpose` + `limitations`.
- **Pine Script**: artefacto exportable (copiar a TradingView); el embed **no** ejecuta Pine custom.
- **Persistencia**: tabla `ticker_chart_plan_versions` por Operator + Ticker; historial independiente del Dossier; retención últimas **10 versiones** o **30 días**.
- **UX ejecución**: SSE de pasos (`ResearchStepEvent`); Chart Plan se renderiza completo al finalizar.
- **Rollout**: flag `CHART_AGENT_ENABLED` (default `false`), mismo espíritu que `RESEARCH_PARALLEL_ENABLED`.
- **Lenguaje canónico**: `CONTEXT.md` — Chart Plan, Chart Agent.

## Consequences

- Nueva migración Store/Supabase `ticker_chart_plan_versions`.
- Nuevos módulos: `chart_plan_repo.py`, `chart_agent.py`, `chart_plan.py` (o equivalente), ruta `POST /chart-plan/{symbol}/analyze` (SSE) + GET latest/versions.
- Frontend: refactor `/dossier` a split; componentes `ChartPlanPanel`, gráficos Corpus (sentimiento, timeline), reutilizar `TickerChartModal` / `tradingview.ts` para embed con intervalo del agente.
- Dependencia de LangGraph + OpenAI; costo por ejecución acotado por rounds y flag.
- **F30** UI evoluciona: Dossier ya en `/dossier`; F33 completa el panel derecho.
- Implementación en feature **F33**; verificación `verify_f33.py` + regresión `verify_f30`.
