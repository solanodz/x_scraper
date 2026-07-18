---
status: accepted
---

# Dossier: análisis integral persistente + Briefing ejecutivo

El Operator necesita un análisis en el que pueda confiar — que cruce narrativa del Corpus, Market Data, sentimiento agregado y contexto macro/sector, no solo un resumen de noticias recientes ni una reacción a un Signal aislado. El **Briefing** (ADR-0007) cubre el memo ejecutivo del día pero su materia prima sigue siendo sobre todo Signals de la ventana corta + precio. Se adopta un segundo artefacto: el **Dossier**, análisis integral persistente por Ticker del Ticker Watch, consumido por el Briefing y mostrado en Signal Detail.

## Considered Options

- **Ampliar solo el Briefing** (ventana más larga, más bloques en el mismo memo) — rechazado: mezcla resumen del día con informe de referencia; cada Briefing regeneraría todo el análisis profundo (costo, pérdida de historial estable).
- **Dossier solo en Research Chat** (sesión por ticker) — rechazado: confunde artefacto de referencia con conversación; versionado y UX de confianza peores.
- **Dossier en ruta/panel separado del layout** — rechazado para MVP: fragmenta la Terminal; Signal Detail ya es el panel de detalle.
- **Dossier persistente + Briefing ejecutivo que lo consume** — elegido (modelo C del diseño).

## Decisiones asociadas

- **Briefing** = memo ejecutivo on-demand (novedad del día, delta vs Briefing anterior, prioridad alta). **Dossier** = análisis integral por Ticker, artefacto de referencia.
- **Estructura del Dossier** (seis bloques): (1) Panorama de mercado, (2) Narrativa del Corpus en dos subcapas — últimos 7d (urgente) y 7–30d (contexto), (3) Sentimiento del Corpus — híbrido (stats determinísticas + síntesis LLM anclada), (4) Contexto macro/sector, (5) Fundamentals — placeholder honesto en F30 hasta F31, (6) Lectura integrada con alineación a **Thesis** y lagunas declaradas.
- **Refresh al Briefing**: antes de sintetizar el memo, refrescar Dossiers de Tickers en **prioridad alta** siempre; el resto solo si tuvieron Signals en la ventana del Briefing; los demás reutilizan la última versión (ADR-0007 prioridad_alta determinística se reusa).
- **Persistencia**: tabla `ticker_dossier_versions` por Operator + Ticker; cada refresh crea versión nueva; retención últimas **10 versiones** o **30 días** (lo que ocurra primero).
- **UI**: Signal Detail en **modo Dossier** al abrir desde Ticker Watch o link en el Briefing; modo Signal sin cambios al clicar un Signal del Feed. Research Chat profundiza un bloque del Dossier.
- **Generación**: servicio determinístico multi-capa (recolectar por bloque → síntesis por bloque o pasada final), mismo espíritu que ADR-0007; no ReAct para el Dossier completo.
- **Guardrails**: analítico, sin recomendaciones de compra/venta; Citations obligatorias en afirmaciones del Corpus; datos de mercado/fundamentals con provenance explícita (F32).
- **Lenguaje canónico**: `CONTEXT.md` — Dossier, Análisis integral, Briefing (ejecutivo).

## Consequences

- Nueva migración Store/Supabase para `ticker_dossier_versions`.
- `backend/services/briefing.py` gana fase previa de refresh + lectura de Dossiers antes de la síntesis del memo.
- Nuevo servicio `backend/services/dossier.py` (o equivalente) y endpoints `GET /dossier/{symbol}`, `POST /dossier/{symbol}/refresh` (on-demand).
- Signal Detail en frontend: toggle Signal | Dossier; historial de versiones.
- Costo de OpenAI sube en Briefing (refresh de 2+ Dossiers) — mitigable con política de refresh B y ventanas acotadas.
- **F31** añade fundamentals reales al bloque 5; **F32** unifica provenance/Citations para datos no-Signal.
- Implementación en feature **F30**; verificación con script dedicado y regresión Briefing (F20–F23).
