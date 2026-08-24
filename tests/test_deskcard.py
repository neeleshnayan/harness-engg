"""The CEO's window — every fold that turns a stored row into what he reads.

THE INCIDENT (CEO, 2026-08-24, verbatim): *"Why is this issue persisting;
shakes my confidence that information is flowing seemlessly in the org."*

His clicks land. The read path is what fails, and each test below names the
measured defect it stops from returning. Every count in a docstring here was
taken from the live spine on 2026-08-24 (``GET /api/v1/fund/desk``, 227 open
recommendations, 109 requests; ``GET /api/v1/fund/desk/ceo``, 34 decisions;
``GET /api/v1/fund/events?limit=1000``, seq 335-1334) and is reproducible with
the command in each docstring.
"""

from __future__ import annotations

import pytest

from app.fund import desk as desk_mod
from app.fund import deskcard


# ============================================================================
# P-1 — two rows on the live desk rendered as a Python dict repr
# ============================================================================

class TestADictPayloadRendersItsTextNeverItsRepr:
    """MEASURED: 2 of 227 rows on the CEO's live desk (2026-08-24) rendered as
    ``{'id': 'O4', 'title': ..., 'detail': ...}`` — run-cfo-8 recs 1 and 2,
    both ``accepted``. ``deskstore.record_run`` stored
    ``str(r.get("text") or r)``, so any payload naming its display field
    anything but ``text`` stored its own repr as the sentence he reads.
    """

    LIVE_ROW = ("{'id': 'O4', 'title': 'Validate serves_requests ids at the "
                "filing door, as an advisory', 'detail': "
                "'app/api/v1/fund.py:2136-2140 stores declared request ids "
                "with no check they resolve.'}")

    def test_the_two_live_rows_are_repaired_from_storage(self):
        """The exact string sitting in the database today. The filing-door fix
        cannot reach a repr written last week; this read-path repair can."""
        parts = deskcard.card_text(self.LIVE_ROW)
        assert parts["headline"] == ("Validate serves_requests ids at the "
                                     "filing door, as an advisory")
        assert parts["basis"] == "title"
        assert parts["from_dict"] is True
        assert parts["detail"].startswith("app/api/v1/fund.py:2136-2140")

    def test_the_door_stores_the_headline_not_the_repr(self):
        assert deskcard.recommendation_text(
            {"title": "Widen the import guard", "detail": "d"}
        ) == "Widen the import guard"

    def test_a_dict_with_no_display_key_keeps_its_payload_verbatim(self):
        """ABSENCE DISCIPLINE, BOTH WAYS. `card_text` reports no headline —
        an absent value is reported absent. `recommendation_text` still stores
        the payload: the rule says do not INVENT a value, not that a present
        one may be destroyed. Storing "" would delete the only copy."""
        row = {"id": "X1", "detail": "everything is in here"}
        assert deskcard.card_text(row)["headline"] is None
        assert deskcard.card_text(row)["basis"] == "unreadable"
        stored = deskcard.recommendation_text(row)
        assert "everything is in here" in stored

    def test_a_plain_string_is_untouched(self):
        parts = deskcard.card_text("Trim TLT to 12% of NAV.")
        assert parts["headline"] == "Trim TLT to 12% of NAV."
        assert parts["from_dict"] is False and parts["detail"] is None
        assert parts["basis"] == "verbatim"

    def test_prose_that_merely_starts_with_a_brace_is_not_a_dict(self):
        """A memo may legitimately open with a brace. Failing to parse is not
        a licence to mangle: the string comes back whole."""
        prose = "{this is not python} and the rest of the sentence."
        assert deskcard.card_text(prose)["headline"] == prose
        assert deskcard.card_text(prose)["from_dict"] is False

    def test_a_literal_that_is_not_a_dict_is_not_a_dict(self):
        """`ast.literal_eval` will happily return a set for `{1, 2, 3}`. Only a
        mapping is a payload."""
        assert deskcard.card_text("{1, 2, 3}")["from_dict"] is False

    def test_the_literal_parser_executes_nothing(self):
        """`literal_eval`, never `eval`. If this ever became `eval`, a stored
        recommendation would be code the spine runs while rendering the CEO's
        desk — and the payload is written by an agent."""
        hostile = "{'text': __import__('os').getcwd()}"
        parts = deskcard.card_text(hostile)
        assert parts["from_dict"] is False
        assert parts["headline"] == hostile

    def test_the_display_key_order_is_the_one_the_corpus_needs(self):
        """`text` wins over `title` — a payload carrying both means the seat
        wrote a display line on purpose and a heading as well."""
        assert deskcard.card_text(
            {"text": "the line", "title": "the heading"}
        )["headline"] == "the line"

    def test_an_empty_or_whitespace_display_key_falls_through(self):
        """`""` and `"   "` are not display lines. The old door's `or` did
        exactly this by accident and then fell all the way to the repr."""
        assert deskcard.card_text(
            {"text": "   ", "title": "the heading"}
        )["headline"] == "the heading"

    def test_a_non_string_display_key_is_never_coerced(self):
        """`{"text": 12}` must not render "12". A number in a headline slot is
        a filing error, and str() would hide it."""
        assert deskcard.card_text({"text": 12, "title": "real"})["headline"] \
            == "real"

    def test_a_string_recommendation_no_longer_crashes_the_door(self):
        """LATENT CRASH, fixed in passing. The old line called
        `r.get("text")` before any isinstance check, so a recommendation filed
        as a bare string raised AttributeError inside `record_run` — the flight
        recorder refusing the record rather than storing it."""
        assert deskcard.recommendation_text("just a sentence") == \
            "just a sentence"


