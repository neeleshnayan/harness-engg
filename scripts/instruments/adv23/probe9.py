"""probe 9: CLAIM SHOPPING on the fund's own stored population -
for each stored enriched result, does it clear must_beat_benchmark (alpha)
and does it clear the premia leg?"""
import sys, os
HEAD = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
sys.path.insert(0, HEAD); os.chdir(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness")
for line in open(".env", encoding="utf-8", errors="replace"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); os.environ.setdefault(k.strip(), v.strip())
from app.fund import gate as gh, pgstore
from app.fund.leanrunner import premia_inputs
import psycopg
with psycopg.connect(pgstore.dsn()) as conn, conn.cursor() as cur:
    cur.execute("SELECT job_id, algorithm, result FROM fund_lean_jobs WHERE result IS NOT NULL AND enrich=true")
    jobs=cur.fetchall()
ab=pb=both=0; n=0
for jid,algo,res in jobs:
    if not isinstance(res,dict): continue
    d=res.get("daily_returns") or {}
    if not d.get("present") or not res.get("benchmark_curve"): continue
    n+=1
    strat=res.get("total_return_pct"); bench=res.get("benchmark_return_pct")
    alpha_ok = strat is not None and bench is not None and float(strat)>float(bench)
    r2=dict(res); r2["benchmark_series_source"]="recomputed_basket"
    r2["premia_inputs"]=premia_inputs(r2)
    o,f=gh._premia_leg(r2, gh.PREMIA_CRITERIA)
    premia_ok = not f
    ab+=alpha_ok; pb+=premia_ok; both+= (alpha_ok and premia_ok)
    print(f"{jid[:8]} {algo[:26]:26s} ret {float(strat or 0):8.2f} vs bench {float(bench or 0):8.2f}"
          f"  alpha_beat={'Y' if alpha_ok else 'n'}  premia={'PASS' if premia_ok else 'fail'}")
print(f"\nn={n}   clears must_beat_benchmark: {ab}   clears the premia leg: {pb}   both: {both}")
