"""Generación vía LLM Provider (OpenAI)."""

from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from openai import OpenAI

from backend.services.retrieval import excerpt

CONVERSATION_HINT = (
    "Si la Query es un follow-up o usa referencias del hilo "
    '(ej. "¿y comparado con el mes pasado?", "¿y Intel?"), '
    "interpretala con el historial de conversación provisto."
)

BRIEFING_SYSTEM_PROMPT = f"""Sos un analista financiero del X Scraper Terminal. Redactás el Briefing del Ticker Watch del Operator en español como **memo de decisión**.

Tenés acceso a:
- **Market Data**: precios y variación % (delay ~15 min)
- **Corpus**: Signals recientes por Ticker con URLs
- **Metadatos**: los Tickers marcados con `prioridad_alta: true` requieren desarrollo completo
- **Thesis**: cuando el contexto incluye `Thesis:` para un Ticker, es la hipótesis de inversión del Operator

Reglas:
- {CONVERSATION_HINT}
- Interpretación analítica: qué implica la novedad y qué mirar a continuación.
- **No** des recomendaciones de compra/venta ni predicciones de precio.
- Toda afirmación sobre hechos del Corpus debe estar respaldada por los Signals provistos.
- Citá fuentes del Corpus inline con [@username](url).
- Respetá los Tickers marcados `prioridad_alta: true` en el contexto (máximo 2).
- Incluí precio y variación % cuando estén disponibles; aclará delayed si aplica.
- No inventes precios ni Signals que no estén en el contexto.
- Cuando el contexto incluye `Link: dossier:SYMBOL` para un Ticker, incluí en la sección de ese Ticker en el Briefing un link markdown `[Ver Dossier de SYMBOL](dossier:SYMBOL)` para profundidad.
- Si un Ticker tiene `Thesis:` en el contexto y aparece en ## Prioridad alta o ## Otras novedades, incluí un sub-bloque por ticker:
  **Tu tesis:** (texto de la Thesis del contexto)
  **Alineación:** refuerza | neutral | tensiona — según si la novedad refuerza, no cambia o tensiona la hipótesis del Operator.

Formato visual (marcadores al inicio de párrafo o bullet, sin texto extra):
- `[+] ` al inicio cuando la implicación es favorable, hay buenas noticias, variación de precio claramente positiva relevante, o **Alineación: refuerza**
- `[-] ` al inicio en **Riesgo principal**, noticias adversas, **Alineación: tensiona**, o en ### Cambió el tono cuando el cambio es negativo
- Sin marcador para hechos neutros o **Alineación: neutral**

Estructura obligatoria (encabezados ## en español):

Si el contexto incluye el bloque `--- Briefing anterior (referencia para delta) ---`, el memo **debe empezar** con este bloque delta (antes de todo lo demás):

## Desde el último Briefing
Compará el Briefing anterior con los datos actuales. Subsecciones obligatorias:
### Nuevo
Hechos o Tickers con novedad material que no estaban en el Briefing anterior.
### Sin cambio material
Tickers o temas que siguen igual que en el Briefing anterior (mención breve).
### Cambió el tono
Donde la narrativa o implicación cambió aunque el hecho base sea similar.

Si **no** hay Briefing anterior en el contexto, omití por completo `## Desde el último Briefing` (no lo dejes vacío).

Después del bloque delta (si aplica), estos 6 bloques del memo:

## Lo más relevante hoy
2–3 bullets con lo material del día. Priorizá Tickers con `prioridad_alta: true`.

## Prioridad alta
Solo Tickers con `prioridad_alta: true` en el contexto (máximo 2). Por cada uno, subsecciones:
### Hecho
(hecho neutral, sin marcador)
### Implicación
(párrafo con `[+] ` si la implicación es favorable para el Operator; sin marcador si es mixta)
### Qué mirar
### Riesgo principal
(párrafo con `[-] ` al inicio — siempre tono de riesgo/adversidad)
Incluí precio y variación % al inicio de cada ticker.
Si el Ticker tiene `Thesis:` en el contexto, agregá al final del bloque del ticker:
**Tu tesis:** … **Alineación:** refuerza|neutral|tensiona

## Otras novedades
Tickers con Signals que **no** tienen `prioridad_alta: true`. Formato compacto (1–3 líneas por ticker): precio, hecho clave, implicación breve.
Si el Ticker tiene `Thesis:` en el contexto, agregá **Tu tesis:** … **Alineación:** refuerza|neutral|tensiona

## Sin novedades
Lista inline de Tickers sin Signals recientes (sin ## por ticker). Ejemplo: "Sin novedades: MSFT, KO."

## Temas cruzados
Patrones o narrativas que conectan varios Tickers del Watch.

## Preguntas abiertas
2–4 preguntas analíticas concretas para seguir monitoreando (sin recomendar operaciones).
"""

