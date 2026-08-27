"""The merge gate's two measured blind spots, and the checks that close them.

BOTH WERE FOUND BY USING THE GATE, NOT BY READING IT.

  * **The guard module that read as ordinary** (adversary, run-adversary-hw5-kp6,
    desk 78e2650b). `app/fund/ticketguard.py` — a whole guard module — classified
    ORDINARY, because `SENSITIVE_PATHS` is matched by equality and nobody had
    added the new file to it. The adversary named the refutation itself: *"a test
    that FAILS when a new app/fund/*guard*.py exists unlisted"*. That test is
    `test_every_guard_module_on_disk_classifies_sensitive` below, and it reads
    the DISK rather than a list, so the next guard module is covered on the day
    it is written.

  * **The keyword filter standing in for a control-flow question** (adversary,
    run-adversary-d8, desk d1d5beef). On `builder-d8` the pattern flagged six
    benign lines of a new read-only endpoint and MISSED `_real_broker()`
    becoming `_broker_is_real()` at the two `/fund/venue/backfill` guards —
    which flipped one of eight flag combinations from refuse to allow, on an
    endpoint that appends ORDER_FILLED to the real ledger. No vocabulary
    describes a backfill or a predicate rename, so the repair does not use one.

The tests are written from the blocker's side, like the file next door: each
constructs something that MUST be caught, and fails if the gate stays quiet.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from merge_builder import (  # noqa: E402
    SENSITIVE_GLOBS,
    SENSITIVE_PATHS,
    changed_lines,
    classify_paths,
    janitor_scan,
    refusal_predicates,
    scan_control_flow,
    scan_diff,
)

ROOT = Path(__file__).resolve().parents[1]


# --- 1. the guard module that read as ordinary ----------------------------

def test_every_guard_module_on_disk_classifies_sensitive():
    """THE ADVERSARY'S OWN REFUTATION CRITERION, made a test.

    Reads the repository rather than a list. A guard module added tomorrow
    fails this the moment it exists, which is the whole difference between a
    check and an inventory someone has to remember to update.
    """
    guards = sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                    for p in (ROOT / "app" / "fund").glob("*guard*.py"))
    # DOMAIN, stated: a pass over an empty list would prove nothing at all.
    assert guards, "no guard modules found — this test compared nothing"
    got = classify_paths(guards)
    assert got["sensitive"] == guards, (
        f"guard modules classified as ordinary: {got['ordinary']}")


def test_the_named_ticketguard_case_specifically():
    """The file the adversary measured, pinned by name as well as by shape."""
    assert (ROOT / "app" / "fund" / "ticketguard.py").exists()
    got = classify_paths(["app/fund/ticketguard.py", "app/fund/desk.py"])
    assert got["sensitive"] == ["app/fund/ticketguard.py"]
    assert got["ordinary"] == ["app/fund/desk.py"]
    # ...and it is covered by SHAPE, not by having been added to the list. If
    # someone "fixes" this by appending the name, the glob check above is what
    # keeps the next module covered.
    assert "app/fund/ticketguard.py" not in SENSITIVE_PATHS


@pytest.mark.parametrize("path", [
    "app/fund/ticketguard.py",
    "app/fund/redecisionguard.py",       # does not exist yet — that is the point
    "app/fund/autopolicy_v5_draft.py",
    "app/fund/projections/nav.py",
    "app/api/v1/orderguard.py",
])
def test_a_guard_shaped_path_is_sensitive_whether_or_not_it_exists(path):
    assert classify_paths([path])["sensitive"] == [path]


def test_an_ordinary_file_is_still_ordinary():
    """A gate that flags everything is a gate nobody reads — the same reason
    fund.py is matched by content and not by name."""
    ordinary = ["app/fund/desk.py", "app/fund/marketdata.py",
                "app/fund/leanrunner.py", "scripts/merge_builder.py",
                "tests/test_marketdata.py"]
    assert classify_paths(ordinary)["sensitive"] == []
    assert set(SENSITIVE_GLOBS)  # the globs exist and are not an empty tuple


# --- 2. the content patterns the hw5 diff scored zero on ------------------

@pytest.mark.parametrize("line", [
    "+        raise HTTPException(status_code=409, detail=EventType.APPROVAL_REFUSED)",
    "+    LEGACY_REDECISION_GUARD_VERSION = 'v2'",
    "+from app.fund.ticketguard import refuse",
    "+    _refuse_if_terminal(row)",
])
def test_the_fund_py_vocabulary_now_covers_the_hw5_shapes(line):
    diff = "+++ b/app/api/v1/fund.py\n" + line + "\n"
    assert scan_diff(diff)["regions"], f"scored zero on {line!r}"


def test_an_order_event_write_is_sensitive_in_ANY_file():
    """The vocabulary had no term for `backfill`, and backfill.py appends
    ORDER_FILLED to the real ledger."""
    diff = ("+++ b/app/fund/backfill.py\n"
            "+    store.append(EventType.ORDER_FILLED, payload)\n")
    assert scan_diff(diff)["regions"]


def test_a_predicate_rename_is_flagged_by_its_shape():
    diff = ("+++ b/app/api/v1/fund.py\n"
            "-def _real_broker() -> bool:\n"
            "+def _broker_is_real() -> bool:\n")
    assert scan_diff(diff)["regions"]


def test_a_removed_refusal_is_seen_at_all():
    """A control taken OUT leaves no added line to match. A scan that reads
    only `+` lines cannot see a deletion, which is the easiest loosening
    there is."""
    diff = ("+++ b/app/fund/backfill.py\n"
            "-        raise HTTPException(status_code=403, detail='no')\n")
    got = scan_diff(diff)
    assert got["removals"], "a deleted refusal was invisible"
    assert "raise HTTPException" in got["removals"][0]["line"]


def test_an_ordinary_removal_is_not_called_a_refusal():
    diff = "+++ b/app/fund/desk.py\n-    total = total + 1\n"
    assert scan_diff(diff)["removals"] == []


# --- 3. the control-flow question, asked without vocabulary ---------------

GUARDED = '''\
from fastapi import HTTPException


def _broker_is_real() -> bool:
    return True


def backfill(order):
    live = _broker_is_real()
    if not live:
        raise HTTPException(status_code=403, detail="paper only")
    return order


def harmless(x):
    return x + 1
'''


def test_the_scan_finds_the_names_a_refusal_depends_on():
    got = refusal_predicates(GUARDED)
    assert got["readable"] is True
    assert "live" in got["names"]
    assert [r["function"] for r in got["regions"]] == ["backfill"]


def test_an_unconditional_raise_is_not_reported_as_a_control():
    """Otherwise every `raise ValueError('bad input')` in the codebase would
    flood the report, and a report nobody reads is the failure this gate is
    trying to prevent."""
    src = "def f(x):\n    raise ValueError('always')\n"
    assert refusal_predicates(src)["regions"] == []


def test_a_conditional_raise_that_is_NOT_a_refusal_is_not_a_control():
    """THE 289-HIT REGRESSION, pinned.

    The first version of this scan counted any conditional `raise` and
    returned 289 hits on a seven-file diff that touched no control at all —
    `marketdata.py` refusing a stale price series raises `BarsError`, which is
    a data-quality answer and has nothing to do with approvals. A gate that
    fires on every new `raise` inside an `if` is one the chair scrolls past,
    which is the same failure the fund.py content pattern was written to
    avoid.
    """
    src = ("def fetch(symbol, fresh):\n"
           "    if not fresh:\n"
           "        raise BarsError('stale')\n"
           "    return symbol\n")
    assert refusal_predicates(src)["regions"] == []
    # ...and the SAME shape raising the fund's refusal IS a control. Without
    # this half the assertion above would pass on a scan that found nothing
    # anywhere.
    http = src.replace("BarsError('stale')", "HTTPException(status_code=403)")
    assert [r["function"] for r in refusal_predicates(http)["regions"]] == ["fetch"]


def test_ubiquitous_names_are_not_treated_as_refusal_predicates():
    """`isinstance`, `get` and `str` appear in nearly every guard AND in
    nearly every other line. Keeping them made the predicate leg a full-text
    match on the diff."""
    src = ("def f(cfg):\n"
           "    if not isinstance(cfg.get('x'), str) or len(cfg) == 0:\n"
           "        raise HTTPException(status_code=422)\n"
           "    return cfg\n")
    names = refusal_predicates(src)["names"]
    assert "cfg" in names
    for noise in ("isinstance", "str", "len", "get"):
        assert noise not in names


def test_a_name_MENTIONED_in_a_comment_is_not_a_change_to_it():
    """Most of the 289 were prose. The ask was "alters a boolean used in a
    refusal", and altering means assigning or defining."""
    src = ("def f(live):\n"
           "    if not live:\n"
           "        raise HTTPException(status_code=403)\n"
           "    return 1\n"
           "\n"
           "\n"
           "def other():\n"
           "    # live is checked above, see f()\n"
           "    return 2\n")
    mention = scan_control_flow({"app/x.py": {8}}, lambda p: src)
    assert mention["hits"] == []
    # ...and an actual assignment to the same name IS caught.
    src2 = src.replace("    # live is checked above, see f()\n",
                       "    live = False\n")
    assign = scan_control_flow({"app/x.py": {8}}, lambda p: src2)
    assert assign["hits"] and "assigns or defines live" in assign["hits"][0]["why"]


