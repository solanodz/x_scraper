"""Article Enrichment: extrae Article Body desde canonical_url (trafilatura).

También parsea og:image del mismo HTML descargado (sin fetch extra) cuando falta image_url.
"""

from __future__ import annotations

import os
import re
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

# meta property/content en cualquier orden (HTML ya descargado por trafilatura).
_OG_IMAGE_RE = re.compile(
    r"<meta\b[^>]*\bproperty\s*=\s*[\"']og:image[\"'][^>]*\bcontent\s*=\s*[\"']([^\"']+)[\"']"
    r"|"
    r"<meta\b[^>]*\bcontent\s*=\s*[\"']([^\"']+)[\"'][^>]*\bproperty\s*=\s*[\"']og:image[\"']",
    re.IGNORECASE,
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


def extract_og_image(html: str) -> str | None:
    """Best-effort og:image desde HTML ya descargado (sin request extra)."""
    if not html:
        return None
    match = _OG_IMAGE_RE.search(html)
    if not match:
        return None
    url = (match.group(1) or match.group(2) or "").strip()
    if not url or not url.startswith(("http://", "https://")):
        return None
    return url


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


def fetch_article(url: str) -> tuple[str | None, str | None]:
    """
    Descarga una vez: (Article Body, og:image).
    Body None si falla/paywall; image_url None si no hay meta og:image.
    """
    try:
        import trafilatura
    except ImportError:
        return None, None

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, None
        og_image = extract_og_image(downloaded)
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
    except Exception:
        return None, None

    body: str | None = None
    if text:
        cleaned = text.strip()
        if len(cleaned) >= _min_body_chars():
            body = cleaned
    return body, og_image


def fetch_article_body(url: str) -> str | None:
    """Best-effort: descarga y extrae texto con trafilatura. None si falla o paywall."""
    body, _ = fetch_article(url)
    return body


def _apply_enriched_body(record: dict[str, Any], body: str) -> None:
    """Actualiza body y rawContent para Store + excerpts en Research Chat."""
    record["body"] = body
    title = str(record.get("title") or "").strip()
    record["rawContent"] = f"{title}\n\n{body}" if title else body


def _apply_image_url(record: dict[str, Any], image_url: str | None) -> None:
    if not image_url or record.get("image_url"):
        return
    record["image_url"] = image_url


def enrich_article_bodies(
    records: list[dict[str, Any]],
    *,
    max_fetch: int | None = None,
) -> tuple[int, int]:
    """
    Enriquece records in-place con Article Body (+ og:image si falta image_url).
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
        body, og_image = fetch_article(url)
        if body:
            _apply_enriched_body(record, body)
            enriched += 1
        _apply_image_url(record, og_image)

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

        body, og_image = fetch_article(url)
        if body:
            title = str(signal.get("title") or "").strip()
            raw_content = f"{title}\n\n{body}" if title else body
            update_signal_body(
                signal["id_str"],
                body=body,
                raw_content=raw_content,
                image_url=og_image,
            )
            updated += 1

        if delay > 0 and index + 1 < len(signals):
            time.sleep(delay)

    return updated
