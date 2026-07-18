"""Dossier: análisis integral persistente por Ticker (servicio determinístico)."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

from backend.app.db import connect
from backend.app.services.ticker_watch_repo import list_watch, tables_ready
from backend.services.corpus_stats import get_corpus_stats
from backend.services.llm import (
    hits_to_citations,
    stream_dossier_answer,
    synthesize_dossier_answer,
)
from backend.services.market_data import Quote, fetch_quotes
from backend.services.recent_signals import get_recent_signals
from backend.services.research_steps import ResearchStepEvent
from backend.services.retrieval import retrieve
from backend.services.ticker_catalog import append_ticker_match_conditions
from backend.services.types import SignalHit

URGENT_HOURS = 168  # 7d
CONTEXT_HOURS = 720  # 30d
MACRO_SINCE_HOURS = 720
MACRO_LIMIT = 8

_DOSSIER_BLOCK_SPECS: tuple[tuple[str, str], ...] = (
    ("panorama_mercado", "Panorama de mercado"),
    ("narrativa_7d", "Narrativa (7d)"),
    ("narrativa_7_30d", "Narrativa (7-30d)"),
    ("sentimiento", "Sentimiento"),
    ("contexto_macro", "Contexto macro/sector"),
    ("fundamentals", "Fundamentals"),
    ("lectura_integrada", "Lectura integrada"),
)

_FUNDAMENTALS_PLACEHOLDER = (
    "F31 pendiente — sin datos de fundamentals en F30"
)


@dataclass
class DossierGather:
    symbol: str
    thesis: str | None
    quote: Quote | None
    hits_7d: list[SignalHit]
    hits_7_30d: list[SignalHit]
    sentiment_stats: dict
    corpus_stats_30d: dict


@dataclass
class _GatherBundle:
    gather: DossierGather
    macro_hits: list[SignalHit]


def should_refresh_dossier(*, prioridad_alta: bool, has_recent_signals: bool) -> bool:
    """Política de refresh del Dossier al generar Briefing (ADR-0009)."""
    return prioridad_alta or has_recent_signals


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().lstrip("$").upper()


def _load_thesis(user_id: str, symbol: str) -> str | None:
    if not tables_ready():
        return None
    normalized = _normalize_symbol(symbol)
    for entry in list_watch(user_id=user_id):
        if entry["symbol"] == normalized:
            note = entry.get("note")
            if isinstance(note, str) and note.strip():
                return note.strip()
    return None


def _resolve_thesis(
    user_id: str,
    symbol: str,
    thesis: str | None,
) -> str | None:
    if thesis is not None and thesis.strip():
        return thesis.strip()
    return _load_thesis(user_id, symbol)


def _sentiment_stats_for_ticker(symbol: str, *, hours: int = 168) -> dict[str, Any]:
    conditions = [
        "published_at >= now() - make_interval(hours => %(hours)s)",
    ]
    params: dict[str, Any] = {"hours": max(1, int(hours))}
    append_ticker_match_conditions(conditions, params, raw_ticker=symbol)
    where_clause = " AND ".join(conditions)

    by_sentiment: dict[str, int] = {}
    by_source_type: dict[str, int] = {}
    total_signals = 0
    with_sentiment = 0

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*)::int FROM signals WHERE {where_clause}",
                params,
            )
            row = cur.fetchone()
            total_signals = int(row[0]) if row else 0

            cur.execute(
                f"""
                SELECT
                    lower(COALESCE(NULLIF(trim(sentiment), ''), 'sin_etiqueta')) AS label,
                    count(*)::int AS cnt
                FROM signals
                WHERE {where_clause}
                GROUP BY 1
                ORDER BY cnt DESC
                """,
                params,
            )
            for label, cnt in cur.fetchall():
                count = int(cnt)
                by_sentiment[str(label)] = count
                if str(label) != "sin_etiqueta":
                    with_sentiment += count

            cur.execute(
                f"""
                SELECT COALESCE(source_type, 'x') AS source_type, count(*)::int AS cnt
                FROM signals
                WHERE {where_clause}
                GROUP BY 1
                ORDER BY cnt DESC
                """,
                params,
            )
            for source_type, cnt in cur.fetchall():
                by_source_type[str(source_type)] = int(cnt)

    return {
        "hours": params["hours"],
        "ticker": _normalize_symbol(symbol),
        "total_signals": total_signals,
        "with_sentiment": with_sentiment,
        "without_sentiment": max(total_signals - with_sentiment, 0),
        "by_sentiment": by_sentiment,
        "by_source_type": by_source_type,
    }


def _split_hits_7_30d(
    hits_30d: list[SignalHit],
    *,
    hits_7d_ids: set[str],
) -> list[SignalHit]:
    now = datetime.now(tz=timezone.utc)
    cutoff_7d = now - timedelta(hours=URGENT_HOURS)
    cutoff_30d = now - timedelta(hours=CONTEXT_HOURS)
    filtered: list[SignalHit] = []
    for hit in hits_30d:
        if hit.id_str in hits_7d_ids:
            continue
        published = hit.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if cutoff_30d <= published < cutoff_7d:
            filtered.append(hit)
    return filtered


def _fetch_macro_hits(symbol: str) -> list[SignalHit]:
    return retrieve(
        query=f"contexto macro y sector {symbol}",
        ticker=symbol,
        since_hours=MACRO_SINCE_HOURS,
        limit=MACRO_LIMIT,
    )


def _gather_bundle(*, symbol: str, thesis: str | None = None) -> _GatherBundle:
    normalized = _normalize_symbol(symbol)
    quotes = fetch_quotes([normalized])
    quote = quotes[0] if quotes else None

    hits_7d = get_recent_signals(ticker=normalized, hours=URGENT_HOURS, limit=15)
    hits_30d = get_recent_signals(ticker=normalized, hours=CONTEXT_HOURS, limit=20)
    hits_7d_ids = {hit.id_str for hit in hits_7d}
    hits_7_30d = _split_hits_7_30d(hits_30d, hits_7d_ids=hits_7d_ids)

    sentiment_stats = _sentiment_stats_for_ticker(normalized, hours=URGENT_HOURS)
    corpus_stats_30d = get_corpus_stats(hours=CONTEXT_HOURS, ticker=normalized)
    macro_hits = _fetch_macro_hits(normalized)

    gather = DossierGather(
        symbol=normalized,
        thesis=thesis,
        quote=quote,
        hits_7d=hits_7d,
        hits_7_30d=hits_7_30d,
        sentiment_stats=sentiment_stats,
        corpus_stats_30d=corpus_stats_30d,
    )
    return _GatherBundle(gather=gather, macro_hits=macro_hits)


def gather_dossier_inputs(*, symbol: str, thesis: str | None = None) -> DossierGather:
    """Recolecta inputs determinísticos para el Dossier de un Ticker."""
    return _gather_bundle(symbol=symbol, thesis=thesis).gather


def _format_price_line(quote: Quote | None) -> str:
    if quote is None:
        return "Precio: no disponible"
    sign = "+" if quote.change_percent >= 0 else ""
    delayed = " (~15 min delayed)" if quote.delayed else ""
    return (
        f"Precio: ${quote.price:.2f} ({sign}{quote.change_percent:.2f}%){delayed}"
    )


def _format_signal_block(hit: SignalHit) -> str:
    return (
        f"Signal id={hit.id_str} @{hit.username} ({hit.published_at.isoformat()})\n"
        f"URL: {hit.url}\n"
        f"{hit.raw_content.strip()}"
    )


def _format_sentiment_stats(stats: dict[str, Any]) -> str:
    lines = [
        f"Ventana: últimas {stats.get('hours', URGENT_HOURS)}h",
        f"Total Signals: {stats.get('total_signals', 0)}",
        f"Con etiqueta de sentimiento: {stats.get('with_sentiment', 0)}",
        f"Sin etiqueta: {stats.get('without_sentiment', 0)}",
    ]
    by_sentiment = stats.get("by_sentiment") or {}
    if by_sentiment:
        lines.append("Conteo por sentimiento:")
        for label, count in by_sentiment.items():
            lines.append(f"- {label}: {count}")
    by_source = stats.get("by_source_type") or {}
    if by_source:
        lines.append("Conteo por fuente:")
        for source_type, count in by_source.items():
            lines.append(f"- {source_type}: {count}")
    return "\n".join(lines)


def _format_corpus_stats(stats: dict[str, Any]) -> str:
    lines = [
        f"Ventana: últimas {stats.get('hours', CONTEXT_HOURS)}h",
        f"Total Signals: {stats.get('total_signals', 0)}",
    ]
    top_topics = stats.get("top_topics") or []
    if top_topics:
        lines.append("Tópicos frecuentes:")
        for item in top_topics[:5]:
            lines.append(f"- {item.get('topic')}: {item.get('count')}")
    return "\n".join(lines)


def build_dossier_context(
    gather: DossierGather,
    *,
    macro_hits: list[SignalHit] | None = None,
) -> str:
    """Arma contexto textual multi-capa para la síntesis del Dossier."""
    if macro_hits is None:
        macro_hits = _fetch_macro_hits(gather.symbol)
    sections: list[str] = [
        f"# Dossier — {gather.symbol}",
    ]
    if gather.thesis:
        sections.append(f"Thesis del Operator: {gather.thesis}")

    sections.append("## Datos de mercado (determinísticos)")
    sections.append(_format_price_line(gather.quote))

    sections.append("## Signals urgentes (últimos 7d)")
    if gather.hits_7d:
        sections.extend(_format_signal_block(hit) for hit in gather.hits_7d)
    else:
        sections.append("Sin Signals en los últimos 7 días.")

    sections.append("## Signals de contexto (7–30d)")
    if gather.hits_7_30d:
        sections.extend(_format_signal_block(hit) for hit in gather.hits_7_30d)
    else:
        sections.append("Sin Signals entre 7 y 30 días.")

    sections.append("## Estadísticas de sentimiento (determinísticas, 7d)")
    sections.append(_format_sentiment_stats(gather.sentiment_stats))

    sections.append("## Estadísticas del Corpus (30d)")
    sections.append(_format_corpus_stats(gather.corpus_stats_30d))

    sections.append("## Contexto macro/sector (recuperación semántica, 30d)")
    if macro_hits:
        sections.extend(_format_signal_block(hit) for hit in macro_hits)
    else:
        sections.append("Sin hits macro/sector en el Corpus para esta ventana.")

    sections.append("## Fundamentals")
    sections.append(_FUNDAMENTALS_PLACEHOLDER)

    return "\n\n".join(sections)


def _header_pattern(title: str) -> re.Pattern[str]:
    escaped = re.escape(title)
    return re.compile(rf"^##\s+{escaped}\s*$", re.IGNORECASE | re.MULTILINE)


def _parse_dossier_blocks(markdown: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    text = markdown.strip()
    if not text:
        return blocks

    matches: list[tuple[int, str, str]] = []
    for key, title in _DOSSIER_BLOCK_SPECS:
        pattern = _header_pattern(title)
        match = pattern.search(text)
        if match:
            matches.append((match.start(), key, title))

    if not matches:
        blocks["lectura_integrada"] = text
        return blocks

    matches.sort(key=lambda item: item[0])
    for index, (start, key, title) in enumerate(matches):
        content_start = start + len(f"## {title}")
        content_end = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        body = text[content_start:content_end].strip()
        blocks[key] = body
    return blocks


def _mock_dossier_content(symbol: str) -> dict[str, Any]:
    blocks = {
        key: f"[Modo mock — OPENAI_API_KEY no configurada] Bloque {title} para {symbol}."
        for key, title in _DOSSIER_BLOCK_SPECS
    }
    markdown = "\n\n".join(
        f"## {title}\n\n{blocks[key]}" for key, title in _DOSSIER_BLOCK_SPECS
    )
    return {
        "symbol": symbol,
        "markdown": markdown,
        "blocks": blocks,
        "mock": True,
    }


def _content_from_markdown(symbol: str, markdown: str) -> dict[str, Any]:
    blocks = _parse_dossier_blocks(markdown)
    return {
        "symbol": symbol,
        "markdown": markdown.strip(),
        "blocks": blocks,
        "mock": False,
    }


def _all_citation_hits(bundle: _GatherBundle) -> list[SignalHit]:
    seen: set[str] = set()
    ordered: list[SignalHit] = []
    for hit in (
        *bundle.gather.hits_7d,
        *bundle.gather.hits_7_30d,
        *bundle.macro_hits,
    ):
        if hit.id_str in seen:
            continue
        seen.add(hit.id_str)
        ordered.append(hit)
    return ordered


def _openai_configured() -> bool:
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def dossier_content_payload(content: dict[str, Any]) -> dict[str, Any]:
    """Normaliza salida de generate_dossier para persistencia/API."""
    blocks = content.get("blocks")
    if not isinstance(blocks, dict):
        blocks = {}
    payload: dict[str, Any] = {"blocks": blocks}
    stats = content.get("sentiment_stats")
    if isinstance(stats, dict):
        payload["sentiment_stats"] = stats
    return payload


def generate_dossier(
    *,
    user_id: str,
    symbol: str,
    thesis: str | None = None,
) -> tuple[dict, list]:
    """Genera contenido del Dossier sin persistir (el caller guarda)."""
    resolved_thesis = _resolve_thesis(user_id, symbol, thesis)
    bundle = _gather_bundle(symbol=symbol, thesis=resolved_thesis)
    normalized = bundle.gather.symbol

    if not _openai_configured():
        mock = _mock_dossier_content(normalized)
        mock["sentiment_stats"] = bundle.gather.sentiment_stats
        return mock, []

    context = build_dossier_context(
        bundle.gather,
        macro_hits=bundle.macro_hits,
    )
    markdown = synthesize_dossier_answer(context, thesis=resolved_thesis)
    content = _content_from_markdown(normalized, markdown)
    content["sentiment_stats"] = bundle.gather.sentiment_stats
    citations = hits_to_citations(_all_citation_hits(bundle))
    return content, citations


def iter_dossier_refresh_stream(
    *,
    user_id: str,
    symbol: str,
    thesis: str | None = None,
) -> Iterator:
    """Streamea pasos de recolección, síntesis y Citations del Dossier."""
    resolved_thesis = _resolve_thesis(user_id, symbol, thesis)
    normalized = _normalize_symbol(symbol)

    yield ResearchStepEvent(
        tool="dossier",
        label=f"Recolectando datos de {normalized}…",
        status="running",
    )

    bundle = _gather_bundle(symbol=normalized, thesis=resolved_thesis)
    context = build_dossier_context(
        bundle.gather,
        macro_hits=bundle.macro_hits,
    )

    yield ResearchStepEvent(
        tool="dossier",
        label=f"Recolectando datos de {normalized}…",
        status="done",
    )

    if not _openai_configured():
        content = _mock_dossier_content(bundle.gather.symbol)
        yield content
        yield []
        return

    yield ResearchStepEvent(
        tool="synthesis",
        label="Sintetizando Dossier…",
        status="running",
    )

    markdown_parts: list[str] = []
    for token in stream_dossier_answer(context, thesis=resolved_thesis):
        markdown_parts.append(token)
        yield token

    yield ResearchStepEvent(
        tool="synthesis",
        label="Sintetizando Dossier…",
        status="done",
    )

    markdown = "".join(markdown_parts)
    content = _content_from_markdown(bundle.gather.symbol, markdown)
    citations = hits_to_citations(_all_citation_hits(bundle))
    yield content
    yield citations
