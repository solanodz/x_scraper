"""Agregaciones del Corpus para análisis de tendencias."""

from __future__ import annotations

from typing import Any

from scraper.store import connect

from backend.services.ticker_catalog import append_ticker_match_conditions


def _base_conditions(
    *,
    hours: int,
    ticker: str | None,
) -> tuple[list[str], dict[str, Any]]:
    conditions = [
        "published_at >= now() - make_interval(hours => %(hours)s)",
    ]
    params: dict[str, Any] = {"hours": max(1, int(hours))}
    append_ticker_match_conditions(conditions, params, raw_ticker=ticker)
    return conditions, params


def get_corpus_stats(
    *,
    hours: int = 168,
    ticker: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Estadísticas agregadas del Corpus en una ventana temporal."""
    effective_limit = max(1, min(int(limit), 50))
    conditions, params = _base_conditions(hours=hours, ticker=ticker)
    where_clause = " AND ".join(conditions)
    params["limit"] = effective_limit

    total_signals = 0
    by_source_type: dict[str, int] = {}
    top_topics: list[dict[str, Any]] = []
    top_tickers: list[dict[str, Any]] = []

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*)::int FROM signals WHERE {where_clause}",
                params,
            )
            row = cur.fetchone()
            total_signals = int(row[0]) if row else 0

            cur.execute(
                f"""
                SELECT COALESCE(source_type, 'x') AS source_type, count(*)::int AS cnt
                FROM signals
                WHERE {where_clause}
                GROUP BY 1
                ORDER BY cnt DESC
                """,
                params,
            )
            for source_type, cnt in cur.fetchall():
                by_source_type[str(source_type)] = int(cnt)

            cur.execute(
                f"""
                SELECT topic, count(*)::int AS cnt
                FROM signals
                WHERE {where_clause}
                  AND topic IS NOT NULL
                  AND trim(topic) <> ''
                GROUP BY topic
                ORDER BY cnt DESC, topic ASC
                LIMIT %(limit)s
                """,
                params,
            )
            for topic, cnt in cur.fetchall():
                top_topics.append({"topic": str(topic), "count": int(cnt)})

            cur.execute(
                f"""
                SELECT
                    upper(regexp_replace(t, '^\\$', '')) AS ticker,
                    count(*)::int AS cnt
                FROM signals,
                     unnest(tickers) AS t
                WHERE {where_clause}
                  AND t IS NOT NULL
                  AND trim(t) <> ''
                GROUP BY 1
                ORDER BY cnt DESC, ticker ASC
                LIMIT %(limit)s
                """,
                params,
            )
            for sym, cnt in cur.fetchall():
                top_tickers.append({"ticker": str(sym), "count": int(cnt)})

    return {
        "hours": params["hours"],
        "ticker_filter": ticker,
        "total_signals": total_signals,
        "by_source_type": by_source_type,
        "top_topics": top_topics,
        "top_tickers": top_tickers,
    }
