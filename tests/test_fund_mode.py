"""The fund's mode: two dimensions, three members, and nothing defaulted.

Every test here names the incident it guards against. The three that produced
this module:

  * **2026-08-21, the ledger flag that moved the venue.** A DURABILITY fix
    silently re-routed order EXECUTION to a real Alpaca account, because
    ``USE_FAKE_FIRESTORE`` named the ledger and selected the venue.
  * **2026-08-21, the store that relocated itself.** ``FUND_STORE`` defaulted
    to ``"firestore"`` and a restart that did not carry the shell variable
    moved the whole fund off Postgres. Caught by a 503 on an unrelated write.
  * **2026-08-21, order 17d64dcd.** The CEO-authorised experimental deployment
    filled on the PAPER connector wearing an ``alpaca`` label, was marked done,
    and produced zero cost information — the whole point of it was the fill.
"""

from __future__ import annotations

import json
import os

import pytest

from app.fund import mode as m


# --- dimension separation ----------------------------------------------------
class TestTwoDimensions:
    def test_every_mode_names_both_a_venue_and_a_store(self):
        """The original sin was ONE flag deciding both. If a mode can be
        constructed without saying where its events land, the tangle is back."""
        for mode in m.FundMode:
            spec = m.MODES[mode]
            assert spec.venue_kind is not None
            assert spec.pg_database, f"{mode} declares no store"

    def test_the_three_modes_use_three_different_stores(self):
        """Paper NAV and real NAV must never be foldable together. Not
        'distinguished by a tag on a row' — a different database."""
        dbs = [m.MODES[mode].pg_database for mode in m.FundMode]
        assert len(set(dbs)) == 3, dbs

    def test_all_three_modes_exist_in_the_enum(self):
        """A two-mode design encodes assumptions that break when the third
        arrives. Built now, wired later."""
        assert [x.value for x in m.FundMode] == [
            "test", "alpaca-paper", "alpaca-prod"]
        assert m.MODES[m.FundMode.ALPACA_PROD].wired is False
        assert m.MODES[m.FundMode.TEST].wired is True
        assert m.MODES[m.FundMode.ALPACA_PAPER].wired is True

    def test_only_prod_is_real_money(self):
        assert m.MODES[m.FundMode.ALPACA_PROD].real_money is True
        assert m.MODES[m.FundMode.TEST].real_money is False
        assert m.MODES[m.FundMode.ALPACA_PAPER].real_money is False

    def test_alpaca_paper_is_a_real_broker_but_not_real_money(self):
        """The distinction the old 'orders_are_real' boolean could not make:
        an order queued at Alpaca's paper account really left the building."""
        spec = m.MODES[m.FundMode.ALPACA_PAPER]
        assert spec.real_broker is True and spec.real_money is False

    def test_test_mode_persists_it_does_not_evaporate(self):
        """ISOLATED, NOT EPHEMERAL. USE_FAKE_FIRESTORE isolated by making the
        record disposable — 552 events lived in memory while the status
        endpoint reported successful mirroring hourly. Isolation and
        durability are orthogonal, and a test mode that writes nowhere makes
        the replay engine measure nothing twice."""
        spec = m.MODES[m.FundMode.TEST]
        assert spec.pg_database == "krypton_fund_dev"
        assert "memory" not in spec.pg_database


# --- UNSET MUST FAIL ---------------------------------------------------------
class TestUnsetFails:
    ENV_ONLY = {"FUND_MODE_FILE": "/nonexistent/.fund_mode"}

    def test_no_declaration_raises(self):
        """No default, no fallback. A fund that cannot determine its own mode
        must refuse to construct an order path at all."""
        with pytest.raises(m.ModeUnset):
            m.resolve(env=dict(self.ENV_ONLY))

    def test_an_empty_string_is_not_a_declaration(self):
        with pytest.raises(m.ModeUnset):
            m.resolve(env={**self.ENV_ONLY, "FUND_MODE": "   "})

    def test_an_unknown_mode_raises_rather_than_falling_back(self):
        with pytest.raises(m.ModeUnknown):
            m.resolve(env={**self.ENV_ONLY, "FUND_MODE": "paper"})

    def test_a_typo_does_not_silently_become_test_mode(self):
        """The nearest neighbour must not win. 'tests' is not 'test'."""
        with pytest.raises(m.ModeUnknown):
            m.resolve(env={**self.ENV_ONLY, "FUND_MODE": "tests"})

    def test_env_and_file_disagreeing_refuses_rather_than_picking(self, tmp_path):
        """A precedence rule is exactly how the durability fix moved the venue:
        one authority quietly won and the operator who set the loser was never
        told. Refuse instead."""
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "alpaca-paper"}), encoding="utf-8")
        with pytest.raises(m.ModeConflict):
            m.resolve(env={"FUND_MODE": "test", "FUND_MODE_FILE": str(f)})

    def test_env_and_file_agreeing_is_fine(self, tmp_path):
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "test"}), encoding="utf-8")
        spec = m.resolve(env={"FUND_MODE": "test", "FUND_MODE_FILE": str(f)})
        assert spec.mode is m.FundMode.TEST

    def test_the_file_alone_is_a_declaration(self, tmp_path):
        """Because that is what the switch writes, and a restart must not
        quietly revert a deliberate switch."""
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "alpaca-paper", "set_by": "neelesh"}),
                     encoding="utf-8")
        spec = m.resolve(env={"FUND_MODE_FILE": str(f)})
        assert spec.mode is m.FundMode.ALPACA_PAPER

    def test_an_unreadable_mode_file_is_not_no_mode_file(self, tmp_path):
        """Unreadable is not unchanged. A corrupt file must not degrade to
        'nobody declared anything' and then to a default."""
        f = tmp_path / ".fund_mode"
        f.write_text("{not json", encoding="utf-8")
        with pytest.raises(Exception) as e:
            m.resolve(env={"FUND_MODE_FILE": str(f)})
        assert not isinstance(e.value, m.ModeUnset)

    def test_a_mode_file_with_no_mode_key_raises(self, tmp_path):
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"set_by": "someone"}), encoding="utf-8")
        with pytest.raises(m.ModeUnknown):
            m.resolve(env={"FUND_MODE_FILE": str(f)})


