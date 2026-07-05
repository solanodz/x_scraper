"""Relevance Score: pase LLM barato en Ingestion (score + tópico + tickers)."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-4o-mini"
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def _enabled() -> bool:
    load_dotenv()
    raw = os.getenv("RELEVANCE_SCORE_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _model() -> str:
    load_dotenv()
    return os.getenv("RELEVANCE_SCORE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _max_per_ingest() -> int:
    load_dotenv()
    raw = os.getenv("RELEVANCE_SCORE_MAX_PER_INGEST", "20").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 20


def _delay_seconds() -> float:
    load_dotenv()
    raw = os.getenv("RELEVANCE_SCORE_DELAY", "0.2").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.2


def feed_min_relevance() -> float | None:
    """Umbral mínimo para el Signal Feed. None = sin filtro por score."""
    load_dotenv()
    raw = os.getenv("RELEVANCE_SCORE_MIN", "0.35").strip()
    if not raw or raw.lower() in {"off", "none", "false"}:
        return None
    try:
        value = float(raw)
    except ValueError:
        return 0.35
    if value <= 0:
        return None
    return min(max(value, 0.0), 1.0)


def _client() -> OpenAI | None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _clip_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return min(max(score, 0.0), 1.0)


def _normalize_tickers(raw: Any) -> list[str]:
    if not raw:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out: list[str] = []
    for item in items:
        symbol = str(item).strip().lstrip("$").upper()
        if not symbol or not _TICKER_RE.match(symbol):
            continue
        if symbol not in out:
            out.append(symbol)
        if len(out) >= 8:
            break
    return out


def _record_text(record: dict[str, Any], *, max_chars: int = 1200) -> str:
    parts: list[str] = []
    title = str(record.get("title") or "").strip()
    summary = str(record.get("summary") or "").strip()
    body = str(record.get("body") or "").strip()
    raw = str(record.get("rawContent") or "").strip()

    if title:
        parts.append(f"Title: {title}")
    if summary and summary != title:
        parts.append(f"Summary: {summary}")
    if body:
        parts.append(f"Body: {body[:800]}")
    elif raw and raw != title:
        parts.append(f"Content: {raw[:800]}")

    text = "\n".join(parts).strip()
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def _needs_scoring(record: dict[str, Any]) -> bool:
    if _clip_score(record.get("relevance_score")) is None:
        return True
    topic = str(record.get("topic") or "").strip()
    tickers = _normalize_tickers(record.get("tickers"))
    return not topic or not tickers


def _score_one(client: OpenAI, record: dict[str, Any]) -> dict[str, Any] | None:
    text = _record_text(record)
    if not text:
        return None

    existing_tickers = _normalize_tickers(record.get("tickers"))
    source_type = str(record.get("source_type") or "x")
    username = str((record.get("user") or {}).get("username") or "").strip()

    system = (
        "You score financial-market relevance for a news terminal. "
        "Return strict JSON only with keys: relevance_score (number 0-1), "
        "topic (short phrase, 2-6 words), tickers (array of US stock symbols, max 5). "
        "relevance_score: 1 = highly relevant to markets/macro/investing; "
        "0 = off-topic noise (sports, entertainment, politics without market angle). "
        "Prefer empty tickers when unsure."
    )
    user = (
        f"source_type: {source_type}\n"
        f"author: {username or 'unknown'}\n"
        f"existing_tickers: {existing_tickers}\n\n"
        f"{text}"
    )

    try:
        response = client.chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception:
        return None

    score = _clip_score(data.get("relevance_score"))
    if score is None:
        return None

    topic = str(data.get("topic") or "").strip() or None
    suggested = _normalize_tickers(data.get("tickers"))
    tickers = existing_tickers or suggested

    return {
        "relevance_score": score,
        "topic": topic or record.get("topic"),
        "tickers": tickers or record.get("tickers") or [],
    }


def apply_relevance_scores(
    records: list[dict[str, Any]],
    *,
    max_score: int | None = None,
) -> tuple[int, int]:
    """
    Enriquece records in-place con Relevance Score (y tópico/tickers si faltan).
    Devuelve (intentados, exitosos).
    """
    if not _enabled():
        return 0, 0

    client = _client()
    if client is None:
        return 0, 0

    limit = _max_per_ingest() if max_score is None else max(0, max_score)
    if limit == 0:
        return 0, 0

    delay = _delay_seconds()
    attempted = 0
    scored = 0

    for record in records:
        if attempted >= limit:
            break
        if not _needs_scoring(record):
            continue

        attempted += 1
        result = _score_one(client, record)
        if result:
            record["relevance_score"] = result["relevance_score"]
            if not str(record.get("topic") or "").strip() and result.get("topic"):
                record["topic"] = result["topic"]
            if not _normalize_tickers(record.get("tickers")) and result.get("tickers"):
                record["tickers"] = result["tickers"]
                record["cashtags"] = [f"${t}" for t in result["tickers"]]
            scored += 1

        if delay > 0 and attempted < limit:
            time.sleep(delay)

    return attempted, scored
