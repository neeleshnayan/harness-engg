"""One UTC day, folded once — events, decisions, NAV, fills, requests, runs.

    ./venv/Scripts/python.exe -X utf8 scripts/desk/day_events.py 2026-08-21
    ./venv/Scripts/python.exe -X utf8 scripts/desk/day_events.py            # today
    ... 2026-08-21 --json                                                   # raw

Replaces the hand fold every end-of-day brief was doing: events by type,
decision tallies by actor and status, NAV open/close/strikes, fills with
notional and venue split, ReconciliationMismatch, the desk-request lifecycle
and per-seat runs. Measured 0.12s against the live log.

READ ``scripts/desk/_common.py`` BEFORE WRITING YOUR OWN QUERY — it carries
every Postgres quirk this repo has cost somebody, including the two that bite
here: event types are PascalCase and ``ts`` is TEXT.

ABSENCE IS RENDERED AS ABSENCE. A day with no NAV strike prints UNKNOWN with
the reason, never $0.00; an unreachable run recorder prints UNKNOWN, never
"no runs". If you copy anything out of this output, copy the word too.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import _common as C


def render(body: dict) -> str:
    out = []
    day = body["day"]
    out.append(f"== {day} (UTC){'' if body['complete_day'] else '  — DAY STILL RUNNING, this is a snapshot'}")

    ev = body["events"]
    out.append(f"\nevents {ev['total']}"
               + (f"  ({ev['untyped']} untyped)" if ev["untyped"] else ""))
    for t, n in list(ev["by_type"].items())[:14]:
        out.append(f"  {n:>5}  {t}")

    d = body["decisions"]
    out.append(f"\ndecisions {d['total']}")
    if d["total"]:
        out.append("  by actor : " + ", ".join(f"{k}={v}" for k, v in
                                               sorted(d["by_actor"].items())))
        out.append("  by status: " + ", ".join(f"{k}={v}" for k, v in
                                               sorted(d["by_status"].items())))

    nav = body["nav"]
    if nav.get("state") == "UNKNOWN":
        out.append(f"\nnav UNKNOWN — {nav['reason']}: {nav['note']}")
    else:
        out.append(f"\nnav {nav['strikes']} strike(s)  open {C.money(nav['open_usd'])}"
                   f" -> close {C.money(nav['close_usd'])}"
                   + ("" if nav["complete"] else
                      f"   ({nav['unreadable_strikes']} strike(s) UNREADABLE)"))

    f = body["fills"]
    out.append(f"\nfills {f['count']}  notional {C.money(f['notional_usd'])}"
               + ("" if f["complete"] else
                  f"  — INCOMPLETE, {f['unreadable']} fill(s) unreadable"))
    if f["count"]:
        out.append("  venue: " + (", ".join(f"{k}={v}" for k, v in
                                            sorted(f["by_venue"].items())) or "none stated")
                   + (f"   venue NOT STATED on {f['venue_unstated']}"
                      if f["venue_unstated"] else ""))
        out.append("  side : " + ", ".join(f"{k}={v}" for k, v in
                                           sorted(f["by_side"].items())))

    out.append(f"\nreconciliation mismatches {body['reconciliation_mismatches']}")

    r = body["desk_requests"]
    out.append("desk requests  " + "  ".join(f"{k}={v}" for k, v in r.items())
               + "   (events on the day, not folded states — see friction.py)")

    runs = body["runs"]
    if runs.get("state") == "UNKNOWN":
        out.append(f"\nruns UNKNOWN — {runs['reason']}: {runs['note']}")
    else:
        out.append(f"\nruns {runs['total_runs']}  tokens {C.num(runs['total_tokens'])}"
                   f"  tool_uses {C.num(runs['total_tool_uses'])}")
        for seat, v in runs["by_seat"].items():
            # median_wall is UNKNOWN, never 0, when dispatched_at was not
            # recorded — a zero would make the slowest work look instant.
            wall = ("UNKNOWN" if v["median_duration_seconds"] is None
                    else f"{v['median_duration_seconds'] / 60:.1f}m")
            out.append(f"  {seat:<12} runs={v['runs']:<3} "
                       f"tokens={C.num(v['tokens']):>11}  "
                       f"tools={C.num(v['tool_uses']):>5}  "
                       f"median_wall={wall}")
        out.append("  " + runs["note"])

    if body["unknown_sections"]:
        out.append("\nUNKNOWN sections: " + ", ".join(body["unknown_sections"])
                   + "  — absent, which is not zero")
    st = body.get("stored")
    if st:
        out.append(f"stored rollup: {st.get('note')}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv
    if len(args) > 1:
        C.usage("usage: day_events.py [YYYY-MM-DD] [--json]")
    day = args[0] if args else datetime.now(timezone.utc).date().isoformat()

    def compute():
        from app.fund import metrics
        store, ds = C.stores()
        return metrics.compute_daily(day, store, deskstore=ds)

    source, body = C.fetch(f"/fund/metrics/daily?date={day}", compute)
    if isinstance(body, dict) and body.get("detail"):
        C.usage(f"refused: {body['detail']}")
    if as_json:
        print(json.dumps(body, indent=1, default=str))
        return 0
    print(C.banner(source, f"day rollup {day}"))
    print(render(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