class TestStoreBackendUnsetFails:
    def test_unset_fund_store_raises(self, monkeypatch):
        """2026-08-21: FUND_STORE defaulted to 'firestore' and a spine restart
        that did not carry the shell variable moved the entire fund off
        Postgres. A default that relocates the ledger is a trapdoor."""
        from app.fund.events import StoreUnset, store_backend

        monkeypatch.delenv("FUND_STORE", raising=False)
        with pytest.raises(StoreUnset):
            store_backend()

    def test_an_unknown_backend_raises(self, monkeypatch):
        from app.fund.events import StoreUnset, store_backend

        monkeypatch.setenv("FUND_STORE", "sqlite")
        with pytest.raises(StoreUnset):
            store_backend()

    def test_a_valid_backend_still_works(self, monkeypatch):
        from app.fund.events import store_backend

        monkeypatch.setenv("FUND_STORE", "Postgres")
        assert store_backend() == "postgres"


# --- alpaca-prod is structurally unreachable ---------------------------------
class TestProdIsLocked:
    def test_selecting_prod_raises(self):
        with pytest.raises(m.ProdLocked):
            m.resolve(env={"FUND_MODE": "alpaca-prod",
                           "FUND_MODE_FILE": "/nonexistent/.fund_mode"})

    def test_the_code_lock_is_closed(self):
        """A code-level gate PLUS a written precondition list — the CEO's own
        shape. If this constant is ever True in a diff, the reviewer must be
        looking at a versioned change with a name on it."""
        assert m.PROD_UNLOCKED is False

    def test_all_five_ceo_preconditions_are_present(self):
        keys = [p.key for p in m.PROD_PRECONDITIONS]
        assert keys == ["controls_fired", "book_venue_reconciled",
                        "exit_sign_fixed", "kill_switch_wired_and_tested",
                        "informative_fills"]

    def test_an_unevaluable_precondition_reports_unchecked_not_met(self):
        """The register's own founding defect, one level up: 17 of 19
        registered triggers were free text no code evaluated while the
        endpoint reported ``triggers_unchecked: []``. Absence rendered as
        zero. Here an unchecked precondition BLOCKS, so the honest answer and
        the safe answer are the same answer."""
        report = m.prod_gate_report(store=None)
        statuses = {c["key"]: c["status"] for c in report["preconditions"]}
        assert statuses["exit_sign_fixed"] == "unchecked"
        assert statuses["kill_switch_wired_and_tested"] == "unchecked"
        assert statuses["book_venue_reconciled"] == "unchecked"
        # And unchecked is counted as blocking, never as met.
        assert report["n_met"] == 0
        assert report["n_blocking"] == len(m.PROD_PRECONDITIONS)
        assert report["reachable"] is False

    def test_an_unreadable_store_makes_a_precondition_unchecked_not_met(self):
        class Exploding:
            def stream(self, *a, **k):
                raise ConnectionError("postgres down")

        report = m.prod_gate_report(store=Exploding())
        got = {c["key"]: c for c in report["preconditions"]}
        assert got["controls_fired"]["status"] == "unchecked"
        assert "ConnectionError" in got["controls_fired"]["detail"]

    def test_controls_fired_is_unmet_on_a_log_that_never_saw_them(self, wire):
        ok, detail = m._controls_have_fired(wire.store)
        assert ok is False
        assert "never observed" in detail

    def test_reachable_requires_both_locks(self, monkeypatch):
        """Even with every precondition met, the code lock alone keeps it
        shut. Two independent locks, both must open."""
        met = [m.Precondition(key="x", text="t", evaluator=lambda s: (True, "ok"))]
        monkeypatch.setattr(m, "PROD_PRECONDITIONS", tuple(met))
        assert m.prod_gate_report(store=object())["reachable"] is False


# --- one process, one store --------------------------------------------------
class TestStoresAreNeverJoined:
    def test_activating_a_second_different_mode_raises(self):
        m.activate(m.MODES[m.FundMode.TEST])
        with pytest.raises(m.StoreCrossing):
            m.activate(m.MODES[m.FundMode.ALPACA_PAPER])

    def test_reactivating_the_same_mode_is_fine(self):
        m.activate(m.MODES[m.FundMode.TEST])
        assert m.activate(m.MODES[m.FundMode.TEST]).mode is m.FundMode.TEST

    def test_the_switch_path_may_force_it(self):
        """Forcing is what the CEO's toggle does, AFTER it has established
        that nothing is in flight. The guard exists to stop an accident, not
        a decision."""
        m.activate(m.MODES[m.FundMode.TEST])
        assert m.activate(m.MODES[m.FundMode.ALPACA_PAPER], force=True)

    def test_no_mode_is_active_by_default(self):
        """current() answers None rather than a guess. A hand-built pipeline
        in a unit test genuinely has no mode."""
        assert m.current() is None
        assert m.current_label() is None


