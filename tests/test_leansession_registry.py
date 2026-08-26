"""The session registry against a real Postgres.

The tests in ``test_leansessions.py`` prove the RULES; these prove the
DATABASE enforces them, which is a different claim and the one that matters
across processes. An in-process lock cannot refuse a second spine, and a
second spine is exactly what a restart is.

Skipped unless a Postgres is reachable, like ``test_pgstore.py`` — and, like
it, always into its OWN database. A test that can wreck the operational
session table is not a test.
"""

import os
import threading
import uuid

import pytest

from app.fund import leansessions as LS

# IMPORTED AT MODULE SCOPE UNDER AN EXPLICIT ENV GUARD, and both halves are
# load-bearing.
#
# ``app.api.v1.fund`` wires its event store AT IMPORT (fund.py:262). Import it
# inside a test that has already set FUND_STORE=postgres and it goes to the
# MODE-resolved database (krypton_fund_dev), which does not exist here, and
# retries the connection for 30 seconds before failing. So it is imported at
# module scope, where collection happens before any fixture runs — AND with
# FUND_STORE forced to a non-Postgres value for the duration, because an
# EXPORTED FUND_STORE=postgres is already set at collection and ``conftest``'s
# ``setdefault`` cannot neutralise it the way it neutralises a ``.env`` file.
# Without the guard this file is uncollectable in any shell that exports it.
#
# Found by the Gauntlet's env-sensitivity pass. The import-time wiring itself is
# a pre-existing defect, open since builder ENG1, and is not this dispatch's to
# fix — this is a work-around and says so.
_PREV_STORE = os.environ.get("FUND_STORE")
os.environ["FUND_STORE"] = "firestore"
try:
    from app.api.v1 import fund as fundapi  # noqa: E402
finally:
    if _PREV_STORE is None:
        os.environ.pop("FUND_STORE", None)
    else:
        os.environ["FUND_STORE"] = _PREV_STORE

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = "krypton_fund_test"


def _test_dsn() -> str:
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    return f"{head}/{TEST_DB}"


def _ensure_db():
    psycopg = pytest.importorskip("psycopg")
    from app.fund.pgstore import dsn
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')


