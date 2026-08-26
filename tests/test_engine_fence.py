"""THE FENCE — can a dead engine's history stop shouting, without a live
divergence ever going quiet?

WHY THIS FILE EXISTS. ``engine_leg`` folded every ``external:`` signal ever
recorded into one live verdict, so ``GET /fund/engine`` read
``DIVERGED — GLD engine 0.1 vs book 0.0`` on a signal from 2026-08-16 whose
LEAN session died with a spine restart days earlier and whose strategy the CEO
archived. The engine's paper book lives inside its container; when the
container goes, so does the book, and the next session starts flat. Old signals
are history, not a disagreement now.

**FENCING IS A LOOSENING AND THIS FILE TREATS IT AS ONE.** A fence removes a
row from the divergence verdict, so the tests that matter most here are not the
ones proving the GLD row fences — they are the SIX proving that a signal which
might still belong to a live engine NEVER does. ``TestNothingLiveIsEverFenced``
is that enumeration, one test per way the proof can fail, and each one names
the mutant that makes it fail.
"""
import datetime

import pytest

from app.fund import engineledger as EL
from app.fund.leanrunner import declared_algorithm_class, declared_datasource

# --------------------------------------------------------------- fixtures

#: Deliberately not "now": every instant in this file is written down, so a
#: test cannot pass because the clock happened to cooperate.
T0 = "2026-08-10T00:00:00+00:00"     # before everything
T1 = "2026-08-16T18:59:52+00:00"     # the signal
T2 = "2026-08-20T00:00:00+00:00"     # after the signal
SID = "strat-gld"
OTHER = "strat-hyg"


class _Store:
    """The event stream, and a witness that nothing here writes."""

    def __init__(self, events):
        self._events = list(events)
        self.appended = []

    def stream(self, since_seq=0, limit=None):
        return list(self._events)

    def append(self, event):        # pragma: no cover — asserted never called
        self.appended.append(event)


class _Attribution:
    def __init__(self, positions=None):
        self._positions = positions or {}

    def positions_by_strategy(self):
        from decimal import Decimal
        return {sid: {sym: Decimal(str(q)) for sym, q in syms.items()}
                for sid, syms in self._positions.items()}


def _proposed(seq, *, sid=SID, symbol="GLD", side="buy", qty=0.1, ts=T1,
              algo="gld_sma_filter", oid=None):
    return {"seq": seq, "ts": ts, "aggregate_type": "order",
            "aggregate_id": oid or f"o{seq}", "type": "OrderProposed",
            "actor": "external:lean",
            "payload": {"symbol": symbol, "side": side, "qty": qty,
                        "strategy_id": sid, "venue": "alpaca",
                        "rationale": f"[lean:{algo}] a reason"}}


def _declined(seq, oid, ts=T1):
    return {"seq": seq, "ts": ts, "aggregate_type": "order",
            "aggregate_id": oid, "type": "OrderDeclined",
            "actor": "someone", "payload": {"approver": "someone"}}


def _session(state="running", sid=SID, algo="gld_sma_filter", started=T0,
             session_id="sess-1"):
    return {"session_id": session_id, "state": state, "strategy_id": sid,
            "algorithm": algo, "started_at": started}


def _ctx(sessions=(), known_since=T2, archived=()):
    return EL.EngineContext(
        sessions=None if sessions is None else list(sessions),
        known_since=known_since,
        archived_strategy_ids=None if archived is None else set(archived))


def _leg(events, positions=None, ctx=None):
    return EL.engine_leg(_Store(events), attribution=_Attribution(positions),
                         context=ctx if ctx is not None else _ctx())


#: The live record's own shape: one engine buy, declined, on a strategy that is
#: now archived, from a session that no longer exists.
DEAD_HISTORY = [_proposed(157, oid="e035957c"), _declined(158, "e035957c")]


# ============================================================ THE LOOSENING

