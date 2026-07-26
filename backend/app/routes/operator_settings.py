"""Operator Settings: preferencias persistidas (JSONB)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth import get_current_user, operator_id_from_user
from backend.app.services.operator_settings_repo import (
    OperatorSettingsRepoError,
    get_or_create_settings,
    patch_settings,
    tables_ready,
)

router = APIRouter(prefix="/operator", tags=["operator"])


class OperatorSettingsResponse(BaseModel):
    settings: dict[str, Any]
    updated_at: datetime | None = None


class OperatorSettingsPatch(BaseModel):
    bot_pnl: dict[str, Any] | None = None
    feed_filters: dict[str, Any] | None = None
    ticker_chart: dict[str, Any] | None = None

    model_config = {"extra": "ignore"}


def _require_tables() -> None:
    if not tables_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "operator_settings table missing. "
                "Run infra/store/init/015_operator_settings.sql (local) "
                "or ensure Supabase migration 002/015 is applied."
            ),
        )


@router.get("/settings", response_model=OperatorSettingsResponse)
def get_operator_settings(
    user: dict | None = Depends(get_current_user),
) -> OperatorSettingsResponse:
    _require_tables()
    operator_id = operator_id_from_user(user)
    try:
        row = get_or_create_settings(user_id=operator_id)
    except OperatorSettingsRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperatorSettingsResponse(
        settings=row["settings"],
        updated_at=row.get("updated_at"),
    )


@router.patch("/settings", response_model=OperatorSettingsResponse)
def patch_operator_settings(
    body: OperatorSettingsPatch,
    user: dict | None = Depends(get_current_user),
) -> OperatorSettingsResponse:
    _require_tables()
    operator_id = operator_id_from_user(user)
    patch: dict[str, Any] = {}
    if body.bot_pnl is not None:
        patch["bot_pnl"] = body.bot_pnl
    if body.feed_filters is not None:
        patch["feed_filters"] = body.feed_filters
    if body.ticker_chart is not None:
        patch["ticker_chart"] = body.ticker_chart
    if not patch:
        raise HTTPException(status_code=400, detail="empty patch")
    try:
        row = patch_settings(user_id=operator_id, patch=patch)
    except OperatorSettingsRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperatorSettingsResponse(
        settings=row["settings"],
        updated_at=row.get("updated_at"),
    )
