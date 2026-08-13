"""Seed the in-memory mock book: fake transactions, real market prices.

Mock mode is for exercising the product when the real ledger is unavailable or
when you simply do not want to touch it. The fills are invented; the prices they
fill at are not — marks come from live market data, so NAV, exposure, drawdown
and reconciliation all move against reality.

Run against a spine started with USE_FAKE_FIRESTORE=1. Refuses otherwise: this
writes subscriptions and fills, and none of that belongs in the real book.
"""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1/fund"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:200]}


def must(res, what):
    """Seeding silently over a failed call is how a book ends up describing
    state it does not have. Stop instead."""
    if isinstance(res, dict) and res.get("_error"):
        print(f"FAILED {what}: HTTP {res['_error']} {res.get('_body','')}")
        raise SystemExit(1)
    return res


def main() -> int:
    book = call("GET", "/book")
    if book.get("env") != "mock":
        print(f"REFUSING: spine is not in mock mode (env={book.get('env')!r}, "
              f"project={book.get('project_id')!r}).")
        print("Start it with USE_FAKE_FIRESTORE=1 first.")
        return 1

    print(f"mock book: {book.get('project_id')} / {book.get('env')}\n")

    # 1. capital
    sub = must(call("POST", "/lp/subscriptions",
                    {"lp_id": "rushi", "lp_name": "Rushi",
                     "usd_amount": 2000.0, "actor": "operator"}), "subscribe")
    sid = sub.get("subscription_id")
    if not sid:
        print(f"FAILED subscribe: no subscription_id in {sub}")
        return 1
    must(call("POST", f"/lp/subscriptions/{sid}/confirm", {"actor": "operator"}), "confirm cash")
    print(f"  funded $2,000  (subscription {str(sid)[:8]})")

    # 2. a strategy with a real, tradeable universe
    st = call("POST", "/strategies", {"name": "Mock SMA Crossover", "actor": "rushi",
                                      "definition": {"type": "sma", "fast": 10, "slow": 30}})
    st_id = st.get("strategy_id")
    if not st_id:
        print("  could not create strategy:", st)
        return 1
    assets = ["INTC", "F", "SOFI", "PLTR"]
    call("POST", f"/strategies/{st_id}/assets", {"symbols": assets, "actor": "rushi"})
    # one backtest is enough to move the strategy out of draft; four means four
    # year-long bar fetches and a needlessly slow seed
    bt = call("POST", f"/strategies/{st_id}/backtest/by_symbol",
              {"symbol": "INTC", "lookback_days": 365})
    if "result" in bt:
        r = bt["result"]
        print(f"  backtested INTC: return {r['total_return']*100:.1f}% sharpe {r['sharpe']:.2f}")
    call("POST", f"/strategies/{st_id}/state", {"state": "deployed", "actor": "rushi"})
    call("POST", f"/strategies/{st_id}/allocation", {"target_pct": 50.0, "actor": "rushi"})
    print(f"  strategy deployed at 50%  ({st_id[:8]}) — {', '.join(assets)}")

    # 3. fills at real prices. Sized to sit inside the limits so the book looks
    #    like a working fund rather than one in permanent breach.
    orders = [("INTC", 2.0), ("F", 12.0), ("SOFI", 8.0)]
    filled = 0
    for sym, qty in orders:
        p = call("POST", "/orders/propose",
                 {"symbol": sym, "side": "buy", "qty": qty,
                  "strategy_id": st_id, "actor": "rushi"})
        oid = p.get("order_id")
        if p.get("status") != "pending_approval":
            print(f"  {sym:<5} not proposed: {p.get('breaches') or p.get('_body') or p.get('status')}")
            continue
        call("POST", f"/orders/{oid}/approve", {"approver": "rushi"})
        filled += 1
        px = (p.get("impact_preview") or {}).get("quote_price")
        print(f"  bought {qty:>5} {sym:<5} @ {px}")

    # 4. one pending order left unapproved, so Decide has something real in it
    p = call("POST", "/orders/propose",
             {"symbol": "PLTR", "side": "buy", "qty": 1.0,
              "strategy_id": st_id, "actor": "rushi"})
    if p.get("status") == "pending_approval":
        print(f"  left 1 PLTR pending approval  ({str(p.get('order_id'))[:8]})")

    call("POST", "/nav/strike", {"actor": "system"})

    nav = call("GET", "/nav").get("live", {})
    print(f"\n  NAV ${nav.get('total_nav_usd'):,.2f} · "
          f"cash ${(nav.get('breakdown') or {}).get('cash', 0):,.2f} · "
          f"{len(nav.get('positions') or [])} positions · {filled} fills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
