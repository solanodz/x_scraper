"""Story Cluster: dedup cross-source por URL canónica + similitud de embedding."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

from dotenv import load_dotenv

SKIP_URL_CLUSTER_DOMAINS = frozenset(
    {
        "news.google.com",
        "www.news.google.com",
    }
)

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "mod",
        "ref",
        "at_medium",
        "at_campaign",
        "ncid",
        "src",
    }
)


def _enabled() -> bool:
    load_dotenv()
    raw = os.getenv("STORY_CLUSTER_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def similarity_threshold() -> float:
    load_dotenv()
    raw = os.getenv("STORY_CLUSTER_SIMILARITY", "0.88").strip()
    try:
        return min(max(float(raw), 0.5), 0.99)
    except ValueError:
        return 0.88


def lookback_hours() -> int:
    load_dotenv()
    raw = os.getenv("STORY_CLUSTER_LOOKBACK_HOURS", "168").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 168


def normalize_story_url(url: str) -> str | None:
    """Normaliza URL para dedup (host + path, sin tracking params)."""
    raw = str(url or "").strip()
    if not raw.startswith(("http://", "https://")):
        return None

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if not host or host in SKIP_URL_CLUSTER_DOMAINS:
        return None

    if host.startswith("www."):
        host = host[4:]

    path = (parsed.path or "").rstrip("/") or "/"
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query = "&".join(f"{k}={v}" for k, v in sorted(kept))
    normalized = urlunparse(("", host, path, "", query, ""))
    return normalized.lstrip("/")


def cluster_id_from_url(url: str) -> str | None:
    normalized = normalize_story_url(url)
    if not normalized:
        return None
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"cluster:url:{digest}"


def _story_url_from_record(record: dict[str, Any]) -> str | None:
    canonical = str(record.get("canonical_url") or "").strip()
    if canonical:
        return canonical

    payload = record.get("payload")
    if isinstance(payload, dict):
        for key in ("url", "canonical_url"):
            value = str(payload.get(key) or "").strip()
            if value.startswith("http"):
                return value

    article = record.get("article")
    if isinstance(article, dict):
        value = str(article.get("url") or "").strip()
        if value.startswith("http"):
            return value

    return None


def assign_url_clusters(records: list[dict[str, Any]]) -> int:
    """Asigna cluster_id por URL canónica. Devuelve cuántos records quedaron agrupados."""
    if not _enabled():
        return 0

    assigned = 0
    for record in records:
        url = _story_url_from_record(record)
        if not url:
            continue
        cluster_id = cluster_id_from_url(url)
        if not cluster_id:
            continue
        record["cluster_id"] = cluster_id
        assigned += 1
    return assigned


def _format_embedding(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.8g}" for value in embedding) + "]"


def find_similar_signal(
    embedding: list[float],
    *,
    exclude_id_str: str | None = None,
) -> dict[str, Any] | None:
    """Busca un Signal similar reciente en el Store (near-duplicate)."""
    from scraper.store import connect

    vector = _format_embedding(embedding)
    params: dict[str, Any] = {
        "query_vector": vector,
        "min_similarity": similarity_threshold(),
        "lookback_hours": lookback_hours(),
        "exclude_id": exclude_id_str or "",
    }

    sql = """
        SELECT
            id_str,
            cluster_id,
            source_type,
            username,
            1 - (embedding <=> %(query_vector)s::vector) AS similarity
        FROM signals
        WHERE embedding IS NOT NULL
          AND published_at >= now() - make_interval(hours => %(lookback_hours)s)
          AND (%(exclude_id)s = '' OR id_str <> %(exclude_id)s)
        ORDER BY embedding <=> %(query_vector)s::vector
        LIMIT 5
    """

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            for row in cur.fetchall():
                id_str, cluster_id, source_type, username, similarity = row
                if float(similarity) < similarity_threshold():
                    continue
                return {
                    "id_str": id_str,
                    "cluster_id": cluster_id,
                    "source_type": source_type,
                    "username": username,
                    "similarity": float(similarity),
                }
    return None


def _story_cluster_id(seed_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9:_-]", "", seed_id)[:48]
    return f"cluster:story:{safe}"


def apply_embedding_clusters(
    records: list[dict[str, Any]],
    embeddings: list[list[float]] | None,
) -> tuple[int, list[tuple[str, str]]]:
    """
    Fusiona near-duplicates por embedding. Devuelve (merged_count, db_updates).
    db_updates: pares (id_str, cluster_id) para filas existentes a actualizar.
    """
    if not _enabled() or not embeddings or len(embeddings) != len(records):
        return 0, []

    merged = 0
    db_updates: list[tuple[str, str]] = []

    for record, embedding in zip(records, embeddings):
        if not embedding:
            continue

        exclude = str(record.get("id_str") or "")
        match = find_similar_signal(embedding, exclude_id_str=exclude)
        if not match:
            continue

        match_cluster = match.get("cluster_id")
        if match_cluster:
            cluster_id = str(match_cluster)
        else:
            cluster_id = _story_cluster_id(str(match["id_str"]))
            db_updates.append((str(match["id_str"]), cluster_id))

        if record.get("cluster_id") != cluster_id:
            record["cluster_id"] = cluster_id
            merged += 1

    return merged, db_updates


def update_cluster_ids(updates: list[tuple[str, str]]) -> int:
    """Persiste cluster_id en filas existentes del Store."""
    if not updates:
        return 0

    from scraper.store import connect

    affected = 0
    with connect() as conn:
        with conn.cursor() as cur:
            for id_str, cluster_id in updates:
                cur.execute(
                    """
                    UPDATE signals
                    SET cluster_id = %(cluster_id)s
                    WHERE id_str = %(id_str)s
                      AND (cluster_id IS NULL OR cluster_id <> %(cluster_id)s)
                    """,
                    {"id_str": id_str, "cluster_id": cluster_id},
                )
                affected += cur.rowcount
    return affected
