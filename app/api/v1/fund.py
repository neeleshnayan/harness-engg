"""Fund harness API — the spine's HTTP surface.

Order path (venue-agnostic, human-gated): propose → risk gate → approve/decline
→ idempotent execution. Ledger path (LP-facing): subscribe/redeem with a
two-phase confirm, minting/burning units at NAV. Read routes expose NAV,
positions, per-LP holdings, and the audit event log.

The pipeline is wired to the PaperConnector today; swapping in the IBKRConnector
(Step 2) changes only the construction block below.
"""

from fastapi import APIRouter, HTTPException, Query

from app.fund.connectors.base import Order, Side
from app.fund.connectors.paper import PaperConnector
from app.fund.events import EventStore
from app.fund.ledger import LedgerError, LedgerService
from app.fund.pipeline import CommandError, CommandPipeline
from app.fund.projections.holdings import HoldingsProjection
from app.fund.projections.nav import NavService
from app.fund.projections.positions import PositionsProjection
from app.schemas.fund import (
    ActorRequest,
    ApprovalRequest,
    ProposeOrderRequest,
    RedeemRequest,
    StrikeNavRequest,
    SubscribeRequest,
)

router = APIRouter()

# --- spine wiring (single place to swap the venue) -------------------------
_connector = PaperConnector()
_store = EventStore()
_projection = PositionsProjection(_store)
_nav = NavService(pricer=_connector.price, store=_store, projection=_projection)
_pipeline = CommandPipeline(connector=_connector, nav_service=_nav, store=_store)
_ledger = LedgerService(nav_service=_nav, store=_store)
_holdings = HoldingsProjection(_store)


# --- reads -----------------------------------------------------------------
@router.get("/fund/nav")
def get_nav():
    """Live (unstruck) valuation plus the last struck snapshot."""
    return {"live": _nav.compute().to_dict(), "last_struck": _nav.latest()}


@router.get("/fund/positions")
def get_positions():
    """The event-sourced book: cash, units outstanding, positions."""
    book = _projection.build()
    return {
        "cash": book.cash,
        "units_outstanding": book.units_outstanding,
        "positions": book.positions,
    }


@router.get("/fund/lps")
def get_lps():
    """Every LP with units and current value (the manager's LP book)."""
    nav = _nav.compute()
    return {"nav_per_unit": nav.nav_per_unit, "lps": _holdings.with_values(nav.nav_per_unit)}


@router.get("/fund/lp/{lp_id}")
def get_lp(lp_id: str):
    """One LP's managed-fund view: units, value, and share of the fund."""
    nav = _nav.compute()
    rec = _holdings.build().get(lp_id)
    if rec is None or abs(rec["units"]) < 1e-9:
        raise HTTPException(status_code=404, detail=f"no holdings for {lp_id}")
    units = rec["units"]
    outstanding = nav.units_outstanding or units
    return {
        "lp_id": lp_id,
        "name": rec["name"],
        "units": round(units, 6),
        "value_usd": round(units * nav.nav_per_unit, 2),
        "nav_per_unit": nav.nav_per_unit,
        "ownership_pct": round(100.0 * units / outstanding, 4),
    }


@router.get("/fund/events")
def get_events(since_seq: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)):
    """The audit trail — the global event log from ``since_seq`` (exclusive)."""
    return {"events": _store.stream(since_seq=since_seq, limit=limit)}


@router.get("/fund/orders/{order_id}")
def get_order(order_id: str):
    events = _store.by_aggregate(order_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"unknown order {order_id}")
    return {"order_id": order_id, "events": events}


# --- order writes ----------------------------------------------------------
@router.post("/fund/orders/propose")
def propose_order(req: ProposeOrderRequest):
    """Propose an order. Passes the risk gate then awaits human approval."""
    order = Order(
        venue=req.venue,
        symbol=req.symbol.upper(),
        side=Side(req.side),
        qty=req.qty,
        limit_price=req.limit_price,
    )
    return _pipeline.propose_order(order, actor=req.actor)


@router.post("/fund/orders/{order_id}/approve")
def approve_order(order_id: str, req: ApprovalRequest):
    """Human approval gate — approving triggers idempotent execution."""
    try:
        return _pipeline.approve_order(order_id, approver=req.approver)
    except CommandError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/orders/{order_id}/decline")
def decline_order(order_id: str, req: ApprovalRequest):
    try:
        return _pipeline.decline_order(order_id, approver=req.approver)
    except CommandError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/nav/strike")
def strike_nav(req: StrikeNavRequest):
    """Strike and persist a NAV snapshot (the scheduled valuation moment)."""
    return _nav.strike(actor=req.actor).to_dict()


# --- ledger writes (subscribe / redeem) ------------------------------------
@router.post("/fund/lp/subscriptions")
def request_subscription(req: SubscribeRequest):
    """Record an intended deposit (friend says money is coming). Units mint on confirm."""
    try:
        return _ledger.request_subscription(
            lp_id=req.lp_id, usd_amount=req.usd_amount, actor=req.actor, lp_name=req.lp_name
        )
    except LedgerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/lp/subscriptions/{subscription_id}/confirm")
def confirm_subscription(subscription_id: str, req: ActorRequest):
    """Cash landed → mint units at the current NAV-per-unit."""
    try:
        return _ledger.confirm_subscription(subscription_id, actor=req.actor)
    except LedgerError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/lp/redemptions")
def request_redemption(req: RedeemRequest):
    """Record an intended redemption; payout is confirmed separately."""
    try:
        return _ledger.request_redemption(lp_id=req.lp_id, units=req.units, actor=req.actor)
    except LedgerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/lp/redemptions/{redemption_id}/confirm")
def confirm_redemption(redemption_id: str, req: ActorRequest):
    """Payout sent → burn units and remove cash at the current NAV-per-unit."""
    try:
        return _ledger.confirm_redemption(redemption_id, actor=req.actor)
    except LedgerError as e:
        raise HTTPException(status_code=409, detail=str(e))
