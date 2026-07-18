"""Endpoints de Market Data (Quotes vía Finnhub + fallback)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.schemas import (
    PriceCandlesResponse,
    Quote,
    TickerLogo,
    TickerSuggestion,
)
from backend.services import market_data
from backend.services.ticker_logos import fetch_ticker_logos

router = APIRouter(prefix="/quotes", tags=["quotes"])


def _attach_logos(quotes: list[Quote]) -> list[Quote]:
    if not quotes:
        return quotes
    logos = fetch_ticker_logos([q.symbol for q in quotes])
    return [
        q.model_copy(update={"logo": logos.get(q.symbol)})
        for q in quotes
    ]


def _to_schema(quote: market_data.Quote, logo: str | None = None) -> Quote:
    return Quote(
        symbol=quote.symbol,
        price=quote.price,
        change=quote.change,
        change_percent=quote.change_percent,
        timestamp=quote.timestamp,
        delayed=quote.delayed,
        available=True,
        logo=logo,
    )


def _placeholder(symbol: str, logo: str | None = None) -> Quote:
    return Quote(
        symbol=symbol,
        price=None,
        change=None,
        change_percent=None,
        timestamp=None,
        delayed=True,
        available=False,
        logo=logo,
    )


@router.get("/watchlist", response_model=list[Quote])
def get_watchlist_quotes() -> list[Quote]:
    symbols = market_data.get_watchlist()
    fetched = {
        q.symbol: q for q in market_data.fetch_quotes(symbols)
    }
    logos = fetch_ticker_logos(symbols)
    results: list[Quote] = []
    for symbol in symbols:
        quote = fetched.get(symbol)
        logo = logos.get(symbol)
        if quote is not None:
            results.append(_to_schema(quote, logo=logo))
        else:
            results.append(_placeholder(symbol, logo=logo))
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


@router.get("/logos", response_model=list[TickerLogo])
def get_ticker_logos(
    symbols: str = Query(..., description="Comma-separated tickers, e.g. AAPL,NVDA,BTC"),
) -> list[TickerLogo]:
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    logos = fetch_ticker_logos(symbol_list)
    return [
        TickerLogo(symbol=symbol, logo=logos.get(symbol))
        for symbol in logos
    ]


@router.get("/candles", response_model=PriceCandlesResponse)
def get_price_candles(
    symbol: str = Query(..., description="Ticker, e.g. NVDA"),
    period: str = Query(
        "1y",
        description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y",
    ),
    interval: str = Query(
        "1d",
        description="1m, 5m, 15m, 30m, 1h, 1d, 1wk",
    ),
) -> PriceCandlesResponse:
    normalized = market_data.normalize_symbol(symbol)
    payload = market_data.fetch_price_candles(
        normalized,
        period=period,
        interval=interval,
    )
    effective_interval = str(payload.get("interval") or interval)
    effective_period = str(payload.get("period") or period)
    if payload.get("error"):
        return PriceCandlesResponse(
            symbol=normalized or symbol.strip().upper(),
            period=effective_period,
            interval=effective_interval,
            error=str(payload.get("error")),
        )
    candles = payload.get("candles") or []
    return PriceCandlesResponse(
        symbol=str(payload.get("symbol") or normalized),
        period=effective_period,
        interval=effective_interval,
        candles=candles,
        data_points=len(candles),
    )


@router.get("", response_model=list[Quote])
def get_quotes(
    symbols: str = Query(..., description="Comma-separated tickers, e.g. AAPL,NVDA"),
) -> list[Quote]:
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    quotes = [_to_schema(q) for q in market_data.fetch_quotes(symbol_list)]
    return _attach_logos(quotes)
