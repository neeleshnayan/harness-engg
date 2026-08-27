import json,datetime,math
y=json.load(open("yahoo.json"))
def d(s): return datetime.date(*map(int,s.split("-")))
for s in ["ETHB","ETHE","ETH"]:
    dv=y[s]["div"]
    print(f"== {s}: {len(dv)} distributions")
    rows=[]
    for k,v in sorted(dv.items(), key=lambda kv: kv[1]["date"]):
        dt=datetime.datetime.utcfromtimestamp(v["date"]).strftime("%Y-%m-%d")
        # price on that date
        px=None
        for dd,c in zip(y[s]["dates"],y[s]["close"]):
            if dd<=dt and c is not None: px=c
        rows.append((dt,v["amount"],px, v["amount"]/px*100 if px else None))
    for r in rows: print(f"   {r[0]}  ${r[1]:.4f}  px ${r[2]:.2f}  = {r[3]:.4f}% of price")
    if rows:
        span=(d(rows[-1][0])-d(rows[0][0])).days
        tot=sum(r[3] for r in rows)
        print(f"   sum {tot:.3f}% over {span}d spanning {len(rows)} pays")
print()
# daily vs monthly t on the FULL post window
def ser(sym,f="adj"): return {a:b for a,b in zip(y[sym]["dates"],y[sym][f]) if b is not None}
E,A=ser("ETH"),ser("ETHA")
cs=sorted(set(E)&set(A))
def stats(s):
    r=[math.log(E[s[i+1]]/E[s[i]])-math.log(A[s[i+1]]/A[s[i]]) for i in range(len(s)-1)]
    n=len(r);m=sum(r)/n;sd=(sum((v-m)**2 for v in r)/(n-1))**.5
    return n,m*252*100,sd*252**.5*100,m/(sd/n**.5)
for lbl,sub in [("PRE  (to 2025-10-03)",[x for x in cs if x<="2025-10-03"]),
                ("POST (from 2025-10-06)",[x for x in cs if x>="2025-10-03"])]:
    n,ar,vol,t=stats(sub)
    print(f"{lbl}: n={n} daily  ann {ar:+.3f}%/yr  active vol {vol:.2f}%/yr  daily t={t:+.2f}   se={vol/ (n/252)**.5:.2f}%/yr")
