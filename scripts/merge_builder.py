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
     the ones it may touch only with an adversary review behind it. By NAME,
     by SHAPE (`SENSITIVE_GLOBS`, so the guard nobody has written yet is
     covered), by CONTENT on both the added and the REMOVED side, and by
     CONTROL FLOW: `scan_control_flow` reads the merged tree's syntax and
     flags any changed line that sits inside — or feeds — a refusal, whatever
     the code happens to be called.

     Checks 4's last two parts exist because this gate was measured and found
     blind twice. `app/fund/ticketguard.py`, an entire guard module, scored as
     ORDINARY; and a keyword filter missed `_real_broker()` becoming
     `_broker_is_real()` at two guards on an endpoint that appends ORDER_FILLED
     to the real ledger. The adversary's sentence is the design brief for the
     AST scan: *a keyword filter is standing in for a control-flow question*.

AND ONE THING IT REPORTS WITHOUT JUDGING: the janitor's advisory scan (ruff
F-set, vulture-80, ts-prune) over the files this diff touches. It never blocks
— a gate that auto-blocked on a dead-code heuristic would manufacture false
urgency — and every tool says whether it was AVAILABLE, because "found
nothing" and "not installed" are the same empty list and opposite facts.

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
import builtins
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

#: The same list, for files that DO NOT EXIST YET.
#:
#: MEASURED FAILURE, adversary run-adversary-hw5-kp6: `app/fund/ticketguard.py`
#: — an entire guard module — classified as ORDINARY, because the list above is
#: matched by equality and nobody added the new file to it. A named list only
#: covers the guards someone remembered, and the guard that matters next is the
#: one written after the list was last edited. The consequence the adversary
#: recorded, and it is the right way to read every "0 sensitive" this gate has
#: printed since: UNPROVEN, not clear.
SENSITIVE_GLOBS: tuple[str, ...] = (
    "app/fund/*guard*.py",
    # Every autopolicy module, drafts included. NAMED BY SHAPE ONLY, and that
    # is load-bearing: the draft envelope's own test module greps `app/**` and
    # `scripts/**` for any reference to the draft BY NAME, because a draft
    # something references is not a draft. Writing that filename in this
    # comment made THIS file an offender against that guard — twice, because
    # the first repair named the test module instead.
    "app/fund/autopolicy*.py",
    "app/api/v1/*guard*.py",
    "app/fund/projections/nav.py",  # the fold the whole ledger rests on
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
     r"allowlist|_guard_|approver|GUARD_VERSION|autopolicy|/approve|confirm"
     # ADDED after the same review found the vocabulary too narrow: the hw5
     # diff loosened a refusal control 37->20, bumped
     # LEGACY_REDECISION_GUARD_VERSION and changed a producer of
     # EventType.APPROVAL_REFUSED, and this pattern scored ZERO on it.
     r"|APPROVAL_REFUSED|ApprovalRefused|_refuse_if_|redecision|ticketguard"),
    # ANY file that writes an order event to the ledger. The vocabulary above
    # has no term for `backfill`, and `/fund/venue/backfill` appends
    # ORDER_FILLED to the real ledger — the endpoint whose guard rename this
    # gate missed the first time it was used in anger.
    (r"^app/.*\.py$", r"EventType\.ORDER_[A-Z_]+"),
    # PREDICATE RENAMES, which is the shape the miss actually took:
    # `_real_broker()` became `_broker_is_real()` and flipped one of eight flag
    # combinations from refuse to allow. The names are a heuristic; the AST
    # scan below is the part that does not depend on what a predicate is
    # called.
    (r"^app/.*\.py$", r"def\s+_?(?:\w*_is_\w*|real_\w+|_real_\w+|\w*_allowed\w*)\s*\("),
)

#: Refusal vocabulary, matched on ADDED **and REMOVED** lines.
#:
#: The removed side is the half a content scan usually forgets, and it is the
#: half that carries a deletion: the adversary's hand-made falsifier for this
#: gate was `+ refusal = None  # guard disabled`, and the sibling of that diff
#: is one that simply DELETES the guard call. A gate blind to removals cannot
#: see a control being taken out.
_REFUSAL_TEXT = re.compile(
    r"raise\s+HTTPException|status_code\s*=\s*40[0-9]|"
    r"\brefus\w*|\bdeny\b|\bforbid\w*|\bblocked\b")

