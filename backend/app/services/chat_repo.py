"""Repositorio de Chat Session y mensajes del Research Chat."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from backend.app.db import connect


class ChatRepoError(Exception):
    pass


def _row_to_session(row: tuple) -> dict[str, Any]:
    sid, user_id, title, created_at, updated_at = row
    return {
        "id": str(sid),
        "user_id": str(user_id),
        "title": title,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _row_to_message(row: tuple) -> dict[str, Any]:
    mid, session_id, role, content, citations, created_at = row
    return {
        "id": str(mid),
        "session_id": str(session_id),
        "role": role,
        "content": content,
        "citations": citations if isinstance(citations, list) else None,
        "created_at": created_at,
    }


def create_session(*, user_id: str, title: str | None = None) -> dict[str, Any]:
    sql = """
        INSERT INTO chat_sessions (user_id, title)
        VALUES (%(user_id)s, %(title)s)
        RETURNING id, user_id, title, created_at, updated_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"user_id": user_id, "title": title})
            row = cur.fetchone()
    if row is None:
        raise ChatRepoError("failed to create chat session")
    return _row_to_session(row)


def list_sessions(*, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    sql = """
        SELECT id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE user_id = %(user_id)s
        ORDER BY updated_at DESC
        LIMIT %(limit)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"user_id": user_id, "limit": limit})
            rows = cur.fetchall()
    return [_row_to_session(row) for row in rows]


def get_session(*, user_id: str, session_id: str) -> dict[str, Any] | None:
    sql = """
        SELECT id, user_id, title, created_at, updated_at
        FROM chat_sessions
        WHERE id = %(session_id)s AND user_id = %(user_id)s
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"session_id": session_id, "user_id": user_id})
            row = cur.fetchone()
    return _row_to_session(row) if row else None


def touch_session(session_id: str) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET updated_at = now() WHERE id = %(id)s",
                {"id": session_id},
            )


def set_session_title_if_empty(session_id: str, title: str) -> None:
    cleaned = title.strip()[:80]
    if not cleaned:
        return
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET title = %(title)s, updated_at = now()
                WHERE id = %(id)s AND (title IS NULL OR trim(title) = '')
                """,
                {"id": session_id, "title": cleaned},
            )


def list_messages(*, user_id: str, session_id: str) -> list[dict[str, Any]]:
    if get_session(user_id=user_id, session_id=session_id) is None:
        raise ChatRepoError("session not found")

    sql = """
        SELECT m.id, m.session_id, m.role, m.content, m.citations, m.created_at
        FROM chat_messages m
        JOIN chat_sessions s ON s.id = m.session_id
        WHERE m.session_id = %(session_id)s AND s.user_id = %(user_id)s
        ORDER BY m.created_at ASC
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"session_id": session_id, "user_id": user_id})
            rows = cur.fetchall()
    return [_row_to_message(row) for row in rows]


def append_message(
    *,
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    citations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if role not in {"user", "assistant"}:
        raise ChatRepoError("invalid role")
    if get_session(user_id=user_id, session_id=session_id) is None:
        raise ChatRepoError("session not found")

    sql = """
        INSERT INTO chat_messages (session_id, role, content, citations)
        VALUES (%(session_id)s, %(role)s, %(content)s, %(citations)s)
        RETURNING id, session_id, role, content, citations, created_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "citations": Json(citations) if citations else None,
                },
            )
            row = cur.fetchone()
            cur.execute(
                "UPDATE chat_sessions SET updated_at = now() WHERE id = %(id)s",
                {"id": session_id},
            )
    if row is None:
        raise ChatRepoError("failed to append message")
    return _row_to_message(row)


def ensure_session(
    *,
    user_id: str,
    session_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    if session_id:
        try:
            uuid.UUID(session_id)
        except ValueError:
            session_id = None
        else:
            existing = get_session(user_id=user_id, session_id=session_id)
            if existing:
                return existing
    return create_session(user_id=user_id, title=title)


def tables_ready() -> bool:
    sql = """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('chat_sessions', 'chat_messages')
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    return bool(row and int(row[0]) >= 2)
