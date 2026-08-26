"""THE WRITE-SET the re-decision guard compares, and the writer it must match.

THE INCIDENT THIS FILE EXISTS FOR (adversary blind review, 2026-08-26). The
v1 form of ``ticketguard.check_redecision`` compared ``status`` ALONE, and
returned a 409 whose message told the caller the write "changes nothing".
``deskstore.decide_recommendation`` writes FIVE fields. Replayed over the
whole record, **17 of v1's 37 refusals carried a real table write** — 13
note-only, 4 note plus ``next_actor``. ``note`` is not prose: it is parsed
into the supersession marker rendered on the CEO's desk card
(``deskcard.superseded_by``, folded at both ``desk.py`` sites), and
``POST /fund/desk/runs/{run_id}/recommendations/{rec_id}`` is the writer's
only caller repo-wide — so a note or routing correction on a row whose status
was already right had no door at all. Seven of the 17 came from one chair
sweep two days before the review.

**NO TEST ASSERTED THE LOSS.** That is why the scope repair fought nothing:
every existing test drove the guard with the same note on every call, so the
status-only comparison and a full-write-set comparison were indistinguishable
to the suite. These are the tests that would have caught it, and the ones that
fail if it ever comes back.

THREE THINGS ARE PINNED HERE, in the order they matter:

  1. **THE CONTRACT WITH THE WRITER** (``TestTheWriteSetMatchesTheWriter``) —
     an ``ast`` read of ``decide_recommendation``'s own source, asserting that
     ``REDECISION_COMPARED`` plus ``REDECISION_ALWAYS_REWRITTEN`` cover every
     recommendation field that writer assigns or pops, with nothing left over
     on either side. A sixth field appearing there without appearing here is
     a field the guard would silently not compare — the defect itself, at a
     new scope. This is the test that generalises; the rest are its boundary.
  2. **THE VALUES ARE READ, NOT COPIED** (``TestTheWritersOwnValuesAreRead``)
     — proved by MOVING them. An assertion that the guard's terminal set
     equals deskstore's cannot tell a live read from a hardcoded duplicate
     that happens to agree today, so these monkeypatch deskstore and require
     the guard's behaviour to follow.
  3. **THE BOUNDARY TABLE** for ``redecision_writes`` itself — the partition
     invariant, the three-branch ``next_actor`` rule against the
     terminal/non-terminal split, and the pivot from a full no-op to exactly
     one changed field.

The boundary table (classes 3–8 below) was drafted by a junior worker against
a written contract that named no implementation; three of its cases asserted a
supplied-and-identical note as ``not_written`` and were rewritten. That is
recorded here rather than in a ledger nobody reads, because the class it
happened in is the one a future reader is most likely to trust on sight.
"""

from __future__ import annotations

import ast
import copy
import itertools
import pathlib

import pytest

from app.fund import deskstore, ticketguard


#: The status vocabulary, as literals. Deliberately NOT imported from
#: deskstore: a table that reads its own expected values from the module under
#: test asserts only that the module agrees with itself.
ALL_STATUSES = ("open", "accepted", "rejected", "staged", "done", "noted")
TERMINAL_STATUSES = ("rejected", "done", "noted")
NON_TERMINAL_STATUSES = ("open", "accepted", "staged")

FIELD_ORDER = ("status", "note", "next_actor")

DESKSTORE_SRC = (pathlib.Path(deskstore.__file__)).read_text(encoding="utf-8")


def _lineage(recorded_status=None, recorded_note="", recorded_next_actor=None):
    """The three keys ``redecision_writes`` reads, and nothing else."""
    return {"recorded_status": recorded_status,
            "recorded_note": recorded_note,
            "recorded_next_actor": recorded_next_actor}


def _call(lineage, *, to, note="", next_actor=None):
    return ticketguard.redecision_writes(
        lineage, to=to, note=note, next_actor=next_actor)


def _partition(result, changes, unchanged, not_written):
    """Assert all THREE lists at once, never membership in one.

    A test that asserted only ``"note" in result["changes"]`` would pass with
    ``note`` ALSO in ``unchanged`` — and a shared-word assertion satisfiable
    by a different branch is how a suite blesses the bug it was written for.
    """
    assert result["changes"] == changes
    assert result["unchanged"] == unchanged
    assert result["not_written"] == not_written


