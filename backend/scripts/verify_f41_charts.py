#!/usr/bin/env python3
"""Verifica Chart cards determinísticos (F41)."""

from __future__ import annotations

import sys

from backend.services.chat_artifacts import (
    ensure_price_chart_artifacts,
    period_from_query,
    query_wants_price_chart,
)
from backend.services.research_steps import ChatArtifact


def main() -> int:
    assert query_wants_price_chart("precio NVDA últimos 30 días")
    assert query_wants_price_chart("evolución de AAPL en 3 meses")
    assert not query_wants_price_chart("qué noticias hay de NVIDIA")
    assert not query_wants_price_chart("dólar blue hoy")

    assert period_from_query("NVDA 30 días") == "1mo"
    assert period_from_query("AAPL 3 meses") == "3mo"
    assert period_from_query("MSFT 1 año") == "1y"

    arts = ensure_price_chart_artifacts("precio AAPL último mes", [])
    assert arts, "expected at least one price_chart artifact"
    assert arts[0]["type"] == "price_chart"
    assert arts[0]["symbol"] == "AAPL"
    assert arts[0].get("candles"), "candles required for FE"
    assert arts[0]["candles"][0].get("t"), "candle.t required for FE parse"

    # Idempotente si ya hay artifact del mismo símbolo
    again = ensure_price_chart_artifacts("precio AAPL último mes", arts)
    assert len([a for a in again if a.get("symbol") == "AAPL"]) == 1

    # SSE shape
    payload = {k: v for k, v in arts[0].items() if k != "type"}
    event = ChatArtifact(type="price_chart", data=payload).to_dict()
    assert event["type"] == "price_chart"
    assert event["candles"]

    print("verify_f41_charts OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
