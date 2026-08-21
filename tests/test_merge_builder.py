"""The merge gate, tested against the ways a merge gate fails.

A gate that passes what it should have blocked is the exact failure class this
whole seat is caged against — two tests once ASSERTED a gate loosening. So the
tests below are written from the blocker's side: each constructs a bundle that
MUST be refused and fails if the gate says PASS.

Real git repositories in temp directories rather than mocks. A merge gate whose
tests never ran `git bundle` would be testing its own idea of git.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from merge_builder import (  # noqa: E402
    FORBIDDEN_PATHS, GateError, classify_paths, detect_suite, render, review,
    scan_diff)

BRANCH = "claude/krypton-fund-agentic-j8r2mu"


def _git(cwd, *args, check=True):
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {p.stderr}")
    return p.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """An upstream repo with a passing suite, on the fund's branch name."""
    r = tmp_path / "upstream"
    r.mkdir()
    _git(r, "init", "-q", "-b", BRANCH)
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
    (r / "tests").mkdir()
    (r / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n",
                                            encoding="utf-8")
    (r / "app").mkdir()
    (r / "app" / "fund").mkdir()
    (r / "app" / "fund" / "gate.py").write_text("MIN_PSR_PCT = 65.0\n", encoding="utf-8")
    (r / "app" / "fund" / "harmless.py").write_text("X = 1\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    return r


def _bundle(repo_dir, tmp_path, mutate, name="b.bundle", branch="work"):
    """Clone, mutate, commit, bundle. Returns (bundle_path, base_sha)."""
    work = tmp_path / f"w-{name}"
    _git(repo_dir.parent, "clone", "-q", "--no-hardlinks", str(repo_dir), str(work))
    _git(work, "config", "user.email", "b@b")
    _git(work, "config", "user.name", "b")
    base = _git(work, "rev-parse", "HEAD")
    _git(work, "checkout", "-q", "-b", branch)
    mutate(work)
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "builder change")
    out = tmp_path / name
    _git(work, "bundle", "create", "-q", str(out), branch)
    return out, base


def _ok(w):
    (w / "app" / "fund" / "newthing.py").write_text(
        '"""A new module."""\nVALUE = 3\n', encoding="utf-8")


# --- the happy path, so the blockers below mean something -------------------


def test_a_clean_bundle_passes_and_says_it_merged_nothing(repo, tmp_path):
    b, base = _bundle(repo, tmp_path, _ok)
    r = review(b, base, repo, BRANCH)
    assert r["verdict"] == "PASS", r["blockers"]
    assert r["merged"] is False
    assert "has NOT merged anything" in r["note"]
    assert r["suite"]["exit_code"] == 0


def test_the_gate_never_writes_to_the_repository_it_gates(repo, tmp_path):
    """The structural guarantee. If this ever fails, the seat's isolation is
    gone and nothing else in this file matters."""
    before = _git(repo, "rev-parse", "HEAD")
    before_refs = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    before_status = _git(repo, "status", "--porcelain")
    b, base = _bundle(repo, tmp_path, _ok)
    review(b, base, repo, BRANCH)
    assert _git(repo, "rev-parse", "HEAD") == before
    assert _git(repo, "for-each-ref",
                "--format=%(refname) %(objectname)") == before_refs
    assert _git(repo, "status", "--porcelain") == before_status


# --- every way it must refuse ----------------------------------------------


