"""Pre-committed exits: a rule you cannot quietly revise or silently ignore.

The property under test throughout: an exit must be evaluable, and the three
states — fired, holding, and could-not-check — must never collapse into each
other. "Could not check" reading as "fine" is how a missing mark becomes a
position in good standing, and every other part of this system refuses that.
"""

from datetime import datetime, timezone

import pytest

from app.fund.exitrule import ExitRuleError, ExitRules, build, evaluate


def test_a_rule_that_cannot_be_checked_is_refused_at_creation():
    """A rule that sounds like a commitment but cannot be evaluated is worse than
    none: it produces the feeling of discipline without the mechanism, and gets
    cited later as though it had been enforced."""
    with pytest.raises(ExitRuleError, match="threshold_pct"):
        build("s1", "loss_pct")
    with pytest.raises(ExitRuleError, match="on_date"):
        build("s1", "time")
    with pytest.raises(ExitRuleError, match="not a rule"):
        build("s1", "thesis")
    with pytest.raises(ExitRuleError, match="one of"):
        build("s1", "vibes", threshold_pct=10)


def test_a_signed_threshold_is_refused_because_it_reads_both_ways():
    """"loss_pct: -10" and "loss_pct: 10" would both look plausible and mean
    opposite things. The direction belongs to the kind, not the number."""
    with pytest.raises(ExitRuleError, match="magnitude"):
        build("s1", "loss_pct", threshold_pct=-10)


def test_a_loss_exit_fires_at_its_threshold_and_says_why():
    r = build("s1", "loss_pct", threshold_pct=10, symbol="ABC")
    assert evaluate(r, unrealised_pnl_pct=-9.9)["fired"] is False
    got = evaluate(r, unrealised_pnl_pct=-10.4)
    assert got["fired"] is True
    assert "past the 10.00% loss exit" in got["reason"]


def test_a_missing_mark_is_could_not_check_not_holding():
    """False means "checked, condition does not hold". None means "could not
    check". Collapsing them lets an unmarked position read as fine."""
    r = build("s1", "loss_pct", threshold_pct=10, symbol="ABC")
    got = evaluate(r, unrealised_pnl_pct=None)
    assert got["fired"] is None
    assert "could not be checked" in got["reason"]


def test_a_time_exit_fires_on_its_date():
    r = build("s1", "time", on_date="2026-09-01")
    assert evaluate(r, today="2026-08-31")["fired"] is False
    assert evaluate(r, today="2026-09-01")["fired"] is True


def test_a_thesis_exit_never_fires_by_itself():
    """A machine claiming to have detected a broken thesis would be inventing the
    hardest part of the judgement. What it can do is put the written condition in
    front of the operator so it gets answered rather than forgotten."""
    r = build("s1", "thesis", note="margins stop compressing")
    got = evaluate(r)
    assert got["fired"] is None
    assert "a human must answer this" in got["reason"]
    assert "margins stop compressing" in got["reason"]


class FakeStore:
    def __init__(self, events):
        self._events = events

    def stream(self, since_seq=0, limit=None):
        return self._events


def E(t, payload):
    """The store yields DICTS. An earlier version of this fake yielded objects,
    so every test here passed while production folded nothing at all — the fake
    was wrong, not the code it was testing. Matching the real contract is the
    whole value of a fake."""
    return {"type": t, "payload": payload}


def _set(**p):
    from app.fund.events import EventType
    return E(EventType.EXIT_RULE_SET.value, p)


def test_rules_fold_from_the_log_and_a_later_one_supersedes():
    """The old commitment stays in the log — that is the point — but only the
    current one governs, and the revision is readable."""
    rules = ExitRules(FakeStore([
        _set(strategy_id="s1", symbol="ABC", kind="loss_pct", threshold_pct=10),
        _set(strategy_id="s1", symbol="ABC", kind="loss_pct", threshold_pct=20),
    ])).active("s1")
    assert len(rules) == 1
    assert rules[0]["threshold_pct"] == 20
    assert rules[0]["superseded"] is True, "a revision must be visible as one"


def test_an_override_is_recorded_against_the_rule():
    """Overrides are allowed. Silent overrides are not — an exit that can be
    ignored without a trace is not an exit."""
    from app.fund.events import EventType
    rules = ExitRules(FakeStore([
        _set(strategy_id="s1", symbol="ABC", kind="loss_pct", threshold_pct=10),
        E(EventType.EXIT_RULE_OVERRIDDEN.value,
          {"strategy_id": "s1", "symbol": "ABC", "kind": "loss_pct",
           "at": "2026-08-17", "reason": "earnings in two days"}),
    ])).active("s1")
    assert rules[0]["override_reason"] == "earnings in two days"


def test_check_separates_fired_from_holding_from_unevaluable():
    rules = ExitRules(FakeStore([
        _set(strategy_id="s1", symbol="DOWN", kind="loss_pct", threshold_pct=5),
        _set(strategy_id="s1", symbol="FINE", kind="loss_pct", threshold_pct=5),
        _set(strategy_id="s1", symbol="GONE", kind="loss_pct", threshold_pct=5),
    ]))
    out = rules.check([
        {"symbol": "DOWN", "unrealized_pnl_pct": -8.0},
        {"symbol": "FINE", "unrealized_pnl_pct": -1.0},
        # GONE has no mark at all.
    ], strategy_id="s1")
    assert [r["symbol"] for r in out["fired"]] == ["DOWN"]
    assert [r["symbol"] for r in out["holding"]] == ["FINE"]
    assert [r["symbol"] for r in out["unevaluable"]] == ["GONE"]
    assert "not the same as fine" in out["note"]


def test_no_rule_at_all_is_stated_rather_than_passing_quietly():
    """A position deployed without a pre-committed exit is exactly the state this
    module exists to make visible."""
    out = ExitRules(FakeStore([])).check([{"symbol": "ABC",
                                           "unrealized_pnl_pct": -30.0}])
    assert out["fired"] == []
    assert "deployed without a pre-committed exit" in out["note"]
