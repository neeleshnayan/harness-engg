"""R39 Phase 2 — THE $4.50 PROBE. Staged at ~13:35 UTC 2026-08-24, after open.

Proposes SELL 0.05 INTC on the alpaca venue through the ordinary propose
path. The routing fix has NEVER carried a live fill; this is the go/no-go
for everything after it. The CEO clicks approve in the Studio; acceptance
is the BROKER QUANTITY moving to 1.508762 — if the fill never reaches the
broker, STOP EVERYTHING (fresh-account trigger 1 arms).

Captures the INTC NBBO at submit time first (validator's requirement).
"""
import json
import subprocess
import sys
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1"
NBBO = (r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-"
        r"Krypton-Fund\e585e083-6f7e-471f-b51b-6e9c3b249cbe\scratchpad"
        r"\capture_nbbo.py")


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"HTTP_FAIL": e.code, "detail": e.read()[:500].decode()}


print("=== NBBO at submit ===")
subprocess.run([sys.executable, NBBO, "INTC", "--tag=phase2-probe"], check=False)

print("\n=== proposing the probe ===")
res = post("/fund/orders/propose", {
    "symbol": "INTC", "side": "sell", "qty": 0.05,
    "venue": "alpaca", "actor": "cto", "discretionary": True,
    "rationale": ("R39 Phase 2 probe (PM_R39_PLAN_2026-08-23.md, CEO-accepted, "
                  "CEO 2026-08-24: 'right, execute it'): $4.50 SELL to prove the "
                  "repaired routing reaches the broker before six orphan sells "
                  "ride on it. Acceptance: broker INTC 1.558762 -> 1.508762. "
                  "If it does not arrive: STOP ALL, fresh-account trigger 1."),
})
print(json.dumps(res, indent=2)[:900])
if not res.get("HTTP_FAIL"):
    print("\nProbe proposed. CEO: approve it in the Studio (pending orders). "
          "After the fill, the chair verifies the broker quantity before "
          "Phase 3 stages.")
