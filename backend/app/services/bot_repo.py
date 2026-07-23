"""Repositorio del Paper Bot (config, positions, fills, events)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg.types.json import Json

from backend.app.db import connect

ALLOWED_SYMBOLS = frozenset({"BTC", "ETH"})
DEFAULT_SYMBOLS = ["BTC", "ETH"]


class BotRepoError(Exception):
    pass


def _dec(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _config_row(row: tuple) -> dict[str, Any]:
    (
        operator_id,
        armed,
        symbols,
        max_positions,
        donchian_period,
        donchian_interval,
        size_usd,
        leverage,
        tp_pct,
        sl_pct,
        venue,
        cooldown_seconds,
        updated_at,
    ) = row
    return {
        "operator_id": str(operator_id),
        "armed": bool(armed),
        "symbols": list(symbols or DEFAULT_SYMBOLS),
        "max_positions": int(max_positions),
        "donchian_period": int(donchian_period),
        "donchian_interval": str(donchian_interval),
        "size_usd": _dec(size_usd),
        "leverage": _dec(leverage),
        "tp_pct": _dec(tp_pct),
        "sl_pct": _dec(sl_pct),
        "venue": str(venue),
        "cooldown_seconds": int(cooldown_seconds),
        "updated_at": updated_at,
    }


def _position_row(row: tuple) -> dict[str, Any]:
    (
        pos_id,
        operator_id,
        symbol,
        side,
        size_usd,
        qty,
        leverage,
        entry_price,
        tp_price,
        sl_price,
        status,
        opened_at,
        closed_at,
        close_reason,
        realized_pnl,
        venue,
        external_id,
        mark_price,
    ) = row
    return {
        "id": str(pos_id),
        "operator_id": str(operator_id),
        "symbol": symbol,
        "side": side,
        "size_usd": _dec(size_usd),
        "qty": _dec(qty),
        "leverage": _dec(leverage),
        "entry_price": _dec(entry_price),
        "tp_price": _dec(tp_price),
        "sl_price": _dec(sl_price),
        "status": status,
        "opened_at": opened_at,
        "closed_at": closed_at,
        "close_reason": close_reason,
        "realized_pnl": None if realized_pnl is None else _dec(realized_pnl),
        "venue": venue,
        "external_id": external_id,
        "mark_price": None if mark_price is None else _dec(mark_price),
    }


def _fill_row(row: tuple) -> dict[str, Any]:
    (
        fill_id,
        position_id,
        operator_id,
        symbol,
        side,
        price,
        qty,
        venue,
        created_at,
        raw,
    ) = row
    return {
        "id": str(fill_id),
        "position_id": str(position_id),
        "operator_id": str(operator_id),
        "symbol": symbol,
        "side": side,
        "price": _dec(price),
        "qty": _dec(qty),
        "venue": venue,
        "created_at": created_at,
        "raw": raw if isinstance(raw, dict) else {},
    }


def _event_row(row: tuple) -> dict[str, Any]:
    event_id, operator_id, kind, symbol, payload, created_at = row
    return {
        "id": str(event_id),
        "operator_id": str(operator_id),
        "kind": kind,
        "symbol": symbol,
        "payload": payload if isinstance(payload, dict) else {},
        "created_at": created_at,
    }


def tables_ready() -> bool:
    sql = """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN (
            'bot_config', 'bot_positions', 'bot_fills', 'bot_events'
          )
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return bool(row and int(row[0]) == 4)


