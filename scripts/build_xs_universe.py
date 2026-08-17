"""Pick the basket by RULE, not by eye.

I can see how these names performed. Hand-picking eight of them would be
look-ahead bias committed by the analyst rather than the code, and it would not
show up in any holdout. So the universe is defined by a stated, reproducible
rule and whatever it returns is what gets tested.

Rule: the N highest-ADV operating companies inside the capacity band
$2M-$25M ADV, excluding funds, trusts and blank-cheque shells by SIC code,
requiring enough daily history for the longest lookback under test.
"""
import json
import os

from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("FUND_STORE", "postgres")

import requests
from app.fund.universe import Universe
from app.fund.edgar import ticker_map, _throttled_get

B = "http://127.0.0.1:8090/api/v1/fund"
WANT = 20
MIN_BARS = 400

#: SIC ranges that are not operating businesses. 6722/6726 are investment
#: offices and closed-end funds; 6770 is blank cheques. A momentum rule across
#: these would be ranking wrappers around other people's portfolios.
EXCLUDE_SIC = {"6722", "6726", "6770", "6799", "6221"}

u = Universe()
KW = dict(turnover_pct=5.0, participation=0.01,
          min_capacity=400_000, max_capacity=5_000_000)
band = u.hunting_ground(limit=2000, **KW)["names"]
total = u.hunting_ground_count(**KW)
tmap = ticker_map()

print(f"band: {total} names in $2M-$25M ADV; page of {len(band)}")

picked, rejected = [], {"not_sec": 0, "fund_sic": 0, "thin_history": 0, "no_sic": 0}
for n in band:
    if len(picked) >= WANT:
        break
    sym = n["symbol"]
    ent = tmap.get(sym)
    if not ent:
        rejected["not_sec"] += 1
        continue
    cik = str(ent["cik_str"] if "cik_str" in ent else ent.get("cik", "")).zfill(10)
    try:
        sub = json.loads(_throttled_get(
            f"https://data.sec.gov/submissions/CIK{cik}.json"))
    except Exception as e:  # noqa: BLE001
        print(f"  {sym}: submissions unavailable ({e}) — skipped, not assumed clean")
        rejected["no_sic"] += 1
        continue
    sic = str(sub.get("sic") or "")
    if not sic:
        rejected["no_sic"] += 1
        continue
    if sic in EXCLUDE_SIC:
        rejected["fund_sic"] += 1
        continue
    r = requests.get(f"{B}/marketdata/bars",
                     params={"symbol": sym, "lookback_days": 900, "format": "csv"},
                     timeout=90)
    bars = len([l for l in r.text.strip().splitlines() if l.strip()])
    if bars < MIN_BARS:
        rejected["thin_history"] += 1
        continue
    picked.append({"symbol": sym, "adv_usd": round(n["adv_usd"]),
                   "sic": sic, "industry": sub.get("sicDescription", ""),
                   "name": sub.get("name", ""), "bars": bars,
                   "big_fund_days": n["big_fund_days_to_build"]})
    print(f"  {len(picked):2d}. {sym:6s} ${n['adv_usd']:>11,.0f}  {bars} bars  "
          f"{sub.get('sicDescription','')[:38]}")

print("\nrejected:", rejected)
out = {"rule": (f"{WANT} highest-ADV operating companies in the $2M-$25M ADV "
                f"capacity band, SIC-filtered, >={MIN_BARS} daily bars"),
       "band_total": total, "picked": picked}
p = "xs_universe.json"
with open(p, "w") as f:
    json.dump(out, f, indent=1)
print("\nUNIVERSE =", [x["symbol"] for x in picked])
