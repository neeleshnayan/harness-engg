"""The durability snapshot must actually work, not merely be scheduled.

"Built but never scheduled" turned out to be "built, never scheduled, and
broken": the snapshot called `db.batch()`, the local Firestore shim had no such
method, and the fund's only second copy of the event log had therefore never been
written. The scheduler was one missing half; this was the other.
"""

import json

import pytest

from app.core.dev_firestore import _DB


def _db(tmp_path):
    return _DB(filepath=str(tmp_path / "ledger.json"))


def test_a_batch_writes_every_document(tmp_path):
    db = _db(tmp_path)
    b = db.batch()
    for i in range(3):
        b.set(db.collection("events").document(f"e{i}"), {"seq": i})
    assert b.commit() == 3
    for i in range(3):
        assert db.collection("events").document(f"e{i}").get().to_dict() == {"seq": i}


def test_a_batch_survives_a_reload(tmp_path):
    """The whole point is a second copy on disk. A batch that only mutated memory
    would report success and protect nothing."""
    path = str(tmp_path / "ledger.json")
    db = _DB(filepath=path)
    b = db.batch()
    b.set(db.collection("events").document("e1"), {"seq": 1, "hash": "abc"})
    b.commit()

    reopened = _DB(filepath=path)
    assert reopened.collection("events").document("e1").get().to_dict() == {
        "seq": 1, "hash": "abc"}


def test_a_batch_writes_the_file_once_not_once_per_document(tmp_path, monkeypatch):
    """`_Doc.set` saves the whole store per document, so an unbatched push of 500
    events would rewrite the entire ledger 500 times and rotate 500 backups.

    Counts actual FILE REPLACEMENTS rather than calls to `_save`: the suppression
    makes `_save` return early, so counting invocations would pass whether or not
    anything was suppressed and prove nothing.
    """
    import app.core.dev_firestore as devfs

    db = _db(tmp_path)
    writes = {"n": 0}
    real_replace = devfs.os.replace

    def counting_replace(src, dst):
        if str(dst).endswith("ledger.json"):
            writes["n"] += 1
        return real_replace(src, dst)

    monkeypatch.setattr(devfs.os, "replace", counting_replace)
    b = db.batch()
    for i in range(10):
        b.set(db.collection("events").document(f"e{i}"), {"seq": i})
    b.commit()
    assert writes["n"] == 1, f"rewrote the ledger {writes['n']} times for one commit"


def test_saving_resumes_after_a_commit(tmp_path):
    """The suspend flag must not leak past the batch, or every later write would
    silently stop persisting — a far worse bug than the one being fixed."""
    db = _db(tmp_path)
    db.batch().set(db.collection("events").document("e1"), {"seq": 1}).commit()
    assert db._suspend_save is False
    db.collection("events").document("e2").set({"seq": 2})
    reopened = _DB(filepath=db._filepath)
    assert reopened.collection("events").document("e2").get().exists


def test_a_failing_write_does_not_leave_saving_suspended(tmp_path):
    """If an exception escaped with the flag set, the ledger would stop
    persisting and nothing would say so."""
    db = _db(tmp_path)
    b = db.batch()

    class Exploding:
        def set(self, data, merge=False):
            raise RuntimeError("disk on fire")

    b._writes.append((Exploding(), {"a": 1}, False))
    with pytest.raises(RuntimeError):
        b.commit()
    assert db._suspend_save is False
