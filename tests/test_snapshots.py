"""Projection snapshots.

The invariant that matters: a snapshot is a cache, never truth. Folding from a
snapshot plus the events since must be identical to folding the whole log, and
deleting every snapshot must change nothing but latency.
"""

from decimal import Decimal

from app.fund.events import EventType
from app.fund.projections.positions import PositionsProjection
from app.fund.snapshots import SnapshotStore


class FakeStore:
    def __init__(self, events=None):
        self._events = []
        self.reads = 0
        for e in events or []:
            self.append(e)

    def append(self, e):
        e = dict(e)
        e["seq"] = len(self._events) + 1
        self._events.append(e)
        return e

    def stream(self, since_seq: int = 0, limit: int = 200):
        rows = [e for e in self._events if e["seq"] > since_seq][:limit]
        self.reads += len(rows)
        return rows


class FakeDoc:
    def __init__(self, data=None):
        self._d = data
        self.exists = data is not None

    def to_dict(self):
        return self._d


class FakeDb:
    """Minimal Firestore stand-in for the snapshot document."""

    def __init__(self):
        self.docs = {}

    def collection(self, _name):
        return self

    def document(self, key):
        self._key = key
        return self

    def get(self):
        return FakeDoc(self.docs.get(self._key))

    def set(self, data):
        self.docs[self._key] = data


def _fill(symbol, qty, price, side="buy"):
    return {
        "aggregate_id": f"{symbol}-{qty}-{price}",
        "type": EventType.ORDER_FILLED.value,
        "payload": {"symbol": symbol, "side": side, "filled_qty": qty,
                    "avg_price": price, "fees": 0},
    }


def _events(n):
    return [_fill("AAPL", 1, 100 + i) for i in range(n)]


def test_snapshotted_fold_matches_a_full_fold():
    events = _events(12)
    plain = PositionsProjection(FakeStore(events)).build()

    snaps = SnapshotStore(db=FakeDb())
    store = FakeStore(events)
    snapped = PositionsProjection(store, snapshots=snaps).build()

    assert snapped.cash == plain.cash
    assert snapped.positions["AAPL"]["qty"] == plain.positions["AAPL"]["qty"]
    assert snapped.positions["AAPL"]["avg_price"] == plain.positions["AAPL"]["avg_price"]


def test_second_read_only_streams_new_events():
    """The whole point: reads stop being O(all history)."""
    db = FakeDb()
    snaps = SnapshotStore(db=db)
    store = FakeStore(_events(10))

    proj = PositionsProjection(store, snapshots=snaps, snapshot_every=5)
    proj.build()                      # writes a snapshot covering seq 10
    reads_after_first = store.reads

    store.append(_fill("MSFT", 2, 400))
    book = proj.build()

    new_reads = store.reads - reads_after_first
    assert new_reads == 1, f"expected to stream only the new event, streamed {new_reads}"
    assert book.positions["AAPL"]["qty"] == Decimal("10")   # snapshot state survived
    assert book.positions["MSFT"]["qty"] == Decimal("2")    # plus the new event


def test_deleting_snapshots_changes_nothing_but_latency():
    """A snapshot is a cache. The event log stays authoritative."""
    db = FakeDb()
    events = _events(8) + [_fill("AAPL", 3, 90, side="sell")]
    with_snap = PositionsProjection(FakeStore(events), snapshots=SnapshotStore(db=db)).build()

    db.docs.clear()
    rebuilt = PositionsProjection(FakeStore(events), snapshots=SnapshotStore(db=db)).build()

    assert rebuilt.cash == with_snap.cash
    assert rebuilt.positions["AAPL"]["qty"] == with_snap.positions["AAPL"]["qty"]


def test_unreadable_snapshot_falls_back_to_a_full_fold():
    db = FakeDb()
    db.docs["positions"] = {"seq": 5, "state": {"cash": {"__dec__": "not-a-number"}}}
    events = _events(6)

    book = PositionsProjection(FakeStore(events), snapshots=SnapshotStore(db=db)).build()

    assert book.positions["AAPL"]["qty"] == Decimal("6")


def test_decimals_survive_a_round_trip_exactly():
    """Money must never be stored as float."""
    db = FakeDb()
    snaps = SnapshotStore(db=db)
    snaps.save("t", 1, {"cash": Decimal("0.1") + Decimal("0.2")})

    seq, state = snaps.load("t")

    assert seq == 1
    assert state["cash"] == Decimal("0.3")
    assert isinstance(state["cash"], Decimal)


