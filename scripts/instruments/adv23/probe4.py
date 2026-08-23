"""probe 4: ALPHA IDENTITY. Re-judge every stored LEAN job result under BASE
gate v4.3 and HEAD, claim_type unset. Diff passed/failures/checks key sets."""
import sys, os, json, importlib.util
HEAD = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
sys.path.insert(0, HEAD)
os.chdir(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness")
for line in open(".env", encoding="utf-8", errors="replace"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,v=line.split("=",1); os.environ.setdefault(k.strip(), v.strip())
from app.fund import gate as gate_head
D = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\adv23"
spec = importlib.util.spec_from_file_location("gate_base", os.path.join(D,"gate_base.py"))
gate_base = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate_base)
print("base GATE_VERSION", gate_base.GATE_VERSION, "| head", gate_head.GATE_VERSION)
print("CRITERIA identical:", gate_base.CRITERIA == gate_head.CRITERIA,
      "| V1", gate_base.CRITERIA_V1==gate_head.CRITERIA_V1,
      "| V2", gate_base.CRITERIA_V2==gate_head.CRITERIA_V2,
      "| V3", gate_base.CRITERIA_V3==gate_head.CRITERIA_V3)

from app.fund import pgstore
import psycopg
dsn = pgstore.dsn()
with psycopg.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1")
    print("tables:", [r[0] for r in cur.fetchall()])

with psycopg.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='fund_lean_jobs' ORDER BY ordinal_position")
    print("fund_lean_jobs cols:", [r[0] for r in cur.fetchall()])
    cur.execute("SELECT count(*) FROM fund_lean_jobs")
    print("jobs:", cur.fetchone()[0])
    cur.execute("SELECT candidate_id, algorithm, verdict FROM fund_candidates WHERE verdict IS NOT NULL")
    cands = cur.fetchall()
print("candidates with verdicts:", len(cands))
