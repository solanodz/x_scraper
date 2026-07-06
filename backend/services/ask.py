"""Core Service: ask RAG con Citations obligatorias."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Union

from backend.services.agent import iter_gather_agent_context
from backend.services.llm import (
    hits_to_citations,
    stream_answer,
)
from backend.services.research_steps import GatherResult, ResearchStepEvent
from backend.services.types import AskResult, Citation

AskStreamChunk = Union[str, list[Citation], ResearchStepEvent]


def _research_engine() -> str:
    return os.getenv("RESEARCH_ENGINE", "legacy").strip().lower()


def _iter_gather(query: str, history: list[dict] | None = None):
    if _research_engine() == "langgraph":
        from backend.services.research_agent import iter_gather_research_context

        yield from iter_gather_research_context(query, history=history)
        return

    yield from iter_gather_agent_context(query)


def ask(
    query: str,
    *,
    history: list[dict] | None = None,
) -> AskResult:
    """Responde una Query del Operator usando el agente (Corpus + Market Data)."""
    from backend.services.llm import generate_answer

    context = ""
    hits: list = []
    for item in _iter_gather(query, history=history):
        if isinstance(item, GatherResult):
            context, hits = item.context, item.hits

    if not hits and "Sin datos" in context:
        return AskResult(
            answer="No encontré Signals ni Market Data relevantes para esta Query.",
            citations=[],
        )

    answer = generate_answer(context, query)
    citations: list[Citation] = hits_to_citations(hits)
    return AskResult(answer=answer, citations=citations)


def ask_stream(
    query: str,
    *,
    history: list[dict] | None = None,
) -> Iterator[AskStreamChunk]:
    """Streamea pasos del agente, tokens de respuesta y Citations finales."""
    context = ""
    hits: list = []

    for item in _iter_gather(query, history=history):
        if isinstance(item, ResearchStepEvent):
            yield item
        elif isinstance(item, GatherResult):
            context, hits = item.context, item.hits

    if not hits and "Sin datos" in context:
        yield "No encontré Signals ni Market Data relevantes para esta Query."
        yield []
        return

    yield ResearchStepEvent(
        tool="synthesis",
        label="Redactando respuesta…",
        status="running",
    )

    citations = hits_to_citations(hits)
    for token in stream_answer(context, query):
        yield token

    yield ResearchStepEvent(
        tool="synthesis",
        label="Redactando respuesta…",
        status="done",
    )
    yield citations