class TestDsnRouting:
    BASE = "postgresql://krypton:krypton_local@127.0.0.1:5433/krypton_fund"

    def test_each_wired_mode_gets_its_own_database_on_the_same_server(self):
        """Only the two WIRED modes. pg_dsn_for refuses to build a connection
        string to the prod ledger while the gate is shut (K5) — the prod
        database's NAME is still readable, on the spec and in the report, but
        a DSN is the act of preparing to open it."""
        got = {mode.value: m.pg_dsn_for(m.MODES[mode], self.BASE)
               for mode in m.FundMode if m.MODES[mode].wired}
        assert got["test"].endswith("/krypton_fund_dev")
        assert got["alpaca-paper"].endswith("/krypton_fund")
        assert len(set(got.values())) == 2
        # The three names are still three, read off the specs rather than out
        # of a DSN — that separation is the whole point.
        assert len({m.MODES[mode].pg_database for mode in m.FundMode}) == 3
        assert m.MODES[m.FundMode.ALPACA_PROD].pg_database == "krypton_fund_prod"

    def test_credentials_host_and_port_are_carried_through(self):
        out = m.pg_dsn_for(m.MODES[m.FundMode.TEST], self.BASE)
        assert out.startswith("postgresql://krypton:krypton_local@127.0.0.1:5433/")

    def test_query_parameters_survive(self):
        out = m.pg_dsn_for(m.MODES[m.FundMode.TEST], self.BASE + "?sslmode=require")
        assert out.endswith("/krypton_fund_dev?sslmode=require")

    def test_a_dsn_with_no_database_raises_rather_than_guessing(self):
        with pytest.raises(m.ModeError):
            m.pg_dsn_for(m.MODES[m.FundMode.TEST], "postgresql:")


# --- a mock venue must be INCAPABLE, not merely discouraged ------------------
class TestVenueIncapability:
    class Fake:
        def __init__(self, name):
            self.name = name

    def test_test_mode_refuses_an_alpaca_connector(self):
        with pytest.raises(m.VenueNotPermitted):
            m.assert_connector_permitted(m.MODES[m.FundMode.TEST],
                                         self.Fake("alpaca"))

    def test_alpaca_paper_refuses_a_paper_connector(self):
        """The other direction matters just as much: a spine that believes it
        is on the broker while a simulator answers is the sham the CEO named
        ('every order needs to route to alpaca paper account no sham')."""
        with pytest.raises(m.VenueNotPermitted):
            m.assert_connector_permitted(m.MODES[m.FundMode.ALPACA_PAPER],
                                         self.Fake("paper"))

    def test_a_connector_that_will_not_name_itself_is_refused(self):
        class Anonymous:
            pass

        with pytest.raises(m.VenueNotPermitted):
            m.assert_connector_permitted(m.MODES[m.FundMode.TEST], Anonymous())

    def test_the_right_connector_passes(self):
        from app.fund.connectors.alpaca import AlpacaConnector

        m.assert_connector_permitted(m.MODES[m.FundMode.TEST], self.Fake("paper"))
        m.assert_connector_permitted(m.MODES[m.FundMode.ALPACA_PAPER],
                                     AlpacaConnector(paper=True))

    def test_a_fake_declaring_the_broker_name_is_REFUSED_for_a_real_venue(self):
        """Adversary review of builder D11, K5, second half.

        The check above this one is a string comparison against an attribute
        the object declares about ITSELF, and the adversary handed it a bare
        class with `name = "alpaca"` and was ACCEPTED. A guard written to stop
        a self-declared label from lying was deciding on a self-declared label.
        For the modes that reach a real broker the class is now checked, and
        nothing a fake declares can satisfy isinstance.
        """
        with pytest.raises(m.VenueNotPermitted) as e:
            m.assert_connector_permitted(m.MODES[m.FundMode.ALPACA_PAPER],
                                         self.Fake("alpaca"))
        assert "A name is a claim; the class is a fact" in str(e.value)

    def test_the_simulated_venue_still_accepts_a_double(self):
        """The asymmetry is deliberate: strictness where the money is. Test
        mode is where substituting a double is legitimate, and 'paper' cannot
        move money by construction. If this ever fails, the class check has
        been applied too widely and every fake pipeline in the suite pays."""
        m.assert_connector_permitted(m.MODES[m.FundMode.TEST],
                                     self.Fake("paper"))


