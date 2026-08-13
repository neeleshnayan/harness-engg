"""The local ledger is the fund's only record. Losing it loses the fund."""

from __future__ import annotations

import json
import os
import time

import pytest

from app.core.dev_firestore import _KEEP_BACKUPS, _DB


def db_at(tmp_path, name="ledger.json"):
    return _DB(filepath=str(tmp_path / name))


def test_a_missing_file_starts_empty():
    """A fund that has never run has no ledger, and that is fine."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        db = _DB(filepath=os.path.join(d, "nothing-here.json"))
        assert db._store == {}


def test_a_valid_file_round_trips(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"events": {"e1": {"seq": 1}}}), encoding="utf-8")
    assert _DB(filepath=str(p))._store["events"]["e1"]["seq"] == 1


# ------------------------------------------------------- corruption handling
def test_a_corrupt_ledger_refuses_to_start(tmp_path):
    """The bug this replaces: a parse error silently became an EMPTY fund, and
    the next write overwrote the damaged file with `{}`."""
    p = tmp_path / "ledger.json"
    p.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(RuntimeError) as e:
        _DB(filepath=str(p))
    assert "could not be parsed" in str(e.value)


def test_a_corrupt_ledger_is_moved_aside_so_it_cannot_be_overwritten(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("{ broken", encoding="utf-8")
    with pytest.raises(RuntimeError):
        _DB(filepath=str(p))
    assert not p.exists()
    quarantined = [f for f in os.listdir(tmp_path) if ".corrupt-" in f]
    assert len(quarantined) == 1
    # The original bytes survive for recovery.
    assert "broken" in (tmp_path / quarantined[0]).read_text(encoding="utf-8")


def test_the_error_names_a_backup_when_one_exists(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("{ broken", encoding="utf-8")
    (tmp_path / "ledger.json.bak-100").write_text('{"events": {}}', encoding="utf-8")
    with pytest.raises(RuntimeError) as e:
        _DB(filepath=str(p))
    assert "newest backup" in str(e.value)


def test_the_error_says_so_when_there_is_no_backup(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text("{ broken", encoding="utf-8")
    with pytest.raises(RuntimeError) as e:
        _DB(filepath=str(p))
    assert "NO backup was found" in str(e.value)


# ------------------------------------------------------------------ backups
def test_saving_preserves_the_previous_version(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"events": {"old": {"seq": 1}}}), encoding="utf-8")
    db = _DB(filepath=str(p))
    db._store = {"events": {"new": {"seq": 2}}}
    db._save()

    baks = [f for f in os.listdir(tmp_path) if ".bak-" in f]
    assert len(baks) == 1
    # The backup holds what was there BEFORE the save.
    assert "old" in (tmp_path / baks[0]).read_text(encoding="utf-8")
    assert "new" in p.read_text(encoding="utf-8")


def test_backups_are_spaced_by_time_not_per_write(tmp_path, monkeypatch):
    """Every appended event triggers a save; a copy per save would fill the ring
    in seconds and cover no useful history."""
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"events": {}}), encoding="utf-8")
    db = _DB(filepath=str(p))
    for i in range(25):
        db._store = {"events": {f"e{i}": {"seq": i}}}
        db._save()
    assert len([f for f in os.listdir(tmp_path) if ".bak-" in f]) == 1


def test_the_backup_ring_is_bounded(tmp_path, monkeypatch):
    import app.core.dev_firestore as mod
    monkeypatch.setattr(mod, "_BACKUP_INTERVAL_SECONDS", 0.0)
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"events": {}}), encoding="utf-8")
    db = _DB(filepath=str(p))
    for i in range(_KEEP_BACKUPS + 8):
        db._store = {"events": {f"e{i}": {"seq": i}}}
        db._save()
        time.sleep(0.01)
    assert len([f for f in os.listdir(tmp_path) if ".bak-" in f]) <= _KEEP_BACKUPS + 1


def test_a_failed_backup_does_not_block_the_save(tmp_path, monkeypatch):
    """Losing a backup is bad; losing the write that backup protects is worse."""
    import app.core.dev_firestore as mod
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps({"events": {}}), encoding="utf-8")
    db = _DB(filepath=str(p))

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(mod.shutil, "copy2", boom)
    monkeypatch.setattr(mod, "_BACKUP_INTERVAL_SECONDS", 0.0)

    db._store = {"events": {"kept": {"seq": 9}}}
    db._save()
    assert "kept" in p.read_text(encoding="utf-8")
