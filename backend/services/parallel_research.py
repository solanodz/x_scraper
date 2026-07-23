"""Parallel Research determinístico por Ticker."""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from backend.services.research_gather import ResearchContext, record_tool_result
from backend.services.research_steps import ResearchStepEvent
from backend.services.tools import execute_tool


@dataclass(frozen=True)
class ParallelTask:
    """Una invocación de tool del bundle paralelo."""

    tool: str
    arguments: dict[str, Any]


@dataclass
class ParallelBundleResult:
    context: ResearchContext
    tasks: list[ParallelTask] = field(default_factory=list)


def build_parallel_tasks(tickers: list[str], query: str) -> list[ParallelTask]:
    """Arma tareas: get_quotes batcheado + signals + search_corpus por Ticker."""
    if not tickers:
        return []

    corpus_limit = _parallel_corpus_limit()
    tasks: list[ParallelTask] = [
        ParallelTask("get_quotes", {"symbols": list(tickers)}),
    ]
    for ticker in tickers:
        tasks.append(
            ParallelTask(
                "get_recent_signals",
                {"ticker": ticker, "hours": 168, "limit": 5},
            )
        )
        tasks.append(
            ParallelTask(
                "search_corpus",
                {"query": query, "ticker": ticker, "limit": corpus_limit},
            )
        )
    return tasks


def execute_parallel_bundle(
    tickers: list[str],
    query: str,
    *,
    execute_tool_fn: Callable[[str, dict[str, Any]], tuple[str, list]] | None = None,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> ParallelBundleResult:
    """Ejecuta el bundle en paralelo (inyectable para tests)."""
    runner = execute_tool_fn or execute_tool
    context = ResearchContext(query=query)
    tasks = build_parallel_tasks(tickers, query)

    def _label(task: ParallelTask) -> str:
        ticker = task.arguments.get("ticker")
        if ticker and task.tool == "get_recent_signals":
            return f"{ticker} · señales"
        if ticker and task.tool == "search_corpus":
            return f"{ticker} · corpus"
        if task.tool == "get_quotes":
            syms = task.arguments.get("symbols") or []
            return f"Cotizaciones ({', '.join(str(s) for s in syms)})"
        return task.tool

    def _run(task: ParallelTask) -> None:
        label = _label(task)
        if on_step:
            on_step(ResearchStepEvent(tool=task.tool, label=label, status="running"))
        result, hits = runner(task.tool, task.arguments)
        record_tool_result(context, task.tool, task.arguments, result, hits)
        if on_step:
            on_step(ResearchStepEvent(tool=task.tool, label=label, status="done"))

    if tasks:
        with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as pool:
            futures = [pool.submit(_run, task) for task in tasks]
            for future in as_completed(futures):
                future.result()

    from backend.services.tools import dedupe_hits

    context.hits = dedupe_hits(context.hits)
    return ParallelBundleResult(context=context, tasks=tasks)


def _parallel_corpus_limit() -> int:
    raw = os.getenv("RESEARCH_PARALLEL_CORPUS_LIMIT", "5").strip()
    try:
        return max(1, min(int(raw), 15))
    except ValueError:
        return 5


def _run_tool_step(
    context: ResearchContext,
    tool_name: str,
    arguments: dict,
    label: str,
    *,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
    operator_id: str | None = None,
) -> None:
    if on_step:
        on_step(ResearchStepEvent(tool=tool_name, label=label, status="running"))
    result, hits = execute_tool(tool_name, arguments, operator_id=operator_id)
    record_tool_result(context, tool_name, arguments, result, hits)
    if on_step:
        on_step(ResearchStepEvent(tool=tool_name, label=label, status="done"))


def run_parallel_research(
    context: ResearchContext,
    query: str,
    tickers: list[str],
    *,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
    operator_id: str | None = None,
) -> None:
    """Ejecuta el bundle Parallel Research: quotes + señales + corpus por Ticker."""
    if not tickers:
        return

    corpus_limit = _parallel_corpus_limit()
    quotes_label = f"Cotizaciones ({', '.join(tickers)})"

    tasks: list[tuple[str, dict, str]] = [
        ("get_quotes", {"symbols": list(tickers)}, quotes_label),
    ]

    for ticker in tickers:
        tasks.append(
            ("get_recent_signals", {"ticker": ticker}, f"{ticker} · señales")
        )
        tasks.append(
            (
                "search_corpus",
                {"query": query, "ticker": ticker, "limit": corpus_limit},
                f"{ticker} · corpus",
            )
        )

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(
                _run_tool_step,
                context,
                tool_name,
                arguments,
                label,
                on_step=on_step,
                operator_id=operator_id,
            ): tool_name
            for tool_name, arguments, label in tasks
        }
        for future in as_completed(futures):
            future.result()
