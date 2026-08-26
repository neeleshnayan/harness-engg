"""The engine ledger and the third reconciliation leg.

THE INCIDENT THIS IS BUILT AGAINST (quant, 2026-08-26; CEO the same day:
"Lean should publish to our UI and DB what is filling vs whats not and our
books should reconcile"):

  A live LEAN session keeps its OWN paper book. It agrees with the fund's book
  only while every signal it raises is approved — LEAN's paper brokerage fills
  the algorithm's order internally whatever the fund decides. **The first
  DECLINED signal makes the two books diverge**, after which the engine
  eventually proposes an exit for stock the fund does not hold and the propose
  path refuses it. Nothing on the live record noticed, because nothing looked.

  It is not hypothetical: order ``e035957c`` (GLD, 0.1, raised by
  ``external:lean`` at seq 157 on 2026-08-16) was DECLINED at seq 158. One
  signal, one divergence, on the record for ten days.

Every test below fails if one of the specific confusions this dispatch was
written to remove comes back:

  * a DECLINED signal and a signal that NEVER ARRIVED rendering the same;
  * a signal still in the approval queue reading as FAILED;
  * an ApprovalRefused annotation being folded in as a fate;
  * an engine that cannot be READ rendering as an engine holding NOTHING;
  * a (strategy, symbol) absent from a COMPLETE fold rendering as unknown
    instead of the measured zero it is — the defect that made the live GLD
    divergence print as "the book could not be read" over a book that had
    just been read;
  * an empty live-session list rendering as an alarm;
  * silence being read as death, or as health.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.fund import engineledger as EL

# ---------------------------------------------------------------- fixtures


def _ev(seq, etype, oid="o1", actor="external:lean", payload=None,
        ts=None, agg="order"):
    return {
        "event_id": f"e{seq}", "seq": seq, "aggregate_id": oid,
        "aggregate_type": agg, "type": etype, "payload": payload or {},
        "actor": actor, "ts": ts or f"2026-08-16T18:{seq:02d}:00+00:00",
    }


def _proposed(seq=1, oid="o1", source="lean", algo="gld_sma_filter",
              symbol="GLD", side="buy", qty=0.1, strategy="s1",
              reason="GLD crossed above its 100-day SMA"):
    return _ev(seq, "OrderProposed", oid, actor=f"external:{source}",
               payload={"symbol": symbol, "side": side, "qty": qty,
                        "strategy_id": strategy, "venue": "paper",
                        "limit_price": None,
                        "rationale": f"[{source}:{algo}] {reason}"})


class _Store:
    """An event store that serves a fixed list. ``append`` is a test failure:
    every path under test is read-only and must stay that way."""

    def __init__(self, events):
        self._events = list(events)
        self.appended = []

    def stream(self, since_seq=0, limit=100_000):
        return [e for e in self._events if e["seq"] > since_seq][:limit]

    def append(self, event):  # pragma: no cover - reaching it IS the failure
        self.appended.append(event)
        raise AssertionError("the engine ledger must never write an event")


class _Attribution:
    """Stands in for StrategyAttribution.positions_by_strategy()."""

    def __init__(self, positions=None, raises=None):
        self._positions = positions or {}
        self._raises = raises

    def positions_by_strategy(self):
        if self._raises:
            raise self._raises
        return {sid: {sym: Decimal(str(q)) for sym, q in syms.items()}
                for sid, syms in self._positions.items()}


#: The live record's own case, reused by several tests below.
_DECLINED_EVENTS = None      # bound after _proposed/_ev are defined, below


def _leg(events, positions=None, sessions=(), raises=None):
    store = _Store(events)
    return EL.engine_leg(store, attribution=_Attribution(positions, raises),
                         sessions=list(sessions))


_DECLINED_EVENTS = [_proposed(1),
                    _ev(2, "OrderDeclined",
                        payload={"approver": "claude:loop-test"})]


# ================================================================== the fates
class TestSignalFates:
    def test_a_declined_signal_is_refused_and_terminal(self):
        """The live record's only engine signal. Its fate is a DECISION."""
        led = EL.signal_ledger(_Store([
            _proposed(1),
            _ev(2, "OrderDeclined", payload={"approver": "claude:loop-test"}),
        ]))
        (row,) = led["signals"]
        assert row["status"] == "declined"
        assert row["outcome"] == "refused"
        assert row["terminal"] is True
        assert row["decided_by"] == "claude:loop-test"
        assert row["reached_venue"] is False

    def test_a_signal_that_never_arrived_is_not_a_refusal(self):
        """A DECLINED signal and a signal that was never raised must not look
        the same. The empty ledger proves it read something — the domain says
        how much — and reports zero in every bucket rather than dropping the
        buckets, because a missing key and a zero read identically to a UI."""
        led = EL.signal_ledger(_Store([
            _ev(1, "OrderProposed", "other", actor="pm",
                payload={"symbol": "SPY", "side": "buy", "qty": 1.0}),
            _ev(2, "OrderDeclined", "other", actor="neelesh", payload={}),
        ]))
        assert led["signals"] == []
        assert led["counts"] == {"filled": 0, "in_flight": 0, "awaiting": 0,
                                 "refused": 0, "failed": 0}
        assert led["total"] == 0
        assert led["domain"]["events_scanned"] == 2      # it LOOKED
        assert led["last_signal_at"] is None

    def test_a_signal_in_the_queue_is_awaiting_not_failed(self):
        """A signal nobody has decided on yet is the one state most easily
        mistaken for a failure. It is not terminal and it is not refused."""
        led = EL.signal_ledger(_Store([_proposed(1)]))
        (row,) = led["signals"]
        assert row["status"] == "awaiting_approval"
        assert row["outcome"] == "awaiting"
        assert row["terminal"] is False
        assert led["counts"]["awaiting"] == 1
        assert led["counts"]["failed"] == 0
        assert led["counts"]["refused"] == 0

    def test_a_filled_signal_carries_its_fill(self):
        led = EL.signal_ledger(_Store([
            _proposed(1),
            _ev(2, "OrderApproved", payload={"approver": "neelesh"}),
            _ev(3, "OrderSubmitted", payload={"venue": "alpaca",
                                              "venue_ref": "v1"}),
            _ev(4, "OrderFilled", payload={"filled_qty": 0.1,
                                           "avg_price": 401.45,
                                           "symbol": "GLD",
                                           "strategy_id": "s1"}),
        ]))
        (row,) = led["signals"]
        assert row["status"] == "filled"
        assert row["outcome"] == "filled"
        assert row["filled_qty"] == 0.1
        assert row["avg_price"] == 401.45
        assert row["reached_venue"] is True
        assert row["decided_by"] == "neelesh"

    def test_a_risk_gate_rejection_is_refused_not_failed(self):
        """The gate saying no and the venue losing the order are different
        facts. Both are terminal; only one is somebody's decision."""
        led = EL.signal_ledger(_Store([
            _proposed(1),
            _ev(2, "OrderRejected", payload={"reason": "position cap"}),
        ]))
        (row,) = led["signals"]
        assert row["status"] == "rejected"
        assert row["outcome"] == "refused"
        assert row["decided_by"] == "risk gate"
        assert row["failure_reason"] == "position cap"

    def test_a_venue_failure_is_failed_not_refused(self):
        led = EL.signal_ledger(_Store([
            _proposed(1),
            _ev(2, "OrderApproved", payload={"approver": "neelesh"}),
            _ev(3, "OrderSubmitted", payload={"venue": "alpaca"}),
            _ev(4, "OrderFailed", payload={"reason": "venue rejected"}),
        ]))
        (row,) = led["signals"]
        assert row["outcome"] == "failed"
        assert row["failure_reason"] == "venue rejected"

    def test_a_partial_fill_is_in_flight_not_filled(self):
        led = EL.signal_ledger(_Store([
            _proposed(1, qty=1.0),
            _ev(2, "OrderApproved", payload={"approver": "neelesh"}),
            _ev(3, "OrderSubmitted", payload={"venue": "alpaca"}),
            _ev(4, "OrderPartiallyFilled", payload={"cumulative_qty": 0.4}),
        ]))
        (row,) = led["signals"]
        assert row["status"] == "partial"
        assert row["outcome"] == "in_flight"
        assert row["terminal"] is False
        assert row["filled_qty"] == 0.4