# ============================================================================
# P-3 — a supersession is rendered only when the note NAMES its superseder
# ============================================================================

class TestSupersessionInProseNeedsANamedTarget:
    """THE NULL TEST IS THE POINT, AND IT IS MEASURED ON THE LIVE CORPUS.

    A word-level search for "supersed" over the live desk (2026-08-24) returns
    10 hits: 3 in recommendation notes, 7 in request resolutions. **SIX of the
    seven resolutions are ONE boilerplate sentence** stapled to unrelated
    requests, about two stray EVENTS and not about the request at all. A parser
    that rendered an edge per hit would have drawn six wrong supersession links
    on the CEO's control surface and one right one — and a wrong link looks
    exactly like a right one, while a gap looks like a gap.

    Reproduce: ``python -c`` over ``GET /api/v1/fund/desk`` with
    ``re.search(r'supersed', note, re.I)``; then the same rows through
    ``deskcard.superseded_by``. Ten to one.
    """

    #: The six-times-repeated boilerplate, verbatim from the live corpus.
    BOILERPLATE = ("The log is append-only and they stand; they are inert - "
                   "they resolve nothing and were superseded by this "
                   "correctly-addressed event minutes later. Recorded rather "
                   "than hidden.")

    #: The three recommendation notes, verbatim heads.
    NOTE_RECORD = ("SUPERSEDED BY THE RECORD, closed under v2: the condition "
                   "ended when D20's repair cleared the adversary and D19+D20 "
                   "merged as the v4.3 bundle (882a660, spine restarted)")
    NOTE_BUILD = ("SUPERSEDED BY BUILD: mark-sanity on manual approvals is "
                  "part F of builder D5; the riskofficer's review becomes a "
                  "post-merge audit")
    NOTE_R39 = ("SUPERSEDED BY THE R39 PLAN (run-pm-r39): R37 is with the "
                "adversary (cd17bd8a), R41/R42 are in the hazard batch")

    @pytest.mark.parametrize("note", [BOILERPLATE, NOTE_RECORD, NOTE_BUILD])
    def test_the_live_false_positives_render_no_edge(self, note):
        """Each of these SAYS superseded and names no row. Absence, not a
        guess: "the record" and "build" are not things a reader can follow."""
        assert deskcard.superseded_by(note) is None

    def test_the_one_real_live_edge_is_found_and_followable(self):
        edge = deskcard.superseded_by(self.NOTE_R39)
        assert edge is not None
        assert edge["ref"] == "run-pm-r39"
        assert edge["quote"].startswith("SUPERSEDED BY")
        # The quote stops AT the identifier — it is evidence for the link, not
        # the whole note pasted into a chip.
        assert edge["quote"].endswith("run-pm-r39")

    def test_the_word_alone_without_by_is_a_status_not_an_edge(self):
        """"Closed as SUPERSEDED, never cleared" — live text. It states what
        happened to the row; there is no superseder to point at."""
        assert deskcard.superseded_by(
            "Closed as SUPERSEDED, never cleared (triage-7 decision 2)") is None

    def test_an_english_word_of_hex_letters_is_not_an_id(self):
        """`[0-9a-f]{8}` matches ordinary words. Requiring a DIGIT removes the
        class: a desk that linked a row to the word "deadbeef" would be
        fabricating an edge on the one surface that must never guess."""
        assert deskcard.superseded_by("superseded by deadbeef entirely") is None
        assert deskcard.superseded_by("replaced by facefeed today") is None

    def test_a_real_request_id_is_an_id(self):
        edge = deskcard.superseded_by("re-filed as cd17bd8a after the review")
        assert edge is not None and edge["ref"] == "cd17bd8a"

    def test_a_canonical_ref_is_preferred_when_it_comes_first(self):
        edge = deskcard.superseded_by("superseded by rec:run-pm-r39#2 (see "
                                      "also run-pm-0908)")
        assert edge is not None and edge["ref"] == "rec:run-pm-r39#2"

    def test_the_window_is_a_boundary_and_it_is_probed_on_both_sides(self):
        """BOUNDARY TABLE for `_TARGET_WINDOW = 60`, and the first draft of
        this test got the boundary wrong in the safe direction — worth keeping
        as the reason the assertion is written the way it is.

        The window bounds where the identifier ENDS, not where it starts: the
        search runs over ``note[end:end+60]``, so an id straddling the edge is
        TRUNCATED and then fails its own pattern. That is the conservative
        behaviour (a half-read id is not an id) and it is what is pinned here.

        The real live edge ends 31 characters out; the nearest false positive's
        numerals sit at 96. Sixty clears the one and refuses the other.
        """
        w = deskcard._TARGET_WINDOW
        tail = " run-abc"
        # The padding starts with a space on purpose: the phrase pattern ends
        # `by\b`, so gluing filler straight onto "by" destroys the word
        # boundary and nothing matches at all. The first draft did exactly
        # that and produced a green-looking `is None` for the wrong reason —
        # a boundary test that passes because its own input never reached the
        # boundary is the bug-blessing pattern in miniature.
        pad = lambda n: " " + "y" * (n - 1)  # noqa: E731
        # The identifier ends on the window's last character.
        inside = f"superseded by{pad(w - len(tail))}{tail}"
        # One character further out: the id is cut and no longer matches.
        outside = f"superseded by{pad(w - len(tail) + 1)}{tail}"
        assert deskcard.superseded_by(inside)["ref"] == "run-abc"
        assert deskcard.superseded_by(outside) is None
        # And the real corpus edge sits comfortably inside it.
        assert self.NOTE_R39.index("run-pm-r39") - \
            (self.NOTE_R39.lower().index("superseded by") + len("superseded by")) \
            + len("run-pm-r39") <= w

    @pytest.mark.parametrize("note", [None, "", "   ", 42, {"a": 1}, []])
    def test_an_unreadable_note_is_absence(self, note):
        assert deskcard.superseded_by(note) is None


