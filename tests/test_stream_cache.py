"""The read cache that makes running on Firestore viable.

Every projection folds by calling stream(). One cockpit render asks for NAV,
risk, orders, compliance, TCA and the chain, so an uncached stream costs a full
log read per projection per request — which is what exhausted the free tier
twice. These check the cache does its job without ever hiding a write from the
process that made it.
"""

from __future__ import annotations

import app.fund.events as ev
from app.fund.events import Event, EventStore, EventType


class CountingDB:
    """Counts how many times the log is actually read from 'Firestore'."""

    def __init__(self):
        self.reads = 0
        self.docs_read = 0
        self.docs: list[dict] = []
        self.counter = {"seq": 0}

    # --- query surface ----------------------------------------------------
    def collection(self, name):
        return _Coll(self, name)

    def transaction(self):
        return _Txn(self)


class _Snap:
    def __init__(self, data):
        self._d = data
        self.exists = data is not None

    def to_dict(self):
        return self._d


class _Ref:
    def __init__(self, db, name, doc_id):
        self.db, self.name, self.doc_id = db, name, doc_id

    def get(self, transaction=None):
        return _Snap(self.db.counter if self.name == "fund_meta" else None)

    def set(self, data, merge=False):
        if self.name == "fund_meta":
            self.db.counter.update(data)
        else:
            self.db.docs.append(data)


class _Query:
    """Honours the seq filter, so 'how many DOCUMENTS did we pay for' is real.

    A fake that ignores where() would make the incremental read look identical
    to a full one and the test would prove nothing.
    """

    def __init__(self, db):
        self.db = db
        self._min_seq = 0

    def where(self, field=None, op=None, value=None, *a, **k):
        if field == "seq" and op == ">":
            self._min_seq = value
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def stream(self):
        rows = [d for d in sorted(self.db.docs, key=lambda x: x.get("seq", 0))
                if (d.get("seq") or 0) > self._min_seq]
        self.db.reads += 1
        # Firestore bills per document returned, with a minimum of one.
        self.db.docs_read += max(1, len(rows))
        return [_Snap(d) for d in rows]


class _Coll(_Query):
    def __init__(self, db, name):
        super().__init__(db)
        self.name = name

    def document(self, doc_id):
        return _Ref(self.db, self.name, doc_id)


class _Txn:
    def __init__(self, db):
        self.db = db

    def set(self, ref, data, merge=False):
        ref.set(data, merge=merge)


def store(monkeypatch):
    import firebase_admin.firestore as fs
    monkeypatch.setattr(fs, "transactional", lambda f: f, raising=False)
    ev.EventStore.invalidate_cache()
    db = CountingDB()
    return EventStore(db=db), db


def an_event(n=1):
    return Event(aggregate_id=f"o{n}", aggregate_type="order",
                 type=EventType.ORDER_PROPOSED, payload={"symbol": "F"}, actor="t")


# ------------------------------------------------------------------ caching
def test_repeated_folds_cost_one_read(monkeypatch):
    s, db = store(monkeypatch)
    s.append(an_event())
    db.reads = 0
    for _ in range(20):
        s.stream(limit=1000)
    assert db.reads == 1


def test_the_cache_is_shared_across_store_instances(monkeypatch):
    """Projections each construct their own EventStore; they must not each
    pay for their own copy of the log."""
    s, db = store(monkeypatch)
    s.append(an_event())
    db.reads = 0
    s.stream(limit=1000)
    EventStore(db=db).stream(limit=1000)
    assert db.reads == 1


def test_by_aggregate_uses_the_same_cache(monkeypatch):
    """This one is on the trade path — the idempotency check runs per order
    per settlement tick."""
    s, db = store(monkeypatch)
    s.append(an_event(1))
    db.reads = 0
    s.stream(limit=1000)
    for _ in range(10):
        s.by_aggregate("o1")
    assert db.reads == 1


# --------------------------------------------------- never hide our own write
def test_an_append_is_immediately_visible(monkeypatch):
    """A fill hidden behind the cache would let the idempotency check pass
    twice and double the position."""
    s, db = store(monkeypatch)
    s.stream(limit=1000)
    s.append(an_event(2))
    assert any(e.get("aggregate_id") == "o2" for e in s.stream(limit=1000))


def test_an_append_is_visible_to_by_aggregate(monkeypatch):
    s, db = store(monkeypatch)
    s.by_aggregate("o3")
    s.append(an_event(3))
    assert len(s.by_aggregate("o3")) == 1


def test_every_append_invalidates(monkeypatch):
    s, db = store(monkeypatch)
    for i in range(1, 4):
        s.append(an_event(i))
        assert len(s.stream(limit=1000)) == i


# ------------------------------------------------------------- correctness
def test_since_seq_still_filters(monkeypatch):
    s, db = store(monkeypatch)
    for i in range(1, 6):
        s.append(an_event(i))
    assert [e["seq"] for e in s.stream(since_seq=3, limit=1000)] == [4, 5]


def test_limit_still_truncates(monkeypatch):
    s, db = store(monkeypatch)
    for i in range(1, 6):
        s.append(an_event(i))
    assert len(s.stream(limit=2)) == 2


def test_events_come_back_in_seq_order(monkeypatch):
    s, db = store(monkeypatch)
    for i in range(1, 6):
        s.append(an_event(i))
    seqs = [e["seq"] for e in s.stream(limit=1000)]
    assert seqs == sorted(seqs)


def test_by_aggregate_only_returns_that_aggregate(monkeypatch):
    s, db = store(monkeypatch)
    s.append(an_event(1))
    s.append(an_event(2))
    assert [e["aggregate_id"] for e in s.by_aggregate("o2")] == ["o2"]


# ------------------------------------------------- incremental, not re-reading
def test_a_refresh_only_fetches_events_we_do_not_have(monkeypatch):
    """The whole point. Re-reading all 52 events every few seconds is what
    blew the free tier; asking only for what is new costs one read."""
    import app.fund.events as _ev

    s, db = store(monkeypatch)
    for i in range(1, 21):
        s.append(an_event(i))
    s.stream(limit=1000)

    monkeypatch.setattr(_ev, "_STREAM_TTL_SECONDS", 0)   # force a refresh
    db.docs_read = 0
    s.stream(limit=1000)
    assert db.docs_read == 1            # empty incremental result, not 20


def test_a_refresh_picks_up_only_the_new_events(monkeypatch):
    import app.fund.events as _ev

    s, db = store(monkeypatch)
    for i in range(1, 21):
        s.append(an_event(i))
    s.stream(limit=1000)

    # Another writer appends behind our back.
    db.docs.append({"seq": 21, "aggregate_id": "o21", "type": "OrderProposed",
                    "payload": {}, "actor": "other", "ts": "2026-08-14T00:00:00+00:00"})
    monkeypatch.setattr(_ev, "_STREAM_TTL_SECONDS", 0)
    db.docs_read = 0
    rows = s.stream(limit=1000)
    assert db.docs_read == 1            # just the one new event
    assert len(rows) == 21              # and it is visible


def test_a_full_session_of_polling_stays_under_the_free_tier(monkeypatch):
    """720 refreshes is six hours of polling every 30 seconds."""
    import app.fund.events as _ev

    s, db = store(monkeypatch)
    for i in range(1, 53):
        s.append(an_event(i))
    s.stream(limit=1000)

    monkeypatch.setattr(_ev, "_STREAM_TTL_SECONDS", 0)
    db.docs_read = 0
    for _ in range(720):
        s.stream(limit=1000)
    assert db.docs_read == 720          # not 720 * 52 = 37,440
