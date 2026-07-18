"""Verificación F30: Dossier análisis integral por Ticker."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.auth import operator_id_from_user
from backend.app.main import app
from backend.app.services.dossier_repo import (
    get_latest,
    list_versions,
    tables_ready as dossier_tables_ready,
)
from backend.app.services.ticker_watch_repo import (
    add_watch,
    remove_watch,
    tables_ready as watch_tables_ready,
)
from backend.services.briefing import (
    _BriefingSlice,
    _refresh_dossiers_for_slices,
)
from backend.services.dossier import (
    _DOSSIER_BLOCK_SPECS,
    should_refresh_dossier,
)

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


def _cleanup(user_id: str) -> None:
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM ticker_dossier_versions
                WHERE user_id = %(user_id)s AND symbol = %(symbol)s
                """,
                {"user_id": user_id, "symbol": TEST_SYMBOL},
            )
    remove_watch(user_id=user_id, symbol=TEST_SYMBOL)


def _fake_generate_dossier(*, user_id: str, symbol: str, thesis=None):
    del user_id, thesis
    blocks = {
        key: f"Bloque de prueba {title} para {symbol}."
        for key, title in _DOSSIER_BLOCK_SPECS
    }
    content = {
        "symbol": symbol,
        "blocks": blocks,
        "sentiment_stats": {"total_signals": 2, "positive": 1},
    }
    return content, []


def main() -> int:
    print("== F30 verification: Dossier integral ==\n")
    load_dotenv()
    os.environ["AUTH_ENABLED"] = "false"

    print("0. Migrations (ticker_watch + ticker_dossier_versions)")
    try:
        _apply_watch_migration_if_needed()
        _apply_dossier_migration_if_needed()
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return 1
    if not watch_tables_ready():
        print("   FAIL: ticker_watch table missing")
        return 1
    if not dossier_tables_ready():
        print("   FAIL: ticker_dossier_versions table missing")
        return 1
    print("   PASS\n")

    operator_id = operator_id_from_user(None)
    client = TestClient(app)
    _cleanup(operator_id)

    print("1. should_refresh_dossier policy")
    if not should_refresh_dossier(prioridad_alta=True, has_recent_signals=False):
        print("   FAIL: prioridad_alta should refresh")
        return 1
    if not should_refresh_dossier(prioridad_alta=False, has_recent_signals=True):
        print("   FAIL: recent signals should refresh")
        return 1
    if should_refresh_dossier(prioridad_alta=False, has_recent_signals=False):
        print("   FAIL: idle ticker should not refresh")
        return 1
    print("   prioridad_alta / novedad / idle OK")
    print("   PASS\n")

    print("2. POST /dossier/TEST/refresh (mock generate_dossier)")
    add_watch(user_id=operator_id, symbol=TEST_SYMBOL)

    with patch(
        "backend.app.routes.dossier.generate_dossier",
        _fake_generate_dossier,
    ):
        resp = client.post(f"/dossier/{TEST_SYMBOL}/refresh")

    if resp.status_code != 200:
        print(f"   FAIL: status {resp.status_code} {resp.text}")
        _cleanup(operator_id)
        return 1

    body = resp.json()
    version = body.get("version") or body
    blocks = version.get("content", {}).get("blocks", {})
    if len(blocks) < len(_DOSSIER_BLOCK_SPECS):
        print(f"   FAIL: expected {len(_DOSSIER_BLOCK_SPECS)} blocks, got {len(blocks)}")
        _cleanup(operator_id)
        return 1
    print(f"   blocks: {len(blocks)}")
    print("   PASS\n")

    print("3. GET /dossier/TEST + versions history")
    latest_resp = client.get(f"/dossier/{TEST_SYMBOL}")
    if latest_resp.status_code != 200:
        print(f"   FAIL: GET latest status {latest_resp.status_code}")
        _cleanup(operator_id)
        return 1

    versions_resp = client.get(f"/dossier/{TEST_SYMBOL}/versions")
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

    repo_latest = get_latest(user_id=operator_id, symbol=TEST_SYMBOL)
    if repo_latest is None:
        print("   FAIL: get_latest returned None")
        _cleanup(operator_id)
        return 1
    print(f"   versions: {len(versions)}")
    print("   PASS\n")

    print("4. Briefing refresca Dossier prioridad_alta (mock save_version)")
    save_calls = {"count": 0}

    def _counting_save(*, user_id, symbol, content, citations):
        del user_id, content, citations
        save_calls["count"] += 1
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "symbol": symbol,
            "content": {"blocks": {}},
            "citations": [],
            "created_at": "2026-07-10T12:00:00+00:00",
        }

    slices = [
        _BriefingSlice(
            TEST_SYMBOL,
            hits=[object()],
            quote=None,
            prioridad_alta=True,
        ),
        _BriefingSlice(
            "IDLE",
            hits=[],
            quote=None,
            prioridad_alta=False,
        ),
    ]

    with patch(
        "backend.services.briefing.generate_dossier",
        _fake_generate_dossier,
    ), patch(
        "backend.services.briefing.save_dossier_version",
        side_effect=_counting_save,
    ):
        steps = list(_refresh_dossiers_for_slices(operator_id, slices))

    if save_calls["count"] != 1:
        print(f"   FAIL: expected 1 save_version call, got {save_calls['count']}")
        _cleanup(operator_id)
        return 1
    if not any("Actualizando Dossier" in step.label for step in steps):
        print("   FAIL: missing dossier refresh step event")
        _cleanup(operator_id)
        return 1
    print(f"   save_version calls: {save_calls['count']}")
    print("   PASS\n")

    _cleanup(operator_id)

    print("== F30 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
