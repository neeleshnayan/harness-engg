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
                 expected: Any = None):
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

    def due(self, today: Optional[str] = None) -> bool:
        now = today or date.today().isoformat()
        return now >= self.review_by

    def to_dict(self, today: Optional[str] = None) -> dict[str, Any]:
        return {
            "key": self.key, "where": self.where, "basis": self.basis,
            "why": self.why, "falsified_by": self.falsified_by,
            "review_trigger": self.review_trigger, "review_by": self.review_by,
            "registered_value": self.expected,
            **self.value(), "drift": self.drift(), "due": self.due(today),
        }


def _gate(key: str) -> Callable[[], Any]:
    def read() -> Any:
        from app.fund.gate import CRITERIA
        return CRITERIA[key]
    return read


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


def registry() -> list[Judgement]:
    """Every number we chose, with the terms on which it can be overturned.

    Ordered by how much damage a wrong value does, not alphabetically. The first
    four decide whether a strategy is ever deployed at all.
    """
    return [
        Judgement(
            "DECISIONS_PER_TEST_LEG",
            where="app/fund/walkforward.py",
            basis="judged", expected=4,
            read=_module("app.fund.walkforward", "DECISIONS_PER_TEST_LEG"),
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
            expected=2, read=_gate("min_walkforward_folds"),
            why="Not a preference. Two is what ~30 months of history can supply "
                "for a 21-day hold once a test leg is sized from the strategy's "
                "own clock. v2 asked for 3, which nothing but a fast rule could "
                "ever satisfy — an unsatisfiable criterion fails everything while "
                "looking like rigour.",
            falsified_by="Buy more history. This number is a measurement OF THE "
                         "DATA, so it should rise the moment the data allows, and "
                         "if it does not rise then something else is binding and "
                         "we have misdiagnosed the constraint.",
            review_trigger="history extended beyond 2024-02-26",
            review_by="2026-10-15"),
        Judgement(
            "MIN_TRAIN_RETURN_PCT",
            where="app/fund/walkforward.py", basis="judged",
            expected=5.0,
            read=_module("app.fund.walkforward", "MIN_TRAIN_RETURN_PCT"),
            why="Retention is a ratio, and a ratio against a near-zero "
                "denominator is arithmetic noise. Set to 2.0 first, then raised "
                "to 5.0 after noticing 2.0 did not exclude the 3.66% case that "
                "motivated it. Raised on principle, not on evidence.",
            falsified_by="Collect the train-leg returns of every fold judged so "
                         "far and plot retention against them. If retention is "
                         "stable well below 5%, the floor is discarding usable "
                         "folds. If it explodes above 5%, the floor is too low.",
            review_trigger="30 folds measured with train returns recorded",
            review_by="2026-11-01"),
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
            where="risk limits", basis="judged", expected=2.0,
            read=_limit("min_effective_bets"),
            why="Two independent bets is the least that can be called "
                "diversified. It is also what forces a $500 sleeve into at least "
                "two names, so it shapes deployment, not just monitoring.",
            falsified_by="A book satisfying 2.0 that still loses like a single "
                         "position in a stress episode. Measured now: 2.93 on 172 "
                         "sessions, so the limit is not currently binding and has "
                         "therefore never been tested.",
            review_trigger="first drawdown episode over 3% from peak",
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
            review_trigger="operator revisits the mandate, or the limit is "
                           "approached (currently 3.3% utilised)",
            review_by="2027-01-01"),
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
            where="app/fund/leanrunner.py", basis="external", expected=1,
            read=_module("app.fund.leanrunner", "MAX_CONCURRENT_CONTAINERS"),
            why="Not a choice. Stacked LEAN containers died with WinError 1455 "
                "on a 15.2 GB machine. One slot is what the hardware supports.",
            falsified_by="More RAM. This is the ceiling that makes population "
                         "search infeasible — ~1,000 candidates is ~230 hours "
                         "here — so it bounds the design space, not just the "
                         "schedule.",
            review_trigger="machine changes, or a vectorised pre-screen lands",
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
    entries = [j.to_dict(today) for j in registry()]
    drifted = [e for e in entries if (e.get("drift") or {}).get("drifted")]
    unreadable = [e for e in entries if not e.get("readable")]
    due = [e for e in entries if e.get("due")]
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
