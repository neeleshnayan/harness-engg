"""Append today's local events to production. Run tonight, once the quota resets.

This is NOT promote_local_to_production.py and must never be confused with it.
That script archives production and replays a whole history over it, because
this morning the two ledgers were unrelated and one had to be chosen. This one
assumes the opposite and checks it: local is production plus today's trading,
so the job is to append the tail.

Three things are verified before a single write, and each of them is a way the
append could silently corrupt the book:

  1. Local's first N events must be IDENTICAL to production's — same event ids,
     same seq, same hashes. If local forked instead of mirrored, appending its
     tail would splice one history onto another and the chain would break at
     the join.

  2. Production's tip must equal local's event at the same seq. If production
     moved on while we were offline — another process, a stray write — then our
     tail chains onto a hash that is no longer the end, and appending would
     produce two events claiming the same parent.

  3. The tail must chain cleanly from that tip. Verified locally before
     anything is sent.

    python scripts/sync_local_to_production.py            # dry run
    python scripts/sync_local_to_production.py --execute
"""

from __future__ import annotations

import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(REPO, ".env"))
os.environ["FUND_MODE"] = "alpaca-paper"   # this script writes the REAL book
# USE_FAKE_FIRESTORE is gone (2026-08-22). The interlock it keyed — refusing
# to open a real Firestore client from an isolated process — now keys on
# FUND_MODE=test in app/core/firebase.py, so declaring the mode here is what
# tells that guard this script genuinely means the real book.

from app.fund.chain import verify  # noqa: E402

LOCAL_DB = os.path.join(REPO, ".firestore_local_db.json")
EVENTS = "fund_events"
BATCH, PAUSE_S = 400, 1.0

GREEN, RED, YELL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def say(m="", c=""):
    print(f"{c}{m}{OFF}" if c else m)


def rule(t=""):
    say()
    say(f"-- {t} " + "-" * max(0, 60 - len(t)), DIM)


def main(execute: bool) -> int:
    from app.core.firebase import active_book, db, initialize_firebase

    initialize_firebase()
    client = db()

    rule("target")
    say(f"project : {active_book().get('project_id')}")
    say(f"mode    : {'EXECUTE' if execute else 'DRY RUN'}", RED if execute else GREEN)

    local = sorted(
        json.load(open(LOCAL_DB, encoding="utf-8")).get("fund_events", {}).values(),
        key=lambda e: e.get("seq", 0),
    )
    prod = sorted(
        [d.to_dict() for d in client.collection(EVENTS).limit(5000).stream()],
        key=lambda e: e.get("seq", 0),
    )

    rule("what is on each side")
    say(f"local      : {len(local)} events, seq 1..{local[-1].get('seq') if local else 0}")
    say(f"production : {len(prod)} events, seq 1..{prod[-1].get('seq') if prod else 0}")

    if len(local) <= len(prod):
        say()
        say("Nothing to sync — local has no events production lacks.", GREEN)
        return 0

    rule("check 1: local is a mirror, not a fork")
    mismatch = None
    for i, p in enumerate(prod):
        l = local[i] if i < len(local) else None
        if l is None or l.get("event_id") != p.get("event_id") or l.get("hash") != p.get("hash"):
            mismatch = (i, p, l)
            break
    if mismatch:
        i, p, l = mismatch
        say(f"XX divergence at index {i} (seq {p.get('seq')})", RED)
        say(f"   production : {p.get('event_id')} {str(p.get('hash'))[:12]}", RED)
        say(f"   local      : {(l or {}).get('event_id')} {str((l or {}).get('hash'))[:12]}", RED)
        say()
        say("Local FORKED rather than mirrored. Appending its tail would splice", RED)
        say("two histories together. Refusing — this needs a human decision.", RED)
        return 3
    say(f"OK production's {len(prod)} events match local's first {len(prod)} exactly", GREEN)

    tail = local[len(prod):]
    rule("check 2: the tail chains onto production's tip")
    prod_tip = prod[-1].get("hash") if prod else None
    if tail[0].get("prev_hash") != prod_tip:
        say(f"XX first new event points at {str(tail[0].get('prev_hash'))[:12]}", RED)
        say(f"   but production's tip is  {str(prod_tip)[:12]}", RED)
        say("   Production moved while we were offline. Refusing.", RED)
        return 4
    say(f"OK tail chains onto {str(prod_tip)[:12]}...", GREEN)

    rule("check 3: the whole chain verifies")
    v = verify(prod + tail)
    if not v.ok:
        say(f"XX combined chain breaks: {v.first_break}", RED)
        return 5
    say(f"OK {v.chained} events verify end to end", GREEN)

    rule("plan")
    say(f"  append {len(tail)} events, seq {tail[0].get('seq')}..{tail[-1].get('seq')}")
    by_type: dict[str, int] = {}
    for e in tail:
        by_type[e.get("type", "?")] = by_type.get(e.get("type", "?"), 0) + 1
    for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
        say(f"    {n:>3}  {t}")
    say(f"  set counter to seq={tail[-1].get('seq')}, tip={str(tail[-1].get('hash'))[:12]}...")

    if not execute:
        say()
        say("DRY RUN — nothing written.", GREEN)
        return 0

    rule("executing")
    for i in range(0, len(tail), BATCH):
        chunk = tail[i:i + BATCH]
        batch = client.batch()
        for e in chunk:
            batch.set(client.collection(EVENTS).document(e["event_id"]), e)
        batch.commit()
        say(f"  wrote {min(i + BATCH, len(tail))}/{len(tail)}", DIM)
        if i + BATCH < len(tail):
            time.sleep(PAUSE_S)

    client.collection("fund_meta").document("event_counter").set(
        {"seq": tail[-1]["seq"], "tip_hash": tail[-1]["hash"]}, merge=True)
    say("OK counter advanced", GREEN)

    # Projection caches now describe a shorter history than the log.
    for d in client.collection("fund_snapshots").limit(100).stream():
        client.collection("fund_snapshots").document(d.id).delete()
    say("OK stale projection caches cleared — they rebuild from the log", GREEN)

    rule("verification")
    time.sleep(2.0)
    back = sorted([d.to_dict() for d in client.collection(EVENTS).limit(5000).stream()],
                  key=lambda e: e.get("seq", 0))
    v2 = verify(back)
    ok = len(back) == len(local) and v2.ok and v2.chained == len(local)
    say(f"  events    : {len(back)} (expected {len(local)})",
        GREEN if len(back) == len(local) else RED)
    say(f"  chain     : ok={v2.ok} chained={v2.chained}", GREEN if v2.ok else RED)

    rule()
    if ok:
        say("SYNCED. Production holds today's trading.", GREEN)
        say("Switch back with ./scripts/run.sh.", DIM)
        return 0
    say("VERIFICATION FAILED — do not trade until this is resolved.", RED)
    return 6


if __name__ == "__main__":
    raise SystemExit(main("--execute" in sys.argv))
