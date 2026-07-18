---
status: accepted
---

# Ticker Chart Operator-first + Lightweight Charts

El Operator necesita explorar precio e indicadores en `/dossier` (y desde la Quote Strip) sin depender del Chart Agent. ADR-0010 definió el **Chart Plan** on-demand, pero la UI de precio evolucionó a un gráfico propio con auto-refresh; Recharts+SVG no escala bien a intervalos intradía ni a controles Operator-first. Se adopta un **Ticker Chart** interactivo, controlado por el Operator, renderizado con Lightweight Charts.

## Considered Options

### Control del gráfico
- **Agent-first** (analyze fija la vista) — rechazado: pelea con el uso exploratorio y con el auto-refresh ya existente.
- **Dos modos Explorar / Chart Plan** — rechazado: complejidad UX prematura.
- **Operator-first** — elegido: el Operator manda intervalo, ventana e indicadores; el Chart Agent sugiere e interpreta.

### Motor de render
- **Recharts + velas caseras** — rechazado: SVG frágil con muchas barras; zoom/pan pobres.
- **Embed TradingView Advanced** — rechazado: poco control, peor integración con lecturas del Chart Plan.
- **Apache ECharts** — rechazado: más genérico/pesado; Recharts ya cubre charts no-OHLC.
- **Lightweight Charts** — elegido: velas nativas, canvas performante, overlays/panes; indicadores los calculamos nosotros.

### Pine Script
- **Seguir generando 0–3 exports** — diferido: bajo valor relativo al Ticker Chart nativo.
- **Fuera del MVP** — elegido: ocultar generación/UI; reabrir si hace falta.

## Decisiones asociadas

- **Lenguaje**: **Ticker Chart** (Operator-first) vs **Chart Plan** (artefacto del Chart Agent). Evitar “timeframe” suelto → **intervalo** + **ventana**. Ver `CONTEXT.md`.
- **Superficies**: mismo Ticker Chart en `/dossier` y en el modal de la **Quote Strip**.
- **Presets**: chips combinados `1D·5m`, `5D·15m`, `1M·1h`, `3M·1d`, `1Y·1d` (default), `5Y·1wk` + modo **advanced** (intervalo y ventana explícitos, con límites Yahoo).
- **Indicadores MVP**: overlays en precio (2 SMA, Donchian, Fib), Volume (sub-pane del precio), RSI + **Oracle Oscillator** en pane separado debajo (no mezclar con precio). Oracle = híbrido ponderado %R/Laguerre/Stoch/RSI/DeMarker (recreación open de la arquitectura publicada; no el binario MQL5). **Todos OFF por defecto**; desplegable Ind. Expand a dialog grande.
- **Prefs**: `localStorage` global (browser), no Store.
- **Chart Agent**: tras analyze, **sugerencia soft** “Aplicar vista del Chart Plan”; no auto-aplica. Si la vista del Ticker Chart diverge, las `indicator_readings` se marcan **desactualizadas**.
- **Auto-refresh**: quote ~1 min; refetch de velas según intervalo; merge de precio solo en la **vela abierta** del intervalo actual.
- **Datos OHLC**: `GET /quotes/candles?interval=&period=` (backend / yfinance) canónico; fallback Next `/api/candles` (Yahoo). Mapeo crypto (`BTC`→`BTC-USD`, etc.) en ambos.
- **Relación con ADR-0010**: Chart Plan / Chart Agent se mantienen; se **supersede** la UI de precio vía TradingView embed / Recharts casero y el énfasis en Pine del MVP. Sentimiento/timeline del Chart Plan siguen en Recharts.

## Consequences

- Dependencia frontend: `lightweight-charts`.
- Ampliar API de velas (`interval` + `period`) y fallback Next.
- Refactor `TickerIndicatorChart` / modal Quote Strip → componente Ticker Chart compartido + toolbar (presets, advanced, indicadores).
- Chart Agent / síntesis: dejar de priorizar `pine_scripts` en MVP; opcionalmente emitir vista sugerida (intervalo/ventana/indicadores) para el CTA soft.
- Feature de implementación (p. ej. F34) + verificación de presets, prefs, refresh intradía y badge desactualizado.