# ============================================================================
# 1. THE CONTRACT WITH THE WRITER — read from its source, not from memory
# ============================================================================

def _fields_the_writer_touches() -> set:
    """Every recommendation field ``decide_recommendation`` assigns or pops.

    Reads the AST rather than the text: a regex over ``r["x"] =`` would count
    the same line in a docstring or a comment, and would miss a field written
    through any other statement shape. The local name is ``r`` — the loop
    variable over ``recs`` — and it is asserted below that the scan found
    something, so a rename cannot turn this test into a vacuous pass.
    """
    tree = ast.parse(DESKSTORE_SRC)
    fn = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "decide_recommendation"):
            fn = node
            break
    assert fn is not None, "decide_recommendation vanished from deskstore"
    found = set()
    for node in ast.walk(fn):
        # r["field"] = ...
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (isinstance(t, ast.Subscript)
                        and isinstance(t.value, ast.Name) and t.value.id == "r"
                        and isinstance(t.slice, ast.Constant)
                        and isinstance(t.slice.value, str)):
                    found.add(t.slice.value)
        # r.pop("field", None)
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "pop"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "r"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            found.add(node.args[0].value)
    return found


class TestTheWriteSetMatchesTheWriter:
    """THE ONE TEST THAT GENERALISES. Everything else in this file is a
    boundary on a rule; this is the rule's own premise, and the premise is
    what failed in v1 — the guard compared one field while the writer wrote
    five, and nothing anywhere held the two lists to each other."""

    def test_the_scan_is_not_vacuous(self):
        """A scan that found nothing would make the equality below trivially
        satisfiable by emptying both constants. State the domain size."""
        touched = _fields_the_writer_touches()
        assert len(touched) >= 4, touched

    def test_every_field_the_writer_touches_is_accounted_for(self):
        """COMPARED plus ALWAYS_REWRITTEN, exactly — no field unlisted (the
        guard would not compare it: v1's defect) and no field listed that the
        writer does not touch (the guard would compare a phantom)."""
        touched = _fields_the_writer_touches()
        declared = (set(ticketguard.REDECISION_COMPARED)
                    | set(ticketguard.REDECISION_ALWAYS_REWRITTEN))
        assert touched == declared

    def test_the_two_lists_are_disjoint(self):
        """A field in both would be compared AND excused from comparison,
        and which one won would depend on statement order."""
        assert not (set(ticketguard.REDECISION_COMPARED)
                    & set(ticketguard.REDECISION_ALWAYS_REWRITTEN))

    def test_the_excused_fields_are_the_clock_and_the_decider(self):
        """Named explicitly. These two are excused because the writer stamps
        them on EVERY call, so counting them would find a change every time
        and this control would refuse nothing at all — a control that cannot
        fire. Any other field appearing here is a hole being excused."""
        assert set(ticketguard.REDECISION_ALWAYS_REWRITTEN) == {
            "decided_by", "decided_at"}


# ============================================================================
# 2. THE VALUES ARE READ FROM THE WRITER'S MODULE — proved by MOVING them
# ============================================================================

