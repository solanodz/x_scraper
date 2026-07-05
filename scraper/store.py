"""Persistencia de Signals en el Store (Postgres)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json

DEFAULT_DSN = "postgresql://xscraper:xscraper@localhost:5433/xscraper"

_COMMON_COLUMNS = """
    id_str,
    published_at,
    username,
    raw_content,
    source,
    cashtags,
    hashtags,
    article,
    reply_count,
    retweet_count,
    like_count,
    quote_count,
    bookmarked_count,
    payload,
    source_type,
    canonical_url,
    title,
    body,
    summary,
    tickers,
    sentiment,
    topic,
    relevance_score,
    cluster_id,
    ingested_at
"""

_COMMON_VALUES = """
    %(id_str)s,
    %(published_at)s,
    %(username)s,
    %(raw_content)s,
    %(source)s,
    %(cashtags)s,
    %(hashtags)s,
    %(article)s,
    %(reply_count)s,
    %(retweet_count)s,
    %(like_count)s,
    %(quote_count)s,
    %(bookmarked_count)s,
    %(payload)s,
    %(source_type)s,
    %(canonical_url)s,
    %(title)s,
    %(body)s,
    %(summary)s,
    %(tickers)s,
    %(sentiment)s,
    %(topic)s,
    %(relevance_score)s,
    %(cluster_id)s,
    now()
"""

UPSERT_SQL = f"""
INSERT INTO signals ({_COMMON_COLUMNS})
VALUES ({_COMMON_VALUES})
ON CONFLICT (id_str) DO UPDATE SET
    title = EXCLUDED.title,
    summary = EXCLUDED.summary,
    body = COALESCE(EXCLUDED.body, signals.body),
    raw_content = CASE
        WHEN EXCLUDED.body IS NOT NULL THEN EXCLUDED.raw_content
        ELSE COALESCE(signals.raw_content, EXCLUDED.raw_content)
    END,
    tickers = EXCLUDED.tickers,
    sentiment = EXCLUDED.sentiment,
    topic = EXCLUDED.topic,
    relevance_score = EXCLUDED.relevance_score,
    canonical_url = EXCLUDED.canonical_url,
    cluster_id = COALESCE(EXCLUDED.cluster_id, signals.cluster_id),
    source_type = EXCLUDED.source_type,
    payload = EXCLUDED.payload,
    reply_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.reply_count
        ELSE signals.reply_count
    END,
    retweet_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.retweet_count
        ELSE signals.retweet_count
    END,
    like_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.like_count
        ELSE signals.like_count
    END,
    quote_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.quote_count
        ELSE signals.quote_count
    END,
    bookmarked_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.bookmarked_count
        ELSE signals.bookmarked_count
    END
"""

UPSERT_WITH_EMBEDDING_SQL = f"""
INSERT INTO signals ({_COMMON_COLUMNS}, embedding)
VALUES ({_COMMON_VALUES}, %(embedding)s::vector)
ON CONFLICT (id_str) DO UPDATE SET
    title = EXCLUDED.title,
    summary = EXCLUDED.summary,
    body = COALESCE(EXCLUDED.body, signals.body),
    raw_content = CASE
        WHEN EXCLUDED.body IS NOT NULL THEN EXCLUDED.raw_content
        ELSE COALESCE(signals.raw_content, EXCLUDED.raw_content)
    END,
    tickers = EXCLUDED.tickers,
    sentiment = EXCLUDED.sentiment,
    topic = EXCLUDED.topic,
    relevance_score = EXCLUDED.relevance_score,
    canonical_url = EXCLUDED.canonical_url,
    cluster_id = COALESCE(EXCLUDED.cluster_id, signals.cluster_id),
    source_type = EXCLUDED.source_type,
    payload = EXCLUDED.payload,
    embedding = EXCLUDED.embedding,
    reply_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.reply_count
        ELSE signals.reply_count
    END,
    retweet_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.retweet_count
        ELSE signals.retweet_count
    END,
    like_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.like_count
        ELSE signals.like_count
    END,
    quote_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.quote_count
        ELSE signals.quote_count
    END,
    bookmarked_count = CASE
        WHEN EXCLUDED.source_type = 'x' THEN EXCLUDED.bookmarked_count
        ELSE signals.bookmarked_count
    END
