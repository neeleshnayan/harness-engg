"""D24 SUPPLEMENT to the adversary's probeC, section E.

probeC's E section builds the stored map BY HAND (`m = {raw: {...}}`) and so
measures a model of the store, not the store. That model was exactly right
before the repair and is exactly wrong after it, which is why probeC's E rows
are unchanged: canonicalisation happens inside `add()`, which the probe never
calls. This calls it.

Left column: what the caller filed. Right: what the table holds, and whether
the reader's own lookup finds it.
"""
import os, sys

WT = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d22ch"
sys.path.insert(0, WT)
for line in open(r"C:\Users\user\Documents\Krypton Fund\ClarkHarness\.env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

import psycopg
from app.fund.pgstore import dsn
from app.fund.deskengine import Supersessions, approval_refusal, req_ref, rec_ref

TEST_DB = "krypton_fund_advd22"
head, _, _ = dsn().rpartition("/")
tdsn = f"{head}/{TEST_DB}"
S = Supersessions(dsn=tdsn)

UID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
cases = [f"req:{UID}", f" req:{UID}", f"req:{UID} ", f"req:{UID}\n",
         f"REQ:{UID}", f"req:{UID.upper()}", " rec:Run-X#007 "]
print(f"{'filed':46s} {'accepted':9s} {'stored':46s} found")
for raw in cases:
    with psycopg.connect(tdsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_desk_supersession")
        c.commit()
    try:
        S.add(target_ref=raw, superseder_ref="rec:run-y#1", mode="superseded",
              reason="R37's premise died", actor="cto")
        accepted = True
    except ValueError:
        accepted = False
    stored = (S.edges()[0]["target_ref"] if accepted else "-")
    if accepted and stored.startswith("rec:"):
        found = bool(approval_refusal(rec_ref("Run-X", 7), S.by_target()))
    else:
        found = bool(approval_refusal(req_ref(UID), S.by_target())) if accepted else False
    print(f"{raw!r:46s} {str(accepted):9s} {stored!r:46s} {found}")
print()
print("`found` asks the question the READER asks: req_ref(<the real id>) / "
      "rec_ref(<run>, <n>). Every accepted spelling must answer True, or the "
      "edge is visible on the page and inert in the control.")
