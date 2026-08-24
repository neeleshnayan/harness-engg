"""R39 Phase 4 — REBUILD THE SLEEVE. Stage 14:30-15:00 UTC 2026-08-24,
ONLY after all six Phase-3 sells are confirmed filled at the broker.

Four separate proposals at UNCHANGED quantities. THE GATE THIS SCRIPT
ENFORCES ITSELF: each order is staged only after its exit rule verifies
LIVE in /exits (superseded false, never triggered) — a position entered
without a live exit rule is the entry-freeze defect being recreated.
Frozen exit dates STAND (TLT/DBC 2026-09-08 — the fund's first real exit
execution, a free control test).

NBBO captured for all four at submit. Each order lands in the Monitor
approval queue for the CEO's click.

NOTE FOR THE RUNNER (chair or co-CTO): if any exit-rule check FAILS, that
symbol is SKIPPED and reported — stage the others, never the uncovered one.
"""
import json
import subprocess
import sys
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1"
NBBO = (r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-"
        r"Krypton-Fund\e585e083-6f7e-471f-b51b-6e9c3b249cbe\scratchpad"
        r"\capture_nbbo.py")

REBUYS = [  # (symbol, qty, strategy_id) — unchanged quantities per the plan
    ("DBC", 8.122157, "sleeve_beta_500"),
    ("TLT", 3.019871, "sleeve_beta_500"),
    ("DBA", 5.314306, "sleeve_premia_carry"),
    ("SPY", 0.128362, "sleeve_premia_equity"),
]


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
        return {"HTTP_FAIL": e.code, "detail": e.read()[:300].decode()}


print("=== precondition: all six sells filled? ===")
rec = get("/fund/venue/reconcile")
print("out_of_sync:", rec.get("symbols_out_of_sync"),
      "| delta_usd:", rec.get("delta_usd"))

print("\n=== exit-rule verification, per symbol ===")
exits = get("/fund/exits")
rules = exits.get("rules") or exits.get("exits") or []
ok = {}
for sym, qty, strat in REBUYS:
    live = [r for r in rules
            if isinstance(r, dict) and r.get("symbol") == sym
            and not r.get("superseded") and not r.get("triggered_at")]
    ok[sym] = len(live)
    print(f"{sym}: {len(live)} live untriggered rule(s) "
          f"{[r.get('kind') for r in live]}"
          + ("" if live else "  << NO LIVE EXIT RULE — WILL SKIP"))

print("\n=== NBBO at submit ===")
subprocess.run([sys.executable, NBBO] + [s for s, _, _ in REBUYS]
               + ["--tag=phase4-rebuys"], check=False)

print("\n=== proposing rebuys (skipping any uncovered symbol) ===")
for sym, qty, strat in REBUYS:
    if not ok.get(sym):
        print(f"{sym}: SKIPPED — no live exit rule; report to the chair")
        continue
    res = post("/fund/orders/propose", {
        "symbol": sym, "side": "buy", "qty": qty,
        "venue": "alpaca", "actor": "cto", "strategy_id": strat,
        "rationale": (f"R39 Phase 4 (PM_R39_PLAN_2026-08-23.md, R39-4 "
                      f"CEO-accepted): re-establish sleeve position {sym} "
                      f"{qty} under {strat} at the broker. Exit rule verified "
                      f"live in /exits at staging; frozen exit dates stand. "
                      f"The sleeve's real inception is today - every exit "
                      f"rule predates its entry."),
    })
    if res.get("HTTP_FAIL"):
        print(f"{sym}: FAILED {res['HTTP_FAIL']} {res.get('detail','')[:150]}")
    else:
        prev = res.get("impact_preview") or {}
        print(f"{sym}: pending_approval  order {res.get('order_id','')[:8]}  "
              f"~${prev.get('notional_usd')}")
print("\nStaged. CEO: four approve clicks on the Monitor. After fills: "
      "Phase 5 acceptance (out_of_sync 0, residual <= $3.00 by 15:30Z; "
      "unsourceable > $10 = STOP, fresh-account trigger 2).")
