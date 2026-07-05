"""Serialización de tweets de twscrape a registros de Signal."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from twscrape.models import Tweet


def serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if is_dataclass(value):
        return {k: serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    return value


def extract_article(tweet: Tweet) -> dict[str, Any] | None:
    """Extrae metadata de artículo cuando X adjunta una tarjeta de enlace."""
    card = tweet.card
    if card is None:
        return None

    card_type = getattr(card, "_type", type(card).__name__)
    article = {"card_type": card_type}

    for field in ("title", "description", "url", "vanityUrl"):
        if hasattr(card, field):
            article[field] = getattr(card, field)

    if article.keys() == {"card_type"}:
        return None
    return article


def tweet_to_record(tweet: Tweet, source: str) -> dict[str, Any]:
    record = serialize(tweet)
    record["source"] = source
    record["article"] = extract_article(tweet)
    return record
