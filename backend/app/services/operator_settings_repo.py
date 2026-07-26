"""Repositorio de Operator Settings (JSONB por user_id)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from psycopg.types.json import Json

from backend.app.db import connect

DEFAULT_SETTINGS: dict[str, Any] = {
    "bot_pnl": {
        "timeZone": "America/Argentina/Buenos_Aires",
        "lookbackDays": 30,
    },
    "feed_filters": {
        "watchOnly": False,
    },
    "ticker_chart": {},
}

ALLOWED_LOOKBACKS = {7, 14, 30, 90}


class OperatorSettingsRepoError(Exception):
    pass


def tables_ready() -> bool:
    sql = """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'operator_settings'
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone() is not None


def _merge_defaults(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(DEFAULT_SETTINGS)
    if not raw:
        return out
    for key, value in raw.items():
        if key not in out:
            out[key] = value
            continue
        if isinstance(out[key], dict) and isinstance(value, dict):
            merged = {**out[key], **value}
            out[key] = merged
        else:
            out[key] = value
    return out


def _normalize_bot_pnl(value: Any) -> dict[str, Any]:
    base = deepcopy(DEFAULT_SETTINGS["bot_pnl"])
    if not isinstance(value, dict):
        return base
    tz = value.get("timeZone")
    if isinstance(tz, str) and tz.strip():
        base["timeZone"] = tz.strip()
    lb = value.get("lookbackDays")
    try:
        n = int(lb)
        if n in ALLOWED_LOOKBACKS:
            base["lookbackDays"] = n
    except (TypeError, ValueError):
        pass
    return base


def _normalize_feed_filters(value: Any) -> dict[str, Any]:
    base = deepcopy(DEFAULT_SETTINGS["feed_filters"])
    if not isinstance(value, dict):
        return base
    if "watchOnly" in value:
        base["watchOnly"] = bool(value["watchOnly"])
    return base


def _normalize_ticker_chart(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    # Pass-through subset; frontend owns shape.
    return dict(value)


def normalize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    merged = _merge_defaults(raw)
    return {
        "bot_pnl": _normalize_bot_pnl(merged.get("bot_pnl")),
        "feed_filters": _normalize_feed_filters(merged.get("feed_filters")),
        "ticker_chart": _normalize_ticker_chart(merged.get("ticker_chart")),
    }


def get_or_create_settings(*, user_id: str) -> dict[str, Any]:
    if not user_id:
        raise OperatorSettingsRepoError("user_id required")
    sql_sel = """
        SELECT settings, updated_at
        FROM operator_settings
        WHERE user_id = %(user_id)s
    """
    sql_ins = """
        INSERT INTO operator_settings (user_id, settings)
        VALUES (%(user_id)s, %(settings)s::jsonb)
        ON CONFLICT (user_id) DO NOTHING
        RETURNING settings, updated_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_sel, {"user_id": user_id})
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    sql_ins,
                    {
                        "user_id": user_id,
                        "settings": Json(DEFAULT_SETTINGS),
                    },
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(sql_sel, {"user_id": user_id})
                    row = cur.fetchone()
    if row is None:
        raise OperatorSettingsRepoError("failed to load settings")
    settings_raw, updated_at = row
    return {
        "settings": normalize_settings(
            settings_raw if isinstance(settings_raw, dict) else {}
        ),
        "updated_at": updated_at,
    }


def patch_settings(*, user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    if not user_id:
        raise OperatorSettingsRepoError("user_id required")
    if not isinstance(patch, dict):
        raise OperatorSettingsRepoError("patch must be an object")

    current = get_or_create_settings(user_id=user_id)
    next_settings = deepcopy(current["settings"])

    if "bot_pnl" in patch:
        next_settings["bot_pnl"] = _normalize_bot_pnl(patch["bot_pnl"])
    if "feed_filters" in patch:
        next_settings["feed_filters"] = _normalize_feed_filters(
            patch["feed_filters"]
        )
    if "ticker_chart" in patch:
        next_settings["ticker_chart"] = _normalize_ticker_chart(
            patch["ticker_chart"]
        )

    # Ignore unknown top-level keys (forward-compat).
    sql = """
        UPDATE operator_settings
        SET settings = %(settings)s::jsonb,
            updated_at = now()
        WHERE user_id = %(user_id)s
        RETURNING settings, updated_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {"user_id": user_id, "settings": Json(next_settings)},
            )
            row = cur.fetchone()
    if row is None:
        raise OperatorSettingsRepoError("settings row missing after patch")
    settings_raw, updated_at = row
    return {
        "settings": normalize_settings(
            settings_raw if isinstance(settings_raw, dict) else next_settings
        ),
        "updated_at": updated_at,
    }
