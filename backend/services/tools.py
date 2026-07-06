"""Herramientas del Research Chat: Corpus + Market Data."""

from __future__ import annotations

import json
from typing import Any

from backend.app.schemas import SignalDetail
from backend.app.services.signals_repo import get_signal
from backend.services.corpus_stats import get_corpus_stats
from backend.services.market_data import fetch_price_history, fetch_quotes
from backend.services.recent_signals import get_recent_signals
from backend.services.retrieval import excerpt, retrieve
from backend.services.ticker_catalog import get_quote_strip_symbols, resolve_ticker_input
from backend.services.types import SignalHit

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_corpus",
            "description": (
                "Busca Signals del Corpus (tweets y noticias scrapeadas de X) "
                "por similitud semántica, con fallback por keywords en "
                "título/resumen cuando no hay hits vectoriales. Usar para "
                "narrativa, catalizadores, sentimiento y contexto de Tickers o temas."
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
                        "description": (
                            "Opcional. Ticker o nombre de empresa "
                            "(ej. INTC, Intel, NVDA)."
                        ),
                    },
                    "since_hours": {
                        "type": "integer",
                        "description": "Opcional. Ventana temporal en horas (ej. 24, 72).",
                    },
                    "source_type": {
                        "type": "string",
                        "description": (
                            "Opcional. Filtra por fuente: x, rss, marketaux, "
                            "alpha_vantage o news (rss+marketaux+alpha_vantage)."
                        ),
                    },
                    "min_relevance": {
                        "type": "number",
                        "description": (
                            "Opcional. Score mínimo de relevancia (0–1). "
                            "Ej. 0.5 para excluir ruido."
                        ),
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
            "name": "get_recent_signals",
            "description": (
                "Lista los Signals más recientes del Corpus ordenados por fecha "
                "(published_at DESC), como el Signal Feed. Usar para "
                "'última noticia', 'noticias recientes', 'qué pasó hoy', "
                "'what happened today' o la noticia más nueva de un Ticker. "
                "Preferir sobre search_corpus cuando la Query pida lo más reciente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": (
                            "Opcional. Ticker o nombre de empresa "
                            "(ej. MSFT, Microsoft, INTC, Intel)."
                        ),
                    },
                    "source_type": {
                        "type": "string",
                        "description": (
                            "Opcional. Filtra por fuente: x, rss, marketaux, "
                            "alpha_vantage o news (rss+marketaux+alpha_vantage)."
                        ),
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Opcional. Ventana temporal en horas (ej. 24, 72).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de Signals a devolver (default 10, max 50).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_signal_detail",
            "description": (
                "Obtiene el contenido completo de un Signal por id_str: "
                "título, resumen, cuerpo del artículo, tickers, tópico y URL. "
                "Usar para lectura profunda cuando search_corpus o "
                "get_recent_signals identifican un Signal relevante."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id_str": {
                        "type": "string",
                        "description": "Identificador del Signal (id_str).",
                    },
                },
                "required": ["id_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "corpus_stats",
            "description": (
                "Estadísticas agregadas del Corpus: volumen por fuente, "
                "tópicos más frecuentes y tickers más mencionados en una ventana "
                "temporal. Útil para tendencias, panorama macro o actividad "
                "reciente de un Ticker."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Ventana temporal en horas (default 168 = 7 días).",
                    },
                    "ticker": {
                        "type": "string",
                        "description": (
                            "Opcional. Filtra estadísticas a Signals de un Ticker "
                            "o nombre de empresa."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Máximo de tópicos/tickers en el ranking (default 10)."
                        ),
                    },
                },
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
                "Cotizaciones del carrusel Quote Strip (tickers activos en el "
                "Corpus, dinámico). Útil para panorama macro o comparar el panel "
                "principal del Terminal."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": (
                "Historial de precios de un Ticker (OHLC diario vía yfinance). "
                "Devuelve precio inicial/final, cambio %, máximo, mínimo y "
                "cantidad de puntos. Usar para tendencias de mercado y "
                "comparaciones temporales."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": (
                            "Ticker o nombre de empresa (ej. NVDA, NVIDIA, INTC)."
                        ),
                    },
                    "period": {
                        "type": "string",
                        "description": (
                            "Ventana histórica: 1mo (default), 3mo, 6mo o 1y."
                        ),
                    },
                },
                "required": ["symbol"],
            },
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


