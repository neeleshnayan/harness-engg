"""probe 8: ZERO-SKILL FALSE-PASS RATE of the shipped premia leg.
Arm A: random Dirichlet weights, monthly rebalance, RISKY universe only.
Arm B: same but the universe includes T-bills (BIL) - a de-risking rule's shape.
Bar in both arms = equal-weight buy&hold of the SAME universe (what _add_benchmark builds)."""
import sys, os, json, random, math
HEAD = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
sys.path.insert(0, HEAD)
D = os.path.dirname(os.path.abspath(__file__))
from app.fund.leanrunner import premia_inputs
from app.fund import gate
def load(s):
    o=json.load(open(os.path.join(D,f"{s}.json"))); return dict(zip(o["dates"],o["closes"]))
NAMES=["SPY","QQQ","IWM","TLT","XLK","XLE","XLF","XLV","XLU","XLP","BIL"]
SY={s:load(s) for s in NAMES}
ALLD=sorted(set.intersection(*[set(v) for v in SY.values()]))
def window(a,b): return [d for d in ALLD if a<=d<=b]
def ew(dates,syms,e0=100000.0):
    return [e0*sum(SY[s][d]/SY[s][dates[0]] for s in syms)/len(syms) for d in dates]
def rebal(dates,syms,wfun,every=21,e0=100000.0):
    lvl=e0; out=[lvl]; w=wfun()
    for i in range(1,len(dates)):
        if i%every==0: w=wfun()
        r=sum(w[j]*(SY[s][dates[i]]/SY[s][dates[i-1]]-1.0) for j,s in enumerate(syms))
        lvl*=(1+r); out.append(lvl)
    return out
def mk(dates,sc,bc):
    sr=[sc[i]/sc[i-1]-1.0 for i in range(1,len(dates))]
    return {"daily_returns":{"present":True,"dates":dates[1:],"strategy":sr,
            "benchmark":[], "benchmark_present":False,"n":len(sr)},
            "benchmark_curve":bc,"benchmark_dates":dates,
            "benchmark_series_source":"recomputed_basket"}
def passes(dates,sc,bc):
    r=mk(dates,sc,bc); r["premia_inputs"]=premia_inputs(r)
    o,f=gate._premia_leg(r,gate.PREMIA_CRITERIA); return (not f), o
WINS={"belt 700d 2024-09..2026-08":window("2024-09-21","2026-12-31"),
      "belt 900d 2024-03..2026-08":window("2024-03-05","2026-12-31"),
      "full 2021-02..2026-08":window("2021-01-01","2026-12-31")}
RISKY=["SPY","QQQ","IWM","TLT","XLK","XLE","XLF","XLV"]
WITHCASH=RISKY+["BIL"]
N=1000
for wn,w in WINS.items():
    for arm,syms in (("A risky-only",RISKY),("B universe includes BIL",WITHCASH)):
        bar=ew(w,syms); rnd=random.Random(20260823)
        def wfun(k=len(syms)):
            x=[rnd.gammavariate(1.0,1.0) for _ in range(k)]; t=sum(x); return [v/t for v in x]
        hits=0
        for _ in range(N):
            ok,_o=passes(w, rebal(w,syms,wfun), bar); hits+=ok
        se=math.sqrt(hits/N*(1-hits/N)/N)*100
        print(f"{wn:30s} {arm:24s} zero-skill FALSE PASS {hits/N*100:5.1f}% +/- {se:.1f}pp  (n={N})")
