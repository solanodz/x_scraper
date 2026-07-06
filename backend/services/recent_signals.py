"""Recuperación de Signals recientes por fecha (no semántica)."""

from __future__ import annotations

from backend.app.schemas import SignalSummary
from backend.app.services.feed_filters import feed_filters_from_query
from backend.app.services.signals_repo import list_recent_signals
from backend.services.types import SignalHit


def _content_for_hit(signal: SignalSummary) -> str:
    title = (signal.title or "").strip()
    if title:
        return title
    return (signal.raw_content or "").strip()


def get_recent_signals(
    *,
    ticker: str | None = None,
    source_type: str | None = None,
    hours: int | None = None,
    limit: int | None = None,
) -> list[SignalHit]:
    """Devuelve Signals ordenados por published_at DESC (como el Signal Feed)."""
    filters = feed_filters_from_query(
        ticker=ticker,
        source_type=source_type,
        since_hours=hours,
    )
    effective_limit = 10 if limit is None else max(1, min(int(limit), 50))
    summaries = list_recent_signals(limit=effective_limit, filters=filters)

    return [
        SignalHit(
            id_str=signal.id_str,
            username=signal.username,
            raw_content=_content_for_hit(signal),
            published_at=signal.published_at,
            source=signal.source,
            similarity=1.0,
            url=signal.url,
        )
        for signal in summaries
    ]
