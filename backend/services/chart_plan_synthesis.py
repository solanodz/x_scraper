"""Síntesis JSON del Chart Plan con stats determinísticas inyectadas."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.services.llm import synthesize_chart_plan_answer
from backend.services.technical_analysis import (
    default_tradingview_studies,
    template_indicator_readings,
)


def _parse_chart_plan_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {}

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}

    return payload if isinstance(payload, dict) else {}


def _default_views() -> list[dict[str, Any]]:
    return [
        {
            "type": "tradingview",
            "enabled": True,
            "interval": "D",
            "rationale": "Vista principal de precio diaria.",
        },
        {
            "type": "sentiment_bars",
            "enabled": True,
            "rationale": "Distribución de sentimiento del Corpus (7d).",
        },
        {
            "type": "signals_timeline",
            "enabled": True,
            "rationale": "Actividad de Signals en los últimos 30 días.",
        },
    ]


def _default_suggested_view() -> dict[str, Any]:
    return {
        "interval": "1d",
        "period": "1y",
        "sma_a": {"enabled": True, "length": 20},
        "sma_b": {"enabled": True, "length": 50},
        "donchian": {"enabled": True, "period": 20},
        "fib": True,
        "volume": True,
    }


def _merge_sma_slot(raw: Any, default: dict[str, Any]) -> dict[str, Any]:
    merged = dict(default)
    if not isinstance(raw, dict):
        return merged
    if "enabled" in raw:
        merged["enabled"] = bool(raw["enabled"])
    if raw.get("length") is not None:
        try:
            length = int(raw["length"])
            if 5 <= length <= 200:
                merged["length"] = length
        except (TypeError, ValueError):
            pass
    return merged


def _merge_donchian(raw: Any, default: dict[str, Any]) -> dict[str, Any]:
    merged = dict(default)
    if not isinstance(raw, dict):
        return merged
    if "enabled" in raw:
        merged["enabled"] = bool(raw["enabled"])
    if raw.get("period") is not None:
        try:
            period = int(raw["period"])
            if period >= 2:
                merged["period"] = period
        except (TypeError, ValueError):
            pass
    return merged


def _merge_suggested_view(llm_view: Any) -> dict[str, Any]:
    defaults = _default_suggested_view()
    if not isinstance(llm_view, dict):
        return defaults

    interval = llm_view.get("interval")
    period = llm_view.get("period")
    return {
        "interval": (
            str(interval).strip()
            if isinstance(interval, str) and interval.strip()
            else defaults["interval"]
        ),
        "period": (
            str(period).strip()
            if isinstance(period, str) and period.strip()
            else defaults["period"]
        ),
        "sma_a": _merge_sma_slot(llm_view.get("sma_a"), defaults["sma_a"]),
        "sma_b": _merge_sma_slot(llm_view.get("sma_b"), defaults["sma_b"]),
        "donchian": _merge_donchian(llm_view.get("donchian"), defaults["donchian"]),
        "fib": bool(llm_view["fib"]) if "fib" in llm_view else defaults["fib"],
        "volume": (
            bool(llm_view["volume"]) if "volume" in llm_view else defaults["volume"]
        ),
    }


_INTERPRETER_ROLE_TO_DIM = {
    "vision": "visual",
    "narrative": "narrative",
    "sentiment": "sentiment_vs_price",
    "multi_tf": "multi_tf",
}
_ASSESSMENT_DIM_KEYS = (
    "visual",
    "narrative",
    "sentiment_vs_price",
    "multi_tf",
)


def _normalize_assessment_dimension(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    summary = str(raw.get("summary") or "").strip()
    findings_raw = raw.get("findings")
    findings = (
        [str(item).strip() for item in findings_raw if str(item).strip()]
        if isinstance(findings_raw, list)
        else []
    )
    stance = raw.get("stance")
    if stance not in {"alcista", "bajista", "neutral"}:
        stance = None
    if not summary and not findings and stance is None:
        return None
    return {"summary": summary, "stance": stance, "findings": findings}


def _dimensions_from_interpreter_notes(
    notes: Any,
) -> dict[str, dict[str, Any]]:
    if not isinstance(notes, list):
        return {}
    dims: dict[str, dict[str, Any]] = {}
    for note in notes:
        if not isinstance(note, dict):
            continue
        key = _INTERPRETER_ROLE_TO_DIM.get(str(note.get("role") or ""))
        if not key:
            continue
        dim = _normalize_assessment_dimension(note)
        if dim:
            dims[key] = dim
    return dims


def _merge_assessment(
    llm_assessment: dict[str, Any] | None,
    deterministic_stats: dict[str, Any],
) -> dict[str, Any]:
    base = llm_assessment if isinstance(llm_assessment, dict) else {}
    conflicts = (
        [str(item).strip() for item in base["conflicts"] if str(item).strip()]
        if isinstance(base.get("conflicts"), list)
        else []
    )
    data_gaps = (
        [str(item).strip() for item in base["data_gaps"] if str(item).strip()]
        if isinstance(base.get("data_gaps"), list)
        else []
    )
    for gap in deterministic_stats.get("parallel_data_gaps") or []:
        text = str(gap).strip()
        if text and text not in data_gaps:
            data_gaps.append(text)

    dims = _dimensions_from_interpreter_notes(
        deterministic_stats.get("interpreter_notes")
    )
    for key in _ASSESSMENT_DIM_KEYS:
        llm_dim = _normalize_assessment_dimension(base.get(key))
        if llm_dim:
            dims[key] = llm_dim

    notes = deterministic_stats.get("interpreter_notes") or []
    if isinstance(notes, list):
        for note in notes:
            if not isinstance(note, dict):
                continue
            for item in note.get("conflicts") or []:
                text = str(item).strip()
                if text and text not in conflicts:
                    conflicts.append(text)

    payload: dict[str, Any] = {
        "summary": str(base.get("summary") or "Lectura objetiva del Chart Plan."),
        "conflicts": conflicts,
        "data_gaps": data_gaps,
        "bias_check": str(
            base.get("bias_check")
            or "Sin recomendaciones de compra/venta; datos anclados al Corpus y mercado."
        ),
        "bullish_count": int(
            base.get("bullish_count")
            if base.get("bullish_count") is not None
            else deterministic_stats.get("bullish_count") or 0
        ),
        "bearish_count": int(
            base.get("bearish_count")
            if base.get("bearish_count") is not None
            else deterministic_stats.get("bearish_count") or 0
        ),
    }
    for key in _ASSESSMENT_DIM_KEYS:
        if key in dims:
            payload[key] = dims[key]
    return payload


def _inject_chart_data(deterministic_stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "sentiment_bars": deterministic_stats.get("sentiment_bars") or [],
        "signals_timeline": deterministic_stats.get("signals_timeline") or [],
    }


def _merge_indicator_readings(
    llm_readings: Any,
    deterministic_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(llm_readings, list) and llm_readings:
        cleaned: list[dict[str, Any]] = []
        for item in llm_readings[:5]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            reading = str(item.get("reading") or "").strip()
            if not name or not reading:
                continue
            cleaned.append(
                {
                    "name": name,
                    "stance": str(item.get("stance") or "neutral").strip().lower(),
                    "reading": reading,
                    "tv_study": item.get("tv_study"),
                }
            )
        if cleaned:
            return cleaned

    technical = deterministic_stats.get("technical_indicators") or {}
    if isinstance(technical, dict) and not technical.get("error"):
        return template_indicator_readings(technical)
    return []


def _merge_tradingview_studies(
    llm_studies: Any,
    indicator_readings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(llm_studies, list) and llm_studies:
        cleaned: list[dict[str, Any]] = []
        for item in llm_studies[:6]:
            if isinstance(item, str) and item.strip():
                cleaned.append({"id": item.strip()})
                continue
            if not isinstance(item, dict):
                continue
            study_id = str(item.get("id") or "").strip()
            if not study_id:
                continue
            entry: dict[str, Any] = {"id": study_id}
            inputs = item.get("inputs")
            if isinstance(inputs, dict) and inputs:
                entry["inputs"] = inputs
            cleaned.append(entry)
        if cleaned:
            return cleaned

    from_readings: list[dict[str, Any]] = []
    for reading in indicator_readings:
        tv_study = reading.get("tv_study")
        if isinstance(tv_study, dict) and tv_study.get("id"):
            from_readings.append(tv_study)
    if from_readings:
        return from_readings[:6]
    return default_tradingview_studies()


def synthesize_chart_plan_json(
    *,
    context: str,
    deterministic_stats: dict[str, Any],
    gather_notes: str,
    symbol: str,
    chart_image_base64: str | None = None,
    chart_image_media_type: str = "image/png",
    chart_view: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sintetiza Chart Plan JSON; chart_data viene de stats determinísticas."""
    raw = synthesize_chart_plan_answer(
        context=context,
        gather_notes=gather_notes,
        deterministic_stats=deterministic_stats,
        symbol=symbol,
        chart_image_base64=chart_image_base64,
        chart_image_media_type=chart_image_media_type,
        chart_view=chart_view,
    )
    parsed = _parse_chart_plan_json(raw)

    timeframes = parsed.get("timeframes")
    if not isinstance(timeframes, list) or not timeframes:
        timeframes = [{"interval": "D", "rationale": "Marco diario por defecto."}]

    views = parsed.get("views")
    if not isinstance(views, list) or not views:
        views = _default_views()

    # Pine fuera del MVP (ADR-0011): omit/[] del modelo OK; salida siempre [].
    pine_scripts: list[Any] = []

    suggested_view = _merge_suggested_view(parsed.get("suggested_view"))

    assessment = _merge_assessment(parsed.get("assessment"), deterministic_stats)
    indicator_readings = _merge_indicator_readings(
        parsed.get("indicator_readings"), deterministic_stats
    )
    tradingview_studies = _merge_tradingview_studies(
        parsed.get("tradingview_studies"), indicator_readings
    )

    return {
        "timeframes": timeframes,
        "views": views,
        "suggested_view": suggested_view,
        "pine_scripts": pine_scripts,
        "indicator_readings": indicator_readings,
        "tradingview_studies": tradingview_studies,
        "assessment": assessment,
        "chart_data": _inject_chart_data(deterministic_stats),
    }
