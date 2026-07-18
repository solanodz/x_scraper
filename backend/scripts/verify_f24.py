"""Verificación F24: Parallel Research + Research Plan (ADR-0008)."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from dotenv import load_dotenv

from backend.services.parallel_research import (
    ParallelTask,
    build_parallel_tasks,
    execute_parallel_bundle,
)
from backend.services.research_gather import (
    parallel_research_enabled,
    resolve_parallel_tickers,
    route_research_path,
)
from backend.services.research_plan import build_research_plan, parse_research_plan_json
from backend.services.ticker_extract import (
    extract_tickers_from_query,
    query_looks_thematic,
)


def _set_parallel_env(enabled: bool = True) -> None:
    os.environ["RESEARCH_ENGINE"] = "langgraph"
    os.environ["RESEARCH_PARALLEL_ENABLED"] = "true" if enabled else "false"
    os.environ.setdefault("RESEARCH_PARALLEL_MAX_TICKERS", "4")
    os.environ.setdefault("RESEARCH_PARALLEL_CORPUS_LIMIT", "5")


def main() -> int:
    print("== F24 verification: Parallel Research ==\n")
    load_dotenv()
    _set_parallel_env(True)

    print("1. extract_tickers_from_query (compará NVDA vs AMD)")
    tickers = extract_tickers_from_query("compará NVDA vs AMD")
    if tickers != ["NVDA", "AMD"]:
        print(f"   FAIL: expected ['NVDA', 'AMD'], got {tickers}")
        return 1
    print(f"   tickers: {tickers}")
    print("   PASS\n")

    print("2. extract_tickers_from_query (Intel → INTC)")
    intel = extract_tickers_from_query("¿Cómo está Intel hoy?")
    if intel != ["INTC"]:
        print(f"   FAIL: expected ['INTC'], got {intel}")
        return 1
    print(f"   tickers: {intel}")
    print("   PASS\n")

    print("3. max 4 tickers truncation")
    os.environ["RESEARCH_PARALLEL_MAX_TICKERS"] = "4"
    many = extract_tickers_from_query("NVDA AMD INTC MSFT AAPL GOOGL")
    if len(many) != 4:
        print(f"   FAIL: expected 4 tickers, got {len(many)}: {many}")
        return 1
    print(f"   tickers: {many}")
    print("   PASS\n")

    print("4. routing: tickers in query → parallel (no OpenAI)")
    path = route_research_path("compará NVDA vs AMD", history=None)
    if path != "parallel":
        print(f"   FAIL: expected parallel, got {path}")
        return 1
    resolved_path, resolved_tickers, _ = resolve_parallel_tickers(
        "compará NVDA vs AMD", history=None
    )
    if resolved_path != "parallel" or resolved_tickers != ["NVDA", "AMD"]:
        print(f"   FAIL: {resolved_path} {resolved_tickers}")
        return 1
    print(f"   path: {path}, tickers: {resolved_tickers}")
    print("   PASS\n")

    print("5. parallel bundle builds correct tasks (mock execute_tool)")
    captured: list[tuple[str, dict]] = []

    def _mock_execute(tool: str, arguments: dict):
        captured.append((tool, dict(arguments)))
        return "{}", []

    tasks = build_parallel_tasks(["NVDA", "AMD"], "compará NVDA vs AMD")
    expected_tools = {
        ("get_quotes", frozenset({"symbols"})),
        ("get_recent_signals", frozenset({"ticker", "hours", "limit"})),
        ("search_corpus", frozenset({"query", "ticker", "limit"})),
    }
    if len(tasks) != 5:
        print(f"   FAIL: expected 5 tasks, got {len(tasks)}")
        return 1
    quotes_tasks = [t for t in tasks if t.tool == "get_quotes"]
    if len(quotes_tasks) != 1 or quotes_tasks[0].arguments.get("symbols") != [
        "NVDA",
        "AMD",
    ]:
        print(f"   FAIL: batched quotes task wrong: {quotes_tasks}")
        return 1
    for task in tasks:
        keys = frozenset(task.arguments.keys())
        if task.tool not in {spec[0] for spec in expected_tools}:
            print(f"   FAIL: unexpected tool {task.tool}")
            return 1

    result = execute_parallel_bundle(
        ["NVDA", "AMD"],
        "compará NVDA vs AMD",
        execute_tool_fn=_mock_execute,
    )
    if len(captured) != 5:
        print(f"   FAIL: mock execute_tool called {len(captured)} times")
        return 1
    quote_calls = [c for c in captured if c[0] == "get_quotes"]
    if not quote_calls or quote_calls[0][1]["symbols"] != ["NVDA", "AMD"]:
        print(f"   FAIL: get_quotes batch {quote_calls}")
        return 1
    signal_tickers = sorted(
        c[1]["ticker"] for c in captured if c[0] == "get_recent_signals"
    )
    if signal_tickers != ["AMD", "NVDA"]:
        print(f"   FAIL: get_recent_signals tickers {signal_tickers}")
        return 1
    print(f"   tasks: {len(tasks)}, execute_tool calls: {len(captured)}")
    print(f"   context hits: {len(result.context.hits)}")
    print("   PASS\n")

    print("6. RESEARCH_PARALLEL_ENABLED=false → react")
    _set_parallel_env(False)
    if parallel_research_enabled():
        print("   FAIL: parallel_research_enabled should be false")
        return 1
    disabled_path = route_research_path("compará NVDA vs AMD", history=None)
    if disabled_path != "react":
        print(f"   FAIL: expected react, got {disabled_path}")
        return 1
    print(f"   path: {disabled_path}")
    print("   PASS\n")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    _set_parallel_env(True)

    print("7. Research Plan follow-up (¿y AMD?)")
    history = [
        {
            "role": "user",
            "content": "compará NVDA vs AMD en precio y noticias",
        },
        {
            "role": "assistant",
            "content": "NVDA subió 2%; AMD plano. Citations…",
        },
    ]
    follow_path = route_research_path("¿y AMD?", history=history)
    if follow_path != "parallel":
        print(f"   FAIL: AMD inline should route parallel, got {follow_path}")
        return 1
    print("   inline AMD → parallel (sin Research Plan, ADR-0008)")

    ambiguous_path = route_research_path("¿qué más?", history=history)
    if ambiguous_path != "react":
        print(
            f"   FAIL: vague follow-up after ticker thread expected react, got {ambiguous_path}"
        )
        return 1
    print("   vague follow-up (¿qué más?) → react (ReAct con historial)")

    print("8. false positives (Argentina / que mas)")
    arg_q = "que esta pasando con Argentina actualmente?"
    if extract_tickers_from_query(arg_q):
        print(f"   FAIL: thematic query extracted tickers: {extract_tickers_from_query(arg_q)}")
        return 1
    if not query_looks_thematic(arg_q):
        print("   FAIL: Argentina query should look thematic")
        return 1
    if route_research_path(arg_q, history=None) != "react":
        print(f"   FAIL: Argentina should route react, got {route_research_path(arg_q)}")
        return 1
    from backend.services.ticker_extract import should_use_parallel_research

    if should_use_parallel_research("que mas?"):
        print("   FAIL: que mas? should not use parallel")
        return 1
    if route_research_path("que mas?", history=history) != "react":
        print(
            f"   FAIL: que mas? after ticker thread should route react, got "
            f"{route_research_path('que mas?', history=history)}"
        )
        return 1
    print("   Argentina → react; que mas? → react (sin ESTA/MA)")
    print("   PASS\n")

    if api_key:
        plan = build_research_plan("¿y AMD?", history)
        if "AMD" not in plan.tickers:
            print(f"   FAIL: plan tickers missing AMD: {plan.tickers}")
            return 1
        print(f"   plan tickers (¿y AMD?): {plan.tickers}")
    else:
        parsed = parse_research_plan_json('{"tickers": ["AMD"]}')
        if parsed.tickers != ["AMD"]:
            print(f"   FAIL: parse_research_plan_json {parsed.tickers}")
            return 1
        with patch(
            "backend.services.research_plan.generate_research_plan",
            return_value=["AMD"],
        ):
            plan = build_research_plan("¿qué más?", history)
        if plan.tickers != ["AMD"]:
            print(f"   FAIL: build_research_plan mock {plan.tickers}")
            return 1
        print("   SKIP live LLM: OPENAI_API_KEY not configured (mock plan OK)")

    print("   PASS\n")

    print("== F24 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
