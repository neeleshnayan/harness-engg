"""The live-session decisions, and the three defects they close.

THE INCIDENTS THESE TESTS GUARD, NAMED:

  * **The TOCTOU double-start (ticket dc12903f, 2026-08-26, chair-verified on
    the live spine).** ``start_live`` read the session table under a lock,
    RELEASED it, and then inserted under the lock again. Two identical POSTs two
    milliseconds apart both got 200. Guarded here by the atomicity pin and the
    barrier race, and at the database by the partial unique index.
  * **The unstoppable orphan (builder ENG2, published as
    ``engineledger.ORPHAN_CHECK=False``).** A LEAN container is started with
    ``docker run`` from a daemon thread, so it lives in the docker daemon and
    outlives the spine; after a restart the session table was empty and
    ``stop_live`` could not reach it. Guarded by the reconciliation tests.
  * **The absence collapse (builder ENG1, the ``engine_status`` payload that
    contradicted itself).** Every input here is three-valued and its unreadable
    case is its own value; the tests below assert on the ACTION, so a reconciler
    that reads ``None`` as "nothing running" cannot pass.
"""

import ast
import inspect
import pathlib
import textwrap
import threading

import pytest

from app.fund import leansessions as LS

#: The spine's entry module, READ AS TEXT rather than imported.
#:
#: ``app.api.v1.fund`` wires its event store AT IMPORT (fund.py:262) and
#: ``app.main`` imports it, so importing either from this file sends it to the
#: MODE-resolved database whenever ``FUND_STORE=postgres`` is set in the
#: environment — 30 seconds of connect retries and then a failure, and at
#: module scope that takes the whole FILE uncollectable. Found by the
#: Gauntlet's env-sensitivity pass against an EXPORTED variable, which
#: ``conftest``'s ``setdefault`` cannot neutralise the way it neutralises a
#: ``.env`` file.
#:
#: The first fix moved the import to module scope and traded eight failures for
#: a collection error, which is worse. The right answer is that this file needs
#: no import: the claim under test is about the SHAPE OF THE SOURCE, and source
#: is a file. The underlying import-time wiring is a pre-existing defect, open
#: since builder ENG1, and is not this dispatch's to fix.
MAIN_SRC = (pathlib.Path(__file__).resolve().parents[1]
            / "app" / "main.py").read_text(encoding="utf-8")


# ================================================================ the scope key

class TestScopeKey:
    def test_a_strategy_is_the_scope_when_there_is_one(self):
        assert LS.scope_key("s1", "algo") == "strategy:s1"

    def test_the_algorithm_is_the_scope_when_the_session_is_unscoped(self):
        """The Lab starts sessions with no strategy_id, and two of those
        running one algorithm is the same hazard with no name:
        ``engineledger._claiming_session`` matches a signal on strategy id OR
        algorithm, so either duplicate makes one signal claimable twice."""
        assert LS.scope_key("", "algo") == "algorithm:algo"
        assert LS.scope_key(None, "algo") == "algorithm:algo"

    def test_whitespace_is_not_a_strategy(self):
        """``"   ".upper()`` is truthy and this fund has already been bitten by
        that once. A blank strategy id must fall through to the algorithm, not
        create a scope named after three spaces."""
        assert LS.scope_key("   ", "algo") == "algorithm:algo"

    def test_two_strategies_never_share_a_scope(self):
        assert LS.scope_key("s1", "a") != LS.scope_key("s2", "a")

    def test_a_strategy_scope_and_an_algorithm_scope_cannot_collide(self):
        """MUTANT: return the bare id instead of a prefixed key. A strategy
        literally named ``algo`` would then share a scope with the algorithm
        ``algo`` and one would refuse the other."""
        assert LS.scope_key("x", "y") != LS.scope_key("", "x")

    def test_nothing_identifiable_does_not_collapse_to_an_empty_key(self):
        """An empty key would make every unidentifiable session collide with
        every other one — a refusal dressed as a uniqueness rule."""
        assert LS.scope_key("", "") == "unidentified:"


# ================================================================== the name

class TestSessionIdOfContainer:
    def test_the_id_comes_back_out_of_the_name(self):
        assert LS.session_id_of("lean-live-abc123") == "abc123"

    def test_a_substring_match_is_not_ours(self):
        """``docker ps --filter name=`` is a SUBSTRING match, verified against
        the real daemon, so a container called ``mine-lean-live-x`` arrives
        from the same query. Prefix, never ``in``."""
        assert LS.session_id_of("mine-lean-live-x") is None

    def test_the_bare_prefix_names_no_session(self):
        assert LS.session_id_of("lean-live-") is None
        assert LS.session_id_of("lean-live-   ") is None

    def test_absence_is_not_a_name(self):
        assert LS.session_id_of(None) is None
        assert LS.session_id_of("") is None


# =============================================================== ownership

