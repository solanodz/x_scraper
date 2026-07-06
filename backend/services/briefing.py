"""Briefing on-demand del Ticker Watch (servicio determinístico)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass

from backend.app.services.chat_repo import get_previous_briefing
from backend.app.services.ticker_watch_repo import list_watch, tables_ready
from backend.services.ask import AskStreamChunk
from backend.services.llm import hits_to_citations, stream_briefing_answer
from backend.services.market_data import Quote, fetch_quotes
from backend.services.recent_signals import get_recent_signals
from backend.services.research_steps import ResearchStepEvent

_EMPTY_WATCH_MESSAGE = (
    "Tu Ticker Watch está vacío. Agregá Tickers desde el botón Watch "
    "en el header para recibir un Briefing."
)

_PRIOR_BRIEFING_MAX_CHARS = 6000


@dataclass
class _BriefingSlice:
    symbol: str
    hits: list
    quote: Quote | None
    thesis: str | None = None
    prioridad_alta: bool = False


def _briefing_window_hours() -> int:
    raw = os.getenv("BRIEFING_WINDOW_HOURS", "24").strip()
    try:
        return max(1, min(int(raw), 168))
    except ValueError:
        return 24


def _load_watch_entries(user_id: str) -> list[dict]:
    if not tables_ready():
        return []
    return list_watch(user_id=user_id)


def _format_price_line(quote: Quote | None) -> str:
    if quote is None:
        return "Precio: no disponible"
    sign = "+" if quote.change_percent >= 0 else ""
    delayed = " (~15 min delayed)" if quote.delayed else ""
    return (
        f"Precio: ${quote.price:.2f} ({sign}{quote.change_percent:.2f}%){delayed}"
    )


def _format_signal_block(hit) -> str:
    return (
        f"Signal id={hit.id_str} @{hit.username} ({hit.published_at.isoformat()})\n"
        f"URL: {hit.url}\n"
        f"{hit.raw_content.strip()}"
    )


def _slice_sort_key(item: _BriefingSlice) -> tuple[int, int, float]:
    count = len(item.hits)
    change = abs(item.quote.change_percent) if item.quote else 0.0
    return (0 if count > 0 else 1, -count, -change)


def _mark_prioridad_alta(slices: list[_BriefingSlice]) -> None:
    marked = 0
    for item in slices:
        if marked >= 2:
            break
        if item.hits:
            item.prioridad_alta = True
            marked += 1


def _format_slice_block(item: _BriefingSlice, *, hours: int) -> str:
    lines = [f"## {item.symbol}"]
    if item.prioridad_alta:
        lines.append("prioridad_alta: true")
    if item.thesis:
        lines.append(f"Thesis: {item.thesis}")
    lines.append(_format_price_line(item.quote))
    if item.hits:
        lines.append("Signals recientes:")
        lines.extend(_format_signal_block(hit) for hit in item.hits)
    else:
        lines.append(f"Sin novedades en las últimas {hours}h")
    return "\n".join(lines)


def _build_context(slices: list[_BriefingSlice], *, hours: int) -> str:
    prioridad_alta = [item for item in slices if item.prioridad_alta]
    otras_con_novedad = [item for item in slices if item.hits and not item.prioridad_alta]
    sin_novedad = [item for item in slices if not item.hits]

    header = (
        f"# Resumen Ticker Watch (últimas {hours}h)\n"
        f"prioridad_alta: {len(prioridad_alta)} | "
        f"otras_con_novedad: {len(otras_con_novedad)} | "
        f"sin_novedad: {len(sin_novedad)}"
    )
    sections: list[str] = [header]

    if prioridad_alta:
        sections.append("# Prioridad alta")
        sections.extend(
            _format_slice_block(item, hours=hours) for item in prioridad_alta
        )

    if otras_con_novedad:
        sections.append("# Otras novedades")
        sections.extend(
            _format_slice_block(item, hours=hours) for item in otras_con_novedad
        )

    if sin_novedad:
        symbols = ", ".join(item.symbol for item in sin_novedad)
        sections.append(f"# Sin novedades\nTickers: {symbols}")

    return "\n\n".join(sections)


def _wrap_with_previous_briefing(context: str, previous: str) -> str:
    prior = previous.strip()[:_PRIOR_BRIEFING_MAX_CHARS]
    return (
        "--- Briefing anterior (referencia para delta) ---\n"
        f"{prior}\n"
        "--- Datos actuales ---\n"
        f"{context}"
    )


def iter_briefing_stream(
    user_id: str,
    *,
    history: list[dict] | None = None,
    exclude_session_id: str | None = None,
) -> Iterator[AskStreamChunk]:
    """Streamea pasos de recolección, síntesis y Citations del Briefing."""
    entries = _load_watch_entries(user_id)
    if not entries:
        yield _EMPTY_WATCH_MESSAGE
        yield []
        return

    hours = _briefing_window_hours()
    slices: list[_BriefingSlice] = []
    all_hits: list = []

    for entry in entries:
        symbol = entry["symbol"]
        thesis = entry.get("note")
        yield ResearchStepEvent(
            tool="briefing",
            label=f"Revisando {symbol}…",
            status="running",
        )
        hits = get_recent_signals(ticker=symbol, hours=hours, limit=10)
        quotes = fetch_quotes([symbol])
        quote = quotes[0] if quotes else None
        yield ResearchStepEvent(
            tool="briefing",
            label=f"Revisando {symbol}…",
            status="done",
        )
        slices.append(
            _BriefingSlice(
                symbol=symbol,
                hits=hits,
                quote=quote,
                thesis=thesis,
            )
        )
        all_hits.extend(hits)

    slices.sort(key=_slice_sort_key)
    _mark_prioridad_alta(slices)
    context = _build_context(slices, hours=hours)
    previous = get_previous_briefing(
        user_id=user_id,
        exclude_session_id=exclude_session_id,
    )
    if previous:
        context = _wrap_with_previous_briefing(context, previous)

    yield ResearchStepEvent(
        tool="synthesis",
        label="Redactando Briefing…",
        status="running",
    )

    for token in stream_briefing_answer(context, hours=hours, history=history):
        yield token

    yield ResearchStepEvent(
        tool="synthesis",
        label="Redactando Briefing…",
        status="done",
    )
    yield hits_to_citations(all_hits)
