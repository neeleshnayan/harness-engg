"""Is the live strategy the one that was backtested?

A strategy is deployed on the strength of a backtest, and from that moment the
backtest is a promise: this rule, on this market, behaves like THIS. Nothing in
the harness checked the promise. A strategy could underperform its own test
forever and the only symptom would be a vague feeling on the P&L panel.

This module puts a number on the gap. For each deployed strategy that has a
recorded backtest, it compares:

    backtest side   annualised return implied by the recorded results
                    (total_return over `bars` daily bars)
    live side       realized + unrealized P&L against money actually put to
                    work, annualised over days since the strategy's first fill

and reports the spread in annualised percentage points.

Honesty rules, because this comparison is easy to abuse:

  - Under MIN_LIVE_DAYS of live history the row says `comparable: false` and
    gives the reason. Two days of live returns annualise into nonsense, and a
    number that is nonsense with a straight face is worse than no number.
  - The live return is computed on capital deployed (cost basis), not on NAV —
    a strategy sized at 2% cannot be blamed for moving NAV by little.
  - Nothing here says "underperforming" until the gap exceeds both a floor in
    percentage points AND the backtest's own volatility band. Markets wobble;
    the flag is for a strategy outside the range its own test called normal.

The watcher's brief already promises "a strategy that has not resembled its
backtest for a fortnight" — this is the measurement that sentence needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.fund.events import EventStore, EventType

#: Below this many live days, refuse to annualise. A fortnight — the same
#: horizon the watcher promises to speak at.
MIN_LIVE_DAYS = 14.0

#: The gap must clear this many annualised percentage points AND one backtest
#: volatility before the verdict says "diverging". Both, not either: a 3-vol
#: move on a 1%-vol strategy is real; a 3pp gap on a 40%-vol strategy is noise.
MIN_GAP_PP = 5.0

_TRADING_DAYS = 252.0
_CAL_DAYS = 365.25


def _first_fill_ts(store: EventStore, strategy_id: str) -> datetime | None:
    """When this strategy first put money to work — the live clock starts here,
    not at deployment: a deployed strategy that never traded has no live record
    to diverge."""
    for e in store.stream():
        if e.get("type") != EventType.ORDER_FILLED.value:
            continue
        if (e.get("payload") or {}).get("strategy_id") != strategy_id:
            continue
        ts = e.get("ts")
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return None


def _annualise(total_return: float, days: float) -> float | None:
    """Geometric annualisation; None where the inputs make it meaningless."""
    if days <= 0 or total_return <= -1.0:
        return None
    return (1.0 + total_return) ** (_CAL_DAYS / days) - 1.0


def compare(
    store: EventStore,
    strategies: list[dict[str, Any]],
    attribution_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """One row per deployed strategy with a backtest on record.

    ``strategies`` is StrategyRegistry.list(); ``attribution_rows`` is
    StrategyAttribution.with_values(price_fn). Pure function of its inputs so
    it tests without a network and caches trivially.
    """
    now = datetime.now(timezone.utc)
    attr = {r.get("strategy_id"): r for r in attribution_rows}
    rows: list[dict[str, Any]] = []

    for s in strategies:
        if s.get("state") not in ("deployed", "paused"):
            continue
        bt = s.get("backtest") or {}
        sid = s.get("strategy_id")
        row: dict[str, Any] = {
            "strategy_id": sid,
            "name": s.get("name"),
            "state": s.get("state"),
            # Carried since 2026-08-21, additively, because the SURFACE could not
            # tell. Three of the four rows this panel served were archived, and
            # it labelled all four "deployed" — the CEO was reading dead
            # strategies as live comparisons. Archived is a fact the registry
            # already holds; the row simply never passed it on, and the client
            # had no way to know without a second call and a join.
            #
            # Reported, NOT filtered. Whether an archived strategy belongs on a
            # given panel is the panel's judgement; dropping the row here would
            # take that choice away from every reader at once, including the
            # audit ones that want it.
            "archived": bool(s.get("archived")),
            "comparable": False,
            "reason": None,
        }

        if not bt or bt.get("total_return") is None:
            row["reason"] = "no backtest on record — deployed on what?"
            rows.append(row)
            continue

        bars = float(bt.get("bars") or 0)
        if bars <= 0:
            row["reason"] = "backtest window unknown (no bars recorded)"
            rows.append(row)
            continue

        # Backtest bars are trading days; convert to calendar for annualising.
        bt_days = bars * (_CAL_DAYS / _TRADING_DAYS)
        bt_annual = _annualise(float(bt["total_return"]), bt_days)
        bt_vol = float(bt.get("volatility") or 0.0)  # already annualised

        a = attr.get(sid) or {}
        exposure = float(a.get("exposure_usd") or 0.0)
        pnl = float(a.get("pnl_usd") or 0.0)
        cost_basis = exposure - pnl if exposure - pnl > 0 else exposure

        first = _first_fill_ts(store, sid)
        live_days = (now - first).total_seconds() / 86400.0 if first else 0.0

        row.update({
            "backtest_annual_return_pct": round(bt_annual * 100.0, 2) if bt_annual is not None else None,
            "backtest_vol_pct": round(bt_vol * 100.0, 2),
            "live_days": round(live_days, 1),
            "live_pnl_usd": round(pnl, 2),
            "live_cost_basis_usd": round(cost_basis, 2),
        })

        if first is None:
            row["reason"] = "no fills yet — nothing live to compare"
            rows.append(row)
            continue
        if cost_basis <= 0:
            row["reason"] = "no capital currently attributable to this strategy"
            rows.append(row)
            continue

        live_return = pnl / cost_basis
        row["live_return_pct"] = round(live_return * 100.0, 2)

        if live_days < MIN_LIVE_DAYS:
            row["reason"] = (
                f"only {live_days:.1f} live days — under the {MIN_LIVE_DAYS:.0f}-day "
                "floor, annualising would manufacture a verdict"
            )
            rows.append(row)
            continue

        live_annual = _annualise(live_return, live_days)
        if live_annual is None or bt_annual is None:
            row["reason"] = "returns out of annualisable range"
            rows.append(row)
            continue

        gap_pp = (live_annual - bt_annual) * 100.0
        band_pp = max(MIN_GAP_PP, bt_vol * 100.0)
        row.update({
            "comparable": True,
            "reason": None,
            "live_annual_return_pct": round(live_annual * 100.0, 2),
            "gap_pp": round(gap_pp, 2),
            "band_pp": round(band_pp, 2),
            # Signed verdict: a strategy far ABOVE its backtest is also not the
            # strategy that was tested — luck is not validation.
            "diverging": abs(gap_pp) > band_pp,
        })
        rows.append(row)

    n_flagged = sum(1 for r in rows if r.get("diverging"))
    live_rows = [r for r in rows if not r.get("archived")]
    n_archived = len(rows) - len(live_rows)
    return {
        "rows": rows,
        # `n_deployed` counts EVERY row, archived included, and is kept at that
        # meaning so no existing reader changes underneath itself. The live
        # counts are new keys beside it rather than a redefinition — silently
        # changing what a number means is worse than adding one.
        "n_deployed": len(rows),
        "n_comparable": sum(1 for r in rows if r["comparable"]),
        "n_diverging": n_flagged,
        "n_archived": n_archived,
        "n_live": len(live_rows),
        "n_live_comparable": sum(1 for r in live_rows if r["comparable"]),
        "n_live_diverging": sum(1 for r in live_rows if r.get("diverging")),
        "note": (
            "live return is P&L over capital deployed, annualised over days since "
            "first fill; a row diverges only beyond max(5pp, one backtest vol)"
        ),
        "archived_note": (
            f"{n_archived} of these {len(rows)} strategies are ARCHIVED. They are "
            f"included in `rows` and in `n_deployed` for audit, and excluded from "
            f"the `n_live_*` counts — an archived strategy's gap to its backtest "
            f"is history, not a live comparison"
            if n_archived else None),
    }