class TestTheWritersOwnValuesAreRead:
    """An assertion that two constants are EQUAL cannot distinguish a live
    read from a hardcoded duplicate that happens to agree today. These move
    the source and require the guard to follow it."""

    def test_the_terminal_set_is_read_from_deskstore(self, monkeypatch):
        """MOVE IT: make ``staged`` terminal in deskstore and the guard must
        start clearing ``next_actor`` on a ``staged`` decision. A duplicated
        tuple inside ticketguard would keep reporting ``not_written``."""
        lin = _lineage(recorded_status="staged", recorded_next_actor="ceo")
        before = _call(lin, to="staged")
        _partition(before, [], ["status"], ["note", "next_actor"])

        monkeypatch.setattr(deskstore, "TERMINAL_REC_STATUSES",
                            ("rejected", "done", "noted", "staged"))
        after = _call(lin, to="staged")
        _partition(after, ["next_actor"], ["status"], ["note"])

    def test_removing_a_status_from_the_terminal_set_is_followed_too(
            self, monkeypatch):
        """The other direction, because a one-sided move can be satisfied by
        a union with a private copy."""
        lin = _lineage(recorded_status="done", recorded_next_actor="ceo")
        _partition(_call(lin, to="done"), ["next_actor"], ["status"], ["note"])

        monkeypatch.setattr(deskstore, "TERMINAL_REC_STATUSES",
                            ("rejected", "noted"))
        _partition(_call(lin, to="done"), [], ["status"],
                   ["note", "next_actor"])

    def test_the_next_actor_normalisation_is_read_from_deskstore(
            self, monkeypatch):
        """MOVE IT: replace deskstore's normaliser with one that neither
        strips nor lower-cases, and ``" CEO "`` stops matching ``"ceo"`` —
        the guard must then report a CHANGE where it reported none.

        Note the shape of the move. Upper-casing instead of lower-casing
        would NOT work as a probe: it transforms both sides identically and
        they stay equal, so the test would pass against a hardcoded copy too.
        A move only proves a read when it changes the ANSWER."""
        lin = _lineage(recorded_status="accepted", recorded_next_actor="ceo")
        _partition(_call(lin, to="accepted", next_actor=" CEO "),
                   [], ["status", "next_actor"], ["note"])

        monkeypatch.setattr(
            deskstore, "_next_actor",
            lambda raw: (raw or None) if isinstance(raw, str) else None)
        _partition(_call(lin, to="accepted", next_actor=" CEO "),
                   ["next_actor"], ["status"], ["note"])


# ============================================================================
# 3. The partition invariant — the structural property, over a broad sweep
# ============================================================================

class TestPartitionInvariant:
    """``changes`` + ``unchanged`` + ``not_written`` is always an exact,
    non-overlapping partition of the three field names. Checked independently
    of which list is CORRECT for a given input: that is what the tables below
    are for, and a structural break would make every one of them meaningless.
    """

    _RECORDED = (None,) + ALL_STATUSES
    _NOTES = ("", "a fresh note")
    _ACTORS = (None, "dave")

    _CASES = [
        pytest.param(rs, to, note, na,
                     id=f"rs={rs}-to={to}-"
                        f"note={'empty' if note == '' else 'set'}-na={na}")
        for rs, to, note, na in itertools.product(
            _RECORDED, ALL_STATUSES, _NOTES, _ACTORS)
    ]

    @pytest.mark.parametrize("recorded_status,to,note,next_actor", _CASES)
    def test_partition_is_exact(self, recorded_status, to, note, next_actor):
        # recorded_note / recorded_next_actor are held NON-TRIVIAL so every
        # branch is actually reached across the sweep rather than only the
        # nothing-recorded-yet corner.
        lineage = _lineage(recorded_status=recorded_status,
                           recorded_note="prior note",
                           recorded_next_actor="alice")
        result = _call(lineage, to=to, note=note, next_actor=next_actor)
        combined = (result["changes"] + result["unchanged"]
                    + result["not_written"])
        assert sorted(combined) == sorted(FIELD_ORDER)
        assert len(combined) == 3
        assert len(set(combined)) == 3


class TestFieldOrderWithinLists:
    """A list's internal order is canonical, never insertion order — so a
    caller may render ``unchanged_fields`` without sorting it and two runs
    cannot print the same refusal two ways."""

    def test_all_three_land_in_changes_in_canonical_order(self):
        lin = _lineage("open", "prior", "alice")
        _partition(_call(lin, to="staged", note="new note", next_actor="bob"),
                   ["status", "note", "next_actor"], [], [])

    def test_note_and_next_actor_unchanged_status_changes(self):
        lin = _lineage("open", "same", "alice")
        _partition(_call(lin, to="accepted", note="same", next_actor="alice"),
                   ["status"], ["note", "next_actor"], [])

    def test_status_and_next_actor_change_note_not_written(self):
        lin = _lineage("open", "prior", "alice")
        _partition(_call(lin, to="accepted", note="", next_actor="bob"),
                   ["status", "next_actor"], [], ["note"])

    def test_note_and_next_actor_change_status_unchanged(self):
        lin = _lineage("accepted", "prior", "alice")
        _partition(_call(lin, to="accepted", note="new", next_actor="bob"),
                   ["note", "next_actor"], ["status"], [])


