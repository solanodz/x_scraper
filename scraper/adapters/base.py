"""Interfaz base para Source Adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SourceAdapter(ABC):
    """Normaliza una fuente externa a registros dict compatibles con store.record_to_params."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre legible del adapter."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Valor de source_type persistido en el Store."""

    @abstractmethod
    async def fetch(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Obtiene Signals normalizados desde la fuente."""
