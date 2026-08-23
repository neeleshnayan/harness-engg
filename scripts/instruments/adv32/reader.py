"""adv32: attack `gross_exposure` directly -- series classification, the per-
timestamp join, the ceiling boundary, and the `_curve` refactor's except-clause."""
import sys, json
sys.path.insert(0, r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23")
from app.fund.leanrunner import gross_exposure, _curve
def s(name, vals): return {name: {"values": vals}}
def ch(**series): return {"Exposure": {"series": dict(series)}}

print("== A. SERIES CLASSIFICATION ==")
CASES = [
 ("both, normal",              ch(**{"Base - Long Ratio": {"values":[[1,0.6],[2,0.6]]},
                                     "Base - Short Ratio":{"values":[[1,0.3],[2,0.3]]}})),
 ("a third, unclassified",     ch(**{"Base - Long Ratio": {"values":[[1,0.6]]},
                                     "Base - Short Ratio":{"values":[[1,0.3]]},
                                     "Base - Net Ratio":  {"values":[[1,0.3]]}})),
 ("LONG SERIES MISSING",       ch(**{"Base - Short Ratio":{"values":[[1,0.9]]}})),
 ("SHORT SERIES MISSING",      ch(**{"Base - Long Ratio": {"values":[[1,1.4]]}})),
 ("two types, SAME stamps",    ch(**{"Base - Long Ratio":  {"values":[[1,0.6]]},
                                     "Base - Short Ratio": {"values":[[1,0.0]]},
                                     "Future - Long Ratio":{"values":[[1,0.6]]},
                                     "Future - Short Ratio":{"values":[[1,0.0]]}})),
 ("two types, DIFFERENT stamps",ch(**{"Base - Long Ratio":  {"values":[[1,0.6],[3,0.6]]},
                                     "Base - Short Ratio": {"values":[[1,0.0],[3,0.0]]},
                                     "Future - Long Ratio":{"values":[[2,0.6],[4,0.6]]},
                                     "Future - Short Ratio":{"values":[[2,0.0],[4,0.0]]}})),
 ("values as {x,y} objects",   ch(**{"Base - Long Ratio": {"values":[{"x":1,"y":2.5}]},
                                     "Base - Short Ratio":{"values":[{"x":1,"y":0.0}]}})),
 ("empty chart",               {"Exposure": {"series": {}}}),
 ("no Exposure chart",         {"Equity": {"series": {}}}),
 ("charts is None",            None),
]
for label, c in CASES:
    o = gross_exposure(c)
    print(f"  {label:30s} measurable={str(o['measurable']):5s} max_gross={str(o['max_gross']):>8s} "
          f"long={str(o['max_long']):>6s} short={str(o['max_short']):>6s} :: {(o['reason'] or '')[:60]}")

print()
print("== B. THE CEILING BOUNDARY (<= 1.0 passes, > 1.0 refuses) ==")
from app.fund import gate
for g in (0.999999, 1.0, 1.0000001, 1.0000004, 1.0000005, 1.000001, 1.00001, 1.01):
    o = gross_exposure(ch(**{"Base - Long Ratio":{"values":[[1,g]]},
                             "Base - Short Ratio":{"values":[[1,0.0]]}}))
    read = o["max_gross"]
    print(f"  true gross {g:<12.7f} -> reader reports {read:<10} -> gross<=1.0 ? "
          f"{read <= gate.PREMIA_CRITERIA['premia_max_gross_exposure']}")

print()
print("== C. `_curve` REFACTOR: the except clause narrowed ==")
big = 10**400   # a JSON integer too large for a float
pts = {"C": {"series": {"S": {"values": [[1, 1.0], [2, big]]}}}}
try:
    v, d = _curve(pts, "C", "S")
    print(f"  huge integer value -> survived, {len(v)} points kept: {v}")
except Exception as e:
    print(f"  huge integer value -> {type(e).__name__}: {e}  <-- UNCAUGHT")
