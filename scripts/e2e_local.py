#!/usr/bin/env python3
"""End-to-end test against a RUNNING ClarkHarness spine (real Firestore).

Usage (spine running, e.g. `uvicorn app.main:app --port 8090`):

    HARNESS_URL=http://127.0.0.1:8090 python3 scripts/e2e_local.py

Exercises the whole fund loop over HTTP: deposit → units, create → backtest →
deploy → allocate a strategy, propose → approve → settle an order, then reads
NAV / positions / strategies / LPs and reconciles.

Assertions are structural and relative (unique ids per run, invariants not
absolutes) so it is safe to run repeatedly against a shared database, and works
on both the paper venue (instant fill) and Alpaca (async fill is reported, not
required). Exit code 0 = all green.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# Windows consoles default to cp1252; this script prints → × ✅ ❌. Force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001  (older/odd streams without reconfigure)
    pass

BASE = os.getenv("HARNESS_URL", "http://127.0.0.1:8090").rstrip("/")
API = BASE + "/api/v1/fund"
RID = str(int(time.time()))
FAILS: list[str] = []


def _call(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def GET(path):
    return _call("GET", API + path)


def POST(path, body=None):
    return _call("POST", API + path, body or {})


def check(name, cond, detail=""):
    ok = bool(cond)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)
    return ok


def section(title):
    print(f"\n{title}")


def main():
    print(f"ClarkHarness E2E · {BASE} · run {RID}")

    section("0) Health")
    st, _ = _call("GET", BASE + "/health")
    if not check("service is up", st == 200, f"GET /health -> {st}"):
        print("\nSpine not reachable — start it: uvicorn app.main:app --port 8090")
        return 1

    section("1) LP subscribes (deposit → units at NAV)")
    lp = f"e2e_alice_{RID}"
    st, r = POST("/lp/subscriptions", {"lp_id": lp, "usd_amount": 1000, "lp_name": f"Alice {RID}"})
    sub_id = r.get("subscription_id")
    check("subscription requested", st == 200 and sub_id, f"{st} {r}")
    st, r = POST(f"/lp/subscriptions/{sub_id}/confirm", {"actor": "e2e"})
    units = r.get("units_issued") or 0
    navpu = r.get("nav_per_unit") or 0
    check("units minted", st == 200 and units > 0, f"units={units} nav/unit={navpu}")
    check("units back the cash (units × nav/unit ≈ $1000)",
          abs(units * navpu - 1000) < 0.5, f"{units} × {navpu} = {round(units * navpu, 2)}")

    section("2) LP appears in the book")
    st, r = GET(f"/lp/{lp}")
    check("LP readable", st == 200 and r.get("units", 0) > 0,
          f"value={r.get('value_usd')} ownership={r.get('ownership_pct')}%")

    section("3) Strategy lifecycle: create → backtest → deploy → allocate")
    st, r = POST("/strategies", {"name": f"E2E Momentum {RID}"})
    sid = r.get("strategy_id")
    check("strategy registered", st == 200 and sid, f"{st} {r.get('state')}")
    prices = [100, 101, 103, 102, 106, 109, 108, 112, 115, 119]
    st, r = POST(f"/strategies/{sid}/backtest/run", {"prices": prices, "strategy": "buy_hold"})
    res = r.get("result", {})
    check("backtest ran", st == 200 and "total_return" in res,
          f"return={res.get('total_return')} sharpe={res.get('sharpe')} maxdd={res.get('max_drawdown')}")
    st, r = POST(f"/strategies/{sid}/state", {"state": "deployed"})
    check("strategy deployed", st == 200 and r.get("state") == "deployed", f"{r.get('state')}")
    st, r = POST(f"/strategies/{sid}/allocation", {"target_pct": 40})
    check("allocation set", st == 200 and abs((r.get("allocation_pct") or 0) - 40) < 0.01,
          f"target={r.get('allocation_pct')}%")

    section("4) Order: propose → approve → settle")
    st, r = POST("/orders/propose", {"symbol": "NVDA", "side": "buy", "qty": 1, "strategy_id": sid, "actor": "e2e"})
    status = r.get("status")
    oid = r.get("order_id")
    if status == "rejected":
        check("order proposed", False, f"rejected by risk: {r.get('breaches')}")
    else:
        check("order proposed", st == 200 and status == "pending_approval" and oid,
              f"preview={r.get('impact_preview')}")
        st, r = POST(f"/orders/{oid}/approve", {"approver": "e2e"})
        check("order approved", st == 200 and r.get("status") in ("filled", "working"),
              f"status={r.get('status')}")
        # Drive settlement (paper fills instantly; Alpaca may take a few polls).
        final = r.get("status")
        for _ in range(5):
            if final == "filled":
                break
            POST("/orders/settle")
            _, o = GET(f"/orders/{oid}")
            types = [e.get("type") for e in o.get("events", [])]
            final = "filled" if "OrderFilled" in types else ("failed" if "OrderFailed" in types else "working")
            if final in ("filled", "failed"):
                break
            time.sleep(1)
        # Report (soft): a real venue outside market hours may stay 'working'.
        print(f"  [INFO] order final status: {final} (paper fills instantly; Alpaca async is OK)")

    section("5) Reads + reconcile")
    st, nav = GET("/nav")
    live = nav.get("live", {})
    check("NAV reads", st == 200 and "total_nav_usd" in live,
          f"NAV=${live.get('total_nav_usd')} nav/unit={live.get('nav_per_unit')}")
    st, strat = GET("/strategies")
    ours = next((s for s in strat.get("strategies", []) if s.get("strategy_id") == sid), None)
    check("our strategy shows deployed + allocation", ours and ours.get("state") == "deployed",
          f"exposure={ours.get('exposure_usd') if ours else None} pnl={ours.get('pnl_usd') if ours else None}")
    st, lps = GET("/lps")
    check("our LP in the book", any(x.get("lp_id") == lp for x in lps.get("lps", [])),
          f"{len(lps.get('lps', []))} LPs")
    st, rec = POST("/reconcile")
    check("reconcile runs", st == 200 and "mismatches" in rec,
          f"{len(rec.get('mismatches', []))} mismatch(es)")

    section("Result")
    if FAILS:
        print(f"❌ {len(FAILS)} check(s) failed: {', '.join(FAILS)}")
        return 1
    print("✅ ALL E2E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
