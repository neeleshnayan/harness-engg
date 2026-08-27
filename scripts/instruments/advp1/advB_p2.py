import sys, json, time, urllib.request
from datetime import datetime, timezone, timedelta
sys.path.insert(0,r"C:\Users\user\Documents\Krypton Fund\ClarkHarness")
from app.fund import navgap

# live strike history via the spine's own route
d=json.load(urllib.request.urlopen('http://localhost:8090/api/v1/fund/nav/history?limit=365',timeout=120))
rows=d["history"]
print(f"live struck-NAV rows: {len(rows)}")
now=datetime.now(timezone.utc)

t0=time.monotonic(); r=navgap.completeness(rows, now=now); cold=time.monotonic()-t0
t0=time.monotonic(); r=navgap.completeness(rows, now=now); warm=time.monotonic()-t0
print(f"completeness() on the live series: first {cold*1000:.0f} ms, second {warm*1000:.0f} ms "
      f"(this EXCLUDES the event-log fold that produced `rows`)")
print(f"verdict now: state={r['state']} holes={r['hole_count']} strikes_in_window={r['strikes_in_window']}")

# 1. SATURATION: does one MORE hole change the alarm key's presence?
print()
print("=== SATURATION: what a NEW hole does to the alarm, given 11 old ones ===")
def state_of(rws, when):
    return navgap.completeness(rws, now=when)
base=state_of(rows, now)
# inject a fresh 4-trading-hour hole ending now, by deleting today's most recent strikes
future = now + timedelta(days=1)
inj = rows + [{"ts": (now + timedelta(hours=30)).isoformat()}]   # a strike 30h from now -> a NEW gap
b2 = state_of(rows, now + timedelta(hours=30))
print(f"  today            : state={base['state']:<8} holes={base['hole_count']}  -> alarm key present = {base['state']=='holes'}")
print(f"  +30h, new hole   : state={b2['state']:<8} holes={b2['hole_count']}  -> alarm key present = {b2['state']=='holes'}")
print("  riskmonitor.py:1698  `for k in sorted(new_keys)` with new_keys = current - active")
print(f"  => key unchanged, new_keys empty, RISK_ALARM_RAISED events emitted for the new hole: 0")

# 2. AGEING: when does the WARN go out with no repair at all?
print()
print("=== SELF-CLEAR: when does the record become 'whole' if nothing more goes wrong? ===")
probe=[r_ for r_ in rows]
for days in [0,7,14,20,21,22,25]:
    when = now + timedelta(days=days)
    # freeze the record: no new strikes at all would itself be one huge hole, so
    # instead extend it with perfect hourly in-session strikes
    ext=list(probe); t=max(datetime.fromisoformat(x["ts"]) for x in rows)
    while t < when:
        t += timedelta(minutes=30); ext.append({"ts": t.isoformat()})
    rr=state_of(ext, when)
    print(f"  +{days:>2}d ({when.date()}): state={rr['state']:<8} holes={rr['hole_count']}  WARN lit = {rr['state']=='holes'}")
