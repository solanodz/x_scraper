"""Verificación F4: Core Services search / summarize / ask."""

from __future__ import annotations

import sys

from scraper.store import connect

from backend.services.ask import ask
from backend.services.search import search


def _check_similarity_order(hits: list) -> bool:
    if len(hits) < 2:
        return True
    scores = [hit.similarity for hit in hits]
    return scores == sorted(scores, reverse=True)


def _ids_exist_in_store(id_strs: list[str]) -> tuple[bool, list[str]]:
    if not id_strs:
        return True, []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id_str FROM signals WHERE id_str = ANY(%s)",
                (id_strs,),
            )
            found = {row[0] for row in cur.fetchall()}
    missing = [item for item in id_strs if item not in found]
    return not missing, missing


def main() -> int:
    print("== F4 verification: Core Services ==\n")

    # 1. search('inflation')
    print("1. search('inflation')")
    hits = search("inflation", limit=5)
    print(f"   hits: {len(hits)}")
    for hit in hits[:3]:
        print(
            f"   - {hit.id_str} @{hit.username} sim={hit.similarity:.4f} "
            f"url={hit.url[:50]}..."
        )
    ordered = _check_similarity_order(hits)
    print(f"   ordered_by_similarity: {ordered}")
    if not hits:
        print("   FAIL: no hits returned")
        return 1
    if not ordered:
        print("   FAIL: hits not ordered by similarity")
        return 1
    print("   PASS\n")

    # 2. ask('resumen mercados hoy')
    print("2. ask('resumen mercados hoy')")
    result = ask("resumen mercados hoy")
    print(f"   answer_len: {len(result.answer)}")
    print(f"   answer_preview: {result.answer[:200]}...")
    print(f"   citations: {len(result.citations)}")
    for citation in result.citations[:3]:
        print(f"   - {citation.id_str} @{citation.username}")
    if not result.answer.strip():
        print("   FAIL: empty answer")
        return 1
    if not result.citations:
        print("   FAIL: no citations")
        return 1
    print("   PASS\n")

    # 3. citation id_str exist in Store
    print("3. citation id_str validation")
    citation_ids = [c.id_str for c in result.citations]
    ok, missing = _ids_exist_in_store(citation_ids)
    print(f"   checked: {len(citation_ids)} missing: {len(missing)}")
    if missing:
        print(f"   missing_ids: {missing}")
        print("   FAIL")
        return 1
    print("   PASS\n")

    print("== F4 verification OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
