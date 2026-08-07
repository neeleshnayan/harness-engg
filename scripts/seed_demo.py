#!/usr/bin/env python3
"""Seed a realistic demo fund into a running spine — so Rushi opens to a live book.

    HARNESS_URL=http://127.0.0.1:8090 python scripts/seed_demo.py

Creates LP deposits, two deployed strategies (backtested on real free bars), a
filled position, and leaves ONE pending order for Rushi to approve. Safe to run
against the paper venue or Alpaca paper (an approved order routes to the venue).
"""
import json
import os
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.getenv("HARNESS_URL", "http://127.0.0.1:8090").rstrip("/") + "/api/v1/fund"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def main():
    print(f"Seeding demo fund → {BASE}")
    for lp_id, usd, name in [("aisha", 2500, "Aisha K"), ("rahul", 1500, "Rahul M"),
                             ("mira", 1000, "Mira S"), ("devs", 800, "Dev Squad")]:
        sub = call("POST", "/lp/subscriptions", {"lp_id": lp_id, "usd_amount": usd, "lp_name": name})
        call("POST", f"/lp/subscriptions/{sub['subscription_id']}/confirm", {"actor": "rushi"})
    print("  4 LPs deposited")

    s1 = call("POST", "/strategies", {"name": "US Momentum"})["strategy_id"]
    s2 = call("POST", "/strategies", {"name": "Mega-Cap Tech"})["strategy_id"]
    for sid, sym, strat in [(s1, "AAPL", "sma"), (s2, "MSFT", "buy_hold")]:
        try:
            call("POST", f"/strategies/{sid}/backtest/by_symbol",
                 {"symbol": sym, "strategy": strat, "fast": 20, "slow": 50})
        except Exception as e:  # noqa: BLE001 — network bars are best-effort
            print(f"  (backtest {sym} skipped: {e})")
    for sid, pct in [(s1, 35), (s2, 25)]:
        call("POST", f"/strategies/{sid}/state", {"state": "deployed"})
        call("POST", f"/strategies/{sid}/allocation", {"target_pct": pct})
    print("  2 strategies backtested + deployed + allocated")

    o = call("POST", "/orders/propose", {"symbol": "AAPL", "side": "buy", "qty": 3, "strategy_id": s1})
    if o.get("status") == "pending_approval":
        call("POST", f"/orders/{o['order_id']}/approve", {"approver": "rushi"})
        call("POST", "/orders/settle")
        print("  1 AAPL position filled")
    call("POST", "/orders/propose", {"symbol": "MSFT", "side": "buy", "qty": 2, "strategy_id": s2})
    print("  1 MSFT order left PENDING for Rushi to approve")

    nav = call("GET", "/nav")["live"]
    print(f"\n✅ Seeded. NAV ${nav['total_nav_usd']:,.0f} · open the cockpit at /clark/studio")


if __name__ == "__main__":
    raise SystemExit(main())
