"""P2b: the grid again, with the BIND's split done RIGHT. A cell is a NO-OP when
the mutation changed nothing the envelope saw -- the whole checks payload is
identical to base. Only cells that CHANGED the payload and still APPROVE are
fail-open candidates, and each is then hand-classified."""
import sys, importlib.util, json
sys.path.insert(0, sys.argv[2]); from base import base, run
spec = importlib.util.spec_from_file_location("v5", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class ES:
    def __str__(s): raise RuntimeError("x")
    def __repr__(s): return "<EvilStr>"
class EG(dict):
    def get(s,*a,**k): raise RuntimeError("x")
    def __repr__(s): return "<EvilGet>"
class EL(list):
    def __len__(s): raise RuntimeError("x")
    def __repr__(s): return "<EvilLen>"
class EI:
    def __iter__(s): raise RuntimeError("x")
    def __repr__(s): return "<EvilIter>"
class EF:
    def __float__(s): raise RuntimeError("x")
    def __repr__(s): return "<EvilFloat>"
H = [None, True, False, 0, 1, -1, "", "x", [], {}, (), 0.0, -0.0, 1e308, -1e308,
     float("nan"), float("inf"), float("-inf"), 1e-9, -1e-9, 1e12, 1e13, 1e-300,
     ES(), EG(), EL(), EI(), EF(), b"x", set(), {"a":1}, [1,2], "TRUE","true","None"]
o0,c0,b0 = base(); r0 = run(m,o0,c0,b0)
assert r0["approve"], "PRECOND"
BASE = json.dumps(r0["checks"], default=str)
res = {"REFUSE":0,"APPROVE_changed":0,"APPROVE_noop":0,"RAISE_guarded":0,"RAISE_escaped":0}
fo = []
for where in ("ctx","ord","beat"):
    keys = {"ctx":c0,"ord":o0,"beat":b0}[where]
    for k in list(keys):
        for v in H:
            o,c,b = base(); {"ctx":c,"ord":o,"beat":b}[where][k] = v
            try: r = run(m,o,c,b)
            except BaseException as e: res["RAISE_escaped"]+=1; continue
            ec = [x for x in r["checks"] if x["check"]=="evaluate_completed"]
            if ec and ec[0]["ok"] is not True: res["RAISE_guarded"]+=1; continue
            if not r["approve"]: res["REFUSE"]+=1; continue
            if json.dumps(r["checks"], default=str) == BASE:
                res["APPROVE_noop"]+=1
            else:
                res["APPROVE_changed"]+=1; fo.append((where,k,repr(v)))
print(json.dumps(res, indent=2))
print(f"\nAPPROVING cells that CHANGED the payload ({len(fo)}):")
for w,k,v in fo: print(f"   {w:<5} {k:<28} = {v}")
