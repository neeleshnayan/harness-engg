"""The chair's bulk-closure instrument. Events through the doors, at SQL speed.

Usage:
  python desk_sweep.py resolve  <sweep.json>   # requests: [{id, citation}]
  python desk_sweep.py decide   <sweep.json>   # recs: [{run_id, rec_id, status, note}]
  python desk_sweep.py --help-shapes

Why this exists (2026-08-24, CEO: "the flow should have been you updating a
few DB entries directly"): the desk's statuses are folds of the append-only
event log - there is nothing to UPDATE, and writing beneath the doors would
bypass the phantom guard, the allowlist and the echo rule. This script keeps
every write an audited event through the ordinary endpoints, and makes the
sweep one command instead of one script per row.

Every row needs a citation. No citation, no closure - Donna's rule.

ALREADY IS NOT A FAILURE (2026-08-24). The decide door now refuses a decision
that re-records the status a row already holds - the narrow decision guard, on
the CEO's decision, and this script is the caller most exposed to it because
it posts `done` in bulk. 237 rows in the record have already recorded `done`,
so re-sweeping any of them refuses. That refusal means "there was nothing to
do here", which is a different outcome from "this closure did not happen", and
printing both as FAIL would train the chair to ignore the word. The sweep
therefore reports three outcomes, and its exit status counts only the third.
"""
import json
import os
import sys
import urllib.error
import urllib.request

#: The spine, overridable so this script can be RUN AGAINST A TEST SERVER.
#: It was a bare constant until 2026-08-24, which made the whole instrument
#: untestable by construction: there was no way to exercise it except by
#: pointing it at the live fund. A tool that can only be tried in production
#: is a tool nobody tries.
BASE = os.getenv("DESK_SWEEP_BASE", "http://127.0.0.1:8090/api/v1")

#: The guard whose 409 means ALREADY rather than FAILED. Matched on the
#: machine-readable `hint`, never on the prose: the detail sentence is written
#: for a human and will be reworded, and a classifier keyed on prose silently
#: reclassifies the day somebody improves the wording.
ALREADY_HINT = "already_at_this_status"


def classify(code, body):
    """`ok` / `already` / `fail`, from an HTTP status and a response body.

    Pure, so the three outcomes can be tested without a spine. `already` is
    ONLY a 409 carrying the re-decision guard's own hint - a 409 from the
    supersession brake is a genuine refusal to act and stays a failure, and an
    unparseable body is a failure rather than a hopeful guess.
    """
    if code == 200:
        return "ok"
    if code != 409:
        return "fail"
    try:
        detail = (json.loads(body) or {}).get("detail")
    except (ValueError, TypeError):
        return "fail"
    if isinstance(detail, dict) and detail.get("hint") == ALREADY_HINT:
        return "already"
    return "fail"


def _post(path, payload):
    """`(outcome, message)`. The message is None on a clean 200."""
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            json.loads(r.read())
            return "ok", None
    except urllib.error.HTTPError as e:
        raw = e.read()
        outcome = classify(e.code, raw)
        if outcome == "already":
            detail = json.loads(raw)["detail"]
            return outcome, (f"already {detail.get('recorded_status')!r} "
                             f"since {detail.get('recorded_at')}")
        return outcome, f"{e.code} {raw[:150].decode(errors='replace')}"


def _full_ids():
    with urllib.request.urlopen(BASE + "/fund/desk", timeout=60) as r:
        desk = json.loads(r.read())
    return {q["request_id"][:8]: q["request_id"]
            for q in (desk.get("requests") or [])}


def resolve(rows):
    full = _full_ids()
    ok = already = fail = 0
    for row in rows:
        rid = row["id"]
        if len(rid) == 8:
            rid = full.get(rid, rid)
        cite = (row.get("citation") or "").strip()
        if not cite:
            print(f"REFUSED {rid[:8]}: no citation"); fail += 1; continue
        outcome, msg = _post(f"/fund/desk/requests/{rid}/resolve",
                             {"resolution": cite, "actor": "cto"})
        if outcome == "ok":
            print(f"OK      {rid[:8]}"); ok += 1
        elif outcome == "already":
            print(f"ALREADY {rid[:8]}: {msg}"); already += 1
        else:
            print(f"FAIL    {rid[:8]}: {msg}"); fail += 1
    print(f"\nresolved {ok}, already {already}, failed {fail}, of {len(rows)}")
    return fail


def decide(rows):
    ok = already = fail = 0
    for row in rows:
        ref = f"{row['run_id']}#{row['rec_id']}"
        note = (row.get("note") or "").strip()
        if not note:
            print(f"REFUSED {ref}: no note"); fail += 1; continue
        outcome, msg = _post(
            f"/fund/desk/runs/{row['run_id']}/recommendations/{row['rec_id']}",
            {"status": row.get("status", "done"), "actor": "cto", "note": note})
        if outcome == "ok":
            print(f"OK      {ref}"); ok += 1
        elif outcome == "already":
            # NOT A FAILURE AND NOT A CLOSURE EITHER. The row was already in
            # the state this sweep wanted it in, so the sweep did nothing and
            # nothing needed doing. Counted separately so a batch of 40 that
            # closes 12 and skips 28 does not read as 28 problems.
            print(f"ALREADY {ref}: {msg}"); already += 1
        else:
            print(f"FAIL    {ref}: {msg}"); fail += 1
    print(f"\ndecided {ok}, already {already}, failed {fail}, of {len(rows)}")
    return fail


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help-shapes":
        print(__doc__)
        print('resolve shape: [{"id": "8-or-36-char request id", "citation": "why, with the record cite"}]')
        print('decide shape:  [{"run_id": "...", "rec_id": "3", "status": "done", "note": "why"}]')
        sys.exit(0)
    mode, path = sys.argv[1], sys.argv[2]
    rows = json.loads(open(path, encoding="utf-8").read())
    # EXIT NON-ZERO ON A REAL FAILURE, and only on one. The script previously
    # exited 0 whatever happened, so a sweep of 40 rows that failed all 40 was
    # indistinguishable to any caller from one that closed all 40. `already`
    # is deliberately NOT counted here: nothing needed doing and nothing went
    # wrong, and a non-zero exit for that would make the guard look like a
    # breakage every time the chair re-ran a sweep.
    sys.exit(1 if {"resolve": resolve, "decide": decide}[mode](rows) else 0)
