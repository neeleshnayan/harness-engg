"""probe 7: REAL belt geometry. Take stored results that already carry both a
daily_returns pair and a recomputed benchmark_curve, stamp the new
benchmark_series_source the new belt would write, and read the coverage
denominator + what the premia bar would say."""
import sys, os
HEAD = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
sys.path.insert(0, HEAD)
os.chdir(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness")
for line in open(".env", encoding="utf-8", errors="replace"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); os.environ.setdefault(k.strip(), v.strip())
from app.fund import gate as gh, pgstore
from app.fund.leanrunner import premia_inputs
import psycopg
with psycopg.connect(pgstore.dsn()) as conn, conn.cursor() as cur:
    cur.execute("SELECT job_id, algorithm, result FROM fund_lean_jobs WHERE result IS NOT NULL AND enrich=true")
    jobs = cur.fetchall()
n=0
for jid, algo, res in jobs:
    if not isinstance(res, dict): continue
    d = res.get("daily_returns") or {}
    if not d.get("present") or not res.get("benchmark_curve"): continue
    r2 = dict(res); r2["benchmark_series_source"] = res.get("benchmark_source")=="fund bars" and "recomputed_basket" or "engine_single_name"
    pi = premia_inputs(r2); r2["premia_inputs"]=pi
    o,f = gh._premia_leg(r2, gh.PREMIA_CRITERIA)
    n+=1
    if not pi.get("measurable"):
        print(f"{jid[:8]} {algo[:26]:26s} UNMEASURABLE: {(pi.get('reason') or '')[:70]}"); continue
    cov=pi["coverage"]; s=pi["strategy"]; b=pi["benchmark"]
    print(f"{jid[:8]} {algo[:26]:26s} src={pi['benchmark_leg_source'][:9]:9s} "
          f"cov {cov['common_days']}/{cov['strategy_days']}={cov['fraction']:.2f} "
          f"K={s['obs_per_year']:.1f} sharpe {o['sharpe_strategy']:+.3f} vs {o['sharpe_benchmark']:+.3f} "
          f"@4% {o['sharpe_advantage_at_stress']:+.3f} vol {o['strategy_ann_vol_pct']:.1f}/{o['benchmark_ann_vol_pct']:.1f} "
          f"-> {'PASS' if not f else 'fail'}")
print("\nresults with both legs present:", n)
