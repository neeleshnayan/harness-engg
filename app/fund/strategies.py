"""Strategy registry — create → backtest → deploy → allocate.

Event-sourced like the rest of the spine, so every deploy and every allocation
change is an auditable event (and reconstructable / forensically replayable).
``StrategyService`` emits the events; ``StrategyRegistry`` folds them into the
current state of each strategy.

The fund is one pooled account — a strategy is a *tag* on orders/fills (see
``strategy_id``), plus a *target allocation* here. Actual exposure and P&L are
computed by ``StrategyAttribution`` folding the tagged fills.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f


class StrategyState(str, Enum):
    DRAFT = "draft"
    BACKTESTED = "backtested"
    DEPLOYED = "deployed"
    PAUSED = "paused"


# Which state transitions are allowed (keeps lifecycle honest).
_ALLOWED = {
    StrategyState.DRAFT: {StrategyState.BACKTESTED, StrategyState.PAUSED},
    StrategyState.BACKTESTED: {StrategyState.DEPLOYED, StrategyState.PAUSED, StrategyState.DRAFT},
    StrategyState.DEPLOYED: {StrategyState.PAUSED},
    StrategyState.PAUSED: {StrategyState.DEPLOYED, StrategyState.DRAFT},
}


class StrategyError(Exception):
    """Invalid strategy operation (unknown id, illegal transition, bad allocation)."""


class StrategyService:
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def register(self, name: str, actor: str, definition: Optional[dict] = None,
                 parent_id: Optional[str] = None) -> dict[str, Any]:
        if parent_id:
            self._require(parent_id)  # a child must attach to an existing strategy (the "container")
        sid = str(uuid.uuid4())
        self._store.append(
            Event(sid, "strategy", EventType.STRATEGY_REGISTERED,
                  {"name": name, "definition": definition or {}, "parent_id": parent_id}, actor)
        )
        return self.get(sid)

    def record_backtest(self, strategy_id: str, results: dict, actor: str) -> dict[str, Any]:
        self._require(strategy_id)
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_BACKTESTED, {"results": results}, actor)
        )
        # A backtest moves a draft to 'backtested'; re-backtesting a later state is fine too.
        cur = StrategyRegistry(self._store).get(strategy_id)
        if cur["state"] == StrategyState.DRAFT.value:
            self._transition(strategy_id, StrategyState.BACKTESTED, actor)
        return self.get(strategy_id)

    def set_state(self, strategy_id: str, state: str, actor: str) -> dict[str, Any]:
        target = StrategyState(state)
        self._transition(strategy_id, target, actor)
        return self.get(strategy_id)

    def rename(self, strategy_id: str, name: str, actor: str) -> dict[str, Any]:
        self._require(strategy_id)
        if not (name or "").strip():
            raise StrategyError("name cannot be empty")
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_RENAMED, {"name": name.strip()}, actor)
        )
        return self.get(strategy_id)

    def set_assets(self, strategy_id: str, symbols: list[str], actor: str) -> dict[str, Any]:
        """Set the universe of symbols this strategy scopes (replaces any previous set)."""
        self._require(strategy_id)
        clean = sorted({s.strip().upper() for s in symbols if s and s.strip()})
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_ASSETS_SET,
                  {"symbols": clean}, actor)
        )
        return self.get(strategy_id)

    def archive(self, strategy_id: str, actor: str) -> dict[str, Any]:
        """Soft-delete: hide from active lists but keep the audit trail."""
        self._require(strategy_id)
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_ARCHIVED, {}, actor)
        )
        return self.get(strategy_id)

    def add_parent(self, strategy_id: str, parent_id: str, actor: str) -> dict[str, Any]:
        """Compose ``strategy_id`` into ``parent_id`` (many-to-many). Guards cycles."""
        self._require(strategy_id)
        self._require(parent_id)
        if parent_id == strategy_id:
            raise StrategyError("a strategy cannot be its own parent")
        # cycle guard: parent must not be a descendant of strategy_id
        if self._is_descendant(parent_id, strategy_id):
            raise StrategyError("that would create a cycle in the strategy graph")
        if parent_id in (self._require(strategy_id).get("parents") or []):
            return self.get(strategy_id)  # already a member — idempotent
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_ADDED_TO_PARENT,
                  {"parent_id": parent_id}, actor)
        )
        return self.get(strategy_id)

    def set_member_weight(self, parent_id: str, child_id: str, weight: Any, actor: str) -> dict[str, Any]:
        self._require(parent_id)
        self._require(child_id)
        if parent_id == child_id:
            raise StrategyError("a strategy cannot be its own parent")
        if self._is_descendant(parent_id, child_id):
            raise StrategyError("that would create a cycle in the strategy graph")
        w = float(D(weight))
        if w < 0:
            raise StrategyError("weight cannot be negative")

        child_rec = self.get(child_id)
        if parent_id not in (child_rec.get("parents") or []):
            self._store.append(
                Event(child_id, "strategy", EventType.STRATEGY_ADDED_TO_PARENT,
                      {"parent_id": parent_id}, actor)
            )

        self._store.append(
            Event(parent_id, "strategy", EventType.STRATEGY_MEMBERSHIP_WEIGHTED,
                  {"child_id": child_id, "weight": w}, actor)
        )
        return self.get(parent_id)

    def set_member_weights(self, parent_id: str, weights: dict[str, Any], actor: str) -> dict[str, Any]:
        self._require(parent_id)
        for cid, weight in weights.items():
            self._require(cid)
            if parent_id == cid:
                raise StrategyError("a strategy cannot be its own parent")
            if self._is_descendant(parent_id, cid):
                raise StrategyError(f"cycle detected between {parent_id} and {cid}")
            w = float(D(weight))
            if w < 0:
                raise StrategyError(f"weight for {cid} cannot be negative")

            child_rec = self.get(cid)
            if parent_id not in (child_rec.get("parents") or []):
                self._store.append(
                    Event(cid, "strategy", EventType.STRATEGY_ADDED_TO_PARENT,
                          {"parent_id": parent_id}, actor)
                )

            self._store.append(
                Event(parent_id, "strategy", EventType.STRATEGY_MEMBERSHIP_WEIGHTED,
                      {"child_id": cid, "weight": w}, actor)
            )
        return self.get(parent_id)

    def remove_parent(self, strategy_id: str, parent_id: str, actor: str) -> dict[str, Any]:
        self._require(strategy_id)
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_REMOVED_FROM_PARENT,
                  {"parent_id": parent_id}, actor)
        )
        return self.get(strategy_id)

    def _is_descendant(self, node: str, ancestor: str) -> bool:
        """True if ``node`` is ``ancestor`` or reachable from it via parent edges."""
        recs = {r["strategy_id"]: r for r in StrategyRegistry(self._store).list()}
        stack, seen = [ancestor], set()
        while stack:
            cur = stack.pop()
            if cur == node:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            # children of cur = strategies whose parents include cur
            stack.extend(sid for sid, r in recs.items() if cur in (r.get("parents") or []))
        return False

    def set_allocation(self, strategy_id: str, target_pct: Any, actor: str) -> dict[str, Any]:
        self._require(strategy_id)
        pct = D(target_pct)
        if pct < 0 or pct > 100:
            raise StrategyError("target_pct must be between 0 and 100")
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_ALLOCATION_SET,
                  {"target_pct": pct}, actor)
        )
        return self.get(strategy_id)

    def get(self, strategy_id: str) -> dict[str, Any]:
        rec = StrategyRegistry(self._store).get(strategy_id)
        if rec is None:
            raise StrategyError(f"unknown strategy {strategy_id}")
        return rec

    def list(self) -> list[dict[str, Any]]:
        return StrategyRegistry(self._store).list()

    # --- internals ---------------------------------------------------------
    def _require(self, strategy_id: str) -> dict[str, Any]:
        rec = StrategyRegistry(self._store).get(strategy_id)
        if rec is None:
            raise StrategyError(f"unknown strategy {strategy_id}")
        return rec

    def _transition(self, strategy_id: str, target: StrategyState, actor: str) -> None:
        rec = self._require(strategy_id)
        cur = StrategyState(rec["state"])
        if target != cur and target not in _ALLOWED[cur]:
            raise StrategyError(f"cannot move strategy from '{cur.value}' to '{target.value}'")
        self._store.append(
            Event(strategy_id, "strategy", EventType.STRATEGY_STATE_CHANGED,
                  {"state": target.value}, actor)
        )


class StrategyRegistry:
    """Projection: current state of every strategy, folded from strategy events."""

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _build(self) -> dict[str, dict[str, Any]]:
        strategies: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            etype = e.get("type")
            sid = e.get("aggregate_id")
            p = e.get("payload", {})
            if etype == EventType.STRATEGY_REGISTERED.value:
                init_parents = [p["parent_id"]] if p.get("parent_id") else []
                strategies[sid] = {
                    "strategy_id": sid,
                    "name": p.get("name"),
                    "state": StrategyState.DRAFT.value,
                    "allocation_pct": Decimal("0"),
                    "definition": p.get("definition", {}),
                    "parents": init_parents,
                    "archived": False,
                    "backtest": None,
                    "assets": [],
                    "members": [],
                    "member_weights": {},
                }
            elif sid in strategies:
                if etype == EventType.STRATEGY_STATE_CHANGED.value:
                    strategies[sid]["state"] = p["state"]
                elif etype == EventType.STRATEGY_ALLOCATION_SET.value:
                    strategies[sid]["allocation_pct"] = D(p["target_pct"])
                elif etype == EventType.STRATEGY_BACKTESTED.value:
                    strategies[sid]["backtest"] = p.get("results")
                elif etype == EventType.STRATEGY_RENAMED.value:
                    strategies[sid]["name"] = p.get("name")
                elif etype == EventType.STRATEGY_ARCHIVED.value:
                    strategies[sid]["archived"] = True
                elif etype == EventType.STRATEGY_ADDED_TO_PARENT.value:
                    pid = p.get("parent_id")
                    if pid and pid not in strategies[sid]["parents"]:
                        strategies[sid]["parents"].append(pid)
                elif etype == EventType.STRATEGY_MEMBERSHIP_WEIGHTED.value:
                    cid = p.get("child_id")
                    if cid and "weight" in p:
                        strategies[sid].setdefault("_raw_member_weights", {})[cid] = float(p["weight"])
                elif etype == EventType.STRATEGY_ASSETS_SET.value:
                    strategies[sid]["assets"] = p.get("symbols", [])
                elif etype == EventType.STRATEGY_REMOVED_FROM_PARENT.value:
                    pid = p.get("parent_id")
                    if pid in strategies[sid]["parents"]:
                        strategies[sid]["parents"].remove(pid)
                    if pid in strategies and sid in strategies[pid].get("_raw_member_weights", {}):
                        del strategies[pid]["_raw_member_weights"][sid]

        for pid, rec in strategies.items():
            raw_w = rec.get("_raw_member_weights", {})
            members = []
            for cid, child_rec in strategies.items():
                if pid in child_rec.get("parents", []):
                    w = raw_w.get(cid, 0.0)
                    members.append({
                        "child_id": cid,
                        "name": child_rec.get("name"),
                        "weight": round(float(w), 4)
                    })
            rec["members"] = members
            rec["member_weights"] = {m["child_id"]: m["weight"] for m in members}

        return strategies

    @staticmethod
    def _view(rec: dict[str, Any]) -> dict[str, Any]:
        parents = rec.get("parents") or []
        # parent_id kept for back-compat (first parent); parents is the full set.
        return {**rec, "allocation_pct": f(rec["allocation_pct"]),
                "parent_id": parents[0] if parents else None}

    def get(self, strategy_id: str) -> Optional[dict[str, Any]]:
        rec = self._build().get(strategy_id)
        return self._view(rec) if rec else None

    def list(self) -> list[dict[str, Any]]:
        return [self._view(r) for r in self._build().values()]
