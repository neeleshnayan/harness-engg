"""Finish the promotion after the snapshot write failed partway.

What happened: the event replay and the archive both completed — production
holds all 52 promoted events and the chain verifies over every one. The script
then tried to copy the local snapshot collections and Firestore rejected the
batch, because ``fund_snapshots`` state wraps Decimals in a ``__dec__`` key and
Firestore reserves every field name matching ``__*__`` at any nesting depth.

That left two things wrong, and only one of them is obvious:

  1. The seq counter was never advanced. It still reads 22 while events run to
     52, so the next append would assign seq 23 — colliding with an existing
     event and breaking the hash chain.

  2. Production still holds its OWN two snapshots, taken at seq 22 against the
     history that has now been archived. A projection loading `orders` at seq
     22 would fold the NEW events 23-52 on top of the OLD order state. That is
     silent corruption, and it is the more dangerous of the two because
     everything would look like it worked.

Snapshots are a pure cache — `load()` returning None falls back to a full fold
— so the fix is to delete the stale ones and let them rebuild against the real
log. They are not migrated: copying a derived cache is pointless, and copying a
cache of a different history is actively harmful.

`fund_nav_snapshots` IS copied. Despite the name it is not a projection cache;
it is the denormalised NAV history the frontend charts read, and it contains
plain floats, so it writes cleanly.
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
os.environ["USE_FAKE_FIRESTORE"] = "0"

from app.fund.chain import verify  # noqa: E402

LOCAL_DB = os.path.join(REPO, ".firestore_local_db.json")
GREEN, RED, YELL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def say(m="", c=""):
    print(f"{c}{m}{OFF}" if c else m)


def main(execute: bool) -> int:
    from app.core.firebase import active_book, db, initialize_firebase

    initialize_firebase()
    c = db()
    say(f"book   : {active_book().get('project_id')}")
    say(f"mode   : {'EXECUTE' if execute else 'DRY RUN'}", RED if execute else GREEN)
    say()

    events = sorted([d.to_dict() for d in c.collection("fund_events").limit(5000).stream()],
                    key=lambda e: e.get("seq", 0))
    v = verify(events)
    say(f"events : {len(events)}  seq {events[0].get('seq')}..{events[-1].get('seq')}")
    say(f"chain  : ok={v.ok} chained={v.chained} unchained={v.unchained}",
        GREEN if v.ok and v.unchained == 0 else RED)
    if not (v.ok and v.chained == len(events)):
        say("REFUSING — the event chain is not intact; fix that before anything else.", RED)
        return 2

    tip = events[-1]["hash"]
    max_seq = max(int(e.get("seq") or 0) for e in events)
    counter = (c.collection("fund_meta").document("event_counter").get().to_dict() or {})
    say(f"counter: seq={counter.get('seq')} (must become {max_seq})",
        RED if counter.get("seq") != max_seq else GREEN)

    stale = [d.id for d in c.collection("fund_snapshots").limit(100).stream()]
    say(f"stale snapshots to delete: {stale}", YELL if stale else DIM)

    local = json.load(open(LOCAL_DB, encoding="utf-8"))
    navs = list(local.get("fund_nav_snapshots", {}).items())
    say(f"nav snapshots to copy    : {len(navs)}")

    if not execute:
        say()
        say("DRY RUN — nothing written. Re-run with --execute.", GREEN)
        return 0

    say()
    # 1. Stale projection caches, describing a history that is now archived.
    for doc_id in stale:
        c.collection("fund_snapshots").document(doc_id).delete()
    say(f"OK deleted {len(stale)} stale snapshot(s) — they will rebuild from the log", GREEN)

    # 2. NAV history the charts read.
    if navs:
        batch = c.batch()
        for doc_id, row in navs:
            batch.set(c.collection("fund_nav_snapshots").document(str(doc_id)), row)
        batch.commit()
        say(f"OK copied {len(navs)} nav snapshot(s)", GREEN)

    # 3. The counter, last — so a crash before this point leaves it low rather
    #    than pointing past events that were never written.
    c.collection("fund_meta").document("event_counter").set(
        {"seq": max_seq, "tip_hash": tip}, merge=True)
    say(f"OK counter set to seq={max_seq}, tip={tip[:12]}...", GREEN)

    # --- verify ------------------------------------------------------------
    time.sleep(2.0)
    say()
    ok = True
    back = (c.collection("fund_meta").document("event_counter").get().to_dict() or {})
    if back.get("seq") != max_seq or back.get("tip_hash") != tip:
        say(f"XX counter reads back wrong: {back}", RED)
        ok = False
    else:
        say(f"OK counter verified: seq={back.get('seq')}", GREEN)

    left = [d.id for d in c.collection("fund_snapshots").limit(10).stream()]
    if left:
        say(f"XX stale snapshots remain: {left}", RED)
        ok = False
    else:
        say("OK no stale projection caches remain", GREEN)

    n = len(list(c.collection("fund_nav_snapshots").limit(100).stream()))
    if n != len(navs):
        say(f"XX nav snapshots: {n}, expected {len(navs)}", RED)
        ok = False
    else:
        say(f"OK nav history present ({n})", GREEN)

    say()
    if ok:
        say("PROMOTION COMPLETE.", GREEN)
        return 0
    say("STILL INCONSISTENT — do not trade.", RED)
    return 3


if __name__ == "__main__":
    raise SystemExit(main("--execute" in sys.argv))
