"""Verificación F22: Briefing delta vs anterior."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

from backend.app.services.chat_repo import (
    append_message,
    create_session,
    get_previous_briefing,
    tables_ready,
)
from backend.services.briefing import (
    _BriefingSlice,
    _build_context,
    _wrap_with_previous_briefing,
    iter_briefing_stream,
)
from backend.services.market_data import Quote
from backend.services.research_steps import ResearchStepEvent

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_LOCAL = ROOT / "infra" / "store" / "init" / "005_operator_chat.sql"
MIGRATION_SUPABASE_FK = ROOT / "infra" / "supabase" / "migrations" / "006_chat_drop_user_fk.sql"

FAKE_PRIOR_BRIEFING = (
    "## Lo más relevante hoy\n"
    "- NVDA subió tras earnings.\n"
    "## Prioridad alta\n"
    "### NVDA\n"
    "Hecho: beat de guidance."
)


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


def _make_quote(symbol: str) -> Quote:
    from datetime import datetime, timezone

    return Quote(
        symbol=symbol,
        price=100.0,
        change=1.0,
        change_percent=1.0,
        timestamp=datetime.now(timezone.utc),
        delayed=True,
    )


def main() -> int:
    print("== F22 verification: Briefing delta vs anterior ==\n")
    load_dotenv()
    os.environ["AUTH_ENABLED"] = "false"

    print("0. Chat tables")
    try:
        _apply_migration_if_needed()
        _maybe_relax_supabase_fk()
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return 1
    if not tables_ready():
        print("   FAIL — chat_sessions/chat_messages missing")
        return 1
    print("   PASS\n")

    test_user = str(uuid.uuid4())
    current_session = create_session(
        user_id=test_user,
        title="Briefing 06/07/2026",
    )
    prior_session = create_session(
        user_id=test_user,
        title="Briefing 05/07/2026",
    )
    append_message(
        user_id=test_user,
        session_id=prior_session["id"],
        role="user",
        content="Briefing de mi Ticker Watch",
    )
    append_message(
        user_id=test_user,
        session_id=prior_session["id"],
        role="assistant",
        content=FAKE_PRIOR_BRIEFING,
    )

    print("1. get_previous_briefing")
    previous = get_previous_briefing(
        user_id=test_user,
        exclude_session_id=current_session["id"],
    )
    if previous != FAKE_PRIOR_BRIEFING:
        print(f"   FAIL — expected prior briefing, got: {previous!r}")
        return 1
    print("   prior briefing content returned")
    print("   PASS\n")

    print("2. context wrap (_wrap_with_previous_briefing)")
    slices = [_BriefingSlice("NVDA", [], _make_quote("NVDA"))]
    base_context = _build_context(slices, hours=24)
    wrapped = _wrap_with_previous_briefing(base_context, FAKE_PRIOR_BRIEFING)
    if "--- Briefing anterior (referencia para delta) ---" not in wrapped:
        print("   FAIL — missing Briefing anterior marker in wrapped context")
        return 1
    if "--- Datos actuales ---" not in wrapped:
        print("   FAIL — missing Datos actuales marker in wrapped context")
        return 1
    if FAKE_PRIOR_BRIEFING not in wrapped:
        print("   FAIL — prior briefing text not in wrapped context")
        return 1
    if base_context not in wrapped:
        print("   FAIL — current context not preserved after wrap")
        return 1
    print("   wrapped context includes prior + current markers")
    print("   PASS\n")

    print("3. iter_briefing_stream exclude_session_id (mocked watch)")
    captured_context: list[str] = []

    def _fake_stream_briefing_answer(context: str, *, hours: int, history=None):
        del hours, history
        captured_context.append(context)
        yield "Delta memo."

    empty_user = str(uuid.uuid4())

    with patch(
        "backend.services.briefing.get_previous_briefing",
        return_value=None,
    ):
        with patch(
            "backend.services.briefing.stream_briefing_answer",
            _fake_stream_briefing_answer,
        ):
            for chunk in iter_briefing_stream(empty_user):
                if isinstance(chunk, str) and chunk.startswith("Tu Ticker Watch"):
                    break

    if captured_context:
        print("   FAIL — empty watch should not call stream_briefing_answer")
        return 1

    captured_context.clear()
    watch_user = str(uuid.uuid4())
    exclude_sid = str(uuid.uuid4())

    with (
        patch(
            "backend.services.briefing._load_watch_entries",
            return_value=[{"symbol": "NVDA", "note": None}],
        ),
        patch(
            "backend.services.briefing.get_recent_signals",
            return_value=[],
        ),
        patch(
            "backend.services.briefing.fetch_quotes",
            return_value=[_make_quote("NVDA")],
        ),
        patch(
            "backend.services.briefing.get_previous_briefing",
            return_value=FAKE_PRIOR_BRIEFING,
        ) as mock_prev,
        patch(
            "backend.services.briefing.stream_briefing_answer",
            _fake_stream_briefing_answer,
        ),
    ):
        for chunk in iter_briefing_stream(
            watch_user,
            exclude_session_id=exclude_sid,
        ):
            if isinstance(chunk, ResearchStepEvent):
                continue
            if isinstance(chunk, list):
                break

    mock_prev.assert_called_with(
        user_id=watch_user,
        exclude_session_id=exclude_sid,
    )
    if not captured_context:
        print("   FAIL — stream_briefing_answer never called")
        return 1
    if "--- Briefing anterior (referencia para delta) ---" not in captured_context[0]:
        print("   FAIL — iter stream context missing Briefing anterior wrapper")
        return 1
    print("   exclude_session_id forwarded; context wrapped with prior briefing")
    print("   PASS\n")

    print("4. no prior briefing — no wrapper")
    captured_context.clear()
    no_prior_user = str(uuid.uuid4())

    with (
        patch(
            "backend.services.briefing._load_watch_entries",
            return_value=[{"symbol": "AAPL", "note": None}],
        ),
        patch(
            "backend.services.briefing.get_recent_signals",
            return_value=[],
        ),
        patch(
            "backend.services.briefing.fetch_quotes",
            return_value=[_make_quote("AAPL")],
        ),
        patch(
            "backend.services.briefing.get_previous_briefing",
            return_value=None,
        ),
        patch(
            "backend.services.briefing.stream_briefing_answer",
            _fake_stream_briefing_answer,
        ),
    ):
        for chunk in iter_briefing_stream(no_prior_user):
            if isinstance(chunk, list):
                break

    if not captured_context:
        print("   FAIL — stream_briefing_answer never called")
        return 1
    if "Briefing anterior" in captured_context[0]:
        print("   FAIL — wrapper present without prior briefing")
        return 1
    print("   context has no Briefing anterior wrapper when prior is None")
    print("   PASS\n")

    print("== F22 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