def get_or_create_config(*, operator_id: str) -> dict[str, Any]:
    select_sql = """
        SELECT operator_id, armed, symbols, max_positions, donchian_period,
               donchian_interval, size_usd, leverage, tp_pct, sl_pct, venue,
               cooldown_seconds, updated_at
        FROM bot_config
        WHERE operator_id = %(operator_id)s::uuid
    """
    insert_sql = """
        INSERT INTO bot_config (operator_id)
        VALUES (%(operator_id)s::uuid)
        ON CONFLICT (operator_id) DO NOTHING
        RETURNING operator_id, armed, symbols, max_positions, donchian_period,
                  donchian_interval, size_usd, leverage, tp_pct, sl_pct, venue,
                  cooldown_seconds, updated_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(select_sql, {"operator_id": operator_id})
            row = cur.fetchone()
            if row is not None:
                return _config_row(row)
            cur.execute(insert_sql, {"operator_id": operator_id})
            row = cur.fetchone()
            if row is not None:
                return _config_row(row)
            cur.execute(select_sql, {"operator_id": operator_id})
            row = cur.fetchone()
    if row is None:
        raise BotRepoError("failed to get_or_create bot_config")
    return _config_row(row)


def list_config_operator_ids() -> list[str]:
    """Operator IDs with a bot_config row (single-tenant deploy helper)."""
    sql = "SELECT operator_id::text FROM bot_config ORDER BY updated_at DESC NULLS LAST"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def update_config(*, operator_id: str, **fields: Any) -> dict[str, Any]:
    allowed = {
        "armed",
        "symbols",
        "max_positions",
        "donchian_period",
        "donchian_interval",
        "size_usd",
        "leverage",
        "tp_pct",
        "sl_pct",
        "venue",
        "cooldown_seconds",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_or_create_config(operator_id=operator_id)

    get_or_create_config(operator_id=operator_id)

    if "symbols" in updates:
        symbols = [str(s).strip().upper() for s in updates["symbols"]]
        if not symbols or any(s not in ALLOWED_SYMBOLS for s in symbols):
            raise BotRepoError("symbols must be a non-empty subset of BTC, ETH")
        updates["symbols"] = symbols

    if "max_positions" in updates:
        mp = int(updates["max_positions"])
        if mp < 1 or mp > 10:
            raise BotRepoError("max_positions must be between 1 and 10")
        updates["max_positions"] = mp

    if "venue" in updates and str(updates["venue"]).strip().lower() != "paper":
        raise BotRepoError("venue must be 'paper' in MVP")

    set_parts = [f"{col} = %({col})s" for col in updates]
    set_parts.append("updated_at = now()")
    sql = f"""
        UPDATE bot_config
        SET {", ".join(set_parts)}
        WHERE operator_id = %(operator_id)s::uuid
        RETURNING operator_id, armed, symbols, max_positions, donchian_period,
                  donchian_interval, size_usd, leverage, tp_pct, sl_pct, venue,
                  cooldown_seconds, updated_at
    """
    params = {"operator_id": operator_id, **updates}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    if row is None:
        raise BotRepoError("bot_config not found")
    return _config_row(row)


def list_positions(
    *,
    operator_id: str,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses = ["operator_id = %(operator_id)s::uuid"]
    params: dict[str, Any] = {
        "operator_id": operator_id,
        "limit": max(1, min(int(limit), 500)),
    }
    if status:
        if status not in {"open", "closed"}:
            raise BotRepoError("status must be open or closed")
        clauses.append("status = %(status)s")
        params["status"] = status
    sql = f"""
        SELECT id, operator_id, symbol, side, size_usd, qty, leverage,
               entry_price, tp_price, sl_price, status, opened_at, closed_at,
               close_reason, realized_pnl, venue, external_id, mark_price
        FROM bot_positions
        WHERE {" AND ".join(clauses)}
        ORDER BY opened_at DESC
        LIMIT %(limit)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [_position_row(r) for r in rows]


def get_position(*, operator_id: str, position_id: str) -> dict[str, Any] | None:
    sql = """
        SELECT id, operator_id, symbol, side, size_usd, qty, leverage,
               entry_price, tp_price, sl_price, status, opened_at, closed_at,
               close_reason, realized_pnl, venue, external_id, mark_price
        FROM bot_positions
        WHERE id = %(position_id)s::uuid
          AND operator_id = %(operator_id)s::uuid
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {"operator_id": operator_id, "position_id": position_id},
            )
            row = cur.fetchone()
    return _position_row(row) if row else None


def insert_position(
    *,
    operator_id: str,
    symbol: str,
    side: str,
    size_usd: float,
    qty: float,
    leverage: float,
    entry_price: float,
    tp_price: float,
    sl_price: float,
    venue: str = "paper",
    external_id: str | None = None,
    mark_price: float | None = None,
) -> dict[str, Any]:
    if side not in {"long", "short"}:
        raise BotRepoError("side must be long or short")
    sql = """
        INSERT INTO bot_positions (
          operator_id, symbol, side, size_usd, qty, leverage,
          entry_price, tp_price, sl_price, status, venue, external_id, mark_price
        )
        VALUES (
          %(operator_id)s::uuid, %(symbol)s, %(side)s, %(size_usd)s, %(qty)s,
          %(leverage)s, %(entry_price)s, %(tp_price)s, %(sl_price)s, 'open',
          %(venue)s, %(external_id)s, %(mark_price)s
        )
        RETURNING id, operator_id, symbol, side, size_usd, qty, leverage,
                  entry_price, tp_price, sl_price, status, opened_at, closed_at,
                  close_reason, realized_pnl, venue, external_id, mark_price
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "operator_id": operator_id,
                    "symbol": symbol,
                    "side": side,
                    "size_usd": size_usd,
                    "qty": qty,
                    "leverage": leverage,
                    "entry_price": entry_price,
                    "tp_price": tp_price,
                    "sl_price": sl_price,
                    "venue": venue,
                    "external_id": external_id,
                    "mark_price": mark_price,
                },
            )
            row = cur.fetchone()
    if row is None:
        raise BotRepoError("failed to insert position")
    return _position_row(row)