class TestNothingLiveIsEverFenced:
    """THE KILLING QUESTION, ENUMERATED: can any signal that might still belong
    to a live engine be classified fenced?

    Each test is one way the proof of death can fail. If any of them ever
    fences, the fence has become a mechanism for hiding a real divergence —
    which is the exact failure this whole feature is one mistake away from.
    """

    def test_an_unreadable_session_list_never_fences(self):
        """MUTANT M1: ``if not ctx.sessions_readable`` -> ``if False``.

        ``sessions=None`` is "we could not ask what is running". Fencing on it
        would turn a Docker outage into silence about a live divergence — the
        absence-as-zero defect with a verdict attached.
        """
        leg = _leg(DEAD_HISTORY, {SID: {}}, _ctx(sessions=None, archived=[SID]))
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"
        row, = leg["implied"]["per_symbol"]
        assert row["sync_state"] == "diverged"
        assert row["fenced"] is False

    def test_a_live_session_on_the_same_strategy_never_fences(self):
        """MUTANT M2: drop the ``_claiming_session`` check.

        The acceptance criterion the brief names: a signal raised by a
        CURRENTLY LIVE session that disagrees with the book still reads
        DIVERGED. Note the strategy is ALSO archived here — archiving must not
        be able to silence a running engine.
        """
        leg = _leg(DEAD_HISTORY, {SID: {}},
                   _ctx(sessions=[_session()], archived=[SID]))
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"
        assert leg["implied"]["per_symbol"][0]["engine_implied_qty"] == 0.1

    def test_a_live_session_matched_only_by_algorithm_never_fences(self):
        """MUTANT M3: drop the ``s_algo == algo`` half of the claim test.

        A session started with an empty ``strategy_id`` (``start_live``'s
        default) still names its algorithm, and the signal names the same one.
        One matching identity is enough — the claim test is generous by design.
        """
        leg = _leg(DEAD_HISTORY, {SID: {}},
                   _ctx(sessions=[_session(sid="")], archived=[SID]))
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"

    def test_a_live_session_naming_nothing_claims_everything(self):
        """MUTANT M4: make an identity-less session claim nothing.

        A running session that declares neither a strategy nor an algorithm
        cannot be RULED OUT as the source, and an engine we cannot identify is
        not an engine we may declare dead.
        """
        leg = _leg(DEAD_HISTORY, {SID: {}},
                   _ctx(sessions=[_session(sid="", algo="")], archived=[SID]))
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"

    def test_a_signal_with_no_timestamp_never_fences(self):
        """MUTANT M5: treat an unreadable ``raised_at`` as fenceable.

        A signal that cannot be placed in time cannot be placed on either side
        of the session-memory line, so it proves nothing.
        """
        ev = _proposed(157, ts=None)
        ev["ts"] = None
        leg = _leg([ev], {SID: {}}, _ctx(archived=[SID]))
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"
        # AND THE BASIS, not only the state. Removing the guard leaves the
        # signal LIVE anyway (the comparison fails on an unparseable instant),
        # so a test asserting only "not fenced" cannot see the mutant - it
        # would report basis ``raised_during_this_process``, a claim about
        # WHEN a signal with no when was raised. Mutation survivor M5.
        led = EL.signal_ledger(_Store([ev]), context=_ctx(archived=[SID]))
        assert led["signals"][0]["liveness"]["basis"] == EL.BASIS_RAISED_AT_UNREADABLE

    def test_an_unaskable_runner_never_fences(self):
        """MUTANT M6: default ``known_since`` to now instead of ``None``.

        If the runner could not say when its session memory began, there is no
        line to place the signal against. A default of "now" would fence the
        entire history of the fund on a failed attribute read.
        """
        leg = _leg(DEAD_HISTORY, {SID: {}}, _ctx(known_since=None, archived=[SID]))
        assert leg["fence"]["sessions_known_since"] is None
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"
        # The basis again, for the same reason as M5: without the guard this
        # still reads LIVE, but it would claim the signal was raised during a
        # session memory that has no beginning. Mutation survivor M6.
        led = EL.signal_ledger(_Store(DEAD_HISTORY),
                               context=_ctx(known_since=None, archived=[SID]))
        assert led["signals"][0]["liveness"]["basis"] == EL.BASIS_KNOWN_SINCE_UNREADABLE

    def test_an_orphan_raised_during_this_process_never_fences(self):
        """MUTANT M7: fence on "no live session" rather than on "predates
        session memory".

        THE HOLE THIS CLOSES, AND IT IS THE REASON THE FENCE IS ANCHORED ON A
        TIMESTAMP RATHER THAN ON AN EMPTY LIST. ``stop_live`` kills a container
        by name; a spine restart does not. So a LEAN container can outlive the
        runner that started it and keep POSTing signals while
        ``live_sessions()`` returns ``[]``. A signal raised AFTER this runner's
        memory began, with no session accounting for it, is evidence that the
        session list is INCOMPLETE — never evidence that the engine is dead.
        """
        ctx = _ctx(sessions=[], known_since=T0, archived=[SID])
        leg = _leg(DEAD_HISTORY, {SID: {}}, ctx)
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"

    def test_a_signal_raised_exactly_at_the_boundary_never_fences(self):
        """BOUNDARY TABLE: the comparison is STRICTLY earlier, and the equal
        case must fall on the LIVE side.

        MUTANT M8: ``<`` -> ``<=`` in ``_iso_lt``'s caller. At exactly the
        instant the runner's memory began, a session record could already
        exist, so the proof of absence does not hold.
        """
        assert not _leg(DEAD_HISTORY, {SID: {}},
                        _ctx(known_since=T1))["signals_fenced"]
        # One microsecond later it DOES fence — so the boundary is the only
        # thing separating these two cases, not some other difference.
        later = "2026-08-16T18:59:52.000001+00:00"
        assert _leg(DEAD_HISTORY, {SID: {}},
                    _ctx(known_since=later))["signals_fenced"] == 1

    def test_an_unparseable_instant_proves_no_ordering(self):
        """MUTANT M9: make ``_iso_lt`` return True on a parse failure.

        A garbage timestamp must not be able to prove a signal is old.
        """
        assert EL._iso_lt("not-a-date", T2) is False
        assert EL._iso_lt(T1, "not-a-date") is False
        ev = _proposed(157, ts="16/08/2026")
        ev["ts"] = "16/08/2026"
        assert _leg([ev], {SID: {}}, _ctx())["signals_fenced"] == 0


