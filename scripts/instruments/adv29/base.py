"""adv29 shared harness: pinned feed + a REAL fetcher for the repaired rf path.
Calls the SHIPPED premia_inputs / _premia_leg. Nothing is reimplemented except
the independent TRUE excess-Sharpe, which is the whole point of the check."""
import json, os, sys, math
HEAD = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23"
sys.path.insert(0, HEAD)
D23 = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\adv23"
from app.fund.leanrunner import premia_inputs
from app.fund import gate
from app.fund import statistics as st

NAMES = ["SPY","QQQ","IWM","BIL","TLT","SHV","XLK","XLE","XLF","XLV","XLU","XLP"]
def _load(s):
    o = json.load(open(os.path.join(D23, f"{s}.json")))
    return dict(zip(o["dates"], o["closes"]))
SY = {s: _load(s) for s in NAMES}
ALLD = sorted(set.intersection(*[set(v) for v in SY.values()]))
def window(a,b): return [d for d in ALLD if a<=d<=b]

class Bars:
    def __init__(self, dates, closes, source="pinned-adv29"):
        self.dates, self.closes, self.source = dates, closes, source

def make_fetcher(symbol_map=None):
    """A fetcher over the PINNED feed. Mirrors the live one's contract:
    .dates/.closes/.source, window inclusive on both ends."""
    def f(symbol, start, end):
        c = SY[symbol]
        ds = [d for d in sorted(c) if start <= d <= end]
        if not ds: return None
        return Bars(ds, [c[d] for d in ds])
    return f
FETCH = make_fetcher()

def ew_curve(dates, syms, e0=100000.0):
    return [e0*sum(SY[s][d]/SY[s][dates[0]] for s in syms)/len(syms) for d in dates]
def mix_curve(dates, weights, e0=100000.0):
    lvl=e0; out=[lvl]
    for i in range(1,len(dates)):
        r = sum(w*(SY[s][dates[i]]/SY[s][dates[i-1]]-1.0) for s,w in weights.items())
        lvl *= (1+r); out.append(lvl)
    return out
def make_result(dates, sc, bc):
    sr = [sc[i]/sc[i-1]-1.0 for i in range(1,len(dates))]
    return {"daily_returns": {"present": True, "dates": dates[1:], "strategy": sr,
                              "benchmark": [], "benchmark_present": False, "n": len(sr)},
            "benchmark_curve": bc, "benchmark_dates": dates,
            "benchmark_series_source": "recomputed_basket",
            "benchmark_return_pct": (bc[-1]/bc[0]-1)*100,
            "total_return_pct": (sc[-1]/sc[0]-1)*100}

def judge(dates, sc, bc, fetcher=FETCH, pc=None):
    res = make_result(dates, sc, bc)
    res["premia_inputs"] = premia_inputs(res, rf_bars=fetcher)
    return gate._premia_leg(res, pc or gate.PREMIA_CRITERIA)

# --- INDEPENDENT true excess Sharpe (my own arithmetic, not the gate's) ----
def true_excess_sharpe(curve, dates, rf_sym="BIL"):
    r  = [curve[i]/curve[i-1]-1.0 for i in range(1,len(dates))]
    rf = [SY[rf_sym][dates[i]]/SY[rf_sym][dates[i-1]]-1.0 for i in range(1,len(dates))]
    ex = [a-b for a,b in zip(r,rf)]
    mu, sd = st.mean_std(ex)
    if sd <= 1e-15: return None
    k = st.observations_per_year(dates[1:], len(ex))["obs_per_year"]
    return mu/sd*math.sqrt(k)