def _tickers_from_detail(detail: SignalDetail) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    payload_tickers = detail.payload.get("tickers") if detail.payload else []
    for raw in payload_tickers or []:
        sym = str(raw).strip().lstrip("$").upper()
        if sym and sym not in seen:
            seen.add(sym)
            tickers.append(sym)
    for tag in detail.cashtags:
        sym = str(tag).strip().lstrip("$").upper()
        if sym and sym not in seen:
            seen.add(sym)
            tickers.append(sym)
    return tickers


def _detail_to_hit(detail: SignalDetail) -> SignalHit:
    content = (detail.title or "").strip() or (detail.raw_content or "").strip()
    return SignalHit(
        id_str=detail.id_str,
        username=detail.username,
        raw_content=content,
        published_at=detail.published_at,
        source=detail.source,
        similarity=1.0,
        url=detail.url,
    )


def _format_signal_detail(detail: SignalDetail) -> dict[str, Any]:
    body = detail.body or detail.summary or detail.raw_content or ""
    return {
        "id_str": detail.id_str,
        "title": detail.title,
        "summary": detail.summary,
        "body": excerpt(body, 2000),
        "tickers": _tickers_from_detail(detail),
        "topic": detail.topic,
        "relevance_score": detail.relevance_score,
        "source_type": detail.source_type,
        "published_at": detail.published_at.isoformat(),
        "url": detail.url,
    }


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
        source_type = arguments.get("source_type")
        min_relevance = arguments.get("min_relevance")
        limit = int(arguments.get("limit") or 10)
        limit = max(1, min(limit, 15))
        hits = retrieve(
            query,
            limit=limit,
            ticker=resolve_ticker_input(str(ticker)) if ticker else None,
            since_hours=int(since_hours) if since_hours else None,
            source_type=str(source_type) if source_type else None,
            min_relevance=float(min_relevance) if min_relevance is not None else None,
        )
        return _format_hits_for_tool(hits), hits

    if name == "get_recent_signals":
        ticker = arguments.get("ticker")
        source_type = arguments.get("source_type")
        hours = arguments.get("hours")
        limit = int(arguments.get("limit") or 10)
        limit = max(1, min(limit, 50))
        hits = get_recent_signals(
            ticker=resolve_ticker_input(str(ticker)) if ticker else None,
            source_type=str(source_type) if source_type else None,
            hours=int(hours) if hours else None,
            limit=limit,
        )
        return _format_hits_for_tool(hits), hits

    if name == "get_signal_detail":
        id_str = str(arguments.get("id_str", "")).strip()
        if not id_str:
            return json.dumps({"error": "id_str requerido"}), []
        detail = get_signal(id_str)
        if detail is None:
            return json.dumps({"error": f"Signal no encontrado: {id_str}"}), []
        hit = _detail_to_hit(detail)
        return json.dumps(_format_signal_detail(detail), ensure_ascii=False), [hit]

    if name == "corpus_stats":
        hours = int(arguments.get("hours") or 168)
        ticker = arguments.get("ticker")
        limit = int(arguments.get("limit") or 10)
        stats = get_corpus_stats(
            hours=hours,
            ticker=resolve_ticker_input(str(ticker)) if ticker else None,
            limit=limit,
        )
        return json.dumps(stats, ensure_ascii=False), []

    if name == "get_quotes":
        raw_symbols = arguments.get("symbols") or []
        symbols = []
        for s in raw_symbols:
            resolved = resolve_ticker_input(str(s).strip())
            if resolved:
                symbols.append(resolved)
            elif str(s).strip():
                symbols.append(str(s).strip().lstrip("$").upper())
        if not symbols:
            return json.dumps({"error": "symbols requerido"}), []
        quotes = fetch_quotes(symbols)
        return _format_quotes_for_tool(quotes), []

    if name == "get_watchlist_quotes":
        symbols = get_quote_strip_symbols()
        quotes = fetch_quotes(symbols)
        payload = json.loads(_format_quotes_for_tool(quotes))
        payload["watchlist"] = symbols
        return json.dumps(payload, ensure_ascii=False), []

    if name == "get_price_history":
        raw_symbol = str(arguments.get("symbol", "")).strip()
        if not raw_symbol:
            return json.dumps({"error": "symbol requerido"}), []
        resolved = resolve_ticker_input(raw_symbol)
        symbol = resolved or raw_symbol.lstrip("$").upper()
        period = str(arguments.get("period") or "1mo").strip()
        result = fetch_price_history(symbol, period=period)
        return json.dumps(result, ensure_ascii=False), []

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