# --- every snapshotted projection must survive the same two properties -------
# 1. snapshotted result == full-fold result
# 2. deleting the snapshot changes nothing but latency

from app.fund.projections.holdings import HoldingsProjection
from app.fund.projections.orders import OrdersProjection
from app.fund.projections.strategy import StrategyAttribution


def _ledger_events():
    return [
        {"aggregate_id": "sub-1", "aggregate_type": "subscription",
         "type": EventType.SUBSCRIPTION_REQUESTED.value,
         "payload": {"lp_id": "alice", "lp_name": "Alice", "usd_amount": 1000}},
        {"aggregate_id": "sub-1", "aggregate_type": "subscription",
         "type": EventType.UNITS_ISSUED.value,
         "payload": {"lp_id": "alice", "units": 1000}},
        {"aggregate_id": "ord-1", "aggregate_type": "order",
         "type": EventType.ORDER_PROPOSED.value,
         "payload": {"symbol": "AAPL", "side": "buy", "qty": 5}},
        {"aggregate_id": "ord-1", "aggregate_type": "order",
         "type": EventType.ORDER_FILLED.value,
         "payload": {"symbol": "AAPL", "side": "buy", "filled_qty": 5,
                     "avg_price": 100, "fees": 0, "strategy_id": "s1"}},
    ]


def test_holdings_snapshot_matches_full_fold():
    ev = _ledger_events()
    plain = HoldingsProjection(FakeStore(ev)).build()
    snapped = HoldingsProjection(FakeStore(ev), snapshots=SnapshotStore(db=FakeDb()),
                                 snapshot_every=1).build()

    assert snapped["alice"]["units"] == plain["alice"]["units"] == Decimal("1000")
    assert snapped["alice"]["name"] == "Alice"


def test_orders_snapshot_matches_full_fold():
    ev = _ledger_events()
    plain = OrdersProjection(FakeStore(ev))._fold()
    snapped = OrdersProjection(FakeStore(ev), snapshots=SnapshotStore(db=FakeDb()),
                               snapshot_every=1)._fold()

    assert snapped["ord-1"]["last"] == plain["ord-1"]["last"] == EventType.ORDER_FILLED.value
    assert snapped["ord-1"]["filled_qty"] == 5.0


def test_attribution_snapshot_matches_full_fold():
    ev = _ledger_events()
    price = lambda _s: 120.0
    plain = StrategyAttribution(FakeStore(ev)).with_values(price)
    snapped = StrategyAttribution(FakeStore(ev), snapshots=SnapshotStore(db=FakeDb()),
                                  snapshot_every=1).with_values(price)

    assert snapped == plain
    assert snapped[0]["unrealized_pnl_usd"] == 100.0   # 5 * (120 - 100)


def test_incremental_fold_equals_full_fold_after_new_events():
    """The property that actually matters: snapshot + delta == fold from scratch."""
    db = FakeDb()
    ev = _ledger_events()
    store = FakeStore(ev)
    proj = HoldingsProjection(store, snapshots=SnapshotStore(db=db), snapshot_every=1)
    proj.build()                                   # snapshot written

    store.append({"aggregate_id": "sub-2", "aggregate_type": "subscription",
                  "type": EventType.UNITS_ISSUED.value,
                  "payload": {"lp_id": "alice", "units": 250}})

    incremental = proj.build()
    from_scratch = HoldingsProjection(FakeStore(store.stream(limit=1000))).build()

    assert incremental["alice"]["units"] == from_scratch["alice"]["units"] == Decimal("1250")


def test_first_snapshot_is_taken_immediately_not_after_N_events():
    """A young book must still snapshot. Waiting for `every` before the FIRST
    snapshot meant a small log never snapshotted and every read re-folded it —
    which exhausted the read quota on a project holding ~22 events."""
    db = FakeDb()
    store = FakeStore(_events(3))                 # far fewer than `every`
    proj = PositionsProjection(store, snapshots=SnapshotStore(db=db), snapshot_every=50)

    proj.build()
    assert "positions" in db.docs, "no snapshot written for a small book"

    reads_before = store.reads
    proj.build()
    assert store.reads - reads_before == 0, "second read should fold nothing"
