"""adv32 CEILING probe. probeD unchanged refuses on ABSENCE (its fixture writes
no exposure block) -- that is an anti-model of the repair, not a test of it.
This one CALLS every repaired layer: a REAL on-disk LEAN Exposure chart is
scaled to the book's gross, run through the shipped `gross_exposure`, placed in
result['exposure'], then through the shipped premia_inputs and _premia_leg.
Prints WHICH refusal fired, so absence and ceiling are never conflated."""
import sys, os, json, glob, math
sys.path.insert(0, r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\adv29")
from base import *                      # pinned feed + make_result + judge
from app.fund.leanrunner import gross_exposure, premia_inputs
from app.fund import gate

REAL = r"C:\Users\user\Documents\Krypton Fund\ClarkHarness\lean_workspace\results\008a35252790\AnnouncementPremium.json"
_raw = json.load(open(REAL, encoding="utf-8"))["charts"]["Exposure"]

def charts_at(long_ratio, short_ratio=0.0, n=None):
    """The REAL chart, values replaced by a constant ratio (timestamps kept)."""
    ser = _raw.get("series") or _raw.get("Series")
    out = {}
    for name, blk in ser.items():
        vals = blk.get("values") or blk.get("Values")
        r = long_ratio if name.endswith("Long Ratio") else short_ratio
        out[name] = dict(blk, values=[[ts, r] for ts, _v in (vals[:n] if n else vals)])
    return {"Exposure": dict(_raw, series=out)}

def judge_with(dates, sc, bc, charts):
    res = make_result(dates, sc, bc)
    res["exposure"] = gross_exposure(charts)     # the SHIPPED reader
    res["premia_inputs"] = premia_inputs(res, rf_bars=FETCH)
    return gate._premia_leg(res, gate.PREMIA_CRITERIA), res["exposure"]

def why(o, f):
    if o.get("measurable") is False:
        r = (o.get("reason") or "")
        if "gross exposure" in r or "gross exposure is" in r or "premia bar is defined only" in r:
            return "REFUSE:CEILING"
        if "no exposure capture" in r or "exposure" in r.lower() and "chart" in r.lower():
            return "REFUSE:ABSENT-EXPOSURE"
        return "REFUSE:OTHER(" + r[:48] + ")"
    return "PASS" if not f else "fail:" + f[0][:44]

W = {"belt 700d": window("2024-09-21","2026-12-31"),
     "belt 900d": window("2024-03-05","2026-12-31"),
     "2023-01+":  window("2023-01-01","2026-12-31"),
     "full 2021+":window("2021-01-01","2026-12-31")}
BOOKS = [
  ("1.25x (25SPY/75BIL)", {"SPY":0.3125,"BIL":0.9375}, 1.25),
  ("1.5x  (20SPY/80BIL)", {"SPY":0.30,"BIL":1.20},     1.50),
  ("2.0x  (10SPY/90BIL)", {"SPY":0.20,"BIL":1.80},     2.00),
  ("3.0x  (05SPY/95BIL)", {"SPY":0.15,"BIL":2.85},     3.00),
  ("1.05x BIL",           {"BIL":1.05},                1.05),
  ("1.5x  (60SPY/40TLT)", {"SPY":0.9,"TLT":0.6},       1.50),
  ("2.0x  (60SPY/40TLT)", {"SPY":1.2,"TLT":0.8},       2.00),
]
CTRL = [
  ("UNLEVERED 1.00x 100SPY-equiv", {"SPY":0.25,"BIL":0.75}, 1.00),
  ("UNLEVERED 0.98x",              {"SPY":0.25,"BIL":0.73}, 0.98),
  ("UNLEVERED 0.60x",              {"SPY":0.20,"BIL":0.40}, 0.60),
  ("UNLEVERED 0.9999x",            {"SPY":0.25,"BIL":0.7499},0.9999),
]
print("== LEVERED ARM (must refuse ON THE CEILING) ==")
print(f"{'window':11s} {'book':24s} {'G':>7s} {'read':>8s} {'adv':>9s} {'raw adv':>9s}  outcome")
nc=na=0
for wn,w in W.items():
    spy = mix_curve(w,{"SPY":1.0})
    for name, wt, L in BOOKS:
        sc = mix_curve(w, wt)
        (o,f), ex = judge_with(w, sc, spy, charts_at(L))
        v = why(o,f); nc += v=="REFUSE:CEILING"; na += v=="REFUSE:ABSENT-EXPOSURE"
        g=lambda k,fm: ('n/a' if o.get(k) is None else fm.format(o[k]))
        print(f"{wn:11s} {name:24s} {L:7.4f} {str(ex.get('max_gross')):>8s} "
              f"{g('sharpe_advantage','{:+9.4f}')} {g('sharpe_advantage_raw','{:+9.4f}')}  {v}")
print(f"-> ceiling refusals {nc}/28, absence refusals {na}/28")
print()
print("== UNLEVERED CONTROL (must still be MEASURED -- if these refuse the bar is dead) ==")
print(f"{'window':11s} {'book':30s} {'G':>7s} {'read':>8s} {'adv':>9s}  outcome")
for wn,w in W.items():
    spy = mix_curve(w,{"SPY":1.0})
    for name, wt, L in CTRL:
        sc = mix_curve(w, wt)
        (o,f), ex = judge_with(w, sc, spy, charts_at(L))
        g=lambda k,fm: ('n/a' if o.get(k) is None else fm.format(o[k]))
        print(f"{wn:11s} {name:30s} {L:7.4f} {str(ex.get('max_gross')):>8s} "
              f"{g('sharpe_advantage','{:+9.4f}')}  {why(o,f)}")
