"""Chart Plan: recolección determinística y orquestación del Chart Agent."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

from dotenv import load_dotenv

from backend.app.services.dossier_repo import get_latest as get_latest_dossier
from backend.services.chart_plan_synthesis import synthesize_chart_plan_json
from backend.services.dossier import build_dossier_context, gather_dossier_inputs
from backend.services.market_data import Quote, fetch_price_candles, fetch_price_history, fetch_quotes
from backend.services.research_steps import ResearchStepEvent
from backend.services.technical_analysis import compute_technical_indicators
from backend.services.ticker_catalog import append_ticker_match_conditions

TIMELINE_DAYS = 30
_DOSSIER_EXCERPT_CHARS = 600


class ChartPlanError(Exception):
    """Error de prerequisitos o configuración del Chart Plan."""


class ChartPlanDisabledError(ChartPlanError):
    pass


class ChartPlanNoDossierError(ChartPlanError):
    pass


@dataclass
class ChartPlanGather:
    symbol: str
    dossier_version_id: str
    dossier_content: dict[str, Any]
    quote: Quote | None
    price_history_1mo: dict[str, Any]
    price_history_3mo: dict[str, Any]
    sentiment_stats: dict[str, Any]
    deterministic_stats: dict[str, Any]
    dossier_context_text: str


def chart_agent_enabled() -> bool:
    load_dotenv()
    raw = os.getenv("CHART_AGENT_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def chart_agent_max_turns() -> int:
    load_dotenv()
    raw = os.getenv("CHART_AGENT_MAX_TURNS", "6").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 6


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().lstrip("$").upper()


def _openai_configured() -> bool:
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _sentiment_stats_from_dossier(dossier_content: dict[str, Any]) -> dict[str, Any]:
    stats = dossier_content.get("sentiment_stats")
    if isinstance(stats, dict) and stats:
        return stats
    return {}


def _signal_counts_by_day(symbol: str, *, days: int = TIMELINE_DAYS) -> list[dict[str, Any]]:
    from backend.app.db import connect

    normalized = _normalize_symbol(symbol)
    conditions = [
        "published_at >= now() - make_interval(days => %(days)s)",
    ]
    params: dict[str, Any] = {"days": max(1, int(days))}
    append_ticker_match_conditions(conditions, params, raw_ticker=normalized)
    where_clause = " AND ".join(conditions)

    timeline: list[dict[str, Any]] = []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT (published_at AT TIME ZONE 'UTC')::date AS day, count(*)::int
                FROM signals
                WHERE {where_clause}
                GROUP BY 1
                ORDER BY 1
                """,
                params,
            )
            for day_value, count in cur.fetchall():
                if isinstance(day_value, date):
                    day_str = day_value.isoformat()
                else:
                    day_str = str(day_value)
                timeline.append({"date": day_str, "count": int(count)})
    return timeline


def _sentiment_bars_from_stats(stats: dict[str, Any]) -> list[dict[str, Any]]:
    by_sentiment = stats.get("by_sentiment") or {}
    if not isinstance(by_sentiment, dict):
        return []
    bars: list[dict[str, Any]] = []
    for label, count in by_sentiment.items():
        try:
            cnt = int(count)
        except (TypeError, ValueError):
            continue
        bars.append({"label": str(label), "count": cnt})
    bars.sort(key=lambda item: item["count"], reverse=True)
    return bars


