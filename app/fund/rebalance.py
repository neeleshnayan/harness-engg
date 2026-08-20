"""Rebalance as a reviewable plan, not a button.

A rebalance is a *batch* of orders decided as one thing. Approving nine buys
individually is not the same act of judgement as approving the shape of the
book, so the plan is the unit that gets proposed, analysed and approved — and it
is event-sourced, so "who changed the fund's shape, when, on what evidence"
answers itself.

The queue exists to create a gap between deciding and doing. That gap is where
the analysis happens, and it introduces the one hazard worth engineering
against: **the world moves while a plan sits.** A plan built at 10:00 against
10:00 prices is a different plan at 15:00. So approval never trusts the proposal:

  * every order is re-priced at approval and the drift is reported
  * the kill switch is re-checked
  * every order still passes the pre-trade risk gate individually — plan
    approval authorises the *intent*, it does not bypass the gate
  * an order that now breaches is rejected and named, and the rest still go

Sells are placed before buys. A rebalance that buys first can breach the cash
floor mid-batch and have its own buys rejected, which would leave the book in a
state nobody chose.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.fund.connectors.base import Order, Side
from app.fund.events import Event, EventStore, EventType

#: Ignore rounding dust. Below this a "rebalance" is churn: commission-free or
#: not, it moves nothing and clutters the queue.
MIN_TRADE_USD = 5.0

#: Plans older than this are stale enough that the prices behind the analysis
#: are not the prices you would trade at. Not a hard block — a stated warning.
STALE_AFTER_MINUTES = 120

#: Share-count tolerance when comparing a strategy's attributed position against
#: the authoritative fold. Both sides are Decimal folds of the same integers and
#: fractional-share fills carry six decimals, so anything above this is a real
#: disagreement, not arithmetic.
ATTRIBUTION_TOLERANCE_QTY = 1e-6


class RebalanceError(Exception):
    """Raised when a plan cannot be built or acted on."""


class AttributionMismatch(RebalanceError):
    """Per-strategy attribution disagrees with the authoritative position fold.

    Refused rather than warned. Measured incident (2026-08-20): a GLD BUY at
    402.18 tagged to one strategy and the matching SELL at 100.00 tagged to
    another left a phantom +0.424471 long and a phantom −0.424471 short that
    net to zero in the book and never net out per strategy. A preview targeting
    the phantom-long strategy at 20% produced a **$376.84 BUY into a symbol the
    fund holds none of**, with ``current_usd: 0.0`` and zero warnings — the
    only tell on the page was a zero. See
    docs/AUDIT_R6_D2_ATTRIBUTION_2026-08-20.md ITEM 3.
    """


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RebalanceService:
    def __init__(self, nav_service, pricer: Callable[[str], float],
                 attribution, strategies, pipeline, control,
                 risk_engine=None, store: EventStore | None = None):
        self._nav = nav_service
        self._price = pricer
        self._attr = attribution
        self._strategies = strategies
        self._pipeline = pipeline
        self._control = control
        self._risk = risk_engine
        self._store = store or EventStore()

    def _venue(self) -> str:
        connector = getattr(self._pipeline, "_connector", None)
        return getattr(connector, "name", "paper") or "paper"

    # --- building -----------------------------------------------------------
    def _authoritative_qty(self) -> dict[str, float]:
        """Symbol -> share count from the fold NAV itself uses.

        Unreadable is not "empty": if the fold cannot be read the guard has no
        reference and must say so rather than wave every strategy through.
        """
        book = self._nav.book()          # raises if the fold is unreadable
        out: dict[str, float] = {}
        for sym, pos in (book.positions or {}).items():
            try:
                out[str(sym).upper()] = float(pos["qty"])
            except (TypeError, ValueError, KeyError):
                continue
        return out

    def _check_attribution(self, rows: list[dict[str, Any]]) -> None:
        """Refuse any strategy whose attributed position the book cannot back.

        Two conditions, both of which the phantom breaks and neither of which a
        correctly-tagged book can. For every symbol a strategy claims:

          * the book must hold the symbol in the SAME DIRECTION — a strategy
            cannot be long what the fund is flat or short;
          * the strategy's share count must not EXCEED the book's — a strategy
            cannot own more of a symbol than the fund holds.

        Two strategies splitting one holding pass both. A mistagged fill fails
        on the first, and it fails for both sides of the pair, which is the
        point: the general fix catches every future mistag, not this one.
        """
        book_qty = self._authoritative_qty()
        problems: list[str] = []
        for row in rows:
            sid = row.get("strategy_id")
            for sym, qty in (row.get("positions") or {}).items():
                symbol = str(sym).upper()
                try:
                    q = float(qty)
                except (TypeError, ValueError):
                    continue
                if abs(q) <= ATTRIBUTION_TOLERANCE_QTY:
                    continue
                held = book_qty.get(symbol, 0.0)
                if abs(held) <= ATTRIBUTION_TOLERANCE_QTY:
                    problems.append(
                        f"{sid} is attributed {q:+.6f} {symbol} but the fund holds "
                        f"none — a fill was tagged to a strategy that did not trade it"
                    )
                elif (q > 0) != (held > 0):
                    problems.append(
                        f"{sid} is attributed {q:+.6f} {symbol} against a book "
                        f"position of {held:+.6f} — opposite directions"
                    )
                elif abs(q) > abs(held) + ATTRIBUTION_TOLERANCE_QTY:
                    problems.append(
                        f"{sid} is attributed {q:+.6f} {symbol} but the fund holds "
                        f"only {held:+.6f} in total"
                    )
        if problems:
            raise AttributionMismatch(
                "per-strategy attribution disagrees with the fund's own position "
                "fold, so a plan built from it would size orders against holdings "
                "that do not exist: " + "; ".join(sorted(problems))
                + ". Correct the attribution with a StrategyAttributionCorrected "
                  "event (the log stays append-only) and rebuild."
            )

    def _composition(self) -> dict[str, dict[str, float]]:
        """Current USD exposure per strategy per symbol.

        Guarded: this is the read that turns a mistagged fill into money (see
        ``AttributionMismatch``), so the disagreement is checked here rather
        than at the one call site that happens to have caused an incident.
        """
        rows = self._attr.with_values(self._price)
        self._check_attribution(rows)
        comp: dict[str, dict[str, float]] = {}
        for row in rows:
            sid, vals = row.get("strategy_id"), {}
            for sym, qty in (row.get("positions") or {}).items():
                try:
                    q, px = float(qty), float(self._price(str(sym).upper()))
                except (TypeError, ValueError):
                    continue
                if abs(q) > 1e-9 and px > 0:
                    vals[str(sym).upper()] = q * px
            if sid and vals:
                comp[sid] = vals
        return comp

    def build(self, targets: dict[str, float]) -> dict[str, Any]:
        """Turn strategy targets into the concrete order list. Writes nothing.

        Each strategy keeps its current internal composition and is only
        resized — the same assumption the risk what-if makes, stated here too. A
        strategy with no holdings has no composition to scale and is reported as
        unallocatable rather than being given an invented one.
        """
        nav = float(self._nav.compute().total_nav_usd)
        if nav <= 0:
            raise RebalanceError("NAV is zero — nothing to rebalance")

        self._refuse_archived(targets)
        comp = self._composition()

        # A strategy that has never traded has no composition to scale — but it
        # does have a declared universe, and refusing to size a newly promoted
        # strategy would mean research could never actually reach the book. Fall
        # back to equal weight across its declared assets, and say so: this is an
        # assumption about intent, not a measurement.
        assumed: list[str] = []
        for sid, t in targets.items():
            if not t or sid in comp:
                continue
            assets = self._declared_assets(sid)
            priced = {}
            for sym in assets:
                try:
                    px = float(self._price(sym))
                except (TypeError, ValueError):
                    continue
                if px > 0:
                    priced[sym] = 1.0        # equal weight; scaled to target below
            if priced:
                comp[sid] = priced
                assumed.append(sid)

        unallocatable = [sid for sid, t in targets.items() if t and sid not in comp]

        desired: dict[str, float] = {}
        owner: dict[str, str] = {}          # symbol -> strategy that carries it
        for sid, target_pct in targets.items():
            book = comp.get(sid)
            if not book:
                continue
            total = sum(book.values())
            if total <= 0:
                continue
            target_usd = nav * (float(target_pct) / 100.0)
            for sym, usd in book.items():
                desired[sym] = desired.get(sym, 0.0) + target_usd * (usd / total)
                owner.setdefault(sym, sid)

        current: dict[str, float] = {}
        for sid, book in comp.items():
            for sym, usd in book.items():
                current[sym] = current.get(sym, 0.0) + usd

        orders: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for sym in sorted(set(desired) | set(current)):
            cur, want = current.get(sym, 0.0), desired.get(sym, 0.0)
            delta = want - cur
            if abs(delta) < MIN_TRADE_USD:
                if abs(delta) > 1e-9:
                    skipped.append({"symbol": sym, "delta_usd": round(delta, 2),
                                    "reason": f"below the ${MIN_TRADE_USD:.0f} minimum trade"})
                continue
            try:
                px = float(self._price(sym))
            except (TypeError, ValueError):
                px = 0.0
            if px <= 0:
                skipped.append({"symbol": sym, "delta_usd": round(delta, 2),
                                "reason": "no live price"})
                continue
            orders.append({
                "symbol": sym,
                "side": "buy" if delta > 0 else "sell",
                "qty": round(abs(delta) / px, 4),
                "est_price": round(px, 4),
                "notional_usd": round(abs(delta), 2),
                "current_usd": round(cur, 2),
                "target_usd": round(want, 2),
                "strategy_id": owner.get(sym),
            })

        # Sells first: they raise the cash the buys need.
        orders.sort(key=lambda o: (0 if o["side"] == "sell" else 1, -o["notional_usd"]))

        gross_after = sum(desired.values())
        cash_after_pct = (nav - gross_after) / nav * 100.0

        # Check the *destination* against the mandate, not just each order.
        #
        # The pre-trade gate sees one order at a time and enforces position size,
        # order notional and the cash floor. It cannot see that nine individually
        # legal orders add up to a strategy weight above its cap — so a rebalance
        # could walk the book into a standing breach that only alarms afterwards.
        # A limit you discover you have broken is not a limit.
        limit_warnings: list[str] = []
        try:
            lim = self._control.limits()
        except Exception:  # noqa: BLE001 — unreadable limits must not block a preview
            lim = None
        if lim is not None:
            cap = lim.max_strategy_pct * 100.0
            for sid, t in targets.items():
                if float(t) > cap:
                    name = self._strategy_name(sid)
                    limit_warnings.append(
                        f"{name} would be {float(t):.1f}% of NAV, above the "
                        f"{cap:.0f}% strategy cap — the orders will fill and the "
                        f"book will sit in breach"
                    )
            floor = lim.min_cash_pct * 100.0
            if cash_after_pct < floor:
                limit_warnings.append(
                    f"cash would land at {cash_after_pct:.1f}%, below the {floor:.0f}% "
                    "floor — the gate will reject the buys that cross it, so this "
                    "would only partly fill"
                )

        return {
            "targets": {k: float(v) for k, v in targets.items()},
            "orders": orders,
            "skipped": skipped,
            "unallocatable": unallocatable,
            "equal_weighted_strategies": assumed,
            "limit_warnings": limit_warnings,
            "nav_usd": round(nav, 2),
            "cash_after_usd": round(nav - gross_after, 2),
            "cash_after_pct": round(cash_after_pct, 2),
            "turnover_usd": round(sum(o["notional_usd"] for o in orders), 2),
            "turnover_pct": round(sum(o["notional_usd"] for o in orders) / nav * 100.0, 2),
            "assumption": (
                "each strategy keeps its current internal composition and is only resized"
                + (f"; {len(assumed)} strategy with no holdings yet is assumed equal-weight "
                   "across its declared universe" if assumed else "")
            ),
        }

    def _refuse_archived(self, targets: dict[str, float]) -> None:
        """An archived strategy is not a rebalance target.

        Archive was cosmetic: the flag was folded, rendered, and enforced by
        nothing, so a strategy retired this morning was still an accepted
        target this afternoon (same audit, ITEM 3(b)). A zero target is allowed
        — winding an archived strategy DOWN is exactly what archiving means.

        The registry being unreadable is not "nothing is archived": the check
        cannot be made, so the plan is refused rather than built blind.
        """
        wanted = {sid for sid, t in (targets or {}).items() if t}
        if not wanted:
            return
        try:
            registry = list(self._strategies.list())
        except Exception as e:  # noqa: BLE001
            raise RebalanceError(
                "the strategy registry could not be read, so whether these "
                f"targets are archived is UNKNOWN ({type(e).__name__}) — refusing "
                "to build a plan on an unchecked target list"
            ) from e
        archived = sorted(
            s.get("strategy_id") for s in registry
            if s.get("strategy_id") in wanted and s.get("archived")
        )
        if archived:
            raise RebalanceError(
                "archived strategies cannot be given a non-zero target: "
                + ", ".join(f"{self._strategy_name(sid)} ({sid})" for sid in archived)
                + " — unarchive it, or target it at 0% to wind it down"
            )

    def _declared_assets(self, sid: str) -> list[str]:
        """The universe a strategy scopes, whether or not it has traded it."""
        try:
            for st in self._strategies.list():
                if st.get("strategy_id") == sid:
                    return [str(a).upper() for a in (st.get("assets") or [])]
        except Exception:  # noqa: BLE001
            pass
        return []

    def _strategy_name(self, sid: str) -> str:
        try:
            for s in self._strategies.list():
                if s.get("strategy_id") == sid:
                    return s.get("name") or sid
        except Exception:  # noqa: BLE001
            pass
        return sid

    # --- propose ------------------------------------------------------------
    def propose(self, targets: dict[str, float], actor: str,
                note: str | None = None) -> dict[str, Any]:
        plan = self.build(targets)
        if not plan["orders"]:
            raise RebalanceError(
                "this allocation is already in place — no orders would be generated"
            )

        # Snapshot the risk mechanics AT PROPOSAL TIME so the reviewer sees the
        # evidence the proposer acted on, not a recomputation that may since
        # have moved. The approval screen recomputes separately and shows both.
        mechanics = None
        if self._risk is not None:
            try:
                w = self._risk.what_if(targets)
                if w.get("measurable"):
                    mechanics = {
                        "before": {k: w["before"].get(k) for k in
                                   ("effective_bets", "portfolio_vol_pct",
                                    "stressed_vol_pct", "expected_shortfall_usd",
                                    "gross_exposure_pct_of_nav")},
                        "after": {k: w["after"].get(k) for k in
                                  ("effective_bets", "portfolio_vol_pct",
                                   "stressed_vol_pct", "expected_shortfall_usd",
                                   "gross_exposure_pct_of_nav")},
                        "deltas": w.get("deltas"),
                    }
                else:
                    mechanics = {"measurable": False, "reason": w.get("reason")}
            except Exception as e:  # noqa: BLE001 — analysis must not block proposing
                mechanics = {"measurable": False,
                             "reason": f"risk analysis unavailable ({type(e).__name__})"}

        plan_id = str(uuid.uuid4())
        payload = {**plan, "plan_id": plan_id, "note": note,
                   "mechanics": mechanics, "proposed_at": _now(), "proposed_by": actor}
        self._store.append(Event(
            aggregate_id=plan_id, aggregate_type="rebalance",
            type=EventType.REBALANCE_PROPOSED, payload=payload, actor=actor,
        ))
        return {"status": "pending_approval", **payload}

    # --- queue --------------------------------------------------------------
    def _fold(self) -> dict[str, dict[str, Any]]:
        plans: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            t, p = e.get("type"), (e.get("payload") or {})
            pid = p.get("plan_id") or e.get("aggregate_id")
            if not pid:
                continue
            if t == EventType.REBALANCE_PROPOSED.value:
                plans[pid] = {**p, "status": "pending_approval"}
            elif t == EventType.REBALANCE_APPROVED.value and pid in plans:
                plans[pid] = {**plans[pid], "status": "approved", "outcome": p}
            elif t == EventType.REBALANCE_DECLINED.value and pid in plans:
                plans[pid] = {**plans[pid], "status": "declined", "outcome": p}
        return plans

    def pending(self) -> list[dict[str, Any]]:
        out = [p for p in self._fold().values() if p["status"] == "pending_approval"]
        out.sort(key=lambda p: p.get("proposed_at") or "", reverse=True)
        return [self._decorate(p) for p in out]

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        out = [p for p in self._fold().values() if p["status"] != "pending_approval"]
        out.sort(key=lambda p: p.get("proposed_at") or "", reverse=True)
        return out[:limit]

    def get(self, plan_id: str) -> dict[str, Any]:
        plan = self._fold().get(plan_id)
        if not plan:
            raise RebalanceError(f"no rebalance plan {plan_id}")
        return self._decorate(plan) if plan["status"] == "pending_approval" else plan

    def _decorate(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Attach what has changed since the plan was written.

        This is the whole point of a queue with a gap in it. A reviewer needs to
        know that the analysis they are reading is describing a book that no
        longer exists.
        """
        age_min = None
        try:
            proposed = datetime.fromisoformat(plan["proposed_at"])
            age_min = (datetime.now(timezone.utc) - proposed).total_seconds() / 60.0
        except (KeyError, TypeError, ValueError):
            pass

        drift: list[dict[str, Any]] = []
        worst = 0.0
        for o in plan.get("orders", []):
            try:
                now_px = float(self._price(o["symbol"]))
            except (TypeError, ValueError):
                continue
            was = float(o.get("est_price") or 0)
            if was > 0 and now_px > 0:
                move = (now_px - was) / was * 100.0
                worst = max(worst, abs(move))
                if abs(move) >= 0.5:
                    drift.append({"symbol": o["symbol"], "est_price": was,
                                  "price_now": round(now_px, 4),
                                  "move_pct": round(move, 2)})

        # Limit warnings were computed when the plan was written; recompute them
        # now, because the limits themselves may have been changed since.
        warnings: list[str] = []
        try:
            warnings.extend(self.build(plan.get("targets") or {}).get("limit_warnings") or [])
        except Exception:  # noqa: BLE001 — a decoration failure must not hide the plan
            warnings.extend(plan.get("limit_warnings") or [])
        if age_min is not None and age_min > STALE_AFTER_MINUTES:
            warnings.append(
                f"proposed {age_min/60:.1f} hours ago — the analysis below describes "
                "prices from then, not now"
            )
        if drift:
            warnings.append(
                f"{len(drift)} holding(s) have moved more than 0.5% since this plan was "
                f"written (worst {worst:.1f}%); order sizes will be recomputed on approval"
            )
        if self._control.is_halted():
            warnings.append("trading is HALTED — buys in this plan will be rejected")

        return {**plan, "age_minutes": round(age_min, 1) if age_min is not None else None,
                "price_drift": drift, "warnings": warnings}

    # --- act ----------------------------------------------------------------
    def decline(self, plan_id: str, actor: str, reason: str | None = None) -> dict[str, Any]:
        plan = self._fold().get(plan_id)
        if not plan:
            raise RebalanceError(f"no rebalance plan {plan_id}")
        if plan["status"] != "pending_approval":
            raise RebalanceError(f"plan {plan_id} is already {plan['status']}")
        self._store.append(Event(
            aggregate_id=plan_id, aggregate_type="rebalance",
            type=EventType.REBALANCE_DECLINED,
            payload={"plan_id": plan_id, "reason": reason, "declined_at": _now(),
                     "declined_by": actor},
            actor=actor,
        ))
        return {"status": "declined", "plan_id": plan_id, "reason": reason}

    def approve(self, plan_id: str, approver: str,
                allow_self_approval: bool = True) -> dict[str, Any]:
        """Push the plan. Re-prices, re-gates, and reports exactly what happened.

        The order list is rebuilt from the plan's *targets* rather than replayed
        from its stored quantities: quantities were computed against prices that
        are now old, and filling a stale quantity would land the book somewhere
        nobody chose. The targets are the decision; the quantities were only ever
        an implementation of them.
        """
        plan = self._fold().get(plan_id)
        if not plan:
            raise RebalanceError(f"no rebalance plan {plan_id}")
        if plan["status"] != "pending_approval":
            raise RebalanceError(f"plan {plan_id} is already {plan['status']}")

        proposer = plan.get("proposed_by")
        self_approved = bool(proposer and proposer == approver)
        if self_approved and not allow_self_approval:
            raise RebalanceError(
                f"{approver} proposed this plan and cannot also approve it"
            )

        rebuilt = self.build(plan.get("targets") or {})
        placed, rejected = [], []
        for o in rebuilt["orders"]:
            order = Order(
                venue=self._venue(),
                symbol=o["symbol"],
                side=Side.BUY if o["side"] == "buy" else Side.SELL,
                qty=float(o["qty"]),
                strategy_id=o.get("strategy_id"),
            )
            try:
                res = self._pipeline.propose_order(order, actor=f"rebalance:{approver}")
            except Exception as e:  # noqa: BLE001 — one bad order must not abort the batch
                rejected.append({**o, "breaches": [f"{type(e).__name__}: {e}"]})
                continue
            if res.get("status") != "pending_approval":
                rejected.append({**o, "breaches": res.get("breaches") or [res.get("status")]})
                continue
            try:
                self._pipeline.approve_order(res["order_id"], approver=approver)
                placed.append({**o, "order_id": res["order_id"]})
            except Exception as e:  # noqa: BLE001
                rejected.append({**o, "order_id": res.get("order_id"),
                                 "breaches": [f"{type(e).__name__}: {e}"]})

        # Record the intent too, so the strategy targets reflect the decision
        # even where an order could not be filled.
        for sid, pct in (plan.get("targets") or {}).items():
            try:
                self._strategies.set_allocation(sid, float(pct), actor=approver)
            except Exception:  # noqa: BLE001 — allocation intent is secondary to the fills
                pass

        outcome = {
            "plan_id": plan_id,
            "approved_at": _now(),
            "approved_by": approver,
            "self_approved": self_approved,
            "placed": placed,
            "rejected": rejected,
            "n_placed": len(placed),
            "n_rejected": len(rejected),
            "turnover_usd": round(sum(o["notional_usd"] for o in placed), 2),
            "repriced": True,
        }
        self._store.append(Event(
            aggregate_id=plan_id, aggregate_type="rebalance",
            type=EventType.REBALANCE_APPROVED, payload=outcome, actor=approver,
        ))
        return {"status": "approved", **outcome}
