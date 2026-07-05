"""Repositorio de Signals sobre el Store."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator

from backend.app.db import connect
from backend.app.schemas import ClusterSource, Engagement, SignalDetail, SignalSummary
from backend.app.services.feed_filters import FeedFilters, build_feed_filter_conditions
from backend.services.retrieval import signal_url
from scraper.filters import build_sql_filter


def _engagement_from_row(row: dict[str, Any]) -> Engagement:
    return Engagement(
        reply_count=row["reply_count"],
        retweet_count=row["retweet_count"],
        like_count=row["like_count"],
        quote_count=row["quote_count"],
        bookmarked_count=row["bookmarked_count"],
    )


_SIGNAL_SELECT_COLUMNS = """
    id_str, published_at, username, raw_content, source,
    cashtags, reply_count, retweet_count, like_count,
    quote_count, bookmarked_count, payload,
    source_type, title, summary, body, canonical_url, relevance_score, topic,
    sentiment,
    cluster_id
"""

_SIGNAL_DETAIL_EXTRA = ", hashtags, article"


def _row_to_summary(
    row: dict[str, Any],
    *,
    cluster_sources: list[ClusterSource] | None = None,
) -> SignalSummary:
    payload = row["payload"] if isinstance(row["payload"], dict) else {}
    username = row["username"]
    id_str = row["id_str"]
    source_type = str(row.get("source_type") or "x")
    canonical_url = row.get("canonical_url")
    return SignalSummary(
        id_str=id_str,
        published_at=row["published_at"],
        username=username,
        raw_content=row["raw_content"],
        source=row["source"],
        cashtags=list(row["cashtags"] or []),
        url=signal_url(
            payload,
            username,
            id_str,
            source_type=source_type,
            canonical_url=canonical_url,
        ),
        engagement=_engagement_from_row(row),
        source_type=source_type,
        title=row.get("title"),
        summary=row.get("summary"),
        body=row.get("body"),
        canonical_url=canonical_url,
        relevance_score=row.get("relevance_score"),
        topic=row.get("topic"),
        sentiment=row.get("sentiment"),
        cluster_id=row.get("cluster_id"),
        cluster_sources=cluster_sources or [],
    )


def _row_to_detail(
    row: dict[str, Any],
    *,
    cluster_sources: list[ClusterSource] | None = None,
) -> SignalDetail:
    summary = _row_to_summary(row, cluster_sources=cluster_sources)
    payload = row["payload"] if isinstance(row["payload"], dict) else {}
    article = row.get("article")
    if article is not None and not isinstance(article, dict):
        article = None
    return SignalDetail(
        **summary.model_dump(),
        hashtags=list(row["hashtags"] or []),
        article=article,
        payload=payload,
    )


def _fetchone_as_dict(cur, row) -> dict[str, Any]:
    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))


def _fetchall_as_dicts(cur) -> list[dict[str, Any]]:
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def _cluster_sources_map(cluster_ids: list[str]) -> dict[str, list[ClusterSource]]:
    cleaned = [cid for cid in cluster_ids if cid]
    if not cleaned:
        return {}

    sql = """
        SELECT cluster_id, id_str, source_type, username
        FROM signals
        WHERE cluster_id = ANY(%(cluster_ids)s)
        ORDER BY published_at DESC
    """
    grouped: dict[str, list[ClusterSource]] = {}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"cluster_ids": cleaned})
            for cluster_id, id_str, source_type, username in cur.fetchall():
                key = str(cluster_id)
                grouped.setdefault(key, []).append(
                    ClusterSource(
                        id_str=id_str,
                        source_type=str(source_type or "x"),
                        username=str(username or ""),
                    )
                )
    return grouped


def _attach_cluster_sources(signals: list[SignalSummary]) -> list[SignalSummary]:
    if not signals:
        return signals

    cluster_ids = [s.cluster_id for s in signals if s.cluster_id]
    sources_map = _cluster_sources_map(cluster_ids)
    if not sources_map:
        return signals

    enriched: list[SignalSummary] = []
    for signal in signals:
        if not signal.cluster_id:
            enriched.append(signal)
            continue
        members = sources_map.get(signal.cluster_id, [])
        if not members:
            enriched.append(signal)
            continue
        enriched.append(signal.model_copy(update={"cluster_sources": members}))
    return enriched


def _clustered_list_sql(where_clause: str) -> str:
    return f"""
        WITH filtered AS (
            SELECT {_SIGNAL_SELECT_COLUMNS}
            FROM signals
            WHERE {where_clause}
        ),
        ranked AS (
            SELECT
                filtered.*,
                ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(cluster_id, id_str)
                    ORDER BY published_at DESC
                ) AS cluster_rn
            FROM filtered
        )
        SELECT
            id_str, published_at, username, raw_content, source,
            cashtags, reply_count, retweet_count, like_count,
            quote_count, bookmarked_count, payload,
            source_type, title, summary, body, canonical_url, relevance_score, topic,
    sentiment,
            cluster_id
        FROM ranked
        WHERE cluster_rn = 1
        ORDER BY published_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """


def list_signals(
    *,
    limit: int = 50,
    offset: int = 0,
    filters: FeedFilters | None = None,
    username: str | None = None,
    ticker: str | None = None,
) -> list[SignalSummary]:
    """Lista representantes de Story Cluster ordenados por fecha (más reciente primero)."""
    conditions = ["TRUE"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    relevance_sql, relevance_params = build_sql_filter()
    if relevance_sql != "TRUE":
        conditions.append(f"({relevance_sql})")
        params.update(relevance_params)

    merged = FeedFilters(
        q=(filters.q if filters else None),
        ticker=(filters.ticker if filters else None) or ticker,
        username=(filters.username if filters else None) or username,
        source_type=filters.source_type if filters else None,
        topic=filters.topic if filters else None,
        since_hours=filters.since_hours if filters else None,
        sentiment=filters.sentiment if filters else None,
    )
    filter_conditions, filter_params = build_feed_filter_conditions(merged)
    conditions.extend(filter_conditions)
    params.update(filter_params)

    where_clause = " AND ".join(conditions)
    sql = _clustered_list_sql(where_clause)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _fetchall_as_dicts(cur)

    summaries = [_row_to_summary(row) for row in rows]
    return _attach_cluster_sources(summaries)


def get_signal(id_str: str) -> SignalDetail | None:
    """Obtiene un Signal por id_str."""
    sql = f"""
        SELECT {_SIGNAL_SELECT_COLUMNS}{_SIGNAL_DETAIL_EXTRA}
        FROM signals
        WHERE id_str = %(id_str)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id_str": id_str})
            row = cur.fetchone()
            if row is None:
                return None
            detail_row = _fetchone_as_dict(cur, row)

    cluster_sources: list[ClusterSource] = []
    cluster_id = detail_row.get("cluster_id")
    if cluster_id:
        sources_map = _cluster_sources_map([str(cluster_id)])
        cluster_sources = sources_map.get(str(cluster_id), [])

    return _row_to_detail(detail_row, cluster_sources=cluster_sources)


