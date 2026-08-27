"""ADV probe A-3: is the fund's OVERNIGHT (frozen) mark equal to the official close?
Compares each post-close NavStruck mark against that session's daily close bar
from the fund's own feed. Answers: whose side is the 110.12 bps overnight gap on?"""
import json, os, sys, urllib.request, subprocess
sys.path.insert(0, os.getcwd())
q = ("select ts, payload::text from fund_events where type='NavStruck' "
     "and right(left(ts,16),5) >= '20:05' order by ts;")
out = subprocess.run(["docker","exec","krypton-pg","psql","-U","krypton","-d","krypton_fund",
                      "-t","-A","-F","\t","-c",q], capture_output=True, text=True).stdout
bars = {}
def close_on(sym, day):
    if sym not in bars:
        u = f"http://localhost:8090/api/v1/fund/marketdata/bars?symbol={sym}&lookback_days=30"
        d = json.load(urllib.request.urlopen(u, timeout=30))
        bars[sym] = dict(zip(d["dates"], d["closes"]))
    return bars[sym].get(day)
print(f"{'strike (UTC)':<26} {'sym':<5} {'struck mark':>12} {'official close':>15} {'bps':>9}")
rows=[]
for line in out.strip().splitlines():
    if not line.strip(): continue
    ts, pay = line.split("\t", 1)
    p = json.loads(pay); day = ts[:10]
    for r in p.get("positions", []):
        c = close_on(r["symbol"], day)
        if c is None: continue
        bps = (float(r["mark"])/c - 1.0)*1e4
        rows.append((ts[:19], r["symbol"], float(r["mark"]), c, bps))
        print(f"{ts[:19]:<26} {r['symbol']:<5} {float(r['mark']):>12.4f} {c:>15.4f} {bps:>9.2f}")
if rows:
    a=[abs(r[4]) for r in rows]
    print(f"\nn={len(a)}  median |bps| {sorted(a)[len(a)//2]:.2f}  max |bps| {max(a):.2f}  "
          f"(worst: {[r[:2] for r in rows if abs(r[4])==max(a)]})")
