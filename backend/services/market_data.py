"""Market Data: Finnhub (primario) + Alpha Vantage (fallback) + yfinance (último recurso)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from dotenv import load_dotenv

from backend.services.market_symbols import yahoo_finance_symbol

DEFAULT_WATCHLIST = (
    "BTC,ETH,SOL,"
    "SPY,QQQ,AMZN,AAPL,MSFT,MU,TSLA,NVDA,GOOGL,VIST,YPF,MELI,KO,META,BBD,GGAL,GLD"
)
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
AV_QUOTE_URL = "https://www.alphavantage.co/query"
# Símbolos cortos del carrusel → par Finnhub (Binance USDT)
CRYPTO_FINNHUB_SYMBOLS: dict[str, str] = {
    "BTC": "BINANCE:BTCUSDT",
    "ETH": "BINANCE:ETHUSDT",
    "SOL": "BINANCE:SOLUSDT",
}
DEFAULT_CACHE_TTL_SECONDS = 900  # 15 min (Finnhub free: 60 req/min)
DEFAULT_MAX_DAILY_REQUESTS = 25  # Solo aplica al fallback Alpha Vantage
FINNHUB_MIN_REQUEST_INTERVAL_SECONDS = 0.2
AV_MIN_REQUEST_INTERVAL_SECONDS = 1.2

_cache: dict[str, tuple["Quote", float]] = {}
_av_daily_request_count = 0
_av_daily_request_date: date | None = None
_last_finnhub_request_monotonic = 0.0
_last_av_request_monotonic = 0.0


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    change: float
    change_percent: float
    timestamp: datetime
    delayed: bool = True


def _load_env() -> None:
    load_dotenv()


def get_finnhub_api_key() -> str | None:
    _load_env()
    key = os.getenv("FINNHUB_API_KEY", "").strip()
    return key or None


def get_alpha_vantage_api_key() -> str | None:
    _load_env()
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    return key or None


def get_api_key() -> str | None:
    """Clave primaria de Market Data (Finnhub, o AV si no hay Finnhub)."""
    return get_finnhub_api_key() or get_alpha_vantage_api_key()


def get_cache_ttl_seconds() -> int:
    _load_env()
    raw = os.getenv("QUOTE_CACHE_TTL_SECONDS", "").strip()
    if raw.isdigit():
        return max(int(raw), 60)
    return DEFAULT_CACHE_TTL_SECONDS


def get_max_daily_requests() -> int:
    _load_env()
    raw = os.getenv("QUOTE_MAX_DAILY_REQUESTS", "").strip()
    if raw.isdigit():
        return max(int(raw), 1)
    return DEFAULT_MAX_DAILY_REQUESTS


def get_watchlist() -> list[str]:
    """Símbolos del carrusel Quote Strip (dinámico desde Corpus, sin WATCHLIST)."""
    from backend.services.ticker_catalog import get_quote_strip_symbols

    return get_quote_strip_symbols()


def normalize_symbol(ticker: str) -> str:
    return ticker.strip().lstrip("$").upper()


def finnhub_symbol(symbol: str) -> str:
    """Resuelve tickers de crypto del carrusel al par Finnhub."""
    normalized = normalize_symbol(symbol)
    return CRYPTO_FINNHUB_SYMBOLS.get(normalized, normalized)


def _reset_av_daily_counter_if_needed() -> None:
    global _av_daily_request_count, _av_daily_request_date
    today = date.today()
    if _av_daily_request_date != today:
        _av_daily_request_date = today
        _av_daily_request_count = 0


def _can_make_av_request() -> bool:
    _reset_av_daily_counter_if_needed()
    return _av_daily_request_count < get_max_daily_requests()


def _record_av_request() -> None:
    global _av_daily_request_count
    _reset_av_daily_counter_if_needed()
    _av_daily_request_count += 1


def _get_cached(symbol: str) -> Quote | None:
    entry = _cache.get(symbol)
    if entry is None:
        return None
    quote, expires_at = entry
    if time.monotonic() >= expires_at:
        _cache.pop(symbol, None)
        return None
    return quote


def _set_cached(quote: Quote) -> None:
    expires_at = time.monotonic() + get_cache_ttl_seconds()
    _cache[quote.symbol] = (quote, expires_at)


def _parse_change_percent(raw: str | None) -> float:
    if not raw:
        return 0.0
    cleaned = raw.strip().rstrip("%")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_trading_day(raw: str | None) -> datetime:
    if raw:
        try:
            day = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return day
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def _throttle_finnhub() -> None:
    global _last_finnhub_request_monotonic
    elapsed = time.monotonic() - _last_finnhub_request_monotonic
    if elapsed < FINNHUB_MIN_REQUEST_INTERVAL_SECONDS:
        time.sleep(FINNHUB_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
    _last_finnhub_request_monotonic = time.monotonic()


def _throttle_alpha_vantage() -> None:
    global _last_av_request_monotonic
    elapsed = time.monotonic() - _last_av_request_monotonic
    if elapsed < AV_MIN_REQUEST_INTERVAL_SECONDS:
        time.sleep(AV_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
    _last_av_request_monotonic = time.monotonic()


def _fetch_quote_finnhub(symbol: str) -> Quote | None:
    api_key = get_finnhub_api_key()
    if not api_key:
        return None

    normalized = normalize_symbol(symbol)
    _throttle_finnhub()
    params = urllib.parse.urlencode(
        {"symbol": finnhub_symbol(normalized), "token": api_key}
    )
    url = f"{FINNHUB_QUOTE_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "XScraperTerminal/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None

    if not isinstance(payload, dict):
        return None

    price_raw = payload.get("c")
    if price_raw is None:
        return None

    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        return None

    if price <= 0:
        return None

    change = float(payload.get("d") or 0)
    change_percent = float(payload.get("dp") or 0)
    ts_raw = payload.get("t")
    if ts_raw:
        try:
            timestamp = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            timestamp = datetime.now(tz=timezone.utc)
    else:
        timestamp = datetime.now(tz=timezone.utc)

    return Quote(
        symbol=normalized,
        price=price,
        change=change,
        change_percent=change_percent,
        timestamp=timestamp,
        delayed=True,
    )


def _fetch_quote_alpha_vantage(symbol: str) -> Quote | None:
    api_key = get_alpha_vantage_api_key()
    if not api_key or not _can_make_av_request():
        return None

    _throttle_alpha_vantage()

    params = urllib.parse.urlencode(
        {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": api_key,
        }
    )
    url = f"{AV_QUOTE_URL}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None

    if payload.get("Note") or payload.get("Information"):
        return None

    global_quote = payload.get("Global Quote")
    if not isinstance(global_quote, dict) or not global_quote:
        return None

    price_raw = global_quote.get("05. price")
    if price_raw is None:
        return None

    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        return None

    if price <= 0:
        return None

    _record_av_request()

    change = float(global_quote.get("09. change") or 0)
    change_percent = _parse_change_percent(global_quote.get("10. change percent"))
    timestamp = _parse_trading_day(global_quote.get("07. latest trading day"))

    return Quote(
        symbol=symbol,
        price=price,
        change=change,
        change_percent=change_percent,
        timestamp=timestamp,
        delayed=True,
    )


def _quote_from_yfinance(symbol: str) -> Quote | None:
    try:
        import yfinance as yf

        return _quote_from_yfinance_ticker(symbol, yf.Ticker(symbol))
    except Exception:
        return None


def _fetch_quotes_yfinance_batch(symbols: list[str]) -> dict[str, Quote]:
    if not symbols:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        return {}

    unique = list(dict.fromkeys(symbols))
    quotes: dict[str, Quote] = {}

    try:
        tickers = yf.Tickers(" ".join(unique))
        for symbol in unique:
            ticker = tickers.tickers.get(symbol)
            if ticker is None:
                continue
            quote = _quote_from_yfinance_ticker(symbol, ticker)
            if quote is not None:
                quotes[symbol] = quote
    except Exception:
        for symbol in unique:
            if symbol in quotes:
                continue
            quote = _quote_from_yfinance(symbol)
            if quote is not None:
                quotes[symbol] = quote

    return quotes


def _quote_from_yfinance_ticker(symbol: str, ticker) -> Quote | None:
    try:
        fast = ticker.fast_info
        price = getattr(fast, "last_price", None) or getattr(
            fast, "regular_market_price", None
        )
        previous_close = getattr(fast, "previous_close", None)

        if price is None or float(price) <= 0:
            history = ticker.history(period="5d", auto_adjust=True)
            if history is None or history.empty:
                return None
            price = float(history["Close"].iloc[-1])
            previous_close = (
                float(history["Close"].iloc[-2])
                if len(history) > 1
                else price
            )
        else:
            price = float(price)
            previous_close = float(previous_close) if previous_close else price

        change = price - previous_close
        change_percent = (change / previous_close * 100) if previous_close else 0.0

        return Quote(
            symbol=symbol,
            price=price,
            change=change,
            change_percent=change_percent,
            timestamp=datetime.now(tz=timezone.utc),
            delayed=True,
        )
    except Exception:
        return None


def _resolve_quote(symbol: str) -> Quote | None:
    quote = _fetch_quote_finnhub(symbol)
    if quote is not None:
        return quote
    quote = _fetch_quote_alpha_vantage(symbol)
    if quote is not None:
        return quote
    return _quote_from_yfinance(symbol)


def fetch_quote(symbol: str) -> Quote | None:
    normalized = normalize_symbol(symbol)
    if not normalized:
        return None

    cached = _get_cached(normalized)
    if cached is not None:
        return cached

    quote = _resolve_quote(normalized)
    if quote is not None:
        _set_cached(quote)
    return quote


def fetch_quotes(symbols: list[str]) -> list[Quote]:
    quotes: list[Quote] = []
    seen: set[str] = set()
    pending: list[str] = []

    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        cached = _get_cached(normalized)
        if cached is not None:
            quotes.append(cached)
            continue

        finnhub_quote = _fetch_quote_finnhub(normalized)
        if finnhub_quote is not None:
            _set_cached(finnhub_quote)
            quotes.append(finnhub_quote)
            continue

        pending.append(normalized)

    if pending:
        still_pending: list[str] = []
        for symbol in pending:
            av_quote = _fetch_quote_alpha_vantage(symbol)
            if av_quote is not None:
                _set_cached(av_quote)
                quotes.append(av_quote)
            else:
                still_pending.append(symbol)

        if still_pending:
            yf_quotes = _fetch_quotes_yfinance_batch(still_pending)
            for symbol in still_pending:
                quote = yf_quotes.get(symbol)
                if quote is not None:
                    _set_cached(quote)
                    quotes.append(quote)

    return quotes


VALID_PRICE_PERIODS = frozenset(
    {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"}
)
VALID_PRICE_INTERVALS = frozenset(
    {"1m", "5m", "15m", "30m", "1h", "1d", "1wk"}
)
_PERIOD_ORDER = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y")
_INTRADAY_INTERVALS = frozenset({"1m", "5m", "15m", "30m", "1h"})


def _normalize_price_period(period: str | None) -> str:
    effective = (period or "1y").strip()
    if effective not in VALID_PRICE_PERIODS:
        return "1y"
    return effective


def _normalize_price_interval(interval: str | None) -> str:
    effective = (interval or "1d").strip()
    if effective not in VALID_PRICE_INTERVALS:
        return "1d"
    return effective


def _clamp_period_for_interval(period: str, interval: str) -> str:
    """Acorta la ventana si supera límites Yahoo para el intervalo."""
    if interval == "1m":
        max_period = "5d"  # Yahoo: 1m max ~7d; sin 7d en VALID → 5d
    elif interval in _INTRADAY_INTERVALS:
        max_period = "1mo"  # Yahoo: intradía <1d max ~60d
    else:
        return period

    try:
        if _PERIOD_ORDER.index(period) > _PERIOD_ORDER.index(max_period):
            return max_period
    except ValueError:
        return max_period
    return period


def _format_candle_date(index: Any, interval: str) -> str:
    """ISO date para 1d/1wk; ISO datetime completo para intradía."""
    if interval in ("1d", "1wk"):
        if hasattr(index, "date"):
            return index.date().isoformat()
        return str(index)[:10]

    if hasattr(index, "isoformat"):
        return index.isoformat()
    return str(index)


def fetch_price_history(symbol: str, period: str = "1mo") -> dict[str, Any]:
    """Historial de precios vía yfinance (OHLC diario)."""
    candles = _fetch_price_candles(symbol, period, interval="1d")
    if candles.get("error"):
        return candles

    closes = [float(c["close"]) for c in candles["candles"]]
    if not closes:
        return {
            "error": "sin datos históricos",
            "symbol": candles.get("symbol"),
            "period": candles.get("period"),
        }

    start_price = closes[0]
    end_price = closes[-1]
    change_percent = (
        (end_price - start_price) / start_price * 100 if start_price else 0.0
    )
    highs = [float(c["high"]) for c in candles["candles"]]
    lows = [float(c["low"]) for c in candles["candles"]]

    return {
        "symbol": candles["symbol"],
        "period": candles["period"],
        "start_price": round(start_price, 2),
        "end_price": round(end_price, 2),
        "change_percent": round(change_percent, 2),
        "high": round(max(highs), 2),
        "low": round(min(lows), 2),
        "data_points": len(closes),
    }


def fetch_price_candles(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
) -> dict[str, Any]:
    """Velas OHLC vía yfinance (intervalo + ventana)."""
    payload = _fetch_price_candles(symbol, period, interval=interval)
    if payload.get("error"):
        return payload
    return {
        "symbol": payload["symbol"],
        "period": payload["period"],
        "interval": payload["interval"],
        "candles": payload["candles"],
        "data_points": len(payload["candles"]),
    }


def _fetch_price_candles(
    symbol: str,
    period: str,
    interval: str = "1d",
) -> dict[str, Any]:
    """Carga OHLC desde yfinance con period + interval (clamp Yahoo)."""
    normalized = normalize_symbol(symbol)
    if not normalized:
        return {
            "error": "symbol inválido",
            "symbol": symbol,
            "period": period,
            "interval": interval,
        }

    effective_interval = _normalize_price_interval(interval)
    effective_period = _clamp_period_for_interval(
        _normalize_price_period(period),
        effective_interval,
    )

    try:
        import yfinance as yf

        yf_symbol = yahoo_finance_symbol(normalized)
        ticker = yf.Ticker(yf_symbol)
        history = ticker.history(
            period=effective_period,
            interval=effective_interval,
            auto_adjust=True,
        )
        if history is None or history.empty:
            return {
                "error": "sin datos históricos",
                "symbol": normalized,
                "period": effective_period,
                "interval": effective_interval,
            }

        candles: list[dict[str, Any]] = []
        for index, row in history.iterrows():
            candles.append(
                {
                    "date": _format_candle_date(index, effective_interval),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row.get("Volume", 0) or 0),
                }
            )

        return {
            "symbol": normalized,
            "period": effective_period,
            "interval": effective_interval,
            "candles": candles,
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "symbol": normalized,
            "period": effective_period,
            "interval": effective_interval,
        }


CURATED_EXTRA_SYMBOLS: tuple[str, ...] = (
    "AMD",
    "INTC",
    "NFLX",
    "CRM",
    "AVGO",
    "WMT",
    "JPM",
    "BAC",
    "XOM",
    "CVX",
    "DIS",
    "PYPL",
    "UBER",
    "COIN",
    "PLTR",
    "IBM",
    "COST",
    "UNH",
    "JNJ",
    "BA",
    "V",
    "MA",
    "GS",
    "WFC",
    "BABA",
    "NIO",
    "RIVN",
    "SMCI",
    "ARM",
    "SOFI",
    "PAM",
    "BMA",
    "IWM",
    "DIA",
    "SLV",
    "USO",
    "XLE",
    "XLF",
)

CURATED_TICKER_LABELS: dict[str, str] = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "IWM": "Russell 2000 ETF",
    "DIA": "Dow Jones ETF",
    "GLD": "Gold ETF",
    "SLV": "Silver ETF",
    "USO": "Oil ETF",
    "XLE": "Energy Sector ETF",
    "XLF": "Financial Sector ETF",
    "AMZN": "Amazon",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "MU": "Micron",
    "TSLA": "Tesla",
    "NVDA": "NVIDIA",
    "GOOGL": "Alphabet",
    "META": "Meta",
    "KO": "Coca-Cola",
    "VIST": "Vista Energy",
    "YPF": "YPF",
    "MELI": "MercadoLibre",
    "BBD": "Bradesco",
    "GGAL": "Galicia",
    "AMD": "AMD",
    "INTC": "Intel",
    "NFLX": "Netflix",
    "CRM": "Salesforce",
    "AVGO": "Broadcom",
    "WMT": "Walmart",
    "JPM": "JPMorgan",
    "BAC": "Bank of America",
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "DIS": "Disney",
    "PYPL": "PayPal",
    "UBER": "Uber",
    "COIN": "Coinbase",
    "PLTR": "Palantir",
    "IBM": "IBM",
    "COST": "Costco",
    "UNH": "UnitedHealth",
    "JNJ": "Johnson & Johnson",
    "BA": "Boeing",
    "V": "Visa",
    "MA": "Mastercard",
    "GS": "Goldman Sachs",
    "WFC": "Wells Fargo",
    "BABA": "Alibaba",
    "NIO": "NIO",
    "RIVN": "Rivian",
    "SMCI": "Super Micro",
    "ARM": "Arm Holdings",
    "SOFI": "SoFi",
    "PAM": "Pampa Energía",
    "BMA": "Banco Macro",
}

_curated_catalog_cache: list["TickerSuggestion"] | None = None


@dataclass(frozen=True)
class TickerSuggestion:
    symbol: str
    description: str = ""
    source: str = "curated"


def _curated_ticker_catalog() -> list[TickerSuggestion]:
    """Carrusel (WATCHLIST) + tickers conocidos adicionales."""
    global _curated_catalog_cache
    if _curated_catalog_cache is not None:
        return _curated_catalog_cache

    ordered: list[str] = []
    seen: set[str] = set()
    for symbol in get_watchlist():
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    for symbol in CURATED_EXTRA_SYMBOLS:
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)

    _curated_catalog_cache = [
        TickerSuggestion(
            symbol=symbol,
            description=CURATED_TICKER_LABELS.get(symbol, ""),
            source="curated",
        )
        for symbol in ordered
    ]
    return _curated_catalog_cache


def search_tickers(prefix: str = "", *, limit: int = 50) -> list[TickerSuggestion]:
    """Sugerencias para autocompletado — Corpus + catálogo curado."""
    from backend.services.ticker_catalog import search_ticker_suggestions

    return search_ticker_suggestions(prefix, limit=limit)
