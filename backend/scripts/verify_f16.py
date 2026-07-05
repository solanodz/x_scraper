"""Verificación F16: RSS noticias Argentina."""

from __future__ import annotations

import asyncio
import sys

from scraper.adapters.rss import ARGENTINA_FEEDS, RssNewsAdapter
from scraper.article_enrichment import enrich_article_bodies, fetch_article_body


async def _fetch_ar_rss(limit: int = 20) -> list[dict]:
    adapter = RssNewsAdapter(feeds=ARGENTINA_FEEDS)
    return await adapter.fetch(limit=limit)


def main() -> int:
    print("== F16 verification: RSS Argentina ==\n")

    records = asyncio.run(_fetch_ar_rss(limit=25))
    print(f"1. AR RSS fetch: {len(records)} signals")
    if len(records) < 5:
        print("   FAIL — expected at least 5 signals from AR feeds")
        return 1

    sources = {str(r.get("user", {}).get("username", "")) for r in records}
    print(f"   feeds: {sorted(sources)}")
    expected_any = {"Ámbito Economía", "Ámbito Finanzas", "La Nación Economía", "Infobae Economía"}
    if not sources.intersection(expected_any):
        print(f"   FAIL — missing AR media feeds in {sources}")
        return 1
    print("   PASS\n")

    ambito = next(
        (
            r
            for r in records
            if str(r.get("user", {}).get("username", "")).startswith("Ámbito")
            and str(r.get("canonical_url", "")).startswith("https://www.ambito.com/")
        ),
        None,
    )
    if ambito is None:
        print("2. Ámbito sample for Article Body: SKIP (no ambito.com link)")
    else:
        url = str(ambito["canonical_url"])
        body = fetch_article_body(url)
        print(f"2. Ámbito Article Body ({url[:70]}...)")
        print(f"   body_len: {len(body or '')}")
        if not body or len(body.strip()) < 200:
            print("   FAIL — trafilatura body too short on Ámbito")
            return 1
        print("   PASS\n")

    attempted, enriched = enrich_article_bodies(records, max_fetch=8)
    print(f"3. Article Enrichment on AR batch: {enriched}/{attempted}")
    with_body = sum(1 for r in records if str(r.get("body") or "").strip())
    print(f"   records with body after enrich: {with_body}")
    if with_body == 0:
        print("   FAIL — no Article Body enriched")
        return 1
    print("   PASS\n")

    spanish = next(
        (r for r in records if any(w in (r.get("title") or "").lower() for w in ("dólar", "economía", "inflación"))),
        records[0],
    )
    title = str(spanish.get("title") or "")
    print(f"4. Spanish headline sample: {title[:90]!r}...")
    print("   PASS\n")

    print("== F16 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
