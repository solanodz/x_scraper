"""Logos de Tickers: Finnhub profile2 (acciones) + CDN (crypto). Cache largo."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from backend.services.market_data import (
    finnhub_symbol,
    get_finnhub_api_key,
    normalize_symbol,
)

FINNHUB_PROFILE2_URL = "https://finnhub.io/api/v1/stock/profile2"
LOGO_CACHE_TTL_SECONDS = 7 * 24 * 3600  # logos casi no cambian
NEGATIVE_CACHE_TTL_SECONDS = 6 * 3600

# CoinGecko ids vía jsDelivr (simplr-sh/coin-logos) — sin API key
CRYPTO_LOGO_URLS: dict[str, str] = {
    "BTC": "https://cdn.jsdelivr.net/gh/simplr-sh/coin-logos/images/bitcoin/small.png",
    "ETH": "https://cdn.jsdelivr.net/gh/simplr-sh/coin-logos/images/ethereum/small.png",
    "SOL": "https://cdn.jsdelivr.net/gh/simplr-sh/coin-logos/images/solana/small.png",
}

# symbol -> (url_or_None, expires_at_monotonic)
_logo_cache: dict[str, tuple[str | None, float]] = {}
_last_finnhub_logo_monotonic = 0.0
_FINNHUB_LOGO_MIN_INTERVAL = 0.25


def _throttle_finnhub_logo() -> None:
    global _last_finnhub_logo_monotonic
    elapsed = time.monotonic() - _last_finnhub_logo_monotonic
    if elapsed < _FINNHUB_LOGO_MIN_INTERVAL:
        time.sleep(_FINNHUB_LOGO_MIN_INTERVAL - elapsed)
    _last_finnhub_logo_monotonic = time.monotonic()


def _cache_get(symbol: str) -> str | None | object:
    """Devuelve URL, None (negativo cacheado), o sentinel si miss."""
    hit = _logo_cache.get(symbol)
    if hit is None:
        return _MISS
    url, expires = hit
    if time.monotonic() > expires:
        _logo_cache.pop(symbol, None)
        return _MISS
    return url


_MISS = object()


def _cache_set(symbol: str, url: str | None) -> None:
    ttl = LOGO_CACHE_TTL_SECONDS if url else NEGATIVE_CACHE_TTL_SECONDS
    _logo_cache[symbol] = (url, time.monotonic() + ttl)


def _fetch_finnhub_logo(symbol: str) -> str | None:
    api_key = get_finnhub_api_key()
    if not api_key:
        return None

    _throttle_finnhub_logo()
    params = urllib.parse.urlencode(
        {"symbol": finnhub_symbol(symbol), "token": api_key}
    )
    url = f"{FINNHUB_PROFILE2_URL}?{params}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "XScraperTerminal/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            payload: Any = json.loads(response.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None

    if not isinstance(payload, dict):
        return None
    logo = payload.get("logo")
    if isinstance(logo, str) and logo.startswith("http"):
        return logo.strip()
    return None


def resolve_ticker_logo(symbol: str) -> str | None:
    """URL de logo para un Ticker, o None."""
    normalized = normalize_symbol(symbol)
    if not normalized:
        return None

    if normalized in CRYPTO_LOGO_URLS:
        return CRYPTO_LOGO_URLS[normalized]

    cached = _cache_get(normalized)
    if cached is not _MISS:
        return cached  # type: ignore[return-value]

    logo = _fetch_finnhub_logo(normalized)
    _cache_set(normalized, logo)
    return logo


def fetch_ticker_logos(symbols: list[str]) -> dict[str, str | None]:
    """Resuelve logos para una lista de símbolos (dedupe + cache)."""
    result: dict[str, str | None] = {}
    seen: set[str] = set()
    for raw in symbols:
        normalized = normalize_symbol(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result[normalized] = resolve_ticker_logo(normalized)
    return result