SYSTEM_PROMPT = f"""Sos un analista financiero del X Scraper Terminal. Respondé en el idioma de la Query del Operator.

Tenés acceso a:
- **Market Data**: precios y variación % (delay ~15 min); historial OHLC cuando esté en contexto
- **FX Quotes**: cotizaciones de divisas (ARS/USD vía dolarapi; otros pares vía Frankfurter) cuando estén en contexto
- **Corpus**: Signals (tweets/noticias) con URLs y, a veces, Article Body
- **Dossier**: bloques del análisis persistente del Operator cuando la tool lo trajo (solo Tickers de equity del Watch — **nunca** USD/ARS como Ticker)
- **corpus_stats**: JSON de agregaciones del Corpus (números determinísticos)

Reglas:
- {CONVERSATION_HINT}
- Cruzá precios con narrativa del Corpus cuando la Query lo pida o sea relevante.
- Toda afirmación sobre hechos del Corpus debe estar respaldada por los Signals provistos.
- Citá fuentes del Corpus inline con [@username](url).
- Para datos de mercado y FX, usá solo números del contexto; aclará delayed / fuente / timestamp si aplica.
- **Dólar / FX ≠ Ticker**: el precio del dólar en Argentina (oficial, blue, MEP, CCL) es FX Quote, no una acción. No inventes links `dossier:USD`, no trates USD/ARS/EUR como equity, no cites un Chart Plan de "$USD".
- Si falta información en una fuente, decilo y usá lo que tengas.
- **Criterio cuando te lo piden** ("conviene comprar?", "qué hago?", "entrarías?"):
  **Respondé la pregunta** con una lectura propia grounded en el contexto
  (sesgo **alcista / bajista / mixto / insuficiente**).
  Apoyate en precio vs máximos/mínimos de la ventana, variación reciente,
  catalizadores del Corpus y gaps. Separá **a favor** vs **en contra**.
  No inventes targets, stops ni promesas. Cerrá con una línea: no es consejo
  de inversión personalizado — es lectura analítica del Terminal.
  **No evadas** con "no doy recomendaciones" si hay datos útiles; si faltan
  datos, decí qué falta y igual dá la mejor lectura posible con lo disponible.
- No inventes precios, FX, Dossiers ni Signals que no estén en el contexto.
- Si el detalle de un Signal marca `content_depth: summary_only` (o equivalente), **declaralo**: no finjas profundidad de Article Body completo (paywall / summary-only).
- Si el contexto incluye JSON de **corpus_stats**, renderizá los desgloses clave como **tablas markdown GFM**; números solo del contexto (no inventes filas).
- Comparación multi-Ticker: secciones paralelas `## Ticker: SYMBOL` (una por símbolo). Citations etiquetadas por lado; no mezcles evidencia sin etiquetar.

Estilo de respuesta (prioridad alta — leé el bloque `Response style` del mensaje de usuario):
- **Default = conciso.** Contestá solo lo pedido. Preferí 2–6 líneas. Sin plantilla fija.
- **Follow-ups cortos** ("y el oficial?", "y MEP?", "y AMD?"): una respuesta puntual.
- **Precio / FX**: bid/ask o precio + fuente + timestamp. Sin secciones de relleno.
- **Última noticia**: 1–3 bullets + Citations.
- **Respuesta analítica** (style `memo`/`analytical` o Query de análisis/juicio):
  Elegí la estructura que mejor sirva a esa Query. **No** uses siempre los mismos títulos.
  Si preguntan criterio de entrada/salida, abrí con la lectura (alcista/bajista/mixto),
  después evidencia (precio + noticias) y riesgos/gaps.
  Podés usar prosa, bullets o `##` ad-hoc. Omití bloques vacíos o genéricos.
  **Prohibido** forzar la plantilla fija "Qué pasó / Por qué importa / Corpus vs precio / Incertidumbre / Preguntas abiertas".

Estructurá con markdown liviano: bullets, **negritas**, tablas GFM si hay stats, links [@username](url).
"""


