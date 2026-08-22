"""ITEM 7 (desk b72847bc): the ledger flag no longer moves the order path.

INCIDENT, 2026-08-21: ``.env`` flipped ``USE_FAKE_FIRESTORE`` from 1 to 0 as a
DURABILITY change. ``_mock_mode()`` read the same variable and it sat in the
middle of a four-branch connector ternary (``app/api/v1/fund.py:151-163``), so
one environment variable named for the ledger silently re-routed order
EXECUTION to a real Alpaca account. Nobody decided that; a flag did. The
fourth branch of the same ternary was worse: with no API key present, orders
went to a SIMULATOR and the book moved as though they were real.

WHY THIS FILE EXISTS AT ALL. The D11 v2 diff closed the item, and the D17
dispatch VERIFIED it was closed — by reading the code and observing that the
cited lines no longer exist. That verification produced no artifact, so it was
unreviewable: a claim that a defect is gone, resting on someone's reading. The
adversary said so in one line — a verification item with no recorded artifact
is unreviewable — and this file is the assertion, made executable.

It asserts three things, and the first is the one that matters:

  1. ``USE_FAKE_FIRESTORE`` has NO executable reference anywhere in ``app/``.
     Not "it is no longer consulted for the venue" — the flag is gone as an
     input, and only prose remembers it. The interlock it used to key was
     re-keyed onto the mode (``app/core/firebase.py::_is_test_mode``), not
     deleted, because the state it guarded against still exists.
  2. The venue is chosen ONLY from the declared mode. Moved, not asserted in
     place: the flag is set to every value it ever held and the connector must
     not change.
  3. The four-branch ternary is gone — ``app/api/v1/fund.py`` constructs no
     connector at all, so there is one order path and it is
     ``venue.build_connector``.
"""

from __future__ import annotations

import ast
import os
import pathlib

import pytest

from app.fund import mode as m
from app.fund.venue import build_connector

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: The variable that used to decide the venue while naming the ledger. Anything
#: with the same shape belongs here; each entry is a name that must not be read
#: by executable code anywhere in ``app/``.
RETIRED_MODE_FLAGS = ("USE_FAKE_FIRESTORE",)


def _executable_references(name: str) -> list[str]:
    """Every EXECUTABLE mention of ``name`` in ``app/``. Prose does not count.

    Docstrings and comments mentioning the flag are wanted — they carry the
    incident — so this reads the AST rather than the text, and looks in the
    four places a flag can actually be consulted: a bare name, an attribute, an
    import, and a string handed to ``os.getenv`` / ``os.environ.get`` / a
    subscript of ``os.environ``.
    """
    hits: list[str] = []
    unparseable: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as e:
            # A file this scanner cannot read is REPORTED, never counted as
            # clean. "I could not look" and "there is nothing there" are the
            # same two facts the drift alarm exists to keep apart.
            unparseable.append(f"{rel} ({type(e).__name__})")
            continue
        for node in ast.walk(tree):
            where = f"{rel}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.Name) and node.id == name:
                hits.append(f"{where} (name)")
            elif isinstance(node, ast.Attribute) and node.attr == name:
                hits.append(f"{where} (attribute)")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if any(a.name == name for a in node.names):
                    hits.append(f"{where} (import)")
            elif isinstance(node, ast.Constant) and node.value == name:
                # A string literal equal to the flag name — the shape an
                # os.getenv("...") read takes. Reported wherever it appears,
                # because a literal lookup is a consultation whatever wraps it.
                hits.append(f"{where} (string literal)")
    assert not unparseable, f"the reference scanner could not read: {unparseable}"
    return hits


@pytest.mark.parametrize("flag", RETIRED_MODE_FLAGS)
def test_the_retired_ledger_flag_has_NO_executable_reference(flag):
    """THE ASSERTION D17 MADE BY READING, executed.

    Fails loudly if anything ever consults this variable again — which is the
    only way the 2026-08-21 conflation can return.
    """
    refs = _executable_references(flag)
    assert refs == [], (
        f"{flag} is read by executable code again. It named the ledger and "
        f"selected the venue once; a fund that routes orders on a durability "
        f"flag routes them by accident. Sites: {refs}")


def test_the_scanner_itself_finds_a_name_that_IS_used():
    """The scanner's falsifier. A check that passes because its matcher is
    broken is worth less than no check, so prove the matcher fires on a name
    the code demonstrably does read."""
    assert _executable_references("ALPACA_API_KEY"), (
        "the reference scanner found nothing for a variable app/ certainly "
        "reads — it is not looking")


