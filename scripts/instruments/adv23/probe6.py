"""probe 6: run the SHIPPED premia path over every stored enriched result -
measurability, coverage denominator, and what the bar would have said."""
import sys, os, json, ast, hashlib
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

# ---- AST scope proof: which top-level defs changed base -> head in gate.py
import subprocess
base_src = subprocess.run(["git","show","1538e77:app/fund/gate.py"], cwd=HEAD,
                          capture_output=True, text=True).stdout
head_src = open(os.path.join(HEAD,"app","fund","gate.py"), encoding="utf-8").read()
def defs(src):
    t = ast.parse(src); out={}
    for n in t.body:
        if isinstance(n,(ast.FunctionDef, ast.AsyncFunctionDef)): out[n.name]=ast.dump(n)
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name): out["CONST:"+tg.id]=ast.dump(n.value)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out["CONST:"+n.target.id]=ast.dump(n.value) if n.value else ""
    return out
a,b = defs(base_src), defs(head_src)
print("gate.py CHANGED base->head:", sorted(k for k in set(a)&set(b) if a[k]!=b[k]))
print("gate.py ADDED  :", sorted(set(b)-set(a)))
print("gate.py REMOVED:", sorted(set(a)-set(b)))

with psycopg.connect(pgstore.dsn()) as conn, conn.cursor() as cur:
    cur.execute("SELECT job_id, algorithm, result FROM fund_lean_jobs WHERE result IS NOT NULL AND enrich=true")
    jobs = cur.fetchall()
meas=0; unmeas=0; reasons={}
print(f"\n{'job':10s} {'algorithm':32s} {'meas':5s} {'cov':>16s} {'K/yr':>7s} {'verdict':7s}")
for jid, algo, res in jobs:
    if not isinstance(res, dict): continue
    pi = premia_inputs(res)
    res2 = dict(res); res2["premia_inputs"]=pi
    o,f = gh._premia_leg(res2, gh.PREMIA_CRITERIA)
    if pi.get("measurable"):
        meas+=1
        cov=pi["coverage"]
        print(f"{jid[:10]:10s} {algo[:32]:32s} {'YES':5s} "
              f"{cov['common_days']:5d}/{cov['strategy_days']:<5d}={cov['fraction']:.2f} "
              f"{pi['strategy']['obs_per_year']:7.1f} {'PASS' if not f else 'fail':7s}")
    else:
        unmeas+=1
        r=(pi.get("reason") or "")[:70]; reasons[r]=reasons.get(r,0)+1
print(f"\nmeasurable {meas} / unmeasurable {unmeas}")
for r,c in sorted(reasons.items(), key=lambda x:-x[1]): print(f"  {c:3d}  {r}")
