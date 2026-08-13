"""Broker backfill — repair a book that has drifted from the venue.

Positions and cash are folded from the event log, so when fills execute at the
broker without ever being logged, the book silently understates reality. This
service replays those fills into the log so the fold produces the truth again.

Design rules (learned the hard way on the 2026-08 drift):

* **Idempotent by ``client_order_id``.** Every replayed fill is appended under
  the broker's own coid as ``aggregate_id``. Running twice is a no-op, so a
  partial run can always be re-run safely.
* **Prior synthetic corrections must be reversed, not stacked.** An earlier
  repair adopted positions via ``alpaca_adopt_*`` events that carry no coid and
  overlap the real fills. Replaying the real fills on top would double-count
  them, so each adoption is reversed first.
* **Positions the venue does not have are reversed too.** A fill booked against
  the wrong venue leaves a phantom position that no broker fill can explain.
* **Nothing is inferred.** Quantities, prices and timestamps come from the
  broker's own records; this never invents a number to make a total balance.

``plan()`` is read-only and returns exactly what ``apply()`` would write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f

ADOPT_PREFIX = "alpaca_adopt"
REVERSAL_SUFFIX = "__reconciled"


@dataclass
class PlannedFill:
    """One event the backfill intends to append."""
    aggregate_id: str
    symbol: str
    side: str
    qty: Decimal
    avg_price: Decimal
    reason: str
    ts: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "filled_qty": f(self.qty),
            "avg_price": f(self.avg_price),
            "fees": 0,
            "venue": "alpaca",
            "backfill_reason": self.reason,
        }


@dataclass
class BackfillPlan:
    replay: list[PlannedFill] = field(default_factory=list)
    reversals: list[PlannedFill] = field(default_factory=list)
    skipped_already_logged: list[str] = field(default_factory=list)

    @property
    def all_events(self) -> list[PlannedFill]:
        # reversals first: undo the synthetic corrections before replaying truth
        return self.reversals + self.replay

    def net_by_symbol(self) -> dict[str, Decimal]:
        net: dict[str, Decimal] = {}
        for p in self.all_events:
            signed = p.qty if p.side == "buy" else -p.qty
            net[p.symbol] = net.get(p.symbol, Decimal("0")) + signed
        return net

    def to_dict(self) -> dict[str, Any]:
        return {
            "reversals": [
                {"aggregate_id": p.aggregate_id, "symbol": p.symbol, "side": p.side,
                 "qty": f(p.qty), "avg_price": f(p.avg_price), "reason": p.reason}
                for p in self.reversals
            ],
            "replay": [
                {"aggregate_id": p.aggregate_id, "symbol": p.symbol, "side": p.side,
                 "qty": f(p.qty), "avg_price": f(p.avg_price), "reason": p.reason}
                for p in self.replay
            ],
            "skipped_already_logged": self.skipped_already_logged,
            "net_by_symbol": {k: f(v) for k, v in self.net_by_symbol().items()},
        }


class BrokerBackfill:
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    # --- reading the log ---------------------------------------------------
    def _logged_fills(self) -> tuple[set[str], list[dict[str, Any]], dict[str, str]]:
        """Returns (coids already logged, adopt events, venue by aggregate_id)."""
        seen: set[str] = set()
        adopts: list[dict[str, Any]] = []
        venue_of: dict[str, str] = {}
        seq = 0
        while True:
            batch = self._store.stream(since_seq=seq, limit=1000)
            if not batch:
                break
            for ev in batch:
                seq = max(seq, ev.get("seq", seq))
                etype = str(ev.get("type"))
                agg = str(ev.get("aggregate_id"))
                payload = ev.get("payload") or {}
                if etype == EventType.ORDER_SUBMITTED.value:
                    venue_of[agg] = payload.get("venue", "")
                elif etype == EventType.ORDER_FILLED.value:
                    seen.add(agg)
                    # A reversal is named "<original>__reconciled", so it still
                    # carries the adopt prefix. Without this guard a second run
                    # treats the reversal as another adoption to reverse, and
                    # each run flips the sign again — re-adding the very shares
                    # the first run removed.
                    if agg.startswith(ADOPT_PREFIX) and not agg.endswith(REVERSAL_SUFFIX):
                        adopts.append(ev)
            if len(batch) < 1000:
                break
        return seen, adopts, venue_of

    # --- planning ----------------------------------------------------------
    def plan(
        self,
        broker_fills: Iterable[dict[str, Any]],
        phantom_coids: Iterable[str] = (),
    ) -> BackfillPlan:
        """Read-only. ``broker_fills`` are dicts with
        client_order_id/symbol/side/qty/price (as returned by the venue)."""
        seen, adopts, venue_of = self._logged_fills()
        plan = BackfillPlan()

        # 1. reverse prior synthetic adoptions (they overlap the real fills)
        for ev in adopts:
            agg = str(ev.get("aggregate_id"))
            if f"{agg}{REVERSAL_SUFFIX}" in seen:
                plan.skipped_already_logged.append(f"{agg}{REVERSAL_SUFFIX}")
                continue
            p = ev.get("payload") or {}
            qty = D(p.get("filled_qty", p.get("qty", 0)))
            if abs(qty) < Decimal("1e-9"):
                continue
            side = p.get("side", "buy")
            plan.reversals.append(PlannedFill(
                aggregate_id=f"{agg}{REVERSAL_SUFFIX}",
                symbol=p["symbol"],
                side="sell" if side == "buy" else "buy",
                qty=qty,
                avg_price=D(p["avg_price"]),
                reason=f"reverse synthetic adoption {agg} — superseded by real broker fills",
            ))

        # 2. reverse phantom positions (booked on the wrong venue)
        for coid in phantom_coids:
            rid = f"{coid}{REVERSAL_SUFFIX}"
            if rid in seen:
                plan.skipped_already_logged.append(rid)
                continue
            src = self._find_fill(str(coid))
            if src is None:
                continue
            p = src.get("payload") or {}
            plan.reversals.append(PlannedFill(
                aggregate_id=rid,
                symbol=p["symbol"],
                side="sell" if p.get("side", "buy") == "buy" else "buy",
                qty=D(p.get("filled_qty", p.get("qty", 0))),
                avg_price=D(p["avg_price"]),
                reason=f"reverse phantom fill {coid} — booked on venue "
                       f"'{venue_of.get(str(coid), '?')}' but absent at the broker",
            ))

        # 3. replay every broker fill the log has never seen
        for bf in broker_fills:
            coid = str(bf["client_order_id"])
            if coid in seen:
                plan.skipped_already_logged.append(coid)
                continue
            plan.replay.append(PlannedFill(
                aggregate_id=coid,
                symbol=bf["symbol"],
                side=bf["side"],
                qty=D(str(bf["qty"])),
                avg_price=D(str(bf["price"])),
                reason="fill executed at the broker but never logged",
                ts=bf.get("ts"),
            ))
        return plan

    def _find_fill(self, aggregate_id: str) -> dict[str, Any] | None:
        seq = 0
        while True:
            batch = self._store.stream(since_seq=seq, limit=1000)
            if not batch:
                return None
            for ev in batch:
                seq = max(seq, ev.get("seq", seq))
                if (str(ev.get("type")) == EventType.ORDER_FILLED.value
                        and str(ev.get("aggregate_id")) == aggregate_id):
                    return ev
            if len(batch) < 1000:
                return None

    # --- writing -----------------------------------------------------------
    def apply(self, plan: BackfillPlan, actor: str = "reconciliation") -> dict[str, Any]:
        """Append the planned events. Safe to re-run: coids already present were
        filtered out at plan time, and each event keeps a stable aggregate_id."""
        written = []
        for pf in plan.all_events:
            self._store.append(Event(
                aggregate_id=pf.aggregate_id,
                aggregate_type="order",
                type=EventType.ORDER_FILLED,
                payload=pf.to_payload(),
                actor=actor,
            ))
            written.append(pf.aggregate_id)
        return {"written": len(written), "aggregate_ids": written}
