"""Execution history — every fill, and every round-trip it closed.

:mod:`app.fund.projections.strategy` folds fills into a single realized number
per strategy. That answers "how much has this made" and nothing else. An operator
watching a live strategy asks narrower questions:

  * when did it buy, when did it sell, and at what price?
  * which of those trades made money, and by how much?
  * is the P&L one lucky trade, or a distribution?

So this is a second fold over the SAME events, keeping what the attribution
throws away: the individual fills in order, and the round-trip each sale closed.

Two honesty notes that shape the output:

**Average-cost basis, not FIFO.** The fund's accounting is average cost (see the
attribution projection), and mixing methods between two views of one book would
produce two different realized totals from the same events. So a round-trip here
closes against the running average, and its "entry" is a *quantity-weighted
average* entry across the lots it consumed — reported under that name, because a
single entry timestamp would be a fiction when the position was built over five
buys.

**Fills are the only truth.** Nothing is inferred from targets, intents or
signals. A strategy that was supposed to trade and did not produces an empty
history, not a modelled one.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.fund.events import EventStore, EventType
from app.fund.money import D, f, money
# READ, not re-declared. This module and the attribution projection fold the
# SAME fills, and both bucket a fill with no ``strategy_id`` under this key.
# Two declarations of one bucket name is how the two folds would come to report
# two different discretionary ledgers out of one event log.
from app.fund.projections.strategy import DISCRETIONARY

#: A round-trip whose P&L is inside this band is a scratch, not a win or a loss.
#: Without it, commission-sized noise is reported as a 51% win rate.
BREAKEVEN_BAND_PCT = 0.05


def _ts(e: dict[str, Any]) -> str | None:
    p = e.get("payload") or {}
    return e.get("ts") or e.get("timestamp") or p.get("filled_at") or p.get("ts")


class ExecutionHistory:
    """Fills and closed round-trips, per strategy, folded from the event log."""

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    # ------------------------------------------------------------------ fold
    def _build(self) -> dict[str, dict[str, Any]]:
        strats: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            self._apply(strats, e)
        return strats

    @classmethod
    def _apply(cls, strats: dict[str, dict[str, Any]], e: dict[str, Any]) -> None:
        if e.get("type") != EventType.ORDER_FILLED.value:
            return
        p = e.get("payload", {}) or {}
        key = p.get("strategy_id") or DISCRETIONARY
        qty = D(p.get("filled_qty", p.get("qty", 0)))
        px = D(p.get("avg_price", p.get("price", p.get("fill_price", 0))))
        fees = D(p.get("fees", 0))
        side = (p.get("side") or "buy").lower()
        sym = (p.get("symbol") or "UNKNOWN").upper()
        ts = _ts(e)

        rec = strats.setdefault(key, {
            "strategy_id": key,
            "fills": [],
            "round_trips": [],
            "open": {},   # symbol -> {qty, cost, entry_ts_weighted}
        })

        rec["fills"].append({
            "ts": ts,
            "seq": e.get("seq"),
            "symbol": sym,
            "side": side,
            "qty": f(qty),
            "price": f(px),
            "notional_usd": f(money(qty * px)),
            "fees_usd": f(money(fees)),
            "order_id": p.get("order_id") or p.get("client_order_id"),
            "venue": p.get("venue"),
        })

        pos = rec["open"].setdefault(sym, {
            "qty": Decimal("0"), "cost": Decimal("0"),
            "entries": [],   # (qty, ts) for the weighted average entry
        })

        if side == "buy":
            # A buy against an open SHORT is a cover, and covers realize P&L —
            # profit when the price fell. Treating every buy as an opening trade
            # would silently drop the entire realized result of any short.
            if pos["qty"] < -D("1e-9"):
                short_qty = -pos["qty"]
                closing = min(qty, short_qty)
                avg = -pos["cost"] / short_qty     # cost is negative for a short
                gross = closing * (avg - px)       # short profits as price falls
                net = gross - fees
                basis = closing * avg
                pct = float(net / basis * 100) if basis else 0.0
                rec["round_trips"].append({
                    "symbol": sym,
                    "side": "short",
                    "qty": f(closing),
                    "avg_entry_price": f(avg),
                    "exit_price": f(px),
                    "avg_entry_ts": cls._weighted_entry(pos["entries"], closing),
                    "exit_ts": ts,
                    "gross_pnl_usd": f(money(gross)),
                    "fees_usd": f(money(fees)),
                    "pnl_usd": f(money(net)),
                    "pnl_pct": round(pct, 4),
                    "outcome": ("breakeven" if abs(pct) <= BREAKEVEN_BAND_PCT
                                else "win" if net > 0 else "loss"),
                    "cost_basis_usd": f(money(basis)),
                })
                pos["qty"] += closing
                pos["cost"] += basis
                cls._consume_entries(pos["entries"], closing)
                remainder = qty - closing
                if remainder <= D("1e-9"):
                    return
                qty = remainder          # the rest opens a long
                fees = D("0")            # already charged against the cover

            pos["qty"] += qty
            pos["cost"] += qty * px + fees
            if ts:
                pos["entries"].append((qty, ts))
            return

        # ---- a sale: whatever closes an existing long is a round-trip --------
        sold = qty
        open_qty = pos["qty"]
        if open_qty > D("1e-9"):
            closing = min(sold, open_qty)
            avg = pos["cost"] / open_qty
            gross = closing * (px - avg)
            net = gross - fees
            cost_of_closed = closing * avg
            pct = float(net / cost_of_closed * 100) if cost_of_closed else 0.0

            rec["round_trips"].append({
                "symbol": sym,
                # A long that was sold. Shorts close on the buy side, below.
                "side": "long",
                "qty": f(closing),
                "avg_entry_price": f(avg),
                "exit_price": f(px),
                # Named for what it is: the position may have been built across
                # several buys, so there is no single entry moment.
                "avg_entry_ts": cls._weighted_entry(pos["entries"], closing),
                "exit_ts": ts,
                "gross_pnl_usd": f(money(gross)),
                "fees_usd": f(money(fees)),
                "pnl_usd": f(money(net)),
                "pnl_pct": round(pct, 4),
                "outcome": ("breakeven" if abs(pct) <= BREAKEVEN_BAND_PCT
                            else "win" if net > 0 else "loss"),
                "cost_basis_usd": f(money(cost_of_closed)),
            })

            pos["cost"] -= cost_of_closed
            pos["qty"] -= closing
            cls._consume_entries(pos["entries"], closing)
            remainder = sold - closing
            if remainder > D("1e-9"):     # flipped short
                pos["qty"] -= remainder
                pos["cost"] -= remainder * px
                if ts:
                    pos["entries"].append((-remainder, ts))
        else:
            # opening or extending a short — nothing realized yet
            pos["qty"] -= sold
            pos["cost"] -= sold * px - fees
            if ts:
                pos["entries"].append((-sold, ts))

    @staticmethod
    def _weighted_entry(entries: list[tuple[Decimal, str]], closing: Decimal) -> str | None:
        """Quantity-weighted entry timestamp of the lots this sale consumes.

        Returned as the timestamp of the lot at the weighted midpoint rather than
        an interpolated instant, so the value is always a moment that actually
        happened.
        """
        if not entries:
            return None
        need = closing / 2 if closing else Decimal("0")
        seen = Decimal("0")
        for q, ts in entries:
            seen += abs(q)
            if seen >= need:
                return ts
        return entries[-1][1]

    @staticmethod
    def _consume_entries(entries: list[tuple[Decimal, str]], closing: Decimal) -> None:
        """Retire the oldest lots up to ``closing`` shares."""
        left = closing
        while left > D("1e-9") and entries:
            q, ts = entries[0]
            take = min(abs(q), left)
            left -= take
            if abs(q) - take <= D("1e-9"):
                entries.pop(0)
            else:
                entries[0] = (q - take if q > 0 else q + take, ts)

    # ---------------------------------------------------------------- public
    def for_strategy(self, strategy_id: str, limit: int = 500) -> dict[str, Any]:
        rec = self._build().get(strategy_id)
        if rec is None:
            # Same shape as a populated strategy, so a caller never has to guess
            # which keys exist before it can count anything.
            return {
                "strategy_id": strategy_id,
                "measurable": False,
                "reason": "no fills recorded for this strategy",
                "fills": [], "n_fills": 0,
                "round_trips": [], "n_round_trips": 0,
                "open_positions": {},
                "summary": summarise([]),
            }
        return self._present(rec, limit=limit)

    def all(self, limit: int = 500) -> list[dict[str, Any]]:
        return [self._present(rec, limit=limit) for rec in self._build().values()]

    def _present(self, rec: dict[str, Any], limit: int) -> dict[str, Any]:
        fills = rec["fills"][-limit:]
        trips = rec["round_trips"][-limit:]
        open_positions = {
            sym: {"qty": f(pos["qty"]), "cost_basis_usd": f(money(pos["cost"]))}
            for sym, pos in rec["open"].items()
            if abs(pos["qty"]) > D("1e-9")
        }
        return {
            "strategy_id": rec["strategy_id"],
            "measurable": True,
            "fills": fills,
            "n_fills": len(rec["fills"]),
            "round_trips": trips,
            "n_round_trips": len(rec["round_trips"]),
            "open_positions": open_positions,
            "summary": summarise(rec["round_trips"]),
            "by_side": by_side(rec["round_trips"]),
        }


def summarise(round_trips: list[dict[str, Any]]) -> dict[str, Any]:
    """Win/loss counts, expectancy and the P&L distribution.

    The distribution is the point. A strategy with a 33% win rate and a 3:1
    payoff is healthy; the same win rate with a 0.8 payoff is a slow bleed, and
    the two are indistinguishable from the headline P&L alone.
    """
    if not round_trips:
        return {"measurable": False, "reason": "no closed round-trips yet"}

    pnl = [float(t["pnl_usd"]) for t in round_trips]
    pct = [float(t["pnl_pct"]) for t in round_trips]
    wins = [t for t in round_trips if t["outcome"] == "win"]
    losses = [t for t in round_trips if t["outcome"] == "loss"]
    scratches = [t for t in round_trips if t["outcome"] == "breakeven"]
    n = len(round_trips)

    win_pnl = [float(t["pnl_usd"]) for t in wins]
    loss_pnl = [float(t["pnl_usd"]) for t in losses]
    avg_win = sum(win_pnl) / len(win_pnl) if win_pnl else 0.0
    avg_loss = sum(loss_pnl) / len(loss_pnl) if loss_pnl else 0.0
    gross_win, gross_loss = sum(win_pnl), abs(sum(loss_pnl))

    return {
        "measurable": True,
        "n_round_trips": n,
        "winners": len(wins),
        "losers": len(losses),
        "breakevens": len(scratches),
        "win_rate": round(len(wins) / n, 4),
        "loss_rate": round(len(losses) / n, 4),
        "breakeven_rate": round(len(scratches) / n, 4),
        "breakeven_band_pct": BREAKEVEN_BAND_PCT,
        "total_realized_usd": round(sum(pnl), 2),
        "avg_win_usd": round(avg_win, 2),
        "avg_loss_usd": round(avg_loss, 2),
        "expectancy_usd": round(sum(pnl) / n, 4),
        "payoff_ratio": round(avg_win / abs(avg_loss), 4) if avg_loss < 0 else None,
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss > 0 else None,
        "best_usd": round(max(pnl), 2),
        "worst_usd": round(min(pnl), 2),
        # If one trade is most of the profit, the "edge" is one trade.
        "top_trade_share_of_gross_profit": (
            round(max(win_pnl) / gross_win, 4) if win_pnl and gross_win > 0 else None
        ),
        "worst_trade_share_of_gross_loss": (
            round(abs(min(loss_pnl)) / gross_loss, 4) if loss_pnl and gross_loss > 0 else None
        ),
        "streaks": streaks(round_trips),
        "holding": holding_periods(round_trips),
        "distribution_pct": histogram(pct),
    }


def by_side(round_trips: list[dict[str, Any]]) -> dict[str, Any]:
    """The same summary split long / short.

    A book that makes money long and loses it short is two strategies wearing one
    name, and the pooled number hides exactly that. Reported separately rather
    than netted.
    """
    longs = [t for t in round_trips if t.get("side") == "long"]
    shorts = [t for t in round_trips if t.get("side") == "short"]
    return {
        "all": summarise(round_trips),
        "long": summarise(longs),
        "short": summarise(shorts),
    }


def streaks(round_trips: list[dict[str, Any]]) -> dict[str, Any]:
    """Longest run of wins and of losses, and the run currently open.

    This is a survivability number, not a curiosity. A strategy with a positive
    expectancy and a nine-loss streak will be switched off by its operator on
    loss seven, so the streak decides whether the edge is reachable in practice.
    Breakevens neither extend nor break a run — they are not outcomes.
    """
    if not round_trips:
        return {"measurable": False, "reason": "no closed round-trips yet"}
    best_w = best_l = cur = 0
    cur_kind: str | None = None
    for t in round_trips:
        o = t.get("outcome")
        if o == "breakeven":
            continue
        if o == cur_kind:
            cur += 1
        else:
            cur_kind, cur = o, 1
        if cur_kind == "win":
            best_w = max(best_w, cur)
        elif cur_kind == "loss":
            best_l = max(best_l, cur)
    return {
        "measurable": True,
        "longest_win_streak": best_w,
        "longest_loss_streak": best_l,
        "current_streak": cur if cur_kind else 0,
        "current_streak_kind": cur_kind,
    }


def holding_periods(round_trips: list[dict[str, Any]]) -> dict[str, Any]:
    """Days held, split by outcome.

    Winners held far longer than losers means the exits are working. The reverse
    — losers held longest — is the signature of an unwilling-to-cut strategy, and
    it is visible here long before it shows up in the P&L.
    """
    def days(t: dict[str, Any]) -> float | None:
        a, b = t.get("avg_entry_ts"), t.get("exit_ts")
        if not (a and b):
            return None
        try:
            from datetime import datetime
            d0 = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
            d1 = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
        except ValueError:
            return None
        return (d1 - d0).total_seconds() / 86400.0

    rows = [(t.get("outcome"), days(t)) for t in round_trips]
    have = [(o, d) for o, d in rows if d is not None]
    if not have:
        return {"measurable": False,
                "reason": "fills carry no usable timestamps, so holding time is unknown"}

    def avg(kind: str | None) -> float | None:
        vals = [d for o, d in have if kind is None or o == kind]
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        "measurable": True,
        "n_timed": len(have),
        "avg_days_all": avg(None),
        "avg_days_winners": avg("win"),
        "avg_days_losers": avg("loss"),
        "longest_days": round(max(d for _, d in have), 4),
    }


def histogram(values: list[float], bins: int = 12) -> dict[str, Any]:
    """A P&L histogram — the TradingView returns-distribution view.

    Bin edges come from the observed range rather than a fixed grid, because a
    fixed grid either flattens a tight distribution into one bar or spreads a
    wide one across empty space.
    """
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return {"measurable": False, "reason": "need at least 2 closed trades"}
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return {"measurable": False, "reason": "all trades returned the same amount"}
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in vals:
        idx = min(bins - 1, int((v - lo) / width))
        counts[idx] += 1
    return {
        "measurable": True,
        "bins": [
            {"from_pct": round(lo + i * width, 4),
             "to_pct": round(lo + (i + 1) * width, 4),
             "count": counts[i],
             "sign": "win" if (lo + (i + 0.5) * width) > 0 else "loss"}
            for i in range(bins)
        ],
        "min_pct": round(lo, 4),
        "max_pct": round(hi, 4),
        "mean_pct": round(sum(vals) / len(vals), 4),
    }