#: The exceptions that REFUSE A REQUEST, as opposed to the ones that report a
#: problem. `HTTPException` is the fund's refusal: it is what the approval
#: path, the redecision guard and every endpoint raise to say no.
#:
#: MEASURED, and this is the difference between a check and a nuisance: with
#: any conditional `raise` counted, the control-flow scan returned **289 hits
#: on a seven-file diff that touched no control** — `BarsError` on a stale
#: price series is a data-quality refusal and has nothing to do with approvals.
#: A guard module raising its OWN class is still covered, by `SENSITIVE_GLOBS`.
REFUSAL_EXCEPTIONS: tuple[str, ...] = ("HTTPException",)

#: Names too common to carry information. `isinstance`, `get` and `str` appear
#: in nearly every guard AND in nearly every other line, so a predicate scan
#: that keeps them is a full-text match wearing a control-flow costume.
_UBIQUITOUS_NAMES = frozenset(dir(builtins)) | frozenset({
    "get", "keys", "values", "items", "strip", "lower", "upper", "split",
    "append", "startswith", "endswith", "isoformat", "value", "name",
    "self", "cls", "args", "kwargs", "payload", "data", "text", "json",
})

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
#:
#: The KryptonPay entry quotes its glob so NODE expands it, not the shell. That
#: is not a style choice and it cost a wrong number to find: this seat had been
#: running `src/app/clark/studio/**/*.test.ts` through bash, where `**` without
#: `globstar` means `*` — one directory level — so a nested suite
#: (`studio/desk/floor/`) was silently never run and the reported total was 163
#: when the truth was 183. A merge gate quoting a short count is worse than one
#: quoting none, so the glob is passed through as a single argument.
_SUITES: tuple[tuple[str, list[str]], ...] = (
    ("pytest.ini", [sys.executable, "-m", "pytest", "-q"]),
    ("next.config.ts", ["node", "--experimental-strip-types", "--test",
                        "src/app/clark/**/*.test.ts"]),
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
    import fnmatch

    forbidden = [p for p in paths
                 if any(p.startswith(f) or f.rstrip("/") in p
                        for f in FORBIDDEN_PATHS)]
    # BY NAME **OR BY SHAPE**. The equality test alone is why a whole guard
    # module read as ordinary; a glob covers the guard nobody has written yet.
    sensitive = [p for p in paths
                 if p in SENSITIVE_PATHS
                 or any(fnmatch.fnmatch(p, g) for g in SENSITIVE_GLOBS)]
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
    removals: list[dict[str, str]] = []
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
        # THE REMOVED SIDE. A control taken OUT leaves no added line to match,
        # and a scan that only reads `+` lines cannot see a deletion at all.
        if (line.startswith("-") and current.startswith("app/")
                and current.endswith(".py") and _REFUSAL_TEXT.search(line)):
            removals.append({"path": current, "line": line.strip()[:200]})
        m = _CONST_ASSIGN.match(line)
        if m:
            constants.append({"path": current, "name": m.group(1),
                              "line": line.strip()[:200]})
    return {"regions": regions, "constants": constants, "removals": removals}


def changed_lines(diff_text: str) -> dict[str, set[int]]:
    """Which NEW-side line numbers a unified diff touches, per path.

    Line numbers rather than text, because the question the control-flow scan
    asks is "where in the file is this", and matching on text cannot answer it.
    Reads the ``@@ -a,b +c,d @@`` headers, so it needs no context lines and
    works on the ``--unified=0`` diff the gate already takes.
    """
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    out: dict[str, set[int]] = {}
    current = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
            continue
        m = hunk.match(line)
        if m and current:
            start = int(m.group(1))
            count = int(m.group(2) if m.group(2) is not None else 1)
            out.setdefault(current, set()).update(range(start, start + count))
    return out


def refusal_predicates(source: str) -> dict[str, Any]:
    """Every name a REFUSAL in this file depends on, and where those refusals live.

    THE MEASURED REASON, and it is the sharpest criticism this gate has taken
    (adversary, run-adversary-d8): *"a keyword filter is standing in for a
    control-flow question."* The vocabulary list missed ``_real_broker()``
    becoming ``_broker_is_real()`` at two ``/fund/venue/backfill`` guards,
    which flipped one of eight flag combinations from refuse to allow on an
    endpoint that appends ORDER_FILLED to the real ledger. No word in the list
    describes a backfill, a ledger write, or a predicate rename — and no word
    ever will, because the property that matters is not what the code is
    CALLED but what it GATES.

    So this reads the syntax instead. A function that can raise one of
    ``REFUSAL_EXCEPTIONS`` from inside an ``if`` is a refusal site; the names
    in that ``if``'s test — minus the ubiquitous ones, see
    ``_UBIQUITOUS_NAMES`` — are what the refusal depends on; and the function's
    own line range is the region a diff cannot touch invisibly.

    MEASURED on ``app/api/v1/fund.py`` (2026-08-27): **60 refusal regions, 61
    guarding names, 1,972 of 7,760 lines — 25.4% of the file** inside a
    refusing function. That last figure is the one that decides whether this is
    a check or a nuisance: flagging the whole file would tell nobody anything,
    which is why the content pattern above exists in the first place.
    Reproduce by folding the file through this function and unioning the region
    ranges.

    The first version of that measurement read 38 regions and 20.6%, and the
    difference is not drift — it is 22 functions that were INVISIBLE because
    the ubiquitous-name filter ran before the region test, so a refusal guarded
    entirely on names like ``req``, ``ok`` or ``abs`` produced an empty guard
    set and was recorded as no refusal at all.

    THE BOUNDARY, stated rather than left to be discovered: this is
    WITHIN-FILE. A predicate defined in another module and merely called here
    is caught only if the CALL is on a guarding line — cross-module dataflow is
    not something a merge gate can do, and pretending otherwise would be the
    same false reassurance as the keyword filter.

    ``readable: False`` when the source will not parse. The caller turns that
    into a blocker: this gate's rule is that anything unknown is a FAIL.
    """
    import ast

    out: dict[str, Any] = {"readable": False, "names": set(), "regions": [],
                           "note": None}
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as e:
        out["note"] = (f"the file did not parse ({type(e).__name__}: {e}), so "
                       f"which of its lines gate a refusal is UNKNOWN")
        return out
    out["readable"] = True

    def _names_in(node: Any) -> set[str]:
        found: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                found.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                found.add(sub.attr)
        return found

    def _raised_name(node: Any) -> str:
        exc = getattr(node, "exc", None)
        exc = exc.func if isinstance(exc, ast.Call) else exc
        if isinstance(exc, ast.Name):
            return exc.id
        if isinstance(exc, ast.Attribute):
            return exc.attr
        return ""

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # A PURE EARLY EXIT, and deliberately NOT a second copy of "what counts
        # as a refusal". It only asks whether this function raises at all, so
        # it cannot disagree with the one place that decides — the
        # `REFUSAL_EXCEPTIONS` test in the branch loop below.
        #
        # It was a second copy, and mutation is what said so: filtering by
        # exception name in BOTH places made each copy invisible to the tests,
        # because breaking either one left the other enforcing the same rule.
        # Two copies of one belief are also two places for it to drift.
        if not any(isinstance(n, ast.Raise) for n in ast.walk(fn)):
            continue
        guards: set[str] = set()
        for branch in ast.walk(fn):
            # `ast.If` ONLY, and deliberately not `ast.IfExp`. A ternary's
            # body and orelse are single EXPRESSIONS, not statement lists, so
            # treating the two alike raised `'Constant' object is not
            # iterable` on the first real file this ran against — and a
            # ternary cannot contain a `raise` in any case, because `raise` is
            # a statement. Whether a ternary's RESULT later feeds a refusal is
            # cross-statement dataflow, which is outside what a merge gate can
            # honestly claim to see.
            if not isinstance(branch, ast.If):
                continue
            # THE ONE PLACE THAT DECIDES WHAT A REFUSAL IS, and the narrowing
            # is measured rather than fastidious. Counting any conditional
            # `raise` produced **289 hits on a seven-file diff that touched no
            # control at all** — `marketdata.py` raising `BarsError` on a stale
            # price series is a data-quality answer, not an approval one, and a
            # gate that fires on every new `raise` inside an `if` is a gate the
            # chair learns to scroll past. That is exactly the failure the
            # fund.py content pattern exists to avoid, rebuilt one layer down.
            reachable = [n
                         for stmt in list(branch.body) + list(branch.orelse)
                         for n in ast.walk(stmt)
                         if isinstance(n, ast.Raise)
                         and _raised_name(n) in REFUSAL_EXCEPTIONS]
            if reachable:
                guards |= _names_in(branch.test)
        if not guards:
            # It raises, but not from a condition — an unconditional raise is
            # not a control this gate can be loosened through, and calling it
            # one would flood the report.
            continue
        # THE FILTER APPLIES TO THE PREDICATE LEG ONLY, NEVER TO REGION-HOOD.
        # `isinstance`, `get`, `str` and `len` appear in almost every guard AND
        # in almost every other line, and short names like `ok` or `id` are
        # loop variables everywhere, so a text match on them is a full-text
        # match on the diff. But whether a function REFUSES has nothing to do
        # with what its variables are called.
        #
        # The first version filtered before the region test, so a refusal
        # gated entirely on a two-character name — `if not ok: raise
        # HTTPException(...)` — was invisible to BOTH legs. A test written to
        # prove the region leg still covered that case is what found it.
        useful = {n for n in guards
                  if n not in _UBIQUITOUS_NAMES and len(n) > 2}
        out["names"] |= useful
        out["regions"].append({
            "function": fn.name,
            "first_line": fn.lineno,
            "last_line": getattr(fn, "end_lineno", fn.lineno) or fn.lineno,
            # EVERY guarding name, filtered or not — this is what a human reads
            # to see why the function was flagged, and hiding `ok` from that
            # sentence would make the flag unexplainable.
            "guards": sorted(guards),
        })
    return out


def scan_control_flow(changed: dict[str, set[int]],
                      read_file: Any) -> dict[str, list[dict[str, Any]]]:
    """Changed lines that sit inside, or feed, a refusal — whatever they are called.

    ``read_file(path) -> str | None`` is injected so this is testable without a
    clone, a bundle or a subprocess. A path that cannot be read is REPORTED as
    unreadable rather than skipped: a file the gate could not open is a file
    the gate did not check, and those are different from a file it cleared.
    """
    hits: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    for path in sorted(changed):
        if not path.endswith(".py") or not path.startswith("app/"):
            continue
        source = read_file(path)
        if source is None:
            unreadable.append({"path": path,
                               "reason": "the file could not be read at the "
                                         "merged tree, so its refusals were "
                                         "not examined"})
            continue
        info = refusal_predicates(source)
        if not info["readable"]:
            unreadable.append({"path": path, "reason": info["note"]})
            continue
        if not info["regions"]:
            continue
        lines = source.splitlines()
        for lineno in sorted(changed[path]):
            text = lines[lineno - 1].strip()[:200] if 0 < lineno <= len(lines) else ""
            inside = [r for r in info["regions"]
                      if r["first_line"] <= lineno <= r["last_line"]]
            if inside:
                hits.append({"path": path, "line": lineno, "text": text,
                             "why": f"inside {inside[0]['function']}(), which "
                                    f"refuses on "
                                    f"{', '.join(inside[0]['guards'][:6])}"})
                continue
            # ASSIGNED OR DEFINED on this line, not merely MENTIONED on it.
            # The mention test matched prose in docstrings and comments and
            # was most of the 289-hit flood; the adversary's ask was narrower
            # and better — *"any changed line that ALTERS a boolean used in a
            # refusal"* — and altering means assigning or defining.
            touched = sorted(n for n in info["names"]
                             if re.match(rf"(?:async\s+)?def\s+{re.escape(n)}\b", text)
                             or re.match(rf"{re.escape(n)}\s*(?::[^=]+)?=(?!=)", text))
            if touched:
                hits.append({"path": path, "line": lineno, "text": text,
                             "why": "assigns or defines " + ", ".join(touched[:6])
                                    + ", which a refusal in this file reads"})
    return {"hits": hits, "unreadable": unreadable}


#: The janitor's merge-time scan, per the code-discipline program
#: (docs/design/CODE_DISCIPLINE_2026-08-27.md, instrument 1). **ADVISORY —
#: it reports and the chair decides.** A gate that auto-blocked on a
#: dead-code heuristic would manufacture false urgency, and this firm's one
#: measured accretion problem is 96:1 insertions to deletions, not a stray
#: unused import.
#:
#: Scoped to the files the diff TOUCHES rather than the tree: a whole-tree
#: census belongs to the weekly pass, and a report that opens with 30
#: pre-existing findings is one nobody reads.
_JANITOR_EXCLUDE = ("app/fund/thesis_generator/", "src/app/clark/studio/thesis/")


def janitor_scan(tree: Path, paths: list[str]) -> dict[str, Any]:
    """Dead imports, dead variables and dead exports among the touched files.

    Never a blocker and never counted in the verdict. Every tool is reported
    with whether it was AVAILABLE, because "ruff found nothing" and "ruff is
    not installed" are the same empty list and opposite facts.
    """
    py = [p for p in paths
          if p.endswith(".py") and not any(p.startswith(x) for x in _JANITOR_EXCLUDE)
          and (tree / p).exists()]
    ts = [p for p in paths
          if p.endswith((".ts", ".tsx"))
          and not any(p.startswith(x) for x in _JANITOR_EXCLUDE)]
    tools: list[dict[str, Any]] = []

    if py:
        code, out = _run([sys.executable, "-m", "ruff", "check",
                          "--select", "F401,F811,F841", "--no-cache",
                          "--output-format", "concise", *py],
                         cwd=tree, timeout=180.0)
        available = code in (0, 1)
        tools.append({
            "tool": "ruff F401/F811/F841", "available": available,
            "findings": ([ln.strip() for ln in out.splitlines()
                          if re.search(r":\d+:\d+: F\d", ln)] if available else []),
            "note": None if available else f"could not run ruff: {out.strip()[-200:]}",
        })
        code, out = _run([sys.executable, "-m", "vulture",
                          "--min-confidence", "80", *py],
                         cwd=tree, timeout=180.0)
        available = code in (0, 3)
        tools.append({
            "tool": "vulture >=80%", "available": available,
            "findings": ([ln.strip() for ln in out.splitlines()
                          if re.search(r":\d+: ", ln)] if available else []),
            "note": None if available else f"could not run vulture: {out.strip()[-200:]}",
        })
    if ts:
        code, out = _run(["npx", "--no-install", "ts-prune"], cwd=tree, timeout=300.0)
        available = code == 0
        touched = {p.split("/")[-1] for p in ts}
        tools.append({
            "tool": "ts-prune", "available": available,
            "findings": ([ln.strip() for ln in out.splitlines()
                          if any(name in ln for name in touched)]
                         if available else []),
            "note": None if available else
                    "ts-prune is not installed in this tree, so dead TypeScript "
                    "exports among the touched files were NOT checked",
        })
    return {"tools": tools,
            "files_scanned": {"python": len(py), "typescript": len(ts)}}


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
            return _verdict(blockers, notes, {}, {}, None, base, head, branch,
                                {}, None)

        code, refs = _git(["for-each-ref", "--format=%(refname)", "refs/bundle/"], clone)
        tips = [r.strip() for r in refs.splitlines() if r.strip()]
        if not tips:
            blockers.append(_blocker(
                "apply", "the bundle carried no refs — there is nothing to merge"))
            return _verdict(blockers, notes, {}, {}, None, base, head, branch,
                                {}, None)
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
            return _verdict(blockers, notes, {}, {}, None, base, head, branch,
                                {}, None)

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
        scan = (scan_diff(diff_text) if code == 0 else
                {"regions": [], "constants": [], "removals": []})
        control: dict[str, list[dict[str, Any]]] = {"hits": [], "unreadable": []}
        if code != 0:
            blockers.append(_blocker(
                "unknown", "the unified diff could not be read, so sensitive "
                           "REGIONS, moved constants and refusal control flow "
                           "were not scanned at all"))
        else:
            # THE CONTROL-FLOW QUESTION, asked of the MERGED tree rather than of
            # the diff's words. Reading the merged tree is the point: what a
            # changed line gates is a property of the file it lands in.
            def _read(rel: str) -> Optional[str]:
                try:
                    return (clone / rel).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    return None

            control = scan_control_flow(changed_lines(diff_text), _read)

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
        if scan.get("removals"):
            blockers.append(_blocker(
                "sensitive",
                f"{len(scan['removals'])} line(s) carrying refusal vocabulary "
                f"were REMOVED. A control taken out leaves no added line to "
                f"match, so this is read as a loosening until a human says "
                f"otherwise — adversary blind first",
                lines=scan["removals"][:20]))
        if control["hits"]:
            blockers.append(_blocker(
                "sensitive",
                f"{len(control['hits'])} changed line(s) sit inside, or feed, a "
                f"REFUSAL in their own file — whatever the code is called. This "
                f"is the check that does not depend on vocabulary, and the "
                f"vocabulary is what missed `_real_broker` becoming "
                f"`_broker_is_real` at two ledger-writing guards",
                lines=control["hits"][:20]))
        if control["unreadable"]:
            blockers.append(_blocker(
                "unknown",
                f"{len(control['unreadable'])} changed Python file(s) could not "
                f"be parsed at the merged tree, so whether their lines gate a "
                f"refusal is UNKNOWN — which is a fail here, not a skip",
                lines=control["unreadable"][:20]))
        if scan["constants"]:
            # Reported, never blocking on its own: a new constant in a new file
            # is ordinary. A human reads the list; the gate refuses to guess
            # which of them is a threshold.
            notes.append(
                f"{len(scan['constants'])} numeric constant(s) added or changed — "
                f"read each one and confirm none is a threshold moving without a "
                f"written reason: "
                + ", ".join(sorted({c['name'] for c in scan['constants']})))

        # --- 3b. the janitor's advisory scan ---------------------------------
        # ADVISORY, and it never touches `blockers`. It rides here because the
        # gate already knows exactly which files a diff touches, which is the
        # scope the code-discipline program asked for.
        janitor = janitor_scan(clone, paths)

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

        return _verdict(blockers, notes, buckets, scan, suite, base, head,
                        branch, control, janitor)
    finally:
        if keep:
            print(f"[kept] {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)


def _verdict(blockers, notes, buckets, scan, suite, base, head, branch,
             control=None, janitor=None) -> dict[str, Any]:
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
        "control_flow": control or {"hits": [], "unreadable": []},
        # ADVISORY and named as such in the payload, so a reader
        # cannot mistake a janitor finding for a blocker.
        "janitor_advisory": janitor,
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
    cf = report.get("control_flow") or {}
    L.append(f"  refusal lines {len(cf.get('hits') or [])} touched, "
             f"{len(cf.get('unreadable') or [])} file(s) unparsed")
    jan = report.get("janitor_advisory")
    if jan:
        L += ["", "JANITOR (ADVISORY — reports, never blocks)"]
        for t in jan.get("tools", []):
            if not t.get("available"):
                L.append(f"  {t['tool']}: NOT RUN — {t.get('note')}")
                continue
            found = t.get("findings") or []
            L.append(f"  {t['tool']}: {len(found)} finding(s)"
                     + (" — none" if not found else ""))
            L += [f"      {ln}" for ln in found[:15]]
        fs = jan.get("files_scanned") or {}
        L.append(f"  scanned {fs.get('python', 0)} python and "
                 f"{fs.get('typescript', 0)} typescript file(s) from this diff")
    if report["blockers"]:
        L += ["", "BLOCKERS"]
        for b in report["blockers"]:
            L.append(f"  [{b['kind']}] {b['detail']}")
            for ln in (b.get("lines") or [])[:6]:
                L.append("      " + json.dumps(ln, ensure_ascii=False)[:220])
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