# ============================================================================
# Item 4 — "accepted, execution yours" is a state, not a synonym for undecided
# ============================================================================

class TestExecutionYoursIsItsOwnState:
    """THE STUCK LAMP, 2026-08-24. The CEO accepted R39 (event seq 1281). The
    write landed, the page refetched — and the row came back with an Accept
    button, because nothing on screen distinguished "you decided this, now
    execute it" from "nobody has decided this".

    MEASURED: **14 of the 34 rows on his live decision list** are ``accepted``
    with the next move still his (``GET /api/v1/fund/desk/ceo``, 2026-08-24).
    41% of that page rendered as undecided work.
    """

    def test_the_r39_shape_is_execution_yours(self):
        assert deskcard.execution_yours("ceo", "accepted") is True
        assert deskcard.execution_yours("ceo", "staged") is True

    def test_an_undecided_row_is_not(self):
        assert deskcard.execution_yours("ceo", "open") is False
        assert deskcard.execution_yours("ceo", None) is False

    def test_a_decided_row_the_chair_owes_is_not(self):
        """A fix that lit up EVERY accepted row would pass the first test and
        still be wrong: 146 of the 227 live rows are accepted, and only 14 are
        his to execute."""
        assert deskcard.execution_yours("chair", "accepted") is False
        assert deskcard.execution_yours("seat", "staged") is False

    def test_an_unreadable_actor_counts_as_his(self):
        """`unknown` stays with the CEO everywhere on this desk. Answering an
        unmeasurable with a zero is the fund's oldest mistake."""
        assert deskcard.execution_yours("unknown", "accepted") is True

    def test_it_changes_no_count(self):
        """THE CONSTRAINT, ASSERTED RATHER THAN INTENDED. These rows live
        inside `awaiting_decision`; `desk_load.total` counts ceo+unknown and
        the stage contract pins the page's total to it. A fourth stage would
        have moved a threshold's population while calling itself a rendering
        change."""
        for status in ("open", "accepted", "staged"):
            assert deskcard.desk_stage("ceo", status) == \
                deskcard.STAGE_AWAITING_DECISION
        rows = [{"status": "accepted", "kind": "awaits-ceo",
                 "next_actor": "ceo"},
                {"status": "open", "kind": "awaits-ceo"}]
        assert desk_mod.desk_load(rows, [], [])["total"] == 2

    def test_the_stage_mapping_moved_without_changing(self):
        """`stage_for` lived in a generator script the running spine never
        imported — the one definition both repos are pinned to could not be
        called by the code being pinned. It is a function now; the answers are
        unchanged."""
        for actor in ("ceo", "unknown", "chair", "seat", "nobody"):
            for status in ("open", "accepted", "staged", None, "weird"):
                expected = ("awaiting_decision" if actor in ("ceo", "unknown")
                            else "awaiting_execution"
                            if status in ("accepted", "staged")
                            else "owned_elsewhere")
                assert deskcard.desk_stage(actor, status) == expected

    def test_the_decided_statuses_agree_with_the_database_vocabulary(self):
        """MOVED, NOT COPIED. A mirrored tuple that merely equalled its source
        today could be a hardcoded duplicate that happens to agree; this reads
        the database module's own list and derives the pair from it."""
        from app.fund import deskstore
        derived = tuple(s for s in deskstore.REC_STATUSES
                        if s not in deskstore.TERMINAL_REC_STATUSES
                        and s != "open")
        assert deskcard.DECIDED_STATUSES == derived


