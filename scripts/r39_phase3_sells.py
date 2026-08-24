"""R39 Phase 3 — CLOSE THE SIX ORPHANS. Staged 13:45-14:15 UTC 2026-08-24.

Six separate proposals, GLD FIRST (the 9.5%-of-NAV position leads). Each
lands in the Monitor approval queue for the CEO's individual click. NBBO
captured per symbol at submit (validator's requirement). Quantities are the
sync-adopted book quantities — INTC is the post-probe remainder 1.558762.
"""
import json
import subprocess
import sys
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1"
NBBO = (r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-"
        r"Krypton-Fund\e585e083-6f7e-471f-b51b-6e9c3b249cbe\scratchpad"
        r"\capture_nbbo.py")

SELLS = [  # (symbol, qty) — GLD first, then descending orphan value
    ("GLD", 0.424471),
    ("XLE", 2.749912),
    ("SOFI", 9.18819),
    ("MSFT", 0.340051),
    ("NVDA", 0.749886),
    ("INTC", 1.558762),
]


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"HTTP_FAIL": e.code, "detail": e.read()[:300].decode()}


print("=== NBBO at submit, all six ===")
subprocess.run([sys.executable, NBBO] + [s for s, _ in SELLS]
               + ["--tag=phase3-sells"], check=False)

print("\n=== proposing six sells, GLD first ===")
for sym, qty in SELLS:
    res = post("/fund/orders/propose", {
        "symbol": sym, "side": "sell", "qty": qty,
        "venue": "alpaca", "actor": "cto", "discretionary": True,
        "rationale": (f"R39 Phase 3 (PM_R39_PLAN_2026-08-23.md, R38/R39-3 "
                      f"CEO-accepted; probe passed 13:36Z, fill verified at "
                      f"the broker): close legacy orphan {sym} {qty}. Six "
                      f"separate clicks; GLD leads. Proceeds fund Phase 4 "
                      f"sleeve rebuild."),
    })
    if res.get("HTTP_FAIL"):
        print(f"{sym}: FAILED {res['HTTP_FAIL']} {res.get('detail','')[:150]}")
    else:
        prev = res.get("impact_preview") or {}
        print(f"{sym}: pending_approval  order {res.get('order_id','')[:8]}  "
              f"~${prev.get('notional_usd')}")
print("\nAll staged. CEO: six approve clicks on the Monitor screen, GLD first.")