class TestNoSilentSimulator:
    """PART A of desk d8f2a2ff, and the sharpest half.

    The old ternary reached PaperConnector on the ``else`` of
    ``if os.getenv("ALPACA_API_KEY")``. An absent, mistyped or restart-dropped
    key sent orders to a simulator with no error and no log line.
    """

    def test_an_alpaca_mode_without_credentials_refuses_to_build(self, monkeypatch):
        from app.fund.venue import VenueUnavailable, build_connector

        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        with pytest.raises(VenueUnavailable) as e:
            build_connector(m.MODES[m.FundMode.ALPACA_PAPER])
        assert "Refusing to construct an order path" in str(e.value)

    def test_half_a_credential_is_not_a_credential(self, monkeypatch):
        from app.fund.venue import VenueUnavailable, build_connector

        monkeypatch.setenv("ALPACA_API_KEY", "key-only")
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        with pytest.raises(VenueUnavailable):
            build_connector(m.MODES[m.FundMode.ALPACA_PAPER])

    def test_test_mode_builds_the_simulator_and_only_that(self, monkeypatch):
        """And it does so REGARDLESS of the Alpaca key being present, which is
        the branch the old ternary got wrong in the other direction."""
        from app.fund.venue import build_connector

        monkeypatch.setenv("ALPACA_API_KEY", "present")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "present")
        conn = build_connector(m.MODES[m.FundMode.TEST])
        assert conn.name == "paper"

    def test_build_connector_ACTUALLY_RUNS_the_permission_check(self, monkeypatch):
        """The check existing is not the check running. A spec that permits
        only 'alpaca' must reject the simulator build_connector produces —
        which can only happen if build_connector calls the guard."""
        import dataclasses

        from app.fund.venue import build_connector

        rigged = dataclasses.replace(m.MODES[m.FundMode.TEST],
                                     permitted_connectors=("alpaca",))
        with pytest.raises(m.VenueNotPermitted):
            build_connector(rigged)

    def test_paper_vs_live_comes_from_the_mode_not_ALPACA_PAPER(self, monkeypatch):
        """ALPACA_PAPER was a fourth accidental switch: it decided real money
        while living beside a CORS list, tied to nothing."""
        from app.fund.venue import build_connector

        monkeypatch.setenv("ALPACA_API_KEY", "k")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
        monkeypatch.setenv("ALPACA_PAPER", "false")     # would have meant LIVE
        conn = build_connector(m.MODES[m.FundMode.ALPACA_PAPER])
        assert conn._paper is True, (
            "the mode says alpaca-paper; an environment variable must not be "
            "able to point that at the live account")


class TestReport:
    def test_the_report_names_the_active_mode_and_both_dimensions(self):
        m.activate(m.MODES[m.FundMode.TEST])
        r = m.report(store=None, env={"FUND_MODE_FILE": "/nonexistent/x"})
        assert r["active"]["mode"] == "test"
        assert r["active"]["venue"]["label"] == "paper"
        assert r["active"]["store"]["pg_database"] == "krypton_fund_dev"
        assert len(r["modes"]) == 3
        assert r["prod_gate"]["reachable"] is False

    def test_an_undeclared_mode_reports_null_not_a_default(self):
        r = m.report(store=None, env={"FUND_MODE_FILE": "/nonexistent/x"})
        assert r["active"] is None

    def test_an_unreadable_mode_file_is_reported_not_swallowed(self, tmp_path):
        f = tmp_path / ".fund_mode"
        f.write_text("{not json", encoding="utf-8")
        r = m.report(store=None, env={"FUND_MODE_FILE": str(f)})
        assert r["declared"]["file"] is None
        assert r["declared"]["file_error"]


class TestModeFile:
    def test_the_file_records_who_when_and_why(self, tmp_path):
        env = {"FUND_MODE_FILE": str(tmp_path / ".fund_mode")}
        written = m.write_mode_file(m.FundMode.TEST, actor="neelesh",
                                   reason="stress test", env=env)
        assert written["mode"] == "test"
        assert written["set_by"] == "neelesh"
        assert written["reason"] == "stress test"
        assert written["set_at"]
        assert m.read_mode_file(env)["mode"] == "test"

    def test_writing_is_atomic_and_leaves_no_temp_behind(self, tmp_path):
        env = {"FUND_MODE_FILE": str(tmp_path / ".fund_mode")}
        m.write_mode_file(m.FundMode.TEST, "neelesh", "r", env=env)
        assert sorted(p.name for p in tmp_path.iterdir()) == [".fund_mode"]


