"""Chat Stream del Research Chat + Chat Session persistence."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth import get_current_user, operator_id_from_user
from backend.app.schemas import (
    BriefingRequest,
    ChatCitation,
    ChatMessageRecord,
    ChatRequest,
    ChatSessionCreate,
    ChatSessionSummary,
)
from backend.app.services.chat_repo import (
    ChatRepoError,
    append_message,
    ensure_session,
    list_messages,
    list_sessions,
    set_session_title_if_empty,
    tables_ready,
)
from backend.services.ask import ask_stream
from backend.services.briefing import iter_briefing_stream
from backend.services.chat_history import prepare_chat_history
from backend.services.research_steps import ChatArtifact, ResearchStepEvent
from backend.services.types import Citation
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/chat", tags=["chat"])

BRIEFING_USER_MESSAGE = "Briefing de mi Ticker Watch"


def _briefing_session_title() -> str:
    now = datetime.now()
    return f"Briefing {now.day:02d}/{now.month:02d}/{now.year}"


def _citation_to_schema(citation: Citation) -> ChatCitation:
    return ChatCitation(
        id_str=citation.id_str,
        username=citation.username,
        url=citation.url,
        excerpt=citation.excerpt,
    )


def _citation_payload(citations: list[Citation]) -> list[dict[str, Any]]:
    return [_citation_to_schema(c).model_dump() for c in citations]


def _session_to_schema(row: dict[str, Any]) -> ChatSessionSummary:
    return ChatSessionSummary(
        id=row["id"],
        title=row.get("title"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message_to_schema(row: dict[str, Any]) -> ChatMessageRecord:
    citations_raw = row.get("citations")
    citations: list[ChatCitation] | None = None
    if isinstance(citations_raw, list):
        citations = [ChatCitation(**item) for item in citations_raw if isinstance(item, dict)]
    artifacts_raw = row.get("artifacts")
    artifacts: list[dict[str, Any]] | None = None
    if isinstance(artifacts_raw, list):
        artifacts = [item for item in artifacts_raw if isinstance(item, dict)]
    return ChatMessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        citations=citations,
        artifacts=artifacts,
        created_at=row["created_at"],
    )


def _require_chat_tables() -> None:
    if not tables_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Chat Session tables missing. "
                "Run infra/store/init/005_operator_chat.sql (local) "
                "or Supabase migration 002_operator_data.sql."
            ),
        )


@router.get("/sessions", response_model=list[ChatSessionSummary])
def get_chat_sessions(
    limit: int = 20,
    user: dict | None = Depends(get_current_user),
) -> list[ChatSessionSummary]:
    _require_chat_tables()
    operator_id = operator_id_from_user(user)
    rows = list_sessions(user_id=operator_id, limit=limit)
    return [_session_to_schema(row) for row in rows]


@router.post("/sessions", response_model=ChatSessionSummary)
def create_chat_session(
    body: ChatSessionCreate | None = None,
    user: dict | None = Depends(get_current_user),
) -> ChatSessionSummary:
    _require_chat_tables()
    operator_id = operator_id_from_user(user)
    title = body.title if body else None
    row = ensure_session(user_id=operator_id, title=title)
    return _session_to_schema(row)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageRecord])
def get_chat_messages(
    session_id: str,
    user: dict | None = Depends(get_current_user),
) -> list[ChatMessageRecord]:
    _require_chat_tables()
    operator_id = operator_id_from_user(user)
    try:
        rows = list_messages(user_id=operator_id, session_id=session_id)
    except ChatRepoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_message_to_schema(row) for row in rows]


async def _consume_stream_chunks(
    stream,
    loop,
) -> AsyncIterator[str]:
    """Convierte AskStreamChunk iterator en eventos SSE."""
    while True:
        chunk = await loop.run_in_executor(None, lambda: next(stream, None))
        if chunk is None:
            break
        if isinstance(chunk, ResearchStepEvent):
            payload = chunk.to_dict()
            yield f"event: step\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        elif isinstance(chunk, ChatArtifact):
            payload = chunk.to_dict()
            yield f"event: artifact\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield ("__artifact__", payload)
        elif isinstance(chunk, list):
            payload = _citation_payload(chunk)
            yield f"event: citations\ndata: {json.dumps(payload)}\n\n"
            yield ("__citations__", chunk)
        else:
            yield f"data: {json.dumps(chunk)}\n\n"
            yield ("__token__", chunk)


async def _sse_research_stream(
    user_message: str,
    *,
    operator_id: str,
    session_id: str | None,
    stream_factory,
    session_title: str | None = None,
) -> AsyncIterator[str]:
    session = ensure_session(user_id=operator_id, session_id=session_id)
    sid = session["id"]
    yield f"event: session\ndata: {json.dumps({'session_id': sid})}\n\n"

    chat_history: list[dict] = []
    if tables_ready():
        try:
            prior = list_messages(user_id=operator_id, session_id=sid)
            chat_history = prepare_chat_history(
                [
                    {"role": row["role"], "content": row["content"]}
                    for row in prior
                ]
            )
        except ChatRepoError:
            chat_history = []

    append_message(
        user_id=operator_id,
        session_id=sid,
        role="user",
        content=user_message,
    )
    set_session_title_if_empty(sid, session_title or user_message)

    loop = asyncio.get_event_loop()
    stream = stream_factory(chat_history, sid)
    answer_parts: list[str] = []
    citations: list[Citation] = []
    artifacts: list[dict[str, Any]] = []

    async for item in _consume_stream_chunks(stream, loop):
        if isinstance(item, tuple):
            kind, value = item
            if kind == "__token__":
                answer_parts.append(value)
            elif kind == "__citations__":
                citations = value
            elif kind == "__artifact__":
                if isinstance(value, dict):
                    artifacts.append(value)
            continue
        yield item

    answer = "".join(answer_parts).strip()
    if answer:
        append_message(
            user_id=operator_id,
            session_id=sid,
            role="assistant",
            content=answer,
            citations=_citation_payload(citations) if citations else None,
            artifacts=artifacts or None,
        )


async def _sse_chat_stream(
    query: str,
    *,
    operator_id: str,
    session_id: str | None,
) -> AsyncIterator[str]:
    async for event in _sse_research_stream(
        query,
        operator_id=operator_id,
        session_id=session_id,
        stream_factory=lambda history, sid: ask_stream(
            query,
            history=history,
            operator_id=operator_id,
        ),
    ):
        yield event


async def _sse_briefing_stream(
    *,
    operator_id: str,
    session_id: str | None,
) -> AsyncIterator[str]:
    async for event in _sse_research_stream(
        BRIEFING_USER_MESSAGE,
        operator_id=operator_id,
        session_id=session_id,
        session_title=_briefing_session_title(),
        stream_factory=lambda history, sid: iter_briefing_stream(
            operator_id,
            history=history,
            exclude_session_id=sid,
        ),
    ):
        yield event


@router.post("")
async def chat(
    body: ChatRequest,
    user: dict | None = Depends(get_current_user),
) -> StreamingResponse:
    _require_chat_tables()
    operator_id = operator_id_from_user(user)
    return StreamingResponse(
        _sse_chat_stream(
            body.query.strip(),
            operator_id=operator_id,
            session_id=body.session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/briefing")
async def chat_briefing(
    body: BriefingRequest | None = None,
    user: dict | None = Depends(get_current_user),
) -> StreamingResponse:
    _require_chat_tables()
    operator_id = operator_id_from_user(user)
    session_id = body.session_id if body else None
    return StreamingResponse(
        _sse_briefing_stream(
            operator_id=operator_id,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
