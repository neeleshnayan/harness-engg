"""In-memory Firestore fake for running the spine without firebase_admin.

``install()`` injects a fake ``firebase_admin`` (with a ``firestore`` module) into
sys.modules and puts the repo root on the path, so the app modules import and run
against an in-memory store. For tests/smoke scripts only.
"""

import pathlib
import sys
import types


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
        self._desc = direction == "DESC"
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
            rows.sort(key=lambda kv: kv[1].get(self._order), reverse=self._desc)
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
    def __init__(self):
        self._store = {}

    def collection(self, name):
        return _Collection(self, name)

    def transaction(self):
        return _Txn()


class _QueryConst:
    DESCENDING = "DESC"


def install():
    db = _DB()
    fake_fs = types.SimpleNamespace(
        client=lambda: db, transactional=lambda f: f, Query=_QueryConst
    )
    fake_admin = types.ModuleType("firebase_admin")
    fake_admin.firestore = fake_fs
    sys.modules["firebase_admin"] = fake_admin
    sys.modules["firebase_admin.firestore"] = fake_fs
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    return db
