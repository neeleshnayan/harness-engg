"""Unit tests for SentinelRadar autonomous alpha scanner."""

from app.fund.sentinel import SentinelRadar


class FakeThesisService:
    def propose_thesis(self, **kwargs):
        return {"thesis_id": kwargs.get("thesis_id"), "status": "draft"}


class FakeMemoService:
    def create_memo(self, **kwargs):
        return {"memo_id": kwargs.get("memo_id"), "status": "created"}


def test_sentinel_scan_and_auto_draft():
    radar = SentinelRadar(thesis_service=FakeThesisService(), memo_service=FakeMemoService())
    res = radar.scan()

    assert res["status"] == "completed"
    assert res["total_signals_scanned"] >= 3
    assert len(res["newly_drafted_theses"]) >= 3

    for sig in res["signals"]:
        assert sig["conviction_score"] >= 85.0
        assert sig["thesis_id"] is not None
        assert sig["memo_id"] is not None
