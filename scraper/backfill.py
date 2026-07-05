#!/usr/bin/env python3
"""
Backfill de embeddings para Signals sin Vector Index.

Uso:
  python -m scraper.backfill
  python -m scraper.backfill --limit 50
"""

from __future__ import annotations

import argparse
import sys

from scraper.embeddings import build_embedding_document, embed_texts_safe
from scraper.store import fetch_signals_without_embedding, update_embeddings


def backfill_embeddings(limit: int = 100) -> int:
    """Genera embeddings para Signals sin embedding. Devuelve filas actualizadas."""
    signals = fetch_signals_without_embedding(limit)
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
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Máximo de Signals a procesar (default: 100)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    limit = max(1, args.limit)
    print(f"== Backfill de embeddings (limit={limit}) ==")
    updated = backfill_embeddings(limit=limit)
    print(f"\nResumen: {updated} embedding(s) actualizados")


if __name__ == "__main__":
    main()
