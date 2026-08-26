"""The CEO's desk counter measures CEO LOAD, not status labels.

THE INCIDENT (2026-08-22, the CEO in his own words): *"I maybe out of sync with
whats happening across agents but they sustain on my queue even if that work has
been done. this needs to be fixed."* On that morning the counter read 18 and
NONE of those rows needed him — every one was waiting on the chair's bookkeeping.
The chair cleared them by hand, which is the symptom, not the fix.

The defect was a promise mismatch: `desk_load`'s docstring said it measured "how
many things are actually waiting for the CEO" and its code counted rows whose
STATUS LABEL was open. A status label is written by a seat at filing time, not
by the world.

Every test below is written so that it FAILS if that defect, or one of the three
defects that could be introduced while fixing it, comes back:

  * counting a decided row again (the CEO's complaint);
  * routing a row away from the CEO and DROPPING it from the surface (solving a
    counting problem by hiding work);
  * answering "I could not determine the actor" with silence (this fund already
    has four instruments that answered an unmeasurable with zero).
"""

import pytest

from app.fund import desk as desk_mod


# ------------------------------------------------------- the classifier -----

class TestNextActor:
    def test_a_decided_row_is_the_chairs_move_not_the_ceos(self):
        """THE CEO'S COMPLAINT, as an assertion.

        `accepted` and `staged` both mean the CEO has already decided. What
        remains is execution, which is the chair's row in the constitution's
        ownership table. A counter that puts these back on the CEO cannot tell
        him what still needs him — which is the whole complaint.
        """
        for status in ("accepted", "staged"):
            v = desk_mod.next_actor({"status": status, "kind": "awaits-ceo"})
            assert v["actor"] == "chair", (status, v)
            assert v["basis"] == "lifecycle"

    def test_kind_alone_would_reintroduce_the_complaint(self):
        """Measured on the live desk 2026-08-22: all 9 rows carrying kind
        `awaits-ceo` were already ACCEPTED. A predicate that read kind and
        ignored the lifecycle would have parked all nine on the CEO's counter
        permanently — the complaint, made structural. Lifecycle wins.
        """
        assert desk_mod.next_actor(
            {"status": "accepted", "kind": "awaits-ceo"})["actor"] == "chair"

    def test_a_terminal_row_owes_nobody_anything(self):
        for status in desk_mod.TERMINAL_STATUSES:
            v = desk_mod.next_actor({"status": status, "kind": "awaits-ceo"})
            assert v["actor"] == "nobody", (status, v)

    def test_an_undecided_row_defaults_to_the_ceo(self):
        """The safe direction. A recommendation is by construction a thing a
        seat asks the firm to decide, and the decision channel is the CEO's —
        so an unrouted open row fails toward "he must look", never toward
        "nobody must look"."""
        v = desk_mod.next_actor({"status": "open", "kind": "a-kind-nobody-has"})
        assert v["actor"] == "ceo"
        assert v["basis"] == "default"
        # A row with no status at all is undecided, not malformed-and-dropped.
        assert desk_mod.next_actor({})["actor"] == "ceo"

    def test_engineering_and_handoffs_are_not_ceo_load(self):
        """Chair work, builder work and seat-to-seat handoffs. Every kind here
        appears in the live corpus and was, in fact, dispositioned by the actor
        this table names."""
        chair = ["build", "harness", "harness-gap", "engineering_ticket",
                 "infra", "code_fix", "ui", "api_card", "docs",
                 "repair-required", "block-merge", "dispatch_request",
                 "next_dispatch"]
        for k in chair:
            assert desk_mod.next_actor({"status": "open", "kind": k})["actor"] \
                == "chair", k
        for k in ("handoff_to_mechanism", "note-to-riskofficer",
                  "routed_to_quant"):
            assert desk_mod.next_actor({"status": "open", "kind": k})["actor"] \
                == "seat", k
        for k in ("no_action", "measurement_recorded"):
            assert desk_mod.next_actor({"status": "open", "kind": k})["actor"] \
                == "nobody", k

    def test_the_kind_table_is_separator_and_case_insensitive(self):
        """Seats write `harness-gap` and `engineering_ticket` in the same
        corpus. A table that cared would need two entries per idea and one of
        them would always be the missing one."""
        for spelling in ("engineering_ticket", "engineering-ticket",
                         "Engineering Ticket", "  ENGINEERING_TICKET  "):
            assert desk_mod.next_actor(
                {"status": "open", "kind": spelling})["actor"] == "chair", spelling

    def test_a_bare_prefix_is_not_a_handoff(self):
        """`handoff_to_` with nothing after it names no recipient. Routing it
        to a seat would send work to a seat that does not exist."""
        v = desk_mod.next_actor({"status": "open", "kind": "handoff_to_"})
        assert v["actor"] == "ceo"

    def test_an_explicit_next_actor_wins_over_inference(self):
        """The COO's standing objection, given a field to live in.

        The objection (2026-08-21, preserved unresolved in the constitution):
        the counter is blind to rows at status `accepted` whose EXECUTION
        requires the CEO personally — three were live that day, including the
        largest-money decision in the firm. Inference cannot see those; a
        declaration can.
        """
        v = desk_mod.next_actor({"status": "accepted", "next_actor": "ceo"})
        assert v["actor"] == "ceo"
        assert v["basis"] == "explicit"

    def test_an_explicitly_declared_nobody_reads_as_english(self):
        """``next_actor_why`` is rendered VERBATIM on the CEO's desk, and the
        one-size-fits-all sentence produced "the row states its next actor is
        the nobody" — grammatical nonsense on the one value a reader is most
        likely to query. ``nobody`` is the spine's own word for a row filed FOR
        THE RECORD (D42: one live row, run-coo-triage8 rec 7), which is a
        different fact from a row nobody has decided yet, so the sentence says
        which one it means.
        """
        v = desk_mod.next_actor({"status": "open", "next_actor": "nobody"})
        assert v["actor"] == "nobody" and v["basis"] == "explicit"
        assert v["why"] == ("the row states its next actor is nobody "
                            "(filed for the record)")
        assert "is the nobody" not in v["why"]

    def test_the_other_THREE_actors_keep_the_article(self):
        """The fix is one branch, not a rewrite of the sentence: "is the ceo"
        is correct English and must not be collateral damage. Asserted for
        every value the branch does NOT cover, so a future simplification that
        drops the article everywhere fails here.

        THREE, not four — ``NEXT_ACTORS`` has five members and this loop is the
        complement of ``nobody`` MINUS ``unknown``, which never reaches this
        sentence at all: the ``e != "unknown"`` guard above routes it to
        ``explicit_unrecognised`` with its own message. The name said "four"
        for one commit; a test whose name overstates its domain is a coverage
        claim nobody checked. The assertion below closes the arithmetic."""
        covered = {"nobody"} | {"unknown"}
        for actor in ("ceo", "chair", "seat"):
            v = desk_mod.next_actor({"status": "open", "next_actor": actor})
            assert v["why"] == f"the row states its next actor is the {actor}"
            covered.add(actor)
        assert covered == set(desk_mod.NEXT_ACTORS), \
            "every NEXT_ACTORS member is accounted for by some test here"
        assert desk_mod.next_actor(
            {"status": "open", "next_actor": "unknown"}
        )["basis"] == "explicit_unrecognised", \
            "and 'unknown' is excluded because it never reaches the sentence"

    def test_a_terminal_status_outranks_a_stale_explicit_label(self):
        """A label written while the row was live outlives its truth.

        If `next_actor` beat a terminal status, a row marked `next_actor: ceo`
        and later marked `done` would sit on the CEO's counter forever — the
        complaint this whole module fixes, wearing the new field as a costume.
        """
        v = desk_mod.next_actor({"status": "done", "next_actor": "ceo"})
        assert v["actor"] == "nobody"
        assert v["basis"] == "lifecycle"

    def test_an_undeterminable_actor_is_unknown_and_never_silence(self):
        """Absence is never zero — including the absence of an answer about
        who must act. Three ways it can happen, three UNKNOWNs."""
        # a status outside the known vocabulary
        v = desk_mod.next_actor({"status": "in_flight"})
        assert v["actor"] == "unknown" and v["basis"] == "status_unrecognised"
        # a declared actor that is not one of ours
        v = desk_mod.next_actor({"status": "open", "next_actor": "legal"})
        assert v["actor"] == "unknown" and v["basis"] == "explicit_unrecognised"
        # a row that is not a row
        v = desk_mod.next_actor("not a dict")
        assert v["actor"] == "unknown" and v["basis"] == "unreadable"

    def test_unknown_cannot_be_declared(self):
        """`next_actor: "unknown"` is not a statement about the world, it is
        the absence of one — so it must not short-circuit inference into a
        confident-looking UNKNOWN with basis `explicit`."""
        v = desk_mod.next_actor({"status": "open", "next_actor": "unknown"})
        assert v["actor"] == "unknown"
        assert v["basis"] == "explicit_unrecognised"

    def test_every_verdict_carries_a_readable_why(self):
        for rec in ({}, {"status": "done"}, {"status": "accepted"},
                    {"status": "open", "kind": "build"}, "junk",
                    {"status": "open", "next_actor": "chair"}):
            v = desk_mod.next_actor(rec)
            assert v["actor"] in desk_mod.NEXT_ACTORS
            assert v["why"] and isinstance(v["why"], str)


