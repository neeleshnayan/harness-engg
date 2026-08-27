import json, math, datetime

# ---- issuer-disclosed quantities (SEC 10-Q/10-K, XBRL + schedules) ----
GS = {  # date: (ETH held, shares out, NAV/share)
 "2024-12-31": (470875.757751, 49970788, 31.48),
 "2025-03-31": (456425.171929, 48450788, 17.21),
 "2025-06-30": (528670.395104, 56140788, 23.70),
 "2025-09-30": (721349.341699, 76630788, 39.17),
 "2025-12-31": (733993.752764, 77730788, 28.06),
 "2026-03-31": (861376.856452, 90880788, 19.86),
 "2026-06-30": (854642.674778, 89790788, 15.02),
}
ETHA = {
 "2024-12-31": (1071415, 141480000, 25.24),
 "2025-03-31": (1191766, 157440000, 13.89),
 "2025-06-30": (1768573, 233720000, 18.81),
 "2025-09-30": (3842823, 508080000, 31.24),
 "2025-12-31": (3467229, 458720000, 22.46),
 "2026-03-31": (3035336, 401880000, 15.87),
 "2026-06-30": (2695456, 357120000, 12.02),
}
def d(s): return datetime.date(*map(int,s.split("-")))
def ann(r, days): return (r ** (365.0/days) - 1.0) * 100

print("== ATTACK 1: issuer-disclosed ETH per share (F1's own instrument) ==")
print(f"{'date':<12}{'mini ETH/sh':>14}{'ETHA ETH/sh':>14}{'ratio':>12}")
dates = sorted(GS)
for k in dates:
    g = GS[k][0]/GS[k][1]; a = ETHA[k][0]/ETHA[k][1]
    print(f"{k:<12}{g:>14.8f}{a:>14.8f}{g/a:>12.6f}")
print()
print(f"{'window':<26}{'days':>6}{'mini %/yr':>12}{'ETHA %/yr':>12}{'RATIO %/yr':>12}{'F1 (>1.000?)':>14}")
for i in range(len(dates)-1):
    a,b = dates[i], dates[i+1]
    nd = (d(b)-d(a)).days
    gm = (GS[b][0]/GS[b][1])/(GS[a][0]/GS[a][1])
    am = (ETHA[b][0]/ETHA[b][1])/(ETHA[a][0]/ETHA[a][1])
    print(f"{a+'->'+b:<26}{nd:>6}{ann(gm,nd):>12.3f}{ann(am,nd):>12.3f}{ann(gm/am,nd):>12.3f}{('PASS' if gm/am>1 else 'KILL'):>14}")
# post-staking full
a,b="2025-12-31","2026-06-30"; nd=(d(b)-d(a)).days
gm=(GS[b][0]/GS[b][1])/(GS[a][0]/GS[a][1]); am=(ETHA[b][0]/ETHA[b][1])/(ETHA[a][0]/ETHA[a][1])
print(f"{'POST-STAKING 2 quarters':<26}{nd:>6}{ann(gm,nd):>12.3f}{ann(am,nd):>12.3f}{ann(gm/am,nd):>12.3f}{'PASS':>14}")
a,b="2024-12-31","2025-09-30"; nd=(d(b)-d(a)).days
gm=(GS[b][0]/GS[b][1])/(GS[a][0]/GS[a][1]); am=(ETHA[b][0]/ETHA[b][1])/(ETHA[a][0]/ETHA[a][1])
print(f"{'PRE-STAKING (control)':<26}{nd:>6}{ann(gm,nd):>12.3f}{ann(am,nd):>12.3f}{ann(gm/am,nd):>12.3f}{'-':>14}")

# ---- ATTACK 2: premium/discount to NAV ----
y=json.load(open("yahoo.json"))
def close_on(sym, day):
    ds=y[sym]["dates"]; cs=y[sym]["close"]
    # last available close on or before day
    best=None
    for i,dd in enumerate(ds):
        if dd<=day and cs[i] is not None: best=(dd,cs[i])
    return best
print()
print("== ATTACK 2: premium/discount to issuer NAV (raw closes, no divs on either) ==")
print(f"{'date':<12}{'mini px':>10}{'mini NAV':>10}{'prem%':>9}{'ETHA px':>10}{'ETHA NAV':>10}{'prem%':>9}{'SPREAD pp':>11}")
sp={}
for k in dates:
    pm=close_on("ETH",k); pa=close_on("ETHA",k)
    if not pm or not pa: continue
    prm=(pm[1]/GS[k][2]-1)*100; pra=(pa[1]/ETHA[k][2]-1)*100
    sp[k]=prm-pra
    print(f"{k:<12}{pm[1]:>10.2f}{GS[k][2]:>10.2f}{prm:>9.3f}{pa[1]:>10.2f}{ETHA[k][2]:>10.2f}{pra:>9.3f}{prm-pra:>11.3f}")
print()
a,b="2025-09-30","2026-06-30"; nd=(d(b)-d(a)).days
print(f"premium-spread drift over the POST-STAKING window {a}->{b} ({nd}d): "
      f"{sp[b]-sp[a]:+.3f} pp  =>  {(sp[b]-sp[a])*365/nd:+.3f} pp/yr of the measured advantage")
a,b="2025-12-31","2026-06-30"; nd=(d(b)-d(a)).days
print(f"premium-spread drift over {a}->{b} ({nd}d): {sp[b]-sp[a]:+.3f} pp => {(sp[b]-sp[a])*365/nd:+.3f} pp/yr")
