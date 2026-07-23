"""Herramientas del Research Chat: Corpus + Market Data + Dossier + FX."""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from typing import Any

from backend.app.schemas import SignalDetail
from backend.app.services.signals_repo import get_signal
from backend.services.corpus_stats import get_corpus_stats
from backend.services.fx import get_fx_quotes, is_fx_currency_code
from backend.services.market_data import fetch_price_history, fetch_quotes
from backend.services.recent_signals import get_recent_signals
from backend.services.retrieval import excerpt, retrieve
from backend.services.ticker_catalog import get_quote_strip_symbols, resolve_ticker_input
from backend.services.types import SignalHit

_operator_id_var: ContextVar[str | None] = ContextVar(
    "research_operator_id",
    default=None,
)

PRICE_CHART_MAX_CANDLES = 90

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
                "título, resumen, Article Body (si hay), tickers, tópico y URL. "
                "Indica content_depth (full_body vs summary_only). "
                "Usar para claims profundos antes de sintetizar: abrir los id_str "
                "clave que devolvió search_corpus o get_recent_signals."
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
                "reciente de un Ticker. Devuelve JSON determinístico para tablas."
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
                "de uno o más Tickers (equities/crypto). Datos con delay ~15 min. "
                "No usar para FX / dólar Argentina (usar get_fx_quotes)."
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
                "Devuelve precio inicial/final, cambio %, máximo, mínimo, "
                "cantidad de puntos y velas (cap 90) para Chart card. "
                "Usar para tendencias de mercado y comparaciones temporales."
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
    {
        "type": "function",
        "function": {
            "name": "get_dossier",
            "description": (
                "Lee el Dossier persistente más reciente del Operator para un "
                "Ticker del Watch (bloques: panorama, narrativa, sentimiento, "
                "macro, fundamentals, lectura integrada). Usar cuando la Query "
                "pida el Dossier, análisis integral previo, o base narrativa "
                "antes de complementar con Corpus reciente / Market Data. "
                "Requiere Operator autenticado en sesión; si no hay Dossier, "
                "declararlo y caer a tools del Corpus."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Ticker o nombre (ej. NVDA, NVIDIA).",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fx_quotes",
            "description": (
                "Cotizaciones FX (divisas), separadas de Quotes de equities. "
                "scope=ars_usd: dólar Argentina (oficial, blue, MEP, CCL, tarjeta "
                "si la fuente los expone) vía dolarapi. "
                "scope=pair: pares ECB vía Frankfurter (EUR/USD, USD/BRL, etc.). "
                "Nunca inventa números; incluye source y timestamp."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "description": (
                            "ars_usd (default) para dólar Argentina, "
                            "o pair para un par / lista de pares."
                        ),
                    },
                    "base": {
                        "type": "string",
                        "description": "Moneda base (ej. EUR) cuando scope=pair.",
                    },
                    "quote": {
                        "type": "string",
                        "description": "Moneda cotizada (ej. USD) cuando scope=pair.",
                    },
                    "pairs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Opcional. Lista de pares ej. ['EUR/USD','USD/BRL'] "
                            "cuando scope=pair."
                        ),
                    },
                },
            },
        },
    },
]


def set_research_operator_id(operator_id: str | None) -> Token:
    """Fija el Operator id para tools que lo requieren (get_dossier)."""
    return _operator_id_var.set(operator_id)


def reset_research_operator_id(token: Token) -> None:
    """Resetea el ContextVar; no falla si el Token es de otro Context (SSE/thread)."""
    try:
        _operator_id_var.reset(token)
    except ValueError:
        # Generators streameados vía run_in_executor cambian de Context entre next().
        _operator_id_var.set(None)


def get_research_operator_id() -> str | None:
    return _operator_id_var.get()


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


def _content_depth(detail: SignalDetail) -> str:
    """full_body si hay Article Body material; summary_only si es resumen/corto."""
    body = (detail.body or "").strip()
    summary = (detail.summary or "").strip()
    if not body:
        return "summary_only"
    if summary and body == summary:
        return "summary_only"
    if len(body) < 200:
        return "summary_only"
    return "full_body"