# ============================================================================
# 4. status — always written; the one field v1 got right
# ============================================================================

class TestStatusField:
    """Every row pins a non-terminal ``to`` with no ``next_actor`` and no
    note, so the other two fields sit in ``not_written`` and the triple
    isolates what status is doing."""

    def test_same_status_is_unchanged(self):
        _partition(_call(_lineage("accepted"), to="accepted"),
                   [], ["status"], ["note", "next_actor"])

    def test_different_status_is_a_change(self):
        _partition(_call(_lineage("accepted"), to="staged"),
                   ["status"], [], ["note", "next_actor"])

    def test_no_decision_history_status_is_a_change(self):
        """``recorded_status=None`` is a row that has never been decided; any
        real status is a change against it, and the guard must not refuse a
        first decision on the strength of a None it read as a match."""
        _partition(_call(_lineage(None), to="open"),
                   ["status"], [], ["note", "next_actor"])


# ============================================================================
# 5. note — THE FIELD v1 DROPPED, 13 times in the record on its own
# ============================================================================

class TestNoteField:
    """Every row pins ``recorded_status == to`` (status unchanged) and a
    non-terminal status with no ``next_actor``, so the triple isolates note.

    The first two rows are the whole finding in miniature: an identical note
    is a no-op and must refuse; a note differing by ONE CHARACTER is a
    correction and must pass. v1 gave the same answer to both.
    """

    _S = "accepted"          # non-terminal, used as recorded AND as `to`

    def _case(self, recorded_note, note):
        return _call(_lineage(self._S, recorded_note, None),
                     to=self._S, note=note)

    def test_identical_note_is_unchanged(self):
        _partition(self._case("same text", "same text"),
                   [], ["status", "note"], ["next_actor"])

    def test_one_character_difference_is_a_change(self):
        _partition(self._case("test", "tests"),
                   ["note"], ["status"], ["next_actor"])

    def test_case_difference_is_a_change(self):
        """Exact and case-sensitive. A note is a sentence a human wrote for
        the record; normalising it would silently merge two of them."""
        _partition(self._case("Done", "done"),
                   ["note"], ["status"], ["next_actor"])

    def test_empty_string_note_is_not_written(self):
        """``if note:`` in the writer — an empty note does not ERASE the
        standing one, so it is not a write and cannot be a change."""
        _partition(self._case("existing note", ""),
                   [], ["status"], ["note", "next_actor"])

    def test_none_note_is_not_written(self):
        _partition(self._case("existing note", None),
                   [], ["status"], ["note", "next_actor"])

    @pytest.mark.parametrize("value", [
        pytest.param(0, id="int-zero"),
        pytest.param({}, id="empty-dict"),
        pytest.param([], id="empty-list"),
        pytest.param(123, id="int-123"),
    ])
    def test_non_str_note_is_not_written(self, value):
        _partition(self._case("existing note", value),
                   [], ["status"], ["note", "next_actor"])

    def test_empty_recorded_note_with_a_supplied_note_is_a_change(self):
        """A row that has never carried a note. This is the FIRST citation
        landing on a row — the shape Donna's rule cares about most."""
        _partition(self._case("", "hello"),
                   ["note"], ["status"], ["next_actor"])

    def test_whitespace_only_note_matching_recorded_is_unchanged(self):
        """``"   "`` is a non-empty str, so it IS written — and compared
        exactly, with no stripping. The writer does not strip either."""
        _partition(self._case("   ", "   "),
                   [], ["status", "note"], ["next_actor"])

    def test_whitespace_only_note_differing_from_recorded_is_a_change(self):
        _partition(self._case("x", "   "),
                   ["note"], ["status"], ["next_actor"])


# ============================================================================
# 6. next_actor — the three-branch field, including the clear
# ============================================================================