# --- K5: THE TWO LOCKS ARE THE LOCKS -----------------------------------------
class TestProdGatesAreWiredNotDescribed:
    """Adversary review of builder D11, 2026-08-22, finding K5.

    v1 documented two independent locks — the ``PROD_UNLOCKED`` constant and
    the five CEO preconditions — and wired NEITHER. ``resolve()`` read only its
    own ``allow_prod`` argument; the constant and the preconditions decided
    nothing, and ``prod_gate_report()["reachable"]`` computed from a line the
    refusal never consulted, so the report could read ``True`` while the code
    refused. The adversary's probe BUILT a live ``AlpacaConnector(paper=False)``
    off the prod spec, because ``build_connector`` never asked. Prod was
    unreachable by ABSENCE OF A CALLER — ``allow_prod`` had zero callers in the
    whole repository — which is the unwired-kill-switch pattern with a report
    on top of it.

    Every surface that can move real money is probed here. A test that only
    checked ``resolve()`` would have passed against v1's successor if someone
    re-added a bypass to any of the other four.
    """

    PROD = None  # set in setup; the spec is a plain dict entry and readable

    def setup_method(self):
        self.PROD = m.MODES[m.FundMode.ALPACA_PROD]

    def test_A_resolve_refuses(self):
        with pytest.raises(m.ProdLocked):
            m.resolve(env={"FUND_MODE": "alpaca-prod",
                           "FUND_MODE_FILE": "/nonexistent/.fund_mode"})

    def test_B_resolve_has_no_bypass_argument_at_all(self):
        """Deleted rather than made private. It had zero callers, so nothing
        needed it and its only function was to be the hole."""
        import inspect
        params = inspect.signature(m.resolve).parameters
        assert list(params) == ["env"], (
            f"resolve() grew a parameter: {list(params)} — if it is a prod "
            f"bypass, K5 has returned")

    def test_C_activate_refuses(self):
        """NOT redundant with resolve(): the mode-switch endpoint passes
        MODES[target] to activate() directly and never calls resolve()."""
        with pytest.raises(m.ProdLocked):
            m.activate(self.PROD)

    def test_D_activate_refuses_even_with_force(self):
        """``force=True`` skips the store-crossing check. It has never been
        permitted to skip this one, and the switch path passes it."""
        with pytest.raises(m.ProdLocked):
            m.activate(self.PROD, force=True)

    def test_E_pg_dsn_for_refuses(self):
        with pytest.raises(m.ProdLocked):
            m.pg_dsn_for(self.PROD,
                         "postgresql://u:p@127.0.0.1:5433/krypton_fund")

    def test_F_build_connector_refuses_before_it_can_construct_one(self,
                                                                   monkeypatch):
        """The probe that made this a KILL: with credentials present,
        build_connector produced a LIVE AlpacaConnector off the prod spec."""
        from app.fund.venue import build_connector

        monkeypatch.setenv("ALPACA_API_KEY", "k")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
        with pytest.raises(m.ProdLocked):
            build_connector(self.PROD)

    def test_G_the_event_store_cannot_be_pointed_at_the_prod_ledger(self,
                                                                    monkeypatch):
        """EventStore.__new__ resolves the mode and calls pg_dsn_for; both are
        gated, so the prod ledger cannot be opened by a forgetful script."""
        from app.fund.events import EventStore

        monkeypatch.setenv("FUND_STORE", "postgres")
        monkeypatch.setenv("FUND_MODE", "alpaca-prod")
        monkeypatch.setenv("FUND_MODE_FILE", "/nonexistent/.fund_mode")
        m.deactivate()
        with pytest.raises(m.ProdLocked):
            EventStore()

    def test_every_gate_reads_prod_gate_report_and_nothing_else(self,
                                                                monkeypatch):
        """v1's sharpest defect: ``reachable`` computed from PROD_UNLOCKED
        while ``resolve()`` read ``allow_prod``, so the boolean measured the
        documented design rather than the shipped line.

        Replaces ``prod_gate_report`` wholesale with a recording stub that says
        reachable. Every gate must then OPEN — which is only possible if each
        of them asks that one call. A gate wired to a private copy of the
        condition stays shut and this fails; a gate that forgot to ask does not
        appear in ``asked``.
        """
        asked = []

        def stub(store=None):
            asked.append(store)
            return {"reachable": True, "preconditions": [],
                    "n_blocking": 0, "n_preconditions": 0}

        monkeypatch.setattr(m, "prod_gate_report", stub)
        spec = m.resolve(env={"FUND_MODE": "alpaca-prod",
                              "FUND_MODE_FILE": "/nonexistent/.fund_mode"})
        assert spec.mode is m.FundMode.ALPACA_PROD
        assert m.pg_dsn_for(spec, "postgresql://u:p@h:1/krypton_fund") \
            .endswith("/krypton_fund_prod")
        m.deactivate()
        assert m.activate(spec).mode is m.FundMode.ALPACA_PROD
        m.deactivate()
        assert len(asked) == 3, (
            f"three gates were exercised and prod_gate_report was asked "
            f"{len(asked)} time(s) — one of them decides on something else")

    def test_at_boot_a_store_dependent_precondition_blocks_and_that_is_stated(self):
        """A property worth naming rather than discovering on the day it bites.

        ``resolve()`` runs at IMPORT, before any event store exists, so it can
        only ever pass ``store=None`` — and ``Precondition.evaluate`` reports
        ``unchecked`` (which blocks) whenever there is no store to read. Two of
        the five CEO preconditions need one.

        The consequence: unlocking alpaca-prod is NOT a one-line constant flip.
        Whoever unlocks it must also arrange for the gate to be evaluated
        somewhere a store exists. That is fail-closed and deliberate; it is
        written down here so it is a decision rather than a surprise.
        """
        report = m.prod_gate_report(store=None)
        got = {c["key"]: c["status"] for c in report["preconditions"]}
        assert got["controls_fired"] == "unchecked"
        assert got["informative_fills"] == "unchecked"
        assert report["reachable"] is False

    def test_one_lock_alone_is_not_enough_in_either_direction(self,
                                                              monkeypatch):
        """Two INDEPENDENT locks. Opening either one alone keeps prod shut, so
        a future edit that satisfies the preconditions does not silently also
        flip the constant, and vice versa."""
        met = [m.Precondition(key="x", text="t",
                              evaluator=lambda s: (True, "ok"))]

        # preconditions met, constant still False
        monkeypatch.setattr(m, "PROD_PRECONDITIONS", tuple(met))
        assert m.prod_gate_report(store=object())["reachable"] is False
        with pytest.raises(m.ProdLocked):
            m.activate(m.MODES[m.FundMode.ALPACA_PROD])

        # constant True, preconditions back to the real (unchecked) five
        monkeypatch.undo()
        monkeypatch.setattr(m, "PROD_UNLOCKED", True)
        assert m.prod_gate_report(store=None)["reachable"] is False
        with pytest.raises(m.ProdLocked):
            m.activate(m.MODES[m.FundMode.ALPACA_PROD])

    def test_the_two_wired_modes_are_untouched_by_the_gate(self):
        """A gate that also blocks the modes the fund actually runs on is a
        different kind of failure. Both wired modes still resolve, activate,
        and produce a DSN."""
        for mode in (m.FundMode.TEST, m.FundMode.ALPACA_PAPER):
            spec = m.MODES[mode]
            m.deactivate()
            assert m.activate(spec).mode is mode
            assert m.pg_dsn_for(spec, "postgresql://u:p@h:1/krypton_fund") \
                .endswith("/" + spec.pg_database)
        m.deactivate()


