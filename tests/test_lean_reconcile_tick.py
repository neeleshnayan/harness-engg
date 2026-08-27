"""THE PERIODIC RECONCILE — the window BETWEEN start-ups, and the race it opens.

**WHAT THIS CLOSES.** Session reconciliation ran once, at spine start-up, so
``engineledger.ORPHAN_NOTE`` published the window between start-ups as an
unclosed limit on what the engine fence proves — and that window is as long as
the spine's uptime, which is the case that is actually normal. The
deterministic worker now repeats it on a timer.

**WHAT IT OPENS, AND THIS IS THE HALF THAT NEEDED DESIGNING.** ``start_live``
writes its registry row (state ``starting``) and only then launches
``docker run`` from a daemon thread — deliberately, because a container nothing
remembers is an orphan. So there is a window of seconds in which a live row has
no container, which is exactly the shape ``reconcile`` calls ``vanished``. A
start-up pass cannot land in it; a five-minute tick can, and would retire a
session that is starting correctly, release its scope, and leave the container
that then appears to be stopped by the following pass as an orphan.

``leansessions.YOUNG`` and ``grace_seconds`` are the answer, and the tests below
are weighted toward the two things that decide whether it is a good one: **the
grace must not weaken the start-up pass** (its default is 0 and every existing
behaviour is unchanged), and **an unreadable age must count as young**, because
refusing to judge costs one pass and retiring a live session costs the session.
"""
import pathlib

import pytest

from app.fund import leansessions as LS


#: ``app/main.py`` read as TEXT rather than imported. Importing it
#: resolves the fund mode, initialises Firebase and builds the router —
#: a unit test that did that would be an integration test wearing a
#: unit test's name, and would fail for reasons that have nothing to do
#: with what is being asserted.
MAIN_SRC = (pathlib.Path(__file__).resolve().parents[1]
            / "app" / "main.py").read_text(encoding="utf-8")

NOW = "2026-08-27T12:00:00+00:00"


def _born(seconds_ago):
    """``NOW`` minus N seconds, as an ISO instant.

    Computed with ``datetime`` rather than by formatting arithmetic into a
    string: the hand-rolled version produced ``11:56:60``, which
    ``fromisoformat`` rejects — so the age read as UNREADABLE and the boundary
    test passed on the absent-age branch instead of the boundary it names."""
    import datetime as _dt
    t = _dt.datetime.fromisoformat(NOW) - _dt.timedelta(seconds=seconds_ago)
    return t.isoformat()


def _row(sid, state="running", started="2026-08-27T11:00:00+00:00"):
    return {"session_id": sid, "state": state,
            "container": f"{LS.CONTAINER_PREFIX}{sid}", "started_at": started}


def _con(sid, mode=None):
    return {"name": f"{LS.CONTAINER_PREFIX}{sid}", "mode": mode}


class TestTheStartUpPassIsUnchanged:
    """THE DEFAULT IS THE OLD BEHAVIOUR TO THE BYTE. A parameter that changed
    what an existing caller does would be a quiet loosening of the one pass
    that has been correct all along."""

    def test_a_live_row_with_no_container_still_vanishes_by_default(self):
        plan = LS.reconcile([_row("gone")], [], our_mode="dev")
        assert [a["action"] for a in plan["actions"]] == [LS.VANISHED]
        assert plan["counts"][LS.YOUNG] == 0
        assert plan["grace_seconds"] == 0.0

    def test_a_row_born_ONE_SECOND_AGO_still_vanishes_by_default(self):
        """The grace is opt-in, not a floor. Zero means zero."""
        plan = LS.reconcile([_row("gone", started="2026-08-27T11:59:59+00:00")],
                            [], our_mode="dev", now=NOW)
        assert [a["action"] for a in plan["actions"]] == [LS.VANISHED]

    def test_the_runner_start_up_call_passes_no_grace(self, tmp_path):
        """Pinned on the RUNNER rather than only in ``app.main``, because the
        default is what makes every other caller safe."""
        import inspect
        from app.fund.leanrunner import LeanRunner
        sig = inspect.signature(LeanRunner.reconcile_containers)
        assert sig.parameters["grace_seconds"].default == 0.0
        assert sig.parameters["trigger"].default == "startup"