def test_a_file_that_does_not_parse_is_UNKNOWN_not_clear():
    got = refusal_predicates("def (:\n")
    assert got["readable"] is False
    assert "UNKNOWN" in got["note"]


def test_the_adversarys_own_falsifier_diff_is_caught():
    """`+ refusal = None  # guard disabled` — the hand-made diff on which the
    old pattern scored ZERO."""
    lines = GUARDED.splitlines()
    lines.insert(9, "    refusal = None  # guard disabled")
    source = "\n".join(lines) + "\n"
    got = scan_control_flow({"app/fund/backfill.py": {10}},
                            lambda p: source)
    assert got["hits"], "the guard-disabling line was invisible"
    assert "backfill()" in got["hits"][0]["why"]


def test_a_changed_line_inside_a_refusing_function_is_flagged():
    got = scan_control_flow({"app/fund/backfill.py": {9}}, lambda p: GUARDED)
    assert got["hits"] and got["hits"][0]["line"] == 9


def test_a_changed_line_far_from_any_refusal_is_left_alone():
    """Zero is quiet. A gate that flags the whole file has told nobody
    anything — that is why fund.py was matched by content in the first place."""
    got = scan_control_flow({"app/fund/backfill.py": {17}}, lambda p: GUARDED)
    assert got["hits"] == []