def close_position_row(
    *,
    operator_id: str,
    position_id: str,
    close_reason: str,
    realized_pnl: float,
    mark_price: float | None = None,
) -> dict[str, Any]:
    sql = """
        UPDATE bot_positions
        SET status = 'closed',
            closed_at = now(),
            close_reason = %(close_reason)s,
            realized_pnl = %(realized_pnl)s,
            mark_price = COALESCE(%(mark_price)s, mark_price)
        WHERE id = %(position_id)s::uuid
          AND operator_id = %(operator_id)s::uuid
          AND status = 'open'
        RETURNING id, operator_id, symbol, side, size_usd, qty, leverage,
                  entry_price, tp_price, sl_price, status, opened_at, closed_at,
                  close_reason, realized_pnl, venue, external_id, mark_price
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "operator_id": operator_id,
                    "position_id": position_id,
                    "close_reason": close_reason,
                    "realized_pnl": realized_pnl,
                    "mark_price": mark_price,
                },
            )
            row = cur.fetchone()
    if row is None:
        raise BotRepoError("open position not found")
    return _position_row(row)


def insert_fill(
    *,
    position_id: str,
    operator_id: str,
    symbol: str,
    side: str,
    price: float,
    qty: float,
    venue: str = "paper",
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sql = """
        INSERT INTO bot_fills (
          position_id, operator_id, symbol, side, price, qty, venue, raw
        )
        VALUES (
          %(position_id)s::uuid, %(operator_id)s::uuid, %(symbol)s, %(side)s,
          %(price)s, %(qty)s, %(venue)s, %(raw)s
        )
        RETURNING id, position_id, operator_id, symbol, side, price, qty,
                  venue, created_at, raw
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "position_id": position_id,
                    "operator_id": operator_id,
                    "symbol": symbol,
                    "side": side,
                    "price": price,
                    "qty": qty,
                    "venue": venue,
                    "raw": Json(raw or {}),
                },
            )
            row = cur.fetchone()
    if row is None:
        raise BotRepoError("failed to insert fill")
    return _fill_row(row)


def list_fills(
    *,
    operator_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = """
        SELECT id, position_id, operator_id, symbol, side, price, qty,
               venue, created_at, raw
        FROM bot_fills
        WHERE operator_id = %(operator_id)s::uuid
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "operator_id": operator_id,
                    "limit": max(1, min(int(limit), 500)),
                },
            )
            rows = cur.fetchall()
    return [_fill_row(r) for r in rows]


def insert_event(
    *,
    operator_id: str,
    kind: str,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sql = """
        INSERT INTO bot_events (operator_id, kind, symbol, payload)
        VALUES (
          %(operator_id)s::uuid, %(kind)s, %(symbol)s, %(payload)s
        )
        RETURNING id, operator_id, kind, symbol, payload, created_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "operator_id": operator_id,
                    "kind": kind,
                    "symbol": symbol,
                    "payload": Json(payload or {}),
                },
            )
            row = cur.fetchone()
    if row is None:
        raise BotRepoError("failed to insert event")
    return _event_row(row)


def list_events(
    *,
    operator_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = """
        SELECT id, operator_id, kind, symbol, payload, created_at
        FROM bot_events
        WHERE operator_id = %(operator_id)s::uuid
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "operator_id": operator_id,
                    "limit": max(1, min(int(limit), 500)),
                },
            )
            rows = cur.fetchall()
    return [_event_row(r) for r in rows]


def count_open_positions(*, operator_id: str) -> int:
    sql = """
        SELECT COUNT(*) FROM bot_positions
        WHERE operator_id = %(operator_id)s::uuid AND status = 'open'
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"operator_id": operator_id})
            row = cur.fetchone()
    return int(row[0]) if row else 0


def get_open_position_for_symbol(
    *,
    operator_id: str,
    symbol: str,
) -> dict[str, Any] | None:
    sql = """
        SELECT id, operator_id, symbol, side, size_usd, qty, leverage,
               entry_price, tp_price, sl_price, status, opened_at, closed_at,
               close_reason, realized_pnl, venue, external_id, mark_price
        FROM bot_positions
        WHERE operator_id = %(operator_id)s::uuid
          AND symbol = %(symbol)s
          AND status = 'open'
        ORDER BY opened_at DESC
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {"operator_id": operator_id, "symbol": symbol},
            )
            row = cur.fetchone()
    return _position_row(row) if row else None


def last_closed_at_for_symbol(
    *,
    operator_id: str,
    symbol: str,
) -> Any | None:
    sql = """
        SELECT closed_at FROM bot_positions
        WHERE operator_id = %(operator_id)s::uuid
          AND symbol = %(symbol)s
          AND status = 'closed'
          AND closed_at IS NOT NULL
        ORDER BY closed_at DESC
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {"operator_id": operator_id, "symbol": symbol},
            )
            row = cur.fetchone()
    return row[0] if row else None


def signal_already_processed(
    *,
    operator_id: str,
    symbol: str,
    side: str,
    bar_ts: str,
) -> bool:
    """Idempotencia: Trade Signal ya abierto/procesado para symbol+side+bar_ts."""
    sql = """
        SELECT 1 FROM bot_events
        WHERE operator_id = %(operator_id)s::uuid
          AND symbol = %(symbol)s
          AND kind IN ('open', 'trade_signal', 'skip_duplicate')
          AND payload->>'side' = %(side)s
          AND payload->>'bar_ts' = %(bar_ts)s
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "operator_id": operator_id,
                    "symbol": symbol,
                    "side": side,
                    "bar_ts": bar_ts,
                },
            )
            return cur.fetchone() is not None
