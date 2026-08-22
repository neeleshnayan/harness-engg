"""The mode switch as a CONTROL — the endpoint, not the module.

`tests/test_fund_mode.py` pins the MODE. This file pins the SWITCH, which is
where the guards actually live and where a control most often turns out to have
no callers.

Every test names the refusal it guards:

  * the CEO's click, on the same channel as an order approval;
  * nothing in flight, because an order proposed against one venue and resolved
    against another is the phantom-fill shape with a switch on the front;
  * an UNREADABLE queue is not an empty one;
  * alpaca-prod refused with its whole gate attached;
  * the fill stream stopped before the store moves — TradeStream captures the
    pipeline it was built with, so a stream started in alpaca-paper would go on
    writing Alpaca fills into the store the fund just left.
"""

from __future__ import annotations

import pytest

from app.api.v1 import fund as fund_router
from app.fund import mode as fundmode
from app.fund.events import EventType


class MemStore:
    def __init__(self):
        self.appended = []

    def append(self, ev):
        self.appended.append(ev)
        return ev

    def stream(self, since_seq=0, limit=200):
        return []

    def by_aggregate(self, aggregate_id):
        return []

    @staticmethod
    def invalidate_cache():
        return None


class FakeOrders:
    def __init__(self, pending=(), in_flight=(), boom=False):
        self._p, self._f, self.boom = list(pending), list(in_flight), boom

    def pending(self):
        if self.boom:
            raise ConnectionError("postgres unreachable")
        return list(self._p)

    def in_flight(self):
        if self.boom:
            raise ConnectionError("postgres unreachable")
        return list(self._f)


class FakeRiskEngine:
    def invalidate(self):
        return None


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """The router pointed at fakes, in alpaca-paper, with a scratch mode file."""
    store = MemStore()
    monkeypatch.setattr(fund_router, "_store", store)
    monkeypatch.setattr(fund_router, "_orders", FakeOrders())
    monkeypatch.setattr(fund_router, "_riskengine", FakeRiskEngine())
    monkeypatch.setattr(fund_router, "_mode_spec",
                        fundmode.MODES[fundmode.FundMode.ALPACA_PAPER])
    monkeypatch.setenv("FUND_MODE_FILE", str(tmp_path / ".fund_mode"))
    # _wire is the expensive, real thing; the switch's OWN behaviour is what is
    # under test, so it is replaced by a recorder.
    wired_to = []
    monkeypatch.setattr(fund_router, "_wire",
                        lambda spec: (wired_to.append(spec.mode.value), spec)[1])
    return {"store": store, "wired_to": wired_to, "tmp": tmp_path}


def _req(**over):
    body = {"mode": "test", "approver": "neelesh", "confirm": "test",
            "reason": "CEO instruction 2026-08-21"}
    body.update(over)
    return fund_router.ModeSwitchRequest(**body)


class TestTheApprovalChannel:
    def test_an_unlisted_approver_is_refused_and_RECORDED(self, wired):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(_req(approver="agent"))
        assert e.value.status_code == 403
        # A refused switch is a FINDING, not silence — same as a refused
        # approval.
        kinds = [ev.type for ev in wired["store"].appended]
        assert EventType.APPROVAL_REFUSED in kinds
        assert wired["wired_to"] == []

    def test_a_missing_echo_is_refused(self, wired):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(_req(confirm=None))
        assert e.value.status_code == 403
        assert "confirm echo" in str(e.value.detail)

    def test_a_wrong_echo_is_refused(self, wired):
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            fund_router.switch_fund_mode(_req(confirm="alpaca-p"))

    def test_a_via_chair_approval_must_quote_the_instruction(self, wired):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(_req(approver="neelesh-via-co-cto"))
        assert "verbatim" in str(e.value.detail)


