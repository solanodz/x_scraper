"""Railway xscraper-trader: loop always-on del Paper Bot."""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv

from backend.app.auth import operator_id_from_user
from backend.app.services import bot_repo
from backend.services.paper_bot import run_tick


def _enabled() -> bool:
    raw = os.getenv("BOT_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _tick_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("BOT_TICK_SECONDS", "30")))
    except ValueError:
        return 30.0


def _resolve_operator_id() -> str:
    """Prefer BOT_OPERATOR_ID, then LOCAL_OPERATOR_ID, then sole bot_config row."""
    for key in ("BOT_OPERATOR_ID", "LOCAL_OPERATOR_ID"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            return raw
    try:
        ids = bot_repo.list_config_operator_ids()
        if len(ids) == 1:
            return ids[0]
        if len(ids) > 1:
            print(
                f"[paper_bot] warn: {len(ids)} bot_config rows; "
                "set BOT_OPERATOR_ID to the Supabase user UUID",
                flush=True,
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[paper_bot] warn: could not list bot_config: {exc}", flush=True)
    return operator_id_from_user(None)


def main() -> None:
    load_dotenv()
    operator_id = _resolve_operator_id()
    print(
        f"[paper_bot] start operator={operator_id} "
        f"BOT_ENABLED={_enabled()} tick={_tick_seconds()}s "
        f"venue={os.getenv('BOT_VENUE', 'paper')}",
        flush=True,
    )
    while True:
        if not _enabled():
            print("[paper_bot] BOT_ENABLED=false; sleeping", flush=True)
            time.sleep(_tick_seconds())
            continue
        try:
            summary = run_tick(operator_id)
            print(
                "[paper_bot] tick "
                f"armed={summary.get('armed')} "
                f"opened={len(summary.get('opened') or [])} "
                f"closed={len(summary.get('closed') or [])} "
                f"skipped={len(summary.get('skipped') or [])} "
                f"errors={len(summary.get('errors') or [])}",
                flush=True,
            )
            for err in summary.get("errors") or []:
                print(f"[paper_bot] error: {err}", flush=True)
        except Exception as exc:  # noqa: BLE001 — keep loop alive
            print(f"[paper_bot] tick failed: {exc}", flush=True)
        time.sleep(_tick_seconds())


if __name__ == "__main__":
    main()