class TestWhatDoesFence:
    """The other direction: the fence must actually fire on proven history, or
    the CEO's page keeps shouting about a dead engine."""

    def test_the_live_record_fences_and_the_verdict_is_not_a_divergence(self):
        """The brief's acceptance (i), on the shape of the real row.

        Nothing running, the runner's memory younger than the signal, strategy
        archived. The verdict must NOT read as a live divergence and must NOT
        read as agreement either.
        """
        leg = _leg(DEAD_HISTORY, {SID: {}}, _ctx(archived=[SID]))
        assert leg["verdict"]["state"] == "fenced_history"
        assert leg["implied"]["symbols_out_of_sync"] == 0
        assert leg["implied"]["symbols_fenced"] == 1
        assert leg["signals_fenced"] == 1
        assert leg["signals_live"] == 0

    def test_fenced_is_its_own_state_and_never_in_sync(self):
        """The brief's acceptance (iii). MUTANT M10: let a fenced key net to
        zero and compare 0 vs 0.

        A fenced row has NO live engine behind it, so its live implied quantity
        is ABSENT. Zero would be a measured claim that a live engine holds
        nothing here, and it would compare equal to a flat book — printing
        agreement where nothing was compared.
        """
        row, = _leg(DEAD_HISTORY, {SID: {}},
                    _ctx(archived=[SID]))["implied"]["per_symbol"]
        assert row["sync_state"] == "fenced_history"
        assert row["in_sync"] is None
        assert row["engine_implied_qty"] is None
        assert row["drift"] is None

    def test_the_fenced_quantity_is_preserved_not_deleted(self):
        """The clean-field rule's guard rail 2, applied here: the contaminated
        value is kept BESIDE the new one, never erased. MUTANT M11: drop
        ``fenced_implied_qty``.

        Without this the page could only say "there was history"; with it the
        page can say what the dead engine had asked for.
        """
        row, = _leg(DEAD_HISTORY, {SID: {}},
                    _ctx(archived=[SID]))["implied"]["per_symbol"]
        assert row["fenced_implied_qty"] == 0.1
        assert row["signals_fenced"] == 1
        assert row["signals_live"] == 0

    def test_the_reason_is_derived_from_the_record_not_from_the_symbol(self):
        """The fence reason must be derivable from the record — never
        hardcoded to GLD. MUTANT M12: hardcode the reason or key it on symbol.

        Same events with a DIFFERENT symbol and strategy fence identically, and
        an unarchived strategy fences on the session ground alone with the
        archived clause absent from the sentence.
        """
        events = [_proposed(9, sid=OTHER, symbol="HYG", algo="hyg_fast_flip_probe")]
        leg = _leg(events, {OTHER: {}}, _ctx())
        row, = leg["implied"]["per_symbol"]
        assert row["symbol"] == "HYG"
        assert row["sync_state"] == "fenced_history"
        assert "ARCHIVED" not in row["fence_reason"]
        assert "session" in row["fence_reason"]
        # ...and with the strategy archived the SAME row gains the clause.
        arch, = _leg(events, {OTHER: {}},
                     _ctx(archived=[OTHER]))["implied"]["per_symbol"]
        assert arch["fence_reason"].startswith("the strategy is ARCHIVED")

    def test_the_fence_reason_is_a_whole_sentence(self):
        """FOUND BY LOOKING AT THE RENDERED PAGE, not by any suite. The engine
        page joins this reason to a follow-up sentence of its own, and without
        the full stop it read "...the paper book it moved, are gone The dead
        session had asked for 0.1". A fold that emits half-sentences makes
        punctuation the caller's problem, and the caller gets it wrong.
        """
        for arch_ids in ([], [SID]):
            r, = _leg(DEAD_HISTORY, {SID: {}},
                      _ctx(archived=arch_ids))["implied"]["per_symbol"]
            assert r["fence_reason"].endswith("."), r["fence_reason"]

    def test_archiving_alone_does_not_fence(self):
        """MUTANT M13: return FENCED as soon as the strategy is archived.

        Archiving is a label a human applied; it is not evidence that the
        container stopped. An archived strategy whose orphan is still
        signalling must still read DIVERGED, and the ordering in
        ``signal_liveness`` is what guarantees it.
        """
        ctx = _ctx(sessions=[_session()], archived=[SID])
        assert _leg(DEAD_HISTORY, {SID: {}}, ctx)["signals_fenced"] == 0


class TestMixedHistory:
    """One (strategy, symbol) carrying both a dead session's signals and a live
    one's. The interesting case, and the one a per-symbol fence would get
    wrong."""

    def _mixed(self):
        # An old buy from a session that is gone, and a newer buy from the
        # session that IS running.
        old = _proposed(10, qty=5, ts=T1, oid="old")
        new = _proposed(20, qty=2, ts=T2 + "", oid="new")
        new["ts"] = "2026-08-21T00:00:00+00:00"
        return [old, new]

    def test_only_the_live_signals_move_the_number_that_is_judged(self):
        """MUTANT M14: net fenced and live signals into one implied book.

        The engine's container started on 2026-08-20 holding NOTHING. Only the
        qty-2 buy after that moved its book. Netting the old 5 in would judge a
        live engine against five units it demonstrably does not hold.
        """
        ctx = _ctx(sessions=[_session(started="2026-08-20T00:00:00+00:00")],
                   known_since=T2)
        row, = _leg(self._mixed(), {SID: {}}, ctx)["implied"]["per_symbol"]
        assert row["engine_implied_qty"] == 2.0
        assert row["fenced_implied_qty"] == 5.0
        assert row["signals_live"] == 1
        assert row["signals_fenced"] == 1
        # The row is LIVE — one live signal is enough to make it judgeable.
        assert row["sync_state"] == "diverged"
        assert row["drift"] == 2.0

    def test_a_fenced_signals_absent_quantity_does_not_poison_the_live_row(self):
        """MUTANT M35: ``unquantified.add(key)`` regardless of the fence.

        An unsized signal from a DEAD session makes the dead engine's book
        unknown; it says nothing about the live one. Marking the live row
        undetermined would take a divergence a live engine is genuinely
        showing and print "cannot be compared" over it - a fence silencing a
        live disagreement by the back door, which is the one thing this
        mechanism must never do.
        """
        old = _proposed(10, qty=None, ts=T1, oid="old")
        old["payload"]["qty"] = None
        new_ = _proposed(20, qty=4, oid="new")
        new_["ts"] = "2026-08-21T00:00:00+00:00"
        ctx = _ctx(sessions=[_session(started="2026-08-20T00:00:00+00:00")],
                   known_since=T2)
        row, = _leg([old, new_], {SID: {}}, ctx)["implied"]["per_symbol"]
        assert row["implied_unquantified"] is False
        assert row["engine_implied_qty"] == 4.0
        assert row["sync_state"] == "diverged"
        # ...and the same signal, LIVE, does make the row undetermined - so
        # the assertion above is about the FENCE, not about qty=None.
        live_ctx = _ctx(sessions=[_session(started=T0)], known_since=T0)
        row2, = _leg([old, new_], {SID: {}}, live_ctx)["implied"]["per_symbol"]
        assert row2["implied_unquantified"] is True
        assert row2["engine_implied_qty"] is None

    def test_the_signal_counts_still_cover_every_signal(self):
        """A fenced signal is still a signal. MUTANT M15: count only live
        signals into ``signals.raised``.

        The fate bucket is a different axis from liveness, and a reader who is
        shown "1 raised" over a symbol with two signals has been shown a
        smaller record than exists.
        """
        row, = _leg(self._mixed(), {SID: {}},
                    _ctx(sessions=[_session(started="2026-08-20T00:00:00+00:00")])
                    )["implied"]["per_symbol"]
        assert row["signals"]["raised"] == 2
        assert row["signals_live"] + row["signals_fenced"] == 2


