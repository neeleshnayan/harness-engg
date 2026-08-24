"""THE POISONED-CACHE SCANNER — does this tree SERVE bytecode its source denies?

BORN 2026-08-24 (builder D41), from a dispatch that opened with twelve red
tests and no defect. The tests were right, the module was right, and the
interpreter was executing neither: `app/fund/__pycache__/statistics.pyc` held
`1.1 / sqrt(k)` where `app/fund/statistics.py` held `1.0 / sqrt(k)`, the
mutation-pass numerator of a previous session. `git status` reported a clean
tree, the source read correctly, and every suite run in that worktree was
scored against the mutant.

WHY PYTHON SERVED IT. A timestamped `.pyc` is invalidated on exactly two facts
about its source: the mtime (SECOND resolution) and the byte SIZE. A mutation
harness that edits a constant IN PLACE without changing the byte length
(`1.0` -> `1.1` is the canonical shape, and it is the shape this codebase's own
mutation harnesses use) and restores the file inside the same wall-clock second
leaves both facts identical. The cache is then a valid cache of a file that no
longer exists.

WHY IT MATTERS MORE THAN IT LOOKS. This is the unwired-kill-switch pattern
pointed at the verification layer itself: the surviving artifact of a
CORRECTNESS check silently decides what every later check measures. It is
invisible to `git status`, to a diff, to a code review, and to the suite — the
suite is the thing being lied to. D35 recorded a mutant reaching HEAD through
an overlapping `git add -A` and answered it with "verify by FRESH CHECKOUT".
That rule works here for the accidental reason that a fresh checkout has no
`__pycache__` — this scanner makes the check direct rather than incidental.

WHAT IT COMPARES. Recompile each source with the import machinery's own
settings and walk the code tree against the cached one, reporting the FIRST
differing node by qualified name WITH BOTH VALUES. A comparison that only says
"these differ" is not evidence; `/lean_psr_target: CONSTANT source=1.0
cached=1.1` is.

WHAT IT DELIBERATELY DOES NOT COMPARE, because each produced FALSE findings on
this scanner's own first pass (11 files reported, 1 real):
  * `co_varnames` and set/frozenset ORDER — both marshal in iteration order and
    differ run to run on identical bytes.
  * anything compiled with inherited `__future__` flags. `compile()` inherits
    the CALLER's futures by default, and this file carries
    `from __future__ import annotations`, so every scanned module WITHOUT that
    import was being compiled under postponed annotations and disagreeing with
    its own honest cache. That single missing `dont_inherit=True` was 7 of the
    8 files the first pass accused: an instrument manufacturing the finding it
    was built to detect.

THE DISTINCTION THAT IS THE WHOLE FINDING: a disagreeing cache whose
invalidation key does NOT match is harmless — the interpreter throws it away.
Only a disagreement WITH a matching key can poison a run. The two are counted
separately and never summed.

Usage:
    python scripts/instruments/stale_pyc_scan.py <root>
    python scripts/instruments/stale_pyc_scan.py <root> --null   # see below
    python scripts/instruments/stale_pyc_scan.py <root> --clear  # remove caches

`--null` is the instrument's own null test: clear every cache, repopulate with
`compileall` (the import machinery's compiler, over every file — NOT `import`,
which this repo refuses without FUND_MODE and FUND_STORE), and require zero
poisonous results against a NON-EMPTY domain. The first version of that test
shelled out through a quoted path containing a space, the repopulation never
happened, and it reported zero against 384 files it had not compared — a green
light wired to nothing. The `agree=` count is printed for exactly that reason.

Exit 1 if anything poisonous is found, 2 if the null test could not be run.
"""
from __future__ import annotations

import marshal
import pathlib
import shutil
import struct
import sys
from typing import Any, Iterable, NamedTuple

#: Trees whose caches nobody serves and whose sources are allowed to be odd.
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "venv", ".venv",
             "lean_workspace", "site-packages"}


class Finding(NamedTuple):
    source: pathlib.Path
    detail: str
    served: bool          # True = Python WILL execute this cache: poisonous


def cached_path(src: pathlib.Path) -> pathlib.Path:
    tag = f"cpython-{sys.version_info[0]}{sys.version_info[1]}"
    return src.parent / "__pycache__" / f"{src.stem}.{tag}.pyc"


def _norm(c: Any) -> Any:
    """Canonicalise a constant so that only MEANING differences survive."""
    if isinstance(c, (frozenset, set)):
        return ("set", tuple(sorted(repr(x) for x in c)))
    if isinstance(c, tuple):
        return ("tuple", tuple(_norm(x) for x in c))
    return repr(c)


