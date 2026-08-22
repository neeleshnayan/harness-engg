"""THE HAZARD BATCH (2026-08-23) — six controls on the first-real-dollar path.

Every test here names the incident it guards, and every one of them FAILS if
the defect it names comes back. That is the whole standard: two tests in this
repository's history once ASSERTED a gate loosening, and a test that cannot
catch its own defect is worse than no test because it certifies the hole.

The six:

  1. ``POST /fund/risk/resume`` had no approval guard while six siblings did.
  2. The three integrity alarms were BUILT and never reached the evaluator.
  3. An autopolicy decline was a ``logger.warning`` and nothing else.
  4. ``AccountState`` read equity and never cash or buying power.
  5. Unrealised P&L ignored the sign of the position, so every exit rule on a
     short was inverted — and the cost basis of a short was wrong too.
  6. Nothing anywhere watched the book against the venue.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

import app.api.v1.fund as api
from app.fund import autopolicy
from app.fund.compliance import AccountState
from app.fund.events import ORDER_ANNOTATION_EVENTS, EventType
from app.fund.exitrule import evaluate as evaluate_rule
from app.fund.projections.orders import OrdersProjection
from app.fund.projections.positions import _new_avg_price
from app.fund.riskmonitor import (
    DRIFT_ALARM_KEY,
    UNEVALUATED_ON_ABSENT,
    RiskControl,
    RiskMonitor,
    _drift_alarm,
    _drift_was_read,
    evaluate_autoresume,
    unrealised_pnl_pct,
)
from app.schemas.fund import RiskResumeRequest


class MemStore:
    """The minimum an append-and-read-back test needs."""

    def __init__(self):
        self.events = []

    def append(self, e):
        self.events.append(e)
        return e

    def by_aggregate(self, aggregate_id):
        return [
            {"type": e.type.value if hasattr(e.type, "value") else e.type,
             "payload": e.payload}
            for e in self.events
            if getattr(e, "aggregate_id", None) == aggregate_id
        ]

    def stream(self, **_kw):
        return []


# ==========================================================================
# 1. GUARD THE RESUME
#
# INCIDENT: resume_trading called _control.resume(actor=req.actor) with actor
# DEFAULTING to "operator" — no allowlist, no echo, no citation, on a CORS-only
# API. An empty POST body re-armed every execution path in the fund. Six
# siblings in the same file were guarded, INCLUDING halt_acknowledge, whose own
# docstring says it re-arms nothing. (CFO GRACE4 2026-08-23; PM readiness
# matrix carried it as a control blocker.) Measured while fixing it: NO TEST IN
# THE REPOSITORY EVER CALLED THIS ENDPOINT, which is how it survived a full
# adversary review of the surrounding module.
# ==========================================================================
class _FakeControl:
    """A control that RECORDS whether the thing behind the guard ran."""

    TOKEN = "ab12cd34"

    def __init__(self):
        self.resumed_by = None

    def halt_ack_token(self):
        return self.TOKEN

    def resume(self, actor):
        self.resumed_by = actor
        return {"status": "resumed", "halted": False}


@pytest.fixture()
def guarded(monkeypatch):
    store, control = MemStore(), _FakeControl()
    monkeypatch.setattr(api, "_store", store)
    monkeypatch.setattr(api, "_control", control)
    return store, control


def _resume(**body):
    return api.resume_trading(RiskResumeRequest(**body))


def _refused_resume(guarded, **body):
    store, control = guarded
    with pytest.raises(HTTPException) as ei:
        _resume(**body)
    assert ei.value.status_code == 403
    # THE LOAD-BEARING ASSERTION. A guard that raises after acting is not a
    # guard. If the refusal ever moves below the resume, this line fails.
    assert control.resumed_by is None, "the halt was REOPENED despite a refusal"
    assert store.events[-1].type == EventType.APPROVAL_REFUSED
    return ei.value.detail


def test_an_empty_body_no_longer_resumes_trading(guarded):
    """THE HOLE ITSELF: `POST /fund/risk/resume` with `{}` used to succeed,
    because `actor` defaulted to "operator" and nothing checked it."""
    detail = _refused_resume(guarded)
    assert "allowlist" in detail


def test_the_old_default_operator_is_refused(guarded):
    """"operator" was the literal default. It must not be a valid approver."""
    detail = _refused_resume(guarded, actor="operator",
                             confirm=_FakeControl.TOKEN)
    assert "allowlist" in detail


def test_a_seat_name_cannot_reopen_trading(guarded):
    assert "allowlist" in _refused_resume(guarded, approver="pm",
                                          confirm=_FakeControl.TOKEN)


def test_a_missing_echo_is_refused(guarded):
    assert "confirm" in _refused_resume(guarded, approver="neelesh")


def test_an_echo_from_a_different_halt_is_refused(guarded):
    """The token digests the halt. A confirm read off a stale screen — a
    DIFFERENT darkness — must not reopen this one."""
    assert "confirm" in _refused_resume(guarded, approver="neelesh",
                                        confirm="deadbeef")


def test_via_cto_must_quote_the_ceo(guarded):
    assert "instruction" in _refused_resume(
        guarded, approver="neelesh-via-cto", confirm=_FakeControl.TOKEN)


def test_a_correct_approval_resumes_and_carries_the_attribution(guarded):
    """The guard must not be so tight it refuses the CEO — a control nobody can
    operate gets removed."""
    _store, control = guarded
    out = _resume(approver="neelesh", confirm=_FakeControl.TOKEN)
    assert out["status"] == "resumed"
    assert control.resumed_by == "neelesh"


def test_via_cto_attribution_reaches_the_resume_event(guarded):
    """The instruction rides onto the actor string, exactly as it does for an
    order approval — the record must show WHICH chair staged it and on what."""
    _store, control = guarded
    _resume(approver="neelesh-via-co-cto", confirm=_FakeControl.TOKEN,
            instruction="reopen it, I have read the halt")
    assert control.resumed_by.startswith("neelesh-via-co-cto [")
    assert "I have read the halt" in control.resumed_by


def test_the_actor_alias_is_guarded_identically(guarded):
    """`actor` is kept only so the existing UI call SHAPE still parses and is
    then refused with a 403 that names the allowlist, instead of a 422 that
    explains nothing. It must not be a second, softer door."""
    _store, control = guarded
    out = _resume(actor="neelesh", confirm=_FakeControl.TOKEN)
    assert out["status"] == "resumed"
    assert control.resumed_by == "neelesh"


def test_approver_wins_over_the_alias_and_both_are_guarded(guarded):
    detail = _refused_resume(guarded, approver="nobody", actor="neelesh",
                             confirm=_FakeControl.TOKEN)
    assert "nobody" in detail


def test_the_allowlist_is_READ_not_copied(guarded, monkeypatch):
    """MOVE THE VALUE. Asserting that "neelesh" is accepted cannot distinguish
    a guard that consults APPROVAL_ALLOWLIST from one with the name baked in —
    they agree on every input while the list stays put. So move it: a name that
    was valid becomes invalid and a name that was not becomes valid. Only a
    real read follows.

    (D16 shipped a test with exactly this blind spot and mutation caught it.)
    """
    _store, control = guarded
    monkeypatch.setattr(api, "APPROVAL_ALLOWLIST", {"someone-else"})

    with pytest.raises(HTTPException):
        _resume(approver="neelesh", confirm=_FakeControl.TOKEN)
    assert control.resumed_by is None

    out = _resume(approver="someone-else", confirm=_FakeControl.TOKEN)
    assert out["status"] == "resumed"
    assert control.resumed_by == "someone-else"


def test_the_echo_is_read_before_the_resume(guarded):
    """A token generated from the POST-resume state must never satisfy the
    guard for the resume that produced it. Pinned by MOVING the token: the
    control's token changes the instant it resumes, and the guard has to have
    used the pre-resume one."""
    store, control = guarded
    before = control.halt_ack_token()

    def resume(actor):
        control.resumed_by = actor
        control.TOKEN = "99999999"  # the state moved
        return {"status": "resumed", "halted": False}

    control.resume = resume
    out = _resume(approver="neelesh", confirm=before)
    assert out["status"] == "resumed"


# ==========================================================================
# 2. THE INTEGRITY ALARMS GET A PRODUCER
#
# INCIDENT: unpriced / stale_nav_marks / stale_marks were constructed in
# assess() AFTER evaluate_alarms had already been called, appended only to the
# returned payload, and never passed back into the evaluator. They rendered on
# the panel and reached the event log NEVER — no RiskAlarmRaised, no
# active_alarms row, no entry in the set evaluate_autoresume reads. The fund
# could be valuing its book on marks it KNEW were stale with the log silent.
# ==========================================================================
def _monitor(store=None, **kw):
    store = store or MemStore()
    return RiskMonitor(nav_service=None, store=store,
                       control=RiskControl(store=store), **kw)


_BASE = {"limits": {}, "history_snaps": [], "positions": [], "strategies": []}


def _keys(assessment_bits):
    return {a.key for a in _monitor().evaluate_alarms({**_BASE, **assessment_bits})}


def test_unpriced_symbols_reach_the_evaluator():
    assert "unpriced" in _keys({"unpriced_symbols": ["GLD"]})


def test_stale_nav_marks_reach_the_evaluator():
    """This one and stale_marks were not even PASSED to evaluate_alarms before
    — `partial_assessment` carried unpriced_symbols alone."""
    assert "stale_nav_marks" in _keys({"stale_nav_symbols": ["TLT"]})


def test_stale_marks_reach_the_evaluator():
    assert "stale_marks" in _keys({"stale_marks": {"SPY": 900.0}})


def test_no_integrity_alarm_when_everything_is_priced_and_fresh():
    """The other half: these must not fire on a healthy tick, or the log fills
    with noise and the operator learns to ignore the colour."""
    keys = _keys({"unpriced_symbols": [], "stale_nav_symbols": [],
                  "stale_marks": {}})
    assert {"unpriced", "stale_nav_marks", "stale_marks"} & keys == set()


def test_an_integrity_alarm_is_RAISED_INTO_THE_EVENT_LOG():
    """THE REGRESSION TEST FOR THE WHOLE DEFECT. Not "does assess() show it" —
    it always showed it. Does run() APPEND it. "Audible" means in the event
    log, never a rendered colour and never a logger.warning (riskofficer,
    2026-08-22)."""
    store = MemStore()
    m = _monitor(store=store)
    m.assess = lambda: {**_BASE, "unpriced_symbols": ["GLD"], "nav_usd": 100.0}
    out = m.run(actor="test")

    assert "unpriced" in [a["key"] for a in out["raised"]]
    appended = [e for e in store.events
                if e.type == EventType.RISK_ALARM_RAISED
                and e.payload.get("key") == "unpriced"]
    assert len(appended) == 1, "the integrity alarm never reached the log"
    assert appended[0].payload["type"] == "data_quality"


def test_an_integrity_alarm_does_not_auto_halt():
    """The auto-halt gate is ("drawdown", "daily_loss") and this change does
    not widen it. Creating an integrity AUTO-halt is a policy decision for a
    human, and this test fails if one ever appears by accident."""
    store = MemStore()
    m = _monitor(store=store)
    m.assess = lambda: {**_BASE, "unpriced_symbols": ["GLD", "TLT"],
                        "stale_marks": {"SPY": 9000.0}, "nav_usd": 100.0}
    out = m.run(actor="test")
    assert out["halted"] is False
    assert not [e for e in store.events if e.type == EventType.TRADING_HALTED]


# ==========================================================================
# 6. THE BOOK-VS-VENUE DRIFT ALARM
#
# INCIDENT: seven alarm types and not one watched the broker, while book and
# venue disagreed on TEN OF ELEVEN symbols worth $126.54 = 6.71% of NAV. The
# first attempt at this alarm was KILLED because it returned an empty list on
# an absence, and the post-fill monitor then erased it — writing a false
# RiskAlarmCleared into the append-only log on every fill.
# ==========================================================================

#: The live reading from 2026-08-23, trimmed to its shape. The acceptance
#: condition the brief set was that the alarm fires on TODAY'S ACTUAL STATE,
#: so today's actual state is the fixture.
LIVE_DRIFT_2026_08_23 = {
    "configured": True,
    "book_nav": "1885.74", "broker_equity": "2012.28",
    "delta_usd": "126.54", "delta_pct": 6.7104,
    "symbols_out_of_sync": 10,
    "per_symbol": [
        {"symbol": "DBA", "drift": "-5.314306", "in_sync": False},
        {"symbol": "DBC", "drift": "-8.122157", "in_sync": False},
        {"symbol": "F", "drift": "0.0", "in_sync": True},
        {"symbol": "GLD", "drift": "0.424471", "in_sync": False},
        {"symbol": "INTC", "drift": "1.608762", "in_sync": False},
        {"symbol": "MSFT", "drift": "0.340051", "in_sync": False},
        {"symbol": "NVDA", "drift": "0.749886", "in_sync": False},
        {"symbol": "SOFI", "drift": "9.18819", "in_sync": False},
        {"symbol": "SPY", "drift": "-0.128362", "in_sync": False},
        {"symbol": "TLT", "drift": "-3.019871", "in_sync": False},
        {"symbol": "XLE", "drift": "2.749912", "in_sync": False},
    ],
}


def test_the_alarm_fires_on_the_measured_live_drift_state():
    """ACCEPTANCE: the condition is true on the fund's real book TODAY, so an
    alarm that does not fire on it is decoration."""
    alarm = _drift_alarm(LIVE_DRIFT_2026_08_23)
    assert alarm is not None
    assert alarm.key == DRIFT_ALARM_KEY
    assert alarm.severity == "critical"
    assert alarm.metric == 10.0
    assert "10 of 11" in alarm.message
    assert "126.54" in alarm.message


@pytest.mark.parametrize("reading, why", [
    (None, "no reading at all"),
    ("not a dict", "a string where a reading should be"),
    ({"configured": False, "reason": "broker not configured"}, "unconfigured"),
    ({"configured": False}, "unconfigured with no reason given"),
    ({"configured": True}, "configured but no per-symbol reading"),
    ({"configured": True, "per_symbol": "rows"}, "per_symbol not a list"),
])
def test_absence_RAISES(reading, why):
    """THE ADVERSARY'S KILL, closed. "I looked and found nothing" and "I could
    not look" are opposite facts, and every shape of the second must alarm.
    An alarm silenced by the failure of the thing it watches is not an alarm."""
    alarm = _drift_alarm(reading)
    assert alarm is not None, f"silent on: {why}"
    assert alarm.severity == "critical"
    assert "UNKNOWN" in alarm.message
    assert "not agreement" in alarm.message or "not in sync" in alarm.message


@pytest.mark.parametrize("rows", [
    [],
    [{"symbol": "SPY", "in_sync": True}, {"symbol": "TLT", "in_sync": True}],
])
def test_a_clean_reading_is_silent(rows):
    """The other direction, and it is not optional: an alarm that always fires
    is an alarm the operator turns off."""
    assert _drift_alarm({"configured": True, "per_symbol": rows}) is None


def test_every_drift_state_shares_ONE_key():
    """run() dedups and clears BY KEY. If "cannot read the broker" carried a
    different key from "the broker disagrees", then going blind would emit a
    RiskAlarmCleared for the drift — the log would record a $126 disagreement
    RESOLVING at the exact moment the fund stopped being able to see it."""
    drifting = _drift_alarm(LIVE_DRIFT_2026_08_23)
    blind = _drift_alarm({"configured": False, "reason": "timeout"})
    assert drifting.key == blind.key == DRIFT_ALARM_KEY


def test_the_three_state_contract_on_the_reader():
    """None means NOT ASKED. It must never be manufactured into a reading."""
    assert _monitor()._venue_drift() is None

    def boom():
        raise RuntimeError("broker down")

    failed = _monitor(drift_fn=boom)._venue_drift()
    assert failed["configured"] is False and "broker down" in failed["reason"]

    junk = _monitor(drift_fn=lambda: ["nope"])._venue_drift()
    assert junk["configured"] is False and "not a reading" in junk["reason"]


def test_a_monitor_WITHOUT_a_drift_source_CANNOT_CLEAR_A_STANDING_ALARM():
    """THE KILL, at the structural level. pipeline._apply_status builds a
    RiskMonitor with no drift source on EVERY FILL. Before this fix that tick
    computed "no drift alarm" and run() cleared the standing one, writing a
    false RiskAlarmCleared into the append-only log on every single fill."""
    store = MemStore()
    m = _monitor(store=store)  # no drift_fn — the post-fill monitor's shape
    m.assess = lambda: {**_BASE, "nav_usd": 100.0}  # no venue_drift key
    m._control.active_alarms = lambda: [
        {"key": DRIFT_ALARM_KEY, "type": DRIFT_ALARM_KEY}]

    out = m.run(actor="fill_re-eval")

    assert DRIFT_ALARM_KEY not in out["cleared"]
    assert not [e for e in store.events
                if e.type == EventType.RISK_ALARM_CLEARED
                and e.payload.get("key") == DRIFT_ALARM_KEY]


def test_a_monitor_WITH_a_drift_source_DOES_clear_it_when_it_resolves():
    """The counterpart, and it is what stops the fix from becoming "this alarm
    can never clear" — which would be a stuck alarm wearing a fix's clothes."""
    store = MemStore()
    m = _monitor(store=store, drift_fn=lambda: {"configured": True,
                                                "per_symbol": []})
    m.assess = lambda: {**_BASE, "nav_usd": 100.0,
                        "venue_drift": {"configured": True, "per_symbol": []}}
    m._control.active_alarms = lambda: [
        {"key": DRIFT_ALARM_KEY, "type": DRIFT_ALARM_KEY}]

    out = m.run(actor="monitor")

    assert DRIFT_ALARM_KEY in out["cleared"]


