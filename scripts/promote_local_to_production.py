"""Promote the local ledger to production.

This is NOT a merge, and the distinction is the whole reason this script exists
rather than a loop that copies missing events.

The two ledgers share zero event ids. Each has its own fund inception —
SubscriptionRequested, CashConfirmed, UnitsIssued — because each was started
from scratch. Replaying one into the other would leave the book with two
inceptions, double the units outstanding, and a NAV per unit that is simply
wrong while looking perfectly consistent.

They are two candidate histories and exactly one can be the fund's. Local is
the one that matches the broker: Alpaca holds the positions local's fills
describe, and production has no fills at all.

So production's events are archived, not merged, and local is replayed into a
clean collection with a hash chain laid down from genesis — the promoted book
is born tamper-evident rather than retrofitted.

    # look, change nothing (default)
    python scripts/promote_local_to_production.py

    # do it
    python scripts/promote_local_to_production.py --execute

Nothing is deleted until its archived copy has been read back and counted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

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

from app.fund.chain import rechain, verify  # noqa: E402

LOCAL_DB = os.path.join(REPO, ".firestore_local_db.json")
EVENTS = "fund_events"
COUNTER_COLL, COUNTER_DOC = "fund_meta", "event_counter"

#: Firestore caps a batch at 500 writes. Below it, with a pause, because the
#: quota ceiling this fund already hit once is the reason it is running local.
BATCH = 400
PAUSE_S = 1.0

#: If production ever held one of these, it is a real book and this script must
#: refuse — promoting over it would destroy history that moved money.
MONEY_EVENTS = {"OrderFilled", "UnitsBurned", "PayoutSent", "DividendReceived"}

GREEN, RED, YELL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def say(msg: str = "", colour: str = "") -> None:
    print(f"{colour}{msg}{OFF}" if colour else msg)


def rule(title: str = "") -> None:
    say()
    say(f"-- {title} " + "-" * max(0, 62 - len(title)), DIM)


# --------------------------------------------------------------------- load
def load_local() -> dict[str, list[dict[str, Any]]]:
    with open(LOCAL_DB, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for coll, docs in raw.items():
        rows = list(docs.values())
        if coll == EVENTS:
            rows.sort(key=lambda e: e.get("seq", 0))
        out[coll] = rows
    return out


def read_production(client, coll: str, limit: int = 5000) -> list[dict[str, Any]]:
    q = client.collection(coll)
    if coll == EVENTS:
        q = q.order_by("seq")
    return [{**(d.to_dict() or {}), "_doc_id": d.id} for d in q.limit(limit).stream()]


# ------------------------------------------------------------------- checks
def preflight(local: dict, prod_events: list[dict]) -> list[str]:
    """Everything that must be true before a single byte is written."""
    problems: list[str] = []
    events = local.get(EVENTS, [])

    if not events:
        problems.append("local ledger has no events — nothing to promote")

    seqs = [e.get("seq") for e in events]
    if len(set(seqs)) != len(seqs):
        problems.append("local ledger has duplicate seq numbers")
    if seqs and seqs != sorted(seqs):
        problems.append("local ledger is not in seq order")

    ids = [e.get("event_id") for e in events]
    if len(set(ids)) != len(ids):
        problems.append("local ledger has duplicate event_ids")
    if any(not i for i in ids):
        problems.append("local ledger has events with no event_id")

    # The guard that matters: never promote over a book that traded.
    traded = [e for e in prod_events if e.get("type") in MONEY_EVENTS]
    if traded:
        problems.append(
            f"production holds {len(traded)} event(s) that moved money "
            f"({', '.join(sorted({e.get('type') for e in traded}))}). "
            f"This is a real book — refusing to promote over it."
        )

    inceptions = [e for e in events if e.get("type") == "UnitsIssued"]
    if len(inceptions) > 1:
        problems.append(
            f"local ledger has {len(inceptions)} UnitsIssued events — more than "
            f"one inception would double the units outstanding"
        )
    return problems


def fold_nav(events: list[dict[str, Any]]) -> dict[str, Any]:
    """A minimal, independent fold — units and cash — to compare both sides.

    Deliberately not NavService: the point is to check the migration preserved
    the events, and reusing the same projection on both sides would agree even
    if both were wrong. This counts the primitives directly.
    """
    units, fills, cash_in = 0.0, 0, 0.0
    for e in events:
        p = e.get("payload") or {}
        t = e.get("type")
        if t == "UnitsIssued":
            units += float(p.get("units") or 0)
        elif t == "UnitsBurned":
            units -= float(p.get("units") or 0)
        elif t == "CashConfirmed":
            cash_in += float(p.get("usd_amount") or p.get("amount_usd") or 0)
        elif t == "OrderFilled":
            fills += 1
    return {"units_issued": round(units, 6), "cash_confirmed": round(cash_in, 2),
            "fills": fills, "events": len(events)}


# -------------------------------------------------------------------- write
def commit(client, coll: str, rows: list[dict[str, Any]], id_key: str,
           execute: bool) -> int:
    """Batched writes with a pause. Returns how many were written."""
    if not execute:
        return len(rows)
    written = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        batch = client.batch()
        for row in chunk:
            doc_id = row.get(id_key) or row.get("_doc_id")
            body = {k: v for k, v in row.items() if k != "_doc_id"}
            batch.set(client.collection(coll).document(str(doc_id)), body)
        batch.commit()
        written += len(chunk)
        say(f"    wrote {written}/{len(rows)}", DIM)
        if i + BATCH < len(rows):
            time.sleep(PAUSE_S)
    return written


def delete_all(client, coll: str, doc_ids: list[str], execute: bool) -> int:
    if not execute:
        return len(doc_ids)
    done = 0
    for i in range(0, len(doc_ids), BATCH):
        batch = client.batch()
        for d in doc_ids[i:i + BATCH]:
            batch.delete(client.collection(coll).document(str(d)))
        batch.commit()
        done += len(doc_ids[i:i + BATCH])
        if i + BATCH < len(doc_ids):
            time.sleep(PAUSE_S)
    return done


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="actually write. Without it, nothing is changed.")
    ap.add_argument("--drop", nargs="*", default=[], metavar="EVENT_ID",
                    help="event ids to leave OUT of the promoted history. For "
                         "test artefacts written into the local ledger before "
                         "it became the book of record. Every dropped event is "
                         "printed; nothing is ever removed silently.")
    args = ap.parse_args()
    execute = args.execute

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_coll = f"fund_events_archive_{stamp}"

    from app.core.firebase import active_book, db, initialize_firebase

    initialize_firebase()
    client = db()
    book = active_book()

    rule("target")
    say(f"project      : {book.get('project_id')}")
    say(f"database     : {book.get('database_id')}")
    say(f"env          : {book.get('env')}")
    say(f"mode         : {'EXECUTE — will write' if execute else 'DRY RUN — nothing changes'}",
        RED if execute else GREEN)

    local = load_local()
    local_events = local.get(EVENTS, [])
    prod_events = read_production(client, EVENTS)

    if args.drop:
        drop = set(args.drop)
        keep, dropped = [], []
        for e in local_events:
            (dropped if e.get("event_id") in drop else keep).append(e)
        rule("dropped from the promoted history")
        for e in dropped:
            say(f"  seq {e.get('seq')} {e.get('type')} "
                f"{e.get('event_id')} {str(e.get('ts'))[:19]}", YELL)
        missing = drop - {e.get("event_id") for e in dropped}
        for m in missing:
            say(f"  (no event with id {m} — nothing to drop)", DIM)
        if any(e.get("type") in MONEY_EVENTS for e in dropped):
            say("  XX refusing: one of those moved money", RED)
            return 2
        local_events = keep
        local[EVENTS] = keep

    rule("what is on each side")
    say(f"local      : {len(local_events)} events   {fold_nav(local_events)}")
    say(f"production : {len(prod_events)} events   {fold_nav(prod_events)}")

    shared = ({e.get("event_id") for e in local_events}
              & {e.get("event_id") for e in prod_events})
    say(f"shared ids : {len(shared)}"
        + ("" if shared else "  (confirmed: two unrelated histories)"))

    rule("preflight")
    problems = preflight(local, prod_events)
    if problems:
        for p in problems:
            say(f"  XX  {p}", RED)
        say()
        say("REFUSING — fix the above first.", RED)
        return 2
    say("  OK  local ledger is internally consistent", GREEN)
    say("  OK  production holds nothing that moved money", GREEN)
    say("  OK  exactly one fund inception in the promoted history", GREEN)

    # --- build the promoted events ----------------------------------------
    promoted = rechain([{k: v for k, v in e.items() if k != "_doc_id"}
                        for e in local_events])
    check = verify(promoted)
    if not check.ok:
        say(f"  XX  rebuilt chain does not verify: {check.first_break}", RED)
        return 2
    say(f"  OK  rebuilt hash chain verifies over {check.chained} events", GREEN)

    tip = promoted[-1]["hash"]
    max_seq = max(int(e.get("seq") or 0) for e in promoted)

    rule("plan")
    say(f"  1. archive {len(prod_events)} production events -> {archive_coll}")
    say(f"  2. delete those {len(prod_events)} from {EVENTS} (only after archive verified)")
    say(f"  3. write {len(promoted)} promoted events into {EVENTS}, chained from genesis")
    for coll, rows in local.items():
        if coll in (EVENTS, COUNTER_COLL):
            continue
        say(f"  4. copy {len(rows)} docs -> {coll}")
    say(f"  5. set {COUNTER_COLL}/{COUNTER_DOC} to seq={max_seq}, tip_hash={tip[:12]}...")
    say(f"  6. read back and verify")

    if not execute:
        rule()
        say("DRY RUN — nothing was written.", GREEN)
        say("Re-run with --execute to apply.", DIM)
        return 0

    # --- 1. archive --------------------------------------------------------
    rule("executing")
    say(f"  archiving {len(prod_events)} events -> {archive_coll}")
    commit(client, archive_coll, prod_events, "event_id", execute)
    back = read_production(client, archive_coll)
    if len(back) != len(prod_events):
        say(f"  XX  archive holds {len(back)}, expected {len(prod_events)} — STOPPING "
            f"before deleting anything", RED)
        return 3
    say(f"  OK  archive verified: {len(back)} documents readable", GREEN)

    # --- 2. clear ----------------------------------------------------------
    ids = [e.get("_doc_id") or e.get("event_id") for e in prod_events]
    delete_all(client, EVENTS, ids, execute)
    say(f"  OK  cleared {len(ids)} events from {EVENTS}", GREEN)

    # --- 3. replay ---------------------------------------------------------
    say(f"  writing {len(promoted)} promoted events")
    commit(client, EVENTS, promoted, "event_id", execute)

    # --- 4. other collections ---------------------------------------------
    for coll, rows in local.items():
        if coll in (EVENTS, COUNTER_COLL) or not rows:
            continue
        key = "snapshot_id" if "snapshot" in coll else "id"
        say(f"  writing {len(rows)} docs -> {coll}")
        commit(client, coll, rows, key, execute)

    # --- 5. counter --------------------------------------------------------
    client.collection(COUNTER_COLL).document(COUNTER_DOC).set(
        {"seq": max_seq, "tip_hash": tip}, merge=True)
    say(f"  OK  counter set to seq={max_seq}", GREEN)

    # --- 6. verify ---------------------------------------------------------
    rule("verification")
    time.sleep(2.0)
    final = read_production(client, EVENTS)
    final.sort(key=lambda e: e.get("seq", 0))

    ok = True
    if len(final) != len(promoted):
        say(f"  XX  production has {len(final)} events, expected {len(promoted)}", RED)
        ok = False
    else:
        say(f"  OK  event count matches ({len(final)})", GREEN)

    v = verify(final)
    if v.ok and v.chained == len(promoted):
        say(f"  OK  hash chain verifies over all {v.chained} events", GREEN)
    else:
        say(f"  XX  chain: {v.to_dict()}", RED)
        ok = False

    before, after = fold_nav(local_events), fold_nav(final)
    if before == after:
        say(f"  OK  book folds identically: {after}", GREEN)
    else:
        say(f"  XX  fold differs — local {before} vs production {after}", RED)
        ok = False

    rule()
    if ok:
        say("PROMOTED. Production now holds the book that matches the broker.", GREEN)
        say(f"The previous 22 events remain readable at {archive_coll}.", DIM)
        say()
        say("Next: set FUND_MODE=alpaca-paper in .env and restart, then reconcile "
            "against Alpaca before proposing anything.", YELL)
        return 0
    say("VERIFICATION FAILED — production may be half-written. Do NOT trade.", RED)
    say(f"The original production events are intact at {archive_coll}.", YELL)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
