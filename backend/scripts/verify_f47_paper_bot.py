"""Verificación F47: Paper Bot (Donchian + PaperVenue + Hyperliquid stub)."""

from __future__ import annotations

import os
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import patch

from dotenv import load_dotenv


def _synthetic_breakout_up(*, period: int = 20) -> list[dict]:
    """Serie donde la última vela rompe upper Donchian (prior window)."""
    candles: list[dict] = []
    for i in range(period):
        candles.append(
            {
                "date": f"2026-01-{(i // 24) + 1:02d}T{i % 24:02d}:00:00",
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
            }
        )
    candles.append(
        {
            "date": "2026-01-02T00:00:00",
            "high": 110.0,
            "low": 100.0,
            "close": 108.0,
        }
    )
    return candles


def _synthetic_breakout_down(*, period: int = 20) -> list[dict]:
    candles: list[dict] = []
    for i in range(period):
        candles.append(
            {
                "date": f"2026-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00",
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
            }
        )
    candles.append(
        {
            "date": "2026-02-02T00:00:00",
            "high": 100.0,
            "low": 90.0,
            "close": 92.0,
        }
    )
    return candles


def test_donchian_and_strategy() -> None:
    from backend.services.bot_strategy import (
        StrategyContext,
        collect_signals,
        evaluate_donchian_breakout,
        filter_trade_signal,
    )
    from backend.services.donchian import donchian_at

    period = 20
    up = _synthetic_breakout_up(period=period)
    upper, lower = donchian_at(up, len(up) - 1, period, prior=True)
    assert upper == 101.0 and lower == 99.0, (upper, lower)

    sig = evaluate_donchian_breakout("BTC", up, period=period)
    assert sig is not None and sig.side == "long", sig
    assert sig.bar_ts == "2026-01-02T00:00:00"

    down = _synthetic_breakout_down(period=period)
    sig_s = evaluate_donchian_breakout("ETH", down, period=period)
    assert sig_s is not None and sig_s.side == "short", sig_s

    ctx = StrategyContext(
        armed=True,
        max_positions=2,
        open_count=0,
        open_symbols=set(),
        cooldown_seconds=0,
        last_closed_at={},
        seen_keys=set(),
    )
    accepted = collect_signals(
        {"BTC": up, "ETH": down},
        period=period,
        ctx=ctx,
    )
    assert len(accepted) == 2
    sides = {s.symbol: s.side for s in accepted}
    assert sides["BTC"] == "long" and sides["ETH"] == "short"

    ok, reason = filter_trade_signal(
        sig,
        StrategyContext(
            armed=False,
            max_positions=2,
            open_count=0,
            open_symbols=set(),
            cooldown_seconds=0,
            last_closed_at={},
            seen_keys=set(),
        ),
    )
    assert not ok and reason == "not_armed"

    ok, reason = filter_trade_signal(
        sig,
        StrategyContext(
            armed=True,
            max_positions=2,
            open_count=1,
            open_symbols={"BTC"},
            cooldown_seconds=0,
            last_closed_at={},
            seen_keys=set(),
        ),
    )
    assert not ok and reason == "symbol_already_open"

    ok, reason = filter_trade_signal(
        sig,
        StrategyContext(
            armed=True,
            max_positions=2,
            open_count=0,
            open_symbols=set(),
            cooldown_seconds=0,
            last_closed_at={},
            seen_keys={("BTC", "long", sig.bar_ts)},
        ),
    )
    assert not ok and reason == "duplicate_bar"

    print("  donchian + strategy OK")


def test_hyperliquid_stub() -> None:
    from backend.services.bot_venue import HyperliquidVenue, VenueNotEnabled

    venue = HyperliquidVenue()
    try:
        venue.open(
            operator_id="00000000-0000-0000-0000-000000000001",
            symbol="BTC",
            side="long",
            size_usd=1000,
            leverage=1,
            tp_pct=2,
            sl_pct=1,
        )
        raise AssertionError("HyperliquidVenue.open should raise")
    except VenueNotEnabled:
        pass
    print("  HyperliquidVenue.open raises VenueNotEnabled OK")


