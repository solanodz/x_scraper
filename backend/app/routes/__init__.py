"""Routers de la API."""

from backend.app.routes.chat import router as chat_router
from backend.app.routes.ingest import router as ingest_router
from backend.app.routes.signals import router as signals_router

__all__ = ["chat_router", "ingest_router", "signals_router"]