def test_an_unreadable_venue_does_not_clear_the_drift_alarm_either():
    """Between the two: the monitor DID look, and could not see. The alarm
    stays up (same key), so no clear is emitted."""
    store = MemStore()
    reading = {"configured": False, "reason": "timeout"}
    m = _monitor(store=store, drift_fn=lambda: reading)
    m.assess = lambda: {**_BASE, "nav_usd": 100.0, "venue_drift": reading}
    m._control.active_alarms = lambda: [
        {"key": DRIFT_ALARM_KEY, "type": DRIFT_ALARM_KEY}]
    assert DRIFT_ALARM_KEY not in m.run(actor="monitor")["cleared"]


def test_drift_blocks_the_loss_halt_from_auto_resuming():
    """A deliberate consequence of severity=critical, pinned so it cannot be
    softened by accident: the fund must not reopen execution automatically
    while it does not know what it holds."""
    verdict = evaluate_autoresume(
        halt_class="loss", halted_at="2026-08-23T00:00:00+00:00",
        halt_alarm={"type": "daily_loss", "key": "daily_loss"},
        acknowledgement={"halted_at": "2026-08-23T00:00:00+00:00",
                         "at": "2026-08-23T00:00:00+00:00", "actor": "neelesh"},
        current_alarms=[_drift_alarm(LIVE_DRIFT_2026_08_23).to_dict()])
    assert verdict["resume"] is False
    blocked = [c for c in verdict["conditions"]
               if c["condition"] == "no_other_critical_alarm"]
    assert blocked and blocked[0]["ok"] is False
    assert DRIFT_ALARM_KEY in blocked[0]["other_critical"]


