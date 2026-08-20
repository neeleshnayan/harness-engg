"""Loss-halt auto-resume — four conditions, and each one withheld.

CEO-approved 2026-08-21 ("approved yes"). A LOSS halt reopens without a second
human click when ALL FOUR hold on the monitor tick:

  1. the CEO ACKNOWLEDGED this halt
  2. the TRIGGERING alarm no longer evaluates true on current arithmetic
  3. no OTHER critical alarm is active
  4. a versioned cool-down has passed since the acknowledgement

The failure this file exists to make impossible is a kill switch that reopens
itself on an ABSENCE — an unclassified halt, an unrecorded trigger, an
unparseable timestamp. Every one of those must hold the halt shut, and each has
its own test below. There is deliberately no test asserting that a condition
can be skipped, because there is no such path.

Nothing here asserts a threshold VALUE except the cool-down's own registered
number, which is asserted to be READ from where it lives rather than copied.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.fund.events import Event, EventType
from app.fund.riskmonitor import (
    HALT_INTEGRITY,
    HALT_LOSS,
    HALT_MANUAL,
    LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES,
    RiskControl,
    evaluate_autoresume,
)

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
HALTED_AT = "2026-08-21T10:00:00+00:00"


def ack(minutes_ago: float = 60.0, halted_at: str = HALTED_AT, **over):
    at = (NOW - timedelta(minutes=minutes_ago)).isoformat()
    return {"halted_at": halted_at, "at": at, "actor": "neelesh",
            "note": "seen; the DBC leg gapped and has recovered", **over}


def alarm(key="daily_loss", type_="daily_loss", severity="critical"):
    return {"key": key, "type": type_, "severity": severity}


def ok_case(**over):
    """Every condition satisfied. Each test below breaks exactly one."""
    base = dict(halt_class=HALT_LOSS, halted_at=HALTED_AT,
                halt_alarm={"type": "daily_loss", "key": "daily_loss"},
                acknowledgement=ack(), current_alarms=[], now=NOW)
    base.update(over)
    return base


def cond(v, name):
    return next(c for c in v["conditions"] if c["condition"] == name)


# ------------------------------------------------------------- the happy path


def test_all_four_conditions_reopen_the_halt_and_the_audit_names_every_value():
    v = evaluate_autoresume(**ok_case())
    assert v["resume"] is True
    names = [c["condition"] for c in v["conditions"]]
    assert names == ["class_is_loss", "ceo_acknowledged", "trigger_cleared",
                     "no_other_critical_alarm", "cooldown_elapsed"]
    assert all(c["ok"] for c in v["conditions"])

    # The audit payload must name the EVALUATED VALUES, not just booleans —
    # an auto-resume nobody can reconstruct is one that never should have
    # happened.
    assert cond(v, "class_is_loss")["halt_class"] == HALT_LOSS
    a = cond(v, "ceo_acknowledged")
    assert a["acknowledged_by"] == "neelesh"
    assert "DBC leg gapped" in a["note"]
    assert a["acknowledged_at"]
    assert cond(v, "trigger_cleared")["trigger_alarm"] == "daily_loss"
    assert cond(v, "no_other_critical_alarm")["other_critical"] == []
    c4 = cond(v, "cooldown_elapsed")
    assert c4["minutes_since_acknowledgement"] == 60.0
    assert c4["cooldown_minutes"] == LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES


# --------------------------------------------- each condition, withheld once


def test_condition_1_withheld_no_acknowledgement_keeps_the_halt():
    v = evaluate_autoresume(**ok_case(acknowledgement=None))
    assert v["resume"] is False
    assert cond(v, "ceo_acknowledged")["ok"] is False
    assert "has not stated they have seen it" in cond(v, "ceo_acknowledged")["detail"]
    # And the cool-down cannot pass on an acknowledgement that does not exist.
    assert cond(v, "cooldown_elapsed")["ok"] is False


def test_condition_1_an_acknowledgement_of_a_DIFFERENT_halt_does_not_count():
    """The CEO saw yesterday's darkness, not this one."""
    v = evaluate_autoresume(**ok_case(
        acknowledgement=ack(halted_at="2026-08-20T09:00:00+00:00")))
    assert v["resume"] is False
    assert cond(v, "ceo_acknowledged")["ok"] is False


def test_condition_2_withheld_the_triggering_alarm_is_still_true():
    v = evaluate_autoresume(**ok_case(current_alarms=[alarm()]))
    assert v["resume"] is False
    assert cond(v, "trigger_cleared")["ok"] is False
    assert "STILL true" in cond(v, "trigger_cleared")["detail"]