class TestNextActorField:
    """``recorded_status == to`` and ``note=""`` throughout, so the triple
    isolates next_actor."""

    def test_supplied_equal_to_recorded_is_unchanged(self):
        _partition(_call(_lineage("accepted", "", "alice"),
                         to="accepted", next_actor="alice"),
                   [], ["status", "next_actor"], ["note"])

    def test_supplied_different_from_recorded_is_a_change(self):
        """The 4 note+next_actor rows in the record are re-routings. This is
        the leg that makes them pass."""
        _partition(_call(_lineage("accepted", "", "alice"),
                         to="accepted", next_actor="bob"),
                   ["next_actor"], ["status"], ["note"])

    def test_normalisation_makes_cased_and_spaced_values_equal(self):
        _partition(_call(_lineage("accepted", "", "ceo"),
                         to="accepted", next_actor=" CEO "),
                   [], ["status", "next_actor"], ["note"])

    @pytest.mark.parametrize("recorded", [
        pytest.param(" CEO ", id="recorded-spaced-and-upper"),
        pytest.param("Ceo", id="recorded-mixed-case"),
        pytest.param("ceo ", id="recorded-trailing-space")])
    def test_the_RECORDED_owner_is_normalised_too(self, recorded):
        """BOTH SIDES, and this is not symmetry for its own sake — it is a
        mutation survivor (M7). Normalising only the supplied value passes
        every test above, because the door writes an already-normalised value
        onto the event and the live payloads are therefore all clean.

        ``redecision_writes`` is PUBLIC and takes a lineage dict; a payload
        written by an older door, a replay, or an instrument folding history
        by hand can carry a raw string. Against one of those, a half-normalised
        comparison reports a CHANGE that is not one — which is safe here
        (it allows) but silently disables the guard on that row, and a control
        that quietly stops applying is the failure this whole stack is about.
        """
        _partition(_call(_lineage("accepted", "", recorded),
                         to="accepted", next_actor="ceo"),
                   [], ["status", "next_actor"], ["note"])

    def test_a_never_noted_row_may_publish_its_note_as_None(self):
        """``redecision_lineage`` always publishes ``recorded_note`` as a
        string, so the ``or ""`` inside the comparison is unreachable through
        the production path. It is kept for callers that build a lineage dict
        by hand — and PROVABLY it changes no answer, because the branch is
        only entered for a non-empty ``note``, which equals neither None nor
        "". Recorded here so the next reader does not take the guard for a
        behaviour fix (mutation M4, retired with this proof)."""
        _partition(_call({"recorded_status": "done",
                          "recorded_next_actor": None}, to="done", note="x"),
                   ["note"], ["status", "next_actor"], [])

    def test_supplied_value_against_recorded_none_is_a_change(self):
        _partition(_call(_lineage("accepted", "", None),
                         to="accepted", next_actor="CEO"),
                   ["next_actor"], ["status"], ["note"])

    @pytest.mark.parametrize("recorded", [
        pytest.param("ceo", id="recorded-ceo"),
        pytest.param(None, id="recorded-none")])
    def test_whitespace_only_with_nonterminal_to_is_not_written(
            self, recorded):
        """``"   "`` normalises to absent, and a non-terminal status does not
        clear — so branch 3, whatever is recorded."""
        _partition(_call(_lineage("accepted", "", recorded),
                         to="accepted", next_actor="   "),
                   [], ["status"], ["note", "next_actor"])

    def test_whitespace_only_with_terminal_to_clears_and_is_a_change(self):
        _partition(_call(_lineage("rejected", "", "ceo"),
                         to="rejected", next_actor="   "),
                   ["next_actor"], ["status"], ["note"])

    def test_none_with_terminal_to_and_recorded_none_is_unchanged(self):
        """THE POP THAT CHANGES NOTHING. The writer's ``r.pop(..., None)``
        deletes a key whose value was already None; every reader uses
        ``.get``, so no reader can tell. Comparing VALUES rather than key
        presence is what keeps this a no-op instead of a phantom change that
        would let a true duplicate through."""
        _partition(_call(_lineage("done", "", None), to="done"),
                   [], ["status", "next_actor"], ["note"])

    def test_none_with_terminal_to_and_recorded_value_is_a_change(self):
        """THE POP THAT DOES SOMETHING. Clearing a standing owner takes the
        row off somebody's queue; refusing it would strand the row there."""
        _partition(_call(_lineage("noted", "", "ceo"), to="noted"),
                   ["next_actor"], ["status"], ["note"])

    @pytest.mark.parametrize("recorded", [
        pytest.param("ceo", id="recorded-ceo"),
        pytest.param(None, id="recorded-none")])
    def test_none_with_nonterminal_to_is_not_written_regardless(
            self, recorded):
        _partition(_call(_lineage("open", "", recorded), to="open"),
                   [], ["status"], ["note", "next_actor"])

    @pytest.mark.parametrize("value", [
        pytest.param(5, id="int-5"), pytest.param({}, id="empty-dict")])
    def test_non_str_next_actor_is_absent_when_nonterminal(self, value):
        _partition(_call(_lineage("open", "", "ceo"),
                         to="open", next_actor=value),
                   [], ["status"], ["note", "next_actor"])

    @pytest.mark.parametrize("value", [
        pytest.param(5, id="int-5"), pytest.param({}, id="empty-dict")])
    def test_non_str_next_actor_is_absent_when_terminal(self, value):
        _partition(_call(_lineage("rejected", "", "ceo"),
                         to="rejected", next_actor=value),
                   ["next_actor"], ["status"], ["note"])


