---
status: accepted
---

# FX Quotes: dolarapi + Frankfurter (separado de equity Quotes)

El Research Chat necesita cotizaciones de **FX** (dólar Argentina y pares comunes) sin mezclarlas con **Quotes** de equities (Finnhub / Alpha Vantage / yfinance). Se adopta una tool dedicada `get_fx_quotes` con providers gratuitos y cache corto.

## Considered Options

- **Reusar Finnhub/AV para FX** — rechazado: cobertura inconsistente para USD/ARS (blue, MEP, CCL, tarjeta); cuota compartida con equities.
- **Una sola API Argentina para todo** — rechazado: no cubre EUR/USD, BRL, etc. de forma estable.
- **dolarapi (ARS/USD) + Frankfurter (pares ECB)** — elegido: APIs públicas, sin API key en MVP, semántica clara por scope.

## Decisiones asociadas

- **Argentina USD**: `https://dolarapi.com` — al menos oficial y blue; MEP (`bolsa`), CCL (`contadoconliqui`) y tarjeta cuando la fuente los expone.
- **Otros pares**: Frankfurter (`https://api.frankfurter.app`) para EUR, USD, BRL, etc. (tasas ECB; no inventar spreads locales).
- **Tool**: `get_fx_quotes` con `scope` (`ars_usd` | `pair`) y opcional `base`/`quote` o `pairs`.
- **Separación de dominio**: **FX Quote** ≠ **Quote** de equities; no confundir con Tickers del Watch.
- **Honestidad**: si la fuente falla, error explícito; nunca inventar números. Respuesta incluye `source` + timestamp.
- **Cache**: ~5 minutos en proceso para no martillar las APIs.

## Consequences

- Módulo `backend/services/fx.py` + tool en `TOOL_DEFINITIONS`.
- CONTEXT.md: término **FX Quote**; lista de tools del Research Chat actualizada.
- Verificación offline: `backend/scripts/verify_f45_fx.py` (HTTP mockeado).
