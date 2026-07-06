"""Eventos de progreso del Research Agent para el Chat Stream."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

TOOL_STEP_LABELS: dict[str, str] = {
    "search_corpus": "Buscando en el Corpus",
    "get_recent_signals": "Consultando noticias recientes",
    "get_signal_detail": "Leyendo artículo",
    "corpus_stats": "Analizando tendencias del Corpus",
    "get_quotes": "Obteniendo cotizaciones",
    "get_watchlist_quotes": "Consultando panel de mercado",
    "get_price_history": "Cargando historial de precios",
}


@dataclass(frozen=True)
class ResearchStepEvent:
    """Paso visible del agente (tool o fase de síntesis)."""

    tool: str
    label: str
    status: str  # running | done

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class GatherResult:
    """Resultado de la fase de research antes de la síntesis."""

    context: str
    hits: list[Any]
    market_sections: list[str] | None = None
    corpus_sections: list[str] | None = None


def format_tool_step_label(tool_name: str, arguments: dict[str, Any]) -> str:
    """Etiqueta legible para el Operator."""
    base = TOOL_STEP_LABELS.get(tool_name, tool_name.replace("_", " "))
    args = {k: v for k, v in arguments.items() if v is not None}

    if tool_name == "search_corpus":
        query = str(args.get("query", "")).strip()
        if query:
            snippet = query if len(query) <= 48 else query[:45] + "…"
            return f'{base}: "{snippet}"'
        if args.get("ticker"):
            return f"{base} ({args['ticker']})"

    if tool_name == "get_recent_signals":
        parts: list[str] = []
        if args.get("ticker"):
            parts.append(str(args["ticker"]))
        if args.get("hours"):
            parts.append(f"{args['hours']}h")
        if parts:
            return f"{base} ({', '.join(parts)})"

    if tool_name == "get_signal_detail" and args.get("id_str"):
        sid = str(args["id_str"])
        short = sid if len(sid) <= 20 else sid[:17] + "…"
        return f"{base} ({short})"

    if tool_name == "get_quotes" and args.get("symbols"):
        symbols = [str(s) for s in args["symbols"][:4]]
        return f"{base} ({', '.join(symbols)})"

    if tool_name == "get_price_history":
        sym = args.get("symbol")
        period = args.get("period")
        if sym and period:
            return f"{base} ({sym}, {period})"
        if sym:
            return f"{base} ({sym})"

    if tool_name == "corpus_stats":
        if args.get("ticker"):
            return f"{base} ({args['ticker']})"
        if args.get("hours"):
            return f"{base} ({args['hours']}h)"

    return base
