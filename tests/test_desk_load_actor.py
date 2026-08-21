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
        assert load["total"] == 13
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
        assert load["not_ceo_load"] == 2
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

    def test_the_total_is_still_the_sum_of_its_named_components(self):
        load = desk_mod.desk_load([{}] * 4, [{}] * 3, [{}] * 2)
        assert load["components"] == {"open_recommendations": 4,
                                      "pending_orders": 3,
                                      "requests_awaiting_approval": 2}
        assert load["total"] == 9

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
        assert load["not_ceo_load"] == 3
        assert load["by_actor"]["nobody"] == 1


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
