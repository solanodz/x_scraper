"""Repositorio de Chat Session y mensajes del Research Chat."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.types.json import Json

from backend.app.db import connect


class ChatRepoError(Exception):
    pass


_artifacts_column_ready: bool | None = None


def _has_artifacts_column() -> bool:
    global _artifacts_column_ready
    if _artifacts_column_ready is not None:
        return _artifacts_column_ready
    sql = """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'chat_messages'
          AND column_name = 'artifacts'
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            _artifacts_column_ready = cur.fetchone() is not None
    return _artifacts_column_ready


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
    # Compatible con SELECT de 6 cols (sin artifacts) o 7 cols.
    if len(row) >= 7:
        mid, session_id, role, content, citations, artifacts, created_at = row[:7]
    else:
        mid, session_id, role, content, citations, created_at = row
        artifacts = None
    return {
        "id": str(mid),
        "session_id": str(session_id),
        "role": role,
        "content": content,
        "citations": citations if isinstance(citations, list) else None,
        "artifacts": artifacts if isinstance(artifacts, list) else None,
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

    if _has_artifacts_column():
        sql = """
            SELECT m.id, m.session_id, m.role, m.content, m.citations,
                   m.artifacts, m.created_at
            FROM chat_messages m
            JOIN chat_sessions s ON s.id = m.session_id
            WHERE m.session_id = %(session_id)s AND s.user_id = %(user_id)s
            ORDER BY m.created_at ASC
        """
    else:
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
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if role not in {"user", "assistant"}:
        raise ChatRepoError("invalid role")
    if get_session(user_id=user_id, session_id=session_id) is None:
        raise ChatRepoError("session not found")

    params = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "citations": Json(citations) if citations else None,
        "artifacts": Json(artifacts) if artifacts else None,
    }
    if _has_artifacts_column():
        sql = """
            INSERT INTO chat_messages
                (session_id, role, content, citations, artifacts)
            VALUES (
                %(session_id)s, %(role)s, %(content)s, %(citations)s, %(artifacts)s
            )
            RETURNING id, session_id, role, content, citations, artifacts, created_at
        """
    else:
        sql = """
            INSERT INTO chat_messages (session_id, role, content, citations)
            VALUES (%(session_id)s, %(role)s, %(content)s, %(citations)s)
            RETURNING id, session_id, role, content, citations, created_at
        """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            cur.execute(
                "UPDATE chat_sessions SET updated_at = now() WHERE id = %(id)s",
                {"id": session_id},
            )
    if row is None:
        raise ChatRepoError("failed to append message")
    return _row_to_message(row)


def get_previous_briefing(
    *,
    user_id: str,
    exclude_session_id: str | None = None,
) -> str | None:
    """Último assistant message de la sesión Briefing % más reciente (excluye sesión actual)."""
    if exclude_session_id:
        session_sql = """
            SELECT id
            FROM chat_sessions
            WHERE user_id = %(user_id)s
              AND title LIKE 'Briefing %%'
              AND id::text != %(exclude_id)s
            ORDER BY created_at DESC
            LIMIT 1
        """
        session_params = {"user_id": user_id, "exclude_id": exclude_session_id}
    else:
        session_sql = """
            SELECT id
            FROM chat_sessions
            WHERE user_id = %(user_id)s
              AND title LIKE 'Briefing %%'
            ORDER BY created_at DESC
            LIMIT 1
        """
        session_params = {"user_id": user_id}
    message_sql = """
        SELECT content
        FROM chat_messages
        WHERE session_id = %(session_id)s AND role = 'assistant'
        ORDER BY created_at DESC
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(session_sql, session_params)
            row = cur.fetchone()
            if row is None:
                return None
            session_id = row[0]
            cur.execute(message_sql, {"session_id": session_id})
            msg_row = cur.fetchone()
    if msg_row is None:
        return None
    content = (msg_row[0] or "").strip()
    return content or None


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