def _format_signal_detail(detail: SignalDetail) -> dict[str, Any]:
    body = detail.body or detail.summary or detail.raw_content or ""
    depth = _content_depth(detail)
    payload: dict[str, Any] = {
        "id_str": detail.id_str,
        "title": detail.title,
        "summary": detail.summary,
        "body": excerpt(body, 2000),
        "content_depth": depth,
        "tickers": _tickers_from_detail(detail),
        "topic": detail.topic,
        "relevance_score": detail.relevance_score,
        "source_type": detail.source_type,
        "published_at": detail.published_at.isoformat(),
        "url": detail.url,
    }
    if depth == "summary_only":
        payload["note"] = (
            "summary-only / posible paywall: no hay Article Body completo; "
            "no fingir profundidad de artículo full."
        )
    return payload


def _condense_dossier(row: dict[str, Any]) -> dict[str, Any]:
    content = row.get("content") if isinstance(row.get("content"), dict) else {}
    blocks = content.get("blocks") if isinstance(content.get("blocks"), dict) else {}
    condensed_blocks: dict[str, str] = {}
    for key, value in blocks.items():
        if isinstance(value, str) and value.strip():
            text = value.strip()
            condensed_blocks[key] = text if len(text) <= 1200 else text[:1200] + "…"
    created_at = row.get("created_at")
    return {
        "symbol": row.get("symbol"),
        "dossier_version_id": row.get("id"),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "blocks": condensed_blocks,
        "message": (
            "Dossier encontrado. Usá estos bloques como base; "
            "complementá con Corpus reciente / Market Data."
            if condensed_blocks
            else "Dossier sin bloques de texto."
        ),
    }


