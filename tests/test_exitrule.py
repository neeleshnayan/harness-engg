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


# --- K2: A DEAD RULE IS NOT COVERAGE -----------------------------------------
#
# Adversary review of builder D11, 2026-08-22, finding K2 — a LOOSENING, and
# the second reason the diff was killed. The coverage block was written to
# reveal unmanaged positions and hid $324.60 of $1,165.44 of them, because
# `covered = {r["symbol"] for r in rules}` counted every rule the fold returns:
# superseded ones, already-triggered ones, overridden ones, and rules belonging
# to a different strategy entirely.
#
# The fixtures below are the LIVE rule set, read from the running spine on
# 2026-08-22 (GET /fund/exits), not invented shapes. Verbatim from that
# reading:
#   GLD  machinery-test loss_pct 25.0  triggered_at 2026-08-20T08:01:26.478554
#                                      overridden_at 2026-08-20T11:00:13.746913
#   INTC machinery-test gain_pct 1.0   overridden_at 2026-08-17T17:03:56.137610
#   INTC wiring_verification_2026_08_18 gain_pct 0.5  superseded True
# and the quantities are the broker's own, from the reconciliation plan.

def _triggered(**p):
    from app.fund.events import EventType
    return E(EventType.EXIT_RULE_TRIGGERED.value, p)


def _overridden(**p):
    from app.fund.events import EventType
    return E(EventType.EXIT_RULE_OVERRIDDEN.value, p)


def test_an_already_triggered_rule_is_not_coverage():
    """THE ADVERSARY'S DEMONSTRATION, reproduced.

    GLD's machinery-test loss_pct fired on 2026-08-20 at 08:01:26 — on the
    phantom mark, in the incident that cost the fund $128.26. It will never
    fire again: `enforce()` skips a rule carrying `triggered_at`. Under v1 it
    made $179.70 of GLD read as covered.
    """
    store = FakeStore([
        _set(strategy_id="machinery-test", symbol="GLD", kind="loss_pct",
             threshold_pct=25.0, note="far away"),
        _triggered(strategy_id="machinery-test", symbol="GLD", kind="loss_pct",
                   at="2026-08-20T08:01:26.478554+00:00",
                   order_id="2ec1ec3f-ddda-48ac-8511-9c19fb87d59b"),
    ])
    out = ExitRules(store).check(
        [{"symbol": "GLD", "unrealized_pnl_pct": -1.0, "value_usd": 179.70}])
    assert [u["symbol"] for u in out["uncovered"]] == ["GLD"], out["note"]
    assert out["uncovered_usd"] == 179.70
    assert "already triggered" in out["uncovered"][0]["why"]
    assert out["rules_not_live"] and \
        out["rules_not_live"][0]["symbol"] == "GLD"


def test_an_overridden_rule_is_not_coverage():
    """An override is a decision NOT to enforce. Counting it as enforcement
    inverts the meaning of the record."""
    store = FakeStore([
        _set(strategy_id="machinery-test", symbol="INTC", kind="gain_pct",
             threshold_pct=1.0, note="proves the loop"),
        _overridden(strategy_id="machinery-test", symbol="INTC",
                    kind="gain_pct", at="2026-08-17T17:03:56.137610+00:00",
                    reason="machinery test, not a real position"),
    ])
    out = ExitRules(store).check(
        [{"symbol": "INTC", "unrealized_pnl_pct": 0.2, "value_usd": 144.90}])
    assert [u["symbol"] for u in out["uncovered"]] == ["INTC"]
    assert "overridden" in out["uncovered"][0]["why"]


def test_a_superseded_rule_is_not_coverage():
    """The superseded copy stays in the log — that is the point — but the
    revision governs, and if the revision is also dead nothing covers this."""
    store = FakeStore([
        _set(strategy_id="wiring_verification_2026_08_18", symbol="INTC",
             kind="gain_pct", threshold_pct=0.5),
        _set(strategy_id="wiring_verification_2026_08_18", symbol="INTC",
             kind="gain_pct", threshold_pct=0.5, note="re-commitment"),
        _overridden(strategy_id="wiring_verification_2026_08_18", symbol="INTC",
                    kind="gain_pct", at="2026-08-19T00:00:00+00:00",
                    reason="test artifact"),
    ])
    out = ExitRules(store).check(
        [{"symbol": "INTC", "unrealized_pnl_pct": 0.2, "value_usd": 144.90}])
    assert [u["symbol"] for u in out["uncovered"]] == ["INTC"]


def test_a_rule_on_another_strategy_does_not_cover_this_holding():
    """SPY $166.74, the third hidden position.

    An exit rule is a commitment BY a strategy ABOUT a symbol: `enforce()`
    raises the closing SELL under the rule's own strategy_id, and autopolicy v3
    will only auto-approve it if THAT strategy holds the quantity being sold.
    A rule on sleeve_premia_equity therefore cannot be executed against a
    holding that sits in `discretionary`, and scoring it as coverage is the
    same absence-as-value error in a different costume.
    """
    store = FakeStore([
        _set(strategy_id="sleeve_premia_equity", symbol="SPY",
             kind="loss_pct", threshold_pct=6.0),
    ])
    out = ExitRules(store).check(
        [{"symbol": "SPY", "unrealized_pnl_pct": 0.4}],
        holdings=[{"strategy_id": "discretionary", "symbol": "SPY",
                   "qty": 0.217757, "usd_value": 166.74}])
    assert [u["symbol"] for u in out["uncovered"]] == ["SPY"]
    assert out["coverage_basis"] == "strategy+symbol"
    assert "sleeve_premia_equity" in out["uncovered"][0]["why"]
    assert out["uncovered_usd"] == 166.74


