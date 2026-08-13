"""Read-only: does our ledger agree with what Alpaca actually did?

Run this while the market is open to prove the live path works end to end. It
places nothing and cancels nothing — it reads both sides and reports the gap.

The three questions it answers, in the order they matter:

  1. Is the venue in the state we think it is? (open orders, positions, cash)
  2. Does every broker fill have a matching event in our log?
  3. Does NAV computed from our event log agree with broker equity?

NAV is folded from the event log and is never overwritten by broker equity — the
broker is a *comparison*, not the truth. A gap is a signal to investigate, not a
number to copy across.
"""

import json
import os
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1/fund"


def call(path, method="GET", body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:300]}
    except Exception as e:  # noqa: BLE001
        return {"_error": "unreachable", "_body": str(e)}


def broker():
    from dotenv import load_dotenv
    load_dotenv()
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        return None
    c = TradingClient(key, secret, paper=True)
    return {
        "client": c,
        "account": c.get_account(),
        "clock": c.get_clock(),
        "positions": c.get_all_positions(),
        "orders": c.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100)),
    }


def main() -> int:
    print("=" * 72)
    book = call("/book")
    if book.get("_error"):
        print("SPINE UNREACHABLE:", book)
        return 1
    print(f"SPINE   env={book.get('env')}  venue={book.get('venue')}  "
          f"orders_are_real={book.get('orders_are_real')}")
    if not book.get("orders_are_real"):
        print("  NOTE: this spine simulates fills locally. Broker comparison below is")
        print("        still useful, but our orders are NOT reaching Alpaca.")

    b = broker()
    if b is None:
        print("No Alpaca credentials — cannot compare.")
        return 1

    acct, clock = b["account"], b["clock"]
    print(f"BROKER  {acct.account_number}  equity ${float(acct.equity):,.2f}  "
          f"cash ${float(acct.cash):,.2f}")
    print(f"MARKET  {'OPEN' if clock.is_open else 'CLOSED'}  "
          f"next_open={clock.next_open}  next_close={clock.next_close}")

    # --- 1. open orders at the venue -------------------------------------
    open_orders = [o for o in b["orders"]
                   if o.status.value in ("new", "accepted", "partially_filled",
                                         "pending_new", "held")]
    print()
    print(f"OPEN ORDERS AT VENUE: {len(open_orders)}")
    for o in open_orders:
        print(f"  {str(o.submitted_at)[:19]}  {o.side.value:<4} {str(o.qty):>10} "
              f"{o.symbol:<6} {o.status.value:<16} filled={o.filled_qty}")
    if open_orders:
        print("  These WILL fill when the market opens. If they were not intended,")
        print("  cancel them at the venue BEFORE the open — a fill is permanent.")

    # --- 2. positions -----------------------------------------------------
    nav = call("/nav").get("live") or {}
    ours = {p["symbol"].upper(): float(p["qty"]) for p in (nav.get("positions") or [])}
    theirs = {p.symbol.upper(): float(p.qty) for p in b["positions"]}
    print()
    print(f"POSITIONS   ledger={len(ours)}  broker={len(theirs)}")
    for sym in sorted(set(ours) | set(theirs)):
        a, t = ours.get(sym, 0.0), theirs.get(sym, 0.0)
        flag = "" if abs(a - t) < 1e-6 else "   <-- MISMATCH"
        print(f"  {sym:<6} ledger {a:>12.4f}   broker {t:>12.4f}{flag}")

    # --- 3. NAV vs equity -------------------------------------------------
    nav_usd = float(nav.get("total_nav_usd") or 0)
    equity = float(acct.equity)
    print()
    print(f"NAV (folded from the event log) ${nav_usd:,.2f}")
    print(f"BROKER EQUITY                   ${equity:,.2f}")
    print(f"DRIFT                           ${nav_usd - equity:,.2f}")
    print("  NAV is never overwritten by broker equity. Drift is a signal to")
    print("  investigate (scripts/reconcile_broker.py, dry run first), not to copy.")

    rec = call("/venue/reconcile")
    if not rec.get("_error"):
        print()
        print("SPINE RECONCILIATION:", json.dumps(rec, default=str)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