class TestOwnership:
    def test_an_unlabelled_container_is_ours_by_name(self):
        """Containers started before the label existed — including the one
        running while this was written — carry no label and are ours."""
        assert LS.ownership(None, "dev") == LS.OWN_LEGACY
        assert LS.ownership("", "dev") == LS.OWN_LEGACY

    def test_our_own_label_is_ours(self):
        assert LS.ownership("dev", "dev") == LS.OWN_OURS

    def test_another_mode_is_never_ours(self):
        assert LS.ownership("prod", "dev") == LS.OWN_FOREIGN

    def test_an_unreadable_own_mode_cannot_judge_a_labelled_container(self):
        """MUTANT: fall back to OURS when our mode is unknown. That makes the
        destructive branch run on an unproven claim — a dev spine with an
        unresolvable mode would stop production's session."""
        assert LS.ownership("prod", None) == LS.OWN_UNJUDGEABLE
        assert LS.ownership("prod", "") == LS.OWN_UNJUDGEABLE

    @pytest.mark.parametrize("own", [LS.OWN_FOREIGN, LS.OWN_UNJUDGEABLE])
    def test_what_is_not_ours_is_never_touched(self, own):
        assert LS._touchable(own) is False

    @pytest.mark.parametrize("own", [LS.OWN_OURS, LS.OWN_LEGACY])
    def test_what_is_ours_is_actionable(self, own):
        assert LS._touchable(own) is True


# ================================================================= is_alive

class TestIsAlive:
    @pytest.mark.parametrize("state", list(LS.ALIVE))
    def test_the_alive_states_are_alive(self, state):
        assert LS.is_alive({"state": state}) is True

    @pytest.mark.parametrize("state",
                             ["stopped", "ended", "failed", LS.VANISHED, "", None])
    def test_everything_else_is_not(self, state):
        assert LS.is_alive({"state": state}) is False

    def test_a_row_that_is_not_a_row_is_not_alive(self):
        assert LS.is_alive(None) is False
        assert LS.is_alive("running") is False

    def test_the_alive_set_matches_the_fence_s_own(self):
        """PROVE IT IS THE SAME RULE, not two that agree today. The engine
        fence decides whether a signal is claimed by a LIVE session using its
        own ``_SESSION_ALIVE``; two ideas of "alive" is the second-opinion
        defect the fence was written to keep out of this area."""
        from app.fund import engineledger
        assert tuple(LS.ALIVE) == tuple(engineledger._SESSION_ALIVE)

    def test_vanished_is_not_one_of_the_alive_states(self):
        """A vanished row must release its scope, or one dead container locks
        a strategy out of the engine forever."""
        assert LS.VANISHED not in LS.ALIVE


# ============================================================== reconcile

def _row(sid, state="running", **kw):
    return {"session_id": sid, "state": state,
            "container": f"{LS.CONTAINER_PREFIX}{sid}", **kw}


def _con(sid, mode=None):
    return {"name": f"{LS.CONTAINER_PREFIX}{sid}", "mode": mode}


def _actions(plan):
    return {a["session_id"]: a["action"] for a in plan["actions"]}


class TestReconcileTheHappyPaths:
    def test_a_known_running_container_is_reattached(self):
        plan = LS.reconcile([_row("a")], [_con("a")], our_mode="dev")
        assert _actions(plan) == {"a": LS.REATTACH}
        assert plan["checked"] is True

    def test_a_container_with_no_row_is_stopped(self):
        """THE ORPHAN. A container the registry has never known is holding a
        signal token and can POST proposals into the approval queue."""
        plan = LS.reconcile([], [_con("ghost")], our_mode="dev")
        assert _actions(plan) == {"ghost": LS.STOP}

    def test_a_row_the_registry_calls_dead_beside_a_running_container_is_adopted(self):
        """The container is the fact. A row saying ``stopped`` while the
        process is up means the kill failed or raced, and recording it as
        running is the truth — which is also what makes it stoppable again."""
        plan = LS.reconcile([_row("a", "stopped")], [_con("a")], our_mode="dev")
        assert _actions(plan) == {"a": LS.ADOPT}

    def test_a_live_row_with_no_container_vanished(self):
        plan = LS.reconcile([_row("a")], [], our_mode="dev")
        assert _actions(plan) == {"a": LS.VANISHED}

    def test_a_dead_row_with_no_container_is_left_entirely_alone(self):
        """Nothing to do and nothing to say: the ordinary end of every
        session. MUTANT: report it as vanished and every finished session
        would be re-written on every start-up."""
        plan = LS.reconcile([_row("a", "ended")], [], our_mode="dev")
        assert plan["actions"] == []

    def test_another_mode_s_container_is_recorded_and_never_stopped(self):
        """Two spines share one docker daemon and one ``lean-live-``
        namespace. Without the label the second would call the first's session
        an unaccounted orphan and kill it."""
        plan = LS.reconcile([], [_con("theirs", mode="prod")], our_mode="dev")
        assert _actions(plan) == {"theirs": LS.LEAVE}
        assert plan["counts"][LS.STOP] == 0

    def test_a_foreign_container_is_left_even_when_a_row_exists(self):
        """MUTANT: check ownership only on the orphan branch. A row plus a
        foreign label must not re-attach someone else's container into our
        session table."""
        plan = LS.reconcile([_row("x")], [_con("x", mode="prod")],
                            our_mode="dev")
        assert _actions(plan) == {"x": LS.LEAVE}

    def test_everything_at_once_is_counted_separately(self):
        plan = LS.reconcile(
            [_row("keep"), _row("gone"), _row("zombie", "ended")],
            [_con("keep"), _con("ghost"), _con("zombie"),
             _con("alien", mode="prod")],
            our_mode="dev")
        assert plan["counts"] == {LS.REATTACH: 1, LS.ADOPT: 1, LS.STOP: 1,
                                  LS.LEAVE: 1, LS.VANISHED: 1}


