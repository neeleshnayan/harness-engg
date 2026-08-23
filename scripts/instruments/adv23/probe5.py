"""probe 5: alpha byte-identity over EVERY enriched stored job result (n=650 pool)."""
import sys, os, json, importlib.util
HEAD = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
sys.path.insert(0, HEAD)
os.chdir(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness")
for line in open(".env", encoding="utf-8", errors="replace"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); os.environ.setdefault(k.strip(), v.strip())
from app.fund import gate as gh, pgstore
import psycopg
D = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("gate_base", os.path.join(D,"gate_base.py"))
gb = importlib.util.module_from_spec(spec); spec.loader.exec_module(gb)

with psycopg.connect(pgstore.dsn()) as conn, conn.cursor() as cur:
    cur.execute("SELECT job_id, result FROM fund_lean_jobs WHERE result IS NOT NULL AND enrich=true")
    jobs = cur.fetchall()
print("enriched jobs with results:", len(jobs))
diff_pass=diff_fail=0; keydiffs={}; n=0; crash=0
for jid, res in jobs:
    if not isinstance(res, dict): continue
    n+=1
    try:
        a = gb.evaluate(res); b = gh.evaluate(res)
    except Exception as e:
        crash+=1; print("CRASH", jid, type(e).__name__, e); continue
    if a["passed"]!=b["passed"]: diff_pass+=1; print("PASS DIFF", jid, a["passed"], b["passed"])
    if a["failures"]!=b["failures"]:
        diff_fail+=1
        print("FAILURES DIFF", jid)
        for x in set(map(str,b["failures"]))-set(map(str,a["failures"])): print("   +", x[:160])
        for x in set(map(str,a["failures"]))-set(map(str,b["failures"])): print("   -", x[:160])
    if a["gate_version"]!=b["gate_version"]: print("VERSION DIFF", jid)
    ka, kb = set(a["checks"]), set(b["checks"])
    if ka!=kb: keydiffs[tuple(sorted(kb-ka))] = keydiffs.get(tuple(sorted(kb-ka)),0)+1
    # value diff on shared keys
    for k in ka & kb:
        if json.dumps(a["checks"][k], sort_keys=True, default=str) != json.dumps(b["checks"][k], sort_keys=True, default=str):
            print("CHECK VALUE DIFF", jid, k)
print(f"\njudged {n}, crashes {crash}, passed-differs {diff_pass}, failures-differ {diff_fail}")
print("new checks keys added by HEAD:", keydiffs)
