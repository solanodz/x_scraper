#!/usr/bin/env python3
"""
Ingestion: News Sources primero (RSS, Marketaux, AV) + X como complemento (twscrape).

Requisitos:
  - Python 3.10+
  - pip install -r requirements.txt
  - Archivo .env con DATABASE_URL (ver .env.example)
  - X: X_COOKIES (opcional si solo News Sources)
  - AV: ALPHA_VANTAGE_API_KEY (opcional; cuota 25/día compartida con Quotes)
  - Marketaux: MARKETAUX_API_KEY (100 req/día free, 3 artículos/request)

Uso:
  python -m scraper.ingest
  python -m scraper.ingest --limit-per-account 5 --limit-per-search 10
  python -m scraper.ingest --accounts-only --max-accounts 3
  python -m scraper.ingest --search-only
  python -m scraper.ingest --av-only
  python -m scraper.ingest --skip-x
  python -m scraper.ingest --skip-av
  python -m scraper.ingest --skip-embeddings
  python -m scraper.ingest --prune-only
  python -m scraper.ingest --skip-retention
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from scraper.adapters import (
    fetch_all_adapters,
    get_enabled_adapters,
    get_x_complement_adapter,
)
from scraper.article_enrichment import enrich_article_bodies, backfill_article_bodies
from scraper.backfill import backfill_embeddings
from scraper.embeddings import build_embedding_document, embed_texts_safe
from scraper.filters import filter_records, get_filter_config
from scraper.relevance import apply_relevance_scores
from scraper.retention import prune_expired_signals
from scraper.store import upsert_signals
from scraper.story_cluster import (
    apply_embedding_clusters,
    assign_url_clusters,
    update_cluster_ids,
)


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        signal_id = record.get("id_str") or str(record.get("id"))
        if signal_id in seen:
            continue
        seen.add(signal_id)
        unique.append(record)
    return unique


def add_ingest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit-per-account",
        type=int,
        default=10,
        help="Signals X por cuenta (default: 10)",
    )
    parser.add_argument(
        "--limit-per-search",
        type=int,
        default=15,
        help="Signals X por búsqueda (default: 15)",
    )
    parser.add_argument(
        "--limit-per-adapter",
        type=int,
        default=50,
        help="Signals por News Source adapter (default: 50)",
    )
    parser.add_argument(
        "--accounts-only",
        action="store_true",
        help="Solo extraer timelines de cuentas de referencia (X)",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Solo extraer resultados de búsqueda (X)",
    )
    parser.add_argument(
        "--av-only",
        action="store_true",
        help="Solo News Sources (RSS + Alpha Vantage); omitir X",
    )
    parser.add_argument(
        "--skip-x",
        action="store_true",
        help="Omitir ingesta de X (solo News Sources)",
    )
    parser.add_argument(
        "--skip-av",
        action="store_true",
        help="Omitir News Sources (solo X)",
    )
    parser.add_argument(
        "--max-accounts",
        type=int,
        default=None,
        help="Limitar cuántas cuentas de FINANCIAL_ACCOUNTS procesar",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Persistir Signals sin Vector Index (desarrollo sin OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--skip-story-cluster",
        action="store_true",
        help="Omitir Story Cluster (dedup cross-source) en la Ingestion",
    )
    parser.add_argument(
        "--skip-relevance",
        action="store_true",
        help="Omitir Relevance Score (LLM) en la Ingestion",
    )
    parser.add_argument(
        "--skip-article-body",
        action="store_true",
        help="Omitir Article Enrichment (trafilatura) en Signals de noticias",
    )
    parser.add_argument(
        "--skip-retention",
        action="store_true",
        help="Omitir poda de Retention Window al final de la Ingestion",
    )
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="Solo ejecutar Retention Window (sin fetch ni persist)",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingestion multi-fuente: News Sources + X hacia el Store"
    )
    add_ingest_args(parser)
    return parser.parse_args()


def persist_records(
    records: list[dict[str, Any]],
    *,
    skip_embeddings: bool = False,
) -> int:
    affected = upsert_signals(records)

    if records and not skip_embeddings:
        documents = [build_embedding_document(record) for record in records]
        print(f"→ Vector Index: {len(documents)} Embedding Documents")
        embeddings = embed_texts_safe(documents)
        if embeddings is not None:
            merged, cluster_updates = apply_embedding_clusters(records, embeddings)
            if cluster_updates:
                update_cluster_ids(cluster_updates)
            if merged:
                print(f"  → Story Cluster: {merged} near-duplicate(s) fusionados")
            upsert_signals(records, embeddings=embeddings)
            print(f"  ✓ {len(embeddings)} embeddings generados")
        else:
            print(
                "  ⚠ Vector Index: embed falló — Signals guardados sin embedding",
                file=sys.stderr,
            )

    return affected


def _run_post_ingestion_steps(args: argparse.Namespace) -> None:
    if not args.skip_article_body:
        updated = backfill_article_bodies(limit=30)
        if updated:
            print(f"→ Backfill Article Body: {updated} Signal(s) enriquecidos")

    if not args.skip_embeddings:
        updated = backfill_embeddings()
        if updated:
            print(f"→ Backfill Vector Index: {updated} embedding(s) actualizados")

    if not args.skip_retention:
        pruned = prune_expired_signals()
        if pruned:
            print(f"→ Retention Window: {pruned} Signal(s) eliminados")


async def run_ingestion(args: argparse.Namespace) -> None:
    if args.prune_only:
        if args.skip_retention:
            print("Nada que ejecutar: --prune-only con --skip-retention.", file=sys.stderr)
            return
        pruned = prune_expired_signals()
        print(f"→ Retention Window: {pruned} Signal(s) eliminados")
        return

    if args.av_only and args.skip_av:
        print("Error: --av-only y --skip-av son incompatibles.", file=sys.stderr)
        sys.exit(1)
    if args.av_only and args.skip_x is False:
        args.skip_x = True

    run_av = not args.skip_av
    run_x = not args.skip_x and not args.av_only

    if not run_av and not run_x:
        print(
            "Error: no hay fuentes activas. --skip-x y --skip-av juntos vacían el pipeline.\n"
            "  Solo noticias: python -m scraper.ingest --skip-x\n"
            "  Solo X:        python -m scraper.ingest --skip-av",
            file=sys.stderr,
        )
        sys.exit(1)

    records: list[dict[str, Any]] = []

    print("Iniciando Ingestion multi-fuente (News Sources primero, X complemento)...\n")

    if run_av:
        adapters = get_enabled_adapters()
        if not adapters:
            print(
                "⚠ No hay News Source adapters habilitados "
                "(RSS_NEWS_ENABLED, MARKETAUX_API_KEY o ALPHA_VANTAGE_API_KEY)"
            )
        else:
            records.extend(
                await fetch_all_adapters(adapters, limit=args.limit_per_adapter)
            )

    if run_x:
        x_adapter = get_x_complement_adapter(
            limit_per_account=args.limit_per_account,
            limit_per_search=args.limit_per_search,
            max_accounts=args.max_accounts,
            accounts_only=args.accounts_only,
            search_only=args.search_only,
        )
        print(f"→ {x_adapter.name}")
        x_batch = await x_adapter.fetch()
        print(f"  ✓ {len(x_batch)} Signals X")
        records.extend(x_batch)

    if records:
        records = deduplicate(records)
        filter_cfg = get_filter_config()
        records, skipped = filter_records(records, filter_cfg)
        if skipped:
            print(f"→ Filtro de relevancia ({filter_cfg.mode}): {skipped} descartados")
        if not args.skip_article_body:
            attempted, enriched = enrich_article_bodies(records)
            if attempted:
                print(
                    f"→ Article Enrichment: {enriched}/{attempted} "
                    f"Article Body extraídos (trafilatura)"
                )
        if not args.skip_relevance:
            attempted, scored = apply_relevance_scores(records)
            if attempted:
                print(
                    f"→ Relevance Score: {scored}/{attempted} "
                    f"Signals puntuados (LLM)"
                )
        if not args.skip_story_cluster:
            clustered = assign_url_clusters(records)
            if clustered:
                print(f"→ Story Cluster: {clustered} Signal(s) agrupados por URL")
        affected = persist_records(records, skip_embeddings=args.skip_embeddings)

        print(
            f"\nListo: {len(records)} Signals relevantes persistidos en el Store "
            f"({affected} filas afectadas)"
        )
        sample = records[0]
        source_type = sample.get("source_type") or "x"
        username = (sample.get("user") or {}).get("username", "?")
        headline = sample.get("title") or sample.get("rawContent", "")[:120]
        print("\nEjemplo del primer Signal:")
        print(f"  [{source_type}] @{username}: {headline}...")
        if sample.get("sentiment"):
            print(f"  Sentiment: {sample['sentiment']}")
        if sample.get("tickers"):
            print(f"  Tickers: {', '.join(sample['tickers'][:5])}")
    else:
        print("\nNo se obtuvieron Signals. Revisá API keys / cookies / flags.")

    _run_post_ingestion_steps(args)


async def main() -> None:
    args = parse_args()
    await run_ingestion(args)


if __name__ == "__main__":
    asyncio.run(main())
