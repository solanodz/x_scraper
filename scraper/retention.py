#!/usr/bin/env python3
"""
Retención del Corpus: poda por antigüedad y purge one-shot por source_type.

Uso:
  python -m scraper.retention
  python -m scraper.retention --prune-only
  python -m scraper.retention --purge-x
  python -m scraper.retention --dry-run
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from scraper.store import connect


def get_retention_days() -> int:
    """Lee RETENTION_DAYS del entorno. Default 30; 0 = deshabilitado."""
    load_dotenv()
    raw = os.getenv("RETENTION_DAYS", "30").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 30


def prune_expired_signals(*, dry_run: bool = False) -> int:
    """Elimina Signals más antiguos que RETENTION_DAYS. Devuelve filas afectadas."""
    days = get_retention_days()
    if days == 0:
        return 0

    sql = (
        "DELETE FROM signals WHERE published_at < now() - (%s * interval '1 day')"
        if not dry_run
        else "SELECT COUNT(*) FROM signals WHERE published_at < now() - (%s * interval '1 day')"
    )

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (days,))
            if dry_run:
                row = cur.fetchone()
                return int(row[0]) if row else 0
            return cur.rowcount


def purge_signals_by_source(source_type: str, *, dry_run: bool = False) -> int:
    """Elimina todos los Signals de un source_type (purge one-shot)."""
    sql = (
        "DELETE FROM signals WHERE source_type = %s"
        if not dry_run
        else "SELECT COUNT(*) FROM signals WHERE source_type = %s"
    )

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (source_type,))
            if dry_run:
                row = cur.fetchone()
                return int(row[0]) if row else 0
            return cur.rowcount


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retención del Corpus: poda por antigüedad y purge por source_type"
    )
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="Solo poda por antigüedad (ignora --purge-x)",
    )
    parser.add_argument(
        "--purge-x",
        action="store_true",
        help="Purge one-shot de Signals con source_type='x'",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Contar filas afectadas sin eliminar",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    days = get_retention_days()
    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "LIVE"

    do_prune = not args.purge_x or args.prune_only
    do_purge_x = bool(args.purge_x) and not args.prune_only

    print(f"== Retención del Corpus ({mode}) ==")
    print(f"RETENTION_DAYS={days}" + (" (deshabilitado)" if days == 0 else ""))

    total = 0

    if do_prune:
        if days == 0:
            print("→ Poda omitida (RETENTION_DAYS=0)")
        else:
            pruned = prune_expired_signals(dry_run=dry_run)
            verb = "Se eliminarían" if dry_run else "Eliminados"
            print(f"→ {verb} {pruned} Signal(s) con published_at anterior a {days} días")
            total += pruned

    if do_purge_x:
        purged = purge_signals_by_source("x", dry_run=dry_run)
        verb = "Se eliminarían" if dry_run else "Eliminados"
        print(f"→ {verb} {purged} Signal(s) source_type='x' (purge one-shot)")
        total += purged

    if not do_prune and not do_purge_x:
        print("Nada que ejecutar. Usá --prune-only (default) o --purge-x.")

    print(f"\nResumen: {total} fila(s) {'contadas' if dry_run else 'afectadas'}")


if __name__ == "__main__":
    main()
