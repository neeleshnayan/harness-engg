"""The register has to catch its own failure modes, or it is decoration.

The point of the module is that a threshold cannot quietly stop matching the
reason on file. So the tests that matter most are the ones proving drift is
DETECTED and that an unreadable value is reported as unverified rather than
silently standing in for the old one — the two ways a register lies while looking
healthy.
"""

from __future__ import annotations

import pytest

from app.fund import judgement
from app.fund.judgement import BASES, Judgement, registry, review


def test_basis_must_be_known():
    with pytest.raises(ValueError):
        Judgement("x", where="w", basis="vibes", why="w", falsified_by="f",
                  review_trigger="t", review_by="2026-01-01")


def test_reads_the_live_value_rather_than_the_registered_one():
    j = Judgement("x", where="w", basis="judged", why="w", falsified_by="f",
                  review_trigger="t", review_by="2030-01-01",
                  expected=4, read=lambda: 4)
    assert j.value() == {"value": 4, "readable": True}
    assert j.drift()["drifted"] is False


def test_drift_is_detected_when_the_number_moves_away_from_its_reason():
    """The whole purpose. A knob at 8 with a reason written for 4 is the bug."""
    j = Judgement("DECISIONS_PER_TEST_LEG", where="w", basis="judged", why="w",
                  falsified_by="f", review_trigger="t", review_by="2030-01-01",
                  expected=4, read=lambda: 8)
    d = j.drift()
    assert d["drifted"] is True
    assert d["from"] == 4 and d["to"] == 8
    assert "stale" in d["reason"]


def test_unreadable_reports_unverified_and_never_substitutes_the_old_value():
    """An unreadable knob must not read as an unchanged one.

    Substituting the registered value here would let the register assert current
    knowledge of something it could not see — the exact habit the fund refuses in
    NAV, in holdouts and in coverage.
    """
    def boom():
        raise RuntimeError("store not initialised")

    j = Judgement("x", where="w", basis="judged", why="w", falsified_by="f",
                  review_trigger="t", review_by="2030-01-01",
                  expected=4, read=boom)
    got = j.value()
    assert got["readable"] is False
    assert got["value"] is None          # NOT 4
    assert "UNVERIFIED" in got["note"]
    assert j.drift()["drifted"] is None  # cannot compare, so does not claim to


def test_no_reader_is_declared_rather_than_guessed():
    j = Judgement("x", where="w", basis="judged", why="w", falsified_by="f",
                  review_trigger="t", review_by="2030-01-01")
    assert j.value()["readable"] is False


def test_due_uses_the_backstop_date():
    j = Judgement("x", where="w", basis="judged", why="w", falsified_by="f",
                  review_trigger="t", review_by="2026-09-15", expected=1,
                  read=lambda: 1)
    assert j.due("2026-08-18") is False
    assert j.due("2026-09-15") is True   # inclusive: the day it comes due


def test_every_registered_entry_states_its_own_falsification():
    """A knob with no falsification condition cannot be wrong, only unlucky."""
    for j in registry():
        assert j.falsified_by.strip(), f"{j.key} has no falsification condition"
        assert j.review_trigger.strip(), f"{j.key} has no review trigger"
        assert j.why.strip(), f"{j.key} has no stated reason"
        assert j.where.strip(), f"{j.key} does not say where it lives"
        assert j.basis in BASES


def test_the_judged_ones_are_counted_and_named_as_such():
    """The register exists because some numbers are chosen, not measured.

    If this ever reports zero judged entries, either the fund became remarkable
    or somebody relabelled a preference as a finding.
    """
    out = review("2026-08-18")
    assert out["by_basis"].get("judged", 0) >= 5
    assert "JUDGED" in out["note"]


def test_mandate_entries_are_registered_to_be_watched_not_tuned():
    mandate = [j for j in registry() if j.basis == "mandate"]
    assert mandate, "the risk appetite must be registered, or a quiet loosening " \
                    "of it looks like a technical adjustment"
    for j in mandate:
        assert "operator" in j.falsified_by.lower()