class TestNothingMayBeInFlight:
    def test_a_pending_order_blocks_the_switch(self, wired, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(fund_router, "_orders",
                            FakeOrders(pending=[{"order_id": "o1"}]))
        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(_req())
        assert e.value.status_code == 409
        assert e.value.detail["orders"][0]["order_id"] == "o1"
        assert wired["wired_to"] == []

    def test_an_in_flight_order_blocks_the_switch(self, wired, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(fund_router, "_orders",
                            FakeOrders(in_flight=[{"order_id": "o2"}]))
        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(_req())
        assert e.value.detail["orders"][0]["state"] == "in_flight"

    def test_an_UNREADABLE_queue_is_not_an_empty_one(self, wired, monkeypatch):
        """The single most dangerous confusion on this path. An exception
        reading the queue must never mean 'nothing pending'."""
        from fastapi import HTTPException

        monkeypatch.setattr(fund_router, "_orders", FakeOrders(boom=True))
        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(_req())
        assert e.value.status_code == 503
        assert "unreadable is not unchanged" in str(e.value.detail)
        assert wired["wired_to"] == []


class TestProdIsRefusedWithItsGateAttached:
    def test_selecting_prod_is_refused(self, wired):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(
                _req(mode="alpaca-prod", confirm="alpaca-p"))
        assert e.value.status_code == 403
        assert e.value.detail["prod_gate"]["reachable"] is False
        assert e.value.detail["prod_gate"]["n_blocking"] == 5
        assert wired["wired_to"] == []


class TestTheHappyPathIsFullyRecorded:
    def test_both_legs_are_appended_and_the_choice_is_durable(self, wired):
        out = fund_router.switch_fund_mode(_req())
        assert out["switched"] is True
        assert out["from"] == "alpaca-paper" and out["to"] == "test"
        assert wired["wired_to"] == ["test"]

        legs = [ev.payload["leg"] for ev in wired["store"].appended
                if ev.type is EventType.FUND_MODE_SWITCHED]
        # The store being LEFT records the departure; the store being ENTERED
        # records the arrival. Neither log gets a silent gap.
        assert legs == ["departure", "arrival"]

        ev = wired["store"].appended[0]
        assert ev.payload["from_ledger"] == "krypton_fund"
        assert ev.payload["to_ledger"] == "krypton_fund_test"
        assert ev.payload["approver"] == "neelesh"
        assert ev.payload["reason"] == "CEO instruction 2026-08-21"

        # Durable: a restart must not quietly revert a deliberate switch.
        assert out["persisted"]["mode"] == "test"
        assert out["persisted"]["set_by"] == "neelesh"
        record = fundmode.read_mode_file({"FUND_MODE_FILE": str(wired["tmp"] / ".fund_mode")})
        assert record["mode"] == "test"

    def test_switching_to_the_current_mode_is_a_no_op(self, wired):
        out = fund_router.switch_fund_mode(
            _req(mode="alpaca-paper", confirm="alpaca-p"))
        assert out["switched"] is False
        assert wired["store"].appended == []

    def test_an_unknown_mode_is_422_not_a_guess(self, wired):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            fund_router.switch_fund_mode(_req(mode="paper", confirm="paper"))
        assert e.value.status_code == 422


class TestTheFillStreamStopsBeforeTheStoreMoves:
    def test_a_live_stream_is_stopped_and_said_so(self, wired, monkeypatch):
        """TradeStream captures the pipeline it was constructed with. Left
        running across a switch it would hold the OLD connector and the OLD
        store, and go on writing Alpaca fills into the ledger the fund just
        left — two books in one process, arriving through the one object that
        does not go through _wire."""
        stopped = []

        class FakeStream:
            def stop(self):
                stopped.append(True)

            def state(self):
                return {"enabled": True}

        monkeypatch.setattr(fund_router, "_trade_stream", FakeStream())
        out = fund_router.switch_fund_mode(_req())
        assert stopped == [True]
        assert "stopped" in out["fill_stream"]
        # And the handle is dropped, so nothing reports a socket that was told
        # to stop as though it were listening.
        assert fund_router._trade_stream is None

    def test_no_stream_says_so_rather_than_implying_one_was_stopped(self, wired,
                                                                    monkeypatch):
        monkeypatch.setattr(fund_router, "_trade_stream", None)
        out = fund_router.switch_fund_mode(_req())
        assert out["fill_stream"] == "was not running"


class TestTheReadEndpoint:
    def test_it_reports_the_active_mode_and_the_prod_gate(self, wired):
        fundmode.activate(fundmode.MODES[fundmode.FundMode.TEST], force=True)
        r = fund_router.get_fund_mode()
        assert r["active"]["mode"] == "test"
        assert r["prod_gate"]["reachable"] is False
        assert len(r["modes"]) == 3
