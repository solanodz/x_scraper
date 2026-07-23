"""Paper Bot API: config, positions, fills, events."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.auth import get_current_user, operator_id_from_user
from backend.app.schemas import (
    BotConfig,
    BotConfigPatch,
    BotEvent,
    BotFill,
    BotPosition,
)
from backend.app.services import bot_repo
from backend.services.bot_venue import VenueNotEnabled, get_venue

router = APIRouter(prefix="/bot", tags=["bot"])


def _require_bot_tables() -> None:
    if not bot_repo.tables_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Paper Bot tables missing. "
                "Run infra/store/init/014_paper_bot.sql (local) "
                "or Supabase migration 014_paper_bot.sql."
            ),
        )


def _config_to_schema(row: dict[str, Any]) -> BotConfig:
    return BotConfig(**row)


def _position_to_schema(row: dict[str, Any]) -> BotPosition:
    return BotPosition(**row)


def _fill_to_schema(row: dict[str, Any]) -> BotFill:
    return BotFill(**row)


def _event_to_schema(row: dict[str, Any]) -> BotEvent:
    return BotEvent(**row)


@router.get("/config", response_model=BotConfig)
def get_bot_config(
    user: dict | None = Depends(get_current_user),
) -> BotConfig:
    _require_bot_tables()
    operator_id = operator_id_from_user(user)
    row = bot_repo.get_or_create_config(operator_id=operator_id)
    return _config_to_schema(row)


@router.patch("/config", response_model=BotConfig)
def patch_bot_config(
    body: BotConfigPatch,
    user: dict | None = Depends(get_current_user),
) -> BotConfig:
    _require_bot_tables()
    operator_id = operator_id_from_user(user)
    payload = body.model_dump(exclude_unset=True)
    if "venue" in payload and payload["venue"] is not None:
        venue = str(payload["venue"]).strip().lower()
        if venue != "paper":
            raise HTTPException(
                status_code=400,
                detail="venue must be 'paper' in MVP (hyperliquid not enabled)",
            )
        payload["venue"] = "paper"
    try:
        row = bot_repo.update_config(operator_id=operator_id, **payload)
    except bot_repo.BotRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _config_to_schema(row)


@router.get("/positions", response_model=list[BotPosition])
def get_bot_positions(
    status: str | None = Query(default=None),
    user: dict | None = Depends(get_current_user),
) -> list[BotPosition]:
    _require_bot_tables()
    operator_id = operator_id_from_user(user)
    try:
        rows = bot_repo.list_positions(operator_id=operator_id, status=status)
    except bot_repo.BotRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [_position_to_schema(r) for r in rows]


@router.post("/positions/{position_id}/close", response_model=BotPosition)
def post_close_position(
    position_id: str,
    user: dict | None = Depends(get_current_user),
) -> BotPosition:
    _require_bot_tables()
    operator_id = operator_id_from_user(user)
    pos = bot_repo.get_position(operator_id=operator_id, position_id=position_id)
    if pos is None or pos["status"] != "open":
        raise HTTPException(status_code=404, detail="open position not found")
    config = bot_repo.get_or_create_config(operator_id=operator_id)
    try:
        venue = get_venue(config.get("venue") or "paper")
        result = venue.close(
            operator_id=operator_id,
            position_id=position_id,
            reason="manual",
        )
    except VenueNotEnabled as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except bot_repo.BotRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    bot_repo.insert_event(
        operator_id=operator_id,
        kind="close",
        symbol=result["position"]["symbol"],
        payload={
            "position_id": position_id,
            "reason": "manual",
            "realized_pnl": result["position"].get("realized_pnl"),
        },
    )
    return _position_to_schema(result["position"])


@router.get("/fills", response_model=list[BotFill])
def get_bot_fills(
    user: dict | None = Depends(get_current_user),
) -> list[BotFill]:
    _require_bot_tables()
    operator_id = operator_id_from_user(user)
    rows = bot_repo.list_fills(operator_id=operator_id)
    return [_fill_to_schema(r) for r in rows]


@router.get("/events", response_model=list[BotEvent])
def get_bot_events(
    user: dict | None = Depends(get_current_user),
) -> list[BotEvent]:
    _require_bot_tables()
    operator_id = operator_id_from_user(user)
    rows = bot_repo.list_events(operator_id=operator_id)
    return [_event_to_schema(r) for r in rows]
