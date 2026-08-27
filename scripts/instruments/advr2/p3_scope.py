"""P3: THE IN-FLIGHT LEDGER'S SCOPE. The module's numbered contract (items 1
and 2) defines in-flight as orders THIS ENVELOPE approved. Every OTHER
committed-but-unfilled order -- the CEO's click, v4's exit envelope -- is
neither in the book (folds ORDER_FILLED only, projections/positions.py:159 and
autopolicy.py:631) nor at the venue (the broker holds no unfilled order), and by
the contract is not in pending_approved either.

PRECONDITION: base approves. MEASUREMENT: what the envelope says when the
invisible order was approved by somebody else."""
import sys, importlib.util
sys.path.insert(0, sys.argv[2]); from base import base, run
spec = importlib.util.spec_from_file_location("v5", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def show(t, o, c, b):
    r = run(m, o, c, b); print(f"{t:<58} approve={r['approve']!s:<5} failed={r['failed']}")
    return r

o, c, b = base(); show("PRECOND base", o, c, b)

print("\n-- A: the CEO clicked approve on 3.7 HYG 40s ago; still unfilled.")
print("   Contract items 1-2 say that order is NOT in pending_approved.")
o, c, b = base()
c["pending_approved"] = []          # <- literally what the contract prescribes
r = show("A  v5 entry 14.8% + CEO's unfilled 14.8% (true 29.6%)", o, c, b)
d = [x['detail'] for x in r['checks'] if x['check']=='post_fill_name_within_concentration'][0]
print("   says:", d)

print("\n-- B: v4's exit envelope auto-approved a SELL of the whole 3.7 long")
print("   40s ago; unfilled. v5 is asked for a reduce-only SELL of 3.7.")
o, c, b = base()
o["side"] = "sell"; o["qty"] = 3.7
c["book_qty_signed"] = 3.7; c["strategy_qty_signed"] = 3.7
c["venue_qty_signed"] = 3.7
c["strategy_exposure_usd"] = 296.0; c["gross_exposure_usd"] = 296.0
c["pending_approved"] = []          # v4's sell is not v5's approval
r = show("B  reduce-only sell, v4's sell invisible (true -3.7)", o, c, b)
d = [x['detail'] for x in r['checks'] if x['check']=='post_fill_position_not_short'][0]
print("   says:", d[:170])

print("\n-- CONTROL: hand the SAME two scenarios a ledger scoped to ALL")
print("   committed-unfilled orders instead of v5's own.")
o, c, b = base()
c["pending_approved"] = [{"order_id":"ceo-1","strategy_id":"s1","symbol":"HYG",
                          "side":"buy","qty":3.7,"mark_usd":80.0,"age_minutes":0.7}]
show("A' same, ledger = ALL committed-unfilled", o, c, b)
o, c, b = base()
o["side"] = "sell"; o["qty"] = 3.7
c["book_qty_signed"] = 3.7; c["strategy_qty_signed"] = 3.7
c["venue_qty_signed"] = 3.7
c["strategy_exposure_usd"] = 296.0; c["gross_exposure_usd"] = 296.0
c["pending_approved"] = [{"order_id":"v4-1","strategy_id":"s1","symbol":"HYG",
                          "side":"sell","qty":3.7,"mark_usd":80.0,"age_minutes":0.7}]
show("B' same, ledger = ALL committed-unfilled", o, c, b)
