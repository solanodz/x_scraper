"""Endpoints REST y Feed Stream (SSE) de Signals."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.app.schemas import SignalCountResponse, SignalDetail, SignalSummary
from backend.app.services.feed_filters import feed_filters_from_query
from backend.app.services.signals_repo import (
    count_signals,
    get_signal,
    iter_poll_new_signals,
    list_signals,
)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalSummary])
def get_signals(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Palabras clave (todas deben aparecer)"),
    username: str | None = Query(None, description="Fuente o cuenta (parcial)"),
    ticker: str | None = Query(None, description="Ticker, ej. NVDA"),
    source_type: str | None = Query(
        None,
        description="x | news | rss | marketaux | alpha_vantage",
    ),
    topic: str | None = Query(None, description="Tópico (parcial)"),
    since_hours: int | None = Query(None, ge=1, le=24 * 90),
    sentiment: str | None = Query(
        None,
        description="positive | negative | neutral | bullish | bearish",
    ),
) -> list[SignalSummary]:
    filters = feed_filters_from_query(
        q=q,
        ticker=ticker,
        username=username,
        source_type=source_type,
        topic=topic,
        since_hours=since_hours,
        sentiment=sentiment,
    )
    return list_signals(limit=limit, offset=offset, filters=filters)


@router.get("/count", response_model=SignalCountResponse)
def get_signals_count(
    q: str | None = Query(None, description="Palabras clave (todas deben aparecer)"),
    username: str | None = Query(None, description="Fuente o cuenta (parcial)"),
    ticker: str | None = Query(None, description="Ticker, ej. NVDA"),
    source_type: str | None = Query(
        None,
        description="x | news | rss | marketaux | alpha_vantage",
    ),
    topic: str | None = Query(None, description="Tópico (parcial)"),
    since_hours: int | None = Query(None, ge=1, le=24 * 90),
    sentiment: str | None = Query(
        None,
        description="positive | negative | neutral | bullish | bearish",
    ),
) -> SignalCountResponse:
    filters = feed_filters_from_query(
        q=q,
        ticker=ticker,
        username=username,
        source_type=source_type,
        topic=topic,
        since_hours=since_hours,
        sentiment=sentiment,
    )
    return SignalCountResponse(total=count_signals(filters=filters))


async def _sse_signal_stream(
    since_id_str: str | None,
    since_ts: datetime | None,
) -> AsyncIterator[str]:
    """Emite heartbeats y eventos signal vía SSE."""
    loop = asyncio.get_event_loop()
    poll_gen = iter_poll_new_signals(
        since_id_str=since_id_str,
        since_ts=since_ts,
        poll_interval=2.0,
    )

    while True:
        batch = await loop.run_in_executor(None, next, poll_gen)
        yield ": heartbeat\n\n"
        for signal in batch:
            payload = signal.model_dump(mode="json")
            yield f"event: signal\ndata: {json.dumps(payload)}\n\n"


@router.get("/stream")
async def stream_signals(
    since_id_str: str | None = None,
    since: datetime | None = Query(None, description="ISO timestamp cursor"),
) -> StreamingResponse:
    return StreamingResponse(
        _sse_signal_stream(since_id_str, since),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{id_str}", response_model=SignalDetail)
def get_signal_by_id(id_str: str) -> SignalDetail:
    signal = get_signal(id_str)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal
