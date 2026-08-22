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


# --- halt classes (2026-08-20, CEO-blessed principle) -----------------------
#
# "Halted" was one word for two different kinds of dark, and the difference is
# the whole reopening procedure:
#
#   integrity — the fund cannot MEASURE itself (bad or absent mark, stale feed,
#               dead heartbeat). Nothing about the book is known to be wrong;
#               what is wrong is our sight of it. Resumes only when the
#               integrity problem is fixed AND a human acknowledges it. There is
#               no "accept it and carry on" — accepting an unmeasured book is
#               how the phantom price became a fill.
#   loss      — the fund measured itself correctly and does not like the answer
#               (drawdown, daily loss). A circuit breaker, with a reopening
#               procedure: the CEO may acknowledge the loss and rebase the
#               reference (see LOSS_REFERENCE_REBASED) with a written reason.
#   manual    — a human pulled the switch. Not automatic, so not classified by
#               cause; resumes when the same authority says so.
#
# The class is carried on the halt event and surfaced by /fund/risk/monitor so
# the UI can say WHICH kind of dark this is. It changes no threshold and adds
# no trigger: it labels the halts that already exist.
HALT_INTEGRITY = "integrity"
HALT_LOSS = "loss"
HALT_MANUAL = "manual"
HALT_CLASSES = (HALT_INTEGRITY, HALT_LOSS, HALT_MANUAL)

#: Alarm type -> halt class. Only drawdown and daily_loss can auto-halt today
#: (see RiskMonitor.run), so `integrity` currently reaches the halt path only
#: through a manual halt that names an integrity cause. Stated rather than
#: implied: this mapping does NOT create an integrity auto-halt, and nothing in
#: this change does.
_HALT_CLASS_BY_ALARM = {
    "drawdown": HALT_LOSS,
    "daily_loss": HALT_LOSS,
    "data_quality": HALT_INTEGRITY,
    "stale_marks": HALT_INTEGRITY,
    "unpriced": HALT_INTEGRITY,
    "heartbeat": HALT_INTEGRITY,
    # The book disagreeing with the venue is an INTEGRITY fault by the
    # definition eighteen lines above: nothing about the book is known to be
    # wrong; what is wrong is our sight of it. Added 2026-08-23 with the drift
    # alarm, and it still creates no auto-halt — the auto-halt gate in ``run``
    # is on ``("drawdown", "daily_loss")`` and this change does not touch it.
    "book_venue_drift": HALT_INTEGRITY,
}

# --- the book-vs-venue drift alarm (2026-08-23, desk d7f38be2) --------------
#
# Seven alarm types existed and none watched the book against the broker, while
# the two disagreed on TEN of eleven symbols worth $126.54 — 6.71% of NAV,
# measured on the live spine the day this was built. That sat unannounced until
# a PM read an endpoint by hand.
#
#: ONE key for every drift state, and that is a load-bearing choice rather than
#: a naming convenience. ``run`` deduplicates and clears BY KEY, so if an
#: unreadable venue produced a different key from a drifting one, the transition
#: "drifting -> cannot read the broker" would emit a RiskAlarmCleared for the
#: drift — the log would record that a $126 disagreement resolved, at the exact
#: moment the fund went blind to it.
DRIFT_ALARM_KEY = "book_venue_drift"

#: Alarm keys whose FAMILY may be absent from a tick's evaluation because the
#: input was not available — as opposed to absent because the rule evaluated
#: false. ``run`` must not clear these on a tick that could not judge them.
#:
#: This is a general contract with exactly one member today. It exists as a set
#: because the next alarm built on an input some monitors lack will need it, and
#: the failure it prevents is silent: a cleared alarm looks like good news.
UNEVALUATED_ON_ABSENT = frozenset({DRIFT_ALARM_KEY})


def classify_halt_cause(alarm_type: str | None) -> str:
    """The halt class an alarm type implies. Unknown causes are MANUAL.

    Unknown is not "loss": misfiling an unrecognised cause as a loss halt would
    make it eligible for acknowledge-and-rebase, which is the one action that
    must never be reachable by accident.
    """
    return _HALT_CLASS_BY_ALARM.get((alarm_type or "").strip().lower(), HALT_MANUAL)


# --- loss-halt auto-resume (2026-08-21, CEO-approved: "approved yes") --------
#
# A LOSS halt reopens without a second human click when ALL FOUR of these hold,
# evaluated on the monitor tick:
#
#   1. the CEO ACKNOWLEDGED this halt (HaltAcknowledged, guard-protected)
#   2. the TRIGGERING alarm no longer evaluates true on current arithmetic
#   3. no other CRITICAL alarm is active
#   4. the cool-down below has passed since the acknowledgement
#
# INTEGRITY and MANUAL halts NEVER auto-resume, and a halt with NO CLASS is
# treated as integrity — pre-classes halts predate this policy entirely and a
# policy that reopened them would be acting on a darkness nobody classified.
#
# The design's centre of gravity: the human decision is condition 1 and it is
# not optional. This does not remove the human from the loop; it removes the
# SECOND click — the one that only ever said "yes, still" about a decision
# already made.

#: Condition 4's value. JUDGED, and tied to a cadence rather than to a round
#: human number: the scheduler strikes NAV every STRIKE_INTERVAL_SECONDS
#: (default 1800 = 30 minutes, app/main.py) while the monitor ticks every ~30
#: seconds. Without a cool-down a metric oscillating around the daily-loss line
#: could halt and reopen ~120 times an hour, and every cycle pays spread.
#: Thirty minutes is ONE FULL STRIKE INTERVAL, which means the fund must stay
#: clear of the line long enough for at least one FRESH NAV strike to land
#: between the CEO's acknowledgement and the reopening — so the reopening is
#: corroborated by a new measurement, not by the same one that cleared.
#:
#: Measured FROM THE ACKNOWLEDGEMENT, not from the halt. Timing it from the
#: halt would let an acknowledgement arriving 40 minutes in reopen instantly;
#: the cool-down's job is "the human decided, and then the market kept agreeing
#: for half an hour".
#:
#: REVIEW TRIGGER: if STRIKE_INTERVAL_SECONDS changes, this number's basis is
#: gone and it must be re-derived. Registered in the judgement register.
LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES = 30.0


def _minutes_since(iso: str | None, now: datetime | None = None) -> float | None:
    """Minutes between an ISO timestamp and now, or None when untellable.

    None, never 0: an unparseable acknowledgement time must fail the cool-down,
    and a 0 would pass it the instant the cool-down were ever set to 0.
    """
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    n = now or datetime.now(timezone.utc)
    return (n - t).total_seconds() / 60.0


