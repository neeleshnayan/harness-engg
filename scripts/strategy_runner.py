"""Auto strategy runner — exercises the whole execution pipeline over time.

A simple, deterministic DCA-style loop that keeps the spine busy so you can watch
the pipeline end-to-end: propose -> risk gate -> approve -> execute -> poll ->
fill -> NAV / positions / strategy attribution / blotter. Every cycle it buys a
small slice of a rotating liquid symbol, tagged to an "Auto DCA (test)" strategy,
then approves and settles it.

This is a TEST HARNESS, not a trading strategy — it auto-approves because there
is no human in this loop by design. It hits whatever venue the spine is wired to
(instant-fill paper by default; Alpaca paper if the spine runs with Alpaca keys).

    python scripts/strategy_runner.py --base http://127.0.0.1:8090 --interval 60 --capital 20000

Stop with Ctrl-C (or kill the process).
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx

SYMBOLS = ["SPY", "AAPL", "MSFT", "NVDA"]  # liquid rotation


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between cycles")
    ap.add_argument("--capital", type=float, default=20000.0, help="paper capital to ensure via a subscription")
    ap.add_argument("--qty", type=float, default=1.0, help="shares per cycle")
    ap.add_argument("--actor", default="auto-runner")
    args = ap.parse_args()

    base = args.base.rstrip("/") + "/api/v1/fund"
    c = httpx.Client(timeout=30)

    def get(p):
        r = c.get(base + p); r.raise_for_status(); return r.json()

    def post(p, j=None):
        r = c.post(base + p, json=j or {}); r.raise_for_status(); return r.json()

    # 1) ensure there is capital (a $20k tranche) to trade with
    nav = get("/nav")["live"]
    if float(nav.get("total_nav_usd", 0) or 0) < args.capital:
        sub = post("/lp/subscriptions", {"lp_id": "auto-test", "usd_amount": args.capital,
                                         "lp_name": "Auto Test", "actor": args.actor})
        post(f"/lp/subscriptions/{sub['subscription_id']}/confirm", {"actor": args.actor})
        _log(f"seeded ${args.capital:,.0f} paper capital")

    # 2) ensure the strategy exists and is deployed
    sid = None
    for s in get("/strategies")["strategies"]:
        if (s.get("name") or "") == "Auto DCA (test)":
            sid = s["strategy_id"]; break
    if not sid:
        sid = post("/strategies", {"name": "Auto DCA (test)", "actor": args.actor})["strategy_id"]
    try:
        post(f"/strategies/{sid}/state", {"state": "deployed", "actor": args.actor})
    except Exception:  # noqa: BLE001 — already deployed / illegal transition is fine
        pass
    _log(f"runner live: strategy={sid[:8]} interval={args.interval:.0f}s base={args.base}")

    i = 0
    while True:
        sym = SYMBOLS[i % len(SYMBOLS)]
        # mostly buy; every 6th cycle trim to keep cash cycling
        side = "sell" if (i and i % 6 == 0) else "buy"
        try:
            res = post("/orders/propose", {"symbol": sym, "side": side, "qty": args.qty,
                                           "strategy_id": sid, "discretionary": True, "actor": args.actor})
            status = res.get("status")
            if status == "pending_approval":
                oid = res["order_id"]
                post(f"/orders/{oid}/approve", {"approver": args.actor})
                settled = post("/orders/settle")
                nav = get("/nav")["live"]
                _log(f"[{i:04d}] {side} {args.qty} {sym} -> approved; settle polled={settled.get('polled')}; "
                     f"NAV ${float(nav['total_nav_usd']):,.0f}, {len(nav.get('positions', []))} positions")
            elif status == "rejected":
                _log(f"[{i:04d}] {side} {sym} rejected by risk: {'; '.join(res.get('breaches', []))}")
            else:
                _log(f"[{i:04d}] {side} {sym} -> {status}")
        except httpx.HTTPStatusError as e:
            _log(f"[{i:04d}] {side} {sym} HTTP {e.response.status_code}: {e.response.text[:120]}")
        except Exception as e:  # noqa: BLE001
            _log(f"[{i:04d}] error: {e}")
        i += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log("runner stopped")