@pytest.mark.parametrize("flag_value", ["1", "0", "true", "false", ""])
def test_the_venue_is_INVARIANT_under_the_ledger_flag(monkeypatch, flag_value):
    """MOVE THE FLAG. Asserting "alpaca-paper builds an AlpacaConnector" cannot
    distinguish a mode-driven choice from one that happens to agree with the
    flag's current value. So set the flag to every value it has ever held and
    require the answer not to move.

    ``alpaca-paper`` is the mode used here because it is the one the incident
    actually re-routed, and because building it touches no ledger — a
    construction failure could not be mistaken for a routing change.
    """
    monkeypatch.setenv("USE_FAKE_FIRESTORE", flag_value)
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")

    conn = build_connector(m.MODES[m.FundMode.ALPACA_PAPER])

    assert type(conn).__name__ == "AlpacaConnector"
    # `name` is the connector's own identity attribute, and paper-vs-live is
    # derived from the MODE rather than from the retired ALPACA_PAPER variable.
    assert conn.name == "alpaca"
    assert conn._paper is True


@pytest.mark.parametrize("flag_value", ["1", "0", ""])
def test_the_SIMULATED_venue_is_invariant_too(monkeypatch, flag_value):
    """The other side of the old ternary. Test mode must resolve to the
    simulated venue whatever the ledger flag says — asserted on the SPEC rather
    than on a constructed connector so a firestore-fake interlock cannot be
    mistaken for a routing decision."""
    monkeypatch.setenv("USE_FAKE_FIRESTORE", flag_value)
    assert m.MODES[m.FundMode.TEST].venue_kind is m.VenueKind.SIMULATED


def test_the_api_module_constructs_NO_connector_of_its_own():
    """The four-branch ternary is gone, and staying gone is the property worth
    pinning. Two construction sites means two policies, and the second one was
    the sham simulator nobody chose."""
    tree = ast.parse((APP / "api" / "v1" / "fund.py").read_text(encoding="utf-8"))
    built = [f"line {n.lineno}: {n.func.id}"
             for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id in ("AlpacaConnector", "PaperConnector")]
    assert built == [], (
        f"the API module builds a connector directly again: {built}. The one "
        f"order path is venue.build_connector(spec).")


def test_the_venue_builder_reads_ONLY_credentials_from_the_environment():
    """``build_connector``'s inputs are the mode and two credentials. Any third
    environment read is a new hidden switch, which is exactly the class of
    defect item 7 was."""
    tree = ast.parse((APP / "fund" / "venue.py").read_text(encoding="utf-8"))
    env_reads = {
        n.args[0].value
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("getenv", "get")
        and n.args and isinstance(n.args[0], ast.Constant)
        and isinstance(n.args[0].value, str)
        and isinstance(getattr(n.func, "value", None), ast.Name)
        and n.func.value.id in ("os", "environ")
    }
    assert env_reads == {"ALPACA_API_KEY", "ALPACA_SECRET_KEY"}, env_reads


def test_the_interlock_the_flag_used_to_key_still_exists(monkeypatch):
    """Removing a guard along with its flag is only correct when the state it
    guarded against stops existing. Test mode did not stop existing — it was
    renamed — so the interlock was RE-KEYED onto the mode, and this fails if a
    later cleanup deletes it as dead code.

    MOVED, not read in place: the mode is set to each of the three and the
    interlock must follow it, which a hardcoded `return True` would not.
    """
    from app.core import firebase

    # PRECONDITION, asserted rather than assumed: `_is_test_mode` prefers an
    # ACTIVE spec over the environment, so if one were active the three moves
    # below would all read the same thing and this test would pass vacuously.
    # conftest's `_clear_active_mode` guarantees it; this line fails loudly if
    # that ever changes.
    assert m.current() is None

    monkeypatch.setenv("FUND_MODE", "test")
    assert firebase._is_test_mode() is True

    monkeypatch.setenv("FUND_MODE", "alpaca-paper")
    assert firebase._is_test_mode() is False

    # An unresolvable mode answers False — an unconfigured process gets the
    # loud refusal from every other guard, never a quiet exemption from this
    # one. (`_is_test_mode`'s own docstring; pinned so it stays true.)
    monkeypatch.setenv("FUND_MODE", "")
    assert firebase._is_test_mode() is False