# ------------------------------------------------------------ the count -----

class TestDeskLoadCountsCeoWork:
    def test_the_incident_reproduced_and_fixed(self):
        """2026-08-22, reconstructed from the live decision log by replaying
        `DeskRecommendationDecided` to 2026-08-21T20:39Z: the feed carried 85
        recommendations, 17 of them status-open, plus 1 open desk request — the
        18 the CEO saw. Of the 17, five were never his: two adversary
        `repair-required` grounds and one `block-merge` (chair), one
        `note-to-riskofficer` (a seat), one `no_action` (nobody).

        This is the shape of that morning, not a toy. 18 becomes 13.
        """
        feed = (
            [{"status": "accepted", "kind": "batch"}] * 68
            + [{"status": "open", "kind": "repair-required"}] * 2
            + [{"status": "open", "kind": "block-merge"}]
            + [{"status": "open", "kind": "note-to-riskofficer"}]
            + [{"status": "open", "kind": "no_action"}]
            + [{"status": "open", "kind": "awaits-ceo"}] * 2
            + [{"status": "open", "kind": "envelope_change"}] * 2
            + [{"status": "open", "kind": "governance"}]
            + [{"status": "open", "kind": "measurement"}]
            + [{"status": "open", "kind": "unblock"}]
            + [{"status": "open", "kind": "defect"}]
            + [{"status": "open", "kind": "process"}]
            + [{"status": "open", "kind": "cheap_next_step"}]
            + [{"status": "open", "kind": "fix"}]
            + [{"status": "open", "kind": "correction"}]
        )
        assert len(feed) == 85
        assert sum(1 for r in feed if r["status"] == "open") == 17

        load = desk_mod.desk_load(feed, [], [{}])   # + the 1 open desk request
        # The old predicate's answer, preserved here so the regression is
        # explicit rather than implied by a different number.
        assert sum(1 for r in feed if r.get("status") in (None, "open")) == 17
        assert load["components"]["open_recommendations"] == 12
        # ROUTING v2 (2026-08-27, CEO "4. Yes" then the full flow in his own
        # words): the open request is the CHAIR's move now, so it leaves the
        # CEO's total. v1 pinned total 13 / requests_awaiting_approval 1 /
        # requests_by_actor ceo 1 here.
        assert load["total"] == 12
        assert load["components"]["requests_awaiting_approval"] == 0
        assert load["requests_by_actor"]["ceo"] == 0
        assert load["requests_by_actor"]["chair"] == 1
        assert load["by_actor"]["chair"] == 71     # 68 decided + 3 engineering
        assert load["by_actor"]["seat"] == 1
        assert load["by_actor"]["nobody"] == 1
        assert load["by_actor"]["ceo"] == 12

    def test_routing_a_row_away_from_the_ceo_never_hides_it(self):
        """The brief's own guard rail: do not solve a counting problem by
        hiding work. Everything routed off the CEO's figure is counted in
        `by_actor`, summed in `not_ceo_load`, and named in the note."""
        feed = [{"status": "open", "kind": "build"},
                {"status": "open", "kind": "handoff_to_quant"},
                {"status": "open", "kind": "awaits-ceo"}]
        load = desk_mod.desk_load(feed, [], [])
        assert load["total"] == 1
        assert load["open_elsewhere"] == 2
        assert sum(load["by_actor"].values()) == 3, \
            "every row in the feed must appear somewhere in by_actor"
        assert "chair or another seat" in load["note"]

    def test_an_undeterminable_row_counts_toward_the_ceo(self):
        """Absence is never zero. A row whose next actor cannot be read is
        work the CEO may still owe, so it lands on his figure AND is named
        separately, because "unknown" and "yours" want different responses."""
        load = desk_mod.desk_load(
            [{"status": "open", "kind": "awaits-ceo"},
             {"status": "quantum_superposition"}], [], [])
        assert load["by_actor"]["unknown"] == 1
        assert load["total"] == 2
        assert "could not be determined" in load["note"]

    def test_the_total_is_the_sum_of_its_named_components(self):
        load = desk_mod.desk_load([{}] * 4, [{}] * 3, [{}] * 2)
        # Routing v2 (2026-08-27): the two open requests are the chair's, so
        # the CEO components carry them at zero. v1 read 2 here.
        assert load["components"] == {"open_recommendations": 4,
                                      "pending_orders": 3,
                                      "requests_awaiting_approval": 0}
        assert load["total"] == 7

    def test_the_request_rule_is_ONE_named_function_and_unchanged(self):
        """THE REPAIR THAT SHIPPED, and it is a de-duplication rather than a
        move. This rule used to live untitled inside `desk_items`, with a
        second copy of its consequences in `desk_load` and a THIRD derivation
        in TypeScript — which is how the CEO's page and the spine came to
        disagree by eleven rows the moment the rule was touched.

        The VALUES are routing v2's (2026-08-27, CEO decision, verbatim
        "4. Yes"): open -> chair, approved -> chair, terminal -> nobody. v1
        sent open -> ceo; the flip is the one-line versioned change
        `desk.OPEN_REQUEST_ACTOR` recorded as its own change-of-mind
        condition, taken on the CEO's word with the measurements already
        written there (28 of 49 requests resolved with no approval event -
        the modal path was always the chair serving them).
        """
        assert desk_mod.open_request_actor("open") == "chair"
        assert desk_mod.open_request_actor(None) == "chair"
        assert desk_mod.open_request_actor("approved") == "chair"
        # Terminal is nobody's move — the same rule `next_actor` applies to a
        # terminal recommendation, so a served request cannot sit on a queue.
        assert desk_mod.open_request_actor("resolved") == "nobody"
        assert desk_mod.open_request_actor("declined") == "nobody"

    def test_the_request_census_is_published_beside_the_unchanged_total(self):
        """The finding without the action: a reader can see how the open
        requests would route without the counter having moved. A measurement
        that only exists in a report is a measurement nobody can check."""
        load = desk_mod.desk_load([], [], [{"status": "open"},
                                           {"status": "approved"}])
        # ROUTING v2: both requests are the chair's, and the total says so.
        assert load["total"] == 0
        assert load["requests_by_actor"] == {"ceo": 0, "chair": 2, "seat": 0,
                                             "nobody": 0, "unknown": 0}

    def test_an_unreadable_component_still_makes_the_total_a_floor(self):
        load = desk_mod.desk_load([{}] * 4, None, [{}])
        assert load["complete"] is False
        assert load["unreadable"] == ["pending_orders"]
        assert "at least this" in load["note"]

    def test_the_payload_says_whether_the_count_rests_on_declarations(self):
        """A reader deserves to know that the actor was INFERRED. Today
        nothing writes `next_actor`, so the honest figure is zero — and it
        must be reported, not left for a reader to assume either way."""
        assert desk_mod.desk_load([{"status": "open"}] * 3, [], []
                                  )["explicit_next_actor"] == 0
        assert desk_mod.desk_load(
            [{"status": "accepted", "next_actor": "ceo"}], [], []
        )["explicit_next_actor"] == 1
        assert desk_mod.desk_load([], [], [])["rules_version"] \
            == desk_mod.NEXT_ACTOR_RULES_VERSION

    def test_the_three_legs_are_a_partition_and_never_double_count(self):
        """The first attempt at this breakdown reported "26 elsewhere" beside a
        page saying "6 with the chair" — both true, both counting different
        things, one label apart. Two numbers that sound like one number is the
        defect this module exists to remove, so the legs partition."""
        feed = ([{"status": "open", "kind": "awaits-ceo"}] * 3
                + [{"status": "open", "kind": "build"}] * 5
                + [{"status": "accepted", "kind": "batch"}] * 20
                + [{"status": "staged", "kind": "fix"}] * 2
                + [{"status": "weird"}])
        load = desk_mod.desk_load(feed, [], [])
        assert load["components"]["open_recommendations"] == 4   # 3 ceo + 1 unknown
        assert load["open_elsewhere"] == 5
        assert load["decided_awaiting_execution"] == 22
        assert (load["components"]["open_recommendations"]
                + load["open_elsewhere"]
                + load["decided_awaiting_execution"]) == len(feed)
        # A decided row that STILL needs the CEO belongs to him alone — it is
        # not also "decided, awaiting execution" from his point of view.
        one = desk_mod.desk_load(
            [{"status": "accepted", "next_actor": "ceo"}], [], [])
        assert one["total"] == 1
        assert one["decided_awaiting_execution"] == 0
        assert one["open_elsewhere"] == 0

    def test_the_trigger_boundary_is_unchanged_and_exact(self):
        """The threshold itself did not move — only what feeds it. One item
        below is quiet; the threshold itself fires."""
        n = desk_mod.COO_TRIAGE_THRESHOLD
        assert desk_mod.desk_load([{}] * (n - 1), [], [])["coo_triage_due"] is False
        assert desk_mod.desk_load([{}] * n, [], [])["coo_triage_due"] is True

    def test_bench_output_no_longer_mechanically_summons_the_coo_but_only_partly(
            self):
        """MEASURED, and the honest answer is 'partly' — recorded here so a
        later reader does not inherit a claim the corpus does not support.

        The hope was that ignoring non-CEO rows would decouple the trigger from
        the bench's output volume. Measured over all 219 recommendations in the
        live flight recorder, treating every row as undecided: 41 (18.7%) route
        away from the CEO by kind, and 178 do not. So a six-run day still adds
        real CEO rows. The lever that WOULD decouple it is `next_actor` written
        at filing time.

        This test pins the mechanism, not the ratio: a seat's own engineering
        and handoff output is excluded, and its decisions are not.
        """
        one_seat_run = [{"status": "open", "kind": k} for k in
                        ("harness", "next_dispatch", "handoff_to_mechanism",
                         "no_action", "awaits-ceo", "envelope_change")]
        load = desk_mod.desk_load(one_seat_run, [], [])
        assert load["by_actor"]["ceo"] == 2
        # chair(harness, next_dispatch) + seat(handoff) + nobody(no_action):
        # all four are OPEN and none is the CEO's.
        assert load["open_elsewhere"] == 4
        assert load["by_actor"]["nobody"] == 1
        assert load["decided_awaiting_execution"] == 0


