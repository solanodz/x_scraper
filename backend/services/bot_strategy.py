"""Strategy DonchianBreakout — emite Trade Signals (≠ Corpus Signal)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.services.donchian import donchian_at


@dataclass(frozen=True)
class TradeSignal:
    """Evento interno de entrada del Paper Bot (no es Signal del Corpus)."""

    symbol: str
    side: str  # long | short
    reason: str
    bar_ts: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyContext:
    armed: bool
    max_positions: int
    open_count: int
    open_symbols: set[str]
    cooldown_seconds: int
    # symbol -> last closed_at (aware datetime or None)
    last_closed_at: dict[str, datetime | None]
    # (symbol, side, bar_ts) already processed
    seen_keys: set[tuple[str, str, str]]
    now: datetime | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_donchian_breakout(
    symbol: str,
    candles: list[dict[str, Any]],
    *,
    period: int = 20,
) -> TradeSignal | None:
    """Long si close > upper (prior period); short si close < lower."""
    if len(candles) < period + 1:
        return None
    i = len(candles) - 1
    bar = candles[i]
    upper, lower = donchian_at(candles, i, period, prior=True)
    if upper is None or lower is None:
        return None
    close = float(bar["close"])
    bar_ts = str(bar.get("date") or bar.get("t") or "")
    meta = {
        "close": close,
        "upper": upper,
        "lower": lower,
        "period": period,
    }
    if close > upper:
        return TradeSignal(
            symbol=symbol,
            side="long",
            reason="donchian_breakout_up",
            bar_ts=bar_ts,
            meta=meta,
        )
    if close < lower:
        return TradeSignal(
            symbol=symbol,
            side="short",
            reason="donchian_breakout_down",
            bar_ts=bar_ts,
            meta=meta,
        )
    return None


def filter_trade_signal(
    signal: TradeSignal,
    ctx: StrategyContext,
) -> tuple[bool, str]:
    """Aplica Risk Policy / filtros. Retorna (ok, skip_reason)."""
    if not ctx.armed:
        return False, "not_armed"
    if signal.symbol in ctx.open_symbols:
        return False, "symbol_already_open"
    if ctx.open_count >= ctx.max_positions:
        return False, "max_positions"
    key = (signal.symbol, signal.side, signal.bar_ts)
    if key in ctx.seen_keys:
        return False, "duplicate_bar"
    last = ctx.last_closed_at.get(signal.symbol)
    if last is not None and ctx.cooldown_seconds > 0:
        now = ctx.now or _utcnow()
        elapsed = (now - _ensure_aware(last)).total_seconds()
        if elapsed < ctx.cooldown_seconds:
            return False, "cooldown"
    return True, ""


def collect_signals(
    candles_by_symbol: dict[str, list[dict[str, Any]]],
    *,
    period: int,
    ctx: StrategyContext,
    on_skip: Callable[[TradeSignal, str], None] | None = None,
) -> list[TradeSignal]:
    accepted: list[TradeSignal] = []
    # Copia mutable del contexto para filtros secuenciales en el mismo tick
    open_count = ctx.open_count
    open_symbols = set(ctx.open_symbols)
    seen = set(ctx.seen_keys)
    for symbol, candles in candles_by_symbol.items():
        signal = evaluate_donchian_breakout(symbol, candles, period=period)
        if signal is None:
            continue
        tick_ctx = StrategyContext(
            armed=ctx.armed,
            max_positions=ctx.max_positions,
            open_count=open_count,
            open_symbols=open_symbols,
            cooldown_seconds=ctx.cooldown_seconds,
            last_closed_at=ctx.last_closed_at,
            seen_keys=seen,
            now=ctx.now,
        )
        ok, reason = filter_trade_signal(signal, tick_ctx)
        if not ok:
            if on_skip:
                on_skip(signal, reason)
            continue
        accepted.append(signal)
        open_count += 1
        open_symbols.add(symbol)
        seen.add((signal.symbol, signal.side, signal.bar_ts))
    return accepted
