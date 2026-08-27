"""THE FIVE ACTION TAGS (CEO instruction 2026-08-28: "I want simpler action
oriented tags. Pending, In FLight, Executed, Deprioritised, Completed").

Pins the fold's whole mapping and its two direction rules: an unreadable
status must land in ``pending`` (never quietly retire a row), and a
supersession edge outranks the stored status.
"""
from app.fund import deskcard
from app.fund.desk import _annotated


def tag(row):
    return deskcard.action_tag(row)["action_tag"]


class TestTheMapping:
    def test_open_is_pending(self):
        assert tag({"status": "open"}) == "pending"

    def test_absent_status_is_pending(self):
        assert tag({}) == "pending"

    def test_decided_statuses_are_in_flight(self):
        for s in ("accepted", "staged", "approved", "dispatched"):
            assert tag({"status": s}) == "in_flight", s

    def test_done_is_executed(self):
        assert tag({"status": "done"}) == "executed"

    def test_closed_without_an_act_is_completed(self):
        for s in ("resolved", "noted"):
            assert tag({"status": s}) == "completed", s

    def test_human_no_is_deprioritised(self):
        for s in ("rejected", "declined", "shelved", "deferred",
                  "superseded", "killed"):
            assert tag({"status": s}) == "deprioritised", s

    def test_labels_cover_every_tag(self):
        assert set(deskcard.ACTION_TAG_LABELS) == set(deskcard.ACTION_TAGS)


class TestTheDirectionRules:
    def test_unreadable_status_is_pending_and_says_so(self):
        got = deskcard.action_tag({"status": "wibble"})
        assert got["action_tag"] == "pending"
        assert got["action_tag_basis"].startswith("unreadable")

    def test_non_dict_row_is_pending_unreadable(self):
        got = deskcard.action_tag(None)
        assert got["action_tag"] == "pending"
        assert got["action_tag_basis"] == "unreadable"

    def test_supersession_outranks_status(self):
        # A superseded row is not actionable whatever its status still says.
        got = deskcard.action_tag({"status": "open",
                                   "supersession": {"mode": "superseded"}})
        assert got["action_tag"] == "deprioritised"
        assert got["action_tag_basis"] == "supersession"


class TestTheTagRidesTheRow:
    def test_annotated_rows_carry_the_tag(self):
        out = _annotated({"rec_id": 1, "status": "accepted",
                          "text": "do the thing", "next_actor": "chair"})
        assert out["action_tag"] == "in_flight"
        assert out["action_tag_label"] == "In flight"
        # The band fold still rides the same row: the tag does not replace it.
        assert "band" in out