def build_deterministic_stats(
    symbol: str,
    dossier_content: dict[str, Any],
) -> dict[str, Any]:
    """Stats determinísticas: sentimiento, retornos de precio y timeline de Signals."""
    normalized = _normalize_symbol(symbol)
    sentiment_stats = _sentiment_stats_from_dossier(dossier_content)
    sentiment_bars = _sentiment_bars_from_stats(sentiment_stats)
    signals_timeline = _signal_counts_by_day(normalized, days=TIMELINE_DAYS)

    price_1mo = fetch_price_history(normalized, period="1mo")
    price_3mo = fetch_price_history(normalized, period="3mo")
    candle_payload = fetch_price_candles(normalized, period="1y")
    candles = candle_payload.get("candles") or []
    technical_indicators = (
        compute_technical_indicators(candles)
        if isinstance(candles, list) and candles
        else {"error": candle_payload.get("error") or "sin velas"}
    )

    bullish_count = 0
    bearish_count = 0
    for bar in sentiment_bars:
        label = str(bar.get("label", "")).lower()
        count = int(bar.get("count") or 0)
        if "bull" in label or label in {"positivo", "positive"}:
            bullish_count += count
        elif "bear" in label or label in {"negativo", "negative"}:
            bearish_count += count

    return {
        "symbol": normalized,
        "sentiment_stats": sentiment_stats,
        "sentiment_bars": sentiment_bars,
        "signals_timeline": signals_timeline,
        "price_returns": {
            "1mo": price_1mo,
            "3mo": price_3mo,
        },
        "technical_indicators": technical_indicators,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
    }


def _format_dossier_excerpt(dossier_content: dict[str, Any]) -> str:
    blocks = dossier_content.get("blocks")
    if not isinstance(blocks, dict):
        return ""
    parts: list[str] = []
    for key in (
        "panorama_mercado",
        "narrativa_7d",
        "sentimiento",
        "lectura_integrada",
    ):
        text = blocks.get(key, "")
        if not isinstance(text, str) or not text.strip():
            continue
        excerpt = text.strip()
        if len(excerpt) > _DOSSIER_EXCERPT_CHARS:
            excerpt = excerpt[:_DOSSIER_EXCERPT_CHARS] + "…"
        parts.append(f"### {key}\n{excerpt}")
    return "\n\n".join(parts)


def _build_dossier_context_text(
    *,
    symbol: str,
    dossier_content: dict[str, Any],
    deterministic_stats: dict[str, Any],
) -> str:
    gather = gather_dossier_inputs(symbol=symbol)
    base = build_dossier_context(gather)
    excerpt = _format_dossier_excerpt(dossier_content)
    stats_json = json.dumps(deterministic_stats, ensure_ascii=False, indent=2)
    sections = [
        f"# Chart Plan — {symbol}",
        "## Dossier persistido (excerpt)",
        excerpt or "(sin bloques de Dossier)",
        "## Stats determinísticas (inyectadas, no inventar)",
        stats_json,
        "## Contexto determinístico ampliado",
        base,
    ]
    return "\n\n".join(sections)


def gather_chart_context(*, user_id: str, symbol: str) -> ChartPlanGather:
    """Carga Dossier prerequisito, mercado y stats para el Chart Plan."""
    normalized = _normalize_symbol(symbol)
    if not normalized:
        raise ChartPlanError("symbol required")

    dossier_version = get_latest_dossier(user_id=user_id, symbol=normalized)
    if dossier_version is None:
        raise ChartPlanNoDossierError(
            f"No hay Dossier para {normalized}. Generá uno antes de analizar gráficos."
        )

    dossier_content = dossier_version.get("content") or {}
    if not isinstance(dossier_content, dict):
        dossier_content = {}

    quotes = fetch_quotes([normalized])
    quote = quotes[0] if quotes else None
    price_history_1mo = fetch_price_history(normalized, period="1mo")
    price_history_3mo = fetch_price_history(normalized, period="3mo")
    sentiment_stats = _sentiment_stats_from_dossier(dossier_content)
    deterministic_stats = build_deterministic_stats(normalized, dossier_content)
    dossier_context_text = _build_dossier_context_text(
        symbol=normalized,
        dossier_content=dossier_content,
        deterministic_stats=deterministic_stats,
    )

    return ChartPlanGather(
        symbol=normalized,
        dossier_version_id=str(dossier_version["id"]),
        dossier_content=dossier_content,
        quote=quote,
        price_history_1mo=price_history_1mo,
        price_history_3mo=price_history_3mo,
        sentiment_stats=sentiment_stats,
        deterministic_stats=deterministic_stats,
        dossier_context_text=dossier_context_text,
    )


