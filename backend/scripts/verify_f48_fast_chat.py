"""Verificación F48: Research Chat fast paths + live parallel steps."""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from unittest.mock import patch

from dotenv import load_dotenv

from backend.services.research_steps import ResearchStepEvent


def _set_fast_env() -> None:
    os.environ["RESEARCH_ENGINE"] = "langgraph"
    os.environ["RESEARCH_PARALLEL_ENABLED"] = "true"
    os.environ.setdefault("RESEARCH_PARALLEL_MAX_TICKERS", "4")
    os.environ.setdefault("RESEARCH_PARALLEL_CORPUS_LIMIT", "5")


def _verify_fast_path_routes() -> int:
    print("1. Fast path routes")
    try:
        from backend.services.research_fast_path import (
            build_fast_path_context,
            infer_response_style,
            resolve_fast_path,
        )
    except Exception as exc:
        print(f"   FAIL: research_fast_path no disponible: {exc}")
        return 1

    cases = [
        ("precio BTC", "quote"),
        ("dólar blue hoy", "fx"),
        ("última noticia de MSFT", "recent_signals"),
        (
            "ultima noticia de msft? y como esta de precios? conviene comprar ahora?",
            None,
        ),
        ("cómo está de precios MSFT", "quote"),
        ("compará NVDA vs AMD", None),
        ("que noticias hubo sobre el dolar esta semana?", None),
        ("que se dijo sobre el dolar en argentina esta semana?", None),
    ]
    for query, expected in cases:
        path = resolve_fast_path(query)
        got = path.kind if path else None
        if got != expected:
            print(f"   FAIL: {query!r} expected {expected!r}, got {got!r}")
            return 1
        print(f"   {query!r} -> {got}")

    style_cases = [
        ("y el oficial?", "concise"),
        ("dólar blue hoy", "concise"),
        ("precio BTC", "concise"),
        ("compará NVDA vs AMD y qué implica", "memo"),
        ("que noticias hubo sobre el dolar esta semana?", "memo"),
        (
            "ultima noticia de msft? y como esta de precios? conviene comprar ahora?",
            "memo",
        ),
    ]
    for query, expected in style_cases:
        got = infer_response_style(query)
        if got != expected:
            print(f"   FAIL: style {query!r} expected {expected!r}, got {got!r}")
            return 1
        print(f"   style {query!r} -> {got}")

    from backend.services.research_fast_path import (
        detect_requested_fx_labels,
        format_fx_direct_answer,
    )

    if detect_requested_fx_labels("dólar blue hoy") != ["blue"]:
        print(
            f"   FAIL: blue labels {detect_requested_fx_labels('dólar blue hoy')}"
        )
        return 1
    if detect_requested_fx_labels("y el oficial?") != ["oficial"]:
        print(
            f"   FAIL: oficial labels {detect_requested_fx_labels('y el oficial?')}"
        )
        return 1

    fx_payload = {
        "scope": "ars_usd",
        "source": "dolarapi.com",
        "quotes": [
            {
                "label": "oficial",
                "bid": 1460.0,
                "ask": 1510.0,
                "updated_at": "2026-07-23T18:55:00.000Z",
                "source": "dolarapi.com",
            },
            {
                "label": "blue",
                "bid": 1530.0,
                "ask": 1550.0,
                "updated_at": "2026-07-24T11:58:00.000Z",
                "source": "dolarapi.com",
            },
        ],
    }
    blue_answer = format_fx_direct_answer("dólar blue hoy", fx_payload)
    if "1530" not in blue_answer or "blue" not in blue_answer.lower():
        print(f"   FAIL: blue answer missing blue quote: {blue_answer}")
        return 1
    if "1460" in blue_answer or "oficial" in blue_answer.lower():
        print(f"   FAIL: blue answer leaked oficial: {blue_answer}")
        return 1
    print("   FX direct answer filters blue correctly")

    calls: list[tuple[str, dict]] = []

    def _mock_execute(tool: str, args: dict, **_kwargs):
        calls.append((tool, dict(args)))
        return '{"ok": true}', []

    with patch("backend.services.research_fast_path.execute_tool", _mock_execute):
        result = build_fast_path_context("precio BTC")

    if result is None:
        print("   FAIL: precio BTC no devolvió GatherResult")
        return 1
    if calls != [("get_quotes", {"symbols": ["BTC"]})]:
        print(f"   FAIL: tool calls inesperadas: {calls}")
        return 1
    if "get_quotes" not in result.context:
        print(f"   FAIL: contexto sin get_quotes: {result.context}")
        return 1
    print("   PASS\n")
    return 0


def _verify_parallel_steps_are_live() -> int:
    print("2. Parallel Research steps live")
    _set_fast_env()

    release = threading.Event()
    first_item: queue.Queue[object] = queue.Queue()

    def _fake_run_parallel_research(context, query, tickers, *, on_step=None, **_kwargs):
        if on_step:
            on_step(
                ResearchStepEvent(
                    tool="get_quotes",
                    label="Cotizaciones (NVDA)",
                    status="running",
                )
            )
        release.wait(timeout=2)

    with (
        patch(
            "backend.services.research_agent._resolve_parallel_tickers",
            return_value=["NVDA"],
        ),
        patch(
            "backend.services.research_agent.run_parallel_research",
            _fake_run_parallel_research,
        ),
        patch(
            "backend.services.research_agent.finalize_research_context",
            lambda *args, **kwargs: None,
        ),
    ):
        from backend.services.research_agent import iter_gather_research_context

        gen = iter_gather_research_context("NVDA", history=None)

        def _read_first() -> None:
            try:
                first_item.put(next(gen))
            except Exception as exc:  # pragma: no cover - diagnostic path
                first_item.put(exc)

        t = threading.Thread(target=_read_first, daemon=True)
        t.start()

        try:
            item = first_item.get(timeout=0.5)
        except queue.Empty:
            release.set()
            t.join(timeout=1)
            print("   FAIL: no se emitió step mientras el bundle seguía corriendo")
            return 1
        finally:
            release.set()

    if not isinstance(item, ResearchStepEvent):
        print(f"   FAIL: expected ResearchStepEvent, got {type(item).__name__}: {item}")
        return 1
    if item.status != "running" or item.tool != "get_quotes":
        print(f"   FAIL: unexpected step: {item}")
        return 1
    print(f"   first step: {item.label} ({item.status})")
    print("   PASS\n")
    return 0


def main() -> int:
    print("== F48 verification: Fast Research Chat ==\n")
    load_dotenv()
    start = time.monotonic()

    for check in (_verify_fast_path_routes, _verify_parallel_steps_are_live):
        rc = check()
        if rc != 0:
            return rc

    elapsed = time.monotonic() - start
    print(f"== F48 verification OK ({elapsed:.2f}s) ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
