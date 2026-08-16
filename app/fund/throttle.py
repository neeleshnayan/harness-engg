"""Cut gross when the market gets fragile. Only ever cut.

Absorption and turbulence have been measured for a while and have only ever
informed a page. They are the two cheapest warnings a book can get:

  * TURBULENCE says today's cross-section of moves is unusual against its own
    history. Risk-taking historically pays badly while it is elevated.
  * ABSORPTION says how much of the variance a few factors explain. When it
    rises, correlations are converging and the diversification a portfolio
    APPEARS to have is quietly disappearing — which is exactly when a book that
    looks spread out is not.

The second is the more valuable and the less intuitive. A portfolio's
protection is not the number of positions, it is how independently they move,
and absorption is the measure of that going away. It rises BEFORE the drawdown,
because correlations converge on the way into a crisis rather than during it.

Two deliberate restrictions.

REDUCTION ONLY. This can lower gross and can never raise it. A system that
automatically increases exposure is a system that can automatically get greedy,
and calm readings are exactly when that is most dangerous — an all-clear from a
model is not the same as an opportunity. Coming back up is a human decision.

A THROTTLE, NOT A SWITCH. It scales gross down in steps rather than flattening
the book, because these measures are noisy and a rule that goes to cash on a
single reading will do so repeatedly and expensively. The halt lives elsewhere,
is much further out, and answers a different question.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Turbulence percentile at which we start trimming, and where the trim maxes
#: out. Below the first, nothing happens at all.
TURBULENCE_START_PCT = 80.0
TURBULENCE_MAX_PCT = 97.0

#: Standardised absorption shift at which trimming starts and maxes out. The
#: shift is in standard deviations against a one-year mean, so 1.0 is "notably
#: more factor-dominated than usual" and 3.0 is a regime change.
ABSORPTION_START_SHIFT = 1.0
ABSORPTION_MAX_SHIFT = 3.0

#: The most this rule will ever take off. Not 100%: going fully to cash on a
#: statistical reading is a decision with its own large cost — being out of a
#: recovery — and it belongs to a person.
MAX_REDUCTION = 0.50


def _ramp(value: Optional[float], start: float, full: float) -> float:
    """0 below `start`, 1 at or above `full`, linear between.

    Linear rather than stepped so a reading that hovers on a threshold does not
    flip the book's size back and forth, which costs spread every time and
    protects nothing.
    """
    if value is None:
        return 0.0
    if value <= start:
        return 0.0
    if value >= full:
        return 1.0
    return (value - start) / (full - start)


def target_gross(regime: dict[str, Any],
                 max_reduction: float = MAX_REDUCTION) -> dict[str, Any]:
    """How much of normal gross to run, given the regime. Never above 1.0.

    Takes the WORSE of the two signals rather than averaging them. Averaging
    lets a calm reading on one measure pay for an alarming reading on the
    other, and these two are not substitutes: absorption and turbulence
    describe different ways for a book to be in trouble, and either one alone
    is a reason to carry less.
    """
    turb = (regime or {}).get("turbulence") or {}
    absb = (regime or {}).get("absorption") or {}

    t_pct = turb.get("recent_20d_percentile") if turb.get("measurable") else None
    a_shift = absb.get("standardised_shift") if absb.get("measurable") else None

    t_ramp = _ramp(t_pct, TURBULENCE_START_PCT, TURBULENCE_MAX_PCT)
    a_ramp = _ramp(a_shift, ABSORPTION_START_SHIFT, ABSORPTION_MAX_SHIFT)
    worst = max(t_ramp, a_ramp)

    reduction = worst * max_reduction
    multiplier = round(1.0 - reduction, 4)

    driver = (None if worst == 0 else
              "turbulence" if t_ramp >= a_ramp else "absorption")
    measurable = bool(turb.get("measurable") or absb.get("measurable"))

    return {
        "gross_multiplier": multiplier,
        "reduction_pct": round(reduction * 100, 2),
        "driver": driver,
        "measurable": measurable,
        "inputs": {
            "turbulence_20d_percentile": t_pct,
            "absorption_standardised_shift": a_shift,
        },
        "reason": _reason(measurable, driver, multiplier, t_pct, a_shift),
        "note": ("reduction only — this rule can lower gross and never raise it. "
                 "Coming back up is a human decision, because an all-clear from "
                 "a model is not the same as an opportunity"),
    }


def _reason(measurable: bool, driver: Optional[str], multiplier: float,
            t_pct: Optional[float], a_shift: Optional[float]) -> str:
    if not measurable:
        # Deliberately NOT a reduction. Unmeasurable is not the same as
        # dangerous, and trimming on missing data would make a data outage
        # into a trading decision.
        return ("regime not measurable — carrying normal gross, because absent "
                "evidence is not evidence of danger")
    if driver is None:
        return (f"calm by both measures (turbulence {t_pct}th percentile, "
                f"absorption shift {a_shift}) — full gross, and this rule "
                f"would not raise it further even if they fell")
    if driver == "turbulence":
        return (f"turbulence at the {t_pct}th percentile of its own history — "
                f"running {multiplier:.0%} of normal gross, because risk-taking "
                f"historically pays poorly while it is elevated")
    return (f"absorption {a_shift} standard deviations above its one-year mean — "
            f"correlations are converging and the book's diversification is "
            f"quietly disappearing, so running {multiplier:.0%} of normal gross")


def apply_to(weights: dict[str, float], regime: dict[str, Any]) -> dict[str, Any]:
    """Scale a set of target weights by the regime multiplier.

    The difference goes to cash. Scaling every weight equally is deliberate:
    deciding WHICH position to cut in a fragile market is a view, and this rule
    does not have views — it only has an opinion about how much.
    """
    t = target_gross(regime)
    m = t["gross_multiplier"]
    scaled = {s: round(w * m, 6) for s, w in (weights or {}).items()}
    return {
        **t,
        "weights": scaled,
        "gross": round(sum(scaled.values()), 6),
        "cash_weight": round(sum((weights or {}).values()) - sum(scaled.values()), 6),
    }
