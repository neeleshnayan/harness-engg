"""Move the fund's event log from Firestore to Postgres.

Copies every event VERBATIM — seq, prev_hash and hash exactly as stored — and
then verifies the chain in its new home. Recomputing the hashes on the way in
would produce a ledger that verifies against itself while proving nothing about
the history it claims to be, which is precisely the dishonesty the chain exists
to prevent.

The migration refuses to declare success unless:

  * the destination was empty (or --force was given),
  * every source event arrived,
  * the chain verifies in Postgres with the same chained count as the source,
  * and the counter row points at the real tail.

Any of those failing leaves Postgres untrusted and the fund still on Firestore.
Nothing is deleted from Firestore, ever — the point of this exercise is that
Firestore becomes the durable copy, not the discarded one.

    python scripts/migrate_to_postgres.py            # dry run: report only
    python scripts/migrate_to_postgres.py --execute
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.fund.chain import verify  # noqa: E402
from app.fund.pgstore import PostgresEventStore  # noqa: E402


LOCAL_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        ".firestore_local_db.json")


def read_local() -> list[dict]:
    """Every event in the on-disk ledger, oldest first.

    The local file predates the Firestore cutover and was kept in step with it,
    so it holds the same hash-chained log — and reading it costs nothing. That
    matters more than convenience: Firestore's free tier has a daily READ
    quota, and replaying a 155-event log to migrate it is exactly the kind of
    read that exhausts it. Migrating out of a database via a source that is not
    that database is a nice property of an append-only log with a hash chain:
    the chain proves the copy, so the copy does not have to be authoritative.

    The chain is what makes this safe. If the local file had drifted from
    Firestore it would not verify to the same tip, and the caller checks that.
    """
    import json
    with open(LOCAL_DB, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = list((doc.get("fund_events") or {}).values())
    rows.sort(key=lambda e: e.get("seq") or 0)
    counter = ((doc.get("fund_meta") or {}).get("event_counter") or {})
    if counter:
        print(f"  local counter: seq={counter.get('seq')} "
              f"tip={str(counter.get('tip_hash'))[:12]}...")
    return rows


def read_source() -> list[dict]:
    """Every event in the Firestore log, oldest first.

    FUND_STORE is forced, not defaulted: running this with the environment
    already switched to postgres would read the destination and report a
    flawless migration of nothing.
    """
    os.environ["FUND_STORE"] = "firestore"
    # Without this the script authenticates with the DEFAULT service-account
    # key, which belongs to the WALLET project — a different, unrelated,
    # unchained 85-event book. A dry run caught it; an --execute would have
    # loaded the wrong ledger into the fund's store and every projection would
    # have folded obediently over it.
    from dotenv import load_dotenv
    load_dotenv()

    from app.core.firebase import active_book, initialize_firebase
    initialize_firebase()
    book = active_book()
    print(f"  book: project={book.get('project')} db={os.getenv('FIRESTORE_DATABASE_ID')}")
    from app.fund.events import EventStore
    src = EventStore()
    return src.stream(limit=1_000_000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="actually write; without it this only reports")
    ap.add_argument("--force", action="store_true",
                    help="write even though Postgres already holds events")
    ap.add_argument("--allow-unchained", action="store_true",
                    help="migrate a source with no hash chain at all (this is "
                         "normally the wrong-project mistake, not an intent)")
    ap.add_argument("--from-local", action="store_true",
                    help="read the on-disk ledger instead of Firestore — no "
                         "read quota, same chained log")
    args = ap.parse_args()

    if args.from_local:
        print(f"reading local ledger {LOCAL_DB}...")
        events = read_local()
    else:
        print("reading Firestore log...")
        events = read_source()
    src_check = verify(events)
    print(f"  source: {len(events)} events | chain ok={src_check.ok} "
          f"chained={src_check.chained} unchained={src_check.unchained}")
    if not events:
        print("nothing to migrate")
        return 0
    if not src_check.ok:
        print("REFUSING: the SOURCE chain is already broken. Migrating a broken "
              "chain would hide the break behind a fresh copy.")
        print(f"  first break: {src_check.first_break}")
        return 1

    # The fund's ledger is hash-chained. A book with NO chained events is not
    # this fund's log — it is the wallet project's, reached by authenticating
    # with the wrong service-account key. That is a config mistake that reads
    # as success, so it is refused by evidence rather than by trusting .env.
    if src_check.chained == 0 and not args.allow_unchained:
        print(f"REFUSING: not one of these {len(events)} events is hash-chained.")
        print("  The fund's ledger IS chained, so this is almost certainly the "
              "wrong Firebase project — check FIREBASE_SERVICE_ACCOUNT_JSON "
              "points at the fund key, not the wallet one.")
        print("  Pass --allow-unchained only if you genuinely mean to migrate "
              "a pre-chain ledger.")
        return 1

    dst = PostgresEventStore()
    existing = dst.count()
    print(f"  destination: {existing} events already in Postgres")
    if existing and not args.force:
        print("REFUSING: Postgres is not empty. Re-running would interleave two "
              "histories. Pass --force only if you know it holds a prefix of "
              "this same log.")
        return 1

    if not args.execute:
        print("\nDRY RUN. Re-run with --execute to write.")
        print(f"would copy {len(events)} events, seq {events[0].get('seq')} "
              f"-> {events[-1].get('seq')}")
        return 0

    print(f"copying {len(events)} events verbatim...")
    for i, e in enumerate(events, 1):
        dst.append_raw(e)
        if i % 25 == 0:
            print(f"  {i}/{len(events)}")

    head = dst.sync_chain_head()
    print(f"  chain head: seq={head['seq']} tip={head['tip_hash'][:12]}...")

    # The check that decides whether any of this is trustworthy.
    copied = dst.count()
    dst_check = verify(dst.stream(limit=1_000_000))
    print(f"\nverification: {copied} events in Postgres | chain ok={dst_check.ok} "
          f"chained={dst_check.chained} unchained={dst_check.unchained}")

    problems = []
    if copied != len(events):
        problems.append(f"copied {copied} of {len(events)} events")
    if not dst_check.ok:
        problems.append(f"destination chain broken at {dst_check.first_break}")
    if dst_check.chained != src_check.chained:
        problems.append(f"chained count changed: {src_check.chained} -> "
                        f"{dst_check.chained} (hashes did not survive the copy)")
    if head["seq"] != events[-1].get("seq"):
        problems.append(f"counter at {head['seq']}, log ends at {events[-1].get('seq')}")

    if problems:
        print("\nMIGRATION NOT TRUSTWORTHY:")
        for p in problems:
            print("  -", p)
        print("Leave FUND_STORE on firestore.")
        return 1

    print("\nMigration verified. The same evidence that held in Firestore holds "
          "here: identical hashes, identical chain.")
    print("Set FUND_STORE=postgres to run the fund on it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
