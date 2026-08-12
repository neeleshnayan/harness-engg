"""Risk monitor & controls — continuous surveillance + the kill switch.

⚠️ SKELETON / CONTRACT FILE — implement the TODOs. Signatures, docstrings, and the
`assess()` return contract are the spec; do not change the shapes without updating
docs/RISK_ENGINE_SPEC.md and the frontend that consumes them.

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

from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.fund.events import EventStore
from app.fund.projections.nav import NavService
from app.fund.risk import RiskLimits


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


class RiskControl:
    """Auditable limits + kill-switch state, folded from the event log."""

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def limits(self) -> RiskLimits:
        """Latest RiskLimitsSet folded over defaults (RiskLimits())."""
        raise NotImplementedError  # TODO: fold RISK_LIMITS_SET; default RiskLimits()

    def set_limits(self, patch: dict, actor: str) -> RiskLimits:
        """Emit RISK_LIMITS_SET (merge patch onto current) and return the result."""
        raise NotImplementedError  # TODO

    def is_halted(self) -> bool:
        """True if the last of TradingHalted/TradingResumed is a halt."""
        raise NotImplementedError  # TODO: fold on aggregate_id 'fund'

    def halt(self, reason: str, actor: str) -> dict:
        """Engage the kill switch (idempotent: no-op if already halted)."""
        raise NotImplementedError  # TODO: emit TRADING_HALTED

    def resume(self, actor: str) -> dict:
        """Re-enable trading (human only)."""
        raise NotImplementedError  # TODO: emit TRADING_RESUMED

    def active_alarms(self) -> list[dict]:
        """Currently-open alarms: RISK_ALARM_RAISED not yet followed by a CLEARED
        for the same key, newest first."""
        raise NotImplementedError  # TODO

    def alarm_history(self, limit: int = 100) -> list[dict]:
        """Recent alarm events (raised + cleared), newest first — the audit feed."""
        raise NotImplementedError  # TODO


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
        """The full current risk picture — Rushi's single pane of glass.

        RETURN CONTRACT (do not change without updating the spec + frontend):
        {
          "nav_usd": float, "cash_usd": float, "cash_pct": float,
          "gross_exposure_usd": float, "gross_exposure_pct": float,
          "halted": bool,
          "drawdown": {
            "peak_nav": float, "current_nav": float,
            "drawdown_pct": float,        # 0..100, current fall from peak
            "max_drawdown_pct": float,    # worst historical
            "limit_pct": float, "utilization": float   # drawdown_pct / limit
          },
          "positions": [ {                # per-ASSET risk
            "symbol": str, "qty": float, "mark": float, "value_usd": float,
            "weight_pct": float,          # of NAV
            "unrealized_pnl_pct": float,  # mark vs avg cost (the "going down" signal)
            "shock_20_usd": float         # P&L if this name drops 20%
          } ],
          "strategies": [ {               # per-STRATEGY risk
            "strategy_id": str, "name": str, "exposure_usd": float,
            "weight_pct": float, "pnl_usd": float,
            "limit_pct": float, "utilization": float, "breach": bool
          } ],
          "limits": {...RiskLimits.to_dict()...},
          "utilization": {                # 0..1+ per limit, for gauges
            "max_position_pct": float, "max_strategy_pct": float,
            "min_cash_pct": float, "max_drawdown_pct": float
          },
          "alarms": [ ...Alarm-as-dict... ],   # what is CURRENTLY breaching this tick
          "worst_position": {...} | null,
          "ts": str
        }
        """
        raise NotImplementedError  # TODO: build from NavService.compute()/history(),
        # positions (mark vs avg cost), attribution, and self._control.limits()

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
        raise NotImplementedError  # TODO

    def run(self, actor: str = "monitor") -> dict[str, Any]:
        """The periodic tick: assess -> diff against active alarms -> emit
        RISK_ALARM_RAISED for new breaches, RISK_ALARM_CLEARED for resolved ones
        (dedup by Alarm.key) -> AUTO-HALT on any critical drawdown/daily_loss alarm.
        Returns {"raised": [...], "cleared": [...], "halted": bool, "active": [...]}.
        Never raises a duplicate for a standing breach; never auto-resumes.
        """
        raise NotImplementedError  # TODO
