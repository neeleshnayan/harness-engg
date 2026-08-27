"""Scratch databases are named per worktree, and can never name a fund ledger.

THE INCIDENT (builder HW3, 2026-08-24; desk 9e1d9fb5): thirty-six tests went
red across three Postgres-backed modules with **no defect behind any of them**
— `assert count() == 0` immediately after a TRUNCATE, while a second builder's
suite truncated the same database. `krypton_fund_test` was a constant in ten
modules and six others had escaped into private databases by a FIXED name, so
two worktrees collided there too. **The shared resource is the NAME.**

THE HAZARD THE REPAIR CREATES, and the reason half this file exists: moving the
name out of the source and into a computed helper opens a door that
`tests/test_fund_mode.py`'s source scan cannot see through. That scan polices
"no destructive test module names a fund ledger" by reading the suite's text;
a name assembled at runtime is not in the text. So the helper REFUSES to
produce a ledger name, and the refusal is tested here rather than trusted.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from _testdb import (  # noqa: E402
    MAX_IDENTIFIER,
    UnsafeDatabaseName,
    scratch_database,
    worktree_token,
)

ROOT = Path(__file__).resolve().parents[1]


def _ledgers():
    from app.fund import mode as m
    return sorted({m.MODES[k].pg_database for k in m.FundMode})


#: Read ONCE, at import, so a test that deliberately breaks the mode import
#: still has something honest to compare against.
REAL_LEDGERS = _ledgers()


# --- the name is this worktree's, and only this worktree's ----------------

def test_the_name_carries_a_suffix_and_is_not_the_bare_shared_one():
    name = scratch_database("krypton_fund_test")
    assert name != "krypton_fund_test"
    assert name.startswith("krypton_fund_test_")


def test_two_worktrees_get_two_names(monkeypatch):
    monkeypatch.setenv("KF_TEST_DB_SUFFIX", "crew_one")
    one = scratch_database("krypton_fund_test")
    monkeypatch.setenv("KF_TEST_DB_SUFFIX", "crew_two")
    two = scratch_database("krypton_fund_test")
    assert one != two
    # The whole point, stated as the property rather than as two strings: the
    # collision that cost 36 red tests is impossible when these differ.
    assert one == "krypton_fund_test_crew_one"
    assert two == "krypton_fund_test_crew_two"


def test_the_same_worktree_gets_the_same_name_every_time(monkeypatch):
    """Otherwise a fixture would create one database and truncate another."""
    monkeypatch.delenv("KF_TEST_DB_SUFFIX", raising=False)
    assert scratch_database("krypton_fund_test") == scratch_database("krypton_fund_test")
    assert worktree_token() == worktree_token()


def test_the_default_token_comes_from_the_TREE_not_from_a_constant(monkeypatch):
    """MOVED, not compared — and the first version of this test did NOT move.

    Found by mutation (M66): replacing the whole derivation with the literal
    `"524fc383"` survived, because that IS the hash of this worktree's path and
    the assertion only ever compared the function against a re-computation of
    the same input. An assertion that a value equals its source cannot tell a
    read from a hardcoded duplicate that happens to agree today.

    So the INPUT is moved. The token is derived from this module's own
    location, so pointing the module somewhere else must change it — a
    constant cannot follow.
    """
    import hashlib

    import _testdb

    monkeypatch.delenv("KF_TEST_DB_SUFFIX", raising=False)
    here = worktree_token()
    assert here == hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:8]

    monkeypatch.setattr(_testdb, "__file__",
                        str(Path("/some/other/worktree/scripts/_testdb.py")))
    moved = worktree_token()
    assert moved != here, (
        "the token did not follow the tree — it is a constant, not a "
        "derivation, and two worktrees would share their databases again")
    # `.resolve()` is what the helper applies, and on Windows it turns
    # `/some/other/worktree` into `C:\some\other\worktree` — so the expectation
    # is computed through the same call rather than through the string handed
    # in. A test that re-typed the path would be measuring the platform.
    elsewhere = Path("/some/other/worktree/scripts/_testdb.py").resolve().parents[1]
    assert moved == hashlib.sha256(str(elsewhere).encode("utf-8")).hexdigest()[:8]


# --- it can never name a fund ledger --------------------------------------

def test_every_fund_ledger_is_REFUSED_not_returned(monkeypatch):
    """The suite TRUNCATEs what these names point at.

    v1 of the mode work designated a real ledger as pytest's scratch space and
    every run against a reachable Postgres would have wiped the test fund's
    entire log. `test_fund_mode.py` polices that from the source side; a
    computed name walks around a source scan, so the door is shut here.

    THE LEDGER NAMES ARE READ, NOT TYPED, and that is not only hygiene: this
    module names Postgres and destructive SQL, so `test_fund_mode.py`'s scan
    POLICES IT — writing the ledgers out here would make this file an offender
    against the very guard it is reinforcing. It fired on the first run.
    """
    ledgers = _ledgers()
    assert len(ledgers) >= 3      # DOMAIN: a loop over nothing proves nothing
    for ledger in ledgers:
        base, _, suffix = ledger.rpartition("_")
        # Force the computed name to land exactly on the ledger.
        monkeypatch.setenv("KF_TEST_DB_SUFFIX", suffix or "x")
        target = base if base else ledger
        with pytest.raises(UnsafeDatabaseName) as e:
            scratch_database(target if base else ledger)
        assert "FUND LEDGER" in str(e.value)


def test_a_ledger_BASE_is_refused_even_when_the_suffix_would_make_it_safe():
    """Found by mutation (M61). `krypton_fund_<token>` is not itself a ledger,
    so only the suffixed check fired and dropping `clean in ledgers` survived.

    Asking for a ledger as the BASE is a mistake whatever the suffix turns it
    into, and it is the exact call a copy-paste from a fixture would produce.
    """
    ledger = sorted(_ledgers(), key=len)[0]
    with pytest.raises(UnsafeDatabaseName) as e:
        scratch_database(ledger)
    assert "FUND LEDGER" in str(e.value)


def test_the_ledger_list_is_READ_from_the_mode_module_not_re_typed():
    """A hardcoded copy would stop refusing the day a mode is added."""
    from _testdb import _fund_ledgers
    assert set(_fund_ledgers()) == set(_ledgers())


def test_an_unreadable_ledger_list_refuses_MORE_not_less(monkeypatch):
    """An absent guard list must not become an open door.

    THE FIRST VERSION OF THIS TEST WAS VACUOUS, and mutation (M64) is what
    said so: it set ``sys.modules["app.fund.mode"] = None`` and expected the
    import to fail. It does not — ``from app.fund import mode`` finds the
    attribute already bound on the package and never consults ``sys.modules``
    at all, so the test was reading the REAL ledger list and asserting it
    against itself. Emptying the fallback survived.

    Both doors have to be shut: the attribute AND the module entry.
    """
    import app.fund as fund_pkg

    import _testdb

    monkeypatch.delattr(fund_pkg, "mode", raising=False)
    monkeypatch.setitem(sys.modules, "app.fund.mode", None)
    fallback = _testdb._fund_ledgers()
    assert fallback, "the fallback is EMPTY — an unreadable list opened the door"
    # Compared against the real list, read before the doors were shut.
    assert set(REAL_LEDGERS) <= set(fallback)


# --- the suffix is sanitised, and silence is not an option -----------------

@pytest.mark.parametrize("raw,expect", [
    ("Crew-One", "crewone"),
    ("  b1  ", "b1"),
    # A ledger name is deliberately NOT used as the injection payload: this
    # module is policed by `test_fund_mode.py`'s source scan, and a sample
    # naming a real ledger would make the sample an offence.
    ('a"; DROP DATABASE somewhere_else; --', "adropdatabasesomewhere_else"),
])
def test_the_suffix_is_sanitised_before_it_reaches_CREATE_DATABASE(raw, expect,
                                                                  monkeypatch):
    """It is interpolated into `CREATE DATABASE "..."` by every module that
    uses it, so anything that is not an identifier character is removed."""
    monkeypatch.setenv("KF_TEST_DB_SUFFIX", raw)
    assert worktree_token() == expect[:24]


def test_a_suffix_that_sanitises_to_nothing_REFUSES(monkeypatch):
    """It must not fall back to the shared default — that is the collision
    coming back through the configuration."""
    monkeypatch.setenv("KF_TEST_DB_SUFFIX", "!!!")
    with pytest.raises(UnsafeDatabaseName):
        worktree_token()


def test_a_name_past_postgres_identifier_limit_REFUSES_rather_than_shortens():
    """Postgres truncates silently at 63 bytes, and two truncated names would
    collapse onto ONE database — the exact collision this ends."""
    with pytest.raises(UnsafeDatabaseName) as e:
        scratch_database("krypton_fund_" + "x" * 60)
    assert str(MAX_IDENTIFIER) in str(e.value)


def test_a_legitimate_name_is_comfortably_inside_the_limit():
    """The other half: the refusal above must not be firing on real names."""
    longest = "krypton_fund_ticketstagingtest"      # the longest base in the suite
    assert len(scratch_database(longest)) <= MAX_IDENTIFIER


@pytest.mark.parametrize("bad", ["", "   ", "!!!"])
def test_an_unusable_base_refuses(bad):
    with pytest.raises(UnsafeDatabaseName):
        scratch_database(bad)


# --- the suite really did stop hardcoding the name ------------------------

def test_no_destructive_test_module_still_hardcodes_a_scratch_database_name():
    """The regression pin. A module that reverts to the literal shares its
    database with every other worktree again, silently.

    Two modules are excluded with their reasons rather than by being forgotten:
    `test_fund_mode.py` is the ledger scanner and forges module text on
    purpose, and this file quotes the names it asserts about.
    """
    excluded = {"test_fund_mode.py", Path(__file__).name}
    offenders = []
    scanned = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if path.name in excluded:
            continue
        text = path.read_text(encoding="utf-8")
        if "psycopg" not in text:
            continue
        scanned += 1
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "scratch_database(" in stripped:
                continue
            if '"krypton_fund_' in stripped or "'krypton_fund_" in stripped:
                offenders.append(f"{path.name}: {stripped[:90]}")
    assert not offenders, ("a scratch database name is hardcoded again: "
                           + "; ".join(offenders))
    # DOMAIN. A pass over nothing proves nothing, and the glob is exactly the
    # thing that could silently stop matching.
    assert scanned >= 18, (
        f"only {scanned} Postgres-touching modules were scanned; there were 20 "
        f"when this was written, so the scan is looking in the wrong place")