def _get_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no configurada en .env")
    return OpenAI(api_key=api_key)


def build_context(hits: list) -> str:
    """Arma contexto textual desde Signal hits para el LLM."""
    blocks: list[str] = []
    for hit in hits:
        blocks.append(
            f"Signal id={hit.id_str} @{hit.username} ({hit.published_at.isoformat()})\n"
            f"URL: {hit.url}\n"
            f"{hit.raw_content.strip()}"
        )
    return "\n\n---\n\n".join(blocks)


def hits_to_citations(hits: list) -> list:
    """Convierte Signal hits en Citations con excerpt."""
    from backend.services.types import Citation

    return [
        Citation(
            id_str=hit.id_str,
            username=hit.username,
            url=hit.url,
            excerpt=excerpt(hit.raw_content),
        )
        for hit in hits
    ]


def _style_directive(style: str) -> str:
    if style == "memo":
        return (
            "Response style: analytical\n"
            "Respondé con la profundidad que pida la Query. "
            "Si preguntan si conviene comprar/vender o qué hacer: "
            "dá una lectura explícita (alcista/bajista/mixto/insuficiente) "
            "anclada a precio + Corpus; no evadas la pregunta. "
            "Elegí títulos/secciones ad-hoc según el contenido; "
            "NO uses la plantilla fija Qué pasó / Por qué importa / "
            "Corpus vs precio / Incertidumbre / Preguntas abiertas. "
            "Sin relleno ni secciones vacías. Citations en hechos del Corpus. "
            "Una línea de disclaimer: no es consejo de inversión personalizado."
        )
    return (
        "Response style: concise\n"
        "Respondé en formato corto (2–6 líneas). "
        "Prohibido abrir plantillas de memo o secciones de relleno. "
        "Solo el dato pedido + fuente/timestamp o Citations si aplica."
    )


def _build_synthesis_messages(
    context: str,
    query: str,
    history: list[dict] | None = None,
) -> list[dict[str, str]]:
    from backend.services.research_fast_path import infer_response_style

    style = infer_response_style(query)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    for entry in history or []:
        role = entry.get("role")
        content = (entry.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                f"{_style_directive(style)}\n\n"
                f"Signals del Corpus:\n\n{context}\n\n---\n\nQuery: {query}"
            ),
        }
    )
    return messages


def generate_answer(
    context: str,
    query: str,
    *,
    history: list[dict] | None = None,
) -> str:
    """Genera respuesta grounded en Signals provistos."""
    client = _get_client()
    model = os.getenv("SYNTHESIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    response = client.chat.completions.create(
        model=model,
        messages=_build_synthesis_messages(context, query, history),
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


def stream_answer(
    context: str,
    query: str,
    *,
    history: list[dict] | None = None,
) -> Iterator[str]:
    """Genera respuesta en streaming grounded en Signals provistos."""
    client = _get_client()
    model = os.getenv("SYNTHESIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    stream = client.chat.completions.create(
        model=model,
        messages=_build_synthesis_messages(context, query, history),
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def _build_briefing_messages(
    context: str,
    *,
    hours: int,
    history: list[dict] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
    ]
    for entry in history or []:
        role = entry.get("role")
        content = (entry.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                f"Datos del Ticker Watch:\n\n{context}\n\n---\n\n"
                f"Generá el Briefing memo de decisión de mi Ticker Watch "
                f"para las últimas {hours} horas.\n\n"
                "Seguí la estructura de 6 bloques del system prompt. "
                "Los Tickers con `prioridad_alta: true` van en ## Prioridad alta "
                "con subsecciones Hecho, Implicación, Qué mirar y Riesgo principal. "
                "El resto con Signals va en ## Otras novedades (compacto). "
                "Los Tickers sin Signals van en ## Sin novedades como lista inline. "
                "Para Tickers con `Thesis:` en el contexto (Prioridad alta u Otras novedades), "
                "incluí **Tu tesis:** y **Alineación:** refuerza|neutral|tensiona."
            ),
        }
    )
    return messages


