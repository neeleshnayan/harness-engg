"""adv29 scope proof: AST + module-constant diff, cab20bf -> ebb233a."""
import ast, subprocess
WT = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
BASE, TIP = "ebb233a", "5900cbd"
def src(rev, path):
    return subprocess.run(["git","-C",WT,"show",f"{rev}:{path}"], capture_output=True, text=True, encoding="utf-8").stdout
def defs(code):
    t = ast.parse(code); out={}
    for n in ast.walk(t):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)): out[n.name]=ast.dump(n)
        elif isinstance(n,ast.Assign):
            for tg in n.targets:
                if isinstance(tg,ast.Name) and tg.id.isupper(): out["CONST:"+tg.id]=ast.dump(n.value)
        elif isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id.isupper():
            out["CONST:"+n.target.id]=ast.dump(n.value) if n.value else "None"
    return out
for path in ["app/fund/gate.py","app/fund/leanrunner.py","app/fund/autopolicy.py",
             "app/fund/statistics.py","app/fund/walkforward.py","app/fund/exitrule.py",
             "app/fund/risk.py","app/fund/orders.py","app/fund/pipeline.py",
             "app/fund/events.py","app/fund/pgstore.py","app/fund/judgement.py",
             "app/fund/factory.py","app/api/v1/fund.py","app/fund/marketdata.py"]:
    a,b = src(BASE,path), src(TIP,path)
    if a==b: print(f"{path}: BYTE-IDENTICAL"); continue
    da,db = defs(a), defs(b)
    changed = sorted(k for k in set(da)|set(db) if da.get(k)!=db.get(k))
    removed = sorted(set(da)-set(db)); added = sorted(set(db)-set(da))
    print(f"{path}:\n   CHANGED {changed}\n   REMOVED {removed}\n   ADDED   {added}")
