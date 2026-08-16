"""Postgres event store — the hash must survive the round trip.

The whole point of moving the ledger is that the evidence moves with it. A
store that quietly changes 3.0 into Decimal('3.0') on the way back out would
produce a DIFFERENT canonical rendering and therefore a different hash, and the
chain would report tampering on a log nobody touched. These tests exist to
catch that before a migration does.

Skipped unless a Postgres is reachable, so the suite still runs on a machine
with no Docker.
"""

import os
import uuid

import pytest

from app.fund.chain import GENESIS_HASH, event_hash, verify
from app.fund.events import Event, EventType

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")


#: Tests get their OWN database, always. An earlier version of this file wrote
#: into whatever FUND_PG_DSN pointed at, which was the operational log — and
#: since one test deliberately inserts a sealed event with a bogus hash, it
#: broke the fund's chain verification. A test that can corrupt the ledger it
#: is testing is not a test.
TEST_DB = "krypton_fund_test"


def _test_dsn() -> str:
    from app.fund.pgstore import dsn
    base = dsn()
    head, _, _ = base.rpartition("/")
    return f"{head}/{TEST_DB}"


def _store():
    psycopg = pytest.importorskip("psycopg")
    from app.fund.pgstore import PostgresEventStore, dsn

    admin = dsn()
    try:
        conn = psycopg.connect(admin, connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    return PostgresEventStore(_test_dsn())


@pytest.fixture
def store():
    """A clean log per test.

    Not merely tidiness: one test inserts a deliberately bogus hash to prove
    append_raw copies verbatim, and another verifies the WHOLE log. Sharing a
    log between them makes the second fail because of the first, and the
    failure points at the store rather than at the test that poisoned it.
    """
    s = _store()
    import psycopg
    with psycopg.connect(_test_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE fund_events")
            cur.execute("UPDATE fund_chain SET seq = 0, tip_hash = %s WHERE id = 1",
                        (GENESIS_HASH,))
        conn.commit()
    return s


ANY_TYPE = list(EventType)[0]


def _ev(agg: str, payload: dict) -> Event:
    return Event(aggregate_id=agg, aggregate_type="fund", type=ANY_TYPE,
                 payload=payload, actor="test")


def test_append_assigns_seq_and_chains(store):
    agg = f"t-{uuid.uuid4().hex[:8]}"
    a = store.append(_ev(agg, {"n": 1}))
    b = store.append(_ev(agg, {"n": 2}))
    assert b.seq == a.seq + 1
    rows = store.by_aggregate(agg)
    assert [r["seq"] for r in rows] == [a.seq, b.seq]
    assert rows[1]["prev_hash"] == rows[0]["hash"]


def test_payload_types_survive_the_round_trip(store):
    """The hash is computed over the payload BEFORE the write and verified
    after the read. If JSONB changed a type, this fails."""
    agg = f"t-{uuid.uuid4().hex[:8]}"
    payload = {
        "int": 3,
        "float": 2.5,
        "whole_float": 3.0,          # the classic: must not come back as 3
        "neg": -1.25,
        "big": 10_000_000_000,
        "str": "GLD",
        "bool": True,
        "null": None,
        "nested": {"a": [1, 2.5, "x"], "b": {"c": 1}},
        "empty": {},
        "list": [],
        "unicode": "café — naïve",
    }
    ev = store.append(_ev(agg, payload))
    row = [r for r in store.by_aggregate(agg) if r["seq"] == ev.seq][0]

    assert row["payload"] == payload
    # The decisive assertion: recomputing the hash from what came BACK must
    # reproduce what was stored.
    assert event_hash(row, row["prev_hash"]) == row["hash"]


def test_a_read_back_log_verifies(store):
    agg = f"t-{uuid.uuid4().hex[:8]}"
    for i in range(5):
        store.append(_ev(agg, {"i": i, "px": 100.0 + i * 0.25}))
    result = verify(store.stream(limit=1_000_000))
    assert result.ok, result.first_break
    assert result.chained >= 5


def test_stream_is_ordered_and_exclusive_of_since(store):
    agg = f"t-{uuid.uuid4().hex[:8]}"
    a = store.append(_ev(agg, {"n": 1}))
    b = store.append(_ev(agg, {"n": 2}))
    rows = store.stream(since_seq=a.seq, limit=1000)
    seqs = [r["seq"] for r in rows]
    assert a.seq not in seqs
    assert b.seq in seqs
    assert seqs == sorted(seqs)


def test_event_ids_are_unique(store):
    """The migration relies on ON CONFLICT (event_id) to be re-runnable, which
    only means anything if the constraint is really there."""
    import psycopg
    agg = f"t-{uuid.uuid4().hex[:8]}"
    ev = store.append(_ev(agg, {"n": 1}))
    row = [r for r in store.by_aggregate(agg) if r["seq"] == ev.seq][0]
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(_test_dsn()) as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO fund_events (seq, event_id, aggregate_id, "
                    "aggregate_type, type, actor, ts, payload, prev_hash, hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (999_999, row["event_id"], "x", "fund", "X", "t", "now",
                     "{}", GENESIS_HASH, "h"))
            c.commit()


def test_append_raw_copies_a_sealed_event_verbatim(store):
    """Migration path: the stored hash must be preserved, not recomputed."""
    agg = f"t-{uuid.uuid4().hex[:8]}"
    seq = 900_000 + int(uuid.uuid4().int % 10_000)
    sealed = {
        "seq": seq, "event_id": str(uuid.uuid4()), "aggregate_id": agg,
        "aggregate_type": "fund", "type": "Imported", "actor": "migration",
        "ts": "2026-01-01T00:00:00+00:00", "payload": {"x": 1},
        "prev_hash": GENESIS_HASH, "hash": "deadbeef" * 8,
    }
    store.append_raw(sealed)
    row = [r for r in store.by_aggregate(agg) if r["seq"] == seq][0]
    assert row["hash"] == "deadbeef" * 8      # verbatim, not recomputed
    assert row["prev_hash"] == GENESIS_HASH


def test_append_raw_is_idempotent(store):
    """A migration that dies halfway must be safe to re-run."""
    agg = f"t-{uuid.uuid4().hex[:8]}"
    seq = 910_000 + int(uuid.uuid4().int % 10_000)
    sealed = {
        "seq": seq, "event_id": str(uuid.uuid4()), "aggregate_id": agg,
        "aggregate_type": "fund", "type": "Imported", "actor": "migration",
        "ts": "2026-01-01T00:00:00+00:00", "payload": {"x": 1},
        "prev_hash": GENESIS_HASH, "hash": "beef" * 16,
    }
    store.append_raw(sealed)
    store.append_raw(sealed)
    assert len([r for r in store.by_aggregate(agg) if r["seq"] == seq]) == 1


def test_decimal_payloads_are_encoded_before_hashing(store):
    """Money is Decimal here, and json.dumps cannot serialise it.

    set_allocation appended a Decimal payload and the call died with a 500 that
    never reached the log — the strategy stayed at its old allocation while the
    caller believed it had changed.

    The hash matters as much as the crash: the Firestore store hashes the
    ENCODED body, so hashing raw Decimals would make the two stores disagree
    about the digest of an identical event.
    """
    from decimal import Decimal
    from app.fund.chain import event_hash
    agg = f"t-{uuid.uuid4().hex[:8]}"
    ev = store.append(_ev(agg, {"target_pct": Decimal("2.5"),
                                "nested": {"usd": Decimal("1234.56")}}))
    row = [r for r in store.by_aggregate(agg) if r["seq"] == ev.seq][0]
    # Decimals land as strings, the way Firestore stored them.
    assert row["payload"]["target_pct"] == "2.5"
    assert row["payload"]["nested"]["usd"] == "1234.56"
    # And the stored hash still describes what came back.
    assert event_hash(row, row["prev_hash"]) == row["hash"]