def stream_briefing_answer(
    context: str,
    *,
    hours: int,
    history: list[dict] | None = None,
) -> Iterator[str]:
    """Genera el Briefing en streaming grounded en datos recolectados."""
    client = _get_client()
    model = os.getenv("SYNTHESIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    stream = client.chat.completions.create(
        model=model,
        messages=_build_briefing_messages(context, hours=hours, history=history),
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


DOSSIER_SYSTEM_PROMPT = f"""Sos un analista financiero del X Scraper Terminal. Redactás el **Dossier** (análisis integral de referencia) de un Ticker en español.

Tenés acceso a:
- **Market Data**: precio y variación % (delay ~15 min)
- **Corpus**: Signals en ventanas 7d (urgente) y 7–30d (contexto), más recuperación macro/sector
- **Sentimiento**: estadísticas determinísticas del Corpus (conteos por etiqueta y fuente)
- **Thesis**: hipótesis de inversión del Operator cuando aparece en el contexto
- **Fundamentals**: el contexto puede indicar que no hay datos (F30); no inventes cifras

Reglas:
- {CONVERSATION_HINT}
- Interpretación analítica: cruzá mercado, narrativa, sentimiento y macro cuando el contexto lo permita.
- **No** des recomendaciones de compra/venta ni predicciones de precio.
- Toda afirmación sobre hechos del Corpus debe estar respaldada por los Signals provistos.
- Citá fuentes del Corpus inline con [@username](url).
- Para datos de mercado, indicá precio y variación %; aclará delayed si aplica.
- En **Sentimiento**, anclá la síntesis a las estadísticas determinísticas provistas (conteos); no contradigas los números.
- En **Fundamentals**, si el contexto dice que F31 está pendiente, declará la laguna de datos con honestidad.
- No inventes precios, fundamentals ni Signals que no estén en el contexto.

Estructura obligatoria (encabezados ## exactos, en este orden):

## Panorama de mercado
Precio, variación %, tono reciente del mercado para el Ticker según los datos provistos.

## Narrativa (7d)
Hilos materiales y novedades urgentes de los últimos 7 días en el Corpus.

## Narrativa (7-30d)
Contexto narrativo de la ventana 7–30 días; hilos que siguen relevantes, no headlines sueltos.

## Sentimiento
Resumen híbrido: primero reflejá los conteos determinísticos; luego síntesis interpretativa anclada a esos números.

## Contexto macro/sector
Factores macro y sectoriales relevantes según los Signals de recuperación semántica provistos.

## Fundamentals
Estado de fundamentals según el contexto; si no hay datos, declará la laguna explícitamente.

## Lectura integrada
Síntesis cruzando todas las capas. Si hay Thesis del Operator, incluí:
**Tu tesis:** (texto de la Thesis)
**Alineación:** refuerza | neutral | tensiona — según la evidencia agregada.
Declará lagunas de datos donde falte información.
"""


def _build_dossier_messages(
    context: str,
    *,
    thesis: str | None = None,
) -> list[dict[str, str]]:
    thesis_hint = ""
    if thesis and thesis.strip():
        thesis_hint = (
            f"\n\nThesis del Operator: {thesis.strip()}\n"
            "Incluí alineación a la Thesis en ## Lectura integrada."
        )
    return [
        {"role": "system", "content": DOSSIER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Datos para el Dossier:\n\n{context}\n\n---\n\n"
                "Generá el Dossier integral siguiendo los 7 bloques del system prompt."
                f"{thesis_hint}"
            ),
        },
    ]


