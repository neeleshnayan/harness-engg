"""How much money this strategy can hold before it stops working.

The number a small fund should care about most, and the one nobody reports.
A strategy's edge is not a percentage — it is a percentage AT A SIZE. Push
enough capital through it and your own orders move the price you were trying
to capture, until the edge is paying for itself and then paying to exist.

Which cuts the other way too, and that is the point here. A strategy whose
capacity is $400k is worthless to Citadel — it cannot move their needle and
they would be the entire float — and that is precisely why it can still be
there for a fund this size. Capacity is not only a ceiling on us; it is a
moat against everyone bigger. Reporting it turns "we are too small to compete"
into "we are small enough that this is ours".

The estimate is deliberately crude and deliberately conservative, because a
precise-looking capacity number would be a lie with decimal places. It answers
"is this a $100k strategy, a $10m one, or a $10bn one" — an order of
magnitude, which is the resolution the decision actually needs.
"""

from __future__ import annotations

import logging
from statistics import median
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Share of a day's dollar volume we assume can be traded without moving the
#: price against us. 1% is the conservative end of the usual 1-10% range, and
#: conservative is right when the output is a ceiling: overestimating capacity
#: is how a strategy gets funded past the point where it works.
DEFAULT_PARTICIPATION = 0.01

#: Below this, the fund's own orders are a material share of the tape and the
#: backtest's fills are fiction.
THIN_ADV_USD = 1_000_000.0

#: What the big shops cannot be bothered with. A strategy under this is
#: invisible to a multi-billion fund: deploying into it would not move their
#: return, and they would be most of the volume.
BIG_FUND_FLOOR_USD = 50_000_000.0


def adv_usd(closes: list[float], volumes: list[float],
            window: int = 60) -> Optional[float]:
    """Median daily dollar volume over the recent window.

    Median, not mean, and that is not fussiness: a single earnings day or an
    index-rebalance print can be ten times a normal session, and a mean lets
    that one day claim capacity the strategy could never actually use.
    """
    if not closes or not volumes:
        return None
    pairs = [(c, v) for c, v in zip(closes, volumes)
             if c and v and c > 0 and v > 0]
    if not pairs:
        return None
    recent = pairs[-window:] if len(pairs) > window else pairs
    return float(median(c * v for c, v in recent))


def estimate(symbol: str, closes: list[float], volumes: list[float],
             daily_turnover_pct: Optional[float],
             participation: float = DEFAULT_PARTICIPATION) -> dict[str, Any]:
    """The AUM at which this strategy's own trading becomes the problem.

    A fund of size A turning over t of itself each day trades A*t per day. Keep
    that under participation*ADV and:

        capacity = participation * ADV / t

    Turnover is what makes this a STRATEGY property rather than a symbol one.
    Two strategies on the same name have wildly different capacity if one holds
    for months and the other flips daily — which is also why turnover is the
    lever you reach for when capacity binds.
    """
    adv = adv_usd(closes, volumes)
    if adv is None:
        return {"symbol": symbol, "capacity_usd": None,
                "reason": "no volume data — capacity cannot be estimated, and "
                          "a guess here would be a ceiling nobody checked"}

    t = (daily_turnover_pct or 0) / 100.0
    if t <= 0:
        return {
            "symbol": symbol, "adv_usd": round(adv, 2), "capacity_usd": None,
            "participation": participation,
            "reason": ("turnover is zero — a strategy that never trades has no "
                       "capacity limit from trading. Its limit is the position "
                       "itself, not the turnover."),
        }

    capacity = participation * adv / t
    return {
        "symbol": symbol,
        "adv_usd": round(adv, 2),
        "daily_turnover_pct": daily_turnover_pct,
        "participation": participation,
        "capacity_usd": round(capacity, 2),
        "thin_market": adv < THIN_ADV_USD,
        # The finding that matters to a small fund.
        "below_big_fund_floor": capacity < BIG_FUND_FLOOR_USD,
        "verdict": _verdict(capacity, adv),
        "assumption": (f"assumes we can be {participation:.1%} of a typical "
                       f"day's dollar volume without moving the price; halve "
                       f"that and halve the capacity"),
    }


def _verdict(capacity: float, adv: float) -> str:
    if adv < THIN_ADV_USD:
        return ("The tape is too thin to trust the backtest's fills at any "
                "size — our own orders would be a material share of the day.")
    if capacity < BIG_FUND_FLOOR_USD:
        return (f"Uninvestable for a large fund, which is the point: at "
                f"${capacity:,.0f} it cannot move a multi-billion book and they "
                f"would be most of the volume. This is the kind of edge that "
                f"stays available to a fund our size.")
    if capacity < 1_000_000_000:
        return (f"Room for ${capacity:,.0f}. Large enough to interest a serious "
                f"fund, so expect the edge to be competed away rather than to "
                f"sit there waiting.")
    return ("Effectively unlimited capacity, which means everyone can trade it "
            "and almost certainly does. Size is not what protects this edge — "
            "check that something else does.")


def headroom(capacity_usd: Optional[float], nav_usd: float) -> dict[str, Any]:
    """How much of the available capacity this fund is actually using.

    At $2k against a capacity of millions the honest answer is "capacity is
    not your constraint" — and saying so plainly is more useful than a
    reassuring ratio nobody reads.
    """
    if not capacity_usd or capacity_usd <= 0:
        return {"used_pct": None, "note": "capacity unknown"}
    used = nav_usd / capacity_usd * 100.0
    return {
        "used_pct": round(used, 6),
        "note": ("capacity is not the binding constraint at this size"
                 if used < 1.0 else
                 f"using {used:.1f}% of estimated capacity — size is starting "
                 f"to matter, and turnover is the lever"),
    }