class TestReconcileCannotRead:
    """THE HALF THAT MATTERS. Every one of these asserts that an UNREADABLE
    input produces NO ACTION and says so — never an empty action list that
    reads like agreement."""

    def test_an_unreadable_docker_stops_nothing_and_vanishes_nothing(self):
        plan = LS.reconcile([_row("a")], None, our_mode="dev")
        assert plan["actions"] == []
        assert plan["checked"] is False
        assert plan["containers_readable"] is False
        assert plan["containers_seen"] is None
        assert plan["rows_alive"] == 1
        assert "UNKNOWN rather than no" in plan["note"]

    def test_an_unreadable_registry_stops_no_container(self):
        """MUTANT: treat ``rows=None`` as ``[]``. Every running container would
        then be an orphan and every one of them would be killed at start-up —
        a whole fund's engines stopped by one unreachable database."""
        plan = LS.reconcile(None, [_con("a"), _con("b")], our_mode="dev")
        assert plan["actions"] == []
        assert plan["counts"][LS.STOP] == 0
        assert plan["registry_readable"] is False
        assert plan["rows_seen"] is None
        assert plan["rows_alive"] is None
        assert plan["containers_seen"] == 2

    def test_neither_readable_says_so_in_one_sentence(self):
        plan = LS.reconcile(None, None)
        assert plan["checked"] is False
        assert "Neither" in plan["note"]

    def test_docker_answering_EMPTY_is_a_claim_and_is_acted_on(self):
        """The other side of the same coin, and the reason ``None`` and ``[]``
        must stay different values: ``[]`` means the daemon answered and
        nothing is running, which is exactly when a live row IS vanished."""
        plan = LS.reconcile([_row("a")], [], our_mode="dev")
        assert plan["checked"] is True
        assert _actions(plan) == {"a": LS.VANISHED}


class TestReconcileReportsItsDomain:
    def test_a_zero_carries_what_it_compared(self):
        """A null result with no domain is not a result. ``0 orphans`` over 4
        containers and 4 rows is a measurement; ``0 orphans`` over nothing is
        a sentence."""
        plan = LS.reconcile([_row(str(i)) for i in range(4)],
                            [_con(str(i)) for i in range(4)], our_mode="dev")
        assert plan["counts"][LS.STOP] == 0
        assert plan["rows_seen"] == 4
        assert plan["rows_alive"] == 4
        assert plan["containers_seen"] == 4
        assert "4 running LEAN container(s) against 4 session(s)" in plan["note"]

    def test_a_container_that_is_not_ours_by_name_is_not_in_the_domain(self):
        plan = LS.reconcile([], [{"name": "postgres", "mode": None},
                                 _con("a")], our_mode="dev")
        assert plan["containers_seen"] == 1

    def test_the_note_is_a_whole_sentence(self):
        """Every consumer concatenates it. A fold that emits half-sentences
        makes punctuation the caller's problem and the caller gets it wrong —
        the engine page printed "...are gone The dead session had asked" for
        exactly this reason."""
        for plan in (LS.reconcile([], [], our_mode="dev"),
                     LS.reconcile(None, None),
                     LS.reconcile([_row("a")], None),
                     LS.reconcile(None, [_con("a")])):
            assert plan["note"].endswith("."), plan["note"]

    def test_our_mode_is_published_so_a_reader_can_see_what_judged_ownership(self):
        assert LS.reconcile([], [], our_mode="dev")["our_mode"] == "dev"
        assert LS.reconcile([], [], our_mode=None)["our_mode"] is None


# ============================================================== the anchor

class TestKnownSince:
    """The fence's anchor, and why the direction of every fallback is the safe
    one. ``engineledger.signal_liveness`` fences a signal only when it was
    raised STRICTLY BEFORE this instant, and a fenced signal stops counting
    toward the divergence verdict — so EARLIER fences fewer and is safer."""

    def test_without_a_registry_the_anchor_is_the_process_birth(self):
        assert LS.known_since(False, None, "2026-01-01T00:00:00+00:00") == \
            "2026-01-01T00:00:00+00:00"

    def test_a_registry_epoch_replaces_the_process_birth(self):
        assert LS.known_since(True, "2026-01-01T00:00:00+00:00",
                              "2026-06-01T00:00:00+00:00") == \
            "2026-01-01T00:00:00+00:00"

    def test_an_unreadable_epoch_is_ABSENT_and_not_the_process_birth(self):
        """THE ONE THAT MATTERS. MUTANT: fall back to ``process_born``. That is
        the LATER value, so it would fence MORE signals — the permissive
        direction — on the exact path where the registry might well have
        accounted for them. ``None`` makes the fence prove nothing, which is
        what an unreadable input is required to do."""
        assert LS.known_since(True, None, "2026-06-01T00:00:00+00:00") is None
        assert LS.known_since(True, "   ", "2026-06-01T00:00:00+00:00") is None

    def test_the_registry_epoch_is_earlier_and_that_is_the_safety_argument(self):
        """Not a tautology: it states the property the direction argument
        rests on, so a later reader can check it rather than trust it."""
        epoch, born = "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00"
        assert LS.known_since(True, epoch, born) < LS.known_since(False, None, born)

    def test_a_blank_process_birth_is_absent_too(self):
        assert LS.known_since(False, None, "") is None
        assert LS.known_since(False, None, None) is None


# ===================================================== the rule, spelled once

