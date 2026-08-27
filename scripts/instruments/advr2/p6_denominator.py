"""P6: EVERY CAP IN v5 IS A PERCENT OF TWO GATHERER-SUPPLIED NUMBERS -- nav_usd
and order_mark_usd. What is the largest order the envelope certifies when each
is wrong in the permissive direction, and what does MAX_PLAUSIBLE_NAV_USD
actually exclude?

PRECONDITION: base approves at NAV 2000 / mark 80. MEASUREMENT: the sweep."""
import sys, importlib.util
sys.path.insert(0, sys.argv[2]); from base import base, run
spec = importlib.util.spec_from_file_location("v5", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
LIVE_NAV = 2005.12   # /fund/nav, measured this run

o,c,b = base(); assert run(m,o,c,b)["approve"] is True, "PRECOND"
print("PRECOND base approves\n")

print("A. NAV wrong in the permissive direction. Order is sized at 14.8% of")
print("   the SUPPLIED nav; the TRUE notional is qty*80 against real NAV",
      LIVE_NAV)
print(f"   {'supplied nav':>16} {'qty':>16} {'true $':>18} {'true % of real NAV':>20}  approve")
for nav in (2005.12, 2e4, 2e6, 1e9, 1e11, 1e12, 1.0000001e12, 1e13, 1e308):
    o,c,bb = base()
    c["nav_usd"] = nav
    c["order_mark_usd"] = 80.0
    qty = 0.148 * nav / 80.0
    o["qty"] = qty
    r = run(m,o,c,bb)
    print(f"   {nav:>16.4g} {qty:>16.4g} {qty*80:>18.4g} "
          f"{qty*80/LIVE_NAV*100:>19.4g}%  {r['approve']}")

print("\nB. MARK understated. NAV honest at", LIVE_NAV, "; the corroboration")
print("   field mark_move_vs_strike_pct is supplied HONESTLY at 0.5 because")
print("   the struck mark carries the same error (both come from the price feed).")
print(f"   {'supplied mark':>16} {'qty':>14} {'true $ @80':>16} {'true % NAV':>12}  approve")
for mk in (80.0, 8.0, 0.8, 0.08, 1e-3, 1e-9):
    o,c,bb = base()
    c["nav_usd"] = LIVE_NAV; c["order_mark_usd"] = mk
    c["mark_move_vs_strike_pct"] = 0.5
    qty = 0.148 * LIVE_NAV / mk
    o["qty"] = qty
    r = run(m,o,c,bb)
    print(f"   {mk:>16.4g} {qty:>14.4g} {qty*80:>16.4g} "
          f"{qty*80/LIVE_NAV*100:>11.4g}%  {r['approve']}")

print("\nC. Which checks still fail when nav_usd = 1e12 and the order is")
print("   1.85e9 shares of HYG? (the four exposure bounds go vacuous together)")
o,c,bb = base(); c["nav_usd"] = 1e12; o["qty"] = 0.148*1e12/80.0
r = run(m,o,c,bb)
print("   approve =", r["approve"], " failed =", r["failed"])
for x in r["checks"]:
    if "within" in x["check"] or "concentration" in x["check"]:
        print("     ", x["check"], "->", x["detail"][:110])
