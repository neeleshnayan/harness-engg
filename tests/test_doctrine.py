"""The doctrine surface must be able to report the fund violating the doctrine.

A page that could only ever say HOLDS would be worse than no page: it would look
like oversight while providing none. So the tests that matter are the ones proving
a GAP and an UNKNOWN can actually surface, and that an unreadable check never
reads as satisfied.
"""

from __future__ import annotations

from app.fund import doctrine, heartbeat
from app.fund.doctrine import GAP, HOLDS, UNKNOWN, Stage, review, stages


def setup_function():
    heartbeat.reset()


def _stage(**kw):
    base = dict(ask="a", why="w", earned_by="e")
    base.update(kw)
    return Stage(99, "t", **base)


def test_a_failing_check_surfaces_as_a_gap():
    s = _stage(check=lambda: {"status": GAP, "detail": "broken"})
    assert s.status()["status"] == GAP
    assert s.status()["basis"] == "measured"


def test_an_unreadable_check_is_unknown_and_never_satisfied():
    def boom():
        raise RuntimeError("store down")

    s = _stage(check=boom)
    got = s.status()
    assert got["status"] == UNKNOWN
    assert got["status"] != HOLDS
    assert "not the same as satisfied" in got["detail"]


def test_an_attested_stage_says_it_is_attested():
    s = _stage(attested=HOLDS, gap="a human said so")
    got = s.status()
    assert got["basis"] == "attested"
    assert got["status"] == HOLDS


def test_a_stage_with_no_status_at_all_is_unknown():
    s = _stage()
    assert s.status()["status"] == UNKNOWN


def test_the_wiring_stage_reads_the_heartbeat_not_the_code():
    """Stage 02's question is 'did it run', not 'does a caller exist'.

    A caller existed for the risk monitor - an endpoint - and nothing hit it.
    """
    from app.fund.doctrine import _check_wiring
    assert _check_wiring()["status"] == UNKNOWN      # nothing has beaten
    heartbeat.beat("risk_monitor")
    heartbeat.beat("exit_check")
    got = _check_wiring()
    assert got["status"] == HOLDS
    assert "ticking" in got["detail"]


def test_the_wiring_stage_reports_a_stopped_control_as_a_gap():
    import time
    for j in ("risk_monitor", "exit_check"):
        heartbeat.beat(j)
    with heartbeat._lock:
        mono, iso, note = heartbeat._beats["exit_check"]
        heartbeat._beats["exit_check"] = (
            mono - heartbeat.BUDGETS_SECONDS["exit_check"] - 60, iso, note)
    from app.fund.doctrine import _check_wiring
    got = _check_wiring()
    assert got["status"] == GAP
    assert "not calm" in got["detail"]


def test_every_gate_version_is_preserved_complete():
    """The stage-07 check, and a guard in its own right.

    `evaluate()` MERGES a supplied criteria dict over the current defaults, so a
    partial historical copy silently inherits today's values and an old verdict
    gets re-read against a bar it never faced. Found live on 2026-08-18:
    CRITERIA_V1 was missing the three walk-forward keys added by v2 and v3.
    """
    from app.fund import gate
    current = set(gate.CRITERIA)
    versions = {n: getattr(gate, n) for n in dir(gate)
                if n.startswith("CRITERIA_V")}
    assert versions, "no prior gate version preserved"
    for name, crit in versions.items():
        assert set(crit) == current, (
            f"{name} is missing {sorted(current - set(crit))} — a v-version must "
            f"describe its bar COMPLETELY, including what it did not ask for")


def test_the_open_change_stage_holds_now_that_v1_is_complete():
    from app.fund.doctrine import _check_open_change
    got = _check_open_change()
    assert got["status"] == HOLDS
    # And it must not overclaim: no code can verify a written reason existed.
    assert "not that each change carried a written reason" in got["detail"]


def test_the_review_names_its_gaps_and_counts_live_readings():
    out = review()
    assert out["canon"] == "docs/FUND_GENESIS.md"
    assert len(out["stages"]) == 7
    assert out["measured_count"] == 3
    # Stage 3 is a real, current gap: the LEAN belt has never produced a v4 FPR.
    assert 3 in out["gaps"]
    assert "GAPS" in out["note"] or "unknown" in out["note"]


def test_the_absence_doctrine_and_invariants_are_carried():
    out = review()
    assert len(out["absence_doctrine"]) >= 8
    rows = {r["this"]: r["is_never"] for r in out["absence_doctrine"]}
    assert rows["Silence"] == "Calm"
    assert rows["Unreadable"] == "Unchanged"
    # The two invariants must travel with the workflow, not live in someone's head.
    joined = " ".join(out["invariants"])
    assert "human clicks" in joined
    assert "does not select securities" in joined


def test_every_stage_carries_the_incident_that_earned_it():
    """A rule with no incident behind it is a preference, and decays like one."""
    for s in stages():
        assert s.earned_by.strip(), f"stage {s.n} has no incident"
        assert s.ask.strip(), f"stage {s.n} has no question to ask"
        assert s.why.strip(), f"stage {s.n} has no rationale"