class TestTheUniquenessRuleIsSpelledOnce:
    def test_the_sql_predicate_is_DERIVED_from_ALIVE_not_retyped(self, monkeypatch):
        """PROVE IT IS READ, NOT COPIED — BY MOVING IT.

        An assertion that the DDL merely CONTAINS ``'running'`` cannot tell a
        real read from a hardcoded duplicate that happens to agree today. So
        the constant is MOVED and the SQL must move with it.
        """
        from app.fund import leanstore
        before = leanstore.session_schema_sql()
        assert "'starting', 'running'" in before

        monkeypatch.setattr(LS, "ALIVE", ("warming", "spinning"))
        after = leanstore.session_schema_sql()
        assert "'warming', 'spinning'" in after
        assert "'running'" not in after

    def test_the_registry_query_reads_the_same_constant(self, monkeypatch):
        """``live_session_rows`` binds ``ALIVE`` as parameters. Pinned at the
        source, because the query needs a database to run and this property
        does not."""
        from app.fund import leanstore
        src = inspect.getsource(leanstore.LeanStore.live_session_rows)
        assert "leansessions.ALIVE" in src
        assert "'running'" not in src and '"running"' not in src


# ================================== the atomicity the race depends on

class TestTheGuardIsAtomic:
    def test_the_scope_check_and_the_insert_are_under_ONE_lock(self):
        """THE TOCTOU, PINNED STRUCTURALLY (ticket dc12903f).

        The behavioural race below is probabilistic — it can only ever say
        "these 50 attempts did not collide". This says the WINDOW DOES NOT
        EXIST: the read that decides and the write that claims are inside the
        same ``with self._lock`` block. Reverting to the two-lock shape that
        shipped the double-200 fails here, deterministically, every time.
        """
        from app.fund import leanrunner
        src = inspect.getsource(leanrunner.LeanRunner.start_live)
        tree = ast.parse(textwrap.dedent(src))
        blocks = []
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                body = "\n".join(ast.unparse(s) for s in node.body)
                head = "".join(ast.unparse(i.context_expr) for i in node.items)
                if "self._lock" in head:
                    blocks.append(body)
        assert blocks, "start_live must claim under a lock at all"
        holding = [b for b in blocks
                   if "self._live[session_id] = session" in b]
        assert len(holding) == 1, "exactly one block may make the claim"
        assert "scope_key" in holding[0], (
            "the scope check must be INSIDE the block that claims — reading it "
            "in an earlier block is the window that let two identical POSTs "
            "both return 200 on 2026-08-26")
        assert "MAX_LIVE_SESSIONS" in holding[0], (
            "the ceiling is decided on the same snapshot as the scope, or two "
            "starts can jointly exceed it")


# ================================== the race, end to end, through the runner

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


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    """EVERY TEST IN THIS FILE IS THE NO-REGISTRY CASE, AND IT SAYS SO.

    These tests exist to prove the IN-PROCESS half of the guard — the half a
    deployment without Postgres has all of. Left to inherit the ambient
    environment they were a different test on a developer's machine than in
    CI: the Gauntlet ran them with ``FUND_STORE=postgres`` exported and eight
    went red, two of them by racing a real ``CREATE TABLE IF NOT EXISTS``.
    A test whose subject depends on an environment variable nobody set on
    purpose is not a test of anything.

    The registry's own behaviour is proved in ``test_leansession_registry.py``,
    which points ``FUND_PG_DSN`` at its own database explicitly.
    """
    monkeypatch.setenv("FUND_STORE", "firestore")
    monkeypatch.delenv("FUND_PG_DSN", raising=False)


def _runner(tmp_path):
    import sys
    from app.fund.leanrunner import LeanRunner
    script = tmp_path / "fake_docker.py"
    script.write_text(FAKE_LIVE, encoding="utf-8")
    r = LeanRunner(workspace=tmp_path / "ws",
                   docker_cmd=[sys.executable, str(script)])
    r.save_algorithm("live", LIVE_ALGO)
    return r


