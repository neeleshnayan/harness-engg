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
import time
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

    def __init__(self, key=None, secret=None, paper=None, trading=None, data=None,
                 price_ttl=None, clock=None):
        self._key = key or os.getenv("ALPACA_API_KEY")
        self._secret = secret or os.getenv("ALPACA_SECRET_KEY")
        self._paper = (os.getenv("ALPACA_PAPER", "true").lower() != "false") if paper is None else paper
        self._t = trading   # inject in tests; else built lazily from creds
        self._d = data
        # Short TTL cache so repeated NAV computes (cockpit polls every ~4s) don't
        # hammer the data API. Tunable via ALPACA_PRICE_TTL (seconds).
        self._ttl = float(os.getenv("ALPACA_PRICE_TTL", "5")) if price_ttl is None else float(price_ttl)
        self._clock = clock or time.monotonic
        self._pcache: dict[str, tuple[float, float]] = {}
        #: symbol -> age(s) of the mark we are serving after a failed refresh
        self._stale: dict[str, float] = {}

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
        now = self._clock()
        hit = self._pcache.get(symbol)
        if hit is not None and (now - hit[0]) < self._ttl:
            self._stale.pop(symbol, None)
            return hit[1]
        try:
            px = self._fetch_price(symbol)
        except Exception:  # noqa: BLE001 — a feed blip must not blank the risk page
            # Fall back to the last price we actually saw, and RECORD that we
            # did. A transient market-data failure taking down the whole risk
            # monitor is worse than a mark a few seconds old — but a stale mark
            # presented as fresh is worse than both, so staleness is tracked and
            # reported (see stale_marks) rather than silently swallowed.
            if hit is not None:
                self._stale[symbol] = round(now - hit[0], 1)
                return hit[1]
            raise
        self._stale.pop(symbol, None)
        self._pcache[symbol] = (now, px)
        return px

    def stale_marks(self) -> dict[str, float]:
        """Symbols currently being served from a failed refresh, and how many
        seconds old that mark is. Empty means every mark is fresh."""
        return dict(self._stale)

    def _fetch_price(self, symbol: str) -> float:
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

    def activities(self, after: str | None = None) -> list[dict[str, Any]]:
        """Non-trade account activities — dividends, interest, splits.

        These are things the venue does TO the book without us ordering them.
        Returned raw and unfiltered; interpreting them is the ingester's job, and
        an activity type we do not recognise must reach it rather than being
        silently dropped here.

        ``id`` is the venue's own idempotency key and is passed straight through.
        """
        # alpaca-py's TradingClient wraps no activities method (only BrokerClient
        # does, and that is the firm-level API with different credentials), but
        # the Trading REST endpoint exists — so this goes through the client's
        # raw GET rather than pulling in a second SDK surface.
        try:
            path = "/account/activities"
            if after:
                path += f"?after={after}"
            raw = self._trading().get(path)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"could not read account activities: {e}") from e

        def field(a: Any, *names: str):
            for n in names:
                v = a.get(n) if isinstance(a, dict) else getattr(a, n, None)
                if v not in (None, ""):
                    return v
            return None

        out: list[dict[str, Any]] = []
        for a in raw or []:
            out.append({
                "id": field(a, "id"),
                "activity_type": str(field(a, "activity_type") or ""),
                "symbol": (field(a, "symbol") or None),
                # Cash activities carry `date`; trade activities carry
                # `transaction_time`. Take whichever is present rather than
                # assuming one shape for both.
                "date": field(a, "date", "transaction_time"),
                "net_amount": field(a, "net_amount"),
                "qty": field(a, "qty"),
                "per_share_amount": field(a, "per_share_amount"),
                "description": field(a, "description"),
            })
        return out

    def market_open(self) -> bool | None:
        """Is the venue open right now? ``None`` when we could not find out.

        The distinction matters: "closed" is a reason to hold, but "unknown" is
        not the same as "closed" and must not silently become it — a caller that
        treats an unreachable clock as a closed market stops trading during an
        API blip, and one that treats it as open sends orders into the dark. The
        caller decides; this only reports what it knows.

        Deliberately uncached. It changes at the open and the close, which are
        precisely the moments a stale answer is wrong.
        """
        try:
            return bool(self._trading().get_clock().is_open)
        except Exception:  # noqa: BLE001
            return None

    def account_info(self) -> dict[str, Any]:
        if not (self._key and self._secret):
            return {
                "venue": self.name,
                "configured": False,
                "mode": "unconfigured",
                "message": "Alpaca API credentials missing. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env",
            }
        try:
            acct = self._trading().get_account()
            return {
                "venue": self.name,
                "configured": True,
                "mode": "alpaca_paper" if self._paper else "alpaca_live",
                "portfolio_value": float(acct.portfolio_value),
                "equity": float(acct.equity),
                "cash": float(acct.cash),
                "buying_power": float(acct.buying_power),
                "currency": getattr(acct, "currency", "USD"),
                "status": getattr(acct, "status", "ACTIVE"),
                **self._standing(acct).to_dict(),
            }
        except Exception as e:
            return {
                "venue": self.name,
                "configured": True,
                "error": str(e),
            }

    def account_state(self) -> "AccountState":
        """The broker's view of what this account is *allowed* to do.

        Split out from ``account_info`` because the compliance gate needs a
        typed answer on the trade path, and because the distinction between a
        flag that is False and a flag we could not read must survive the trip.
        An unreadable account is ``AccountState.unknown()``, never a set of
        permissive defaults.
        """
        from app.fund.compliance import AccountState

        if not (self._key and self._secret):
            return AccountState.unknown("Alpaca credentials not configured")
        try:
            return self._standing(self._trading().get_account())
        except Exception as e:  # noqa: BLE001
            return AccountState.unknown(str(e))

    @staticmethod
    def _standing(acct: Any) -> "AccountState":
        """Map an Alpaca account object onto our own flags.

        ``getattr`` with a None default throughout: the SDK has added and
        renamed account fields between versions, and a missing attribute must
        read as "unknown" rather than raising and taking the whole account
        fetch down with it.
        """
        from app.fund.compliance import AccountState

        def num(name: str) -> float | None:
            v = getattr(acct, name, None)
            return None if v is None else float(v)

        def count(name: str) -> int | None:
            v = getattr(acct, name, None)
            return None if v is None else int(v)

        def flag(name: str) -> bool | None:
            v = getattr(acct, name, None)
            return None if v is None else bool(v)

        status = getattr(acct, "status", None)
        return AccountState(
            known=True,
            equity=num("equity"),
            daytrade_count=count("daytrade_count"),
            pattern_day_trader=flag("pattern_day_trader"),
            trading_blocked=flag("trading_blocked"),
            account_blocked=flag("account_blocked"),
            shorting_enabled=flag("shorting_enabled"),
            status=None if status is None else str(status),
        )

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
