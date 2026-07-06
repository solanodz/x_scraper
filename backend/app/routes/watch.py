"""Ticker Watch: lista personal de símbolos por Operator."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.app.auth import get_current_user, operator_id_from_user
from backend.app.schemas import (
    TickerWatchAddRequest,
    TickerWatchEntry,
    TickerWatchUpdateRequest,
)
from backend.app.services.ticker_watch_repo import (
    TickerWatchRepoError,
    add_watch,
    list_watch,
    remove_watch,
    tables_ready,
    update_watch,
)

router = APIRouter(prefix="/watch", tags=["watch"])


def _entry_to_schema(row: dict[str, Any]) -> TickerWatchEntry:
    return TickerWatchEntry(
        id=row["id"],
        symbol=row["symbol"],
        note=row.get("note"),
        created_at=row["created_at"],
    )


def _require_ticker_watch_tables() -> None:
    if not tables_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Ticker Watch table missing. "
                "Run infra/store/init/006_ticker_watch.sql (local) "
                "or Supabase migration 007_ticker_watch.sql."
            ),
        )


@router.get("", response_model=list[TickerWatchEntry])
def get_watch_list(
    user: dict | None = Depends(get_current_user),
) -> list[TickerWatchEntry]:
    _require_ticker_watch_tables()
    operator_id = operator_id_from_user(user)
    rows = list_watch(user_id=operator_id)
    return [_entry_to_schema(row) for row in rows]


@router.post("", response_model=TickerWatchEntry, status_code=201)
def post_watch_entry(
    body: TickerWatchAddRequest,
    user: dict | None = Depends(get_current_user),
) -> TickerWatchEntry:
    _require_ticker_watch_tables()
    operator_id = operator_id_from_user(user)
    try:
        row = add_watch(
            user_id=operator_id,
            symbol=body.symbol,
            note=body.note,
        )
    except TickerWatchRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _entry_to_schema(row)


@router.patch("/{symbol}", response_model=TickerWatchEntry)
def patch_watch_entry(
    symbol: str,
    body: TickerWatchUpdateRequest,
    user: dict | None = Depends(get_current_user),
) -> TickerWatchEntry:
    _require_ticker_watch_tables()
    operator_id = operator_id_from_user(user)
    try:
        row = update_watch(
            user_id=operator_id,
            symbol=symbol,
            note=body.note,
        )
    except TickerWatchRepoError as exc:
        detail = str(exc)
        if detail == "symbol not in watch list":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return _entry_to_schema(row)


@router.delete("/{symbol}", status_code=204)
def delete_watch_entry(
    symbol: str,
    user: dict | None = Depends(get_current_user),
) -> Response:
    _require_ticker_watch_tables()
    operator_id = operator_id_from_user(user)
    removed = remove_watch(user_id=operator_id, symbol=symbol)
    if not removed:
        raise HTTPException(status_code=404, detail="symbol not in watch list")
    return Response(status_code=204)
