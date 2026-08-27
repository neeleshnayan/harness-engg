"""THE DESK'S PRIORITY BANDS — high to low, and never inferred.

CEO DECISION 2026-08-27, verbatim: *"can we add ordering to my desk say
high-priority to low; time-sensitive or not; blocker or not?"*

THREE BANDS: blocker · time-sensitive · the rest. The whole design rests on
one rule and these tests exist to defend it: **a band is derived from DECLARED
FACTS and never inferred.** A renderer that read urgency out of a sentence
would be manufacturing priority, which is the same class of mistake as reading
a deadline out of prose — a mistake this desk has already been repaired from
twice.

THE PREMISE THAT FAILED, recorded because it is the reason `deskstore` is in
this diff at all. The direction stated that *"recommendation dicts on POST
/fund/desk/runs pass arbitrary keys through today"*. They do not.
`AgentRunRecord.recommendations` is `Optional[list[dict]]`, so Pydantic does
not REFUSE an unknown key — but `deskstore.build_recommendations` rebuilds
every row field by field, and a key with no line there is silently dropped. A
band fold shipped without the storage line would have been a chip that could
never light: a control with no caller, this firm's named worst failure.
`test_a_filed_blocks_flag_SURVIVES_STORAGE` is that fact, pinned.

Every test below fails if one of these comes back:

  1. urgency inferred from text, kind, seat or age;
  2. a truthy non-boolean promoted into the loudest band;
  3. an unreadable declaration reported as an absent one;
  4. absent money sorted as zero;
  5. `blocks` dropped on the way into the record.
"""

from __future__ import annotations

import pytest

from app.fund import desk
from app.fund.deskstore import build_recommendations


# ---------------------------------------------------------- the three bands --

def test_a_declared_blocker_is_band_one():
    b = desk.desk_band({"text": "x", "blocks": True})
    assert b["band"] == "blocker"
    assert b["band_rank"] == 1
    assert b["band_basis"] == "declared"
    assert b["band_label"] == "blocker"


def test_a_dated_row_is_band_two():
    b = desk.desk_band({"text": "x", "due_date": "2026-09-05"})
    assert (b["band"], b["band_rank"], b["band_basis"]) == \
        ("time_sensitive", 2, "due_date")
    assert b["band_label"] == "dated"


def test_everything_else_is_band_three_WITH_NO_CHIP():
    b = desk.desk_band({"text": "x"})
    assert (b["band"], b["band_rank"], b["band_basis"]) == \
        ("rest", 3, "undeclared")
    # An empty string, not "normal" or "low": a chip needs a fact, and
    # "nobody said" is not a priority level. The renderer draws nothing.
    assert b["band_label"] == ""
    assert "Nobody said" in b["band_note"]


def test_a_blocker_outranks_its_own_date():
    """Band first, always. A blocker with a far date still beats a dated row."""
    b = desk.desk_band({"blocks": True, "due_date": "2027-01-01"})
    assert b["band"] == "blocker"


# ------------------------------------------------- never inferred, ever ------

@pytest.mark.parametrize("row", [
    {"text": "THIS BLOCKS EVERYTHING and is URGENT and CRITICAL"},
    {"text": "x", "kind": "blocker"},
    {"text": "x", "kind": "envelope_v2", "seat": "riskofficer"},
    {"text": "x", "money_at_stake": 1_000_000.0},
    {"text": "x", "reversibility": "irreversible"},
    {"text": "x", "resolved_at": "2020-01-01T00:00:00+00:00"},
])
def test_urgency_is_NEVER_read_out_of_text_kind_seat_money_or_age(row):
    """THE RULE. Every one of these rows screams urgent to a human and none of
    them DECLARES anything, so every one is band 3 with no chip. A fold that
    promoted any of them would be manufacturing priority."""
    b = desk.desk_band(row)
    assert b["band"] == "rest"
    assert b["band_label"] == ""


@pytest.mark.parametrize("truthy", ["true", "True", "yes", 1, [1], {"a": 1}])
def test_a_TRUTHY_NON_BOOLEAN_is_refused_and_reported_UNREADABLE(truthy):
    """Coercion here only ever PROMOTES, so a filer who typos a flag would
    jump the CEO's queue by accident. Same argument as routing_version's
    StrictInt, one layer out."""
    b = desk.desk_band({"text": "x", "blocks": truthy})
    assert b["band"] == "rest"
    assert b["band_basis"] == "unreadable"
    assert "could not read the answer" in b["band_note"]
    assert "not as no" in b["band_note"]


