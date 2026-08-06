"""End-to-end smoke test of the fund spine using an in-memory Firestore fake.

No firebase_admin install required: we inject a fake `firebase_admin.firestore`
into sys.modules before importing the app modules. Exercises the real code
paths: event append (with the transactional counter), the positions fold, NAV
compute/strike, and the propose->approve->fill pipeline incl. idempotency.
"""

import pathlib
import sys
import types

# ---------------------------------------------------------------------------
# Minimal in-memory Firestore fake
# ---------------------------------------------------------------------------
class FakeSnap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
    @property
    def exists(self):
        return self._data is not None
    def to_dict(self):
        return dict(self._data) if self._data is not None else None

class FakeQuery:
    def __init__(self, coll):
        self._coll = coll
        self._filters = []
        self._order = None
        self._desc = False
        self._limit = None
    def where(self, field, op, val):
        self._filters.append((field, op, val)); return self
    def order_by(self, field, direction=None):
        self._order = field; self._desc = (direction == "DESC"); return self
    def limit(self, n):
        self._limit = n; return self
    def _match(self, d):
        for f, op, v in self._filters:
            x = d.get(f)
            if op == "==" and not (x == v): return False
            if op == ">" and not (x is not None and x > v): return False
        return True
    def stream(self):
        rows = [(k, v) for k, v in self._coll._docs.items() if self._match(v)]
        if self._order:
            rows.sort(key=lambda kv: kv[1].get(self._order), reverse=self._desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return [FakeSnap(k, v) for k, v in rows]

class FakeDoc:
    def __init__(self, coll, doc_id):
        self._coll = coll; self.id = doc_id
    def get(self, transaction=None):
        return FakeSnap(self.id, self._coll._docs.get(self.id))
    def set(self, data, merge=False):
        if merge and self.id in self._coll._docs:
            self._coll._docs[self.id].update(data)
        else:
            self._coll._docs[self.id] = dict(data)

class FakeCollection(FakeQuery):
    def __init__(self, db, name):
        self._db = db; self._name = name
        self._docs = db._store.setdefault(name, {})
        super().__init__(self)
    def document(self, doc_id):
        return FakeDoc(self, doc_id)

class FakeTxn:
    def set(self, ref, data, merge=False):
        ref.set(data, merge=merge)

class FakeDB:
    def __init__(self):
        self._store = {}
    def collection(self, name):
        return FakeCollection(self, name)
    def transaction(self):
        return FakeTxn()

class _QueryConst:
    DESCENDING = "DESC"

_DB = FakeDB()
fake_fs = types.SimpleNamespace(
    client=lambda: _DB,
    transactional=lambda f: f,          # decorator: run the fn as-is
    Query=_QueryConst,
)
fake_admin = types.ModuleType("firebase_admin")
fake_admin.firestore = fake_fs
sys.modules["firebase_admin"] = fake_admin
sys.modules["firebase_admin.firestore"] = fake_fs

# ---------------------------------------------------------------------------
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.fund.events import Event, EventStore, EventType
from app.fund.connectors.base import Order, Side
from app.fund.connectors.paper import PaperConnector
from app.fund.projections.positions import PositionsProjection
from app.fund.projections.nav import NavService
from app.fund.pipeline import CommandPipeline, CommandError

store = EventStore()
conn = PaperConnector(prices={"AAPL": 200.0})
proj = PositionsProjection(store)
nav = NavService(pricer=conn.price, store=store, projection=proj)
pipe = CommandPipeline(connector=conn, nav_service=nav, store=store)

def line(msg): print(f"  {msg}")

print("1) Seed $10,000 cash via a CASH_CONFIRMED event (simulated deposit)")
store.append(Event("fund", "fund", EventType.CASH_CONFIRMED, {"usd_amount": 10000.0}, "system"))
snap = nav.compute()
line(f"NAV={snap.total_nav_usd}  cash={snap.breakdown['cash']}  nav/unit={snap.nav_per_unit}")
assert snap.total_nav_usd == 10000.0

print("2) Propose BUY 10 AAPL @ 200 (notional 2000 = 20% of NAV, under 50% cap)")
res = pipe.propose_order(Order("paper", "AAPL", Side.BUY, 10), actor="rushi")
line(f"status={res['status']} preview={res.get('impact_preview')}")
assert res["status"] == "pending_approval"
oid = res["order_id"]

print("3) Approve -> executes on paper venue, fills, appends OrderFilled")
res2 = pipe.approve_order(oid, approver="rushi")
line(f"status={res2['status']} filled_qty={res2['filled_qty']} @ {res2['avg_price']}")
assert res2["status"] == "filled"

print("4) Book now reflects the fill")
book = proj.build()
line(f"cash={book.cash}  positions={book.positions}")
assert abs(book.cash - 8000.0) < 1e-6
assert abs(book.positions["AAPL"]["qty"] - 10) < 1e-6

print("5) NAV holds (2000 in AAPL + 8000 cash = 10000)")
snap2 = nav.strike(actor="system")
line(f"NAV={snap2.total_nav_usd}  breakdown={snap2.breakdown}")
assert abs(snap2.total_nav_usd - 10000.0) < 1e-6
assert nav.latest()["total_nav_usd"] == 10000.0

print("6) Idempotency: re-approving the same order is refused")
try:
    pipe.approve_order(oid, approver="rushi")
    raise SystemExit("FAIL: double-approve was allowed")
except CommandError as e:
    line(f"correctly refused: {e}")

print("7) Risk gate: propose BUY 40 AAPL (notional 8000 = 80% > 50% cap) -> rejected")
res3 = pipe.propose_order(Order("paper", "AAPL", Side.BUY, 40), actor="rushi")
line(f"status={res3['status']} breaches={res3['breaches']}")
assert res3["status"] == "rejected"

print("8) Audit trail = the event log")
events = store.stream(limit=100)
line(f"{len(events)} events: " + ", ".join(e['type'] for e in events))

print("\nALL ASSERTIONS PASSED ✅")
