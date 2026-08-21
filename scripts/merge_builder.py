"""The gate a builder bundle passes BEFORE a human merges it. It never merges.

Why this exists, stated plainly because it is the whole justification: every
serious bug this fund has shipped was HARNESS code — a gate loosened by an
off-by-one and blessed by its own tests, kill switches with zero callers, a
write-only verdict column. The builder seat exists to write harness code fast,
in an isolated worktree, and the CTO chair is the only thing between its diff
and the live tree. That review has so far been done by hand, from memory, at the
end of a long session. This is that review, written down and made repeatable.

**IT GATES A MERGE; IT NEVER PERFORMS ONE.** There is no `git merge`, no
`git push`, no write of any kind against the repository you point it at. The
bundle is applied to a THROWAWAY CLONE in a temp directory that is deleted on
the way out. That is a structural guarantee, not a promise: the only path that
touches the source repo is `git clone`, and the only mutating commands run
inside the clone.

FOUR THINGS IT CHECKS, and one rule that governs all of them.

  1. BASE ANCESTRY — the bundle's declared base must be an ancestor of the
     branch you intend to merge into. A bundle cut from a stale base can apply
     cleanly and still silently revert whatever landed in between.
  2. IT APPLIES — the bundle's tip must fetch and check out. A bundle that
     cannot be read is not a bundle that passes.
  3. THE SUITE IS GREEN ON THE MERGED TREE — not on the builder's tree. The
     builder's suite passing says the diff works in isolation; only the merged
     tree says it works here.
  4. FORBIDDEN AND SENSITIVE SURFACES — the paths an agent may never touch, and
     the ones it may touch only with an adversary review behind it.

THE RULE: **anything unknown is a FAIL.** A suite that could not be run, a
base that could not be resolved, a diff that could not be read — every one of
those reports FAIL, never PASS. This is the same discipline the gate applies to
a candidate: absent evidence is not satisfied evidence, and a merge gate that
degrades to "probably fine" is worse than no merge gate, because it reassures.

Run:
    ./venv/Scripts/python.exe -X utf8 scripts/merge_builder.py \\
        --bundle /path/to/builder.bundle --base <sha> [--repo .] [--branch ...]

Exit code 0 on PASS, 1 on FAIL, 2 on a usage error. Nothing is printed that a
human has to interpret: the verdict is a word and every blocker is a sentence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

#: Paths NO agent-authored diff may touch, ever. Not a judgement call and not
#: reviewable away: these are another human's surfaces (the constitution names
#: them by owner) and the event log, which is append-only by design.
#:
#: A hit here is a FAIL that no review clears — the correct response is to
#: remove the file from the bundle, not to argue about it.
FORBIDDEN_PATHS: tuple[str, ...] = (
    "app/fund/thesis_generator/",
    "src/app/clark/studio/thesis/",
)

#: Whole files whose every line is load-bearing for money or for the approval
#: chain. A diff touching one is not rejected outright — the builder is
#: sometimes asked to refactor around them — but it CANNOT be merged on this
#: gate alone. The constitution's rule: "sensitive diffs also pass the adversary
#: blind".
SENSITIVE_PATHS: tuple[str, ...] = (
    "app/fund/autopolicy.py",
    "app/fund/gate.py",
    "app/fund/risk.py",
    "app/fund/riskengine.py",
    "app/fund/riskmonitor.py",
    "app/fund/exitrule.py",
    "app/fund/events.py",
    "app/fund/judgement.py",
)

#: Sensitive REGIONS inside files that change for many innocent reasons.
#:
#: The approval guard lives inside `app/api/v1/fund.py`, which is 3,600 lines and
#: gains an endpoint most weeks. Flagging the whole file would fire on every
#: dispatch, and a check that fires every time is a check nobody reads — which is
#: how a real loosening gets waved through. So the file is matched by CONTENT:
#: only a changed line that looks like the guard, the allowlist or the approval
#: path raises it.
#:
#: Deliberately over-broad within that narrow scope. A false positive here costs
#: one human glance; a false negative costs the invariant.
SENSITIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"app/api/v1/fund\.py$",
     r"allowlist|_guard_|approver|GUARD_VERSION|autopolicy|/approve|confirm"),
)

#: Assignments that MOVE A NUMBER, in any file. A threshold moves only by a
#: versioned human change with a written reason — in either direction — so a
#: numeric constant changing inside a builder diff is always worth a sentence in
#: the report, wherever it lives.
#:
#: Matches an ADDED line that assigns a bare number to an UPPER_SNAKE name. Not a
#: verdict on its own: new constants in new files are normal and are reported as
#: additions rather than as moves.
_CONST_ASSIGN = re.compile(r"^\+\s*([A-Z][A-Z0-9_]{2,})\s*[:=]\s*"
                           r"(?:float\(|int\()?\s*[-+]?[0-9][0-9_.]*")

#: How the suite is run, per repo shape. Detected from what is actually on disk
#: rather than passed in, so the caller cannot accidentally gate a Python repo
#: with a command that tests nothing.
_SUITES: tuple[tuple[str, list[str]], ...] = (
    ("pytest.ini", [sys.executable, "-m", "pytest", "-q"]),
)


class GateError(Exception):
    """A usage problem — distinct from a FAIL verdict, which is a real answer."""


def _run(cmd: list[str], cwd: Optional[Path] = None,
         timeout: float = 3_600.0) -> tuple[int, str]:
    """Run a command, returning (code, combined output).

    Never raises on a non-zero exit: a failing suite is an ANSWER this gate
    reports, not an exception it propagates. Only a missing binary or a timeout
    is exceptional, and both are converted into a stated failure rather than a
    traceback — the caller needs a verdict, not a stack.
    """
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, timeout=timeout,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError as e:
        return 127, f"command not found: {e}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:.0f}s: {' '.join(cmd)}"


def _git(args: list[str], cwd: Path, timeout: float = 600.0) -> tuple[int, str]:
    return _run(["git", *args], cwd=cwd, timeout=timeout)


def _blocker(kind: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "detail": detail, **extra}


def classify_paths(paths: list[str]) -> dict[str, list[str]]:
    """Split changed paths into forbidden, sensitive and ordinary.

    Pure and separately testable, deliberately: this is the part of the gate
    that decides whether a human has to look, and a decision like that should
    not be reachable only through a subprocess and a temp directory.
    """
    forbidden = [p for p in paths
                 if any(p.startswith(f) or f.rstrip("/") in p
                        for f in FORBIDDEN_PATHS)]
    sensitive = [p for p in paths if p in SENSITIVE_PATHS]
    ordinary = [p for p in paths if p not in forbidden and p not in sensitive]
    return {"forbidden": sorted(set(forbidden)),
            "sensitive": sorted(set(sensitive)),
            "ordinary": sorted(set(ordinary))}


def scan_diff(diff_text: str) -> dict[str, list[dict[str, str]]]:
    """Find sensitive REGIONS and moved constants inside a unified diff.

    Reads the diff rather than the file list, because the two questions are
    different: "did this touch fund.py" is nearly always yes and tells nobody
    anything, while "did this touch a line mentioning the allowlist" is the
    question the invariant actually rests on.
    """
    regions: list[dict[str, str]] = []
    constants: list[dict[str, str]] = []
    current = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if not line.startswith("+") and not line.startswith("-"):
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        for path_re, body_re in SENSITIVE_PATTERNS:
            if re.search(path_re, current) and re.search(body_re, line):
                regions.append({"path": current, "line": line[:200]})
                break
        m = _CONST_ASSIGN.match(line)
        if m:
            constants.append({"path": current, "name": m.group(1),
                              "line": line.strip()[:200]})
    return {"regions": regions, "constants": constants}


def detect_suite(tree: Path) -> Optional[list[str]]:
    """The command that runs this repo's tests, from what is on disk.

    Returns None when nothing is recognised — which the caller turns into a
    FAIL, not a skip. "We could not test it" and "it passed" must never share
    an exit code.
    """
    for marker, cmd in _SUITES:
        if (tree / marker).exists():
            return list(cmd)
    return None


def review(bundle: Path, base: str, repo: Path, branch: str,
           run_tests: bool = True, keep: bool = False,
           suite_timeout: float = 3_600.0) -> dict[str, Any]:
    """The whole check. Returns a report; raises only on a usage error.

    Every mutating command below runs inside `work`, a temp directory. The one
    command that touches `repo` is a clone, which is a read.
    """
    if not bundle.exists():
        raise GateError(f"no bundle at {bundle}")
    if not (repo / ".git").exists():
        raise GateError(f"{repo} is not a git repository")

    blockers: list[dict[str, Any]] = []
    notes: list[str] = []
    work = Path(tempfile.mkdtemp(prefix="merge-gate-"))
    clone = work / "tree"
    try:
        code, out = _run(["git", "clone", "--no-hardlinks", "--quiet",
                          "--branch", branch, str(repo), str(clone)])
        if code != 0:
            raise GateError(f"could not clone {repo} at {branch}: {out[-400:]}")

        head_code, head = _git(["rev-parse", "HEAD"], clone)
        head = head.strip() if head_code == 0 else ""

        # --- 1. base ancestry ------------------------------------------------
        code, _ = _git(["merge-base", "--is-ancestor", base, "HEAD"], clone)
        if code == 0:
            notes.append(f"base {base[:12]} is an ancestor of {branch} "
                         f"({head[:12]})")
        else:
            # UNKNOWN and NO are both blockers, with different sentences: a base
            # git cannot resolve is not a base that failed the check.
            resolved, _ = _git(["rev-parse", "--verify", f"{base}^{{commit}}"], clone)
            blockers.append(_blocker(
                "base",
                f"the declared base {base} is NOT an ancestor of {branch} — the "
                f"bundle was cut from a stale tree and merging it can silently "
                f"revert what landed since"
                if resolved == 0 else
                f"the declared base {base} does not resolve in this repository "
                f"at all — ancestry is UNKNOWN, which is not the same as fine"))

        # --- 2. it applies ---------------------------------------------------
        code, out = _git(["fetch", "--quiet", str(bundle), "*:refs/bundle/*"], clone)
        if code != 0:
            blockers.append(_blocker(
                "apply", f"the bundle could not be fetched: {out.strip()[-300:]}"))
            return _verdict(blockers, notes, {}, {}, None, base, head, branch)

        code, refs = _git(["for-each-ref", "--format=%(refname)", "refs/bundle/"], clone)
        tips = [r.strip() for r in refs.splitlines() if r.strip()]
        if not tips:
            blockers.append(_blocker(
                "apply", "the bundle carried no refs — there is nothing to merge"))
            return _verdict(blockers, notes, {}, {}, None, base, head, branch)
        tip = tips[0]
        if len(tips) > 1:
            notes.append(f"the bundle carries {len(tips)} refs; reviewing "
                         f"{tip}. Review the others separately: "
                         + ", ".join(tips))

        # THE MERGE ITSELF, in the throwaway clone.
        #
        # This block replaced a plain `checkout --detach tip`, and the
        # difference is not cosmetic — it was found by running this gate on its
        # own bundle. Checking out the TIP runs the suite on the builder's tree,
        # which by definition does not contain whatever landed on the target
        # since the bundle was cut. On the very first real run the target had
        # moved TWO commits past the declared base, so "green on the merged
        # tree" was a claim the gate had not actually tested.
        #
        # `--no-commit --no-ff`: no commit object is created, so even inside the
        # clone there is nothing that could be pushed anywhere. The worktree
        # holds the merge result and that is what the suite runs against.
        code, out = _git(["merge", "--no-commit", "--no-ff", tip], clone)
        if code != 0:
            _cf, conflicts = _git(["diff", "--name-only", "--diff-filter=U"], clone)
            blockers.append(_blocker(
                "apply",
                "the bundle does not merge cleanly into "
                f"{branch} ({head[:12]}) — conflicts in: "
                + (", ".join(conflicts.split()) or "unknown files")
                + ". Rebase the builder branch and re-cut the bundle",
                output=out.strip()[-400:]))
            return _verdict(blockers, notes, {}, {}, None, base, head, branch)

        # --- 3. what it changes ---------------------------------------------
        code, names = _git(["diff", "--name-only", f"{head}...{tip}"], clone)
        if code != 0:
            blockers.append(_blocker(
                "unknown", "the diff against the merge target could not be read, "
                           "so WHICH surfaces this touches is unknown — a merge "
                           "gate that cannot see the diff has not checked it"))
            paths: list[str] = []
        else:
            paths = [p.strip() for p in names.splitlines() if p.strip()]
        buckets = classify_paths(paths)

        code, diff_text = _git(["diff", "--unified=0", f"{head}...{tip}"], clone,
                               timeout=300.0)
        scan = scan_diff(diff_text) if code == 0 else {"regions": [], "constants": []}
        if code != 0:
            blockers.append(_blocker(
                "unknown", "the unified diff could not be read, so sensitive "
                           "REGIONS and moved constants were not scanned at all"))

        if buckets["forbidden"]:
            blockers.append(_blocker(
                "forbidden",
                "this bundle touches surfaces no agent-authored diff may touch. "
                "There is no review that clears this — remove the files: "
                + ", ".join(buckets["forbidden"]),
                paths=buckets["forbidden"]))
        if buckets["sensitive"]:
            blockers.append(_blocker(
                "sensitive",
                "this bundle changes money- or approval-critical files, so it "
                "cannot be merged on this gate alone — it goes to the adversary "
                "blind first (constitution: 'sensitive diffs also pass the "
                "adversary blind'): " + ", ".join(buckets["sensitive"]),
                paths=buckets["sensitive"]))
        if scan["regions"]:
            blockers.append(_blocker(
                "sensitive",
                f"{len(scan['regions'])} changed line(s) fall inside the "
                f"approval-guard region — same route, adversary blind first",
                lines=scan["regions"][:20]))
        if scan["constants"]:
            # Reported, never blocking on its own: a new constant in a new file
            # is ordinary. A human reads the list; the gate refuses to guess
            # which of them is a threshold.
            notes.append(
                f"{len(scan['constants'])} numeric constant(s) added or changed — "
                f"read each one and confirm none is a threshold moving without a "
                f"written reason: "
                + ", ".join(sorted({c['name'] for c in scan['constants']})))

        # --- 4. the suite, on the ACTUAL merge result ------------------------
        # The worktree now holds target + bundle. Not the builder's tree: the
        # builder's own green run says the diff works in isolation, and the only
        # thing that says it works HERE is this.
        suite: Optional[dict[str, Any]] = None
        if run_tests:
            cmd = detect_suite(clone)
            if cmd is None:
                blockers.append(_blocker(
                    "unknown",
                    "no test suite was recognised in this repository, so the "
                    "merged tree is UNVERIFIED. Unverified is a fail here, not "
                    "a skip"))
            else:
                code, out = _run(cmd, cwd=clone, timeout=suite_timeout)
                tail = "\n".join(out.strip().splitlines()[-12:])
                suite = {"command": " ".join(cmd), "exit_code": code, "tail": tail}
                if code != 0:
                    blockers.append(_blocker(
                        "tests",
                        f"the suite FAILED on the merged tree (exit {code}). The "
                        f"builder's own green run says the diff works in "
                        f"isolation; only this says it works here",
                        tail=tail))
        else:
            blockers.append(_blocker(
                "unknown",
                "tests were skipped by request, so this report says nothing "
                "about whether the merged tree works. It cannot PASS"))

        return _verdict(blockers, notes, buckets, scan, suite, base, head, branch)
    finally:
        if keep:
            print(f"[kept] {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)


def _verdict(blockers, notes, buckets, scan, suite, base, head, branch
             ) -> dict[str, Any]:
    passed = not blockers
    return {
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "branch": branch,
        "declared_base": base,
        "merge_target_head": head,
        "blockers": blockers,
        "notes": notes,
        "changed": buckets,
        "scan": scan,
        "suite": suite,
        "merged": False,
        "note": ("every check cleared — this gate is satisfied. It has NOT "
                 "merged anything and cannot: the merge is a human action, "
                 "taken with this report in hand"
                 if passed else
                 f"{len(blockers)} blocker(s). This does not mean the work is "
                 f"wrong — a sensitive-surface blocker means it needs the "
                 f"adversary, not that it is bad. It means it is not mergeable "
                 f"on this gate alone"),
    }


def render(report: dict[str, Any]) -> str:
    """The report a human reads. One word, then the reasons."""
    L = [f"MERGE GATE: {report['verdict']}",
         f"  branch        {report['branch']}",
         f"  merge target  {(report['merge_target_head'] or '?')[:12]}",
         f"  declared base {report['declared_base'][:12]}"]
    ch = report.get("changed") or {}
    L.append(f"  changed       {len(ch.get('ordinary') or [])} ordinary, "
             f"{len(ch.get('sensitive') or [])} sensitive, "
             f"{len(ch.get('forbidden') or [])} forbidden")
    s = report.get("suite")
    L.append("  suite         " + (
        f"{s['command']} -> exit {s['exit_code']}" if s else "NOT RUN"))
    if s and s.get("tail"):
        L += ["", "  suite tail, verbatim:"]
        L += [f"    {ln}" for ln in s["tail"].splitlines()]
    if report["blockers"]:
        L += ["", "BLOCKERS"]
        for b in report["blockers"]:
            L.append(f"  [{b['kind']}] {b['detail']}")
    if report["notes"]:
        L += ["", "NOTES"]
        L += [f"  - {n}" for n in report["notes"]]
    L += ["", f"{report['note']}",
          "", "This script gates a merge. It has performed none."]
    return "\n".join(L)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--base", required=True,
                    help="the commit the bundle was cut from")
    ap.add_argument("--repo", type=Path, default=Path.cwd(),
                    help="the repository to merge INTO (cloned, never written)")
    ap.add_argument("--branch", default="claude/krypton-fund-agentic-j8r2mu")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--skip-tests", action="store_true",
                    help="report cannot PASS; for a fast surface-only look")
    ap.add_argument("--keep", action="store_true", help="keep the temp clone")
    ap.add_argument("--suite-timeout", type=float, default=3_600.0)
    a = ap.parse_args(argv)
    try:
        report = review(a.bundle.resolve(), a.base, a.repo.resolve(), a.branch,
                        run_tests=not a.skip_tests, keep=a.keep,
                        suite_timeout=a.suite_timeout)
    except GateError as e:
        print(f"merge_builder: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=1) if a.json else render(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(main())