def test_the_drift_read_is_cached_so_a_ui_poll_is_not_a_broker_round_trip():
    """assess() is what the risk bar polls on every page and drift() costs two
    Alpaca calls. Without the cache the fund's broker-call rate is a function
    of somebody scrolling."""
    calls = []

    def counting():
        calls.append(1)
        return {"configured": True, "per_symbol": []}

    m = _monitor(drift_fn=counting)
    for _ in range(5):
        m._venue_drift()
    assert len(calls) == 1


def test_a_failed_drift_read_is_cached_too():
    """A broker refusing calls must not be retried once per poll. The alarm is
    identical either way, so nothing is lost by waiting out the TTL."""
    calls = []

    def failing():
        calls.append(1)
        raise RuntimeError("429")

    m = _monitor(drift_fn=failing)
    for _ in range(4):
        assert m._venue_drift()["configured"] is False
    assert len(calls) == 1


def test_the_cache_expires():
    """MOVE THE TTL. A test that only proves "the second call is cached" cannot
    tell a cache from a call-once bug."""
    calls = []

    def counting():
        calls.append(1)
        return {"configured": True, "per_symbol": []}

    m = _monitor(drift_fn=counting)
    m.DRIFT_CACHE_TTL_SECONDS = -1.0  # every read is past the ceiling
    m._venue_drift()
    m._venue_drift()
    assert len(calls) == 2


# ==========================================================================
# 3. THE AUTOPOLICY DECLINE BECOMES A RECORD (PM R41)
#
# INCIDENT: the decline path was a logger.warning, beneath eleven lines of its
# own comment arguing that a silent refusal is the unwired kill switch wearing
# the opposite costume. The seat whose job is auditing this policy reads
# /fund/events, not stdout. On 2026-09-08 the fund's own TLT and DBC time exits
# fall due, v4 refuses them, the proposal expires at 120 minutes and does NOT
# come back — and nothing the CEO could see said so.
# ==========================================================================
ORDER = {"order_id": "aa11bb22-3344-5566-7788-99aabbccddee", "symbol": "TLT",
         "side": "sell", "qty": 3.019871}
VERDICT = {"approve": False,
           "checks": [{"check": "fresh", "ok": False},
                      {"check": "exit_rule_linked", "ok": True}]}


def test_a_declined_tick_produces_a_readable_record():
    """THE BRIEF'S ACCEPTANCE CONDITION. Read it back off the store the way an
    auditor would, by aggregate."""
    store = MemStore()
    autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT)

    rows = [e for e in store.events
            if e.type == EventType.AUTOPOLICY_DECLINED]
    assert len(rows) == 1
    p = rows[0].payload
    assert p["order_id"] == ORDER["order_id"]
    assert p["symbol"] == "TLT"
    assert p["failed_checks"] == ["fresh"]
    assert p["evaluation"] == VERDICT
    assert p["policy_version"] == autopolicy.AUTOPOLICY_VERSION
    assert rows[0].aggregate_id == ORDER["order_id"]


def test_the_record_names_WHICH_checks_failed():
    """A decline that does not say why is a shrug in the log. Two failures must
    both survive, sorted so the idempotency key is stable."""
    store = MemStore()
    autopolicy.record_decline(
        store, ORDER, ["mark_corroborated", "fresh"],
        {"approve": False, "checks": []})
    assert (store.events[-1].payload["failed_checks"]
            == ["fresh", "mark_corroborated"])


def test_the_decline_is_idempotent_across_ticks():
    """The tick runs every 30s. An order outside the envelope for its full
    120-minute life would append 240 identical events — which is how a control
    that works becomes a control the operator turns off (ExitRules.enforce's
    own words, learned in the other direction)."""
    store = MemStore()
    first = autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT)
    assert first is not None
    for _ in range(10):
        assert autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT) is None
    assert len([e for e in store.events
                if e.type == EventType.AUTOPOLICY_DECLINED]) == 1


def test_a_CHANGED_verdict_is_recorded_again():
    """Idempotency must not swallow news. An order refused for a stale mark and
    now refused for a dead heartbeat has had two different things go wrong, and
    collapsing them hides the second."""
    store = MemStore()
    autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT)
    assert autopolicy.record_decline(
        store, ORDER, ["heartbeat_alive"], VERDICT) is not None
    assert len([e for e in store.events
                if e.type == EventType.AUTOPOLICY_DECLINED]) == 2


def test_a_verdict_that_reverts_is_recorded_again():
    """...and back. The comparison is against the LAST decline only, so an
    order that oscillates records each change rather than deduping against
    ancient history."""
    store = MemStore()
    autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT)
    autopolicy.record_decline(store, ORDER, ["heartbeat_alive"], VERDICT)
    assert autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT) is not None


def test_two_orders_do_not_dedupe_against_each_other():
    store = MemStore()
    other = {**ORDER, "order_id": "ffffffff-0000-0000-0000-000000000000"}
    assert autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT)
    assert autopolicy.record_decline(store, other, ["fresh"], VERDICT)


def test_an_unreadable_log_fails_toward_RECORDING_the_decline():
    """A repeated finding is noise; a missing one is the defect being closed.
    So an unreadable history duplicates rather than swallows."""
    class Unreadable(MemStore):
        def by_aggregate(self, aggregate_id):
            raise RuntimeError("postgres is down")

    store = Unreadable()
    assert autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT)
    assert autopolicy.record_decline(store, ORDER, ["fresh"], VERDICT)
    assert len(store.events) == 2


def test_no_store_still_declines():
    """The recording is additive. Every existing caller passes no store and
    must keep working exactly as before."""
    assert autopolicy.record_decline(None, ORDER, ["fresh"], VERDICT) is None


def test_run_records_the_decline_and_does_not_approve():
    """The recording half, against a fake pipeline.

    RENAMED AT D18. It used to be called `..._and_leaves_the_order_pending` and
    its body never called `pending()` — the adversary's second rule, verbatim:
    re-read every test whose NAME states an invariant its BODY does not assert.
    The pending half is now
    `test_a_policy_declined_order_is_STILL_PENDING_end_to_end`, which folds a
    real store instead of asserting against a stub.
    """
    store = MemStore()

    class Pipe:
        approved = []

        def approve_order(self, oid, **kw):
            self.approved.append(oid)

    pipe = Pipe()
    out = autopolicy.run(pipe, [{**ORDER, "age_minutes": 900.0}],
                         halted=False, heartbeats={}, store=store)

    assert pipe.approved == [], "a declined order must not be approved"
    assert len(out["skipped"]) == 1
    assert out["skipped"][0]["recorded"] is True
    assert out["skipped"][0]["failed_checks"]
    ev = [e for e in store.events if e.type == EventType.AUTOPOLICY_DECLINED]
    assert len(ev) == 1
    # SAME CONTENT, DIFFERENT ORDER, deliberately: `skipped` preserves the
    # order the checks were evaluated in (useful to a human reading a tick),
    # and the event SORTS them because the sorted set is the idempotency key.
    # Compared as sets so neither can silently drop a check.
    assert (set(ev[0].payload["failed_checks"])
            == set(out["skipped"][0]["failed_checks"]))
    assert ev[0].payload["failed_checks"] == sorted(
        set(out["skipped"][0]["failed_checks"]))


