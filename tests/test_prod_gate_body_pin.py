"""BODY-LEVEL PINS ON THE PROD GATE — the adversary's M2, made impossible.

2026-08-27: the adversary planted a dormant ``if os.environ.get(...):
return`` inside ``_refuse_prod_unless_reachable`` — the function whose own
docstring reads "THE ONE GATE. Every alpaca-prod refusal in the fund comes
through here" — and it passed the merge-gate classifier on every leg AND
left ``tests/test_fund_mode.py`` 76/76 green. The module's only bypass pin
was on ``resolve``'s SIGNATURE (the shape of the bypass that was already
removed). The last hole's shape is never the next hole's shape; these pins
read the BODY.

The pins are deliberately narrow: they refuse the specific capability
classes a bypass needs (environment reads, an early return before the
refusal logic) rather than freezing the prose, so an honest edit to the
function still passes and a bypass of either known class cannot.
"""
import inspect

from app.fund import mode


def _gate_source() -> str:
    return inspect.getsource(mode._refuse_prod_unless_reachable)


def test_the_one_gate_reads_no_environment():
    """A dormant env-var bypass is the demonstrated attack. The gate's
    decision may depend only on the reachability spec it is handed — never
    on process environment."""
    src = _gate_source()
    assert "os.environ" not in src
    assert "getenv" not in src


def test_the_one_gate_contains_its_refusal():
    """The function must still be a refusal: deleting or short-circuiting
    the raise is the other bypass shape. The raise must be present and not
    inside a swallowing handler."""
    src = _gate_source()
    assert "raise" in src
    # the refusal must not be wrapped so that it cannot escape
    assert "except Exception" not in src


def test_prod_stays_locked_by_the_constant():
    """The independent lock the whole precondition chain leans on. This
    literal moves ONLY by a versioned human decision; the test existing is
    what makes a quiet flip loud."""
    assert mode.PROD_UNLOCKED is False


def test_the_gate_function_takes_no_bypass_parameter():
    """The removed bypass was a parameter (`allow_prod`); the signature pin
    for it lives in test_fund_mode. Kept here too so the two bypass classes
    — a new parameter and an env read — are refused side by side, in the
    file named for the gate's body."""
    params = inspect.signature(mode._refuse_prod_unless_reachable).parameters
    assert set(params) == {"spec", "action", "store"}
