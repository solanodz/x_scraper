"""Orquestador del Morning Briefing Email (F46).

FX solo USD/ARS vía get_fx_quotes(scope="ars_usd").
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.auth import operator_id_from_user
from backend.app.services.briefing_email_repo import (
    already_sent,
    insert_sent_log,
    table_ready as log_table_ready,
)
from backend.app.services.chat_repo import (
    append_message,
    ensure_session,
    set_session_title_if_empty,
    tables_ready as chat_tables_ready,
)
from backend.services.briefing import iter_briefing_stream
from backend.services.briefing_email_render import build_email_bodies
from backend.services.email_resend import send_email
from backend.services.fx import get_fx_quotes
from backend.services.research_steps import ResearchStepEvent
from backend.services.types import Citation

BRIEFING_USER_MESSAGE = "Briefing de mi Ticker Watch"

_DEFAULT_TZ = "America/Argentina/Buenos_Aires"


def _env_truthy(name: str, default: str = "false") -> bool:
    raw = (os.getenv(name, default) or default).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _briefing_session_title(sent_on: date) -> str:
    """Mirror de chat._briefing_session_title con fecha del TZ del Briefing."""
    return f"Briefing {sent_on.day:02d}/{sent_on.month:02d}/{sent_on.year}"


def _resolve_operator_id() -> str:
    override = (os.getenv("BRIEFING_OPERATOR_ID") or "").strip()
    if override:
        return override
    return operator_id_from_user(None)


def _sent_on_today() -> date:
    tz_name = (os.getenv("BRIEFING_EMAIL_TZ") or _DEFAULT_TZ).strip() or _DEFAULT_TZ
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(_DEFAULT_TZ)
    return datetime.now(tz).date()


def _citation_payload(citations: list[Citation]) -> list[dict[str, Any]]:
    return [
        {
            "id_str": c.id_str,
            "username": c.username,
            "url": c.url,
            "excerpt": c.excerpt,
        }
        for c in citations
    ]


def _collect_briefing(operator_id: str) -> tuple[str, list[Citation]]:
    """Recolecta markdown del Briefing; ignora ResearchStepEvent."""
    parts: list[str] = []
    citations: list[Citation] = []
    for chunk in iter_briefing_stream(operator_id):
        if isinstance(chunk, ResearchStepEvent):
            continue
        if isinstance(chunk, list):
            citations = [c for c in chunk if isinstance(c, Citation)]
            continue
        parts.append(str(chunk))
    return "".join(parts).strip(), citations


def _persist_briefing_session(
    *,
    operator_id: str,
    sent_on: date,
    content: str,
    citations: list[Citation],
) -> str | None:
    """Persiste Chat Session como el Briefing on-demand. Retorna session_id."""
    if not chat_tables_ready():
        return None
    title = _briefing_session_title(sent_on)
    session = ensure_session(user_id=operator_id, title=title)
    sid = session["id"]
    set_session_title_if_empty(sid, title)
    append_message(
        user_id=operator_id,
        session_id=sid,
        role="user",
        content=BRIEFING_USER_MESSAGE,
    )
    if content:
        append_message(
            user_id=operator_id,
            session_id=sid,
            role="assistant",
            content=content,
            citations=_citation_payload(citations) if citations else None,
        )
    return sid


def run_morning_briefing(
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Genera y (opcionalmente) envía el Morning Briefing Email."""
    enabled = _env_truthy("BRIEFING_EMAIL_ENABLED", "false")
    if not enabled and not dry_run:
        return {
            "skipped": True,
            "reason": "disabled",
            "dry_run": dry_run,
            "force": force,
        }

    operator_id = _resolve_operator_id()
    sent_on = _sent_on_today()

    if not force:
        try:
            was_sent = log_table_ready() and already_sent(
                operator_id=operator_id,
                sent_on=sent_on,
            )
        except Exception:
            if dry_run:
                was_sent = False
            else:
                raise
        if was_sent:
            return {
                "skipped": True,
                "reason": "already_sent",
                "operator_id": operator_id,
                "sent_on": sent_on.isoformat(),
                "dry_run": dry_run,
                "force": force,
            }

    to_addr = (os.getenv("BRIEFING_EMAIL_TO") or "").strip()
    if not dry_run and not to_addr:
        raise ValueError("BRIEFING_EMAIL_TO requerida para envío real")

    # FX: SOLO ars_usd (nunca pair / Frankfurter)
    fx_payload = get_fx_quotes(scope="ars_usd")

    briefing_md, citations = _collect_briefing(operator_id)

    frontend_base = (
        os.getenv("FRONTEND_BASE_URL") or "http://localhost:3000"
    ).strip()
    tz_name = (os.getenv("BRIEFING_EMAIL_TZ") or _DEFAULT_TZ).strip() or _DEFAULT_TZ
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(_DEFAULT_TZ)
    now_local = datetime.now(tz)
    has_prioridad = "prioridad alta" in briefing_md.lower() or "## Prioridad alta" in briefing_md

    subject, text_body, html_body = build_email_bodies(
        briefing_markdown=briefing_md,
        fx_payload=fx_payload,
        frontend_base_url=frontend_base,
        now_local=now_local,
        has_prioridad_alta=has_prioridad,
    )

    result: dict[str, Any] = {
        "skipped": False,
        "operator_id": operator_id,
        "sent_on": sent_on.isoformat(),
        "dry_run": dry_run,
        "force": force,
        "subject": subject,
        "session_id": None,
        "to": to_addr or None,
    }

    if dry_run:
        result["text"] = text_body
        result["html"] = html_body
        result["resend_id"] = None
        return result

    session_id = _persist_briefing_session(
        operator_id=operator_id,
        sent_on=sent_on,
        content=briefing_md,
        citations=citations,
    )
    result["session_id"] = session_id

    resend_id = send_email(
        to=to_addr,
        subject=subject,
        html=html_body,
        text=text_body,
    )
    insert_sent_log(
        operator_id=operator_id,
        sent_on=sent_on,
        resend_id=resend_id,
    )
    result["resend_id"] = resend_id
    return result
