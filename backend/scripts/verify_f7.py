"""Verificación F7: Market Data (Quote Strip + Signal Detail enrichment)."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.services.market_data import get_api_key, get_finnhub_api_key


def main() -> int:
    print("== F7 verification: Market Data ==\n")

    api_key = get_finnhub_api_key() or get_api_key()
    if not api_key:
        print("SKIP: FINNHUB_API_KEY (o ALPHA_VANTAGE_API_KEY fallback) no configurada en .env")
        print("== F7 verification SKIPPED (no API key) ==")
        return 0

    provider = "Finnhub" if get_finnhub_api_key() else "Alpha Vantage (fallback)"
    print(f"   provider: {provider}\n")
    client = TestClient(app)

    # 1. GET /quotes/watchlist
    print("1. GET /quotes/watchlist")
    response = client.get("/quotes/watchlist")
    if response.status_code != 200:
        print(f"   FAIL: status {response.status_code}")
        return 1
    watchlist_quotes = response.json()
    print(f"   count: {len(watchlist_quotes)}")
    if not watchlist_quotes:
        print("   FAIL: empty watchlist quotes")
        return 1
    first = watchlist_quotes[0]
    required = {
        "symbol",
        "price",
        "change",
        "change_percent",
        "timestamp",
        "delayed",
        "available",
    }
    if not required.issubset(first.keys()):
        print(f"   FAIL: missing fields in quote: {first.keys()}")
        return 1
    available = [
        q for q in watchlist_quotes if q.get("available") and q.get("price")
    ]
    print(f"   total symbols: {len(watchlist_quotes)}, with price: {len(available)}")
    if not available:
        print("   FAIL: no quotes with price data")
        return 1
    first = available[0]
    print(
        f"   first: {first['symbol']} ${first['price']:.2f} "
        f"({first['change_percent']:+.2f}%) delayed={first.get('delayed')}"
    )
    print("   PASS\n")

    # 2. GET /quotes?symbols=AAPL
    print("2. GET /quotes?symbols=AAPL")
    response = client.get("/quotes", params={"symbols": "AAPL"})
    if response.status_code != 200:
        print(f"   FAIL: status {response.status_code}")
        return 1
    quotes = response.json()
    print(f"   count: {len(quotes)}")
    if len(quotes) != 1:
        print(f"   FAIL: expected 1 quote, got {len(quotes)}")
        return 1
    quote = quotes[0]
    if quote["symbol"] != "AAPL":
        print(f"   FAIL: expected AAPL, got {quote['symbol']}")
        return 1
    if quote["price"] <= 0:
        print(f"   FAIL: invalid price {quote['price']}")
        return 1
    print(
        f"   AAPL: ${quote['price']:.2f} "
        f"({quote['change_percent']:+.2f}%) delayed={quote.get('delayed')}"
    )
    print("   PASS\n")

    print("== F7 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