class _MemStore:
    """In-memory bot_repo stand-in for offline PaperVenue tests."""

    def __init__(self, operator_id: str) -> None:
        self.operator_id = operator_id
        self.config: dict[str, Any] = {
            "operator_id": operator_id,
            "armed": True,
            "symbols": ["BTC"],
            "max_positions": 2,
            "donchian_period": 20,
            "donchian_interval": "30m",
            "size_usd": 1000.0,
            "leverage": 1.0,
            "tp_pct": 2.0,
            "sl_pct": 1.0,
            "venue": "paper",
            "cooldown_seconds": 0,
            "updated_at": datetime.now(timezone.utc),
        }
        self.positions: dict[str, dict[str, Any]] = {}
        self.fills: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def tables_ready(self) -> bool:
        return True

    def get_or_create_config(self, *, operator_id: str) -> dict[str, Any]:
        return deepcopy(self.config)

    def update_config(self, *, operator_id: str, **fields: Any) -> dict[str, Any]:
        for k, v in fields.items():
            if v is not None and k in self.config:
                self.config[k] = v
        return deepcopy(self.config)

    def list_positions(
        self,
        *,
        operator_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        rows = list(self.positions.values())
        if status:
            rows = [r for r in rows if r["status"] == status]
        return [deepcopy(r) for r in rows[:limit]]

    def get_position(
        self, *, operator_id: str, position_id: str
    ) -> dict[str, Any] | None:
        row = self.positions.get(position_id)
        return deepcopy(row) if row else None

    def insert_position(self, **kwargs: Any) -> dict[str, Any]:
        pos_id = str(uuid.uuid4())
        row = {
            "id": pos_id,
            "operator_id": kwargs["operator_id"],
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "size_usd": float(kwargs["size_usd"]),
            "qty": float(kwargs["qty"]),
            "leverage": float(kwargs["leverage"]),
            "entry_price": float(kwargs["entry_price"]),
            "tp_price": float(kwargs["tp_price"]),
            "sl_price": float(kwargs["sl_price"]),
            "status": "open",
            "opened_at": datetime.now(timezone.utc),
            "closed_at": None,
            "close_reason": None,
            "realized_pnl": None,
            "venue": kwargs.get("venue") or "paper",
            "external_id": kwargs.get("external_id"),
            "mark_price": kwargs.get("mark_price"),
        }
        self.positions[pos_id] = row
        return deepcopy(row)

    def update_mark_price(
        self,
        *,
        operator_id: str,
        position_id: str,
        mark_price: float,
    ) -> dict[str, Any] | None:
        row = self.positions.get(position_id)
        if row is None or row.get("status") != "open":
            return None
        if row.get("operator_id") != operator_id:
            return None
        row["mark_price"] = float(mark_price)
        return deepcopy(row)

    def close_position_row(
        self,
        *,
        operator_id: str,
        position_id: str,
        close_reason: str,
        realized_pnl: float,
        mark_price: float | None = None,
    ) -> dict[str, Any]:
        row = self.positions[position_id]
        row["status"] = "closed"
        row["closed_at"] = datetime.now(timezone.utc)
        row["close_reason"] = close_reason
        row["realized_pnl"] = realized_pnl
        if mark_price is not None:
            row["mark_price"] = mark_price
        return deepcopy(row)

    def insert_fill(self, **kwargs: Any) -> dict[str, Any]:
        row = {
            "id": str(uuid.uuid4()),
            "position_id": kwargs["position_id"],
            "operator_id": kwargs["operator_id"],
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "price": float(kwargs["price"]),
            "qty": float(kwargs["qty"]),
            "venue": kwargs.get("venue") or "paper",
            "created_at": datetime.now(timezone.utc),
            "raw": kwargs.get("raw") or {},
        }
        self.fills.append(row)
        return deepcopy(row)

    def list_fills(self, *, operator_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [deepcopy(r) for r in self.fills[-limit:]]

    def insert_event(self, **kwargs: Any) -> dict[str, Any]:
        row = {
            "id": str(uuid.uuid4()),
            "operator_id": kwargs["operator_id"],
            "kind": kwargs["kind"],
            "symbol": kwargs.get("symbol"),
            "payload": kwargs.get("payload") or {},
            "created_at": datetime.now(timezone.utc),
        }
        self.events.append(row)
        return deepcopy(row)

    def list_events(self, *, operator_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return [deepcopy(r) for r in reversed(self.events[-limit:])]

    def count_open_positions(self, *, operator_id: str) -> int:
        return sum(1 for r in self.positions.values() if r["status"] == "open")

    def get_open_position_for_symbol(
        self, *, operator_id: str, symbol: str
    ) -> dict[str, Any] | None:
        for r in self.positions.values():
            if r["symbol"] == symbol and r["status"] == "open":
                return deepcopy(r)
        return None

    def last_closed_at_for_symbol(
        self, *, operator_id: str, symbol: str
    ) -> datetime | None:
        closed = [
            r["closed_at"]
            for r in self.positions.values()
            if r["symbol"] == symbol and r["status"] == "closed" and r["closed_at"]
        ]
        return max(closed) if closed else None

    def signal_already_processed(
        self,
        *,
        operator_id: str,
        symbol: str,
        side: str,
        bar_ts: str,
    ) -> bool:
        for ev in self.events:
            if (
                ev.get("symbol") == symbol
                and ev.get("kind") in {"open", "trade_signal", "skip_duplicate"}
                and (ev.get("payload") or {}).get("side") == side
                and (ev.get("payload") or {}).get("bar_ts") == bar_ts
            ):
                return True
        return False


def _patch_bot_repo(store: _MemStore):
    import backend.app.services.bot_repo as bot_repo
    import backend.services.bot_venue as bot_venue
    import backend.services.paper_bot as paper_bot

    names = [
        "tables_ready",
        "get_or_create_config",
        "update_config",
        "list_positions",
        "get_position",
        "insert_position",
        "update_mark_price",
        "close_position_row",
        "insert_fill",
        "list_fills",
        "insert_event",
        "list_events",
        "count_open_positions",
        "get_open_position_for_symbol",
        "last_closed_at_for_symbol",
        "signal_already_processed",
    ]
    patches = []
    for name in names:
        fn = getattr(store, name)
        patches.append(patch.object(bot_repo, name, fn))
        patches.append(patch.object(bot_venue.bot_repo, name, fn))
        patches.append(patch.object(paper_bot.bot_repo, name, fn))
    return patches


def test_paper_venue_open_tp() -> None:
    from backend.services.bot_venue import PaperVenue
    from backend.services.paper_bot import run_tick

    operator_id = f"00000000-0000-4000-8000-{uuid.uuid4().hex[:12]}"
    store = _MemStore(operator_id)
    marks = {"BTC": 100.0}

    patches = _patch_bot_repo(store)
    for p in patches:
        p.start()
    try:
        venue = PaperVenue(mark_fn=lambda s: Decimal(str(marks[s])))
        opened = venue.open(
            operator_id=operator_id,
            symbol="BTC",
            side="long",
            size_usd=1000,
            leverage=1,
            tp_pct=2,
            sl_pct=1,
            meta={"bar_ts": "test-bar"},
        )
        pos = opened["position"]
        assert pos["status"] == "open"
        assert abs(pos["tp_price"] - 102.0) < 1e-6
        assert abs(pos["sl_price"] - 99.0) < 1e-6
        assert opened["fill"]["price"] == 100.0

        # Mark-to-market without hitting TP/SL should refresh mark_price.
        marks["BTC"] = 100.5
        none_close = venue.check_tp_sl(operator_id=operator_id, position=pos)
        assert none_close is None
        assert abs(float(store.positions[pos["id"]]["mark_price"]) - 100.5) < 1e-6

        marks["BTC"] = 103.0
        closed = venue.check_tp_sl(operator_id=operator_id, position=pos)
        assert closed is not None
        assert closed["position"]["status"] == "closed"
        assert closed["position"]["close_reason"] == "tp"
        assert closed["position"]["realized_pnl"] > 0

        candles = _synthetic_breakout_up(period=20)
        marks["BTC"] = 108.0
        summary = run_tick(
            operator_id,
            candles_by_symbol={"BTC": candles},
            mark_prices=marks,
        )
        assert summary.get("armed") is True
        assert len(summary.get("opened") or []) >= 1, summary

        store.config["armed"] = False
        marks["BTC"] = 120.0
        summary2 = run_tick(
            operator_id,
            candles_by_symbol={"BTC": candles},
            mark_prices=marks,
        )
        assert summary2.get("armed") is False
        assert len(summary2.get("opened") or []) == 0
        assert len(summary2.get("closed") or []) >= 1, summary2
    finally:
        for p in patches:
            p.stop()

    print("  PaperVenue open + TP close (injected marks, no network) OK")


def test_api_venue_reject_hyperliquid() -> None:
    """API rejects venue=hyperliquid without needing Store (route-level 400)."""
    os.environ["AUTH_ENABLED"] = "false"
    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.services import bot_repo

    fake_cfg = {
        "operator_id": "00000000-0000-0000-0000-000000000001",
        "armed": False,
        "symbols": ["BTC", "ETH"],
        "max_positions": 2,
        "donchian_period": 20,
        "donchian_interval": "30m",
        "size_usd": 1000.0,
        "leverage": 1.0,
        "tp_pct": 2.0,
        "sl_pct": 1.0,
        "venue": "paper",
        "cooldown_seconds": 3600,
        "updated_at": datetime.now(timezone.utc),
    }

    with (
        patch.object(bot_repo, "tables_ready", return_value=True),
        patch.object(bot_repo, "get_or_create_config", return_value=fake_cfg),
        patch.object(bot_repo, "update_config", side_effect=bot_repo.BotRepoError("venue must be 'paper' in MVP")),
        patch.object(bot_repo, "list_positions", return_value=[]),
        patch.object(bot_repo, "list_fills", return_value=[]),
        patch.object(bot_repo, "list_events", return_value=[]),
    ):
        client = TestClient(app)
        r = client.get("/bot/config")
        assert r.status_code == 200, r.text
        assert r.json()["venue"] == "paper"
        r = client.patch("/bot/config", json={"venue": "hyperliquid"})
        assert r.status_code == 400, r.text
        r = client.get("/bot/positions")
        assert r.status_code == 200, r.text
        r = client.get("/bot/fills")
        assert r.status_code == 200
        r = client.get("/bot/events")
        assert r.status_code == 200
    print("  API /bot config+venue reject OK")


def main() -> int:
    load_dotenv()
    print("verify_f47_paper_bot")
    test_donchian_and_strategy()
    test_hyperliquid_stub()
    test_paper_venue_open_tp()
    test_api_venue_reject_hyperliquid()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
