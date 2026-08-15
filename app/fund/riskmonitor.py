"""Risk monitor & controls — continuous surveillance + the kill switch.

Two responsibilities, both deterministic and event-sourced:

  RiskControl  — the auditable *state*: current limits (RiskLimitsSet) and the
                 halt flag (TradingHalted / TradingResumed), folded from events.
  RiskMonitor  — the continuous *evaluation*: `assess()` produces the full risk
                 picture (the observability pane); `run()` is the periodic tick
                 that persists alarm events (dedup), and auto-halts on a drawdown
                 or daily-loss breach.

Everything reads live truth (NAV, positions, marks, attribution) — the monitor
never keeps its own copy. Alarms are events so the audit trail shows exactly what
tripped, when, at what value vs. which threshold.
"""

from __future__ import annotations

import time

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.fund.events import Event, EventStore, EventType
from app.fund.projections.nav import NavService
from app.fund.projections.positions import PositionsProjection
from app.fund.projections.strategy import StrategyAttribution
from app.fund.risk import RiskLimits
from app.fund.strategies import StrategyRegistry


# Severity ordering for the UI + alarm sorting.
SEVERITY = ("info", "warn", "critical")


@dataclass
class Alarm:
    """One breach. `key` (e.g. 'drawdown' or 'concentration:AAPL') dedups across
    ticks so a standing breach is raised once and cleared once."""
    key: str
    type: str            # drawdown | daily_loss | concentration | cash_floor | underwater | strategy_cap
    severity: str        # one of SEVERITY
    message: str         # human-readable, e.g. "AAPL is 27% of NAV (limit 20%)"
    metric: float        # the observed value
    threshold: float     # the limit it crossed
    symbol: Optional[str] = None
    strategy_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "metric": self.metric,
            "threshold": self.threshold,
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
        }


class RiskControl:
    """Auditable limits + kill-switch state, folded from the event log."""

    #: seconds a read-path fold may be reused. The trade path never uses it.
    CACHE_TTL_SECONDS = 5.0

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()
        self._cache: tuple[float, dict[str, Any]] | None = None

    def _fold(self, fresh: bool = False) -> dict[str, Any]:
        """Fold limits, halt state and alarms in ONE pass.

        These were four separate full-log scans, and ``/fund/risk/monitor`` —
        polled continuously by the risk bar on every page — paid for all of
        them on every request. On a nearly-empty project that alone exhausted
        the Firestore read quota.

        The result is cached briefly for reads. Anything that gates a trade must
        pass ``fresh=True``: a stale "not halted" could let an order through
        after the kill switch engaged, which is the one staleness we will not
        accept.
        """
        if not fresh and self._cache is not None:
            age = time.monotonic() - self._cache[0]
            if age < self.CACHE_TTL_SECONDS:
                return self._cache[1]

        limits = RiskLimits()
        halted = False
        active: dict[str, dict] = {}
        history: list[dict] = []

        for e in self._store.stream(since_seq=0, limit=100_000):
            etype = e.get("type")
            p = e.get("payload", {}) or {}
            if etype == EventType.RISK_LIMITS_SET.value:
                limits = RiskLimits.from_dict(p)
            elif etype == EventType.TRADING_HALTED.value:
                halted = True
            elif etype == EventType.TRADING_RESUMED.value:
                halted = False
            elif etype == EventType.RISK_ALARM_RAISED.value:
                history.append(e)
                if p.get("key"):
                    active[p["key"]] = p
            elif etype == EventType.RISK_ALARM_CLEARED.value:
                history.append(e)
                if p.get("key"):
                    active.pop(p["key"], None)

        state = {"limits": limits, "halted": halted, "active": active, "history": history}
        self._cache = (time.monotonic(), state)
        return state

    def _invalidate(self) -> None:
        self._cache = None

    def limits(self) -> RiskLimits:
        """Latest RiskLimitsSet folded over defaults (RiskLimits())."""
        return self._fold()["limits"]

    def set_limits(self, patch: dict, actor: str) -> RiskLimits:
        """Emit RISK_LIMITS_SET (merge patch onto current) and return the result."""
        cur_dict = self.limits().to_dict()
        cur_dict.update(patch or {})
        res = RiskLimits.from_dict(cur_dict)
        self._invalidate()
        self._store.append(
            Event(
                aggregate_id="fund",
                aggregate_type="fund",
                type=EventType.RISK_LIMITS_SET,
                payload=res.to_dict(),
                actor=actor,
            )
        )
        return res

    def is_halted(self, fresh: bool = True) -> bool:
        """True if the last of TradingHalted/TradingResumed is a halt.

        Defaults to a FRESH read: this gates trading, and a stale "not halted"
        would be the one cache miss that actually costs money.
        """
        return self._fold(fresh=fresh)["halted"]

    def halt(self, reason: str, actor: str) -> dict:
        """Engage the kill switch (idempotent: no-op if already halted)."""
        if self.is_halted():
            return {"status": "already_halted", "reason": reason, "halted": True}
        self._store.append(
            Event(
                aggregate_id="fund",
                aggregate_type="fund",
                type=EventType.TRADING_HALTED,
                payload={"reason": reason},
                actor=actor,
            )
        )
        self._invalidate()
        return {"status": "halted", "reason": reason, "halted": True}

    def resume(self, actor: str) -> dict:
        """Re-enable trading (human only)."""
        if not self.is_halted():
            return {"status": "not_halted", "halted": False}
        self._store.append(
            Event(
                aggregate_id="fund",
                aggregate_type="fund",
                type=EventType.TRADING_RESUMED,
                payload={},
                actor=actor,
            )
        )
        self._invalidate()
        return {"status": "resumed", "halted": False}

    def active_alarms(self) -> list[dict]:
        """Currently-open alarms: RISK_ALARM_RAISED not yet followed by a CLEARED
        for the same key, newest first."""
        return list(reversed(list(self._fold()["active"].values())))

    def alarm_history(self, limit: int = 100) -> list[dict]:
        """Recent alarm events (raised + cleared), newest first — the audit feed."""
        return list(reversed(self._fold()["history"][-limit:]))