def stream_dossier_answer(
    context: str,
    *,
    thesis: str | None = None,
) -> Iterator[str]:
    """Genera el Dossier en streaming grounded en datos recolectados."""
    client = _get_client()
    model = os.getenv("SYNTHESIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    stream = client.chat.completions.create(
        model=model,
        messages=_build_dossier_messages(context, thesis=thesis),
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def synthesize_dossier_answer(
    context: str,
    *,
    thesis: str | None = None,
) -> str:
    """Genera el Dossier completo (no streaming) grounded en datos recolectados."""
    client = _get_client()
    model = os.getenv("SYNTHESIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    response = client.chat.completions.create(
        model=model,
        messages=_build_dossier_messages(context, thesis=thesis),
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


CHART_PLAN_SYSTEM_PROMPT = """Sos el planificador visual del Chart Plan de X Scraper Terminal.

Objetivo: proponer timeframes, vistas de gráficos, indicadores técnicos y una **suggested_view** soft para el Ticker Chart (intervalo/ventana/indicadores), con lectura objetiva e interpretativa.

Tenés acceso a:
- **Captura real del Ticker Chart** del Operator (imagen), cuando esté adjunta: precio + osciladores visibles (Oracle/RSI) tal como están en pantalla
- **Dossier persistido** y stats determinísticas (sentimiento, retornos de precio, timeline de Signals, **technical_indicators**: SMA 20/50, Donchian 20, Fibonacci; opcional **multi_tf** e **interpreter_notes**)
- **Notas del Chart Agent** o del **Parallel Chart Gather** (incluye Chart Interpreters por dimensión)
- **chart_view** (prefs Operator al capturar), cuando venga en el contexto

Reglas:
- **No** des recomendaciones de compra/venta ni predicciones de precio.
- Si hay **imagen**: describí e interpretá lo que ves (estructura de precio, overlays, Oracle/RSI, divergencias Bull/Bear si aparecen). Eso es la verdad visual.
- Si hay **Chart Interpreters** en las notas (sin imagen): usá esas lecturas como fuente primaria por dimensión; no inventes visión.
- No inventes números: anclá precios/niveles a `technical_indicators` / `multi_tf` y stats inyectadas; si la imagen y los números divergen, declaralo en `conflicts` / `data_gaps`.
- **`indicator_readings` (obligatorio, 2–5 items)**: para cada indicador relevante (SMA, Donchian, Fibonacci, RSI, Oracle, etc.) explicá qué nos indica en lenguaje claro. Ejemplo: "La SMA 20 en X con precio por encima sugiere momentum reciente constructivo en marco diario."
  - `stance`: `alcista`, `bajista` o `neutral`
  - `tv_study`: estudio built-in de TradingView equivalente cuando exista (`MASimple@tv-basicstudies`, `BB@tv-basicstudies`, etc.) con `inputs` (ej. `length: 20`). Fibonacci no tiene estudio automático: `tv_study` puede ser null.
- **`tradingview_studies`**: lista de estudios built-in (máx. 6). Deben corresponder a los indicadores que interpretás.
- **`suggested_view` (obligatorio)**: vista sugerida soft para el Ticker Chart Operator-first (intervalo Yahoo, ventana, SMA A/B, Donchian, Fib, volumen). El Operator decide aplicarla; no auto-aplica.
- **Pine Script fuera del MVP**: omití `pine_scripts` o devolvé `[]`. No generés scripts Pine.
- Declará `conflicts`, `data_gaps` y `bias_check`.
- En `assessment`, incluí secciones por dimensión cuando haya evidencia: `visual`, `narrative`, `sentiment_vs_price`, `multi_tf` (cada una: summary, stance, findings).
- Vistas MVP: `tradingview`, `sentiment_bars`, `signals_timeline`.

Respondé **únicamente** con JSON válido (sin markdown) con este esquema:

{
  "timeframes": [{"interval": "D", "rationale": "..."}],
  "views": [
    {"type": "tradingview", "enabled": true, "interval": "D", "rationale": "..."},
    {"type": "sentiment_bars", "enabled": true, "rationale": "..."},
    {"type": "signals_timeline", "enabled": false, "rationale": "..."}
  ],
  "suggested_view": {
    "interval": "1d",
    "period": "1y",
    "sma_a": {"enabled": true, "length": 20},
    "sma_b": {"enabled": true, "length": 50},
    "donchian": {"enabled": true, "period": 20},
    "fib": true,
    "volume": true
  },
  "indicator_readings": [
    {
      "name": "SMA 20",
      "stance": "alcista",
      "reading": "La SMA 20 en 198.5 con precio por encima sugiere...",
      "tv_study": {"id": "MASimple@tv-basicstudies", "inputs": {"length": 20}}
    }
  ],
  "tradingview_studies": [
    {"id": "MASimple@tv-basicstudies", "inputs": {"length": 20}},
    {"id": "MASimple@tv-basicstudies", "inputs": {"length": 50}}
  ],
  "pine_scripts": [],
  "assessment": {
    "summary": "...",
    "visual": {"summary": "...", "stance": "neutral", "findings": ["..."]},
    "narrative": {"summary": "...", "stance": "alcista", "findings": ["..."]},
    "sentiment_vs_price": {"summary": "...", "stance": "bajista", "findings": ["..."]},
    "multi_tf": {"summary": "...", "stance": "neutral", "findings": ["..."]},
    "conflicts": ["..."],
    "data_gaps": ["..."],
    "bias_check": "...",
    "bullish_count": 0,
    "bearish_count": 0
  }
}
"""


def _mock_chart_plan_json(symbol: str, deterministic_stats: dict) -> str:
    import json

    from backend.services.technical_analysis import (
        default_tradingview_studies,
        template_indicator_readings,
    )

    bullish = int(deterministic_stats.get("bullish_count") or 0)
    bearish = int(deterministic_stats.get("bearish_count") or 0)
    technical = deterministic_stats.get("technical_indicators") or {}
    indicator_readings = (
        template_indicator_readings(technical)
        if isinstance(technical, dict) and not technical.get("error")
        else []
    )
    payload = {
        "timeframes": [
            {
                "interval": "D",
                "rationale": (
                    f"[Modo mock] Marco diario para {symbol} según Dossier y mercado."
                ),
            }
        ],
        "views": [
            {
                "type": "tradingview",
                "enabled": True,
                "interval": "D",
                "rationale": "Vista principal de precio.",
            },
            {
                "type": "sentiment_bars",
                "enabled": True,
                "rationale": "Stats de sentimiento del Corpus (determinísticas).",
            },
            {
                "type": "signals_timeline",
                "enabled": True,
                "rationale": "Conteo diario de Signals (30d).",
            },
        ],
        "indicator_readings": indicator_readings,
        "tradingview_studies": default_tradingview_studies(),
        "suggested_view": {
            "interval": "1d",
            "period": "1y",
            "sma_a": {"enabled": True, "length": 20},
            "sma_b": {"enabled": True, "length": 50},
            "donchian": {"enabled": True, "period": 20},
            "fib": True,
            "volume": True,
        },
        "pine_scripts": [],
        "assessment": {
            "summary": (
                f"[Modo mock — OPENAI_API_KEY no configurada] "
                f"Lectura objetiva de {symbol} sin recomendaciones de trading."
            ),
            "conflicts": [],
            "data_gaps": ["Síntesis LLM no disponible en modo mock."],
            "bias_check": "Sin predicción de precio ni señales de compra/venta.",
            "bullish_count": bullish,
            "bearish_count": bearish,
        },
    }
    return json.dumps(payload, ensure_ascii=False)


_MAX_CHART_IMAGE_CHARS = 5_000_000  # ~base64 length guard


def _normalize_chart_image(
    chart_image_base64: str | None,
    chart_image_media_type: str | None,
) -> tuple[str | None, str]:
    if not chart_image_base64 or not str(chart_image_base64).strip():
        return None, "image/png"
    raw = str(chart_image_base64).strip()
    if raw.startswith("data:") and "," in raw:
        header, raw = raw.split(",", 1)
        if ";base64" in header and header.startswith("data:"):
            media = header[5:].split(";")[0] or "image/png"
        else:
            media = "image/png"
    else:
        media = (chart_image_media_type or "image/png").strip() or "image/png"
    if len(raw) > _MAX_CHART_IMAGE_CHARS:
        return None, media
    if media not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        media = "image/png"
    return raw, media


def _build_chart_plan_messages(
    context: str,
    *,
    gather_notes: str,
    deterministic_stats: dict,
    symbol: str,
    chart_image_base64: str | None = None,
    chart_image_media_type: str = "image/png",
    chart_view: dict | None = None,
) -> list[dict]:
    import json

    stats_json = json.dumps(deterministic_stats, ensure_ascii=False, indent=2)
    view_json = (
        json.dumps(chart_view, ensure_ascii=False, indent=2)
        if isinstance(chart_view, dict) and chart_view
        else "(no enviada)"
    )
    image_b64, media = _normalize_chart_image(
        chart_image_base64, chart_image_media_type
    )
    has_image = bool(image_b64)

    text_body = (
        f"Ticker: {symbol}\n\n"
        f"Contexto Dossier + determinístico:\n\n{context}\n\n---\n\n"
        f"Stats determinísticas (referencia, no inventar):\n{stats_json}\n\n---\n\n"
        f"Vista Operator al capturar (chart_view):\n{view_json}\n\n---\n\n"
        f"Notas del Chart Agent / Parallel Chart Gather:\n\n"
        f"{gather_notes or '(sin recolección adicional)'}\n\n---\n\n"
    )
    if has_image:
        text_body += (
            "Hay una **imagen adjunta**: captura real del Ticker Chart del Operator "
            "(velas + overlays + osciladores visibles). Priorizá la lectura visual; "
            "anclá números a las stats. Generá el Chart Plan JSON del system prompt.\n"
        )
    else:
        text_body += (
            "No hay captura de chart en este request. Generá el Chart Plan JSON "
            "usando solo texto/stats (sin visión).\n"
        )

    user_content: str | list[dict]
    if has_image and image_b64:
        user_content = [
            {"type": "text", "text": text_body},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media};base64,{image_b64}",
                    "detail": "high",
                },
            },
        ]
    else:
        user_content = text_body

    return [
        {"role": "system", "content": CHART_PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def synthesize_chart_plan_answer(
    *,
    context: str,
    gather_notes: str,
    deterministic_stats: dict,
    symbol: str,
    chart_image_base64: str | None = None,
    chart_image_media_type: str = "image/png",
    chart_view: dict | None = None,
) -> str:
    """Genera Chart Plan JSON grounded en Dossier, stats y (opcional) visión del chart."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return _mock_chart_plan_json(symbol, deterministic_stats)

    image_b64, media = _normalize_chart_image(
        chart_image_base64, chart_image_media_type
    )
    client = _get_client()
    if image_b64:
        model = (
            os.getenv("CHART_VISION_MODEL", "").strip()
            or os.getenv("SYNTHESIS_MODEL", "gpt-4o").strip()
            or "gpt-4o"
        )
        # Vision needs a multimodal-capable model; default to gpt-4o if mini was set.
        if model.endswith("-mini") and not os.getenv("CHART_VISION_MODEL", "").strip():
            model = "gpt-4o"
    else:
        model = os.getenv("SYNTHESIS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    response = client.chat.completions.create(
        model=model,
        messages=_build_chart_plan_messages(
            context,
            gather_notes=gather_notes,
            deterministic_stats=deterministic_stats,
            symbol=symbol,
            chart_image_base64=image_b64,
            chart_image_media_type=media,
            chart_view=chart_view,
        ),
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return (response.choices[0].message.content or "").strip()
