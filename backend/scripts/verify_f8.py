"""Verificación F8: Research Chat agente (Corpus + Market Data)."""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

from backend.services.agent import format_agent_context, gather_agent_context
from backend.services.tools import execute_tool


def main() -> int:
    print("== F8 verification: Research Chat Agent ==\n")
    load_dotenv()

    # 1. Tool: search_corpus
    print("1. Tool search_corpus")
    result, hits = execute_tool(
        "search_corpus",
        {"query": "mercado acciones", "limit": 3},
    )
    payload = json.loads(result)
    print(f"   signals: {len(payload.get('signals', []))}")
    if not hits:
        print("   WARN: no corpus hits (Store puede estar vacío o sin embeddings)")
    else:
        print(f"   first: @{hits[0].username}")
    print("   PASS\n")

    # 2. Tool: get_quotes
    print("2. Tool get_quotes")
    result, _ = execute_tool("get_quotes", {"symbols": ["AAPL", "NVDA"]})
    quotes = json.loads(result).get("quotes", [])
    print(f"   quotes: {len(quotes)}")
    if not quotes:
        print("   FAIL: expected quote data")
        return 1
    print(f"   AAPL: ${quotes[0]['price']} ({quotes[0]['change_percent']:+.2f}%)")
    print("   PASS\n")

    # 3. Agent context (requiere OPENAI_API_KEY)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("3. Agent gather_agent_context")
        print("   SKIP: OPENAI_API_KEY not configured")
        print("\n== F8 verification OK (tools only) ==")
        return 0

    print("3. Agent gather_agent_context")
    query = "¿Cómo está AAPL en precio y qué dicen en X?"
    ctx = gather_agent_context(query)
    formatted = format_agent_context(ctx)
    print(f"   hits: {len(ctx.hits)}")
    print(f"   market sections: {len(ctx.market_sections)}")
    print(f"   corpus sections: {len(ctx.corpus_sections)}")
    if "Market Data" not in formatted and "Signals" not in formatted:
        print("   FAIL: context vacío")
        return 1
    if not ctx.market_sections:
        print("   WARN: agente no llamó get_quotes (puede variar)")
    print("   PASS\n")

    print("== F8 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
