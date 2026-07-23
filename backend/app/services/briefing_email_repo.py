"""Persistencia del log de Morning Briefing Email (idempotencia diaria)."""

from __future__ import annotations

from datetime import date
from typing import Any

from backend.app.db import connect


class BriefingEmailRepoError(Exception):
    pass


def already_sent(*, operator_id: str, sent_on: date) -> bool:
    """True si ya hay un envío exitoso para (operator_id, sent_on)."""
    sql = """
        SELECT 1
        FROM briefing_email_log
        WHERE operator_id = %(operator_id)s::uuid
          AND sent_on = %(sent_on)s
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {"operator_id": operator_id, "sent_on": sent_on},
            )
            return cur.fetchone() is not None


def insert_sent_log(
    *,
    operator_id: str,
    sent_on: date,
    resend_id: str | None,
) -> dict[str, Any]:
    """Registra envío. ON CONFLICT actualiza resend_id (para --force)."""
    sql = """
        INSERT INTO briefing_email_log (operator_id, sent_on, resend_id)
        VALUES (%(operator_id)s::uuid, %(sent_on)s, %(resend_id)s)
        ON CONFLICT (operator_id, sent_on) DO UPDATE
          SET resend_id = EXCLUDED.resend_id,
              created_at = now()
        RETURNING id, operator_id, sent_on, resend_id, created_at
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "operator_id": operator_id,
                    "sent_on": sent_on,
                    "resend_id": resend_id,
                },
            )
            row = cur.fetchone()
    if row is None:
        raise BriefingEmailRepoError("failed to insert briefing_email_log")
    return {
        "id": str(row[0]),
        "operator_id": str(row[1]),
        "sent_on": row[2],
        "resend_id": row[3],
        "created_at": row[4],
    }


def table_ready() -> bool:
    sql = """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'briefing_email_log'
        LIMIT 1
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone() is not None
