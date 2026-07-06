"""Búsqueda semántica sobre el Vector Index (pgvector)."""

from __future__ import annotations

from typing import Any

from scraper.embeddings import embed_texts
from scraper.filters import build_sql_filter
from scraper.store import connect

from backend.services.ticker_catalog import (
    append_ticker_match_conditions,
    build_ticker_match,
)
from backend.services.types import SignalHit

SEARCH_BASE_SQL = """
SELECT
    id_str,
    username,
    COALESCE(NULLIF(title, ''), raw_content) AS raw_content,
    published_at,
    source,
    payload,
    1 - (embedding <=> %(query_vector)s::vector) AS similarity
FROM signals
WHERE {where_clause}
ORDER BY embedding <=> %(query_vector)s::vector
LIMIT %(limit)s
"""

KEYWORD_SEARCH_SQL = """
SELECT
    id_str,
    username,
    COALESCE(NULLIF(title, ''), raw_content) AS raw_content,
    published_at,
    source,
    payload,
    0.5 AS similarity
FROM signals
WHERE {where_clause}
ORDER BY published_at DESC
LIMIT %(limit)s
"""

_STOPWORDS = frozenset({
    "de",
    "la",
    "el",
    "en",
    "y",
    "the",
    "a",
    "an",
    "for",
    "about",
    "última",
    "ultima",
    "noticia",
    "noticias",
})


def _format_embedding(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.8g}" for value in embedding) + "]"


def normalize_ticker(ticker: str | None) -> str | None:
    """Normaliza un Ticker: quita $ y pasa a mayúsculas."""
    if not ticker:
        return None
    normalized = ticker.strip().lstrip("$").upper()
    return normalized or None


def signal_url(
    payload: dict[str, Any],
    username: str,
    id_str: str,
    *,
    source_type: str = "x",
    canonical_url: str | None = None,
) -> str:
    """URL del Signal desde canonical_url, payload o construida desde username/id_str."""
    if source_type != "x" and canonical_url:
        return str(canonical_url)
    if source_type != "x":
        url = payload.get("canonical_url")
        if url:
            return str(url)
    url = payload.get("url")
    if url:
        return str(url)
    return f"https://x.com/{username}/status/{id_str}"


def excerpt(text: str, max_len: int = 200) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _extract_keywords(query: str) -> list[str]:
    keywords: list[str] = []
    for part in query.split():
        cleaned = part.strip().strip(".,!?;:")
        if not cleaned or cleaned.lower() in _STOPWORDS:
            continue
        keywords.append(cleaned)
    return keywords


def _row_to_signal_hit(row: tuple[Any, ...]) -> SignalHit:
    id_str, username, raw_content, published_at, source, payload, similarity = row
    payload_dict = payload if isinstance(payload, dict) else {}
    return SignalHit(
        id_str=id_str,
        username=username,
        raw_content=raw_content,
        published_at=published_at,
        source=source,
        similarity=float(similarity),
        url=signal_url(
            payload_dict,
            username,
            id_str,
            source_type=str(payload_dict.get("source_type") or "x"),
            canonical_url=payload_dict.get("canonical_url"),
        ),
    )


def _append_common_filters(
    conditions: list[str],
    params: dict[str, Any],
    *,
    ticker: str | None,
    since_hours: int | None,
) -> None:
    append_ticker_match_conditions(
        conditions,
        params,
        raw_ticker=ticker,
    )

    if since_hours is not None:
        conditions.append(
            "published_at >= now() - make_interval(hours => %(since_hours)s)"
        )
        params["since_hours"] = since_hours


def search_by_keywords(
    query: str,
    limit: int = 10,
    ticker: str | None = None,
    since_hours: int | None = None,
) -> list[SignalHit]:
    """Recupera Signals por coincidencia de keywords en title/summary/raw_content."""
    keywords = _extract_keywords(query)
    match = build_ticker_match(ticker)
    if not keywords and match is None:
        return []

    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit}

    relevance_sql, relevance_params = build_sql_filter()
    if relevance_sql != "TRUE":
        conditions.append(f"({relevance_sql})")
        params.update(relevance_params)

    _append_common_filters(
        conditions,
        params,
        ticker=ticker,
        since_hours=since_hours,
    )

    for index, keyword in enumerate(keywords):
        key = f"kw_{index}"
        params[key] = f"%{keyword}%"
        conditions.append(
            "("
            f"COALESCE(title, '') ILIKE %({key})s OR "
            f"COALESCE(summary, '') ILIKE %({key})s OR "
            f"COALESCE(raw_content, '') ILIKE %({key})s"
            ")"
        )

    sql = KEYWORD_SEARCH_SQL.format(where_clause=" AND ".join(conditions))

    hits: list[SignalHit] = []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            for row in cur.fetchall():
                hits.append(_row_to_signal_hit(row))
    return hits


def retrieve(
    query: str,
    limit: int = 10,
    ticker: str | None = None,
    since_hours: int | None = None,
) -> list[SignalHit]:
    """Recupera Signals por similitud semántica; fallback a keywords si no hay hits."""
    query_vector = _format_embedding(embed_texts([query])[0])

    conditions = ["embedding IS NOT NULL"]
    params: dict[str, Any] = {
        "query_vector": query_vector,
        "limit": limit,
    }

    relevance_sql, relevance_params = build_sql_filter()
    if relevance_sql != "TRUE":
        conditions.append(f"({relevance_sql})")
        params.update(relevance_params)

    _append_common_filters(
        conditions,
        params,
        ticker=ticker,
        since_hours=since_hours,
    )

    sql = SEARCH_BASE_SQL.format(where_clause=" AND ".join(conditions))

    hits: list[SignalHit] = []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            for row in cur.fetchall():
                hits.append(_row_to_signal_hit(row))

    if hits:
        return hits
    return search_by_keywords(query, limit=limit, ticker=ticker, since_hours=since_hours)
