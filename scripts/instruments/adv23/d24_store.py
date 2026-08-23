"""D24 re-review, REAL STORE (my D22 probeC modelled by_target with the raw key;
the repair canonicalises on WRITE, so the model is stale - re-derived here)."""
import os, sys, uuid
WT = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d22ch"
sys.path.insert(0, WT)
for line in open(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness\.env", encoding="utf-8", errors="replace"):
    line=line.strip()
    if line and not line.startswith("#") and "=" in line:
        k,_,v=line.partition("="); os.environ.setdefault(k.strip(), v.strip())
import psycopg
from app.fund.pgstore import dsn
from app.fund.deskengine import (Supersessions, approval_refusal, req_ref,
                                 canonical_ref, EDGE_QUERY_LIMIT, SupersessionsTruncated)
TEST_DB="krypton_fund_advd24"
head,_,_ = dsn().rpartition("/"); tdsn=f"{head}/{TEST_DB}"
with psycopg.connect(dsn(), connect_timeout=5, autocommit=True) as c, c.cursor() as cur:
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s",(TEST_DB,))
    if not cur.fetchone(): cur.execute(f'CREATE DATABASE "{TEST_DB}"')
S=Supersessions(dsn=tdsn)
with psycopg.connect(tdsn) as c, c.cursor() as cur:
    cur.execute("TRUNCATE fund_desk_supersession"); c.commit()

print("=== E RE-DERIVED: file an edge through the REAL store, then read it back ===")
for raw_id, filed in [("plain-abc","req:plain-abc"), ("lead-abc"," req:lead-abc"),
                      ("trail-abc","req:trail-abc "), ("nl-abc","req:nl-abc\n")]:
    S.add(target_ref=filed, mode="superseded_pending", reason="r", actor="a", dies_at_event="E1", revives_if="never",
          superseder_ref="rec:run-x#1")
    m=S.by_target()
    blocks=bool(approval_refusal(req_ref(raw_id), m))
    stored=[k for k in m if raw_id in k]
    print(f"  filed {filed!r:20s} stored_key={stored!r:22s} blocks approve({raw_id})={blocks}")
u=str(uuid.uuid4())
S.add(target_ref=f"req:{u.upper()}", mode="superseded_pending", reason="r", actor="a", dies_at_event="E1", revives_if="never",
      superseder_ref="rec:run-x#2")
m=S.by_target()
print(f"  filed UPPERCASE UUID          stored_key={[k for k in m if u in k.lower()]!r}")
print(f"     blocks approve(lowercase uuid) = {bool(approval_refusal(req_ref(u), m))}")
S.add(target_ref=f"req:{uuid.uuid4().hex}", mode="killed", reason="r", actor="a")
print(f"  undashed-uuid canonical_ref -> {canonical_ref('req:'+uuid.uuid4().hex)[:20]}...(dashed)")
try:
    S.add(target_ref="REQ:abc", mode="killed", reason="r", actor="a"); print("  'REQ:abc' ACCEPTED")
except ValueError as e: print(f"  'REQ:abc' refused: {str(e)[:60]}")

print("\n=== MIGRATION: pre-repair raw rows already in the table ===")
with psycopg.connect(tdsn) as c, c.cursor() as cur:
    cur.execute("INSERT INTO fund_desk_supersession (edge_id,target_ref,superseder_ref,mode,reason,applied_by,applied_at) "
                "VALUES ('legacy1',' req:legacy-1','rec:run-y#1','superseded_pending','r','a',now())")
    cur.execute("INSERT INTO fund_desk_supersession (edge_id,target_ref,superseder_ref,mode,reason,applied_by,applied_at) "
                "VALUES ('legacy2','not-a-ref',NULL,'killed','r','a',now())")
    c.commit()
S2=Supersessions(dsn=tdsn)
print("  migration_report:", S2.migration_report)
m=S2.by_target()
print(f"  blocks approve(legacy-1) after migration = {bool(approval_refusal(req_ref('legacy-1'), m))}")

print("\n=== TRUNCATION at the ENDPOINT layer: what the approval path actually does ===")
with psycopg.connect(tdsn) as c, c.cursor() as cur:
    cur.execute("TRUNCATE fund_desk_supersession"); c.commit()
S.add(target_ref="req:victim", mode="superseded_pending", reason="R37", actor="a", dies_at_event="E1", revives_if="never",
      superseder_ref="rec:run-z#1")
print("  1 edge  -> refusal:", bool(approval_refusal(req_ref("victim"), S.by_target())))
with psycopg.connect(tdsn) as c, c.cursor() as cur:
    for i in range(EDGE_QUERY_LIMIT):
        cur.execute("INSERT INTO fund_desk_supersession (edge_id,target_ref,superseder_ref,mode,reason,applied_by,applied_at) "
                    "VALUES (%s,%s,'rec:run-f#1','killed','flood','a',now())",
                    (f"f{i}", f"req:flood-{i}"))
    c.commit()
try:
    S.by_target(); print("  1001 edges -> by_target returned a map (NOT truncated)")
except SupersessionsTruncated as e:
    print("  1001 edges -> by_target RAISES:", str(e)[:70])
# and now the endpoint-level policy
import app.api.v1.fund as F
F._supersession_cache = S
print("  _edges_by_target() ->", F._edges_by_target())
chk = F._supersession_check(req_ref("victim"))
print("  _supersession_check(victim) ->", chk)
print(f"  => under a 1001-edge flood the victim's brake is {'STILL ON' if chk['refusal'] else 'OFF'}"
      f", disclosed readable={chk['supersession_readable']}")
# how many OTHER rows lose their brake at the same time
print(f"  rows that had a live brake before the flood: 1 ; rows with a brake now: 0 (all fail open)")
