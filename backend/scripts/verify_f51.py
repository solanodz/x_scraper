"""Verificación F51: filtro multi-ticker (Mis tickers) del Signal Feed."""

from __future__ import annotations

import sys


def main() -> int:
    print("verify_f51_mis_tickers")

    # Carga app primero para resolver ciclos de import en cold-start de scripts.
    import backend.app.main  # noqa: F401

    from backend.app.services.feed_filters import (
        build_feed_filter_conditions,
        feed_filters_from_query,
        parse_tickers_param,
    )

    if parse_tickers_param(None) is not None:
        print("   FAIL: parse None")
        return 1
    if parse_tickers_param("") != ():
        print("   FAIL: parse empty")
        return 1
    if parse_tickers_param("AAPL, MSFT") != ("AAPL", "MSFT"):
        print("   FAIL: parse list")
        return 1
    if parse_tickers_param("$nvda,aapl") != ("NVDA", "AAPL"):
        print("   FAIL: parse $ / case")
        return 1
    print("   parse_tickers_param OK")

    empty = feed_filters_from_query(tickers="")
    if empty.tickers != ():
        print("   FAIL: empty tickers tuple")
        return 1
    conds, _params = build_feed_filter_conditions(empty)
    if "FALSE" not in conds:
        print(f"   FAIL: empty tickers should force FALSE, got {conds}")
        return 1
    print("   empty tickers → FALSE (no deceptive feed)")

    multi = feed_filters_from_query(tickers="AAPL,MSFT")
    if multi.tickers != ("AAPL", "MSFT"):
        print("   FAIL: multi parse")
        return 1
    conds, params = build_feed_filter_conditions(multi)
    joined = " AND ".join(conds)
    if " OR " not in joined:
        print(f"   FAIL: multi-ticker should OR match clauses: {joined}")
        return 1
    symbol_vals = {
        params[k]
        for k in params
        if k.startswith("tk_") and "_pat_" not in k
    }
    if symbol_vals != {"AAPL", "MSFT"}:
        print(f"   FAIL: expected AAPL+MSFT params, got {symbol_vals}")
        return 1
    print("   tickers=AAPL,MSFT → OR + params")

    single = feed_filters_from_query(ticker="NVDA")
    conds, params = build_feed_filter_conditions(single)
    if params.get("ticker") != "NVDA":
        print(f"   FAIL: single ticker broken: {params}")
        return 1
    print("   ticker=NVDA still works")

    import inspect

    from backend.app.routes import signals as signals_routes

    params_names = inspect.signature(signals_routes.get_signals).parameters
    if "tickers" not in params_names:
        print("   FAIL: GET /signals missing tickers query param")
        return 1
    print("   GET /signals?tickers= exposed")

    # Frontend contract strings
    from pathlib import Path

    feed = Path(__file__).resolve().parents[2] / "frontend/src/components/SignalFeed.tsx"
    filters_ui = (
        Path(__file__).resolve().parents[2]
        / "frontend/src/components/SignalFeedFilters.tsx"
    )
    text = feed.read_text() + filters_ui.read_text()
    if "Mis tickers" not in text or "watchOnly" not in text:
        print("   FAIL: Feed UI missing Mis tickers toggle")
        return 1
    if "Ticker Watch está vacío" not in text:
        print("   FAIL: missing empty Watch empty-state copy")
        return 1
    print("   UI: Mis tickers toggle + empty Watch state")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
