"""THE STRIKE CLOCK — it counts seconds, and it resumes from the record.

**THE INCIDENT (CAD1, 2026-08-27).** The deterministic worker advanced its
accumulators by the NOMINAL sleep constant — ``since_strike += settle_every`` —
which is the truth only if the loop body costs nothing. It does not: one pass
settles fills, re-screens the universe, snapshots, runs the risk monitor, the
exit check, the autopolicy, two reconciles, prunes results, and every fifth
minute shells out to ``docker ps``. Measured from the fund's own NavStruck
series (n=76, 2026-08-13..26), the strike interval ran between **1.6% and 20.0%
long against a configured 3600s**, and the stretch GREW as the loop gained
work — 4321s on 2026-08-26 against the heartbeat's 5400s nav_strike budget, so
1.25x more loop growth fires that alarm. Note WHAT the heartbeat watches: it
beats on a deliberate no-strike too, so the budget bounds the strike CHECK's
cadence, which is exactly the quantity this defect stretched.

**THE SECOND HALF.** A fresh worker started its strike clock at zero, so every
spine restart and every lease handoff bought a full interval of silence however
long it had already been since the last strike. Five of the ten over-budget
in-session gaps sit in windows where the spine was demonstrably up — it
appended dozens of other events — and where the strike phase MOVED, which is
the signature of an accumulator reset or frozen.

These tests fail if either defect returns. The arithmetic ones drive the real
functions; the source-anchored ones guard the CALL SITE, because the defect
lived there and a correct helper called with the wrong argument is the same
outage.
"""

from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.fund import schedule as S

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
HOUR = 3600.0


def _ts(seconds_ago: float) -> str:
    return (NOW - timedelta(seconds=seconds_ago)).isoformat()


# ===================================================================== advance
def test_a_slow_tick_still_strikes_at_the_configured_interval():
    """THE ACCEPTANCE TEST. Ticks that overrun by 17.5% must not stretch the
    strike interval by 17.5%.

    Measured tick period on this fund is ~23.5s against a nominal 20s. Driving
    the accumulator with the real elapsed time must put every strike inside
    [interval, interval + one tick] — the reset-to-zero policy gives away at
    most one tick of overshoot and never more.
    """
    tick = 23.5
    served, clock, strikes = 0.0, 0.0, []
    for _ in range(2000):
        clock += tick
        served, due = S.advance(served, tick, HOUR)
        if due:
            strikes.append(clock)
    assert len(strikes) >= 10, "the simulation must produce enough strikes to measure"
    periods = [b - a for a, b in zip(strikes, strikes[1:])]
    assert min(periods) >= HOUR, "a strike must never land EARLY"
    assert max(periods) <= HOUR + tick, (
        f"strike period {max(periods)}s exceeds the interval plus one tick "
        f"({HOUR + tick}s) — the accumulator is not counting measured time")


def test_a_SPIKY_tick_still_strikes_at_the_configured_interval():
    """THE WORST CASE, not the average one. The previous test drives a constant
    23.5s tick, which is a MODEL of a loop that never spikes — and this loop
    spikes by design: ``run_universe_refresh`` spends ~50 seconds when the
    screen goes stale, and the LEAN reconcile shells out to ``docker ps`` every
    fifth minute. So the bound must be asserted against the SPIKIEST tick in the
    run, not the typical one, because the overshoot is bounded by the tick that
    happens to cross the boundary and that is the one a mean would hide.
    """
    ticks = []
    for i in range(3000):
        t = 21.0
        if i % 15 == 0:
            t = 71.0        # a universe refresh landed on this pass
        elif i % 4 == 0:
            t = 26.0        # a docker ps
        ticks.append(t)
    worst = max(ticks)

    served, clock, strikes = 0.0, 0.0, []
    for t in ticks:
        clock += t
        served, due = S.advance(served, t, HOUR)
        if due:
            strikes.append(clock)
    periods = [b - a for a, b in zip(strikes, strikes[1:])]
    assert len(periods) >= 10
    assert min(periods) >= HOUR, "a strike must never land EARLY"
    assert max(periods) <= HOUR + worst, (
        f"strike period {max(periods):.1f}s exceeds the interval plus the "
        f"worst tick in the run ({HOUR + worst}s)")
    # And the whole point: a loop whose worst pass is 71 seconds still holds a
    # cadence far inside the 5400s budget the heartbeat measures it against.
    assert max(periods) < 5400.0


