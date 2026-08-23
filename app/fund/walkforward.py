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

Retention compares RATES, not cumulative returns, and that distinction is not a
refinement — it is the difference between a working criterion and one nothing can
pass. Measured with a strategy that reads future prices: 12-month train legs
returned +137% to +302% while their 3-month test legs returned +3% to +9%, so the
raw ratio was 0.02 to 0.04 against a 0.5 floor. Perfect foreknowledge scored 0.03.
A ratio of cumulative returns over unequal windows measures the length of the
windows, and compounding makes the longer one enormously larger.

Four ways a fold can fail to produce a number, all kept distinct from zero and
from each other, because each implies a different next action:

  * the test leg placed NO ORDERS — it was never examined (usually warm-up
    starvation), and scoring that as 0% retention would condemn a strategy
    nobody looked at;
  * the run was KILLED BY THE CLOCK — the engine hit its wall-clock ceiling and
    the container was destroyed. Added as its own case 2026-08-21 on the quant
    seat's accepted finding: six runs died at exactly LEAN_JOB_TIMEOUT and every
    one of them entered the belt indistinguishable from a strategy that had
    nothing to say. The action is "re-run it, probably with more time", which is
    nothing like "give it warm-up" or "stop asking";
  * the run CRASHED — unmeasured, and a crash is not a result;
  * the train leg LOST money — retention is undefined, because a ratio against a
    negative denominator inverts sign and reports a losing fold as a triumph.