def test_run_without_a_store_still_reports_recorded_false():
    """`recorded: False` must mean "not written down", never "no decline
    happened". The caller has to be able to tell those apart."""
    class Pipe:
        def approve_order(self, oid, **kw):  # pragma: no cover - never reached
            raise AssertionError("must not approve")

    out = autopolicy.run(Pipe(), [{**ORDER, "age_minutes": 900.0}],
                         halted=False, heartbeats={})
    assert out["skipped"][0]["recorded"] is False
    assert out["skipped"][0]["failed_checks"]


# ==========================================================================
# 4. AccountState LEARNS CASH AND BUYING POWER (PM R42)
# ==========================================================================
class _Acct:
    equity = "2012.28"
    cash = "1885.74"
    buying_power = "3771.48"
    daytrade_count = 0
    pattern_day_trader = False
    trading_blocked = False
    account_blocked = False
    shorting_enabled = True
    status = "ACTIVE"


def _standing(acct):
    from app.fund.connectors.alpaca import AlpacaConnector
    return AlpacaConnector._standing(acct)


def test_the_typed_account_path_reports_cash_and_buying_power():
    """account_info() read both off the same object all along; the TYPED path
    the compliance gate uses read neither, so the fund knew its equity and not
    whether it could pay for anything."""
    st = _standing(_Acct())
    assert st.cash == 1885.74
    assert st.buying_power == 3771.48
    assert st.to_dict()["cash"] == 1885.74
    assert st.to_dict()["buying_power"] == 3771.48


def test_an_unreported_field_is_None_and_NOT_ZERO():
    """Absence is never zero. Read as 0.0, a real balance looks spent and an
    empty one looks the same — and only one of those is true at a time."""
    class Sparse:
        equity = "10.0"
        status = "ACTIVE"

    st = _standing(Sparse())
    assert st.cash is None
    assert st.buying_power is None
    assert st.equity == 10.0


def test_an_unreadable_account_reports_neither():
    st = AccountState.unknown("credentials missing")
    assert st.known is False
    assert st.cash is None and st.buying_power is None
    assert st.to_dict()["cash"] is None


def test_the_new_fields_block_nothing():
    """READ AND REPORTED, not enforced. A refusal built on cash or buying power
    is a MANDATE decision for a human — "may the fund borrow" is not a question
    a builder answers while wiring a getter. This fails the day one appears, so
    the decision has to be made deliberately rather than arrived at."""
    import inspect

    from app.fund import compliance

    gate_src = inspect.getsource(compliance.ComplianceGate)
    for field in ("buying_power", "state.cash"):
        assert field not in gate_src, (
            f"ComplianceGate now reads {field!r}. If that is a real block, it "
            f"is a mandate change and needs a human's decision on the record — "
            f"not an updated assertion here.")


# ==========================================================================
# 5. THE SIGN-INVERTED EXIT TRIGGER (desk 34338ef6)
#
# INCIDENT: riskmonitor computed (mark - avg_cost)/avg_cost with no reference
# to the sign of qty, and positions.py only updated avg_price on a BUY. On a
# short a RISING price is a LOSS and read as a GAIN, so a loss_pct stop would
# never fire while the short bled and a gain_pct exit would fire precisely when
# it was losing. Every exit rule on a short was inverted.
#
# GATING: no short-selling strategy deploys before this is closed. It is
# registered as the `exit_sign_fixed` alpaca-prod precondition.
# ==========================================================================
def test_a_rising_price_is_a_GAIN_on_a_long():
    """The half that was always right, pinned so the fix cannot invert it."""
    assert unrealised_pnl_pct(qty=10, mark=110.0, avg_cost=100.0) == pytest.approx(10.0)


def test_a_rising_price_is_a_LOSS_on_a_short():
    """THE DEFECT. This returned +10.0 — a short bleeding 10% reported as a
    10% gain."""
    assert unrealised_pnl_pct(qty=-10, mark=110.0, avg_cost=100.0) == pytest.approx(-10.0)


def test_a_falling_price_is_a_GAIN_on_a_short():
    assert unrealised_pnl_pct(qty=-10, mark=90.0, avg_cost=100.0) == pytest.approx(10.0)


def test_a_falling_price_is_a_LOSS_on_a_long():
    assert unrealised_pnl_pct(qty=10, mark=90.0, avg_cost=100.0) == pytest.approx(-10.0)


def test_an_unknown_basis_still_returns_zero():
    """PRESERVED, not improved. Changing what avg_cost<=0 returns would move
    the underwater alarm and every exit rule for reasons unrelated to the sign;
    it is a separate defect with a separate owner."""
    assert unrealised_pnl_pct(qty=-10, mark=110.0, avg_cost=0.0) == 0.0


def test_a_LOSS_STOP_FIRES_ON_A_BLEEDING_SHORT():
    """THE MONEY TEST, end to end through the rule the fund actually commits.
    A short at 100, price up to 115, with a 10% stop. Before the fix this
    evaluated at +15% and the stop sat there while the position bled."""
    pnl = unrealised_pnl_pct(qty=-10, mark=115.0, avg_cost=100.0)
    rule = {"kind": "loss_pct", "threshold_pct": 10.0, "set_at": "2026-08-23"}
    assert evaluate_rule(rule, unrealised_pnl_pct=pnl)["fired"] is True


def test_a_GAIN_EXIT_DOES_NOT_FIRE_ON_A_BLEEDING_SHORT():
    """The inverse half, and the more expensive one: the old code would have
    taken 'profit' on a position that was 15% underwater."""
    pnl = unrealised_pnl_pct(qty=-10, mark=115.0, avg_cost=100.0)
    rule = {"kind": "gain_pct", "threshold_pct": 10.0, "set_at": "2026-08-23"}
    assert evaluate_rule(rule, unrealised_pnl_pct=pnl)["fired"] is False


def test_a_gain_exit_fires_on_a_WINNING_short():
    """...and still works when the short is actually winning."""
    pnl = unrealised_pnl_pct(qty=-10, mark=85.0, avg_cost=100.0)
    rule = {"kind": "gain_pct", "threshold_pct": 10.0, "set_at": "2026-08-23"}
    assert evaluate_rule(rule, unrealised_pnl_pct=pnl)["fired"] is True


def test_the_long_exit_rules_are_UNCHANGED():
    """A fix that also moved the long behaviour would be a new defect wearing a
    repair's clothes — every live position in the fund is long."""
    down = unrealised_pnl_pct(qty=10, mark=85.0, avg_cost=100.0)
    up = unrealised_pnl_pct(qty=10, mark=115.0, avg_cost=100.0)
    loss = {"kind": "loss_pct", "threshold_pct": 10.0, "set_at": "2026-08-23"}
    gain = {"kind": "gain_pct", "threshold_pct": 10.0, "set_at": "2026-08-23"}
    assert evaluate_rule(loss, unrealised_pnl_pct=down)["fired"] is True
    assert evaluate_rule(gain, unrealised_pnl_pct=down)["fired"] is False
    assert evaluate_rule(gain, unrealised_pnl_pct=up)["fired"] is True
    assert evaluate_rule(loss, unrealised_pnl_pct=up)["fired"] is False


# --- the cost basis, case by case ------------------------------------------
def D_(x):
    return Decimal(str(x))


def _avg(old_qty, old_avg, signed, px):
    return _new_avg_price(D_(old_qty), D_(old_avg), D_(signed), D_(px),
                          D_(old_qty) + D_(signed))


def test_basis_opening_from_flat_long():
    assert _avg(0, 0, 10, 100) == D_(100)


def test_basis_opening_from_flat_short():
    assert _avg(0, 0, -10, 100) == D_(100)


def test_basis_adding_to_a_long_averages():
    assert _avg(10, 100, 10, 110) == D_(105)


def test_basis_ADDING_TO_A_SHORT_AVERAGES():
    """DEFECT: `if signed > 0` asks "was this a BUY". Adding to a short is a
    SELL, so the basis never moved — it stayed at 100 instead of 95."""
    assert _avg(-10, 100, -10, 90) == D_(95)


def test_basis_reducing_a_long_does_not_move():
    assert _avg(10, 100, -5, 110) == D_(100)


