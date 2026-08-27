import json,math,statistics,datetime
y=json.load(open("yahoo.json"))
def ser(s,f="adj"): return {a:b for a,b in zip(y[s]["dates"],y[s][f]) if b is not None}
E,A=ser("ETH"),ser("ETHA")
cs=sorted(set(E)&set(A)); post=[x for x in cs if x>="2025-10-03"]
r=[math.log(E[post[i+1]]/E[post[i]])-math.log(A[post[i+1]]/A[post[i]]) for i in range(len(post)-1)]
n=len(r); m=statistics.mean(r); sd=statistics.stdev(r)
def ac(k):
    a=[r[i]-m for i in range(n-k)]; b=[r[i+k]-m for i in range(n-k)]
    return sum(x*z for x,z in zip(a,b))/sum((v-m)**2 for v in r)
print(f"post-staking daily active return: n={n} mean={m*1e4:.3f}bp sd={sd*1e4:.1f}bp")
print("lag-1..5 autocorrelation:", [round(ac(k),3) for k in range(1,6)])
# variance ratio: k-day var / k*1day var
for k in [5,21,63]:
    agg=[sum(r[i:i+k]) for i in range(0,n-k+1,k)]
    vr=statistics.variance(agg)/(k*sd**2)
    print(f"  VR({k}d) = {vr:.3f}   (=1 iid; <1 mean-reverting daily noise)")
# volume / dollar liquidity
print()
for s in ["ETH","ETHA","ETHB"]:
    ds,cl,vo=y[s]["dates"],y[s]["close"],y[s]["vol"]
    dv=[c*v for dd,c,v in zip(ds,cl,vo) if dd>="2026-07-01" and c and v]
    dv.sort()
    print(f"{s}: last-40 sessions median $ volume = ${statistics.median(dv):,.0f}  min ${dv[0]:,.0f}  n={len(dv)}")
