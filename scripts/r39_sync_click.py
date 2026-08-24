"""R39 Phase 1 — THE SYNC CLICK. Run by the CEO, once, pre-open 2026-08-24.

Reads the live sync plan and applies THAT plan in the same sitting (the
run_id echo is taken from the plan this script just fetched, which is what
the approval guard requires). Actor is 'neelesh' — the CEO's own identity;
running this script IS the sync click.

It then verifies the four acceptance facts from PM_R39_PLAN_2026-08-23.md:
reconciliation_usd steps ~+126, pnl_ex_reconciliation_usd UNCHANGED at
-114.26 (THE TEST), symbols_out_of_sync 0, and prints the NAV step.
Expected and predicted-so-nobody-discovers: a TEMPORARY gross ~57.9% /
discretionary ~49.6% breach that Phase 4 cures.
"""
import json
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"HTTP_FAIL": e.code, "detail": e.read()[:500].decode()}


print("=== R39 PHASE 1: reading the sync plan ===")
plan = get("/fund/venue/sync/plan")
rid = plan["run_id"]
print(f"plan run_id: {rid}")
print(f"nav (projection block): {plan.get('nav')}")
print(f"cash: {plan.get('cash')}")
print(f"symbols_moving: {plan.get('symbols_moving')}")
unmanaged = [x.get("symbol") if isinstance(x, dict) else x
             for x in (plan.get("unmanaged_after") or [])]
print(f"unmanaged_after (should be the six orphans): {unmanaged}")

print("\n=== applying THAT plan (actor: neelesh — this is the click) ===")
res = post("/fund/venue/sync/apply", {
    "run_id": rid,
    "approver": "neelesh",
    "confirm": rid[:8],
    "reason": ("R39 Phase 1 (PM_R39_PLAN_2026-08-23.md, R38/R39-1 CEO-accepted): "
               "align the book to the venue before closing the six legacy "
               "orphans and rebuilding the sleeve - SYNC then SELL then REBUY "
               "is the only sequence that never fabricates a fill."),
})
if res.get("HTTP_FAIL"):
    print("REFUSED:", res)
    raise SystemExit(1)
print("applied:", res.get("applied"), "| run_id:", res.get("run_id"))

print("\n=== acceptance checks ===")
nav = get("/fund/nav")
print(f"NAV now: {nav.get('nav') or nav.get('nav_usd')}")
pnl_keys = {}
for k in ("reconciliation_usd", "pnl_ex_reconciliation_usd"):
    for src in (nav, nav.get("pnl") or {}):
        if isinstance(src, dict) and k in src:
            pnl_keys[k] = src[k]
print(f"reconciliation_usd (expect ~+121..126): {pnl_keys.get('reconciliation_usd')}")
print(f"pnl_ex_reconciliation_usd (MUST stay -114.26): {pnl_keys.get('pnl_ex_reconciliation_usd')}")
rec = get("/fund/venue/reconcile")
print(f"symbols_out_of_sync (MUST be 0): {rec.get('symbols_out_of_sync')}")
print(f"reconcile delta_usd: {rec.get('delta_usd')}")
print("\nPhase 1 done. Expected temporary breaches until Phase 4: gross ~57.9%, "
      "discretionary ~49.6%. Next: the $4.50 INTC probe at 13:35 UTC.")