def test_basis_REDUCING_A_SHORT_DOES_NOT_MOVE():
    """DEFECT, and the nastiest one: covering half a short took `signed > 0`
    and ran the weighted average with a NEGATIVE denominator —
    (-10*100 + 5*90) / -5 = 110. Reducing a position CORRUPTED the basis of the
    part still open, in the profitable-looking direction."""
    assert _avg(-10, 100, 5, 90) == D_(100)


def test_basis_CROSSING_ZERO_LONG_TO_SHORT_REPRICES():
    """DEFECT: long 10 @ 100, sell 20 @ 110 leaves a short 10 whose true basis
    is 110. It stayed at 100, so the new short was born reporting a 10% gain it
    never made."""
    assert _avg(10, 100, -20, 110) == D_(110)


def test_basis_crossing_zero_short_to_long_reprices():
    assert _avg(-10, 100, 20, 90) == D_(90)


def test_basis_going_flat_keeps_the_last_price():
    """Not zeroed: a 0.00 basis is read as "unknown" by the P&L formula's
    avg_cost<=0 branch, so zeroing a closed position would silently make its
    history unreadable."""
    assert _avg(10, 100, -10, 130) == D_(100)


def test_basis_treats_a_QUANTITY_RESIDUE_as_flat():
    """A position that is 1e-15 shares "long" is CLOSED, so the next fill sets
    the basis outright rather than weighted-averaging against a ghost.

    No such residue exists in the live log today — measured 2026-08-23, seven
    closed symbols sit at EXACTLY zero because this projection is Decimal. The
    epsilon guards the paths that can still produce one: a corporate action
    divides quantities, and BookReconciledToVenue SETS them from a broker
    string.

    Written after the first version of this test used 1e-15 MINUS 1e-15, which
    is exactly zero and therefore proved nothing about the epsilon — mutation
    caught it (an `== 0` test passed it unharmed).
    """
    # 1e-15 shares left over, then a real 10-share buy at 200.
    assert _avg("1e-15", 100, 10, 200) == D_(200)
    # ...and the same on the short side.
    assert _avg("-1e-15", 100, -10, 200) == D_(200)


def test_the_FOLD_uses_the_new_rule(  # noqa: D401
):
    """THE WIRING, not the arithmetic. `_new_avg_price` could be flawless and
    uncalled — a control is not done until something calls it. This drives the
    real ``PositionsProjection._apply`` over real ORDER_FILLED events.

    Written after mutation: restoring the ORIGINAL `if signed > 0` line inside
    the fold left every basis test above passing, because they all called the
    helper directly.
    """
    from app.fund.projections.positions import Book, PositionsProjection

    def fill(book, side, qty, px, symbol="SPY"):
        PositionsProjection._apply(book, {
            "type": EventType.ORDER_FILLED.value,
            "payload": {"symbol": symbol, "side": side, "filled_qty": qty,
                        "avg_price": px, "fees": 0}})

    # long 10 @ 100, then SELL 20 @ 110 -> short 10, basis must reprice to 110
    b = Book()
    fill(b, "buy", 10, 100)
    fill(b, "sell", 20, 110)
    assert b.positions["SPY"]["qty"] == D_(-10)
    assert b.positions["SPY"]["avg_price"] == D_(110), (
        "the fold kept the LONG basis on a flipped position")

    # short 10 @ 100, then SELL 10 more @ 90 -> basis must average to 95
    b2 = Book()
    fill(b2, "sell", 10, 100)
    fill(b2, "sell", 10, 90)
    assert b2.positions["SPY"]["qty"] == D_(-20)
    assert b2.positions["SPY"]["avg_price"] == D_(95), (
        "adding to a short did not move its basis")

    # short 10 @ 100, then BUY 5 @ 90 (covering) -> basis must NOT move.
    # The original line ran the weighted average with a negative denominator
    # here and produced 110.
    b3 = Book()
    fill(b3, "sell", 10, 100)
    fill(b3, "buy", 5, 90)
    assert b3.positions["SPY"]["qty"] == D_(-5)
    assert b3.positions["SPY"]["avg_price"] == D_(100), (
        "covering part of a short corrupted the basis of the rest")


def test_the_fold_is_unchanged_for_the_long_only_history_the_fund_actually_has():
    """MEASURED SEPARATELY, PINNED HERE. Folding all 29 OrderFilled events in
    the live log under the old and new rules produced identical cost bases for
    all 11 symbols, and no negative quantity is ever reached. This is the
    long-only shape that result depends on."""
    from app.fund.projections.positions import Book, PositionsProjection

    def fill(book, side, qty, px):
        PositionsProjection._apply(book, {
            "type": EventType.ORDER_FILLED.value,
            "payload": {"symbol": "TLT", "side": side, "filled_qty": qty,
                        "avg_price": px, "fees": 0}})

    b = Book()
    fill(b, "buy", 2, 80)          # basis 80
    fill(b, "buy", 2, 90)          # -> 85
    fill(b, "sell", 1, 120)        # reducing: unchanged
    assert b.positions["TLT"]["avg_price"] == D_(85)
    assert b.positions["TLT"]["qty"] == D_(3)


# --- the rest of the short's blast radius ----------------------------------
# --- through the REAL assess(), against a REAL short -----------------------
#
# Everything above this line tests pure functions. That is necessary and not
# sufficient: the defect was as much in the WIRING as in the arithmetic — the
# integrity alarms were correct code that reached no consumer, and a sign fix
# that never gets called is the same shape of nothing. These build an actual
# short in an actual book and read the actual row.
def _short_the_book(wire, symbol="AAPL", qty=5.0, price=200.0):
    """Sell a symbol the fund does not hold. The fold takes qty negative —
    which is exactly the accidental short nothing in the book can currently
    distinguish from an intended one."""
    from app.fund.events import Event

    wire.store.append(Event(
        aggregate_id="short-test-order", aggregate_type="order",
        type=EventType.ORDER_FILLED,
        payload={"symbol": symbol, "side": "sell", "strategy_id": "s1",
                 "filled_qty": qty, "avg_price": price, "fees": 0},
        actor="test"))


def test_assess_reports_a_real_short_as_LOSING_when_the_price_rises(wire):
    """END TO END. Short 5 AAPL at $200, price rises to $220. The row must say
    -10%, and before the fix it said +10% — which is the number every exit rule
    in the fund is evaluated against."""
    _short_the_book(wire, "AAPL", 5.0, 200.0)
    wire.conn._prices["AAPL"] = 220.0

    control = RiskControl(wire.store)
    m = RiskMonitor(nav_service=wire.nav, store=wire.store,
                    pricer=wire.conn.price, control=control)
    row = next(p for p in m.assess()["positions"] if p["symbol"] == "AAPL")

    assert row["qty"] == -5.0
    assert row["unrealized_pnl_pct"] == pytest.approx(-10.0)
    assert row["side"] == "short"


def test_assess_stamps_side_on_a_long(wire):
    from app.fund.events import Event
    wire.store.append(Event(
        aggregate_id="long-test-order", aggregate_type="order",
        type=EventType.ORDER_FILLED,
        payload={"symbol": "AAPL", "side": "buy", "strategy_id": "s1",
                 "filled_qty": 5.0, "avg_price": 200.0, "fees": 0},
        actor="test"))
    control = RiskControl(wire.store)
    m = RiskMonitor(nav_service=wire.nav, store=wire.store,
                    pricer=wire.conn.price, control=control)
    row = next(p for p in m.assess()["positions"] if p["symbol"] == "AAPL")
    assert row["side"] == "long"
    assert row["qty"] == 5.0


def test_assess_shocks_a_short_ADVERSELY(wire):
    """shock_20_usd was `value * -0.20`, and a short's value is NEGATIVE — so
    the row reporting a short's disaster reported it as a $200 gain. Read off
    the real row, because the arithmetic being right in a comment is not the
    thing that failed."""
    _short_the_book(wire, "AAPL", 5.0, 200.0)
    control = RiskControl(wire.store)
    m = RiskMonitor(nav_service=wire.nav, store=wire.store,
                    pricer=wire.conn.price, control=control)
    row = next(p for p in m.assess()["positions"] if p["symbol"] == "AAPL")

    assert row["value_usd"] < 0, "the fixture is not actually short"
    assert row["shock_20_usd"] < 0, "a 20% shock reported as a GAIN"
    assert row["shock_20_usd"] == pytest.approx(-abs(row["value_usd"]) * 0.20)


def test_assess_PASSES_the_three_integrity_inputs_to_the_evaluator(wire):
    """The wiring half of defect 2. `partial_assessment` used to carry
    `unpriced_symbols` ALONE, so even after moving the rules into the evaluator
    two of the three would have had no input to fire on."""
    control = RiskControl(wire.store)
    m = RiskMonitor(nav_service=wire.nav, store=wire.store,
                    pricer=wire.conn.price, control=control)
    seen = {}
    real = m.evaluate_alarms

    def spy(assessment=None):
        seen.update(assessment or {})
        return real(assessment)

    m.evaluate_alarms = spy
    m.assess()

    assert "unpriced_symbols" in seen
    assert "stale_nav_symbols" in seen
    assert "stale_marks" in seen


