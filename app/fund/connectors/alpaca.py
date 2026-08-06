"""Alpaca connector — the live venue (paper or real), same protocol as PaperConnector.

Direct programmatic integration via ``alpaca-py`` (not the Alpaca *MCP server*,
which is an LLM tool surface and must stay out of the deterministic money path).

Idempotency is venue-side and real: we set Alpaca's ``client_order_id`` to our
own order id, so ``execute()`` first looks the order up by that id and returns
the existing handle on any replay/retry — never a second submission. This is
the async-boundary guarantee the spine relies on.

Config comes from the environment (never committed):
    ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER (default "true")

The SDK-touching calls are thin; the tricky mapping (order status, positions)
is extracted into pure functions that are unit-tested without a network.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from app.fund.connectors.base import (
    Balance,
    Connector,
    ExecStatus,
    FillState,
    Order,
    Position,
    Quote,
    Side,
    ValidationResult,
    VenueRef,
)

# Alpaca order.status -> our FillState
_FAILED = {"canceled", "cancelled", "rejected", "expired", "done_for_day", "stopped", "suspended"}


def map_status(status: str, filled_qty: Any, filled_avg_price: Any, fees: Any = 0) -> ExecStatus:
    """Pure: Alpaca order status/fills -> ExecStatus. Unit-tested."""
    s = (status or "").lower()
    qty = float(filled_qty or 0)
    px = float(filled_avg_price) if filled_avg_price not in (None, "", "None") else None
    if s == "filled":
        state = FillState.FILLED
    elif s == "partially_filled":
        state = FillState.PARTIAL
    elif s in _FAILED:
        state = FillState.FAILED
    else:
        state = FillState.PENDING
    return ExecStatus(state=state, filled_qty=qty, avg_price=px, fees=float(fees or 0),
                      reason=(status if state == FillState.FAILED else None))


def map_positions(raw: list[Any]) -> list[Position]:
    """Pure: Alpaca positions -> our Positions. Unit-tested."""
    out = []
    for p in raw:
        out.append(Position(
            venue="alpaca",
            symbol=getattr(p, "symbol", None) or p["symbol"],
            qty=float(getattr(p, "qty", None) if hasattr(p, "qty") else p["qty"]),
            avg_price=float(getattr(p, "avg_entry_price", None) if hasattr(p, "avg_entry_price")
                            else p["avg_entry_price"]),
        ))
    return out


class AlpacaConnector(Connector):
    name = "alpaca"

    def __init__(self, key=None, secret=None, paper=None, trading=None, data=None):
        self._key = key or os.getenv("ALPACA_API_KEY")
        self._secret = secret or os.getenv("ALPACA_SECRET_KEY")
        self._paper = (os.getenv("ALPACA_PAPER", "true").lower() != "false") if paper is None else paper
        self._t = trading   # inject in tests; else built lazily from creds
        self._d = data

    # --- lazy SDK clients --------------------------------------------------
    def _trading(self):
        if self._t is None:
            if not (self._key and self._secret):
                raise RuntimeError("Alpaca not configured: set ALPACA_API_KEY / ALPACA_SECRET_KEY")
            from alpaca.trading.client import TradingClient
            self._t = TradingClient(self._key, self._secret, paper=self._paper)
        return self._t

    def _data_client(self):
        if self._d is None:
            if not (self._key and self._secret):
                raise RuntimeError("Alpaca not configured: set ALPACA_API_KEY / ALPACA_SECRET_KEY")
            from alpaca.data.historical import StockHistoricalDataClient
            self._d = StockHistoricalDataClient(self._key, self._secret)
        return self._d

    # --- pricing -----------------------------------------------------------
    def price(self, symbol: str) -> float:
        from alpaca.data.requests import StockLatestTradeRequest
        res = self._data_client().get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbol)
        )
        return float(res[symbol].price)

    def quote(self, order: Order) -> Quote:
        px = order.limit_price if order.limit_price is not None else self.price(order.symbol)
        return Quote(symbol=order.symbol, price=float(px))

    def validate(self, order: Order) -> ValidationResult:
        errors = []
        if order.qty <= 0:
            errors.append("qty must be positive")
        if not order.symbol:
            errors.append("symbol required")
        return ValidationResult(ok=not errors, errors=errors)

    # --- execution (idempotent via client_order_id) ------------------------
    def execute(self, order: Order, idempotency_key: str) -> VenueRef:
        t = self._trading()
        existing = self._get_by_client_id(t, idempotency_key)
        if existing is not None:
            return VenueRef(venue=self.name, ref_id=str(existing.id))
        req = self._build_request(order, idempotency_key)
        submitted = t.submit_order(order_data=req)
        return VenueRef(venue=self.name, ref_id=str(submitted.id))

    def poll(self, ref: VenueRef) -> ExecStatus:
        o = self._trading().get_order_by_id(ref.ref_id)
        return map_status(getattr(o, "status", None), getattr(o, "filled_qty", 0),
                          getattr(o, "filled_avg_price", None))

    def positions(self) -> list[Position]:
        return map_positions(self._trading().get_all_positions())

    def balances(self) -> list[Balance]:
        acct = self._trading().get_account()
        return [Balance(venue=self.name, asset="USD", amount=float(acct.cash))]

    # --- helpers -----------------------------------------------------------
    @staticmethod
    def _get_by_client_id(trading, client_order_id: str):
        try:
            return trading.get_order_by_client_order_id(client_order_id)
        except Exception:
            return None  # not found -> safe to submit

    def _build_request(self, order: Order, client_order_id: str):
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
        side = OrderSide.BUY if order.side == Side.BUY else OrderSide.SELL
        common = dict(symbol=order.symbol, qty=order.qty, side=side,
                      time_in_force=TimeInForce.DAY, client_order_id=client_order_id)
        if order.limit_price is not None:
            return LimitOrderRequest(limit_price=order.limit_price, **common)
        return MarketOrderRequest(**common)
