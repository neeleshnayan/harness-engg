"""The worker tick that ages out captured candidate analytics.

One tick, two retention policies, deliberately not one schedule: an engine
results DIRECTORY is debug material with a one-day life, while a candidate's
captured evidence is what a deployment decision rested on and keeps for a
quarter.

The property under test is the one that is easy to get wrong: when the candidate
leg cannot run, the tick must SAY so. A prune that silently examined nothing
because Postgres was unavailable looks exactly like a prune with nothing due,
and the difference is whether an operator should go and look.
"""

from app.api.v1 import fund as fund_router


class _FakeLean:
    def prune_results(self):
        return {"removed": 2, "reclaimed_mb": 1.5, "note": "removed 2 dir(s)"}


class _FakeFactory:
    def __init__(self, boom=False):
        self.boom = boom
        self.called = False

    def prune_analytics(self):
        self.called = True
        if self.boom:
            raise RuntimeError("connection refused")
        return {"pruned": ["abc"], "count": 1, "retention_days": 90.0,
                "note": "1 candidate(s) had their captured analytics aged out"}


def test_the_tick_prunes_both_and_keeps_the_engine_leg_intact(monkeypatch):
    f = _FakeFactory()
    monkeypatch.setattr(fund_router, "_lean", lambda: _FakeLean())
    monkeypatch.setattr(fund_router, "_factory", lambda: f)
    out = fund_router.run_results_prune_tick()
    assert out["removed"] == 2 and out["reclaimed_mb"] == 1.5
    assert out["analytics"]["count"] == 1
    assert f.called


def test_an_unavailable_factory_is_reported_not_silently_skipped(monkeypatch):
    """Nothing examined is NOT nothing due."""
    monkeypatch.setattr(fund_router, "_lean", lambda: _FakeLean())
    monkeypatch.setattr(fund_router, "_factory", lambda: None)
    out = fund_router.run_results_prune_tick()
    assert out["removed"] == 2, "the engine leg must still run"
    assert out["analytics"]["count"] == 0
    assert "nothing was examined" in out["analytics"]["note"]


def test_a_failing_prune_never_takes_the_engine_leg_down_with_it(monkeypatch):
    """Losing the mirror of a result is a smaller harm than losing the tick."""
    monkeypatch.setattr(fund_router, "_lean", lambda: _FakeLean())
    monkeypatch.setattr(fund_router, "_factory", lambda: _FakeFactory(boom=True))
    out = fund_router.run_results_prune_tick()
    assert out["removed"] == 2
    assert out["analytics"]["count"] == 0
    assert "RuntimeError" in out["analytics"]["error"]
    assert "nothing was removed" in out["analytics"]["note"]
