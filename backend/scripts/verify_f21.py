"""Verificación F21: Briefing memo de decisión."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

from backend.app.services.ticker_watch_repo import (
    add_watch,
    remove_watch,
    tables_ready as watch_tables_ready,
)
from backend.services.briefing import (
    _BriefingSlice,
    _build_context,
    _mark_prioridad_alta,
    _slice_sort_key,
    iter_briefing_stream,
)
from backend.services.market_data import Quote
from backend.services.research_steps import ResearchStepEvent
from backend.services.types import SignalHit

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_WATCH_LOCAL = ROOT / "infra" / "store" / "init" / "006_ticker_watch.sql"
MIGRATION_WATCH_SUPABASE = ROOT / "infra" / "supabase" / "migrations" / "007_ticker_watch.sql"
MIGRATION_WATCH_SUPABASE_FK = (
    ROOT / "infra" / "supabase" / "migrations" / "008_ticker_watch_drop_user_fk.sql"
)


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


def _make_hit(id_str: str, content: str) -> SignalHit:
    return SignalHit(
        id_str=id_str,
        username="Reuters",
        raw_content=content,
        published_at=datetime.now(timezone.utc),
        source="rss",
        similarity=1.0,
        url=f"https://example.com/{id_str}",
    )


def _make_quote(symbol: str, change_percent: float) -> Quote:
    return Quote(
        symbol=symbol,
        price=100.0,
        change=change_percent,
        change_percent=change_percent,
        timestamp=datetime.now(timezone.utc),
        delayed=True,
    )


def _mock_get_recent_signals(*, ticker=None, hours=None, limit=None):
    del hours, limit
    if ticker == "NVDA":
        return [_make_hit(f"nvda-{i}", f"NVDA headline {i}") for i in range(5)]
    if ticker == "AAPL":
        return [_make_hit("aapl-1", "AAPL headline 1")]
    return []


def _mock_fetch_quotes(symbols: list[str]) -> list[Quote]:
    return [_make_quote(symbol, 2.0 if symbol == "NVDA" else 0.5) for symbol in symbols]


def _cleanup(user_id: str, symbols: list[str]) -> None:
    for sym in symbols:
        remove_watch(user_id=user_id, symbol=sym)


def main() -> int:
    print("== F21 verification: Briefing memo de decisión ==\n")
    load_dotenv()
    os.environ["AUTH_ENABLED"] = "false"

    print("0. Migration (ticker_watch)")
    try:
        _apply_watch_migration_if_needed()
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return 1
    if not watch_tables_ready():
        print("   FAIL: ticker_watch table missing")
        return 1
    print("   PASS\n")

    print("1. prioridad_alta ranking + context (_build_context)")
    nvda_hits = _mock_get_recent_signals(ticker="NVDA")
    aapl_hits = _mock_get_recent_signals(ticker="AAPL")
    msft_hits = _mock_get_recent_signals(ticker="MSFT")
    slices = [
        _BriefingSlice("MSFT", msft_hits, _make_quote("MSFT", 0.1)),
        _BriefingSlice("AAPL", aapl_hits, _make_quote("AAPL", 0.5)),
        _BriefingSlice("NVDA", nvda_hits, _make_quote("NVDA", 2.0)),
    ]
    slices.sort(key=_slice_sort_key)
    _mark_prioridad_alta(slices)
    context = _build_context(slices, hours=24)

    prioridad_markers = context.count("prioridad_alta: true")
    if prioridad_markers > 2:
        print(f"   FAIL: expected at most 2 prioridad_alta markers, got {prioridad_markers}")
        return 1
    if "prioridad_alta: true" not in context.split("## AAPL")[0]:
        print("   FAIL: NVDA (top by signal count) missing prioridad_alta: true")
        return 1
    if "prioridad_alta: 2" not in context:
        print("   FAIL: summary header missing prioridad_alta count")
        return 1
    if "# Sin novedades" not in context or "MSFT" not in context:
        print("   FAIL: quiet ticker MSFT not grouped under Sin novedades")
        return 1
    print(f"   prioridad_alta markers: {prioridad_markers}")
    print("   NVDA flagged prioridad_alta")
    print("   summary header + sin_novedad group present")
    print("   PASS\n")

    test_user = str(uuid.uuid4())
    symbols = ["NVDA", "AAPL", "MSFT"]
    _cleanup(test_user, symbols)

    print("2. iter_briefing_stream (mocked data + synthesis)")
    add_watch(user_id=test_user, symbol="NVDA")
    add_watch(user_id=test_user, symbol="AAPL")
    add_watch(user_id=test_user, symbol="MSFT")

    captured_context: list[str] = []
    saw_revisando = False
    tokens: list[str] = []
    final_citations = None

    def _fake_stream_briefing_answer(context: str, *, hours: int, history=None):
        del hours, history
        captured_context.append(context)
        yield "Memo "
        yield "de decisión."

    with (
        patch(
            "backend.services.briefing.get_recent_signals",
            side_effect=_mock_get_recent_signals,
        ),
        patch(
            "backend.services.briefing.fetch_quotes",
            side_effect=_mock_fetch_quotes,
        ),
        patch(
            "backend.services.briefing.stream_briefing_answer",
            _fake_stream_briefing_answer,
        ),
    ):
        for chunk in iter_briefing_stream(test_user):
            if isinstance(chunk, ResearchStepEvent):
                if "Revisando" in chunk.label:
                    saw_revisando = True
            elif isinstance(chunk, str):
                tokens.append(chunk)
            elif isinstance(chunk, list):
                final_citations = chunk

    _cleanup(test_user, symbols)

    if not captured_context:
        print("   FAIL: stream_briefing_answer never called")
        return 1

    stream_context = captured_context[0]
    stream_markers = stream_context.count("prioridad_alta: true")
    if stream_markers > 2:
        print(f"   FAIL: stream context has {stream_markers} prioridad_alta markers")
        return 1
    nvda_block = stream_context.split("## NVDA")[1].split("##")[0]
    if "prioridad_alta: true" not in nvda_block:
        print("   FAIL: NVDA missing prioridad_alta in stream context")
        return 1
    if not saw_revisando:
        print("   FAIL: missing 'Revisando' step event")
        return 1
    if not tokens:
        print("   FAIL: no synthesis tokens yielded")
        return 1
    if not isinstance(final_citations, list):
        print(f"   FAIL: expected citations list, got {type(final_citations)}")
        return 1

    print(f"   stream prioridad_alta markers: {stream_markers}")
    print(f"   synthesis tokens: {len(tokens)}")
    print(f"   citations: {len(final_citations)}")
    print("   PASS\n")

    print("== F21 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
