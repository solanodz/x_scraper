#!/usr/bin/env python3
"""
Worker: ejecuta Ingestion periódicamente (cron) o bajo demanda (Refresh).

Ingesta multi-fuente: News Sources primero, X como complemento (cron / Refresh).
Al final de cada ciclo: backfill de embeddings (best-effort) y Retention Window.

Uso:
  python -m scraper.worker --once
  python -m scraper.worker --once --limit-per-account 2 --accounts-only --max-accounts 2
  python -m scraper.worker --once --av-only
  python -m scraper.worker --once --skip-x
  python -m scraper.worker --once --prune-only
  python -m scraper.worker --interval 1800
  python -m scraper.worker --interval
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from scraper.ingest import add_ingest_args, run_ingestion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Worker de Ingestion multi-fuente: cron (--interval) o Refresh (--once)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Ejecutar un ciclo de Ingestion y salir (Refresh manual)",
    )
    mode.add_argument(
        "--interval",
        type=int,
        nargs="?",
        const=1800,
        metavar="SECONDS",
        help="Repetir Ingestion cada N segundos (default: 1800 = 30 min)",
    )
    add_ingest_args(parser)
    args = parser.parse_args()
    if not args.once and args.interval is None:
        args.once = True
    return args


async def main() -> None:
    args = parse_args()

    if args.once:
        await run_ingestion(args)
        return

    interval = args.interval if args.interval is not None else 1800
    print(f"Worker iniciado: Ingestion cada {interval}s (Ctrl+C para detener)\n")
    while True:
        await run_ingestion(args)
        print(f"\nPróxima Ingestion en {interval}s...\n")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nWorker detenido.", file=sys.stderr)
        sys.exit(0)
