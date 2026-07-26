"""Dossier: análisis integral persistente por Ticker del Ticker Watch."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.auth import get_current_user, operator_id_from_user
from backend.app.schemas import (
    ChatCitation,
    DossierBlockContent,
    DossierRefreshResponse,
    DossierVersion,
)
from backend.app.services.dossier_repo import (
    DossierRepoError,
    get_latest,
    list_versions,
    save_version,
    tables_ready,
)
from backend.app.services.ticker_watch_repo import list_watch
from backend.services.dossier import (
    dossier_content_payload,
    generate_dossier,
    iter_dossier_refresh_stream,
)
from backend.services.research_steps import ResearchStepEvent
from backend.services.ticker_catalog import resolve_ticker_input

router = APIRouter(prefix="/dossier", tags=["dossier"])


def _citations_to_json(citations: list) -> list[dict]:
    payload: list[dict] = []
    for item in citations:
        if is_dataclass(item):
            payload.append(asdict(item))
        elif isinstance(item, dict):
            payload.append(item)
    return payload


def _canonical_symbol(raw: str) -> str:
    from backend.services.fx import is_fx_currency_code

    if is_fx_currency_code(raw):
        raise HTTPException(
            status_code=400,
            detail=(
                "FX currency codes (USD, ARS, …) are not Tickers. "
                "Use Research Chat FX Quotes (get_fx_quotes) for dólar Argentina."
            ),
        )
    resolved = resolve_ticker_input(raw)
    if resolved:
        return resolved
    return str(raw).strip().upper()


def _require_dossier_tables() -> None:
    if not tables_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Dossier table missing. "
                "Run infra/store/init/009_ticker_dossier_versions.sql (local) "
                "or Supabase migration 009_ticker_dossier_versions.sql."
            ),
        )


def _symbol_in_watch(*, user_id: str, symbol: str) -> bool:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        return False
    return any(entry["symbol"] == canonical for entry in list_watch(user_id=user_id))


def _content_to_schema(raw: dict[str, Any]) -> DossierBlockContent:
    blocks = raw.get("blocks")
    if not isinstance(blocks, dict):
        blocks = {
            key: value
            for key, value in raw.items()
            if key not in ("sentiment_stats", "fundamentals")
            and isinstance(value, str)
        }
    fundamentals = raw.get("fundamentals")
    return DossierBlockContent(
        blocks=blocks,
        sentiment_stats=raw.get("sentiment_stats"),
        fundamentals=fundamentals if isinstance(fundamentals, dict) else None,
    )


def _version_to_schema(row: dict[str, Any]) -> DossierVersion:
    content_raw = row.get("content")
    if not isinstance(content_raw, dict):
        content_raw = {}
    citations_raw = row.get("citations")
    citations: list[ChatCitation] = []
    if isinstance(citations_raw, list):
        citations = [
            ChatCitation(**item)
            for item in citations_raw
            if isinstance(item, dict)
        ]
    return DossierVersion(
        id=row["id"],
        symbol=row["symbol"],
        content=_content_to_schema(content_raw),
        citations=citations,
        created_at=row["created_at"],
    )


def _require_watched_symbol(*, user_id: str, symbol: str) -> str:
    canonical = _canonical_symbol(symbol)
    if not canonical:
        raise HTTPException(status_code=404, detail="symbol not in watch list")
    if not _symbol_in_watch(user_id=user_id, symbol=canonical):
        raise HTTPException(status_code=404, detail="symbol not in watch list")
    return canonical


def _watch_thesis(*, user_id: str, symbol: str) -> str | None:
    for entry in list_watch(user_id=user_id):
        if entry["symbol"] == symbol:
            return entry.get("note")
    return None


@router.get("/{symbol}", response_model=DossierVersion)
def get_dossier_latest(
    symbol: str,
    user: dict | None = Depends(get_current_user),
) -> DossierVersion:
    _require_dossier_tables()
    operator_id = operator_id_from_user(user)
    canonical = _require_watched_symbol(user_id=operator_id, symbol=symbol)
    row = get_latest(user_id=operator_id, symbol=canonical)
    if row is None:
        raise HTTPException(status_code=404, detail="dossier not found")
    return _version_to_schema(row)


@router.get("/{symbol}/versions", response_model=list[DossierVersion])
def get_dossier_versions(
    symbol: str,
    user: dict | None = Depends(get_current_user),
) -> list[DossierVersion]:
    _require_dossier_tables()
    operator_id = operator_id_from_user(user)
    canonical = _require_watched_symbol(user_id=operator_id, symbol=symbol)
    rows = list_versions(user_id=operator_id, symbol=canonical, limit=10)
    return [_version_to_schema(row) for row in rows]


@router.post("/{symbol}/refresh", response_model=DossierRefreshResponse)
def post_dossier_refresh(
    symbol: str,
    user: dict | None = Depends(get_current_user),
) -> DossierRefreshResponse:
    """Refresh síncrono (compat). Preferí `/refresh/stream` para UX con steps."""
    _require_dossier_tables()
    operator_id = operator_id_from_user(user)
    canonical = _require_watched_symbol(user_id=operator_id, symbol=symbol)
    thesis = _watch_thesis(user_id=operator_id, symbol=canonical)
    try:
        generated_content, generated_citations = generate_dossier(
            user_id=operator_id,
            symbol=canonical,
            thesis=thesis,
        )
        row = save_version(
            user_id=operator_id,
            symbol=canonical,
            content=dossier_content_payload(generated_content),
            citations=_citations_to_json(generated_citations),
        )
    except DossierRepoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DossierRefreshResponse(version=_version_to_schema(row))


def _sse_dossier_refresh(
    *,
    operator_id: str,
    symbol: str,
    thesis: str | None,
) -> Iterator[str]:
    content: dict[str, Any] | None = None
    citations: list = []
    try:
        for item in iter_dossier_refresh_stream(
            user_id=operator_id,
            symbol=symbol,
            thesis=thesis,
        ):
            if isinstance(item, ResearchStepEvent):
                yield (
                    f"event: step\ndata: "
                    f"{json.dumps(item.to_dict(), ensure_ascii=False)}\n\n"
                )
            elif isinstance(item, str):
                # Tokens de síntesis — omitidos en UI del Dossier (no markdown live).
                continue
            elif isinstance(item, dict):
                content = item
            elif isinstance(item, list):
                citations = item

        if content is None:
            yield (
                'event: error\ndata: {"detail":"dossier generation produced no content"}\n\n'
            )
            return

        row = save_version(
            user_id=operator_id,
            symbol=symbol,
            content=dossier_content_payload(content),
            citations=_citations_to_json(citations),
        )
        version = _version_to_schema(row)
        yield (
            f"event: dossier\ndata: "
            f"{json.dumps(version.model_dump(mode='json'), ensure_ascii=False)}\n\n"
        )
    except DossierRepoError as exc:
        payload = json.dumps({"detail": str(exc)}, ensure_ascii=False)
        yield f"event: error\ndata: {payload}\n\n"
    except Exception as exc:  # noqa: BLE001
        detail = str(exc).strip() or type(exc).__name__
        if len(detail) > 400:
            detail = detail[:397] + "…"
        payload = json.dumps({"detail": detail}, ensure_ascii=False)
        yield f"event: error\ndata: {payload}\n\n"


@router.post("/{symbol}/refresh/stream")
async def post_dossier_refresh_stream(
    symbol: str,
    user: dict | None = Depends(get_current_user),
) -> StreamingResponse:
    _require_dossier_tables()
    operator_id = operator_id_from_user(user)
    canonical = _require_watched_symbol(user_id=operator_id, symbol=symbol)
    thesis = _watch_thesis(user_id=operator_id, symbol=canonical)

    async def _stream() -> AsyncIterator[str]:
        for event in _sse_dossier_refresh(
            operator_id=operator_id,
            symbol=canonical,
            thesis=thesis,
        ):
            yield event

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
