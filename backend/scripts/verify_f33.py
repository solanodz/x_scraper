"""Verificación F33: Chart Plan + Chart Agent on-demand."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.auth import operator_id_from_user
from backend.app.main import app
from backend.app.services.chart_plan_repo import (
    get_latest,
    list_versions,
    tables_ready as chart_plan_tables_ready,
)
from backend.app.services.dossier_repo import (
    save_version as save_dossier_version,
    tables_ready as dossier_tables_ready,
)
from backend.app.services.ticker_watch_repo import (
    add_watch,
    remove_watch,
    tables_ready as watch_tables_ready,
)
from backend.services.research_steps import ResearchStepEvent

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_WATCH_LOCAL = ROOT / "infra" / "store" / "init" / "006_ticker_watch.sql"
MIGRATION_WATCH_SUPABASE = ROOT / "infra" / "supabase" / "migrations" / "007_ticker_watch.sql"
MIGRATION_WATCH_SUPABASE_FK = (
    ROOT / "infra" / "supabase" / "migrations" / "008_ticker_watch_drop_user_fk.sql"
)
MIGRATION_DOSSIER_LOCAL = ROOT / "infra" / "store" / "init" / "009_ticker_dossier_versions.sql"
MIGRATION_DOSSIER_SUPABASE = (
    ROOT / "infra" / "supabase" / "migrations" / "009_ticker_dossier_versions.sql"
)
MIGRATION_CHART_PLAN_LOCAL = (
    ROOT / "infra" / "store" / "init" / "010_ticker_chart_plan_versions.sql"
)
MIGRATION_CHART_PLAN_SUPABASE = (
    ROOT / "infra" / "supabase" / "migrations" / "010_ticker_chart_plan_versions.sql"
)

TEST_SYMBOL = "TEST"


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
        if _user_id_is_text("ticker_watch") and _auth_schema_exists():
            if MIGRATION_WATCH_SUPABASE.is_file():
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
    if _user_id_is_text("ticker_watch") and MIGRATION_WATCH_SUPABASE.is_file():
        _apply_sql_file(MIGRATION_WATCH_SUPABASE)
    _maybe_relax_fk(
        "ticker_watch_user_id_fkey",
        "ticker_watch",
        MIGRATION_WATCH_SUPABASE_FK,
    )


def _apply_dossier_migration_if_needed() -> None:
    if dossier_tables_ready():
        return
    if not MIGRATION_DOSSIER_LOCAL.is_file():
        raise RuntimeError(f"migration not found: {MIGRATION_DOSSIER_LOCAL}")
    _apply_sql_file(MIGRATION_DOSSIER_LOCAL)
    if not _user_id_is_text("ticker_dossier_versions") and _auth_schema_exists():
        if MIGRATION_DOSSIER_SUPABASE.is_file():
            _apply_sql_file(MIGRATION_DOSSIER_SUPABASE)


def _apply_chart_plan_migration_if_needed() -> None:
    if chart_plan_tables_ready():
        return
    if not MIGRATION_CHART_PLAN_LOCAL.is_file():
        raise RuntimeError(f"migration not found: {MIGRATION_CHART_PLAN_LOCAL}")
    _apply_sql_file(MIGRATION_CHART_PLAN_LOCAL)
    if not _user_id_is_text("ticker_chart_plan_versions") and _auth_schema_exists():
        if MIGRATION_CHART_PLAN_SUPABASE.is_file():
            _apply_sql_file(MIGRATION_CHART_PLAN_SUPABASE)


def _cleanup(user_id: str) -> None:
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM ticker_chart_plan_versions
                WHERE user_id = %(user_id)s AND symbol = %(symbol)s
                """,
                {"user_id": user_id, "symbol": TEST_SYMBOL},
            )
            cur.execute(
                """
                DELETE FROM ticker_dossier_versions
                WHERE user_id = %(user_id)s AND symbol = %(symbol)s
                """,
                {"user_id": user_id, "symbol": TEST_SYMBOL},
            )
    remove_watch(user_id=user_id, symbol=TEST_SYMBOL)


def _fake_synthesize_chart_plan_json(*, context, deterministic_stats, gather_notes, symbol):
    del context, gather_notes
    return {
        "timeframes": [{"interval": "D", "rationale": "mock"}],
        "views": [
            {"type": "tradingview", "enabled": True, "interval": "D"},
            {"type": "sentiment_bars", "enabled": True},
            {"type": "signals_timeline", "enabled": True},
        ],
        "chart_data": {
            "sentiment_bars": deterministic_stats.get("sentiment_bars")
            or [{"label": "positive", "count": 2}],
            "signals_timeline": deterministic_stats.get("signals_timeline")
            or [{"date": "2026-07-10", "count": 2}],
        },
        "suggested_view": {
            "interval": "1d",
            "period": "1y",
            "sma_a": {"enabled": True, "length": 20},
            "sma_b": {"enabled": True, "length": 50},
            "donchian": {"enabled": True, "period": 20},
            "fib": True,
            "volume": True,
        },
        "pine_scripts": [],
        "indicator_readings": [
            {
                "name": "SMA 20",
                "stance": "alcista",
                "reading": "Mock SMA reading",
                "tv_study": {
                    "id": "MASimple@tv-basicstudies",
                    "inputs": {"length": 20},
                },
            }
        ],
        "tradingview_studies": [
            {"id": "MASimple@tv-basicstudies", "inputs": {"length": 20}}
        ],
        "assessment": {
            "summary": "Mock chart plan assessment",
            "conflicts": ["mock conflict"],
            "data_gaps": ["mock gap"],
            "bias_check": "mock bias check",
        },
        "symbol": symbol,
    }


