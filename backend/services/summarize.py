"""Core Service: resumen por Ticker y ventana temporal."""

from __future__ import annotations

from backend.services.llm import build_context, generate_answer, hits_to_citations
from backend.services.retrieval import normalize_ticker, retrieve
from backend.services.types import AskResult, Citation


def summarize(ticker: str, hours: int = 24) -> AskResult:
    """Resume Signals de un Ticker en las últimas `hours` horas."""
    normalized = normalize_ticker(ticker)
    if not normalized:
        raise ValueError("Ticker requerido")

    query = f"Resumen de noticias y movimientos sobre ${normalized}"
    hits = retrieve(query, limit=10, ticker=normalized, since_hours=hours)

    if not hits:
        return AskResult(
            answer=f"No hay Signals recientes en el Corpus para ${normalized} en las últimas {hours}h.",
            citations=[],
        )

    context = build_context(hits)
    user_query = f"Resumen de ${normalized} en las últimas {hours} horas"
    answer = generate_answer(context, user_query)
    citations: list[Citation] = hits_to_citations(hits)
    return AskResult(answer=answer, citations=citations)