class TestTheVerdict:
    def test_a_live_divergence_outranks_any_number_of_fenced_rows(self):
        """MUTANT M16: check ``fenced_history`` before ``diverged``.

        The ordering is the whole safety property: a fenced row must never be
        able to suppress a live disagreement, however many of them there are.
        """
        events = [
            _proposed(10, symbol="GLD", ts=T1),                    # fenced
            _proposed(11, symbol="DBA", ts=T1),                    # fenced
            _proposed(20, symbol="HYG", sid=OTHER, algo="hyg_fast_flip_probe",
                      ts="2026-08-21T00:00:00+00:00"),             # live
        ]
        ctx = _ctx(sessions=[_session(sid=OTHER, algo="hyg_fast_flip_probe",
                                      started=T2)])
        leg = _leg(events, {SID: {}, OTHER: {}}, ctx)
        assert leg["verdict"]["state"] == "diverged"
        assert leg["verdict"]["symbols"] == ["HYG"]
        # ...and the fenced rows are NAMED in the same sentence, so the number
        # never arrives without its domain.
        assert "2 symbols are FENCED HISTORY" in leg["verdict"]["sentence"]

    def test_an_undetermined_live_row_outranks_a_fenced_one(self):
        """MUTANT M17: reach ``fenced_history`` while a live row is
        undetermined. An unreadable book is not a resolved question."""
        class _Boom:
            def positions_by_strategy(self):
                raise RuntimeError("book down")

        events = [_proposed(10, ts=T1),
                  _proposed(20, sid=OTHER, symbol="HYG",
                            algo="hyg_fast_flip_probe",
                            ts="2026-08-21T00:00:00+00:00")]
        ctx = _ctx(sessions=[_session(sid=OTHER, algo="hyg_fast_flip_probe",
                                      started=T2)])
        leg = EL.engine_leg(_Store(events), attribution=_Boom(), context=ctx)
        assert leg["verdict"]["state"] == "unknown"
        assert "1 symbol is FENCED HISTORY" in leg["verdict"]["sentence"]

    def test_in_sync_counts_only_live_rows(self):
        """MUTANT M18: let ``in_sync``'s sentence count fenced rows too.

        "All 2 symbols agree" over one live agreement and one fenced row is a
        claim about a comparison that was never made.
        """
        events = [_proposed(10, symbol="GLD", ts=T1),               # fenced
                  _proposed(20, sid=OTHER, symbol="HYG", qty=3,
                            algo="hyg", ts="2026-08-21T00:00:00+00:00")]
        ctx = _ctx(sessions=[_session(sid=OTHER, algo="hyg", started=T2)])
        leg = _leg(events, {OTHER: {"HYG": 3}}, ctx)
        assert leg["verdict"]["state"] == "in_sync"
        assert leg["verdict"]["sentence"].startswith("All 1 symbol ")
        assert "1 symbol is FENCED HISTORY" in leg["verdict"]["sentence"]

    def test_the_four_way_partition_is_counted_directly(self):
        """Every row lands in exactly one of four states, and all four are
        counted from the rows rather than one taken as a remainder — a
        partition computed as "everything else" makes its own exhaustiveness
        test a tautology (HW1)."""
        events = [_proposed(10, symbol="GLD", ts=T1),
                  _proposed(20, sid=OTHER, symbol="HYG", qty=3, algo="hyg",
                            ts="2026-08-21T00:00:00+00:00")]
        ctx = _ctx(sessions=[_session(sid=OTHER, algo="hyg", started=T2)])
        im = _leg(events, {OTHER: {"HYG": 3}}, ctx)["implied"]
        total = (im["symbols_out_of_sync"] + im["symbols_undetermined"]
                 + im["symbols_in_sync"] + im["symbols_fenced"])
        assert total == len(im["per_symbol"]) == 2


class TestTheLedgerSide:
    def test_without_a_context_the_fenced_count_is_absent_not_zero(self):
        """MUTANT M19: default ``fenced`` to 0 when no context is supplied.

        A ledger read with no way to ask what is running has not established
        that nothing is fenced. It has not asked, and ``None`` is the only
        honest rendering of that.
        """
        led = EL.signal_ledger(_Store(DEAD_HISTORY))
        assert led["fenced"] is None
        assert led["live"] is None
        assert led["fence"] is None
        assert "fenced" not in led["signals"][0]

    def test_with_a_context_every_row_carries_its_basis(self):
        led = EL.signal_ledger(_Store(DEAD_HISTORY), context=_ctx(archived=[SID]))
        assert led["fenced"] == 1 and led["live"] == 0
        row, = led["signals"]
        assert row["fenced"] is True
        assert row["liveness"]["basis"] == EL.BASIS_PREDATES_SESSION_MEMORY

    def test_the_fate_buckets_are_untouched_by_the_fence(self):
        """MUTANT M20: add ``fenced`` to ``counts``.

        Liveness is orthogonal to fate — a fenced signal was still refused. A
        sixth bucket would break ``sum(counts) == total`` and, worse, make
        "refused" and "fenced" read as alternatives.
        """
        led = EL.signal_ledger(_Store(DEAD_HISTORY), context=_ctx(archived=[SID]))
        assert sum(led["counts"].values()) == led["total"] == 1
        assert led["counts"]["refused"] == 1
        assert "fenced" not in led["counts"]

    def test_the_fence_writes_nothing(self):
        store = _Store(DEAD_HISTORY)
        EL.engine_leg(store, attribution=_Attribution({SID: {}}),
                      context=_ctx(archived=[SID]))
        EL.signal_ledger(store, context=_ctx(archived=[SID]))
        assert store.appended == []


