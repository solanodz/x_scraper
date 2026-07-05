"""Generación vía LLM Provider (OpenAI)."""

from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from openai import OpenAI

from backend.services.retrieval import excerpt

SYSTEM_PROMPT = """Sos un analista financiero del X Scraper Terminal. Respondé en el idioma de la Query del Operator.

Tenés acceso a:
- **Market Data**: precios y variación % (delay ~15 min)
- **Corpus**: Signals de X (tweets/noticias) con URLs

Reglas:
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


def generate_answer(context: str, query: str) -> str:
    """Genera respuesta grounded en Signals provistos."""
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Signals del Corpus:\n\n{context}\n\n---\n\nQuery: {query}",
            },
        ],
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


def stream_answer(context: str, query: str) -> Iterator[str]:
    """Genera respuesta en streaming grounded en Signals provistos."""
    client = _get_client()
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Signals del Corpus:\n\n{context}\n\n---\n\nQuery: {query}",
            },
        ],
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
