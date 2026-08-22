"""The friction view — desk requests folded forward, aged, oldest first.

Written from the secretary's first friction ledger (2026-08-21): **28 requests
approved and undispatched at midnight, all waiting on the chair, oldest
14h34m, only 3 of 28 answered the next day.** She assembled it by hand from
raw events and it cost most of a 26-minute dispatch. It is one call now.

Three properties are load-bearing and each has a measured incident behind it:

  * **`DeskDispatched` NEVER ENTERS THE FOLD.** 14 of 24 live dispatch events
    carry no `request_id`, and one names a `request_id` that was never filed.
    A fold that included them creates a phantom request with a `None` id which
    then ages forever at the top of an oldest-first list.
  * **THE FOLD IS ORDER-HONEST.** A resolution must never overwrite a decline
    — executing a declined ask is the chair overriding the CEO's no, and a
    view that shows it as resolved hides exactly that.
  * **THE UNDISPATCHED COUNT IS AN UPPER BOUND AND SAYS SO.** With half the
    dispatch events unlinkable, "30 undispatched" is a ceiling. A confident
    number resting on an instrument that cannot see half its input is the
    defect class this firm keeps finding.
"""

from datetime import datetime, timezone

from app.fund import metrics


NOW = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self, events):
        self._events = list(events)

    def stream(self, since_seq=0, limit=200):
        return [e for e in self._events if e.get("seq", 0) > since_seq][:limit]


def ev(seq, type_, ts, payload, actor="ceo"):
    return {"seq": seq, "type": type_, "ts": ts, "actor": actor,
            "payload": payload}


def requested(seq, rid, at, **kw):
    return ev(seq, "DeskRequested", at, {"request_id": rid, "at": at, **kw})


def approved(seq, rid, at, actor="ceo"):
    return ev(seq, "DeskRequestApproved", at,
              {"request_id": rid, "at": at, "actor": actor}, actor=actor)


def resolved(seq, rid, at):
    return ev(seq, "DeskRequestResolved", at,
              {"request_id": rid, "at": at, "resolution": "done"}, actor="cto")


def declined(seq, rid, at):
    return ev(seq, "DeskRequestDeclined", at,
              {"request_id": rid, "at": at, "reason": "no"})


def dispatched(seq, at, rid=None):
    p = {"at": at, "seat": "builder", "task_id": "t1"}
    if rid:
        p["request_id"] = rid
    return ev(seq, "DeskDispatched", at, p, actor="cto")


# --- the states -------------------------------------------------------------

def test_approved_but_undispatched_is_a_FIRST_CLASS_state():
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00", subject="do a thing",
                  serves="pm"),
        approved(2, "r1", "2026-08-21T09:26:00+00:00"),
    ])
    got = metrics.friction(store, now=NOW)
    row = got["requests"][0]
    assert row["state"] == "approved_undispatched"
    assert row["waiting_on"] == "chair"
    assert row["terminal"] is False
    assert got["approved_undispatched"] == 1
    assert got["by_state"]["approved_undispatched"] == 1


def test_a_dispatched_approved_request_leaves_the_undispatched_queue():
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        approved(2, "r1", "2026-08-21T09:30:00+00:00"),
        dispatched(3, "2026-08-21T10:00:00+00:00", rid="r1"),
    ])
    got = metrics.friction(store, now=NOW)
    assert got["requests"][0]["state"] == "approved_dispatched"
    assert got["requests"][0]["dispatch_seen"] is True
    assert got["approved_undispatched"] == 0
    assert got["requests"][0]["waiting_on"] == "seat"


def test_an_open_request_waits_on_the_CEO():
    store = FakeStore([requested(1, "r1", "2026-08-21T09:00:00+00:00")])
    got = metrics.friction(store, now=NOW)
    assert got["requests"][0]["state"] == "open"
    assert got["requests"][0]["waiting_on"] == "ceo"
    assert got["waiting_on"] == {"ceo": 1}


# --- the fold's honesty -----------------------------------------------------

def test_a_dispatch_event_with_NO_request_id_creates_no_phantom_row():
    """14 of 24 live DeskDispatched carry no request_id. A fold that included
    them invents a request keyed None, which then sorts to the top of an
    oldest-first list and never leaves."""
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        dispatched(2, "2026-08-21T10:00:00+00:00"),
        dispatched(3, "2026-08-21T11:00:00+00:00"),
    ])
    got = metrics.friction(store, now=NOW)
    assert got["count"] == 1
    assert [r["request_id"] for r in got["requests"]] == ["r1"]
    assert got["dispatch_link_coverage"]["unlinkable_no_request_id"] == 2
    assert got["dispatch_link_coverage"]["complete"] is False


def test_a_dispatch_naming_a_request_that_was_never_filed_is_counted_not_folded():
    """One such event is live in the log today."""
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        dispatched(2, "2026-08-21T10:00:00+00:00", rid="ghost"),
    ])
    got = metrics.friction(store, now=NOW)
    assert got["count"] == 1
    assert got["dispatch_link_coverage"]["orphan_request_id"] == 1
    assert "never filed" in got["note"]


def test_the_undispatched_figure_is_declared_an_UPPER_BOUND_when_links_are_missing():
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        approved(2, "r1", "2026-08-21T09:30:00+00:00"),
        dispatched(3, "2026-08-21T10:00:00+00:00"),   # unlinkable
    ])
    got = metrics.friction(store, now=NOW)
    assert got["approved_undispatched"] == 1
    assert got["requests"][0]["dispatch_detectable"] is False
    assert "UPPER BOUND" in got["note"]


