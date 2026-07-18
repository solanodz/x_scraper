"""Tickers dinámicos desde el Corpus + resolución de nombres (Intel → INTC)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.db import connect
from backend.services.market_data import (
    CURATED_EXTRA_SYMBOLS,
    CURATED_TICKER_LABELS,
    TickerSuggestion,
    normalize_symbol,
)

# Anclas del carrusel cuando el Corpus aún no tiene volumen.
STRIP_ANCHOR_SYMBOLS: tuple[str, ...] = ("BTC", "ETH", "SPY", "QQQ")

_NAME_TO_SYMBOL: dict[str, str] = {
    name.lower(): symbol for symbol, name in CURATED_TICKER_LABELS.items()
}


@dataclass(frozen=True)
class TickerMatch:
    """Símbolo canónico y variantes de texto para búsqueda en Signals."""

    symbol: str
    patterns: tuple[str, ...]


def resolve_ticker_input(raw: str | None) -> str | None:
    """Resuelve ticker o nombre de empresa a símbolo US (ej. Intel → INTC)."""
    if not raw or not str(raw).strip():
        return None

    text = str(raw).strip()
    as_symbol = normalize_symbol(text)
    if as_symbol in CURATED_TICKER_LABELS or as_symbol in CURATED_EXTRA_SYMBOLS:
        return as_symbol

    lower = text.lower()
    if lower in _NAME_TO_SYMBOL:
        return _NAME_TO_SYMBOL[lower]

    # Símbolo explícito en MAYÚSCULAS (NVDA, AMD). Sin fuzzy substring de nombres
    # (evita "mas" → Mastercard, "esta" → ESTA).
    if text.isupper() and as_symbol.isalpha():
        if len(as_symbol) == 2:
            if as_symbol in CURATED_TICKER_LABELS or as_symbol in CURATED_EXTRA_SYMBOLS:
                return as_symbol
            return None
        if 3 <= len(as_symbol) <= 6:
            return as_symbol

    return None


def build_ticker_match(raw: str | None) -> TickerMatch | None:
    symbol = resolve_ticker_input(raw)
    if not symbol:
        return None

    patterns: list[str] = [symbol, f"${symbol}"]
    label = CURATED_TICKER_LABELS.get(symbol)
    if label:
        patterns.append(label)
    # dedupe preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for p in patterns:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return TickerMatch(symbol=symbol, patterns=tuple(unique))


def append_ticker_match_conditions(
    conditions: list[str],
    params: dict[str, Any],
    *,
    raw_ticker: str | None,
    param_prefix: str = "ticker",
) -> str | None:
    """Agrega SQL OR para cashtags, tickers y texto (nombre de empresa). Devuelve símbolo."""
    match = build_ticker_match(raw_ticker)
    if match is None:
        return None

    parts: list[str] = [
        f"%({param_prefix})s = ANY(cashtags)",
        f"('$' || %({param_prefix})s) = ANY(cashtags)",
        f"%({param_prefix})s = ANY(tickers)",
        f"('$' || %({param_prefix})s) = ANY(tickers)",
    ]
    params[param_prefix] = match.symbol

    for index, pattern in enumerate(match.patterns):
        key = f"{param_prefix}_pat_{index}"
        params[key] = f"%{pattern}%"
        parts.append(
            "("
            f"COALESCE(title, '') ILIKE %({key})s OR "
            f"COALESCE(summary, '') ILIKE %({key})s OR "
            f"COALESCE(raw_content, '') ILIKE %({key})s"
            ")"
        )

    conditions.append("(" + " OR ".join(parts) + ")")
    return match.symbol


def _distinct_tags_sql(where_extra: str = "") -> str:
    return f"""
        SELECT upper(regexp_replace(tag, '^\\$', '')) AS symbol, count(*)::int AS cnt
        FROM signals,
             unnest(
                 COALESCE(cashtags, ARRAY[]::text[])
                 || COALESCE(tickers, ARRAY[]::text[])
             ) AS tag
        WHERE tag IS NOT NULL
          AND trim(tag) <> ''
          {where_extra}
        GROUP BY 1
        ORDER BY cnt DESC, symbol ASC
    """


def fetch_corpus_ticker_symbols(
    *,
    prefix: str = "",
    limit: int = 50,
    since_days: int = 30,
) -> list[str]:
    """Tickers que aparecen en Signals del Corpus (cashtags + tickers)."""
    limit = max(1, min(limit, 100))
    prefix_clean = prefix.strip().lstrip("$").upper()

    params: dict[str, Any] = {"limit": limit, "since_days": since_days}
    where_parts = ["AND published_at >= now() - make_interval(days => %(since_days)s)"]
    if prefix_clean:
        params["prefix"] = f"{prefix_clean}%"
        where_parts.append("AND upper(regexp_replace(tag, '^\\$', '')) LIKE %(prefix)s")

    sql = _distinct_tags_sql(" ".join(where_parts)) + " LIMIT %(limit)s"

    symbols: list[str] = []
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    sym = str(row[0]).strip().upper()
                    if sym and sym not in symbols:
                        symbols.append(sym)
    except Exception:
        return []

    return symbols


def get_quote_strip_symbols(*, limit: int = 24) -> list[str]:
    """Símbolos del carrusel: anclas + top tickers del Corpus (sin WATCHLIST)."""
    limit = max(1, min(limit, 40))
    ordered: list[str] = []
    seen: set[str] = set()

    for symbol in STRIP_ANCHOR_SYMBOLS:
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)

    for symbol in fetch_corpus_ticker_symbols(limit=limit * 2, since_days=14):
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
        if len(ordered) >= limit:
            break

    return ordered[:limit]


def search_ticker_suggestions(prefix: str = "", *, limit: int = 50) -> list[TickerSuggestion]:
    """Autocompletado: Corpus primero, luego catálogo curado."""
    limit = max(1, min(limit, 100))
    prefix_clean = prefix.strip().lstrip("$").upper()

    results: list[TickerSuggestion] = []
    seen: set[str] = set()

    for symbol in fetch_corpus_ticker_symbols(prefix=prefix_clean, limit=limit):
        seen.add(symbol)
        results.append(
            TickerSuggestion(
                symbol=symbol,
                description=CURATED_TICKER_LABELS.get(symbol, ""),
                source="corpus",
            )
        )
        if len(results) >= limit:
            return results

    for symbol in CURATED_EXTRA_SYMBOLS:
        if prefix_clean and not symbol.startswith(prefix_clean):
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        results.append(
            TickerSuggestion(
                symbol=symbol,
                description=CURATED_TICKER_LABELS.get(symbol, ""),
                source="curated",
            )
        )
        if len(results) >= limit:
            break

    for symbol, label in sorted(CURATED_TICKER_LABELS.items()):
        if prefix_clean and not symbol.startswith(prefix_clean):
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        results.append(
            TickerSuggestion(symbol=symbol, description=label, source="curated")
        )
        if len(results) >= limit:
            break

    return results
