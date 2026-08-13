"""In-memory + File-backed persistent Firestore for local dev & production fallback.

Data is loaded from `.firestore_local_db.json` on startup and saved synchronously
on mutation (doc set/update/delete), ensuring 100% persistence across restarts
without hitting external quota limits.
"""

from __future__ import annotations

import os
import shutil
import time
import json
import logging
from firebase_admin import firestore

logger = logging.getLogger(__name__)

#: How many previous ledgers to keep beside the live one, and how far apart.
#: 12 x 15 minutes covers about three hours — long enough to notice a problem
#: and roll back, short enough not to hoard copies of the whole event log.
_KEEP_BACKUPS = 12
_BACKUP_INTERVAL_SECONDS = float(os.getenv("LEDGER_BACKUP_INTERVAL_SECONDS", "900"))

_DB_FILEPATH = os.path.join(os.path.dirname(__file__), "../../.firestore_local_db.json")


class _Snap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _Query:
    def __init__(self, coll):
        self._coll = coll
        self._filters = []
        self._order = None
        self._desc = False
        self._limit = None

    def where(self, field, op, val):
        self._filters.append((field, op, val))
        return self

    def order_by(self, field, direction=None):
        self._order = field
        self._desc = direction == "DESCENDING"
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _match(self, d):
        for f, op, v in self._filters:
            x = d.get(f)
            if op == "==" and not (x == v):
                return False
            if op == ">" and not (x is not None and x > v):
                return False
        return True

    def stream(self):
        rows = [(k, v) for k, v in self._coll._docs.items() if self._match(v)]
        if self._order:
            rows.sort(key=lambda kv: kv[1].get(self._order) or "", reverse=self._desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return [_Snap(k, v) for k, v in rows]


class _Doc:
    def __init__(self, coll, doc_id):
        self._coll = coll
        self.id = doc_id

    def get(self, transaction=None):
        return _Snap(self.id, self._coll._docs.get(self.id))

    def set(self, data, merge=False):
        if merge and self.id in self._coll._docs:
            self._coll._docs[self.id].update(data)
        else:
            self._coll._docs[self.id] = dict(data)
        self._coll._db._save()

    def delete(self):
        if self.id in self._coll._docs:
            del self._coll._docs[self.id]
            self._coll._db._save()


class _Collection(_Query):
    def __init__(self, db, name):
        self._db = db
        self._docs = db._store.setdefault(name, {})
        super().__init__(self)

    def document(self, doc_id):
        return _Doc(self, doc_id)


class _Txn:
    def set(self, ref, data, merge=False):
        ref.set(data, merge=merge)


class _DB:
    def __init__(self, filepath: str = _DB_FILEPATH):
        self._filepath = filepath
        self._store: dict[str, dict] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self._filepath):
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                self._store = json.load(f)
            logger.info("Loaded persistent local Firestore DB from %s", self._filepath)
            return
        except Exception as e:
            # An unreadable ledger must NOT become an empty one. Starting blank
            # here used to look like a fresh fund, and the very next write
            # replaced the damaged file with `{}` — turning a recoverable parse
            # error into total, silent loss of the fund's entire history.
            #
            # So: move the bad file aside so nothing can overwrite it, point at
            # the newest backup if there is one, and refuse to start otherwise.
            quarantine = f"{self._filepath}.corrupt-{int(time.time())}"
            try:
                os.replace(self._filepath, quarantine)
            except OSError:
                quarantine = "(could not be moved aside)"
            newest = self._newest_backup()
            raise RuntimeError(
                f"local ledger at {self._filepath} could not be parsed ({e}). "
                f"It has been moved to {quarantine} so it cannot be overwritten. "
                + (f"The newest backup is {newest} — inspect it and copy it into "
                   "place deliberately." if newest else
                   "NO backup was found. Do not start the fund against an empty "
                   "ledger; recover the file first.")
            ) from e

    def _backup_paths(self) -> list[str]:
        d = os.path.dirname(self._filepath) or "."
        base = os.path.basename(self._filepath)
        try:
            names = [n for n in os.listdir(d) if n.startswith(base + ".bak")]
        except OSError:
            return []
        return sorted((os.path.join(d, n) for n in names), reverse=True)

    def _newest_backup(self) -> str | None:
        paths = self._backup_paths()
        return paths[0] if paths else None

    def _rotate_backup(self):
        """Keep a small ring of previous ledgers beside the live one.

        The event log is the fund's only record of what it owns and why. One
        file with no copies is a single delete away from having no fund, so each
        save first preserves the version it is about to replace.
        """
        if not os.path.exists(self._filepath):
            return
        # Spaced by time, not by write. Every appended event triggers a save, so
        # a copy-per-save would fill the whole ring within seconds and leave the
        # fund with ten near-identical backups covering no useful history.
        newest = self._newest_backup()
        if newest is not None:
            try:
                if time.time() - os.path.getmtime(newest) < _BACKUP_INTERVAL_SECONDS:
                    return
            except OSError:
                pass
        try:
            shutil.copy2(self._filepath, f"{self._filepath}.bak-{int(time.time())}")
        except OSError as e:
            logger.warning("Could not write ledger backup: %s", e)
            return
        for old in self._backup_paths()[_KEEP_BACKUPS:]:
            try:
                os.remove(old)
            except OSError:
                pass

    def _save(self):
        try:
            self._rotate_backup()
            tmp = self._filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._store, f, indent=2, default=str)
            os.replace(tmp, self._filepath)
        except Exception as e:
            logger.error("Failed to save local Firestore DB: %s", e)

    def collection(self, name):
        return _Collection(self, name)

    def transaction(self):
        return _Txn()


class _QueryConst:
    DESCENDING = "DESCENDING"
    ASCENDING = "ASCENDING"


_INSTANCE = _DB()


def install_fake() -> None:
    firestore.client = lambda *a, **k: _INSTANCE  # type: ignore[assignment]
    firestore.transactional = lambda f: f  # type: ignore[assignment]
    firestore.Query = _QueryConst  # type: ignore[assignment]
