"""Verificación F12: Relevance Score (LLM) para el Signal Feed."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from backend.app.services.signals_repo import list_signals
from scraper.adapters import fetch_all_adapters, get_enabled_adapters
from scraper.relevance import apply_relevance_scores, feed_min_relevance
from scraper.store import connect, upsert_signals


def _fix_legacy_scores() -> int:
    """Limpia relevance_score fuera de [0,1] (legacy: sentiment mal mapeado)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE signals
                SET relevance_score = NULL
                WHERE relevance_score IS NOT NULL
                  AND (relevance_score < 0 OR relevance_score > 1)
                """
            )
            return cur.rowcount


def _count_scored() -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)
                FROM signals
                WHERE relevance_score IS NOT NULL
                  AND relevance_score >= 0
                  AND relevance_score <= 1
                """
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0


def _scores_in_range() -> tuple[bool, str]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)
                FROM signals
                WHERE relevance_score IS NOT NULL
                  AND (relevance_score < 0 OR relevance_score > 1)
                """
            )
            bad = int(cur.fetchone()[0])
    if bad:
        return False, f"{bad} rows out of [0,1] range"
    return True, "all scores in [0,1]"


async def _score_rss_batch(limit: int = 6) -> tuple[int, int]:
    adapters = [a for a in get_enabled_adapters() if a.source_type == "rss"]
    if not adapters:
        return 0, 0
    records = await fetch_all_adapters(adapters, limit=limit)
    for record in records:
        record.pop("relevance_score", None)
        record.pop("topic", None)
    attempted, scored = apply_relevance_scores(records, max_score=limit)
    if records:
        upsert_signals(records)
    return attempted, scored


def _seed_noise_signal() -> str:
    """Inserta un Signal de ruido con score bajo para probar el umbral del Feed."""
    noise_id = "verify_f12:noise"
    now = datetime.now(tz=timezone.utc).isoformat()
    record = {
        "id_str": noise_id,
        "source_type": "rss",
        "canonical_url": "https://example.com/world-cup-finals-party",
        "title": "World Cup party photos and celebrity gossip",
        "body": None,
        "summary": "Fans celebrate the championship with concerts and memes.",
        "tickers": [],
        "sentiment": None,
        "topic": "sports entertainment",
        "relevance_score": 0.05,
        "date": now,
        "user": {"username": "Verify F12"},
        "rawContent": "World Cup party photos and celebrity gossip",
        "source": "verify:f12",
        "cashtags": [],
        "hashtags": [],
        "replyCount": 0,
        "retweetCount": 0,
        "likeCount": 0,
        "quoteCount": 0,
        "bookmarkedCount": 0,
        "payload": {"verify": "f12_noise"},
    }
    upsert_signals([record])
    return noise_id


def _feed_contains(id_str: str) -> bool:
    return any(s.id_str == id_str for s in list_signals(limit=200))


def _feed_ordered_by_date() -> tuple[bool, str]:
    signals = list_signals(limit=30)
    if len(signals) < 2:
        return True, "insufficient rows for order check"
    timestamps = [s.published_at.timestamp() for s in signals]
    ordered = timestamps == sorted(timestamps, reverse=True)
    if not ordered:
        return False, f"published_at not descending: {timestamps[:8]}"
    return True, f"top dates: {[s.published_at.isoformat()[:19] for s in signals[:3]]}"


def main() -> int:
    print("== F12 verification: Relevance Score ==\n")
    load_dotenv()

    fixed = _fix_legacy_scores()
    if fixed:
        print(f"0. Legacy score cleanup: {fixed} row(s) nulled\n")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("FAIL — OPENAI_API_KEY required for Relevance Score")
        print("\n== F12 verification FAIL ==")
        return 1

    scored_count = _count_scored()
    print(f"1. Signals with relevance_score in Store: {scored_count}")
    if scored_count < 3:
        print("   → scoring RSS batch in-process...")
        attempted, scored = asyncio.run(_score_rss_batch(limit=6))
        print(f"   LLM scoring: {scored}/{attempted}")
        scored_count = _count_scored()
        print(f"   scored after ingest: {scored_count}")

    if scored_count == 0:
        print("   FAIL — no relevance_score persisted")
        print("\n== F12 verification FAIL ==")
        return 1

    ok, detail = _scores_in_range()
    print(f"   range check: {detail}")
    if not ok:
        print("   FAIL")
        print("\n== F12 verification FAIL ==")
        return 1
    print("   PASS\n")

    print("2. GET /signals orders by published_at DESC:")
    ok, detail = _feed_ordered_by_date()
    print(f"   {detail}")
    if not ok:
        print("   FAIL")
        print("\n== F12 verification FAIL ==")
        return 1
    print("   PASS\n")

    print("3. Low-relevance Signal below feed threshold:")
    min_rel = feed_min_relevance()
    print(f"   RELEVANCE_SCORE_MIN={min_rel}")
    noise_id = _seed_noise_signal()
    in_feed = _feed_contains(noise_id)
    print(f"   noise id={noise_id} in_feed={in_feed}")
    if min_rel is not None and in_feed:
        print("   FAIL — noise signal should be filtered from feed")
        print("\n== F12 verification FAIL ==")
        return 1
    if min_rel is None:
        print("   WARN — threshold disabled; skip filter assertion")
    else:
        print("   PASS (noise excluded from feed)\n")

    print("4. Feed chronological order (newest first):")
    signals = list_signals(limit=10)
    if len(signals) >= 2:
        first = signals[0].published_at
        second = signals[1].published_at
        if first < second:
            print("   FAIL — feed not sorted by published_at DESC")
            print("\n== F12 verification FAIL ==")
            return 1
    print(
        f"   top: {signals[0].id_str} at={signals[0].published_at.isoformat()[:19]}"
        if signals
        else "   no signals"
    )
    print("   PASS\n")

    print("== F12 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