class TestAnnotationsAreNotFates:
    """AN ANNOTATION IS NOT A LIFECYCLE STEP. This codebase has made that
    mistake twice already (projections/orders.py names both incidents); a
    third surface repeating it would take a signal the CEO can still approve
    and print it as refused."""

    @pytest.mark.parametrize("annotation", sorted(EL.ORDER_ANNOTATION_EVENTS))
    def test_an_annotation_leaves_the_signal_awaiting(self, annotation):
        led = EL.signal_ledger(_Store([
            _proposed(1),
            _ev(2, annotation, actor="prober",
                payload={"reason": "not on the allowlist"}),
        ]))
        (row,) = led["signals"]
        assert row["status"] == "awaiting_approval"
        assert row["outcome"] == "awaiting"
        assert row["terminal"] is False

    def test_the_annotation_is_still_shown(self):
        """Refusing to fold it in is not the same as hiding it — a refused
        approval attempt on an engine signal is exactly what this ledger is
        for."""
        led = EL.signal_ledger(_Store([
            _proposed(1),
            _ev(2, "ApprovalRefused", actor="prober",
                payload={"reason": "not on the allowlist"}),
        ]))
        (row,) = led["signals"]
        assert len(row["annotations"]) == 1
        assert row["annotations"][0]["type"] == "ApprovalRefused"
        assert row["annotations"][0]["reason"] == "not on the allowlist"
        assert row["annotations"][0]["actor"] == "prober"


