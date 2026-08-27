import json, datetime
y=json.load(open("yahoo.json"))
GS={"2024-12-31":(470875.757751,49970788),"2025-03-31":(456425.171929,48450788),
    "2025-06-30":(528670.395104,56140788),"2025-09-30":(721349.341699,76630788),
    "2025-12-31":(733993.752764,77730788),"2026-03-31":(861376.856452,90880788),
    "2026-06-30":(854642.674778,89790788)}
EA={"2024-12-31":(1071415,141480000),"2025-03-31":(1191766,157440000),
    "2025-06-30":(1768573,233720000),"2025-09-30":(3842823,508080000),
    "2025-12-31":(3467229,458720000),"2026-03-31":(3035336,401880000),
    "2026-06-30":(2695456,357120000)}
def d(s): return datetime.date(*map(int,s.split("-")))
def px(sym,day):
    ds,cs=y[sym]["dates"],y[sym]["close"]; best=None
    for i,dd in enumerate(ds):
        if dd<=day and cs[i] is not None: best=cs[i]
    return best
def ann(r,days): return (r**(365.0/days)-1)*100
dates=sorted(GS)
print("== DECOMPOSITION: price advantage = ETH/share accrual + premium-spread drift ==")
print(f"{'window':<26}{'d':>5}{'PRICE %/yr':>12}{'ACCRUAL %/yr':>14}{'PREMIUM %/yr':>14}")
for i in range(len(dates)-1):
    a,b=dates[i],dates[i+1]; nd=(d(b)-d(a)).days
    pr=(px("ETH",b)/px("ETH",a))/(px("ETHA",b)/px("ETHA",a))
    ac=((GS[b][0]/GS[b][1])/(GS[a][0]/GS[a][1]))/((EA[b][0]/EA[b][1])/(EA[a][0]/EA[a][1]))
    print(f"{a+'->'+b:<26}{nd:>5}{ann(pr,nd):>12.3f}{ann(ac,nd):>14.3f}{ann(pr/ac,nd):>14.3f}")
for a,b,lbl in [("2025-09-30","2026-06-30","POST-STAKING 3 qtrs"),("2025-12-31","2026-06-30","POST 2 qtrs"),
                ("2024-12-31","2025-09-30","PRE-STAKING control")]:
    nd=(d(b)-d(a)).days
    pr=(px("ETH",b)/px("ETH",a))/(px("ETHA",b)/px("ETHA",a))
    ac=((GS[b][0]/GS[b][1])/(GS[a][0]/GS[a][1]))/((EA[b][0]/EA[b][1])/(EA[a][0]/EA[a][1]))
    print(f"{lbl:<26}{nd:>5}{ann(pr,nd):>12.3f}{ann(ac,nd):>14.3f}{ann(pr/ac,nd):>14.3f}")

# reproduce the author's headline windows on the fund's own bars
b=json.load(open("bars.json"))
def series(sym):
    return dict(zip(b[sym]["dates"],b[sym]["closes"]))
E,A=series("ETH"),series("ETHA")
ds=[x for x in b["ETH"]["dates"] if x in A]
def seg(d0,d1):
    sub=[x for x in ds if d0<=x<=d1]
    r=(E[sub[-1]]/E[sub[0]])/(A[sub[-1]]/A[sub[0]])
    nd=(d(sub[-1])-d(sub[0])).days
    return sub[0],sub[-1],len(sub),ann(r,nd)
print()
print("== REPRODUCTION of the filed headline, fund's own adjusted bars ==")
print("full  ",seg(ds[0],ds[-1]))
print("pre   ",seg(ds[0],"2025-10-03"))
print("post  ",seg("2025-10-06",ds[-1]))
print("did   diff-in-diff = post - pre =", round(seg('2025-10-06',ds[-1])[3]-seg(ds[0],'2025-10-03')[3],3))
