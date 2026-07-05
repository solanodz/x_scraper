"""Tipos compartidos de Core Services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SignalHit:
    """Signal recuperado del Vector Index con score de similitud."""

    id_str: str
    username: str
    raw_content: str
    published_at: datetime
    source: str
    similarity: float
    url: str


@dataclass
class Citation:
    """Referencia obligatoria a un Signal fuente."""

    id_str: str
    username: str
    url: str
    excerpt: str


@dataclass
class AskResult:
    """Respuesta del Research Chat con Citations."""

    answer: str
    citations: list[Citation]
