"""Execution Venue port: PaperVenue + HyperliquidVenue stub."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Protocol

from backend.app.services import bot_repo


class VenueNotEnabled(Exception):
    """Venue no habilitado / sin credenciales (fail-closed)."""


class ExecutionVenue(Protocol):
    def open(
        self,
        *,
        operator_id: str,
        symbol: str,
        side: str,
        size_usd: float,
        leverage: float,
        tp_pct: float,
        sl_pct: float,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def close(
        self,
        *,
        operator_id: str,
        position_id: str,
        reason: str,
    ) -> dict[str, Any]: ...

    def get_mark_price(self, symbol: str) -> Decimal: ...


def _tp_sl_prices(
    *,
    side: str,
    entry: float,
    tp_pct: float,
    sl_pct: float,
) -> tuple[float, float]:
    if side == "long":
        tp = entry * (1.0 + tp_pct / 100.0)
        sl = entry * (1.0 - sl_pct / 100.0)
    else:
        tp = entry * (1.0 - tp_pct / 100.0)
        sl = entry * (1.0 + sl_pct / 100.0)
    return tp, sl


def _realized_pnl(
    *,
    side: str,
    entry: float,
    exit_price: float,
    qty: float,
) -> float:
    if side == "long":
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


def _default_mark_fn(symbol: str) -> Decimal:
    from backend.services.market_data import fetch_quotes

    quotes = fetch_quotes([symbol], bypass_cache=True)
    for q in quotes:
        price = getattr(q, "price", None)
        if price is None and isinstance(q, dict):
            price = q.get("price")
        if price is not None:
            return Decimal(str(price))
    raise VenueNotEnabled(f"no mark price for {symbol}")


class PaperVenue:
    """Fills al mark; persiste Position/Fill vía bot_repo."""

    def __init__(
        self,
        *,
        mark_fn: Callable[[str], Decimal] | None = None,
        venue_name: str = "paper",
    ) -> None:
        self._mark_fn = mark_fn or _default_mark_fn
        self.venue_name = venue_name

    def get_mark_price(self, symbol: str) -> Decimal:
        return self._mark_fn(symbol)

    def open(
        self,
        *,
        operator_id: str,
        symbol: str,
        side: str,
        size_usd: float,
        leverage: float,
        tp_pct: float,
        sl_pct: float,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mark = float(self.get_mark_price(symbol))
        if mark <= 0:
            raise bot_repo.BotRepoError(f"invalid mark for {symbol}")
        qty = float(size_usd) / mark
        tp_price, sl_price = _tp_sl_prices(
            side=side,
            entry=mark,
            tp_pct=float(tp_pct),
            sl_pct=float(sl_pct),
        )
        position = bot_repo.insert_position(
            operator_id=operator_id,
            symbol=symbol,
            side=side,
            size_usd=float(size_usd),
            qty=qty,
            leverage=float(leverage),
            entry_price=mark,
            tp_price=tp_price,
            sl_price=sl_price,
            venue=self.venue_name,
            mark_price=mark,
        )
        fill = bot_repo.insert_fill(
            position_id=position["id"],
            operator_id=operator_id,
            symbol=symbol,
            side=side,
            price=mark,
            qty=qty,
            venue=self.venue_name,
            raw={"action": "open", "meta": meta or {}},
        )
        return {"position": position, "fill": fill}

    def close(
        self,
        *,
        operator_id: str,
        position_id: str,
        reason: str,
    ) -> dict[str, Any]:
        pos = bot_repo.get_position(
            operator_id=operator_id,
            position_id=position_id,
        )
        if pos is None or pos["status"] != "open":
            raise bot_repo.BotRepoError("open position not found")
        mark = float(self.get_mark_price(pos["symbol"]))
        pnl = _realized_pnl(
            side=pos["side"],
            entry=float(pos["entry_price"]),
            exit_price=mark,
            qty=float(pos["qty"]),
        )
        closed = bot_repo.close_position_row(
            operator_id=operator_id,
            position_id=position_id,
            close_reason=reason,
            realized_pnl=pnl,
            mark_price=mark,
        )
        # Fill side: opposite of position for close bookkeeping
        close_side = "sell" if pos["side"] == "long" else "buy"
        fill = bot_repo.insert_fill(
            position_id=position_id,
            operator_id=operator_id,
            symbol=pos["symbol"],
            side=close_side,
            price=mark,
            qty=float(pos["qty"]),
            venue=self.venue_name,
            raw={"action": "close", "reason": reason},
        )
        return {"position": closed, "fill": fill}

    def check_tp_sl(
        self,
        *,
        operator_id: str,
        position: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Si mark toca TP/SL, cierra y retorna resultado; si no, None."""
        mark = float(self.get_mark_price(position["symbol"]))
        side = position["side"]
        tp = float(position["tp_price"])
        sl = float(position["sl_price"])
        reason: str | None = None
        if side == "long":
            if mark >= tp:
                reason = "tp"
            elif mark <= sl:
                reason = "sl"
        else:
            if mark <= tp:
                reason = "tp"
            elif mark >= sl:
                reason = "sl"
        if reason is None:
            # Keep mark fresh so UI / equity reflect live price between closes.
            bot_repo.update_mark_price(
                operator_id=operator_id,
                position_id=position["id"],
                mark_price=mark,
            )
            return None
        return self.close(
            operator_id=operator_id,
            position_id=position["id"],
            reason=reason,
        )


class HyperliquidVenue:
    """Stub fail-closed hasta secrets + ADR live."""

    def get_mark_price(self, symbol: str) -> Decimal:
        raise VenueNotEnabled("HyperliquidVenue not enabled in MVP")

    def open(
        self,
        *,
        operator_id: str,
        symbol: str,
        side: str,
        size_usd: float,
        leverage: float,
        tp_pct: float,
        sl_pct: float,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise VenueNotEnabled("HyperliquidVenue not enabled in MVP")

    def close(
        self,
        *,
        operator_id: str,
        position_id: str,
        reason: str,
    ) -> dict[str, Any]:
        raise VenueNotEnabled("HyperliquidVenue not enabled in MVP")


def get_venue(
    name: str,
    *,
    mark_fn: Callable[[str], Decimal] | None = None,
) -> ExecutionVenue:
    key = (name or "paper").strip().lower()
    if key == "paper":
        return PaperVenue(mark_fn=mark_fn)
    if key == "hyperliquid":
        return HyperliquidVenue()
    raise VenueNotEnabled(f"unknown venue: {name}")