class TestTheRaceTheTickOpens:
    def test_A_ROW_INSIDE_THE_GRACE_IS_NOT_RETIRED(self):
        """THE INCIDENT THIS PREVENTS. A session 30 seconds into its start has
        a live row and no container yet."""
        plan = LS.reconcile(
            [_row("starting", state="starting",
                  started="2026-08-27T11:59:30+00:00")],
            [], our_mode="dev", now=NOW, grace_seconds=180.0)
        act, = plan["actions"]
        assert act["action"] == LS.YOUNG
        assert act["age_seconds"] == 30.0
        assert plan["counts"][LS.VANISHED] == 0
        assert plan["counts"][LS.YOUNG] == 1

    def test_a_row_OLDER_than_the_grace_is_still_retired(self):
        """THE POSITIVE CONTROL, and the one that matters: a grace that spared
        everything would turn the tick into a control that never acts."""
        plan = LS.reconcile(
            [_row("gone", started="2026-08-27T11:00:00+00:00")],
            [], our_mode="dev", now=NOW, grace_seconds=180.0)
        act, = plan["actions"]
        assert act["action"] == LS.VANISHED
        assert plan["counts"][LS.YOUNG] == 0

    def test_the_grace_boundary_is_probed_on_BOTH_sides(self):
        """Strict-vs-non-strict at the boundary. ``age < grace`` spares;
        ``age == grace`` does not.

        The instants are computed with ``datetime`` rather than by formatting
        arithmetic into a string — the first version of this test produced
        ``11:56:60``, which ``fromisoformat`` rejects, so the row's age read as
        UNREADABLE and the test passed the boundary case for the wrong reason.
        A boundary probe that never reaches the boundary is worse than none."""
        assert _born(180) == "2026-08-27T11:57:00+00:00", _born(180)
        for delta, expected in ((181, LS.VANISHED), (180, LS.VANISHED),
                                (179, LS.YOUNG)):
            born = _born(delta)
            plan = LS.reconcile([_row("s", started=born)], [], our_mode="dev",
                                now=NOW, grace_seconds=180.0)
            act, = plan["actions"]
            # THE AGE IS ASSERTED TOO. Without it an unparseable instant lands
            # on YOUNG through the absent-age branch and looks like a pass.
            assert act.get("age_seconds") == float(delta), (delta, born)
            assert act["action"] == expected, (delta, born)

    @pytest.mark.parametrize("started,now", [
        (None, NOW), ("", NOW), ("yesterday", NOW), ("2026-13-45", NOW),
        ("2026-08-27T11:00:00+00:00", None),
        ("2026-08-27T11:00:00", NOW),          # naive beside aware -> TypeError
    ])
    def test_an_UNREADABLE_age_counts_as_YOUNG(self, started, now):
        """ABSENCE TAKES THE RECOVERABLE BRANCH. Refusing to judge costs one
        pass; retiring a live session costs the session, its scope, and leaves
        a container the next pass will stop as an orphan."""
        plan = LS.reconcile([_row("s", started=started)], [], our_mode="dev",
                            now=now, grace_seconds=180.0)
        act, = plan["actions"]
        assert act["action"] == LS.YOUNG
        assert act["age_seconds"] is None

    def test_the_grace_does_not_touch_the_other_four_actions(self):
        """It guards ONE branch. A row with a container reattaches whatever its
        age, an unaccounted container is still stopped, and a foreign one is
        still left alone — the grace must not have become a general amnesty."""
        plan = LS.reconcile(
            [_row("keep", started="2026-08-27T11:59:59+00:00"),
             _row("zombie", state="ended")],
            [_con("keep"), _con("ghost"), _con("zombie"),
             _con("alien", mode="prod")],
            our_mode="dev", now=NOW, grace_seconds=180.0)
        assert plan["counts"] == {LS.REATTACH: 1, LS.ADOPT: 1, LS.STOP: 1,
                                  LS.LEAVE: 1, LS.VANISHED: 0, LS.YOUNG: 0}

    def test_the_note_names_the_spared_rows(self):
        plan = LS.reconcile([_row("s", started="2026-08-27T11:59:30+00:00")],
                            [], our_mode="dev", now=NOW, grace_seconds=180.0)
        assert "too young to judge" in plan["note"]
        assert plan["note"].endswith(".")

    def test_the_grace_and_the_instant_are_PUBLISHED(self):
        """A reader who sees a live row in neither ``reattach`` nor ``vanished``
        has to be able to find out why. ``0`` says plainly that no row was
        spared, which is what makes the start-up payload unambiguous too."""
        plan = LS.reconcile([_row("s")], [], our_mode="dev", now=NOW,
                            grace_seconds=180.0)
        assert plan["grace_seconds"] == 180.0
        assert plan["measured_at"] == NOW
        bare = LS.reconcile([_row("s")], [], our_mode="dev")
        assert bare["grace_seconds"] == 0.0
        assert bare["measured_at"] is None

    def test_nothing_is_decided_when_either_side_is_unreadable(self):
        """The grace must not have created a path that acts on half a
        comparison."""
        for rows, cons in (([_row("s")], None), (None, [_con("s")]),
                           (None, None)):
            plan = LS.reconcile(rows, cons, our_mode="dev", now=NOW,
                                grace_seconds=180.0)
            assert plan["actions"] == []
            assert plan["checked"] is False