# ============================================================================
# Addition B — a disposition the chair made is its own visible category
# ============================================================================

class TestChairAdjudicationIsFirstClass:
    """CEO, 2026-08-24, verbatim: *"your desk on the UI only marks items as
    CEO approved - trigger it so I cant form a view of whats closed and
    adjudicated by you."*

    MEASURED over the 227 live rows: **122 decided by the CEO, 52 by the chair
    alone** (``co-cto`` 39, ``cto`` 13), **11 via-chair**, 42 undecided. The
    desk labelled all 185 decided rows identically.
    """

    def test_the_three_channels_are_distinguishable(self):
        assert deskcard.adjudication({"decided_by": "ceo"})["channel"] == "ceo"
        assert deskcard.adjudication({"decided_by": "co-cto"})["channel"] \
            == "chair"
        assert deskcard.adjudication({"decided_by": "cto"})["channel"] == "chair"
        assert deskcard.adjudication(
            {"decided_by": "neelesh-via-cto"})["channel"] == "via_chair"
        assert deskcard.adjudication(
            {"decided_by": "neelesh-via-co-cto"})["channel"] == "via_chair"

    def test_the_via_channel_is_not_the_chair_channel(self):
        """THE DISTINCTION THE CEO ASKED FOR. `neelesh-via-cto` is HIS
        decision with the chair's hand on it; `cto` is the chair deciding under
        delegation v2. Collapsing them would answer his question with the
        wrong number — 63 instead of 52."""
        assert deskcard.adjudication({"decided_by": "neelesh-via-cto"})[
            "channel"] != deskcard.adjudication({"decided_by": "cto"})["channel"]

    def test_the_instruction_is_lifted_verbatim(self):
        """The approval guard writes `neelesh-via-cto [Agree]`. That bracketed
        quote is delegation v2's audit trail; it is never summarised."""
        a = deskcard.adjudication(
            {"decided_by": "neelesh-via-co-cto [lets try 1 but its not policy "
                           "just yet]"})
        assert a["channel"] == "via_chair"
        assert a["actor"] == "neelesh-via-co-cto"
        assert a["instruction"] == "lets try 1 but its not policy just yet"

    def test_an_instruction_containing_brackets_survives(self):
        a = deskcard.adjudication(
            {"decided_by": "neelesh-via-cto [approve [1] and [2]]"})
        assert a["instruction"] == "approve [1] and [2]"

    def test_an_undecided_row_has_no_adjudication_at_all(self):
        """None is "nobody has decided this", which is a different fact from
        "decided by nobody" and renders differently."""
        assert deskcard.adjudication({"status": "open"}) is None
        assert deskcard.adjudication({"decided_by": "  "}) is None
        assert deskcard.adjudication("not a row") is None

    def test_a_stranger_is_unknown_and_keeps_its_name(self):
        """A desk that filed an unrecognised actor under "the chair" would be
        laundering exactly the attribution this category exposes."""
        a = deskcard.adjudication({"decided_by": "someone-else"})
        assert a["channel"] == "unknown" and a["actor"] == "someone-else"

    def test_the_citation_is_the_note_untruncated(self):
        note = "Merged under delegation v2; " + "x" * 400
        a = deskcard.adjudication({"decided_by": "cto", "note": note})
        assert a["citation"] == note

    def test_a_decision_with_no_note_reports_no_citation(self):
        assert deskcard.adjudication({"decided_by": "cto"})["citation"] is None


