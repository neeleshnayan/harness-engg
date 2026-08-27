"""THE SIXTH BASIS — a ROW is fenced on the ENGINE, not on the SIGNAL.

**THE DEFECT** (run-adversary-night2, probe ``scratchpad/advn2/p7_fence.py``).
``engineledger`` fenced a per-symbol row with one expression —
``fenced_row = (n_live == 0)`` — and justified it with *"there is no live
engine to hold anything"*. Those are two different facts:

  * ``n_live == 0`` measures **no live SIGNAL on this key**;
  * the justification claims **no live ENGINE for this strategy**.

Where a live session EXISTS for the strategy and has simply not signalled on
this symbol, they point opposite ways. This module's own published model says
*"a LEAN container starts FLAT"* — so a live session that has raised nothing
here holds a **measured ZERO**, and a fund book that disagrees with zero is a
**LIVE divergence**, not history. The old rule fenced it, which took a real
divergence off the verdict.

**DIRECTION.** Un-fencing is the STRICT direction: every row still fenced was
fenced before, and three classes that were fenced are not. The file's sibling
``test_engine_fence.py`` guards the loosening direction (nothing live is ever
fenced); this one guards the conflation.

A separate file rather than an addition to that one, because these tests need a
fixture where the SIGNAL is legitimately fenced and the SESSION is legitimately
live — the exact combination the old rule could not represent.
"""
import pytest

from app.fund import engineledger as EL

T0 = "2026-08-10T00:00:00+00:00"     # the signal, and the epoch's ancestor
T1 = "2026-08-16T18:59:52+00:00"     # the registry epoch
T2 = "2026-08-20T00:00:00+00:00"     # the live session started here
SID = "strat-gld"
OTHER = "strat-hyg"


class _Store:
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


def _proposed(seq, *, sid=SID, symbol="GLD", side="buy", qty=0.1, ts=T0,
              algo="gld_sma_filter", oid=None):
    return {"seq": seq, "ts": ts, "aggregate_type": "order",
            "aggregate_id": oid or f"o{seq}", "type": "OrderProposed",
            "actor": "external:lean",
            "payload": {"symbol": symbol, "side": side, "qty": qty,
                        "strategy_id": sid, "venue": "alpaca",
                        "rationale": f"[lean:{algo}] a reason"}}


def _filled(seq, oid, *, sid=SID, symbol="GLD", qty=0.1, ts=T0):
    return {"seq": seq, "ts": ts, "aggregate_type": "order",
            "aggregate_id": oid, "type": "OrderFilled", "actor": "venue",
            "payload": {"symbol": symbol, "side": "buy", "filled_qty": qty,
                        "avg_price": 300.0, "strategy_id": sid, "qty": qty}}


def _session(state="running", sid=SID, algo="gld_sma_filter", started=T2,
             session_id="sess-1"):
    return {"session_id": session_id, "state": state, "strategy_id": sid,
            "algorithm": algo, "started_at": started}


def _ctx(sessions=(), known_since=T1, archived=()):
    return EL.EngineContext(
        sessions=None if sessions is None else list(sessions),
        known_since=known_since,
        archived_strategy_ids=None if archived is None else set(archived))


def _leg(events, positions=None, ctx=None):
    return EL.engine_leg(_Store(events), attribution=_Attribution(positions),
                         context=ctx if ctx is not None else _ctx())


#: The probe's shape: an engine signal raised BEFORE the registry epoch (so it
#: fences at the SIGNAL level, correctly), FILLED, so the fund's book holds it.
HISTORY = [_proposed(157, oid="e035957c"), _filled(158, "e035957c")]

#: The live record's own shape: a signal that was declined, so the book is flat.
DECLINED_HISTORY = [
    _proposed(157, oid="e035957c"),
    {"seq": 158, "ts": T0, "aggregate_type": "order",
     "aggregate_id": "e035957c", "type": "OrderDeclined",
     "actor": "someone", "payload": {"approver": "someone"}},
]


class TestTheIncident:
    def test_A_LIVE_SESSION_FOR_THE_STRATEGY_MAKES_THE_ROW_DIVERGED(self):
        """The signal is still fenced — it genuinely predates the session — but
        the ROW is not, because a live container for this strategy exists and
        holds nothing here."""
        leg = _leg(HISTORY, {SID: {"GLD": 0.1}},
                   _ctx(sessions=[_session()]))
        row, = leg["implied"]["per_symbol"]
        assert row["signals_live"] == 0            # the SIGNAL is fenced
        assert row["signals_fenced"] == 1
        assert row["fenced"] is False              # the ROW is not
        assert row["engine_implied_qty"] == 0.0    # measured, not absent
        assert row["drift"] == -0.1
        assert row["sync_state"] == "diverged"
        assert row["row_basis"] == EL.ROW_LIVE_SESSION_STARTED_FLAT
        assert leg["verdict"]["state"] == "diverged"

    def test_the_measured_zero_is_a_ZERO_and_not_an_ABSENCE(self):
        """The half that makes the row worth reading. ``None`` would have made
        it ``undetermined`` — honest, and it would have thrown the whole
        finding away: the engine holds nothing and the fund holds 0.1."""
        leg = _leg(HISTORY, {SID: {"GLD": 0.1}}, _ctx(sessions=[_session()]))
        row, = leg["implied"]["per_symbol"]
        assert row["engine_implied_qty"] is not None
        assert row["in_sync"] is False
        # ...and the DEAD engine's own figure is still preserved beside it,
        # exactly as the clean-field rule requires.
        assert row["fenced_implied_qty"] == 0.1

    def test_a_live_engine_that_AGREES_with_a_flat_book_reads_IN_SYNC(self):
        """The other side of the same reading, and the one that proves the
        change is a measurement rather than a way to manufacture divergences.
        A flat book against a flat live container agrees."""
        leg = _leg(DECLINED_HISTORY, {SID: {}}, _ctx(sessions=[_session()]))
        row, = leg["implied"]["per_symbol"]
        assert row["engine_implied_qty"] == 0.0
        assert row["drift"] == 0.0
        assert row["sync_state"] == "in_sync"
        assert leg["verdict"]["state"] == "in_sync"


