"""The snapshot's off-switch must be the DOCUMENTED return, never an exception.

The incident (ticket 14a796d8, filed by the CEO 2026-08-23): `run_snapshot`
guarded on `store_backend()` while `fund.py` imported only `EventStore` — a
NameError on the guard's first name. The worker's catch-all logged
"snapshot skipped: name 'store_backend' is not defined" **476 times in one
night**, and both snapshot endpoints 500'd. The tick LOOKED like the intended
off-switch — same log prefix, same cadence — while the durability mirror was
dead. A skip that happens via an exception is indistinguishable in the log
from a skip that happens on purpose, which is why the fix (81a32336, one
import) ships with these tests rather than alone.

Three pins, one per way the incident could return:

1. The guard's names RESOLVE — a NameError anywhere in `run_snapshot` is a
   failure even when a catch-all upstream would have swallowed it.
2. The non-postgres path returns the DOCUMENTED skip dict, raising nothing.
3. The endpoint twin (`snapshot_run`) refuses non-postgres with its
   documented 503, not a NameError-shaped 500.
"""

from unittest import mock

from fastapi import HTTPException

import pytest

from app.api.v1 import fund as fund_router


def test_run_snapshot_names_resolve_without_a_catchall():
    """The exact incident: `store_backend` must be resolvable in fund.py.

    Calls `run_snapshot` with the backend mocked to the non-postgres arm, so
    the guard line — the line that NameError'd 476 times — executes outside
    any try block. A NameError here fails the test; in production it was
    swallowed by the worker's catch-all and impersonated the off-switch.
    """
    with mock.patch.object(fund_router, "store_backend",
                           return_value="firestore"):
        out = fund_router.run_snapshot()
    assert out == {"skipped": "the snapshot copies FROM postgres"}


def test_the_off_switch_is_a_return_not_an_exception():
    """The documented skip carries the documented sentence, and raises nothing.

    The log line "snapshot skipped: <exception>" is the FAILURE shape; the
    off-switch shape is a clean return the worker never logs a warning for.
    If this raises, the two shapes have collapsed back into one.
    """
    with mock.patch.object(fund_router, "store_backend",
                           return_value="firestore"):
        try:
            out = fund_router.run_snapshot()
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"the off-switch raised {type(e).__name__}: {e} — "
                        "a skip via exception is the 14a796d8 incident")
    assert "skipped" in out
    assert "postgres" in out["skipped"]


def test_snapshot_run_endpoint_refuses_with_503_not_a_nameerror_500():
    """The endpoint twin guards on the same name and 500'd the same night.

    Its documented refusal is a 503 with the same sentence; a NameError
    would surface as an unhandled 500 with no sentence at all.
    """
    with mock.patch.object(fund_router, "store_backend",
                           return_value="firestore"):
        with pytest.raises(HTTPException) as exc:
            fund_router.snapshot_run(dry_run=True)
    assert exc.value.status_code == 503
    assert "postgres" in exc.value.detail


def test_snapshot_status_endpoint_refuses_the_same_way():
    """Third caller of the same guard, pinned so a fourth cannot regress it."""
    with mock.patch.object(fund_router, "store_backend",
                           return_value="firestore"):
        with pytest.raises(HTTPException) as exc:
            fund_router.snapshot_status()
    assert exc.value.status_code == 503
