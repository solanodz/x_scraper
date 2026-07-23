#!/usr/bin/env python3
"""CLI: envía (o dry-run) el Morning Briefing Email.

Usage:
  python -m backend.scripts.send_morning_briefing [--dry-run] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Morning Briefing Email (F46): Briefing + FX USD/ARS vía Resend",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Genera asunto/cuerpo sin llamar Resend ni escribir log",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reenvía aunque ya exista log del día",
    )
    args = parser.parse_args(argv)

    from backend.services.briefing_email import run_morning_briefing

    try:
        result = run_morning_briefing(dry_run=args.dry_run, force=args.force)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    # Resumen legible; preview completo en dry-run
    summary = {
        k: result.get(k)
        for k in (
            "skipped",
            "reason",
            "operator_id",
            "sent_on",
            "dry_run",
            "force",
            "subject",
            "resend_id",
            "session_id",
            "to",
        )
        if k in result or result.get("skipped")
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))

    if args.dry_run and not result.get("skipped"):
        print("\n--- text ---\n")
        print(result.get("text") or "")
        print("\n--- html (truncated) ---\n")
        html = result.get("html") or ""
        print(html[:2000] + ("…" if len(html) > 2000 else ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