class TestTheContext:
    def test_an_absent_context_reports_every_input_unreadable(self):
        """``EngineContext()`` with no arguments is not an empty world — it is
        an unread one, and it must fence nothing."""
        ctx = EL.EngineContext()
        d = ctx.describe()
        assert d["sessions_readable"] is False
        assert d["sessions"] is None and d["sessions_running"] is None
        assert d["archived_readable"] is False
        assert d["archived_strategies"] is None
        assert d["sessions_known_since"] is None
        assert EL.engine_leg(_Store(DEAD_HISTORY),
                             attribution=_Attribution({SID: {}}),
                             context=ctx)["signals_fenced"] == 0

    def test_an_OMITTED_context_is_unreadable_in_both_folds(self):
        """MUTANTS M31 and M39: default the missing context to
        ``EngineContext(sessions=[])``.

        The test above passes a context explicitly, so it cannot see this: the
        mutant only bites when a caller supplies NONE. A default of "readable,
        and nothing is running" would let any caller that forgot the argument
        fence the fund's whole history — the omitted-argument path being
        exactly the one nobody looks at.
        """
        leg = EL.engine_leg(_Store(DEAD_HISTORY),
                            attribution=_Attribution({SID: {}}))
        assert leg["fence"]["sessions_readable"] is False
        assert leg["signals_fenced"] == 0
        assert leg["verdict"]["state"] == "diverged"

        cards = EL.engine_strategies([LEAN_HYG], ledger=None,
                                     algorithm_source=lambda n: None,
                                     datasource_reader=declared_datasource)
        # An unreadable session list makes "is it running" UNKNOWN, not "none".
        assert cards["strategies"][0]["session_state"] is None

    def test_an_empty_session_list_is_not_an_unreadable_one(self):
        """The distinction the whole class exists for: ``[]`` is a claim,
        ``None`` is the absence of one, and they lead to OPPOSITE verdicts."""
        empty = _ctx(sessions=[]).describe()
        unread = _ctx(sessions=None).describe()
        assert empty["sessions_readable"] is True and empty["sessions"] == 0
        assert unread["sessions_readable"] is False and unread["sessions"] is None

    def test_a_blank_known_since_is_the_same_as_an_absent_one(self):
        assert _ctx(known_since="   ").describe()["sessions_known_since"] is None


# ================================================== the runner's own anchor

class TestSessionsKnownSince:
    def test_the_anchor_moves_with_the_runner_it_describes(self, tmp_path):
        """PROVE IT IS READ, NOT COPIED — by MOVING it. An assertion that the
        fence's anchor merely EQUALS the runner's timestamp cannot tell a real
        read from a hardcoded duplicate that happens to agree today.

        Two runners built a measurable interval apart must report two different
        anchors, and a signal between them must fence against the LATER one and
        not against the earlier.
        """
        import time
        from app.fund.leanrunner import LeanRunner
        a = LeanRunner(workspace=tmp_path / "a")
        time.sleep(0.01)
        b = LeanRunner(workspace=tmp_path / "b")
        assert a.sessions_known_since() < b.sessions_known_since()

        between = a.sessions_known_since()
        ev = _proposed(1, ts=between)
        ev["ts"] = between
        assert _leg([ev], {SID: {}},
                    _ctx(known_since=a.sessions_known_since()))["signals_fenced"] == 0
        assert _leg([ev], {SID: {}},
                    _ctx(known_since=b.sessions_known_since()))["signals_fenced"] == 1

    def test_a_fresh_runner_has_no_sessions_to_know_about(self, tmp_path):
        from app.fund.leanrunner import LeanRunner
        r = LeanRunner(workspace=tmp_path)
        assert r.live_sessions() == []
        assert r.sessions_known_since()


# ============================================================ the datasource

class TestDeclaredDatasource:
    ALGO = '''
from AlgorithmImports import *
SPINE = "http://host.docker.internal:8090/api/v1/fund"
UNIVERSE = ["HYG"]
# a comment that lies: lookback_days=1200
class SpineBars(PythonData):
    def get_source(self, config, dt_, is_live):
        url = (f"{SPINE}/marketdata/bars?symbol={config.symbol.value}"
               f"&lookback_days=2000&format=csv")
        return SubscriptionDataSource(url, SubscriptionTransportMedium.REMOTE_FILE)
class HygFastFlipProbe(QCAlgorithm):
    def initialize(self):
        sec = self.add_data(SpineBars, UNIVERSE[0], Resolution.DAILY)
'''

    def test_it_reads_every_field_from_the_source(self):
        d = declared_datasource(self.ALGO)
        assert d["readable"] is True
        assert d["class_name"] == "SpineBars"
        assert d["base"] == "PythonData"
        assert d["resolution"] == "daily"
        assert d["transport"] == "REMOTE_FILE"
        assert d["feed_path"] == "/marketdata/bars"
        assert d["feed_origin"] == "http://host.docker.internal:8090/api/v1/fund"
        assert d["format"] == "csv"
        assert d["symbols"] == ["HYG"]

    def test_the_comment_that_lies_is_not_read(self):
        """FROM THE AST, NOT THE TEXT. The source above carries
        ``lookback_days=1200`` in a COMMENT above a URL that asks for 2000 —
        the exact shape that cost the bar cache its one real candidate. A text
        scan would see two lookbacks; the tree sees one.
        """
        assert declared_datasource(self.ALGO)["lookback_days"] == 2000

    #: A SECOND, CONTRADICTING bar URL - and it must be VALID PYTHON. The
    #: first version of this fixture spliced a line inside an open
    #: parenthesis, so the module did not parse and the assertion below passed
    #: on the SYNTAX-ERROR path instead of the two-URL path. It survived
    #: mutation M21 and looked green the whole time it was testing nothing.
    TWO_URLS = ALGO + (
        '\nALT = "http://elsewhere/marketdata/bars'
        '?lookback_days=700&format=json"\n')

    def test_the_two_url_fixture_actually_parses(self):
        """THE FIXTURE'S OWN NULL TEST, and it is not ceremony: the check below
        is worthless if the source does not parse, and that is exactly how it
        failed once. A fixture that cannot reach the branch it targets is a
        green test with no subject."""
        import ast
        ast.parse(self.TWO_URLS)
        assert declared_datasource(self.TWO_URLS)["readable"] is True

    def test_two_contradicting_urls_report_absent_rather_than_a_guess(self):
        """MUTANT M21: return the first match instead of requiring exactly one.
        A datasource this fund guessed at is worse than no panel at all - and
        the wrong number here is PLAUSIBLE, which is what makes it dangerous."""
        d = declared_datasource(self.TWO_URLS)
        assert d["lookback_days"] is None
        assert d["format"] is None

    def test_a_qcalgorithm_class_is_never_reported_as_a_feed(self):
        """MUTANT M22: accept any class as the data class. ``PythonData`` is
        the base LEAN's custom feeds derive from; the algorithm class is not a
        feed and labelling it one would be a confident falsehood."""
        no_feed = "from AlgorithmImports import *\nclass A(QCAlgorithm):\n    pass\n"
        d = declared_datasource(no_feed)
        assert d["class_name"] is None
        assert d["readable"] is False
        assert "UNKNOWN" in d["reason"]

    @pytest.mark.parametrize("code", [None, "", "def ("])
    def test_unreadable_source_is_absent_with_a_reason(self, code):
        d = declared_datasource(code)
        assert d["readable"] is False
        assert d["reason"]
        assert all(d[k] is None for k in
                   ("class_name", "base", "resolution", "transport",
                    "feed_path", "feed_origin", "lookback_days", "format"))

    def test_the_algorithm_class_is_not_the_data_class(self):
        """The two names live in one file and a card showing one under the
        other's label would be quietly wrong."""
        assert declared_algorithm_class(self.ALGO) == "HygFastFlipProbe"
        assert declared_datasource(self.ALGO)["class_name"] == "SpineBars"
        assert declared_algorithm_class(None) is None
        assert declared_algorithm_class("no class here") is None