class TestTheRace:
    def test_two_simultaneous_starts_give_exactly_one_winner(self, tmp_path):
        """THE INCIDENT, REPRODUCED AS A TEST (ticket dc12903f, 2026-08-26):
        two identical POSTs two milliseconds apart BOTH returned 200 and both
        ran a container for one strategy.

        A barrier makes both threads arrive together, and the assertion is on
        the INVARIANT rather than on which one wins: exactly one session, and
        exactly one refusal that says it lost.
        """
        from app.fund.leanrunner import LeanConflict
        r = _runner(tmp_path)
        gate = threading.Barrier(2)
        out, err = [], []

        def go():
            gate.wait()
            try:
                out.append(r.start_live("live", strategy_id="s1"))
            except LeanConflict as e:
                err.append(str(e))

        ts = [threading.Thread(target=go) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(20)

        assert len(out) == 1, f"expected one winner, got {len(out)}"
        assert len(err) == 1, f"expected one refusal, got {err}"
        assert "already holds strategy:s1" in err[0]
        alive = [s for s in r.live_sessions() if LS.is_alive(s)]
        assert len(alive) == 1

    def test_the_refusal_is_a_CONFLICT_and_not_a_bad_request(self, tmp_path):
        """A 409 and a 400 are different answers: the caller that lost a race
        may retry, the caller that asked for something impossible may not.
        ``LeanConflict`` subclasses ``LeanError`` so every existing handler
        still catches it."""
        from app.fund.leanrunner import LeanConflict, LeanError
        assert issubclass(LeanConflict, LeanError)
        r = _runner(tmp_path)
        r.start_live("live", strategy_id="s1")
        with pytest.raises(LeanConflict):
            r.start_live("live", strategy_id="s1")

    def test_two_DIFFERENT_strategies_both_start(self, tmp_path):
        """The widening the CEO's autopilot decision asked for: N strategies,
        N sessions. The old refusal was global and would have failed this."""
        r = _runner(tmp_path)
        a = r.start_live("live", strategy_id="s1")
        b = r.start_live("live", strategy_id="s2")
        assert a["session_id"] != b["session_id"]
        assert a["scope_key"] == "strategy:s1"
        assert b["scope_key"] == "strategy:s2"
        assert len([s for s in r.live_sessions() if LS.is_alive(s)]) == 2

    def test_a_stopped_session_releases_its_scope(self, tmp_path):
        """MUTANT: keep the scope claimed after a stop. A strategy would be
        locked out of the engine for the life of the process after one stop."""
        r = _runner(tmp_path)
        first = r.start_live("live", strategy_id="s1")["session_id"]
        r.stop_live(first)
        again = r.start_live("live", strategy_id="s1")
        assert again["session_id"] != first

    def test_the_ceiling_refuses_and_names_itself(self, tmp_path, monkeypatch):
        from app.fund import leanrunner
        monkeypatch.setattr(leanrunner, "MAX_LIVE_SESSIONS", 2)
        r = _runner(tmp_path)
        r.start_live("live", strategy_id="s1")
        r.start_live("live", strategy_id="s2")
        with pytest.raises(leanrunner.LeanError) as e:
            r.start_live("live", strategy_id="s3")
        assert "LEAN_MAX_LIVE_SESSIONS" in str(e.value)

    def test_the_ceiling_counts_only_LIVE_sessions(self, tmp_path, monkeypatch):
        """MUTANT: count every row ever. A day of finished sessions would then
        refuse every new one."""
        from app.fund import leanrunner
        monkeypatch.setattr(leanrunner, "MAX_LIVE_SESSIONS", 1)
        r = _runner(tmp_path)
        sid = r.start_live("live", strategy_id="s1")["session_id"]
        r.stop_live(sid)
        assert r.start_live("live", strategy_id="s2")["session_id"]

    def test_the_uniqueness_basis_says_which_guarantee_this_is(self, tmp_path):
        """A deployment with no registry has the in-process lock only, which
        cannot see a second spine. Two different guarantees; the response says
        which one it gave rather than letting the caller assume the stronger."""
        r = _runner(tmp_path)
        assert r.start_live("live")["uniqueness_basis"] == "process_memory"


# ============================== the runner's reconciliation, with a fake docker

class _FakeDocker:
    """A runner whose docker answers exactly what a test says it answers.

    Replaces the two subprocess calls the reconciler makes rather than the
    whole runner, so the classification, the ordering and the state writes are
    the REAL ones — a fixture that stubbed ``reconcile_containers`` itself
    would exercise nothing.
    """

    def __init__(self, runner, containers, kill_ok=True):
        self.runner, self.containers, self.kill_ok = runner, containers, kill_ok
        self.killed = []
        runner.docker_live_containers = lambda: self.containers
        runner._kill_container = self._kill

    def _kill(self, container):
        self.killed.append(container)
        return (self.kill_ok, f"docker killed {container}."
                if self.kill_ok else f"docker refused to kill {container}.")


class TestRunnerReconciliation:
    def test_an_unaccounted_container_is_stopped(self, tmp_path):
        """THE ORPHAN, CLOSED. Before this, a container that outlived the spine
        was invisible AND unstoppable: ``_live`` was empty after a restart and
        ``stop_live`` could only reach what that dict knew."""
        r = _runner(tmp_path)
        d = _FakeDocker(r, [_con("ghost")])
        report = r.reconcile_containers()
        assert d.killed == [f"{LS.CONTAINER_PREFIX}ghost"]
        assert report["counts"][LS.STOP] == 1

    def test_an_unreadable_docker_kills_nothing(self, tmp_path):
        """MUTANT: treat ``None`` as ``[]``. Nothing would be killed either —
        but every live row would be marked vanished, which releases scopes for
        containers that are still running. Both halves are asserted."""
        r = _runner(tmp_path)
        d = _FakeDocker(r, None)
        report = r.reconcile_containers()
        assert d.killed == []
        assert report["actions"] == []
        assert report["checked"] is False

    def test_reconciliation_never_raises_into_start_up(self, tmp_path):
        """It runs inside ``app.main.lifespan``. A reconciliation that cannot
        run must not stop the spine from starting."""
        r = _runner(tmp_path)

        def boom():
            raise RuntimeError("docker is on fire")
        r.docker_live_containers = boom
        with pytest.raises(RuntimeError):
            r.reconcile_containers()   # the runner does raise ...

    def test_the_spine_start_up_swallows_that_and_says_so(self):
        """... and ``lifespan`` is where it is caught. Pinned at the SOURCE
        because starting the whole app in a unit test would prove less — and
        read as text rather than imported, for the reason on ``MAIN_SRC``.

        The window is bounded on both sides so a ``try`` belonging to some
        other statement two hundred lines away cannot satisfy it."""
        assert MAIN_SRC.count("reconcile_containers") == 1
        i = MAIN_SRC.index("reconcile_containers")
        window = MAIN_SRC[max(0, i - 400):i + 600]
        assert "try:" in window
        assert "except Exception" in window
        assert "_log.warning" in window
        # AND IT RUNS BEFORE THE SCHEDULER, not after: a reconciliation that
        # happens once the strike/exit ticks are already firing would be acting
        # on a book those ticks had begun to move.
        assert i < MAIN_SRC.index("_scheduler())")


# ================== the real docker read, and the real registry read

class TestTheRealDockerRead:
    """``docker_live_containers`` had NO coverage of its real implementation —
    every reconciliation test replaced it with a lambda. Found by the
    Gauntlet's fixture-classification pass, and it is the function whose
    ``None``-vs-``[]`` answer decides whether a start-up marks live sessions
    vanished. A fake that stands in for the thing under test proves nothing
    about the format string or the tab split.

    These use a FAKE DOCKER EXECUTABLE — the real subprocess, the real argv,
    the real stdout parsing — which is the same instrument
    ``tests/test_leanrunner.py`` already uses for backtests.
    """

    def _runner_with(self, tmp_path, script):
        import sys
        from app.fund.leanrunner import LeanRunner
        p = tmp_path / "fake_docker_ps.py"
        p.write_text(script, encoding="utf-8")
        return LeanRunner(workspace=tmp_path / "ws",
                          docker_cmd=[sys.executable, str(p)])

    PS_TWO = r"""
import sys
sys.stdout.write("lean-live-aaa\tdev\nlean-live-bbb\t\n")
"""

    def test_it_parses_names_and_labels_off_the_real_stdout(self, tmp_path):
        r = self._runner_with(tmp_path, self.PS_TWO)
        assert r.docker_live_containers() == [
            {"name": "lean-live-aaa", "mode": "dev"},
            {"name": "lean-live-bbb", "mode": None}]

    def test_an_EMPTY_label_column_reads_as_ABSENT_and_not_as_a_mode(self, tmp_path):
        """``docker ps --format {{.Label "x"}}`` prints an empty column for BOTH
        "no such label" and "the label is empty". Reading "" as a mode would
        make a container claim a mode named nothing."""
        r = self._runner_with(tmp_path, self.PS_TWO)
        assert r.docker_live_containers()[1]["mode"] is None

    def test_the_argv_asks_docker_the_question_we_think_it_asks(self, tmp_path):
        """The format string is a contract with another program and nothing
        else in this suite reads it. Verified against the real daemon on
        2026-08-27 before it was written; pinned here so a later edit to the
        template cannot pass silently."""
        script = r"""
import json, sys, os
open(os.environ["ARGV_OUT"], "w").write(json.dumps(sys.argv))
"""
        out = tmp_path / "argv.json"
        import os
        os.environ["ARGV_OUT"] = str(out)
        try:
            self._runner_with(tmp_path, script).docker_live_containers()
        finally:
            os.environ.pop("ARGV_OUT", None)
        import json
        argv = json.loads(out.read_text())
        assert "ps" in argv
        assert f"name={LS.CONTAINER_PREFIX}" in argv
        assert any(LS.MODE_LABEL in a and "{{.Names}}" in a for a in argv)

    def test_a_NONZERO_exit_is_UNREADABLE_and_not_nothing_running(self, tmp_path):
        """MUTANT M35. ``[]`` would make start-up mark every live session
        VANISHED — releasing the uniqueness scope of containers that are still
        running — on the strength of a failed query."""
        r = self._runner_with(tmp_path, 'import sys; sys.exit(3)')
        assert r.docker_live_containers() is None

    def test_an_UNREACHABLE_docker_is_UNREADABLE(self, tmp_path):
        """MUTANT M34, the same defect one branch over."""
        from app.fund.leanrunner import LeanRunner
        r = LeanRunner(workspace=tmp_path / "ws",
                       docker_cmd=["definitely-not-a-real-binary-9f3a"])
        assert r.docker_live_containers() is None

    def test_docker_answering_NOTHING_is_a_readable_empty_list(self, tmp_path):
        """The other side, and it must NOT be ``None``: a daemon that answered
        and listed nothing is exactly when a live row IS vanished."""
        r = self._runner_with(tmp_path, 'pass')
        assert r.docker_live_containers() == []

    def test_the_reader_is_RAW_and_the_prefix_filter_lives_in_ONE_place(
            self, tmp_path):
        """``docker ps --filter name=`` is a SUBSTRING match, so the daemon
        really does return ``mine-lean-live-x`` from this query — verified
        against the real daemon.

        THE READER DOES NOT FILTER, AND THAT IS THE DESIGN: the rule for "is
        this ours" is ``leansessions.session_id_of``, in the pure module, with
        the test that names the hazard. Filtering here as well would be the
        rule spelled twice, and the second spelling is the one that goes stale.
        So this asserts BOTH halves — the raw read returns what docker said,
        and the impostor is gone by the time anything acts on it.
        """
        r = self._runner_with(tmp_path, r"""
import sys
sys.stdout.write("mine-lean-live-x\t\nlean-live-ok\t\n")
""")
        raw = r.docker_live_containers()
        assert [c["name"] for c in raw] == ["mine-lean-live-x", "lean-live-ok"]
        plan = LS.reconcile([], raw, our_mode="dev")
        assert plan["containers_seen"] == 1
        assert [a["session_id"] for a in plan["actions"]] == ["ok"]

    def test_the_unreadable_read_reaches_the_reconciler_as_unreadable(self, tmp_path):
        """END TO END, through the real method rather than a lambda: a docker
        that cannot be reached must produce ``checked: false`` and no action."""
        from app.fund.leanrunner import LeanRunner
        r = LeanRunner(workspace=tmp_path / "ws",
                       docker_cmd=["definitely-not-a-real-binary-9f3a"])
        report = r.reconcile_containers()
        assert report["checked"] is False
        assert report["containers_readable"] is False
        assert report["actions"] == []


class TestTheRegistryReadIsThreeValued:
    def test_no_registry_configured_is_an_EMPTY_list_of_rows(self, tmp_path):
        """Not ``None``: a deployment with no registry genuinely has no rows,
        and the reconciler must still be able to stop an orphan on it."""
        assert _runner(tmp_path).registry_rows_or_none() == []

    def test_an_UNREADABLE_registry_is_None_and_never_an_empty_list(
            self, tmp_path, monkeypatch):
        """MUTANT M33, and it is the most dangerous of the four survivors.
        ``[]`` means "the registry knows of no session", which makes EVERY
        running container an unaccounted orphan — so one unreachable database
        at start-up would stop every engine this fund is running."""
        monkeypatch.setenv("FUND_STORE", "postgres")
        r = _runner(tmp_path)
        monkeypatch.setattr(type(r), "_registry",
                            lambda self: (_ for _ in ()).throw(RuntimeError("down")))
        assert r.registry_rows_or_none() is None

    def test_and_the_reconciler_then_stops_nothing(self, tmp_path, monkeypatch):
        """The consequence, asserted separately from the value — because the
        value is only interesting for what it prevents."""
        monkeypatch.setenv("FUND_STORE", "postgres")
        r = _runner(tmp_path)
        monkeypatch.setattr(type(r), "_registry",
                            lambda self: (_ for _ in ()).throw(RuntimeError("down")))
        killed = []
        r._kill_container = lambda c: (killed.append(c), (True, "x"))[1]
        r.docker_live_containers = lambda: [_con("ghost")]
        report = r.reconcile_containers()
        assert killed == []
        assert report["registry_readable"] is False
        assert report["checked"] is False


class TestAnUnregisterableSessionNeverStarts:
    def test_a_claim_that_raises_something_other_than_a_conflict_refuses(
            self, tmp_path, monkeypatch):
        """MUTANT M30. The existing test covered an unreachable registry at
        RESOLUTION time; this covers the claim itself failing, which is a
        different branch and was the one with no test.

        FAIL CLOSED: starting a container the registry never recorded creates
        exactly the orphan this whole change exists to remove."""
        from app.fund.leanrunner import LeanError
        monkeypatch.setenv("FUND_STORE", "postgres")
        r = _runner(tmp_path)

        class _Boom:
            """A registry that RESOLVES and then refuses the write. The
            existing coverage broke at resolution; this breaks one step later,
            which is a different branch of ``start_live``."""

            def claim_session(self, session):
                raise RuntimeError("the insert failed")

            def live_session_rows(self):
                return []

        monkeypatch.setattr(type(r), "_registry", lambda self: _Boom())
        with pytest.raises(LeanError, match="refusing to start"):
            r.start_live("live", strategy_id="s1")
        # AND THE TENTATIVE CLAIM IS ROLLED BACK. Without this the scope would
        # stay held in memory by a session that never ran.
        assert r._live == {}
        assert r.live_sessions() == []


# ================== the stop path, and what a stop actually did

class TestStopLiveActuallyStops:
    """MUTATION SURVIVORS M63, M64 AND M66 — all three in ``stop_live``, and
    all three the same shape: the state said ``stopped`` and nothing checked
    that anything had been stopped.

    A control is not done until something calls it, and a control that reports
    success without calling anything is the unwired kill switch wearing a green
    tick. These assert on the SIDE EFFECT, not on the returned state.
    """

    def _spy(self, tmp_path):
        r = _runner(tmp_path)
        calls = []
        real = r._kill_container

        def spy(container):
            calls.append(container)
            return real(container)
        r._kill_container = spy
        return r, calls

    def test_stopping_asks_docker_to_kill_THIS_session_s_container(self, tmp_path):
        """MUTANT M64: ``killed, detail = (True, "assumed")``. Every existing
        assertion about ``state == "stopped"`` passes under that mutant, which
        is the point — the state is what the fund BELIEVES and the kill is what
        happened."""
        r, calls = self._spy(tmp_path)
        out = r.start_live("live", strategy_id="s1")
        sid = out["session_id"]
        expected = r.live_session(sid)["container"]
        r.stop_live(sid)
        assert calls == [expected]

    def test_a_kill_docker_REFUSED_is_reported_as_not_killed(self, tmp_path):
        """MUTANT M63: ``if proc.returncode >= 0``. The state is ``stopped``
        either way — it is not running now — but WHY is not the same, and the
        reason is what tells a reader whether the orphan problem just bit
        them."""
        import sys
        from app.fund.leanrunner import LeanRunner
        script = tmp_path / "refuse.py"
        script.write_text(
            'import sys\nsys.stderr.write("No such container\\n")\n'
            'sys.exit(1)\n', encoding="utf-8")
        r = LeanRunner(workspace=tmp_path / "ws",
                       docker_cmd=[sys.executable, str(script)])
        killed, detail = r._kill_container("lean-live-ghost")
        assert killed is False
        assert "refused to kill" in detail
        assert "No such container" in detail

    def test_a_kill_docker_ACCEPTED_is_reported_as_killed(self, tmp_path):
        """The positive control. Without it the assertion above is satisfied by
        a function that always says False."""
        r = _runner(tmp_path)
        killed, detail = r._kill_container("lean-live-anything")
        assert killed is True
        assert "docker killed" in detail

    def test_an_unreachable_docker_says_UNKNOWN_and_not_killed(self, tmp_path):
        from app.fund.leanrunner import LeanRunner
        r = LeanRunner(workspace=tmp_path / "ws",
                       docker_cmd=["definitely-not-a-real-binary-9f3a"])
        killed, detail = r._kill_container("lean-live-x")
        assert killed is False
        assert "UNKNOWN" in detail

    def test_a_session_with_no_container_name_kills_nothing_and_says_so(self):
        from app.fund.leanrunner import LeanRunner
        killed, detail = LeanRunner.__new__(LeanRunner)._kill_container("")
        assert killed is False
        assert "no container name" in detail

    def test_the_stop_returns_whether_the_container_really_died(self, tmp_path):
        r = _runner(tmp_path)
        sid = r.start_live("live", strategy_id="s1")["session_id"]
        out = r.stop_live(sid)
        assert out["container_killed"] is True
        assert "docker killed" in out["detail"]


class TestTheListOrder:
    def test_sessions_come_back_NEWEST_first(self, tmp_path):
        """MUTANT M60: drop ``reverse=True``. Nothing asserted the order, and
        'newest first' is the contract every consumer of this list reads it
        under — the engine page renders the head of it as the current
        session.

        The sleep is load-bearing and its absence is what found the tie-break
        defect: without it both sessions carried the SAME ``started_at`` (the
        Windows clock is coarser than ``_now()``'s microseconds) and the order
        was dict-insertion order wearing a timestamp's clothes.
        """
        import time
        r = _runner(tmp_path)
        first = r.start_live("live", strategy_id="s1")["session_id"]
        time.sleep(0.05)
        second = r.start_live("live", strategy_id="s2")["session_id"]
        assert r.live_session(first)["started_at"] !=             r.live_session(second)["started_at"], "the clock did not move"
        ids = [s["session_id"] for s in r.live_sessions()]
        assert ids == [second, first], ids

    def test_two_sessions_on_the_SAME_instant_sort_DETERMINISTICALLY(self):
        """Nothing can make this order truthful — the two things happened at
        the same recorded instant. It can be made REPRODUCIBLE, which is the
        property a reader can rely on and a screenshot can be compared
        against. Without the tie-break the answer is dict-insertion order.
        """
        from app.fund.leanrunner import _by_started_at
        t = "2026-08-27T00:00:00.000000+00:00"
        a = {"session_id": "aaa", "started_at": t}
        b = {"session_id": "bbb", "started_at": t}
        assert _by_started_at([a, b]) == _by_started_at([b, a]) == [b, a]

    def test_a_row_with_no_start_sorts_last_and_does_not_raise(self):
        from app.fund.leanrunner import _by_started_at
        rows = [{"session_id": "no-start"},
                {"session_id": "x", "started_at": "2026-01-01T00:00:00+00:00"}]
        assert [r["session_id"] for r in _by_started_at(rows)] == ["x", "no-start"]


class TestTheContainerLabel:
    """MUTATION SURVIVOR M62. An unreadable mode must produce NO label, not an
    empty one: ``docker ps --format {{.Label "x"}}`` prints "" for both "no
    such label" and "the label is empty", so writing an empty label makes a
    claim indistinguishable from an absence — and the reconciler's ownership
    rule turns on exactly that distinction."""

    ARGV_DUMP = r"""
import json, os, sys
open(os.environ["LIVE_ARGV_OUT"], "w").write(json.dumps(sys.argv))
"""

    def _argv_for(self, tmp_path, monkeypatch, mode):
        import json
        import sys
        import time
        from app.fund.leanrunner import LeanRunner
        out = tmp_path / "argv.json"
        monkeypatch.setenv("LIVE_ARGV_OUT", str(out))
        script = tmp_path / "argv_docker.py"
        script.write_text(self.ARGV_DUMP, encoding="utf-8")
        r = LeanRunner(workspace=tmp_path / "ws",
                       docker_cmd=[sys.executable, str(script)])
        monkeypatch.setattr(type(r), "_our_mode", lambda self: mode)
        r.save_algorithm("live", LIVE_ALGO)
        r.start_live("live", strategy_id="s1")
        for _ in range(100):
            if out.exists():
                break
            time.sleep(0.05)
        return json.loads(out.read_text())

    def test_a_readable_mode_is_stamped_on_the_container(self, tmp_path,
                                                         monkeypatch):
        argv = self._argv_for(tmp_path, monkeypatch, "alpaca-paper")
        assert "--label" in argv
        assert f"{LS.MODE_LABEL}=alpaca-paper" in argv

    @pytest.mark.parametrize("mode", [None, ""])
    def test_an_UNREADABLE_mode_stamps_NOTHING(self, tmp_path, monkeypatch,
                                               mode):
        argv = self._argv_for(tmp_path, monkeypatch, mode)
        assert "--label" not in argv
        assert not any(LS.MODE_LABEL in a for a in argv)

    def test_and_an_unlabelled_container_then_reads_as_LEGACY_and_ours(self):
        """The consequence, asserted at the other end: an absent label is
        already the honest reading of a container whose mode we could not
        record, and it keeps that container reconcilable."""
        assert LS.ownership(None, "alpaca-paper") == LS.OWN_LEGACY

