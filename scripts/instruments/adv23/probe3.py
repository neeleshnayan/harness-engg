"""probe 3: the SAME pairs judged against the CONSTITUTION's definition -
excess returns over the REALISED risk-free series (BIL), the fund's own feed -
beside the shipped rule's verdict. Zero skill should score adv == 0."""
import sys, os, math
sys.path.insert(0, r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"probe1.py")).read().split("WINDOWS = {")[0])
from app.fund import statistics as st

def sharpe_excess(curve, dates, rf_sym="BIL"):
    r = [curve[i]/curve[i-1]-1.0 for i in range(1,len(dates))]
    rf = [SY[rf_sym][dates[i]]/SY[rf_sym][dates[i-1]]-1.0 for i in range(1,len(dates))]
    ex = [a-b for a,b in zip(r,rf)]
    mu, sd = st.mean_std(ex)
    if sd <= 1e-15: return None
    k = st.observations_per_year(dates[1:], len(ex))["obs_per_year"]
    return mu/sd*math.sqrt(k)

W = {"belt 700d": window("2024-09-21","2026-12-31"),
     "belt 900d": window("2024-03-05","2026-12-31"),
     "2023-01+":  window("2023-01-01","2026-12-31"),
     "full":      window("2021-01-01","2026-12-31")}
print(f"{'window':11s} {'pair':40s} {'TRUE excess-Sharpe adv':>24s}   shipped adv@rf0  adv@4%  verdict")
for wn,w in W.items():
    pairs = [
      ("20SPY/80BIL vs EW(SPY,BIL)", mix_curve(w,{"SPY":0.2,"BIL":0.8}), ew_curve(w,["SPY","BIL"])),
      ("40SPY/60BIL vs EW(SPY,BIL)", mix_curve(w,{"SPY":0.4,"BIL":0.6}), ew_curve(w,["SPY","BIL"])),
      ("100% BIL vs EW(SPY,QQQ,IWM)", mix_curve(w,{"BIL":1.0}), ew_curve(w,["SPY","QQQ","IWM"])),
      ("40SPY/60BIL vs SPY",         mix_curve(w,{"SPY":0.4,"BIL":0.6}), mix_curve(w,{"SPY":1.0})),
    ]
    for name, sc, bc in pairs:
        res = make_result(w, sc, bc); res["premia_inputs"] = premia_inputs(res)
        o, f = gate._premia_leg(res, gate.PREMIA_CRITERIA)
        a,b = sharpe_excess(sc,w), sharpe_excess(bc,w)
        true_adv = None if (a is None or b is None) else a-b
        ta = "  ZERO by construction" if true_adv is None else f"{true_adv:+24.4f}"
        print(f"{wn:11s} {name:40s} {ta:>24s}   {o['sharpe_advantage']:+9.4f} "
              f"{o['sharpe_advantage_at_stress']:+8.4f}  {'PASS' if not f else 'fail'}")