# =============================================================== the cards

def _strategy(sid, name, definition, *, assets=(), state="draft",
              archived=False, alloc=0.0):
    return {"strategy_id": sid, "name": name, "definition": definition,
            "assets": list(assets), "state": state, "archived": archived,
            "allocation_pct": alloc}


LEAN_GLD = _strategy(SID, "LEAN - GLD 100d SMA filter",
                     {"engine": "lean", "algorithm": "gld_sma_filter",
                      "rule": "long above 100d SMA, cash below",
                      "symbol": "GLD", "signal_only": True},
                     archived=True)
LEAN_HYG = _strategy(OTHER, "LEAN - HYG fast flip probe",
                     {"engine": "lean", "algorithm": "hyg_fast_flip_probe",
                      "rule": "hold HYG while fast>slow", "class": "HygFastFlipProbe",
                      "universe": ["HYG"], "claim_type": "alpha"},
                     assets=["HYG"])
MANUAL = _strategy("sleeve_x", "Sleeve - equity risk premium (SPY)",
                   {"claim_type": "premia", "instrument": "SPY"},
                   assets=["SPY"], state="deployed", alloc=50.0)


def _cards(strategies, ledger=None, ctx=None, source=None):
    return EL.engine_strategies(
        strategies, ledger=ledger, context=ctx if ctx is not None else _ctx(),
        algorithm_source=source or (lambda n: None),
        datasource_reader=declared_datasource)


