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
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1"


def _post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            json.loads(r.read())
            return None
    except urllib.error.HTTPError as e:
        return f"{e.code} {e.read()[:150].decode()}"


def _full_ids():
    with urllib.request.urlopen(BASE + "/fund/desk", timeout=60) as r:
        desk = json.loads(r.read())
    return {q["request_id"][:8]: q["request_id"]
            for q in (desk.get("requests") or [])}


def resolve(rows):
    full = _full_ids()
    ok = fail = 0
    for row in rows:
        rid = row["id"]
        if len(rid) == 8:
            rid = full.get(rid, rid)
        cite = (row.get("citation") or "").strip()
        if not cite:
            print(f"REFUSED {rid[:8]}: no citation"); fail += 1; continue
        err = _post(f"/fund/desk/requests/{rid}/resolve",
                    {"resolution": cite, "actor": "cto"})
        if err:
            print(f"FAIL {rid[:8]}: {err}"); fail += 1
        else:
            print(f"OK   {rid[:8]}"); ok += 1
    print(f"\nresolved {ok}, failed {fail}, of {len(rows)}")


def decide(rows):
    ok = fail = 0
    for row in rows:
        note = (row.get("note") or "").strip()
        if not note:
            print(f"REFUSED {row['run_id']}#{row['rec_id']}: no note"); fail += 1; continue
        err = _post(f"/fund/desk/runs/{row['run_id']}/recommendations/{row['rec_id']}",
                    {"status": row.get("status", "done"), "actor": "cto", "note": note})
        if err:
            print(f"FAIL {row['run_id']}#{row['rec_id']}: {err}"); fail += 1
        else:
            print(f"OK   {row['run_id']}#{row['rec_id']}"); ok += 1
    print(f"\ndecided {ok}, failed {fail}, of {len(rows)}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help-shapes":
        print(__doc__)
        print('resolve shape: [{"id": "8-or-36-char request id", "citation": "why, with the record cite"}]')
        print('decide shape:  [{"run_id": "...", "rec_id": "3", "status": "done", "note": "why"}]')
        sys.exit(0)
    mode, path = sys.argv[1], sys.argv[2]
    rows = json.loads(open(path, encoding="utf-8").read())
    {"resolve": resolve, "decide": decide}[mode](rows)