class TestTheAgeHelper:
    def test_it_measures_forward(self):
        assert LS._age_seconds("2026-08-27T11:59:00+00:00", NOW) == 60.0

    def test_a_row_from_the_FUTURE_gives_a_negative_age_and_counts_as_young(self):
        """A clock skew between the spine and the database. Negative is under
        any positive grace, so it takes the safe branch — asserted rather than
        left to arithmetic, because the alternative reading (abs) would retire
        a row that has not existed yet."""
        assert LS._age_seconds("2026-08-27T12:05:00+00:00", NOW) == -300.0
        plan = LS.reconcile([_row("s", started="2026-08-27T12:05:00+00:00")],
                            [], our_mode="dev", now=NOW, grace_seconds=180.0)
        assert plan["actions"][0]["action"] == LS.YOUNG

    @pytest.mark.parametrize("a,b", [
        (None, NOW), (NOW, None), ("", NOW), (NOW, ""),
        ("x", NOW), (NOW, "x"), ("2026-08-27T11:00:00", NOW), (7, NOW),
    ])
    def test_it_is_ABSENT_and_never_raises(self, a, b):
        assert LS._age_seconds(a, b) is None


class TestTheFreshnessFold:
    """``reconciliation_status`` — one input, one state, three values.

    NEVER RUN IS NOT STALE. They call for different responses: stale means the
    worker stopped ticking; never-run means the START-UP pass itself failed,
    which is louder and is the case where an inherited container is still
    holding a signal token. This fund shipped a payload whose note said
    "nothing has ever run, so there is no liveness question to answer" on the
    exact path where the list could not be read; one field with three values is
    the shape that cannot do that.
    """

    def test_never_run_is_its_OWN_state_with_its_OWN_sentence(self):
        s = LS.reconciliation_status(None, NOW, 600.0)
        assert s["state"] == LS.RECON_NEVER
        assert s["ever_run"] is False
        assert s["at"] is None
        assert s["age_seconds"] is None
        assert s["counts"] is None          # NOT zeros
        assert s["checked"] is None
        assert "start-up pass either did not run" in s["note"]
        assert "must not be read as one" in s["note"]

    def test_a_recent_pass_is_FRESH(self):
        last = {"at": "2026-08-27T11:59:00+00:00", "trigger": "worker",
                "report": {"checked": True, "counts": {LS.STOP: 0},
                           "note": "Reconciled 0 running LEAN container(s)."}}
        s = LS.reconciliation_status(last, NOW, 600.0, interval_seconds=300.0)
        assert s["state"] == LS.RECON_FRESH
        assert s["ever_run"] is True
        assert s["age_seconds"] == 60.0
        assert s["trigger"] == "worker"
        assert s["checked"] is True
        assert s["counts"] == {LS.STOP: 0}
        assert s["reconcile_note"].startswith("Reconciled")
        assert "60s ago" in s["note"]

    def test_an_OLD_pass_is_STALE_and_says_what_stopped(self):
        last = {"at": "2026-08-27T10:00:00+00:00", "trigger": "startup",
                "report": {"checked": True, "counts": {}}}
        s = LS.reconciliation_status(last, NOW, 600.0)
        assert s["state"] == LS.RECON_STALE
        assert s["ever_run"] is True
        assert s["age_seconds"] == 7200.0
        assert "worker tick that performs it has stopped" in s["note"]

    def test_the_staleness_boundary_is_probed_on_BOTH_sides(self):
        for age, expected in ((601, LS.RECON_STALE), (600, LS.RECON_FRESH),
                              (599, LS.RECON_FRESH)):
            at = _born(age)
            s = LS.reconciliation_status({"at": at, "report": {}}, NOW, 600.0)
            # The age is asserted alongside the verdict, so an unparseable
            # instant cannot satisfy the STALE arm through the unmeasurable
            # branch — which is a different sentence for a different defect.
            assert s["age_seconds"] == float(age), (age, at)
            assert s["state"] == expected, (age, at)

    @pytest.mark.parametrize("last", [
        {"at": None}, {"at": ""}, {}, "not a dict", 7, [],
    ])
    def test_a_record_with_no_INSTANT_is_never_run_not_fresh(self, last):
        assert LS.reconciliation_status(last, NOW, 600.0)["state"] == LS.RECON_NEVER

    @pytest.mark.parametrize("now,ceiling", [
        (None, 600.0), ("x", 600.0),
        ("2026-08-27T12:00:00+00:00", None),
    ])
    def test_an_UNMEASURABLE_age_is_STALE_and_not_NEVER_and_not_FRESH(
            self, now, ceiling):
        """A reconciliation DID run — that much is known — and how long ago is
        what cannot be told. Reporting it as never-run would overstate the
        problem; reporting it as fresh would understate it."""
        last = {"at": "2026-08-27T11:59:00+00:00", "report": {}}
        s = LS.reconciliation_status(last, now, ceiling)
        assert s["state"] == LS.RECON_STALE
        assert s["ever_run"] is True
        assert "unmeasurable is not recent" in s["note"]

    def test_the_CEILING_it_judged_against_is_published(self):
        """A freshness verdict whose bound is invisible is a verdict nobody can
        check — and the cadence it was derived from is published beside it."""
        s = LS.reconciliation_status(None, NOW, 600.0, interval_seconds=300.0)
        assert s["stale_after_seconds"] == 600.0
        assert s["interval_seconds"] == 300.0

    def test_a_report_that_is_not_a_dict_does_not_poison_the_fold(self):
        s = LS.reconciliation_status({"at": NOW, "report": "boom"}, NOW, 600.0)
        assert s["ever_run"] is True
        assert s["counts"] is None
        assert s["checked"] is None


