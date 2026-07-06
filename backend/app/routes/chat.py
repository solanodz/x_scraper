"""Chat Stream del Research Chat + Chat Session persistence."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth import get_current_user, operator_id_from_user
from backend.app.schemas import (
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
from backend.services.chat_history import prepare_chat_history
from backend.services.research_steps import ResearchStepEvent
from backend.services.types import Citation
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/chat", tags=["chat"])


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
    return ChatMessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        citations=citations,
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


async def _sse_chat_stream(
    query: str,
    *,
    operator_id: str,
    session_id: str | None,
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
        content=query,
    )
    set_session_title_if_empty(sid, query)

    loop = asyncio.get_event_loop()
    stream = ask_stream(query, history=chat_history)
    answer_parts: list[str] = []
    citations: list[Citation] = []

    while True:
        chunk = await loop.run_in_executor(None, lambda: next(stream, None))
        if chunk is None:
            break
        if isinstance(chunk, ResearchStepEvent):
            payload = chunk.to_dict()
            yield f"event: step\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        elif isinstance(chunk, list):
            citations = chunk
            payload = _citation_payload(citations)
            yield f"event: citations\ndata: {json.dumps(payload)}\n\n"
        else:
            answer_parts.append(chunk)
            yield f"data: {json.dumps(chunk)}\n\n"

    answer = "".join(answer_parts).strip()
    if answer:
        append_message(
            user_id=operator_id,
            session_id=sid,
            role="assistant",
            content=answer,
            citations=_citation_payload(citations) if citations else None,
        )


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