def test_condition_2_a_halt_that_never_recorded_its_trigger_stays_shut():
    """Fails CLOSED rather than parsing the reason prose.

    Every halt in the log before 2026-08-21 is in this state, including the one
    open on the live spine when this shipped. That is correct: a policy that
    guessed the trigger from a free-text reason would be doing provenance by
    wording, which is exactly the mistake autopolicy v2 fixed for exit markers.
    """
    v = evaluate_autoresume(**ok_case(halt_alarm=None))
    assert v["resume"] is False
    c = cond(v, "trigger_cleared")
    assert c["ok"] is False
    assert c["trigger_alarm"] is None
    assert "cannot be evaluated" in c["detail"]


def test_condition_3_withheld_another_critical_alarm_is_open():
    v = evaluate_autoresume(**ok_case(
        current_alarms=[alarm(key="concentration:DBC", type_="concentration")]))
    assert v["resume"] is False
    c = cond(v, "no_other_critical_alarm")
    assert c["ok"] is False
    assert c["other_critical"] == ["concentration:DBC"]
    # Condition 2 is unaffected — the two conditions say different things, and
    # a test that could not tell them apart would let one cover for the other.
    assert cond(v, "trigger_cleared")["ok"] is True


def test_condition_3_a_non_critical_alarm_does_not_hold_the_halt():
    """A warn-level breach is information, not a reason to stay dark."""
    v = evaluate_autoresume(**ok_case(
        current_alarms=[alarm(key="cash_floor", type_="cash_floor",
                              severity="warn")]))
    assert v["resume"] is True


def test_condition_4_withheld_the_cooldown_has_not_elapsed():
    v = evaluate_autoresume(**ok_case(
        acknowledgement=ack(minutes_ago=LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES - 1)))
    assert v["resume"] is False
    c = cond(v, "cooldown_elapsed")
    assert c["ok"] is False
    assert c["minutes_since_acknowledgement"] == pytest.approx(
        LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES - 1)


def test_condition_4_exactly_at_the_cooldown_passes():
    v = evaluate_autoresume(**ok_case(
        acknowledgement=ack(minutes_ago=LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES)))
    assert cond(v, "cooldown_elapsed")["ok"] is True
    assert v["resume"] is True


def test_condition_4_an_unparseable_acknowledgement_time_is_not_a_passed_cooldown():
    """None minutes, never 0 — a 0 would pass the instant the cool-down were 0."""
    v = evaluate_autoresume(**ok_case(acknowledgement=ack(at="not a timestamp")))
    assert v["resume"] is False
    c = cond(v, "cooldown_elapsed")
    assert c["ok"] is False
    assert c["minutes_since_acknowledgement"] is None


# ------------------------------------------------------------ the class gate


@pytest.mark.parametrize("klass", [HALT_INTEGRITY, HALT_MANUAL, None, "", "loss "])
def test_only_a_LOSS_halt_may_auto_resume_and_a_classless_one_never_does(klass):
    """INTEGRITY and MANUAL never auto-resume; no class is treated as integrity.

    The classless case is the important one: every halt recorded before halt
    classes existed carries None, and reopening a darkness nobody classified is
    exactly the move the class system exists to prevent. `"loss "` is here
    because a whitespace-tolerant comparison would be a silent widening.
    """
    v = evaluate_autoresume(**ok_case(halt_class=klass))
    assert v["resume"] is False
    assert cond(v, "class_is_loss")["ok"] is False
    assert "only a LOSS halt" in cond(v, "class_is_loss")["detail"]


def test_a_loss_halt_with_all_four_held_is_the_only_resuming_combination():
    """Exhaustive over the four booleans: 15 of 16 combinations stay shut."""
    resumed = 0
    for c1 in (True, False):
        for c2 in (True, False):
            for c3 in (True, False):
                for c4 in (True, False):
                    v = evaluate_autoresume(**ok_case(
                        acknowledgement=(
                            ack(minutes_ago=(60.0 if c4 else 1.0)) if c1 else None),
                        halt_alarm=({"type": "daily_loss", "key": "daily_loss"}
                                    if c2 else None),
                        current_alarms=([] if c3 else
                                        [alarm(key="concentration:X",
                                               type_="concentration")]),
                    ))
                    if v["resume"]:
                        resumed += 1
                        assert (c1, c2, c3, c4) == (True, True, True, True)
    assert resumed == 1


# ------------------------------------------------- the fold and the endpoint


class MemStore:
    def __init__(self):
        self.events = []
        self._seq = 0

    def append(self, e):
        self._seq += 1
        self.events.append({
            "type": e.type.value, "payload": e.payload, "actor": e.actor,
            "ts": e.payload.get("at") or f"2026-08-21T10:{self._seq:02d}:00+00:00",
        })
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)


def _halt(store, klass=HALT_LOSS, at="2026-08-21T10:01:00+00:00", **p):
    store.events.append({"type": EventType.TRADING_HALTED.value, "ts": at,
                         "actor": "monitor",
                         "payload": {"reason": "Auto-halt: daily loss",
                                     "halt_class": klass, **p}})