def first_difference(fresh: Any, cached: Any, path: str = "") -> str | None:
    """The qualified name of the first node whose code or constants differ."""
    where = path or "<module>"
    if fresh.co_code != cached.co_code:
        return f"{where}: BYTECODE differs"
    if fresh.co_names != cached.co_names:
        return (f"{where}: NAMES differ "
                f"({sorted(set(fresh.co_names) ^ set(cached.co_names))})")
    if len(fresh.co_consts) != len(cached.co_consts):
        return (f"{where}: constant COUNT differs "
                f"({len(fresh.co_consts)} vs {len(cached.co_consts)})")
    for x, y in zip(fresh.co_consts, cached.co_consts):
        if hasattr(x, "co_code") and hasattr(y, "co_code"):
            deeper = first_difference(x, y, f"{path}/{x.co_name}")
            if deeper:
                return deeper
        elif _norm(x) != _norm(y):
            return f"{where}: CONSTANT source={x!r} cached={y!r}"
    return None


def key_matches(src: pathlib.Path, pyc: pathlib.Path) -> bool:
    """True when Python will SERVE this cache in preference to the source.

    THREE HEADER SHAPES, and they do not answer this question the same way.
    PEP 552 puts two flags after the magic: bit 0 `hash_based`, bit 1
    `check_source`. VERIFIED BY CONSTRUCTION rather than from memory — the
    three `py_compile.PycInvalidationMode` values produce flags 0b0000,
    0b0011 and 0b0001 respectively:

      * TIMESTAMP (0b0000) — validated on the source's mtime and size, both
        stored in this header. This is what CPython writes by default and what
        this repo contains. Served iff both still match, which is exactly the
        loophole a same-length in-place edit walks through.
      * CHECKED_HASH (0b0011) — the interpreter hashes the source on every
        import, so a disagreeing cache is NEVER served. Reporting one as
        poisonous would be a false alarm.
      * UNCHECKED_HASH (0b0001) — never validated against anything. ALWAYS
        served, which makes it the most dangerous shape of the three, not the
        most exotic.

    The first draft of this function returned True for both hash shapes on the
    reasoning that "there is no timestamp to compare". That is conservative in
    one direction and simply wrong in the other, and conservative-but-wrong on
    a detector is how an instrument earns the distrust of the people reading it.
    """
    _magic, flags, mtime, size = struct.unpack("<4sIII", pyc.read_bytes()[:16])
    if flags & 0b01:                                   # hash-based
        return not flags & 0b10                        # served unless checked
    st = src.stat()
    return mtime == int(st.st_mtime) and size == st.st_size


def sources(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for src in sorted(root.rglob("*.py")):
        if not SKIP_DIRS.isdisjoint(src.parts):
            continue
        yield src


def scan(root: pathlib.Path) -> tuple[list[Finding], dict[str, int]]:
    """Returns (findings, counts). `counts['agree']` is the null domain size."""
    findings: list[Finding] = []
    counts = {"agree": 0, "no_cache": 0, "unreadable": 0,
              "poisonous": 0, "stale_not_served": 0}
    for src in sources(root):
        pyc = cached_path(src)
        if not pyc.exists():
            counts["no_cache"] += 1
            continue
        try:
            # `dont_inherit=True` IS LOAD-BEARING — see the module docstring.
            fresh = compile(src.read_text(encoding="utf-8"), str(src), "exec",
                            dont_inherit=True)
            cached = marshal.loads(pyc.read_bytes()[16:])
            detail = first_difference(fresh, cached)
            served = key_matches(src, pyc)
        except Exception as exc:            # a scanner REPORTS, never raises
            counts["unreadable"] += 1
            findings.append(Finding(src, f"could not be compared: {exc!r}",
                                    served=False))
            continue
        if detail is None:
            counts["agree"] += 1
        else:
            findings.append(Finding(src, detail, served))
            counts["poisonous" if served else "stale_not_served"] += 1
    return findings, counts


def clear(root: pathlib.Path) -> int:
    removed = 0
    for d in sorted(root.rglob("__pycache__")):
        if ".git" in d.parts:
            continue
        shutil.rmtree(d, ignore_errors=True)
        removed += 1
    return removed


def _report(findings: list[Finding], counts: dict[str, int]) -> None:
    print(" ".join(f"{k}={v}" for k, v in counts.items()))
    for f in findings:
        print(f"  {'POISONOUS' if f.served else 'stale-not-served'} {f.source}"
              f"\n      {f.detail}")


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1] if len(argv) > 1 and not argv[1].startswith("-")
                        else ".")
    if "--clear" in argv:
        print(f"cleared {clear(root)} __pycache__ directories")
        return 0
    if "--null" in argv:
        import compileall
        print(f"cleared {clear(root)} __pycache__ directories")
        compileall.compile_dir(str(root), quiet=2, force=True)
        findings, counts = scan(root)
        _report(findings, counts)
        if counts["agree"] == 0:
            print("NULL TEST INVALID: the domain is empty, so zero findings "
                  "is zero evidence")
            return 2
        print("NULL TEST:", "PASS" if counts["poisonous"] == 0 else "FAIL",
              f"over {counts['agree']} freshly compiled files")
        return 0 if counts["poisonous"] == 0 else 1
    findings, counts = scan(root)
    _report(findings, counts)
    return 1 if counts["poisonous"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