class TestNextActorTerminalBoundaryTable:
    """THE STRICT BOUNDARY OF THIS FUNCTION, as a table over all six statuses
    rather than as scattered prose-derived cases. ``recorded_status == to`` on
    every row and ``note=""``, so the next_actor column is what moves."""

    _ROWS = [
        pytest.param(to, ["next_actor"], ["status"], ["note"],
                     id=f"terminal-{to}")
        for to in TERMINAL_STATUSES
    ] + [
        pytest.param(to, [], ["status"], ["note", "next_actor"],
                     id=f"nonterminal-{to}")
        for to in NON_TERMINAL_STATUSES
    ]

    @pytest.mark.parametrize("to,changes,unchanged,not_written", _ROWS)
    def test_the_terminal_split(self, to, changes, unchanged, not_written):
        _partition(_call(_lineage(to, "", "ceo"), to=to),
                   changes, unchanged, not_written)


# ============================================================================
# 7. Purity — no store, no clock, no mutation of the caller's lineage
# ============================================================================

class TestPurity:
    def test_repeated_calls_are_equal_and_the_lineage_is_untouched(self):
        lin = _lineage("accepted", "x", "alice")
        before = copy.deepcopy(lin)
        a = _call(lin, to="staged", note="y", next_actor="bob")
        b = _call(lin, to="staged", note="y", next_actor="bob")
        assert a == b
        assert lin == before


# ============================================================================
# 8. The all-no-op case and the minimal perturbation of each field in turn
# ============================================================================

class TestTheNoOpAndItsMinimalPerturbations:
    """THE PIVOT, written so a reader can see it by inspection: one row where
    NOTHING changes (the only shape the guard may refuse) and three rows that
    differ from it in exactly one field (all of which must pass).

    A junior draft of this class asserted the supplied-and-identical note as
    ``not_written`` on three of the four rows. It is ``unchanged``: the writer
    DOES write an identical non-empty note, it simply writes the same bytes.
    The distinction is not cosmetic — ``desk_sweep`` reads ``unchanged_fields``
    to tell the chair whether the citation it was carrying is on the record,
    and under the junior's reading it never would be.
    """

    _RECORDED_STATUS = "done"        # terminal, so the clear branch is live
    _RECORDED_NOTE = "x"
    _RECORDED_ACTOR = None

    def _base(self):
        return _lineage(self._RECORDED_STATUS, self._RECORDED_NOTE,
                        self._RECORDED_ACTOR)

    def test_every_field_matching_is_a_full_no_op(self):
        result = _call(self._base(), to="done", note="x", next_actor=None)
        assert result["changes"] == []
        _partition(result, [], ["status", "note", "next_actor"], [])

    def test_perturbing_only_the_status_changes_only_the_status(self):
        result = _call(self._base(), to="rejected", note="x", next_actor=None)
        _partition(result, ["status"], ["note", "next_actor"], [])

    def test_perturbing_only_the_note_changes_only_the_note(self):
        """13 of the 17 rows v1 wrongly refused are exactly this shape."""
        result = _call(self._base(), to="done", note="y", next_actor=None)
        _partition(result, ["note"], ["status", "next_actor"], [])

    def test_perturbing_only_the_next_actor_changes_only_it(self):
        result = _call(self._base(), to="done", note="x", next_actor="ceo")
        _partition(result, ["next_actor"], ["status", "note"], [])