class TestProvenance:
    def test_only_engine_raised_orders_enter_the_ledger(self):
        led = EL.signal_ledger(_Store([
            _proposed(1, oid="engine"),
            _ev(2, "OrderProposed", "human", actor="neelesh",
                payload={"symbol": "SPY", "side": "buy", "qty": 1.0,
                         "rationale": "[pm - rec R4] rebalance"}),
        ]))
        assert [r["order_id"] for r in led["signals"]] == ["engine"]
        assert led["sources"] == ["lean"]

    def test_the_source_comes_from_the_actor_and_the_algo_from_the_rationale(self):
        led = EL.signal_ledger(_Store([_proposed(1)]))
        (row,) = led["signals"]
        assert row["source"] == "lean"
        assert row["algo_id"] == "gld_sma_filter"
        assert row["reason"] == "GLD crossed above its 100-day SMA"

    def test_an_unparseable_rationale_leaves_the_algo_ABSENT(self):
        """Absent, not "unknown" and not a guess: the intake builds this string
        by hand and there is no structured field to fall back on."""
        ev = _proposed(1)
        ev["payload"]["rationale"] = "no brackets here at all"
        led = EL.signal_ledger(_Store([ev]))
        (row,) = led["signals"]
        assert row["algo_id"] is None
        assert row["reason"] == "no brackets here at all"

    def test_a_bracket_without_a_colon_still_yields_no_algo(self):
        ev = _proposed(1)
        ev["payload"]["rationale"] = "[lean] it went up"
        led = EL.signal_ledger(_Store([ev]))
        (row,) = led["signals"]
        assert row["algo_id"] is None
        assert row["reason"] == "it went up"


class TestLedgerDomain:
    """A count without its domain is not a result. An engine signal older than
    the scan window is UNREAD, not absent, and the two must not print alike."""

    def test_the_domain_reports_the_window_edges(self):
        led = EL.signal_ledger(_Store([_proposed(7), _ev(9, "OrderDeclined")]))
        assert led["domain"]["seq_first"] == 7
        assert led["domain"]["seq_last"] == 9
        assert led["domain"]["events_scanned"] == 2
        assert led["domain"]["window_bound"] is False

    def test_a_bound_window_says_so(self, monkeypatch):
        monkeypatch.setattr(EL, "SIGNAL_SCAN_LIMIT", 2)
        led = EL.signal_ledger(_Store([_proposed(1), _ev(2, "OrderDeclined"),
                                       _ev(3, "NavStruck", agg="fund")]))
        assert led["domain"]["events_scanned"] == 2
        assert led["domain"]["window_bound"] is True

    def test_the_limit_truncates_rows_but_the_total_does_not_lie(self):
        events = []
        for i in range(1, 6):
            events.append(_proposed(i, oid=f"o{i}"))
        led = EL.signal_ledger(_Store(events), limit=2)
        assert led["returned"] == 2
        assert led["total"] == 5
        assert len(led["signals"]) == 2

    def test_rows_come_back_newest_first(self):
        events = [_proposed(i, oid=f"o{i}") for i in (1, 5, 3)]
        led = EL.signal_ledger(_Store(events))
        assert [r["seq"] for r in led["signals"]] == [5, 3, 1]