def test_the_owning_strategy_IS_covered_by_its_own_live_rule():
    """The other direction, so the fix cannot pass by calling everything
    uncovered. A live rule on the strategy that actually holds the position is
    coverage, and must not be reported as a gap."""
    store = FakeStore([
        _set(strategy_id="sleeve_premia_equity", symbol="SPY",
             kind="loss_pct", threshold_pct=6.0),
    ])
    out = ExitRules(store).check(
        [{"symbol": "SPY", "unrealized_pnl_pct": 0.4}],
        holdings=[{"strategy_id": "sleeve_premia_equity", "symbol": "SPY",
                   "qty": 0.346119, "usd_value": 264.97}])
    assert out["uncovered"] == []
    assert out["uncovered_usd"] is None


def test_the_full_reconciled_book_reports_every_dollar_it_should():
    """THE HEADLINE NUMBER: $674.10 reported vs $1,165.44 actual.

    The whole post-reconciliation book, with the three dead/misowned rules the
    adversary found. If any of the three repairs regresses, this total falls
    back toward $674.10 and the test says by how much.
    """
    store = FakeStore([
        # dead: triggered
        _set(strategy_id="machinery-test", symbol="GLD", kind="loss_pct",
             threshold_pct=25.0),
        _triggered(strategy_id="machinery-test", symbol="GLD",
                   kind="loss_pct", at="2026-08-20T08:01:26+00:00"),
        # dead: overridden
        _set(strategy_id="machinery-test", symbol="INTC", kind="gain_pct",
             threshold_pct=1.0),
        _overridden(strategy_id="machinery-test", symbol="INTC",
                    kind="gain_pct", at="2026-08-17T17:03:56+00:00",
                    reason="machinery test"),
        # live, but on a strategy that no longer holds SPY
        _set(strategy_id="sleeve_premia_equity", symbol="SPY",
             kind="loss_pct", threshold_pct=6.0),
    ])
    book = [
        ("discretionary", "SPY", 0.217757, 166.74),
        ("discretionary", "GLD", 0.424471, 179.70),
        ("discretionary", "INTC", 1.608762, 144.90),
        ("discretionary", "MSFT", 0.340051, 174.30),
        ("discretionary", "NVDA", 0.749886, 133.80),
        ("discretionary", "SOFI", 9.188190, 209.40),
        ("discretionary", "XLE", 2.749912, 156.60),
    ]
    out = ExitRules(store).check(
        [{"symbol": s, "unrealized_pnl_pct": 0.0} for _, s, _, _ in book],
        holdings=[{"strategy_id": sid, "symbol": s, "qty": q, "usd_value": v}
                  for sid, s, q, v in book])
    assert sorted(u["symbol"] for u in out["uncovered"]) == \
        ["GLD", "INTC", "MSFT", "NVDA", "SOFI", "SPY", "XLE"]
    assert out["uncovered_usd"] == 1165.44
    assert out["uncovered_unvalued"] == []
    assert "$1,165.44" in out["note"]
    # The rules that stopped counting are NAMED, not silently dropped: a reader
    # comparing this against last week's coverage needs to know the number
    # moved because the rules were never controls.
    assert len(out["rules_not_live"]) == 2


def test_an_unvalued_holding_is_counted_separately_never_as_zero():
    """Absence is never zero, applied to the money column. A holding the
    pricer could not value must not silently improve the uncovered total."""
    out = ExitRules(FakeStore([])).check(
        [{"symbol": "AAA", "unrealized_pnl_pct": 0.0}],
        holdings=[{"strategy_id": "d", "symbol": "AAA", "qty": 1,
                   "usd_value": 100.0},
                  {"strategy_id": "d", "symbol": "BBB", "qty": 1}])
    assert out["uncovered_usd"] == 100.0
    assert out["uncovered_unvalued"] == ["BBB"]
    assert "no readable value" in out["note"]


def test_the_risk_monitors_own_key_name_is_read():
    """RiskMonitor.assess() emits `value_usd`; venuesync emits `usd_value`.

    v1 read only `usd_value`, so on the LIVE path every uncovered row carried a
    null dollar figure and the block could not be ranked by money. Verified
    against the running spine 2026-08-22: the monitor's rows are exactly
    symbol / qty / mark / value_usd / weight_pct / unrealized_pnl_pct /
    shock_20_usd.
    """
    out = ExitRules(FakeStore([])).check(
        [{"symbol": "AAA", "qty": 2.0, "mark": 50.0, "value_usd": 100.0,
          "weight_pct": 5.0, "unrealized_pnl_pct": 0.0, "shock_20_usd": -20.0}])
    assert out["uncovered"][0]["usd_value"] == 100.0
    assert out["uncovered_usd"] == 100.0


def test_symbol_level_coverage_says_that_is_what_it_measured():
    """The weaker question, answered honestly.

    The monitor's rows name no owner. Falling back to symbol level is fine;
    doing it silently is the K2 defect in miniature, so the basis is reported.
    """
    out = ExitRules(FakeStore([
        _set(strategy_id="whoever", symbol="AAA", kind="loss_pct",
             threshold_pct=5),
    ])).check([{"symbol": "AAA", "unrealized_pnl_pct": 0.0}])
    assert out["uncovered"] == []
    assert out["coverage_basis"] == "symbol"
