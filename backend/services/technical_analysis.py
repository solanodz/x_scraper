"""Indicadores técnicos determinísticos para Chart Plan (SMA, Donchian, Fibonacci)."""

from __future__ import annotations

from typing import Any


def _sma(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    return round(sum(window) / len(window), 4)


def _donchian(
    highs: list[float], lows: list[float], period: int
) -> tuple[float | None, float | None]:
    if period <= 0 or len(highs) < period or len(lows) < period:
        return None, None
    upper = round(max(highs[-period:]), 4)
    lower = round(min(lows[-period:]), 4)
    return upper, lower


def _fibonacci_levels(swing_high: float, swing_low: float) -> dict[str, float]:
    span = swing_high - swing_low
    if span <= 0:
        return {}
    ratios = {
        "0.0": 0.0,
        "0.236": 0.236,
        "0.382": 0.382,
        "0.5": 0.5,
        "0.618": 0.618,
        "0.786": 0.786,
        "1.0": 1.0,
    }
    return {
        label: round(swing_high - span * ratio, 4)
        for label, ratio in ratios.items()
    }


def _price_position(price: float, upper: float | None, lower: float | None) -> str:
    if upper is None or lower is None:
        return "unknown"
    if price >= upper:
        return "at_upper"
    if price <= lower:
        return "at_lower"
    mid = (upper + lower) / 2
    return "upper_half" if price >= mid else "lower_half"


def _nearest_fib_level(
    price: float, levels: dict[str, float]
) -> tuple[str, float] | None:
    if not levels:
        return None
    nearest_label = min(levels, key=lambda label: abs(levels[label] - price))
    return nearest_label, levels[nearest_label]


def compute_technical_indicators(candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula SMA, Donchian y Fibonacci sobre velas OHLC diarias."""
    if len(candles) < 5:
        return {"error": "insufficient_candles", "data_points": len(candles)}

    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    last_close = closes[-1]

    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50)
    donchian_upper, donchian_lower = _donchian(highs, lows, 20)

    lookback = candles[-min(60, len(candles)) :]
    swing_high = round(max(float(c["high"]) for c in lookback), 4)
    swing_low = round(min(float(c["low"]) for c in lookback), 4)
    fib_levels = _fibonacci_levels(swing_high, swing_low)
    nearest_fib = _nearest_fib_level(last_close, fib_levels)

    return {
        "data_points": len(candles),
        "last_close": round(last_close, 4),
        "sma_20": sma_20,
        "sma_50": sma_50,
        "price_vs_sma20": (
            "above" if sma_20 is not None and last_close > sma_20 else "below"
        ),
        "price_vs_sma50": (
            "above" if sma_50 is not None and last_close > sma_50 else "below"
        ),
        "sma_cross": (
            "bullish" if sma_20 is not None and sma_50 is not None and sma_20 > sma_50
            else "bearish"
            if sma_20 is not None and sma_50 is not None
            else "unknown"
        ),
        "donchian_20": {
            "upper": donchian_upper,
            "lower": donchian_lower,
            "position": _price_position(last_close, donchian_upper, donchian_lower),
        },
        "fibonacci": {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "levels": fib_levels,
            "nearest_level": (
                {"ratio": nearest_fib[0], "price": nearest_fib[1]}
                if nearest_fib
                else None
            ),
        },
    }


def default_tradingview_studies() -> list[dict[str, Any]]:
    """Estudios built-in de TradingView equivalentes al set técnico base."""
    return [
        {"id": "MASimple@tv-basicstudies", "inputs": {"length": 20}},
        {"id": "MASimple@tv-basicstudies", "inputs": {"length": 50}},
        {"id": "BB@tv-basicstudies", "inputs": {"length": 20}},
    ]


def template_indicator_readings(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """Lecturas base cuando el LLM no está disponible."""
    readings: list[dict[str, Any]] = []
    last_close = stats.get("last_close")
    sma_20 = stats.get("sma_20")
    sma_50 = stats.get("sma_50")

    if sma_20 is not None and last_close is not None:
        relation = "por encima" if last_close > sma_20 else "por debajo"
        readings.append(
            {
                "name": "SMA 20",
                "stance": "alcista" if last_close > sma_20 else "bajista",
                "reading": (
                    f"El precio ({last_close}) está {relation} de la SMA 20 ({sma_20}). "
                    "En marco diario, esto sugiere momentum reciente "
                    + ("constructivo" if last_close > sma_20 else "débil")
                    + "."
                ),
                "tv_study": {
                    "id": "MASimple@tv-basicstudies",
                    "inputs": {"length": 20},
                },
            }
        )

    if sma_50 is not None and last_close is not None:
        relation = "por encima" if last_close > sma_50 else "por debajo"
        readings.append(
            {
                "name": "SMA 50",
                "stance": "alcista" if last_close > sma_50 else "bajista",
                "reading": (
                    f"El precio está {relation} de la SMA 50 ({sma_50}), referencia de "
                    "tendencia intermedia."
                ),
                "tv_study": {
                    "id": "MASimple@tv-basicstudies",
                    "inputs": {"length": 50},
                },
            }
        )

    donchian = stats.get("donchian_20") or {}
    upper = donchian.get("upper")
    lower = donchian.get("lower")
    if upper is not None and lower is not None and last_close is not None:
        position = donchian.get("position")
        if position == "at_upper":
            msg = f"El precio toca el canal superior ({upper}): presión de ruptura o sobrecompra relativa."
            stance = "alcista"
        elif position == "at_lower":
            msg = f"El precio toca el canal inferior ({lower}): soporte o debilidad relativa."
            stance = "bajista"
        elif position == "upper_half":
            msg = (
                f"El precio opera en la mitad superior del canal Donchian 20 "
                f"({lower}–{upper})."
            )
            stance = "alcista"
        else:
            msg = (
                f"El precio opera en la mitad inferior del canal Donchian 20 "
                f"({lower}–{upper})."
            )
            stance = "bajista"
        readings.append(
            {
                "name": "Canal Donchian 20",
                "stance": stance,
                "reading": msg,
                "tv_study": {"id": "BB@tv-basicstudies", "inputs": {"length": 20}},
            }
        )

    fib = stats.get("fibonacci") or {}
    nearest = fib.get("nearest_level")
    if isinstance(nearest, dict) and nearest.get("ratio") is not None:
        readings.append(
            {
                "name": "Retroceso Fibonacci",
                "stance": "neutral",
                "reading": (
                    f"Entre swing high {fib.get('swing_high')} y swing low {fib.get('swing_low')}, "
                    f"el precio se acerca al nivel {nearest.get('ratio')} "
                    f"({nearest.get('price')}). Útil como zona de reacción, no como predicción."
                ),
                "tv_study": None,
            }
        )

    return readings[:5]