def test_an_UNREADABLE_declaration_is_not_the_same_as_an_ABSENT_one():
    """The two must not collapse: one is a defect in the filing, the other is
    a question nobody has been asked."""
    assert desk.desk_band({"blocks": "maybe"})["band_basis"] == "unreadable"
    assert desk.desk_band({})["band_basis"] == "undeclared"
    assert desk.desk_band({"blocks": None})["band_basis"] == "unreadable"


def test_a_declared_FALSE_is_its_own_basis_not_silence():
    """A seat that thought about it and said no is a different record from a
    seat that never answered — and the desk can count the difference."""
    assert desk.desk_band({"blocks": False})["band_basis"] == "not_blocking"
    assert desk.desk_band({})["band_basis"] == "undeclared"


def test_a_declared_FALSE_still_reaches_band_two_on_its_date():
    b = desk.desk_band({"blocks": False, "due_date": "2026-09-05"})
    assert b["band"] == "time_sensitive"
    assert b["band_basis"] == "not_blocking"


@pytest.mark.parametrize("bad_due", ["", "   ", None, 20260905])
def test_an_unusable_due_date_does_not_promote_to_band_two(bad_due):
    assert desk.desk_band({"due_date": bad_due})["band"] == "rest"


def test_a_non_dict_row_is_band_three_and_says_it_could_not_be_read():
    for junk in ["a string", None, 7, ["a", "list"]]:
        b = desk.desk_band(junk)
        assert b["band"] == "rest"
        assert "could not be read" in b["band_note"]


# --------------------------------------------------------------- the order --

def test_the_full_order_is_band_then_date_then_money():
    rows = [
        {"rec_id": "e", "money_at_stake": 5.0},
        {"rec_id": "d", "money_at_stake": 500.0},
        {"rec_id": "c", "due_date": "2026-09-05"},
        {"rec_id": "b", "due_date": "2026-09-01"},
        {"rec_id": "a", "blocks": True},
        {"rec_id": "f"},
    ]
    assert [r["rec_id"] for r in desk.rank_desk_rows(rows)] == \
        ["a", "b", "c", "d", "e", "f"]


def test_within_the_BLOCKER_band_the_tiebreak_is_date_then_money():
    rows = [
        {"rec_id": "money", "blocks": True, "money_at_stake": 900.0},
        {"rec_id": "dated", "blocks": True, "due_date": "2026-09-01"},
        {"rec_id": "bare", "blocks": True},
    ]
    assert [r["rec_id"] for r in desk.rank_desk_rows(rows)] == \
        ["dated", "money", "bare"]


def test_ABSENT_MONEY_SORTS_LAST_and_BEHIND_a_stated_zero():
    """Absence is never zero — including in a sort, which is one of the places
    the two quietly become the same thing."""
    rows = [
        {"rec_id": "absent"},
        {"rec_id": "zero", "money_at_stake": 0.0},
        {"rec_id": "small", "money_at_stake": 0.01},
    ]
    assert [r["rec_id"] for r in desk.rank_desk_rows(rows)] == \
        ["small", "zero", "absent"]


def test_a_BOOLEAN_money_figure_is_not_treated_as_a_number():
    """`True` is `1` in Python arithmetic and would sort above a stated $0."""
    rows = [{"rec_id": "bool", "money_at_stake": True},
            {"rec_id": "real", "money_at_stake": 0.5}]
    assert [r["rec_id"] for r in desk.rank_desk_rows(rows)] == ["real", "bool"]


def test_the_order_is_STABLE_for_otherwise_identical_rows():
    """Two rows alike in every ranking key must not shuffle between renders."""
    rows = [{"rec_id": "b"}, {"rec_id": "a"}, {"rec_id": "c"}]
    once = [r["rec_id"] for r in desk.rank_desk_rows(rows)]
    twice = [r["rec_id"] for r in desk.rank_desk_rows(list(reversed(rows)))]
    assert once == twice == ["a", "b", "c"]


def test_ranking_does_not_mutate_or_alias_the_caller_s_list():
    rows = [{"rec_id": "b"}, {"rec_id": "a"}]
    out = desk.rank_desk_rows(rows)
    assert [r["rec_id"] for r in rows] == ["b", "a"]
    assert out is not rows


