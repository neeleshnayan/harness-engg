"""Push new Postgres events to Firestore for durability.

    python scripts/snapshot_to_firestore.py            # report only
    python scripts/snapshot_to_firestore.py --execute
    python scripts/snapshot_to_firestore.py --status

Safe to run on a schedule and safe to run twice: events are keyed by event_id,
so a re-push overwrites rather than duplicates, and the watermark means a run
with nothing new costs no writes at all.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--set-watermark", type=int, metavar="SEQ",
                    help="declare Firestore already holds events up to SEQ "
                         "(use once, right after the migration)")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    # The source is Postgres regardless of how the spine happens to be
    # configured; this script's whole job is the direction pg -> firestore.
    os.environ["FUND_STORE"] = "postgres"

    from app.core.firebase import active_book, initialize_firebase
    initialize_firebase()
    book = active_book()
    print(f"destination: project={book.get('project')} "
          f"db={os.getenv('FIRESTORE_DATABASE_ID')}")

    from app.fund.snapshot_firestore import FirestoreSnapshotter
    snap = FirestoreSnapshotter()

    if args.set_watermark is not None:
        snap.set_watermark(args.set_watermark)
        print(f"  watermark set to seq {args.set_watermark}")
        for k, v in snap.status().items():
            print(f"  {k}: {v}")
        return 0

    if args.status:
        for k, v in snap.status().items():
            print(f"  {k}: {v}")
        return 0

    result = snap.run(dry_run=not args.execute)
    for k, v in result.items():
        print(f"  {k}: {v}")
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
