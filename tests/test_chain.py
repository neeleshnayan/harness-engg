"""Tamper evidence. The tests are mostly attacks.

Every projection folds obediently from the log, so an edited event produces a
NAV that is internally consistent and completely false. These check that each
way of editing it leaves a mark.
"""

from __future__ import annotations

import copy

from app.fund.chain import (
    GENESIS_HASH,
    canonical,
    event_hash,
    rechain,
    verify,
)


def ev(seq, etype="OrderFilled", payload=None, eid=None):
    return {
        "seq": seq,
        "event_id": eid or f"e{seq}",
        "aggregate_id": f"o{seq}",
        "aggregate_type": "order",
        "type": etype,
        "payload": payload if payload is not None else {"symbol": "F", "qty": "10"},
        "actor": "system",
        "ts": f"2026-08-13T10:00:{seq:02d}+00:00",
    }


def chained(n=5):
    return rechain([ev(i) for i in range(1, n + 1)])


# ------------------------------------------------------------- a good chain
def test_a_freshly_built_chain_verifies():
    r = verify(chained(5))
    assert r.ok is True and r.chained == 5 and r.unchained == 0


def test_the_first_event_links_to_genesis():
    rows = chained(3)
    assert rows[0]["prev_hash"] == GENESIS_HASH


def test_each_event_links_to_the_one_before():
    rows = chained(4)
    for a, b in zip(rows, rows[1:]):
        assert b["prev_hash"] == a["hash"]


def test_an_empty_log_is_not_claimed_to_be_verified():
    r = verify([])
    assert r.chained == 0
    assert any("no tamper evidence" in n for n in r.notes)


# ------------------------------------------------------------------ attacks
def test_editing_a_filled_price_breaks_the_chain():
    rows = chained(5)
    rows[2]["payload"]["qty"] = "9999"
    r = verify(rows)
    assert r.ok is False
    assert r.first_break["seq"] == 3
    assert "altered" in r.first_break["reason"]


def test_editing_the_actor_breaks_the_chain():
    """Who did it is as much a fact as what was done."""
    rows = chained(5)
    rows[1]["actor"] = "somebody_else"
    assert verify(rows).ok is False


def test_backdating_an_event_breaks_the_chain():
    rows = chained(5)
    rows[3]["ts"] = "2026-01-01T00:00:00+00:00"
    assert verify(rows).ok is False


def test_deleting_an_event_breaks_the_chain():
    """The classic: remove the inconvenient order and renumber nothing."""
    rows = chained(5)
    del rows[2]
    r = verify(rows)
    assert r.ok is False
    assert "removed" in r.first_break["reason"] or "inserted" in r.first_break["reason"]


def test_inserting_a_forged_event_breaks_the_chain():
    rows = chained(5)
    forged = ev(99, "UnitsIssued", {"units": "1000000"})
    forged["prev_hash"] = rows[1]["hash"]
    forged["hash"] = event_hash(forged, forged["prev_hash"])
    rows.insert(2, forged)
    # The forgery itself hashes correctly — it is the event AFTER it whose
    # prev_hash no longer matches. That is the property that matters: you
    # cannot splice without rewriting the remainder.
    assert verify(rows).ok is False


def test_reordering_two_events_breaks_the_chain():
    rows = chained(5)
    rows[1], rows[2] = rows[2], rows[1]
    assert verify(rows).ok is False


def test_truncating_the_tail_still_verifies_as_far_as_it_goes():
    """Removing the LAST events cannot be caught by the chain alone — nothing
    points at them. This documents the limit rather than pretending otherwise;
    catching it needs the seq counter, which is why the tip is stored."""
    rows = chained(5)[:3]
    assert verify(rows).ok is True


def test_a_chain_that_stops_halfway_is_a_break():
    """Deleting the chained tail and leaving unchained events after it."""
    rows = chained(3)
    rows.append(ev(4))                       # no hash at all
    r = verify(rows)
    assert r.ok is False
    assert "cannot stop and restart" in r.first_break["reason"]


def test_resealing_a_tampered_log_is_detectable_only_by_the_tip():
    """Someone with write access CAN recompute the whole chain. The chain
    converts silent edits into loud ones; it does not make the log
    unfalsifiable, and this test exists so nobody believes it does."""
    rows = chained(5)
    rows[2]["payload"]["qty"] = "9999"
    resealed = rechain(rows)
    assert verify(resealed).ok is True       # the chain alone cannot tell


# ------------------------------------------------- ledgers predating the chain
def test_unchained_events_are_not_reported_as_valid():
    rows = [ev(1), ev(2)]                    # no hashes
    r = verify(rows)
    assert r.ok is True                      # not a break
    assert r.chained == 0 and r.unchained == 2
    assert any("not proved" in n for n in r.notes)


def test_a_retrofit_verifies_from_the_first_chained_event():
    old = [ev(1), ev(2)]
    new = rechain([ev(3), ev(4)], start_hash=GENESIS_HASH)
    r = verify(old + new)
    assert r.ok is True
    assert r.unchained == 2 and r.chained == 2


def test_tampering_after_a_retrofit_is_still_caught():
    old = [ev(1)]
    new = rechain([ev(2), ev(3)])
    rows = old + new
    rows[2]["payload"]["qty"] = "1"
    assert verify(rows).ok is False


# ------------------------------------------------------------- canonicalisation
def test_key_order_does_not_change_the_hash():
    """A Firestore round trip does not preserve dict order, and a hash that
    depended on it would cry tampering on every read."""
    a = ev(1)
    b = {k: a[k] for k in reversed(list(a.keys()))}
    assert event_hash(a, GENESIS_HASH) == event_hash(b, GENESIS_HASH)


def test_nested_payload_order_does_not_change_the_hash():
    a = ev(1, payload={"symbol": "F", "qty": "10", "price": "13.87"})
    b = ev(1, payload={"price": "13.87", "qty": "10", "symbol": "F"})
    assert event_hash(a, GENESIS_HASH) == event_hash(b, GENESIS_HASH)


def test_the_stored_hash_is_not_itself_hashed():
    """Otherwise the hash would depend on itself and never be reproducible."""
    a = ev(1)
    a["hash"] = "whatever"
    b = ev(1)
    assert event_hash(a, GENESIS_HASH) == event_hash(b, GENESIS_HASH)


def test_prev_hash_is_part_of_the_hash():
    a = ev(1)
    assert event_hash(a, GENESIS_HASH) != event_hash(a, "f" * 64)


def test_canonical_is_stable_across_calls():
    a = ev(1)
    assert canonical(a, GENESIS_HASH) == canonical(copy.deepcopy(a), GENESIS_HASH)


def test_two_different_events_do_not_collide():
    assert event_hash(ev(1), GENESIS_HASH) != event_hash(ev(2), GENESIS_HASH)


# -------------------------------------------------------------------- rechain
def test_rechain_produces_a_verifying_chain():
    assert verify(rechain([ev(i) for i in range(1, 8)])).ok is True


def test_rechain_can_continue_from_an_existing_tip():
    first = rechain([ev(1), ev(2)])
    second = rechain([ev(3), ev(4)], start_hash=first[-1]["hash"])
    assert verify(first + second).ok is True


def test_rechain_does_not_mutate_its_input():
    rows = [ev(1), ev(2)]
    rechain(rows)
    assert "hash" not in rows[0]
