"""Verificación F10: Corpus multi-fuente (Alpha Vantage News Source)."""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

from scraper.adapters import fetch_all_adapters, get_enabled_adapters
from scraper.adapters import alpha_vantage as av_module
from scraper.store import connect, upsert_signals


REQUIRED_COLUMNS = (
    "source_type",
    "canonical_url",
    "title",
    "body",
    "summary",
    "tickers",
    "sentiment",
    "topic",
    "relevance_score",
    "cluster_id",
)


def _migration_ok() -> tuple[bool, str]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'signals'
                  AND column_name = ANY(%s)
                """,
                (list(REQUIRED_COLUMNS),),
            )
            found = {row[0] for row in cur.fetchall()}
    missing = [col for col in REQUIRED_COLUMNS if col not in found]
    if missing:
        return False, f"missing columns: {', '.join(missing)}"
    return True, "migration columns present"


def _count_signals(source_type: str) -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM signals WHERE source_type = %s",
                (source_type,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0


def _sample_signal(source_type: str) -> dict | None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, summary, tickers, sentiment, canonical_url, source_type
                FROM signals
                WHERE source_type = %s
                ORDER BY published_at DESC
                LIMIT 1
                """,
                (source_type,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))


async def _ingest_source(source_type: str, limit: int = 20) -> int:
    adapters = [a for a in get_enabled_adapters() if a.source_type == source_type]
    if not adapters:
        return 0
    records = await fetch_all_adapters(adapters, limit=limit)
    if not records:
        return 0
    return upsert_signals(records)


def _validate_news_sample(sample: dict, *, require_enrichment: bool) -> tuple[bool, str]:
    title = (sample.get("title") or "").strip()
    summary = (sample.get("summary") or "").strip()
    tickers = list(sample.get("tickers") or [])
    sentiment = (sample.get("sentiment") or "").strip()
    canonical_url = (sample.get("canonical_url") or "").strip()

    print(f"   title: {title[:80]!r}{'...' if len(title) > 80 else ''}")
    print(f"   summary: {summary[:80]!r}{'...' if len(summary) > 80 else ''}")
    print(f"   tickers: {tickers[:5]}")
    print(f"   sentiment: {sentiment!r}")
    print(f"   canonical_url: {canonical_url[:80]!r}")

    if not title or not summary:
        return False, "title/summary not populated"
    if not canonical_url:
        return False, "canonical_url not populated"
    if require_enrichment and not tickers and not sentiment:
        return False, "neither tickers nor sentiment populated (AV enrichment)"
    return True, "ok"


def main() -> int:
    print("== F10 verification: Alpha Vantage News Source ==\n")
    load_dotenv()

    ok, detail = _migration_ok()
    print(f"1. Schema migration: {detail}")
    if not ok:
        print("   FAIL — run infra/store/init/003_signals_multisource.sql")
        print("\n== F10 verification FAIL ==")
        return 1
    print("   PASS\n")

    av_count = _count_signals("alpha_vantage")
    print(f"2. AV signals in Store: {av_count}")
    av_rate_limited = False

    if av_count == 0:
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        if not api_key:
            print("   WARN — ALPHA_VANTAGE_API_KEY missing; skipping AV ingest")
        else:
            print("   → ingesting one AV batch in-process...")
            inserted = asyncio.run(_ingest_source("alpha_vantage", limit=20))
            print(f"   upsert affected rows: {inserted}")
            av_count = _count_signals("alpha_vantage")
            print(f"   AV signals after ingest: {av_count}")
            if av_count == 0 and av_module.last_fetch_status == "rate_limited":
                av_rate_limited = True
                msg = (av_module.last_fetch_message or "")[:160]
                print(f"   WARN — AV rate limited (shares daily quota with Quotes): {msg}")

    rss_count = _count_signals("rss")
    print(f"\n3. RSS signals in Store: {rss_count}")
    if rss_count == 0:
        print("   → ingesting one RSS batch in-process...")
        inserted = asyncio.run(_ingest_source("rss", limit=20))
        print(f"   upsert affected rows: {inserted}")
        rss_count = _count_signals("rss")
        print(f"   RSS signals after ingest: {rss_count}")

    if av_count > 0:
        print("\n4. Sample AV signal fields:")
        sample = _sample_signal("alpha_vantage")
        if sample is None:
            print("   FAIL — no sample row")
            print("\n== F10 verification FAIL ==")
            return 1
        valid, reason = _validate_news_sample(sample, require_enrichment=True)
        if not valid:
            print(f"   FAIL — {reason}")
            print("\n== F10 verification FAIL ==")
            return 1
        print("   PASS\n")
        print("== F10 verification OK ==")
        return 0

    if av_rate_limited and rss_count > 0:
        print("\n4. Sample RSS signal fields (AV quota exhausted; pipeline fallback):")
        sample = _sample_signal("rss")
        if sample is None:
            print("   FAIL — no RSS sample row")
            print("\n== F10 verification FAIL ==")
            return 1
        valid, reason = _validate_news_sample(sample, require_enrichment=False)
        if not valid:
            print(f"   FAIL — {reason}")
            print("\n== F10 verification FAIL ==")
            return 1
        print("   PASS (AV quota exhausted; RSS confirms multi-source pipeline)\n")
        print("== F10 verification OK ==")
        return 0

    print("\n   FAIL — no AV signals and RSS fallback did not populate Store")
    print("   Run: python -m scraper.ingest --skip-x --skip-embeddings")
    print("\n== F10 verification FAIL ==")
    return 1


if __name__ == "__main__":
    sys.exit(main())