def test_assess_reports_venue_drift_as_NOT_ASKED_when_there_is_no_source(wire):
    """ABSENT, not empty, and the SAME absence in both dicts.

    REWRITTEN AT D18 (adversary kill 2). This test used to assert that the
    judged dict OMITS the key while the report carries it as null — and that
    difference WAS the defect: run() re-evaluates on the report, so the two
    dicts disagreeing about this one field is what raised a fabricated CRITICAL
    on every fill. The contract now is one value, None, meaning NOT ASKED in
    both places, with `_drift_was_read` the single reader of it.
    """
    control = RiskControl(wire.store)
    seen = {}
    m = RiskMonitor(nav_service=wire.nav, store=wire.store,
                    pricer=wire.conn.price, control=control)
    real = m.evaluate_alarms

    def spy(assessment=None):
        seen["judged"] = dict(assessment or {})
        return real(assessment)

    m.evaluate_alarms = spy
    out = m.assess()

    assert seen["judged"]["venue_drift"] is None
    assert out["venue_drift"] is None
    assert _drift_was_read(seen["judged"]) is False
    assert _drift_was_read(out) is False
    assert DRIFT_ALARM_KEY not in [a["key"] for a in out["alarms"]]


def test_assess_carries_the_drift_reading_when_there_IS_a_source(wire):
    control = RiskControl(wire.store)
    m = RiskMonitor(nav_service=wire.nav, store=wire.store,
                    pricer=wire.conn.price, control=control,
                    drift_fn=lambda: LIVE_DRIFT_2026_08_23)
    out = m.assess()
    assert out["venue_drift"]["symbols_out_of_sync"] == 10
    assert DRIFT_ALARM_KEY in [a["key"] for a in out["alarms"]]


def test_a_short_position_raises_an_alarm():
    """Intent is not modelled anywhere, so every short is reported and a human
    decides. The fund holds none today: this is a canary that should never
    sing."""
    keys = _keys({"positions": [{"symbol": "SPY", "qty": -3.0,
                                 "weight_pct": 1.0,
                                 "unrealized_pnl_pct": 0.0}]})
    assert "short_position:SPY" in keys


@pytest.mark.parametrize("qty", [3.0, 0.0, None])
def test_only_a_NEGATIVE_quantity_raises_the_short_alarm(qty):
    """qty == 0 is a CLOSED position, not a short. assess() skips flat rows so
    this is unreachable there today, but evaluate_alarms is public and a
    `qty <= 0` test would alarm on every closed symbol in the book — noise that
    trains the operator to ignore the one row that matters."""
    keys = _keys({"positions": [{"symbol": "SPY", "qty": qty,
                                 "weight_pct": 1.0,
                                 "unrealized_pnl_pct": 0.0}]})
    assert not [k for k in keys if k.startswith("short_position")]


# ==========================================================================
# 7. THE TWO D17 KILLS (adversary review, 2026-08-23) — repaired at D18.
#
# KILL 1 — DENIAL OF APPROVAL. `AutopolicyDeclined` landed on the order
# aggregate and both order folds excluded only `ApprovalRefused`, so a declined
# order left `pending()` and BOTH `approve_order` and `decline_order` refused it
# as "not awaiting approval". The event's own payload says "it remains PENDING
# and the CEO can still approve it"; the code made that sentence false.
#
# KILL 2 — A FABRICATED CRITICAL. `assess()` built the judged dict and the
# returned report as two separate literals, adding `venue_drift` conditionally
# to the first and unconditionally to the second. `run()` re-evaluates on the
# report, so every driftless post-fill tick raised "the venue could not be
# read" — and `UNEVALUATED_ON_ABSENT` / `_can_evaluate`, written to prevent
# exactly that, were dead code on every production path.
#
# THE TWO RULES BOTH KILLS TAUGHT, and the tests below are those rules made
# executable:
#   1. A new EventType on an existing aggregate is a LIFECYCLE CHANGE until
#      proven otherwise.
#   2. A test that stubs the producer cannot test the producer's contract.
# ==========================================================================

_DECLINE_NOTE_FRAGMENT = "remains PENDING and the CEO can still approve it"


