"""Bootstrap the real fund's book — the first events in a clean ledger.

    python scripts/bootstrap_fund.py --check                    # inspect only
    python scripts/bootstrap_fund.py --lp "Rushi:5000" --apply  # write

Why this exists: the staging book was polluted by demo seeds and test
subscriptions (fbtest/fix5 holding 10,000 units of capital that never arrived,
plus a synthetic lp_alpaca_import LP holding ~92% of the fund). Because the
ledger is append-only, none of that can be removed — only compensated for. The
production book therefore starts empty and is filled deliberately, here.

Refuses to run against a non-empty book, so it can never be the thing that
pollutes the real ledger.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.abspath("."), ".env"))

from app.core.firebase import active_book, initialize_firebase

initialize_firebase()

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f
from app.fund.projections.positions import PositionsProjection


def parse_lp(spec: str) -> tuple[str, float]:
    """"Name:amount" -> (name, amount)."""
    if ":" not in spec:
        raise ValueError(f"expected Name:amount, got {spec!r}")
    name, amount = spec.rsplit(":", 1)
    return name.strip(), float(amount)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lp", action="append", default=[],
                    help='real subscription, "Name:amount" (repeatable)')
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument("--check", action="store_true", help="report book state and exit")
    args = ap.parse_args()

    book_info = active_book()
    store = EventStore()
    existing = list(store.stream(since_seq=0, limit=5))

    print("=" * 66)
    print(f"  project : {book_info.get('project_id')}")
    print(f"  env     : {book_info.get('env')}")
    print(f"  events  : {len(existing)}{'+' if len(existing) >= 5 else ''}")
    print("=" * 66)

    if args.check:
        book = PositionsProjection(store).build()
        print(f"  cash              : {f(book.cash)}")
        print(f"  units outstanding : {f(book.units_outstanding)}")
        print(f"  positions         : {len(book.positions)}")
        return 0

    if existing:
        print("\nREFUSING: this book already has events.")
        print("Bootstrap is only for a clean ledger — inspect with --check.")
        return 1

    if not args.lp:
        print("\nNothing to do: pass --lp \"Name:amount\" for each real subscription.")
        print("Only include money that has actually arrived; the Alpaca account's")
        print("starting cash should equal the total, so reconcile reads zero drift.")
        return 1

    lps = [parse_lp(s) for s in args.lp]
    total = sum(a for _, a in lps)

    print("\nPLAN" + ("  (APPLYING)" if args.apply else "  (dry run)"))
    for name, amount in lps:
        print(f"  subscribe {name:<20} ${amount:,.2f}  -> {amount:,.2f} units @ $1.00")
    print(f"  {'TOTAL':<30} ${total:,.2f}")
    print("\n  Fund the Alpaca account with exactly this amount so that")
    print("  GET /fund/venue/reconcile reports zero drift from day one.")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write.")
        return 0

    for name, amount in lps:
        lp_id = name.lower().replace(" ", "_")
        sub_id = f"sub-{lp_id}"
        store.append(Event(
            aggregate_id=sub_id, aggregate_type="subscription",
            type=EventType.SUBSCRIPTION_REQUESTED,
            payload={"lp_id": lp_id, "lp_name": name, "usd_amount": D(amount)},
            actor="operator",
        ))
        store.append(Event(
            aggregate_id=sub_id, aggregate_type="subscription",
            type=EventType.CASH_CONFIRMED,
            payload={"subscription_id": sub_id, "lp_id": lp_id, "usd_amount": D(amount)},
            actor="operator",
        ))
        # first money in prices at $1.00/unit by definition
        store.append(Event(
            aggregate_id=sub_id, aggregate_type="subscription",
            type=EventType.UNITS_ISSUED,
            payload={"lp_id": lp_id, "units": D(amount), "nav_per_unit": D("1.0")},
            actor="operator",
        ))
        print(f"  wrote {name}: ${amount:,.2f}")

    book = PositionsProjection(store).build()
    print(f"\nBOOK OPEN — cash {f(book.cash)}, units {f(book.units_outstanding)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