# --- K1: THE MODE LEDGERS ARE NOT PYTEST'S SCRATCH SPACE ---------------------
class TestModeStoresAreNotTestScratchDatabases:
    """Adversary review of builder D11, 2026-08-22, finding K1.

    v1 of this module designated ``krypton_fund_test`` as the TEST mode's
    *persistent, append-only* ledger. That is the database ``tests/
    test_pgstore.py`` TRUNCATEs in a fixture, along with ten other modules.
    Every ``pytest`` run against a reachable Postgres would have wiped the test
    fund's entire log, so the mode's headline property — *persistent, because a
    replay of 2020-03 is only worth running twice if both runs still exist* —
    was false from the first run.

    The scan reads the test suite ITSELF rather than asserting a hard-coded
    name, because the hazard is symmetrical: it returns either by repointing a
    mode at a scratch database, or by a future test module pointing itself at a
    mode's ledger. Both directions fail here.

    It scans for the DATABASE NAME rather than for a constant, deliberately.
    The first draft of this test keyed on ``TEST_DB = "..."`` and asserted in a
    comment that all thirteen modules use that shape — they do not.
    ``test_snapshot_firestore.py`` uses a lowercase local and
    ``test_observations.py`` inlines the literal, so a constant-shaped guard
    would have missed two of the modules it was written to police. A name has
    to appear literally somewhere for a connection to reach it; that is the
    one thing every shape has in common.
    """

    #: SQL that can destroy a ledger.
    _DESTRUCTIVE = ("TRUNCATE", "CREATE DATABASE", "DROP DATABASE")
    #: ...and the driver that could carry it there. BOTH are required before a
    #: module is policed: "can reach a Postgres AND can destroy a table" is a
    #: predicate rather than a list of names, because a list of names is where
    #: the next offender hides.
    _DRIVER = "psycopg"

    #: THE ONE EXCLUSION, and it is the scanner itself. This module names all
    #: three ledgers on purpose — it is the module that ASSERTS them — and it
    #: quotes the destructive SQL in its forged samples. Excluding it is not a
    #: hole in the guard, but "it is safe because I say so" would be, so
    #: ``test_the_scanner_itself_cannot_reach_a_database`` proves the property
    #: the exclusion rests on rather than assuming it.
    @staticmethod
    def _self_name():
        import pathlib
        return pathlib.Path(__file__).name

    @staticmethod
    def _test_modules():
        import pathlib
        here = pathlib.Path(__file__).resolve().parent
        return sorted(p for p in here.glob("test_*.py"))

    @staticmethod
    def _names_database(text: str, db: str) -> bool:
        """Whole-word match. ``krypton_fund`` must NOT match inside
        ``krypton_fund_test`` — that substring collision made the first draft
        of this test flag all nine PG modules against the paper ledger."""
        import re
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(db)}(?![A-Za-z0-9_])",
                         text) is not None

    def _mode_databases(self):
        return {m.MODES[mode].pg_database for mode in m.FundMode}

    def _scan(self, texts):
        """(offenders, n_destructive_scanned) over {name: source} pairs."""
        mode_dbs = sorted(self._mode_databases())
        offenders, scanned = [], 0
        for name, text in texts:
            if self._DRIVER not in text:
                continue
            if not any(word in text for word in self._DESTRUCTIVE):
                continue
            scanned += 1
            for db in mode_dbs:
                if self._names_database(text, db):
                    offenders.append(f"{name} names {db}")
        return offenders, scanned

    def test_no_destructive_test_module_names_a_fund_ledger(self):
        texts = [(p.name, p.read_text(encoding="utf-8"))
                 for p in self._test_modules() if p.name != self._self_name()]
        offenders, scanned = self._scan(texts)
        assert not offenders, (
            "a test module that TRUNCATEs also names a FUND MODE's ledger — a "
            "pytest run would wipe the fund's own log: " + ", ".join(offenders))
        # Absence discipline: an empty scan is not a clean scan. If the glob or
        # the suite's layout changes, the assertion above goes green by looking
        # at nothing, and this is the line that notices.
        assert scanned >= 10, (
            f"only {scanned} Postgres-touching destructive test modules were "
            f"scanned; there were 12 when this guard was written, so the scan "
            f"is looking in the wrong place rather than finding a clean tree")

    def test_the_scan_would_have_caught_the_original_defect(self):
        """A guard that cannot fail is not a guard.

        Feeds the scanner the exact shape of the v1 defect — a truncating
        module pointed at the TEST mode's ledger — and requires a flag. Run
        against the real database name, so if the mode is ever repointed back
        at a scratch database this stays honest.
        """
        test_db = m.MODES[m.FundMode.TEST].pg_database
        forged = (f'import psycopg\nTEST_DB = "{test_db}"\n'
                  f'cur.execute("TRUNCATE fund_events")\n')
        offenders, scanned = self._scan([("forged_module.py", forged)])
        assert scanned == 1
        assert offenders == [f"forged_module.py names {test_db}"]

    def test_the_scan_does_not_flag_the_pytest_scratch_database(self):
        """The other half of the same proof: the suite's real target must NOT
        be a mode ledger, or the guard above is trivially satisfiable by
        making every database a fund database."""
        forged = ('import psycopg\nTEST_DB = "krypton_fund_test"\n'
                  'cur.execute("TRUNCATE x")\n')
        offenders, _ = self._scan([("forged_module.py", forged)])
        assert offenders == [], (
            "krypton_fund_test is pytest's scratch database and must not be "
            "any mode's ledger; if this fires, a mode was repointed at it")

    def test_the_scanner_itself_cannot_reach_a_database(self):
        """The proof behind the one exclusion above.

        This module is skipped by its own scan because it quotes both the
        ledger names and the destructive SQL. That is only safe while it
        cannot actually open a connection, so the property is asserted rather
        than assumed. Checked on the PARSE TREE, not the text: the forged
        samples and the docstrings legitimately contain the words, and what
        matters is whether any live statement does. If someone later adds a
        real Postgres fixture here, this fails and the exclusion has to be
        re-earned.
        """
        import ast
        import pathlib
        tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
        imported, calls = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute):
                    calls.add(fn.attr)
                elif isinstance(fn, ast.Name):
                    calls.add(fn.id)
        for mod in sorted(imported):
            assert not mod.startswith("psycopg"), \
                f"{mod!r} is imported here, so the self-exclusion is unsafe"
            assert "pgstore" not in mod, \
                f"{mod!r} is imported here, so the self-exclusion is unsafe"
        for call in ("connect", "execute", "PostgresEventStore"):
            assert call not in calls, (
                f"{call}() is called in the scanner module, so excluding it "
                f"from its own scan is no longer safe")


