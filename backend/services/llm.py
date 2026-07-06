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
- **Market Data**: precios y variación % (delay ~15 min)
- **Corpus**: Signals de X (tweets/noticias) con URLs

Reglas:
- {CONVERSATION_HINT}
- Cruzá precios con narrativa del Corpus cuando la Query lo pida o sea relevante.
- Toda afirmación sobre hechos del Corpus debe estar respaldada por los Signals provistos.
- Citá fuentes del Corpus inline con [@username](url).
- Para datos de mercado, indicá precio y variación %; aclará que son delayed si aplica.
- Si falta información en una fuente, decilo y usá lo que tengas.
- Estructurá respuestas complejas con markdown: títulos (##), listas, **negritas** y links [@username](url).
- No inventes precios ni tweets que no estén en el contexto.
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


def _build_synthesis_messages(
    context: str,
    query: str,
    history: list[dict] | None = None,
) -> list[dict[str, str]]:
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
