"""Tests for Strategy Composer (spine tasks S1, S2, S3)."""

import pytest
import pandas as pd
from app.fund.events import EventStore
from app.fund.strategies import StrategyService, StrategyError
from app.fund.optimization import optimize_return_streams
from app.api.v1.fund import (
    set_strategy_member,
    set_strategy_member_weights,
    compose_strategy_weights,
    get_composite_strategy,
)
from app.schemas.fund import (
    StrategyMemberRequest,
    StrategyMemberWeightsRequest,
    StrategyComposeWeightsRequest,
)


@pytest.fixture
def mock_store(monkeypatch):
    """In-memory Firestore mock via EventStore."""
    from unittest.mock import MagicMock
    class DummyDoc:
        def __init__(self, data=None, exists=True):
            self._data = data or {}
            self.exists = exists
        def to_dict(self):
            return self._data

    class DummyTransaction:
        pass

    events_db = {}
    counter_data = {"seq": 0}

    class DummyCollection:
        def __init__(self, name):
            self.name = name
        def document(self, doc_id):
            return DummyDocRef(self.name, doc_id)
        def where(self, field, op, val):
            return DummyQuery(self.name, field, op, val)

    class DummyDocRef:
        def __init__(self, coll_name, doc_id):
            self.coll_name = coll_name
            self.doc_id = doc_id
        def get(self, transaction=None):
            if (self.coll_name, self.doc_id) == ("fund_meta", "event_counter"):
                return DummyDoc(counter_data, exists=True)
            return DummyDoc(events_db.get(self.doc_id), exists=self.doc_id in events_db)
        def set(self, data, merge=False):
            if (self.coll_name, self.doc_id) == ("fund_meta", "event_counter"):
                counter_data.update(data)
            else:
                events_db[self.doc_id] = data

    class DummyQuery:
        def __init__(self, coll_name, field=None, op=None, val=None):
            self.coll_name = coll_name
            self.filters = [(field, op, val)] if field else []
            self._limit = 1000
        def where(self, field, op, val):
            self.filters.append((field, op, val))
            return self
        def order_by(self, field):
            return self
        def limit(self, l):
            self._limit = l
            return self
        def stream(self):
            res = []
            for ev in sorted(events_db.values(), key=lambda x: x.get("seq", 0)):
                match = True
                for f, op, v in self.filters:
                    if op == "==" and ev.get(f) != v:
                        match = False
                    elif op == ">" and ev.get(f, 0) <= v:
                        match = False
                if match:
                    res.append(DummyDoc(ev))
            return res[:self._limit]

    class DummyDB:
        def collection(self, name):
            return DummyCollection(name)
        def transaction(self):
            return DummyTransaction()

    def mock_txn(txn):
        counter_data["seq"] += 1
        return counter_data["seq"]

    mock_db = DummyDB()
    monkeypatch.setattr("firebase_admin.firestore.client", lambda: mock_db)
    monkeypatch.setattr("app.fund.events.firestore.transactional", lambda f: (lambda txn: mock_txn(txn)))
    return EventStore(db=mock_db)


def test_s1_weighted_membership(mock_store, monkeypatch):
    svc = StrategyService(store=mock_store)
    p = svc.register("Parent Container", actor="rushi")
    c1 = svc.register("Sleeve Alpha", actor="rushi")
    c2 = svc.register("Sleeve Beta", actor="rushi")

    pid, c1_id, c2_id = p["strategy_id"], c1["strategy_id"], c2["strategy_id"]

    # 1. Set member weight for c1
    updated_p = svc.set_member_weight(pid, c1_id, 0.4, actor="rushi")
    assert any(m["child_id"] == c1_id and m["weight"] == 0.4 for m in updated_p["members"])
    assert updated_p["member_weights"].get(c1_id) == 0.4

    # 2. Bulk set member weights
    updated_p2 = svc.set_member_weights(pid, {c1_id: 0.5, c2_id: 0.5}, actor="rushi")
    assert len(updated_p2["members"]) == 2
    assert updated_p2["member_weights"][c1_id] == 0.5
    assert updated_p2["member_weights"][c2_id] == 0.5

    # 3. Cycle guard enforcement
    with pytest.raises(StrategyError, match="cycle"):
        svc.set_member_weight(c1_id, pid, 0.5, actor="rushi")


def test_s2_composite_weight_suggestion():
    # Synthetic return streams for 2 strategies
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    s1_vals = 1.0 + (pd.Series(range(100)) * 0.005)
    s2_vals = 1.0 + (pd.Series(range(100)) * 0.002)

    df = pd.DataFrame({"strat1": s1_vals, "strat2": s2_vals}, index=dates)

    # 1. Equal weighting
    res_eq = optimize_return_streams(df, method="equal")
    assert res_eq["weights"]["strat1"] == 0.5
    assert res_eq["weights"]["strat2"] == 0.5
    assert sum(res_eq["weights"].values()) == pytest.approx(1.0)

    # 2. HRP weighting
    res_hrp = optimize_return_streams(df, method="hrp")
    assert "strat1" in res_hrp["weights"]
    assert "strat2" in res_hrp["weights"]
    assert sum(res_hrp["weights"].values()) == pytest.approx(1.0)


def test_s3_composite_rollup_api(mock_store, monkeypatch):
    svc = StrategyService(store=mock_store)
    monkeypatch.setattr("app.api.v1.fund._strategies", svc)

    p = svc.register("Master Fund", actor="rushi")
    c1 = svc.register("Sleeve 1", actor="rushi")
    c2 = svc.register("Sleeve 2", actor="rushi")

    pid, c1_id, c2_id = p["strategy_id"], c1["strategy_id"], c2["strategy_id"]

    # Record backtests for children
    svc.record_backtest(c1_id, {"total_return": 15.0, "sharpe": 1.5, "bars": 100}, actor="rushi")
    svc.record_backtest(c2_id, {"total_return": 10.0, "sharpe": 1.2, "bars": 100}, actor="rushi")

    # Set weights (0.6 and 0.4)
    svc.set_member_weights(pid, {c1_id: 0.6, c2_id: 0.4}, actor="rushi")

    # Fetch composite view
    composite = get_composite_strategy(pid)
    assert composite["strategy_id"] == pid
    assert len(composite["members"]) == 2
    assert composite["weights_sum"] == pytest.approx(1.0)
    assert len(composite["blended_equity"]) > 0
    assert "metrics" in composite
    assert "total_return" in composite["metrics"]
    assert composite["risk"]["concentration_hhi"] > 0
