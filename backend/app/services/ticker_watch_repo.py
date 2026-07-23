"""Repositorio de Ticker Watch (lista personal de símbolos por Operator)."""

from __future__ import annotations

from typing import Any

from backend.app.db import connect
from backend.services.ticker_catalog import resolve_ticker_input


class TickerWatchRepoError(Exception):
    pass


MAX_THESIS_LENGTH = 280


def _normalize_note(note: str | None) -> str | None:
    if note is None:
        return None
    stripped = note.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_THESIS_LENGTH:
        raise TickerWatchRepoError(
            f"note exceeds {MAX_THESIS_LENGTH} characters"
        )
    return stripped


def _canonical_symbol(raw: str) -> str:
    from backend.services.fx import is_fx_currency_code

    if is_fx_currency_code(raw):
        raise TickerWatchRepoError(
            "FX currency codes (USD, ARS, EUR, …) are not Tickers — "
            "use Research Chat get_fx_quotes for dólar / FX"
        )
    resolved = resolve_ticker_input(raw)
    if resolved:
        return resolved
    return str(raw).strip().upper()


def _row_to_entry(row: tuple) -> dict[str, Any]:
    entry_id, symbol, note, created_at = row
    return {
        "id": str(entry_id),
        "symbol": symbol,
        "note": note,
        "created_at": created_at,
    }


def list_watch(*, user_id: str) -> list[dict[str, Any]]:
    sql = """
        SELECT id, symbol, note, created_at
        FROM ticker_watch
        WHERE user_id = %(user_id)s
        ORDER BY created_at ASC
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"user_id": user_id})
            rows = cur.fetchall()
    return [_row_to_entry(row) for row in rows]


def _get_watch_entry(*, user_id: str, symbol: str) -> dict[str, Any] | None:
    sql = """
        SELECT id, symbol, note, created_at
        FROM ticker_watch
        WHERE user_id = %(user_id)s AND symbol = %(symbol)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"user_id": user_id, "symbol": symbol})
            row = cur.fetchone()
    return _row_to_entry(row) if row else None


def add_watch(*, user_id: str, symbol: str, note: str | None = None) -> dict[str, Any]:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        raise TickerWatchRepoError("symbol required")

    sql = """
        INSERT INTO ticker_watch (user_id, symbol, note)
        VALUES (%(user_id)s, %(symbol)s, %(note)s)
        ON CONFLICT (user_id, symbol) DO NOTHING
        RETURNING id, symbol, note, created_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {"user_id": user_id, "symbol": canonical, "note": note},
            )
            row = cur.fetchone()

    if row is not None:
        return _row_to_entry(row)

    existing = _get_watch_entry(user_id=user_id, symbol=canonical)
    if existing is None:
        raise TickerWatchRepoError("failed to add ticker watch entry")
    return existing


def update_watch(*, user_id: str, symbol: str, note: str | None) -> dict[str, Any]:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        raise TickerWatchRepoError("symbol required")

    normalized_note = _normalize_note(note)
    sql = """
        UPDATE ticker_watch
        SET note = %(note)s
        WHERE user_id = %(user_id)s AND symbol = %(symbol)s
        RETURNING id, symbol, note, created_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "user_id": user_id,
                    "symbol": canonical,
                    "note": normalized_note,
                },
            )
            row = cur.fetchone()

    if row is None:
        raise TickerWatchRepoError("symbol not in watch list")
    return _row_to_entry(row)


def remove_watch(*, user_id: str, symbol: str) -> bool:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        return False

    sql = """
        DELETE FROM ticker_watch
        WHERE user_id = %(user_id)s AND symbol = %(symbol)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"user_id": user_id, "symbol": canonical})
            deleted = cur.rowcount
    return deleted > 0


def tables_ready() -> bool:
    sql = """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'ticker_watch'
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return bool(row and int(row[0]) >= 1)