class TestWhatStillFences:
    def test_a_live_session_for_ANOTHER_strategy_still_fences(self):
        """THE LIVE POPULATION TODAY, and the assertion the brief asked for.
        Measured against the running spine 2026-08-27: the fund's one live
        session names strategy ``95520a8a-b527-4813-b0a5-bd466206912b`` and its
        one fenced row belongs to ``a356b00a-d6c9-45f0-96ff-0a3a67f2af06``. A
        rule that un-fenced on ANY live session would have changed the CEO's
        page on account of a container with nothing to do with that strategy.
        """
        leg = _leg(DECLINED_HISTORY, {SID: {}},
                   _ctx(sessions=[_session(sid=OTHER, algo="hyg_probe")],
                        archived=[SID]))
        row, = leg["implied"]["per_symbol"]
        assert row["fenced"] is True
        assert row["engine_implied_qty"] is None
        assert row["sync_state"] == "fenced_history"
        assert row["row_basis"] == EL.ROW_NO_LIVE_ENGINE
        assert leg["verdict"]["state"] == "fenced_history"

    def test_NO_live_sessions_at_all_still_fences(self):
        """The original case, unchanged. A readable, EMPTY session list PROVES
        there is no live engine — which is why ``[]`` and ``None`` had to stay
        different values."""
        leg = _leg(DECLINED_HISTORY, {SID: {}},
                   _ctx(sessions=[], archived=[SID]))
        row, = leg["implied"]["per_symbol"]
        assert row["fenced"] is True
        assert row["row_basis"] == EL.ROW_NO_LIVE_ENGINE

    @pytest.mark.parametrize("state", ["ended", "failed", "stopped",
                                       "vanished", "", "Running"])
    def test_a_session_that_is_not_ALIVE_does_not_un_fence(self, state):
        """A row that is not in ``_SESSION_ALIVE`` holds nothing and proves
        nothing. ``"Running"`` is in the table because the state comparison is
        exact and a case-folded one would be a second idea of "alive"."""
        leg = _leg(DECLINED_HISTORY, {SID: {}},
                   _ctx(sessions=[_session(state=state)], archived=[SID]))
        row, = leg["implied"]["per_symbol"]
        assert row["fenced"] is True
        assert row["row_basis"] == EL.ROW_NO_LIVE_ENGINE

    def test_a_session_naming_only_an_ALGORITHM_is_attributable_and_not_ours(self):
        """It identifies itself as something we can compare, and it is not this
        strategy — so the row still fences. The row key carries a strategy id
        and no algorithm, which is why the algorithm cannot rescue it."""
        leg = _leg(DECLINED_HISTORY, {SID: {}},
                   _ctx(sessions=[_session(sid="", algo="some_algo")],
                        archived=[SID]))
        row, = leg["implied"]["per_symbol"]
        assert row["fenced"] is True
        assert row["row_basis"] == EL.ROW_NO_LIVE_ENGINE


class TestWhatIsNeitherFencedNorMeasured:
    """THE TWO HALVES ARE SEPARATE AND BOTH MATTER. Not fencing says "we could
    not prove there is no live engine". Claiming a zero says "we know one
    exists and it holds nothing". A rule that treated the first as the second
    would print ``engine 0.0 vs book 0.1`` on evidence it never had."""

    def test_an_UNREADABLE_session_list_neither_fences_nor_claims_a_zero(self):
        rf = EL.row_fence(0, SID, _ctx(sessions=None))
        assert rf["fenced"] is False
        assert rf["implied"] == EL.IMPLIED_ABSENT
        assert rf["basis"] == EL.ROW_SESSIONS_UNREADABLE
        assert "UNKNOWN" in rf["reason"]

    def test_a_session_naming_NEITHER_strategy_nor_algorithm_blocks_both(self):
        """It cannot be ruled out, so it stops the fence; it cannot be
        attributed, so it stops the measured zero. Granting it the zero would
        credit one unidentifiable container with a flat book in every strategy
        at once."""
        leg = _leg(DECLINED_HISTORY, {SID: {}},
                   _ctx(sessions=[_session(sid="", algo="")], archived=[SID]))
        row, = leg["implied"]["per_symbol"]
        assert row["fenced"] is False
        assert row["engine_implied_qty"] is None
        assert row["sync_state"] == "undetermined"
        assert row["row_basis"] == EL.ROW_SESSION_UNATTRIBUTABLE
        assert "be neither ruled out nor credited" in row["row_note"]

    def test_an_anonymous_session_does_not_stop_an_ATTRIBUTABLE_match(self):
        """Order independence. A session that IS ours must win however the
        anonymous one is ordered in the list, or the reading would depend on
        which row Postgres returned first."""
        anon = _session(sid="", algo="", session_id="anon")
        mine = _session(session_id="mine")
        for sessions in ([anon, mine], [mine, anon]):
            rf = EL.row_fence(0, SID, _ctx(sessions=sessions))
            assert rf["implied"] == EL.IMPLIED_MEASURED_ZERO, sessions
            assert rf["basis"] == EL.ROW_LIVE_SESSION_STARTED_FLAT