"""


def get_dsn() -> str:
    load_dotenv()
    return os.getenv("DATABASE_URL", DEFAULT_DSN).strip() or DEFAULT_DSN


def _connect_kwargs(dsn: str) -> dict[str, Any]:
    """PgBouncer (Supabase transaction pooler) no soporta prepared statements."""
    lowered = dsn.lower()
    if "pooler" in lowered or ":6543/" in lowered or ":6543?" in lowered:
        return {"prepare_threshold": None}
    return {}


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    dsn = get_dsn()
    conn = psycopg.connect(dsn, **_connect_kwargs(dsn))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _as_text_list(value: Any) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


def _format_embedding(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.8g}" for value in embedding) + "]"


def record_to_params(record: dict[str, Any]) -> dict[str, Any]:
    user = record.get("user") or {}
    cashtags = _as_text_list(record.get("cashtags"))
    tickers = _as_text_list(record.get("tickers"))
    if not tickers and cashtags:
        tickers = [tag.lstrip("$").upper() for tag in cashtags if tag.strip()]
    if not cashtags and tickers:
        cashtags = [f"${tag.lstrip('$')}" for tag in tickers if tag.strip()]

    relevance_score = record.get("relevance_score")
    if relevance_score is not None:
        try:
            relevance_score = float(relevance_score)
            relevance_score = min(max(relevance_score, 0.0), 1.0)
        except (TypeError, ValueError):
            relevance_score = None

    return {
        "id_str": record.get("id_str") or str(record.get("id")),
        "published_at": record["date"],
        "username": user.get("username") or "",
        "raw_content": record.get("rawContent") or "",
        "source": record.get("source") or "",
        "cashtags": cashtags,
        "hashtags": _as_text_list(record.get("hashtags")),
        "article": Json(record.get("article")) if record.get("article") else None,
        "reply_count": int(record.get("replyCount") or 0),
        "retweet_count": int(record.get("retweetCount") or 0),
        "like_count": int(record.get("likeCount") or 0),
        "quote_count": int(record.get("quoteCount") or 0),
        "bookmarked_count": int(record.get("bookmarkedCount") or 0),
        "payload": Json(record),
        "source_type": record.get("source_type") or "x",
        "canonical_url": record.get("canonical_url"),
        "title": record.get("title"),
        "body": record.get("body"),
        "summary": record.get("summary"),
        "tickers": tickers,
        "sentiment": record.get("sentiment"),
        "topic": record.get("topic"),
        "relevance_score": relevance_score,
        "cluster_id": record.get("cluster_id"),
    }


def upsert_signals(
    records: list[dict[str, Any]],
    embeddings: list[list[float]] | None = None,
) -> int:
    """Persiste Signals con UPSERT por id_str. Devuelve filas afectadas."""
    if not records:
        return 0

    if embeddings is not None and len(embeddings) != len(records):
        raise ValueError("embeddings debe tener la misma longitud que records")

    params = [record_to_params(record) for record in records]
    sql = UPSERT_SQL

    if embeddings is not None:
        sql = UPSERT_WITH_EMBEDDING_SQL
        for param, embedding in zip(params, embeddings):
            param["embedding"] = _format_embedding(embedding)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, params)
            return cur.rowcount


_EMBEDDING_BACKFILL_COLUMNS = """
    id_str, title, summary, body, raw_content, article
"""


def _row_to_embedding_record(row: tuple, columns: list[str]) -> dict[str, Any]:
    data = dict(zip(columns, row))
    return {
        "id_str": data["id_str"],
        "title": data.get("title"),
        "summary": data.get("summary"),
        "body": data.get("body"),
        "rawContent": data.get("raw_content") or "",
        "article": data.get("article"),
    }


def fetch_signals_without_embedding(limit: int) -> list[dict[str, Any]]:
    """Signals sin embedding, más recientes primero, como dicts para build_embedding_document."""
    sql = f"""
        SELECT {_EMBEDDING_BACKFILL_COLUMNS}
        FROM signals
        WHERE embedding IS NULL
        ORDER BY published_at DESC
        LIMIT %s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            columns = [desc[0] for desc in cur.description]
            return [_row_to_embedding_record(row, columns) for row in cur.fetchall()]


def update_embeddings(id_str: str, embedding: list[float]) -> None:
    """Actualiza el embedding de un Signal por id_str."""
    sql = "UPDATE signals SET embedding = %s::vector WHERE id_str = %s"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (_format_embedding(embedding), id_str))


_BODY_BACKFILL_COLUMNS = """
    id_str, title, summary, body, canonical_url, source_type
"""


def fetch_signals_needing_body(limit: int) -> list[dict[str, Any]]:
    """Noticias recientes sin Article Body completo (para backfill trafilatura)."""
    sql = f"""
        SELECT {_BODY_BACKFILL_COLUMNS}
        FROM signals
        WHERE source_type IN ('rss', 'marketaux', 'alpha_vantage')
          AND canonical_url IS NOT NULL
          AND length(trim(canonical_url)) > 0
          AND (
            body IS NULL
            OR length(trim(body)) < 200
            OR body = summary
          )
        ORDER BY published_at DESC
        LIMIT %s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def update_signal_body(
    id_str: str,
    *,
    body: str,
    raw_content: str,
) -> None:
    """Persiste Article Body extraído sin re-ingestar el Signal completo."""
    sql = """
        UPDATE signals
        SET body = %s,
            raw_content = %s
        WHERE id_str = %s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (body, raw_content, id_str))