# ============================================================================
# Item 5 — the cascade rule finally has machinery
# ============================================================================

class TestTheCascadeBlock:
    """Constitution 2026-08-21: *"a batch acceptance CASCADES — when the CEO
    accepts a COO batch, the CTO executes the underlying items and marks them
    done."* Written as governance and never given a field, so "did the cascade
    actually happen" was unanswerable except by reading prose.
    """

    BUNDLE = {"status": "accepted",
              "members": [{"run_id": "r", "rec_id": 1},
                          {"run_id": "r", "rec_id": 2},
                          {"request_id": "q1"}]}
    LOOKUP = {"rec:r#1": "open", "rec:r#2": "accepted", "req:q1": "resolved"}

    def test_a_decided_bundle_reports_what_is_still_owed(self):
        c = deskcard.cascade(self.BUNDLE, self.LOOKUP)
        assert (c["total"], c["done"], c["pending"], c["not_open"]) == \
            (3, 1, 2, 0)
        assert "CASCADE PENDING: 2 member(s) undecided" in c["note"]

    def test_an_undecided_bundle_shows_nothing(self):
        """A reminder that fires before the decision is a reminder that gets
        ignored."""
        assert deskcard.cascade({**self.BUNDLE, "status": "open"},
                                self.LOOKUP) is None

    def test_a_row_with_no_members_is_an_ordinary_row(self):
        assert deskcard.cascade({"status": "accepted"}, self.LOOKUP) is None
        assert deskcard.cascade({"status": "accepted", "members": []},
                                self.LOOKUP) is None

    def test_a_member_absent_from_the_open_desk_is_never_counted_as_done(self):
        """THE DEFECT THE CONTRACT FIXTURE FOUND BEFORE ANY OF THIS SHIPPED.
        `open_recommendations` returns only open/accepted/staged, so a FINISHED
        recommendation is simply absent — and the first cut called that
        `unresolvable`, which rendered a fully-executed cascade as "3 members
        could not be read". It is `not_open`, named for what was observed, and
        it is not `done`: absent means "finished, or never filed, and this fold
        cannot tell which"."""
        c = deskcard.cascade(self.BUNDLE, {})
        assert c["not_open"] == 3 and c["done"] == 0 and c["pending"] == 0
        assert "does not count them as done" in c["note"]

    def test_an_unreadable_lookup_does_not_invent_progress(self):
        c = deskcard.cascade(self.BUNDLE, None)
        assert c["done"] == 0 and c["not_open"] == 3

    def test_a_fully_closed_cascade_says_so(self):
        c = deskcard.cascade(self.BUNDLE,
                             {"rec:r#1": "done", "rec:r#2": "rejected",
                              "req:q1": "resolved"})
        assert c["pending"] == 0 and c["done"] == 3
        assert "all 3 member(s) closed" in c["note"]

    def test_the_block_never_executes_anything(self):
        """A reminder surface. The constitution says the chair VALIDATES then
        executes; a fold that acted would be the unwired-kill-switch pattern
        inverted."""
        assert "nothing here executes anything" in \
            deskcard.cascade(self.BUNDLE, self.LOOKUP)["note"]

    def test_a_member_that_names_no_row_is_dropped_not_stored(self):
        """A member the block could never resolve would render "0 of 3" over
        a third that does not exist."""
        assert deskcard.normalise_members(
            [{"note": "the thing we discussed"}, {"rec_id": 3},
             {"run_id": "r"}, "a string", None]) == []

    def test_a_bool_rec_id_is_not_a_rec_id(self):
        """`True` is an int in Python and would mint `rec:r#True`."""
        assert deskcard.normalise_members([{"run_id": "r", "rec_id": True}]) == []

    def test_duplicate_members_are_counted_once(self):
        m = deskcard.normalise_members([{"run_id": "r", "rec_id": 1},
                                        {"run_id": "r", "rec_id": 1}])
        assert len(m) == 1

    def test_the_member_list_is_bounded(self):
        many = [{"run_id": "r", "rec_id": i} for i in range(500)]
        assert len(deskcard.normalise_members(many)) == deskcard.MAX_MEMBERS


