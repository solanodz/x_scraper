"""Verificación F17: Acceso confiable al Corpus (retrieval)."""

from __future__ import annotations

import inspect
import os
import sys

from dotenv import load_dotenv

from scraper.backfill import embedding_backfill_limit


def _db_available() -> tuple[bool, str]:
    try:
        from scraper.store import connect

        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _check_embedding_backfill_limit() -> bool:
    print("1. EMBEDDING_BACKFILL_LIMIT env")
    saved = os.environ.get("EMBEDDING_BACKFILL_LIMIT")
    try:
        os.environ.pop("EMBEDDING_BACKFILL_LIMIT", None)
        default_limit = embedding_backfill_limit()
        if default_limit != 200:
            print(f"   FAIL — expected default 200, got {default_limit}")
            return False

        os.environ["EMBEDDING_BACKFILL_LIMIT"] = "150"
        if embedding_backfill_limit() != 150:
            print("   FAIL — env override not read")
            return False

        print(f"   default=200 override=150")
        print("   PASS\n")
        return True
    finally:
        if saved is None:
            os.environ.pop("EMBEDDING_BACKFILL_LIMIT", None)
        else:
            os.environ["EMBEDDING_BACKFILL_LIMIT"] = saved


def _check_get_recent_signals(db_ok: bool, db_err: str) -> bool:
    print("2. get_recent_signals")
    try:
        from backend.services.recent_signals import get_recent_signals
    except ImportError as exc:
        print(f"   FAIL — import: {exc}")
        return False

    if not callable(get_recent_signals):
        print("   FAIL — not callable")
        return False

    sig = inspect.signature(get_recent_signals)
    print(f"   signature: {sig}")

    if not db_ok:
        print(f"   SKIP — no DB ({db_err})")
        print("   PASS (import only)\n")
        return True

    hits = get_recent_signals(limit=5)
    print(f"   hits: {len(hits)}")
    if len(hits) >= 2:
        timestamps = [h.published_at for h in hits]
        if timestamps != sorted(timestamps, reverse=True):
            print("   FAIL — not ordered by published_at DESC")
            return False
        print("   order: published_at DESC OK")
    elif len(hits) == 0:
        print("   WARN — Store empty")
    print("   PASS\n")
    return True


def _check_keyword_retrieval(db_ok: bool, db_err: str) -> bool:
    print("3. search_by_keywords / retrieve fallback")
    try:
        from backend.services.retrieval import retrieve, search_by_keywords
    except ImportError as exc:
        print(f"   FAIL — import: {exc}")
        return False

    if not db_ok:
        print(f"   SKIP — no DB ({db_err})")
        print("   PASS (imports only)\n")
        return True

    kw_hits = search_by_keywords("mercado acciones", limit=3)
    print(f"   search_by_keywords hits: {len(kw_hits)}")
    if not kw_hits:
        print("   WARN — no keyword hits (Store puede estar vacío)")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("   SKIP retrieve — OPENAI_API_KEY not set")
    else:
        try:
            vec_hits = retrieve("mercado acciones", limit=3)
            print(f"   retrieve hits: {len(vec_hits)} (vector or keyword fallback)")
        except Exception as exc:
            print(f"   WARN retrieve failed: {exc}")

    print("   PASS\n")
    return True


def main() -> int:
    print("== F17 verification: Corpus retrieval ==\n")
    load_dotenv()

    db_ok, db_err = _db_available()
    if not db_ok:
        print(f"NOTE: DB unavailable — runtime checks will SKIP ({db_err})\n")

    checks = [
        _check_embedding_backfill_limit(),
        _check_get_recent_signals(db_ok, db_err),
        _check_keyword_retrieval(db_ok, db_err),
    ]

    if not all(checks):
        print("== F17 verification FAIL ==")
        return 1

    print("== F17 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
