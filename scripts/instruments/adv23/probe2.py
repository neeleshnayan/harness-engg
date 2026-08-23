"""probe 2: the SAME attack without any declared-universe trickery -
the bar is the EQUAL-WEIGHT BASKET OF THE SYMBOLS ACTUALLY TRADED
(leanrunner._add_benchmark: basis='traded_symbols' when no UNIVERSE is declared)."""
import sys, os
sys.path.insert(0, r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d23")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"probe1.py")).read().split("WINDOWS = {")[0])

W = {
  "full 2021-02..2026-08": window("2021-01-01","2026-12-31"),
  "belt 700d 2024-09..2026-08": window("2024-09-21","2026-12-31"),
  "belt 900d 2024-03..2026-08": window("2024-03-05","2026-12-31"),
  "2023-01..2026-08": window("2023-01-01","2026-12-31"),
}
out={}
for wn,w in W.items():
    print("\n\n##########", wn)
    # bar = EW(SPY, BIL) : exactly what _add_benchmark builds for an algorithm
    # that declares no UNIVERSE and trades SPY and BIL.
    bar = ew_curve(w, ["SPY","BIL"])
    out[(wn,"T1 20SPY/80BIL vs EW(SPY,BIL) traded-symbols bar")] = judge(
        "T1  20% SPY / 80% BIL   bar = EW(SPY,BIL) [no UNIVERSE declared]", w,
        mix_curve(w,{"SPY":0.2,"BIL":0.8}), bar)
    out[(wn,"T2 40SPY/60BIL vs EW(SPY,BIL)")] = judge(
        "T2  40% SPY / 60% BIL   bar = EW(SPY,BIL)", w,
        mix_curve(w,{"SPY":0.4,"BIL":0.6}), bar)
    # T3: a 200d-MA de-risking rule: SPY when above its own 200d MA else BIL.
    closes = [SY["SPY"][d] for d in w]
    # use the full history for the MA so no look-ahead and no warmup hole
    alld = ALLD
    idx = {d:i for i,d in enumerate(alld)}
    lvl=100000.0; curve=[lvl]
    for i in range(1,len(w)):
        d_prev, d = w[i-1], w[i]
        j = idx[d_prev]
        ma = sum(SY["SPY"][alld[k]] for k in range(max(0,j-199), j+1))/min(200, j+1)
        sym = "SPY" if SY["SPY"][d_prev] > ma else "BIL"
        lvl *= SY[sym][d]/SY[sym][d_prev]; curve.append(lvl)
    out[(wn,"T3 200dMA SPY/BIL vs EW(SPY,BIL)")] = judge(
        "T3  200-day-MA switch SPY<->BIL   bar = EW(SPY,BIL)", w, curve, bar)
    out[(wn,"T3b 200dMA SPY/BIL vs SPY")] = judge(
        "T3b 200-day-MA switch SPY<->BIL   bar = SPY (UNIVERSE=['SPY'])", w, curve,
        mix_curve(w,{"SPY":1.0}))
print("\n\n############ SUMMARY (traded-symbols bar, no universe trickery) ############")
for (wn,k),v in out.items():
    print(f"  {'PASS' if v else 'fail'}  {k:52s} {wn}")
