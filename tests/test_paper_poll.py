"""Regression: paper connector fill/poll must be a deterministic document read.

The old poll() used a where("ref_id"==) *field query*, which returned
inconsistently on real Firestore and left orders stuck at 'working'. execute()
now also keys the fill record by ref_id, and poll() reads it by document id.
"""

from app.fund.connectors.base import FillState, Order, Side
from app.fund.connectors.paper import _ORDERS


def test_poll_reads_fill_by_ref_id_document(wire):
    from firebase_admin import firestore

    ref = wire.conn.execute(Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1), "idem-1")
    db = firestore.client()
    # execute keys the record by BOTH the idempotency key and the ref_id
    assert db.collection(_ORDERS).document(ref.ref_id).get().exists
    assert db.collection(_ORDERS).document("idem-1").get().exists
    # poll finds it deterministically and reports the instant fill
    status = wire.conn.poll(ref)
    assert status.state == FillState.FILLED and status.filled_qty == 1


def test_execute_is_idempotent(wire):
    o = Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1)
    ref1 = wire.conn.execute(o, "idem-2")
    ref2 = wire.conn.execute(o, "idem-2")  # replay -> same handle, no double fill
    assert ref1.ref_id == ref2.ref_id