class TestTheRunnerRecordsAndPublishesIt:
    def _runner(self, tmp_path, containers):
        from app.fund.leanrunner import LeanRunner
        r = LeanRunner(workspace=tmp_path)
        r.registry_rows_or_none = lambda: []
        r.docker_live_containers = lambda: containers
        return r

    def test_a_fresh_runner_has_NEVER_reconciled(self, tmp_path):
        r = self._runner(tmp_path, [])
        s = r.last_reconciliation()
        assert s["state"] == LS.RECON_NEVER
        assert s["ever_run"] is False

    def test_BOTH_triggers_record_the_stamp(self, tmp_path):
        """Recorded inside ``reconcile_containers`` rather than at each caller,
        so a fresh spine does not report ``never_run`` for the first interval
        of its life — which is the reading the field exists to make honest."""
        for trigger in ("startup", "worker"):
            r = self._runner(tmp_path, [])
            r.reconcile_containers(trigger=trigger)
            s = r.last_reconciliation()
            assert s["ever_run"] is True, trigger
            assert s["trigger"] == trigger
            assert s["state"] == LS.RECON_FRESH
            assert s["checked"] is True

    def test_a_pass_that_could_not_compare_still_records_that_it_RAN(self, tmp_path):
        """``checked: False`` and ``ever_run: True`` are both true at once, and
        both are needed: the tick is alive AND it compared nothing."""
        r = self._runner(tmp_path, None)     # docker unreadable
        r.reconcile_containers(trigger="worker")
        s = r.last_reconciliation()
        assert s["ever_run"] is True
        assert s["checked"] is False

    def test_the_default_ceiling_is_TWICE_the_configured_interval(self, tmp_path):
        """One missed tick is a slow host; two is a worker that has stopped."""
        from app.fund import leanrunner as LR
        r = self._runner(tmp_path, [])
        s = r.last_reconciliation()
        assert s["interval_seconds"] == LR.RECONCILE_INTERVAL_SECONDS
        assert s["stale_after_seconds"] == 2 * LR.RECONCILE_INTERVAL_SECONDS

    def test_the_runner_passes_the_registry_page_cap_and_a_clock(self, tmp_path):
        seen = {}
        r = self._runner(tmp_path, [])
        r.registry_page_size = lambda: 200
        import app.fund.leansessions as mod
        real = mod.reconcile

        def spy(*a, **k):
            seen.update(k)
            return real(*a, **k)
        mod.reconcile = spy
        try:
            r.reconcile_containers(trigger="worker", grace_seconds=180.0)
        finally:
            mod.reconcile = real
        assert seen["rows_cap"] == 200
        assert seen["grace_seconds"] == 180.0
        assert seen["now"]      # a real instant, supplied by the runner


