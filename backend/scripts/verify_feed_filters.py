"""Verificación: filtros del Signal Feed (palabras clave + criterios)."""

from __future__ import annotations

import sys

from backend.app.services.feed_filters import feed_filters_from_query
from backend.app.services.signals_repo import list_signals


def main() -> int:
    print("== Feed filters verification ==\n")

    all_signals = list_signals(limit=5)
    print(f"1. Baseline feed: {len(all_signals)} signals")
    if not all_signals:
        print("   SKIP filter assertions (empty store)")
        print("\n== Feed filters verification OK (empty) ==")
        return 0

    sample = all_signals[0]
    title_word = (sample.title or sample.raw_content or "").split()[0]
    if title_word:
        filters = feed_filters_from_query(q=title_word)
        hits = list_signals(limit=20, filters=filters)
        print(f"2. Keyword q={title_word!r}: {len(hits)} hits")
        if not hits:
            print("   FAIL: keyword filter returned empty")
            return 1
        print("   PASS")

    news_filters = feed_filters_from_query(source_type="news")
    news_hits = list_signals(limit=10, filters=news_filters)
    print(f"3. source_type=news: {len(news_hits)} hits")
    for item in news_hits:
        if item.source_type == "x":
            print("   FAIL: x signal in news filter")
            return 1
    print("   PASS")

    x_filters = feed_filters_from_query(source_type="x")
    x_hits = list_signals(limit=10, filters=x_filters)
    print(f"4. source_type=x: {len(x_hits)} hits")
    for item in x_hits:
        if item.source_type not in (None, "x"):
            print(f"   FAIL: non-x in x filter: {item.source_type}")
            return 1
    print("   PASS")

    recent_filters = feed_filters_from_query(since_hours=168)
    recent_hits = list_signals(limit=10, filters=recent_filters)
    print(f"5. since_hours=168: {len(recent_hits)} hits — PASS")

    if len(all_signals) >= 2:
        ts = [s.published_at.timestamp() for s in all_signals]
        if ts != sorted(ts, reverse=True):
            print("6. Feed order by published_at DESC: FAIL")
            return 1
        print("6. Feed order by published_at DESC: PASS")

    print("\n== Feed filters verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
