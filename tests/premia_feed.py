"""A synthetic cash feed for the premia tests, and nothing else.

Gate v5r2 reads the REALISED risk-free series from the fund's own feed over the
candidate's own window. A test must therefore be able to say what the cash rate
WAS, exactly, without touching the network — and, more importantly, must be able
to say it DIFFERENTLY twice, because "the rate is read rather than assumed" can
only be proved by moving it (D16).

Two shapes, because they prove different things:

  * ``cash_feed(rate_pct)`` — a constant per-session rate. The excess Sharpe is
    then exactly ``sharpe_at_rf(raw_moments, rate_pct)``, so a fixture's expected
    answer is closed form rather than eyeballed.
  * ``cash_feed(rate_pct, later_pct=..., switch_on=...)`` — a rate that CHANGES
    inside the window. Its mean is a constant that no single-rate rule could
    distinguish it from, and its Sharpe answer is different — which is the only
    way to show the code consumes a series and not an average.

THE RATE IS A FUNCTION OF THE DATE, never of the position in the returned
slice. An index-based switch made the series depend on how wide a window the
caller asked for — and `premia_inputs` asks with a pad, so a test computing the
"same" series by hand got a DIFFERENT one and the assertion failed for a reason
that had nothing to do with the code under test.

The dates are consecutive weekdays, matching ``_dates`` in the premia tests and
matching what the real feed serves (sessions, not calendar days).
"""
from __future__ import annotations

import datetime
from typing import Any, Optional


class FakeBars:
    """The two attributes ``rf_series`` reads, and a source label."""

    def __init__(self, dates: list[str], closes: list[float], source: str):
        self.dates, self.closes, self.source = dates, closes, source


def weekdays_between(start: str, end: str) -> list[str]:
    d = datetime.date.fromisoformat(start[:10])
    last = datetime.date.fromisoformat(end[:10])
    out = []
    while d <= last:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def per_obs(annual_pct: float, obs_per_year: float) -> float:
    """An annual rate at one observation's frequency, compounded — the same
    conversion ``statistics.sharpe_at_rf`` applies, so the two agree exactly."""
    return (1.0 + annual_pct / 100.0) ** (1.0 / float(obs_per_year)) - 1.0


def cash_feed(annual_pct: float, obs_per_year: float = 261.0,
              symbol: str = "BIL", later_pct: Optional[float] = None,
              switch_on: Optional[str] = None,
              calls: Optional[list] = None, short_by: int = 0,
              stop_after: Optional[str] = None,
              start_from: Optional[str] = None,
              skip: Optional[tuple] = None) -> Any:
    """A fetcher ``(symbol, start, end) -> FakeBars`` for a cash instrument.

    ``short_by`` truncates the series from the END by that many sessions, which
    is how a real feed behaves at the edge of its history and is what
    ``coverage.rf_dropped_days`` exists to report.

    ``stop_after`` / ``start_from`` truncate on a DATE rather than a count, and
    exist for the D29 ground-G2 shapes: the bar and the cash leg come through
    the same fetcher, so a vendor's tail-lag cuts BOTH at the same date, and a
    count-based cut cannot express "cut at exactly the day the bar was cut".
    A date is also stable under the pad ``rf_series`` adds, where a count is not.

    ``skip`` removes an inclusive DATE RANGE from the middle — a vendor outage.
    Both legs missing the same middle stretch is the one shape that reaches both
    ENDS of a run while covering none of its centre.

    ``later_pct`` + ``switch_on`` give a rate that steps on a DATE, so the
    series a caller gets for a padded window is the same series on the dates
    they share with an unpadded one.
    """
    if later_pct is not None and not switch_on:
        raise ValueError("a stepped rate needs the DATE it steps on")

    def fetch(sym: str, start: str, end: str):
        if calls is not None:
            calls.append((sym, start, end))
        if sym != symbol:
            raise RuntimeError(f"no cash series for {sym}")
        dates = weekdays_between(start, end)
        if start_from:
            dates = [d for d in dates if d >= start_from]
        if stop_after:
            dates = [d for d in dates if d <= stop_after]
        if skip:
            lo, hi = skip
            dates = [d for d in dates if not (lo <= d <= hi)]
        if short_by:
            dates = dates[:-short_by]
        level, closes = 100.0, []
        for d in dates:
            rate = (later_pct if (later_pct is not None and d >= switch_on)
                    else annual_pct)
            closes.append(level)
            level *= (1.0 + per_obs(rate, obs_per_year))
        return FakeBars(dates, closes, "synthetic-cash")

    return fetch


def no_feed(sym: str, start: str, end: str):
    """A feed that is reachable and has nothing. Distinct from `rf_bars=None`,
    which is 'nobody supplied a source at all' — the gate must fail closed on
    both, and a test that only exercises one has not tested the pair."""
    raise RuntimeError(f"the feed has no history for {sym} over {start}..{end}")


def series_with_psr(target_pct: float, n: int = 400, seed: int = 7
                    ) -> list[float]:
    """A deterministic return series whose target-ZERO PSR is ``target_pct``.

    The luck filter reads a run's own observations, so every fixture that judges
    a candidate now has to carry a series — and a fixture that carries "some
    returns" has an accidental PSR that quietly decides verdicts nobody wrote.
    This makes the reading the INPUT: ask for 90% and the criterion sees 90%.

    SOLVED FORWARD ONLY, by bisection on a mean shift, and that is deliberate.
    `statistics.sharpe_bar_for_psr` would answer this in closed form and would
    also make every fixture a function of the inverse the tests are supposed to
    be checking independently — if the forward and the inverse were wrong the
    same way, the pair would agree and the suite would prove nothing. Shifting
    the mean leaves the standard deviation, the skew and the kurtosis untouched,
    so the bisection is monotone in exactly one parameter.

    The achieved value is ASSERTED before the series is handed back. A fixture
    builder that silently misses its target is a test that is not testing what
    its name says.
    """
    import random as _random
    from app.fund import statistics as _st

    rnd = _random.Random(seed)
    base = [rnd.gauss(0.0, 0.01) for _ in range(n)]
    mu0 = sum(base) / len(base)
    base = [x - mu0 for x in base]                      # centred: PSR is 50%
    lo, hi = -0.02, 0.02
    for _ in range(200):
        mid = (lo + hi) / 2.0
        got = _st.psr_from_series([x + mid for x in base], 0.0)
        if not got["measurable"]:                       # pragma: no cover
            raise AssertionError("the fixture's own series is unmeasurable")
        if got["psr_pct"] < target_pct:
            lo = mid
        else:
            hi = mid
    out = [x + (lo + hi) / 2.0 for x in base]
    got = _st.psr_from_series(out, 0.0)
    assert abs(got["psr_pct"] - target_pct) < 0.05, (
        f"series_with_psr asked for {target_pct} and built {got['psr_pct']}")
    return out


def daily_returns_block(series: list[float], start: str = "2021-01-04") -> dict:
    """``daily_returns`` in the belt's shape, on consecutive weekdays.

    Sessions rather than calendar days: the alpha luck filter only needs a clock
    it can read, and a weekday series keeps the fixture's annualisation near 252
    so a Sharpe quoted in a failure sentence is in units a reader recognises.
    """
    dates = weekdays_between(start, "2099-12-31")[:len(series)]
    return {"present": True, "dates": dates, "strategy": list(series),
            "benchmark": [], "benchmark_present": False, "n": len(series)}