def test_an_acknowledgement_is_bound_to_the_halt_it_names():
    c = RiskControl(MemStore())
    _halt(c._store, at="2026-08-21T10:01:00+00:00")
    c._invalidate()
    got = c.acknowledge_halt(actor="neelesh", note="seen, the gap recovered")
    assert got["status"] == "acknowledged"
    assert got["halted_at"] == "2026-08-21T10:01:00+00:00"
    assert c.halt_acknowledgement()["note"] == "seen, the gap recovered"

    # A NEW halt voids it: the CEO acknowledged the last dark, not this one.
    c._store.events.append({"type": EventType.TRADING_RESUMED.value,
                            "ts": "2026-08-21T11:00:00+00:00",
                            "actor": "neelesh", "payload": {}})
    _halt(c._store, at="2026-08-21T11:30:00+00:00")
    c._invalidate()
    assert c.halt_acknowledgement() is None


def test_acknowledging_requires_a_written_note_and_an_open_halt():
    c = RiskControl(MemStore())
    _halt(c._store)
    c._invalidate()
    with pytest.raises(ValueError, match="written note"):
        c.acknowledge_halt(actor="neelesh", note="   ")

    c2 = RiskControl(MemStore())
    with pytest.raises(ValueError, match="not halted"):
        c2.acknowledge_halt(actor="neelesh", note="nothing to see")


def test_acknowledging_does_NOT_resume_and_does_NOT_move_the_loss_reference():
    """The whole point of a separate action: it changes nothing by itself."""
    c = RiskControl(MemStore())
    _halt(c._store)
    c._invalidate()
    c.acknowledge_halt(actor="neelesh", note="seen")
    assert c.is_halted() is True
    assert c.loss_reference() is None
    assert not any(e["type"] == EventType.TRADING_RESUMED.value
                   for e in c._store.events)


def test_the_ack_token_changes_with_the_halt_it_describes():
    """A confirm typed against a screen showing a different darkness is refused."""
    c = RiskControl(MemStore())
    _halt(c._store, at="2026-08-21T10:01:00+00:00")
    c._invalidate()
    first = c.halt_ack_token()
    assert len(first) == 8
    c._store.events.append({"type": EventType.TRADING_RESUMED.value,
                            "ts": "2026-08-21T11:00:00+00:00",
                            "actor": "neelesh", "payload": {}})
    _halt(c._store, at="2026-08-21T11:30:00+00:00")
    c._invalidate()
    assert c.halt_ack_token() != first


def test_the_halt_records_which_alarm_tripped_it():
    c = RiskControl(MemStore())
    got = c.halt(reason="Auto-halt: daily loss 6.3%", actor="monitor",
                 halt_class=HALT_LOSS, alarm_type="daily_loss",
                 alarm_key="daily_loss")
    assert got["alarm_type"] == "daily_loss"
    assert c.halt_alarm() == {"type": "daily_loss", "key": "daily_loss"}

    # A manual halt names no alarm, and that absence is what keeps it out of
    # the auto-resume path.
    c2 = RiskControl(MemStore())
    c2.halt(reason="pulled the switch", actor="neelesh", halt_class=HALT_MANUAL)
    assert c2.halt_alarm() is None


def test_the_resume_event_carries_the_four_conditions_verbatim():
    c = RiskControl(MemStore())
    _halt(c._store)
    c._invalidate()
    verdict = evaluate_autoresume(**ok_case())
    c.resume(actor="auto-resume-loss-v1", audit=verdict)
    resumed = [e for e in c._store.events
               if e["type"] == EventType.TRADING_RESUMED.value]
    assert len(resumed) == 1
    audit = resumed[0]["payload"]["auto_resume"]
    assert audit["resume"] is True
    assert [x["condition"] for x in audit["conditions"]] == [
        "class_is_loss", "ceo_acknowledged", "trigger_cleared",
        "no_other_critical_alarm", "cooldown_elapsed"]
    assert resumed[0]["actor"] == "auto-resume-loss-v1"
    # A MANUAL resume carries no audit block — the human IS the audit.
    c2 = RiskControl(MemStore())
    _halt(c2._store)
    c2._invalidate()
    c2.resume(actor="neelesh")
    assert [e for e in c2._store.events
            if e["type"] == EventType.TRADING_RESUMED.value][0]["payload"] == {}


# ---------------------------------------------------------------- the tick --
#
# A control is not done until something CALLS it. The kill switches themselves
# spent a period with zero callers (judgement register: `risk_monitor_is_wired`),
# so an auto-resume that only exists as a pure function would be the unwired
# kill switch pattern wearing a new costume.


