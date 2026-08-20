"""Transaction cost analysis — what the fund actually paid to trade.

The backtester charges a `CostModel` of a couple of basis points a side and
reports a Sharpe ratio net of it. Nothing has ever checked that number against
a fill. The first real order in this fund's life, MSFT, came back about 23
cents away from the price on the approval card — on a $497 stock that is
roughly 4.6bps, more than double the assumption, on one order in a quiet
market.

Until realised cost is measured, every Sharpe ratio in the system is a
statement about an assumption rather than about the strategy, and a strategy
that flips several times a day is exactly where a wrong cost assumption does
the most damage: at 5.5 round trips a day, an error of 2bps a side compounds to
something like 30 percentage points a year.

Everything here is folded from events already in the log. No new bookkeeping,
and it applies retroactively to every order the fund has ever placed.

The decomposition, following Perold's implementation shortfall:

    decision price   the quote shown on the approval card (ORDER_PROPOSED)
    arrival price    the market when we submitted     (ORDER_SUBMITTED)
    fill price       what we actually got             (ORDER_FILLED)

    delay      = arrival - decision   the market moving while a human decided
    execution  = fill    - arrival    the cost of crossing the spread
    total      = fill    - decision   what it cost against the decision

Signed so that positive is always a cost: paying above the decision price on a
buy, or receiving below it on a sell. The split matters because the two halves
have different remedies — delay is an argument for approving faster or letting
the machine size smaller; execution is an argument for limit orders.

Orders placed before arrival-price capture existed have a total but no split.
They report `has_split: False` rather than a fabricated zero, because a delay
cost of "unknown" and one of "nothing" are not the same claim.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.fund.events import EventStore, EventType

BPS = 10_000.0

#: What the backtester assumes, per side, so realised cost can be read against
#: the number the Sharpe ratios were computed with. Kept in sync by eye rather
#: than imported, because backtest.CostModel is a default and callers override
#: it; this is the figure the fund's own backtests were actually run at.
#: Kept only so an old import does not break. The live number is
#: costassumption.DEFAULT_SLIPPAGE_BPS, which the backtests also read —
#: two copies of one belief is how they drifted apart in the first place.
from app.fund.costassumption import DEFAULT_SLIPPAGE_BPS as ASSUMED_COST_BPS_PER_SIDE


def _ts(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None          # reject NaN


def _gap(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
    if a is None or b is None:
        return None
    return (b - a).total_seconds()


@dataclass
class OrderCost:
    order_id: str
    symbol: str
    side: str
    strategy_id: Optional[str]
    qty: Optional[float]
    decision_price: Optional[float]
    arrival_price: Optional[float]
    fill_price: Optional[float]
    notional_usd: Optional[float]
    fees_usd: Optional[float]
    #: Seconds a human held the order, and seconds the venue held it.
    approval_latency_s: Optional[float]
    submit_to_fill_s: Optional[float]
    total_bps: Optional[float]
    delay_bps: Optional[float]
    execution_bps: Optional[float]
    fees_bps: Optional[float]
    total_usd: Optional[float]
    has_split: bool
    proposed_ts: Optional[str]
    filled_ts: Optional[str]
    #: Venue from the OrderSubmitted leg. Load-bearing for the assumption
    #: verdict: the paper connector fills at its own quote (paper.py:116 is
    #: the same call pipeline.py:215 records as arrival_price), so a paper
    #: fill's execution slippage is identically zero at any sample size — a
    #: tautology, not a measurement (validator audit 8b863152, 2026-08-20).
    venue: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


def _bps(reference: Optional[float], got: Optional[float], side: str) -> Optional[float]:
    """Cost in bps, signed so positive always means worse for the fund.

    A buy filled above its reference paid; a sell filled below it gave up the
    difference. Without the sign flip, a sell that executed badly would show as
    a saving and the aggregate would net two real costs to nearly zero.
    """
    if reference is None or got is None or reference <= 0:
        return None
    direction = 1.0 if side == "buy" else -1.0
    return direction * (got - reference) / reference * BPS


class TransactionCosts:
    """Realised trading cost, folded from the order lifecycle in the event log."""

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _lifecycles(self, limit: int = 100_000) -> dict[str, dict[str, Any]]:
        """Group every order event by order id, keeping the ones that matter."""
        want = {
            EventType.ORDER_PROPOSED.value,
            EventType.ORDER_APPROVED.value,
            EventType.ORDER_SUBMITTED.value,
            EventType.ORDER_FILLED.value,
        }
        out: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(limit=limit):
            t = e.get("type")
            if t not in want:
                continue
            oid = str(e.get("aggregate_id"))
            out.setdefault(oid, {})[t] = e
        return out

    def costs(self, limit: int = 100_000) -> list[OrderCost]:
        rows: list[OrderCost] = []
        for oid, ev in self._lifecycles(limit).items():
            filled = ev.get(EventType.ORDER_FILLED.value)
            proposed = ev.get(EventType.ORDER_PROPOSED.value)
            # An unfilled order has no realised cost, and an order we never
            # proposed has no decision price to measure against. Both are
            # skipped rather than defaulted.
            if not filled or not proposed:
                continue
            rows.append(self._one(oid, proposed, ev.get(EventType.ORDER_APPROVED.value),
                                  ev.get(EventType.ORDER_SUBMITTED.value), filled))
        rows.sort(key=lambda r: r.filled_ts or "", reverse=True)
        return rows

    @staticmethod
    def _one(oid, proposed, approved, submitted, filled) -> OrderCost:
        p_pay = proposed.get("payload") or {}
        s_pay = (submitted or {}).get("payload") or {}
        f_pay = filled.get("payload") or {}

        decision = _num((p_pay.get("impact_preview") or {}).get("quote_price"))
        arrival = _num(s_pay.get("arrival_price"))
        fill = _num(f_pay.get("avg_price"))
        qty = _num(f_pay.get("filled_qty"))
        fees = _num(f_pay.get("fees")) or 0.0
        side = str(f_pay.get("side") or p_pay.get("side") or "buy")

        t_prop = _ts(proposed.get("ts"))
        t_appr = _ts((approved or {}).get("ts"))
        t_subm = _ts((submitted or {}).get("ts"))
        t_fill = _ts(filled.get("ts"))

        total_bps = _bps(decision, fill, side)
        delay_bps = _bps(decision, arrival, side)
        execution_bps = _bps(arrival, fill, side)

        notional = (qty * fill) if (qty is not None and fill is not None) else None
        total_usd = (notional * total_bps / BPS) if (notional and total_bps is not None) else None
        fees_bps = (fees / notional * BPS) if (notional and notional > 0) else None

        return OrderCost(
            order_id=oid, symbol=str(f_pay.get("symbol") or p_pay.get("symbol") or "?"),
            side=side, strategy_id=f_pay.get("strategy_id") or p_pay.get("strategy_id"),
            qty=qty, decision_price=decision, arrival_price=arrival, fill_price=fill,
            notional_usd=notional, fees_usd=fees,
            # Approval latency is measured from the proposal, not the approval
            # event, because the wait the market sees is the whole human pause.
            approval_latency_s=_gap(t_prop, t_subm) if t_subm else _gap(t_prop, t_appr),
            submit_to_fill_s=_gap(t_subm, t_fill),
            total_bps=total_bps, delay_bps=delay_bps, execution_bps=execution_bps,
            fees_bps=fees_bps, total_usd=total_usd,
            has_split=(delay_bps is not None and execution_bps is not None),
            proposed_ts=proposed.get("ts"), filled_ts=filled.get("ts"),
            # The fill's own venue first (recorded on OrderFilled since
            # 2026-08-20), falling back to the submitted leg for the fills that
            # predate it. Absent on neither leg stays None — not "paper".
            venue=f_pay.get("venue") or s_pay.get("venue"),
        )

    # --- aggregates ---------------------------------------------------------
    def summary(self, limit: int = 100_000) -> dict[str, Any]:
        return summarise(self.costs(limit))

    def by_strategy(self, limit: int = 100_000) -> dict[str, Any]:
        rows = self.costs(limit)
        groups: dict[str, list[OrderCost]] = {}
        for r in rows:
            groups.setdefault(r.strategy_id or "(discretionary)", []).append(r)
        return {k: summarise(v) for k, v in groups.items()}

    def by_symbol(self, limit: int = 100_000) -> dict[str, Any]:
        """Realised cost per instrument.

        Per-instrument is the cut anyone asking "is our cost model right for
        ETFs vs single names?" actually wants — and the cut that makes the
        sample size per instrument visible, which is the finding that refused
        a per-instrument cost model in the first place (max 2 informative price
        events per instrument, against RELIABLE_SAMPLE = 20).
        """
        rows = self.costs(limit)
        groups: dict[str, list[OrderCost]] = {}
        for r in rows:
            groups.setdefault(r.symbol or "?", []).append(r)
        return {k: summarise(v) for k, v in sorted(groups.items())}

    def by_venue(self, limit: int = 100_000) -> dict[str, Any]:
        rows = self.costs(limit)
        groups: dict[str, list[OrderCost]] = {}
        for r in rows:
            groups.setdefault(r.venue or "(unrecorded)", []).append(r)
        return {k: summarise(v) for k, v in sorted(groups.items())}


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "worst": None, "best": None}
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 2),
        "median": round(statistics.median(values), 2),
        # Worst = most expensive, which is the largest positive number.
        "worst": round(max(values), 2),
        "best": round(min(values), 2),
    }


def summarise(rows: list[OrderCost]) -> dict[str, Any]:
    """Realised cost across a set of orders, against what was assumed."""
    total = [r.total_bps for r in rows if r.total_bps is not None]
    delay = [r.delay_bps for r in rows if r.delay_bps is not None]
    execution = [r.execution_bps for r in rows if r.execution_bps is not None]
    latency = [r.approval_latency_s for r in rows if r.approval_latency_s is not None]
    usd = [r.total_usd for r in rows if r.total_usd is not None]

    # Graded against the SAME number the backtests charge. These were two
    # separate constants that disagreed — LEAN priced 5bps a side while this
    # compared to 2 — so "we are over assumption" was meaningless, because
    # there were two assumptions. A comparison against a number no backtest
    # uses validates nothing, which is the entire point of measuring.
    from app.fund.costassumption import compare
    # The verdict compares the EXECUTION leg (arrival -> fill), never
    # total_bps: the constant is documented as the spread, and total_bps is
    # decision -> fill, which is mostly market drift during the human
    # approval pause (measured: mean 523.6s of latency put -12.59bps of
    # drift into a "reliable: true, cheaper than modelled" verdict,
    # 2026-08-20). Paper-venue fills are excluded — the paper connector
    # fills at its own quote, so their execution cost is identically zero
    # by construction, a tautology that would drag the average toward zero
    # as paper fills accumulate. Validator audit 8b863152.
    informative = [r.execution_bps for r in rows
                   if r.execution_bps is not None and (r.venue or "") != "paper"]
    # None when nothing informative has filled, deliberately preserved: the
    # alternative is a verdict block whose numbers are all None, which reads
    # like a measurement of zero to anything scanning for a field rather
    # than a shape.
    verdict = (compare(statistics.fmean(informative), len(informative))
               if informative else None)

    # The same "informative fills only" discipline as the verdict, applied to
    # the STATS a panel quotes.
    #
    # The verdict leg was fixed in August; the stats above were not, and the
    # Monitor's EXECUTION QUALITY panel reads those (CDO D3, CTO-confirmed).
    # Every paper fill contributes an execution cost of exactly 0.00bps by
    # construction — paper.py fills at the same quote pipeline.py records as
    # arrival — so the more paper fills accumulate the closer the headline
    # drifts to "we trade for free". These blocks are the same statistics over
    # the fills that carry information, and they NAME the venues they counted
    # so the panel can label itself instead of implying it measured everything.
    informative_rows = [r for r in rows if (r.venue or "") != "paper"]
    venues_counted = sorted({r.venue for r in informative_rows if r.venue})
    venues_excluded = sorted({r.venue for r in rows if (r.venue or "") == "paper"})
    informative_block = {
        "orders": len(informative_rows),
        "venues_counted": venues_counted,
        "venues_excluded": venues_excluded,
        "excluded_orders": len(rows) - len(informative_rows),
        "total_bps": _stats([r.total_bps for r in informative_rows
                             if r.total_bps is not None]),
        "execution_bps": _stats(informative),
        # Said plainly rather than left to be inferred from n: a zero-sample
        # block is an ABSENCE of measurement, and a panel that renders "0.00bps"
        # from it is reporting a number nobody measured.
        "measurable": bool(informative),
        "reason": (None if informative else
                   "no fills on a venue that can measure execution cost — the "
                   "paper venue fills at its own quote, so its slippage is "
                   "identically zero at any sample size"),
    }

    return {
        "orders": len(rows),
        # ALL venues, paper included. Kept because existing consumers read them,
        # named here so nobody quotes them as a cost measurement again.
        "total_bps": _stats(total),
        "delay_bps": _stats(delay),
        "execution_bps": _stats(execution),
        "approval_latency_s": _stats(latency),
        "realised_cost_usd": round(sum(usd), 2) if usd else None,
        "split_available": len(delay),
        "vs_assumption": verdict,
        "informative": informative_block,
    }
