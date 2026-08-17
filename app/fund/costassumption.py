"""The fund's one cost assumption, in one place.

It was in two, and they disagreed. The LEAN algorithms price slippage at 5bps a
side; transaction-cost analysis judged realised fills against 2bps. So the
backtests were charging one number, the report card was grading against
another, and "we are 4bps over assumption" meant nothing because there were two
assumptions.

That is not a tidiness problem. The whole argument for measuring realised cost
is that it VALIDATES the backtest premise — and a comparison against a number
no backtest uses validates nothing. A duplicated constant in a fund is a
duplicated belief, and beliefs drift.

Realised cost is 5.95bps a side over ten fills, which is worth stating plainly:
the old 2bps assumption was optimistic by roughly threefold, and every Sharpe
computed under it was correspondingly flattered. The 5bps default this now
carries was chosen before that number was measured, and it turned out close —
but "close" is a fact to check periodically, not a reason to stop checking.
"""

from __future__ import annotations

import os
from typing import Any, Optional

#: Slippage charged per side, in basis points, everywhere the fund models a
#: cost: the LEAN slippage model, the in-process backtester, and the baseline
#: TCA grades realised fills against.
#:
#: Not a broker commission. Alpaca charges none on US equities, so that really
#: is zero — this is the SPREAD, which is paid whether or not anyone invoices
#: for it.
DEFAULT_SLIPPAGE_BPS = float(os.getenv("FUND_SLIPPAGE_BPS", "5.0"))

#: Below this many fills, a realised average is an anecdote. Ten orders in a
#: quiet market says little about what a bad day costs.
#:
#: 20 because that is what the codebase already chose. Both 20 and 30 are rules
#: of thumb, and raising it would have been my preference quietly overriding a
#: decision someone had already made and written a test for.
RELIABLE_SAMPLE = 20


def slippage_bps() -> float:
    return DEFAULT_SLIPPAGE_BPS


def slippage_fraction() -> float:
    """The same number as a fraction, for LEAN's ConstantSlippageModel."""
    return DEFAULT_SLIPPAGE_BPS / 10_000.0


def compare(realised_bps: Optional[float], sample: int) -> dict[str, Any]:
    """Realised cost against the number the backtests actually charge.

    Reports the sample size beside the verdict and refuses to call a small one
    reliable, because the failure this invites is re-tuning the assumption to
    match six fills in a calm week and then being surprised by a volatile one.
    """
    assumed = slippage_bps()
    if realised_bps is None or sample <= 0:
        return {"assumed_bps_per_side": assumed, "realised_bps_per_side": None,
                "sample": sample, "reliable": False,
                "verdict": "no fills yet — the assumption is unchallenged, "
                           "which is not the same as validated"}
    excess = round(realised_bps - assumed, 2)
    reliable = sample >= RELIABLE_SAMPLE
    if abs(excess) <= 1.0:
        verdict = (f"realised {realised_bps:.2f}bps against {assumed:.1f} assumed — "
                   f"the backtests are charging about what trading costs")
    elif excess > 0:
        verdict = (f"realised {realised_bps:.2f}bps against {assumed:.1f} assumed — "
                   f"paying {excess:.2f}bps a side MORE than every backtest "
                   f"charges, so returns are overstated, and most for whatever "
                   f"trades most")
    else:
        verdict = (f"realised {realised_bps:.2f}bps against {assumed:.1f} assumed — "
                   f"cheaper than modelled, so the backtests are conservative")
    return {
        "assumed_bps_per_side": assumed,
        "realised_bps_per_side": round(realised_bps, 2),
        "excess_bps": excess,
        "sample": sample,
        "reliable": reliable,
        "verdict": verdict + ("" if reliable else
                              f" — but {sample} fills is an anecdote, not a "
                              f"measurement; {RELIABLE_SAMPLE} is the bar"),
    }