# --- K7: THE TOGGLE THAT BRICKS THE NEXT RESTART -----------------------------
class TestTheRestartHazardIsVisibleAtTheClick:
    """Adversary review of builder D11, 2026-08-22, finding K7.

    ``scripts/run.sh`` exports FUND_MODE unconditionally and the switch
    endpoint writes only the mode file, so any UI switch away from the launch
    script's mode guarantees a ModeConflict on the next start. It fails closed,
    which is right — but the failure landed at BOOT, hours after the click, as
    a spine that would not come up, and nothing rendered the two declarations.

    Neither half is a bug on its own. The script exports the mode because that
    is what the script IS; the endpoint writes the file because a toggle a
    restart silently reverts is the exact trapdoor this module closes. The
    repair is to SAY SO, at the click and continuously afterwards.
    """

    def test_a_conflict_is_reported_with_its_effect_and_its_remedy(self,
                                                                   tmp_path):
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "test"}), encoding="utf-8")
        got = m.declaration_conflict(
            {"FUND_MODE": "alpaca-paper", "FUND_MODE_FILE": str(f)})
        assert got["env"] == "alpaca-paper"
        assert got["file"] == "test"
        assert "ModeConflict" in got["effect"]
        assert "FUND_MODE=test" in got["remedy"]

    def test_agreement_is_not_a_warning(self, tmp_path):
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "test"}), encoding="utf-8")
        assert m.declaration_conflict(
            {"FUND_MODE": "test", "FUND_MODE_FILE": str(f)}) is None

    def test_one_authority_alone_is_not_a_warning(self, tmp_path):
        """The ordinary case. A spine launched with FUND_MODE and no file, or
        a file and no environment, is fine and must not cry wolf."""
        assert m.declaration_conflict(
            {"FUND_MODE": "test", "FUND_MODE_FILE": str(tmp_path / "absent")}) \
            is None
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "test"}), encoding="utf-8")
        assert m.declaration_conflict({"FUND_MODE_FILE": str(f)}) is None

    def test_an_unreadable_file_is_not_reported_as_a_conflict(self, tmp_path):
        """A corrupt file is a DIFFERENT failure, and resolve() raises on it
        already. Reporting it here as a mode disagreement would name the wrong
        cause, which is worse than saying nothing."""
        f = tmp_path / ".fund_mode"
        f.write_text("{not json", encoding="utf-8")
        assert m.declaration_conflict(
            {"FUND_MODE": "test", "FUND_MODE_FILE": str(f)}) is None

    def test_the_report_carries_the_conflict_on_every_reading(self, tmp_path):
        """Not only in the switch response. A spine that will refuse its next
        start says so continuously, so the UI can render it whenever it looks
        — the click is one moment and the hazard lasts until someone fixes it.
        """
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "test"}), encoding="utf-8")
        env = {"FUND_MODE": "alpaca-paper", "FUND_MODE_FILE": str(f)}
        r = m.report(store=None, env=env)
        assert r["declared"]["env"] == "alpaca-paper"
        assert r["declared"]["file"]["mode"] == "test"
        assert r["declared"]["conflict"]["file"] == "test"

    def test_the_report_says_None_not_absent_when_there_is_no_conflict(self,
                                                                       tmp_path):
        """The key is always present. A consumer testing `"conflict" in
        declared` must not read a missing key as "no conflict" on a version
        that never wrote one."""
        r = m.report(store=None,
                     env={"FUND_MODE_FILE": str(tmp_path / "absent")})
        assert "conflict" in r["declared"]
        assert r["declared"]["conflict"] is None

    def test_resolve_still_refuses_the_conflict_it_describes(self, tmp_path):
        """Describing the hazard must not have softened the refusal. The
        endpoint WARNS; the boot path still REFUSES, and those are different
        jobs."""
        f = tmp_path / ".fund_mode"
        f.write_text(json.dumps({"mode": "test"}), encoding="utf-8")
        with pytest.raises(m.ModeConflict):
            m.resolve(env={"FUND_MODE": "alpaca-paper",
                           "FUND_MODE_FILE": str(f)})


