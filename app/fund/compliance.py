"""Pre-trade compliance — the rules that are not ours to weigh.

Deliberately separate from ``risk.py``. A risk limit is the mandate's own
judgement: we chose 20% single-name concentration and we can choose 25%
tomorrow. A compliance rule is imposed from outside — by the regulator or by
the broker — and no view about the trade's merit changes it. Mixing the two
would let a risk-limit edit silently widen a legal constraint, and would make
"the gate said no" ambiguous about whether the fund disagreed with the trade or
was forbidden from placing it.

The rule that actually binds this fund is FINRA's pattern-day-trader rule.
Four day trades inside five rolling business days, in a margin account under
$25,000 of equity, flags the account — and a flagged account under the
threshold is restricted to closing-only for ninety days. This fund holds about
$2,000 and runs an intraday strategy that flips several times a day, so the
distance between "working normally" and "cannot open a position until
November" is four clicks.

Alpaca reports ``daytrade_count`` on the account and enforces the rule itself
on a live account. Relying on that enforcement would mean a human approves an
order, the spine submits it, and the venue rejects it — the operator learns
about a ninety-day cliff from a rejection message. So the check runs before the
order is ever shown for approval.

MEASURED, 2026-08-14, against the paper account this fund trades: Alpaca
returns ``daytrade_count = None``, ``pattern_day_trader = None`` and
``multiplier = 4`` on a $2,036 balance. A live account that size would carry
multiplier 2 and a real day-trade counter — 4x day-trading buying power is
only granted above the $25,000 threshold. In other words the paper venue does
not simulate this rule at all, and will cheerfully let the fund day trade past
the point where the real one would be restricted for ninety days.

That is why ``DayTradeLedger`` exists. It was designed as a backstop for an
unreachable broker; on paper it turns out to be the only count there is, and
the sim-to-real divergence it papers over is exactly the kind a PoC is
supposed to surface rather than inherit. Before this fund trades a live
account, re-check that ``daytrade_count`` is populated there and let the
broker's number take over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.fund.connectors.base import Order, Side
from app.fund.events import EventStore, EventType

#: The venue's own clock. A "trading day" is an exchange day, not a UTC day —
#: 21:00 UTC is the same session as 14:00 UTC in New York but a different
#: calendar date, and counting day trades on UTC dates would split one session
#: in two and undercount exactly at the boundary that matters.
MARKET_TZ = ZoneInfo("America/New_York")

#: FINRA's threshold. Above this, the pattern-day-trader designation carries no
#: restriction and the check stops applying.
PDT_EQUITY_THRESHOLD = 25_000.0

#: The rule flags an account on the *fourth* day trade in five business days,
#: so the third is the last safe one. Block when placing this order would make
#: the count reach the flag.
PDT_MAX_DAY_TRADES = 4

#: How far back to look for our own day-trade count. Five business days is the
#: regulation's window; calendar days are used with a weekend allowance because
#: the exact holiday calendar is not worth carrying for a backstop count.
PDT_LOOKBACK_DAYS = 7


@dataclass
class AccountState:
    """What the broker says about the account's standing.

    Every field is Optional and defaults to None because "we could not read it"
    is a distinct answer from any particular value, and the two must not be
    allowed to collapse. ``known`` is False when the fetch failed outright.
    """

    known: bool = False
    equity: Optional[float] = None
    #: Settled cash and purchasing power at the broker (PM R42, 2026-08-23).
    #:
    #: ``equity`` was the only money this class carried, and equity is the
    #: WRONG number for the two questions the trade path actually asks: "can
    #: this order be paid for" and "would it borrow". A fully-invested account
    #: has healthy equity and no cash, and an account whose buying power
    #: exceeds its cash is one where the next BUY is on margin — which the
    #: fund's own mandate has an opinion about and could not previously see.
    #:
    #: Optional and None-by-default like every other field here, and for the
    #: same reason: the broker not reporting cash is a different fact from the
    #: broker reporting zero cash, and a fund that cannot tell those apart will
    #: eventually treat "I could not read it" as "there is none". Note the
    #: direction that costs money: read as zero, a real balance looks spent;
    #: read as zero, an EMPTY balance looks the same, and only one of those is
    #: true at a time.
    #:
    #: NOT YET A BLOCK. Nothing in ``ComplianceGate`` refuses on either field —
    #: they are READ and REPORTED, and any refusal built on them is a mandate
    #: decision for a human, not a check a builder adds while wiring a getter.
    cash: Optional[float] = None
    buying_power: Optional[float] = None
    daytrade_count: Optional[int] = None
    pattern_day_trader: Optional[bool] = None
    trading_blocked: Optional[bool] = None
    account_blocked: Optional[bool] = None
    shorting_enabled: Optional[bool] = None
    status: Optional[str] = None
    #: Why the read failed, when it did.
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "known": self.known,
            "equity": self.equity,
            "cash": self.cash,
            "buying_power": self.buying_power,
            "daytrade_count": self.daytrade_count,
            "pattern_day_trader": self.pattern_day_trader,
            "trading_blocked": self.trading_blocked,
            "account_blocked": self.account_blocked,
            "shorting_enabled": self.shorting_enabled,
            "status": self.status,
            "error": self.error,
        }

    @classmethod
    def unknown(cls, error: str | None = None) -> "AccountState":
        return cls(known=False, error=error)


@dataclass
class ComplianceDecision:
    ok: bool
    blocks: list[str] = field(default_factory=list)
    #: Non-blocking observations worth showing the operator (e.g. "one day
    #: trade left"). A warning that only appears once it is too late to act on
    #: is not a warning.
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "blocks": self.blocks, "warnings": self.warnings}


def market_day(ts: str | datetime) -> str | None:
    """The exchange date a timestamp falls on, as YYYY-MM-DD in market time."""
    if isinstance(ts, str):
        raw = ts.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        dt = ts
    if dt.tzinfo is None:
        return None
    return dt.astimezone(MARKET_TZ).date().isoformat()


class DayTradeLedger:
    """Our own day-trade count, folded from the event log.

    The broker's ``daytrade_count`` is authoritative — it is the number the
    broker enforces on — but it is only available while the API answers. This
    is the backstop, and it is also a cross-check: the reconciler already
    treats a divergence between our books and the venue's as a finding rather
    than an embarrassment, and this is the same idea applied to a count.

    A day trade is opening and closing the same security within one session.
    Both directions count: buy-then-sell and sell-then-buy (covering a short)
    are each a round trip inside the day.
    """

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _fills(self, since_days: int) -> list[dict[str, Any]]:
        cutoff = datetime.now(MARKET_TZ) - timedelta(days=since_days)
        out: list[dict[str, Any]] = []
        for e in self._store.stream(limit=100_000):
            if e.get("type") != EventType.ORDER_FILLED.value:
                continue
            day = market_day(e.get("ts") or "")
            if day is None or day < cutoff.date().isoformat():
                continue
            out.append(e)
        return out

    @staticmethod
    def _sides_by_day_symbol(fills: list[dict[str, Any]]) -> dict[tuple[str, str], set[str]]:
        seen: dict[tuple[str, str], set[str]] = {}
        for e in fills:
            p = e.get("payload") or {}
            symbol = p.get("symbol")
            side = p.get("side")
            day = market_day(e.get("ts") or "")
            if not symbol or not side or day is None:
                continue
            seen.setdefault((day, str(symbol)), set()).add(str(side))
        return seen

    def count(self, lookback_days: int = PDT_LOOKBACK_DAYS) -> int:
        """Round trips completed inside a single session, over the window."""
        pairs = self._sides_by_day_symbol(self._fills(lookback_days))
        return sum(1 for sides in pairs.values() if len(sides) >= 2)

    def traded_today(self, symbol: str) -> set[str]:
        """Which sides this symbol has already filled in today's session."""
        today = datetime.now(MARKET_TZ).date().isoformat()
        pairs = self._sides_by_day_symbol(self._fills(2))
        return pairs.get((today, symbol), set())

    def would_create_day_trade(self, order: Order) -> bool:
        """True when filling this order closes a position opened this session.

        Conservative by construction: any opposite-side fill in the same symbol
        today makes this a day trade. Partial offsets are still day trades, so
        there is no quantity arithmetic to get wrong.
        """
        opposite = Side.SELL.value if order.side == Side.BUY else Side.BUY.value
        return opposite in self.traded_today(order.symbol)


