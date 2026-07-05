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

from dotenv import load_dotenv

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
    _load_env()
    raw = os.getenv("WATCHLIST", DEFAULT_WATCHLIST)
    symbols: list[str] = []
    for part in raw.split(","):
        symbol = normalize_symbol(part.strip())
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


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
    """Sugerencias para autocompletado ($) — carrusel + tickers conocidos."""
    limit = max(1, min(limit, 100))
    prefix_clean = prefix.strip().lstrip("$").upper()

    results: list[TickerSuggestion] = []
    for item in _curated_ticker_catalog():
        if prefix_clean and not item.symbol.startswith(prefix_clean):
            continue
        results.append(item)
        if len(results) >= limit:
            break

    return results
