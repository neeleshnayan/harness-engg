"""One scheduler at a time, across processes that cannot see each other."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.fund.lease import SchedulerLease, identity


class FakeTxn:
    def __init__(self, db):
        self._db = db

    def set(self, ref, data, merge=False):
        ref.set(data, merge=merge)


class FakeSnap:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class FakeRef:
    def __init__(self, store, key):
        self._store = store
        self._key = key

    def get(self, transaction=None):
        if self._store.get("__raise__"):
            raise RuntimeError("firestore unreachable")
        return FakeSnap(self._store.get(self._key))

    def set(self, data, merge=False):
        cur = dict(self._store.get(self._key) or {}) if merge else {}
        cur.update(data)
        self._store[self._key] = cur


class FakeColl:
    def __init__(self, store, name):
        self._store, self._name = store, name

    def document(self, doc_id):
        return FakeRef(self._store, f"{self._name}/{doc_id}")


class FakeDB:
    """One dict shared by every 'process' — that is the whole point."""

    def __init__(self, store=None):
        self.store = store if store is not None else {}

    def collection(self, name):
        return FakeColl(self.store, name)

    def transaction(self):
        return FakeTxn(self)


@pytest.fixture(autouse=True)
def _no_real_firestore(monkeypatch):
    """The lease imports firestore.transactional inside its methods."""
    import firebase_admin.firestore as fs
    monkeypatch.setattr(fs, "transactional", lambda f: f, raising=False)


def lease(db, owner, ttl=180):
    return SchedulerLease(db=db, ttl_seconds=ttl, owner=owner)


# ------------------------------------------------------------- the core rule
def test_the_first_process_takes_a_free_lease():
    db = FakeDB()
    s = lease(db, "a").acquire()
    assert s.held is True and "free" in s.reason


def test_a_second_process_does_not_get_it():
    db = FakeDB()
    lease(db, "a").acquire()
    s = lease(db, "b").acquire()
    assert s.held is False
    assert s.holder == "a"


def test_the_holder_can_renew_indefinitely():
    db = FakeDB()
    a = lease(db, "a")
    a.acquire()
    s = a.acquire()
    assert s.held is True and s.reason == "renewed"


def test_renewing_does_not_let_a_rival_in():
    db = FakeDB()
    a = lease(db, "a")
    a.acquire()
    a.acquire()
    assert lease(db, "b").acquire().held is False


def test_two_processes_cannot_both_hold_it():
    db = FakeDB()
    results = [lease(db, f"p{i}").acquire().held for i in range(5)]
    assert results.count(True) == 1


# ------------------------------------------------------------------ expiry
def test_an_expired_lease_is_taken_over():
    """A lock held by a dead process is held forever; a lease is not."""
    db = FakeDB()
    lease(db, "dead").acquire()
    db.store["fund_meta/scheduler_lease"]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    s = lease(db, "live").acquire()
    assert s.held is True and "expired" in s.reason


def test_a_lease_expiring_in_the_future_is_respected():
    db = FakeDB()
    lease(db, "a").acquire()
    db.store["fund_meta/scheduler_lease"]["expires_at"] = (
        datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
    assert lease(db, "b").acquire().held is False


def test_an_unreadable_expiry_does_not_lock_the_scheduler_out_forever():
    """A corrupt field must not become an eternal lease with no way back."""
    db = FakeDB()
    lease(db, "a").acquire()
    db.store["fund_meta/scheduler_lease"]["expires_at"] = "garbage"
    s = lease(db, "b").acquire()
    assert s.held is True and "unreadable expiry" in s.reason


def test_the_ttl_is_written_into_the_future():
    db = FakeDB()
    lease(db, "a", ttl=120).acquire()
    exp = datetime.fromisoformat(db.store["fund_meta/scheduler_lease"]["expires_at"])
    assert exp > datetime.now(timezone.utc) + timedelta(seconds=100)


# ------------------------------------------------------------------ release
def test_releasing_lets_the_next_process_start_immediately():
    db = FakeDB()
    a = lease(db, "a")
    a.acquire()
    a.release()
    assert lease(db, "b").acquire().held is True


def test_a_non_holder_cannot_evict_the_holder_on_its_way_out():
    """The dangerous version of release: a losing process deleting the doc."""
    db = FakeDB()
    lease(db, "a").acquire()
    loser = lease(db, "b")
    loser.acquire()
    loser.release()
    assert db.store["fund_meta/scheduler_lease"]["owner"] == "a"


def test_release_clears_our_held_flag():
    db = FakeDB()
    a = lease(db, "a")
    a.acquire()
    assert a.held is True
    a.release()
    assert a.held is False


# ------------------------------------------------- when firestore is unreachable
def test_an_unreachable_lease_means_we_do_not_run():
    """The case where we know least is the case where we must not double-write."""
    db = FakeDB({"__raise__": True})
    s = lease(db, "a").acquire()
    assert s.held is False
    assert "unreadable" in s.reason


def test_an_unreachable_lease_does_not_leave_a_stale_held_flag():
    db = FakeDB()
    a = lease(db, "a")
    a.acquire()
    assert a.held is True
    db.store["__raise__"] = True
    a.acquire()
    assert a.held is False


# ------------------------------------------------------------------- state
def test_state_reports_who_holds_it_without_taking_it():
    db = FakeDB()
    lease(db, "a").acquire()
    b = lease(db, "b")
    s = b.state()
    assert s.held is False and s.holder == "a"
    # ...and asking did not steal it
    assert db.store["fund_meta/scheduler_lease"]["owner"] == "a"


def test_state_on_a_free_lease_says_free():
    assert lease(FakeDB(), "a").state().reason == "free"


def test_state_treats_an_expired_lease_as_free():
    db = FakeDB()
    lease(db, "a").acquire()
    db.store["fund_meta/scheduler_lease"]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert lease(db, "b").state().reason == "free"


# ---------------------------------------------------------------- identity
def test_identity_names_a_host_and_pid_an_operator_can_act_on():
    """A bare uuid says someone else holds it but not where to go stop it."""
    who = identity()
    assert who.count("/") == 2 and who.split("/")[1].isdigit()


def test_two_identities_are_distinct():
    assert identity() != identity()