class TestPrecedenceAndPartition:
    def test_a_row_WITH_live_signals_is_untouched_by_any_of_this(self):
        """The path that carried every row before this change. Its basis is
        named so a regression that started folding the wrong quantity shows up
        as a basis change rather than only as a number."""
        leg = _leg([_proposed(1, ts=T2)], {SID: {"GLD": 0.1}},
                   _ctx(sessions=[_session(started=T0)]))
        row, = leg["implied"]["per_symbol"]
        assert row["signals_live"] == 1
        assert row["row_basis"] == EL.ROW_LIVE_SIGNAL
        assert row["engine_implied_qty"] == 0.1
        assert row["sync_state"] == "in_sync"

    def test_an_UNQUANTIFIED_live_signal_outranks_everything(self):
        """Precedence, asserted rather than assumed. We KNOW the engine asked
        for something here and cannot size it; a zero would be a claim we do
        not have, and a fold would be a sum with an unknown term in it."""
        noqty = _proposed(1, ts=T2)
        noqty["payload"].pop("qty")
        leg = _leg([noqty], {SID: {"GLD": 0.1}},
                   _ctx(sessions=[_session(started=T0)]))
        row, = leg["implied"]["per_symbol"]
        assert row["implied_unquantified"] is True
        assert row["engine_implied_qty"] is None
        assert row["sync_state"] == "undetermined"

    @pytest.mark.parametrize("sessions", [
        [_session()], [_session(sid="", algo="")], [], None,
        [_session(sid=OTHER, algo="hyg")],
    ])
    def test_the_four_sync_states_still_partition_the_rows(self, sessions):
        """``engine_leg`` asserts exhaustiveness by counting all four directly
        rather than one as a remainder. Three new ways to be un-fenced must not
        have escaped that."""
        leg = _leg(HISTORY, {SID: {"GLD": 0.1}}, _ctx(sessions=sessions))
        im = leg["implied"]
        assert (im["symbols_out_of_sync"] + im["symbols_undetermined"]
                + im["symbols_in_sync"] + im["symbols_fenced"]
                == len(im["per_symbol"]))

    def test_every_row_carries_a_basis_and_it_is_one_of_the_five(self):
        """A field that can be absent is a field a renderer will read as a
        default. Enumerated by NAME rather than by count, because a partition
        whose safety rests on one field must have every value asserted (the
        engineGlance lesson, adversary night2)."""
        known = {EL.ROW_LIVE_SIGNAL, EL.ROW_LIVE_SESSION_STARTED_FLAT,
                 EL.ROW_SESSIONS_UNREADABLE, EL.ROW_SESSION_UNATTRIBUTABLE,
                 EL.ROW_NO_LIVE_ENGINE}
        assert len(known) == 5, "two bases share a string"
        seen = set()
        for sessions in ([_session()], [_session(sid="", algo="")], [], None,
                         [_session(sid=OTHER, algo="hyg")]):
            for events in (HISTORY, [_proposed(1, ts=T2)]):
                leg = _leg(events, {SID: {"GLD": 0.1}}, _ctx(sessions=sessions))
                for row in leg["implied"]["per_symbol"]:
                    assert row["row_basis"] in known, row["row_basis"]
                    seen.add(row["row_basis"])
        # THE DOMAIN OF THE SWEEP, stated: four of the five are reachable
        # through ``engine_leg``. ROW_SESSIONS_UNREADABLE is not, because an
        # unreadable session list makes every SIGNAL live (signal_liveness rule
        # 1), so ``n_live`` is never zero on a key that has signals. It is
        # reachable only by calling ``row_fence`` directly, which
        # ``TestWhatIsNeitherFencedNorMeasured`` does — and saying so here is
        # what stops this test from looking like a full enumeration.
        assert seen == known - {EL.ROW_SESSIONS_UNREADABLE}, seen

    def test_the_fold_writes_nothing(self):
        store = _Store(HISTORY)
        EL.engine_leg(store, attribution=_Attribution({SID: {"GLD": 0.1}}),
                      context=_ctx(sessions=[_session()]))
        assert store.appended == []
