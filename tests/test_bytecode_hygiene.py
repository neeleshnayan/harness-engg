"""THE BYTECODE THIS TREE ACTUALLY EXECUTES agrees with the source we review.

THE INCIDENT (builder D41, 2026-08-24). A dispatch opened with twelve failing
tests in the gate's luck leg and no defect behind any of them. The module was
correct, the tests were correct, and the interpreter was running neither:
`app/fund/__pycache__/statistics.cpython-311.pyc` held `1.1 / sqrt(k)` where
`app/fund/statistics.py` held `1.0 / sqrt(k)` — the numerator mutant of a
previous session's mutation pass, cached and served. The observed failure
values are the arithmetic signature of exactly that: `0.057576631` against an
expected `0.052342392` is `1.1/sqrt(365)` against `1.0/sqrt(365)`.

Python invalidates a timestamped cache on the source's mtime (second
resolution) and byte size. A mutation harness that edits a constant IN PLACE at
equal byte length — `1.0` -> `1.1`, the shape this codebase's own harnesses use
— and restores it within the same second changes neither. `git status` reports
clean, the source reads correctly, code review sees nothing, and the SUITE is
the instrument being lied to.

So this file is the tripwire for a defect class that can silently decide what
every OTHER test in this repository measures — including the Tier-A gate tests
whose whole job is to refuse a loosening. It is deliberately cheap: a compile
pass over `app/`, no imports, no I/O beyond reading files.

Everything below the guard is what makes the guard trustworthy, and it is more
code than the guard by design: a PLANT (the guard can fail, and names the
constant), a BOUNDARY (a disagreeing cache Python would discard is NOT reported
as poisonous — that distinction is the whole finding), the two PEP 552 hash
modes, and REGRESSIONS for the two false-positive classes the scanner shipped
with in its first hour, which between them accused seven innocent files.
"""

from __future__ import annotations

import os
import pathlib
import py_compile
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.instruments import stale_pyc_scan as sps  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# The guard itself
# ---------------------------------------------------------------------------

def test_no_cached_bytecode_in_app_disagrees_with_its_source():
    """Would catch: the D41 incident — a mutation-pass artifact left in
    __pycache__ with an intact invalidation key, silently scoring every later
    test run against a mutant.

    Only `app/` is scanned: it is what the suite imports and what a mutation
    harness edits. A finding here is never cosmetic — it means the code you
    reviewed and the code that ran are different code.
    """
    findings, counts = sps.scan(REPO / "app")
    poisonous = [f for f in findings if f.served]
    assert not poisonous, (
        "cached bytecode disagrees with its source AND Python will serve it:\n"
        + "\n".join(f"  {f.source}\n      {f.detail}" for f in poisonous)
        + "\n\nDelete the caches and re-run: "
          "python scripts/instruments/stale_pyc_scan.py . --clear")
    # A guard that scanned nothing has proven nothing. `no_cache` is the normal
    # state of a fresh checkout, so this asserts the SCAN RAN, not that caches
    # exist: the file count is what makes the zero above meaningful.
    assert counts["agree"] + counts["no_cache"] > 50, counts


# ---------------------------------------------------------------------------
# Why the guard is trustworthy: plant, boundary, regression
# ---------------------------------------------------------------------------

def _module_with_numerator(value: str) -> str:
    # The two bodies must be BYTE-IDENTICAL IN LENGTH — that is the whole
    # mechanism, not a convenience of the fixture.
    return f'''"""A module whose only interesting feature is one constant."""
import math


def target(k):
    return {value} / math.sqrt(k)
'''


def _plant(tmp_path: pathlib.Path, before: str, after: str,
           keep_key: bool) -> pathlib.Path:
    """Compile `before`, then swap in `after` behind the interpreter's back.

    `keep_key=True` restores the original mtime, so the invalidation key still
    matches and Python would serve the stale cache. `keep_key=False` leaves the
    new mtime, which is the harmless case Python self-corrects.
    """
    src = tmp_path / "planted.py"
    src.write_text(before, encoding="utf-8")
    py_compile.compile(str(src), cfile=str(sps.cached_path(src)), doraise=True)
    st = src.stat()
    src.write_text(after, encoding="utf-8")
    if keep_key:
        os.utime(src, (st.st_atime, st.st_mtime))
    return src


