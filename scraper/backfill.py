#!/usr/bin/env python3
"""
Backfill de embeddings para Signals sin Vector Index.

Uso:
  python -m scraper.backfill
  python -m scraper.backfill --limit 200
"""

from __future__ import annotations

import argparse
import os
import sys

from scraper.embeddings import build_embedding_document, embed_texts_safe
from scraper.store import fetch_signals_without_embedding, update_embeddings


def embedding_backfill_limit() -> int:
    """Máximo de Signals a backfillear por ciclo (env EMBEDDING_BACKFILL_LIMIT, default 200)."""
    raw = os.getenv("EMBEDDING_BACKFILL_LIMIT", "200").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 200


def backfill_embeddings(limit: int | None = None) -> int:
    """Genera embeddings para Signals sin embedding. Devuelve filas actualizadas."""
    effective_limit = embedding_backfill_limit() if limit is None else max(1, limit)
    signals = fetch_signals_without_embedding(effective_limit)
    if not signals:
        return 0

    pairs: list[tuple[dict, str]] = []
    for signal in signals:
        document = build_embedding_document(signal)
        if document.strip():
            pairs.append((signal, document))

    if not pairs:
        return 0

    texts = [document for _, document in pairs]
    embeddings = embed_texts_safe(texts)
    if embeddings is None:
        print(
            "Warning: no se pudieron generar embeddings (OPENAI_API_KEY o API error)",
            file=sys.stderr,
        )
        return 0

    updated = 0
    for (signal, _), embedding in zip(pairs, embeddings):
        update_embeddings(signal["id_str"], embedding)
        updated += 1
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill de embeddings para Signals sin Vector Index"
    )
    default_limit = embedding_backfill_limit()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Máximo de Signals a procesar "
            f"(default: EMBEDDING_BACKFILL_LIMIT={default_limit})"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    limit = max(1, args.limit if args.limit is not None else embedding_backfill_limit())
    print(f"== Backfill de embeddings (limit={limit}) ==")
    updated = backfill_embeddings(limit=limit)
    print(f"\nResumen: {updated} embedding(s) actualizados")


if __name__ == "__main__":
    main()