class TestEngineStrategyCards:
    def test_only_engine_strategies_get_a_card(self):
        """MUTANT M23: select on the NAME prefix instead of
        ``definition.engine``. ``"LEAN - …"`` is a habit, not a contract, and
        ``"TEST - Fast Intraday (5m SMA)"`` shows the habit is not even
        consistent."""
        out = _cards([MANUAL, LEAN_GLD, LEAN_HYG])
        assert out["total"] == 2
        assert {c["strategy_id"] for c in out["strategies"]} == {SID, OTHER}
        assert out["engines"] == ["lean"]

    def test_an_unreadable_registry_is_not_an_empty_bench(self):
        out = _cards(None)
        assert out["readable"] is False
        assert out["total"] is None
        assert out["archived"] is None
        assert "UNKNOWN" in out["reason"]

    def test_archived_strategies_are_labelled_and_sorted_last(self):
        """The CEO archived one of these today. It stays visible — an archived
        engine strategy is the record of what ran, and hiding it would leave
        the fenced GLD row on the reconcile panel with nothing to point at."""
        out = _cards([LEAN_GLD, LEAN_HYG])
        assert [c["archived"] for c in out["strategies"]] == [False, True]
        assert out["archived"] == 1

    def test_assets_fall_back_through_three_fields_and_name_which_one(self):
        """MEASURED ON THE LIVE RECORD: the HYG probe carries ``assets`` on the
        row; the GLD filter carries ``assets: []`` and only
        ``definition.symbol``. Reading only the first would print "no assets"
        for a strategy whose symbol is two fields away.
        """
        out = _cards([LEAN_GLD, LEAN_HYG])
        by_id = {c["strategy_id"]: c for c in out["strategies"]}
        assert by_id[OTHER]["assets"] == ["HYG"]
        assert by_id[OTHER]["assets_basis"] == "strategy.assets"
        assert by_id[SID]["assets"] == ["GLD"]
        assert by_id[SID]["assets_basis"] == "definition.symbol"

    def test_a_universe_definition_is_read_when_the_row_has_no_assets(self):
        s = _strategy("s", "n", {"engine": "lean", "universe": ["hyg", " spy "]})
        c, = _cards([s])["strategies"]
        assert c["assets"] == ["HYG", "SPY"]
        assert c["assets_basis"] == "definition.universe"

    def test_no_asset_anywhere_is_absent_not_empty_by_accident(self):
        """MUTANT M24: return ``[]`` with a basis. An empty list WITH a basis
        claims a field was read and found empty; ``None`` says no field
        answered."""
        c, = _cards([_strategy("s", "n", {"engine": "lean"})])["strategies"]
        assert c["assets"] == []
        assert c["assets_basis"] is None

    def test_the_datasource_is_read_from_the_algorithm_file(self):
        src = {"gld_sma_filter": TestDeclaredDatasource.ALGO}
        c, = _cards([LEAN_GLD], source=src.get)["strategies"]
        assert c["datasource"]["lookback_days"] == 2000
        assert c["datasource"]["class_name"] == "SpineBars"
        assert c["class_name"] == "HygFastFlipProbe"   # from the FILE

    def test_the_definitions_class_is_carried_separately_never_merged(self):
        """MUTANT M25: ``declared_algorithm_class(code) or definition['class']``.

        An ``or`` would hide a definition that has drifted from its file behind
        a plausible name. The two are shown side by side so the drift is
        visible.
        """
        c, = _cards([LEAN_HYG], source=lambda n: None)["strategies"]
        assert c["class_name"] is None                       # the file is absent
        assert c["class_in_definition"] == "HygFastFlipProbe"

    def test_a_missing_algorithm_file_is_unreadable_with_a_reason(self):
        def boom(name):
            raise RuntimeError(f"unknown algorithm {name!r}")
        c, = _cards([LEAN_GLD], source=boom)["strategies"]
        assert c["datasource"]["readable"] is False
        assert "could not be read" in c["datasource"]["reason"]
        assert "gld_sma_filter" in c["datasource"]["reason"]

    def test_a_definition_with_no_algorithm_says_so(self):
        s = _strategy("s", "n", {"engine": "lean", "rule": "something"})
        c, = _cards([s])["strategies"]
        assert c["algorithm"] is None
        assert "names no algorithm" in c["datasource"]["reason"]

    def test_the_last_signal_and_its_fate_ride_on_the_card(self):
        led = EL.signal_ledger(_Store(DEAD_HISTORY), context=_ctx(archived=[SID]))
        c, = _cards([LEAN_GLD], ledger=led)["strategies"]
        assert c["signals"]["raised"] == 1
        assert c["signals"]["refused"] == 1
        assert c["signals_fenced"] == 1
        assert c["last_signal"]["order_id"] == "e035957c"
        assert c["last_signal"]["outcome"] == "refused"

    def test_the_last_signal_is_the_newest_one(self):
        """MUTANT M26: take ``mine[-1]``. The ledger is newest-first, so the
        last element is the OLDEST signal — a card headlining a stale reason
        while a newer one sits above it."""
        events = [_proposed(10, ts=T1, oid="old"),
                  _proposed(20, ts="2026-08-21T00:00:00+00:00", oid="new")]
        led = EL.signal_ledger(_Store(events), context=_ctx())
        c, = _cards([LEAN_GLD], ledger=led)["strategies"]
        assert c["last_signal"]["order_id"] == "new"

    def test_a_strategy_that_has_never_signalled_shows_zero_not_absent(self):
        """A strategy with no signals in a COMPLETE ledger has genuinely
        raised none — a measured zero. ``last_signal`` is ``None`` because
        there is no row, which is a different fact and gets a different
        field."""
        led = EL.signal_ledger(_Store([]), context=_ctx())
        c, = _cards([LEAN_HYG], ledger=led)["strategies"]
        assert c["signals"]["raised"] == 0
        assert c["last_signal"] is None

    def test_a_running_session_is_matched_to_its_card(self):
        ctx = _ctx(sessions=[_session(sid=OTHER, algo="hyg_fast_flip_probe")])
        out = _cards([LEAN_GLD, LEAN_HYG], ctx=ctx)
        by_id = {c["strategy_id"]: c for c in out["strategies"]}
        assert by_id[OTHER]["session_state"] == "running"
        assert by_id[SID]["session_state"] == "none"
        assert out["sessions_unmatched"] == []

    def test_a_session_no_card_accounts_for_is_named(self):
        """MUTANT M27: drop ``sessions_unmatched``.

        A live session the strategy registry cannot explain is the loudest
        thing this payload can carry — it is the same orphan evidence the fence
        refuses to read as death, and it must not vanish just because no card
        claimed it.
        """
        ctx = _ctx(sessions=[_session(sid="ghost", algo="unknown_algo")])
        out = _cards([LEAN_GLD, LEAN_HYG], ctx=ctx)
        assert len(out["sessions_unmatched"]) == 1
        assert out["sessions_unmatched"][0]["strategy_id"] == "ghost"

    def test_an_unreadable_session_list_makes_session_state_unknown(self):
        """MUTANT M28: report ``"none"`` when the list could not be read.
        ``None`` is "we could not ask"; ``"none"`` is "we asked and nothing is
        running"."""
        c, = _cards([LEAN_HYG], ctx=_ctx(sessions=None))["strategies"]
        assert c["session_state"] is None

    def test_the_signal_buckets_sum_to_the_raised_count(self):
        events = [_proposed(10, oid="a"), _declined(11, "a"),
                  _proposed(12, oid="b")]
        led = EL.signal_ledger(_Store(events), context=_ctx())
        c, = _cards([LEAN_GLD], ledger=led)["strategies"]
        assert sum(v for k, v in c["signals"].items() if k != "raised") == 2
        assert c["signals"]["raised"] == 2

    def test_the_definition_keys_are_named_so_the_card_is_not_mistaken_for_all(self):
        c, = _cards([LEAN_HYG])["strategies"]
        assert "claim_type" in c["definition_keys"]
        assert "universe" in c["definition_keys"]


# ============================================================== the endpoint

class _Lean:
    """A runner complete enough to be ASKED the fence's questions.

    The pre-existing fake in ``test_engineledger.py`` has neither
    ``sessions_known_since`` nor ``get_algorithm``, so the endpoint's guards
    swallow an AttributeError and the fence proves nothing — which is correct
    fail-safe behaviour and is exactly why it cannot be the fixture that proves
    the fence WORKS. A test whose subject is degraded away is a test that
    cannot fail for the right reason.
    """

    def __init__(self, sessions=(), known_since=T2, algorithms=None,
                 raises=None):
        self._sessions = list(sessions)
        self._known_since = known_since
        self._algorithms = algorithms or {}
        self._raises = raises

    def live_sessions(self):
        if self._raises:
            raise self._raises
        return list(self._sessions)

    def sessions_known_since(self):
        return self._known_since

    def get_algorithm(self, name):
        if name not in self._algorithms:
            raise RuntimeError(f"unknown algorithm {name!r}")
        return {"name": name, "code": self._algorithms[name]}


class _Strategies:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def list(self):
        return [dict(r) for r in self._rows]

    def get(self, sid):
        for r in self._rows:
            if r["strategy_id"] == sid:
                return dict(r)
        from app.fund.strategies import StrategyError
        raise StrategyError(f"unknown strategy {sid}")