def test_the_nominal_constant_is_what_stretched_the_interval():
    """THE BUG, PINNED. Feeding the accumulator the NOMINAL sleep while the wall
    clock advances by the real tick reproduces the measured stretch. If this
    ever stops failing to hold the budget, the incident's arithmetic was wrong.
    """
    nominal, real = 20.0, 23.5
    served, clock, strikes = 0.0, 0.0, []
    for _ in range(2000):
        clock += real
        served, due = S.advance(served, nominal, HOUR)   # the old call site
        if due:
            strikes.append(clock)
    periods = [b - a for a, b in zip(strikes, strikes[1:])]
    stretch = min(periods) / HOUR
    assert stretch > 1.15, (
        f"the nominal-constant call site should stretch the interval by ~17.5%, "
        f"measured {stretch:.3f}x")
    # And that stretch is what walks a 3600s interval into a 5400s budget.
    assert min(periods) == pytest.approx(HOUR * real / nominal, rel=0.01)


def test_the_boundary_is_inclusive_and_one_step_below_is_not_due():
    """Strict vs non-strict, probed AT the boundary."""
    assert S.advance(HOUR - 1.0, 1.0, HOUR) == (0.0, True)
    served, due = S.advance(HOUR - 1.0, 0.999999, HOUR)
    assert due is False and served == pytest.approx(HOUR - 0.000001)


def test_a_non_positive_interval_is_never_due():
    """Zero DISABLES a tick — it is a supported setting for the LEAN reconcile,
    and it must not mean 'due on every pass'."""
    assert S.advance(10.0, 5.0, 0) == (10.0, False)
    assert S.advance(10.0, 5.0, -1) == (10.0, False)
    assert S.advance(10_000.0, 10_000.0, 0) == (10_000.0, False)


def test_a_backwards_clock_does_not_wind_the_accumulator_back():
    """A monotonic clock cannot go backwards, and if one ever does the periodic
    control must not become LESS due than it already was."""
    served, due = S.advance(100.0, -50.0, HOUR)
    assert served == 100.0 and due is False


def test_one_long_stall_fires_once_and_does_not_burst():
    """A suspended host must not produce a run of official NAVs for one moment."""
    served, due = S.advance(0.0, 10 * HOUR, HOUR)
    assert due is True and served == 0.0
    served, due = S.advance(served, 1.0, HOUR)
    assert due is False, "the overshoot must not be carried into a second strike"


def test_advance_reads_its_interval_argument():
    """MOVED, not compared: the same accumulator and elapsed must give a
    different answer for a different interval, which a hardcoded 3600 could
    not do."""
    assert S.advance(0.0, 1801.0, 1800)[1] is True
    assert S.advance(0.0, 1801.0, 7200)[1] is False


# ======================================================== resume_strike_clock
def test_an_unreadable_record_restarts_the_clock_and_says_it_is_a_fault():
    r = S.resume_strike_clock(S.UNREADABLE, HOUR, NOW)
    assert r.seconds_served == 0.0
    assert r.basis == S.UNREADABLE
    assert "could NOT BE READ" in r.note
    assert "fault" in r.note


def test_a_fund_that_never_struck_is_not_the_same_as_an_unreadable_one():
    """ABSENCE DISCIPLINE, at the input. ``None`` means the log is readable and
    holds no strike; ``UNREADABLE`` means the read failed. Same number, and they
    must never share a sentence — the log is where a cause is diagnosed."""
    never = S.resume_strike_clock(None, HOUR, NOW)
    unread = S.resume_strike_clock(S.UNREADABLE, HOUR, NOW)
    assert never.seconds_served == unread.seconds_served == 0.0
    assert never.basis == S.NEVER_STRUCK and unread.basis == S.UNREADABLE
    assert never.note != unread.note
    assert "no NAV has ever been struck" in never.note
    assert "ever been struck" not in unread.note


def test_a_payload_that_is_not_a_payload_names_its_type():
    r = S.resume_strike_clock([], HOUR, NOW)
    assert r.basis == S.UNREADABLE and r.seconds_served == 0.0
    assert "list" in r.note