def _save_mock_dossier(user_id: str, symbol: str) -> dict:
    return save_dossier_version(
        user_id=user_id,
        symbol=symbol,
        content={
            "blocks": {"lectura_integrada": "Mock dossier for chart plan."},
            "sentiment_stats": {"total_signals": 2},
        },
        citations=[],
    )


def main() -> int:
    print("== F33 verification: Chart Plan + Chart Agent ==\n")
    load_dotenv()
    os.environ["AUTH_ENABLED"] = "false"

    print("0. Migrations (watch + dossier + chart plan)")
    try:
        _apply_watch_migration_if_needed()
        _apply_dossier_migration_if_needed()
        _apply_chart_plan_migration_if_needed()
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return 1
    if not watch_tables_ready():
        print("   FAIL: ticker_watch table missing")
        return 1
    if not dossier_tables_ready():
        print("   FAIL: ticker_dossier_versions table missing")
        return 1
    if not chart_plan_tables_ready():
        print("   FAIL: ticker_chart_plan_versions table missing")
        return 1
    print("   PASS\n")

    operator_id = operator_id_from_user(None)
    client = TestClient(app)
    _cleanup(operator_id)
    add_watch(user_id=operator_id, symbol=TEST_SYMBOL)

    print("1. CHART_AGENT_ENABLED=false => 503")
    os.environ["CHART_AGENT_ENABLED"] = "false"
    _save_mock_dossier(operator_id, TEST_SYMBOL)
    resp_disabled = client.post(f"/chart-plan/{TEST_SYMBOL}/analyze")
    if resp_disabled.status_code != 503:
        print(f"   FAIL: expected 503, got {resp_disabled.status_code}")
        _cleanup(operator_id)
        return 1
    print("   PASS\n")

    print("2. POST analyze sin Dossier => 404")
    os.environ["CHART_AGENT_ENABLED"] = "true"
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM ticker_dossier_versions
                WHERE user_id = %(user_id)s AND symbol = %(symbol)s
                """,
                {"user_id": operator_id, "symbol": TEST_SYMBOL},
            )
    resp_no_dossier = client.post(f"/chart-plan/{TEST_SYMBOL}/analyze")
    if resp_no_dossier.status_code != 404:
        print(f"   FAIL: expected 404, got {resp_no_dossier.status_code}")
        _cleanup(operator_id)
        return 1
    print("   PASS\n")

    print("3. POST analyze (mock synthesis) + SSE steps + persist")
    dossier_row = _save_mock_dossier(operator_id, TEST_SYMBOL)

    with patch(
        "backend.services.chart_plan.synthesize_chart_plan_json",
        _fake_synthesize_chart_plan_json,
    ), patch(
        "backend.services.chart_plan._openai_configured",
        lambda: False,
    ):
        with client.stream("POST", f"/chart-plan/{TEST_SYMBOL}/analyze") as response:
            if response.status_code != 200:
                print(f"   FAIL: status {response.status_code} {response.text}")
                _cleanup(operator_id)
                return 1
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                print(f"   FAIL: content-type {content_type}")
                _cleanup(operator_id)
                return 1
            body = "".join(response.iter_text())

    if "event: step" not in body:
        print("   FAIL: missing event: step in SSE body")
        _cleanup(operator_id)
        return 1
    if "event: chart_plan" not in body and "event: version" not in body:
        print("   FAIL: missing chart_plan/version event in SSE body")
        _cleanup(operator_id)
        return 1

    latest = get_latest(user_id=operator_id, symbol=TEST_SYMBOL)
    if latest is None:
        print("   FAIL: chart plan not persisted")
        _cleanup(operator_id)
        return 1

    content = latest.get("content") or {}
    assessment = content.get("assessment") or {}
    views = content.get("views") or []
    if not assessment.get("conflicts"):
        print("   FAIL: assessment.conflicts missing")
        _cleanup(operator_id)
        return 1
    if not views:
        print("   FAIL: views missing")
        _cleanup(operator_id)
        return 1
    if latest.get("dossier_version_id") != dossier_row["id"]:
        print("   FAIL: dossier_version_id not linked")
        _cleanup(operator_id)
        return 1
    print(f"   views: {len(views)}")
    print("   PASS\n")

    print("4. GET latest + versions history")
    latest_resp = client.get(f"/chart-plan/{TEST_SYMBOL}")
    if latest_resp.status_code != 200:
        print(f"   FAIL: GET latest status {latest_resp.status_code}")
        _cleanup(operator_id)
        return 1

    versions_resp = client.get(f"/chart-plan/{TEST_SYMBOL}/versions")
    if versions_resp.status_code != 200:
        print(f"   FAIL: GET versions status {versions_resp.status_code}")
        _cleanup(operator_id)
        return 1

    versions = versions_resp.json()
    if not versions:
        print("   FAIL: versions list empty")
        _cleanup(operator_id)
        return 1
    if len(versions) > 10:
        print(f"   FAIL: expected ≤10 versions, got {len(versions)}")
        _cleanup(operator_id)
        return 1

    repo_versions = list_versions(user_id=operator_id, symbol=TEST_SYMBOL)
    if not repo_versions:
        print("   FAIL: list_versions empty")
        _cleanup(operator_id)
        return 1

    event_marker = "event: chart_plan" if "event: chart_plan" in body else "event: version"
    payload = json.loads(
        body.split(event_marker, 1)[1].split("data: ", 1)[1].split("\n\n", 1)[0]
    )
    if payload.get("symbol") != TEST_SYMBOL:
        print("   FAIL: SSE version symbol mismatch")
        _cleanup(operator_id)
        return 1

    print(f"   versions: {len(versions)}")
    print("   PASS\n")

    _cleanup(operator_id)

    print("== F33 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
