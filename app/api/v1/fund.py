"""Fund harness API — the spine's HTTP surface (Step 1 scaffold).

Read routes (no gate): NAV, positions/book, audit stream, one order's history.
Write routes: propose an order (runs the risk gate) then approve/decline it
(the human-in-the-loop gate) which triggers idempotent execution on the venue.

Everything here is venue-agnostic: the pipeline is wired to the PaperConnector
today; swapping in the IBKRConnector (Step 2) changes only the construction
below. The agent (krypton_clark) will reach these same routes through
clark_mcp's tool surface.
"""

from fastapi import APIRouter, HTTPException, Query

from app.fund.connectors.base import Order, Side
from app.fund.connectors.paper import PaperConnector
from app.fund.events import EventStore
from app.fund.pipeline import CommandError, CommandPipeline
from app.fund.projections.nav import NavService
from app.fund.projections.positions import PositionsProjection
from app.schemas.fund import ApprovalRequest, ProposeOrderRequest, StrikeNavRequest

router = APIRouter()

# --- spine wiring (single place to swap the venue) -------------------------
_connector = PaperConnector()
_store = EventStore()
_projection = PositionsProjection(_store)
_nav = NavService(pricer=_connector.price, store=_store, projection=_projection)
_pipeline = CommandPipeline(connector=_connector, nav_service=_nav, store=_store)


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


# --- writes ----------------------------------------------------------------
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