def test_a_strike_with_no_timestamp_is_unreadable_not_never_struck():
    r = S.resume_strike_clock({"total_nav_usd": 1885.0}, HOUR, NOW)
    assert r.basis == S.UNREADABLE
    assert "carries no timestamp" in r.note
    assert "ever been struck" not in r.note


def test_an_unparseable_timestamp_quotes_what_it_read():
    r = S.resume_strike_clock({"ts": "yesterday"}, HOUR, NOW)
    assert r.basis == S.UNREADABLE
    assert "yesterday" in r.note and "not a timestamp" in r.note


def test_a_strike_dated_in_the_future_gets_its_own_basis():
    """Two clocks disagreeing is not the same as a young fund, and serving a
    negative age would make the next strike LATE by that amount."""
    r = S.resume_strike_clock({"ts": _ts(-90)}, HOUR, NOW)
    assert r.basis == S.FUTURE and r.seconds_served == 0.0
    assert "FUTURE" in r.note


def test_an_overdue_record_makes_the_next_tick_strike():
    r = S.resume_strike_clock({"ts": _ts(4000)}, HOUR, NOW)
    assert r.basis == S.OVERDUE and r.seconds_served == pytest.approx(4000, abs=1)
    assert S.advance(r.seconds_served, 1.0, HOUR)[1] is True


def test_exactly_one_interval_old_counts_as_overdue():
    r = S.resume_strike_clock({"ts": _ts(HOUR)}, HOUR, NOW)
    assert r.basis == S.OVERDUE


def test_a_recent_strike_resumes_part_way_through_the_interval():
    r = S.resume_strike_clock({"ts": _ts(100)}, HOUR, NOW)
    assert r.basis == S.RESUMED and r.seconds_served == pytest.approx(100, abs=1)
    assert S.advance(r.seconds_served, 1.0, HOUR)[1] is False


def test_a_naive_timestamp_is_read_as_utc_rather_than_refused():
    r = S.resume_strike_clock({"ts": "2026-08-27T11:00:00"}, HOUR, NOW)
    assert r.basis == S.OVERDUE and r.seconds_served == pytest.approx(HOUR, abs=1)


def test_every_basis_carries_its_own_sentence():
    """SHARED-WORD AUDIT. Nine inputs, nine distinct notes: an assertion that a
    different branch could satisfy is not an assertion."""
    inputs = [
        S.UNREADABLE, None, [], {}, {"ts": "nope"}, {"ts": _ts(-5)},
        {"ts": _ts(9000)}, {"ts": _ts(10)},
    ]
    notes = [S.resume_strike_clock(x, HOUR, NOW).note for x in inputs]
    assert len(set(notes)) == len(notes), (
        f"two causes share a sentence: {sorted(notes)}")


def test_a_restart_mid_interval_does_not_cost_a_whole_interval():
    """THE MONEY TEST for the second half. A worker that comes up 40 minutes
    after the last strike must strike 20 minutes later, not 60.

    Before this, ``since_strike`` started at zero on every acquisition and the
    fund lost a full interval per restart — measured on five of the ten
    over-budget in-session gaps in its own NavStruck series.
    """
    r = S.resume_strike_clock({"ts": _ts(2400)}, HOUR, NOW)
    served, clock = r.seconds_served, 0.0
    tick = 23.5
    while True:
        clock += tick
        served, due = S.advance(served, tick, HOUR)
        if due:
            break
    assert 1200 - tick <= clock <= 1200 + tick, (
        f"a worker resuming 2400s into a 3600s interval struck {clock:.0f}s "
        f"after start-up; it should have struck at ~1200s")


def test_resuming_is_self_limiting_after_a_fresh_strike():
    """A restart loop must not manufacture strikes. Immediately after a strike
    the newest event is seconds old, so the next process waits."""
    r = S.resume_strike_clock({"ts": _ts(2)}, HOUR, NOW)
    assert r.basis == S.RESUMED
    assert S.advance(r.seconds_served, 30.0, HOUR)[1] is False


def test_resume_reads_its_interval_argument():
    """MOVED, not compared."""
    payload = {"ts": _ts(2000)}
    assert S.resume_strike_clock(payload, HOUR, NOW).basis == S.RESUMED
    assert S.resume_strike_clock(payload, 1800, NOW).basis == S.OVERDUE


