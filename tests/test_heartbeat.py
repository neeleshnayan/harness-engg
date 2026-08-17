"""Silence must not read as good news.

The harness could not tell a control that reported nothing from a control that
never ran. The risk monitor had zero callers and its silence was indistinguishable
from a calm book. These tests pin the three-state answer that fixes it: alive,
overdue, and NOT YET OBSERVED — which is neither of the other two.
"""

from __future__ import annotations

from app.fund import heartbeat


def setup_function():
    heartbeat.reset()


def _backdate(name: str, seconds: float) -> None:
    """Pretend a job last beat `seconds` ago.

    Needed because Windows' monotonic clock has ~15ms resolution: beat() followed
    immediately by status() can yield an age of exactly 0.0, so a zero-second
    budget does not reliably trip. Backdating states the intent directly instead of
    depending on clock granularity.
    """
    import time
    heartbeat.beat(name)
    with heartbeat._lock:
        mono, iso, note = heartbeat._beats[name]
        heartbeat._beats[name] = (mono - seconds, iso, note)


def test_a_job_that_never_ran_is_unknown_not_fine_and_not_broken():
    st = heartbeat.status("risk_monitor")
    assert st["ok"] is None, "unobserved must not collapse to True or False"
    assert "not the same as fine" in st["note"]
    assert "not the same as broken" in st["note"] or "may hold the scheduler" in st["note"]


def test_a_recent_beat_is_alive():
    heartbeat.beat("risk_monitor")
    st = heartbeat.status("risk_monitor")
    assert st["ok"] is True
    assert st["age_seconds"] < 5


def test_an_overdue_job_says_its_work_is_unchecked_not_clear():
    _backdate("risk_monitor", heartbeat.BUDGETS_SECONDS["risk_monitor"] + 60)
    st = heartbeat.status("risk_monitor")
    assert st["ok"] is False
    assert "UNCHECKED, not as clear" in st["note"]


def test_a_job_with_no_declared_budget_cannot_be_judged():
    heartbeat.beat("something_nobody_declared")
    st = heartbeat.status("something_nobody_declared")
    assert st["ok"] is None
    assert "no staleness budget" in st["note"]


def test_the_report_leads_with_overdue_jobs():
    for job in heartbeat.BUDGETS_SECONDS:
        heartbeat.beat(job)
    _backdate("exit_check", heartbeat.BUDGETS_SECONDS["exit_check"] + 60)
    r = heartbeat.report()
    assert r["stale"] == ["exit_check"]
    assert "OVERDUE" in r["note"]
    assert "not evidence of calm" in r["note"]


def test_all_alive_says_so_plainly():
    for job in heartbeat.BUDGETS_SECONDS:
        heartbeat.beat(job)
    r = heartbeat.report()
    assert r["stale"] == [] and r["unobserved"] == []
    assert "within budget" in r["note"]


def test_the_two_controls_that_were_unwired_have_declared_budgets():
    """Regression guard on the actual bug.

    If either of these loses its budget entry, `status()` returns ok=None forever
    and the register can never assert the control is running — which is exactly the
    blind spot that let both ship unwired.
    """
    assert "risk_monitor" in heartbeat.BUDGETS_SECONDS
    assert "exit_check" in heartbeat.BUDGETS_SECONDS


def test_the_register_reports_an_unobserved_control_as_unverified():
    """Wiring entries must not claim a control is broken when it is merely unseen.

    Another process may hold the scheduler lease. UNVERIFIED is the honest answer,
    and it is distinct from `drifted`.
    """
    from app.fund.judgement import registry
    entry = next(j for j in registry() if j.key == "risk_monitor_is_wired")
    got = entry.value()
    assert got["readable"] is False
    assert "UNVERIFIED" in got["note"]
    assert entry.drift()["drifted"] is None


def test_the_register_sees_a_wired_control_as_matching_expectation():
    from app.fund.judgement import registry
    heartbeat.beat("risk_monitor")
    entry = next(j for j in registry() if j.key == "risk_monitor_is_wired")
    assert entry.value() == {"value": True, "readable": True}
    assert entry.drift()["drifted"] is False


def test_the_register_flags_a_control_that_stopped():
    """The whole purpose: a control that dies shows up as DRIFT."""
    from app.fund.judgement import registry
    _backdate("exit_check", heartbeat.BUDGETS_SECONDS["exit_check"] + 60)
    entry = next(j for j in registry() if j.key == "exit_check_is_wired")
    assert entry.value()["value"] is False
    assert entry.drift()["drifted"] is True
