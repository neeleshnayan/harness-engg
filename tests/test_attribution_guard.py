"""The attribution guard, the two-sided strategy cap, and the repair mechanism.

Every test here is aimed at ONE measured incident
(docs/AUDIT_R6_D2_ATTRIBUTION_2026-08-20.md ITEM 3, 2026-08-20):

  seq 76  GLD BUY  0.424471 @ 402.18 tagged `e54f40af` (Trend)
  seq 258 GLD SELL 0.424471 @ 100.00 tagged `machinery-test`

The quantities net to zero, so NAV and positions were never wrong. Attribution
keys on the fill's ``strategy_id``, so Trend kept a phantom LONG and
machinery-test a phantom SHORT forever — and `POST /fund/rebalance/preview`
targeting Trend at 20% returned a **$376.84 GLD BUY with `current_usd: 0.0`
and zero warnings**: an order into a symbol the fund holds none of.

These tests fail if that behaviour ever comes back. None of them asserts that a
plan IS produced from a disagreeing fold — that is the bug, and a test that
blessed it would be the second half of the same accident.
"""

from decimal import Decimal

import pytest

from app.fund.events import Event, EventStore, EventType
from app.fund.projections.strategy import (
    AttributionCorrectionError,
    StrategyAttribution,
    append_attribution_correction,
)
from app.fund.rebalance import AttributionMismatch, RebalanceError, RebalanceService
from app.fund.riskmonitor import RiskMonitor
from app.fund.risk import RiskLimits

from tests.test_rebalance import (        # the fakes this file deliberately reuses
    FakeAttribution,
    FakeControl,
    FakeNav,
    FakePipeline,
    FakeStore,
    FakeStrategies,
)


GLD_QTY = 0.424471          # the exact quantity of the incident
GLD_PRICE = 402.18


def _svc(rows, book, strategies=None):
    return RebalanceService(
        nav_service=FakeNav(1884.21, book=book),
        pricer=lambda s: GLD_PRICE if s.upper() == "GLD" else 100.0,
        attribution=FakeAttribution(rows),
        strategies=strategies or FakeStrategies(),
        pipeline=FakePipeline(),
        control=FakeControl(),
        risk_engine=None,
        store=FakeStore(),
    )


# --- A1: the guard ----------------------------------------------------------

class TestAttributionGuard:
    def test_the_measured_phantom_is_refused_not_priced(self):
        """The incident, replayed at its measured quantities. Both phantom legs
        are named; no plan is returned at all."""
        svc = _svc(
            rows=[
                {"strategy_id": "e54f40af", "positions": {"GLD": GLD_QTY}},
                {"strategy_id": "machinery-test", "positions": {"GLD": -GLD_QTY}},
            ],
            book={},                       # the fund holds NO GLD — it netted out
        )
        with pytest.raises(AttributionMismatch) as e:
            svc.build({"e54f40af": 20.0})
        msg = str(e.value)
        assert "e54f40af" in msg and "machinery-test" in msg
        assert "GLD" in msg
        assert "holds none" in msg

    def test_the_guard_fires_on_preview_of_an_unrelated_strategy(self):
        """The phantom corrupts the shared `current` map, so it must be refused
        even when the plan targets something else entirely."""
        svc = _svc(
            rows=[
                {"strategy_id": "e54f40af", "positions": {"GLD": GLD_QTY}},
                {"strategy_id": "machinery-test", "positions": {"GLD": -GLD_QTY}},
                {"strategy_id": "s1", "positions": {"AAA": 5.0}},
            ],
            book={"AAA": 5.0},
        )
        with pytest.raises(AttributionMismatch):
            svc.build({"s1": 10.0})

    def test_a_strategy_cannot_claim_more_than_the_fund_holds(self):
        svc = _svc(rows=[{"strategy_id": "s1", "positions": {"AAA": 9.0}}],
                   book={"AAA": 5.0})
        with pytest.raises(AttributionMismatch) as e:
            svc.build({"s1": 10.0})
        assert "only" in str(e.value)

    def test_a_strategy_cannot_be_long_what_the_fund_is_short(self):
        svc = _svc(rows=[{"strategy_id": "s1", "positions": {"AAA": 5.0}}],
                   book={"AAA": -5.0})
        with pytest.raises(AttributionMismatch) as e:
            svc.build({"s1": 10.0})
        assert "opposite directions" in str(e.value)

    def test_two_strategies_splitting_one_holding_are_allowed(self):
        """The guard must not refuse a correctly-tagged book: this is the
        false-positive that would make it get switched off."""
        svc = _svc(
            rows=[{"strategy_id": "s1", "positions": {"AAA": 3.0}},
                  {"strategy_id": "s2", "positions": {"AAA": 2.0}}],
            book={"AAA": 5.0},
        )
        plan = svc.build({"s1": 20.0, "s2": 10.0})
        assert plan["orders"] or plan["skipped"]      # it built, which is the point

    def test_dust_below_tolerance_is_not_a_disagreement(self):
        svc = _svc(rows=[{"strategy_id": "s1", "positions": {"AAA": 5.0000001}}],
                   book={"AAA": 5.0})
        svc.build({"s1": 10.0})           # must not raise

    def test_an_unreadable_fold_refuses_rather_than_assuming_empty(self):
        """Unreadable is not 'the fund holds nothing'. If the authoritative fold
        cannot be read the guard has no reference, and a plan built without a
        reference is exactly the plan this guard exists to stop."""
        class DeadNav(FakeNav):
            def book(self):
                raise RuntimeError("postgres unreachable")

        svc = _svc(rows=[{"strategy_id": "s1", "positions": {"AAA": 5.0}}], book={})
        svc._nav = DeadNav(1884.21, book={})
        with pytest.raises(RuntimeError):
            svc.build({"s1": 10.0})