# ============================================================================
# Addition A — the request card, structured or prose
# ============================================================================

class TestTheRequestCard:
    """Spec: ``KryptonPay/docs/design/REQUEST_CARD_2026-08-24.md``, CEO-
    ratified, after request ``0c295ec7`` rendered as a wall of prose: *"it
    could have been designed in a far more intuitive and cleaner way"*.
    """

    def test_prose_only_stays_valid_and_says_so(self):
        """109 requests exist and none was filed under a schema that did not
        exist. `structured: false` is how the renderer picks the fallback."""
        c = deskcard.request_card(
            {"subject": "DESK RENDERING + ROUTING\nFive rows rendered as raw "
                        "Python reprs this weekend."})
        assert c["structured"] is False
        assert c["headline"] == "DESK RENDERING + ROUTING"
        # The whole subject is kept, so nothing is lost behind the headline.
        assert "Five rows rendered" in c["incident"]

    def test_the_fallback_headline_is_a_line_not_a_sentence(self):
        """Splitting on the first full stop would cut a subject mid-clause;
        the renderer knows its own width and does the truncating."""
        c = deskcard.request_card(
            {"subject": "Fix the desk. Then fix the floor."})
        assert c["headline"] == "Fix the desk. Then fix the floor."

    def test_a_structured_filing_answers_the_four_questions(self):
        c = deskcard.request_card({
            "subject": "ignored when a headline is given",
            "headline": "Repair the CEO's desk read path",
            "summary": "His clicks land; the fold does not.",
            "incident": "Six defects pooled in a starved batch.",
            "wanted": [{"text": "dict payloads", "state": "done"},
                       {"text": "cascade", "state": "in_progress",
                        "note": "spine half landed"},
                       {"text": "contract test"}],
            "next_move": {"actor": "the chair", "act": "batch it"}})
        assert c["structured"] is True
        assert c["headline"] == "Repair the CEO's desk read path"
        assert [w["state"] for w in c["wanted"]] == \
            ["done", "in_progress", "open"]
        assert c["wanted"][1]["note"] == "spine half landed"
        assert c["next_move"] == {"actor": "the chair", "act": "batch it"}

    def test_a_next_move_missing_its_act_is_refused_whole(self):
        """The spec's own complaint about the old chip: it named an owner and
        left the reader to guess the obligation."""
        assert deskcard.request_card(
            {"subject": "s", "next_move": {"actor": "the chair"}}
        )["next_move"] is None
        assert deskcard.request_card(
            {"subject": "s", "next_move": {"act": "batch it"}}
        )["next_move"] is None

    def test_an_unrecognised_wanted_state_is_open_not_dropped(self):
        """Advisory field, safe direction: a typoed state must still show as
        something still owed."""
        assert deskcard.normalise_wanted(
            [{"text": "a", "state": "finished-ish"}])[0]["state"] == "open"

    def test_a_wanted_item_with_no_text_is_dropped(self):
        assert deskcard.normalise_wanted([{"state": "done"}, {"text": "  "},
                                          None, 7]) == []

    def test_a_bare_string_is_an_open_wanted_item(self):
        assert deskcard.normalise_wanted(["do the thing"]) == \
            [{"text": "do the thing", "state": "open"}]