def test_resume_reads_its_now_argument():
    payload = {"ts": _ts(100)}
    later = S.resume_strike_clock(payload, HOUR, NOW + timedelta(seconds=4000))
    assert later.basis == S.OVERDUE


# ================================================================= the call site
#: ``app/main.py`` read as TEXT rather than imported. Importing it resolves the
#: fund mode, initialises Firebase and builds the router — a unit test that did
#: that would be an integration test wearing a unit test's name.
MAIN_SRC = (pathlib.Path(__file__).resolve().parents[1]
            / "app" / "main.py").read_text(encoding="utf-8")


def _scheduler_body() -> str:
    """The text of ``_scheduler`` only.

    ANCHORED ON THE ENCLOSING FUNCTION, never on a character count: a bound
    measured against today's prose goes red the afternoon a comment grows.
    ``lifespan`` is the next top-level definition and its decorator is the fence.
    """
    start = MAIN_SRC.index("async def _scheduler()")
    end = MAIN_SRC.index("@asynccontextmanager", start)
    body = MAIN_SRC[start:end]
    assert len(body) > 1000, "the scheduler body did not survive the anchor"
    assert "def lifespan" not in body, "the anchor swallowed the next function"
    return body


def test_the_scheduler_no_longer_advances_by_the_nominal_sleep():
    """THE DEFECT, GUARDED AT ITS CALL SITE. ``advance`` can be perfect and the
    worker still broken if it is handed the sleep constant."""
    body = _scheduler_body()
    assert "+= settle_every" not in body, (
        "an accumulator is advancing by the NOMINAL sleep again — that is the "
        "CAD1 defect, measured at 1.6%-20.0% of the strike interval")


def test_the_scheduler_measures_elapsed_time_with_a_monotonic_clock():
    body = _scheduler_body()
    # A MONOTONIC clock, not a wall clock: an NTP step or a DST change must not
    # be able to move the strike cadence, and a wall-clock delta is exactly how
    # that would happen.
    assert "now_mono = time.monotonic()" in body
    assert "elapsed = now_mono - last_tick" in body
    assert "last_tick = now_mono" in body


def test_both_accumulators_advance_by_measured_elapsed_time():
    """ONE RULE, N DERIVATIONS is this codebase's most-paid-for defect family:
    the strike accumulator and the reconcile accumulator had the same bug and
    a fix applied to one of a family is half a fix."""
    body = _scheduler_body()
    for name in ("since_strike", "since_reconcile"):
        assert f"{name}, " in body, f"{name} is no longer advanced by advance()"
        assert f"schedule.advance(\n            {name}, elapsed" in body \
            or f"schedule.advance({name}, elapsed" in body, (
                f"{name} is not advanced by measured elapsed time")


def test_the_strike_clock_is_resumed_on_every_lease_acquisition():
    """Start-up and handoff are the same event from the clock's point of view,
    and both were losing an interval."""
    body = _scheduler_body()
    assert "resume_strike_clock(" in body
    assert "_newest_strike()" in body
    before = body.split("resume_strike_clock(", 1)[0]
    between = before[before.rindex("if state.held and strike_every > 0:"):]
    assert "if not state.held:" not in between, (
        "the resume moved out of the lease-acquisition branch")
    # SIXTEEN SPACES: inside ``if state.held != was_held:`` and then inside
    # ``if state.held:``. Resuming at loop top instead would fold the event log
    # every twenty seconds, on the coroutine whose event loop also serves the
    # route the host watchdog polls.
    assert "\n                resumed = schedule.resume_strike_clock(" in body


def test_a_disabled_strike_interval_says_so_out_loud():
    """Zero means no NAV is ever struck. That is legitimate to want and
    illegitimate to discover from a flat chart three days later."""
    body = _scheduler_body()
    assert "strike_every <= 0" in body
    assert "DISABLED" in body


def test_the_reconcile_tick_can_still_be_disabled_by_zero():
    """LEAN_RECONCILE_INTERVAL=0 is a supported setting and the refactor must
    not have turned it into 'due on every pass'."""
    body = _scheduler_body()
    assert "if reconcile_every and reconcile_due:" in body
    assert S.advance(1e9, 1e9, 0) == (1e9, False)