def test_a_file_the_gate_could_not_read_is_reported_not_skipped():
    got = scan_control_flow({"app/fund/backfill.py": {1}}, lambda p: None)
    assert got["hits"] == []
    assert got["unreadable"] and "not examined" in got["unreadable"][0]["reason"]


def test_only_python_under_app_is_control_flow_scanned():
    """The scan reads Python syntax. Handing it a TypeScript file would
    produce an 'unparsed' blocker that means nothing."""
    got = scan_control_flow({"src/app/clark/x.tsx": {1}, "scripts/tool.py": {1}},
                            lambda p: "def (")
    assert got["hits"] == [] and got["unreadable"] == []


# --- 4. the diff's own line numbers ---------------------------------------

def test_changed_lines_reads_the_hunk_headers():
    diff = ("+++ b/a.py\n"
            "@@ -1,0 +2,3 @@\n+x\n+y\n+z\n"
            "@@ -9 +12 @@\n-old\n+new\n"
            "+++ b/b.py\n"
            "@@ -0,0 +1,1 @@\n+q\n")
    got = changed_lines(diff)
    assert got["a.py"] == {2, 3, 4, 12}
    assert got["b.py"] == {1}


def test_a_pure_deletion_hunk_contributes_no_new_lines():
    """`@@ -5,3 +4,0 @@` removes three lines and adds none; a scan that read
    the count as 1 would flag an unrelated line by number."""
    got = changed_lines("+++ b/a.py\n@@ -5,3 +4,0 @@\n-a\n-b\n-c\n")
    assert got.get("a.py", set()) == set()


# --- 5. the janitor rides along and never blocks ---------------------------

def test_the_janitor_reports_a_dead_import_without_blocking(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "x.py").write_text("import os\n\n\ndef f():\n    return 1\n",
                                           encoding="utf-8")
    got = janitor_scan(tmp_path, ["app/x.py"])
    ruff = [t for t in got["tools"] if t["tool"].startswith("ruff")]
    assert ruff and ruff[0]["available"] is True
    assert any("F401" in f for f in ruff[0]["findings"])
    assert got["files_scanned"]["python"] == 1


def test_the_janitor_finds_nothing_in_clean_code_and_says_so(tmp_path):
    """THE NULL ARM. A scanner that cannot return zero has not been shown to
    return anything meaningful when it returns non-zero."""
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "y.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    got = janitor_scan(tmp_path, ["app/y.py"])
    ruff = [t for t in got["tools"] if t["tool"].startswith("ruff")][0]
    assert ruff["available"] is True and ruff["findings"] == []


def test_the_janitor_never_scans_abhisheks_surfaces(tmp_path):
    (tmp_path / "app" / "fund" / "thesis_generator").mkdir(parents=True)
    (tmp_path / "app" / "fund" / "thesis_generator" / "z.py").write_text(
        "import os\n", encoding="utf-8")
    got = janitor_scan(tmp_path, ["app/fund/thesis_generator/z.py"])
    assert got["files_scanned"]["python"] == 0
    assert got["tools"] == []


def test_a_missing_file_is_not_scanned_rather_than_erroring(tmp_path):
    got = janitor_scan(tmp_path, ["app/gone.py"])
    assert got["files_scanned"]["python"] == 0
