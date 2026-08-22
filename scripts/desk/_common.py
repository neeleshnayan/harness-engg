"""Shared plumbing for the desk query scripts — and the quirk list, once.

WHY THESE SCRIPTS EXIST. The secretary's end-of-day brief cost 80 tool uses,
26 minutes and 271k tokens, most of it re-deriving aggregates from 965 raw
events by hand; the CFO built the firm's first spend meter from a capped
payload and was silently truncated; the validator re-derived three findings
already on the desk. Every seat was re-learning the same Postgres quirks and
burning tool calls debugging them. So: vetted scripts a seat RUNS instead of
authoring, and the traps written down where they cannot be missed.

TWO SOURCES, AND THE SCRIPT ALWAYS SAYS WHICH ONE IT USED.

The spine is preferred: one HTTP call, no credentials, and the same arithmetic
the UI sees. Postgres is the fallback, because the spine has been observed
ALIVE AND LISTENING WHILE SERVING NOTHING (desk request d1d5beef, 2026-08-22)
and a seat with a deadline needs a path that does not depend on it. The source
is printed on every run: a number's provenance is part of the number.

THE QUIRKS. Each one cost somebody tool calls before it was written here.

  * Event types are **PascalCase** — ``OrderFilled``, ``NavStruck``,
    ``DeskRequested``. Not snake_case, not upper.
  * The column is ``type``, NOT ``event_type``.
  * ``ts`` is **TEXT**, not a timestamp. All 965 stored values are exactly 32
    characters ending ``+00:00``, so a string range works — but bound it with
    ``ts >= %s AND ts < %s`` and pass full ISO instants, never a bare date.
  * **A ``%`` inside a LIKE literal beside a ``%s`` placeholder raises**
    ``only '%s','%b','%t' are allowed``. Write ``LIKE 'Desk%%'``, or better,
    use ``= ANY(%s)`` with a list and avoid LIKE entirely.
  * The runs table's token column is ``tokens``, NOT ``tokens_used``.
  * ``DeskStore.runs(limit=…)`` is capped **across all seats** — the desk
    payload's 25 is a FLOOR wearing the costume of a count. Use
    ``/fund/desk/runs/stats`` or ``all_runs()``.
  * ``OrderFilled.avg_price`` is a JSON **string** on 22 of 29 live rows and a
    **number** on 7. Coerce through ``Decimal(str(x))`` or your sum will raise
    or concatenate.
  * **20 of 29 ``OrderFilled`` payloads carry no ``venue`` key.** Do not bucket
    them as paper.
  * **14 of 24 ``DeskDispatched`` events carry no ``request_id``** and one
    names a request that was never filed. Never fold them into a request
    table; they create a phantom row with a ``None`` id.
  * There is **no ``psql``** here. Use ``psycopg`` from the ClarkHarness venv:
    ``./venv/Scripts/python.exe -X utf8 scripts/desk/<script>.py``.
  * Postgres is ``127.0.0.1:5433``, database ``krypton_fund``, and the DSN is
    already in ``app.fund.pgstore.dsn()`` — do not retype it.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.request
from typing import Any, Optional

BASE = os.getenv("FUND_API_BASE", "http://127.0.0.1:8090/api/v1")

#: How long to wait on the spine before falling back. Short on purpose: a
#: wedged spine answers the TCP connect and then never replies, so a generous
#: timeout would make the fallback useless exactly when it is needed.
SPINE_TIMEOUT = float(os.getenv("FUND_API_TIMEOUT", "20"))

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _ensure_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


# AT IMPORT TIME, not inside stores(). A script's fallback `compute()` closure
# imports `app.fund.metrics`, and if the path were only set when stores() ran
# the import would raise ModuleNotFoundError the first time the spine was
# down — i.e. the fallback would fail in exactly the situation it exists for.
# Found by running the scripts against a spine that 404s, not by reading them.
_ensure_path()


def from_spine(path: str) -> Optional[dict[str, Any]]:
    """One GET, or None if the spine cannot serve it.

    None means "could not read", never "empty". Callers fall back to Postgres
    and SAY they did.
    """
    try:
        with urllib.request.urlopen(BASE + path, timeout=SPINE_TIMEOUT) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"# spine unreachable for {path}: {type(e).__name__}: {e}",
              file=sys.stderr)
        return None


def stores() -> tuple[Any, Any]:
    """(event store, run recorder) straight from Postgres.

    ``FUND_STORE`` is forced to postgres for this process only: these scripts
    read the operational log, and a script that silently answered from a
    Firestore fake would be worse than one that failed.
    """
    os.environ["FUND_STORE"] = "postgres"
    _ensure_path()
    from app.fund.pgstore import PostgresEventStore
    try:
        from app.fund.deskstore import DeskStore
        ds: Any = DeskStore()
    except Exception as e:  # noqa: BLE001
        print(f"# run recorder unreachable: {e} — run figures will read "
              f"UNKNOWN, which is not zero", file=sys.stderr)
        ds = None
    return PostgresEventStore(), ds


def fetch(path: str, compute) -> tuple[str, dict[str, Any]]:
    """Spine first, Postgres second. Returns (source, body).

    ``compute`` is a zero-argument callable that produces the same body from
    the database. Both paths run the SAME module functions — the scripts do
    not carry a second implementation of any fold, because two copies of an
    aggregate drift and the drift is invisible.
    """
    body = from_spine(path)
    if body is not None:
        return "spine", body
    return "postgres", compute()


def banner(source: str, what: str) -> str:
    return (f"# {what}   source={source}"
            + ("   (spine did not answer; read straight from Postgres)"
               if source == "postgres" else ""))


def usage(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def money(x: Any) -> str:
    """A dollar figure, or the word ABSENT. Never 0.00 for a missing value."""
    if x is None:
        return "ABSENT"
    try:
        return f"${float(x):,.2f}"
    except (TypeError, ValueError):
        return "UNREADABLE"


def num(x: Any) -> str:
    return "ABSENT" if x is None else f"{x:,}"
