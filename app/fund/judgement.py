"""The knobs we chose ourselves, and what would show we chose wrong.

Every threshold in this fund judges strategies. Nothing judges the thresholds.

That asymmetry is the real gap in "learn as you go with strong feedback loops":
the gate is ruthless about a backtest and silent about its own numbers, and those
numbers shape every verdict it has ever issued. `DECISIONS_PER_TEST_LEG = 4` is
labelled a judgement in its own source and is not derived from any measurement.
`MIN_TRAIN_RETURN_PCT` was raised 2.0 -> 5.0 on principle, after the author
noticed the threshold failed to catch the very example that motivated it. Both
decide outcomes. Neither can currently be wrong, because nothing states what being
wrong would look like.

So this module is a register of our own judgement calls. Four properties, and the
first is the one that makes it worth having at all:

  1. It READS the live value rather than restating it. A registry that carries its
     own copy of a number is a second place to disagree with the code, and it will
     drift silently and then be cited as though it had been checked. Where a value
     cannot be read, the entry says so instead of guessing.
  2. Each entry declares its BASIS — measured, judged, mandate or external — which
     answers who may change it and on what grounds. Conflating these is how a
     convention borrowed from someone else's fund ends up defended as a finding.
  3. Each entry states what would FALSIFY it. Not "review periodically": the
     specific observation that would mean the number is wrong.
  4. Each has a review TRIGGER (the evidence that makes the question answerable)
     and a backstop DATE. A trigger alone can be postponed forever; a date alone
     invites a review with nothing to review against. Both, or the loop is theatre.

What this module does not do is change anything. It surfaces the questions. A knob
still moves the only way any threshold here moves — a versioned change with a
written reason, in either direction.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: The live RiskControl, injected by the API so limits are read from the fund that
#: is actually running. Left None outside the app, where the register then reports
#: those entries UNREADABLE — which is the truthful answer, because a bare process
#: genuinely cannot see what limits are in force.
_CONTROL: Any = None


def use_control(control: Any) -> None:
    """Point the register at the running fund's risk control."""
    global _CONTROL
    _CONTROL = control


#: A provider returning the live metric namespace that ``TriggerSpec`` reads.
#: None outside the app, where every spec then reports UNREADABLE — which is
#: the truthful answer and, importantly, NOT "did not fire".
_METRICS: Optional[Callable[[], dict[str, Any]]] = None


def use_metrics(provider: Optional[Callable[[], dict[str, Any]]]) -> None:
    """Point the register at a live metric source for machine-checkable triggers."""
    global _METRICS
    _METRICS = provider


#: Comparators a trigger may use. Deliberately tiny: a trigger language rich
#: enough to be interesting is rich enough to be wrong in ways nobody reviews.
_COMPARATORS: dict[str, Callable[[float, float], bool]] = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
}


class TriggerSpec:
    """A review trigger a machine can check: ``<metric> <comparator> <value>``.

    Sixteen of seventeen registered triggers were free text no code evaluated,
    and the register returned ``due_for_review: []`` while a 7.75% drawdown sat
    in plain sight — R6's own trigger ("first drawdown episode over 3% from
    peak") had demonstrably fired (validator run 8b863152, 2026-08-20). A
    trigger nothing evaluates is a note, and a register of notes reviews
    nothing.

    Free-text triggers stay prose. This is for the quantifiable ones, and it
    carries the same absence discipline as everything else here: an unreadable
    metric is reported UNREADABLE, never as "not fired". A trigger that cannot
    be checked has NOT been checked.
    """

    def __init__(self, metric: str, comparator: str, value: float,
                 means: str = ""):
        if comparator not in _COMPARATORS:
            raise ValueError(
                f"comparator must be one of {sorted(_COMPARATORS)}, got {comparator!r}")
        self.metric = metric
        self.comparator = comparator
        self.value = float(value)
        self.means = means

    def __str__(self) -> str:
        return f"{self.metric} {self.comparator} {self.value:g}"

    def evaluate(self, metrics: Optional[dict[str, Any]]) -> dict[str, Any]:
        base = {"spec": str(self), "metric": self.metric,
                "comparator": self.comparator, "threshold": self.value,
                "means": self.means}
        if metrics is None:
            return {**base, "readable": False, "fired": None, "observed": None,
                    "note": "no live metric source wired — this trigger has NOT "
                            "been checked, which is not the same as not fired"}
        if self.metric not in metrics:
            return {**base, "readable": False, "fired": None, "observed": None,
                    "note": f"{self.metric} is not in the live metric namespace — "
                            f"this trigger has NOT been checked"}
        raw = metrics.get(self.metric)
        try:
            observed = float(raw)
        except (TypeError, ValueError):
            return {**base, "readable": False, "fired": None, "observed": raw,
                    "note": f"{self.metric} read as {raw!r}, which is not a number — "
                            f"this trigger has NOT been checked"}
        return {**base, "readable": True, "observed": observed,
                "fired": _COMPARATORS[self.comparator](observed, self.value)}