def _since_published_at(since_id_str: str | None, since_ts: datetime | None) -> datetime | None:
    if since_ts is not None:
        return since_ts
    if not since_id_str:
        return None
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT published_at FROM signals WHERE id_str = %(id_str)s",
                {"id_str": since_id_str},
            )
            row = cur.fetchone()
            return row[0] if row else None


def poll_new_signals(
    *,
    since_id_str: str | None = None,
    since_ts: datetime | None = None,
    seen_ids: set[str] | None = None,
) -> list[SignalSummary]:
    """Signals nuevos desde un cursor (published_at o id_str no visto)."""
    seen = seen_ids or set()
    anchor = _since_published_at(since_id_str, since_ts)

    conditions = ["TRUE"]
    params: dict[str, Any] = {}

    relevance_sql, relevance_params = build_sql_filter()
    if relevance_sql != "TRUE":
        conditions.append(f"({relevance_sql})")
        params.update(relevance_params)

    if anchor is not None:
        conditions.append("published_at > %(anchor)s")
        params["anchor"] = anchor

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT {_SIGNAL_SELECT_COLUMNS}
        FROM signals
        WHERE {where_clause}
        ORDER BY published_at ASC
        LIMIT 100
    """

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _fetchall_as_dicts(cur)

    results: list[SignalSummary] = []
    for row in rows:
        row_id = row["id_str"]
        if row_id in seen:
            continue
        results.append(_row_to_summary(row))

    return _attach_cluster_sources(results)


def iter_poll_new_signals(
    *,
    since_id_str: str | None = None,
    since_ts: datetime | None = None,
    poll_interval: float = 2.0,
) -> Iterator[list[SignalSummary]]:
    """Generador infinito que emite lotes de Signals nuevos cada poll_interval."""
    import time

    seen: set[str] = set()
    if since_id_str:
        seen.add(since_id_str)

    while True:
        batch = poll_new_signals(
            since_id_str=since_id_str,
            since_ts=since_ts,
            seen_ids=seen,
        )
        for signal in batch:
            seen.add(signal.id_str)
        yield batch
        time.sleep(poll_interval)
