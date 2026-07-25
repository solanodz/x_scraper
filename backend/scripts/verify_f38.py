"""Verificación F38: caps Article Body + SKIP_DOMAINS + backfill limit."""

from __future__ import annotations

import os
import sys


def main() -> int:
    print("verify_f38_article_body")

    # Defaults without stale env from caller
    for key in (
        "ARTICLE_BODY_MAX_PER_INGEST",
        "ARTICLE_BODY_BACKFILL_LIMIT",
        "ARTICLE_BODY_MIN_CHARS",
    ):
        os.environ.pop(key, None)

    from scraper import article_enrichment as ae

    max_ingest = ae._max_per_ingest()
    backfill = ae.article_body_backfill_limit()
    if max_ingest < 100:
        print(f"   FAIL: MAX_PER_INGEST default too low: {max_ingest}")
        return 1
    if backfill < 50:
        print(f"   FAIL: BACKFILL_LIMIT default too low: {backfill}")
        return 1
    print(f"   defaults MAX_PER_INGEST={max_ingest} BACKFILL_LIMIT={backfill}")

    # SKIP_DOMAINS still refuse enrichment
    skip_rec = {
        "source_type": "rss",
        "canonical_url": "https://news.google.com/articles/foo",
        "body": "",
        "summary": "short",
    }
    if ae.needs_article_body(skip_rec):
        print("   FAIL: news.google.com should not need_article_body")
        return 1
    mw = {
        "source_type": "rss",
        "canonical_url": "https://www.marketwatch.com/story/x",
        "body": "",
        "summary": "short",
    }
    if ae.needs_article_body(mw):
        print("   FAIL: marketwatch should not need_article_body")
        return 1
    print("   SKIP_DOMAINS still skipped (honest)")

    open_rec = {
        "source_type": "rss",
        "canonical_url": "https://www.cnbc.com/2026/07/25/example.html",
        "body": "",
        "summary": "headline only",
    }
    if not ae.needs_article_body(open_rec):
        print("   FAIL: open publisher should need_article_body")
        return 1
    print("   open publisher eligible for enrichment")

    docs = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "docs",
        "ops",
        "article-body.md",
    )
    if not os.path.isfile(docs):
        print(f"   FAIL: missing docs {docs}")
        return 1
    print("   docs/ops/article-body.md present")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