class TestTheLifecycleRail:
    """The spec's worked example: request ``0c295ec7`` was approved 22 minutes
    after filing and then sat idle 2.5 days. The old card rendered that as gray
    footer text."""

    FILED = {"status": "open", "at": "2026-08-22T10:00:00+00:00"}
    APPROVED = {"status": "approved", "at": "2026-08-22T10:00:00+00:00",
                "approved_at": "2026-08-22T10:22:00+00:00"}

    def test_the_current_stage_is_where_the_row_actually_is(self):
        assert deskcard.lifecycle_rail(self.FILED)["current"] == "filed"
        assert deskcard.lifecycle_rail(self.APPROVED)["current"] == \
            "awaiting_dispatch"
        assert deskcard.lifecycle_rail(
            {**self.APPROVED, "dispatched": True})["current"] == "dispatched"
        assert deskcard.lifecycle_rail(
            {**self.APPROVED, "status": "resolved",
             "resolved_at": "2026-08-25T10:00:00+00:00"})["current"] == \
            "delivered"

    def test_the_age_is_of_the_CURRENT_stage_not_of_the_row(self):
        """2.5 days idle AFTER approval is the story; 2.5 days since filing is
        not the same sentence and is the one the old card told."""
        rail = deskcard.lifecycle_rail(self.APPROVED,
                                       now="2026-08-24T22:22:00+00:00")
        assert rail["age_hours"] == 60.0

    def test_a_stage_with_no_timestamp_reports_no_age(self):
        """A desk that printed "awaiting dispatch · 0.0h" over a row idle for
        two and a half days would be this fund's oldest mistake on its newest
        surface."""
        rail = deskcard.lifecycle_rail({"status": "approved"})
        assert rail["current"] == "awaiting_dispatch"
        assert rail["age_hours"] is None

    def test_a_future_timestamp_is_unknown_and_never_zero(self):
        rail = deskcard.lifecycle_rail(self.APPROVED,
                                       now="2026-08-22T09:00:00+00:00")
        assert rail["age_hours"] is None

    def test_reached_marks_every_stage_up_to_the_current_one(self):
        rail = deskcard.lifecycle_rail({**self.APPROVED, "dispatched": True})
        reached = [s["stage"] for s in rail["stages"] if s["reached"]]
        assert reached == ["filed", "approved", "awaiting_dispatch",
                           "dispatched"]
        assert sum(1 for s in rail["stages"] if s["current"]) == 1

    def test_a_declined_request_is_not_walked_up_the_rail(self):
        rail = deskcard.lifecycle_rail(
            {"status": "declined", "at": "2026-08-22T10:00:00+00:00",
             "declined_at": "2026-08-22T11:00:00+00:00"})
        assert rail["declined"] is True and rail["current"] == "filed"


