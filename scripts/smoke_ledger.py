"""Unit-ledger smoke test — the fairness property that matters.

Three LPs subscribe at different NAV-per-unit, the fund gains, and every LP must
revalue pro-rata to their units. Also checks a full redemption and that a
subscription never dilutes existing LPs.
"""

import _fake_firestore

_fake_firestore.install()

from app.fund.connectors.base import Order, Side
from app.fund.connectors.paper import PaperConnector
from app.fund.events import EventStore
from app.fund.ledger import LedgerService
from app.fund.pipeline import CommandPipeline
from app.fund.projections.holdings import HoldingsProjection
from app.fund.projections.nav import NavService
from app.fund.projections.positions import PositionsProjection
from app.fund.risk import RiskGate, RiskLimits

store = EventStore()
conn = PaperConnector(prices={"AAPL": 200.0})
proj = PositionsProjection(store)
nav = NavService(pricer=conn.price, store=store, projection=proj)
# Permissive risk gate here — this script tests ledger fairness, not risk limits
# (those are covered in smoke_fund.py).
_open = RiskGate(RiskLimits(max_position_pct=10.0, max_order_notional_pct=10.0, min_cash_buffer=0.0))
pipe = CommandPipeline(connector=conn, nav_service=nav, store=store, risk_gate=_open)
ledger = LedgerService(nav_service=nav, store=store)
holdings = HoldingsProjection(store)


def approx(a, b, tol=1e-6):
    return abs(a - b) < tol


def sub(lp, amount, name):
    r = ledger.request_subscription(lp_id=lp, usd_amount=amount, actor="manager", lp_name=name)
    return ledger.confirm_subscription(r["subscription_id"], actor="manager")


def line(m):
    print(f"  {m}")


print("1) Alice subscribes $1,000 as the first LP (base NAV/unit = 1.00)")
a = sub("alice", 1000.0, "Alice")
line(f"units={a['units_issued']} @ nav/unit={a['nav_per_unit']}")
assert approx(a["units_issued"], 1000.0) and approx(a["nav_per_unit"], 1.0)

print("2) Bob subscribes $500 while NAV/unit is still 1.00")
b = sub("bob", 500.0, "Bob")
line(f"units={b['units_issued']} @ nav/unit={b['nav_per_unit']}")
assert approx(b["units_issued"], 500.0)

print("3) Fund invests and the position appreciates (AAPL 200 -> 260, +30%)")
o = pipe.propose_order(Order("paper", "AAPL", Side.BUY, 6), actor="rushi")  # $1,200 of $1,500
pipe.approve_order(o["order_id"], approver="rushi")
conn._prices["AAPL"] = 260.0  # mark up
snap = nav.compute()
line(f"NAV={snap.total_nav_usd}  nav/unit={snap.nav_per_unit:.6f}  units_out={snap.units_outstanding}")
# NAV = 6*260 + cash 300 = 1860 on 1500 units -> 1.24 per unit
assert approx(snap.total_nav_usd, 1860.0) and approx(snap.nav_per_unit, 1.24)

print("4) Everyone revalues pro-rata; Alice up 24%, Bob up 24%")
vals = {r["lp_id"]: r for r in holdings.with_values(snap.nav_per_unit)}
line(f"Alice ${vals['alice']['value_usd']}  Bob ${vals['bob']['value_usd']}")
assert approx(vals["alice"]["value_usd"], 1240.0, 0.01)   # 1000 * 1.24
assert approx(vals["bob"]["value_usd"], 620.0, 0.01)      # 500 * 1.24

print("5) Carol subscribes $620 at the higher NAV/unit — must NOT dilute Alice/Bob")
nav_before = nav.compute().nav_per_unit
c = sub("carol", 620.0, "Carol")
nav_after = nav.compute().nav_per_unit
line(f"Carol units={c['units_issued']:.4f} @ {c['nav_per_unit']:.4f}; nav/unit {nav_before:.6f} -> {nav_after:.6f}")
assert approx(c["units_issued"], 500.0, 0.01)             # 620 / 1.24
assert approx(nav_before, nav_after)                      # invariant: no dilution
snap2 = nav.compute()
line(f"NAV now ${snap2.total_nav_usd}  units_out={snap2.units_outstanding}")
assert approx(snap2.total_nav_usd, 2480.0)                # 1860 + 620

print("6) Bob redeems in full — burns his units, pays out at NAV/unit")
r = ledger.request_redemption(lp_id="bob", actor="manager")
res = ledger.confirm_redemption(r["redemption_id"], actor="manager")
line(f"Bob out ${res['usd_out']} ({res['units_burned']} units @ {res['nav_per_unit']:.4f})")
assert approx(res["usd_out"], 620.0, 0.01)
assert "bob" not in {x["lp_id"] for x in holdings.with_values(nav.compute().nav_per_unit)}

print("7) Remaining LPs unchanged by Bob's exit; NAV/unit steady")
snap3 = nav.compute()
line(f"nav/unit={snap3.nav_per_unit:.6f}  units_out={snap3.units_outstanding}")
assert approx(snap3.nav_per_unit, 1.24, 1e-4)             # redemption is NAV-neutral too

print("\nALL LEDGER ASSERTIONS PASSED ✅")
