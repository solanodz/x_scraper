"""Filtros del Signal Feed (lista REST + criterios compartidos)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.services.retrieval import normalize_ticker

VALID_SOURCE_TYPES = frozenset({"x", "rss", "marketaux", "alpha_vantage", "news"})
VALID_SENTIMENTS = frozenset({"positive", "negative", "neutral", "bullish", "bearish"})


@dataclass(frozen=True)
class FeedFilters:
    q: str | None = None
    ticker: str | None = None
    username: str | None = None
    source_type: str | None = None
    topic: str | None = None
    since_hours: int | None = None
    sentiment: str | None = None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _keyword_terms(query: str | None) -> list[str]:
    if not query:
        return []
    return [part for part in query.split() if part.strip()]


def build_feed_filter_conditions(
    filters: FeedFilters,
) -> tuple[list[str], dict[str, Any]]:
    """Devuelve fragmentos SQL AND y parámetros para list_signals."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    for index, term in enumerate(_keyword_terms(filters.q)):
        key = f"q_{index}"
        params[key] = f"%{term}%"
        conditions.append(
            "("
            "COALESCE(title, '') || ' ' || "
            "COALESCE(summary, '') || ' ' || "
            "COALESCE(body, '') || ' ' || "
            "COALESCE(raw_content, '') || ' ' || "
            "COALESCE(topic, '') || ' ' || "
            "COALESCE(username, '') || ' ' || "
            "COALESCE(array_to_string(tickers, ' '), '') || ' ' || "
            "COALESCE(array_to_string(cashtags, ' '), '')"
            f") ILIKE %({key})s"
        )

    normalized_ticker = normalize_ticker(filters.ticker)
    if normalized_ticker:
        params["ticker"] = normalized_ticker
        params["ticker_pattern"] = f"%{normalized_ticker}%"
        conditions.append(
            "("
            "%(ticker)s = ANY(cashtags) OR ('$' || %(ticker)s) = ANY(cashtags) "
            "OR %(ticker)s = ANY(tickers) OR ('$' || %(ticker)s) = ANY(tickers) "
            "OR COALESCE(title, '') ILIKE %(ticker_pattern)s "
            "OR COALESCE(summary, '') ILIKE %(ticker_pattern)s "
            "OR COALESCE(raw_content, '') ILIKE %(ticker_pattern)s"
            ")"
        )

    username = _clean_text(filters.username)
    if username:
        params["username"] = username.lstrip("@")
        conditions.append("username ILIKE %(username_pattern)s")
        params["username_pattern"] = f"%{params['username']}%"

    source_type = _clean_text(filters.source_type)
    if source_type:
        lowered = source_type.lower()
        if lowered == "news":
            conditions.append(
                "source_type IN ('rss', 'marketaux', 'alpha_vantage')"
            )
        elif lowered == "x":
            conditions.append("(source_type = 'x' OR source_type IS NULL)")
        elif lowered in VALID_SOURCE_TYPES:
            conditions.append("source_type = %(source_type)s")
            params["source_type"] = lowered

    topic = _clean_text(filters.topic)
    if topic:
        params["topic"] = f"%{topic}%"
        conditions.append("COALESCE(topic, '') ILIKE %(topic)s")

    if filters.since_hours is not None and filters.since_hours > 0:
        params["since_hours"] = int(filters.since_hours)
        conditions.append(
            "published_at >= now() - (%(since_hours)s * interval '1 hour')"
        )

    sentiment = _clean_text(filters.sentiment)
    if sentiment:
        lowered = sentiment.lower()
        if lowered in VALID_SENTIMENTS:
            params["sentiment"] = lowered
            conditions.append("lower(COALESCE(sentiment, '')) = %(sentiment)s")

    return conditions, params


def feed_filters_from_query(
    *,
    q: str | None = None,
    ticker: str | None = None,
    username: str | None = None,
    source_type: str | None = None,
    topic: str | None = None,
    since_hours: int | None = None,
    sentiment: str | None = None,
) -> FeedFilters:
    return FeedFilters(
        q=_clean_text(q),
        ticker=_clean_text(ticker),
        username=_clean_text(username),
        source_type=_clean_text(source_type),
        topic=_clean_text(topic),
        since_hours=since_hours,
        sentiment=_clean_text(sentiment),
    )
