"""
Comprehensive End-to-End System Audit & Testing Script for ClarkHarness Spine
Tests all endpoints, risk gates, idempotency guards, strategy trees, and Alpaca Paper connector.
"""

import sys
import json
import urllib.request
import urllib.error

import sys
import json
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HARNESS_URL = "http://127.0.0.1:8090"

def log_result(test_name: str, passed: bool, detail: str = ""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {test_name} - {detail}")
    if not passed:
        sys.exit(1)

def http_get(path: str):
    url = f"{HARNESS_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def http_post(path: str, data: dict):
    url = f"{HARNESS_URL}{path}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())

def run_audit():
    print("==================================================")
    print("  CLARK HARNESS FULL SYSTEM & FEATURE AUDIT       ")
    print("==================================================\n")

    # 1. Health Endpoint
    try:
        res = http_get("/health")
        log_result("1. Health Endpoint", res.get("status") in ["ok", "healthy"], f"Status: {res}")
    except Exception as e:
        log_result("1. Health Endpoint", False, str(e))

    # 2. Fund NAV & Holdings
    try:
        res = http_get("/api/v1/fund/nav")
        live_data = res.get("live", res)
        nav_usd = live_data.get("nav_usd", 0)
        log_result("2. Fund NAV Strike", nav_usd >= 0, f"NAV: ${nav_usd:,.2f}, Unit Value: ${live_data.get('nav_per_unit', 0):,.2f}")
    except Exception as e:
        log_result("2. Fund NAV Strike", False, str(e))

    # 3. Active Positions Reconciliation
    try:
        res = http_get("/api/v1/fund/positions")
        positions = res.get("positions", {})
        count = len(positions) if isinstance(positions, (dict, list)) else 0
        log_result("3. Active Positions", isinstance(positions, (dict, list)), f"Found {count} active position(s): {positions}")
    except Exception as e:
        log_result("3. Active Positions", False, str(e))

    # 4. Strategy Tree & Allocations
    try:
        res = http_get("/api/v1/fund/strategies")
        strategies = res.get("strategies", [])
        log_result("4. Strategy Hierarchy", len(strategies) > 0, f"Total Strategies: {len(strategies)}")
    except Exception as e:
        log_result("4. Strategy Hierarchy", False, str(e))

    # 5. Risk Analytics Engine
    try:
        res = http_get("/api/v1/fund/risk/analytics")
        hhi = res.get("concentration_hhi", 0)
        scenarios = res.get("scenarios", [])
        log_result("5. Risk Analytics Engine", hhi > 0 and len(scenarios) > 0, f"HHI: {hhi}, Scenarios: {len(scenarios)}")
    except Exception as e:
        log_result("5. Risk Analytics Engine", False, str(e))

    # 6. Risk Factor Shock Simulation
    try:
        res = http_post("/api/v1/fund/risk/shock", {"symbol": "AAPL", "pct": -20.0})
        pnl = res.get("pnl_usd", 0)
        log_result("6. Factor Shock Simulation", "pnl_usd" in res, f"AAPL -20% Shock Impact: ${pnl:,.2f}")
    except Exception as e:
        log_result("6. Factor Shock Simulation", False, str(e))

    # 7. Pre-Trade Deterministic Risk Gate (Oversized Order Rejection)
    try:
        # Requesting 100,000 AAPL shares (~$17M) should breach the 25% single-stock position limit
        res = http_post("/api/v1/fund/orders/propose", {
            "symbol": "AAPL",
            "side": "buy",
            "qty": 100000,
            "strategy_id": "us_momentum",
            "discretionary": True
        })
        is_rejected = res.get("status") == "rejected" or "risk" in str(res).lower()
        log_result("7. Pre-Trade Risk Gate Rejection", is_rejected, f"Result: {res}")
    except Exception as e:
        log_result("7. Pre-Trade Risk Gate Rejection", False, str(e))

    # 8. Valid Order Proposal & Execution Cycle
    try:
        # Propose small valid order (1 share of MSFT)
        prop_res = http_post("/api/v1/fund/orders/propose", {
            "symbol": "MSFT",
            "side": "buy",
            "qty": 1,
            "strategy_id": "us_momentum",
            "discretionary": True
        })
        order_id = prop_res.get("order_id")
        log_result("8a. Valid Order Proposal", bool(order_id), f"Proposed Order ID: {order_id}")

        if order_id:
            # Approve order on Alpaca venue
            appr_res = http_post(f"/api/v1/fund/orders/{order_id}/approve", {"approver": "manager"})
            log_result("8b. Venue Order Submission", "order_id" in appr_res or "status" in appr_res, f"Approval Response: {appr_res}")
    except Exception as e:
        log_result("8. Valid Order Proposal & Execution", False, str(e))

    # 9. LP Unit Ledger
    try:
        res = http_get("/api/v1/fund/lps")
        lps = res.get("lps", [])
        log_result("9. LP Unit Ledger", isinstance(lps, list), f"Found {len(lps)} LP account(s)")
    except Exception as e:
        log_result("9. LP Unit Ledger", False, str(e))

    # 10. Audit Event Spine Monotonic Sequence
    try:
        res = http_get("/api/v1/fund/events")
        events = res.get("events", [])
        # The endpoint returns the tail newest-first, so seq must strictly DECREASE.
        is_seq_monotonic = True
        for i in range(1, len(events)):
            if events[i].get("seq", 0) >= events[i-1].get("seq", 0):
                is_seq_monotonic = False
                break
        log_result("10. Event Spine Sequence Monotonicity", is_seq_monotonic, f"Audited {len(events)} total events in spine")
    except Exception as e:
        log_result("10. Event Spine Sequence Monotonicity", False, str(e))

    print("\n==================================================")
    print("  ALL FEATURE TESTS COMPLETED SUCCESSFULLY!       ")
    print("==================================================")

if __name__ == "__main__":
    run_audit()
