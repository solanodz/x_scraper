"""Utilidades para memoria conversacional del Research Chat."""

from __future__ import annotations

import os


def chat_history_limit() -> int:
    raw = os.getenv("CHAT_HISTORY_MAX_MESSAGES", "20").strip()
    try:
        return max(0, min(int(raw), 50))
    except ValueError:
        return 20


def prepare_chat_history(
    history: list[dict] | None,
    *,
    max_messages: int | None = None,
) -> list[dict]:
    """Normaliza y recorta el historial persistido (user/assistant)."""
    if not history:
        return []

    limit = chat_history_limit() if max_messages is None else max_messages
    cleaned: list[dict] = []
    for entry in history:
        role = entry.get("role")
        content = (entry.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        cleaned.append({"role": role, "content": content})

    if limit <= 0:
        return []
    return cleaned[-limit:]
