"""D24 SUPPLEMENT to the adversary's probeA — the END of the story the
unchanged probe can no longer print.

probeA now stops at a traceback, because `by_target()` raises past its limit
instead of returning a short map. That IS the repair, but it leaves the
downstream question unanswered: what does the approval path do while the
store is flooded? This runs the same flood and then asks the real endpoint.

Expected: the brake does not silently disappear — the approval is taken under
the DISCLOSED fail-open (`supersession_readable: false` on the response and on
the event), not under a map that quietly lost the edge.
"""
import os, sys, uuid, time

WT = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d22ch"
sys.path.insert(0, WT)
sys.path.insert(0, WT + r"\scripts")
for line in open(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness\.env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())
os.environ.setdefault("FUND_MODE", "test")
os.environ.setdefault("FUND_MODE_FILE", WT + r"\tests\.fund_mode.absent")

import psycopg
from app.fund.pgstore import dsn
from app.fund.deskengine import (Supersessions, SupersessionsTruncated,
                                 approval_refusal, req_ref, EDGE_QUERY_LIMIT)

TEST_DB = "krypton_fund_advd22"
head, _, _ = dsn().rpartition("/")
tdsn = f"{head}/{TEST_DB}"
with psycopg.connect(dsn(), connect_timeout=5, autocommit=True) as c:
    with c.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TEST_DB,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{TEST_DB}"')
S = Supersessions(dsn=tdsn)
with psycopg.connect(tdsn) as c:
    with c.cursor() as cur:
        cur.execute("TRUNCATE fund_desk_supersession")
    c.commit()

VICTIM = "r37-real-request-id"
S.add(target_ref=req_ref(VICTIM), superseder_ref="rec:run-pm-0908#1",
      mode="superseded_pending", reason="R37's premise dies at R39 step 4",
      actor="cto", dies_at_event="R39 step 4 (Monday probe)",
      revives_if="the probe stops before step 4")
print("BEFORE flood, refusal:", bool(approval_refusal(req_ref(VICTIM), S.by_target())))

t0 = time.time()
with psycopg.connect(tdsn) as c:
    with c.cursor() as cur:
        cur.executemany(
            "INSERT INTO fund_desk_supersession "
            "(edge_id,target_ref,superseder_ref,mode,reason,applied_by) "
            "VALUES (%s,%s,%s,'killed','noise','anyone')",
            [(str(uuid.uuid4()), f"req:noise-{i}", None)
             for i in range(EDGE_QUERY_LIMIT)])
    c.commit()
print(f"flooded {EDGE_QUERY_LIMIT} edges in {time.time()-t0:.1f}s")

try:
    S.by_target()
    print("by_target() -> RETURNED A MAP (the D22 defect: a silent cap)")
except SupersessionsTruncated as e:
    print("by_target() -> RAISED SupersessionsTruncated (repair 2)")
rows, truncated = S.page()
print(f"page() (display path) -> {len(rows)} rows, truncated={truncated}")

# ---- the endpoint, with the flooded store wired in -------------------------
import _fake_firestore; _fake_firestore.install()
import app.api.v1.fund as F


class Rec:
    def __init__(self): self.events = []
    def append(self, e):
        self.events.append((getattr(e.type, "value", e.type), e.payload))
        return e


F._store = Rec()
F._supersessions = lambda: S
print("_edges_by_target() under flood ->", F._edges_by_target())
out = F.desk_approve(VICTIM, F.DeskApprove(actor="ceo", confirm=VICTIM[:8]))
print("desk_approve ->", {k: out[k] for k in ("actor", "supersession_readable")})
print("event payload supersession_readable:",
      F._store.events[0][1].get("supersession_readable"))
print("VERDICT: the brake is DISCLOSED-unreadable under flood, "
      "never silently absent" if out["supersession_readable"] is False
      else "VERDICT: UNEXPECTED")