def effective_peak(history_snaps: list[dict[str, Any]] | None,
                   nav_usd: float,
                   rebase: dict[str, Any] | None) -> dict[str, Any]:
    """The peak the drawdown rule measures from, and where it came from.

    Pure, so the direction rule is testable without a NAV service.

    With no rebase this is exactly what it always was: the trailing-365d high,
    including current NAV. With a rebase it is

        max(rebased value, every NAV observed AT OR AFTER the rebase, current NAV)

    which is the sentence "the rebase is a FLOOR on the peak, and a later
    genuine high still raises it" written as arithmetic. Two properties follow
    and both are tested:

      * a rebase can only ever LOWER the peak — the `>= current_peak` refusal
        in ``rebase_drawdown_reference`` enforces the input side, and the max()
        above means even an accepted rebase cannot lower it below what has
        happened SINCE;
      * a rebase can never HIDE a real new high, because post-rebase
        observations and current NAV are both in the max.

    A rebase with no usable timestamp is IGNORED rather than applied to the
    whole series: without knowing when it was struck, "observations after it"
    is unanswerable, and applying it anyway would silently erase real history.
    """
    series: list[tuple[str, float]] = []
    for s in (history_snaps or []):
        v = s.get("total_nav_usd")
        if v is None:
            continue
        try:
            series.append((str(s.get("ts") or ""), float(v)))
        except (TypeError, ValueError):
            continue
    unrebased = max([v for _, v in series] + [nav_usd])

    ref_val: float | None = None
    ref_at: str | None = None
    if rebase:
        try:
            r = float(rebase.get("nav_usd"))
        except (TypeError, ValueError):
            r = 0.0
        if r > 0 and rebase.get("at"):
            ref_val, ref_at = r, str(rebase["at"])

    if ref_val is None:
        return {"peak_nav": unrebased, "unrebased_peak_nav": unrebased,
                "basis": "trailing_365d", "rebase": None,
                "note": ("the trailing-365-day high, including current NAV — "
                         "the drawdown reference has never been rebased")}

    post = [v for ts, v in series if ts >= (ref_at or "")]
    peak = max([ref_val, *post, nav_usd])
    basis = ("rebased" if peak == ref_val
             else "post_rebase_high" if post and peak == max(post)
             else "current_nav")
    return {
        "peak_nav": peak,
        "unrebased_peak_nav": unrebased,
        "basis": basis,
        "rebase": {"nav_usd": ref_val, "at": ref_at,
                   "reason": rebase.get("reason"),
                   "actor": rebase.get("actor"),
                   "previous_peak_usd": rebase.get("previous_peak_usd")},
        "note": (
            f"measured from a reference rebased to ${ref_val:,.2f} on "
            f"{ref_at} (the un-rebased trailing high is ${unrebased:,.2f})"
            if basis == "rebased" else
            f"a genuine high of ${peak:,.2f} since the rebase to "
            f"${ref_val:,.2f} has raised the reference back"),
    }


def evaluate_autoresume(*, halt_class: str | None,
                        halted_at: str | None,
                        halt_alarm: dict[str, Any] | None,
                        acknowledgement: dict[str, Any] | None,
                        current_alarms: list[dict[str, Any]],
                        now: datetime | None = None,
                        cooldown_minutes: float = LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES,
                        ) -> dict[str, Any]:
    """Should this halt reopen without a second click? Pure; four conditions.

    Returns ``{"resume": bool, "conditions": [...], "reason": str}`` where each
    condition carries the VALUE it was evaluated on, not just a boolean. The
    caller puts that list straight onto the TradingResumed event: an
    auto-resume nobody can audit is an auto-resume that never should have
    happened.

    ``current_alarms`` is the alarm list AS OF THIS TICK — dicts with `type`,
    `key`, `severity`. It must be the freshly evaluated set, not the stored
    active set, because condition 2 asks about CURRENT arithmetic.

    Every unknown fails closed. There is no branch in this function that
    resumes on an absence.
    """
    conds: list[dict[str, Any]] = []

    def cond(name: str, ok: bool, detail: str, **values: Any) -> None:
        conds.append({"condition": name, "ok": bool(ok), "detail": detail,
                      **values})

    # Condition 0 — the class gate. Not one of the four; it decides whether the
    # four are even asked. A halt with NO class is treated as INTEGRITY:
    # pre-classes halts predate this policy, and reopening a darkness nobody
    # classified is precisely the move the class system exists to prevent.
    eligible = halt_class == HALT_LOSS
    cond("class_is_loss", eligible,
         f"halt_class={halt_class!r}; only a LOSS halt may auto-resume. "
         + ("" if eligible else
            "INTEGRITY and MANUAL never do, and an unclassified halt is "
            "treated as integrity."),
         halt_class=halt_class)

    # 1 — acknowledged by the CEO, for THIS halt.
    ack_at = (acknowledgement or {}).get("at")
    ack_matches = bool(acknowledgement) and (
        str((acknowledgement or {}).get("halted_at") or "") == str(halted_at or ""))
    cond("ceo_acknowledged", ack_matches,
         ("acknowledged by "
          f"{(acknowledgement or {}).get('actor')!r} at {ack_at}: "
          f"{(acknowledgement or {}).get('note')!r}")
         if ack_matches else
         "no HaltAcknowledged event names this halt — the CEO has not stated "
         "they have seen it, and an unseen halt does not reopen itself",
         acknowledged_at=ack_at,
         acknowledged_by=(acknowledgement or {}).get("actor"),
         note=(acknowledgement or {}).get("note"))

    # 2 — the TRIGGERING alarm is no longer true on current arithmetic.
    trigger_type = (halt_alarm or {}).get("type")
    trigger_key = (halt_alarm or {}).get("key")
    live_keys = {a.get("key") for a in current_alarms}
    live_types = {a.get("type") for a in current_alarms}
    if not trigger_type:
        cond("trigger_cleared", False,
             "this halt did not record which alarm tripped it, so whether that "
             "alarm is still true cannot be evaluated. Fails closed — the "
             "reason string is free text and parsing it would be provenance "
             "by wording.",
             trigger_alarm=None)
    else:
        still = (trigger_key in live_keys) if trigger_key else (trigger_type in live_types)
        cond("trigger_cleared", not still,
             (f"{trigger_type!r} no longer evaluates true"
              if not still else
              f"{trigger_type!r} is STILL true on current arithmetic"),
             trigger_alarm=trigger_type, trigger_key=trigger_key)

    # 3 — nothing else critical is open. The triggering alarm is excluded so
    # this condition says something condition 2 does not.
    others = [a for a in current_alarms
              if a.get("severity") == "critical"
              and a.get("key") != trigger_key]
    cond("no_other_critical_alarm", not others,
         "no other critical alarm is active" if not others else
         "other critical alarms are active: "
         + ", ".join(sorted(str(a.get("key")) for a in others)),
         other_critical=sorted(str(a.get("key")) for a in others))

    # 4 — the cool-down, from the acknowledgement.
    mins = _minutes_since(ack_at, now) if ack_matches else None
    passed = mins is not None and mins >= cooldown_minutes
    cond("cooldown_elapsed", passed,
         (f"{mins:.1f} min since the acknowledgement against a "
          f"{cooldown_minutes:.0f} min cool-down")
         if mins is not None else
         "no usable acknowledgement time, so the cool-down cannot be shown to "
         "have passed",
         minutes_since_acknowledgement=(None if mins is None else round(mins, 2)),
         cooldown_minutes=cooldown_minutes)

    resume = all(c["ok"] for c in conds)
    failed = [c["condition"] for c in conds if not c["ok"]]
    return {
        "resume": resume,
        "conditions": conds,
        "cooldown_minutes": cooldown_minutes,
        "reason": ("all four conditions hold; the halt reopens under the "
                   "CEO-approved loss auto-resume policy"
                   if resume else
                   "held: " + ", ".join(failed)),
    }


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


