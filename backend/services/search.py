"""Core Service: búsqueda semántica sobre el Corpus."""

from __future__ import annotations

from backend.services.retrieval import retrieve
from backend.services.types import SignalHit


def search(query: str, limit: int = 10) -> list[SignalHit]:
    """Busca Signals relevantes ordenados por similitud semántica."""
    return retrieve(query, limit=limit)
