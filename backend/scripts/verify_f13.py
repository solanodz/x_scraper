"""Verificación F13: Story Cluster (dedup cross-source)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from backend.app.services.signals_repo import get_signal, list_signals
from scraper.store import connect, upsert_signals
from scraper.story_cluster import assign_url_clusters, cluster_id_from_url


CLUSTER_URL = "https://finance.yahoo.com/verify-f13-same-story"


def _seed_cluster_pair() -> tuple[str, str, str]:
    now = datetime.now(tz=timezone.utc).isoformat()
    cluster_id = cluster_id_from_url(CLUSTER_URL)
    if not cluster_id:
        raise RuntimeError("could not derive cluster_id from test URL")

    records = [
        {
            "id_str": "verify_f13:rss",
            "source_type": "rss",
            "canonical_url": CLUSTER_URL,
            "title": "Fed signals rate path unchanged amid inflation data",
            "body": None,
            "summary": "Central bank officials indicated patience on cuts.",
            "tickers": ["SPY"],
            "sentiment": None,
            "topic": "monetary policy",
            "relevance_score": 0.92,
            "date": now,
            "user": {"username": "Yahoo Finance"},
            "rawContent": "Fed signals rate path unchanged amid inflation data",
            "source": "verify:f13:rss",
            "cashtags": ["$SPY"],
            "hashtags": [],
            "replyCount": 0,
            "retweetCount": 0,
            "likeCount": 0,
            "quoteCount": 0,
            "bookmarkedCount": 0,
            "payload": {"verify": "f13"},
        },
        {
            "id_str": "verify_f13:marketaux",
            "source_type": "marketaux",
            "canonical_url": f"{CLUSTER_URL}?utm_source=test",
            "title": "Fed signals rate path unchanged amid inflation data",
            "body": None,
            "summary": "Central bank officials indicated patience on cuts.",
            "tickers": ["SPY"],
            "sentiment": "Neutral",
            "topic": "monetary policy",
            "relevance_score": 0.88,
            "date": now,
            "user": {"username": "Reuters"},
            "rawContent": "Fed signals rate path unchanged amid inflation data",
            "source": "verify:f13:marketaux",
            "cashtags": ["$SPY"],
            "hashtags": [],
            "replyCount": 0,
            "retweetCount": 0,
            "likeCount": 0,
            "quoteCount": 0,
            "bookmarkedCount": 0,
            "payload": {"verify": "f13"},
        },
    ]

    assign_url_clusters(records)
    upsert_signals(records)
    return records[0]["id_str"], records[1]["id_str"], cluster_id


def _cluster_member_count(cluster_id: str) -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM signals WHERE cluster_id = %s",
                (cluster_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0


def main() -> int:
    print("== F13 verification: Story Cluster ==\n")
    load_dotenv()

    id_a, id_b, cluster_id = _seed_cluster_pair()
    print(f"1. Seeded pair: {id_a} + {id_b}")
    print(f"   expected cluster_id: {cluster_id}")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id_str, cluster_id FROM signals WHERE id_str = ANY(%s)",
                ([id_a, id_b],),
            )
            rows = {row[0]: row[1] for row in cur.fetchall()}

    print(f"   actual: {rows}")
    if rows.get(id_a) != cluster_id or rows.get(id_b) != cluster_id:
        print("   FAIL — cluster_id mismatch")
        print("\n== F13 verification FAIL ==")
        return 1
    print("   PASS\n")

    members = _cluster_member_count(cluster_id)
    print(f"2. Cluster members in Store: {members}")
    if members < 2:
        print("   FAIL — expected >= 2 members")
        print("\n== F13 verification FAIL ==")
        return 1
    print("   PASS\n")

    feed = list_signals(limit=200)
    feed_ids = {s.id_str for s in feed}
    cluster_reps = [s for s in feed if s.cluster_id == cluster_id]
    print(f"3. Feed representatives for cluster: {len(cluster_reps)}")
    print(f"   rep ids: {[s.id_str for s in cluster_reps]}")
    if len(cluster_reps) != 1:
        print("   FAIL — feed should show one representative per cluster")
        print("\n== F13 verification FAIL ==")
        return 1
    if cluster_reps[0].id_str != id_a:
        print(f"   WARN — expected rep {id_a}, got {cluster_reps[0].id_str}")
    print("   PASS\n")

    detail = get_signal(id_a)
    if detail is None:
        print("4. Signal Detail cluster sources: FAIL — detail not found")
        print("\n== F13 verification FAIL ==")
        return 1

    sources = detail.cluster_sources
    print(f"4. Signal Detail cluster sources: {len(sources)}")
    for source in sources:
        print(f"   - {source.source_type} {source.username} ({source.id_str})")
    if len(sources) < 2:
        print("   FAIL — expected multiple cluster sources")
        print("\n== F13 verification FAIL ==")
        return 1
    print("   PASS\n")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM signals")
            total_signals = int(cur.fetchone()[0])
            cur.execute(
                "SELECT count(DISTINCT COALESCE(cluster_id, id_str)) FROM signals"
            )
            distinct_clusters = int(cur.fetchone()[0])

    print("5. Dedup metric:")
    print(f"   signals: {total_signals}")
    print(f"   clusters: {distinct_clusters}")
    if distinct_clusters >= total_signals:
        print("   FAIL — clusters should be fewer than signals when dedup works")
        print("\n== F13 verification FAIL ==")
        return 1
    print("   PASS\n")

    if id_a in feed_ids and id_b in feed_ids:
        print("   FAIL — both cluster members visible in feed")
        print("\n== F13 verification FAIL ==")
        return 1

    print("== F13 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