def test_dispatch_detectable_is_TRUE_only_when_every_dispatch_links():
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        approved(2, "r1", "2026-08-21T09:30:00+00:00"),
        dispatched(3, "2026-08-21T10:00:00+00:00", rid="r1"),
    ])
    got = metrics.friction(store, now=NOW)
    assert got["requests"][0]["dispatch_detectable"] is True
    assert "UPPER BOUND" not in got["note"]


def test_a_resolution_does_NOT_overwrite_a_decline():
    """Executing a declined ask is the chair overriding the CEO's no. A view
    that renders it `resolved` hides the one thing worth seeing."""
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        declined(2, "r1", "2026-08-21T10:00:00+00:00"),
        resolved(3, "r1", "2026-08-21T11:00:00+00:00"),
    ])
    got = metrics.friction(store, now=NOW)
    assert got["requests"][0]["state"] == "declined"


def test_an_approval_does_NOT_reopen_a_resolved_request():
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        resolved(2, "r1", "2026-08-21T10:00:00+00:00"),
        approved(3, "r1", "2026-08-21T11:00:00+00:00"),
    ])
    assert metrics.friction(store, now=NOW)["requests"][0]["state"] == "resolved"


def test_a_seat_filed_ask_is_normalised_so_it_does_not_render_blank():
    """Seat asks write subject/serves where CEO-typed requests write task/seat.
    Two of twenty open items were invisible on the CEO's desk for this reason
    (2026-08-21)."""
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00",
                  subject="close R8", serves="pm"),
    ])
    row = metrics.friction(store, now=NOW)["requests"][0]
    assert row["task"] == "close R8"
    assert row["seat"] == "pm"


# --- ageing and ordering ----------------------------------------------------

def test_rows_are_sorted_OLDEST_FIRST_by_age_since_filing():
    store = FakeStore([
        requested(1, "new", "2026-08-21T20:00:00+00:00"),
        requested(2, "old", "2026-08-21T04:00:00+00:00"),
        requested(3, "mid", "2026-08-21T12:00:00+00:00"),
    ])
    got = metrics.friction(store, now=NOW)
    assert [r["request_id"] for r in got["requests"]] == ["old", "mid", "new"]
    assert got["requests"][0]["age_hours"] == 20.0
    assert got["oldest_open_hours"] == 20.0
    assert got["oldest_open_request_id"] == "old"


def test_a_row_whose_filing_time_cannot_be_read_ages_UNKNOWN_and_sorts_LAST():
    """None is not "brand new" and it is certainly not "zero hours old" — a
    zero would put an unreadable row at the top of a queue ranked by age."""
    store = FakeStore([
        requested(1, "bad", "not-a-timestamp"),
        requested(2, "good", "2026-08-21T04:00:00+00:00"),
    ])
    got = metrics.friction(store, now=NOW)
    assert [r["request_id"] for r in got["requests"]] == ["good", "bad"]
    assert got["requests"][1]["age_hours"] is None


def test_age_in_state_is_measured_from_the_LAST_transition():
    store = FakeStore([
        requested(1, "r1", "2026-08-21T00:00:00+00:00"),
        approved(2, "r1", "2026-08-21T18:00:00+00:00"),
    ])
    row = metrics.friction(store, now=NOW)["requests"][0]
    assert row["age_hours"] == 24.0
    assert row["age_in_state_hours"] == 6.0


def test_terminal_rows_wait_on_nobody_and_leave_the_open_count():
    store = FakeStore([
        requested(1, "r1", "2026-08-21T09:00:00+00:00"),
        resolved(2, "r1", "2026-08-21T10:00:00+00:00"),
        requested(3, "r2", "2026-08-21T09:00:00+00:00"),
    ])
    got = metrics.friction(store, now=NOW)
    assert got["count"] == 2
    assert got["open_count"] == 1
    assert got["waiting_on"] == {"ceo": 1}
    done = [r for r in got["requests"] if r["request_id"] == "r1"][0]
    assert done["waiting_on"] is None and done["terminal"] is True


def test_by_state_sums_to_the_row_count():
    store = FakeStore([
        requested(1, "a", "2026-08-21T01:00:00+00:00"),
        requested(2, "b", "2026-08-21T02:00:00+00:00"),
        approved(3, "b", "2026-08-21T03:00:00+00:00"),
        requested(4, "c", "2026-08-21T04:00:00+00:00"),
        declined(5, "c", "2026-08-21T05:00:00+00:00"),
        requested(6, "d", "2026-08-21T06:00:00+00:00"),
        resolved(7, "d", "2026-08-21T07:00:00+00:00"),
    ])
    got = metrics.friction(store, now=NOW)
    assert sum(got["by_state"].values()) == got["count"] == 4


def test_the_ordering_is_stable_across_identical_calls():
    """An unstable sort makes two identical reads look like a change."""
    store = FakeStore([
        requested(1, "b", "2026-08-21T09:00:00+00:00"),
        requested(2, "a", "2026-08-21T09:00:00+00:00"),
    ])
    first = [r["request_id"] for r in metrics.friction(store, now=NOW)["requests"]]
    second = [r["request_id"] for r in metrics.friction(store, now=NOW)["requests"]]
    assert first == second == ["a", "b"]