"""

from __future__ import annotations

import ast
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
#: the way a negative one does.
#:
#: PROVENANCE CORRECTED 2026-08-20 (docs/MIN_TRAIN_RETURN_REVIEW_2026-08-20.md):
#: the "motivating case" earlier recorded here — a null training at +3.66% and
#: testing at +50.5% — never occurred. The real sweep trained at +10.171% and
#: tested at +140.219%; the 3.66% was back-solved from the wrong numerator. No
#: floor of 2, 5, or 10 excludes the real shape, and on 83 real belt sweeps this
#: floor has never removed a null fold. It is kept because it is the only guard
#: against the one demonstrated real explosion (train +0.03% -> raw ratio 231)
#: that a strict-positive check alone would miss.
#:
#: The THRESHOLD is a judgement and is labelled as one. 5% over a training year
#: is the point below which an "edge" sits under the equal-weight benchmark this
#: fund measures against (+14.8% in 2025) and inside the noise of a single
#: small-cap's daily moves — so there is nothing whose persistence is worth
#: asking about.
MIN_TRAIN_RETURN_PCT = 5.0


def _d(s: str) -> date:
    return date.fromisoformat(s)


def cal_days(trading_days: int) -> int:
    """Trading days as calendar days, at roughly 252/365.

    Named once and called everywhere this conversion is needed. It used to be a
    lambda redefined in two functions, which is two copies of one belief — and
    the fold-count arithmetic below now depends on it agreeing with itself
    exactly, because ``span_for_folds`` predicts what ``folds`` will produce.
    """
    return int(trading_days * 365 / 252)


def span_for_folds(n_folds: int, test_days: int, train_days: int = 252) -> int:
    """Calendar days ``n_folds`` folds occupy, for that train/test geometry.

    NOT an estimate — it is the closed form of what ``folds()`` below actually
    lays down, and it is used to decide how many folds a covered window must
    supply. Fold *i* starts at ``S + (i-1)*cal(step)``; with the default
    non-overlapping step the last test leg ends at
    ``S + cal(train) + n*cal(test) + 1``.

    Verified against the shipped generator 2026-08-23 for holds 1/2/3/5/10/21/
    42/63 at both history floors: predicted span equalled the generated span in
    every case (e.g. a 21-day hold gives 850 days at 4 folds and 971 at 5, and
    the generator produced exactly those).
    """
    return cal_days(train_days) + n_folds * cal_days(test_days) + 1


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
    cal = cal_days
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


def decisions_per_test_leg(criteria: Optional[dict[str, Any]] = None) -> int:
    """How many of a strategy's own decisions a test leg must contain.

    Four is a judgement, labelled as one: the point where one lucky trade stops
    dominating the leg's return. It is not derived from any measurement here.

    READ FROM THE GATE, not held here. Until 2026-08-23 this was a module
    constant ``DECISIONS_PER_TEST_LEG = 4`` sitting beside
    ``CRITERIA["min_decisions_per_test_leg"] = 4`` — two copies of one belief,
    and the criterion was the copy NOBODY READ: grepping the repo, the gate's
    key had zero consumers while the geometry used the constant. A declared
    criterion that decides nothing is the register-of-notes failure at the
    level of the bar itself, so the constant is gone and the criterion is the
    value in force. That also makes it version-aware: ``CRITERIA_V2`` and
    ``CRITERIA_V1`` set this to 0, and re-judging under them now really does
    use their geometry instead of v4's.
    """
    from app.fund.gate import CRITERIA
    c = {**CRITERIA, **(criteria or {})}
    return int(c.get("min_decisions_per_test_leg") or 0)


def declared_hold_days(code: Optional[str], grid: Optional[dict] = None,
                       default: int = 21) -> dict[str, Any]:
    """A strategy's holding period, from its source or its grid.

    Needed because the walk-forward test leg has to be long enough for the
    strategy's OWN clock. Measured: our ~30 months of history supports 6 folds for
    a 5-day hold, 4 for a 21-day hold, and ONE for a 63-day hold — so the same
    fold geometry is generous for a fast rule and meaningless for a slow one.

    Read the same way the benchmark reads UNIVERSE: statically from a module-level
    constant, because the engine has exited by the time results are judged. Falls
    back to the largest value in the grid, then to a default that is REPORTED as
    assumed — a test leg sized from a guessed holding period would look rigorous
    while measuring nothing.
    """
    if code:
        try:
            tree = ast.parse(code)
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if "HOLD_DAYS" not in [t.id for t in node.targets
                                       if isinstance(t, ast.Name)]:
                    continue
                if isinstance(node.value, ast.Constant) and isinstance(
                        node.value.value, int):
                    return {"hold_days": node.value.value, "source": "declared"}
        except SyntaxError:
            pass
    for key in ("hold_days", "period", "slow"):
        vals = (grid or {}).get(key)
        if vals:
            try:
                return {"hold_days": max(int(v) for v in vals),
                        "source": f"grid:{key}"}
            except (TypeError, ValueError):
                continue
    return {"hold_days": default, "source": "assumed",
            "note": (f"no HOLD_DAYS constant and nothing holding-period-shaped in "
                     f"the grid, so the test leg was sized on an assumed "
                     f"{default}-day hold — declare HOLD_DAYS to make this exact")}


#: The test leg a bar with no decision requirement gets. Pre-v3 behaviour, kept
#: reachable so a re-judge under CRITERIA_V1/V2 — both of which set
#: ``min_decisions_per_test_leg`` to 0, meaning "this bar had no such concept" —
#: gets the fixed calendar leg those versions were written against, rather than
#: ``hold * 0`` collapsing every test leg to one day.
DEFAULT_TEST_DAYS = 63


def window_for_strategy(end: str, hold_days: int, min_folds: int,
                        train_days: int = 252,
                        floor: Optional[str] = None,
                        criteria: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Folds whose test legs are long enough for THIS strategy to act several times.

    Returns the folds AND, when the history cannot supply ``min_folds`` of them,
    says so — because a slow strategy on short history is UNTESTABLE, which is a
    different verdict from failed. Reporting it as failed is the same error as
    reading a no-trade holdout as a lost edge.
    """
    decisions = decisions_per_test_leg(criteria)
    test_days = max(1, hold_days * decisions) if decisions > 0 else DEFAULT_TEST_DAYS
    w = window_for(end, min_folds=min_folds, train_days=train_days,
                   test_days=test_days, floor=floor)
    return {
        "folds": w,
        "test_days": test_days,
        "hold_days": hold_days,
        "decisions_per_test_leg": decisions,
        "train_days": train_days,
        "enough": len(w) >= min_folds,
        "min_folds": min_folds,
        "note": (f"{len(w)} fold(s) fit; a {hold_days}-day hold needs a "
                 f"{test_days}-day test leg to make "
                 f"{decisions} decisions, and the available history "
                 f"does not supply {min_folds} of them — this strategy is NOT "
                 f"TESTABLE here, which is not the same as failing"
                 if len(w) < min_folds else
                 f"{len(w)} fold(s), each a {test_days}-day test leg giving the "
                 f"{hold_days}-day hold about {decisions} decisions"),
    }


