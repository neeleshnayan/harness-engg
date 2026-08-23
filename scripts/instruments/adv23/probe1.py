"""ADVERSARY probe 1 (D23 premia gate): does the shipped premia bar admit
zero-skill / pure-cash constructions? Uses the SHIPPED code, no reimplementation."""
import json, os, sys, math
HEAD = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
sys.path.insert(0, HEAD)
D = os.path.dirname(os.path.abspath(__file__))
from app.fund.leanrunner import premia_inputs
from app.fund import gate

def load(s):
    o = json.load(open(os.path.join(D, f"{s}.json")))
    return dict(zip(o["dates"], o["closes"]))

SY = {s: load(s) for s in ["SPY","QQQ","IWM","BIL","TLT","SHV"]}
ALLD = sorted(set.intersection(*[set(v) for v in SY.values()]))

def window(start, end):
    return [d for d in ALLD if start <= d <= end]

def rets(dates, sym):
    c = SY[sym]
    return [c[dates[i]]/c[dates[i-1]] - 1.0 for i in range(1, len(dates))]

def annret(dates, sym):
    c = SY[sym]
    yrs = (len(dates)-1)/252.0
    return ((c[dates[-1]]/c[dates[0]]) ** (1/yrs) - 1)*100

def ew_curve(dates, syms, start_equity=100000.0):
    out = []
    for d in dates:
        out.append(start_equity * sum(SY[s][d]/SY[s][dates[0]] for s in syms)/len(syms))
    return out

def mix_curve(dates, weights, start_equity=100000.0):
    """daily-rebalanced mix; weights: {sym: w}"""
    lvl = start_equity; out=[lvl]
    for i in range(1, len(dates)):
        r = sum(w*(SY[s][dates[i]]/SY[s][dates[i-1]]-1.0) for s,w in weights.items())
        lvl *= (1+r); out.append(lvl)
    return out

def make_result(dates, strat_curve, bench_curve):
    sr = [strat_curve[i]/strat_curve[i-1]-1.0 for i in range(1,len(dates))]
    return {
        "daily_returns": {"present": True, "dates": dates[1:], "strategy": sr,
                          "benchmark": [], "benchmark_present": False,
                          "n": len(sr)},
        "benchmark_curve": bench_curve, "benchmark_dates": dates,
        "benchmark_series_source": "recomputed_basket",
        "benchmark_return_pct": (bench_curve[-1]/bench_curve[0]-1)*100,
        "total_return_pct": (strat_curve[-1]/strat_curve[0]-1)*100,
    }

def judge(name, dates, strat_curve, bench_curve):
    res = make_result(dates, strat_curve, bench_curve)
    res["premia_inputs"] = premia_inputs(res)
    out, fails = gate._premia_leg(res, gate.PREMIA_CRITERIA)
    print(f"\n--- {name}  [{dates[0]} .. {dates[-1]}, n={len(dates)}]")
    if not out.get("measurable"):
        print("   UNMEASURABLE:", out.get("reason")); return False
    print(f"   sharpe strat {out['sharpe_strategy']:.4f} vs bench {out['sharpe_benchmark']:.4f}"
          f"  adv {out['sharpe_advantage']:+.4f}")
    print(f"   at rf=4%:     {out['sharpe_strategy_at_stress']:.4f} vs {out['sharpe_benchmark_at_stress']:.4f}"
          f"  adv {out['sharpe_advantage_at_stress']:+.4f}")
    print(f"   vol {out['strategy_ann_vol_pct']:.2f}% vs {out['benchmark_ann_vol_pct']:.2f}%"
          f" | dd {out['strategy_max_drawdown_pct']:.2f}% vs {out['benchmark_max_drawdown_pct']:.2f}%"
          f" | ret {out['strategy_total_return_pct']:.2f}% vs {out['benchmark_total_return_pct']:.2f}%")
    print(f"   coverage {out['coverage']['common_days']}/{out['coverage']['strategy_days']}"
          f"  rf_breakeven {out.get('rf_breakeven_pct')}")
    print("   PREMIA LEG:", "PASS (zero failures)" if not fails else "FAIL")
    for f in fails: print("     -", f[:200])
    return not fails

WINDOWS = {
  "full 2021-02..2026-08": window("2021-01-01","2026-12-31"),
  "belt 700d 2024-09..2026-08": window("2024-09-21","2026-12-31"),
  "belt 900d 2024-03..2026-08": window("2024-03-05","2026-12-31"),
  "2023-01..2026-08": window("2023-01-01","2026-12-31"),
}
print("=== cash rate ACTUALLY paid in each window, vs the shipped 4.0% stress ===")
for n,w in WINDOWS.items():
    print(f"  {n:32s} BIL {annret(w,'BIL'):.2f}%/yr  SHV {annret(w,'SHV'):.2f}%/yr  "
          f"SPY {annret(w,'SPY'):.2f}%/yr   stress=4.00%")

print("\n\n################ ADVERSARIAL CONSTRUCTIONS ################")
res = {}
for wn, w in WINDOWS.items():
    bench3 = ew_curve(w, ["SPY","QQQ","IWM"])
    # N1: 100% T-bills, declared UNIVERSE = SPY/QQQ/IWM (bar = EW of the declared universe)
    res[(wn,"N1 100% BIL vs EW(SPY,QQQ,IWM)")] = judge(
        "N1  100% T-BILLS, declared universe SPY/QQQ/IWM", w, mix_curve(w,{"BIL":1.0}), bench3)
    # N2: 40/60 SPY/BIL vs SPY (single-name declared universe)
    spy = mix_curve(w, {"SPY":1.0})
    res[(wn,"N2 40SPY/60BIL vs SPY")] = judge(
        "N2  40% SPY / 60% BIL, bar = SPY", w, mix_curve(w,{"SPY":0.4,"BIL":0.6}), spy)
    # C1 control: the bar itself
    res[(wn,"C1 bar itself")] = judge("C1  the bar itself (control, must FAIL)", w, bench3, bench3)
    # C2 control: half the bar, no carry (dead cash)
    half = mix_curve(w, {"SPY":0.5/3,"QQQ":0.5/3,"IWM":0.5/3})
    res[(wn,"C2 half bar dead cash")] = judge("C2  50% bar + 50% DEAD cash (control, must FAIL)", w, half, bench3)
    # C3 control: 2x levered bar
    lev = mix_curve(w, {"SPY":2/3,"QQQ":2/3,"IWM":2/3})
    res[(wn,"C3 2x levered bar")] = judge("C3  2x levered bar, no financing (control)", w, lev, bench3)

print("\n\n################ SUMMARY ################")
for (wn,k),v in res.items():
    print(f"  {'PASS' if v else 'fail'}  {k:38s} {wn}")
