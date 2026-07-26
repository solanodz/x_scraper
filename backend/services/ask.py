"""Core Service: ask RAG con Citations obligatorias."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Union

from backend.services.agent import iter_gather_agent_context
from backend.services.chat_artifacts import ensure_price_chart_artifacts
from backend.services.chat_history import prepare_chat_history
from backend.services.llm import (
    hits_to_citations,
    stream_answer,
)
from backend.services.provenance import collect_provenances
from backend.services.research_steps import (
    ChatArtifact,
    GatherResult,
    ResearchAnswerMeta,
    ResearchStepEvent,
    context_mentions_summary_only,
)
from backend.services.types import AskResult, Citation

AskStreamChunk = Union[
    str,
    list[Citation],
    ResearchStepEvent,
    ChatArtifact,
    ResearchAnswerMeta,
]


def _research_engine() -> str:
    return os.getenv("RESEARCH_ENGINE", "legacy").strip().lower()


def _iter_text_tokens(text: str) -> Iterator[str]:
    """Parte texto en trozos chicos para SSE (UX de streaming)."""
    import re

    content = text or ""
    if not content:
        return
    # Palabras + whitespace / saltos de línea, para que el bubble crezca fluido.
    parts = re.findall(r"\S+\s*|\n+", content)
    if not parts:
        yield content
        return
    for part in parts:
        yield part


def _iter_gather(
    query: str,
    history: list[dict] | None = None,
    *,
    operator_id: str | None = None,
):
    prior = prepare_chat_history(history)
    from backend.services.research_fast_path import iter_fast_path_context

    fast_path_used = False
    for item in iter_fast_path_context(query, operator_id=operator_id):
        fast_path_used = True
        yield item
    if fast_path_used:
        return

    if _research_engine() == "langgraph":
        from backend.services.research_agent import iter_gather_research_context

        yield from iter_gather_research_context(
            query,
            history=prior,
            operator_id=operator_id,
        )
        return

    yield from iter_gather_agent_context(
        query,
        history=prior,
        operator_id=operator_id,
    )


def ask(
    query: str,
    *,
    history: list[dict] | None = None,
    operator_id: str | None = None,
) -> AskResult:
    """Responde una Query del Operator usando el agente (Corpus + Market Data)."""
    from backend.services.llm import generate_answer

    context = ""
    hits: list = []
    direct_answer: str | None = None
    for item in _iter_gather(query, history=history, operator_id=operator_id):
        if isinstance(item, GatherResult):
            context, hits = item.context, item.hits
            direct_answer = item.direct_answer

    if direct_answer:
        return AskResult(answer=direct_answer, citations=[])

    if not hits and "Sin datos" in context:
        return AskResult(
            answer="No encontré Signals ni Market Data relevantes para esta Query.",
            citations=[],
        )

    answer = generate_answer(context, query, history=prepare_chat_history(history))
    citations: list[Citation] = hits_to_citations(hits)
    return AskResult(answer=answer, citations=citations)


def ask_stream(
    query: str,
    *,
    history: list[dict] | None = None,
    operator_id: str | None = None,
) -> Iterator[AskStreamChunk]:
    """Streamea pasos del agente, tokens de respuesta, artifacts y Citations."""
    prior = prepare_chat_history(history)
    context = ""
    hits: list = []
    artifacts: list[dict] = []
    gather_provenances: list[dict] = []
    direct_answer: str | None = None
    answer_path = "research"
    summary_only = False

    for item in _iter_gather(query, history=history, operator_id=operator_id):
        if isinstance(item, ResearchStepEvent):
            yield item
        elif isinstance(item, GatherResult):
            context, hits = item.context, item.hits
            artifacts = list(item.artifacts or [])
            gather_provenances = list(item.provenances or [])
            direct_answer = item.direct_answer
            answer_path = item.path or "research"
            summary_only = bool(item.summary_only) or context_mentions_summary_only(
                context
            )

    if direct_answer:
        provenances = collect_provenances(gather_provenances)
        yield ResearchAnswerMeta(
            path=answer_path,
            summary_only=summary_only,
            provenances=tuple(provenances),
        )
        yield ResearchStepEvent(
            tool="synthesis",
            label="Redactando respuesta…",
            status="running",
        )
        for token in _iter_text_tokens(direct_answer):
            yield token
        yield ResearchStepEvent(
            tool="synthesis",
            label="Redactando respuesta…",
            status="done",
        )
        yield []
        return

    if not hits and "Sin datos" in context:
        yield ResearchAnswerMeta(path=answer_path, summary_only=summary_only)
        for token in _iter_text_tokens(
            "No encontré Signals ni Market Data relevantes para esta Query."
        ):
            yield token
        yield []
        return

    # Charts en paralelo con la síntesis: no bloquear time-to-first-token.
    from concurrent.futures import ThreadPoolExecutor

    seed_artifacts = list(artifacts)
    provenances = collect_provenances(gather_provenances, *seed_artifacts)
    yield ResearchAnswerMeta(
        path=answer_path,
        summary_only=summary_only,
        provenances=tuple(provenances),
    )

    for artifact_data in seed_artifacts:
        art_type = str(artifact_data.get("type") or "unknown")
        payload = {k: v for k, v in artifact_data.items() if k != "type"}
        yield ChatArtifact(type=art_type, data=payload)

    yield ResearchStepEvent(
        tool="synthesis",
        label="Redactando respuesta…",
        status="running",
    )

    citations = hits_to_citations(hits)
    emitted_keys = {
        (
            str(a.get("type") or ""),
            str(a.get("symbol") or "").upper(),
            str(a.get("period") or ""),
        )
        for a in seed_artifacts
    }

    with ThreadPoolExecutor(max_workers=1) as pool:
        chart_future = pool.submit(ensure_price_chart_artifacts, query, seed_artifacts)
        charts_emitted = False

        def _emit_pending_charts():
            nonlocal charts_emitted
            if charts_emitted or not chart_future.done():
                return
            charts_emitted = True
            for artifact_data in chart_future.result():
                key = (
                    str(artifact_data.get("type") or ""),
                    str(artifact_data.get("symbol") or "").upper(),
                    str(artifact_data.get("period") or ""),
                )
                if key in emitted_keys:
                    continue
                emitted_keys.add(key)
                art_type = str(artifact_data.get("type") or "unknown")
                payload = {
                    k: v for k, v in artifact_data.items() if k != "type"
                }
                yield ChatArtifact(type=art_type, data=payload)

        for token in stream_answer(context, query, history=prior):
            yield from _emit_pending_charts()
            yield token

        yield from _emit_pending_charts()
        if not charts_emitted:
            for artifact_data in chart_future.result():
                key = (
                    str(artifact_data.get("type") or ""),
                    str(artifact_data.get("symbol") or "").upper(),
                    str(artifact_data.get("period") or ""),
                )
                if key in emitted_keys:
                    continue
                emitted_keys.add(key)
                art_type = str(artifact_data.get("type") or "unknown")
                payload = {
                    k: v for k, v in artifact_data.items() if k != "type"
                }
                yield ChatArtifact(type=art_type, data=payload)

    yield ResearchStepEvent(
        tool="synthesis",
        label="Redactando respuesta…",
        status="done",
    )
    yield citations
