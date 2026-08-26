"""THE SCOPE MEASUREMENT — what the v1 re-decision guard refused that it should not.

Companion to ``scripts/instruments/hw4/redecision_census.py``, which counted
the POPULATION (how often the legacy door records the same status twice). This
one measures the CONTROL: replaying every decision event in the record through
``ticketguard.check_redecision`` at both scopes, how many of v1's refusals
would have blocked a write that genuinely changed the row?

**THE FINDING THIS INSTRUMENT REPRODUCES** (adversary blind review, 2026-08-26).
``deskstore.decide_recommendation`` is the sole writer of five recommendation
fields — ``status``, ``decided_by``, ``decided_at``, ``note`` (when supplied)
and ``next_actor`` (when supplied). v1 of the guard compared ``status`` alone
and returned a 409 whose message said the write "changes nothing". Seventeen
of its thirty-seven refusals in the live record carried a real table write.
``note`` is not prose: ``deskcard.superseded_by`` parses it into the
supersession marker on the CEO's desk card, so a blocked note was a blocked
marker, and ``POST /fund/desk/runs/{run_id}/recommendations/{rec_id}`` is that
writer's only caller repo-wide, so there was no other door.

**THE TWO SCOPES, AND WHY ONE OF THEM IS RESTATED HERE.** v1.1 is called
through the real ``ticketguard`` functions — that is the point of the
instrument. v1 no longer exists in the source, so its rule (``the row's
recorded status equals the status asked for``) is reproduced in ``v1_refuses``
below. That is a deliberate duplicate of a RETIRED rule and it cannot drift,
because there is no longer a second copy for it to drift from. Reproducing it
is the only way to measure a difference at all.

**WHAT IT REPLAYS, AND ONE LIMIT NAMED.** Each event is judged against the
history that PRECEDED it, so the question asked is exactly "would the guard,
had it been live, have refused this?". The table state each write would have
found is folded from the same events: ``note`` from the last decision carrying
a non-empty one (the writer's ``if note:``), ``next_actor`` from the last
event's field (the door writes the POST-write value). Decision events older
than those payload fields carry neither, and against such a row the fold reads
absent — which makes the replay report a CHANGE and pass. The bias is toward
under-counting refusals, never over-counting them.

REFUSES ON AN EMPTY POPULATION, and the ``--null`` arm states its domain size:
a zero without its domain is not a result (builder D41).

Usage:
    python scripts/instruments/hw5/redecision_scope.py
    python scripts/instruments/hw5/redecision_scope.py --dump out.json
    python scripts/instruments/hw5/redecision_scope.py --null
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DECIDED = "DeskRecommendationDecided"


def pull(dsn: str | None = None) -> tuple[list[dict], dict]:
    """Every decision event, oldest first, with its note and routing owner.

    Same fold as the hw4 census, plus the two payload fields the scope repair
    turns on. Reads Postgres rather than ``GET /fund/events``, which serves the
    newest 1000 and would make a refusal count understate itself the moment the
    log grew past the window.
    """
    import psycopg

    from app.fund import mode as _mode
    from app.fund.pgstore import dsn as _base_dsn

    if dsn is None:
        dsn = _mode.pg_dsn_for(_mode.current() or _mode.resolve(), _base_dsn())
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), min(seq), max(seq) FROM fund_events")
            total, lo, hi = cur.fetchone()
            cur.execute(
                "SELECT seq, aggregate_id, actor, payload FROM fund_events "
                "WHERE type = %s ORDER BY seq ASC", (DECIDED,))
            rows = cur.fetchall()
    events = []
    for seq, agg, actor, payload in rows:
        p = payload if isinstance(payload, dict) else json.loads(payload or "{}")
        events.append({
            "seq": seq, "type": DECIDED, "actor": actor,
            "aggregate_id": agg,
            "payload": {**p, "run_id": p.get("run_id") or agg},
        })
    return events, {"log_events": total, "seq_min": lo, "seq_max": hi,
                    "covers_whole_log": True}


def v1_refuses(lineage: dict, to) -> bool:
    """THE RETIRED RULE, restated. See the module docstring for why.

    v1: refuse iff the row's recorded status equals the status asked for. It
    read no other field, which is the whole defect.
    """
    if not isinstance(to, str) or not to:
        return False
    return lineage.get("recorded_status") == to


def replay(events: list[dict]) -> dict:
    """Judge every decision event against the history that preceded it."""
    from app.fund import ticketguard

    by_row: "OrderedDict[tuple, list[dict]]" = OrderedDict()
    for e in events:
        p = e["payload"]
        by_row.setdefault((str(p.get("run_id")), str(p.get("rec_id"))),
                          []).append(e)

    v1_only, both, v11_only = [], [], []
    freed_shapes = Counter()
    freed_by_actor = Counter()
    still_by_actor = Counter()
    # THE TWO STATUS POPULATIONS, KEPT SEPARATE, because collapsing them
    # produced a wrong sentence that read right for two days: "237 rows have
    # already recorded ``done``" is the EVER count, while the population this
    # guard can refuse is the rows that CURRENTLY hold it (236). Both are true
    # and they differ by the reopened rows. Emitted here rather than left to a
    # hand query, because a claim whose reproduction command does not
    # reproduce it is a citation to nothing.
    holding_now: Counter = Counter()
    ever_held: Counter = Counter()

    for (run, rec), evs in by_row.items():
        statuses = [e["payload"].get("status") for e in evs]
        if statuses and statuses[-1] is not None:
            holding_now[statuses[-1]] += 1
        for s in {x for x in statuses if x is not None}:
            ever_held[s] += 1
        for i, e in enumerate(evs):
            p = e["payload"]
            to = p.get("status")
            dec = ticketguard.decisions_for(evs[:i], run, rec)
            lin = ticketguard.redecision_lineage(dec)
            v1 = v1_refuses(lin, to)
            v11 = ticketguard.check_redecision(
                dec, to=to, run_id=run, rec_id=rec,
                note=p.get("note") or "",
                next_actor=p.get("next_actor")) is not None
            row = {"row": f"{run}#{rec}", "seq": e["seq"], "status": to,
                   "actor": e.get("actor")}
            if v1 and v11:
                both.append(row)
                still_by_actor[e.get("actor")] += 1
            elif v1 and not v11:
                writes = ticketguard.redecision_writes(
                    lin, to=to, note=p.get("note") or "",
                    next_actor=p.get("next_actor"))
                row["would_change"] = writes["changes"]
                v1_only.append(row)
                freed_shapes["+".join(writes["changes"])] += 1
                freed_by_actor[e.get("actor")] += 1
            elif v11 and not v1:
                v11_only.append(row)

    return {
        "decision_events": len(events),
        "distinct_rows": len(by_row),
        "v1_refusals": len(v1_only) + len(both),
        "v11_refusals": len(both) + len(v11_only),
        "freed_by_the_repair": len(v1_only),
        "newly_refused_by_the_repair": len(v11_only),
        "rows_currently_holding": dict(holding_now),
        "rows_ever_recording": dict(ever_held),
        "freed_shapes": dict(freed_shapes),
        "freed_by_actor": dict(freed_by_actor),
        "still_refused_by_actor": dict(still_by_actor),
        "freed_rows": v1_only,
        "newly_refused_rows": v11_only,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--dump", default=None)
    ap.add_argument("--null", action="store_true",
                    help="replay a synthetic population in which every repeat "
                         "is a TRUE no-op, and confirm the repair frees none")
    args = ap.parse_args(argv)

    if args.null:
        # THE NULL ARM, AND IT STATES ITS DOMAIN. Eight events on one row, all
        # `accepted`, all with the same empty note and the same owner — R39's
        # own shape. The repair must free NONE of them: the whole safety
        # argument is that it did not throw away what the guard was built for.
        evs = [{"seq": 100 + i, "type": DECIDED, "actor": "ceo",
                "aggregate_id": "run-null",
                "payload": {"run_id": "run-null", "rec_id": 1,
                            "status": "accepted", "at": f"t{i}", "note": "",
                            "next_actor": "ceo"}}
               for i in range(8)]
        out = replay(evs)
        assert out["decision_events"] == 8, out
        assert out["v1_refusals"] == 7, out
        print(f"NULL ARM: {out['decision_events']} events over "
              f"{out['distinct_rows']} row(s) compared; v1 refused "
              f"{out['v1_refusals']}, v1.1 refused {out['v11_refusals']}, "
              f"freed {out['freed_by_the_repair']}")
        return 0 if (out["freed_by_the_repair"] == 0
                     and out["v11_refusals"] == 7) else 1

    events, bounds = pull(args.dsn)
    if not events:
        print(f"REFUSED: no {DECIDED} events in the log "
              f"({bounds['log_events']} events, seq {bounds['seq_min']}.."
              f"{bounds['seq_max']}). An empty population and an unreachable "
              f"one look identical in a table; this instrument will not "
              f"print one.", file=sys.stderr)
        return 2

    out = {**bounds, **replay(events)}
    text = json.dumps(out, indent=2, default=str)
    print(text)
    if args.dump:
        with io.open(args.dump, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
