"""Core Service: ask RAG con Citations obligatorias."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Union

from backend.services.agent import format_agent_context, gather_agent_context
from backend.services.llm import (
    build_context,
    generate_answer,
    hits_to_citations,
    stream_answer,
)
from backend.services.retrieval import retrieve
from backend.services.types import AskResult, Citation

AskStreamChunk = Union[str, list[Citation]]


def ask(query: str) -> AskResult:
    """Responde una Query del Operator usando el agente (Corpus + Market Data)."""
    agent_context = gather_agent_context(query)
    context = format_agent_context(agent_context)

    if not agent_context.hits and "Sin datos" in context:
        return AskResult(
            answer="No encontré Signals ni Market Data relevantes para esta Query.",
            citations=[],
        )

    answer = generate_answer(context, query)
    citations: list[Citation] = hits_to_citations(agent_context.hits)
    return AskResult(answer=answer, citations=citations)


def ask_stream(query: str) -> Iterator[AskStreamChunk]:
    """Streamea tokens de respuesta y finaliza con la lista de Citations."""
    agent_context = gather_agent_context(query)
    context = format_agent_context(agent_context)

    if not agent_context.hits and "Sin datos" in context:
        yield "No encontré Signals ni Market Data relevantes para esta Query."
        yield []
        return

    citations = hits_to_citations(agent_context.hits)
    for token in stream_answer(context, query):
        yield token
    yield citations
