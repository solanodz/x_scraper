"""Repositorio de versiones de Chart Plan por Operator + Ticker."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Json

from backend.app.db import connect
from backend.services.ticker_catalog import resolve_ticker_input


class ChartPlanRepoError(Exception):
    pass


MAX_VERSIONS = 10
RETENTION_DAYS = 30


def _canonical_symbol(raw: str) -> str:
    resolved = resolve_ticker_input(raw)
    if resolved:
        return resolved
    return str(raw).strip().upper()


def _row_to_version(row: tuple) -> dict[str, Any]:
    version_id, symbol, content, dossier_version_id, created_at = row
    return {
        "id": str(version_id),
        "symbol": symbol,
        "content": content if isinstance(content, dict) else {},
        "dossier_version_id": str(dossier_version_id) if dossier_version_id else None,
        "created_at": created_at,
    }


def save_version(
    *,
    user_id: str,
    symbol: str,
    content: dict,
    dossier_version_id: str | None = None,
) -> dict[str, Any]:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        raise ChartPlanRepoError("symbol required")
    if not isinstance(content, dict):
        raise ChartPlanRepoError("content must be a dict")

    sql = """
        INSERT INTO ticker_chart_plan_versions
            (user_id, symbol, content, dossier_version_id)
        VALUES (%(user_id)s, %(symbol)s, %(content)s, %(dossier_version_id)s)
        RETURNING id, symbol, content, dossier_version_id, created_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "user_id": user_id,
                    "symbol": canonical,
                    "content": Json(content),
                    "dossier_version_id": dossier_version_id,
                },
            )
            row = cur.fetchone()

    if row is None:
        raise ChartPlanRepoError("failed to save chart plan version")

    prune_old_versions(user_id=user_id, symbol=canonical)
    return _row_to_version(row)


def get_latest(*, user_id: str, symbol: str) -> dict[str, Any] | None:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        return None

    sql = """
        SELECT id, symbol, content, dossier_version_id, created_at
        FROM ticker_chart_plan_versions
        WHERE user_id = %(user_id)s AND symbol = %(symbol)s
        ORDER BY created_at DESC
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"user_id": user_id, "symbol": canonical})
            row = cur.fetchone()
    return _row_to_version(row) if row else None


def list_versions(
    *,
    user_id: str,
    symbol: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        return []

    sql = """
        SELECT id, symbol, content, dossier_version_id, created_at
        FROM ticker_chart_plan_versions
        WHERE user_id = %(user_id)s AND symbol = %(symbol)s
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {"user_id": user_id, "symbol": canonical, "limit": limit},
            )
            rows = cur.fetchall()
    return [_row_to_version(row) for row in rows]


def prune_old_versions(*, user_id: str, symbol: str) -> None:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        return

    delete_older_than_retention_sql = """
        DELETE FROM ticker_chart_plan_versions
        WHERE user_id = %(user_id)s
          AND symbol = %(symbol)s
          AND created_at < now() - make_interval(days => %(days)s)
    """
    delete_excess_sql = """
        DELETE FROM ticker_chart_plan_versions
        WHERE id IN (
            SELECT id
            FROM ticker_chart_plan_versions
            WHERE user_id = %(user_id)s AND symbol = %(symbol)s
            ORDER BY created_at DESC
            OFFSET %(max_versions)s
        )
    """
    params = {
        "user_id": user_id,
        "symbol": canonical,
        "days": RETENTION_DAYS,
        "max_versions": MAX_VERSIONS,
    }
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(delete_older_than_retention_sql, params)
            cur.execute(delete_excess_sql, params)


def tables_ready() -> bool:
    sql = """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'ticker_chart_plan_versions'
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return bool(row and int(row[0]) >= 1)
