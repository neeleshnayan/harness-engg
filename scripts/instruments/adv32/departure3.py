"""adv32: REACHABILITY of the departure's floor. The greedy 32% shape is
phase-locked and adversarial. What does a RANDOM correlated outage (both legs
lose the same i.i.d. sessions) actually reach before the gap test refuses?"""
import sys, random
sys.path.insert(0, r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\adv29")
from base import *
from app.fund.leanrunner import premia_inputs
from app.fund import gate
w = window("2021-01-01","2026-12-31")
spy = mix_curve(w,{"SPY":1.0}); bar = ew_curve(w,["SPY","QQQ","IWM"])
def fetch_only(days):
    S=set(days)
    def f(sym,a,b):
        c=SY[sym]; ds=[x for x in sorted(c) if a<=x<=b and x in S]
        return Bars(ds,[c[x] for x in ds]) if ds else None
    return f
print(f"{'drop q':>7s} {'trials':>6s} {'vouched':>8s} {'min TRUE cov when vouched':>26s} {'cov_majority true':>18s}")
for q in (0.05,0.10,0.15,0.20,0.30,0.40,0.50,0.60):
    v=0; mn=None; maj=0; T=40
    for t in range(T):
        rng=random.Random(1000*t+int(q*100))
        kept=[d for d in w if rng.random()>q] or [w[0]]
        if kept[0]!=w[0]: kept=[w[0]]+kept
        if kept[-1]!=w[-1]: kept=kept+[w[-1]]
        res = make_result(w, spy, bar)
        res["benchmark_dates"]=kept; res["benchmark_curve"]=[bar[w.index(d)] for d in kept]
        res["premia_inputs"]=premia_inputs(res, rf_bars=fetch_only(kept))
        o,f = gate._premia_leg(res, gate.PREMIA_CRITERIA)
        sp=res["premia_inputs"]["coverage"]["session_span"]
        if sp["vouched"]:
            v+=1; c=len(kept)/len(w)
            mn = c if mn is None else min(mn,c)
            if o.get("coverage_majority"): maj+=1
    print(f"{q:7.2f} {T:6d} {v:8d} {('n/a' if mn is None else f'{mn*100:.1f}%'):>26s} {maj:18d}")