# ============================================================ the third leg
class TestEngineLeg:
    def test_the_engines_own_book_is_UNREADABLE_never_zero(self):
        """An engine that cannot be read and an engine holding nothing are
        different facts. Every direct quantity is None and the leg says why."""
        leg = _leg([_proposed(1), _ev(2, "OrderDeclined")],
                   positions={"s1": {}})
        assert leg["direct"]["readable"] is False
        assert leg["direct"]["qty_basis"] == "UNKNOWN"
        assert all(r["engine_qty"] is None
                   for r in leg["implied"]["per_symbol"])
        assert "publishes no holdings" in leg["direct"]["reason"]

    def test_the_live_divergence_is_reproduced(self):
        """The record's own case: one declined signal, and the books part.
        Engine-implied 0.1 GLD against a book that holds none of it."""
        leg = _leg([_proposed(1), _ev(2, "OrderDeclined",
                                      payload={"approver": "claude:loop-test"})],
                   positions={"s1": {}})
        (row,) = leg["implied"]["per_symbol"]
        assert row["symbol"] == "GLD"
        assert row["engine_implied_qty"] == 0.1
        assert row["book_qty"] == 0.0
        assert row["drift"] == pytest.approx(0.1)
        assert row["in_sync"] is False
        assert leg["implied"]["symbols_out_of_sync"] == 1
        assert leg["verdict"]["state"] == "diverged"
        assert leg["verdict"]["symbols"] == ["GLD"]

    def test_absence_inside_a_complete_fold_is_ZERO(self):
        """THE DEFECT THIS TEST EXISTS FOR: the first version of the leg
        returned None for a (strategy, symbol) the attribution fold has no
        entry for, so the live GLD divergence printed as "the book could not be
        read" over a book it had just read. StrategyAttribution folds EVERY
        fill, so no entry means no fills means flat — a measured zero."""
        leg = _leg([_proposed(1), _ev(2, "OrderDeclined")],
                   positions={"other-strategy": {"SPY": 3}})
        (row,) = leg["implied"]["per_symbol"]
        assert row["book_qty"] == 0.0
        assert row["in_sync"] is False
        assert leg["implied"]["book_readable"] is True
        assert leg["implied"]["symbols_undetermined"] == 0

    def test_absence_of_the_fold_is_NOT_zero(self):
        """The other half of the same rule. An unreadable book yields None on
        every side and an ``in_sync`` of None — never True, which would read
        as an agreement nobody measured."""
        leg = _leg([_proposed(1), _ev(2, "OrderDeclined")],
                   raises=RuntimeError("the store is down"))
        (row,) = leg["implied"]["per_symbol"]
        assert row["book_qty"] is None
        assert row["drift"] is None
        assert row["in_sync"] is None
        assert leg["implied"]["book_readable"] is False
        assert "RuntimeError" in leg["implied"]["book_unreadable_reason"]
        assert leg["verdict"]["state"] == "unknown"
        assert leg["implied"]["symbols_undetermined"] == 1
        assert leg["implied"]["symbols_out_of_sync"] == 0

    def test_a_filled_signal_leaves_the_books_agreeing(self):
        leg = _leg([
            _proposed(1),
            _ev(2, "OrderApproved", payload={"approver": "neelesh"}),
            _ev(3, "OrderSubmitted", payload={"venue": "alpaca"}),
            _ev(4, "OrderFilled", payload={"filled_qty": 0.1,
                                           "avg_price": 401.45,
                                           "symbol": "GLD",
                                           "strategy_id": "s1"}),
        ], positions={"s1": {"GLD": 0.1}})
        (row,) = leg["implied"]["per_symbol"]
        assert row["in_sync"] is True
        assert leg["verdict"]["state"] == "in_sync"
        assert leg["signals_not_filled"] == 0

    def test_a_sell_signal_nets_the_implied_book_down(self):
        """The engine's book is a NET of what it raised, not a count of it.
        A buy then a sell of the same size leaves it flat — and if the fund
        followed neither, the two agree at zero."""
        leg = _leg([
            _proposed(1, oid="a", side="buy", qty=0.1),
            _ev(2, "OrderDeclined", "a"),
            _proposed(3, oid="b", side="sell", qty=0.1),
            _ev(4, "OrderDeclined", "b"),
        ], positions={"s1": {}})
        (row,) = leg["implied"]["per_symbol"]
        assert row["engine_implied_qty"] == 0.0
        assert row["in_sync"] is True
        assert row["signals"]["raised"] == 2
        assert row["signals"]["refused"] == 2

    def test_the_row_says_how_many_signals_and_of_which_fate(self):
        leg = _leg([
            _proposed(1, oid="a"), _ev(2, "OrderDeclined", "a"),
            _proposed(3, oid="b"),
        ], positions={"s1": {}})
        (row,) = leg["implied"]["per_symbol"]
        assert row["signals"] == {"raised": 2, "filled": 0, "awaiting": 1,
                                  "refused": 1, "in_flight": 0, "failed": 0}

    def test_fills_from_elsewhere_on_the_same_pair_are_counted(self):
        """A drift can also come from a hand-staged order tagged to the same
        strategy. Saying so is what keeps the attribution honest instead of
        blaming every disagreement on the engine."""
        leg = _leg([
            _proposed(1, oid="engine"),
            _ev(2, "OrderDeclined", "engine"),
            _ev(3, "OrderFilled", "byhand", actor="neelesh",
                payload={"filled_qty": 2.0, "avg_price": 400.0,
                         "symbol": "GLD", "strategy_id": "s1"}),
        ], positions={"s1": {"GLD": 2.0}})
        (row,) = leg["implied"]["per_symbol"]
        assert row["other_fills"] == 1
        assert row["book_qty"] == 2.0
        assert row["in_sync"] is False

    def test_the_leg_reads_the_book_it_is_GIVEN(self):
        """MOVE the value rather than matching it: the same events against two
        different books must produce two different answers. An assertion that
        the leg's number equals the fold's number cannot tell a read from a
        hardcoded duplicate that happens to agree."""
        events = [_proposed(1), _ev(2, "OrderDeclined")]
        flat = _leg(events, positions={"s1": {}})
        held = _leg(events, positions={"s1": {"GLD": 0.1}})
        assert flat["implied"]["per_symbol"][0]["book_qty"] == 0.0
        assert held["implied"]["per_symbol"][0]["book_qty"] == 0.1
        assert flat["verdict"]["state"] == "diverged"
        assert held["verdict"]["state"] == "in_sync"

    def test_nothing_to_compare_is_not_agreement(self):
        leg = _leg([], positions={"s1": {"GLD": 5}})
        assert leg["verdict"]["state"] == "no_signals"
        assert "not the same as agreement" in leg["verdict"]["sentence"]
        assert leg["implied"]["per_symbol"] == []

    def test_the_tolerance_treats_fold_residue_as_flat(self):
        """Folding every fill leaves ~1e-15 on a closed symbol. An 'is it held'
        test on != 0 reports phantom holdings."""
        leg = _leg([_proposed(1, qty=0.1), _ev(2, "OrderFilled",
                                               payload={"filled_qty": 0.1,
                                                        "symbol": "GLD",
                                                        "strategy_id": "s1"})],
                   positions={"s1": {"GLD": Decimal("0.1") + Decimal("1e-15")}})
        (row,) = leg["implied"]["per_symbol"]
        assert row["in_sync"] is True

    def test_the_leg_writes_nothing(self):
        store = _Store([_proposed(1), _ev(2, "OrderDeclined")])
        EL.engine_leg(store, attribution=_Attribution({"s1": {}}), sessions=[])
        EL.signal_ledger(store)
        assert store.appended == []

    def test_a_running_session_does_not_make_the_book_readable(self):
        """The session record carries state and a log tail. Neither is a
        position, so a running engine is exactly as unreadable as a stopped
        one — and the reason must not silently claim otherwise."""
        leg = _leg([_proposed(1)], positions={"s1": {}},
                   sessions=[{"session_id": "x", "state": "running"}])
        assert leg["direct"]["readable"] is False
        assert leg["direct"]["sessions_running"] == 1
        assert "nothing to ask" not in leg["direct"]["reason"]


