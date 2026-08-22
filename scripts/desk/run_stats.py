"""Lifetime per-seat run figures — UNCAPPED, and it proves it saw everything.

    ./venv/Scripts/python.exe -X utf8 scripts/desk/run_stats.py
    ... run_stats.py --json

THE REASON THIS EXISTS IS A MEASURED MISTAKE. The firm's first spend meter was
hand-assembled from ``GET /fund/desk/runs``, whose default payload caps at 25
rows ACROSS ALL SEATS — ``deskstore`` calls it "a FLOOR wearing the costume of
a count" in its own source — while lifetime runs were 49+. The meter was
truncated to roughly half and nobody knew until someone queried with
``limit=500``. Do not build a lifetime figure from a capped payload again;
run this.

WHAT IT PRINTS AND WHY THE ABSENCES MATTER MORE THAN THE TOTALS:

  * ``rows_read`` vs ``row_count`` — from ``SELECT count(*)``. If they differ
    the header says TRUNCATED and every figure below is a floor.
  * ``tokens: ABSENT`` — a seat whose runs carry no token count. NOT zero. A
    zero would make the least-measured seat also the cheapest on the meter.
  * ``median_wall: UNKNOWN`` — nobody passed ``dispatched_at`` at record time,
    so the run has no wall-clock. The chair passes it; see the POST docstring.
  * ``unrecorded`` in the outcome split — the run stated no outcome. It is NOT
    ``delivered``. While any row is unrecorded, the failure count is a FLOOR,
    and a zero-failure line next to 50 unrecorded rows is not a clean record.

See ``scripts/desk/_common.py`` for the Postgres quirks (the token column is
``tokens``, not ``tokens_used``).
"""

from __future__ import annotations

import json
import sys

import _common as C


def render(body: dict) -> str:
    if body.get("state") == "UNKNOWN":
        return f"UNKNOWN — {body['reason']}: {body['note']}"
    out = []
    head = (f"{body['rows_read']} of {body['row_count']} run rows read")
    if body.get("truncated"):
        head = "TRUNCATED: " + head + "  — every figure below is a FLOOR"
    out.append(head)
    out.append(f"lifetime tokens {C.num(body['total_tokens'])}   "
               f"tool_uses {C.num(body['total_tool_uses'])}   "
               f"failed {body['runs_failed']}   "
               f"outcome unrecorded {body['runs_unrecorded_status']}")
    out.append("")
    out.append(f"{'SEAT':<13}{'RUNS':>5}{'TOKENS':>12}{'TOOLS':>7}"
               f"{'MED WALL':>10}  {'FIRST':<11}{'LAST':<11}OUTCOMES")
    for seat, v in body["by_seat"].items():
        wall = ("UNKNOWN" if v["median_duration_seconds"] is None
                else f"{v['median_duration_seconds'] / 60:.0f}m")
        first = (v["first_resolved_at"] or "ABSENT")[:10]
        last = (v["last_resolved_at"] or "ABSENT")[:10]
        outcomes = ", ".join(f"{k}={n}" for k, n in sorted(v["by_status"].items()))
        out.append(f"{seat:<13}{v['runs']:>5}{C.num(v['tokens']):>12}"
                   f"{C.num(v['tool_uses']):>7}{wall:>10}  "
                   f"{first:<11}{last:<11}{outcomes}")
    out.append("")
    out.append(body["note"])
    return "\n".join(out)


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    for a in argv[1:]:
        if a != "--json":
            C.usage("usage: run_stats.py [--json]")

    def compute():
        from app.fund import metrics
        _, ds = C.stores()
        return metrics.run_stats(ds)

    source, body = C.fetch("/fund/desk/runs/stats", compute)
    if as_json:
        print(json.dumps(body, indent=1, default=str))
        return 0
    print(C.banner(source, "lifetime run stats"))
    print(render(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
