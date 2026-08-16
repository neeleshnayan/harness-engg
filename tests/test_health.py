"""Operational health — the question the fund could not previously ask.

Every test here encodes a real outage from this month. The unifying property:
the service was UP through all of them, so a liveness ping would have returned
200 while the fund was unusable.
"""

import pytest

from app.fund import health


class _Snap:
    total_nav_usd = 2026.86
    positions = [{"symbol": "SPY"}]


class _Nav:
    def __init__(self, delay=0.0, boom=False):
        self._delay, self._boom = delay, boom

    def compute(self):
        import time
        time.sleep(self._delay)
        if self._boom:
            raise RuntimeError("projection exploded")
        return _Snap()


def test_a_check_that_raises_is_a_failed_check_not_a_failed_request():
    """A health endpoint that 500s tells the operator only that the health
    endpoint is broken."""
    out = health._timed("nav", lambda: health.check_nav(_Nav(boom=True)))
    assert out["ok"] is False
    assert "projection exploded" in out["error"]
    assert out["latency_ms"] >= 0


def test_a_slow_dependency_fails_even_though_it_answers():
    """THE case. NAV answered correctly and took sixty seconds; Clark's tools
    time out at twenty, so the fund was unreachable to its own assistant while
    every component reported healthy."""
    health.BUDGETS_MS["nav"] = 50.0
    try:
        out = health._timed("nav", lambda: health.check_nav(_Nav(delay=0.2)))
        assert out["over_budget"] is True
        assert out["ok"] is False
        assert "too slowly to be useful" in out["note"]
    finally:
        health.BUDGETS_MS["nav"] = 10_000.0


def test_a_fast_healthy_dependency_passes():
    out = health._timed("nav", lambda: health.check_nav(_Nav()))
    assert out["ok"] is True
    assert out["over_budget"] is False
    assert out["nav_usd"] == pytest.approx(2026.86)


def test_a_broken_chain_fails_the_check(monkeypatch):
    """A hash-chain break is not a slow day and must never read as degraded."""
    class _Store:
        def verify_chain(self):
            return {"ok": False, "checked": 10, "chained": 9,
                    "first_break": {"seq": 5}}
    monkeypatch.setattr("app.fund.events.EventStore", lambda *a, **k: _Store())
    out = health._timed("chain", health.check_chain)
    assert out["ok"] is False
    assert out["first_break"]["seq"] == 5


def test_an_unwired_dependency_reports_skipped_rather_than_healthy():
    """Absent evidence must not read as satisfied evidence."""
    out = health._timed("venue", lambda: health.check_venue(None))
    assert out["ok"] is False
    assert out["skipped"]


def test_down_and_degraded_are_different_states(monkeypatch):
    """A fund whose venue is unreachable can still value its book; one whose
    event store is gone can do nothing. Collapsing both into 'unhealthy' means
    the word teaches an operator nothing."""
    monkeypatch.setattr(health, "check_event_store", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_chain", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_market_data", lambda symbol="SPY": {"ok": True})
    monkeypatch.setattr(health, "check_lean_engine", lambda runner=None: {"ok": True})

    degraded = health.report(nav_service=_Nav(), connector=None)
    assert degraded["status"] == "degraded"
    assert "venue" in degraded["failed"]
    assert "still" in degraded["summary"]

    monkeypatch.setattr(health, "check_event_store",
                        lambda: (_ for _ in ()).throw(RuntimeError("no db")))
    down = health.report(nav_service=_Nav(), connector=None)
    assert down["status"] == "down"
    assert "event_store" in down["summary"]


def test_a_fully_healthy_system_says_so(monkeypatch):
    for name, fn in (("check_event_store", lambda: {"ok": True}),
                     ("check_chain", lambda: {"ok": True}),
                     ("check_market_data", lambda symbol="SPY": {"ok": True}),
                     ("check_lean_engine", lambda runner=None: {"ok": True}),
                     ("check_venue", lambda connector=None: {"ok": True})):
        monkeypatch.setattr(health, name, fn)
    out = health.report(nav_service=_Nav())
    assert out["status"] == "ok"
    assert out["failed"] == [] and out["slow"] == []