class TestTheEndpointPublishesIt:
    def test_the_read_only_endpoint_carries_last_acted(self, monkeypatch,
                                                       tmp_path):
        """WITHOUT THIS FIELD a fund whose worker reconciles every five minutes
        and one whose worker died an hour ago answer this endpoint
        IDENTICALLY — the payload describes a comparison, not a cadence."""
        from fastapi.testclient import TestClient
        from app.api.v1 import fund as fundapi
        from app.fund.leanrunner import LeanRunner
        from fastapi import FastAPI

        r = LeanRunner(workspace=tmp_path)
        r.registry_rows_or_none = lambda: []
        r.docker_live_containers = lambda: []
        r.registry_page_size = lambda: 200
        monkeypatch.setattr(fundapi, "_lean", lambda: r)

        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        c = TestClient(app)

        body = c.get("/api/v1/fund/lean/live/reconciliation").json()
        assert body["last_acted"]["state"] == LS.RECON_NEVER
        # The READ-ONLY twin must not have started acting: asking must not make
        # the answer true.
        assert body["last_acted"]["ever_run"] is False
        # ...and the other side's cap is named rather than rendering null,
        # which reads as "no cap" on a read that has one.
        assert body["rows_cap"] == 200
        assert body["rows_capped"] is False

        r.reconcile_containers(trigger="worker")
        body = c.get("/api/v1/fund/lean/live/reconciliation").json()
        assert body["last_acted"]["state"] == LS.RECON_FRESH
        assert body["last_acted"]["trigger"] == "worker"