def _normalize_chart_candles(candles: Any) -> list[dict[str, Any]]:
    """Normaliza velas Market Data (`date`) al contrato FE (`t`)."""
    if not isinstance(candles, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in candles:
        if not isinstance(raw, dict):
            continue
        t = raw.get("t") or raw.get("date")
        if t is None:
            continue
        try:
            out.append(
                {
                    "t": str(t),
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _fx_not_equity_error(symbol: str) -> str:
    return json.dumps(
        {
            "error": f"{symbol} es una divisa (FX), no un Ticker de equity",
            "hint": (
                "Usá get_fx_quotes (scope=ars_usd para dólar Argentina; "
                "scope=pair para EUR/USD etc.). No abras Dossier/Chart Plan."
            ),
            "symbol": symbol,
        },
        ensure_ascii=False,
    )


def _price_chart_artifact(result: dict[str, Any]) -> dict[str, Any] | None:
    if result.get("error"):
        return None
    symbol = str(result.get("symbol") or "").strip().upper()
    if is_fx_currency_code(symbol):
        return None
    candles = _normalize_chart_candles(result.get("candles"))
    closes = result.get("closes")
    if not closes and candles:
        closes = [float(c["close"]) for c in candles]
    if not candles and not closes:
        return None
    return {
        "type": "price_chart",
        "symbol": result.get("symbol"),
        "period": result.get("period"),
        "interval": result.get("interval") or "1d",
        "candles": candles,
        "closes": closes,
        "start_price": result.get("start_price"),
        "end_price": result.get("end_price"),
        "change_percent": result.get("change_percent"),
    }


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    operator_id: str | None = None,
) -> tuple[str, list[SignalHit]]:
    """Ejecuta una herramienta. Devuelve JSON para el LLM y hits del Corpus."""
    effective_operator = operator_id or get_research_operator_id()

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
        payload = {
            "tool": "corpus_stats",
            "label": "corpus_stats JSON (números determinísticos para tablas GFM)",
            **stats,
        }
        return json.dumps(payload, ensure_ascii=False), []

    if name == "get_quotes":
        raw_symbols = arguments.get("symbols") or []
        symbols = []
        rejected_fx: list[str] = []
        for s in raw_symbols:
            raw = str(s).strip()
            if not raw:
                continue
            candidate = raw.lstrip("$").upper()
            if is_fx_currency_code(candidate):
                rejected_fx.append(candidate)
                continue
            resolved = resolve_ticker_input(raw)
            if resolved:
                symbols.append(resolved)
            else:
                # Solo símbolos que pasaron resolución (no inventar equities FX).
                continue
        if rejected_fx and not symbols:
            return _fx_not_equity_error(rejected_fx[0]), []
        if not symbols:
            return json.dumps({"error": "symbols requerido"}), []
        quotes = fetch_quotes(symbols)
        payload = json.loads(_format_quotes_for_tool(quotes))
        if rejected_fx:
            payload["rejected_fx"] = rejected_fx
            payload["fx_hint"] = "Para divisas usá get_fx_quotes"
        return json.dumps(payload, ensure_ascii=False), []

    if name == "get_watchlist_quotes":
        symbols = [
            s for s in get_quote_strip_symbols() if not is_fx_currency_code(s)
        ]
        quotes = fetch_quotes(symbols)
        payload = json.loads(_format_quotes_for_tool(quotes))
        payload["watchlist"] = symbols
        return json.dumps(payload, ensure_ascii=False), []

    if name == "get_price_history":
        raw_symbol = str(arguments.get("symbol", "")).strip()
        if not raw_symbol:
            return json.dumps({"error": "symbol requerido"}), []
        candidate = raw_symbol.lstrip("$").upper()
        if is_fx_currency_code(candidate):
            return _fx_not_equity_error(candidate), []
        resolved = resolve_ticker_input(raw_symbol)
        if not resolved:
            return json.dumps(
                {
                    "error": f"Ticker no reconocido: {raw_symbol}",
                    "hint": "Si es FX (dólar/euro), usá get_fx_quotes",
                },
                ensure_ascii=False,
            ), []
        symbol = resolved
        period = str(arguments.get("period") or "1mo").strip()
        result = fetch_price_history(
            symbol,
            period=period,
            include_candles=True,
            max_candles=PRICE_CHART_MAX_CANDLES,
        )
        return json.dumps(result, ensure_ascii=False), []

    if name == "get_dossier":
        raw_symbol = str(arguments.get("symbol", "")).strip()
        if not raw_symbol:
            return json.dumps({"error": "symbol requerido"}), []
        if is_fx_currency_code(raw_symbol):
            return _fx_not_equity_error(raw_symbol.lstrip("$").upper()), []
        if not effective_operator:
            return json.dumps(
                {
                    "error": "operator_id no disponible",
                    "message": (
                        "No se puede leer el Dossier sin Operator. "
                        "Usá Corpus / Market Data."
                    ),
                },
                ensure_ascii=False,
            ), []
        from backend.app.services.dossier_repo import get_latest as get_latest_dossier

        resolved = resolve_ticker_input(raw_symbol)
        symbol = resolved or raw_symbol.lstrip("$").upper()
        row = get_latest_dossier(user_id=effective_operator, symbol=symbol)
        if row is None:
            return json.dumps(
                {
                    "symbol": symbol,
                    "found": False,
                    "message": (
                        f"No hay Dossier persistido para {symbol}. "
                        "Declaralo con honestidad y complementá con "
                        "get_recent_signals / search_corpus / get_quotes."
                    ),
                },
                ensure_ascii=False,
            ), []
        payload = _condense_dossier(row)
        payload["found"] = True
        return json.dumps(payload, ensure_ascii=False), []

    if name == "get_fx_quotes":
        scope = str(arguments.get("scope") or "ars_usd").strip()
        base = arguments.get("base")
        quote = arguments.get("quote")
        pairs = arguments.get("pairs")
        pair_list = None
        if isinstance(pairs, list):
            pair_list = [str(p) for p in pairs]
        elif pairs:
            pair_list = [str(pairs)]
        result = get_fx_quotes(
            scope=scope,
            base=str(base) if base else None,
            quote=str(quote) if quote else None,
            pairs=pair_list,
        )
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


def build_price_chart_artifact(result_json: str) -> dict[str, Any] | None:
    """Parsea resultado de get_price_history y arma artefacto Chart card."""
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(result, dict):
        return None
    return _price_chart_artifact(result)
