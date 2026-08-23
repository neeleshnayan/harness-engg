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
              calls: Optional[list] = None, short_by: int = 0) -> Any:
    """A fetcher ``(symbol, start, end) -> FakeBars`` for a cash instrument.

    ``short_by`` truncates the series from the END by that many sessions, which
    is how a real feed behaves at the edge of its history and is what
    ``coverage.rf_dropped_days`` exists to report.

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
