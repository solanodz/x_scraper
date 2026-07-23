"""Donchian Channel — funciones puras sobre series OHLC."""

from __future__ import annotations

from typing import Any, TypedDict


class OhlcBar(TypedDict, total=False):
    high: float
    low: float
    close: float
    date: str
    t: str


def _bar_ts(bar: dict[str, Any]) -> str:
    raw = bar.get("date") or bar.get("t") or ""
    return str(raw)


def donchian_at(
    candles: list[dict[str, Any]],
    index: int,
    period: int,
    *,
    prior: bool = True,
) -> tuple[float | None, float | None]:
    """Upper/lower Donchian en `index`.

    Si prior=True (breakout clásico), la ventana es [index-period, index)
    — excluye la vela actual. Si prior=False, incluye la vela actual.
    """
    if period < 1 or index < 0 or index >= len(candles):
        return None, None
    if prior:
        start = index - period
        end = index
    else:
        start = index - period + 1
        end = index + 1
    if start < 0 or end <= start:
        return None, None
    window = candles[start:end]
    highs = [float(c["high"]) for c in window]
    lows = [float(c["low"]) for c in window]
    return max(highs), min(lows)


def donchian_series(
    candles: list[dict[str, Any]],
    period: int,
    *,
    prior: bool = True,
) -> list[dict[str, Any]]:
    """Serie alineada: por cada vela, upper/lower (o null) + close/ts."""
    out: list[dict[str, Any]] = []
    for i, bar in enumerate(candles):
        upper, lower = donchian_at(candles, i, period, prior=prior)
        out.append(
            {
                "index": i,
                "bar_ts": _bar_ts(bar),
                "close": float(bar["close"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "upper": upper,
                "lower": lower,
            }
        )
    return out
