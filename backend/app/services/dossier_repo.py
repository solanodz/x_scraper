"""Repositorio de versiones de Dossier por Operator + Ticker."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Json

from backend.app.db import connect
from backend.services.ticker_catalog import resolve_ticker_input


class DossierRepoError(Exception):
    pass


MAX_VERSIONS = 10
RETENTION_DAYS = 30


def _canonical_symbol(raw: str) -> str:
    resolved = resolve_ticker_input(raw)
    if resolved:
        return resolved
    return str(raw).strip().upper()


def _row_to_version(row: tuple) -> dict[str, Any]:
    version_id, symbol, content, citations, created_at = row
    return {
        "id": str(version_id),
        "symbol": symbol,
        "content": content if isinstance(content, dict) else {},
        "citations": citations if isinstance(citations, list) else [],
        "created_at": created_at,
    }


def save_version(
    *,
    user_id: str,
    symbol: str,
    content: dict,
    citations: list,
) -> dict[str, Any]:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        raise DossierRepoError("symbol required")
    if not isinstance(content, dict):
        raise DossierRepoError("content must be a dict")

    sql = """
        INSERT INTO ticker_dossier_versions (user_id, symbol, content, citations)
        VALUES (%(user_id)s, %(symbol)s, %(content)s, %(citations)s)
        RETURNING id, symbol, content, citations, created_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "user_id": user_id,
                    "symbol": canonical,
                    "content": Json(content),
                    "citations": Json(citations if citations else []),
                },
            )
            row = cur.fetchone()

    if row is None:
        raise DossierRepoError("failed to save dossier version")

    prune_old_versions(user_id=user_id, symbol=canonical)
    return _row_to_version(row)


def get_latest(*, user_id: str, symbol: str) -> dict[str, Any] | None:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        return None

    sql = """
        SELECT id, symbol, content, citations, created_at
        FROM ticker_dossier_versions
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
        SELECT id, symbol, content, citations, created_at
        FROM ticker_dossier_versions
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
        DELETE FROM ticker_dossier_versions
        WHERE user_id = %(user_id)s
          AND symbol = %(symbol)s
          AND created_at < now() - make_interval(days => %(days)s)
    """
    delete_excess_sql = """
        DELETE FROM ticker_dossier_versions
        WHERE id IN (
            SELECT id
            FROM ticker_dossier_versions
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
          AND table_name = 'ticker_dossier_versions'
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return bool(row and int(row[0]) >= 1)
