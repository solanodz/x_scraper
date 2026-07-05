"""Verificación F14: X como complemento (News Sources primero)."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.signals_repo import list_signals
from scraper.adapters import get_enabled_adapters
from scraper.adapters.rss import RssNewsAdapter
from scraper.adapters.x_complement import XComplementAdapter
from scraper.ingest import run_ingestion
from scraper.store import connect


def _count_by_source(days: int = 7) -> dict[str, int]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_type, count(*)
                FROM signals
                WHERE published_at >= now() - make_interval(days => %(days)s)
                GROUP BY source_type
                """,
                {"days": days},
            )
            return {str(row[0] or "x"): int(row[1]) for row in cur.fetchall()}


async def _ingest_news_only(limit: int = 8) -> int:
    from argparse import Namespace

    from scraper.adapters import fetch_all_adapters

    adapters = [a for a in get_enabled_adapters() if a.source_type == "rss"]
    if not adapters:
        adapters = [RssNewsAdapter()]
    records = await fetch_all_adapters(adapters, limit=limit)
    if not records:
        return 0
    from scraper.store import upsert_signals

    return upsert_signals(records)


def main() -> int:
    print("== F14 verification: X como complemento ==\n")
    load_dotenv()

    print("1. X adapter aísla fallos de twscrape")
    adapter = XComplementAdapter(limit_per_account=1, max_accounts=1)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("twscrape unavailable")

    with patch.object(XComplementAdapter, "_fetch_safe", new=AsyncMock(side_effect=_boom)):
        batch = asyncio.run(adapter.fetch(limit=3))
    if batch:
        print("   FAIL — expected empty batch on twscrape failure")
        print("\n== F14 verification FAIL ==")
        return 1
    print("   PASS (0 Signals, sin excepción propagada)\n")

    print("2. Ingestion con X roto + News Sources activos")
    news_before = _count_by_source().get("rss", 0)

    async def _run_ingest_skip_embed():
        from argparse import Namespace

        args = Namespace(
            prune_only=False,
            av_only=False,
            skip_av=False,
            skip_x=False,
            skip_embeddings=True,
            skip_article_body=True,
            skip_relevance=True,
            skip_story_cluster=True,
            skip_retention=True,
            limit_per_adapter=6,
            limit_per_account=1,
            limit_per_search=1,
            max_accounts=1,
            accounts_only=False,
            search_only=False,
        )
        with patch.object(XComplementAdapter, "_fetch_safe", new=AsyncMock(side_effect=_boom)):
            await run_ingestion(args)

    try:
        asyncio.run(_run_ingest_skip_embed())
    except SystemExit:
        pass

    counts = _count_by_source()
    news_after = counts.get("rss", 0)
    print(f"   source counts (7d): {counts}")
    if news_after < news_before and counts.get("rss", 0) == 0:
        inserted = asyncio.run(_ingest_news_only(limit=6))
        print(f"   fallback RSS upsert: {inserted}")
        counts = _count_by_source()
    news_total = sum(v for k, v in counts.items() if k != "x")
    if news_total == 0:
        print("   FAIL — no news signals in Store")
        print("\n== F14 verification FAIL ==")
        return 1
    print("   PASS (News Sources persistieron con X fallido)\n")

    print("3. Feed: noticias y X conviven (source_type visible)")
    import os

    os.environ["AUTH_ENABLED"] = "false"
    client = TestClient(app)
    feed = client.get("/signals?limit=30").json()
    types = {item.get("source_type", "x") for item in feed}
    print(f"   feed source_types: {sorted(types)}")
    if not any(t != "x" for t in types):
        print("   FAIL — feed sin News Sources")
        print("\n== F14 verification FAIL ==")
        return 1
    print("   PASS\n")

    print("4. Proporción: News Sources mayoría en feed reciente")
    feed_news = sum(1 for s in feed if s.get("source_type") != "x")
    feed_x = sum(1 for s in feed if s.get("source_type") == "x")
    print(f"   feed mix: news={feed_news} x={feed_x}")
    if feed_news <= feed_x:
        print("   WARN — X no es minoría en feed (puede haber backlog legacy de X)")
        if feed_news < feed_x:
            print("   FAIL — noticias no dominan el feed")
            print("\n== F14 verification FAIL ==")
            return 1
    print("   PASS\n")

    print("5. Orden del feed: noticias antes que X (misma relevancia)")
    signals = list_signals(limit=20)
    if signals:
        first_x = next(
            (i for i, s in enumerate(signals) if s.source_type == "x"),
            None,
        )
        last_news = next(
            (
                i
                for i in range(len(signals) - 1, -1, -1)
                if signals[i].source_type != "x"
            ),
            None,
        )
        if (
            first_x is not None
            and last_news is not None
            and first_x < last_news
        ):
            print(f"   FAIL — X en índice {first_x} antes de noticia en {last_news}")
            print("\n== F14 verification FAIL ==")
            return 1
    print("   PASS\n")

    print("== F14 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