# --- A1b: archived strategies ----------------------------------------------

class ArchivingStrategies(FakeStrategies):
    def __init__(self, archived=()):
        super().__init__()
        self._archived = set(archived)

    def list(self):
        return [{"strategy_id": sid, "name": f"Strategy {sid}",
                 "archived": sid in self._archived}
                for sid in ("s1", "s2", "e54f40af")]


class TestArchivedTargets:
    def test_an_archived_strategy_cannot_be_given_a_target(self):
        """Archive was cosmetic: Trend was archived the morning of the incident
        and rebalance/preview still accepted it as a target."""
        svc = _svc(rows=[{"strategy_id": "e54f40af", "positions": {"AAA": 5.0}}],
                   book={"AAA": 5.0},
                   strategies=ArchivingStrategies(archived={"e54f40af"}))
        with pytest.raises(RebalanceError) as e:
            svc.build({"e54f40af": 20.0})
        assert "archived" in str(e.value)
        assert "e54f40af" in str(e.value)

    def test_winding_an_archived_strategy_down_to_zero_is_allowed(self):
        svc = _svc(rows=[{"strategy_id": "e54f40af", "positions": {"AAA": 5.0}}],
                   book={"AAA": 5.0},
                   strategies=ArchivingStrategies(archived={"e54f40af"}))
        plan = svc.build({"e54f40af": 0.0})
        assert plan["orders"][0]["side"] == "sell"

    def test_an_unreadable_registry_refuses_rather_than_assuming_active(self):
        class DeadRegistry(FakeStrategies):
            def list(self):
                raise RuntimeError("registry unreadable")

        svc = _svc(rows=[{"strategy_id": "s1", "positions": {"AAA": 5.0}}],
                   book={"AAA": 5.0}, strategies=DeadRegistry())
        with pytest.raises(RebalanceError) as e:
            svc.build({"s1": 20.0})
        assert "UNKNOWN" in str(e.value)


# --- A2: the two-sided cap --------------------------------------------------

class TestTwoSidedStrategyCap:
    """`weight > strat_limit` meant a phantom SHORT of any size could never
    breach the 40% cap (ITEM 3(a)). The cap is on magnitude now."""

    def _alarms(self, weight_pct):
        monitor = RiskMonitor(nav_service=None, store=None)
        return monitor.evaluate_alarms({
            "limits": RiskLimits(max_strategy_pct=0.40).to_dict(),
            "strategies": [{"strategy_id": "phantom", "name": "Phantom",
                            "weight_pct": weight_pct}],
            "positions": [], "cash_pct": 100.0, "history_snaps": [],
            "drawdown": {"drawdown_pct": 0.0}, "nav_usd": 1000.0,
        })

    def test_a_negative_weight_past_the_cap_breaches(self):
        alarms = [a for a in self._alarms(-63.0) if a.type == "strategy_cap"]
        assert alarms, "a -63% strategy weight did not breach a 40% cap"
        assert alarms[0].metric == pytest.approx(63.0)
        assert "short" in alarms[0].message

    def test_a_positive_weight_past_the_cap_still_breaches(self):
        alarms = [a for a in self._alarms(63.0) if a.type == "strategy_cap"]
        assert alarms and "long" in alarms[0].message

    def test_a_weight_inside_the_cap_on_either_side_does_not_breach(self):
        assert not [a for a in self._alarms(-20.0) if a.type == "strategy_cap"]
        assert not [a for a in self._alarms(20.0) if a.type == "strategy_cap"]


# --- A3: the repair mechanism ----------------------------------------------

