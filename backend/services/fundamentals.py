"""Fundamentals snapshot: Finnhub (profile2 + metric) → yfinance. Sin inventar cifras."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from backend.services.market_data import (
    CRYPTO_FINNHUB_SYMBOLS,
    Quote,
    _throttle_finnhub,
    finnhub_symbol,
    get_finnhub_api_key,
    normalize_symbol,
)
from backend.services.market_symbols import yahoo_finance_symbol

FINNHUB_PROFILE2_URL = "https://finnhub.io/api/v1/stock/profile2"
FINNHUB_METRIC_URL = "https://finnhub.io/api/v1/stock/metric"

_NA = "no disponible"


@dataclass(frozen=True)
class FundamentalsSnapshot:
    symbol: str
    asset_kind: str  # equity | crypto | unknown
    price: float | None
    market_cap: float | None
    pe: float | None
    eps: float | None
    sector: str | None
    industry: str | None
    source: str  # finnhub | yfinance | none
    as_of: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if number in (float("inf"), float("-inf")):
        return None
    return number


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _http_json(url: str, *, timeout: float = 12.0) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "XScraperTerminal/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except (
        urllib.error.URLError,
        json.JSONDecodeError,
        TimeoutError,
        OSError,
        ValueError,
    ):
        return None
    return payload if isinstance(payload, dict) else None


def _fetch_finnhub_profile(symbol: str) -> dict[str, Any] | None:
    api_key = get_finnhub_api_key()
    if not api_key:
        return None
    _throttle_finnhub()
    params = urllib.parse.urlencode(
        {"symbol": finnhub_symbol(symbol), "token": api_key}
    )
    return _http_json(f"{FINNHUB_PROFILE2_URL}?{params}")


def _fetch_finnhub_metric(symbol: str) -> dict[str, Any] | None:
    api_key = get_finnhub_api_key()
    if not api_key:
        return None
    _throttle_finnhub()
    params = urllib.parse.urlencode(
        {
            "symbol": finnhub_symbol(symbol),
            "metric": "all",
            "token": api_key,
        }
    )
    return _http_json(f"{FINNHUB_METRIC_URL}?{params}")


def _snapshot_from_finnhub(
    symbol: str,
    *,
    price: float | None,
) -> FundamentalsSnapshot | None:
    profile = _fetch_finnhub_profile(symbol) or {}
    metric_payload = _fetch_finnhub_metric(symbol) or {}
    metric = metric_payload.get("metric")
    if not isinstance(metric, dict):
        metric = {}

    # Finnhub marketCapitalization suele venir en millones USD.
    mcap_millions = _finite_float(profile.get("marketCapitalization"))
    market_cap = mcap_millions * 1_000_000 if mcap_millions is not None else None

    pe = _finite_float(metric.get("peTTM")) or _finite_float(metric.get("peAnnual"))
    eps = _finite_float(metric.get("epsTTM")) or _finite_float(
        metric.get("epsAnnual")
    )
    sector = _clean_text(profile.get("finnhubIndustry")) or _clean_text(
        profile.get("gicsSector")
    )
    industry = _clean_text(profile.get("finnhubIndustry"))
    name = _clean_text(profile.get("name"))

    has_any = any(
        v is not None for v in (market_cap, pe, eps, sector, industry, name)
    )
    if not has_any:
        return None

    return FundamentalsSnapshot(
        symbol=symbol,
        asset_kind="equity",
        price=price,
        market_cap=market_cap,
        pe=pe,
        eps=eps,
        sector=sector,
        industry=industry if industry != sector else None,
        source="finnhub",
        as_of=_now_iso(),
    )


def _snapshot_from_yfinance(
    symbol: str,
    *,
    price: float | None,
) -> FundamentalsSnapshot | None:
    try:
        import yfinance as yf
    except ImportError:
        return None

    yahoo = yahoo_finance_symbol(symbol)
    try:
        ticker = yf.Ticker(yahoo)
        info = ticker.info if isinstance(getattr(ticker, "info", None), dict) else {}
    except Exception:
        return None

    if not info:
        return None

    market_cap = _finite_float(info.get("marketCap"))
    pe = _finite_float(info.get("trailingPE")) or _finite_float(info.get("forwardPE"))
    eps = _finite_float(info.get("trailingEps")) or _finite_float(
        info.get("forwardEps")
    )
    sector = _clean_text(info.get("sector"))
    industry = _clean_text(info.get("industry"))
    quote_price = price or _finite_float(info.get("currentPrice")) or _finite_float(
        info.get("regularMarketPrice")
    )

    has_any = any(v is not None for v in (market_cap, pe, eps, sector, industry))
    if not has_any and quote_price is None:
        return None

    return FundamentalsSnapshot(
        symbol=symbol,
        asset_kind="equity",
        price=quote_price,
        market_cap=market_cap,
        pe=pe,
        eps=eps,
        sector=sector,
        industry=industry,
        source="yfinance",
        as_of=_now_iso(),
    )


def _crypto_snapshot(symbol: str, *, price: float | None) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=symbol,
        asset_kind="crypto",
        price=price,
        market_cap=None,
        pe=None,
        eps=None,
        sector=None,
        industry=None,
        source="none",
        as_of=_now_iso(),
    )


def _empty_snapshot(symbol: str, *, price: float | None) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=symbol,
        asset_kind="unknown",
        price=price,
        market_cap=None,
        pe=None,
        eps=None,
        sector=None,
        industry=None,
        source="none",
        as_of=_now_iso(),
    )


def fetch_fundamentals_snapshot(
    symbol: str,
    *,
    quote: Quote | None = None,
) -> FundamentalsSnapshot:
    """Snapshot básico: Finnhub → yfinance. Crypto: solo precio honesto."""
    normalized = normalize_symbol(symbol)
    if not normalized:
        return _empty_snapshot("", price=None)

    price = quote.price if quote is not None else None

    if normalized in CRYPTO_FINNHUB_SYMBOLS:
        return _crypto_snapshot(normalized, price=price)

    snap = _snapshot_from_finnhub(normalized, price=price)
    if snap is not None:
        return snap

    snap = _snapshot_from_yfinance(normalized, price=price)
    if snap is not None:
        return snap

    return _empty_snapshot(normalized, price=price)


def _fmt_price(value: float | None) -> str:
    if value is None:
        return _NA
    return f"${value:,.2f}"


def _fmt_mcap(value: float | None) -> str:
    if value is None:
        return _NA
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"


def _fmt_ratio(value: float | None) -> str:
    if value is None:
        return _NA
    return f"{value:.2f}"


def format_fundamentals_markdown(snapshot: FundamentalsSnapshot) -> str:
    """Texto determinístico del bloque Fundamentals (sin lectura buy/sell)."""
    lines = [
        f"**Snapshot** (fuente: {snapshot.source})",
        f"- Precio: {_fmt_price(snapshot.price)}",
        f"- Market cap: {_fmt_mcap(snapshot.market_cap)}",
        f"- P/E: {_fmt_ratio(snapshot.pe)}",
        f"- EPS: {_fmt_ratio(snapshot.eps)}",
        f"- Sector: {snapshot.sector or _NA}",
        f"- Industry: {snapshot.industry or _NA}",
    ]
    if snapshot.asset_kind == "crypto":
        lines.append(
            "- Nota: PE/EPS/market cap equity no aplican a crypto; "
            "solo precio de Market Data cuando hay."
        )
    elif snapshot.source == "none":
        lines.append(
            "- Nota: sin fundamentals de proveedor; campos ausentes = no disponible."
        )
    else:
        lines.append(
            "- Snapshot informativo; no es recomendación de compra/venta."
        )
    return "\n".join(lines)


def format_fundamentals_context(snapshot: FundamentalsSnapshot) -> str:
    """Contexto para el LLM: cifras solo si existen."""
    return (
        f"asset_kind={snapshot.asset_kind}; source={snapshot.source}\n"
        f"{format_fundamentals_markdown(snapshot)}\n"
        "Usá solo estos números; si un campo dice "
        f"'{_NA}', declaralo así — no inventes."
    )