def test_a_planted_mutant_is_reported_POISONOUS_and_NAMED(tmp_path):
    """Would catch: the guard above passing because it cannot fail.

    This is the D41 mutation reproduced exactly — same constant, same equal
    byte length, same restored mtime — and the assertion is on the NAMED
    function and BOTH values, because `these differ` is not evidence a reader
    can act on.
    """
    before = _module_with_numerator("1.1")   # what got compiled
    after = _module_with_numerator("1.0")    # what the tree now shows
    assert len(before) == len(after), "the plant must not change the byte size"
    _plant(tmp_path, before, after, keep_key=True)

    findings, counts = sps.scan(tmp_path)
    assert counts["poisonous"] == 1, (counts, findings)
    assert counts["agree"] == 0, counts
    detail = findings[0].detail
    assert "/target" in detail, detail
    assert "source=1.0" in detail and "cached=1.1" in detail, detail


def test_a_disagreeing_cache_PYTHON_WOULD_DISCARD_is_not_called_poisonous(tmp_path):
    """Would catch: the scanner collapsing 'stale' into 'dangerous' and
    crying wolf on every ordinary edit.

    An edit that moves the mtime leaves a disagreeing cache that the
    interpreter throws away on the next import. It is reported — absence of a
    report would hide a real one — but it is COUNTED SEPARATELY, and the two
    counts are never summed.
    """
    before = _module_with_numerator("1.1")
    after = _module_with_numerator("1.0")
    src = _plant(tmp_path, before, after, keep_key=False)
    # Second-resolution mtimes: force the key apart rather than trust the clock,
    # or this test passes for the wrong reason on a fast machine.
    st = src.stat()
    os.utime(src, (st.st_atime, st.st_mtime + 10))

    findings, counts = sps.scan(tmp_path)
    assert counts["poisonous"] == 0, (counts, findings)
    assert counts["stale_not_served"] == 1, (counts, findings)


def test_a_module_WITHOUT_future_annotations_is_not_falsely_accused(tmp_path):
    """Would catch: the scanner's own first-hour defect, which accused SEVEN
    innocent files.

    `compile()` inherits the CALLING module's __future__ flags unless told not
    to, and the scanner carries `from __future__ import annotations`. So every
    scanned module that does NOT carry that import was compiled under postponed
    annotations, produced different bytecode from its own honest cache, and was
    reported as poisoned. An instrument that manufactures the finding it exists
    to detect is worse than no instrument.

    The fixture below therefore has annotations and NO future import — the
    exact shape that broke — and its cache is honest.
    """
    src = tmp_path / "annotated.py"
    src.write_text(
        "def f(x: int, y: 'list[int]') -> str:\n"
        "    z: float = float(x)\n"
        "    return str(z) + str(y)\n",
        encoding="utf-8")
    py_compile.compile(str(src), cfile=str(sps.cached_path(src)), doraise=True)

    findings, counts = sps.scan(tmp_path)
    assert counts["poisonous"] == 0, (counts, findings)
    assert counts["agree"] == 1, (counts, findings)


def _equal_sets_in_different_order() -> tuple[frozenset, frozenset]:
    """Two EQUAL frozensets whose iteration order genuinely differs.

    Set iteration order is a function of the hash table's LAYOUT, and the layout
    depends on construction history — not only on the contents. Growing a set
    past a resize and then discarding the extras leaves a table sized for the
    larger population, and the survivors land in different slots. Deterministic,
    same-process, no hash-seed games.
    """
    members = ["FILL", "PTR", "PTC", "ABC", "XYZ"]
    grown = set(members + [f"Z{i}" for i in range(8)])
    for i in range(8):
        grown.discard(f"Z{i}")
    return frozenset(members), frozenset(grown)


