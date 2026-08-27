"""ADV probe A-1: the MISS profile of |delta_pct| <= 0.50%.
Uses the LIVE book (GET /fund/nav) and the SHIPPED arithmetic of
Reconciler.drift(): delta = broker_equity - book_nav ; delta_pct = delta/book_nav*100.
A per-name mark error e_s changes book_nav by qty_s * mark_s * e_s (cash unchanged),
so |delta_pct| = |w_s * e_s| where w_s = notional_s / NAV.
Question: how wrong may ONE name's mark be and still read 'met'?"""
import json, urllib.request
B = 0.50  # the proposed bound, % of NAV
nav = json.load(urllib.request.urlopen("http://localhost:8090/api/v1/fund/nav", timeout=20))["live"]
N = nav["total_nav_usd"]
rows = sorted(nav["positions"], key=lambda p: -p["usd_value"])
print(f"live NAV  = {N}   cash = {nav['breakdown']['cash']}   invested = {nav['breakdown']['positions']}")
print(f"{'sym':<5} {'notional':>9} {'wt %NAV':>8} {'max mark err passing 0.50%':>28}  {'in bps':>9}")
for p in rows:
    w = p["usd_value"]/N
    e = B/100.0/w
    print(f"{p['symbol']:<5} {p['usd_value']:>9.2f} {w*100:>7.2f}% {e*100:>27.2f}% {e*1e4:>9.0f}")
# whole-book uniform error
print(f"\nuniform error on EVERY position (invested {nav['breakdown']['positions']/N*100:.1f}% of NAV):"
      f" {B/100.0/(nav['breakdown']['positions']/N)*100:.2f}%")
# netting: two names, opposite signs, aggregate reads ~0
a, b = rows[0], rows[-1]
ea = 0.05   # +5% on the largest
eb = -(a["usd_value"]*ea)/b["usd_value"]
print(f"\nNETTING: {a['symbol']} mark +{ea*100:.1f}% and {b['symbol']} mark {eb*100:.1f}% "
      f"-> delta_usd {a['usd_value']*ea + b['usd_value']*eb:+.6f}, delta_pct "
      f"{(a['usd_value']*ea + b['usd_value']*eb)/N*100:+.6f}%  (both names grossly mis-marked, check reads MET)")