def test_ranking_an_empty_or_absent_list_is_empty_and_does_not_raise():
    assert desk.rank_desk_rows([]) == []
    assert desk.rank_desk_rows(None) == []


# ------------------------------------------------- ONE fold, every surface ---

def test_recommendations_and_requests_are_banded_by_THE_SAME_function():
    """The console merges both populations into one ranked list. Two
    implementations of one priority rule is two priority rules, and the day
    they disagree the disagreement is invisible — each surface looks
    internally consistent."""
    rec = desk._annotated({"run_id": "r", "rec_id": 1, "text": "x",
                           "blocks": True})
    req = desk._annotated_request({"request_id": "q", "subject": "y",
                                   "status": "approved", "blocks": True})
    assert rec["band"] == req["band"] == "blocker"
    assert rec["band_rank"] == req["band_rank"] == 1
    assert rec["band_basis"] == req["band_basis"] == "declared"


def test_the_band_annotation_does_not_disturb_the_routing_fields():
    """The band spread sits ahead of the routing keys on purpose: a band field
    must never be able to overwrite a next-actor field."""
    rec = desk._annotated({"run_id": "r", "rec_id": 1, "text": "x",
                           "next_actor": "ceo", "blocks": True})
    assert rec["next_actor_resolved"] == "ceo"
    assert rec["text"] == "x"
    assert rec["band"] == "blocker"


def test_a_live_shaped_request_bands_as_UNDECLARED_not_as_low_priority():
    """Measured against the live record 2026-08-27: a desk request carries
    neither `blocks` nor `due_date`, so every one lands in band 3 with basis
    `undeclared`. That is the truthful reading and NOT a gap — nobody has been
    asked to declare it yet, and the chip is absent rather than saying 'low'."""
    req = desk._annotated_request({
        "request_id": "910c480a", "kind": "audit", "serves": "builder",
        "subject": "SLICE 3 CHARTER", "status": "approved", "actor": "cto",
        "at": "2026-08-27T06:18:24.479125+00:00"})
    assert req["band"] == "rest"
    assert req["band_basis"] == "undeclared"
    assert req["band_label"] == ""


# ------------------------------------------------------------ the door ------

def test_a_filed_blocks_flag_SURVIVES_STORAGE():
    """THE PREMISE THAT FAILED, PINNED.

    `build_recommendations` rebuilds every row field by field, so a key with
    no line there is silently dropped — no error, no warning, nothing on the
    wire. Without this the band could never be `blocker` for any row ever
    filed, and the chip would have been a control with no caller.
    """
    out = build_recommendations([{"kind": "fix", "text": "do it",
                                  "blocks": True}],
                                seat="builder", trace_id=None)
    assert out[0]["blocks"] is True
    assert desk.desk_band(out[0])["band"] == "blocker"


def test_a_GARBLED_blocks_flag_survives_storage_TOO():
    """Dropping it would turn a filer's garbled answer into 'nobody said', and
    those are different facts with different fixes. Presence is preserved;
    meaning is read once, in `desk_band`."""
    out = build_recommendations([{"text": "x", "blocks": "yes"}],
                                seat="builder", trace_id=None)
    assert out[0]["blocks"] == "yes"
    assert desk.desk_band(out[0])["band_basis"] == "unreadable"


def test_a_row_that_never_mentions_blocks_gains_NO_key():
    """Absent must stay absent through storage: a stored `blocks: None` would
    read as `unreadable` — a filer who wrote the key and said nothing — when
    in fact nobody wrote anything."""
    out = build_recommendations([{"text": "x"}], seat="builder", trace_id=None)
    assert "blocks" not in out[0]
    assert desk.desk_band(out[0])["band_basis"] == "undeclared"


def test_storage_still_carries_every_field_it_carried_before():
    """The additive promise at the door, as an assertion."""
    out = build_recommendations(
        [{"kind": "fix", "text": "do it", "money_at_stake": 12.5,
          "next_actor": "ceo", "due_date": "2026-09-05",
          "reversibility": "hard", "blocks": True}],
        seat="builder", trace_id="tr")[0]
    assert out["kind"] == "fix"
    assert out["text"] == "do it"
    assert out["money_at_stake"] == 12.5
    assert out["next_actor"] == "ceo"
    assert out["due_date"] == "2026-09-05"
    assert out["reversibility"] == "hard"
    assert out["seat"] == "builder"
    assert out["trace_id"] == "tr"
    assert out["rec_id"] == 1
    assert out["status"] == "open"
