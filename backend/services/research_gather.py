"""Contexto reunido por el Research Agent y registro de resultados de tools."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.services.chat_history import prepare_chat_history
from backend.services.research_steps import ResearchStepEvent
from backend.services.retrieval import retrieve
from backend.services.types import SignalHit


@dataclass
class ResearchContext:
    """Contexto reunido por el agente para la síntesis final."""

    query: str
    hits: list[SignalHit] = field(default_factory=list)
    market_sections: list[str] = field(default_factory=list)
    corpus_sections: list[str] = field(default_factory=list)
    dossier_sections: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)


def record_tool_result(
    context: ResearchContext,
    tool_name: str,
    arguments: dict[str, Any],
    result: str,
    hits: list[SignalHit],
) -> None:
    context.hits.extend(hits)

    if tool_name == "search_corpus":
        label = f"search_corpus(query={arguments.get('query')!r}"
        if arguments.get("ticker"):
            label += f", ticker={arguments.get('ticker')!r}"
        if arguments.get("since_hours"):
            label += f", since_hours={arguments.get('since_hours')}"
        if arguments.get("source_type"):
            label += f", source_type={arguments.get('source_type')!r}"
        if arguments.get("min_relevance") is not None:
            label += f", min_relevance={arguments.get('min_relevance')}"
        if arguments.get("limit"):
            label += f", limit={arguments.get('limit')}"
        label += ")"
        context.corpus_sections.append(f"### {label}\n{result}")

    elif tool_name == "get_recent_signals":
        parts: list[str] = []
        if arguments.get("ticker"):
            parts.append(f"ticker={arguments.get('ticker')!r}")
        if arguments.get("source_type"):
            parts.append(f"source_type={arguments.get('source_type')!r}")
        if arguments.get("hours"):
            parts.append(f"hours={arguments.get('hours')}")
        if arguments.get("limit"):
            parts.append(f"limit={arguments.get('limit')}")
        label = f"get_recent_signals({', '.join(parts)})"
        context.corpus_sections.append(f"### {label}\n{result}")

    elif tool_name == "get_signal_detail":
        parts = []
        if arguments.get("id_str"):
            parts.append(f"id_str={arguments.get('id_str')!r}")
        if arguments.get("signal_id"):
            parts.append(f"signal_id={arguments.get('signal_id')!r}")
        label = f"get_signal_detail({', '.join(parts) or ''})"
        context.corpus_sections.append(f"### {label}\n{result}")

    elif tool_name == "corpus_stats":
        parts = []
        for key in ("ticker", "source_type", "hours", "group_by"):
            if arguments.get(key) is not None:
                parts.append(f"{key}={arguments.get(key)!r}")
        label = f"corpus_stats({', '.join(parts) or ''})"
        context.corpus_sections.append(
            f"### {label}\n"
            "<!-- Usar estos números en tablas markdown GFM; no inventar filas -->\n"
            f"{result}"
        )

    elif tool_name == "get_price_history":
        parts = []
        if arguments.get("symbol"):
            parts.append(f"symbol={arguments.get('symbol')!r}")
        if arguments.get("period"):
            parts.append(f"period={arguments.get('period')!r}")
        label = f"get_price_history({', '.join(parts) or ''})"
        context.market_sections.append(f"### {label}\n{result}")
        from backend.services.tools import build_price_chart_artifact

        artifact = build_price_chart_artifact(result)
        if artifact:
            context.artifacts.append(artifact)

    elif tool_name == "get_dossier":
        parts = []
        if arguments.get("symbol"):
            parts.append(f"symbol={arguments.get('symbol')!r}")
        label = f"get_dossier({', '.join(parts) or ''})"
        context.dossier_sections.append(f"### {label}\n{result}")

    elif tool_name == "get_fx_quotes":
        parts = []
        for key in ("scope", "base", "quote", "pairs"):
            if arguments.get(key) is not None:
                parts.append(f"{key}={arguments.get(key)!r}")
        label = f"get_fx_quotes({', '.join(parts) or ''})"
        context.market_sections.append(f"### {label}\n{result}")

    elif tool_name in {"get_quotes", "get_watchlist_quotes"}:
        label = (
            "get_watchlist_quotes()"
            if tool_name == "get_watchlist_quotes"
            else f"get_quotes(symbols={arguments.get('symbols')})"
        )
        context.market_sections.append(f"### {label}\n{result}")


def _load_tools_module():
    from backend.services import tools as tools_module

    return tools_module


def finalize_research_context(
    context: ResearchContext,
    query: str,
    *,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> ResearchContext:
    if not context.hits:
        if on_step:
            on_step(
                ResearchStepEvent(
                    tool="search_corpus",
                    label="Búsqueda de respaldo en el Corpus",
                    status="running",
                )
            )
        fallback_hits = retrieve(query, limit=10)
        context.hits.extend(fallback_hits)
        if fallback_hits:
            tools_module = _load_tools_module()
            context.corpus_sections.append(
                "### search_corpus (fallback)\n"
                + tools_module._format_hits_for_tool(fallback_hits)
            )
        if on_step:
            on_step(
                ResearchStepEvent(
                    tool="search_corpus",
                    label="Búsqueda de respaldo en el Corpus",
                    status="done",
                )
            )

    context.hits = _load_tools_module().dedupe_hits(context.hits)
    return context


def parallel_research_enabled() -> bool:
    raw = os.getenv("RESEARCH_PARALLEL_ENABLED", "false").strip().lower()
    if raw not in {"1", "true", "yes", "on"}:
        return False
    engine = os.getenv("RESEARCH_ENGINE", "legacy").strip().lower()
    return engine == "langgraph"


def route_research_path(
    query: str,
    history: list[dict] | None = None,
) -> str:
    """Elige camino: parallel, plan_then_parallel o react."""
    from backend.services.ticker_extract import (
        extract_tickers_from_query,
        query_looks_thematic,
        should_use_parallel_research,
    )

    if not parallel_research_enabled():
        return "react"

    if should_use_parallel_research(query):
        return "parallel"

    if prepare_chat_history(history) and not query_looks_thematic(query):
        from backend.services.ticker_extract import query_looks_vague_followup

        if not query_looks_vague_followup(query):
            return "plan_then_parallel"

    return "react"


def resolve_parallel_tickers(
    query: str,
    history: list[dict] | None = None,
) -> tuple[str, list[str], Any | None]:
    """Resuelve ruta y Tickers (con Research Plan en follow-ups)."""
    from backend.services.research_plan import ResearchPlan, build_research_plan

    path = route_research_path(query, history)
    if path == "react":
        return path, [], None

    if path == "parallel":
        from backend.services.ticker_extract import extract_tickers_from_query

        tickers = extract_tickers_from_query(query)
        if not tickers:
            return "react", [], None
        return path, tickers, None

    plan = build_research_plan(query, history)
    if plan.tickers:
        return "plan_then_parallel", plan.tickers, plan
    return "react", [], plan
