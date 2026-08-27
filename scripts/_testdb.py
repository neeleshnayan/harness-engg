"""One name for every scratch database the suite creates — unique per worktree.

WHY, MEASURED (builder HW3, 2026-08-24; desk 9e1d9fb5). Thirty-six tests went
red across three Postgres-backed modules with **no defect behind any of them**:
``assert count() == 0`` immediately after a ``TRUNCATE``, while a second
builder's suite truncated the same database.

THE POPULATION IS GROWING AND BOTH READINGS ARE HERE, because a single count
goes quietly stale. The ticket said ten modules on 2026-08-24. Re-measured on
2026-08-27, immediately before this module was written: **``krypton_fund_test``
appears in 13 Postgres-touching test modules** (12 using it as their database,
one naming it in a forged sample), and **7 more had escaped into private
databases — by a FIXED name, so two worktrees collided there too**, one of them
using two. Reproduce by scanning ``tests/test_*.py`` for
``"krypton_fund_[a-z0-9_]+"`` in modules that import psycopg.

**THE SHARED RESOURCE IS THE NAME, NOT THE SERVER.** Two crews on one Postgres
are fine; two crews on one database name are not. ``scripts/suite_lock.py``
already makes concurrent suites correct by making them sequential; this makes
them correct AND parallel, which is what the constitution's two-builder rule
actually asked for.

The suffix comes from ``KF_TEST_DB_SUFFIX`` when set, and otherwise from a hash
of the repository root — so a worktree gets its own databases with no
coordination, no configuration and nothing for a builder to remember.

**IT REFUSES TO NAME A FUND LEDGER.** That is the whole safety property and it
is enforced here rather than trusted: the suite TRUNCATEs what these names
point at, and the first version of the mode work designated a real ledger as
pytest's scratch space — every run against a reachable Postgres would have
wiped the test fund's entire log. ``tests/test_fund_mode.py`` polices the same
boundary from the other side by scanning the suite's source; this closes the
door that a computed name would otherwise open behind that scan.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

#: Postgres truncates identifiers at 63 bytes, and a SILENT truncation is the
#: worst possible failure here: two long names would collapse onto one database
#: and reproduce the exact collision this module exists to end.
MAX_IDENTIFIER = 63

#: Eight hex characters. Enough that two worktrees on one host do not collide
#: (birthday odds at ten worktrees: ~1 in 10^8), short enough that every base
#: name in this suite stays well inside the identifier limit — the longest,
#: `krypton_fund_ticketstagingtest`, becomes 39 characters.
_TOKEN_CHARS = 8

_SAFE = re.compile(r"[^a-z0-9_]+")


class UnsafeDatabaseName(RuntimeError):
    """A computed scratch name would have collided with a real ledger."""


def _fund_ledgers() -> frozenset[str]:
    """Every database a FUND MODE writes its log to. Read, never re-typed.

    Imported lazily and defensively: this module is used by test collection,
    and a scratch name must still be computable in an environment where the
    mode module cannot be imported. When it cannot be read, the fallback is a
    literal copy of the three ledger names — which refuses at least as much as
    the live list, never less. An unreadable guard list must not open the door
    it guards, and ``test_an_unreadable_ledger_list_refuses_MORE_not_less``
    compares the fallback against the live list rather than against typed
    names, so a fourth mode makes that test fail rather than pass quietly.
    """
    try:
        from app.fund import mode as _mode
        return frozenset(_mode.MODES[m].pg_database for m in _mode.FundMode)
    except Exception:  # noqa: BLE001
        return frozenset({"krypton_fund", "krypton_fund_dev", "krypton_fund_prod"})


def worktree_token() -> str:
    """The per-worktree suffix. Explicit env first, else the tree's own path.

    Sanitised rather than trusted: this string is interpolated into
    ``CREATE DATABASE "..."`` by every module that uses it, so anything that is
    not a lowercase identifier character is removed before it can be.
    """
    raw = os.getenv("KF_TEST_DB_SUFFIX")
    if raw:
        cleaned = _SAFE.sub("", raw.strip().lower())
        if cleaned:
            return cleaned[:24]
        # An env var that sanitises to nothing is a MISCONFIGURATION, not an
        # instruction to share the default database with everyone else.
        raise UnsafeDatabaseName(
            f"KF_TEST_DB_SUFFIX={raw!r} contains no usable identifier "
            f"characters; it would silently fall back to the shared name")
    root = Path(__file__).resolve().parents[1]
    return hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:_TOKEN_CHARS]


def scratch_database(base: str) -> str:
    """``<base>_<worktree token>`` — this worktree's own database for ``base``.

    Refuses, rather than returns, when the result would name a fund ledger or
    would not survive Postgres's identifier limit.
    """
    clean = _SAFE.sub("", (base or "").strip().lower())
    if not clean:
        raise UnsafeDatabaseName(f"{base!r} is not a usable database name")
    name = f"{clean}_{worktree_token()}"
    if len(name) > MAX_IDENTIFIER:
        # Refuse rather than shorten. Shortening is what produces the collision
        # this module exists to prevent, and it would do it silently.
        raise UnsafeDatabaseName(
            f"{name!r} is {len(name)} characters, past Postgres's "
            f"{MAX_IDENTIFIER}-byte identifier limit — two such names would be "
            f"truncated onto ONE database, which is the collision this is "
            f"here to end. Shorten the base name")
    ledgers = _fund_ledgers()
    if name in ledgers or clean in ledgers:
        raise UnsafeDatabaseName(
            f"{name!r} names a FUND LEDGER ({sorted(ledgers)}). The suite "
            f"TRUNCATEs what these names point at; a scratch database is "
            f"never a fund's log")
    return name
