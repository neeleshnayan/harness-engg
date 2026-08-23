"""adv29 probe B: LEVERAGED CASH -- the carry channel the excess repair cannot see.
A backtest that levers pays no financing, so a levered CASH book's excess over BIL
is (L-1)*r_BIL: an almost-riskless positive drift with a tiny drawdown. Both the
Sharpe leg AND the drawdown leg are cleared by construction."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import *
from app.fund import statistics as st

W = {"belt 700d": window("2024-09-21","2026-12-31"),
     "belt 900d": window("2024-03-05","2026-12-31"),
     "2023-01+":  window("2023-01-01","2026-12-31"),
     "full 2021+":window("2021-01-01","2026-12-31")}

print("first: the raw spread Sharpes, computed independently (mine, not the gate's)")
for wn,w in W.items():
    for sym in ("SHV","BIL"):
        sp=[SY[sym][w[i]]/SY[sym][w[i-1]] - SY["BIL"][w[i]]/SY["BIL"][w[i-1]] for i in range(1,len(w))]
        mu,sd=st.mean_std(sp); k=st.observations_per_year(w[1:],len(sp))["obs_per_year"]
        s = None if sd<=1e-15 else mu/sd*math.sqrt(k)
        print(f"   {wn:11s} ({sym} - BIL) ann Sharpe {('n/a' if s is None else f'{s:+8.3f}')}  ann drift {((1+mu)**k-1)*100:+.3f}%/yr")

print(f"\n{'window':11s} {'construction':40s} {'adv':>8s} {'sSh':>8s} {'bSh':>8s} {'s.dd%':>7s} {'b.dd%':>7s} {'cov':>10s} verdict")
for wn,w in W.items():
    spy = mix_curve(w,{"SPY":1.0}); ew3 = ew_curve(w,["SPY","QQQ","IWM"])
    cells = [
      ("2.0x BIL (levered cash) vs SPY",       mix_curve(w,{"BIL":2.0}), spy),
      ("3.0x BIL (levered cash) vs SPY",       mix_curve(w,{"BIL":3.0}), spy),
      ("2.0x BIL vs EW(SPY,QQQ,IWM)",          mix_curve(w,{"BIL":2.0}), ew3),
      ("1.05x BIL vs SPY",                     mix_curve(w,{"BIL":1.05}), spy),
      ("4xBIL - 3xSHV? no: 2xBIL+0.02SPY vs SPY", mix_curve(w,{"BIL":2.0,"SPY":0.02}), spy),
    ]
    for name, sc, bc in cells:
        o,f = judge(w, sc, bc)
        g=lambda k,fm: ('n/a' if o.get(k) is None else fm.format(o[k]))
        print(f"{wn:11s} {name:40s} {g('sharpe_advantage','{:+8.3f}')} "
              f"{g('sharpe_strategy','{:8.3f}')} {g('sharpe_benchmark','{:8.3f}')} "
              f"{g('strategy_max_drawdown_pct','{:7.2f}')} {g('benchmark_max_drawdown_pct','{:7.2f}')} "
              f"{str(o.get('coverage',{}).get('common_days'))+'/'+str(o.get('coverage_denominator')):>10s} "
              f"{'PASS' if not f else 'fail'}"
              + ("" if not f else "   :: " + f[0][:90]))
