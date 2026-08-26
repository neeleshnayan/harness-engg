"""THE RE-DECISION CENSUS — how often does the legacy door record a status twice?

The measurement behind the narrow decision guard on
``POST /fund/desk/runs/{run_id}/recommendations/{rec_id}``
(``ticketguard.check_redecision``), and the acceptance figures quoted in
``tests/test_legacy_redecision_guard.py``. Shelved rather than left in a
session scratchpad, because a register citation must outlive the session that
made it (builder D41).

**IT READS POSTGRES, NOT ``GET /fund/events``, AND THAT IS THE POINT.** Its
predecessor ``scripts/instruments/hw3/r39_census.py`` pulls the HTTP feed,
which is capped at the NEWEST 1000 events and therefore prints
``covers_whole_log: false`` on a log that is already longer. A guard whose
refusal count is quoted from a WINDOW would understate itself the moment the
log grew. This one folds ``fund_events`` end to end and says which seqs it
covered.

THREE POPULATIONS, DELIBERATELY SEPARATE, because the phrase "same-status
repeat" collapses them and they give different numbers:

  ROWS-WITH-A-REPEAT   distinct (run_id, rec_id) identities carrying at least
                       one repeat of a given status. Small.
  EVER-REPEAT EVENTS   events whose status was recorded on this row by ANY
                       earlier event. Larger.
  CONSECUTIVE-REPEAT   events whose status equals the row's CURRENTLY recorded
  EVENTS               status — i.e. what the shipped guard actually refuses.

They differ by the A -> B -> A shape: a row that was accepted, closed,
REOPENED and then legitimately accepted again. The shipped guard refuses the
consecutive population only; the ever-repeat population would have refused
that re-acceptance, which is a control refusing correct work.

REFUSES ON AN EMPTY POPULATION. An unreachable database and a database with no
matching events produce the same clean table otherwise, and a zero without its
domain is not a result (builder D41).

Usage:
    python scripts/instruments/hw4/redecision_census.py
    python scripts/instruments/hw4/redecision_census.py --dump out.json
    python scripts/instruments/hw4/redecision_census.py --null   # domain check
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import Counter, OrderedDict

#: The repo root, from THIS FILE rather than from the cwd. Python puts the
#: script's own directory on ``sys.path``, never the working directory, so an
#: instrument three levels down cannot import ``app`` without saying where the
#: root is. Derived rather than passed as ``argv[1]`` (the D41 instrument's
#: convention) because this one takes real flags and a positional root would
#: collide with them.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DECIDED = "DeskRecommendationDecided"


def pull(dsn: str | None = None) -> tuple[list[dict], dict]:
    """Every decision event, oldest first, plus the log's own bounds.

    The bounds ride along because a census that cannot say what it scanned is
    a window wearing a total's name (the HW3 lesson this instrument replaces).
    """
    import psycopg

    from app.fund import mode as _mode
    from app.fund.pgstore import dsn as _base_dsn

    if dsn is None:
        # WHICH database is a property of the MODE, not of the backend —
        # `EventStore.__new__` resolves it exactly this way, and an instrument
        # that guessed would happily census the dev ledger and label it the
        # fund's. `resolve()` raises when nothing declared a mode, which is the
        # correct outcome for a forgetful invocation.
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
        events.append({"seq": seq, "aggregate_id": agg, "actor": actor,
                       "run_id": p.get("run_id") or agg,
                       "rec_id": p.get("rec_id"), "status": p.get("status"),
                       "at": p.get("at")})
    return events, {"log_events": total, "seq_min": lo, "seq_max": hi,
                    "covers_whole_log": True}


def census(events: list[dict]) -> dict:
    """The three populations over a list of decision events, oldest first."""
    by_row: "OrderedDict[tuple, list[dict]]" = OrderedDict()
    for e in events:
        by_row.setdefault((e.get("run_id"), e.get("rec_id")), []).append(e)

    ever_events, consec_events = Counter(), Counter()
    rows_with_ever, rows_with_consec = Counter(), Counter()
    progressions = 0
    aba_rows = []
    per_row = Counter()
    refusable_by_actor = Counter()

    for key, evs in by_row.items():
        st = [e.get("status") for e in evs]
        per_row[len(evs)] += 1
        if len(set(st)) > 1:
            progressions += 1
        seen: set = set()
        ever_here, consec_here = set(), set()
        for i, s in enumerate(st):
            if s in seen:
                ever_events[s] += 1
                ever_here.add(s)
            if i and st[i - 1] == s:
                consec_events[s] += 1
                consec_here.add(s)
                refusable_by_actor[evs[i].get("actor")] += 1
            seen.add(s)
        for s in ever_here:
            rows_with_ever[s] += 1
        for s in consec_here:
            rows_with_consec[s] += 1
        # A -> B -> A: a status returning to the row after a different one
        # intervened. The ONE row of this shape in the record is why the guard
        # is consecutive rather than ever-repeat.
        for i, s in enumerate(st):
            first = st.index(s)
            if first < i and any(x != s for x in st[first + 1:i]):
                aba_rows.append({"row": list(key), "statuses": st})
                break

    return {
        "decision_events": len(events),
        "distinct_rows": len(by_row),
        "rows_with_a_repeat": dict(rows_with_ever),
        "rows_with_a_repeat_total": sum(rows_with_ever.values()),
        "ever_repeat_events": dict(ever_events),
        "ever_repeat_events_total": sum(ever_events.values()),
        "consecutive_repeat_events": dict(consec_events),
        "consecutive_repeat_events_total": sum(consec_events.values()),
        "rows_with_a_consecutive_repeat": dict(rows_with_consec),
        "progression_rows": progressions,
        "aba_rows": aba_rows,
        "events_per_row": dict(sorted(per_row.items())),
        "refusable_by_actor": dict(refusable_by_actor),
    }


def worst_row(events: list[dict]) -> dict:
    """The identity decided most often, with its seqs. R39's row, today."""
    by_row: "OrderedDict[tuple, list[dict]]" = OrderedDict()
    for e in events:
        by_row.setdefault((e.get("run_id"), e.get("rec_id")), []).append(e)
    if not by_row:
        return {}
    key, evs = max(by_row.items(), key=lambda kv: len(kv[1]))
    return {"row": list(key), "decisions": len(evs),
            "seqs": [e.get("seq") for e in evs],
            "statuses": [e.get("status") for e in evs]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--dump", default=None)
    ap.add_argument("--null", action="store_true",
                    help="fold a population with no repeats and confirm the "
                         "census reports zero over a NON-empty domain")
    args = ap.parse_args(argv)

    if args.null:
        # THE NULL ARM STATES ITS DOMAIN SIZE. A --null that silently compared
        # nothing prints the same zero as one that compared a clean corpus.
        clean = [{"seq": i + 1, "run_id": f"run-{i}", "rec_id": 1,
                  "status": "accepted", "actor": "ceo"} for i in range(7)]
        out = census(clean)
        assert out["decision_events"] == 7, out
        assert out["distinct_rows"] == 7, out
        print(f"NULL ARM: {out['decision_events']} events over "
              f"{out['distinct_rows']} distinct rows compared; "
              f"consecutive repeats = {out['consecutive_repeat_events_total']}, "
              f"ever repeats = {out['ever_repeat_events_total']}")
        return 0 if out["consecutive_repeat_events_total"] == 0 else 1

    events, bounds = pull(args.dsn)
    if not events:
        print(f"REFUSED: no {DECIDED} events in the log "
              f"({bounds['log_events']} events, seq {bounds['seq_min']}.."
              f"{bounds['seq_max']}). An empty population and an unreachable "
              f"one look identical in a table; this instrument will not "
              f"print one.", file=sys.stderr)
        return 2

    out = {**bounds, **census(events), "worst_row": worst_row(events)}
    text = json.dumps(out, indent=2, default=str)
    print(text)
    if args.dump:
        with io.open(args.dump, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