# ================================================== the reader, in a subprocess
#: ``app.main`` is imported in a CLEAN INTERPRETER, never in-process.
#: ``tests/test_executionquality_store.py`` enforces that rule with an AST scan
#: and it is not decoration: constructing the app runs its lifespan hook, which
#: seeds demo events into the shared Firestore fake and hands every later module
#: a pre-seeded log — measured at 39 downstream failures the one time it
#: happened. So the reader is exercised the way the archive-memo route is.
_READER_PROBE = r'''
import json, os, sys
sys.path.insert(0, "tests")
import conftest  # installs the in-memory Firestore fake before any app import
import app.main as M
from app.fund import schedule


class _Raises:
    def latest(self):
        raise RuntimeError("postgres is on fire")


class _Returns:
    def __init__(self, value):
        self.value = value

    def latest(self):
        return self.value


out = {}
M.fund_router._nav = _Raises()
out["raises"] = M._newest_strike()
M.fund_router._nav = _Returns(None)
out["none"] = M._newest_strike()
M.fund_router._nav = _Returns({"ts": "2026-08-27T11:00:00+00:00", "total_nav_usd": 1885.0})
out["payload"] = M._newest_strike()
out["UNREADABLE"] = schedule.UNREADABLE
sys.stdout.write("PROBE" + json.dumps(out) + "PROBE")
'''


