"""Endpoints de Market Data (Quotes vía Finnhub + fallback)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.schemas import Quote, TickerSuggestion
from backend.services import market_data

router = APIRouter(prefix="/quotes", tags=["quotes"])


def _to_schema(quote: market_data.Quote) -> Quote:
    return Quote(
        symbol=quote.symbol,
        price=quote.price,
        change=quote.change,
        change_percent=quote.change_percent,
        timestamp=quote.timestamp,
        delayed=quote.delayed,
        available=True,
    )


def _placeholder(symbol: str) -> Quote:
    return Quote(
        symbol=symbol,
        price=None,
        change=None,
        change_percent=None,
        timestamp=None,
        delayed=True,
        available=False,
    )


@router.get("/watchlist", response_model=list[Quote])
def get_watchlist_quotes() -> list[Quote]:
    symbols = market_data.get_watchlist()
    fetched = {
        q.symbol: q for q in market_data.fetch_quotes(symbols)
    }
    results: list[Quote] = []
    for symbol in symbols:
        quote = fetched.get(symbol)
        if quote is not None:
            results.append(_to_schema(quote))
        else:
            results.append(_placeholder(symbol))
    return results


@router.get("/tickers", response_model=list[TickerSuggestion])
def get_ticker_suggestions(
    q: str = Query("", description="Prefijo tras $, ej. NV para NVDA"),
    limit: int = Query(50, ge=1, le=100),
) -> list[TickerSuggestion]:
    return [
        TickerSuggestion(
            symbol=item.symbol,
            description=item.description,
            source=item.source,
        )
        for item in market_data.search_tickers(q, limit=limit)
    ]


@router.get("", response_model=list[Quote])
def get_quotes(
    symbols: str = Query(..., description="Comma-separated tickers, e.g. AAPL,NVDA"),
) -> list[Quote]:
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return [_to_schema(q) for q in market_data.fetch_quotes(symbol_list)]
