"""Retention across several folds, because one holdout is one draw.

Every retention number this fund has produced came from a single test window —
2026 year-to-date, one regime, small caps up sharply. A candidate judged on that
window was judged once, by one draw, and "kept 33% of its edge" reads like a
measurement when it is closer to a coin landing somewhere.

Walk-forward asks the question repeatedly. Slide a train/test pair down the
history, re-select parameters on each train leg, and score each test leg. The
useful output is not a number but a DISTRIBUTION: a rule that retains across
most folds has something; one that retains in a single fold and collapses in the
rest was fitted, and the single-window test had a real chance of landing on the
flattering fold.

Parameters are re-chosen inside every fold. Choosing them once on all the data
and then "testing" per fold leaks the answer into every exam — the folds would
differ in dates while sharing a selection made with full hindsight, which looks
like validation and is not.

Three ways a fold can fail to produce a number, all kept distinct from zero:

  * the test leg placed NO ORDERS — it was never examined (usually warm-up
    starvation), and scoring that as 0% retention would condemn a strategy
    nobody looked at;
  * the run CRASHED — unmeasured, and a crash is not a result;
  * the train leg LOST money — retention is undefined, because a ratio against a
    negative denominator inverts sign and reports a losing fold as a triumph.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from statistics import median
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: What fraction of its training edge a fold must keep to count as retained.
#: The same floor the gate applies to the single-window test, deliberately — a
#: per-fold bar that differed from the gate's would make the two disagree about
#: the same strategy.
RETENTION_FLOOR = 0.5

#: A training return below this makes the retention RATIO meaningless, in exactly
#: the way a negative one does. The failure is real and was observed: a null in
#: the calibration audit trained at +3.66% and tested at +50.5%, reporting that
#: it "kept 1379% of its edge" while a criterion asking for 50% waved it through.
#:
#: The THRESHOLD, unlike the failure, is a judgement and is labelled as one. 5%
#: over a training year is the point below which an "edge" sits under the
#: equal-weight benchmark this fund measures against (+14.8% in 2025) and inside
#: the noise of a single small-cap's daily moves — so there is nothing whose
#: persistence is worth asking about. It is not derived from the audit; picking a
#: number just large enough to catch one example would be fitting the instrument
#: to its first reading.
MIN_TRAIN_RETURN_PCT = 5.0


def _d(s: str) -> date:
    return date.fromisoformat(s)


def folds(start: str, end: str, train_days: int = 252,
          test_days: int = 63, step_days: Optional[int] = None,
          max_folds: int = 6) -> list[dict[str, str]]:
    """Sliding train/test windows across the available history.

    Non-overlapping TEST legs by default (``step_days`` defaults to
    ``test_days``): overlapping tests would count the same days more than once
    and make a lucky patch look like several independent successes.

    Trading days are approximated by calendar days at roughly 252/365. Exactness
    is not needed — the engine reports the window it actually covered, and that
    is what gets recorded.
    """
    step = step_days or test_days
    cal = lambda d: int(d * 365 / 252)  # noqa: E731 — trading days to calendar
    s, e = _d(start), _d(end)
    out: list[dict[str, str]] = []
    train_start = s
    while len(out) < max_folds:
        train_end = train_start + timedelta(days=cal(train_days))
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=cal(test_days))
        if test_end > e:
            break
        out.append({"train_start": train_start.isoformat(),
                    "train_end": train_end.isoformat(),
                    "test_start": test_start.isoformat(),
                    "test_end": test_end.isoformat()})
        train_start = train_start + timedelta(days=cal(step))
    return out


def window_for(end: str, min_folds: int, train_days: int = 252,
               test_days: int = 63, floor: Optional[str] = None) -> list[dict[str, str]]:
    """Folds ending at ``end``, reaching back far enough to fit ``min_folds``.

    Exists because sizing the window from a CALLER'S holdout silently made the
    gate unclearable. The audits used a 2025-01-01 to 2026-08-14 holdout, which
    fits exactly two folds, while the gate asks for three — so every candidate
    failed with "the consistency test did not run" no matter how good it was, and
    the failure described our arithmetic rather than the strategy.

    A window is therefore derived from what the TEST needs, not from what one
    train/test split happened to use: reach back
    ``train + test + (min_folds - 1) * step`` trading days, converted to calendar
    days at 252/365.

    ``floor`` caps the reach-back at the earliest date with data. Reaching past it
    is not harmful — folds with no bars place no trades and are reported
    unmeasurable rather than failed — but it wastes engine time on runs that
    cannot say anything.
    """
    cal = lambda d: int(d * 365 / 252)  # noqa: E731
    # K folds need train + test + (K-1) steps of room. One extra step is added as
    # slack: the trading-to-calendar conversion rounds down at every term, and
    # without it the last fold's test leg overshot the window by a single day and
    # silently produced K-1 folds — which read as "the history cannot support this
    # test" when the real cause was arithmetic.
    need = train_days + test_days * (min_folds + 1)
    start = _d(end) - timedelta(days=cal(need))
    if floor and start < _d(floor):
        start = _d(floor)
    return folds(start.isoformat(), end, train_days=train_days,
                 test_days=test_days, max_folds=max(min_folds, 6))


def retention(train_return: Optional[float],
              test_return: Optional[float],
              test_orders: Optional[int]) -> dict[str, Any]:
    """One fold's retention, or a stated reason there isn't one.

    Never returns a number it cannot justify. The three undefined cases are
    named rather than collapsed to zero, because each implies a different next
    action: give it warm-up, re-run it, or stop asking about retention on a
    strategy that did not make money to retain.
    """
    if test_orders == 0:
        return {"retention": None, "measurable": False,
                "reason": "the test leg placed no trades, so it says nothing "
                          "either way — usually warm-up starvation"}
    if test_return is None or train_return is None:
        return {"retention": None, "measurable": False,
                "reason": "a leg produced no return figure — unmeasured, "
                          "which is not the same as zero"}
    if train_return <= 0:
        return {"retention": None, "measurable": False,
                "reason": f"the train leg made {train_return:.2f}% — there was "
                          f"no edge to retain, and a ratio against a negative "
                          f"denominator would report a loss as a triumph"}
    if train_return < MIN_TRAIN_RETURN_PCT:
        # The failure mode this closes, from the null audit: train +3.7%, test
        # +50.5%, "retention 1379%" — a criterion asking for 50% waved through by
        # a denominator too small to divide by.
        return {"retention": None, "measurable": False,
                "reason": f"the train leg made only {train_return:.2f}%, under "
                          f"the {MIN_TRAIN_RETURN_PCT}% needed for a ratio to "
                          f"mean anything — retention against a near-zero "
                          f"denominator explodes and passes trivially"}
    return {"retention": test_return / train_return, "measurable": True,
            "reason": None}


class WalkForward:
    """Runs the folds and reports the distribution, not a headline."""

    def __init__(self, runner: Any = None):
        self._runner = runner

    def _lean(self):
        if self._runner is None:
            from app.fund.leanrunner import LeanRunner
            self._runner = LeanRunner()
        return self._runner

    def evaluate(self, algorithm: str, grid: dict[str, list[str]],
                 window: list[dict[str, str]]) -> dict[str, Any]:
        """Sweep-then-test, once per fold. Sequential by design.

        Each fold is a full grid plus one test run, and the engine slots are
        capped at one container, so this is minutes per fold. Parallelising it
        would only queue against the same semaphore while making the failures
        harder to read.
        """
        r = self._lean()
        results: list[dict[str, Any]] = []
        for i, f in enumerate(window, 1):
            logger.info("walk-forward fold %d/%d: train %s..%s test %s..%s",
                        i, len(window), f["train_start"], f["train_end"],
                        f["test_start"], f["test_end"])
            try:
                sid = r.submit_sweep(algorithm, grid, holdout=f)["sweep_id"]
            except Exception as e:  # noqa: BLE001
                results.append({"fold": i, **f, "state": "failed",
                                "error": f"{type(e).__name__}: {e}"[:200]})
                continue
            sweep = self._await_sweep(r, sid)
            ho = (sweep or {}).get("holdout_result") or {}
            train = ho.get("train") or {}
            test = ho.get("test") or {}
            ret = retention(train.get("return_pct"), test.get("return_pct"),
                            test.get("total_orders"))
            results.append({
                "fold": i, **f,
                "state": ho.get("state") or (sweep or {}).get("state"),
                "sweep_id": sid,
                "chosen": ho.get("parameters"),
                "train_return_pct": train.get("return_pct"),
                "test_return_pct": test.get("return_pct"),
                "test_orders": test.get("total_orders"),
                "test_psr_pct": test.get("psr_pct"),
                "dates_honoured": ho.get("dates_honoured"),
                **ret,
            })
        return {"algorithm": algorithm, "grid": grid,
                "folds": results, **summarise(results)}

    @staticmethod
    def _await_sweep(r: Any, sweep_id: str, timeout_s: float = 5_400.0):
        import time
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            s = r.sweep(sweep_id)
            if s.get("state") != "running":
                return s
            time.sleep(5)
        logger.warning("walk-forward fold timed out waiting on sweep %s", sweep_id)
        return None


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    """The distribution, and a sentence about what it means.

    Reports the measurable folds AND the count that could not be measured. A
    median over two folds when four were attempted is a different claim from a
    median over four, and hiding the denominator is how a thin result passes for
    a robust one.
    """
    measurable = [f for f in results if f.get("measurable")]
    rets = [f["retention"] for f in measurable]
    unmeasurable = [f for f in results if not f.get("measurable")]
    if not rets:
        return {
            "folds_attempted": len(results),
            "folds_measurable": 0,
            "median_retention": None,
            "folds_retained": 0,
            "verdict": ("no fold produced a measurable retention — "
                        + "; ".join(sorted({str(f.get("reason")) for f in unmeasurable}))
                        + ". This is an absence of evidence, not evidence of absence"),
        }
    retained = [x for x in rets if x >= RETENTION_FLOOR]
    med = median(rets)
    return {
        "folds_attempted": len(results),
        "folds_measurable": len(rets),
        "folds_unmeasurable": len(unmeasurable),
        "median_retention": round(med, 4),
        "min_retention": round(min(rets), 4),
        "max_retention": round(max(rets), 4),
        "folds_retained": len(retained),
        "retention_floor": RETENTION_FLOOR,
        "verdict": _verdict(len(rets), len(retained), med, len(unmeasurable)),
    }


def _verdict(n: int, retained: int, med: float, unmeasurable: int) -> str:
    tail = (f" {unmeasurable} fold(s) could not be measured at all."
            if unmeasurable else "")
    if retained == n and n >= 2:
        return (f"kept at least {RETENTION_FLOOR:.0%} of its edge in all {n} "
                f"measurable folds (median {med:.0%}) — the one result so far "
                f"that a single window could not have manufactured." + tail)
    if retained == 0:
        return (f"kept the floor in none of {n} measurable folds "
                f"(median {med:.0%}) — consistent with a fit, not an edge." + tail)
    return (f"kept the floor in {retained} of {n} measurable folds "
            f"(median {med:.0%}) — inconsistent, which is what a single "
            f"flattering window looks like from the inside." + tail)
