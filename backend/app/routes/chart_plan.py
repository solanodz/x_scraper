"""Chart Plan: análisis visual on-demand por Ticker del Ticker Watch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.auth import get_current_user, operator_id_from_user
from backend.app.schemas import ChartPlanAnalyzeRequest, ChartPlanVersion
from backend.app.services.chart_plan_repo import (
    ChartPlanRepoError,
    get_latest,
    list_versions,
    save_version,
    tables_ready,
)
from backend.app.services.dossier_repo import get_latest as get_latest_dossier
from backend.app.services.ticker_watch_repo import list_watch
from backend.services.chart_plan import (
    ChartPlanDisabledError,
    ChartPlanNoDossierError,
    chart_agent_enabled,
    chart_plan_content_payload,
    iter_chart_plan_analyze_stream,
)
from backend.services.research_steps import ResearchStepEvent
from backend.services.ticker_catalog import resolve_ticker_input

router = APIRouter(prefix="/chart-plan", tags=["chart-plan"])


def _canonical_symbol(raw: str) -> str:
    resolved = resolve_ticker_input(raw)
    if resolved:
        return resolved
    return str(raw).strip().upper()


def _require_chart_plan_tables() -> None:
    if not tables_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Chart Plan table missing. "
                "Run infra/store/init/010_ticker_chart_plan_versions.sql (local) "
                "or Supabase migration 010_ticker_chart_plan_versions.sql."
            ),
        )


def _require_chart_agent_enabled() -> None:
    if not chart_agent_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Chart Agent disabled. "
                "Set CHART_AGENT_ENABLED=true to enable chart analysis."
            ),
        )


def _symbol_in_watch(*, user_id: str, symbol: str) -> bool:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        return False
    return any(entry["symbol"] == canonical for entry in list_watch(user_id=user_id))


def _require_watched_symbol(*, user_id: str, symbol: str) -> str:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        raise HTTPException(status_code=404, detail="symbol not in watch list")
    if not _symbol_in_watch(user_id=user_id, symbol=canonical):
        raise HTTPException(status_code=404, detail="symbol not in watch list")
    return canonical


def _version_to_schema(row: dict[str, Any]) -> ChartPlanVersion:
    content_raw = row.get("content")
    if not isinstance(content_raw, dict):
        content_raw = {}
    return ChartPlanVersion(
        id=row["id"],
        symbol=row["symbol"],
        content=content_raw,
        dossier_version_id=row.get("dossier_version_id"),
        created_at=row["created_at"],
    )


@router.get("/{symbol}", response_model=ChartPlanVersion)
def get_chart_plan_latest(
    symbol: str,
    user: dict | None = Depends(get_current_user),
) -> ChartPlanVersion:
    _require_chart_plan_tables()
    operator_id = operator_id_from_user(user)
    canonical = _require_watched_symbol(user_id=operator_id, symbol=symbol)
    row = get_latest(user_id=operator_id, symbol=canonical)
    if row is None:
        raise HTTPException(status_code=404, detail="chart plan not found")
    return _version_to_schema(row)


@router.get("/{symbol}/versions", response_model=list[ChartPlanVersion])
def get_chart_plan_versions(
    symbol: str,
    user: dict | None = Depends(get_current_user),
) -> list[ChartPlanVersion]:
    _require_chart_plan_tables()
    operator_id = operator_id_from_user(user)
    canonical = _require_watched_symbol(user_id=operator_id, symbol=symbol)
    rows = list_versions(user_id=operator_id, symbol=canonical, limit=10)
    return [_version_to_schema(row) for row in rows]


async def _sse_chart_plan_analyze(
    *,
    operator_id: str,
    symbol: str,
    chart_image_base64: str | None = None,
    chart_image_media_type: str = "image/png",
    chart_view: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    loop = asyncio.get_event_loop()

    def _next_chunk(iterator):
        return next(iterator, None)

    stream = iter_chart_plan_analyze_stream(
        operator_id,
        symbol,
        chart_image_base64=chart_image_base64,
        chart_image_media_type=chart_image_media_type,
        chart_view=chart_view,
    )
    pending_content: dict[str, Any] | None = None
    pending_dossier_id: str | None = None
    while True:
        chunk = await loop.run_in_executor(None, _next_chunk, stream)
        if chunk is None:
            break
        if isinstance(chunk, ResearchStepEvent):
            payload = chunk.to_dict()
            yield f"event: step\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        elif isinstance(chunk, dict):
            pending_content = chunk
        elif isinstance(chunk, str):
            pending_dossier_id = chunk

    if pending_content is not None:
        row = save_version(
            user_id=operator_id,
            symbol=symbol,
            content=chart_plan_content_payload(pending_content),
            dossier_version_id=pending_dossier_id,
        )
        version = _version_to_schema(row)
        yield (
            f"event: chart_plan\ndata: "
            f"{json.dumps(version.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        )


@router.post("/{symbol}/analyze")
async def post_chart_plan_analyze(
    symbol: str,
    body: ChartPlanAnalyzeRequest | None = None,
    user: dict | None = Depends(get_current_user),
) -> StreamingResponse:
    _require_chart_plan_tables()
    _require_chart_agent_enabled()

    operator_id = operator_id_from_user(user)
    canonical = _require_watched_symbol(user_id=operator_id, symbol=symbol)

    if get_latest_dossier(user_id=operator_id, symbol=canonical) is None:
        raise HTTPException(
            status_code=404,
            detail="dossier not found — generate dossier first",
        )

    request = body or ChartPlanAnalyzeRequest()
    chart_image = request.chart_image_base64
    media_type = request.chart_image_media_type or "image/png"
    chart_view = request.chart_view

    async def _stream() -> AsyncIterator[str]:
        try:
            async for event in _sse_chart_plan_analyze(
                operator_id=operator_id,
                symbol=canonical,
                chart_image_base64=chart_image,
                chart_image_media_type=media_type,
                chart_view=chart_view,
            ):
                yield event
        except ChartPlanNoDossierError as exc:
            payload = json.dumps({"detail": str(exc)})
            yield f"event: error\ndata: {payload}\n\n"
        except ChartPlanDisabledError as exc:
            payload = json.dumps({"detail": str(exc)})
            yield f"event: error\ndata: {payload}\n\n"
        except ChartPlanRepoError as exc:
            payload = json.dumps({"detail": str(exc)})
            yield f"event: error\ndata: {payload}\n\n"
        except RuntimeError as exc:
            payload = json.dumps({"detail": str(exc)})
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