class RiskMonitor:
    def __init__(self, nav_service: NavService, store: EventStore | None = None,
                 pricer: Callable[[str], float] | None = None,
                 attribution: Any | None = None,
                 strategies: Any | None = None,
                 control: RiskControl | None = None):
        self._nav = nav_service
        self._store = store or EventStore()
        self._price = pricer or (lambda _s: 0.0)
        self._attr = attribution        # StrategyAttribution (per-strategy exposure/pnl)
        self._strategies = strategies    # StrategyService (names, limits context)
        self._control = control or RiskControl(self._store)

    def assess(self) -> dict[str, Any]:
        """The full current risk picture — Rushi's single pane of glass."""
        limits_obj = self._control.limits()
        limits_dict = limits_obj.to_dict()

        snap = self._nav.compute()
        nav_usd = float(snap.total_nav_usd)
        cash_usd = float(snap.breakdown.get("cash", 0))
        cash_pct = (cash_usd / nav_usd * 100.0) if nav_usd > 0 else (100.0 if cash_usd > 0 else 0.0)
        gross_exposure_usd = float(snap.breakdown.get("positions", 0))
        gross_exposure_pct = (gross_exposure_usd / nav_usd * 100.0) if nav_usd > 0 else 0.0
        halted = self._control.is_halted()

        # Drawdown calculation
        history_snaps = self._nav.history(365)
        nav_series = [float(s.get("total_nav_usd", 0)) for s in history_snaps if s.get("total_nav_usd") is not None]
        nav_series.append(nav_usd)
        peak_nav = max(nav_series) if nav_series else nav_usd
        drawdown_pct = ((peak_nav - nav_usd) / peak_nav * 100.0) if peak_nav > 0 else 0.0

        running_peak = 0.0
        max_drawdown_pct = 0.0
        for n in nav_series:
            if n > running_peak:
                running_peak = n
            if running_peak > 0:
                dd = (running_peak - n) / running_peak * 100.0
                if dd > max_drawdown_pct:
                    max_drawdown_pct = dd

        limit_pct = limits_obj.max_drawdown_pct * 100.0
        dd_utilization = (drawdown_pct / limit_pct) if limit_pct > 0 else 0.0

        drawdown = {
            "peak_nav": round(peak_nav, 2),
            "current_nav": round(nav_usd, 2),
            "drawdown_pct": round(drawdown_pct, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "limit_pct": round(limit_pct, 4),
            "utilization": round(dd_utilization, 4),
        }

        # Positions (per-asset risk)
        book = PositionsProjection(self._store).build()
        positions_list: list[dict[str, Any]] = []
        unpriced: list[str] = []
        for sym, pos in book.positions.items():
            qty = float(pos["qty"])
            if abs(qty) < 1e-9:
                continue
            # A single symbol the feed cannot price must not 500 the entire risk
            # monitor — the risk bar polls this on every page. Drop the name,
            # name it, and let the rest of the picture render.
            try:
                mark = float(self._price(sym))
            except Exception:  # noqa: BLE001
                unpriced.append(sym)
                continue
            val = qty * mark
            weight_pct = (val / nav_usd * 100.0) if nav_usd > 0 else 0.0
            avg_cost = float(pos.get("avg_price", 0))
            unrealized_pnl_pct = ((mark - avg_cost) / avg_cost * 100.0) if avg_cost > 0 else 0.0
            shock_20_usd = val * -0.20
            positions_list.append({
                "symbol": sym,
                "qty": qty,
                "mark": mark,
                "value_usd": round(val, 2),
                "weight_pct": round(weight_pct, 4),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 4),
                "shock_20_usd": round(shock_20_usd, 2),
            })
        positions_list.sort(key=lambda p: p["value_usd"], reverse=True)

        worst_position = min(positions_list, key=lambda p: p["unrealized_pnl_pct"]) if positions_list else None

        # Strategies (per-strategy risk)
        attr = self._attr or StrategyAttribution(self._store)
        attr_rows = attr.with_values(self._price)
        reg = StrategyRegistry(self._store)
        reg_map = {s["strategy_id"]: s.get("name", s["strategy_id"]) for s in reg.list()}

        max_strat_limit_pct = limits_obj.max_strategy_pct * 100.0
        strategies_list: list[dict[str, Any]] = []
        for r in attr_rows:
            sid = r["strategy_id"]
            name = reg_map.get(sid, "Discretionary" if sid == "discretionary" else sid)
            exp = float(r["exposure_usd"])
            pnl = float(r["pnl_usd"])
            weight_pct = (exp / nav_usd * 100.0) if nav_usd > 0 else 0.0
            utilization = (weight_pct / max_strat_limit_pct) if max_strat_limit_pct > 0 else 0.0
            breach = weight_pct > max_strat_limit_pct
            strategies_list.append({
                "strategy_id": sid,
                "name": name,
                "exposure_usd": round(exp, 2),
                "weight_pct": round(weight_pct, 4),
                "pnl_usd": round(pnl, 2),
                "limit_pct": round(max_strat_limit_pct, 4),
                "utilization": round(utilization, 4),
                "breach": breach,
            })
        strategies_list.sort(key=lambda s: s["exposure_usd"], reverse=True)

        # Limits & Gauge Utilization
        max_pos_weight = max([p["weight_pct"] for p in positions_list], default=0.0)
        max_strat_weight = max([s["weight_pct"] for s in strategies_list], default=0.0)
        pos_limit_pct = limits_obj.max_position_pct * 100.0
        strat_limit_pct = limits_obj.max_strategy_pct * 100.0
        cash_limit_pct = limits_obj.min_cash_pct * 100.0

        utilization_map = {
            "max_position_pct": round(max_pos_weight / pos_limit_pct, 4) if pos_limit_pct > 0 else 0.0,
            "max_strategy_pct": round(max_strat_weight / strat_limit_pct, 4) if strat_limit_pct > 0 else 0.0,
            "min_cash_pct": round((cash_limit_pct - cash_pct) / cash_limit_pct, 4) if (cash_limit_pct > 0 and cash_pct < cash_limit_pct) else 0.0,
            "max_drawdown_pct": round(dd_utilization, 4),
        }

        partial_assessment = {
            "nav_usd": round(nav_usd, 2),
            "cash_usd": round(cash_usd, 2),
            "cash_pct": round(cash_pct, 4),
            "gross_exposure_usd": round(gross_exposure_usd, 2),
            "gross_exposure_pct": round(gross_exposure_pct, 4),
            "halted": halted,
            "drawdown": drawdown,
            "positions": positions_list,
            "strategies": strategies_list,
            "limits": limits_dict,
            "utilization": utilization_map,
            "worst_position": worst_position,
            "history_snaps": history_snaps,
            "unpriced_symbols": unpriced,
        }

        alarms = self.evaluate_alarms(partial_assessment)
        alarm_dicts = [a.to_dict() for a in alarms]

        # Marks served from a failed refresh are reported, never presented as
        # fresh: a book valued on stale prices is a book whose NAV is a guess.
        stale_marks: dict[str, float] = {}
        getter = getattr(self._price, "__self__", None)
        if getter is not None and hasattr(getter, "stale_marks"):
            try:
                stale_marks = getter.stale_marks()
            except Exception:  # noqa: BLE001
                stale_marks = {}
        if unpriced:
            alarm_dicts.append(Alarm(
                key="unpriced", type="data_quality", severity="warn",
                message=(f"no live price for {', '.join(unpriced)} — these positions are "
                         "EXCLUDED from NAV, exposure and every limit check below"),
                metric=float(len(unpriced)), threshold=0.0,
            ).to_dict())
        if stale_marks:
            oldest = max(stale_marks.values())
            alarm_dicts.append(Alarm(
                key="stale_marks", type="data_quality", severity="warn",
                message=(f"{len(stale_marks)} mark(s) served from a failed refresh, "
                         f"oldest {oldest:.0f}s — valuations below are not live"),
                metric=float(oldest), threshold=0.0,
            ).to_dict())

        return {
            "nav_usd": round(nav_usd, 2),
            "cash_usd": round(cash_usd, 2),
            "cash_pct": round(cash_pct, 4),
            "gross_exposure_usd": round(gross_exposure_usd, 2),
            "gross_exposure_pct": round(gross_exposure_pct, 4),
            "halted": halted,
            "drawdown": drawdown,
            "positions": positions_list,
            "strategies": strategies_list,
            "limits": limits_dict,
            "utilization": utilization_map,
            "alarms": alarm_dicts,
            "worst_position": worst_position,
            "unpriced_symbols": unpriced,
            "stale_marks": stale_marks,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def evaluate_alarms(self, assessment: dict | None = None) -> list[Alarm]:
        """Pure: turn an assessment into the list of Alarms currently breaching.
        Rules (all thresholds from RiskControl.limits()):
          - drawdown:      drawdown_pct > max_drawdown_pct          -> critical
          - concentration: any position weight_pct > max_position_pct -> critical if >1.25x, else warn
          - cash_floor:    cash_pct < min_cash_pct                  -> warn
          - underwater:    any position unrealized_pnl_pct < -underwater_pct -> warn
          - strategy_cap:  any strategy weight_pct > max_strategy_pct -> warn
          - daily_loss:    NAV vs last daily strike < -max_daily_loss_pct -> critical
        """
        a = assessment or self.assess()
        limits = RiskLimits.from_dict(a.get("limits", {}))
        alarms: list[Alarm] = []

        # 1. Drawdown rule
        dd_pct = a.get("drawdown", {}).get("drawdown_pct", 0.0)
        dd_limit = limits.max_drawdown_pct * 100.0
        if dd_pct > dd_limit:
            alarms.append(Alarm(
                key="drawdown",
                type="drawdown",
                severity="critical",
                message=f"Portfolio drawdown {dd_pct:.2f}% exceeds limit {dd_limit:.2f}%",
                metric=dd_pct,
                threshold=dd_limit,
            ))

        # 2. Daily loss rule (uses prior-day strike reference, not last strike)
        history_snaps = a.get("history_snaps")
        if history_snaps is None:
            history_snaps = self._nav.history(365)
        if history_snaps:
            now_ts = a.get("ts") or datetime.now(timezone.utc).isoformat()
            today_date = now_ts[:10]
            prior_snaps = [s for s in history_snaps if s.get("ts", "")[:10] < today_date]
            if prior_snaps:
                prior_daily_nav = float(prior_snaps[-1].get("total_nav_usd", 0))
                nav_usd = a.get("nav_usd", 0.0)
                if prior_daily_nav > 0:
                    daily_change_pct = ((nav_usd - prior_daily_nav) / prior_daily_nav) * 100.0
                    daily_loss_limit = limits.max_daily_loss_pct * 100.0
                    if daily_change_pct < -daily_loss_limit:
                        alarms.append(Alarm(
                            key="daily_loss",
                            type="daily_loss",
                            severity="critical",
                            message=f"Daily NAV loss {abs(daily_change_pct):.2f}% exceeds limit {daily_loss_limit:.2f}%",
                            metric=abs(daily_change_pct),
                            threshold=daily_loss_limit,
                        ))

        # 3. Concentration rule
        pos_limit = limits.max_position_pct * 100.0
        for pos in a.get("positions", []):
            weight = pos.get("weight_pct", 0.0)
            sym = pos.get("symbol", "")
            if weight > pos_limit:
                severity = "critical" if weight > (1.25 * pos_limit) else "warn"
                alarms.append(Alarm(
                    key=f"concentration:{sym}",
                    type="concentration",
                    severity=severity,
                    message=f"{sym} concentration {weight:.2f}% exceeds limit {pos_limit:.2f}%",
                    metric=weight,
                    threshold=pos_limit,
                    symbol=sym,
                ))

        # 4. Cash floor rule
        cash_pct = a.get("cash_pct", 0.0)
        cash_limit = limits.min_cash_pct * 100.0
        if cash_pct < cash_limit:
            alarms.append(Alarm(
                key="cash_floor",
                type="cash_floor",
                severity="warn",
                message=f"Cash buffer {cash_pct:.2f}% is below limit {cash_limit:.2f}%",
                metric=cash_pct,
                threshold=cash_limit,
            ))

        # 5. Underwater position rule
        underwater_limit = limits.underwater_pct * 100.0
        for pos in a.get("positions", []):
            pnl_pct = pos.get("unrealized_pnl_pct", 0.0)
            sym = pos.get("symbol", "")
            if pnl_pct < -underwater_limit:
                alarms.append(Alarm(
                    key=f"underwater:{sym}",
                    type="underwater",
                    severity="warn",
                    message=f"{sym} position is {abs(pnl_pct):.2f}% underwater (limit {underwater_limit:.2f}%)",
                    metric=abs(pnl_pct),
                    threshold=underwater_limit,
                    symbol=sym,
                ))

        # 6. Strategy cap rule
        strat_limit = limits.max_strategy_pct * 100.0
        for strat in a.get("strategies", []):
            weight = strat.get("weight_pct", 0.0)
            sid = strat.get("strategy_id", "")
            name = strat.get("name", sid)
            if weight > strat_limit:
                alarms.append(Alarm(
                    key=f"strategy_cap:{sid}",
                    type="strategy_cap",
                    severity="warn",
                    message=f"Strategy {name} weight {weight:.2f}% exceeds limit {strat_limit:.2f}%",
                    metric=weight,
                    threshold=strat_limit,
                    strategy_id=sid,
                ))

        return alarms

    def run(self, actor: str = "monitor") -> dict[str, Any]:
        """The periodic tick: assess -> diff against active alarms -> emit
        RISK_ALARM_RAISED for new breaches, RISK_ALARM_CLEARED for resolved ones
        (dedup by Alarm.key) -> AUTO-HALT on any critical drawdown/daily_loss alarm.
        Returns {"raised": [...], "cleared": [...], "halted": bool, "active": [...]}.
        Never raises a duplicate for a standing breach; never auto-resumes.
        """
        assessment = self.assess()
        current_alarms = self.evaluate_alarms(assessment)
        current_map = {a.key: a for a in current_alarms}

        active_raw = self._control.active_alarms()
        active_keys = {a["key"] for a in active_raw}

        new_keys = set(current_map.keys()) - active_keys
        cleared_keys = active_keys - set(current_map.keys())

        # Emit RISK_ALARM_RAISED for new breaches
        raised_alarms = []
        for k in sorted(new_keys):
            alarm = current_map[k]
            alarm_dict = alarm.to_dict()
            self._store.append(
                Event(
                    aggregate_id="fund",
                    aggregate_type="fund",
                    type=EventType.RISK_ALARM_RAISED,
                    payload=alarm_dict,
                    actor=actor,
                )
            )
            raised_alarms.append(alarm_dict)

        # Emit RISK_ALARM_CLEARED for resolved breaches
        cleared_list = sorted(list(cleared_keys))
        for k in cleared_list:
            cleared_payload = next((a for a in active_raw if a["key"] == k), {"key": k})
            self._store.append(
                Event(
                    aggregate_id="fund",
                    aggregate_type="fund",
                    type=EventType.RISK_ALARM_CLEARED,
                    payload={
                        "key": k,
                        "type": cleared_payload.get("type"),
                        "message": f"Cleared breach for {k}",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    },
                    actor=actor,
                )
            )

        # Auto-halt on critical drawdown or daily_loss alarm
        critical_halt_alarm = next(
            (a for a in current_alarms if a.severity == "critical" and a.type in ("drawdown", "daily_loss")),
            None,
        )
        if critical_halt_alarm and not self._control.is_halted():
            self._control.halt(reason=f"Auto-halt: {critical_halt_alarm.message}", actor="monitor")

        return {
            "raised": raised_alarms,
            "cleared": cleared_list,
            "halted": self._control.is_halted(),
            "active": self._control.active_alarms(),
        }