def _live_metrics() -> Optional[dict[str, Any]]:
    if _METRICS is None:
        return None
    try:
        return _METRICS() or {}
    except Exception as e:  # noqa: BLE001
        logger.info("judgement: metric source unreadable: %s", e)
        return None

#: How a number came to hold its value. The distinction is not cosmetic: it says
#: who is entitled to change it and what kind of argument counts.
#:
#:   measured  — derived from something we observed here. Falsified by new
#:               measurement, and the measurement is the argument.
#:   judged    — we picked it. Defensible, undemonstrated, and the category that
#:               most needs this register.
#:   mandate   — the operator's risk appetite. NOT ours to tune. A mandate number
#:               drifting quietly downward is the failure this whole system exists
#:               to prevent, so it is registered to be watched, never to be
#:               optimised.
#:   external  — a fact about the world (a vendor limit, the machine, the data).
#:               Changed by changing the world, not by argument.
BASES = ("measured", "judged", "mandate", "external")


class Judgement:
    """One number we are responsible for, and the terms of its own review."""

    def __init__(self, key: str, *, where: str, basis: str, why: str,
                 falsified_by: str, review_trigger: str, review_by: str,
                 read: Optional[Callable[[], Any]] = None,
                 expected: Any = None,
                 trigger_spec: Any = None):
        if basis not in BASES:
            raise ValueError(f"basis must be one of {BASES}, got {basis!r}")
        self.key = key
        self.where = where
        self.basis = basis
        self.why = why
        self.falsified_by = falsified_by
        self.review_trigger = review_trigger
        self.review_by = review_by
        self._read = read
        self.expected = expected
        #: Zero or more machine-checkable forms of ``review_trigger``. ANY one
        #: firing makes the entry due — a register that required all of them
        #: would be harder to trip than the prose it replaces.
        if trigger_spec is None:
            self.trigger_spec: list[TriggerSpec] = []
        elif isinstance(trigger_spec, TriggerSpec):
            self.trigger_spec = [trigger_spec]
        else:
            self.trigger_spec = list(trigger_spec)

    def value(self) -> dict[str, Any]:
        """The value as it is RIGHT NOW, read from the running system.

        Reports the read failure rather than substituting a remembered value.
        A register that quietly falls back to what the number used to be would
        assert current knowledge of something it could not see, which is the one
        habit this codebase refuses everywhere else.
        """
        if self._read is None:
            return {"value": None, "readable": False,
                    "note": "no reader wired — this entry documents a decision "
                            "whose value is not a single readable constant"}
        try:
            return {"value": self._read(), "readable": True}
        except Exception as e:  # noqa: BLE001
            logger.info("judgement %s: could not read live value: %s", self.key, e)
            return {"value": None, "readable": False,
                    "note": f"could not read the live value: {e}. Treat this "
                            f"entry as UNVERIFIED, not as unchanged"}

    def drift(self) -> dict[str, Any]:
        """Has the live value moved away from what was registered?

        Drift is not misconduct — numbers are supposed to change. Drift that
        nobody noticed is the problem, because the reason on file then describes a
        decision that is no longer in force.
        """
        got = self.value()
        if not got["readable"] or self.expected is None:
            return {"drifted": None, "reason": "cannot compare"}
        if got["value"] == self.expected:
            return {"drifted": False, "reason": "matches the registered value"}
        return {
            "drifted": True,
            "from": self.expected,
            "to": got["value"],
            "reason": (f"{self.key} is now {got['value']!r} but was registered as "
                       f"{self.expected!r}. The reason on file describes the old "
                       f"number, so either the reason or the number is stale"),
        }

    def triggers(self, metrics: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """Every machine-checkable trigger, evaluated against the live metrics."""
        if not self.trigger_spec:
            return []
        if metrics is None:
            metrics = _live_metrics()
        return [t.evaluate(metrics) for t in self.trigger_spec]

    def due(self, today: Optional[str] = None,
            metrics: Optional[dict[str, Any]] = None) -> bool:
        """Due when the backstop DATE has passed *or* a trigger has FIRED.

        Both, because a date alone invites a review with nothing to review
        against and a trigger alone can be postponed forever — the register's
        own stated rule, now actually enforced for the quantifiable triggers.
        """
        now = today or date.today().isoformat()
        if now >= self.review_by:
            return True
        return any(t.get("fired") for t in self.triggers(metrics))

    def to_dict(self, today: Optional[str] = None,
                metrics: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if metrics is None and self.trigger_spec:
            metrics = _live_metrics()
        evaluated = self.triggers(metrics)
        fired = [t for t in evaluated if t.get("fired")]
        unchecked = [t for t in evaluated if not t.get("readable")]
        now = today or date.today().isoformat()
        date_due = now >= self.review_by
        if date_due and fired:
            why_due = "the backstop date has passed AND a trigger has fired"
        elif date_due:
            why_due = "the backstop date has passed"
        elif fired:
            why_due = "a registered trigger has fired: " + "; ".join(
                f"{t['spec']} (observed {t['observed']})" for t in fired)
        else:
            why_due = None
        return {
            "key": self.key, "where": self.where, "basis": self.basis,
            "why": self.why, "falsified_by": self.falsified_by,
            "review_trigger": self.review_trigger, "review_by": self.review_by,
            "registered_value": self.expected,
            # The trigger in machine-checkable form, its live reading, and
            # whether it fired. `unchecked_triggers` is separate from `fired`
            # on purpose: a trigger nobody could evaluate must never be counted
            # among the ones that did not fire.
            "trigger_spec": evaluated,
            "trigger_fired": bool(fired),
            "unchecked_triggers": len(unchecked),
            "due_reason": why_due,
            **self.value(), "drift": self.drift(),
            "due": date_due or bool(fired),
        }


def _gate(key: str) -> Callable[[], Any]:
    def read() -> Any:
        from app.fund.gate import CRITERIA
        return CRITERIA[key]
    return read


def _autoresume_cooldown() -> Any:
    """The loss-halt auto-resume cool-down, read from where it lives.

    Read rather than restated: a register entry that carries its own copy of
    the number cannot detect the number moving, which is the one thing the
    register exists to do.
    """
    from app.fund.riskmonitor import LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES
    return LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES


def _limit(key: str) -> Callable[[], Any]:
    """Read a risk limit as it is IN FORCE, not as `RiskLimits()` defaults it.

    Deliberately folded through RiskControl rather than read off the dataclass,
    because the two disagree: the dataclass defaults `max_order_notional_pct` to
    0.25 and `min_cash_pct` to 0.10, while the limits actually in force — folded
    from RISK_LIMITS_SET — are 0.15 and 0.05. Registering the defaults would have
    produced a register that agreed with the source code and contradicted the
    running fund, which is the exact failure it exists to catch.
    """
    def read() -> Any:
        if _CONTROL is not None:
            return getattr(_CONTROL.limits(), key)
        from app.fund.riskmonitor import RiskControl
        return getattr(RiskControl().limits(), key)
    return read


def _module(mod: str, name: str) -> Callable[[], Any]:
    def read() -> Any:
        import importlib
        return getattr(importlib.import_module(mod), name)
    return read


def _wired(job: str) -> Callable[[], Any]:
    """Reads whether a scheduled job is actually TICKING, not what it is set to.

    The generalisation that closes the hole this register was built for. Drift
    detection caught a threshold whose value no longer matched its reason; it could
    not have caught the risk monitor, whose value was fine and whose CALLER did not
    exist. A control that is correctly configured and unreachable is the same class
    of lie as a threshold that silently moved - the fund believes something about
    itself that is not true - so wiring is registered exactly like a value.

    Returns True/False rather than the tick time: the registered expectation is
    "this is wired and running", and drift means it stopped.
    """
    def read() -> Any:
        from app.fund import heartbeat
        st = heartbeat.status(job)
        if st.get("ok") is None:
            # Unobserved is not False. Another process may hold the scheduler
            # lease, so claiming it is broken would be as wrong as claiming it is
            # fine. Raising makes the register report it UNVERIFIED.
            raise RuntimeError(st.get("note") or f"{job} liveness unknown")
        return bool(st["ok"])
    return read


def registry() -> list[Judgement]:
    """Every number we chose, with the terms on which it can be overturned.

    Ordered by how much damage a wrong value does, not alphabetically. The first
    four decide whether a strategy is ever deployed at all.
    """
    return [
        Judgement(
            "DECISIONS_PER_TEST_LEG",
            # POINTER MOVED 2026-08-23, VALUE UNCHANGED. The number lived in
            # two places — a module constant in walkforward.py and
            # CRITERIA["min_decisions_per_test_leg"] in the gate — and the
            # criterion was the copy nobody read. The constant is gone and the
            # geometry now reads the criterion, so the register follows the
            # value rather than the old address; a register still pointing at a
            # deleted constant would report UNREADABLE, which is the register
            # failing at the one job it has.
            where="app/fund/gate.py CRITERIA (min_decisions_per_test_leg)",
            basis="judged", expected=4,
            read=_gate("min_decisions_per_test_leg"),
            why="A test leg should contain enough of a strategy's own decisions "
                "that one lucky trade cannot dominate it. Four is where that felt "
                "true. It is not derived from anything measured here, and the "
                "source says so.",
            falsified_by="Judge the same strategies at 4 and at 8 decisions per "
                         "leg. If the verdicts agree, 4 is fine and the extra "
                         "history it costs is waste. If they disagree, 4 is too "
                         "few and every NOT TESTABLE verdict issued under it is "
                         "suspect — including the ones that made us feel rigorous.",
            review_trigger="10 strategies judged under gate v3",
            review_by="2026-11-01"),
        Judgement(
            "min_psr_pct",
            where="app/fund/gate.py CRITERIA", basis="measured",
            expected=65.0, read=_gate("min_psr_pct"),
            why="Nulls reached ~57% PSR on this history, so the original 50% sat "
                "inside the noise. The floor is measured; the 15-point margin "
                "above it is a judgement wearing a measurement's clothes.",
            falsified_by="Re-run the null audit on a longer history. If nulls "
                         "clear 65%, the margin was too thin and noise has been "
                         "passing. If they top out near 57% across many more "
                         "draws, 65 is costing us real candidates for nothing.",
            review_trigger="null audit re-run on >5 years of history",
            review_by="2026-12-01"),
        Judgement(
            "min_walkforward_folds",
            where="app/fund/gate.py CRITERIA", basis="measured",
            expected=4, read=_gate("min_walkforward_folds"),
            why="Four, with a STRICT majority of three required. Chosen with the "
                "majority rule rather than separately, because the two only mean "
                "something together: P(walk-forward leg passes) for noise vs a "
                "p=0.7 edge is 75%/91% at 1-of-2 (discrimination 1.21 — nearly "
                "uninformative), 31%/65% at 3-of-4 (2.09), and 6%/24% at 4-of-4 "
                "(3.84, but a gate that can only say no). 3-of-4 is the balance "
                "our ~30 months supports, since the v3 fold geometry yields 4 "
                "folds at a 21-day hold. Registered as MEASURED because the fold "
                "count is a fact about the data; the majority rule on top of it "
                "is the judgement.",
            falsified_by="Two ways, and the first already happened. (1) The value "
                         "moves without the arithmetic moving — v3 set this to 2 "
                         "and the register flagged the drift, which is how the "
                         "loosening was caught. (2) Buy more history: this is a "
                         "measurement OF THE DATA and should rise when the data "
                         "allows. If it does not, something else is binding and we "
                         "have misdiagnosed the constraint. KNOWN DEFECT, measured "
                         "2026-08-18: this is a FIXED floor while the number of "
                         "available folds grows with history, so a null can end up "
                         "with a handful of measurable folds and win a majority of "
                         "that small subset. Simulated false-positive rate rises "
                         "2.9% -> 12.5% between 30 months and 5 years of data. It "
                         "must be made to scale BEFORE any new history is trusted, "
                         "or a data purchase loosens the gate silently.",
            review_trigger="ANY extension of history past 2024-02-26 — this is a "
                           "blocking review, not a periodic one",
            review_by="2026-10-15"),
        Judgement(
            "gate_walkforward_false_positive_pct",
            where="docs/GATE_CALIBRATION_2026-08-18.md; "
                  "scripts/gate_power_audit.py", basis="measured",
            expected=2.9,
            why="Gate v4's walk-forward leg passes pure noise 2.9% of the time on "
                "our 630 sessions, over 4,000 draws. This is the number gate v1's "
                "~50% failure started the whole calibration to find, and no reader "
                "is wired because it is the output of a simulation rather than a "
                "constant — re-run the script to re-measure it.",
            falsified_by="Re-running the audit and getting a materially different "
                         "figure, or — the real test — giving null_audit.py a "
                         "walk-forward leg and finding the REAL belt disagrees with "
                         "this model. A model of the gate's statistics is not a run "
                         "of the gate, and only the second one settles it.",
            review_trigger="null_audit.py gains a walk-forward leg",
            review_by="2026-11-15"),
        Judgement(
            "gate_walkforward_power_at_sharpe_1",
            where="docs/GATE_CALIBRATION_2026-08-18.md", basis="measured",
            expected=22.8,
            why="A genuinely good Sharpe-1.0 strategy clears the walk-forward leg "
                "22.8% of the time on 30 months of history, and 80% power is "
                "unreachable at any Sharpe up to 2.0. An UPPER BOUND: the "
                "synthetic edge never decays. Registered because it bounds what "
                "this fund can learn — at this resolution only strong edges are "
                "confirmable, so hunting modest ones yields NOT TESTABLE rather "
                "than knowledge, and the alpha sleeve's rarity is a measured "
                "property of the instrument rather than a broken pipeline.",
            falsified_by="More history: power rises to 84.7% at Sharpe 1.5 with 10 "
                         "years. If a data purchase does NOT move this, the "
                         "constraint was never history and the diagnosis is wrong. "
                         "Also falsified by any dashboard or report that renders "
                         "NOT TESTABLE as a rejection — at Sharpe 0.6 that is 71% "
                         "of real strategies being described as failures.",
            review_trigger="any extension of history, or a cost-aware re-run",
            review_by="2026-11-15"),
        Judgement(
            "MIN_TRAIN_RETURN_PCT",
            where="app/fund/walkforward.py", basis="judged",
            expected=5.0,
            read=_module("app.fund.walkforward", "MIN_TRAIN_RETURN_PCT"),
            why="Retention is a ratio, and a ratio against a near-zero "
                "denominator is arithmetic noise. Basis stays JUDGED and now "
                "honestly UNDEMONSTRATED: the review below found the written "
                "derivation was false.\n\n"
                "CORRECTED 2026-08-20 (validator, first real-belt execution of "
                "the falsifier below — docs/MIN_TRAIN_RETURN_REVIEW_2026-08-20"
                ".md): the 'motivating +3.66% case' NEVER OCCURRED. The real "
                "sweep (420a94db2621) trained at +10.171% and tested at "
                "+140.219%; the 3.66% was back-solved from the wrong numerator. "
                "No floor of 2, 5, or 10 excludes the real shape, so the "
                "2.0->5.0 derivation is void. On 83 real belt sweeps the floor "
                "has NEVER removed a null fold (0 of 57) and has never changed "
                "a verdict (counterfactual floors 0/2/5/10 identical). The "
                "earlier MEASURED 2026-08-17 claim that this is the fund's "
                "main noise filter (89.6% starvation) was a property of a "
                "driftless, no-grid-max simulation and is FALSE on the belt. "
                "KEPT on the raw scale regardless: it is the only guard against "
                "the one demonstrated real explosion (train +0.03% -> ratio "
                "231) that strict-positive alone would miss — and as of v4.1 "
                "it finally applies to the holdout leg too (gate.py), where "
                "the original bug actually lived.",
            falsified_by="Executed 2026-08-20 — the falsifier as originally "
                         "written ('collect train-leg returns across judged "
                         "folds and plot retention against them') was run on "
                         "83 real sweeps: retention is not unstable below 5% "
                         "(n=0 folds there); it is unstable at train legs of "
                         "10-20%, ABOVE the floor, because the instability is "
                         "the annualised short test leg in the NUMERATOR. "
                         "Next falsifier: a fresh null audit whose generator "
                         "carries market drift and grid-max selection — if its "
                         "nulls still never land under the floor, the floor is "
                         "confirmed inert and survives only as the explosion "
                         "guard.",
            review_trigger="BEFORE gate v5 lands — v5's floor-sweep tables "
                           "must be regenerated with a drifted, grid-max null "
                           "first (blocking finding of the 2026-08-20 review)",
            review_by="2026-10-01"),
        Judgement(
            "min_holdout_retention",
            where="app/fund/gate.py CRITERIA", basis="judged",
            expected=0.5, read=_gate("min_holdout_retention"),
            why="Out of sample a strategy should keep at least half of what it "
                "showed in sample. Half is a round number chosen because it is "
                "round, which is the whole reason it is registered here.",
            falsified_by="Compare the retention of the oracle (perfect foresight) "
                         "against the nulls. If the oracle's own retention sits "
                         "near 0.5, the bar cannot separate foresight from noise "
                         "and is measuring the market's stability, not the rule's.",
            review_trigger="oracle audit re-run under gate v3",
            review_by="2026-09-15"),
        Judgement(
            "min_capacity_usd",
            where="app/fund/gate.py CRITERIA", basis="judged",
            expected=100_000.0, read=_gate("min_capacity_usd"),
            why="A strategy should carry more than the effort of running it. "
                "$100k was picked as a plausible future size, not from this "
                "fund's economics — at NAV ~$2k it is a bet on our own growth.",
            falsified_by="Any strategy rejected on capacity ALONE whose edge "
                         "survives everything else. That is the fund declining a "
                         "real edge on the grounds that it will not scale to a "
                         "size we do not have.",
            review_trigger="first capacity-only rejection",
            review_by="2027-01-01"),
        Judgement(
            "max_avg_correlation",
            where="risk limits", basis="judged", expected=0.75,
            read=_limit("max_avg_correlation"),
            why="A convention, borrowed rather than derived. It is a real "
                "constraint on the book and no measurement here produced it.",
            falsified_by="Measure realised diversification benefit against this "
                         "limit over the coming quarter. If drawdowns are "
                         "unaffected either side of 0.75, it is not the "
                         "load-bearing control we treat it as.",
            review_trigger="one quarter of daily correlation history",
            review_by="2026-12-01"),
        Judgement(
            "min_effective_bets",
            where="risk limits", basis="measured", expected=2.0,
            read=_limit("min_effective_bets"),
            why="Two independent bets is the least that can be called "
                "diversified. It is also what forces a $500 sleeve into at least "
                "two names, so it shapes deployment, not just monitoring. "
                "REVIEWED 2026-08-20 (validator run 8b863152, R6 trigger fired "
                "at 7.75% drawdown; CEO accepted): on the sleeve-only book the "
                "floor is exactly 'DBC/TLT correlation <= -0.209' — it fires "
                "when the hedge stops hedging. LEFT UNCHANGED; basis upgraded "
                "judged -> measured.",
            falsified_by="A book satisfying 2.0 that still loses like a single "
                         "position in a stress episode. Measured 2026-08-20: "
                         "2.47 on 174 sessions (0.23 bets of headroom; the "
                         "earlier 2.93-on-172 justification was stale). Known "
                         "false-positive mode: a low-vol lopsided book (10/90 "
                         "reads 1.84) — fails in the tolerable direction.",
            review_trigger="effective bets within 0.1 of the floor, or the "
                           "sleeve grows past two names (the floor maps onto a "
                           "different correlation statement per book), or the "
                           "first drawdown episode over 3% from peak",
            # The drawdown leg, in machine-checkable form. This is the exact
            # trigger that HAD fired — at 7.75% — while /fund/judgement returned
            # `due_for_review: []` (validator 8b863152). The 3.0 is the number
            # the entry was registered with, not a new one.
            trigger_spec=TriggerSpec(
                "risk_monitor.drawdown_pct", ">", 3.0,
                means="a drawdown episode past 3% from peak is the evidence that "
                      "makes 'is two effective bets actually diversified?' "
                      "answerable rather than theoretical"),
            review_by="2026-12-01"),
        Judgement(
            "max_component_vol_pct",
            where="risk limits", basis="measured", expected=15.0,
            read=_limit("max_component_vol_pct"),
            why="Replaces max_risk_concentration_pct (RETIRED 2026-08-20, CEO-"
                "accepted validator finding: risk shares sum to 100% by Euler, "
                "so the definitive accident — one name, 100.00% — scored BETTER "
                "than the healthy hedged book at 102.49%, and the alarm grew "
                "louder as the hedge improved; no threshold value could "
                "separate healthy from accident). This statistic is the top "
                "name's contribution to annualised NAV volatility: "
                "cardinality-free, monotone in the accident. 15.0 sits between "
                "the healthy hedged sleeve (9.78) and a 90/10 concentration "
                "accident (20.09); single-name reads 22.35, risk parity 4.87. "
                "ADVISORY: no pre-trade check, halt, or throttle reads the "
                "structural limits — stated per the same review; wiring them "
                "into gating would be its own versioned change.",
            falsified_by="A concentration accident this alarm misses, or a "
                         "healthy book it flags: re-run the validator's "
                         "accident table (scratchpad r6b.py method) against "
                         "the then-current book.",
            review_trigger="book gains a third name, or the alarm fires",
            review_by="2026-12-01"),
        Judgement(
            "max_drawdown_pct",
            where="risk limits", basis="mandate", expected=0.1,
            read=_limit("max_drawdown_pct"),
            why="The operator's risk appetite: 'make money without risking more "
                "than we can chew.' Registered to be WATCHED, not tuned. Halts "
                "trading when hit.",
            falsified_by="Nothing measurable — this is a preference, and the only "
                         "legitimate change is the operator stating a different "
                         "one. Listed here so that a quiet loosening is visible "
                         "as drift rather than passing as a technical adjustment.",
            # "The limit is approached" made machine-checkable at the number the
            # entry itself already records: the 2026-08-20 review happened at
            # 77.5% utilisation, so 75% of the limit is the level this fund has
            # in fact treated as "approached". No threshold moves; the mandate
            # limit is untouched and this only decides when to ASK about it.
            trigger_spec=TriggerSpec(
                "risk_monitor.drawdown_utilization_pct", ">=", 75.0,
                means="drawdown has used three quarters of the mandate's "
                      "tolerance — the level at which this entry was last "
                      "reviewed in practice"),
            review_trigger="operator revisits the mandate, or the limit is "
                           "approached (75% of it used). (REVIEWED 2026-08-20 at 77.5% utilised "
                           "after the phantom-price incident: WATCHED, "
                           "UNCHANGED by CEO batch decision — the drawdown is "
                           "an incident artifact, not a mandate change, and "
                           "moving the limit toward the loss would be the "
                           "quiet loosening this entry exists to catch.)",
            review_by="2027-01-01"),
        Judgement(
            "loss_halt_autoresume_cooldown_minutes",
            where="app/fund/riskmonitor.py::LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES",
            basis="judged", expected=30.0,
            read=lambda: _autoresume_cooldown(),
            why="Condition (4) of the loss-halt auto-resume policy (CEO-"
                "approved 2026-08-21, 'approved yes'). Tied to a CADENCE, not "
                "to a round human number: the scheduler strikes NAV every "
                "STRIKE_INTERVAL_SECONDS (default 1800s = 30 min, app/main.py) "
                "while the monitor ticks every ~30s. With no cool-down a "
                "metric oscillating around the daily-loss line could halt and "
                "reopen ~120 times an hour and every cycle pays spread. Thirty "
                "minutes is ONE FULL STRIKE INTERVAL, so at least one FRESH "
                "NAV strike must land between the CEO's acknowledgement and "
                "the reopening — the reopening is corroborated by a new "
                "measurement rather than by the same one that cleared. "
                "Measured FROM THE ACKNOWLEDGEMENT, not from the halt: timing "
                "from the halt would let an acknowledgement arriving 40 "
                "minutes in reopen instantly.",
            falsified_by="A halt that auto-resumes and re-halts on the same "
                         "cause inside one session (too short), or a loss halt "
                         "sitting acknowledged-and-clear for hours while the "
                         "book is fine and the fund is out of the market (too "
                         "long). Both are countable off TradingHalted / "
                         "TradingResumed pairs in the log; neither has happened "
                         "yet, because the policy has never fired.",
            review_trigger="STRIKE_INTERVAL_SECONDS changes — this number's "
                           "entire basis is that it equals one strike interval, "
                           "so it must be re-derived rather than left; or the "
                           "first time the policy actually fires",
            review_by="2026-12-01"),
        Judgement(
            "risk_monitor_is_wired",
            where="app/main.py::_scheduler -> run_risk_monitor_tick",
            basis="measured", expected=True, read=_wired("risk_monitor"),
            why="RiskMonitor.run() is the ONLY code that raises alarms and trips "
                "the -10% drawdown and -4% daily-loss halts. It had ZERO callers: "
                "reachable from an endpoint nothing hit, and from one post-fill "
                "path that swallowed its own exceptions. The framework document "
                "said 'kill switches that will act without asking' - they would "
                "not have acted, because nothing asked them to. Found by outside "
                "review, not by this system.",
            falsified_by="This entry reading False or UNVERIFIED. That is the "
                         "point: the kill switches are only real while the tick "
                         "runs, and an absence of alarms is evidence of calm ONLY "
                         "if something was looking.",
            review_trigger="continuous - checked on every digest",
            review_by="2026-12-31"),
        Judgement(
            "exit_check_is_wired",
            where="app/main.py::_scheduler -> run_exit_check_tick",
            basis="measured", expected=True, read=_wired("exit_check"),
            why="EXIT_RULE_TRIGGERED was emitted by NO code in the repository. "
                "The commitment event, the evaluation and all three event types "
                "existed and nothing joined them, so a fired rule produced "
                "nothing. The $500 sleeve's primary falsification condition - 'an "
                "exit fires and no proposal appears in the queue' - was therefore "
                "guaranteed true before a single order was placed.",
            falsified_by="This entry reading False or UNVERIFIED, or a fired rule "
                         "appearing in the log with no order_id beside it. Either "
                         "means the pre-committed exit is once again a document.",
            review_trigger="continuous - checked on every digest",
            review_by="2026-12-31"),
        Judgement(
            "sleeve_stop_sigma_multiple",
            where="docs/SLEEVE_500_FRAMEWORK.md §1, §5a", basis="judged",
            expected=1.5,
            why="The $500 sleeve's loss stop is set at 1.5x the instrument's "
                "measured 21-day sigma. Chosen so the stop fires roughly 1 time in "
                "7 over the holding window: often enough that the exit machinery "
                "genuinely gets exercised, rarely enough that firing is not the "
                "expected outcome. No reader is wired because the commitment is "
                "deliberately FROZEN as a percent per instrument — a rule quoting "
                "sigma could be relitigated by recomputing sigma, which is the "
                "lever the mechanism exists to remove.",
            falsified_by="Count how often the stop actually fires across sleeves. "
                         "Far above ~15% and 1.5 is inside the noise, so the exits "
                         "are meaningless and we will invent reasons for them. Far "
                         "below and the machinery completes its whole test without "
                         "ever having been exercised — which fails the objective "
                         "while looking like success.",
            review_trigger="4 sleeve cycles completed",
            review_by="2026-11-15"),
        Judgement(
            "sleeve_horizon_days",
            where="docs/SLEEVE_500_FRAMEWORK.md §1", basis="judged",
            expected=21,
            why="21 calendar days to the time exit. Long enough for fills, marks, "
                "TCA and at least two written reviews; short enough that the loop "
                "closes while attention is still on it. It sets the sigma window "
                "in 5a, so the stop distances all descend from this number.",
            falsified_by="If the loop has NOT completed all eight measured steps "
                         "within 21 days, the horizon is too short and the "
                         "conclusion 'the machinery works' would be unsupported. "
                         "If it completes in a week with time idle, it is longer "
                         "than the test needs and delays the next iteration.",
            review_trigger="first sleeve cycle completes",
            review_by="2026-10-01"),
        Judgement(
            "MAX_CONCURRENT_CONTAINERS",
            where="app/fund/leanrunner.py", basis="measured", expected=6,
            read=_module("app.fund.leanrunner", "MAX_CONCURRENT_CONTAINERS"),
            why="RE-REGISTERED 2026-08-20 after the COO's founding triage "
                "caught the register at 1 while the code ran 6 — a quiet "
                "loosening in form, though the reasoning existed: the sizing "
                "rule is slots x per-container cap <= free RAM even if every "
                "container claims its ceiling. 6 slots x 768 MiB = 4.5 GiB "
                "inside ~5 GB free, capturing a measured 3.2-5.3x throughput "
                "gain (leanrunner.py:70-83). The original entry ('one slot is "
                "what the hardware supports') predated the per-container cap; "
                "the lesson kept: the value and its register entry moved "
                "separately, which is exactly what the register exists to "
                "catch — and did.",
            falsified_by="A WinError 1455 (or any host-memory kill) at 6 slots "
                         "with the 768 MiB cap enforced — that would mean the "
                         "sizing rule's 'free RAM' input was wrong. Also "
                         "falsified by the cap being raised without this "
                         "entry moving.",
            review_trigger="machine changes, the per-container cap changes, or "
                           "a vectorised pre-screen lands",
            review_by="2026-12-01"),
        Judgement(
            "WALKFORWARD_HISTORY_FLOOR",
            where="app/fund/factory.py", basis="external",
            expected="2024-02-26",
            read=_module("app.fund.factory", "WALKFORWARD_HISTORY_FLOOR"),
            why="The first bar we hold. Every fold-geometry conclusion rests on "
                "it, including the NOT TESTABLE verdict.",
            falsified_by="Nothing to falsify; it is a fact about the data. It is "
                         "registered because so much is derived from it that it "
                         "must be visible when it changes.",
            review_trigger="any data purchase",
            review_by="2026-10-15"),
    ]


def review(today: Optional[str] = None) -> dict[str, Any]:
    """The register, plus what needs attention and why.

    ``drifted`` leads the summary deliberately. A number that moved without its
    reason moving is worse than a number that is merely due for review: the
    written justification is then describing a decision nobody is making.
    """
    # ONE metric read for the whole register: the source folds the event log,
    # and evaluating seventeen entries against seventeen separate folds is how
    # a register becomes something nobody dares call.
    metrics = _live_metrics()
    entries = [j.to_dict(today, metrics) for j in registry()]
    drifted = [e for e in entries if (e.get("drift") or {}).get("drifted")]
    unreadable = [e for e in entries if not e.get("readable")]
    due = [e for e in entries if e.get("due")]
    triggered = [e for e in entries if e.get("trigger_fired")]
    unchecked = [e for e in entries if e.get("unchecked_triggers")]
    by_basis: dict[str, int] = {}
    for e in entries:
        by_basis[e["basis"]] = by_basis.get(e["basis"], 0) + 1
    return {
        "as_of": today or date.today().isoformat(),
        "count": len(entries),
        "by_basis": by_basis,
        "drifted": drifted,
        "unreadable": unreadable,
        "due_for_review": due,
        # Entries due because a machine-checkable trigger FIRED, split out from
        # the ones merely due by date: the register's first job is to notice
        # evidence, and evidence should not be buried in a calendar.
        "triggered": triggered,
        # Entries carrying a trigger that could NOT be evaluated. An unchecked
        # trigger is not a passing one.
        "triggers_unchecked": unchecked,
        "entries": entries,
        "note": _note(entries, drifted, unreadable, due, by_basis),
    }


def _note(entries: list, drifted: list, unreadable: list, due: list,
          by_basis: dict) -> str:
    bits = [f"{len(entries)} registered decision(s): "
            + ", ".join(f"{n} {b}" for b, n in sorted(by_basis.items()))]
    if drifted:
        bits.append(f"{len(drifted)} DRIFTED from the registered value — the "
                    f"written reason no longer describes the number in force")
    if unreadable:
        bits.append(f"{len(unreadable)} could not be read, so they are UNVERIFIED "
                    f"rather than unchanged")
    if due:
        bits.append(f"{len(due)} past the backstop review date")
    if not (drifted or unreadable or due):
        bits.append("nothing drifted, nothing unreadable, nothing overdue")
    judged = by_basis.get("judged", 0)
    if judged:
        bits.append(f"{judged} of these are JUDGED — chosen, defensible and "
                    f"undemonstrated. They decide verdicts and no measurement "
                    f"supports them yet")
    return "; ".join(bits)