def _order_event_census() -> dict[str, str]:
    """Every EventType appended to an ORDER aggregate anywhere in ``app/``.

    Reads the AST, not the text: a grep for `aggregate_type="order"` cannot tell
    a live append from one inside a docstring, and the census's whole value is
    that its answer is the set of types the folds will actually meet.
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    found: dict[str, str] = {}
    unparseable: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as e:
            # A file the census cannot read is reported, never treated as
            # containing nothing. Absence is not zero, and a scanner that
            # swallows its own blind spots certifies whatever hides there.
            unparseable.append(f"{path.relative_to(root)} ({type(e).__name__})")
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "Event"):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            agg = kw.get("aggregate_type")
            if not (isinstance(agg, ast.Constant) and agg.value == "order"):
                continue
            ty = kw.get("type")
            # `type=EventType.X` is the only shape used today. A computed type
            # becomes UNREADABLE and therefore unclassified, rather than being
            # skipped: the same absence-is-not-zero rule one level down.
            name = ty.attr if isinstance(ty, ast.Attribute) else "UNREADABLE"
            found.setdefault(name, f"{path.relative_to(root)}:{node.lineno}")
    assert not unparseable, f"the census could not read: {unparseable}"
    return found


def _unclassified(found: dict[str, str]) -> dict[str, str]:
    """Those census entries that are NEITHER a lifecycle step nor an annotation."""
    lifecycle = set(OrdersProjection._STATUS)
    out = {}
    for name, where in found.items():
        member = getattr(EventType, name, None)
        if member is None or (member.value not in lifecycle
                              and member.value not in ORDER_ANNOTATION_EVENTS):
            out[name] = where
    return out


def _propose_real(wire, qty=1.0):
    """One real order through the real pipeline. Returns its id."""
    from app.fund.connectors.base import Order, Side

    r = wire.ledger.request_subscription(lp_id="lp-d18", usd_amount=100_000.0,
                                         actor="mgr")
    wire.ledger.confirm_subscription(r["subscription_id"], actor="mgr")
    res = wire.pipe_open.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=qty), actor="op")
    # `pending_approval` is what the real pipeline returns — verified against
    # it rather than assumed, because a helper that silently accepts a rejected
    # order would make every test below pass on an empty queue.
    assert res["status"] == "pending_approval", res
    return res["order_id"]


def _decline_it_for_real(wire, order_id):
    """Append the decline THE PRODUCER ITSELF writes.

    Adversary rule 2: where the contract is what a real function EMITS, call
    the real function. Hand-rolling the event here would test a fixture's idea
    of `AutopolicyDeclined`, and the whole kill was that the real one lands on
    the ORDER aggregate.
    """
    row = {"order_id": order_id, "symbol": "AAPL", "side": "buy", "qty": 1.0}
    payload = autopolicy.record_decline(
        wire.store, row, ["not_halted"],
        {"approve": False, "checks": [{"check": "not_halted", "ok": False}]})
    assert payload is not None, "the producer wrote nothing to decline against"
    return payload


def test_the_producer_writes_the_decline_onto_the_ORDER_aggregate(wire):
    """The premise of kill 1, measured rather than assumed. If this event ever
    moves to a different aggregate the fold tests below stop meaning anything,
    so the shape is pinned where they can see it."""
    oid = _propose_real(wire)
    _decline_it_for_real(wire, oid)

    rows = [e for e in wire.store.stream(since_seq=0, limit=10_000)
            if e["type"] == EventType.AUTOPOLICY_DECLINED.value]
    assert len(rows) == 1
    assert rows[0]["aggregate_id"] == oid
    assert rows[0]["aggregate_type"] == "order"


def test_a_policy_declined_order_is_STILL_PENDING_end_to_end(wire):
    """KILL 1, THE ACCEPTANCE. Real pipeline, real store, real producer, and
    `pending()` actually called — the projection is what the CEO's approval
    queue renders, and before this fix the order was simply not in it."""
    oid = _propose_real(wire)
    assert oid in [r["order_id"] for r in wire.orders.pending()]

    _decline_it_for_real(wire, oid)

    still = [r["order_id"] for r in OrdersProjection(wire.store).pending()]
    assert oid in still, "the policy's decline erased the order from the queue"


def test_the_CEO_can_still_APPROVE_an_order_the_policy_declined(wire):
    """The payload's own promise, executed. `approve_order` raised
    CommandError("... is 'AutopolicyDeclined', not awaiting approval") — the
    deterministic envelope saying no became the human being unable to say yes,
    which inverts the entire relationship between the two."""
    oid = _propose_real(wire)
    _decline_it_for_real(wire, oid)

    out = wire.pipe_open.approve_order(oid, approver="neelesh")

    assert out is not None
    types = [e["type"] for e in wire.store.by_aggregate(oid)]
    assert EventType.ORDER_APPROVED.value in types


def test_the_CEO_can_still_DECLINE_an_order_the_policy_declined(wire):
    """The other half, and it is not symmetric decoration: with both refused
    the ticket could be neither actioned nor cleared, so it sat on the queue
    until the staleness sweep — which also calls `decline_order`."""
    oid = _propose_real(wire)
    _decline_it_for_real(wire, oid)

    out = wire.pipe_open.decline_order(oid, approver="neelesh")

    assert out["status"] == "declined"
    types = [e["type"] for e in wire.store.by_aggregate(oid)]
    assert EventType.ORDER_DECLINED.value in types


def test_the_declines_own_words_are_TRUE_not_deleted(wire):
    """The event says "it remains PENDING and the CEO can still approve it".
    Read that sentence OUT OF THE PRODUCER'S PAYLOAD and then prove both
    clauses of it, so the fix can never be "delete the sentence"."""
    oid = _propose_real(wire)
    payload = _decline_it_for_real(wire, oid)

    assert _DECLINE_NOTE_FRAGMENT in payload["note"]
    assert oid in [r["order_id"] for r in OrdersProjection(wire.store).pending()]
    wire.pipe_open.approve_order(oid, approver="neelesh")


def test_a_refused_approval_ALSO_still_leaves_the_order_pending(wire):
    """The FIRST incident, guarded in the same breath as the second. Two 403
    probes made a live SOFI ticket vanish on the guard's first day; the
    single-type exclusion that fixed it is now set membership, and this test
    fails if the generalisation dropped the original case."""
    from app.fund.events import Event

    oid = _propose_real(wire)
    wire.store.append(Event(
        aggregate_id=oid, aggregate_type="order",
        type=EventType.APPROVAL_REFUSED,
        payload={"order_id": oid, "reason": "not on the allowlist"},
        actor="probe"))

    assert oid in [r["order_id"] for r in OrdersProjection(wire.store).pending()]
    wire.pipe_open.approve_order(oid, approver="neelesh")


def test_an_annotation_does_not_hide_a_REAL_terminal_state(wire):
    """The over-correction, which would be just as wrong: skipping annotations
    must not make an executed order look pending. The annotation is skipped;
    the lifecycle underneath it is untouched."""
    from app.fund.events import Event

    oid = _propose_real(wire)
    wire.pipe_open.approve_order(oid, approver="neelesh")
    wire.store.append(Event(
        aggregate_id=oid, aggregate_type="order",
        type=EventType.APPROVAL_REFUSED,
        payload={"order_id": oid, "reason": "a late probe"}, actor="probe"))

    row = next(r for r in OrdersProjection(wire.store).history()
               if r["order_id"] == oid)
    assert row["status"] in ("filled", "working", "partial")
    assert oid not in [r["order_id"]
                       for r in OrdersProjection(wire.store).pending()]


def test_BOTH_folds_read_THE_SAME_set_object():
    """Identity, not equality. An assertion that two copies AGREE cannot tell a
    shared constant from a hardcoded duplicate that happens to match today —
    and a duplicate is precisely how the two fold sites came to disagree about
    `AutopolicyDeclined` in the first place."""
    from app.fund import events as events_mod
    from app.fund import pipeline as pipeline_mod
    from app.fund.projections import orders as orders_mod

    assert (orders_mod.ORDER_ANNOTATION_EVENTS
            is events_mod.ORDER_ANNOTATION_EVENTS
            is pipeline_mod.ORDER_ANNOTATION_EVENTS)


def test_the_folds_READ_the_set_rather_than_matching_a_literal(wire, monkeypatch):
    """MOVE IT. Put a type that is NOT an annotation into the set and both folds
    must start skipping it. A test that only checks today's two members cannot
    distinguish "reads the set" from "compares against two hardcoded names",
    which is the same defect one level up."""
    from app.fund import pipeline as pipeline_mod
    from app.fund.projections import orders as orders_mod
    from app.fund.events import Event

    oid = _propose_real(wire)
    wire.pipe_open.decline_order(oid, approver="neelesh")
    assert oid not in [r["order_id"]
                       for r in OrdersProjection(wire.store).pending()]

    moved = frozenset({EventType.ORDER_DECLINED.value})
    monkeypatch.setattr(orders_mod, "ORDER_ANNOTATION_EVENTS", moved)
    monkeypatch.setattr(pipeline_mod, "ORDER_ANNOTATION_EVENTS", moved)

    # OrderDeclined is now an "annotation", so both folds must ignore it and
    # the order reads as pending again.
    assert oid in [r["order_id"] for r in OrdersProjection(wire.store).pending()]
    _, last = wire.pipe_open._load_order(oid)
    assert last == EventType.ORDER_PROPOSED.value

    # ...and AutopolicyDeclined, no longer in the set, folds as a lifecycle
    # step: the defect reappears exactly when the set stops naming it.
    wire.store.append(Event(
        aggregate_id=oid, aggregate_type="order",
        type=EventType.AUTOPOLICY_DECLINED,
        payload={"order_id": oid, "failed_checks": ["not_halted"]},
        actor="auto-policy"))
    assert oid not in [r["order_id"]
                       for r in OrdersProjection(wire.store).pending()]


def test_EVERY_order_event_type_in_the_codebase_is_CLASSIFIED():
    """THE RULE, MECHANISED: a new EventType on an existing aggregate is a
    lifecycle change until proven otherwise.

    Walks `app/` for every `Event(..., aggregate_type="order", ...)` literal and
    demands that its type be either a lifecycle step (`OrdersProjection._STATUS`
    knows how to label it) or a declared annotation. `AutopolicyDeclined` was
    neither, and nothing anywhere said so — the two exclusion comments named the
    previous incident and were not revisited when the next event type arrived.

    This fails on the ELEVENTH type, which is the point. The fix is one line —
    in `ORDER_ANNOTATION_EVENTS` or in `_STATUS` — and the author has to decide
    which, in a diff someone reviews.
    """
    found = _order_event_census()

    assert found, "the census found no order events at all — it is not looking"

    unclassified = _unclassified(found)
    assert not unclassified, (
        "order-aggregate event type(s) classified as NEITHER a lifecycle step "
        "nor an annotation — every fold over an order will treat them as a "
        "lifecycle change, which is how a declined order became un-approvable: "
        f"{unclassified}")


def test_the_census_and_its_classifier_CATCH_an_unclassified_type():
    """The census's own falsifier, and it runs the real classifier rather than
    restating its premise. A scan that passes because its matcher is broken is
    worth less than no scan."""
    real = _order_event_census()
    assert _unclassified(real) == {}

    planted = dict(real, NAV_STRUCK="planted/by/this/test.py:1")
    assert _unclassified(planted) == {"NAV_STRUCK": "planted/by/this/test.py:1"}

    # ...and a type the enum does not have at all — the shape a rename leaves
    # behind — is unclassified rather than quietly skipped.
    assert "NOT_AN_EVENT_TYPE" in _unclassified(
        dict(real, NOT_AN_EVENT_TYPE="planted:2"))


def test_the_annotation_set_names_exactly_the_two_known_findings():
    """A shrink-only pin. If a THIRD type joins the set this fails, and the
    author has to state in the diff why that event is a FINDING about an order
    rather than a step in its life. Membership makes an event invisible to
    every order fold — a permission, not a formality."""
    assert ORDER_ANNOTATION_EVENTS == frozenset({
        EventType.APPROVAL_REFUSED.value,
        EventType.AUTOPOLICY_DECLINED.value,
    })


# --------------------------------------------------------------------------
# KILL 2 — the drift alarm through the REAL assess(), not a stub of it.
#
# Every drift test written at D17 replaced `assess` with a lambda, so the two
# dicts assess() actually builds were never compared and the fabricated CRITICAL
# went straight past a green suite. These drive the real method.
# --------------------------------------------------------------------------
def _real_monitor(wire, **kw):
    """A monitor whose assess() is the REAL one, over the real wiring."""
    return RiskMonitor(nav_service=wire.nav, store=wire.store,
                       pricer=wire.conn.price,
                       control=RiskControl(wire.store), **kw)


def _drift_events(wire):
    return [e for e in wire.store.stream(since_seq=0, limit=10_000)
            if e["type"] in (EventType.RISK_ALARM_RAISED.value,
                             EventType.RISK_ALARM_CLEARED.value)
            and (e["payload"] or {}).get("key") == DRIFT_ALARM_KEY]


def test_a_driftless_monitor_run_raises_NOTHING_drift_related(wire):
    """KILL 2, THE ACCEPTANCE. `pipeline._apply_status` builds exactly this
    monitor — no drift source — on every fill. It raised a CRITICAL saying the
    venue could not be read, on a book nobody had asked about."""
    out = _real_monitor(wire).run(actor="fill_re-eval")

    assert DRIFT_ALARM_KEY not in [a["key"] for a in out["raised"]]
    assert DRIFT_ALARM_KEY not in out["cleared"]
    assert _drift_events(wire) == [], (
        "a monitor with no drift source wrote a drift alarm into the log")


def test_a_monitor_WITH_a_source_raises_the_TRUE_drift_through_run(wire):
    """The other direction, and it is what stops the fix from being "the alarm
    never fires". Today's real book: ten of eleven positions out of sync,
    $126.54 of broker-vs-book disagreement."""
    m = _real_monitor(wire, drift_fn=lambda: LIVE_DRIFT_2026_08_23)
    out = m.run(actor="monitor")

    alarm = next(a for a in out["raised"] if a["key"] == DRIFT_ALARM_KEY)
    assert alarm["severity"] == "critical"
    assert "10 of 11" in alarm["message"]
    assert "126.54" in alarm["message"]
    assert len(_drift_events(wire)) == 1


def test_an_unreadable_venue_still_raises_through_the_real_assess(wire):
    """Absence RAISES, and the path it raises through is the real one. This is
    the message the driftless monitor was FABRICATING — it must be reachable
    only when something actually tried to read the broker and failed."""
    m = _real_monitor(wire, drift_fn=lambda: {"configured": False,
                                              "reason": "alpaca 500"})
    alarm = next(a for a in m.run(actor="monitor")["raised"]
                 if a["key"] == DRIFT_ALARM_KEY)

    assert alarm["severity"] == "critical"
    assert "UNKNOWN" in alarm["message"] and "alpaca 500" in alarm["message"]


def test_repeated_driftless_ticks_write_NOTHING_at_all(wire):
    """The fill loop, run for real. Three fills produced three CRITICAL raises
    and three false clears in the append-only log — one pair per fill, forever,
    on a book that was in sync."""
    for _ in range(3):
        _real_monitor(wire).run(actor="fill_re-eval")

    assert _drift_events(wire) == []


def test_a_driftless_tick_does_not_CLEAR_a_standing_drift_alarm(wire):
    """UNEVALUATED_ON_ABSENT, exercised on the path it was written for.

    D17 shipped this guard and it was DEAD CODE: `_can_evaluate` asked
    `"venue_drift" in assessment` and the report always carried the key, so the
    filter never removed anything. This drives the real assess() and so proves
    the guard is wired, not merely present.
    """
    scheduled = _real_monitor(wire, drift_fn=lambda: LIVE_DRIFT_2026_08_23)
    scheduled.run(actor="monitor")
    assert DRIFT_ALARM_KEY in [a["key"]
                               for a in scheduled._control.active_alarms()]

    before = len(_drift_events(wire))
    _real_monitor(wire).run(actor="fill_re-eval")

    assert len(_drift_events(wire)) == before, (
        "a monitor that never looked at the broker cleared the drift alarm")
    assert DRIFT_ALARM_KEY in [
        a["key"] for a in RiskControl(wire.store).active_alarms()]


def test_the_drift_alarm_DOES_clear_when_a_real_reading_says_in_sync(wire):
    """...and it must still be able to clear, or the fix is a stuck alarm
    wearing a repair's clothes. Only a monitor that LOOKED may clear it."""
    _real_monitor(wire, drift_fn=lambda: LIVE_DRIFT_2026_08_23).run(actor="monitor")

    clean = {"configured": True, "per_symbol": [{"symbol": "AAPL",
                                                 "in_sync": True}]}
    out = _real_monitor(wire, drift_fn=lambda: clean).run(actor="monitor")

    assert DRIFT_ALARM_KEY in out["cleared"]


