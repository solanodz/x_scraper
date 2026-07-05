"""Búsqueda semántica sobre el Vector Index (pgvector)."""

from __future__ import annotations

from typing import Any

from scraper.embeddings import embed_texts
from scraper.filters import build_sql_filter
from scraper.store import connect

from backend.services.types import SignalHit

SEARCH_BASE_SQL = """
SELECT
    id_str,
    username,
    raw_content,
    published_at,
    source,
    payload,
    1 - (embedding <=> %(query_vector)s::vector) AS similarity
FROM signals
WHERE {where_clause}
ORDER BY embedding <=> %(query_vector)s::vector
LIMIT %(limit)s
"""


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


def retrieve(
    query: str,
    limit: int = 10,
    ticker: str | None = None,
    since_hours: int | None = None,
) -> list[SignalHit]:
    """Recupera Signals por similitud semántica con filtros opcionales."""
    query_vector = _format_embedding(embed_texts([query])[0])
    normalized_ticker = normalize_ticker(ticker)

    conditions = ["embedding IS NOT NULL"]
    params: dict[str, Any] = {
        "query_vector": query_vector,
        "limit": limit,
    }

    relevance_sql, relevance_params = build_sql_filter()
    if relevance_sql != "TRUE":
        conditions.append(f"({relevance_sql})")
        params.update(relevance_params)

    if normalized_ticker:
        conditions.append(
            "(%(ticker)s = ANY(cashtags) OR ('$' || %(ticker)s) = ANY(cashtags) "
            "OR %(ticker)s = ANY(tickers) OR ('$' || %(ticker)s) = ANY(tickers))"
        )
        params["ticker"] = normalized_ticker

    if since_hours is not None:
        conditions.append(
            "published_at >= now() - make_interval(hours => %(since_hours)s)"
        )
        params["since_hours"] = since_hours

    sql = SEARCH_BASE_SQL.format(where_clause=" AND ".join(conditions))

    hits: list[SignalHit] = []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            for row in cur.fetchall():
                id_str, username, raw_content, published_at, source, payload, similarity = row
                payload_dict = payload if isinstance(payload, dict) else {}
                hits.append(
                    SignalHit(
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
                )
    return hits
