"""Verificación F15: Chat Session (historial Research Chat)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.auth import operator_id_from_user
from backend.app.main import app
from backend.app.services.chat_repo import (
    append_message,
    ensure_session,
    list_messages,
    list_sessions,
    tables_ready,
)
from backend.services.types import AskResult, Citation

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_LOCAL = ROOT / "infra" / "store" / "init" / "005_operator_chat.sql"
MIGRATION_SUPABASE_FK = ROOT / "infra" / "supabase" / "migrations" / "006_chat_drop_user_fk.sql"


def _apply_sql_file(path: Path) -> None:
    from backend.app.db import connect

    sql = path.read_text()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def _apply_migration_if_needed() -> None:
    if tables_ready():
        _maybe_relax_supabase_fk()
        return
    if not MIGRATION_LOCAL.is_file():
        raise RuntimeError(f"migration not found: {MIGRATION_LOCAL}")
    _apply_sql_file(MIGRATION_LOCAL)


def _maybe_relax_supabase_fk() -> None:
    """Supabase 002 tiene FK a auth.users; 006 la suelta para dev sin login."""
    if not MIGRATION_SUPABASE_FK.is_file():
        return
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'chat_sessions_user_id_fkey'
                  AND table_name = 'chat_sessions'
                """
            )
            if cur.fetchone() is None:
                return
    _apply_sql_file(MIGRATION_SUPABASE_FK)


def main() -> int:
    print("== F15 verification: Chat Session ==\n")
    load_dotenv()
    os.environ["AUTH_ENABLED"] = "false"

    print("0. Chat tables")
    try:
        _apply_migration_if_needed()
        _maybe_relax_supabase_fk()
    except Exception as exc:
        print(f"   FAIL — {exc}")
        print("\n== F15 verification FAIL ==")
        return 1
    print(f"   tables_ready={tables_ready()}")
    if not tables_ready():
        print("   FAIL — chat_sessions/chat_messages missing")
        print("\n== F15 verification FAIL ==")
        return 1
    print("   PASS\n")

    operator_id = operator_id_from_user(None)
    print(f"1. Operator id (local): {operator_id}")

    session = ensure_session(user_id=operator_id, title="verify f15")
    sid = session["id"]
    append_message(
        user_id=operator_id,
        session_id=sid,
        role="user",
        content="verify user message",
    )
    append_message(
        user_id=operator_id,
        session_id=sid,
        role="assistant",
        content="verify assistant answer",
        citations=[
            {
                "id_str": "rss:test",
                "username": "Reuters",
                "url": "https://example.com",
                "excerpt": "sample",
            }
        ],
    )
    rows = list_messages(user_id=operator_id, session_id=sid)
    print(f"   messages persisted: {len(rows)}")
    if len(rows) < 2:
        print("   FAIL — expected user + assistant messages")
        print("\n== F15 verification FAIL ==")
        return 1
    if rows[1].get("citations") is None:
        print("   FAIL — assistant citations not stored")
        print("\n== F15 verification FAIL ==")
        return 1
    print("   PASS\n")

    client = TestClient(app)

    print("2. GET /chat/sessions")
    r = client.get("/chat/sessions")
    if r.status_code != 200:
        print(f"   FAIL: {r.status_code} {r.text}")
        print("\n== F15 verification FAIL ==")
        return 1
    sessions = r.json()
    if not any(item["id"] == sid for item in sessions):
        print("   FAIL — seeded session not listed")
        print("\n== F15 verification FAIL ==")
        return 1
    print(f"   sessions: {len(sessions)}")
    print("   PASS\n")

    print("3. GET /chat/sessions/{id}/messages")
    r = client.get(f"/chat/sessions/{sid}/messages")
    if r.status_code != 200:
        print(f"   FAIL: {r.status_code}")
        print("\n== F15 verification FAIL ==")
        return 1
    api_messages = r.json()
    if len(api_messages) < 2:
        print("   FAIL — API history incomplete")
        print("\n== F15 verification FAIL ==")
        return 1
    print(f"   messages: {len(api_messages)}")
    print("   PASS\n")

    print("4. POST /chat persists streamed exchange")

    def _fake_ask_stream(query: str):
        yield "Persisted "
        yield "answer."
        yield [
            Citation(
                id_str="rss:verify",
                username="Reuters",
                url="https://example.com/a",
                excerpt="excerpt",
            )
        ]

    with patch("backend.app.routes.chat.ask_stream", _fake_ask_stream):
        with client.stream(
            "POST",
            "/chat",
            json={"query": "verify stream persistence", "session_id": sid},
        ) as response:
            if response.status_code != 200:
                print(f"   FAIL: status {response.status_code}")
                print("\n== F15 verification FAIL ==")
                return 1
            body = "".join(response.iter_text())

    if "event: session" not in body:
        print("   FAIL — missing session SSE event")
        print("\n== F15 verification FAIL ==")
        return 1

    refreshed = list_messages(user_id=operator_id, session_id=sid)
    print(f"   messages after stream: {len(refreshed)}")
    if len(refreshed) < 4:
        print("   FAIL — stream did not append user+assistant messages")
        print("\n== F15 verification FAIL ==")
        return 1
    last = refreshed[-1]
    if last["role"] != "assistant" or "Persisted answer." not in last["content"]:
        print("   FAIL — assistant content mismatch")
        print("\n== F15 verification FAIL ==")
        return 1
    print("   PASS\n")

    print("5. POST /chat/sessions (new empty session)")
    r = client.post("/chat/sessions", json={})
    if r.status_code != 200:
        print(f"   FAIL: {r.status_code}")
        print("\n== F15 verification FAIL ==")
        return 1
    new_sid = r.json()["id"]
    r = client.get(f"/chat/sessions/{new_sid}/messages")
    if r.status_code != 200 or r.json():
        print("   FAIL — new session should start empty")
        print("\n== F15 verification FAIL ==")
        return 1
    print("   PASS\n")

    print("== F15 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