@pytest.mark.parametrize("drift_fn, why", [
    (None, "no drift source — the post-fill monitor"),
    (lambda: {"configured": True, "per_symbol": []}, "a clean reading"),
    (lambda: {"configured": False, "reason": "timeout"}, "an unreadable venue"),
    (lambda: LIVE_DRIFT_2026_08_23, "today's real drift"),
])
def test_the_REPORTED_alarms_and_the_RE_EVALUATED_alarms_AGREE(wire, drift_fn, why):
    """THE INVARIANT THAT WOULD HAVE CAUGHT KILL 2, and it is general.

    `assess()` judges a dict and reports another; `run()` re-judges the report.
    Any field the two dicts disagree about can flip a rule between "judged" and
    "not judged" without a single test noticing — which is exactly what happened
    to `venue_drift`. This compares the two verdicts directly, so a future field
    with the same shape of divergence fails here rather than in production.
    """
    m = _real_monitor(wire, **({"drift_fn": drift_fn} if drift_fn else {}))
    report = m.assess()
    re_evaluated = [a.to_dict() for a in m.evaluate_alarms(report)]

    assert report["alarms"] == re_evaluated, (
        f"assess() reported different alarms from the ones run() computes "
        f"from its own report ({why})")


def test_the_report_shows_EVERY_field_the_evaluator_judged(wire):
    """The structural half. `history_snaps` is the ONE documented exclusion (up
    to 365 NAV snapshots on a poll the risk bar makes every page render, and it
    steers no rule by its presence). Anything else the evaluator saw and the
    report hides is a divergence waiting to become an alarm."""
    m = _real_monitor(wire, drift_fn=lambda: LIVE_DRIFT_2026_08_23)
    seen = {}
    real = m.evaluate_alarms

    def spy(assessment=None):
        seen["judged"] = dict(assessment or {})
        return real(assessment)

    m.evaluate_alarms = spy
    report = m.assess()

    withheld = set(seen["judged"]) - set(report)
    assert withheld == {"history_snaps"}, (
        f"the evaluator judged field(s) the report does not show: {withheld}")
    for k in set(seen["judged"]) & set(report):
        assert seen["judged"][k] == report[k], f"{k} differs between the two"


def test_the_post_fill_path_is_NOT_a_producer_of_this_alarm(wire):
    """WHO OWNS THE MESSAGE. A standing alarm's payload is written once, by
    whichever monitor raises it, so two producers with different sight of the
    broker would race to describe the same key — and the driftless one would
    win whenever it ran first, stamping "the venue could not be read" onto a
    disagreement that had been measured in dollars.

    After the fix there is exactly ONE producer: only a monitor holding a
    `drift_fn` can put this key into `current_map` at all. The scheduled
    monitor in `app/api/v1/fund.py` is the only one wired with one; the
    post-fill monitor in `pipeline._apply_status` is deliberately blind and now
    contributes neither a raise nor a clear.
    """
    blind = _real_monitor(wire)
    assert DRIFT_ALARM_KEY not in {
        a.key for a in blind.evaluate_alarms(blind.assess())}

    seeing = _real_monitor(wire, drift_fn=lambda: LIVE_DRIFT_2026_08_23)
    assert DRIFT_ALARM_KEY in {
        a.key for a in seeing.evaluate_alarms(seeing.assess())}


def test_the_drift_predicate_is_READ_by_both_the_rule_and_the_guard(wire):
    """MOVE IT. The rule and the clear guard each carried their own copy of
    "was a reading taken", and the copies disagreeing with the dict is the whole
    kill. Force the shared predicate to answer the opposite of the truth and
    BOTH must follow — a hardcoded second copy in either one would not.
    """
    import app.fund.riskmonitor as rm

    m = _real_monitor(wire)                      # genuinely NOT asked
    assert _drift_was_read(m.assess()) is False

    monkey = lambda _a: True  # noqa: E731 — "pretend a reading was taken"
    original = rm._drift_was_read
    try:
        rm._drift_was_read = monkey
        report = m.assess()
        # the RULE follows the predicate...
        assert DRIFT_ALARM_KEY in {a.key for a in m.evaluate_alarms(report)}
        # ...and so does the CLEAR GUARD.
        assert m._can_evaluate(DRIFT_ALARM_KEY, report) is True
    finally:
        rm._drift_was_read = original

    assert m._can_evaluate(DRIFT_ALARM_KEY, m.assess()) is False


def test_DRIFT_ALARM_KEY_is_the_only_member_of_UNEVALUATED_ON_ABSENT():
    """A shrink-only pin with a live consequence: `_can_evaluate` returns False
    for any member it has no clause for, so a key added to this set without a
    clause can never be cleared again. Adding one is a decision, not a tidy-up.
    """
    assert UNEVALUATED_ON_ABSENT == frozenset({DRIFT_ALARM_KEY})
    assert RiskMonitor._can_evaluate("some_future_key", {"venue_drift": {}}) is False
