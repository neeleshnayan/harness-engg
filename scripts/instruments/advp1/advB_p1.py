import sys, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0,r"C:\Users\user\Documents\Krypton Fund\ClarkHarness")
from app.fund import navgap, heartbeat

ET_NOON_WED = datetime(2026,8,26,16,0,tzinfo=timezone.utc)   # 12:00 ET Wed, mid-session
def row(dt): return {"ts": dt.isoformat()}
def verdict(strikes, now, lbl):
    r = navgap.completeness(strikes, now=now)
    warn = (r["state"] == navgap.STATE_HOLES)
    print(f"{lbl:<52} state={r['state']:<13} holes={r['hole_count']} "
          f"WARN_FIRES={warn}  undet_gaps={sum(1 for g in r['gaps'] if g['verdict']=='undetermined')}")
    return r

print("=== A. FRESH FUND / FIRST HOUR AFTER A RESTART (now = Wed 12:00 ET, mid-session) ===")
verdict([], ET_NOON_WED, "0 strikes ever (empty list)")
verdict([row(ET_NOON_WED - timedelta(minutes=5))], ET_NOON_WED, "exactly 1 strike, 5 min ago")
verdict([row(ET_NOON_WED - timedelta(minutes=65)), row(ET_NOON_WED - timedelta(minutes=5))],
        ET_NOON_WED, "2 strikes, hourly, newest 5 min ago")
verdict(None, ET_NOON_WED, "history UNREADABLE (None)")

print()
print("=== B. MARKET-CLOSED PERIODS ===")
fri = datetime(2026,8,21,19,58,tzinfo=timezone.utc)   # Fri 15:58 ET
mon = datetime(2026,8,24,13,32,tzinfo=timezone.utc)   # Mon 09:32 ET
verdict([row(fri), row(mon)], mon+timedelta(minutes=1), "Fri 15:58 ET -> Mon 09:32 ET (65h wall)")
xmas0 = datetime(2026,12,24,18,5,tzinfo=timezone.utc)  # 13:05 ET on a 13:00 half-day
xmas1 = datetime(2026,12,28,13,35,tzinfo=timezone.utc) # Mon 08:35 ET
verdict([row(xmas0), row(xmas1)], xmas1+timedelta(minutes=1),
        "half-day 12/24 13:05 ET -> 12/28 (Xmas holiday)")
night0 = datetime(2026,8,26,19,58,tzinfo=timezone.utc) # Wed 15:58 ET
verdict([row(night0)], datetime(2026,8,27,10,37,tzinfo=timezone.utc),
        "last strike Wed 15:58 ET, now Thu 06:37 ET (overnight)")

print()
print("=== C. THE TOLERANCE DISAPPEARS (the module's own named failure) ===")
saved = heartbeat.BUDGETS_SECONDS.pop("nav_strike")
r = verdict([row(ET_NOON_WED - timedelta(days=3)), row(ET_NOON_WED)], ET_NOON_WED,
            "3-DAY REAL HOLE with heartbeat key absent")
print(f"   tolerance_source={r['tolerance_source']}  tolerance_seconds={r['tolerance_seconds']}")
print(f"   -> the same series WITH the key present:")
heartbeat.BUDGETS_SECONDS["nav_strike"] = saved
verdict([row(ET_NOON_WED - timedelta(days=3)), row(ET_NOON_WED)], ET_NOON_WED,
        "3-DAY REAL HOLE with heartbeat key present")

print()
print("=== D. CALENDAR RUNS OUT (covers_to = %s) ===" % navgap.CALENDAR_LAST_DAY)
far = datetime(2028,3,15,16,0,tzinfo=timezone.utc)
verdict([row(far - timedelta(days=3)), row(far)], far, "3-DAY REAL HOLE in 2028 (past calendar)")