def test_review_leads_with_drift(monkeypatch):
    """Drift outranks overdue in the summary, because it is worse."""
    drifting = Judgement("k", where="w", basis="judged", why="w",
                         falsified_by="f", review_trigger="t",
                         review_by="2030-01-01", expected=1, read=lambda: 99)
    monkeypatch.setattr(judgement, "registry", lambda: [drifting])
    out = review("2026-08-18")
    assert len(out["drifted"]) == 1
    assert "DRIFTED" in out["note"]
    assert out["due_for_review"] == []


def test_limits_are_read_from_the_injected_control_not_dataclass_defaults():
    """The defaults and the limits in force genuinely disagree.

    ``RiskLimits()`` defaults ``max_order_notional_pct`` to 0.25; the fund runs at
    0.15. A register built on the dataclass would agree with the source and
    contradict the running fund.
    """
    class FakeLimits:
        max_avg_correlation = 0.60

    class FakeControl:
        def limits(self):
            return FakeLimits()

    judgement.use_control(FakeControl())
    try:
        entry = next(j for j in registry() if j.key == "max_avg_correlation")
        got = entry.value()
        assert got["readable"] is True
        assert got["value"] == 0.60
        assert entry.drift()["drifted"] is True   # registered 0.75, in force 0.60
    finally:
        judgement.use_control(None)


def test_registry_keys_are_unique():
    keys = [j.key for j in registry()]
    assert len(keys) == len(set(keys))


# --- the guard that outlives the comment -------------------------------------

#: Every limit, and which direction "looser" points. A cap loosens by rising; a
#: floor loosens by falling. Getting this table backwards is the whole bug class,
#: so the direction is stated per key rather than inferred from the name.
_LOOSENS_BY = {
    "max_position_pct": "rising",
    "max_order_notional_pct": "rising",
    "max_strategy_pct": "rising",
    "max_drawdown_pct": "rising",
    "max_daily_loss_pct": "rising",
    "underwater_pct": "rising",
    "max_avg_correlation": "rising",
    "max_strategy_correlation": "rising",
    "max_risk_concentration_pct": "rising",
    "max_component_vol_pct": "rising",
    "max_expected_shortfall_pct": "rising",
    "min_cash_pct": "falling",
    "min_cash_buffer": "falling",
    "min_effective_bets": "falling",
}


def test_no_default_is_looser_than_the_mandate():
    """A missing RISK_LIMITS_SET must never widen a limit.

    `RiskControl._fold()` layers the latest limits event OVER `RiskLimits()`, so
    the defaults govern whenever that event is absent: an empty log, a fresh
    deployment, or a restore from a snapshot predating the limits being set.

    Three defaults were once looser than the running fund — drawdown 0.15 against
    0.10, daily loss 0.05 against 0.04, order cap 0.25 against 0.15 — which meant a
    restore could have widened the drawdown kill switch by half with nobody
    deciding to. The mandate may only move by someone changing it on purpose, so
    the failure direction has to be tighter-than-intended, never looser.
    """
    from app.fund.risk import RiskLimits

    mandate = {
        "max_position_pct": 0.20,
        "max_order_notional_pct": 0.15,
        "max_strategy_pct": 0.40,
        "min_cash_pct": 0.05,
        "max_drawdown_pct": 0.10,
        "max_daily_loss_pct": 0.04,
        "underwater_pct": 0.15,
        "min_effective_bets": 2.0,
        "max_avg_correlation": 0.75,
    }
    defaults = RiskLimits().to_dict()
    for key, in_force in mandate.items():
        got = defaults[key]
        if _LOOSENS_BY[key] == "rising":
            assert got <= in_force, (
                f"{key} defaults to {got}, LOOSER than the mandate's {in_force}. "
                f"An empty or truncated event log would silently run the fund at "
                f"the wider limit")
        else:
            assert got >= in_force, (
                f"{key} defaults to {got}, LOOSER than the mandate's {in_force} "
                f"(it is a floor, so lower is looser)")


def test_every_limit_has_a_declared_loosening_direction():
    """A limit nobody classified cannot be checked by the test above."""
    from app.fund.risk import RiskLimits
    for key in RiskLimits().to_dict():
        assert key in _LOOSENS_BY, (
            f"{key} is a risk limit with no declared loosening direction, so "
            f"test_no_default_is_looser_than_the_mandate silently skips it")
