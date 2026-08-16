"""Postgres -> Firestore durability snapshot.

The properties that matter are about COST and RESUMABILITY, because the whole
reason the ledger left Firestore is that its free tier metered the fund out of
its own trading day. A snapshot that re-read the destination, or re-pushed
events it had already sent, would spend the quota it exists to conserve.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")


class FakeBatch:
    def __init__(self, sink):
        self._sink = sink
        self._ops = []

    def set(self, ref, doc):
        self._ops.append((ref, doc))

    def commit(self):
        # Key by the document PATH, exactly as a direct .set() does. Keying by
        # the ref object instead made batched and unbatched writes land in two
        # different namespaces, which hid whether a repush overwrote or
        # duplicated — the property this fake exists to check.
        for ref, doc in self._ops:
            self._sink[ref._key] = doc
        self._ops = []


class FakeDoc:
    def __init__(self, sink, key):
        self._sink, self._key = sink, key

    def set(self, doc, merge=False):
        self._sink[self._key] = doc


class FakeCollection:
    def __init__(self, sink, name):
        self._sink, self._name = sink, name

    def document(self, doc_id):
        return FakeDoc(self._sink, f"{self._name}/{doc_id}")


class FakeDb:
    """Enough Firestore to record what a snapshot would have written.

    Deliberately records EVERY write: a test asserting "no writes happened" is
    the only way to prove the watermark is doing its job.
    """

    def __init__(self, fail_after=None):
        self.writes = {}
        self._fail_after = fail_after
        self._committed = 0

    def collection(self, name):
        return FakeCollection(self.writes, name)

    def batch(self):
        db = self

        class _B(FakeBatch):
            def commit(inner):
                if db._fail_after is not None and db._committed >= db._fail_after:
                    raise RuntimeError("firestore went away")
                db._committed += 1
                FakeBatch.commit(inner)

        return _B(self.writes)


def _snapshotter(fail_after=None):
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import PostgresEventStore, dsn

    test_db = "krypton_fund_test"
    head, _, _ = dsn().rpartition("/")
    test_dsn = f"{head}/{test_db}"
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_db,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{test_db}"')

    store = PostgresEventStore(test_dsn)
    from app.fund.chain import GENESIS_HASH
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_events")
            cur.execute("UPDATE fund_chain SET seq = 0, tip_hash = %s WHERE id = 1",
                        (GENESIS_HASH,))
        c.commit()

    from app.fund.snapshot_firestore import FirestoreSnapshotter
    snap = FirestoreSnapshotter(pg_store=store, db=FakeDb(fail_after=fail_after))
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("UPDATE fund_snapshot_state SET last_seq = 0, "
                        "last_ok = NULL, last_error = NULL WHERE id = 1")
        c.commit()
    return snap, store


def _append(store, n):
    from app.fund.events import Event, EventType
    t = list(EventType)[0]
    for i in range(n):
        store.append(Event(aggregate_id="fund", aggregate_type="fund", type=t,
                           payload={"i": i}, actor="test"))


def test_pushes_new_events_and_advances_the_watermark():
    snap, store = _snapshotter()
    _append(store, 3)
    out = snap.run()
    assert out["pushed"] == 3
    assert out["to_seq"] == 3
    assert snap.watermark() == 3


def test_a_second_run_with_nothing_new_writes_nothing():
    """The point of the watermark: an idle snapshot must cost zero writes."""
    snap, store = _snapshotter()
    _append(store, 2)
    snap.run()
    before = dict(snap._db_override.writes)
    out = snap.run()
    assert out["pushed"] == 0
    assert "already up to date" in out["note"]
    assert snap._db_override.writes == before


def test_only_the_tail_is_pushed_on_a_later_run():
    snap, store = _snapshotter()
    _append(store, 2)
    snap.run()
    _append(store, 2)
    out = snap.run()
    assert out["pushed"] == 2
    assert out["from_seq"] == 3 and out["to_seq"] == 4


def test_events_are_keyed_by_event_id_so_a_repush_overwrites():
    snap, store = _snapshotter()
    _append(store, 2)
    snap.run()
    rows = store.stream(limit=100)
    for e in rows:
        assert f"fund_events/{e['event_id']}" in snap._db_override.writes


def test_the_counter_is_updated_so_the_copy_knows_where_the_log_ends():
    """Without this the copy holds every event but believes the log ends where
    it did before — and an append against a restored copy would reuse a seq."""
    snap, store = _snapshotter()
    _append(store, 3)
    snap.run()
    counter = snap._db_override.writes.get("fund_meta/event_counter")
    assert counter is not None
    tail = store.stream(limit=100)[-1]
    assert counter["seq"] == tail["seq"]
    assert counter["tip_hash"] == tail["hash"]


def test_a_failure_records_the_error_and_does_not_raise():
    snap, store = _snapshotter(fail_after=0)
    _append(store, 2)
    out = snap.run()
    assert "error" in out
    assert snap.status()["last_ok"] is False
    assert "firestore went away" in snap.status()["last_error"]


def test_a_failed_run_leaves_the_watermark_where_it_can_resume():
    snap, store = _snapshotter(fail_after=0)
    _append(store, 2)
    snap.run()
    # Nothing landed, so nothing is claimed as sent: the retry re-sends it all.
    assert snap.watermark() == 0


def test_status_reports_how_far_behind_the_copy_is():
    snap, store = _snapshotter()
    _append(store, 5)
    assert snap.status()["behind_by"] == 5
    snap.run()
    assert snap.status()["behind_by"] == 0


def test_set_watermark_declares_the_destination_already_current():
    snap, store = _snapshotter()
    _append(store, 4)
    snap.set_watermark(4)
    out = snap.run()
    assert out["pushed"] == 0
    assert snap._db_override.writes == {}