def _span_days(start: str, end: str) -> Optional[int]:
    """Calendar days a window covers, for annualising its return."""
    try:
        return max(1, (_d(end) - _d(start)).days)
    except Exception:  # noqa: BLE001
        return None


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
    cal = cal_days
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


def _annualise(total_pct: Optional[float], days: Optional[int]) -> Optional[float]:
    """A cumulative return expressed as an annual rate.

    Load-bearing. Without it retention divides a 12-month return by a 3-month one
    and reports the ratio as decay: measured, a perfect-foresight strategy scored
    0.03 against a 0.5 floor purely because its test leg was a quarter as long.

    Returns None rather than guessing when the window length is unknown — a rate
    computed over an assumed duration is a fabricated number, and this one decides
    verdicts.
    """
    if total_pct is None or not days or days <= 0:
        return None
    growth = 1.0 + total_pct / 100.0
    if growth <= 0:
        # A total loss has no meaningful annual rate; -100% annualised is still
        # -100% and the root would be complex.
        return -100.0
    return (growth ** (365.0 / days) - 1.0) * 100.0


#: What an unmeasurable fold says when the engine ran out of wall clock. Named
#: rather than inlined so the Lab, the gate's failure text and the tests all
#: agree on one sentence, and so a reader grepping for "timed out" finds one
#: place. See the module docstring's four-cases list.
TIMEOUT_REASON = (
    "the engine hit its wall-clock ceiling and the container was killed, so this "
    "fold produced NO evidence — it is not a result and it is not a strategy "
    "that declined to trade. Re-run it, with more time if it happens again")


def timed_out(*legs: Any) -> bool:
    """Whether any supplied leg carries the engine's timeout flag.

    Reads a BOOLEAN the runner sets, never the error prose. The sentence is for
    humans and gets reworded; a flag does not, and a `"timed out" in error` match
    is one copy-edit away from silently reclassifying every killed run as an
    ordinary failure.
    """
    return any(bool((leg or {}).get("timed_out")) for leg in legs
               if isinstance(leg, dict))


