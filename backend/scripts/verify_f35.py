"""Verificación F35: Parallel Chart Gather + Chart Interpreters (ADR-0012)."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from dotenv import load_dotenv

from backend.services.chart_plan_synthesis import _merge_assessment
from backend.services.parallel_chart_gather import (
    chart_parallel_enabled,
    format_interpreter_notes_for_synthesis,
)
from backend.services.research_steps import ResearchStepEvent


def _set_parallel_env(enabled: bool) -> None:
    os.environ["CHART_AGENT_ENABLED"] = "true"
    os.environ["CHART_PARALLEL_ENABLED"] = "true" if enabled else "false"


def main() -> int:
    print("== F35 verification: Parallel Chart Gather ==\n")
    load_dotenv()

    print("1. chart_parallel_enabled flag")
    _set_parallel_env(False)
    if chart_parallel_enabled():
        print("   FAIL: expected false")
        return 1
    _set_parallel_env(True)
    if not chart_parallel_enabled():
        print("   FAIL: expected true")
        return 1
    print("   PASS\n")

    print("2. format_interpreter_notes_for_synthesis")
    notes = [
        {
            "role": "vision",
            "summary": "Estructura lateral",
            "stance": "neutral",
            "findings": ["rango claro"],
            "conflicts": [],
            "data_gaps": [],
        }
    ]
    text = format_interpreter_notes_for_synthesis(notes)
    if "Chart Interpreters" not in text or "vision" not in text:
        print(f"   FAIL: bad format: {text[:120]}")
        return 1
    print("   PASS\n")

    print("3. _merge_assessment mapea interpreter_notes → dimensiones")
    stats = {
        "bullish_count": 2,
        "bearish_count": 1,
        "parallel_data_gaps": ["Sin captura del Ticker Chart (visión omitida)."],
        "interpreter_notes": [
            {
                "role": "vision",
                "summary": "Canal alcista corto",
                "stance": "alcista",
                "findings": ["precio sobre SMA"],
                "conflicts": ["TV diverge de stats"],
                "data_gaps": [],
            },
            {
                "role": "narrative",
                "summary": "Catalizadores mixtos",
                "stance": "neutral",
                "findings": ["earnings"],
                "conflicts": [],
                "data_gaps": [],
            },
            {
                "role": "sentiment",
                "summary": "Sentimiento vs precio divergente",
                "stance": "bajista",
                "findings": ["bearish > bullish"],
                "conflicts": [],
                "data_gaps": [],
            },
            {
                "role": "multi_tf",
                "summary": "15m débil, 1y constructivo",
                "stance": "neutral",
                "findings": ["1y_1d encima SMA50"],
                "conflicts": [],
                "data_gaps": [],
            },
        ],
    }
    assessment = _merge_assessment(
        {"summary": "Resumen sintetizado", "conflicts": [], "data_gaps": []},
        stats,
    )
    for key in ("visual", "narrative", "sentiment_vs_price", "multi_tf"):
        if key not in assessment:
            print(f"   FAIL: missing dimension {key}")
            return 1
    if assessment["visual"]["stance"] != "alcista":
        print(f"   FAIL: visual stance {assessment['visual']}")
        return 1
    if "Sin captura del Ticker Chart" not in " ".join(assessment["data_gaps"]):
        print(f"   FAIL: parallel gaps not merged: {assessment['data_gaps']}")
        return 1
    if "TV diverge de stats" not in assessment["conflicts"]:
        print(f"   FAIL: interpreter conflict missing: {assessment['conflicts']}")
        return 1
    print(
        f"   dims={list(k for k in ('visual','narrative','sentiment_vs_price','multi_tf') if k in assessment)}"
    )
    print("   PASS\n")

    print("4. iter_chart_plan_analyze_stream usa Parallel Chart Gather (mock)")
    _set_parallel_env(True)

    class _FakeGather:
        symbol = "NVDA"
        dossier_version_id = "dossier-1"
        dossier_context_text = "ctx"
        deterministic_stats = {
            "bullish_count": 1,
            "bearish_count": 0,
            "technical_indicators": {"error": "skip"},
            "sentiment_bars": [],
            "signals_timeline": [],
            "interpreter_notes": notes,
            "parallel_data_gaps": [],
        }

    class _FakeResult:
        gather = _FakeGather()
        corpus_notes = "corpus"
        multi_tf_stats = {}
        interpreter_notes = notes
        data_gaps: list[str] = []

    steps: list[ResearchStepEvent] = []
    content = None
    dossier_id = None

    def _fake_parallel(**_kwargs):
        on_step = _kwargs.get("on_step")
        if on_step:
            on_step(
                ResearchStepEvent(
                    tool="chart_gather_multi_tf",
                    label="Gather · multi-TF",
                    status="running",
                )
            )
            on_step(
                ResearchStepEvent(
                    tool="chart_gather_multi_tf",
                    label="Gather · multi-TF",
                    status="done",
                )
            )
            on_step(
                ResearchStepEvent(
                    tool="chart_interpreter_vision",
                    label="Interpreter · visión",
                    status="running",
                )
            )
            on_step(
                ResearchStepEvent(
                    tool="chart_interpreter_vision",
                    label="Interpreter · visión",
                    status="done",
                )
            )
        return _FakeResult()

    with (
        patch(
            "backend.services.parallel_chart_gather.run_parallel_chart_gather",
            _fake_parallel,
        ),
        patch(
            "backend.services.chart_plan._synthesize_plan",
            lambda gather, gather_notes, **_kw: {
                "symbol": gather.symbol,
                "assessment": _merge_assessment(
                    {"summary": "ok"}, gather.deterministic_stats
                ),
                "timeframes": [],
                "views": [],
                "suggested_view": {},
                "indicator_readings": [],
                "tradingview_studies": [],
                "chart_data": {},
            },
        ),
        patch("backend.services.chart_plan.chart_agent_enabled", lambda: True),
    ):
        from backend.services.chart_plan import iter_chart_plan_analyze_stream

        for item in iter_chart_plan_analyze_stream(
            "user-1",
            "NVDA",
            chart_image_base64=None,
        ):
            if isinstance(item, ResearchStepEvent):
                steps.append(item)
            elif isinstance(item, dict):
                content = item
            elif isinstance(item, str):
                dossier_id = item

    tools = {s.tool for s in steps}
    if "chart_gather_multi_tf" not in tools:
        print(f"   FAIL: expected gather step, got {tools}")
        return 1
    if "chart_interpreter_vision" not in tools:
        print(f"   FAIL: expected interpreter step, got {tools}")
        return 1
    if "synthesis" not in tools:
        print(f"   FAIL: expected synthesis step, got {tools}")
        return 1
    if not content or not content.get("assessment", {}).get("visual"):
        print(f"   FAIL: content missing visual assessment: {content}")
        return 1
    if dossier_id != "dossier-1":
        print(f"   FAIL: dossier id {dossier_id}")
        return 1
    print(f"   steps={len(steps)} tools={sorted(tools)}")
    print("   PASS\n")

    print("5. flag off no llama Parallel Chart Gather")
    _set_parallel_env(False)
    called = {"parallel": False}

    def _should_not_run(**_kwargs):
        called["parallel"] = True
        raise AssertionError("parallel should not run")

    with (
        patch(
            "backend.services.parallel_chart_gather.run_parallel_chart_gather",
            _should_not_run,
        ),
        patch("backend.services.chart_plan.chart_agent_enabled", lambda: True),
        patch(
            "backend.services.chart_plan.gather_chart_context",
            lambda **_kw: _FakeGather(),
        ),
        patch("backend.services.chart_plan._openai_configured", lambda: False),
        patch(
            "backend.services.chart_plan._synthesize_plan",
            lambda gather, gather_notes, **_kw: {
                "symbol": gather.symbol,
                "assessment": {"summary": "legacy"},
            },
        ),
    ):
        from backend.services.chart_plan import iter_chart_plan_analyze_stream

        list(
            iter_chart_plan_analyze_stream(
                "user-1",
                "NVDA",
            )
        )
    if called["parallel"]:
        print("   FAIL: parallel gather was called with flag off")
        return 1
    print("   PASS\n")

    print("== F35 OK ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