def _tick_world(monkeypatch, *, ack_minutes_ago=60.0, alarms=(),
                halt_class=HALT_LOSS, with_alarm_type=True):
    from app.fund.riskmonitor import Alarm, RiskMonitor

    store = MemStore()
    control = RiskControl(store)
    control.halt(reason="Auto-halt: daily loss 6.3%", actor="monitor",
                 halt_class=halt_class,
                 **({"alarm_type": "daily_loss", "alarm_key": "daily_loss"}
                    if with_alarm_type else {}))
    halted_at = control._fold(fresh=True)["halted_at"]
    if ack_minutes_ago is not None:
        at = (datetime.now(timezone.utc)
              - timedelta(minutes=ack_minutes_ago)).isoformat()
        store.events.append({
            "type": EventType.HALT_ACKNOWLEDGED.value, "ts": at,
            "actor": "neelesh",
            "payload": {"halted_at": halted_at, "at": at,
                        "note": "seen; the leg gapped and recovered"}})
    control._invalidate()

    m = RiskMonitor(nav_service=None, store=store, control=control)
    monkeypatch.setattr(m, "assess", lambda: {})
    monkeypatch.setattr(m, "evaluate_alarms", lambda a=None: [
        Alarm(key=x["key"], type=x["type"], severity=x["severity"],
              message="m", metric=1.0, threshold=1.0) for x in alarms])
    return m, control, store


def test_the_tick_reopens_an_acknowledged_cleared_loss_halt(monkeypatch):
    m, control, store = _tick_world(monkeypatch)
    assert control.is_halted() is True
    out = m.run(actor="worker")
    assert out["autoresume"]["resume"] is True
    assert out["halted"] is False
    resumed = [e for e in store.events
               if e["type"] == EventType.TRADING_RESUMED.value]
    assert len(resumed) == 1
    assert resumed[0]["actor"] == "auto-resume-loss-v1"
    assert resumed[0]["payload"]["auto_resume"]["resume"] is True


def test_the_tick_leaves_the_halt_shut_and_SAYS_WHY(monkeypatch):
    """The tick reports the policy's verdict on every tick a halt is open, so a
    reader can see why it stayed dark rather than only that it did."""
    m, control, store = _tick_world(monkeypatch, ack_minutes_ago=1.0)
    out = m.run(actor="worker")
    assert out["halted"] is True
    assert out["autoresume"]["resume"] is False
    assert "cooldown_elapsed" in out["autoresume"]["reason"]


def test_the_tick_never_auto_resumes_a_manual_or_integrity_halt(monkeypatch):
    for klass in (HALT_MANUAL, HALT_INTEGRITY):
        m, control, store = _tick_world(monkeypatch, halt_class=klass)
        out = m.run(actor="worker")
        assert out["halted"] is True, f"{klass} halt auto-resumed"
        assert out["autoresume"]["resume"] is False


def test_the_tick_does_not_halt_and_reopen_in_the_same_pass(monkeypatch):
    """A tick that disagreed with itself would flap the switch inside one pass."""
    from app.fund.riskmonitor import Alarm, RiskMonitor

    store = MemStore()
    control = RiskControl(store)
    m = RiskMonitor(nav_service=None, store=store, control=control)
    monkeypatch.setattr(m, "assess", lambda: {})
    monkeypatch.setattr(m, "evaluate_alarms", lambda a=None: [
        Alarm(key="daily_loss", type="daily_loss", severity="critical",
              message="daily loss 6.3% exceeds 4%", metric=6.3, threshold=4.0)])
    out = m.run(actor="worker")
    assert out["halted"] is True
    # The policy is not even consulted on the tick that halted.
    assert out["autoresume"] is None
    assert control.halt_alarm() == {"type": "daily_loss", "key": "daily_loss"}


def test_a_tick_with_no_halt_open_evaluates_nothing(monkeypatch):
    from app.fund.riskmonitor import RiskMonitor

    store = MemStore()
    control = RiskControl(store)
    m = RiskMonitor(nav_service=None, store=store, control=control)
    monkeypatch.setattr(m, "assess", lambda: {})
    monkeypatch.setattr(m, "evaluate_alarms", lambda a=None: [])
    out = m.run(actor="worker")
    assert out["halted"] is False
    assert out["autoresume"] is None


def test_the_cooldown_is_registered_in_the_judgement_register_and_READ_not_copied():
    """A register entry carrying its own copy cannot detect the number moving."""
    from app.fund import judgement, riskmonitor

    entry = next(j for j in judgement.registry()
                 if j.key == "loss_halt_autoresume_cooldown_minutes")
    assert entry.value()["value"] == riskmonitor.LOSS_HALT_AUTORESUME_COOLDOWN_MINUTES
    assert entry.basis == "judged"
    assert "STRIKE_INTERVAL_SECONDS" in entry.review_trigger
    assert entry.falsified_by.strip()