@pytest.fixture(scope="module")
def reader_probe():
    """The probe's environment is SET, never ``setdefault``-ed.

    The first version used ``os.environ.setdefault`` inside the probe, which is
    a no-op when the variable is already present — so the subprocess INHERITED
    the developer's shell instead of being isolated from it. Reproduced: with a
    leftover ``FUND_MODE=alpaca-paper`` the probe died on absent Alpaca
    credentials, and with ``FUND_STORE=postgres`` it spent thirty seconds
    retrying a database that does not exist before failing. A test that reports
    the developer's shell is not a test of anything, and the failure mode is
    worst for whoever has the most interesting environment.
    """
    import json as _json
    import os as _os
    import subprocess
    import sys as _sys
    repo = pathlib.Path(__file__).resolve().parents[1]
    env = dict(_os.environ)
    env.update({
        "FUND_STORE": "firestore",
        "FUND_MODE": "test",
        "FUND_MODE_FILE": str(pathlib.Path("tests") / ".fund_mode.absent"),
    })
    # Poisoning variables the parent may carry are REMOVED, not overridden:
    # there is no value for these that means "ignore me".
    for poison in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FUND_ENV",
                   "STRIKE_INTERVAL_SECONDS", "SETTLE_INTERVAL_SECONDS"):
        env.pop(poison, None)
    r = subprocess.run([_sys.executable, "-c", _READER_PROBE],
                       capture_output=True, text=True, cwd=str(repo),
                       env=env, timeout=300)
    assert r.returncode == 0, (
        f"the reader probe could not run:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    assert "PROBE" in r.stdout, f"probe produced no result:\n{r.stdout[-2000:]}"
    return _json.loads(r.stdout.split("PROBE")[1])


def test_a_read_that_raises_returns_UNREADABLE_and_never_propagates(reader_probe):
    """The reader runs inside a coroutine started with ``asyncio.create_task``.
    An exception there surfaces only when awaited — at shutdown — so the whole
    deterministic worker goes quiet with nothing in the log."""
    assert reader_probe["raises"] == reader_probe["UNREADABLE"]


def test_a_readable_log_with_no_strike_is_NOT_reported_as_unreadable(reader_probe):
    """ABSENCE DISCIPLINE AT THE SOURCE. A young fund and a broken store must
    not arrive at the resume logic as the same input, or the note an operator
    reads is a coin toss."""
    assert reader_probe["none"] is None
    assert reader_probe["none"] != reader_probe["UNREADABLE"]


def test_the_reader_hands_the_payload_over_uninterpreted(reader_probe):
    """One place interprets the payload — ``resume_strike_clock`` — so there is
    no second place for the interpretation to drift."""
    assert reader_probe["payload"] == {
        "ts": "2026-08-27T11:00:00+00:00", "total_nav_usd": 1885.0}


# ============================================ gaps the mutation pass exposed
def test_a_strike_dated_exactly_now_resumes_and_is_not_called_a_future_one():
    """MUTANT M16. ``age <= 0`` instead of ``age < 0`` changes NO verdict — both
    arms serve 0.0 seconds — and changes only the SENTENCE, from "resuming the
    clock 0s in" to "this clock disagrees with the one that wrote the record".

    That is not an equivalent mutant. The log is where a cause is diagnosed, and
    a fund that struck a NAV this instant must not be reported as evidence its
    two clocks disagree. Every other assertion in this file was on the number.
    """
    r = S.resume_strike_clock({"ts": _ts(0)}, HOUR, NOW)
    assert r.basis == S.RESUMED, "a strike dated exactly now is not in the future"
    assert "FUTURE" not in r.note
    assert "disagrees" not in r.note


def test_the_resumed_value_is_actually_assigned_to_the_accumulator():
    """MUTANT M28. Computing the resume, logging its note, and then setting the
    accumulator to zero anyway leaves a log line that says the clock resumed and
    a worker that did not. The structural guard asserted the CALL and not the
    ASSIGNMENT, which is the difference between a control and a control's
    advertisement."""
    body = _scheduler_body()
    assert "since_strike = resumed.seconds_served" in body
    assert "since_strike = 0.0\n                _log" not in body


def test_the_strike_block_is_gated_on_the_accumulator_being_due():
    """MUTANT M31. With the gate removed the worker writes a NAV_STRUCK — the
    fund's official record of what a unit was worth — on EVERY tick, which at
    the configured 20-second settle interval is 180 official NAVs an hour."""
    body = _scheduler_body()
    assert "\n        if strike_due:\n" in body, (
        "the strike block is no longer gated on the accumulator being due")


# ================================================ gaps the Gauntlet exposed
def test_a_NaN_can_never_kill_the_accumulator_permanently():
    """GAUNTLET, boundary table. Every comparison against NaN is False, so
    ``elapsed < 0`` would let a NaN through, ``seconds_served`` would become NaN,
    and ``seconds_served >= interval`` would then be False on EVERY future tick.

    That is a periodic control that has died silently and permanently — no
    strike, no reconcile, no log line, forever. ``time.monotonic()`` deltas
    cannot be NaN, so nothing in production reaches this today; the reason it is
    guarded anyway is that the failure is unbounded, undetectable and one new
    caller away.
    """
    nan = float("nan")
    served, due = S.advance(0.0, nan, HOUR)
    assert served == 0.0 and due is False, "a NaN elapsed must not enter the sum"
    # ...and the accumulator still works afterwards, which is the real assertion.
    served, due = S.advance(served, HOUR, HOUR)
    assert due is True

    served, due = S.advance(10.0, 5.0, nan)
    assert due is False, "a NaN interval is not a period"
    assert served == 10.0, "a NaN interval must not consume the accumulator"


def test_an_infinite_elapsed_fires_once_and_leaves_the_clock_usable():
    served, due = S.advance(0.0, float("inf"), HOUR)
    assert due is True and served == 0.0
    served, due = S.advance(served, 1.0, HOUR)
    assert due is False


def test_the_resume_is_skipped_when_striking_is_disabled():
    """GAUNTLET, cost on a hot path. With ``strike_every <= 0`` nothing will
    ever be struck, so folding the whole event log on every lease acquisition to
    find out how overdue the strike is would be work for a feature that is off.
    """
    body = _scheduler_body()
    assert "if state.held and strike_every > 0:" in body


def test_the_probe_sets_its_environment_rather_than_defaulting_it():
    """GAUNTLET, env sensitivity. ``os.environ.setdefault`` in a subprocess that
    INHERITS the parent env is not isolation — it is a no-op whenever the
    variable is already there. Reproduced by the Gauntlet: a leftover
    ``FUND_MODE=alpaca-paper`` killed three tests on absent credentials, and
    ``FUND_STORE=postgres`` spent thirty seconds retrying a missing database.
    """
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    probe = src[src.index("_READER_PROBE = r'''"):src.index("@pytest.fixture")]
    assert "setdefault" not in probe, (
        "the probe is configuring itself from the parent's environment again")
    assert "env=env" in src, "the subprocess is not given an explicit environment"
