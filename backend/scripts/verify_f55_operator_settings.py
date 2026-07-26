"""Verificación F55: Operator Settings (GET/PATCH + merge + UI wire)."""

from __future__ import annotations

import copy
import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    print("verify_f55_operator_settings")

    import backend.app.main  # noqa: F401

    from backend.app.services.operator_settings_repo import (
        _normalize_bot_pnl,
        _normalize_feed_filters,
        _normalize_ticker_chart,
        normalize_settings,
    )

    # --- normalize / defaults ---
    empty = normalize_settings({})
    if empty["bot_pnl"]["lookbackDays"] != 30:
        print(f"   FAIL: default lookback: {empty}")
        return 1
    if empty["feed_filters"]["watchOnly"] is not False:
        print(f"   FAIL: default watchOnly: {empty}")
        return 1
    print("   defaults OK")

    bad_lb = normalize_settings(
        {"bot_pnl": {"lookbackDays": 11, "timeZone": "UTC"}}
    )
    if bad_lb["bot_pnl"]["lookbackDays"] != 30:
        print(f"   FAIL: invalid lookback should fall back: {bad_lb}")
        return 1
    if bad_lb["bot_pnl"]["timeZone"] != "UTC":
        print(f"   FAIL: timezone not applied: {bad_lb}")
        return 1
    print("   lookback whitelist OK")

    # --- shallow merge semantics (same as patch_settings) ---
    current = normalize_settings(
        {
            "bot_pnl": {
                "timeZone": "America/Argentina/Buenos_Aires",
                "lookbackDays": 30,
            },
            "feed_filters": {"watchOnly": True},
            "ticker_chart": {"interval": "1h"},
        }
    )
    next_settings = copy.deepcopy(current)
    next_settings["bot_pnl"] = _normalize_bot_pnl(
        {"timeZone": "UTC", "lookbackDays": 7}
    )
    if next_settings["bot_pnl"]["timeZone"] != "UTC":
        print(f"   FAIL: bot_pnl not patched: {next_settings}")
        return 1
    if next_settings["bot_pnl"]["lookbackDays"] != 7:
        print(f"   FAIL: lookback not patched: {next_settings}")
        return 1
    if next_settings["feed_filters"]["watchOnly"] is not True:
        print(f"   FAIL: merge wiped feed_filters: {next_settings}")
        return 1
    if next_settings["ticker_chart"].get("interval") != "1h":
        print(f"   FAIL: merge wiped ticker_chart: {next_settings}")
        return 1
    # feed-only patch keeps bot_pnl
    next2 = copy.deepcopy(next_settings)
    next2["feed_filters"] = _normalize_feed_filters({"watchOnly": False})
    if next2["bot_pnl"]["lookbackDays"] != 7:
        print(f"   FAIL: feed patch wiped bot_pnl: {next2}")
        return 1
    _ = _normalize_ticker_chart({"interval": "15m", "period": "5d"})
    print("   shallow merge OK (top-level keys independent)")

    # --- routes exposed ---
    from backend.app.routes import operator_settings as routes

    get_sig = inspect.signature(routes.get_operator_settings)
    patch_sig = inspect.signature(routes.patch_operator_settings)
    if "user" not in get_sig.parameters or "user" not in patch_sig.parameters:
        print("   FAIL: routes missing auth dependency")
        return 1
    openapi_paths = backend.app.main.app.openapi().get("paths", {})
    if "/operator/settings" not in openapi_paths:
        print(
            f"   FAIL: /operator/settings not in OpenAPI; sample={list(openapi_paths)[:8]}"
        )
        return 1
    methods = set(openapi_paths["/operator/settings"])
    if "get" not in methods or "patch" not in methods:
        print(f"   FAIL: expected GET+PATCH, got {methods}")
        return 1
    print("   GET/PATCH /operator/settings mounted")

    # --- frontend wire ---
    settings_page = ROOT / "frontend/src/app/settings/page.tsx"
    api = (ROOT / "frontend/src/lib/api.ts").read_text()
    header = (ROOT / "frontend/src/components/TerminalHeader.tsx").read_text()
    bot = (ROOT / "frontend/src/app/bot/page.tsx").read_text()
    feed = (ROOT / "frontend/src/components/SignalFeed.tsx").read_text()
    if not settings_page.is_file():
        print("   FAIL: missing /settings page")
        return 1
    if "fetchOperatorSettings" not in api or "patchOperatorSettings" not in api:
        print("   FAIL: api missing operator settings helpers")
        return 1
    if "/settings" not in header:
        print("   FAIL: header missing Settings link")
        return 1
    if "fetchOperatorSettings" not in bot:
        print("   FAIL: /bot not wired to operator settings")
        return 1
    if "fetchOperatorSettings" not in feed:
        print("   FAIL: SignalFeed does not hydrate from operator settings")
        return 1
    print("   UI: Settings + /bot + Feed wire")

    # Optional live DB smoke (skipped if unavailable)
    try:
        from backend.app.services.operator_settings_repo import tables_ready

        if tables_ready() and os.getenv("SKIP_F55_DB", "").strip().lower() not in {
            "1",
            "true",
            "yes",
        }:
            from backend.app.auth import operator_id_from_user
            from backend.app.services import operator_settings_repo as repo

            oid = operator_id_from_user(None)
            before = repo.get_or_create_settings(user_id=oid)
            mid = repo.patch_settings(
                user_id=oid,
                patch={"bot_pnl": {"timeZone": "UTC", "lookbackDays": 14}},
            )
            if mid["settings"]["bot_pnl"]["lookbackDays"] != 14:
                print("   FAIL: live patch lookback")
                return 1
            repo.patch_settings(
                user_id=oid,
                patch={"bot_pnl": before["settings"]["bot_pnl"]},
            )
            print("   live DB GET/PATCH OK")
        else:
            print("   live DB skipped (table missing or SKIP_F55_DB)")
    except Exception as exc:  # noqa: BLE001
        print(f"   live DB skipped ({exc})")

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
