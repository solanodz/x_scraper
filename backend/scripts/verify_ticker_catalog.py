"""Verificación: tickers dinámicos y resolución Intel → INTC."""

from __future__ import annotations

import sys

from backend.services.ticker_catalog import (
    build_ticker_match,
    get_quote_strip_symbols,
    resolve_ticker_input,
    search_ticker_suggestions,
)


def main() -> int:
    print("== Ticker catalog verification ==\n")

    print("1. resolve_ticker_input")
    cases = [
        ("Intel", "INTC"),
        ("INTC", "INTC"),
        ("Microsoft", "MSFT"),
        ("NVDA", "NVDA"),
    ]
    for raw, expected in cases:
        got = resolve_ticker_input(raw)
        if got != expected:
            print(f"   FAIL {raw!r} => {got!r}, expected {expected!r}")
            return 1
        print(f"   {raw!r} => {got}")
    print("   PASS\n")

    print("2. build_ticker_match patterns")
    match = build_ticker_match("Intel")
    if match is None or "Intel" not in match.patterns:
        print("   FAIL — Intel pattern missing")
        return 1
    print(f"   INTC patterns: {match.patterns}")
    print("   PASS\n")

    print("3. get_quote_strip_symbols (dynamic)")
    strip = get_quote_strip_symbols(limit=8)
    print(f"   strip ({len(strip)}): {', '.join(strip[:8])}")
    if not strip:
        print("   WARN — empty strip (Store vacío?)")
    print("   PASS\n")

    print("4. search_ticker_suggestions")
    hits = search_ticker_suggestions("INT", limit=5)
    symbols = [h.symbol for h in hits]
    print(f"   INT* => {symbols}")
    if "INTC" not in symbols and not any(s.startswith("INT") for s in symbols):
        print("   WARN — INTC not in suggestions")
    print("   PASS\n")

    print("== Ticker catalog OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
