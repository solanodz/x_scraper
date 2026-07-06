"""Verificación F23: Thesis por ticker en Ticker Watch."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.auth import operator_id_from_user
from backend.app.main import app
from backend.app.services.ticker_watch_repo import (
    MAX_THESIS_LENGTH,
    add_watch,
    remove_watch,
    tables_ready,
    update_watch,
)
from backend.services.briefing import (
    _BriefingSlice,
    _build_context,
    _format_slice_block,
    _mark_prioridad_alta,
)
from backend.services.market_data import Quote
from backend.services.types import SignalHit

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


def _cleanup(user_id: str, symbols: list[str]) -> None:
    for sym in symbols:
        remove_watch(user_id=user_id, symbol=sym)


def _make_quote(symbol: str) -> Quote:
    return Quote(
        symbol=symbol,
        price=100.0,
        change=1.0,
        change_percent=1.0,
        timestamp=datetime.now(timezone.utc),
        delayed=True,
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


def main() -> int:
    print("== F23 verification: Thesis por ticker ==\n")
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

    operator_id = operator_id_from_user(None)
    client = TestClient(app)
    _cleanup(operator_id, ["NVDA"])
    client.delete("/watch/NVDA")

    print("1. PATCH /watch/NVDA persists thesis")
    resp = client.post("/watch", json={"symbol": "NVDA"})
    if resp.status_code != 201:
        print(f"   FAIL: POST status {resp.status_code} {resp.text}")
        return 1
    thesis = "Apuesta a demanda AI en datacenters; riesgo export controls."
    resp = client.patch("/watch/NVDA", json={"note": thesis})
    if resp.status_code != 200:
        print(f"   FAIL: status {resp.status_code} {resp.text}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    if resp.json().get("note") != thesis:
        print(f"   FAIL: note mismatch {resp.json().get('note')!r}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    print(f"   note: {thesis[:48]}…")
    print("   PASS\n")

    print("2. GET /watch returns note")
    resp = client.get("/watch")
    if resp.status_code != 200:
        print(f"   FAIL: status {resp.status_code}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    nvda = next((row for row in resp.json() if row["symbol"] == "NVDA"), None)
    if nvda is None or nvda.get("note") != thesis:
        print(f"   FAIL: GET note {nvda}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    print("   GET note matches PATCH")
    print("   PASS\n")

    print("3. PATCH empty note clears thesis")
    resp = client.patch("/watch/NVDA", json={"note": "   "})
    if resp.status_code != 200 or resp.json().get("note") is not None:
        print(f"   FAIL: expected null note, got {resp.json()}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    print("   PASS\n")

    print("4. PATCH note too long rejected")
    too_long = "x" * (MAX_THESIS_LENGTH + 1)
    resp = client.patch("/watch/NVDA", json={"note": too_long})
    if resp.status_code not in {400, 422}:
        print(f"   FAIL: expected 400/422, got {resp.status_code}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    print("   PASS\n")

    print("5. Briefing context includes Thesis when set")
    block = _format_slice_block(
        _BriefingSlice(
            "NVDA",
            hits=[_make_hit("nvda-1", "NVDA headline")],
            quote=_make_quote("NVDA"),
            thesis=thesis,
            prioridad_alta=True,
        ),
        hours=24,
    )
    if f"Thesis: {thesis}" not in block:
        print("   FAIL: Thesis line missing from slice block")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1

    slices = [
        _BriefingSlice(
            "NVDA",
            hits=[_make_hit("nvda-1", "NVDA headline")],
            quote=_make_quote("NVDA"),
            thesis=thesis,
        ),
        _BriefingSlice(
            "MSFT",
            hits=[],
            quote=_make_quote("MSFT"),
            thesis=None,
        ),
    ]
    _mark_prioridad_alta(slices)
    context = _build_context(slices, hours=24)
    if f"Thesis: {thesis}" not in context:
        print("   FAIL: Thesis line missing from _build_context")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    if context.count("Thesis:") != 1:
        print(f"   FAIL: expected 1 Thesis line, got {context.count('Thesis:')}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    print("   Thesis line present for NVDA only")
    print("   PASS\n")

    print("6. Repo update_watch strips and validates")
    add_watch(user_id=operator_id, symbol="NVDA")
    try:
        update_watch(user_id=operator_id, symbol="NVDA", note="  trimmed  ")
    except Exception as exc:
        print(f"   FAIL: update_watch raised {exc}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    row = update_watch(user_id=operator_id, symbol="NVDA", note=None)
    if row.get("note") is not None:
        print(f"   FAIL: expected cleared note, got {row.get('note')!r}")
        _cleanup(operator_id, ["NVDA"])
        client.delete("/watch/NVDA")
        return 1
    print("   PASS\n")

    _cleanup(operator_id, ["NVDA"])
    client.delete("/watch/NVDA")

    print("== F23 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