class TestTheReattachDoesNotClobberTheThreadThatOwnsTheSession:
    """FOUND BY THE LATE READ-THROUGH, not by any suite, and it is a defect the
    PERIODIC pass created rather than one it inherited.

    ``_run_live`` binds ``session = self._live[session_id]`` ONCE and mutates
    that object for the rest of the session's life. The REATTACH branch of
    ``reconcile_containers`` did ``self._live[sid] = taken`` — a NEW dict built
    from the registry row.

    At START-UP that is correct and harmless: ``_live`` is empty, there is no
    thread, and taking the row back in is the entire point. Every five minutes
    it is not. After the first periodic pass, ``_live[sid]`` and the object the
    running thread is writing to are two different dicts — so when the engine
    exits, the thread records ``ended`` on its own object while
    ``live_sessions()`` and ``stop_live()`` read ``running``, forever.

    Asserted by IDENTITY. Equality would pass on the clobbered version, because
    the replacement dict is built from a row that (at that instant) says the
    same thing.
    """

    def _runner(self, tmp_path, sid="abc123"):
        from app.fund.leanrunner import LeanRunner
        r = LeanRunner(workspace=tmp_path)
        con = f"{LS.CONTAINER_PREFIX}{sid}"
        owned = {"session_id": sid, "algorithm": "probe", "class_name": "P",
                 "state": "running", "started_at": "2026-08-27T11:00:00+00:00",
                 "stopped_at": None, "container": con, "strategy_id": "s1",
                 "signal_configured": True, "error": None, "log_tail": [],
                 "scope_key": "strategy:s1", "mode": "alpaca-paper"}
        r._live[sid] = owned
        r.registry_rows_or_none = lambda: [dict(owned)]
        r.docker_live_containers = lambda: [{"name": con,
                                             "mode": "alpaca-paper"}]
        r._our_mode = lambda: "alpaca-paper"
        return r, owned, sid

    def test_the_object_in__live_IS_the_one_the_thread_holds(self, tmp_path):
        r, owned, sid = self._runner(tmp_path)
        r.reconcile_containers(trigger="worker", grace_seconds=180.0)
        assert r._live[sid] is owned

    def test_a_state_the_thread_writes_AFTER_a_pass_is_what_is_served(
            self, tmp_path):
        """THE CONSEQUENCE, which is what makes the identity assertion matter.
        The engine exits; the thread records it; the process must agree."""
        r, owned, sid = self._runner(tmp_path)
        r.reconcile_containers(trigger="worker", grace_seconds=180.0)
        owned["state"] = "ended"
        owned["stopped_at"] = "2026-08-27T12:00:00+00:00"
        assert r._live[sid]["state"] == "ended"

    def test_it_is_recorded_as_a_FINDING_and_not_skipped_silently(self,
                                                                 tmp_path):
        """A reconciliation's job is to say what it found. "This one is already
        ours" is a finding, and a pass that dropped it would report an action
        list that does not add up to the containers it saw."""
        r, _, sid = self._runner(tmp_path)
        rep = r.reconcile_containers(trigger="worker", grace_seconds=180.0)
        act, = rep["actions"]
        assert act["action"] == LS.REATTACH
        assert act["done"] is False
        assert "already holds the session" in act["detail"]

    def test_a_session_this_process_does_NOT_hold_is_still_taken(self,
                                                                 tmp_path):
        """THE POSITIVE CONTROL, and it is the start-up case — the one that has
        been correct all along. A guard that skipped every reattach would have
        un-built the feature."""
        r, owned, sid = self._runner(tmp_path)
        r._live.clear()
        rep = r.reconcile_containers(trigger="startup")
        act, = rep["actions"]
        assert act["action"] == LS.REATTACH
        assert act["done"] is True
        assert sid in r._live
        assert r._live[sid]["restored"] is True

    def test_a_repeat_pass_is_IDEMPOTENT(self, tmp_path):
        """Three passes, one outcome. The other ticks in that loop all have
        this property and this one must too."""
        r, owned, sid = self._runner(tmp_path)
        r._live.clear()
        first = r.reconcile_containers(trigger="startup")
        taken = r._live[sid]
        assert first["actions"][0]["done"] is True
        for _ in range(2):
            rep = r.reconcile_containers(trigger="worker", grace_seconds=180.0)
            assert rep["actions"][0]["done"] is False
            assert r._live[sid] is taken


class TestTheWorkerTickCannotKillTheWorker:
    """The second read-through finding. Every tick in ``_scheduler``'s loop is
    wrapped in its own ``try`` so an exception costs one tick and never the
    worker — but an IMPORT at function level is not covered by any of them, and
    a coroutine that raises inside ``asyncio.create_task`` surfaces its
    exception only when it is awaited, at shutdown. The whole deterministic
    worker would go quiet with nothing in the log."""

    def test_the_imports_that_serve_the_tick_are_guarded(self):
        i = MAIN_SRC.index("from app.fund import leanrunner as _lr")
        window = MAIN_SRC[max(0, i - 900):i + 700]
        assert "try:" in window
        assert "except Exception" in window
        assert "_log.error" in window
        # ...and the failure is LOUD about what it cost, not a bare message.
        assert "UNWIRED in this process" in window
        assert "window between start-ups is open again" in window

    def test_a_falsy_interval_DISABLES_the_tick_rather_than_firing_it(self):
        """``reconcile_every = 0`` is both the failure path and a supported
        setting. Without the guard, ``since_reconcile >= 0`` is true on every
        tick and a broken import would produce a reconciliation attempt every
        thirty seconds."""
        assert "if reconcile_every and since_reconcile >= reconcile_every:" \
            in MAIN_SRC

    def test_the_ACTED_count_excludes_the_steady_state(self):
        """A live session's row and its container agree on EVERY pass, so a
        reattach is the steady state of a healthy fund. Counting it as "acted"
        would put a warning in the log every five minutes for as long as
        anything is running — which is how a log stops being read.

        Pinned at the source because the alternative is a five-minute
        integration test, and what is being asserted is a decision, not a
        behaviour that varies."""
        i = MAIN_SRC.index("acted = sum(")
        window = MAIN_SRC[i:i + 300]
        assert '.get("done") is True' in window
        assert '!= _ls.REATTACH' in window
        # It counts ACTIONS PERFORMED, not the plan's counts: an action the
        # runner declined to perform must not read as one it did.
        assert 'rep.get("actions")' in window
        assert 'rep.get("counts")' not in window