@pytest.mark.parametrize("wrap", ["bare", "in_tuple"])
def test_set_iteration_order_is_not_mistaken_for_a_code_change(wrap):
    """Would catch: set-literal ORDER being read as a difference in meaning.

    This was a real false positive, not a hypothetical: the scanner's first
    pass accused `app/fund/custody.py` over
    `frozenset({'FILL','PTR','PTC'})` against `frozenset({'PTC','FILL','PTR'})`
    — the same constant, two orders. `_norm` sorts set members for exactly this
    reason.

    THE FIRST VERSION OF THIS TEST WAS VACUOUS AND THE MUTATION PASS SAID SO.
    It wrote a source file, compiled it, and compared — but two compilations of
    identical bytes usually produce identical ORDER, so it passed with `_norm`'s
    set branch deleted. A comparator test has to contain a difference before it
    can prove the comparator forgives one, so the fixture below ASSERTS that the
    two orders differ before asserting that the scanner ignores it.
    """
    a, b = _equal_sets_in_different_order()
    # THE FIXTURE'S OWN PRECONDITION. Without this the test proves nothing.
    assert a == b, "the two sets must be equal"
    assert list(a) != list(b), "the two sets must ITERATE differently"
    assert repr(a) != repr(b), "a repr-based comparison must be able to differ"

    template = compile("X = 0\n", "x.py", "exec", dont_inherit=True)
    left = template.replace(co_consts=((a,) if wrap == "bare" else ((a, 1),)))
    right = template.replace(co_consts=((b,) if wrap == "bare" else ((b, 1),)))

    assert sps.first_difference(left, right) is None, \
        sps.first_difference(left, right)


def test_a_set_whose_MEMBERS_changed_is_still_reported(tmp_path):
    """The other side of the boundary above: forgiving ORDER must not mean
    forgiving CONTENT. A criterion set that quietly loses a member is precisely
    the kind of change this scanner exists to surface.
    """
    template = compile("X = 0\n", "x.py", "exec", dont_inherit=True)
    left = template.replace(co_consts=(frozenset({"FILL", "PTR", "PTC"}),))
    right = template.replace(co_consts=(frozenset({"FILL", "PTR"}),))

    detail = sps.first_difference(left, right)
    assert detail is not None and "CONSTANT" in detail, detail


@pytest.mark.parametrize(
    "mode,expect_poisonous,why",
    [(py_compile.PycInvalidationMode.UNCHECKED_HASH, 1,
      "never validated against anything, so ALWAYS served — the most "
      "dangerous of the three header shapes"),
     (py_compile.PycInvalidationMode.CHECKED_HASH, 0,
      "the interpreter hashes the source on every import, so a disagreeing "
      "cache is never served and reporting it would be a false alarm")])
def test_hash_based_caches_are_classified_by_their_check_source_flag(
        tmp_path, mode, expect_poisonous, why):
    """Would catch: the two PEP 552 hash modes being collapsed into one
    answer — which is what the first draft of `key_matches` did, calling both
    'served' because neither carries a timestamp.

    The distinction is not academic: UNCHECKED_HASH is served unconditionally
    (worse than the timestamp loophole this file exists for), CHECKED_HASH is
    never served stale. One answer cannot be right for both.
    """
    before = _module_with_numerator("1.1")
    after = _module_with_numerator("1.0")
    src = tmp_path / "hashed.py"
    src.write_text(before, encoding="utf-8")
    py_compile.compile(str(src), cfile=str(sps.cached_path(src)),
                       invalidation_mode=mode, doraise=True)
    src.write_text(after, encoding="utf-8")

    findings, counts = sps.scan(tmp_path)
    assert len(findings) == 1, findings          # it disagrees either way
    assert counts["poisonous"] == expect_poisonous, (counts, why)
    assert counts["stale_not_served"] == 1 - expect_poisonous, (counts, why)


def test_a_missing_cache_is_reported_ABSENT_not_as_agreement(tmp_path):
    """Would catch: `no cache` being folded into `agree`, which would let a
    tree with no caches at all report a clean bill of health it never earned.
    Absence is never agreement — the fund's oldest rule, applied to an
    instrument.
    """
    (tmp_path / "lonely.py").write_text("X = 1\n", encoding="utf-8")
    findings, counts = sps.scan(tmp_path)
    assert counts == {"agree": 0, "no_cache": 1, "unreadable": 0,
                      "poisonous": 0, "stale_not_served": 0}
    assert findings == []


def test_an_unparseable_source_is_reported_not_raised(tmp_path):
    """Would catch: the scanner raising on a syntactically invalid file and
    taking the whole suite down. A scanner reports; it never raises.
    """
    src = tmp_path / "broken.py"
    src.write_text("def f(:\n", encoding="utf-8")
    sps.cached_path(src).parent.mkdir(exist_ok=True)
    sps.cached_path(src).write_bytes(b"\x00" * 32)

    findings, counts = sps.scan(tmp_path)
    assert counts["unreadable"] == 1, counts
    assert counts["poisonous"] == 0, counts
    assert "could not be compared" in findings[0].detail
