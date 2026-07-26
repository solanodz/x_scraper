"""F54 — Paper Bot daily PnL (tz/range) + trade history on /bot."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
BOT_PAGE = ROOT / "frontend" / "src" / "app" / "bot" / "page.tsx"
PNL_LIB = ROOT / "frontend" / "src" / "lib" / "botDailyPnl.ts"
BOT_ROUTES = ROOT / "backend" / "app" / "routes" / "bot.py"


def day_key(iso: str, tz_name: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d")


def build_daily(
    closed: list[dict],
    *,
    time_zone: str,
    lookback_days: int,
    now_iso: str,
) -> dict[str, float]:
    end = day_key(now_iso, time_zone)
    y, m, d = (int(x) for x in end.split("-"))
    # Civil walk matching frontend enumerateDays.
    from datetime import timedelta

    end_dt = datetime(y, m, d, 12, 0, 0)
    days: list[str] = []
    for i in range(lookback_days):
        days.append((end_dt - timedelta(days=i)).strftime("%Y-%m-%d"))
    days.reverse()
    by_day = {k: 0.0 for k in days}
    for row in closed:
        key = day_key(row["closed_at"], time_zone)
        if key in by_day:
            by_day[key] += float(row["realized_pnl"])
    return by_day


def main() -> int:
    assert BOT_PAGE.is_file(), f"missing {BOT_PAGE}"
    assert PNL_LIB.is_file(), f"missing {PNL_LIB}"
    page = BOT_PAGE.read_text(encoding="utf-8")
    lib = PNL_LIB.read_text(encoding="utf-8")
    routes = BOT_ROUTES.read_text(encoding="utf-8")

    for needle in (
        "Trade history",
        "Daily PnL",
        "buildDailyPnl",
        "pnlPrefs",
        "BOT_PNL_TIMEZONES",
    ):
        assert needle in page or needle in lib, f"missing UI/lib marker: {needle}"

    assert "Trade history" in page
    assert "Daily PnL" in page
    assert "loadBotPnlPrefs" in page
    assert 'limit: int = Query(default=100' in routes or "limit: int = Query(default=100" in routes
    assert "limit: int = Query(default=50" in routes

    # Same instant can fall on different calendar days by TZ.
    iso = "2026-07-25T03:30:00+00:00"
    assert day_key(iso, "UTC") == "2026-07-25"
    assert day_key(iso, "America/Argentina/Buenos_Aires") == "2026-07-25"
    assert day_key(iso, "America/Los_Angeles") == "2026-07-24"

    closed = [
        # Both land on AR calendar 2026-07-24 (UTC-3).
        {"closed_at": "2026-07-24T22:00:00+00:00", "realized_pnl": 10.0},
        {"closed_at": "2026-07-25T01:00:00+00:00", "realized_pnl": -3.0},
        # Outside a 3-day window ending 2026-07-25.
        {"closed_at": "2026-07-20T12:00:00+00:00", "realized_pnl": 99.0},
    ]
    by = build_daily(
        closed,
        time_zone="America/Argentina/Buenos_Aires",
        lookback_days=3,
        now_iso="2026-07-25T18:00:00+00:00",
    )
    assert set(by) == {"2026-07-23", "2026-07-24", "2026-07-25"}, by
    assert abs(by["2026-07-24"] - 7.0) < 1e-9, by
    assert abs(by["2026-07-25"]) < 1e-9, by
    assert "2026-07-20" not in by

    print("verify_f54_bot_pnl_history: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"verify_f54_bot_pnl_history: FAIL — {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
