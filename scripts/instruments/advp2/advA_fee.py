"""ADV probe A-2: at what OUTSTANDING FEE does |delta_pct| <= 0.50% false-fire?
Runs the SHIPPED NavService.compute() and the SHIPPED Reconciler.drift() arithmetic
against the REAL store, with FeeLedger.outstanding monkeypatched to a candidate
accrual. NO EVENT IS APPENDED (compute() is read-only; strike() is never called)."""
import os, sys, json
sys.path.insert(0, os.getcwd())
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), ".env"))
from app.fund.mode import resolve, activate
from app.fund.venue import build_connector
from app.fund.events import EventStore
from app.fund.projections.nav import NavService
from app.fund.reconcile import Reconciler
import app.fund.fees as fees

spec = activate(resolve()); conn = build_connector(spec)
store = EventStore()
nav = NavService(pricer=conn.price, store=store)
base = nav.compute()
print("shipped NAV (accrued=0):", base.total_nav_usd, "breakdown", base.breakdown)

def run(acc):
    fees.FeeLedger.outstanding = lambda self, _a=Decimal(str(acc)): _a
    r = Reconciler(conn, store=store, nav_service=NavService(pricer=conn.price, store=store))
    d = r.drift()
    return d["book_nav"], d["broker_equity"], d["delta_usd"], d["delta_pct"], d["symbols_out_of_sync"]

print(f"{'accrued$':>9} {'book_nav':>9} {'broker_eq':>10} {'delta_usd':>10} {'delta_pct':>10} {'oos':>4}  verdict@0.50%")
for acc in [0, 2, 5, 9.9, 10.0, 10.1, 12, 20, 50]:
    bn, be, du, dp, oos = run(acc)
    print(f"{acc:>9.2f} {bn:>9.2f} {be:>10.2f} {du:>10.2f} {dp:>10.4f} {oos:>4}  "
          f"{'MET' if abs(dp) <= 0.50 else '*** UNMET (false fire) ***'}")