class TestAttributionCorrection:
    def _fill(self, store, sid, symbol, side, qty, price):
        store.append(Event(
            aggregate_id=f"{sid}-{symbol}-{side}", aggregate_type="order",
            type=EventType.ORDER_FILLED,
            payload={"symbol": symbol, "side": side, "strategy_id": sid,
                     "filled_qty": Decimal(str(qty)), "avg_price": Decimal(str(price)),
                     "fees": Decimal("0")},
            actor="system"))

    def test_a_correction_moves_the_phantom_pair_to_zero(self):
        """The repair for the measured incident, folded — and NOTHING else moves."""
        store = FakeStore()
        self._fill(store, "e54f40af", "GLD", "buy", GLD_QTY, GLD_PRICE)
        self._fill(store, "machinery-test", "GLD", "sell", GLD_QTY, 100.00)

        before = {r["strategy_id"]: r for r in
                  StrategyAttribution(store).with_values(lambda s: GLD_PRICE)}
        assert float(before["e54f40af"]["positions"]["GLD"]) == pytest.approx(GLD_QTY)
        assert float(before["machinery-test"]["positions"]["GLD"]) == pytest.approx(-GLD_QTY)

        append_attribution_correction(
            store, symbol="GLD", qty=GLD_QTY, cost_usd=GLD_QTY * GLD_PRICE,
            from_strategy_id="e54f40af", to_strategy_id="machinery-test",
            reason=("seq 258 GLD SELL was tagged machinery-test; the matching BUY at "
                    "seq 76 was e54f40af — docs/AUDIT_R6_D2_ATTRIBUTION_2026-08-20.md"),
            actor="cto")

        after = {r["strategy_id"]: r for r in
                 StrategyAttribution(store).with_values(lambda s: GLD_PRICE)}
        # Both phantom legs are gone: `with_values` drops sub-dust positions.
        assert "GLD" not in after.get("e54f40af", {}).get("positions", {})
        assert "GLD" not in after.get("machinery-test", {}).get("positions", {})

    def test_a_correction_without_a_reason_is_refused_before_the_log(self):
        store = FakeStore()
        with pytest.raises(AttributionCorrectionError) as e:
            append_attribution_correction(
                store, symbol="GLD", qty=1, cost_usd=1,
                from_strategy_id="a", to_strategy_id="b", reason="   ", actor="cto")
        assert "written reason" in str(e.value)
        assert store.events == [], "a refused correction must not reach the log"

    def test_an_unexplained_correction_already_in_the_log_is_ignored_by_the_fold(self):
        """Belt and braces: validation lives at the append, but the fold must not
        apply an unexplained correction that reached the log some other way."""
        store = FakeStore()
        self._fill(store, "s1", "AAA", "buy", 5, 100.0)
        store.append(Event(
            aggregate_id="s2", aggregate_type="strategy",
            type=EventType.STRATEGY_ATTRIBUTION_CORRECTED,
            payload={"symbol": "AAA", "qty": "5", "cost_usd": "500",
                     "from_strategy_id": "s1", "to_strategy_id": "s2", "reason": ""},
            actor="whoever"))
        rows = {r["strategy_id"]: r for r in
                StrategyAttribution(store).with_values(lambda s: 100.0)}
        assert float(rows["s1"]["positions"]["AAA"]) == pytest.approx(5.0)
        assert "s2" not in rows

    def test_a_self_directed_correction_is_refused(self):
        store = FakeStore()
        with pytest.raises(AttributionCorrectionError):
            append_attribution_correction(
                store, symbol="GLD", qty=1, cost_usd=1, from_strategy_id="a",
                to_strategy_id="a", reason="because", actor="cto")

    def test_a_correction_moves_realised_pnl_when_asked(self):
        store = FakeStore()
        self._fill(store, "s1", "AAA", "buy", 5, 100.0)
        self._fill(store, "s1", "AAA", "sell", 5, 120.0)
        append_attribution_correction(
            store, symbol="AAA", qty=0, cost_usd=0, realized_usd=100.0,
            net_invested_usd=-100.0, from_strategy_id="s1", to_strategy_id="s2",
            reason="the closing leg belonged to s2", actor="cto")
        rows = {r["strategy_id"]: r for r in
                StrategyAttribution(store).with_values(lambda s: 120.0)}
        assert float(rows["s1"]["realized_pnl_usd"]) == pytest.approx(0.0)
        assert float(rows["s2"]["realized_pnl_usd"]) == pytest.approx(100.0)

    def test_a_correction_does_not_touch_the_fund_position_fold(self):
        """The repair moves an index, never a share. If it ever moves the book,
        a correction becomes an untraded position change — the thing the
        append-only log exists to make impossible."""
        from app.fund.projections.positions import PositionsProjection

        store = FakeStore()
        self._fill(store, "s1", "AAA", "buy", 5, 100.0)
        before = float(PositionsProjection(store).build().positions["AAA"]["qty"])
        append_attribution_correction(
            store, symbol="AAA", qty=5, cost_usd=500, from_strategy_id="s1",
            to_strategy_id="s2", reason="mistagged", actor="cto")
        after = float(PositionsProjection(store).build().positions["AAA"]["qty"])
        assert before == after == 5.0
