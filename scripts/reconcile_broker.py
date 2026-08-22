"""Reconcile the event-sourced book against the broker.

    python scripts/reconcile_broker.py            # dry run — writes nothing
    python scripts/reconcile_broker.py --apply    # append the planned events

Idempotent: fills already in the log are skipped, so a partial run can be
re-run safely. Always read the dry run before applying.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.abspath("."), ".env"))

from app.core.firebase import initialize_firebase

initialize_firebase()

from app.fund.backfill import BrokerBackfill
from app.fund.events import EventStore
from app.fund.projections.positions import PositionsProjection


def _paper_from_mode() -> bool:
    """Paper vs LIVE, decided by the fund's declared MODE.

    Refuses (via resolve()) when no mode is declared, which is right for a
    script that opens a real broker client: the alternative was
    ``os.getenv("ALPACA_PAPER", "true")``, a variable that decided whether
    real money could move while living beside a CORS list.
    """
    from app.fund.mode import VenueKind, resolve
    return resolve().venue_kind is VenueKind.ALPACA_PAPER


def broker_state():
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    client = TradingClient(
        os.getenv("ALPACA_API_KEY"),
        os.getenv("ALPACA_SECRET_KEY"),
        # From the MODE, like the order path. ALPACA_PAPER decided real money
        # while living beside a CORS list (adversary D11, K8).
        paper=_paper_from_mode(),
    )
    fills = [
        {
            "client_order_id": o.client_order_id,
            "symbol": o.symbol,
            "side": str(o.side).split(".")[-1].lower(),
            "qty": float(o.filled_qty),
            "price": float(o.filled_avg_price or 0),
            "ts": str(o.filled_at or o.submitted_at)[:19],
        }
        for o in client.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=500))
        if float(o.filled_qty or 0) > 0
    ]
    positions = {p.symbol: float(p.qty) for p in client.get_all_positions()}
    equity = float(client.get_account().equity)
    return fills, positions, equity


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="append the events (default: dry run)")
    ap.add_argument("--phantom", nargs="*", default=[],
                    help="client_order_ids booked on the wrong venue, to reverse")
    args = ap.parse_args()

    store = EventStore()
    fills, broker_pos, broker_equity = broker_state()
    bf = BrokerBackfill(store=store)
    plan = bf.plan(fills, phantom_coids=args.phantom)

    before = PositionsProjection(store).build()
    before_qty = {s: float(p["qty"]) for s, p in before.positions.items()}

    print("=" * 74)
    print("PLAN" + ("  (APPLYING)" if args.apply else "  (dry run — nothing will be written)"))
    print("=" * 74)
    print(f"  reversals : {len(plan.reversals)}")
    for p in plan.reversals:
        print(f"      {p.side:<4} {float(p.qty):>6.2f} {p.symbol:<5} @ {float(p.avg_price):>8.2f}  {p.reason}")
    print(f"  replay    : {len(plan.replay)} unlogged broker fills")
    print(f"  skipped   : {len(plan.skipped_already_logged)} already in the log")

    print("\n  net change by symbol:")
    for s, q in sorted(plan.net_by_symbol().items()):
        print(f"      {s:<6} {float(q):>+8.2f}")

    print("\n" + "=" * 74)
    print("PROJECTED RESULT vs BROKER")
    print("=" * 74)
    net = {s: float(q) for s, q in plan.net_by_symbol().items()}
    all_ok = True
    for s in sorted(set(before_qty) | set(broker_pos) | set(net)):
        after = before_qty.get(s, 0.0) + net.get(s, 0.0)
        tgt = broker_pos.get(s, 0.0)
        ok = abs(after - tgt) < 1e-6
        all_ok = all_ok and ok
        print(f"  {s:<6} before={before_qty.get(s,0.0):>7.2f}  after={after:>7.2f}  "
              f"broker={tgt:>7.2f}  {'OK' if ok else 'MISMATCH'}")

    print(f"\n  book cash before: {float(before.cash):>12,.2f}")
    print(f"  broker equity   : {broker_equity:>12,.2f}")

    if not all_ok:
        print("\nREFUSING: the plan does not reconcile the book to the broker.")
        return 1

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write these events.")
        return 0

    res = bf.apply(plan)
    after = PositionsProjection(EventStore()).build()
    print(f"\nAPPLIED: {res['written']} events written.")
    print("  post-apply book:")
    for s, p in sorted(after.positions.items()):
        if abs(float(p["qty"])) > 1e-9:
            print(f"      {s:<6} {float(p['qty']):>7.2f}   (broker {broker_pos.get(s, 0.0):>7.2f})")
    print(f"  cash: {float(after.cash):,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