# ============================================================================
# The wiring — the folds the CEO's page actually reads
# ============================================================================

class TestTheProjectionCarriesWhatTheRendererNeeds:
    def test_on_fire_rows_carry_who_decided_and_when(self):
        """THE ITEM-4 GAP, in the projection rather than the fold. `desk_items`
        carried `status` and dropped `decided_by`/`decided_at`, so no renderer
        could say "you did this, at 09:12" — which is the whole of the one-
        second feedback the CEO asked for."""
        items = desk_mod.desk_items(
            [{"run_id": "r", "rec_id": 1, "status": "accepted",
              "kind": "awaits-ceo", "next_actor": "ceo", "text": "t",
              "due_date": "2026-01-01", "decided_by": "ceo",
              "decided_at": "2026-08-24T09:12:00+00:00"}], [])
        it = items[0]
        assert it["decided_by"] == "ceo"
        assert it["decided_at"] == "2026-08-24T09:12:00+00:00"
        assert it["execution_yours"] is True
        assert it["adjudication"]["channel"] == "ceo"

    def test_the_annotated_row_repairs_a_stored_repr_without_rewriting_it(self):
        rec = {"run_id": "run-cfo-8", "rec_id": 1, "status": "accepted",
               "text": "{'id': 'O4', 'title': 'Validate the ids', "
                       "'detail': 'the detail'}"}
        out = desk_mod._annotated(rec)
        assert out["text"] == rec["text"], "the stored value is never edited"
        assert out["text_display"] == "Validate the ids"
        assert out["text_detail"] == "the detail"
        assert out["text_basis"] == "title"

    def test_the_cascade_lookup_sees_both_populations(self):
        items = desk_mod.desk_items(
            [{"run_id": "b", "rec_id": 1, "status": "accepted", "text": "b",
              "next_actor": "ceo",
              "members": [{"run_id": "m", "rec_id": 1},
                          {"request_id": "q"}]},
             {"run_id": "m", "rec_id": 1, "status": "open", "text": "m"}],
            [{"request_id": "q", "status": "resolved", "task": "t"}])
        c = items[0]["cascade"]
        assert c["pending"] == 1 and c["done"] == 1 and c["not_open"] == 0

    def test_a_request_row_carries_its_card_and_its_rail(self):
        items = desk_mod.desk_items([], [
            {"request_id": "q", "status": "approved", "kind": "build",
             "serves": "builder", "at": "2026-08-22T10:00:00+00:00",
             "approved_at": "2026-08-22T10:22:00+00:00", "approved_by": "ceo",
             "headline": "Repair the read path", "summary": "s",
             "wanted": [{"text": "w"}],
             "next_move": {"actor": "the chair", "act": "dispatch it"}}])
        it = items[0]
        assert it["structured"] is True
        assert it["title_display"] == "Repair the read path"
        assert it["lifecycle"]["current"] == "awaiting_dispatch"
        assert it["next_move"]["act"] == "dispatch it"
        assert it["adjudication"]["channel"] == "ceo"
