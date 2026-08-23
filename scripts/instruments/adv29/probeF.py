"""adv29 probe F: characterise the coverage test HONESTLY -- when does it fire?
Three truncation shapes on the SAME run, v5r1 denominator beside v5r2's."""
import sys, os, subprocess, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import *
WT=r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
def load(rev,path,name):
    s=subprocess.run(["git","-C",WT,"show",f"{rev}:{path}"],capture_output=True,text=True,encoding="utf-8").stdout
    p=os.path.join(os.path.dirname(os.path.abspath(__file__)),name+".py"); open(p,"w",encoding="utf-8").write(s)
    sp=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
g1=load("cab20bf","app/fund/gate.py","gF1"); l1=load("cab20bf","app/fund/leanrunner.py","lF1")

w = window("2021-01-01","2026-12-31")
spy = mix_curve(w,{"SPY":1.0}); full_bar = ew_curve(w,["SPY","QQQ","IWM"])
def fetch_to(last):
    def f(sym,a,b):
        c=SY[sym]; ds=[d for d in sorted(c) if a<=d<=b and (last is None or d<=last)]
        return Bars(ds,[c[d] for d in ds]) if ds else None
    return f
print(f"{'shape':46s} {'bar cov':>8s} {'v5r2 common/denom':>19s} {'v5r2':>8s} {'v5r1':>8s}")
for label, bar_cut, rf_cut in [
    ("bar FULL, rf FULL",                    None,        None),
    ("bar truncated 50%, rf FULL",           "2023-12-31",None),
    ("bar truncated 30%, rf FULL",           "2022-08-31",None),
    ("bar truncated 15%, rf FULL",           "2021-12-31",None),
    ("bar FULL, rf truncated 30%",           None,        "2022-08-31"),
    ("bar AND rf truncated 30% (same day)",  "2022-08-31","2022-08-31"),
    ("bar AND rf truncated 15% (same day)",  "2021-12-31","2021-12-31"),
]:
    bd = [d for d in w if bar_cut is None or d<=bar_cut]
    res = make_result(w, spy, full_bar)
    res["benchmark_dates"]=bd; res["benchmark_curve"]=full_bar[:len(bd)]
    res["premia_inputs"]=premia_inputs(res, rf_bars=fetch_to(rf_cut))
    o,f = gate._premia_leg(res, gate.PREMIA_CRITERIA)
    r1 = make_result(w, spy, full_bar); r1["benchmark_dates"]=bd; r1["benchmark_curve"]=full_bar[:len(bd)]
    r1["premia_inputs"]=l1.premia_inputs(r1)
    o1,f1 = g1._premia_leg(r1, g1.PREMIA_CRITERIA)
    covflag = lambda o: ("cov OK" if o.get("coverage_majority") else "cov FAIL")
    print(f"{label:46s} {len(bd)/len(w)*100:7.1f}% "
          f"{str(o.get('coverage',{}).get('common_days'))+'/'+str(o.get('coverage_denominator')):>19s} "
          f"{covflag(o):>8s} {covflag(o1):>8s}")