class TestTheRowsCarryTheirOwnVerdict:
    """The count and the list must not be able to disagree.

    They already did once: the CEO desk page kept its own status-label rule and
    the spine's counter kept another, and on one payload they rendered 11 and 6
    for the same question eight pixels apart. The predicate has ONE definition
    and the answer travels ON the row.
    """

    class _Store:
        def __init__(self, recs):
            self._recs = recs

        def runs(self, limit=25):
            return []

        def open_recommendations(self):
            return self._recs

    def _view(self, recs):
        from tests.test_desk import MemStore
        return desk_mod.view(MemStore(), self._Store(recs))

    def test_every_row_carries_the_resolved_actor_and_its_reason(self):
        v = self._view([{"status": "open", "kind": "build", "rec_id": 1},
                        {"status": "accepted", "kind": "awaits-ceo", "rec_id": 2},
                        {"status": "open", "kind": "awaits-ceo", "rec_id": 3}])
        rows = v["open_recommendations"]
        assert [r["next_actor_resolved"] for r in rows] == ["chair", "chair", "ceo"]
        assert [r["next_actor_basis"] for r in rows] == ["kind", "lifecycle", "kind"]
        # The sentence travels too — a surface that showed only the verdict
        # would be asking a reader to trust a routing they cannot inspect.
        assert all(r["next_actor_why"] for r in rows)

    def test_the_annotation_and_the_count_agree_by_construction(self):
        recs = [{"status": "open", "kind": k, "rec_id": i}
                for i, k in enumerate(["build", "awaits-ceo", "no_action",
                                       "handoff_to_quant", "envelope_change"])]
        v = self._view(recs)
        rows = v["open_recommendations"]
        ceo_rows = [r for r in rows
                    if r["next_actor_resolved"] in ("ceo", "unknown")]
        assert len(ceo_rows) == v["desk_load"]["components"]["open_recommendations"]

    def test_annotating_does_not_disturb_an_explicit_declaration(self):
        """`next_actor_resolved` is a derived field. It must never be mistaken
        for the seat's own `next_actor` on a later pass — a derived value fed
        back in as a declaration is how an inference becomes a fact nobody
        stated."""
        v = self._view([{"status": "accepted", "next_actor": "ceo", "rec_id": 1}])
        row = v["open_recommendations"][0]
        assert row["next_actor"] == "ceo"
        assert row["next_actor_resolved"] == "ceo"
        assert row["next_actor_basis"] == "explicit"
        assert desk_mod.next_actor(row)["basis"] == "explicit"

    def test_a_non_dict_row_survives_annotation(self):
        v = self._view(["not a row"])
        assert v["open_recommendations"] == ["not a row"]
        assert v["desk_load"]["by_actor"]["unknown"] == 1