def _drift_alarm(reading: Any) -> Optional[Alarm]:
    """The book-vs-venue alarm for one drift reading. Pure; absence RAISES.

    Returns None for exactly ONE input — a well-formed reading in which the
    reconciler looked at every symbol and found them all in sync. Every other
    input produces an alarm, including every shape of "I could not look",
    because the alarm's whole job is to be un-silenceable by the failure of the
    thing it watches.

    ``reading`` is ``Reconciler.drift()``'s output, consumed as the reconciler
    already computed it:

      * ``configured: True`` with ``per_symbol`` — the count of rows whose own
        ``in_sync`` is false. NO SECOND OPINION about what "in sync" means; the
        tolerance lives in ``reconcile._TOL`` and is read through this verdict,
        never recomputed here.
      * ``configured: True`` with NO ``per_symbol`` — malformed. The reconciler
        says it read the venue and then does not say what it read. Unreadable.
      * ``configured: False``, a non-dict, or None — unreadable, and it RAISES.

    CRITICAL, not warn, and that is a deliberate consequence worth naming: it
    means ``evaluate_autoresume`` condition 3 ("no other critical alarm is
    active") holds a LOSS halt shut while book and broker disagree. A fund that
    reopens execution automatically while it does not know what it holds has
    inverted the reason condition 3 exists. It still cannot AUTO-HALT — that
    gate is on ``("drawdown", "daily_loss")`` and is untouched by this change.
    """
    if not isinstance(reading, dict):
        return Alarm(
            key=DRIFT_ALARM_KEY, type=DRIFT_ALARM_KEY, severity="critical",
            message=("book-vs-venue drift is UNKNOWN: no usable reading from "
                     "the reconciler. This is an absence, not agreement — the "
                     "number of positions the broker disagrees with us about "
                     "could be any number, including all of them"),
            metric=1.0, threshold=0.0)

    if not reading.get("configured"):
        why = reading.get("reason") or "no reason recorded"
        return Alarm(
            key=DRIFT_ALARM_KEY, type=DRIFT_ALARM_KEY, severity="critical",
            message=(f"book-vs-venue drift is UNKNOWN: the venue could not be "
                     f"read ({why}). This is an absence, not agreement — the "
                     f"book may be perfectly in sync or wrong on every symbol, "
                     f"and this alarm cannot tell you which"),
            metric=1.0, threshold=0.0)

    rows = reading.get("per_symbol")
    if not isinstance(rows, list):
        return Alarm(
            key=DRIFT_ALARM_KEY, type=DRIFT_ALARM_KEY, severity="critical",
            message=("book-vs-venue drift is UNKNOWN: the reconciler reported a "
                     "configured venue and no per-symbol reading, so there is "
                     "nothing to compare. Malformed is unreadable, and "
                     "unreadable is not in sync"),
            metric=1.0, threshold=0.0)

    out = [r for r in rows if not r.get("in_sync")]
    if not out:
        return None

    # The dollar figure is CONTEXT on the message, never the trigger: the
    # trigger is the reconciler's own per-symbol verdict, so this rule owns no
    # threshold of its own. `delta_usd` is absent whenever the monitor was
    # built without a NAV service, and an absent delta is simply not mentioned
    # rather than rendered as $0.00.
    delta = reading.get("delta_usd")
    delta_pct = reading.get("delta_pct")
    money = ""
    if delta is not None:
        money = f"; broker equity differs from folded NAV by ${float(delta):,.2f}"
        if delta_pct is not None:
            money += f" ({float(delta_pct):.2f}% of NAV)"
    names = ", ".join(str(r.get("symbol")) for r in out[:6])
    if len(out) > 6:
        names += f", +{len(out) - 6} more"
    return Alarm(
        key=DRIFT_ALARM_KEY, type=DRIFT_ALARM_KEY, severity="critical",
        message=(f"book and venue disagree on {len(out)} of {len(rows)} "
                 f"position(s): {names}{money}. Every limit check on this page "
                 f"is computed from the BOOK, so a disagreement here means they "
                 f"were computed against quantities the broker does not confirm"),
        metric=float(len(out)), threshold=0.0)


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
        halt_class: str | None = None
        halt_reason: str | None = None
        halted_at: str | None = None
        halt_alarm: dict[str, Any] | None = None
        halt_ack: dict[str, Any] | None = None
        loss_reference: dict[str, Any] | None = None
        drawdown_reference: dict[str, Any] | None = None
        active: dict[str, dict] = {}
        history: list[dict] = []

        for e in self._store.stream(since_seq=0, limit=100_000):
            etype = e.get("type")
            p = e.get("payload", {}) or {}
            if etype == EventType.RISK_LIMITS_SET.value:
                limits = RiskLimits.from_dict(p)
            elif etype == EventType.TRADING_HALTED.value:
                halted = True
                # Halts recorded before halt classes existed carry no class.
                # They are reported as None — "we do not know which kind of
                # dark this was" — never back-filled as `manual`, which would
                # invent a fact about a historical event.
                halt_class = p.get("halt_class")
                halt_reason = p.get("reason")
                halted_at = e.get("ts")
                # WHICH alarm tripped it, where the halter knew. Absent on
                # every halt recorded before 2026-08-21 and on every manual
                # one — and an absent trigger is a trigger the auto-resume
                # policy cannot evaluate, so it fails closed rather than
                # guessing from the reason prose.
                halt_alarm = ({"type": p.get("alarm_type"),
                               "key": p.get("alarm_key")}
                              if p.get("alarm_type") else None)
                # A NEW halt voids any earlier acknowledgement: the CEO
                # acknowledged the last dark, not this one.
                halt_ack = None
            elif etype == EventType.TRADING_RESUMED.value:
                halted = False
                halt_class = halt_reason = halted_at = None
                halt_alarm = halt_ack = None
            elif etype == EventType.HALT_ACKNOWLEDGED.value:
                # Only counts for the halt it names. An acknowledgement whose
                # halted_at does not match the open halt is a stale click and
                # is folded away rather than applied to a darkness the CEO
                # has not seen.
                if halted and str(p.get("halted_at") or "") == str(halted_at or ""):
                    halt_ack = {**p, "at": p.get("at") or e.get("ts"),
                                "actor": e.get("actor")}
            elif etype == EventType.LOSS_REFERENCE_REBASED.value:
                loss_reference = {**p, "at": p.get("at") or e.get("ts"),
                                  "actor": e.get("actor")}
            elif etype == EventType.DRAWDOWN_REFERENCE_REBASED.value:
                # Last one wins. Each rebase is a fresh statement about where
                # the peak is measured from; they do not compose.
                drawdown_reference = {**p, "at": p.get("at") or e.get("ts"),
                                      "actor": e.get("actor")}
            elif etype == EventType.RISK_ALARM_RAISED.value:
                history.append(e)
                if p.get("key"):
                    active[p["key"]] = p
            elif etype == EventType.RISK_ALARM_CLEARED.value:
                history.append(e)
                if p.get("key"):
                    active.pop(p["key"], None)

        state = {"limits": limits, "halted": halted, "halt_class": halt_class,
                 "halt_reason": halt_reason, "halted_at": halted_at,
                 "halt_alarm": halt_alarm if halted else None,
                 "halt_ack": halt_ack if halted else None,
                 "loss_reference": loss_reference,
                 "drawdown_reference": drawdown_reference,
                 "active": active, "history": history}
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

    def halt(self, reason: str, actor: str,
             halt_class: str = HALT_MANUAL,
             alarm_type: str | None = None,
             alarm_key: str | None = None) -> dict:
        """Engage the kill switch (idempotent: no-op if already halted).

        ``halt_class`` says which KIND of dark this is (see HALT_CLASSES). It
        defaults to manual because a caller that does not know the cause has,
        by definition, not measured one.

        ``alarm_type``/``alarm_key`` name the alarm that tripped it, where the
        caller knows. Added 2026-08-21 for the loss-halt auto-resume policy,
        whose second condition is "the TRIGGERING alarm no longer evaluates
        true" — a question that cannot be asked of a halt that never recorded
        which alarm it was. Absent on every historical halt and on every manual
        one, and an absent trigger makes the policy fail closed rather than
        parse the reason prose (a free-text field is not provenance; the same
        rule faces.ts follows about actor strings).
        """
        if halt_class not in HALT_CLASSES:
            halt_class = HALT_MANUAL
        if self.is_halted():
            return {"status": "already_halted", "reason": reason, "halted": True,
                    "halt_class": self.halt_class()}
        payload: dict[str, Any] = {"reason": reason, "halt_class": halt_class}
        if alarm_type:
            payload["alarm_type"] = alarm_type
            if alarm_key:
                payload["alarm_key"] = alarm_key
        self._store.append(
            Event(
                aggregate_id="fund",
                aggregate_type="fund",
                type=EventType.TRADING_HALTED,
                payload=payload,
                actor=actor,
            )
        )
        self._invalidate()
        return {"status": "halted", "reason": reason, "halted": True,
                "halt_class": halt_class, "alarm_type": alarm_type}

    def halt_class(self) -> str | None:
        """The class of the OPEN halt, or None when not halted / unclassified."""
        return self._fold()["halt_class"] if self._fold()["halted"] else None

    def halt_state(self) -> dict[str, Any]:
        """The full halt picture for the UI: halted, class, reason, since."""
        st = self._fold()
        return {"halted": st["halted"],
                "halt_class": st["halt_class"] if st["halted"] else None,
                "halt_reason": st["halt_reason"] if st["halted"] else None,
                "halted_at": st["halted_at"] if st["halted"] else None}

    def resume(self, actor: str, audit: dict[str, Any] | None = None) -> dict:
        """Re-enable trading. Every class resumes manually; only a LOSS halt
        may ALSO be resumed by the auto-resume policy, which passes ``audit``.

        ``audit`` is the four conditions with their EVALUATED VALUES, not a
        verdict word. An auto-resume nobody can reconstruct is an auto-resume
        that never should have happened — the same reason an auto-APPROVAL
        carries its full check-by-check evaluation onto the approval event.
        """
        if not self.is_halted():
            return {"status": "not_halted", "halted": False}
        self._store.append(
            Event(
                aggregate_id="fund",
                aggregate_type="fund",
                type=EventType.TRADING_RESUMED,
                payload=({"auto_resume": audit} if audit else {}),
                actor=actor,
            )
        )
        self._invalidate()
        return {"status": "resumed", "halted": False}

    # --- acknowledge (any class; a precondition, never an action) -----------
    def halt_acknowledgement(self) -> dict[str, Any] | None:
        """The CEO's acknowledgement of the CURRENTLY OPEN halt, or None.

        None means "this darkness has not been acknowledged" — it never means
        "acknowledged with no detail". An acknowledgement of a PREVIOUS halt is
        folded away by ``_fold``: the CEO saw that one, not this one.
        """
        return self._fold()["halt_ack"]

    def halt_alarm(self) -> dict[str, Any] | None:
        """Which alarm tripped the open halt, or None when it was not recorded."""
        return self._fold()["halt_alarm"]

    def halt_ack_token(self) -> str:
        """An 8-char digest of the halt an acknowledgement would name.

        The approval-channel guard needs something to echo, and a halt has no
        id. The token IS the halt: its class, when it engaged, and its reason.
        Echoing it proves the clicker read THIS halt — an acknowledgement typed
        against a screen showing yesterday's darkness no longer matches.
        """
        import hashlib
        st = self._fold()
        raw = (f"{st['halted']}|{st['halt_class']}|{st['halted_at']}|"
               f"{st['halt_reason']}")
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    def acknowledge_halt(self, actor: str, note: str) -> dict:
        """Record that the CEO has SEEN the open halt. Changes nothing else.

        Deliberately separable from the rebase (the brief's words: "recordable
        without rebasing"). Acknowledging is not accepting a loss and is not
        reopening: it moves no reference, re-arms no path, and by itself
        resumes nothing. It is condition (1) of four, and on its own it is
        worth exactly one sentence in the log.

        The note is MANDATORY for the same reason the rebase's reason is: this
        is a control whose whole purpose is to be hard to use casually.
        """
        note = (note or "").strip()
        if not note:
            raise ValueError(
                "acknowledging a halt requires a written note — the log records "
                "that you saw it, and it has to say what you saw")
        st = self._fold(fresh=True)
        if not st["halted"]:
            raise ValueError("trading is not halted — there is nothing to "
                             "acknowledge")
        payload = {"halt_class": st["halt_class"],
                   "halted_at": st["halted_at"],
                   "halt_reason": st["halt_reason"],
                   "note": note,
                   "at": datetime.now(timezone.utc).isoformat()}
        self._store.append(Event(
            aggregate_id="fund", aggregate_type="fund",
            type=EventType.HALT_ACKNOWLEDGED, payload=payload, actor=actor))
        self._invalidate()
        return {"status": "acknowledged", **payload, "actor": actor}

    # --- acknowledge-and-rebase (loss class only) ---------------------------
    def loss_reference(self) -> dict[str, Any] | None:
        """The rebased daily-loss reference, or None if it has never been moved.

        None means "no rebase has happened", NOT "the reference is zero": with
        no rebase the daily-loss rule falls back to the prior day's strike, and
        the caller must be able to tell those two states apart.
        """
        return self._fold()["loss_reference"]

    def rebase_loss_reference(self, nav_usd: float, reason: str, actor: str) -> dict:
        """Acknowledge a loss and move the daily-loss reference to current NAV.

        The CEO's reopening procedure for a LOSS halt. It changes no threshold —
        the limit stays exactly where the register says it is — it moves the
        point the limit is measured FROM, once, deliberately, in the log, with
        a reason that is mandatory because this is the one control whose whole
        purpose is to be hard to use casually.

        REFUSED while an integrity halt is open: rebasing to "current NAV" when
        current NAV is the number we do not trust would launder a bad mark into
        the fund's own reference. That is the phantom-price incident with a
        signature on it.
        """
        reason = (reason or "").strip()
        if not reason:
            raise ValueError(
                "acknowledging a loss requires a written reason — the reference "
                "moves in the log and the log has to say why"
            )
        if self._fold()["halted"] and self._fold()["halt_class"] == HALT_INTEGRITY:
            raise ValueError(
                "an INTEGRITY halt is open: the fund cannot currently measure "
                "itself, so 'current NAV' is not a number to rebase onto. Fix "
                "the integrity fault and resume first."
            )
        try:
            nav = float(nav_usd)
        except (TypeError, ValueError) as e:
            raise ValueError("the rebase reference must be a number") from e
        if not (nav > 0):
            raise ValueError(
                f"refusing to rebase the daily-loss reference onto {nav_usd!r} — "
                "a non-positive reference makes every future loss unmeasurable"
            )
        payload = {"nav_usd": round(nav, 2), "reason": reason,
                   "at": datetime.now(timezone.utc).isoformat()}
        self._store.append(Event(
            aggregate_id="fund", aggregate_type="fund",
            type=EventType.LOSS_REFERENCE_REBASED, payload=payload, actor=actor,
        ))
        self._invalidate()
        return {"status": "rebased", **payload, "actor": actor}

    # --- acknowledge-and-rebase, the DRAWDOWN twin --------------------------
    def drawdown_reference(self) -> dict[str, Any] | None:
        """The rebased drawdown reference, or None if it has never been moved.

        None means "no rebase has happened", NOT "the peak is zero": with no
        rebase the drawdown rule falls back to the trailing-365d high, and the
        caller must be able to tell those two states apart.
        """
        return self._fold()["drawdown_reference"]

    def drawdown_rebase_token(self, current_peak: float | None = None) -> str:
        """An 8-char digest of the peak a drawdown rebase would replace."""
        import hashlib
        cur = self._fold()["drawdown_reference"]
        raw = (f"{None if current_peak is None else round(float(current_peak), 2)}"
               f"|{(cur or {}).get('nav_usd')}|{(cur or {}).get('at')}")
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    def rebase_drawdown_reference(self, new_peak: float, current_peak: float,
                                  reason: str, actor: str) -> dict:
        """Lower the peak the drawdown rule measures from. CEO-only.

        The defect this exists for (PM sleeve-v2 R1, CEO-accepted 2026-08-21):
        `assess()` takes the trailing-365d MAX of NAV history as the peak, and
        the fund's $2,036.35 high includes the phantom-fill era. A peak
        inflated by a bad mark caps risk capacity for a YEAR — the drawdown
        limit ends up measured against money the fund never had.

        Exactly like the loss rebase, and for the same reasons: it changes no
        threshold (the limit stays where the register says), it moves the point
        the limit is measured FROM, once, in the log, with a mandatory reason.

        THE DIRECTION IS ENFORCED. A rebase may only LOWER the reference:

          * ``new_peak >= current_peak`` is REFUSED. Raising the peak would
            manufacture a drawdown out of nothing, which is a way to halt the
            fund by typing, and — worse — a way to make a future real drawdown
            look smaller by having pre-inflated the denominator.
          * ``new_peak < current NAV`` is REFUSED as a probable typo: the
            effective peak is floored at current NAV anyway, so such a rebase
            would be recorded, change nothing, and read as if it had.

        And it can never HIDE a real peak: ``effective_peak`` (below) is the
        max of the rebased value, every NAV observed AFTER the rebase, and
        current NAV. A later genuine high raises it straight back.
        """
        reason = (reason or "").strip()
        if not reason:
            raise ValueError(
                "rebasing the drawdown reference requires a written reason — "
                "the peak moves in the log and the log has to say why")
        if self._fold()["halted"] and self._fold()["halt_class"] == HALT_INTEGRITY:
            raise ValueError(
                "an INTEGRITY halt is open: the fund cannot currently measure "
                "itself, so no NAV figure is a number to rebase a peak onto. "
                "Fix the integrity fault and resume first.")
        try:
            new = float(new_peak)
            cur = float(current_peak)
        except (TypeError, ValueError) as e:
            raise ValueError("the rebase peak must be a number") from e
        if not (new > 0):
            raise ValueError(
                f"refusing to rebase the drawdown reference onto {new_peak!r} — "
                "a non-positive peak makes every future drawdown unmeasurable")
        if new >= cur:
            raise ValueError(
                f"refusing to rebase the drawdown peak from ${cur:,.2f} to "
                f"${new:,.2f}: a rebase may only LOWER the reference. Raising "
                f"it would manufacture a drawdown out of nothing and would make "
                f"a future real one look smaller.")
        payload = {"nav_usd": round(new, 2),
                   "previous_peak_usd": round(cur, 2),
                   "reason": reason,
                   "at": datetime.now(timezone.utc).isoformat()}
        self._store.append(Event(
            aggregate_id="fund", aggregate_type="fund",
            type=EventType.DRAWDOWN_REFERENCE_REBASED, payload=payload,
            actor=actor))
        self._invalidate()
        return {"status": "rebased", **payload, "actor": actor}

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
                 control: RiskControl | None = None,
                 drift_fn: Callable[[], dict[str, Any]] | None = None):
        self._nav = nav_service
        self._store = store or EventStore()
        self._price = pricer or (lambda _s: 0.0)
        self._attr = attribution        # StrategyAttribution (per-strategy exposure/pnl)
        self._strategies = strategies    # StrategyService (names, limits context)
        self._control = control or RiskControl(self._store)
        #: ``Reconciler.drift`` on the wired spine; None everywhere the monitor
        #: has no business making a broker round trip (the post-fill re-eval,
        #: and every unit test that builds a monitor by hand). None is NOT
        #: "in sync" — see ``_venue_drift`` for the three-state contract.
        self._drift_fn = drift_fn
        self._drift_cache: tuple[float, dict[str, Any]] | None = None

    #: Seconds a drift reading may be reused. ``Reconciler.drift`` costs TWO
    #: Alpaca round trips (``account_info`` + ``positions``) and ``assess`` is
    #: what the UI's risk bar polls on every page, so an uncached read would
    #: put the fund's broker-call rate on a human's scrolling. Set BELOW the
    #: worker's 30s tick (``SETTLE_INTERVAL_SECONDS``, app/main.py) so the
    #: scheduled evaluation — the one that writes events — always gets a fresh
    #: reading and only the read-only polls in between reuse one.
    #:
    #: Staleness is disclosed rather than hidden: ``Reconciler.drift`` stamps
    #: its own ``as_of``, and that timestamp rides on the reading into the
    #: assessment, so a reader can always see how old the comparison is. Same
    #: idiom and same reasoning as ``RiskControl.CACHE_TTL_SECONDS``.
    DRIFT_CACHE_TTL_SECONDS = 25.0

    def _venue_drift(self) -> dict[str, Any] | None:
        """The book-vs-venue reading, an honest failure, or None for NOT ASKED.

        THREE STATES, and collapsing any two of them is how the first version
        of this alarm was killed (adversary review, desk d7f38be2):

          * ``None``        — no drift source. This monitor did not look and
                              cannot. ``evaluate_alarms`` produces no drift
                              alarm AND ``run`` refuses to clear a standing
                              one; see ``UNEVALUATED_ON_ABSENT``.
          * ``configured: False`` — we tried and could not read the venue.
                              That RAISES, with ``readable: False``.
          * ``configured: True``  — a real reading, which may or may not drift.

        The killed version returned an empty list on an absence, so the
        post-fill monitor at ``pipeline._apply_status`` — which has no drift
        source and never will — computed "no drift alarm this tick", and
        ``run``'s ``active_keys - current_keys`` wrote a false
        ``RiskAlarmCleared`` into the append-only log on EVERY FILL. An alarm
        that cannot distinguish "I looked and found nothing" from "I could not
        look" is not an alarm, and one that erases itself on the fund's busiest
        code path is worse than none.
        """
        if self._drift_fn is None:
            return None
        now = time.monotonic()
        if self._drift_cache is not None:
            at, cached = self._drift_cache
            if (now - at) < self.DRIFT_CACHE_TTL_SECONDS:
                return cached
        try:
            reading = self._drift_fn()
        except Exception as e:  # noqa: BLE001 — unreadable is not unchanged
            reading = {"configured": False,
                       "reason": f"drift read failed ({type(e).__name__}: {e})"}
        if not isinstance(reading, dict):
            reading = {"configured": False,
                       "reason": (f"drift source returned "
                                  f"{type(reading).__name__}, not a reading")}
        # The FAILURE is cached too, deliberately. A broker that is refusing
        # calls must not be retried once per UI poll — and the alarm the
        # failure raises is identical either way, so nothing is lost by
        # waiting out the TTL before asking again.
        self._drift_cache = (now, reading)
        return reading

    def assess(self) -> dict[str, Any]:
        """The full current risk picture — the CEO's single pane of glass."""
        limits_obj = self._control.limits()
        limits_dict = limits_obj.to_dict()

        # stale_ok: the monitor must keep evaluating the halts while a symbol
        # is unpriceable. Strict compute() raising here took the drawdown and
        # daily-loss checks dark for the whole outage (builder audit H2,
        # 2026-08-20) — the unpriced alarm below was unreachable because this
        # line raised first. Degraded marks are flagged on the snapshot and
        # surfaced as alarms; a dark monitor surfaces nothing.
        snap = self._nav.compute(stale_ok=True)
        nav_usd = float(snap.total_nav_usd)
        cash_usd = float(snap.breakdown.get("cash", 0))
        cash_pct = (cash_usd / nav_usd * 100.0) if nav_usd > 0 else (100.0 if cash_usd > 0 else 0.0)
        gross_exposure_usd = float(snap.breakdown.get("positions", 0))
        gross_exposure_pct = (gross_exposure_usd / nav_usd * 100.0) if nav_usd > 0 else 0.0
        halted = self._control.is_halted()
        halt_state = self._control.halt_state()

        # Drawdown calculation
        history_snaps = self._nav.history(365)
        nav_series = [float(s.get("total_nav_usd", 0)) for s in history_snaps if s.get("total_nav_usd") is not None]
        nav_series.append(nav_usd)
        peak = effective_peak(history_snaps, nav_usd,
                              self._control.drawdown_reference())
        peak_nav = peak["peak_nav"]
        drawdown_pct = ((peak_nav - nav_usd) / peak_nav * 100.0) if peak_nav > 0 else 0.0

        # The historical worst, over the FULL series and deliberately NOT
        # rebased. A rebase moves the point the LIVE control measures from; it
        # does not edit what happened. Erasing a real past drawdown from the
        # record would be the one forbidden move wearing a repair's clothes.
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
            # WHERE the peak came from, so the panel can say it rather than
            # showing a number that quietly stopped meaning "the 365d high".
            "peak_basis": peak["basis"],
            "peak_note": peak["note"],
            "unrebased_peak_nav": round(peak["unrebased_peak_nav"], 2),
            "rebase": peak["rebase"],
            "rebase_token": self._control.drawdown_rebase_token(
                peak["unrebased_peak_nav"]),
        }

        # Positions (per-asset risk)
        book = PositionsProjection(self._store).build()
        positions_list: list[dict[str, Any]] = []
        # Seed with NAV's own degraded-valuation report so a symbol NAV could
        # not price (excluded) or priced from a stale struck mark is named even
        # if the per-symbol loop below happens to price it on a flaky feed.
        unpriced: list[str] = list(getattr(snap, "unpriced_symbols", []) or [])
        nav_stale: list[str] = list(getattr(snap, "stale_symbols", []) or [])
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
                if sym not in unpriced:
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
            # Magnitude, matching the two-sided cap in evaluate_alarms — the
            # UI's breach flag and the alarm must not disagree about the same
            # strategy on the same tick.
            utilization = (abs(weight_pct) / max_strat_limit_pct) if max_strat_limit_pct > 0 else 0.0
            breach = abs(weight_pct) > max_strat_limit_pct
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
        max_strat_weight = max([abs(s["weight_pct"]) for s in strategies_list], default=0.0)
        pos_limit_pct = limits_obj.max_position_pct * 100.0
        strat_limit_pct = limits_obj.max_strategy_pct * 100.0
        cash_limit_pct = limits_obj.min_cash_pct * 100.0

        utilization_map = {
            "max_position_pct": round(max_pos_weight / pos_limit_pct, 4) if pos_limit_pct > 0 else 0.0,
            "max_strategy_pct": round(max_strat_weight / strat_limit_pct, 4) if strat_limit_pct > 0 else 0.0,
            "min_cash_pct": round((cash_limit_pct - cash_pct) / cash_limit_pct, 4) if (cash_limit_pct > 0 and cash_pct < cash_limit_pct) else 0.0,
            "max_drawdown_pct": round(dd_utilization, 4),
        }

        # Marks served from a failed refresh are reported, never presented as
        # fresh: a book valued on stale prices is a book whose NAV is a guess.
        #
        # READ BEFORE ``evaluate_alarms`` AS OF 2026-08-23, and that ordering is
        # the whole of the integrity-producer fix below.
        stale_marks: dict[str, float] = {}
        getter = getattr(self._price, "__self__", None)
        if getter is not None and hasattr(getter, "stale_marks"):
            try:
                stale_marks = getter.stale_marks()
            except Exception:  # noqa: BLE001
                stale_marks = {}

        # The book against the venue. A reading, an honest "could not read", or
        # ABSENT when this monitor was built without a drift source — three
        # states, and ``evaluate_alarms`` treats the third as "not evaluated"
        # rather than "in sync". See ``_venue_drift`` and ``UNEVALUATED_ON_ABSENT``.
        venue_drift = self._venue_drift()

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
            # THE THREE INTEGRITY INPUTS, passed in as of 2026-08-23. Until this
            # change ``unpriced_symbols`` was the only one here and the other two
            # did not reach the evaluator at all — see the block that used to sit
            # after this call, and ``evaluate_alarms`` section 7.
            "unpriced_symbols": unpriced,
            "stale_nav_symbols": nav_stale,
            "stale_marks": stale_marks,
        }
        if venue_drift is not None:
            partial_assessment["venue_drift"] = venue_drift

        alarms = self.evaluate_alarms(partial_assessment)
        alarm_dicts = [a.to_dict() for a in alarms]

        return {
            "nav_usd": round(nav_usd, 2),
            "cash_usd": round(cash_usd, 2),
            "cash_pct": round(cash_pct, 4),
            "gross_exposure_usd": round(gross_exposure_usd, 2),
            "gross_exposure_pct": round(gross_exposure_pct, 4),
            "halted": halted,
            # WHICH kind of dark, so the UI stops saying only "HALTED":
            # `integrity` (we cannot measure) vs `loss` (we measured and do not
            # like it) vs `manual`. None on a pre-classes halt — unknown, not
            # back-filled. `rebase_token` is what the acknowledge-and-rebase
            # control must echo back; it changes whenever the state it describes
            # changes, so a confirm read off a stale screen is refused.
            "halt_class": halt_state.get("halt_class"),
            "halt_reason": halt_state.get("halt_reason"),
            "halted_at": halt_state.get("halted_at"),
            "loss_reference": self._loss_reference_report(nav_usd),
            "rebase_token": self.rebase_token(nav_usd),
            # The halt's acknowledgement state, for the panel that offers the
            # control. `halt_acknowledgement: null` means UNACKNOWLEDGED, never
            # "acknowledged with no detail"; `halt_alarm: null` means the halt
            # never recorded which alarm tripped it, which is why the
            # auto-resume policy will not evaluate it (fails closed).
            "halt_acknowledgement": self._control.halt_acknowledgement(),
            "halt_alarm": self._control.halt_alarm(),
            "halt_ack_token": self._control.halt_ack_token(),
            "autoresume_cooldown_minutes": LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES,
            "drawdown": drawdown,
            "positions": positions_list,
            "strategies": strategies_list,
            "limits": limits_dict,
            "utilization": utilization_map,
            "alarms": alarm_dicts,
            "worst_position": worst_position,
            "unpriced_symbols": unpriced,
            "stale_nav_symbols": nav_stale,
            "stale_marks": stale_marks,
            # The book-vs-venue reading this tick's drift alarm was judged on,
            # or None when this monitor has no drift source. None means NOT
            # LOOKED — a UI reading it must say so and must never render it as
            # agreement.
            "venue_drift": venue_drift,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def _loss_reference_report(self, nav_usd: float) -> dict[str, Any]:
        """What the daily-loss rule is measuring FROM, for the UI.

        ``nav_usd: None`` with ``kind: 'absent'`` is the honest reading when
        there is no reference — the panel must be able to say "not evaluating"
        rather than render a 0.00% loss.
        """
        ref, kind, at = self._loss_reference(
            {"ts": datetime.now(timezone.utc).isoformat()})
        change = None
        if ref:
            change = round((nav_usd - ref) / ref * 100.0, 4)
        return {"nav_usd": ref, "kind": kind, "at": at, "change_pct": change}

    def rebase_token(self, nav_usd: float | None = None) -> str:
        """An 8-char digest of the state a rebase would act on.

        The approval-channel guard's confirm echo needs something to echo, and
        for an order that is the order id. A rebase has no id, so the token IS
        the state: current NAV, the reference it would replace, and the halt.
        Echoing it proves the clicker read the screen AND that the screen was
        current — a confirm copied from a stale panel no longer matches.
        """
        import hashlib

        st = self._fold_state()
        ref, kind, at = self._loss_reference(
            {"ts": datetime.now(timezone.utc).isoformat()})
        if nav_usd is None:
            nav_usd = float(self._nav.compute(stale_ok=True).total_nav_usd)
        raw = f"{round(float(nav_usd), 2)}|{ref}|{kind}|{at}|{st['halted']}|{st['halt_class']}"
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    def _fold_state(self) -> dict[str, Any]:
        return {"halted": self._control.is_halted(fresh=False),
                "halt_class": self._control.halt_class()}

    def _loss_reference(self, a: dict) -> tuple[float | None, str, str | None]:
        """(nav, kind, at) for the daily-loss rule. ``nav`` is None when ABSENT.

        Returns the NEWER of the prior day's last strike and any acknowledged
        rebase. ``kind`` is 'prior_strike' | 'rebased' | 'absent'.
        """
        now_ts = a.get("ts") or datetime.now(timezone.utc).isoformat()
        today_date = now_ts[:10]

        strike_nav: float | None = None
        strike_at: str | None = None
        history_snaps = a.get("history_snaps")
        if history_snaps is None:
            history_snaps = self._nav.history(365)
        for s in (history_snaps or []):
            ts = s.get("ts", "")
            if ts[:10] < today_date:
                try:
                    nav = float(s.get("total_nav_usd", 0))
                except (TypeError, ValueError):
                    continue
                if nav > 0:
                    strike_nav, strike_at = nav, ts

        rebase = None
        try:
            rebase = self._control.loss_reference()
        except Exception:  # noqa: BLE001 — an unreadable rebase must not blind the rule
            rebase = None
        rebase_nav: float | None = None
        rebase_at: str | None = None
        if rebase:
            try:
                nav = float(rebase.get("nav_usd"))
            except (TypeError, ValueError):
                nav = 0.0
            if nav > 0:
                rebase_nav, rebase_at = nav, rebase.get("at")

        if rebase_nav is not None and (strike_at is None or (rebase_at or "") > strike_at):
            return rebase_nav, "rebased", rebase_at
        if strike_nav is not None:
            return strike_nav, "prior_strike", strike_at
        return None, "absent", None

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

        # 2. Daily loss rule.
        #
        # The reference is the prior day's LAST strike — or, if the CEO has
        # acknowledged a loss since then, the rebased reference (C2). Whichever
        # is NEWER wins: a rebase at 14:00 must not be undone by a strike from
        # yesterday, and yesterday's strike must not be undone by a rebase from
        # last week.
        #
        # If there is no reference at all, the rule is UNEVALUABLE and says so.
        # It used to return silently, which read on every surface as "the daily
        # loss limit is fine" — a fund that has never struck a prior-day NAV had
        # no daily-loss kill switch and nothing anywhere said it.
        reference_nav, reference_kind, reference_at = self._loss_reference(a)
        daily_loss_limit = limits.max_daily_loss_pct * 100.0
        if reference_nav is None:
            alarms.append(Alarm(
                key="daily_loss_unevaluable",
                type="data_quality",
                severity="warn",
                message=("the daily-loss halt has NO reference — no prior-day NAV "
                         "strike and no acknowledged rebase — so the "
                         f"{daily_loss_limit:.2f}% daily-loss limit is not being "
                         "evaluated at all; this is an absence, not a pass"),
                metric=0.0,
                threshold=daily_loss_limit,
            ))
        else:
            nav_usd = a.get("nav_usd", 0.0)
            daily_change_pct = ((nav_usd - reference_nav) / reference_nav) * 100.0
            if daily_change_pct < -daily_loss_limit:
                since = (f" since the reference was rebased at {reference_at}"
                         if reference_kind == "rebased" else "")
                alarms.append(Alarm(
                    key="daily_loss",
                    type="daily_loss",
                    severity="critical",
                    message=(f"Daily NAV loss {abs(daily_change_pct):.2f}% exceeds "
                             f"limit {daily_loss_limit:.2f}%{since}"),
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

        # 6. Strategy cap rule — TWO-SIDED.
        #
        # This read `weight > strat_limit`, so a NEGATIVE strategy weight could
        # never breach and the 40% cap was one-sided: a phantom short of any
        # size sat under it forever (validator audit R6/D2, ITEM 3(a),
        # 2026-08-20 — the same mistagged GLD pair). Exposure is exposure in
        # either direction, so the cap is on the MAGNITUDE and the message says
        # which side of zero the weight is on, because "-63% exceeds 40%" reads
        # like a typo unless the word "short" is in the sentence.
        strat_limit = limits.max_strategy_pct * 100.0
        for strat in a.get("strategies", []):
            weight = strat.get("weight_pct", 0.0)
            sid = strat.get("strategy_id", "")
            name = strat.get("name", sid)
            if abs(weight) > strat_limit:
                side = "short" if weight < 0 else "long"
                alarms.append(Alarm(
                    key=f"strategy_cap:{sid}",
                    type="strategy_cap",
                    severity="warn",
                    message=(f"Strategy {name} weight {weight:.2f}% ({side}) exceeds "
                             f"limit {strat_limit:.2f}% of NAV in either direction"),
                    metric=abs(weight),
                    threshold=strat_limit,
                    strategy_id=sid,
                ))

        # 7. DATA QUALITY — the integrity alarms, which until 2026-08-23 had no
        #    producer.
        #
        #    These three were BUILT, in assess(), into a list called
        #    `alarm_dicts` that was appended to the returned payload AFTER
        #    evaluate_alarms had already been called and never passed back in.
        #    So they rendered on /fund/risk/monitor and reached the evaluator
        #    NEVER: no RISK_ALARM_RAISED, no active-alarm row, no entry in the
        #    set evaluate_autoresume reads. The fund could be valuing its book
        #    on marks it knew were stale, with the panel saying so in orange,
        #    and the event log containing not one word of it — which is the
        #    unwired kill switch in its purest form, because the code that
        #    detects the fault was correct and complete and simply had no
        #    consumer.
        #
        #    Wiring them here changes four things and no thresholds: they enter
        #    the event log, they dedupe and clear like every other alarm, they
        #    appear in `active_alarms()`, and they count as open alarms for the
        #    loss auto-resume policy. They remain severity=warn, so they still
        #    cannot auto-halt — the auto-halt gate in run() is on
        #    ("drawdown", "daily_loss") and is untouched. The `data_quality`
        #    -> HALT_INTEGRITY mapping at the top of this module keeps saying
        #    what it said before: it classifies a halt, it does not cause one.
        unpriced = a.get("unpriced_symbols") or []
        if unpriced:
            alarms.append(Alarm(
                key="unpriced", type="data_quality", severity="warn",
                message=(f"no live price for {', '.join(unpriced)} — these positions are "
                         "EXCLUDED from NAV, exposure and every limit check below"),
                metric=float(len(unpriced)), threshold=0.0,
            ))
        nav_stale = a.get("stale_nav_symbols") or []
        if nav_stale:
            alarms.append(Alarm(
                key="stale_nav_marks", type="data_quality", severity="warn",
                message=(f"no live price for {', '.join(nav_stale)} — valued at the "
                         "fund's own LAST STRUCK mark so the limit checks keep "
                         "running; this NAV is degraded, not fresh"),
                metric=float(len(nav_stale)), threshold=0.0,
            ))
        stale_marks = a.get("stale_marks") or {}
        if stale_marks:
            oldest = max(stale_marks.values())
            alarms.append(Alarm(
                key="stale_marks", type="data_quality", severity="warn",
                message=(f"{len(stale_marks)} mark(s) served from a failed refresh, "
                         f"oldest {oldest:.0f}s — valuations below are not live"),
                metric=float(oldest), threshold=0.0,
            ))

        # 8. BOOK vs VENUE — the drift alarm (desk d7f38be2, 2026-08-23).
        #
        #    ABSENCE RAISES. The `configured: False` branch below is the whole
        #    point of the alarm and the reason the first attempt was killed: a
        #    venue we cannot read is a venue we cannot be in sync with, and the
        #    only honest alarm state is "raised, and here is why I could not
        #    look". `assess()` reaching this rule with no `venue_drift` key at
        #    all is a THIRD thing — not asked — and it falls through to no
        #    alarm, protected from a false clear by UNEVALUATED_ON_ABSENT.
        #
        #    NO NEW THRESHOLD. What counts as out-of-sync is the reconciler's
        #    own `in_sync` verdict, computed against reconcile._TOL, read off
        #    the reading rather than recomputed here. Two definitions of "in
        #    sync" is exactly the divergence autopolicy v4 wrote a comment
        #    about when it set its own drift tolerance EQUAL to the
        #    reconciler's; this rule does not even have a copy to keep in step.
        if "venue_drift" in a:
            alarms.append(_drift_alarm(a.get("venue_drift")))

        return [al for al in alarms if al is not None]

    @staticmethod
    def _can_evaluate(alarm_key: str, assessment: dict[str, Any]) -> bool:
        """Did this assessment carry the input `alarm_key`'s rule needs?

        Separate from the rule itself on purpose. "Was this judged?" and "what
        was the verdict?" are different questions, and answering the first by
        inspecting the second is the confusion that makes an unevaluated rule
        look like a passing one.
        """
        if alarm_key == DRIFT_ALARM_KEY:
            return "venue_drift" in assessment
        # An unknown member of UNEVALUATED_ON_ABSENT is treated as NOT
        # evaluable, so a key added to that set without a clause here fails
        # toward never clearing rather than toward clearing blindly.
        return False

    def run(self, actor: str = "monitor") -> dict[str, Any]:
        """The periodic tick: assess -> diff against active alarms -> emit
        RISK_ALARM_RAISED for new breaches, RISK_ALARM_CLEARED for resolved ones
        (dedup by Alarm.key) -> AUTO-HALT on any critical drawdown/daily_loss alarm
        -> for a LOSS halt only, evaluate the four-condition auto-resume policy.
        Returns {"raised": [...], "cleared": [...], "halted": bool,
        "active": [...], "autoresume": {...}|None}.
        Never raises a duplicate for a standing breach.

        AMENDED 2026-08-21 (CEO-approved, "approved yes"): this used to say
        "never auto-resumes". It now does, for a LOSS halt the CEO has
        acknowledged, whose triggering alarm has cleared, with no other
        critical alarm open, after a versioned cool-down — see
        ``evaluate_autoresume``. INTEGRITY, MANUAL and unclassified halts still
        never do.
        """
        assessment = self.assess()
        current_alarms = self.evaluate_alarms(assessment)
        current_map = {a.key: a for a in current_alarms}

        active_raw = self._control.active_alarms()
        active_keys = {a["key"] for a in active_raw}

        new_keys = set(current_map.keys()) - active_keys

        # A TICK MAY ONLY CLEAR WHAT IT COULD JUDGE (2026-08-23).
        #
        # `active_keys - current_keys` treats "this rule evaluated false" and
        # "this rule was never evaluated" as the same fact, and they are
        # opposites. Every alarm before today was computed from the assessment
        # dict alone, so the two coincided and nothing was wrong. The drift
        # alarm is the first that depends on an input SOME MONITORS DO NOT
        # HAVE: `pipeline._apply_status` builds a RiskMonitor with no drift
        # source on every fill, deliberately — a broker round trip per fill is
        # a cost nobody agreed to.
        #
        # Without this filter, that post-fill monitor would emit a
        # RiskAlarmCleared for `book_venue_drift` on EVERY FILL, writing into
        # the append-only log that a book-vs-broker disagreement had resolved,
        # at a moment when nothing had looked at the broker at all. The
        # adversary killed the first version of this alarm for exactly that,
        # and the fix belongs here rather than in the alarm: any future rule
        # with an optional input inherits the same hazard, and a cleared alarm
        # is the one kind of wrong that reads as good news.
        unevaluated = {k for k in UNEVALUATED_ON_ABSENT
                       if k not in current_map and not self._can_evaluate(k, assessment)}
        cleared_keys = active_keys - set(current_map.keys()) - unevaluated

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
        auto_halted = False
        if critical_halt_alarm and not self._control.is_halted():
            self._control.halt(
                reason=f"Auto-halt: {critical_halt_alarm.message}",
                actor="monitor",
                halt_class=classify_halt_cause(critical_halt_alarm.type),
                alarm_type=critical_halt_alarm.type,
                alarm_key=critical_halt_alarm.key,
            )
            auto_halted = True

        # Loss-halt auto-resume (CEO-approved 2026-08-21). Evaluated LAST, on
        # the alarm set this tick just computed, and never in the same tick
        # that halted: a halt and a reopening in one pass would mean the tick
        # disagreed with itself.
        autoresume = None
        if not auto_halted and self._control.is_halted():
            st = self._control._fold(fresh=True)
            autoresume = evaluate_autoresume(
                halt_class=st["halt_class"],
                halted_at=st["halted_at"],
                halt_alarm=st["halt_alarm"],
                acknowledgement=st["halt_ack"],
                current_alarms=[a.to_dict() for a in current_alarms],
            )
            if autoresume["resume"]:
                self._control.resume(actor="auto-resume-loss-v1",
                                     audit=autoresume)

        return {
            "raised": raised_alarms,
            "cleared": cleared_list,
            "halted": self._control.is_halted(),
            "halt_class": self._control.halt_class(),
            "active": self._control.active_alarms(),
            # Present on every tick where a halt was open, so a reader can see
            # WHY it stayed shut, not only that it did.
            "autoresume": autoresume,
        }
