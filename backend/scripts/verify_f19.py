"""Verificación F19: Ticker Watch (lista personal del Operator)."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.auth import operator_id_from_user
from backend.app.main import app
from backend.app.services.ticker_watch_repo import (
    add_watch,
    list_watch,
    remove_watch,
    tables_ready,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_LOCAL = ROOT / "infra" / "store" / "init" / "006_ticker_watch.sql"
MIGRATION_SUPABASE = ROOT / "infra" / "supabase" / "migrations" / "007_ticker_watch.sql"
MIGRATION_SUPABASE_FK = (
    ROOT / "infra" / "supabase" / "migrations" / "008_ticker_watch_drop_user_fk.sql"
)


def _apply_sql_file(path: Path) -> None:
    from backend.app.db import connect

    sql = path.read_text()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def _user_id_is_text() -> bool:
    from backend.app.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'ticker_watch'
                  AND column_name = 'user_id'
                """
            )
            row = cur.fetchone()
    return bool(row and row[0] == "text")


def _apply_migration_if_needed() -> None:
    if tables_ready():
        if _user_id_is_text() and MIGRATION_SUPABASE.is_file():
            _apply_sql_file(MIGRATION_SUPABASE)
        _maybe_relax_supabase_fk()
        return
    if not MIGRATION_LOCAL.is_file():
        raise RuntimeError(f"migration not found: {MIGRATION_LOCAL}")
    _apply_sql_file(MIGRATION_LOCAL)
    if _user_id_is_text() and MIGRATION_SUPABASE.is_file():
        _apply_sql_file(MIGRATION_SUPABASE)
    _maybe_relax_supabase_fk()


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
                WHERE constraint_name = 'ticker_watch_user_id_fkey'
                  AND table_name = 'ticker_watch'
                """
            )
            if cur.fetchone() is None:
                return
    _apply_sql_file(MIGRATION_SUPABASE_FK)


def _cleanup(user_id: str, symbols: list[str]) -> None:
    for sym in symbols:
        remove_watch(user_id=user_id, symbol=sym)


def main() -> int:
    print("== F19 verification: Ticker Watch ==\n")
    load_dotenv()
    os.environ["AUTH_ENABLED"] = "false"

    print("0. ticker_watch table")
    try:
        _apply_migration_if_needed()
    except Exception as exc:
        print(f"   FAIL — {exc}")
        return 1
    if not tables_ready():
        print("   FAIL: ticker_watch table missing")
        return 1
    print("   PASS\n")

    operator_a = str(uuid.uuid4())
    operator_b = str(uuid.uuid4())
    client = TestClient(app)

    print("1. POST /watch with Intel → INTC")
    _cleanup(operator_a, ["INTC", "NVDA"])
    resp = client.post("/watch", json={"symbol": "Intel"})
    if resp.status_code != 201:
        print(f"   FAIL: status {resp.status_code} {resp.text}")
        return 1
    entry = resp.json()
    if entry.get("symbol") != "INTC":
        print(f"   FAIL: expected INTC, got {entry.get('symbol')}")
        return 1
    print(f"   symbol: {entry['symbol']}")
    print("   PASS\n")

    print("2. GET /watch lists followed tickers")
    resp = client.get("/watch")
    if resp.status_code != 200:
        print(f"   FAIL: status {resp.status_code}")
        return 1
    symbols = [row["symbol"] for row in resp.json()]
    if "INTC" not in symbols:
        print(f"   FAIL: INTC not in {symbols}")
        return 1
    print(f"   symbols: {symbols}")
    print("   PASS\n")

    print("3. DELETE /watch/INTC")
    resp = client.delete("/watch/INTC")
    if resp.status_code != 204:
        print(f"   FAIL: status {resp.status_code}")
        return 1
    resp = client.get("/watch")
    if any(row["symbol"] == "INTC" for row in resp.json()):
        print("   FAIL: INTC still present")
        return 1
    print("   PASS\n")

    print("4. Operator isolation")
    add_watch(user_id=operator_a, symbol="NVDA")
    add_watch(user_id=operator_b, symbol="AAPL")
    list_a = {row["symbol"] for row in list_watch(user_id=operator_a)}
    list_b = {row["symbol"] for row in list_watch(user_id=operator_b)}
    if list_a != {"NVDA"} or list_b != {"AAPL"}:
        print(f"   FAIL: A={list_a} B={list_b}")
        _cleanup(operator_a, ["NVDA"])
        _cleanup(operator_b, ["AAPL"])
        return 1
    _cleanup(operator_a, ["NVDA"])
    _cleanup(operator_b, ["AAPL"])
    print("   PASS\n")

    print("5. Duplicate add returns existing")
    add_watch(user_id=operator_a, symbol="MSFT")
    row1 = add_watch(user_id=operator_a, symbol="Microsoft")
    if row1["symbol"] != "MSFT":
        print(f"   FAIL: duplicate resolve got {row1['symbol']}")
        _cleanup(operator_a, ["MSFT"])
        return 1
    count = len(list_watch(user_id=operator_a))
    if count != 1:
        print(f"   FAIL: expected 1 row, got {count}")
        _cleanup(operator_a, ["MSFT"])
        return 1
    _cleanup(operator_a, ["MSFT"])
    print("   PASS\n")

    default_op = operator_id_from_user(None)
    print(f"6. Default operator id (API): {default_op[:8]}…")
    print("   PASS\n")

    print("== F19 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
