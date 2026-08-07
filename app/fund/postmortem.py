"""Post-mortem — the closing entry that diffs a thesis against what happened.

Every thesis eventually resolves: it played out, it was invalidated, or it was
just wrong. The post-mortem records that verdict alongside the *realized* P&L of
the trades that referenced the thesis, plus the human's narrative and lessons.
Together these close the loop and accumulate the reasoning dataset a fund learns
from (and that a future Clark can be evaluated against).

P&L is computed from the thesis's own filled orders (mark-to-market total P&L =
net cash flow + net position × current mark), so the number in the post-mortem
is derived from the event log, not typed in by hand. Recording a post-mortem
also moves the thesis to ``reviewed`` — its terminal, audited state.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Callable, Optional

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f
from app.fund.thesis import ThesisService


class Verdict(str, Enum):
    CORRECT = "correct"                    # thesis played out, trade made money
    PARTIALLY_CORRECT = "partially_correct"
    WRONG = "wrong"                        # thesis was mistaken
    INVALIDATED = "invalidated"           # an invalidation condition hit; exited by rule
    TOO_EARLY = "too_early"               # right idea, wrong timing


class PostmortemError(Exception):
    """Invalid post-mortem operation (unknown thesis, bad verdict)."""


class PostmortemService:
    def __init__(self, store: EventStore | None = None,
                 pricer: Callable[[str], float] | None = None):
        self._store = store or EventStore()
        self._price = pricer or (lambda _s: 0.0)
        self._theses = ThesisService(store=self._store)

    def record(self, thesis_id: str, verdict: str, actor: str,
               what_happened: str | None = None,
               lessons: Optional[list[str]] = None) -> dict[str, Any]:
        thesis = self._theses.get(thesis_id)  # raises ThesisError if unknown
        try:
            v = Verdict(verdict)
        except ValueError:
            raise PostmortemError(
                f"unknown verdict '{verdict}' (expected one of {[x.value for x in Verdict]})"
            )
        pnl = self._realized_pnl(thesis)
        pm_id = str(uuid.uuid4())
        payload = {
            "postmortem_id": pm_id,
            "thesis_id": thesis_id,
            "verdict": v.value,
            "outcome_pnl_usd": f(pnl["total_pnl"]),
            "pnl_detail": pnl,
            "what_happened": what_happened,
            "lessons": lessons or [],
            # Snapshot the prediction we're grading, so the diff is self-contained.
            "predicted_claim": thesis.get("claim"),
            "invalidation_conditions": thesis.get("invalidation_conditions") or [],
        }
        self._store.append(
            Event(thesis_id, "thesis", EventType.POSTMORTEM_RECORDED, payload, actor)
        )
        # Move the thesis to its terminal reviewed state (best-effort: a thesis
        # already reviewed just stays there).
        try:
            self._theses.set_status(thesis_id, "reviewed", actor=actor,
                                    note=f"post-mortem: {v.value}")
        except Exception:  # noqa: BLE001 — status may already be terminal
            pass
        return self.get(thesis_id)

    def get(self, thesis_id: str) -> Optional[dict[str, Any]]:
        """The latest post-mortem recorded for a thesis, or None."""
        latest = None
        for e in self._store.by_aggregate(thesis_id):
            if e.get("type") == EventType.POSTMORTEM_RECORDED.value:
                latest = e.get("payload")
        return latest

    # --- P&L from the thesis's own filled orders ---------------------------
    def _realized_pnl(self, thesis: dict) -> dict[str, Any]:
        order_ids = set(thesis.get("order_ids") or [])
        # net cash flow + net qty per symbol, folded from that thesis's fills
        cash_flow = D(0)
        net: dict[str, Any] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            if e.get("type") != EventType.ORDER_FILLED.value:
                continue
            if e.get("aggregate_id") not in order_ids:
                continue
            p = e.get("payload", {}) or {}
            sym = p.get("symbol")
            qty = D(str(p.get("filled_qty", 0) or 0))
            px = D(str(p.get("avg_price", 0) or 0))
            fees = D(str(p.get("fees", 0) or 0))
            signed = qty if p.get("side") == "buy" else -qty
            cash_flow -= signed * px          # buys cost cash, sells return it
            cash_flow -= fees
            slot = net.setdefault(sym, {"qty": D(0)})
            slot["qty"] += signed

        # Mark-to-market the residual net position.
        mtm = D(0)
        positions = []
        for sym, slot in net.items():
            q = slot["qty"]
            mark = D(str(self._price(sym) or 0))
            value = q * mark
            mtm += value
            if abs(q) > D("1e-9"):
                positions.append({"symbol": sym, "net_qty": f(q),
                                  "mark": f(mark), "value_usd": f(value)})

        total = cash_flow + mtm
        return {
            "total_pnl": total,
            "total_pnl_usd": f(total),
            "cash_flow_usd": f(cash_flow),
            "residual_mtm_usd": f(mtm),
            "residual_positions": positions,
            "n_orders": len(order_ids),
        }
