# Grill: Operator Settings (F55) + Provenance no-Signal (F32)

Programa post-soak Paper Bot. Dos features independientes; **orden recomendado: F55 → F32**. Solo una `in_progress` a la vez.

Lenguaje canónico: `CONTEXT.md`. Stack MVP: sin Qdrant, OpenAI, monorepo plano.

---

## F55 — Operator Settings (persistidos)

### Problema

Hoy gran parte de las prefs viven en `localStorage` (Daily PnL TZ/lookback, filtros Feed, prefs Ticker Chart) o no existen. La tabla `operator_settings` (JSONB) ya está en Supabase (`002_operator_data.sql`) pero casi no se usa (Ticker Watch tiene tabla propia).

### User-visible behavior

El Operator abre **Settings** (desde Header o `/settings` mínimo) y persiste:

1. **Timezone** + lookback default del Daily PnL del Paper Bot  
2. **Filtros Signal Feed** (Mis tickers on/off, source/ticker draft opcional)  
3. **Ticker Chart prefs** (intervalo/periodo/indicadores ON) — soft sync con `localStorage` en MVP  

Al recargar otro browser/dispositivo (mismo login), esas prefs vuelven. Sin Settings, defaults actuales.

### Fuera de alcance F55

- Watchlist en `operator_settings` (ya es `ticker_watch`)  
- Layout multi-panel drag  
- Auth multi-Operator / teams  

### Forma de datos (MVP)

```json
{
  "bot_pnl": { "timeZone": "America/Argentina/Buenos_Aires", "lookbackDays": 30 },
  "feed_filters": { "watchOnly": false },
  "ticker_chart": { /* subset de TickerChartPrefs */ }
}
```

API:

- `GET /operator/settings` → settings JSON (+ defaults)  
- `PATCH /operator/settings` → merge shallow por clave top-level  

Repo: leer/escribir `operator_settings.settings` por `user_id` (mismo patrón que chat). Local Docker: fila por operator id de dev.

### Slices (tracer bullets)

| # | Slice | Tipo | Demo |
|---|--------|------|------|
| 1 | API GET/PATCH + repo + verify | AFK | curl merge `bot_pnl` |
| 2 | UI Settings: TZ + lookback; `/bot` lee/escribe settings | AFK | cambio TZ sobrevive reload |
| 3 | Feed: `watchOnly` hidrata desde settings | AFK | Mis tickers persiste |
| 4 | Chart prefs: load/save subset (opcional si 1–3 alcanzan) | AFK | prefs chart en settings |

### Verification (feature)

- `python -m backend.scripts.verify_f55_operator_settings => OK`  
- PATCH merge no pisa claves ajenas  
- UI Settings + `/bot` Daily PnL usa settings (no solo localStorage)  
- Mis tickers restaura `watchOnly` tras reload  

### Dependencies

- F9/F10 auth + `operator_settings` table  
- F54 Daily PnL (consume `bot_pnl`)  
- F51 Mis tickers (consume `feed_filters.watchOnly`)  

---

## F32 — Provenance para datos no-Signal

### Problema

Las **Citations** hoy apuntan a Signals del Corpus. Quotes, FX, fundamentals, stats de sentimiento y lecturas de Chart Plan aparecen en UI/chat **sin un contrato uniforme de “de dónde salió”** (fuente, delay, timestamp, N/A). ADR-0009 ya lo exige post-F52.

### User-visible behavior

Donde el Terminal muestre un hecho que **no** es un Signal:

1. Se ve una **Provenance** corta y legible (zinc/ámbar neutro, no clutter):  
   `Market Data · Finnhub · delay ~15m · 14:02`  
   `Fundamentals · yfinance · PE no disponible`  
   `FX · dolarapi · oficial`  
2. En Research Chat / Dossier / Chart Plan, los números anclados a Market Data o fundamentals llevan esa marca (chip o línea bajo el bloque).  
3. Las Citations de Corpus **no cambian** (siguen siendo Signal → Detail).

### Fuera de alcance F32

- Provenance on-chain / exchange fills del Paper Bot (venue paper ya dice “paper”)  
- Rediseño completo del Citation chip  
- Auditoría legal/compliance formal  

### Modelo (MVP)

Tipo canónico (backend + frontend), p. ej.:

```ts
type Provenance = {
  kind: "market_data" | "fundamentals" | "fx" | "corpus_stats" | "chart_plan";
  source: string;       // finnhub | yfinance | dolarapi | frankfurter | ...
  as_of?: string;       // ISO
  delay_label?: string; // "~15m"
  note?: string;        // "PE no disponible"
};
```

Surfaces mínimas:

1. Quote Strip / cashtag quote cards  
2. Dossier bloque fundamentals (+ market panorama si aplica)  
3. Research Chat: al citar precio/FX/fundamentals, adjuntar provenance en meta o footer del mensaje  

### Slices

| # | Slice | Tipo | Demo |
|---|--------|------|------|
| 1 | Tipo + helpers + attach en `fetch_quotes` / fundamentals / FX | AFK | verify shape |
| 2 | UI Dossier + Quote cards muestran provenance | AFK | chip visible |
| 3 | Research Chat / Briefing: footer provenance no-Signal | AFK | respuesta precio con chip |
| 4 | Chart Plan: provenance de lecturas basadas en Market Data | AFK | panel lecturas |

### Verification (feature)

- `python -m backend.scripts.verify_f32_provenance => OK`  
- Quote / fundamentals / FX responses incluyen provenance  
- UI: al menos Dossier fundamentals + una quote card  
- Citations Corpus intactas (regresión chat citation click)  

### Dependencies

- F7 Market Data, F52 Fundamentals, F45 FX, F30 Dossier  
- F18 Research Chat (surface)  

---

## Orden y handoff

1. **Soak Paper Bot** (en curso) — no bloquear F55.  
2. **F55** `in_progress` — Settings + bot PnL/feed prefs.  
3. **F32** `in_progress` — Provenance no-Signal.  
4. Si hace falta ADR nuevo: solo si F32 cambia el contrato de Citation (preferir **no**; Provenance es tipo hermano, no Citation).

### Definition of done (ambos)

- `user_visible_behavior` E2E  
- verification[] ejecutada + evidence[]  
- `CONTEXT.md` actualizado si el dominio crece (Provenance como término canónico en F32)  
