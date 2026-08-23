"""Scope proof: AST-compare the functions + module constants the diff CLAIMS not to touch."""
import ast, subprocess, sys
WT = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d22ch"
BASE, TIP = "16991f3", "3ac7275"
def src(rev, path):
    return subprocess.run(["git","-C",WT,"show",f"{rev}:{path}"],
                          capture_output=True, text=True, encoding="utf-8").stdout
def defs(code):
    t = ast.parse(code); out = {}
    for n in ast.walk(t):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            out[n.name] = ast.dump(n)
        elif isinstance(n,ast.Assign):
            for tg in n.targets:
                if isinstance(tg,ast.Name) and tg.id.isupper():
                    out["CONST:"+tg.id] = ast.dump(n.value)
    return out
for path, watch in [
    ("app/api/v1/fund.py", ["_guard_approval","approve_order","_guard_mark_sanity",
                            "CONST:APPROVAL_ALLOWLIST","CONST:DESK_APPROVAL_ALLOWLIST",
                            "desk_request","approve_desk_request","decline_desk_request",
                            "CONST:REC_STATUSES"]),
    ("app/fund/autopolicy.py", None), ("app/fund/gate.py", None),
    ("app/fund/exitrule.py", None), ("app/fund/risk.py", None),
    ("app/fund/pipeline.py", None), ("app/fund/orders.py", None),
    ("app/fund/events.py", None), ("app/fund/pgstore.py", None),
    ("app/fund/judgement.py", None), ("app/fund/marksanity.py", None),
]:
    a, b = src(BASE,path), src(TIP,path)
    if not a and not b: print(f"{path}: MISSING both"); continue
    if a == b:
        print(f"{path}: BYTE-IDENTICAL base->tip"); continue
    da, db = defs(a), defs(b)
    changed = sorted(k for k in set(da)|set(db) if da.get(k)!=db.get(k))
    print(f"{path}: text differs; AST-changed symbols = {changed}")
    if watch:
        bad = [w for w in watch if w in changed]
        print(f"    protected symbols changed: {bad or 'NONE'}")
