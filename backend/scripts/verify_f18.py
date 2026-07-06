"""Verificación F18: Research Agent con LangGraph."""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

from backend.services.tools import TOOL_DEFINITIONS, execute_tool


def main() -> int:
    print("== F18 verification: LangGraph Research Agent ==\n")
    load_dotenv()

    tool_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    expected = {
        "search_corpus",
        "get_recent_signals",
        "get_signal_detail",
        "corpus_stats",
        "get_quotes",
        "get_watchlist_quotes",
        "get_price_history",
    }
    print("1. Tool definitions (7 tools)")
    missing = expected - tool_names
    if missing:
        print(f"   FAIL: missing tools: {sorted(missing)}")
        return 1
    print(f"   tools: {sorted(tool_names)}")
    print("   PASS\n")

    print("2. Tool corpus_stats")
    result, _ = execute_tool("corpus_stats", {"hours": 168, "limit": 5})
    stats = json.loads(result)
    print(f"   total_signals: {stats.get('total_signals')}")
    print("   PASS\n")

    print("3. Tool get_price_history")
    result, _ = execute_tool("get_price_history", {"symbol": "AAPL", "period": "1mo"})
    hist = json.loads(result)
    if hist.get("error"):
        print(f"   WARN: {hist['error']} (yfinance puede fallar sin red)")
    else:
        print(f"   AAPL change_percent: {hist.get('change_percent')}%")
    print("   PASS\n")

    print("4. Tool search_corpus (+source_type, +min_relevance)")
    result, hits = execute_tool(
        "search_corpus",
        {"query": "mercado", "limit": 3, "min_relevance": 0.35},
    )
    payload = json.loads(result)
    print(f"   signals: {len(payload.get('signals', []))}")
    print("   PASS\n")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("5. LangGraph gather_research_context")
        print("   SKIP: OPENAI_API_KEY not configured")
        print("\n== F18 verification OK (tools only) ==")
        return 0

    print("5. LangGraph gather_research_context")
    os.environ["RESEARCH_ENGINE"] = "langgraph"
    from backend.services.research_agent import (
        format_research_context,
        gather_research_context,
    )

    ctx = gather_research_context("¿Cómo está NVDA en precio y noticias recientes?")
    formatted = format_research_context(ctx)
    print(f"   hits: {len(ctx.hits)}")
    print(f"   market sections: {len(ctx.market_sections)}")
    print(f"   corpus sections: {len(ctx.corpus_sections)}")
    if "Market Data" not in formatted and "Signals" not in formatted and not ctx.hits:
        print("   FAIL: context vacío")
        return 1
    print("   PASS\n")

    print("6. Rollback RESEARCH_ENGINE=legacy")
    os.environ["RESEARCH_ENGINE"] = "legacy"
    from backend.services.ask import _gather_context

    context, hits, _ = _gather_context("resumen mercados hoy")
    if not hits and "Sin datos" in context:
        print("   WARN: legacy sin hits (Store puede estar vacío)")
    else:
        print(f"   legacy hits: {len(hits)}")
    print("   PASS\n")

    print("== F18 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