def chart_plan_content_payload(content: dict[str, Any]) -> dict[str, Any]:
    """Normaliza salida del Chart Plan para persistencia/API."""
    payload: dict[str, Any] = {
        "timeframes": content.get("timeframes") or [],
        "views": content.get("views") or [],
        "suggested_view": content.get("suggested_view") or {},
        # Pine fuera del MVP (ADR-0011).
        "pine_scripts": [],
        "indicator_readings": content.get("indicator_readings") or [],
        "tradingview_studies": content.get("tradingview_studies") or [],
        "assessment": content.get("assessment") or {},
        "chart_data": content.get("chart_data") or {},
    }
    if content.get("symbol"):
        payload["symbol"] = content["symbol"]
    if content.get("mock"):
        payload["mock"] = True
    return payload


def _synthesize_plan(
    gather: ChartPlanGather,
    gather_notes: str,
) -> dict[str, Any]:
    plan = synthesize_chart_plan_json(
        context=gather.dossier_context_text,
        deterministic_stats=gather.deterministic_stats,
        gather_notes=gather_notes,
        symbol=gather.symbol,
    )
    plan["symbol"] = gather.symbol
    if not _openai_configured():
        plan["mock"] = True
    return plan


def _run_agent_gather(
    user_id: str,
    gather: ChartPlanGather,
) -> str:
    from backend.services.chart_agent import iter_chart_plan_stream

    gather_notes = ""
    for item in iter_chart_plan_stream(user_id, gather.symbol, gather=gather):
        if isinstance(item, str):
            gather_notes = item
    return gather_notes


def generate_chart_plan(
    *,
    user_id: str,
    symbol: str,
) -> tuple[dict[str, Any], str | None]:
    """Genera Chart Plan JSON sin persistir. Devuelve (content, dossier_version_id)."""
    if not chart_agent_enabled():
        raise ChartPlanDisabledError("Chart Agent deshabilitado (CHART_AGENT_ENABLED=false)")

    gather = gather_chart_context(user_id=user_id, symbol=symbol)
    gather_notes = _run_agent_gather(user_id, gather) if _openai_configured() else ""
    content = _synthesize_plan(gather, gather_notes)
    return content, gather.dossier_version_id


def iter_chart_plan_analyze_stream(
    user_id: str,
    symbol: str,
) -> Iterator:
    """Pipeline SSE: pasos de recolección + síntesis; el caller persiste."""
    if not chart_agent_enabled():
        raise ChartPlanDisabledError("Chart Agent deshabilitado (CHART_AGENT_ENABLED=false)")

    normalized = _normalize_symbol(symbol)
    yield ResearchStepEvent(
        tool="chart_plan",
        label=f"Verificando Dossier de {normalized}…",
        status="running",
    )

    gather = gather_chart_context(user_id=user_id, symbol=normalized)

    yield ResearchStepEvent(
        tool="chart_plan",
        label=f"Verificando Dossier de {normalized}…",
        status="done",
    )
    yield ResearchStepEvent(
        tool="chart_plan",
        label=f"Recolectando datos de mercado y Corpus para {normalized}…",
        status="running",
    )
    yield ResearchStepEvent(
        tool="chart_plan",
        label=f"Recolectando datos de mercado y Corpus para {normalized}…",
        status="done",
    )

    gather_notes = ""
    if _openai_configured():
        from backend.services.chart_agent import iter_chart_plan_stream

        for item in iter_chart_plan_stream(user_id, gather.symbol, gather=gather):
            if isinstance(item, ResearchStepEvent):
                yield item
            elif isinstance(item, str):
                gather_notes = item
    else:
        gather_notes = gather.dossier_context_text

    yield ResearchStepEvent(
        tool="synthesis",
        label="Sintetizando Chart Plan…",
        status="running",
    )

    content = _synthesize_plan(gather, gather_notes)

    yield ResearchStepEvent(
        tool="synthesis",
        label="Sintetizando Chart Plan…",
        status="done",
    )

    yield content
    yield gather.dossier_version_id
