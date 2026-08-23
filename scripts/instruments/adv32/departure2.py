"""adv32: the FLOOR of the departure. A <=T-calendar-day gap test bounds the RUN
LENGTH of omissions, never the FRACTION omitted. Greedy: keep the LATEST session
still within T days of the last kept one. That is the sparsest union the shipped
check will still vouch for. Then ask whether the shipped majority test can be
fooled by it. Shipped premia_inputs + _premia_leg; nothing modelled."""
import sys
sys.path.insert(0, r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\adv29")
from base import *
from app.fund.leanrunner import premia_inputs, SESSION_SPAN_TOLERANCE_DAYS as TOL
from app.fund import gate
from datetime import date
def dd(a,b): return (date.fromisoformat(b)-date.fromisoformat(a)).days

w = window("2021-01-01","2026-12-31")
spy = mix_curve(w,{"SPY":1.0}); bar = ew_curve(w,["SPY","QQQ","IWM"])
print("tolerance in shipped module:", TOL, "days")

# greedy sparsest union that still vouches (both ends must also be within TOL)
kept=[w[0]]
for i,d in enumerate(w[1:],1):
    nxt = w[i+1] if i+1 < len(w) else None
    if nxt is None or dd(kept[-1], nxt) > TOL:
        kept.append(d)
if kept[-1] != w[-1]: kept.append(w[-1])

res = make_result(w, spy, bar)
res["benchmark_dates"] = kept
res["benchmark_curve"] = [bar[w.index(d)] for d in kept]
def fetch_only(days):
    S=set(days)
    def f(sym,a,b):
        c=SY[sym]; ds=[x for x in sorted(c) if a<=x<=b and x in S]
        return Bars(ds,[c[x] for x in ds]) if ds else None
    return f
res["premia_inputs"] = premia_inputs(res, rf_bars=fetch_only(kept))
o,f = gate._premia_leg(res, gate.PREMIA_CRITERIA)
p=res["premia_inputs"]; cov=p["coverage"]; sp=cov["session_span"]
print(f"\nGREEDY SPARSEST correlated thinning of BOTH legs")
print(f"  sessions in run                 {len(w)}")
print(f"  sessions surviving in BOTH legs {len(kept)}  = {len(kept)/len(w)*100:.1f}% TRUE coverage")
print(f"  head/tail/largest-internal gap  {sp['head_shortfall_days']}/{sp['tail_shortfall_days']}/{sp['largest_internal_gap_days']} days (tol {sp['tolerance_days']})")
print(f"  span VOUCHED                    {sp['vouched']}")
print(f"  reported denominator            {o.get('coverage_denominator')}  (basis {cov.get('session_basis')})")
print(f"  common_days / session_fraction  {cov['common_days']} / {cov['session_fraction']}")
print(f"  coverage_majority               {o.get('coverage_majority')}")
print(f"  premia measurable               {o.get('measurable')}   failures {len(f)}")
print(f"\n  => TRUE coverage {len(kept)/len(w)*100:.1f}% ; the bar reads it as "
      f"{(cov['session_fraction'] or 0)*100:.1f}% and calls it a strict majority: {o.get('coverage_majority')}")
