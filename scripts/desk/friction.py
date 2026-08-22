"""The friction ledger — desk requests folded forward, AGED, oldest first.

    ./venv/Scripts/python.exe -X utf8 scripts/desk/friction.py
    ... friction.py --all          # include resolved and declined
    ... friction.py --json

The secretary's ledger as one command. Its first hand-built run (2026-08-21)
found 28 requests approved and undispatched at midnight, ALL waiting on the
chair, the oldest 14h34m — and only 3 of the 28 answered the next day. That
number took most of a 26-minute dispatch to produce.

TWO THINGS TO KNOW BEFORE YOU QUOTE A NUMBER FROM THIS.

**``approved_undispatched`` IS AN UPPER BOUND.** 14 of 24 ``DeskDispatched``
events carry no ``request_id``, so a request that WAS dispatched can look
undispatched here. The footer prints the link coverage; quote it with the
number or do not quote the number.

**``DeskDispatched`` IS NEVER FOLDED INTO THE REQUEST TABLE.** One live event
names a ``request_id`` that was never filed, and folding dispatches in creates
a phantom request with a ``None`` id which then sorts to the top of an
oldest-first list and never leaves. It is used only to annotate rows that
already exist.

See ``scripts/desk/_common.py`` for the rest of the quirks.
"""

from __future__ import annotations

import json
import sys

import _common as C


def render(body: dict, show_all: bool = False) -> str:
    rows = body["requests"]
    if not show_all:
        rows = [r for r in rows if not r["terminal"]]
    out = []
    out.append(f"{body['count']} request(s) on file; {body['open_count']} still "
               f"on the path")
    out.append("waiting on: " + (", ".join(f"{k}={v}" for k, v in
                                           sorted(body["waiting_on"].items()))
                                 or "nobody"))
    out.append("by state  : " + ", ".join(f"{k}={v}" for k, v in
                                          body["by_state"].items() if v))
    out.append("")
    out.append(f"{'AGE':>9}  {'IN STATE':>9}  {'STATE':<22} {'ON':<6} "
               f"{'SEAT':<11} TASK")
    for r in rows:
        # ABSENT, never 0.0 — a row whose filing time cannot be read has an
        # unknown age and sorts last rather than jumping the queue.
        age = "ABSENT" if r["age_hours"] is None else f"{r['age_hours']:.1f}h"
        st = "ABSENT" if r["age_in_state_hours"] is None \
            else f"{r['age_in_state_hours']:.1f}h"
        task = (r["task"] or "(no task recorded)").replace("\n", " ")
        out.append(f"{age:>9}  {st:>9}  {r['state']:<22} "
                   f"{str(r['waiting_on'] or '-'):<6} "
                   f"{str(r['seat'] or '-'):<11} {task[:64]}")
    cov = body["dispatch_link_coverage"]
    out.append("")
    out.append(f"approved_undispatched = {body['approved_undispatched']}"
               + ("   <-- UPPER BOUND" if not cov["complete"] else ""))
    out.append(f"dispatch link coverage: {cov['linkable']} of "
               f"{cov['dispatch_events']} events linkable; "
               f"{cov['unlinkable_no_request_id']} carry no request_id; "
               f"{cov['orphan_request_id']} naming a request never filed")
    out.append(body["note"])
    return "\n".join(out)


def main(argv: list[str]) -> int:
    show_all = "--all" in argv
    as_json = "--json" in argv
    for a in argv[1:]:
        if a not in ("--all", "--json"):
            C.usage("usage: friction.py [--all] [--json]")

    def compute():
        from app.fund import metrics
        store, _ = C.stores()
        return metrics.friction(store)

    source, body = C.fetch("/fund/metrics/friction", compute)
    if as_json:
        print(json.dumps(body, indent=1, default=str))
        return 0
    print(C.banner(source, "desk friction ledger"))
    print(render(body, show_all=show_all))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
