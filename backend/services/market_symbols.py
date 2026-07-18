"""Resolución de símbolos para proveedores OHLC (Yahoo / yfinance)."""

from __future__ import annotations

YAHOO_FINANCE_SYMBOLS: dict[str, str] = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}


def normalize_market_symbol(ticker: str) -> str:
    return ticker.strip().lstrip("$").upper()


def yahoo_finance_symbol(ticker: str) -> str:
    symbol = normalize_market_symbol(ticker)
    return YAHOO_FINANCE_SYMBOLS.get(symbol, symbol)