class ComplianceGate:
    """Checks that cannot be overridden by a view about the trade."""

    def __init__(self, ledger: DayTradeLedger | None = None):
        self._ledger = ledger or DayTradeLedger()

    def check(self, order: Order, account: AccountState) -> ComplianceDecision:
        blocks: list[str] = []
        warnings: list[str] = []

        # --- the broker has closed the account or the trading desk ----------
        if account.account_blocked:
            blocks.append("broker reports the account is blocked")
        if account.trading_blocked:
            blocks.append("broker reports trading is blocked on this account")

        # --- shorting ------------------------------------------------------
        # Only relevant to a sell that goes beyond flat. The risk gate already
        # measures how much of a sell is exposure-increasing; here we only need
        # to know whether opening a short is permitted at all.
        if order.side == Side.SELL and account.shorting_enabled is False:
            warnings.append(
                "shorting is disabled on this account — a sell beyond flat will "
                "be rejected by the venue"
            )

        # THE PDT BLOCK WAS RETIRED HERE (2026-08-27, CEO signature on AB4-2,
        # verbatim "sign E20-1 and AB4-2 - both cleared review"). The rule it
        # enforced no longer exists: SEC approved the FINRA amendment
        # 2026-04-14 (Reg Notice 26-10), effective 2026-06-04; Alpaca
        # implemented same day and deleted the pattern_day_trader API fields
        # by 2026-07-06. All four facts URL-verified by the adversary blind
        # (docs/reviews/ADVERSARY_BATCH4_2026-08-24.md item 2). The block read
        # only a day-trade count — no margin-deficiency logic existed here, so
        # retiring it removed nothing that covered the replacement hazard,
        # which is de-minimis-excused below $1,000. Removing a compliance
        # check is a LOOSENING and took the full chain: adversary blind pass,
        # then the CEO's click. `DayTradeLedger` stays: the count is still an
        # honest fact about the account's trading, and /fund/compliance still
        # reports it beside `retired: true`.

        return ComplianceDecision(ok=not blocks, blocks=blocks, warnings=warnings)