def test_the_suite_runs_on_the_MERGE_not_on_the_builder_s_tree(repo, tmp_path):
    """Found by running this gate on its own bundle, 2026-08-21.

    The gate used to `checkout --detach` the bundle tip and call that "the
    merged tree". It is not: the tip does not contain whatever landed on the
    target after the bundle was cut. Here the target gains a test the bundle
    has never seen, and it must still run — if it does not, the gate is
    reporting green on a tree nobody will ever have.
    """
    b, base = _bundle(repo, tmp_path, _ok)
    (repo / "tests" / "test_landed_after.py").write_text(
        "def test_landed_after():\n    assert True\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "landed on the target after the bundle")

    r = review(b, base, repo, BRANCH)
    assert r["verdict"] == "PASS", r["blockers"]
    # 2 tests collected proves the target's newer test ran alongside the
    # bundle's. One would mean the tip was checked out on its own.
    assert "2 passed" in r["suite"]["tail"], r["suite"]["tail"]


def test_a_bundle_that_conflicts_with_the_target_is_refused(repo, tmp_path):
    b, base = _bundle(repo, tmp_path, lambda w: (
        w / "app" / "fund" / "harmless.py").write_text("X = 2\n", encoding="utf-8"))
    (repo / "app" / "fund" / "harmless.py").write_text("X = 3\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "the target moved the same line")

    r = review(b, base, repo, BRANCH)
    assert r["verdict"] == "FAIL"
    a = next(x for x in r["blockers"] if x["kind"] == "apply")
    assert "does not merge cleanly" in a["detail"]
    assert "app/fund/harmless.py" in a["detail"]
    assert r["suite"] is None, "a conflicted merge must not report a suite result"


def test_a_stale_base_is_refused(repo, tmp_path):
    """A bundle cut from a stale base applies cleanly and silently reverts
    whatever landed in between. That is the quiet one."""
    b, base = _bundle(repo, tmp_path, _ok)
    del base
    r = review(b, "0" * 40, repo, BRANCH)
    assert r["verdict"] == "FAIL"
    assert any(x["kind"] == "base" for x in r["blockers"])


def test_a_base_git_cannot_resolve_is_UNKNOWN_and_still_fails(repo, tmp_path):
    b, _ = _bundle(repo, tmp_path, _ok)
    r = review(b, "not-a-ref-at-all", repo, BRANCH)
    assert r["verdict"] == "FAIL"
    blocker = next(x for x in r["blockers"] if x["kind"] == "base")
    assert "UNKNOWN" in blocker["detail"]
    assert "not the same as fine" in blocker["detail"]


def test_a_failing_suite_on_the_MERGED_tree_fails(repo, tmp_path):
    """The builder's own green run says the diff works in isolation."""
    def breaks(w):
        (w / "tests" / "test_bad.py").write_text(
            "def test_bad():\n    assert False\n", encoding="utf-8")
    b, base = _bundle(repo, tmp_path, breaks)
    r = review(b, base, repo, BRANCH)
    assert r["verdict"] == "FAIL"
    t = next(x for x in r["blockers"] if x["kind"] == "tests")
    assert r["suite"]["exit_code"] != 0
    assert "works here" in t["detail"]
    assert t["tail"], "the failure must be reported verbatim, not summarised"


def test_a_diff_touching_the_gate_cannot_pass_on_this_check_alone(repo, tmp_path):
    """Not a rejection of the work — a routing decision. The constitution:
    'sensitive diffs also pass the adversary blind'."""
    def loosen(w):
        (w / "app" / "fund" / "gate.py").write_text("MIN_PSR_PCT = 50.0\n",
                                                    encoding="utf-8")
    b, base = _bundle(repo, tmp_path, loosen)
    r = review(b, base, repo, BRANCH)
    assert r["verdict"] == "FAIL"
    s = next(x for x in r["blockers"] if x["kind"] == "sensitive")
    assert "app/fund/gate.py" in s["paths"]
    assert "adversary blind" in s["detail"]


def test_a_forbidden_surface_is_a_fail_no_review_can_clear(repo, tmp_path):
    def touch_thesis(w):
        d = w / "app" / "fund" / "thesis_generator"
        d.mkdir(parents=True)
        (d / "models.py").write_text("X = 1\n", encoding="utf-8")
    b, base = _bundle(repo, tmp_path, touch_thesis)
    r = review(b, base, repo, BRANCH)
    assert r["verdict"] == "FAIL"
    f = next(x for x in r["blockers"] if x["kind"] == "forbidden")
    assert "no review that clears this" in f["detail"]


def test_skipping_the_tests_can_never_produce_a_PASS(repo, tmp_path):
    """'We did not check' and 'it passed' must not share an exit code."""
    b, base = _bundle(repo, tmp_path, _ok)
    r = review(b, base, repo, BRANCH, run_tests=False)
    assert r["verdict"] == "FAIL"
    u = next(x for x in r["blockers"] if x["kind"] == "unknown")
    assert "cannot PASS" in u["detail"]


def test_a_repo_with_no_recognisable_suite_is_UNVERIFIED_not_fine(repo, tmp_path):
    (repo / "pytest.ini").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "drop the suite")
    b, base = _bundle(repo, tmp_path, _ok)
    r = review(b, base, repo, BRANCH)
    assert r["verdict"] == "FAIL"
    u = next(x for x in r["blockers"] if x["kind"] == "unknown")
    assert "UNVERIFIED" in u["detail"]
    assert "not a skip" in u["detail"]


def test_an_unreadable_bundle_fails_rather_than_passing_emptily(repo, tmp_path):
    bad = tmp_path / "not.bundle"
    bad.write_text("this is not a git bundle", encoding="utf-8")
    r = review(bad, _git(repo, "rev-parse", "HEAD"), repo, BRANCH)
    assert r["verdict"] == "FAIL"
    assert any(x["kind"] == "apply" for x in r["blockers"])


def test_a_missing_bundle_is_a_usage_error_not_a_verdict(repo, tmp_path):
    """A typo in a path must never render as 'FAIL' — that reads like a
    judgement about the work."""
    with pytest.raises(GateError):
        review(tmp_path / "nope.bundle", "HEAD", repo, BRANCH)


# --- the pure parts ---------------------------------------------------------


def test_the_forbidden_list_covers_both_of_the_owner_s_surfaces():
    assert "app/fund/thesis_generator/" in FORBIDDEN_PATHS
    assert "src/app/clark/studio/thesis/" in FORBIDDEN_PATHS


def test_classify_keeps_the_three_buckets_disjoint():
    got = classify_paths(["app/fund/gate.py", "app/fund/thesis_generator/x.py",
                          "app/fund/tca.py"])
    assert got["sensitive"] == ["app/fund/gate.py"]
    assert got["forbidden"] == ["app/fund/thesis_generator/x.py"]
    assert got["ordinary"] == ["app/fund/tca.py"]


def test_the_guard_region_is_matched_by_CONTENT_not_by_filename():
    """The whole point of the region tier. `app/api/v1/fund.py` gains an
    endpoint most weeks; flagging the file would fire every dispatch, and a
    check that always fires is a check nobody reads."""
    innocent = ("+++ b/app/api/v1/fund.py\n"
                '+@router.get("/fund/tca")\n'
                "+def tca_report():\n")
    assert scan_diff(innocent)["regions"] == []

    guardy = ("+++ b/app/api/v1/fund.py\n"
              '+    allowlist={"neelesh", "neelesh-via-cto", "someone-else"}\n')
    hits = scan_diff(guardy)["regions"]
    assert len(hits) == 1
    assert hits[0]["path"] == "app/api/v1/fund.py"


def test_a_removed_guard_line_is_caught_as_well_as_an_added_one():
    """A loosening is usually a DELETION."""
    removed = ("+++ b/app/api/v1/fund.py\n"
               '-    if who not in allowlist:\n')
    assert len(scan_diff(removed)["regions"]) == 1


def test_a_moved_numeric_constant_is_reported_wherever_it_lives():
    out = scan_diff("+++ b/app/fund/anything.py\n+MAX_NOTIONAL_USD = 5000.0\n")
    assert out["constants"][0]["name"] == "MAX_NOTIONAL_USD"


def test_ordinary_code_does_not_trip_the_constant_scan():
    quiet = ("+++ b/app/fund/x.py\n"
             "+def f(n):\n+    return n * 2\n+lower_case = 3\n")
    assert scan_diff(quiet)["constants"] == []


def test_an_unrecognised_repo_shape_returns_None_rather_than_a_default(tmp_path):
    assert detect_suite(tmp_path) is None


def test_the_python_and_node_repo_shapes_are_both_recognised(tmp_path):
    py, node = tmp_path / "py", tmp_path / "node"
    py.mkdir()
    node.mkdir()
    (py / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (node / "next.config.ts").write_text("export default {};\n", encoding="utf-8")
    assert "pytest" in " ".join(detect_suite(py) or [])
    assert "--test" in (detect_suite(node) or [])


def test_the_node_glob_is_ONE_argument_so_node_expands_it_not_the_shell(tmp_path):
    """`**` in bash without globstar means `*` — one level — and a nested suite
    is then silently never run. This seat reported 163 passing when the truth
    was 183, exactly that way. The glob must reach node intact."""
    node = tmp_path / "node"
    node.mkdir()
    (node / "next.config.ts").write_text("export default {};\n", encoding="utf-8")
    cmd = detect_suite(node) or []
    globs = [a for a in cmd if "*" in a]
    assert len(globs) == 1, cmd
    assert globs[0].count("**") == 1
    assert globs[0] == "src/app/clark/**/*.test.ts"


def test_the_rendered_report_states_that_nothing_was_merged(repo, tmp_path):
    b, base = _bundle(repo, tmp_path, _ok)
    text = render(review(b, base, repo, BRANCH))
    assert text.startswith("MERGE GATE: PASS")
    assert "It has performed none." in text


def test_the_rendered_report_carries_the_suite_tail_verbatim(repo, tmp_path):
    def breaks(w):
        (w / "tests" / "test_bad.py").write_text(
            "def test_bad():\n    assert 1 == 2\n", encoding="utf-8")
    b, base = _bundle(repo, tmp_path, breaks)
    text = render(review(b, base, repo, BRANCH))
    assert text.startswith("MERGE GATE: FAIL")
    assert "suite tail, verbatim:" in text
