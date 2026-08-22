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
        assert spec.pg_database == "krypton_fund_test"
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

    def test_each_mode_gets_its_own_database_on_the_same_server(self):
        got = {mode.value: m.pg_dsn_for(m.MODES[mode], self.BASE)
               for mode in m.FundMode}
        assert got["test"].endswith("/krypton_fund_test")
        assert got["alpaca-paper"].endswith("/krypton_fund")
        assert got["alpaca-prod"].endswith("/krypton_fund_prod")
        assert len(set(got.values())) == 3

    def test_credentials_host_and_port_are_carried_through(self):
        out = m.pg_dsn_for(m.MODES[m.FundMode.TEST], self.BASE)
        assert out.startswith("postgresql://krypton:krypton_local@127.0.0.1:5433/")

    def test_query_parameters_survive(self):
        out = m.pg_dsn_for(m.MODES[m.FundMode.TEST], self.BASE + "?sslmode=require")
        assert out.endswith("/krypton_fund_test?sslmode=require")

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
        m.assert_connector_permitted(m.MODES[m.FundMode.TEST], self.Fake("paper"))
        m.assert_connector_permitted(m.MODES[m.FundMode.ALPACA_PAPER],
                                     self.Fake("alpaca"))


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
        assert r["active"]["store"]["pg_database"] == "krypton_fund_test"
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
