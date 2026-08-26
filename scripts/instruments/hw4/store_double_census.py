"""How many of the suite's event-store doubles can answer ``by_aggregate``?

The reproduction command for the count cited beside ``REDECISION_BASIS_*`` in
``app/api/v1/fund.py``. It exists because that comment cites a number, and a
number in a comment needs a command that re-derives it (builder D39: the same
quantity was stated as 174 and 185 in two files).

WHY AST AND NOT GREP. The first pass counted with ``grep -l``, which counts
FILES MENTIONING a name — 19 files defining a class called ``MemStore`` and 7
files containing the string ``def by_aggregate`` anywhere. The question is how
many event-store-shaped DOUBLES implement the method, and the answer is
different: 23 and 5. A file that defines two doubles counts once under grep,
and a helper function named ``by_aggregate`` outside any class counts as a
store that has one.

WHAT THE COUNT IS FOR. ``_refuse_if_redecided`` fails OPEN against a store that
cannot answer, which is correct — a store that could not be asked has not
answered "no". The point of the census is that this path is reachable from
inside the suite today, so "the guard allowed" and "the guard could not look"
must be distinguishable in the response, or a green test blesses an unwired
control.

The two numbers MOVE as the suite grows. The invariant that does not: at least
one double lacks the method, so ``--assert-reachable`` is the check worth
wiring, not the totals.

Usage:
    python scripts/instruments/hw4/store_double_census.py
    python scripts/instruments/hw4/store_double_census.py --assert-reachable
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

#: What makes a class an EVENT-STORE DOUBLE for this census. Both, not either:
#: a class with only ``append`` is a recorder, and a class with only ``stream``
#: is a feed. The store this guard reads is the one that does both.
STORE_SHAPE = ("append", "stream")

#: The method the guard needs. Named rather than inlined so the census and the
#: door cannot drift apart about which question is being asked.
NEEDED = "by_aggregate"


def census(tests_dir: str) -> dict:
    doubles, with_needed, unparseable = [], [], []
    for name in sorted(os.listdir(tests_dir)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(tests_dir, name)
        try:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
        except (SyntaxError, UnicodeDecodeError) as e:
            # A FILE THE CENSUS COULD NOT READ IS NAMED, never skipped into a
            # smaller total. Absence is not zero, and a scanner that swallows
            # its own blind spots certifies whatever hides there.
            unparseable.append(f"{name} ({type(e).__name__})")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {m.name for m in node.body
                       if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if not all(m in methods for m in STORE_SHAPE):
                continue
            doubles.append(f"{name}::{node.name}")
            if NEEDED in methods:
                with_needed.append(f"{name}::{node.name}")
    return {
        "doubles": len(doubles),
        "files": len({d.split("::")[0] for d in doubles}),
        f"with_{NEEDED}": len(with_needed),
        f"without_{NEEDED}": len(doubles) - len(with_needed),
        "unparseable": unparseable,
        f"{NEEDED}_present_in": with_needed,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tests", default=os.path.join(ROOT, "tests"))
    ap.add_argument("--assert-reachable", action="store_true",
                    help="exit non-zero unless at least one double LACKS the "
                         "method, i.e. unless the fail-open path is reachable "
                         "from inside the suite")
    args = ap.parse_args(argv)

    out = census(args.tests)
    if not out["doubles"]:
        print(f"REFUSED: no event-store-shaped doubles found under "
              f"{args.tests!r}. A zero here means the census looked in the "
              f"wrong place, not that the suite has no doubles.",
              file=sys.stderr)
        return 2
    assert not out["unparseable"], f"could not read: {out['unparseable']}"
    print(json.dumps(out, indent=2))
    if args.assert_reachable:
        return 0 if out[f"without_{NEEDED}"] > 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
