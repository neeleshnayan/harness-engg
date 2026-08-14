"""Rebuild the local ledger as an exact mirror of production.

The point is to make today's offline session APPEND to the fund's history
rather than fork it. This morning's mess came from two ledgers that each began
at seq 1 with their own inception, which cannot be merged — only chosen
between. Doing that again tonight would be the same mistake with the day's real
fills inside it.

So local is not "a fresh book to play with". It is production's 52 events,
byte-for-byte, with the same event ids, the same seq numbers and the same hash
chain. Today's trading continues from seq 53. Tonight, syncing back is a matter
of appending the events production has never seen, which chain cleanly onto a
tip it already holds.

The chain is what makes this verifiable. rechain() is deterministic over an
ordered list of events, so recomputing it here must reproduce production's tip
exactly. If it does not, local is NOT a mirror and this script refuses — that
check is the whole safety argument, because the alternative is discovering the
divergence tonight with a session's fills at stake.

    python scripts/mirror_production_locally.py            # dry run
    python scripts/mirror_production_locally.py --execute
"""

from __future__ import annotations

import json
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from app.fund.chain import rechain, verify  # noqa: E402

LOCAL_DB = os.path.join(REPO, ".firestore_local_db.json")
SOURCE = os.path.join(REPO, ".firestore_local_db.json.promoted-20260814")

#: The hash of the last event in production, printed by finish_promotion.py
#: when the counter was set. Recomputing the chain here must land on it.
EXPECTED_TIP_PREFIX = "6f63f5bb9dde"

#: My hash-chain smoke test, written into the local ledger before promotion and
#: deliberately excluded from it. Excluded here too, or local would hold an
#: event production does not and the mirror would be off by one.
DROP_EVENT_IDS = {"58432ef8-bf52-4f11-811b-39b45b7ead26"}

GREEN, RED, YELL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def say(m="", c=""):
    print(f"{c}{m}{OFF}" if c else m)


def main(execute: bool) -> int:
    if not os.path.exists(SOURCE):
        say(f"XX no source ledger at {SOURCE}", RED)
        return 2

    raw = json.load(open(SOURCE, encoding="utf-8"))
    events = sorted(raw.get("fund_events", {}).values(), key=lambda e: e.get("seq", 0))
    kept = [e for e in events if e.get("event_id") not in DROP_EVENT_IDS]

    say(f"source        : {os.path.basename(SOURCE)}")
    say(f"events        : {len(events)} -> {len(kept)} after excluding the smoke test")

    # Strip any chain fields so we rebuild from the same starting point the
    # promotion did — otherwise we would be hashing over hashes.
    bare = [{k: v for k, v in e.items() if k not in ("hash", "prev_hash")} for e in kept]
    chained = rechain(bare)

    v = verify(chained)
    tip = chained[-1]["hash"] if chained else ""
    say(f"chain rebuilt : ok={v.ok} chained={v.chained}")
    say(f"tip           : {tip[:12]}...")

    if not tip.startswith(EXPECTED_TIP_PREFIX):
        say()
        say(f"XX tip does not match production ({EXPECTED_TIP_PREFIX}...).", RED)
        say("   Local would NOT be a mirror, and tonight's sync would fork the", RED)
        say("   book again. Refusing.", RED)
        return 3
    say(f"OK matches production's tip — local will be an exact mirror", GREEN)

    max_seq = max(int(e.get("seq") or 0) for e in chained)
    say(f"counter       : seq={max_seq}, tip_hash set so appends continue the chain")
    say(f"today's fills : will start at seq {max_seq + 1}")

    if not execute:
        say()
        say("DRY RUN — nothing written. Re-run with --execute.", GREEN)
        return 0

    # Preserve whatever is currently there before overwriting.
    if os.path.exists(LOCAL_DB):
        backup = LOCAL_DB + ".replaced"
        shutil.copy2(LOCAL_DB, backup)
        say(f"OK existing local ledger copied to {os.path.basename(backup)}", DIM)

    out = {
        "fund_events": {e["event_id"]: e for e in chained},
        "fund_nav_snapshots": raw.get("fund_nav_snapshots", {}),
        # Projection caches are derived — let them rebuild against the real log
        # rather than carrying a snapshot of a slightly different history.
        "fund_snapshots": {},
        "fund_meta": {"event_counter": {"seq": max_seq, "tip_hash": tip}},
    }
    with open(LOCAL_DB, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    say()
    say(f"OK local ledger rebuilt: {len(chained)} events, seq 1..{max_seq}", GREEN)
    say("MIRROR READY.", GREEN)
    say()
    say("Today: run ./scripts/run_local.sh. Tonight: sync_local_to_production.py", YELL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--execute" in sys.argv))