def test_a_due_date_is_validated_never_parsed_out_of_prose():
    """The desk's TOP ranking key. A malformed date would sort
    lexicographically against real ones and put a row silently in the wrong
    place, which is worse than the row carrying no date at all."""
    pytest.importorskip("psycopg")
    from app.fund.deskstore import _due_date
    assert _due_date("2026-09-08") == "2026-09-08"
    assert _due_date("  2026-09-08 ") == "2026-09-08"
    for junk in ("Sept 8", "2026-9-8", "2026-09-08T00:00:00Z", "", None, 20260908,
                 "the 2026-09-08 auto-close"):
        assert _due_date(junk) is None, junk


def test_a_stated_reversibility_is_validated_against_a_closed_set():
    """The desk's SECOND ranking key. A free string would put a row in a band
    the comparator does not know about, which sorts as undefined rather than as
    wrong — the worst of the three outcomes."""
    pytest.importorskip("psycopg")
    from app.fund.deskstore import _reversibility
    for good in ("hard", "IRREVERSIBLE", " reversible "):
        assert _reversibility(good) == good.strip().lower()
    for junk in ("unclassified", "very hard", "", None, 3, "revertible"):
        assert _reversibility(junk) is None, junk


def test_the_two_terminal_lists_agree():
    """`desk` keeps its own copy so it stays importable without a database.
    Two definitions of "finished" that drift is how a surface counts work that
    is done — the exact complaint this file is written against."""
    pytest.importorskip("psycopg")
    from app.fund import deskstore
    assert tuple(desk_mod.TERMINAL_STATUSES) == \
        tuple(deskstore.TERMINAL_REC_STATUSES)
    for s in desk_mod.TERMINAL_STATUSES:
        assert s in deskstore.REC_STATUSES