# ========================================================== the engine status
class TestEngineStatus:
    def test_no_session_is_a_fact_not_an_alarm(self):
        """GET /fund/lean/live has returned {"sessions": []} for the whole life
        of this fund. Rendering that as a fault trains its reader to ignore the
        one time it is a fault."""
        st = EL.engine_status([], {"last_signal_at": None})
        assert st["state"] == "no_session"
        assert st["sessions"] == []
        assert st["liveness_provable"] is None
        assert "not a fault" in st["note"]

    def test_a_running_sessions_liveness_is_NOT_provable(self):
        """On daily bars a healthy algorithm is silent for days. A dead engine
        and a correctly-quiet one look identical from here, and this must say
        so rather than infer either way."""
        st = EL.engine_status([{"session_id": "x", "state": "running",
                                "started_at": "2026-08-26T00:00:00+00:00"}],
                              {"last_signal_at": "2026-08-16T18:59:52+00:00"})
        assert st["state"] == "running"
        assert st["liveness_provable"] is False
        assert "silent" in st["note"]

    def test_a_failed_session_IS_readable(self):
        st = EL.engine_status([{"session_id": "x", "state": "failed",
                                "error": "LiveDataQueue not implemented"}], {})
        assert st["state"] == "failed"
        assert st["liveness_provable"] is True
        assert st["sessions"][0]["error"] == "LiveDataQueue not implemented"

    def test_a_running_sessions_empty_log_tail_is_marked_PENDING(self):
        """_run_live captures log_tail from the COMPLETED subprocess, so a
        running session's tail is empty by construction. Empty must not read
        as 'nothing is happening'."""
        st = EL.engine_status([{"session_id": "x", "state": "running",
                                "log_tail": []}], {})
        assert st["sessions"][0]["log_tail_pending"] is True

    def test_an_ended_sessions_empty_tail_is_not_pending(self):
        st = EL.engine_status([{"session_id": "x", "state": "ended",
                                "log_tail": []}], {})
        assert st["sessions"][0]["log_tail_pending"] is False

    def test_the_bar_clock_is_UNKNOWN_and_says_what_would_close_it(self):
        st = EL.engine_status([{"session_id": "x", "state": "running"}], {})
        assert st["last_bar_seen"] is None
        assert "UNKNOWN" in st["last_bar_seen_note"]
        assert "results folder" in st["last_bar_seen_note"]

    def test_the_last_signal_is_fund_wide_and_says_so(self):
        """A signal carries no session id, so 'the running session last spoke
        at X' is a claim the record cannot support."""
        st = EL.engine_status([{"session_id": "x", "state": "running"}],
                              {"last_signal_at": "2026-08-16T18:59:52+00:00"})
        assert st["last_signal_at"] == "2026-08-16T18:59:52+00:00"
        assert "no session id" in st["last_signal_scope"]

    def test_a_session_record_never_leaks_a_token(self):
        """start_live keeps the signal token out of the session dict on
        purpose (it is returned over the API). Nothing here may reintroduce
        it."""
        st = EL.engine_status([{"session_id": "x", "state": "running",
                                "signal_configured": True,
                                "container": "lean-live-x"}], {})
        rendered = repr(st)
        assert "token" not in rendered.lower()
        assert st["sessions"][0]["signal_configured"] is True


