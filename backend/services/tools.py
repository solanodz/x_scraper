"""Herramientas del Research Chat: Corpus + Market Data."""

from __future__ import annotations

import json
from typing import Any

from backend.services.market_data import fetch_quotes, get_watchlist
from backend.services.retrieval import excerpt, retrieve
from backend.services.types import SignalHit

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_corpus",
            "description": (
                "Busca Signals del Corpus (tweets y noticias scrapeadas de X) "
                "por similitud semántica. Usar para narrativa, catalizadores, "
                "sentimiento y contexto de Tickers o temas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta semántica en lenguaje natural.",
                    },
                    "ticker": {
                        "type": "string",
                        "description": "Opcional. Filtra por cashtag, ej. AAPL o $NVDA.",
                    },
                    "since_hours": {
                        "type": "integer",
                        "description": "Opcional. Ventana temporal en horas (ej. 24, 72).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de Signals a devolver (default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quotes",
            "description": (
                "Obtiene cotización actual (precio, cambio absoluto y %) "
                "de uno o más Tickers. Datos con delay ~15 min."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de tickers, ej. ['AAPL','NVDA'].",
                    },
                },
                "required": ["symbols"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_watchlist_quotes",
            "description": (
                "Cotizaciones de la Watchlist fija configurada en el Terminal. "
                "Útil para preguntas macro o comparar el panel principal."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _format_hits_for_tool(hits: list[SignalHit]) -> str:
    if not hits:
        return json.dumps(
            {"signals": [], "message": "Sin Signals relevantes en el Corpus."},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "signals": [
                {
                    "id_str": hit.id_str,
                    "username": hit.username,
                    "published_at": hit.published_at.isoformat(),
                    "url": hit.url,
                    "content": excerpt(hit.raw_content, 400),
                    "similarity": round(hit.similarity, 3),
                }
                for hit in hits
            ]
        },
        ensure_ascii=False,
    )


def _format_quotes_for_tool(quotes: list) -> str:
    if not quotes:
        return json.dumps(
            {"quotes": [], "message": "No se obtuvieron cotizaciones."},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "quotes": [
                {
                    "symbol": quote.symbol,
                    "price": round(quote.price, 2),
                    "change": round(quote.change, 2),
                    "change_percent": round(quote.change_percent, 2),
                    "delayed": quote.delayed,
                }
                for quote in quotes
            ]
        },
        ensure_ascii=False,
    )


def execute_tool(
    name: str,
    arguments: dict[str, Any],
) -> tuple[str, list[SignalHit]]:
    """Ejecuta una herramienta. Devuelve JSON para el LLM y hits del Corpus."""
    if name == "search_corpus":
        query = str(arguments.get("query", "")).strip()
        if not query:
            return json.dumps({"error": "query requerida"}), []
        ticker = arguments.get("ticker")
        since_hours = arguments.get("since_hours")
        limit = int(arguments.get("limit") or 10)
        limit = max(1, min(limit, 15))
        hits = retrieve(
            query,
            limit=limit,
            ticker=str(ticker) if ticker else None,
            since_hours=int(since_hours) if since_hours else None,
        )
        return _format_hits_for_tool(hits), hits

    if name == "get_quotes":
        raw_symbols = arguments.get("symbols") or []
        symbols = [str(s).strip() for s in raw_symbols if str(s).strip()]
        if not symbols:
            return json.dumps({"error": "symbols requerido"}), []
        quotes = fetch_quotes(symbols)
        return _format_quotes_for_tool(quotes), []

    if name == "get_watchlist_quotes":
        symbols = get_watchlist()
        quotes = fetch_quotes(symbols)
        payload = json.loads(_format_quotes_for_tool(quotes))
        payload["watchlist"] = symbols
        return json.dumps(payload, ensure_ascii=False), []

    return json.dumps({"error": f"herramienta desconocida: {name}"}), []


def dedupe_hits(hits: list[SignalHit]) -> list[SignalHit]:
    seen: set[str] = set()
    unique: list[SignalHit] = []
    for hit in hits:
        if hit.id_str in seen:
            continue
        seen.add(hit.id_str)
        unique.append(hit)
    return unique
