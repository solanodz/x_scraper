"""Orquestación de un tick del Paper Bot."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from backend.app.services import bot_repo
from backend.services.bot_strategy import (
    StrategyContext,
    TradeSignal,
    collect_signals,
)
from backend.services.bot_venue import (
    HyperliquidVenue,
    PaperVenue,
    VenueNotEnabled,
    get_venue,
)

# Ventana OHLC suficiente para Donchian period 20 (Yahoo clamps).
_OHLC_PERIOD_BY_INTERVAL = {
    "1m": "5d",
    "5m": "5d",
    "15m": "5d",
    "30m": "1mo",
    "1h": "1mo",
    "4h": "3mo",
    "1d": "6mo",
}


def _fetch_candles_live(
    symbol: str,
    *,
    interval: str,
) -> list[dict[str, Any]]:
    from backend.services.market_data import fetch_price_candles

    period = _OHLC_PERIOD_BY_INTERVAL.get(interval, "1mo")
    payload = fetch_price_candles(symbol, period=period, interval=interval)
    if payload.get("error"):
        return []
    return list(payload.get("candles") or [])


def run_tick(
    operator_id: str,
    *,
    candles_by_symbol: dict[str, list[dict[str, Any]]] | None = None,
    mark_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Un tick: (1) TP/SL en open, (2) si armed, evaluar Trade Signals y abrir.

    Para tests: inyectar `candles_by_symbol` y/o `mark_prices` (sin red).
    Sin candles inyectadas, intenta OHLC live vía market_data.fetch_price_candles.
    """
    summary: dict[str, Any] = {
        "operator_id": operator_id,
        "closed": [],
        "opened": [],
        "skipped": [],
        "errors": [],
        "armed": False,
    }

    if not bot_repo.tables_ready():
        summary["errors"].append("bot tables missing")
        return summary

    config = bot_repo.get_or_create_config(operator_id=operator_id)
    summary["armed"] = bool(config["armed"])

    mark_fn: Callable[[str], Decimal] | None = None
    if mark_prices is not None:

        def _marks(symbol: str) -> Decimal:
            if symbol not in mark_prices:
                raise VenueNotEnabled(f"no injected mark for {symbol}")
            return Decimal(str(mark_prices[symbol]))

        mark_fn = _marks

    try:
        venue = get_venue(config.get("venue") or "paper", mark_fn=mark_fn)
    except VenueNotEnabled as exc:
        summary["errors"].append(str(exc))
        bot_repo.insert_event(
            operator_id=operator_id,
            kind="error",
            payload={"error": str(exc)},
        )
        return summary

    # 1) Manage TP/SL even when disarmed
    open_positions = bot_repo.list_positions(
        operator_id=operator_id,
        status="open",
        limit=50,
    )
    for pos in open_positions:
        if not isinstance(venue, PaperVenue):
            # Hyperliquid stub: no live management
            break
        try:
            result = venue.check_tp_sl(
                operator_id=operator_id,
                position=pos,
            )
        except Exception as exc:  # noqa: BLE001 — tick must continue
            summary["errors"].append(f"tp_sl {pos['id']}: {exc}")
            bot_repo.insert_event(
                operator_id=operator_id,
                kind="error",
                symbol=pos["symbol"],
                payload={"error": str(exc), "position_id": pos["id"]},
            )
            continue
        if result:
            summary["closed"].append(
                {
                    "position_id": result["position"]["id"],
                    "symbol": result["position"]["symbol"],
                    "reason": result["position"].get("close_reason"),
                }
            )
            bot_repo.insert_event(
                operator_id=operator_id,
                kind="close",
                symbol=result["position"]["symbol"],
                payload={
                    "position_id": result["position"]["id"],
                    "reason": result["position"].get("close_reason"),
                    "realized_pnl": result["position"].get("realized_pnl"),
                },
            )

    if not config["armed"]:
        bot_repo.insert_event(
            operator_id=operator_id,
            kind="heartbeat",
            payload={"armed": False, "note": "paused; tp/sl managed"},
        )
        return summary

    if isinstance(venue, HyperliquidVenue):
        summary["errors"].append("HyperliquidVenue not enabled")
        bot_repo.insert_event(
            operator_id=operator_id,
            kind="error",
            payload={"error": "HyperliquidVenue not enabled in MVP"},
        )
        return summary

    symbols = [str(s).upper() for s in (config.get("symbols") or ["BTC", "ETH"])]
    interval = str(config.get("donchian_interval") or "30m")
    period = int(config.get("donchian_period") or 20)

    resolved_candles: dict[str, list[dict[str, Any]]] = {}
    if candles_by_symbol is not None:
        resolved_candles = {
            k.upper(): v for k, v in candles_by_symbol.items() if k.upper() in symbols
        }
    else:
        for sym in symbols:
            bars = _fetch_candles_live(sym, interval=interval)
            if bars:
                resolved_candles[sym] = bars
            else:
                summary["errors"].append(f"no candles for {sym}")

    open_after = bot_repo.list_positions(
        operator_id=operator_id,
        status="open",
        limit=50,
    )
    open_symbols = {p["symbol"] for p in open_after}
    last_closed: dict[str, datetime | None] = {}
    for sym in symbols:
        last_closed[sym] = bot_repo.last_closed_at_for_symbol(
            operator_id=operator_id,
            symbol=sym,
        )

    seen: set[tuple[str, str, str]] = set()
    # Seed seen from recent events for idempotency across ticks
    for ev in bot_repo.list_events(operator_id=operator_id, limit=200):
        payload = ev.get("payload") or {}
        side = payload.get("side")
        bar_ts = payload.get("bar_ts")
        sym = ev.get("symbol")
        if (
            ev.get("kind") in {"open", "trade_signal", "skip_duplicate"}
            and sym
            and side
            and bar_ts
        ):
            seen.add((sym, str(side), str(bar_ts)))

    ctx = StrategyContext(
        armed=True,
        max_positions=int(config["max_positions"]),
        open_count=len(open_after),
        open_symbols=open_symbols,
        cooldown_seconds=int(config.get("cooldown_seconds") or 0),
        last_closed_at=last_closed,
        seen_keys=seen,
        now=datetime.now(timezone.utc),
    )

    def _on_skip(signal: TradeSignal, reason: str) -> None:
        summary["skipped"].append(
            {
                "symbol": signal.symbol,
                "side": signal.side,
                "bar_ts": signal.bar_ts,
                "reason": reason,
            }
        )
        kind = "skip_duplicate" if reason == "duplicate_bar" else "skip"
        bot_repo.insert_event(
            operator_id=operator_id,
            kind=kind,
            symbol=signal.symbol,
            payload={
                "side": signal.side,
                "bar_ts": signal.bar_ts,
                "reason": reason,
                "strategy_reason": signal.reason,
            },
        )

    signals = collect_signals(
        resolved_candles,
        period=period,
        ctx=ctx,
        on_skip=_on_skip,
    )

    for signal in signals:
        # Extra idempotency against DB
        if bot_repo.signal_already_processed(
            operator_id=operator_id,
            symbol=signal.symbol,
            side=signal.side,
            bar_ts=signal.bar_ts,
        ):
            _on_skip(signal, "duplicate_bar")
            continue
        bot_repo.insert_event(
            operator_id=operator_id,
            kind="trade_signal",
            symbol=signal.symbol,
            payload={
                "side": signal.side,
                "bar_ts": signal.bar_ts,
                "reason": signal.reason,
                "meta": signal.meta,
            },
        )
        try:
            result = venue.open(
                operator_id=operator_id,
                symbol=signal.symbol,
                side=signal.side,
                size_usd=float(config["size_usd"]),
                leverage=float(config["leverage"]),
                tp_pct=float(config["tp_pct"]),
                sl_pct=float(config["sl_pct"]),
                meta={"bar_ts": signal.bar_ts, "reason": signal.reason, **signal.meta},
            )
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"open {signal.symbol}: {exc}")
            bot_repo.insert_event(
                operator_id=operator_id,
                kind="error",
                symbol=signal.symbol,
                payload={"error": str(exc), "side": signal.side, "bar_ts": signal.bar_ts},
            )
            continue
        summary["opened"].append(
            {
                "position_id": result["position"]["id"],
                "symbol": signal.symbol,
                "side": signal.side,
                "bar_ts": signal.bar_ts,
            }
        )
        bot_repo.insert_event(
            operator_id=operator_id,
            kind="open",
            symbol=signal.symbol,
            payload={
                "side": signal.side,
                "bar_ts": signal.bar_ts,
                "position_id": result["position"]["id"],
                "entry_price": result["position"]["entry_price"],
            },
        )

    return summary