# --- K8: THE TWO FALSIFIED CLAIMS --------------------------------------------
class TestTheFourthSwitchIsActuallyGone:
    """Adversary review of builder D11, 2026-08-22, finding K8.

    ``.env.example`` removed ``ALPACA_PAPER=true`` on the claim that the switch
    was gone. It was not: ``connectors/alpaca.py`` still read it as the default
    for ``paper``, and ``scripts/preflight.py`` and ``scripts/reconcile_broker.py``
    each read it to open their own broker clients. Three live readers of a
    variable that decides whether real money can move, while the file that
    documents the environment said it no longer existed.

    Removing a variable from a template does not remove a variable.
    """

    def test_the_connector_refuses_to_guess_paper_or_live(self):
        """Not defaulted to paper — REFUSED. A safe default would still be a
        default deciding where money goes, which is the shape of every incident
        in mode.py's docstring."""
        from app.fund.connectors.alpaca import AlpacaConnector

        with pytest.raises(ValueError) as e:
            AlpacaConnector()
        assert "requires paper=True or paper=False" in str(e.value)
        assert "build_connector" in str(e.value)

    def test_the_environment_variable_cannot_reach_the_connector(self,
                                                                 monkeypatch):
        """Set it to the value that used to mean LIVE, and it changes
        nothing — because nothing reads it."""
        from app.fund.connectors.alpaca import AlpacaConnector

        monkeypatch.setenv("ALPACA_PAPER", "false")
        assert AlpacaConnector(paper=True)._paper is True
        with pytest.raises(ValueError):
            AlpacaConnector()

    def test_nothing_in_the_shipped_tree_reads_ALPACA_PAPER(self):
        """The claim, enforced. Scans app/ and scripts/ for a live read of the
        variable, ignoring string literals and comments — those legitimately
        NAME it, and several deliberately do, to record that it was retired.
        """
        import ast
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        offenders = []
        for pat in ("app/**/*.py", "scripts/**/*.py"):
            for p in root.glob(pat):
                try:
                    tree = ast.parse(p.read_text(encoding="utf-8"))
                except SyntaxError:            # pragma: no cover
                    continue
                for node in ast.walk(tree):
                    # os.getenv("ALPACA_PAPER") / os.environ.get("ALPACA_PAPER")
                    if not isinstance(node, ast.Call):
                        continue
                    fn = node.func
                    name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                    if name not in ("getenv", "get", "environ"):
                        continue
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and \
                                arg.value == "ALPACA_PAPER":
                            offenders.append(f"{p.name}:{node.lineno}")
                    # os.environ["ALPACA_PAPER"]
                for node in ast.walk(tree):
                    if isinstance(node, ast.Subscript) and \
                            isinstance(node.slice, ast.Constant) and \
                            node.slice.value == "ALPACA_PAPER":
                        offenders.append(f"{p.name}:{node.lineno}")
        assert not offenders, (
            f"ALPACA_PAPER is still read at {offenders} — .env.example says it "
            f"is gone, so either the readers go or the claim does (K8)")

    def test_the_scan_can_see_a_reader(self):
        """A guard that cannot fail is not a guard."""
        import ast
        tree = ast.parse('import os\nx = os.getenv("ALPACA_PAPER", "true")\n')
        found = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", None) == "getenv"
                 and any(isinstance(a, ast.Constant) and a.value == "ALPACA_PAPER"
                         for a in n.args)]
        assert len(found) == 1


class TestFundLiveMarksClaim:
    def test_the_flag_alone_decides_and_the_env_does_not_carry_it(self,
                                                                  monkeypatch):
        """The other falsified claim (K8).

        The comment argued the hidden ``or`` could be removed harmlessly
        because ``.env`` carries FUND_LIVE_MARKS=true. Measured against the
        live .env on 2026-08-22: there is no such key. So removal DOES change
        behaviour for a test-mode spine started outside run_test.sh — the safe
        direction (an absent mark is loud, an invented one is not), but shipped
        as "no change", which was wrong.

        What is testable here is the behaviour, which is now unconditional on
        the flag in BOTH directions.
        """
        from app.api.v1 import fund as fundapi

        monkeypatch.delenv("FUND_LIVE_MARKS", raising=False)
        assert fundapi._paper_live_pricer() is None
        monkeypatch.setenv("FUND_LIVE_MARKS", "true")
        assert fundapi._paper_live_pricer() is not None
        monkeypatch.setenv("FUND_LIVE_MARKS", "false")
        assert fundapi._paper_live_pricer() is None
