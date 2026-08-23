"""adv29 probe D: the REALISTIC form of the financing hole -- a levered low-vol
book, which is what a risk-premia harvester actually looks like. Backtests here
charge no margin interest, so excess = L*r - rf instead of L*(r - rf); the gift
in annualised Sharpe units is (1 - 1/L) * rf / sd_asset. Both criteria are run."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import *
from app.fund import statistics as st

W = {"belt 700d": window("2024-09-21","2026-12-31"),
     "belt 900d": window("2024-03-05","2026-12-31"),
     "2023-01+":  window("2023-01-01","2026-12-31"),
     "full 2021+":window("2021-01-01","2026-12-31")}

def fin_adv(w, weights, L, bench_curve):
    """my own arithmetic: shipped adv MINUS the adv you would get if financing
    on the borrowed (gross-1) were charged at BIL."""
    dates=w
    r=[sum(x*(SY[s][dates[i]]/SY[s][dates[i-1]]-1.0) for s,x in weights.items()) for i in range(1,len(dates))]
    rf=[SY["BIL"][dates[i]]/SY["BIL"][dates[i-1]]-1.0 for i in range(1,len(dates))]
    b=[bench_curve[i]/bench_curve[i-1]-1.0 for i in range(1,len(dates))]
    k=st.observations_per_year(dates[1:],len(r))["obs_per_year"]
    def sh(x):
        mu,sd=st.mean_std(x); return None if sd<=1e-15 else mu/sd*math.sqrt(k)
    shipped = sh([a-c for a,c in zip(r,rf)]) - sh([a-c for a,c in zip(b,rf)])
    financed= sh([a-(L-1)*c-c for a,c in zip(r,rf)]) - sh([a-c for a,c in zip(b,rf)])
    return shipped, financed

print(f"{'window':11s} {'book (gross)':38s} {'shipped adv':>11s} {'if financed':>11s} {'gift':>7s} {'s.dd':>7s} {'b.dd':>7s} verdict")
for wn,w in W.items():
    spy=mix_curve(w,{"SPY":1.0}); ew3=ew_curve(w,["SPY","QQQ","IWM"])
    books = [
      ("1.5x (60SPY/40TLT) vs SPY", {"SPY":0.9,"TLT":0.6}, 1.5, spy),
      ("2.0x (60SPY/40TLT) vs SPY", {"SPY":1.2,"TLT":0.8}, 2.0, spy),
      ("1.25x (25SPY/75BIL) vs SPY",{"SPY":0.3125,"BIL":0.9375},1.25, spy),
      ("1.5x (20SPY/80BIL) vs SPY", {"SPY":0.30,"BIL":1.20}, 1.5, spy),
      ("2.0x (10SPY/90BIL) vs SPY", {"SPY":0.20,"BIL":1.80}, 2.0, spy),
      ("2.0x (10SPY/90BIL) vs EW3", {"SPY":0.20,"BIL":1.80}, 2.0, ew3),
      ("3.0x (05SPY/95BIL) vs SPY", {"SPY":0.15,"BIL":2.85}, 3.0, spy),
    ]
    for name, wt, L, bc in books:
        sc = mix_curve(w, wt)
        o,f = judge(w, sc, bc)
        sh, fi = fin_adv(w, wt, L, bc)
        g=lambda k,fm: ('n/a' if o.get(k) is None else fm.format(o[k]))
        print(f"{wn:11s} {name:38s} {g('sharpe_advantage','{:+11.4f}')} {fi:+11.4f} {sh-fi:+7.3f} "
              f"{g('strategy_max_drawdown_pct','{:7.2f}')} {g('benchmark_max_drawdown_pct','{:7.2f}')} "
              f"{'PASS' if not f else 'fail'}")