def retention(train_return: Optional[float],
              test_return: Optional[float],
              test_orders: Optional[int],
              train_days: Optional[int] = None,
              test_days: Optional[int] = None,
              engine_timed_out: bool = False) -> dict[str, Any]:
    """One fold's retention as a ratio of RATES, or a stated reason there isn't one.

    Never returns a number it cannot justify. The undefined cases are named rather
    than collapsed to zero, because each implies a different next action: give it
    warm-up, re-run it with more time, re-run it, or stop asking about retention
    on a strategy that did not make money to retain.

    When window lengths are supplied both legs are annualised first, so the ratio
    measures whether the EDGE persisted rather than how long each window was.
    Without them it falls back to raw cumulative returns and says so, because a
    silent fallback here is how the criterion became unpassable.
    """
    # FIRST, ahead of every other reason. A killed container explains all the
    # missing figures below it, and reporting one of the downstream symptoms —
    # "no return figure", or worse "placed no trades" — sends the reader to fix
    # a strategy when the thing that failed was ours. Deliberately does NOT
    # depend on test_orders: a run killed mid-window may have placed orders
    # already, and a partial count is not a measurement either.
    if engine_timed_out:
        return {"retention": None, "measurable": False,
                "timed_out": True, "reason": TIMEOUT_REASON}
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
        # The failure mode this closes, measured on the real belt: train +0.03%,
        # test +6.94%, raw ratio 231 — a criterion asking for 50% waved through
        # by a denominator too small to divide by. (An earlier comment here
        # cited a +3.7%/+50.5% case; that case never occurred — see
        # docs/MIN_TRAIN_RETURN_REVIEW_2026-08-20.md.)
        return {"retention": None, "measurable": False,
                "reason": f"the train leg made only {train_return:.2f}%, under "
                          f"the {MIN_TRAIN_RETURN_PCT}% needed for a ratio to "
                          f"mean anything — retention against a near-zero "
                          f"denominator explodes and passes trivially"}
    tr_rate = _annualise(train_return, train_days)
    te_rate = _annualise(test_return, test_days)
    if tr_rate is not None and te_rate is not None and tr_rate > 0:
        return {"retention": te_rate / tr_rate, "measurable": True,
                "basis": "annualised", "train_annual_pct": round(tr_rate, 2),
                "test_annual_pct": round(te_rate, 2), "reason": None}
    return {"retention": test_return / train_return, "measurable": True,
            "basis": "cumulative",
            "reason": ("window lengths were not supplied, so this compares "
                       "cumulative returns over possibly unequal periods — "
                       "treat it as indicative only")}


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
            if sweep is None:
                # The fold's whole sweep outlasted its own deadline. Previously
                # this fell through as an empty dict and the fold was reported
                # "a leg produced no return figure" — true, and useless: it
                # describes the symptom of our clock running out as though the
                # strategy had been examined.
                results.append({
                    "fold": i, **f, "state": "timeout", "sweep_id": sid,
                    "retention": None, "measurable": False, "timed_out": True,
                    "reason": TIMEOUT_REASON,
                })
                continue
            ho = sweep.get("holdout_result") or {}
            train = ho.get("train") or {}
            test = ho.get("test") or {}
            killed = timed_out(ho, test)
            ret = retention(train.get("return_pct"), test.get("return_pct"),
                            test.get("total_orders"),
                            train_days=_span_days(f["train_start"], f["train_end"]),
                            test_days=_span_days(f["test_start"], f["test_end"]),
                            engine_timed_out=killed)
            results.append({
                "fold": i, **f,
                "state": "timeout" if killed else (
                    ho.get("state") or sweep.get("state")),
                "sweep_id": sid,
                "chosen": ho.get("parameters"),
                "train_return_pct": train.get("return_pct"),
                "test_return_pct": test.get("return_pct"),
                "test_orders": test.get("total_orders"),
                "test_psr_pct": test.get("psr_pct"),
                # The requested window is already in **f; this is the window the
                # ENGINE actually covered, and `dates_honoured` says whether the
                # two agree. An algorithm that ignores start/end runs the same
                # dates twice and the "held-out" fold proves nothing.
                "train_window": train.get("window"),
                "test_window": test.get("window"),
                # The fold's out-of-sample daily series, aligned strategy vs
                # benchmark and undownsampled (adversary r4 rec 4). This is
                # what gate v5 needs per fold; without it no premia statistic
                # is computable and the fold reduces to one retention scalar.
                "daily_returns": test.get("daily_returns"),
                "daily_returns_note": ho.get("daily_returns_note"),
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
    # Counted on its own line because it is OUR failure, not the strategy's, and
    # a summary that folds it into "unmeasurable" invites the reader to conclude
    # something about the rule. Six of these were read as strategy findings
    # before the reason was split out (run-quant-entry11).
    killed = [f for f in unmeasurable if f.get("timed_out")]
    if not rets:
        return {
            "folds_attempted": len(results),
            "folds_measurable": 0,
            "median_retention": None,
            "folds_retained": 0,
            "folds_timed_out": len(killed),
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
        "folds_timed_out": len(killed),
        "median_retention": round(med, 4),
        "min_retention": round(min(rets), 4),
        "max_retention": round(max(rets), 4),
        "folds_retained": len(retained),
        "retention_floor": RETENTION_FLOOR,
        "verdict": _verdict(len(rets), len(retained), med, len(unmeasurable),
                            len(killed)),
    }


def _verdict(n: int, retained: int, med: float, unmeasurable: int,
             killed: int = 0) -> str:
    tail = (f" {unmeasurable} fold(s) could not be measured at all."
            if unmeasurable else "")
    if killed:
        tail += (f" {killed} of those was the ENGINE running out of wall clock, "
                 f"not the strategy — that fold was never examined."
                 if killed == 1 else
                 f" {killed} of those were the ENGINE running out of wall clock, "
                 f"not the strategy — those folds were never examined.")
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