@pytest.fixture(scope="module", autouse=True)
def _fresh_registry():
    """Clear the test registry ONCE per module, never between tests.

    Two different reasons, and both are load-bearing:

    * NOT PER TEST, because tests that depend on an empty table are tests that
      depend on ORDER. Every session id below is a fresh uuid and every scope
      is namespaced by one, so each test asserts on ITS OWN rows and would pass
      on a table with a million others.
    * ONCE PER MODULE, because ``session_rows`` is CAPPED (200 by default) and
      rows here are never deleted by the code under test. Without this, a few
      hundred runs would push a test's own row past the cap and the suite would
      start failing for a reason that has nothing to do with the code — the
      HW1 lesson, arriving inside the test harness instead of an instrument.
    """
    _ensure_db()
    psycopg = pytest.importorskip("psycopg")
    from app.fund.leanstore import LeanStore
    LeanStore(_test_dsn())          # create the tables if this is a fresh DB
    with psycopg.connect(_test_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE fund_lean_sessions")
        conn.commit()


@pytest.fixture
def store():
    _ensure_db()
    from app.fund.leanstore import LeanStore
    return LeanStore(_test_dsn())


def _session(scope: str, sid: str | None = None, state: str = "running"):
    sid = sid or uuid.uuid4().hex[:12]
    return {"session_id": sid, "scope_key": scope, "algorithm": "algo",
            "class_name": "Algo", "strategy_id": scope, "state": state,
            "container": f"{LS.CONTAINER_PREFIX}{sid}",
            "signal_configured": True, "mode": "test", "error": None,
            "log_tail": [], "started_at": "2026-08-27T00:00:00+00:00",
            "stopped_at": None}


class TestTheDatabaseDecidesTheRace:
    def test_a_second_live_claim_on_one_scope_is_refused(self, store):
        """THE INCIDENT AT THE LAYER THAT CAN ACTUALLY REFUSE IT (ticket
        dc12903f). The in-process lock closes the window inside one spine; only
        the partial unique index closes it across two."""
        from app.fund.leanstore import SessionConflict
        scope = f"strategy:{uuid.uuid4()}"
        store.claim_session(_session(scope))
        with pytest.raises(SessionConflict):
            store.claim_session(_session(scope))

    def test_two_threads_claiming_at_once_give_exactly_one_winner(self, store):
        """Two CONNECTIONS, not two dict reads — the closest this suite gets to
        two spines. The barrier makes them arrive together and the assertion is
        on the invariant, not on which one wins."""
        from app.fund.leanstore import SessionConflict
        scope = f"strategy:{uuid.uuid4()}"
        gate = threading.Barrier(2)
        won, lost = [], []

        def go():
            s = _session(scope)
            gate.wait()
            try:
                store.claim_session(s)
                won.append(s["session_id"])
            except SessionConflict:
                lost.append(s["session_id"])

        ts = [threading.Thread(target=go) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        assert len(won) == 1, f"expected one winner, got {won}"
        assert len(lost) == 1, f"expected one refusal, got {lost}"

    def test_a_finished_session_releases_its_scope(self, store):
        """The index is PARTIAL on the alive states. MUTANT: make it total and
        a strategy could never run a second session, ever."""
        scope = f"strategy:{uuid.uuid4()}"
        first = _session(scope)
        store.claim_session(first)
        store.update_session({**first, "state": "ended",
                              "stopped_at": "2026-08-27T01:00:00+00:00"})
        store.claim_session(_session(scope))  # must not raise

    def test_a_vanished_session_releases_its_scope(self, store):
        """The state start-up reconciliation writes when a live row has no
        container. If ``vanished`` counted as alive, one lost container would
        lock its strategy out until a human deleted a row."""
        scope = f"strategy:{uuid.uuid4()}"
        first = _session(scope)
        store.claim_session(first)
        store.update_session({**first, "state": LS.VANISHED})
        store.claim_session(_session(scope))

    def test_two_DIFFERENT_scopes_both_claim(self, store):
        store.claim_session(_session(f"strategy:{uuid.uuid4()}"))
        store.claim_session(_session(f"strategy:{uuid.uuid4()}"))

    def test_the_same_session_id_twice_is_still_a_conflict(self, store):
        """Primary key, not the partial index — a different constraint with the
        same SQLSTATE. Both must arrive as SessionConflict, or a retry loop
        would treat a duplicate id as a transport error."""
        from app.fund.leanstore import SessionConflict
        s = _session(f"strategy:{uuid.uuid4()}")
        store.claim_session(s)
        with pytest.raises(SessionConflict):
            store.claim_session({**s, "scope_key": f"strategy:{uuid.uuid4()}"})


class TestTheRowsSurviveTheProcess:
    def test_a_claimed_session_reads_back_in_the_runner_s_own_shape(self, store):
        """A restored row must be key-for-key what ``start_live`` builds, or a
        session's fields would depend on whether the spine had restarted —
        which is exactly the class of defect the engine fence exists to keep
        out of this area."""
        s = _session(f"strategy:{uuid.uuid4()}")
        store.claim_session(s)
        row, = [r for r in store.live_session_rows()
                if r["session_id"] == s["session_id"]]
        for k in ("session_id", "algorithm", "class_name", "strategy_id",
                  "state", "container", "signal_configured", "started_at"):
            assert row[k] == s[k], k
        assert row["restored"] is True

    def test_a_second_store_object_sees_the_first_one_s_rows(self, store):
        """The point of the whole change, stated as a test: the record is the
        table, not the process."""
        from app.fund.leanstore import LeanStore
        s = _session(f"strategy:{uuid.uuid4()}")
        store.claim_session(s)
        fresh = LeanStore(_test_dsn())
        assert any(r["session_id"] == s["session_id"]
                   for r in fresh.live_session_rows())

    def test_live_rows_exclude_the_dead(self, store):
        s = _session(f"strategy:{uuid.uuid4()}")
        store.claim_session(s)
        store.update_session({**s, "state": "ended"})
        assert not any(r["session_id"] == s["session_id"]
                       for r in store.live_session_rows())
        assert any(r["session_id"] == s["session_id"]
                   for r in store.session_rows())


class TestTheEpoch:
    def test_the_registry_says_when_it_began(self, store):
        assert store.registry_epoch()

    def test_the_epoch_does_not_move_when_the_schema_is_re_applied(self, store):
        """MUTANT: drop the ``ON CONFLICT DO NOTHING``. Every restart would
        stamp a new epoch, the fence's anchor would jump forward to now, and
        every signal older than the last restart would fence — the exact
        false-negative the fence's five LIVE bases exist to prevent."""
        from app.fund.leanstore import LeanStore
        first = store.registry_epoch()
        LeanStore(_test_dsn())   # re-runs the DDL, as every start-up does
        LeanStore(_test_dsn())
        assert LeanStore(_test_dsn()).registry_epoch() == first

    def test_the_epoch_is_earlier_than_a_runner_born_now(self, store, tmp_path):
        """The direction argument, measured rather than asserted: the anchor
        moved EARLIER when sessions became durable, and earlier fences strictly
        fewer signals."""
        from app.fund.leanrunner import LeanRunner
        r = LeanRunner(workspace=tmp_path)
        assert store.registry_epoch() < r._born


LIVE_ALGO = """
from AlgorithmImports import *
class LiveAlgo(QCAlgorithm):
    def initialize(self):
        self.sym = self.add_data(SpineBars, "GLD", Resolution.DAILY).symbol
        self.set_benchmark(self.sym)
"""

FAKE_LIVE = r"""
import sys, time
if "kill" in sys.argv[:2]:
    sys.exit(0)
time.sleep(60)
"""


@pytest.fixture
def durable(monkeypatch):
    """A runner factory whose registry is the TEST database.

    ``FUND_PG_DSN`` is redirected rather than ``LeanStore`` stubbed, because
    what is under test is the real query against the real constraint. Every
    env read here is per-call (``pgstore.dsn`` and ``leanstore.enabled`` both
    read ``os.getenv`` each time), so the redirect holds for the whole test and
    is undone with it.
    """
    import sys
    _ensure_db()
    monkeypatch.setenv("FUND_PG_DSN", _test_dsn())
    monkeypatch.setenv("FUND_STORE", "postgres")

    def make(tmp_path, name="ws"):
        from app.fund.leanrunner import LeanRunner
        script = tmp_path / "fake_docker.py"
        script.write_text(FAKE_LIVE, encoding="utf-8")
        r = LeanRunner(workspace=tmp_path / name,
                       docker_cmd=[sys.executable, str(script)])
        r.save_algorithm("live", LIVE_ALGO)
        return r
    return make


class TestTheRunnerAgainstTheRealRegistry:
    def test_a_session_survives_the_process_that_started_it(self, durable, tmp_path):
        """THE HEADLINE. A second runner is a restarted spine: it has an empty
        ``_live`` and must still see, and be able to stop, the session."""
        first = durable(tmp_path)
        sid = first.start_live("live", strategy_id=f"s-{uuid.uuid4()}")["session_id"]

        second = durable(tmp_path, name="ws2")
        assert any(s["session_id"] == sid for s in second.live_sessions())
        assert second.live_session(sid)["state"] in LS.ALIVE
        assert second.stop_live(sid)["state"] == "stopped"

    def test_the_uniqueness_basis_is_the_registry_when_there_is_one(
            self, durable, tmp_path):
        r = durable(tmp_path)
        out = r.start_live("live", strategy_id=f"s-{uuid.uuid4()}")
        assert out["uniqueness_basis"] == "registry"

    def test_a_SECOND_process_cannot_start_the_same_scope(self, durable, tmp_path):
        """What no in-process lock can do. The first runner holds the scope;
        the second has an empty ``_live`` and would have sailed straight past
        the memory guard."""
        from app.fund.leanrunner import LeanConflict
        scope = f"s-{uuid.uuid4()}"
        durable(tmp_path).start_live("live", strategy_id=scope)
        with pytest.raises(LeanConflict):
            durable(tmp_path, name="ws2").start_live("live", strategy_id=scope)

    def test_the_anchor_becomes_the_registry_epoch_not_this_process(
            self, durable, tmp_path):
        """The fence's anchor, MOVED. Two runners built apart report the SAME
        anchor once sessions are durable, where before they reported two — and
        that anchor is earlier than either birth, which is the safe direction.
        """
        a = durable(tmp_path)
        b = durable(tmp_path, name="ws2")
        assert a.sessions_known_since() == b.sessions_known_since()
        assert a.sessions_known_since() < a._born

    def test_an_unreadable_registry_makes_the_anchor_ABSENT(
            self, durable, tmp_path, monkeypatch):
        """MUTANT: fall back to ``_born``. That is the LATER value and would
        fence MORE signals on the exact path where the registry might have
        accounted for them."""
        r = durable(tmp_path)
        monkeypatch.setattr(type(r), "_registry",
                            lambda self: (_ for _ in ()).throw(RuntimeError("down")))
        assert r.sessions_known_since() is None

    def test_an_unreadable_registry_makes_live_sessions_RAISE(
            self, durable, tmp_path, monkeypatch):
        """NOT ``[]``. ``fund._live_sessions_or_none`` turns an exception into
        ``None`` ("could not be read") and a list into a claim; after a restart
        ``_live`` is empty, so returning it while the registry was unreachable
        would claim nothing is running on the one path where we cannot know."""
        r = durable(tmp_path)
        monkeypatch.setattr(type(r), "_registry",
                            lambda self: (_ for _ in ()).throw(RuntimeError("down")))
        with pytest.raises(RuntimeError):
            r.live_sessions()

    def test_an_unregisterable_session_is_NOT_started(
            self, durable, tmp_path, monkeypatch):
        """FAIL CLOSED. Starting a container the registry never recorded
        creates exactly the orphan this whole change exists to remove — so the
        refusal costs a retry and the alternative costs a container nobody can
        stop."""
        from app.fund.leanrunner import LeanError
        r = durable(tmp_path)
        monkeypatch.setattr(type(r), "_registry",
                            lambda self: (_ for _ in ()).throw(RuntimeError("down")))
        with pytest.raises(LeanError, match="refusing to start"):
            r.start_live("live", strategy_id=f"s-{uuid.uuid4()}")
        assert r._live == {}

    def test_reconciliation_reattaches_a_session_this_process_never_started(
            self, durable, tmp_path):
        """THE ORPHAN, ADOPTED. The registry knows it and docker says it runs,
        so the restarted spine takes it back and it is stoppable again — which
        is the whole content of ``engineledger.ORPHAN_NOTE``'s former claim
        that closing this needed exactly this."""
        first = durable(tmp_path)
        sid = first.start_live("live", strategy_id=f"s-{uuid.uuid4()}")["session_id"]

        second = durable(tmp_path, name="ws2")
        second.docker_live_containers = lambda: [
            {"name": f"{LS.CONTAINER_PREFIX}{sid}", "mode": None}]
        report = second.reconcile_containers()
        assert report["counts"][LS.REATTACH] == 1
        assert sid in second._live

    def test_reconciliation_marks_a_row_with_no_container_vanished(
            self, durable, tmp_path):
        """And ``vanished`` is not one of the alive states, so the scope is
        released — otherwise one lost container locks its strategy out."""
        r = durable(tmp_path)
        scope = f"s-{uuid.uuid4()}"
        sid = r.start_live("live", strategy_id=scope)["session_id"]
        r._live.clear()                      # a restarted spine
        r.docker_live_containers = lambda: []   # docker answered: nothing
        report = r.reconcile_containers()
        # ON THIS SESSION, not on the count. The test database is shared and
        # never truncated (see the ``store`` fixture), so a global count would
        # be a function of how many other tests ran first — an assertion that
        # passes or fails on test ORDER is not an assertion.
        mine = [a for a in report["actions"] if a["session_id"] == sid]
        assert [a["action"] for a in mine] == [LS.VANISHED]
        rows = r._registry().session_rows(limit=500)
        assert rows, "the registry returned no rows at all"
        row, = [x for x in rows if x["session_id"] == sid]
        assert row["state"] == LS.VANISHED
        assert "UNKNOWN" in (row["error"] or "")
        r.start_live("live", strategy_id=scope)   # the scope is free again


class TestTheEndpointAnswers409:
    def _client(self, monkeypatch, runner):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        monkeypatch.setattr(fundapi, "_lean", lambda: runner)
        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        return TestClient(app)

    def test_the_loser_of_a_race_gets_409_and_the_winner_200(
            self, durable, tmp_path, monkeypatch):
        """THE ACCEPTANCE, ON THE WIRE. On 2026-08-26 two identical POSTs two
        milliseconds apart BOTH returned 200 (ticket dc12903f). One 200, one
        409, and the 409 body says which scope it lost."""
        r = durable(tmp_path)
        c = self._client(monkeypatch, r)
        scope = f"s-{uuid.uuid4()}"
        body = {"algorithm": "live", "strategy_id": scope}
        first = c.post("/api/v1/fund/lean/live", json=body)
        second = c.post("/api/v1/fund/lean/live", json=body)
        assert first.status_code == 200, first.text
        assert second.status_code == 409, second.text
        assert scope in second.json()["detail"]

    def test_an_ordinary_refusal_is_still_400(self, durable, tmp_path, monkeypatch):
        """MUTANT: catch LeanError before LeanConflict, or map both to 409.
        "You asked for something impossible" and "someone else got there
        first" are different answers and a retrying caller is right about
        exactly one of them."""
        r = durable(tmp_path)
        c = self._client(monkeypatch, r)
        resp = c.post("/api/v1/fund/lean/live",
                      json={"algorithm": "no-such-algorithm"})
        assert resp.status_code == 400, resp.text

    def test_the_list_publishes_whether_sessions_are_durable_at_all(
            self, durable, tmp_path, monkeypatch):
        """An empty session list means two different things and the reader
        cannot tell them apart without this."""
        r = durable(tmp_path)
        c = self._client(monkeypatch, r)
        body = c.get("/api/v1/fund/lean/live").json()
        assert body["registry"]["durable"] is True
        assert body["registry"]["sessions_known_since"]
        assert body["registry"]["max_live_sessions"] >= 1

    def test_the_read_only_reconciliation_reports_its_domain(
            self, durable, tmp_path, monkeypatch):
        r = durable(tmp_path)
        r.docker_live_containers = lambda: None
        c = self._client(monkeypatch, r)
        body = c.get("/api/v1/fund/lean/live/reconciliation").json()
        assert body["checked"] is False
        assert body["containers_seen"] is None
        assert body["registry_readable"] is True
        assert body["actions"] == []

    def test_an_unreadable_registry_is_503_and_never_an_empty_session_list(
            self, durable, tmp_path, monkeypatch):
        """FOUND BY THE GAUNTLET: this endpoint called ``live_sessions()`` with
        no handler, and that method RAISES by design when the registry is
        configured and unreachable — so the failure fell through to an
        unstructured 500 while its sibling reconciliation endpoint answered
        cleanly.

        503 rather than 200-with-an-empty-list is the whole point. After a
        restart the in-memory table is empty, so ``{"sessions": []}`` would
        tell the reader that NOTHING IS RUNNING on the exact path where nothing
        can be known — and every consumer of this endpoint, including the
        engine fence's own domain, counts what it returns.
        """
        r = durable(tmp_path)
        monkeypatch.setattr(type(r), "_registry",
                            lambda self: (_ for _ in ()).throw(RuntimeError("down")))
        c = self._client(monkeypatch, r)
        resp = c.get("/api/v1/fund/lean/live")
        assert resp.status_code == 503, resp.text
        body = resp.json()["detail"]
        assert "UNKNOWN" in body
        assert "not a claim that nothing is running" in body


class TestTheLookupDoesNotExpireAtTheCap:
    def test_a_session_past_the_page_cap_is_still_found_by_id(
            self, durable, tmp_path, monkeypatch):
        """MUTATION SURVIVOR M61. ``live_session`` used to scan
        ``session_rows()``, which is a CAPPED page — so the lookup answered
        "unknown live session" for a real session as soon as 200 newer ones
        existed, and a session nobody could look up is a session nobody can
        stop.

        Tested against the CONTRACT rather than by inserting 201 rows: the fake
        registry's page deliberately does NOT contain the id and its by-id read
        does. A scan cannot pass this; a lookup cannot fail it.
        """
        from app.fund.leanrunner import LeanError
        r = durable(tmp_path)
        wanted = {"session_id": "beyond-the-cap", "state": "running",
                  "algorithm": "live", "container": "lean-live-beyond-the-cap",
                  "started_at": "2026-01-01T00:00:00+00:00", "restored": True}

        class _Paged:
            def session_rows(self, limit=200):
                return [{"session_id": f"newer-{i}", "state": "ended"}
                        for i in range(limit)]

            def live_session_rows(self):
                return []

            def session(self, session_id):
                return dict(wanted) if session_id == wanted["session_id"] else None

        monkeypatch.setattr(type(r), "_registry", lambda self: _Paged())
        assert r.live_session("beyond-the-cap")["container"] == \
            "lean-live-beyond-the-cap"
        # POSITIVE CONTROL: a genuinely unknown id must still raise, or the
        # assertion above would pass on a lookup that returns everything.
        with pytest.raises(LeanError, match="unknown live session"):
            r.live_session("no-such-session")

    def test_a_stop_is_WRITTEN_to_the_registry_and_releases_the_scope(
            self, durable, tmp_path):
        """MUTATION SURVIVOR M66. Without the write the row stays ``running``
        for ever: the partial unique index would refuse every future session
        for that strategy, and the next start-up would find a live row with no
        container and mark it vanished — a strategy locked out until a
        restart."""
        r = durable(tmp_path)
        scope = f"s-{uuid.uuid4()}"
        sid = r.start_live("live", strategy_id=scope)["session_id"]
        r.stop_live(sid)
        row = r._registry().session(sid)
        assert row is not None
        assert row["state"] == "stopped"
        assert row["stopped_at"]
        # AND A SECOND PROCESS CAN CLAIM THE SCOPE AGAIN — the consequence,
        # asserted separately, because the row's value is only interesting for
        # what it permits.
        durable(tmp_path, name="ws2").start_live("live", strategy_id=scope)

    def test_the_by_id_read_is_an_EQUALITY_and_never_a_pattern(self, store):
        """MUTATION SURVIVOR M78, and it is the one with teeth.

        ``DELETE /fund/lean/live/{session_id}`` puts a caller-supplied string
        straight into this lookup and then KILLS whatever container comes back.
        Under ``LIKE`` instead of ``=``, ``%`` matches every row — so one
        request could stop a session it never named. Session ids are hex today
        and contain no wildcard, which is exactly why nothing noticed: the
        defect is unreachable through legitimate input and wide open to
        anything else.
        """
        s = _session(f"strategy:{uuid.uuid4()}")
        store.claim_session(s)
        assert store.session(s["session_id"])["session_id"] == s["session_id"]
        for pattern in ("%", "_" * len(s["session_id"]), s["session_id"][:4] + "%"):
            assert store.session(pattern) is None, pattern

    def test_the_page_really_IS_the_published_cap(self, store, monkeypatch):
        """MUTATION SURVIVOR M81, and it is the HW1 failure mode exactly: the
        reconciliation PUBLISHES a cap, and nothing checked that the query
        obeys the number it publishes. Under the mutant the payload says 7 and
        the query fetches 200 - a published bound that is not the bound.

        MOVED, not compared: an assertion that the page returns 200 rows cannot
        tell a read of the constant from a literal that happens to agree.
        """
        from app.fund.leanstore import LeanStore
        for _ in range(9):
            store.claim_session(_session(f"strategy:{uuid.uuid4()}",
                                         state="ended"))
        monkeypatch.setattr(LeanStore, "SESSION_PAGE", 3)
        assert len(store.session_rows()) == 3
        monkeypatch.setattr(LeanStore, "SESSION_PAGE", 5)
        assert len(store.session_rows()) == 5
        # An explicit limit still wins, because the reconciler is not the only
        # caller this method will ever have.
        assert len(store.session_rows(limit=2)) == 2

    def test_a_late_running_stamp_cannot_resurrect_a_retired_row(
            self, durable, tmp_path):
        """THE RACE, AS A TEST. Measured at 2 failures in 20 runs before the
        guard: ``_run_live`` stamps ``running`` from a daemon thread, and if
        reconciliation retires the row in between, the straggler wrote
        ``running`` back over ``vanished`` — a session with no container,
        holding its strategy's scope, that nothing would look at again until
        the next restart.

        Driven through the STORE rather than by racing threads, because a test
        that reproduces a race by timing is a test that reproduces it 10% of
        the time.
        """
        r = durable(tmp_path)
        store = r._registry()
        s = _session(f"strategy:{uuid.uuid4()}")
        store.claim_session(s)
        # something retires it
        assert store.update_session({**s, "state": LS.VANISHED}) == 1
        # ... and the straggling stamp arrives
        assert store.update_session({**s, "state": "running"},
                                    only_if_alive=True) == 0
        assert store.session(s["session_id"])["state"] == LS.VANISHED

    def test_the_guard_does_NOT_block_a_stamp_on_a_live_row(
            self, durable, tmp_path):
        """POSITIVE CONTROL, AND IT ASSERTS SOMETHING. Without it the test
        above is satisfied by a guard that blocks EVERY write, which would
        leave every session stuck at ``starting`` for ever — a refusal wearing
        a race fix's clothes."""
        r = durable(tmp_path)
        store = r._registry()
        s = _session(f"strategy:{uuid.uuid4()}", state="starting")
        store.claim_session(s)
        assert store.update_session({**s, "state": "running"},
                                    only_if_alive=True) == 1
        assert store.session(s["session_id"])["state"] == "running"

    def test_a_terminal_write_is_never_blocked(self, durable, tmp_path):
        """``only_if_alive`` is opt-in and only ``_run_live``'s running stamp
        opts in. A stop, an end or a vanish must always land, or a session
        could never leave the alive set and its scope would be held for ever."""
        r = durable(tmp_path)
        store = r._registry()
        s = _session(f"strategy:{uuid.uuid4()}")
        store.claim_session(s)
        assert store.update_session({**s, "state": LS.VANISHED}) == 1
        assert store.update_session({**s, "state": "ended"}) == 1
        assert store.session(s["session_id"])["state"] == "ended"

