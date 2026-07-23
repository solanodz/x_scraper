"""Parallel Chart Gather: lanes concurrentes + Chart Interpreters (ADR-0012)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

from backend.services.chart_interpreters import run_chart_interpreters_parallel
from backend.services.market_data import Quote, fetch_price_candles
from backend.services.research_steps import ResearchStepEvent
from backend.services.technical_analysis import compute_technical_indicators
from backend.services.tools import execute_tool

if TYPE_CHECKING:
    from backend.services.chart_plan import ChartPlanGather

_MULTI_TF_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("5d_15m", "5d", "15m"),
    ("3mo_1d", "3mo", "1d"),
    ("1y_1d", "1y", "1d"),
)


@dataclass
class ParallelChartGatherResult:
    symbol: str
    gather: "ChartPlanGather"
    corpus_notes: str
    multi_tf_stats: dict[str, Any]
    interpreter_notes: list[dict]
    data_gaps: list[str] = field(default_factory=list)


def chart_parallel_enabled() -> bool:
    load_dotenv()
    raw = os.getenv("CHART_PARALLEL_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _format_quote_summary(quote: Quote | None) -> str:
    if quote is None:
        return "(sin cotización)"
    delayed = " (delayed)" if quote.delayed else ""
    return (
        f"{quote.symbol}: price={quote.price} change={quote.change} "
        f"change_percent={quote.change_percent}%{delayed}"
    )


def _emit(
    on_step: Callable[[ResearchStepEvent], None] | None,
    *,
    tool: str,
    label: str,
    status: str,
) -> None:
    if on_step:
        on_step(ResearchStepEvent(tool=tool, label=label, status=status))


def _gather_multi_tf(symbol: str) -> tuple[dict[str, Any], list[str]]:
    stats: dict[str, Any] = {}
    gaps: list[str] = []
    for label, period, interval in _MULTI_TF_WINDOWS:
        try:
            payload = fetch_price_candles(symbol, period=period, interval=interval)
            if payload.get("error"):
                err = str(payload["error"])
                gaps.append(f"Gather multi-TF {label}: {err}")
                stats[label] = {"error": err, "period": period, "interval": interval}
                continue
            candles = payload.get("candles") or []
            if not isinstance(candles, list) or not candles:
                gaps.append(f"Gather multi-TF {label}: sin velas")
                stats[label] = {
                    "error": "sin velas",
                    "period": period,
                    "interval": interval,
                }
                continue
            indicators = compute_technical_indicators(candles)
            stats[label] = {
                "period": period,
                "interval": interval,
                "data_points": payload.get("data_points"),
                "indicators": indicators,
            }
            if isinstance(indicators, dict) and indicators.get("error"):
                gaps.append(f"Gather multi-TF {label}: {indicators['error']}")
        except Exception as exc:  # noqa: BLE001 — lane degradable
            gaps.append(f"Gather multi-TF {label}: {exc}")
            stats[label] = {
                "error": str(exc),
                "period": period,
                "interval": interval,
            }
    return stats, gaps


def _gather_corpus(symbol: str) -> tuple[str, list[str]]:
    parts: list[str] = []
    gaps: list[str] = []
    try:
        recent, _hits = execute_tool(
            "get_recent_signals",
            {"ticker": symbol, "hours": 168, "limit": 8},
        )
        parts.append(f"### Signals recientes\n{recent}")
    except Exception as exc:  # noqa: BLE001
        gaps.append(f"Gather Corpus get_recent_signals: {exc}")

    try:
        search, _hits = execute_tool(
            "search_corpus",
            {
                "query": f"narrativa catalizadores sentimiento {symbol}",
                "ticker": symbol,
                "limit": 8,
            },
        )
        parts.append(f"### Búsqueda Corpus\n{search}")
    except Exception as exc:  # noqa: BLE001
        gaps.append(f"Gather Corpus search_corpus: {exc}")

    if not parts:
        gaps.append("Gather Corpus: sin resultados de Signals ni búsqueda.")
        return "(sin notas de Corpus)", gaps
    return "\n\n".join(parts), gaps


def run_parallel_chart_gather(
    *,
    user_id: str,
    symbol: str,
    chart_image_base64: str | None = None,
    chart_image_media_type: str = "image/png",
    chart_view: dict | None = None,
    on_step: Callable[[ResearchStepEvent], None] | None = None,
) -> ParallelChartGatherResult:
    """Gather concurrente + Chart Interpreters en paralelo."""
    # Lazy import: evita ciclo chart_plan ↔ parallel_chart_gather.
    from backend.services.chart_plan import gather_chart_context

    gather = gather_chart_context(user_id=user_id, symbol=symbol)
    normalized = gather.symbol
    data_gaps: list[str] = []

    corpus_notes = "(sin notas de Corpus)"
    multi_tf_stats: dict[str, Any] = {}

    def lane_dossier() -> None:
        _emit(
            on_step,
            tool="chart_gather_dossier",
            label="Gather · Dossier/sentimiento",
            status="running",
        )
        _emit(
            on_step,
            tool="chart_gather_dossier",
            label="Gather · Dossier/sentimiento",
            status="done",
        )

    def lane_corpus() -> tuple[str, list[str]]:
        _emit(
            on_step,
            tool="chart_gather_corpus",
            label="Gather · Corpus",
            status="running",
        )
        try:
            return _gather_corpus(normalized)
        finally:
            _emit(
                on_step,
                tool="chart_gather_corpus",
                label="Gather · Corpus",
                status="done",
            )

    def lane_multi_tf() -> tuple[dict[str, Any], list[str]]:
        _emit(
            on_step,
            tool="chart_gather_multi_tf",
            label="Gather · multi-TF",
            status="running",
        )
        try:
            return _gather_multi_tf(normalized)
        finally:
            _emit(
                on_step,
                tool="chart_gather_multi_tf",
                label="Gather · multi-TF",
                status="done",
            )

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(lane_dossier): "dossier",
            pool.submit(lane_corpus): "corpus",
            pool.submit(lane_multi_tf): "multi_tf",
        }
        for future in as_completed(futures):
            kind = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                data_gaps.append(f"Gather {kind} falló: {exc}")
                continue
            if kind == "corpus" and isinstance(result, tuple):
                corpus_notes, gaps = result
                data_gaps.extend(gaps)
            elif kind == "multi_tf" and isinstance(result, tuple):
                multi_tf_stats, gaps = result
                data_gaps.extend(gaps)

    price_returns = gather.deterministic_stats.get("price_returns") or {}
    if not isinstance(price_returns, dict):
        price_returns = {}

    if not chart_image_base64:
        data_gaps.append("Sin captura del Ticker Chart (visión omitida).")

    interpreter_notes = run_chart_interpreters_parallel(
        symbol=normalized,
        chart_image_base64=chart_image_base64,
        chart_image_media_type=chart_image_media_type,
        chart_view=chart_view,
        corpus_notes=corpus_notes,
        sentiment_stats=gather.sentiment_stats or {},
        quote_summary=_format_quote_summary(gather.quote),
        price_returns=price_returns,
        multi_tf_stats=multi_tf_stats,
        on_step=on_step,
    )

    for note in interpreter_notes:
        for gap in note.get("data_gaps") or []:
            text = str(gap).strip()
            if text and text not in data_gaps:
                data_gaps.append(text)

    gather.deterministic_stats = {
        **gather.deterministic_stats,
        "multi_tf": multi_tf_stats,
        "interpreter_notes": interpreter_notes,
        "parallel_data_gaps": data_gaps,
    }

    return ParallelChartGatherResult(
        symbol=normalized,
        gather=gather,
        corpus_notes=corpus_notes,
        multi_tf_stats=multi_tf_stats,
        interpreter_notes=interpreter_notes,
        data_gaps=data_gaps,
    )


def format_interpreter_notes_for_synthesis(notes: list[dict[str, Any]]) -> str:
    """Texto para el sintetizador del Chart Plan."""
    if not notes:
        return "(sin Chart Interpreters)"
    parts: list[str] = ["# Chart Interpreters (Parallel Chart Gather)"]
    for note in notes:
        role = note.get("role", "?")
        parts.append(f"## {role}")
        parts.append(json.dumps(note, ensure_ascii=False, indent=2))
    return "\n\n".join(parts)
