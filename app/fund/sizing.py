"""How much of each — the step that turns an edge into a return.

The book currently holds seven roughly equal $168 positions. That is not a
sizing decision, it is the absence of one, and it means a name with three times
the volatility of another contributes three times the risk while contributing
the same conviction.

Two honest warnings before any of the maths, because both are places where
sophistication makes things worse:

EQUAL WEIGHT IS A STRONG BASELINE. The 1/N portfolio beats most optimised ones
out of sample, and it beats them for a specific reason: optimisation consumes
estimates, and estimated covariances are noisy enough that the optimiser spends
most of its cleverness fitting that noise. Nothing here should be adopted
because it is more sophisticated. It should be adopted where it survives the
same held-out scrutiny we demand of a strategy.

FULL KELLY IS RUINOUS IN PRACTICE. It maximises long-run growth only if the
edge is known exactly, and an edge estimated from a backtest never is. Half
Kelly gives up a quarter of the growth for a large reduction in drawdown, and
that trade is worth taking every time at this size. The cap here is a quarter,
which is deliberately timid.

So the default is inverse-volatility: it uses only variances, which are far
better estimated than covariances, and it does the single most valuable thing —
stopping the noisiest name from dominating the book's risk.
"""

from __future__ import annotations

import logging
import math
from statistics import mean, pstdev
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)

#: Trading days per year, for annualising a daily standard deviation.
TRADING_DAYS = 252

#: Fraction of Kelly ever allowed. A quarter is timid on purpose: the edge is
#: estimated, and Kelly's optimality assumes it is not.
KELLY_CAP = 0.25

#: Nothing gets more than this share of the book regardless of what the maths
#: says. A sizing rule that can concentrate the fund into one name has replaced
#: one risk with another.
MAX_WEIGHT = 0.35

#: Below this a position is not worth the ticket: at a $2k book a 2% weight is
#: $40, and the spread starts to matter more than the idea.
MIN_WEIGHT = 0.02


def annualised_vol(returns: Sequence[float]) -> Optional[float]:
    """Annualised standard deviation of daily returns, or None if unknowable."""
    r = [x for x in returns if x is not None]
    if len(r) < 20:
        return None            # too few points to call it a volatility
    return float(pstdev(r) * math.sqrt(TRADING_DAYS))


def inverse_vol_weights(vols: dict[str, Optional[float]]) -> dict[str, float]:
    """Weight inversely to volatility, so each name contributes similar risk.

    Uses only variances. Covariances are far noisier to estimate, and a rule
    that needs them buys correlation-awareness at the cost of fitting noise —
    usually a bad trade at this sample size.

    A name whose volatility is unknown is DROPPED rather than defaulted. Giving
    it an assumed volatility would size a position on a number nobody measured.
    """
    usable = {s: v for s, v in vols.items() if v and v > 0}
    if not usable:
        return {}
    raw = {s: 1.0 / v for s, v in usable.items()}
    total = sum(raw.values())
    return {s: w / total for s, w in raw.items()}


def kelly_fraction(edge_annual: float, vol_annual: float,
                   cap: float = KELLY_CAP) -> float:
    """Capped Kelly: edge over variance, then heavily discounted.

    Returns 0 for a non-positive edge rather than a short. Deciding to be short
    is a strategy decision and must not fall out of a sizing formula.
    """
    if edge_annual <= 0 or vol_annual <= 0:
        return 0.0
    full = edge_annual / (vol_annual ** 2)
    return max(0.0, min(full * cap, cap))


def risk_contributions(weights: dict[str, float],
                       returns: dict[str, list[float]]) -> dict[str, float]:
    """Each name's share of portfolio variance — where the risk actually is.

    Weight and risk are different things, and the gap between them is the whole
    argument for this module: equal weights in a book holding both a utility
    and a small-cap biotech are not equal risk, they only look it.
    """
    syms = [s for s in weights if s in returns and returns[s]]
    if not syms:
        return {}
    n = min(len(returns[s]) for s in syms)
    if n < 20:
        return {}
    cols = {s: returns[s][-n:] for s in syms}
    mu = {s: mean(cols[s]) for s in syms}

    def cov(a: str, b: str) -> float:
        return sum((cols[a][i] - mu[a]) * (cols[b][i] - mu[b]) for i in range(n)) / n

    port_var = sum(weights[a] * weights[b] * cov(a, b) for a in syms for b in syms)
    if port_var <= 0:
        return {}
    # Euler decomposition: contributions sum to one by construction.
    out = {}
    for a in syms:
        marginal = sum(weights[b] * cov(a, b) for b in syms)
        out[a] = round(weights[a] * marginal / port_var, 6)
    return out


def size(candidates: dict[str, Optional[float]],
         returns: Optional[dict[str, list[float]]] = None,
         nav_usd: float = 0.0,
         gross_cap: float = 1.0,
         max_weight: float = MAX_WEIGHT,
         min_weight: float = MIN_WEIGHT) -> dict[str, Any]:
    """Turn a set of names into position sizes, and show the work.

    ``candidates`` maps symbol -> annualised volatility (None when unknown).
    Returns weights, dollar sizes, and the diagnostics needed to argue with the
    result: what equal weight would have given, and where the risk ended up
    versus where the weight did.
    """
    weights = inverse_vol_weights(candidates)
    dropped = [s for s, v in candidates.items() if not (v and v > 0)]
    if not weights:
        return {"weights": {}, "dropped": dropped,
                "reason": "no candidate had a measurable volatility"}

    # Cap, and do NOT renormalise back up to fully invested.
    #
    # The obvious implementation redistributes what the cap removed across the
    # remaining names, and it inverts the entire rule. With a calm name and a
    # wild one, inverse-vol wants 99% in the calm one; capping it at 35% and
    # pushing the rest into the survivor hands 65% to the WILDEST name in the
    # book — the exact concentration the cap existed to prevent.
    #
    # When a concentration limit cannot be met while fully invested, the honest
    # answer is to hold cash. A cap that quietly relaxes itself is not a cap.
    weights = {s: min(w, max_weight) for s, w in weights.items()}

    # Drop dust and renormalise: a position too small to matter still costs a
    # spread to enter and a line on every report thereafter.
    dust = [s for s, w in weights.items() if w < min_weight]
    if dust and len(dust) < len(weights):
        for s in dust:
            weights.pop(s)

    weights = {s: round(w * gross_cap, 6) for s, w in weights.items()}
    equal = round(gross_cap / len(weights), 6) if weights else 0.0
    invested = sum(weights.values())

    out: dict[str, Any] = {
        "weights": weights,
        "usd": {s: round(w * nav_usd, 2) for s, w in weights.items()} if nav_usd else {},
        "gross": round(invested, 6),
        # What the concentration cap and the dust floor left uninvested. Named
        # rather than hidden: an operator seeing 0.65 gross should know it is a
        # decision the rules made, not a bug.
        "cash_weight": round(max(0.0, gross_cap - invested), 6),
        "equal_weight_would_be": equal,
        "dropped_no_vol": dropped,
        "dropped_too_small": dust,
        "method": "inverse volatility",
        "caveat": ("equal weight is a strong baseline and beats most optimised "
                   "portfolios out of sample; this is worth adopting only where "
                   "it survives the same scrutiny we demand of a strategy"),
    }
    if returns:
        rc = risk_contributions(weights, returns)
        if rc:
            out["risk_contribution"] = rc
            # The number that justifies the whole exercise: under equal
            # weights these would be lopsided, and the gap is what sizing fixes.
            out["risk_spread"] = round(max(rc.values()) - min(rc.values()), 6)
    return out
