"""Article Enrichment: extrae Article Body desde canonical_url (trafilatura)."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

NEWS_SOURCE_TYPES = frozenset({"rss", "marketaux", "alpha_vantage"})

# Dominios wrapper donde la extracción suele fallar (fallback a summary).
SKIP_DOMAINS = frozenset(
    {
        "news.google.com",
        "www.news.google.com",
        "www.marketwatch.com",
        "marketwatch.com",
    }
)


def _article_body_enabled() -> bool:
    load_dotenv()
    raw = os.getenv("ARTICLE_BODY_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _max_per_ingest() -> int:
    load_dotenv()
    raw = os.getenv("ARTICLE_BODY_MAX_PER_INGEST", "50").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 50


def _min_body_chars() -> int:
    load_dotenv()
    raw = os.getenv("ARTICLE_BODY_MIN_CHARS", "200").strip()
    try:
        return max(50, int(raw))
    except ValueError:
        return 200


def _fetch_delay_seconds() -> float:
    load_dotenv()
    raw = os.getenv("ARTICLE_BODY_FETCH_DELAY", "0.5").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.5


def _domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""


def needs_article_body(record: dict[str, Any]) -> bool:
    """True si el Signal de noticia puede enriquecerse con Article Body."""
    source_type = str(record.get("source_type") or "x")
    if source_type not in NEWS_SOURCE_TYPES:
        return False
    url = str(record.get("canonical_url") or "").strip()
    if not url or _domain(url) in SKIP_DOMAINS:
        return False
    existing = str(record.get("body") or "").strip()
    summary = str(record.get("summary") or "").strip()
    if len(existing) >= _min_body_chars() and existing != summary:
        return False
    return True


def fetch_article_body(url: str) -> str | None:
    """Best-effort: descarga y extrae texto con trafilatura. None si falla o paywall."""
    try:
        import trafilatura
    except ImportError:
        return None

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
    except Exception:
        return None

    if not text:
        return None
    cleaned = text.strip()
    if len(cleaned) < _min_body_chars():
        return None
    return cleaned


def _apply_enriched_body(record: dict[str, Any], body: str) -> None:
    """Actualiza body y rawContent para Store + excerpts en Research Chat."""
    record["body"] = body
    title = str(record.get("title") or "").strip()
    record["rawContent"] = f"{title}\n\n{body}" if title else body


def enrich_article_bodies(
    records: list[dict[str, Any]],
    *,
    max_fetch: int | None = None,
) -> tuple[int, int]:
    """
    Enriquece records in-place con Article Body.
    Devuelve (intentados, exitosos).
    """
    if not _article_body_enabled():
        return 0, 0

    limit = _max_per_ingest() if max_fetch is None else max(0, max_fetch)
    if limit == 0:
        return 0, 0

    # Priorizar noticias sin body antes de aplicar el límite por ingesta.
    ordered = [r for r in records if needs_article_body(r)]
    ordered.extend(r for r in records if not needs_article_body(r))

    delay = _fetch_delay_seconds()
    attempted = 0
    enriched = 0

    for record in ordered:
        if attempted >= limit:
            break
        if not needs_article_body(record):
            continue

        url = str(record["canonical_url"]).strip()
        attempted += 1
        body = fetch_article_body(url)
        if body:
            _apply_enriched_body(record, body)
            enriched += 1

        if delay > 0 and attempted < limit:
            time.sleep(delay)

    return attempted, enriched


def backfill_article_bodies(limit: int = 30) -> int:
    """Extrae Article Body para Signals de noticias guardados sin cuerpo completo."""
    if not _article_body_enabled() or limit <= 0:
        return 0

    from scraper.store import fetch_signals_needing_body, update_signal_body

    signals = fetch_signals_needing_body(limit)
    if not signals:
        return 0

    delay = _fetch_delay_seconds()
    updated = 0

    for index, signal in enumerate(signals):
        url = str(signal.get("canonical_url") or "").strip()
        if not url or _domain(url) in SKIP_DOMAINS:
            continue

        body = fetch_article_body(url)
        if body:
            title = str(signal.get("title") or "").strip()
            raw_content = f"{title}\n\n{body}" if title else body
            update_signal_body(signal["id_str"], body=body, raw_content=raw_content)
            updated += 1

        if delay > 0 and index + 1 < len(signals):
            time.sleep(delay)

    return updated
