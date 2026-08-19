"""The desk must render the firm honestly — kills as kills, absences as absences.

Two lies this surface could tell, both pinned here: an unreviewed artifact shown
as surviving (absence scored as a value), and a request that evaporates on
restart (a toast wearing the costume of a commitment).
"""

from __future__ import annotations

from app.fund import desk
from app.fund.events import Event, EventType


class MemStore:
    def __init__(self):
        self.events = []

    def append(self, e):
        self.events.append(e)
        return e

    def stream(self, since_seq=0, limit=100_000):
        return [{"type": e.type.value, "payload": e.payload} for e in self.events]


def test_the_view_reads_real_artifacts_and_pairs_them_with_verdicts():
    """Runs against the actual docs/ tree — the files ARE the state."""
    v = desk.view(MemStore())
    assert len(v["roster"]) == 3
    assert {r["agent"] for r in v["roster"]} == {"mechanism", "adversary",
                                                 "validator"}
    # Both known artifacts are on the desk and both were killed with a review
    # on file. If this fails after adding artifacts, the pairing broke — check
    # the "Artifact attacked:" line in the review.
    by_path = {a["path"]: a for a in v["artifacts"]}
    vrp = by_path.get("docs/proposals/VRP_XYLD_2026-08-19.md")
    assert vrp is not None
    assert vrp["status"] == "killed"
    assert vrp["review"] and vrp["review"]["verdict"] == "KILL"
    assert v["kills"] >= 2


def test_an_unreviewed_artifact_is_not_shown_as_surviving(tmp_path, monkeypatch):
    monkeypatch.setattr(desk, "DOCS", tmp_path)
    (tmp_path / "proposals").mkdir()
    (tmp_path / "proposals" / "NEW_IDEA_2026-08-20.md").write_text(
        "# A new idea\n\nno review yet\n", encoding="utf-8")
    v = desk.view(MemStore())
    a = v["artifacts"][0]
    assert a["status"] == "under_review"
    assert "unreviewed is not the same as surviving" in a["note"]
    assert v["kills"] == 0


def test_requests_fold_from_the_event_log_and_survive_resolution():
    store = MemStore()
    store.append(Event(aggregate_id="r1", aggregate_type="desk_request",
                       type=EventType.DESK_REQUESTED,
                       payload={"request_id": "r1", "kind": "attack",
                                "serves": "adversary", "subject": "the sieve",
                                "at": "2026-08-20T00:00:00Z"}, actor="operator"))
    v = desk.view(store)
    assert v["open_requests"] == 1
    assert v["requests"][0]["subject"] == "the sieve"

    store.append(Event(aggregate_id="r1", aggregate_type="desk_request",
                       type=EventType.DESK_REQUEST_RESOLVED,
                       payload={"request_id": "r1",
                                "resolution": "docs/reviews/X.md",
                                "at": "2026-08-20T01:00:00Z"}, actor="cto"))
    v = desk.view(store)
    assert v["open_requests"] == 0
    assert v["requests"][0]["status"] == "resolved"
    assert v["requests"][0]["resolution"] == "docs/reviews/X.md"


def test_the_execution_honesty_line_is_in_the_payload():
    """The one lie this page must never tell: that the spine can think."""
    v = desk.view(MemStore())
    assert "does not run agents" in v["execution_note"]