# ======================================================== the name attachment
class TestStrategyNames:
    def test_names_are_attached_to_both_surfaces(self):
        led = EL.signal_ledger(_Store([_proposed(1)]))
        EL.attach_strategy_names(led, lambda sid: f"name-of-{sid}")
        assert led["signals"][0]["strategy_name"] == "name-of-s1"

        leg = _leg([_proposed(1)], positions={"s1": {}})
        EL.attach_strategy_names(leg, lambda sid: f"name-of-{sid}")
        assert leg["implied"]["per_symbol"][0]["strategy_name"] == "name-of-s1"

    def test_an_unresolvable_id_yields_None_and_does_not_raise(self):
        def boom(sid):
            raise KeyError(sid)

        led = EL.signal_ledger(_Store([_proposed(1)]))
        EL.attach_strategy_names(led, boom)
        assert led["signals"][0]["strategy_name"] is None

    def test_the_resolver_is_called_once_per_distinct_id(self):
        calls = []

        def resolver(sid):
            calls.append(sid)
            return sid.upper()

        led = EL.signal_ledger(_Store([
            _proposed(1, oid="a", strategy="s1"),
            _proposed(2, oid="b", strategy="s1"),
            _proposed(3, oid="c", strategy="s2"),
        ]))
        EL.attach_strategy_names(led, resolver)
        assert sorted(calls) == ["s1", "s2"]


# ================================================================ the doors
class _Lean:
    def __init__(self, sessions=(), raises=None):
        self._sessions = list(sessions)
        self._raises = raises

    def live_sessions(self):
        if self._raises:
            raise self._raises
        return list(self._sessions)