def _client(monkeypatch, events, *, sessions=(), known_since=T2, rows=(),
            algorithms=None, positions=None, lean_raises=None,
            strategies_raise=False, drift=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1 import fund as fundapi

    strategies = _Strategies(rows)
    if strategies_raise:
        def _boom():
            raise RuntimeError("registry down")
        strategies.list = _boom
    monkeypatch.setattr(fundapi, "_store", _Store(events))
    monkeypatch.setattr(fundapi, "_attribution", _Attribution(positions or {}))
    monkeypatch.setattr(fundapi, "_strategies", strategies)
    monkeypatch.setattr(fundapi, "_reconciler",
                        type("R", (), {"drift": staticmethod(
                            lambda: dict(drift or {"configured": True}))})())
    monkeypatch.setattr(fundapi, "_lean", lambda: _Lean(
        sessions, known_since, algorithms, lean_raises))
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


class TestTheEndpoint:
    def test_the_live_shape_reads_fenced_history_not_diverged(self, monkeypatch):
        """THE WHOLE POINT, ON THE WIRE. The fund's own record — one declined
        GLD signal from a dead session on an archived strategy — must not
        render as a live divergence on the page the CEO opens."""
        c = _client(monkeypatch, DEAD_HISTORY, rows=[LEAN_GLD],
                    positions={SID: {}})
        body = c.get("/api/v1/fund/engine").json()
        assert body["reconcile"]["verdict"]["state"] == "fenced_history"
        assert body["reconcile"]["signals_fenced"] == 1
        assert body["ledger"]["fenced"] == 1
        row, = body["reconcile"]["implied"]["per_symbol"]
        assert row["sync_state"] == "fenced_history"
        assert row["fenced_implied_qty"] == 0.1

    def test_a_live_session_on_the_wire_still_reads_diverged(self, monkeypatch):
        """The brief's acceptance (ii), end to end and through the real
        endpoint rather than through the fold alone."""
        c = _client(monkeypatch, DEAD_HISTORY, rows=[LEAN_GLD],
                    positions={SID: {}}, sessions=[_session()])
        body = c.get("/api/v1/fund/engine").json()
        assert body["reconcile"]["verdict"]["state"] == "diverged"
        assert body["ledger"]["fenced"] == 0

    def test_an_unreachable_runner_fences_nothing(self, monkeypatch):
        """Docker down. ``live_sessions`` raises, the context reports the list
        unreadable, and the divergence stays visible."""
        c = _client(monkeypatch, DEAD_HISTORY, rows=[LEAN_GLD],
                    positions={SID: {}}, lean_raises=RuntimeError("docker gone"))
        body = c.get("/api/v1/fund/engine").json()
        assert body["reconcile"]["fence"]["sessions_readable"] is False
        assert body["reconcile"]["verdict"]["state"] == "diverged"
        assert body["status"]["sessions_error"]

    def test_one_request_reads_the_session_list_once(self, monkeypatch):
        """MUTANT M29: let ``_engine_context`` read the sessions itself inside
        ``engine_view``.

        The fence's answer depends on what is running. Two reads inside one
        response could fence a signal in the ledger and not in the leg — one
        payload, two truths, which is the defect the single-fold rule already
        closed for the event stream.
        """
        from app.api.v1 import fund as fundapi
        c = _client(monkeypatch, DEAD_HISTORY, rows=[LEAN_GLD],
                    positions={SID: {}})
        calls = []
        real = fundapi._live_sessions_or_none

        def counting():
            calls.append(1)
            return real()
        monkeypatch.setattr(fundapi, "_live_sessions_or_none", counting)
        c.get("/api/v1/fund/engine")
        assert len(calls) == 1

    def test_the_strategy_cards_ride_on_the_same_response(self, monkeypatch):
        """One call for one page: the cards must not need a second round trip,
        or the page renders two different moments."""
        c = _client(monkeypatch, DEAD_HISTORY,
                    rows=[MANUAL, LEAN_GLD, LEAN_HYG], positions={SID: {}},
                    algorithms={"gld_sma_filter": TestDeclaredDatasource.ALGO})
        body = c.get("/api/v1/fund/engine").json()
        cards = body["strategies"]
        assert cards["readable"] is True
        assert cards["total"] == 2                 # the manual sleeve excluded
        by_id = {c_["strategy_id"]: c_ for c_ in cards["strategies"]}
        assert by_id[SID]["datasource"]["lookback_days"] == 2000
        assert by_id[SID]["datasource"]["class_name"] == "SpineBars"
        assert by_id[OTHER]["datasource"]["readable"] is False

    def test_an_unreadable_registry_does_not_take_the_page_down(self, monkeypatch):
        """A reporting panel must not be able to break the page the CEO opens
        to see what LEAN is doing."""
        c = _client(monkeypatch, DEAD_HISTORY, positions={SID: {}},
                    strategies_raise=True)
        r = c.get("/api/v1/fund/engine")
        assert r.status_code == 200
        body = r.json()
        assert body["strategies"]["readable"] is False
        assert body["strategies"]["total"] is None
        # ...and with the registry unreadable, ARCHIVED is unknown too, so the
        # fence loses one ground and must not silently keep using it.
        assert body["reconcile"]["fence"]["archived_readable"] is False

    def test_the_reconcile_endpoint_gains_the_fence_too(self, monkeypatch):
        """``/fund/venue/reconcile`` composes the same leg, so it must reach
        the same verdict — two surfaces disagreeing about one book is the
        thing this module exists to prevent."""
        c = _client(monkeypatch, DEAD_HISTORY, rows=[LEAN_GLD],
                    positions={SID: {}},
                    drift={"configured": True, "book_nav": 1999.01})
        body = c.get("/api/v1/fund/venue/reconcile").json()
        assert body["configured"] is True
        assert body["engine"]["verdict"]["state"] == "fenced_history"

    def test_the_endpoint_writes_nothing(self, monkeypatch):
        from app.api.v1 import fund as fundapi
        store = _Store(DEAD_HISTORY)
        c = _client(monkeypatch, DEAD_HISTORY, rows=[LEAN_GLD],
                    positions={SID: {}})
        monkeypatch.setattr(fundapi, "_store", store)
        c.get("/api/v1/fund/engine")
        c.get("/api/v1/fund/venue/reconcile")
        assert store.appended == []
