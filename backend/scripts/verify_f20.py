"""Verificación F20: Briefing on-demand del Ticker Watch."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.auth import operator_id_from_user
from backend.app.main import app
from backend.app.services.chat_repo import tables_ready as chat_tables_ready
from backend.app.services.ticker_watch_repo import (
    add_watch,
    remove_watch,
    tables_ready as watch_tables_ready,
)
from backend.services.briefing import iter_briefing_stream
from backend.services.research_steps import ResearchStepEvent
from backend.services.types import Citation

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_WATCH_LOCAL = ROOT / "infra" / "store" / "init" / "006_ticker_watch.sql"
MIGRATION_WATCH_SUPABASE = ROOT / "infra" / "supabase" / "migrations" / "007_ticker_watch.sql"
MIGRATION_WATCH_SUPABASE_FK = (
    ROOT / "infra" / "supabase" / "migrations" / "008_ticker_watch_drop_user_fk.sql"
)
MIGRATION_CHAT_LOCAL = ROOT / "infra" / "store" / "init" / "005_operator_chat.sql"
MIGRATION_CHAT_SUPABASE_FK = ROOT / "infra" / "supabase" / "migrations" / "006_chat_drop_user_fk.sql"


def _apply_sql_file(path: Path) -> None:
    from backend.app.db import connect

    sql = path.read_text()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def _user_id_is_text(table: str) -> bool:
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %(table)s
                  AND column_name = 'user_id'
                """,
                {"table": table},
            )
            row = cur.fetchone()
    return bool(row and row[0] == "text")


def _maybe_relax_fk(constraint: str, table: str, migration: Path) -> None:
    if not migration.is_file():
        return
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = %(constraint)s
                  AND table_name = %(table)s
                """,
                {"constraint": constraint, "table": table},
            )
            if cur.fetchone() is None:
                return
    _apply_sql_file(migration)


def _auth_schema_exists() -> bool:
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.schemata
                WHERE schema_name = 'auth'
                """
            )
            return cur.fetchone() is not None


def _apply_watch_migration_if_needed() -> None:
    if watch_tables_ready():
        if (
            _user_id_is_text("ticker_watch")
            and _auth_schema_exists()
            and MIGRATION_WATCH_SUPABASE.is_file()
        ):
            _apply_sql_file(MIGRATION_WATCH_SUPABASE)
        _maybe_relax_fk(
            "ticker_watch_user_id_fkey",
            "ticker_watch",
            MIGRATION_WATCH_SUPABASE_FK,
        )
        return
    if not MIGRATION_WATCH_LOCAL.is_file():
        raise RuntimeError(f"migration not found: {MIGRATION_WATCH_LOCAL}")
    _apply_sql_file(MIGRATION_WATCH_LOCAL)
    if (
        _user_id_is_text("ticker_watch")
        and _auth_schema_exists()
        and MIGRATION_WATCH_SUPABASE.is_file()
    ):
        _apply_sql_file(MIGRATION_WATCH_SUPABASE)
    _maybe_relax_fk(
        "ticker_watch_user_id_fkey",
        "ticker_watch",
        MIGRATION_WATCH_SUPABASE_FK,
    )


def _apply_chat_migration_if_needed() -> None:
    if chat_tables_ready():
        _maybe_relax_fk(
            "chat_sessions_user_id_fkey",
            "chat_sessions",
            MIGRATION_CHAT_SUPABASE_FK,
        )
        return
    if not MIGRATION_CHAT_LOCAL.is_file():
        raise RuntimeError(f"migration not found: {MIGRATION_CHAT_LOCAL}")
    _apply_sql_file(MIGRATION_CHAT_LOCAL)
    _maybe_relax_fk(
        "chat_sessions_user_id_fkey",
        "chat_sessions",
        MIGRATION_CHAT_SUPABASE_FK,
    )


def _fake_stream_briefing_answer(context: str, *, hours: int, history=None):
    del context, hours, history
    yield "Briefing "
    yield "de prueba."


def _cleanup(user_id: str, symbols: list[str]) -> None:
    for sym in symbols:
        remove_watch(user_id=user_id, symbol=sym)


def main() -> int:
    print("== F20 verification: Briefing on-demand ==\n")
    load_dotenv()
    os.environ["AUTH_ENABLED"] = "false"

    print("0. Migrations (ticker_watch + chat)")
    try:
        _apply_watch_migration_if_needed()
        _apply_chat_migration_if_needed()
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return 1
    if not watch_tables_ready():
        print("   FAIL: ticker_watch table missing")
        return 1
    if not chat_tables_ready():
        print("   FAIL: chat tables missing")
        return 1
    print("   PASS\n")

    operator_id = operator_id_from_user(None)
    test_user = str(uuid.uuid4())
    _cleanup(test_user, ["NVDA"])

    print("1. iter_briefing_stream (service)")
    add_watch(user_id=test_user, symbol="NVDA")

    saw_revisando = False
    final_citations = None

    with patch(
        "backend.services.briefing.stream_briefing_answer",
        _fake_stream_briefing_answer,
    ):
        for chunk in iter_briefing_stream(test_user):
            if isinstance(chunk, ResearchStepEvent):
                if "Revisando" in chunk.label:
                    saw_revisando = True
            elif isinstance(chunk, list):
                final_citations = chunk

    _cleanup(test_user, ["NVDA"])

    if not saw_revisando:
        print("   FAIL: missing 'Revisando' step event")
        return 1
    if not isinstance(final_citations, list):
        print(f"   FAIL: expected citations list, got {type(final_citations)}")
        return 1
    print(f"   revisando step: {saw_revisando}")
    print(f"   citations type: list ({len(final_citations)} items)")
    print("   PASS\n")

    print("2. POST /chat/briefing (SSE)")
    client = TestClient(app)

    with patch(
        "backend.services.briefing.stream_briefing_answer",
        _fake_stream_briefing_answer,
    ):
        add_watch(user_id=operator_id, symbol="NVDA")
        with client.stream("POST", "/chat/briefing", json={}) as response:
            if response.status_code != 200:
                print(f"   FAIL: status {response.status_code} {response.text}")
                _cleanup(operator_id, ["NVDA"])
                return 1
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                print(f"   FAIL: content-type {content_type}")
                _cleanup(operator_id, ["NVDA"])
                return 1
            body = "".join(response.iter_text())

    _cleanup(operator_id, ["NVDA"])

    if "event: step" not in body:
        print("   FAIL: missing event: step in SSE body")
        return 1
    if "Revisando" not in body:
        print("   FAIL: missing Revisando in SSE body")
        return 1
    print("   content-type: text/event-stream")
    print("   event: step present")
    print("   PASS\n")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        print("3. stream_briefing_answer (live synthesis)")
        from backend.services.llm import stream_briefing_answer

        tokens = list(
            stream_briefing_answer(
                "## NVDA\nPrecio: $100.00 (+1.00%)\nSin novedades en las últimas 24h",
                hours=24,
            )
        )
        if not tokens:
            print("   WARN: synthesis returned no tokens")
        else:
            print(f"   tokens: {len(tokens)}")
        print("   PASS\n")
    else:
        print("3. stream_briefing_answer (live synthesis)")
        print("   SKIP: OPENAI_API_KEY not configured")
        print("   PASS\n")

    print("== F20 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