class _Strategies:
    def __init__(self, names=None):
        self._names = names or {}

    def get(self, sid):
        from app.fund.strategies import StrategyError
        if sid not in self._names:
            raise StrategyError(f"unknown strategy {sid}")
        return {"strategy_id": sid, "name": self._names[sid]}


def _client(monkeypatch, events, drift, positions=None, sessions=(),
            lean_raises=None, names=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1 import fund as fundapi

    monkeypatch.setattr(fundapi, "_store", _Store(events))
    monkeypatch.setattr(fundapi, "_attribution", _Attribution(positions or {}))
    monkeypatch.setattr(fundapi, "_strategies", _Strategies(names))
    monkeypatch.setattr(fundapi, "_reconciler",
                        type("R", (), {"drift": staticmethod(lambda: dict(drift))})())
    monkeypatch.setattr(fundapi, "_lean",
                        lambda: _Lean(sessions, lean_raises))
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


_DECLINED = [_proposed(1), _ev(2, "OrderDeclined",
                               payload={"approver": "claude:loop-test"})]


class TestReconcileEndpoint:
    def test_the_third_leg_rides_on_the_existing_reconcile(self, monkeypatch):
        c = _client(monkeypatch, _DECLINED,
                    drift={"configured": True, "book_nav": 1999.01,
                           "per_symbol": [], "symbols_out_of_sync": 0})
        r = c.get("/api/v1/fund/venue/reconcile")
        assert r.status_code == 200
        body = r.json()
        # The broker leg is untouched — same keys, same words.
        assert body["configured"] is True
        assert body["book_nav"] == 1999.01
        # And the leg that did not exist before.
        assert body["engine"]["verdict"]["state"] == "diverged"

    def test_the_engine_leg_SURVIVES_an_unreachable_broker(self, monkeypatch):
        """The reason the leg is composed at the endpoint rather than inside
        Reconciler.drift: drift returns early the moment the broker is
        unreachable, so a leg computed inside it would VANISH exactly when the
        broker is down. A leg that disappears reads as a leg with nothing to
        say."""
        c = _client(monkeypatch, _DECLINED,
                    drift={"configured": False, "reason": "broker error: boom"})
        body = c.get("/api/v1/fund/venue/reconcile").json()
        assert body["configured"] is False
        assert body["engine"]["verdict"]["state"] == "diverged"
        assert body["engine"]["implied"]["symbols_out_of_sync"] == 1

    def test_an_unbuildable_leg_is_NAMED_not_silently_agreeing(self, monkeypatch):
        from app.api.v1 import fund as fundapi

        c = _client(monkeypatch, _DECLINED, drift={"configured": True})
        monkeypatch.setattr(fundapi, "_attribution", None)

        def boom(*a, **k):
            raise RuntimeError("fold unavailable")

        from app.fund import engineledger
        monkeypatch.setattr(engineledger, "engine_leg", boom)
        body = c.get("/api/v1/fund/venue/reconcile").json()
        assert body["engine"]["readable"] is False
        assert body["engine"]["verdict"]["state"] == "unreadable"
        assert "fold unavailable" in body["engine"]["verdict"]["sentence"]

    def test_a_broken_leg_does_not_take_the_reconcile_down(self, monkeypatch):
        from app.fund import engineledger

        c = _client(monkeypatch, _DECLINED,
                    drift={"configured": True, "book_nav": 1999.01})
        monkeypatch.setattr(engineledger, "engine_leg",
                            lambda *a, **k: (_ for _ in ()).throw(
                                RuntimeError("boom")))
        r = c.get("/api/v1/fund/venue/reconcile")
        assert r.status_code == 200
        assert r.json()["book_nav"] == 1999.01


class TestSignalLedgerEndpoint:
    def test_the_ledger_serves_the_fates_and_the_names(self, monkeypatch):
        c = _client(monkeypatch, _DECLINED, drift={"configured": True},
                    names={"s1": "GLD SMA filter"})
        body = c.get("/api/v1/fund/signals/ledger").json()
        (row,) = body["signals"]
        assert row["outcome"] == "refused"
        assert row["strategy_name"] == "GLD SMA filter"
        assert body["counts"]["refused"] == 1

    def test_an_unregistered_strategy_leaves_the_name_absent(self, monkeypatch):
        c = _client(monkeypatch, _DECLINED, drift={"configured": True})
        (row,) = c.get("/api/v1/fund/signals/ledger").json()["signals"]
        assert row["strategy_name"] is None
        assert row["strategy_id"] == "s1"      # the id is still there to show

    def test_the_limit_is_honoured(self, monkeypatch):
        events = [_proposed(i, oid=f"o{i}") for i in range(1, 6)]
        c = _client(monkeypatch, events, drift={"configured": True})
        body = c.get("/api/v1/fund/signals/ledger?limit=2").json()
        assert body["returned"] == 2 and body["total"] == 5


class TestEngineEndpoint:
    def test_one_call_answers_all_three_questions(self, monkeypatch):
        c = _client(monkeypatch, _DECLINED,
                    drift={"configured": True}, names={"s1": "GLD SMA filter"})
        body = c.get("/api/v1/fund/engine").json()
        assert body["status"]["state"] == "no_session"
        assert body["ledger"]["counts"]["refused"] == 1
        assert body["reconcile"]["verdict"]["state"] == "diverged"

    def test_an_unreadable_session_list_is_not_an_empty_one(self, monkeypatch):
        """An engine we cannot ASK about is not an engine that is not running.
        'no_session' is a claim about the fund; this is a claim about the
        reading, and they must not print the same word."""
        c = _client(monkeypatch, _DECLINED, drift={"configured": True},
                    lean_raises=RuntimeError("docker is down"))
        st = c.get("/api/v1/fund/engine").json()["status"]
        assert st["state"] == "unknown"
        assert st["sessions_readable"] is False
        assert "docker is down" in st["note"]

    def test_a_readable_empty_list_says_so(self, monkeypatch):
        c = _client(monkeypatch, _DECLINED, drift={"configured": True})
        st = c.get("/api/v1/fund/engine").json()["status"]
        assert st["state"] == "no_session"
        assert st["sessions_readable"] is True

    def test_a_running_session_is_rendered_with_its_caveat(self, monkeypatch):
        c = _client(monkeypatch, _DECLINED, drift={"configured": True},
                    sessions=[{"session_id": "abc", "algorithm": "gld_sma",
                               "state": "running", "log_tail": [],
                               "started_at": "2026-08-26T00:00:00+00:00"}])
        st = c.get("/api/v1/fund/engine").json()["status"]
        assert st["state"] == "running"
        assert st["liveness_provable"] is False
        assert st["sessions"][0]["log_tail_pending"] is True


class TestSentencesReadLikeEnglish:
    """These strings ARE the surface — the CEO reads the verdict sentence and
    nothing under it. "1 symbol(s)" is the tell of a number formatted by a
    machine that did not look at it, and it shipped in the first draft."""

    def test_one_symbol_is_singular(self):
        leg = _leg(_DECLINED_EVENTS, positions={"s1": {}})
        assert "1 symbol:" in leg["verdict"]["sentence"]
        assert "(s)" not in leg["verdict"]["sentence"]

    def test_two_symbols_are_plural(self):
        leg = _leg([
            _proposed(1, oid="a", symbol="GLD"), _ev(2, "OrderDeclined", "a"),
            _proposed(3, oid="b", symbol="SLV"), _ev(4, "OrderDeclined", "b"),
        ], positions={"s1": {}})
        assert "2 symbols:" in leg["verdict"]["sentence"]

    def test_one_agreeing_symbol_is_singular(self):
        leg = _leg([
            _proposed(1),
            _ev(2, "OrderFilled", payload={"filled_qty": 0.1, "symbol": "GLD",
                                           "strategy_id": "s1"}),
        ], positions={"s1": {"GLD": 0.1}})
        assert "All 1 symbol the engine" in leg["verdict"]["sentence"]

    def test_one_running_session_is_singular(self):
        st = EL.engine_status([{"session_id": "x", "state": "running"}], {})
        assert st["note"].startswith("1 session running")

    def test_two_running_sessions_are_plural(self):
        st = EL.engine_status([{"session_id": "x", "state": "running"},
                               {"session_id": "y", "state": "running"}], {})
        assert st["note"].startswith("2 sessions running")

    def test_an_undetermined_symbol_is_singular(self):
        leg = _leg(_DECLINED_EVENTS, raises=RuntimeError("down"))
        assert leg["verdict"]["sentence"].startswith("1 symbol cannot be compared")
