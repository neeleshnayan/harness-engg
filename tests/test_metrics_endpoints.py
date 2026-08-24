"""The metrics endpoints — one call each, and the traps they must not fall in.

THE ROUTE-ORDERING TRAP IS THE SHARPEST THING IN THIS FILE. FastAPI matches
routes in DECLARATION order, so `GET /fund/desk/runs/stats` declared after
`GET /fund/desk/runs/{run_id}` is unreachable: the literal path is swallowed by
the parameter and the endpoint returns `404 no run stats` — a plausible-looking
404 for a route that exists. A test pins the order because reading the file top
to bottom is exactly how this gets reintroduced by the next person appending a
route at the end.

The rest guard the same property the module guards: a section that cannot be
computed says UNKNOWN, and a rollup is never authoritative over the log.
"""

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient


class Store:
    """Enough of an event store for the read paths."""

    def __init__(self, events=None):
        self._events = list(events or [])

    def stream(self, since_seq=0, limit=200):
        return [e for e in self._events if e.get("seq", 0) > since_seq][:limit]


def ev(seq, type_, ts, payload=None, actor="system"):
    return {"seq": seq, "type": type_, "ts": ts, "actor": actor,
            "payload": payload or {}}


def _client(monkeypatch, store, deskstore=None, metricsstore=None):
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_deskstore", lambda: deskstore)
    monkeypatch.setattr(fundapi, "_metricsstore", lambda: metricsstore)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


# --- the route-ordering trap ------------------------------------------------

def test_runs_stats_is_declared_BEFORE_the_run_id_parameter_route():
    """If `/fund/desk/runs/stats` is registered after `/fund/desk/runs/{run_id}`
    it is unreachable and returns a plausible 404. Pinned by index, in the
    router's own route table, so appending a route at the end of the file
    cannot quietly break it."""
    from app.api.v1 import fund as fundapi
    paths = [getattr(r, "path", "") for r in fundapi.router.routes]
    assert "/fund/desk/runs/stats" in paths
    assert "/fund/desk/runs/{run_id}" in paths
    assert paths.index("/fund/desk/runs/stats") < \
        paths.index("/fund/desk/runs/{run_id}"), (
            "the literal /stats route is shadowed by the {run_id} parameter")


def test_runs_stats_actually_RESOLVES_over_HTTP(monkeypatch):
    """The index assertion above is necessary and not sufficient — this proves
    the request lands on the stats handler and not on the 404."""
    class DS:
        def all_runs(self, limit=100_000):
            return [{"seat": "builder", "tokens": 7, "tool_uses": 2}]

        def run_count(self):
            return 1

    r = _client(monkeypatch, Store(), deskstore=DS()).get(
        "/api/v1/fund/desk/runs/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_runs"] == 1
    assert body["by_seat"]["builder"]["tokens"] == 7
    assert body["truncated"] is False


def test_runs_stats_reports_UNKNOWN_when_the_recorder_is_absent(monkeypatch):
    r = _client(monkeypatch, Store(), deskstore=None).get(
        "/api/v1/fund/desk/runs/stats")
    assert r.status_code == 200
    assert r.json()["state"] == "UNKNOWN"
    assert r.json()["reason"] == "RECORDER_UNREACHABLE"


# --- the daily rollup -------------------------------------------------------

def test_daily_returns_the_whole_day_in_ONE_call(monkeypatch):
    store = Store([
        ev(1, "NavStruck", "2026-08-21T09:00:00+00:00",
           {"total_nav_usd": 2000}),
        ev(2, "OrderFilled", "2026-08-21T10:00:00+00:00",
           {"avg_price": "10", "filled_qty": "2", "venue": "alpaca",
            "side": "buy"}),
        ev(3, "ReconciliationMismatch", "2026-08-21T11:00:00+00:00", {}),
        ev(4, "DeskRequested", "2026-08-21T12:00:00+00:00",
           {"request_id": "r1", "at": "2026-08-21T12:00:00+00:00"}),
    ])
    r = _client(monkeypatch, store).get("/api/v1/fund/metrics/daily?date=2026-08-21")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["day"] == "2026-08-21"
    assert b["events"]["total"] == 4
    assert b["nav"]["close_usd"] == 2000.0
    assert b["fills"]["notional_usd"] == pytest.approx(20.0)
    assert b["reconciliation_mismatches"] == 1
    assert b["desk_requests"]["filed"] == 1


def test_daily_refuses_a_malformed_date_with_422_rather_than_serving_today(monkeypatch):
    r = _client(monkeypatch, Store()).get("/api/v1/fund/metrics/daily?date=last-tuesday")
    assert r.status_code == 422


def test_daily_says_NO_ROLLUP_RECORDED_rather_than_implying_agreement(monkeypatch):
    """`agrees` is None when nothing is stored. False would read as "the cache
    is wrong" when the truth is "there is no cache"."""
    r = _client(monkeypatch, Store()).get("/api/v1/fund/metrics/daily?date=2026-08-21")
    stored = r.json()["stored"]
    assert stored["present"] is None
    assert "only under FUND_STORE=postgres" in stored["note"]


def test_daily_reports_a_STALE_stored_row_as_disagreeing(monkeypatch):
    """The rollup is never authoritative. If the recorded digest no longer
    matches a fresh fold, the reader is told — the live figures still win."""
    class MS:
        def stored(self, day):
            return {"day": day, "digest": "stale-digest",
                    "metrics_version": "v0", "computed_at": "2026-08-21T00:00:00+00:00"}

    store = Store([ev(1, "NavStruck", "2026-08-21T09:00:00+00:00",
                      {"total_nav_usd": 2000})])
    b = _client(monkeypatch, store, metricsstore=MS()).get(
        "/api/v1/fund/metrics/daily?date=2026-08-21").json()
    assert b["stored"]["present"] is True
    assert b["stored"]["agrees"] is False
    assert "DISAGREES" in b["stored"]["note"]
    # And the live numbers are unaffected by the stale row.
    assert b["nav"]["close_usd"] == 2000.0


def test_daily_reports_a_matching_stored_row_as_agreeing(monkeypatch):
    from app.fund import metrics
    store = Store([ev(1, "NavStruck", "2026-08-21T09:00:00+00:00",
                      {"total_nav_usd": 2000})])
    fresh = metrics.compute_daily("2026-08-21", store)

    class MS:
        def stored(self, day):
            return {"day": day, "digest": fresh["digest"],
                    "metrics_version": fresh["metrics_version"],
                    "computed_at": "2026-08-22T01:00:00+00:00"}

    b = _client(monkeypatch, store, metricsstore=MS()).get(
        "/api/v1/fund/metrics/daily?date=2026-08-21").json()
    assert b["stored"]["agrees"] is True
    assert "MATCHES" in b["stored"]["note"]


def test_an_unreadable_rollup_table_does_not_take_the_endpoint_down(monkeypatch):
    """The live fold is the answer; the stored row is commentary. A cache that
    can 500 the endpoint it decorates has the priority backwards."""
    class MS:
        def stored(self, day):
            raise RuntimeError("relation does not exist")

    store = Store([ev(1, "NavStruck", "2026-08-21T09:00:00+00:00",
                      {"total_nav_usd": 2000})])
    r = _client(monkeypatch, store, metricsstore=MS()).get(
        "/api/v1/fund/metrics/daily?date=2026-08-21")
    assert r.status_code == 200
    assert r.json()["nav"]["close_usd"] == 2000.0
    assert r.json()["stored"]["present"] is None


def test_refresh_needs_postgres_and_says_so(monkeypatch):
    r = _client(monkeypatch, Store()).post("/api/v1/fund/metrics/refresh", json={})
    assert r.status_code == 503
    assert "postgres" in r.json()["detail"]


def test_refresh_is_idempotent_and_reports_whether_content_MOVED(monkeypatch):
    calls = []

    class MS:
        def refresh(self, day, store, deskstore=None):
            calls.append(day)
            return {"day": day, "digest": "d1", "changed": len(calls) > 1,
                    "first_write": len(calls) == 1, "complete_day": True,
                    "metrics_version": "v1", "previous_digest": None,
                    "unknown_sections": []}

    c = _client(monkeypatch, Store(), metricsstore=MS())
    a = c.post("/api/v1/fund/metrics/refresh", json={"date": "2026-08-21"}).json()
    b = c.post("/api/v1/fund/metrics/refresh", json={"date": "2026-08-21"}).json()
    assert a["first_write"] is True and a["changed"] is False
    assert b["first_write"] is False
    assert calls == ["2026-08-21", "2026-08-21"]


# --- the friction endpoint --------------------------------------------------

def test_friction_returns_the_aged_table_oldest_first(monkeypatch):
    store = Store([
        ev(1, "DeskRequested", "2026-08-21T01:00:00+00:00",
           {"request_id": "old", "at": "2026-08-21T01:00:00+00:00"}, actor="ceo"),
        ev(2, "DeskRequested", "2026-08-21T20:00:00+00:00",
           {"request_id": "new", "at": "2026-08-21T20:00:00+00:00"}, actor="ceo"),
        ev(3, "DeskRequestApproved", "2026-08-21T21:00:00+00:00",
           {"request_id": "old", "at": "2026-08-21T21:00:00+00:00",
            "actor": "ceo"}, actor="ceo"),
    ])
    b = _client(monkeypatch, store).get("/api/v1/fund/metrics/friction").json()
    assert [r["request_id"] for r in b["requests"]] == ["old", "new"]
    assert b["by_state"]["approved_undispatched"] == 1
    assert b["waiting_on"] == {"chair": 1, "ceo": 1}
    assert b["requests"][0]["age_hours"] > b["requests"][1]["age_hours"]


def test_friction_open_only_drops_terminal_rows_but_keeps_the_totals_honest(monkeypatch):
    store = Store([
        ev(1, "DeskRequested", "2026-08-21T01:00:00+00:00",
           {"request_id": "a", "at": "2026-08-21T01:00:00+00:00"}),
        ev(2, "DeskRequestResolved", "2026-08-21T02:00:00+00:00",
           {"request_id": "a", "at": "2026-08-21T02:00:00+00:00"}),
        ev(3, "DeskRequested", "2026-08-21T03:00:00+00:00",
           {"request_id": "b", "at": "2026-08-21T03:00:00+00:00"}),
    ])
    b = _client(monkeypatch, store).get(
        "/api/v1/fund/metrics/friction?open_only=true").json()
    assert [r["request_id"] for r in b["requests"]] == ["b"]
    # The census is NOT filtered with the list — dropping rows from a view must
    # not drop them from the count.
    assert b["count"] == 2
    assert b["by_state"]["resolved"] == 1


# --- desk_load's additive component ----------------------------------------

def test_chair_backlog_is_reported_and_NOT_summed_into_the_CEO_total():
    """Measured 2026-08-22: the live CEO total is 38 with coo_triage_due false;
    folding in the 30 approved-undispatched requests makes 68 and flips the
    trigger TRUE the same second. Changing what a threshold COUNTS is a
    threshold change, and this number's next actor is the chair, not the CEO."""
    from app.fund import desk
    backlog = {"requests_approved_undispatched": 30, "oldest_hours": 20.0,
               "upper_bound": True}
    plain = desk.desk_load([], [], [{}] * 5)
    with_backlog = desk.desk_load([], [], [{}] * 5, chair_backlog=backlog)
    # 5 UNTIL 2026-08-24, WHEN OPEN REQUESTS LEFT THIS TOTAL TOO — by exactly
    # the argument this test was written to make, applied one step earlier in
    # the lifecycle. An APPROVED-undispatched request waits on the chair; so,
    # it turns out, does an OPEN one: 28 of the 49 requests resolved in the
    # live log window carry no approval event at all. Both legs are now
    # published, excluded, and named in `excluded_from_total`.
    assert with_backlog["total"] == plain["total"] == 0
    assert with_backlog["coo_triage_due"] == plain["coo_triage_due"]
    assert with_backlog["requests_approved_undispatched"] == 30
    assert with_backlog["chair_backlog"] == backlog
    assert with_backlog["excluded_from_total"] == [
        "requests_awaiting_approval", "requests_approved_undispatched"]
    assert with_backlog["components"]["requests_awaiting_approval"] == 5, \
        "excluded from the headline, never dropped from the payload"
    assert "await DISPATCH by the chair" in with_backlog["note"]


def test_an_uncomputed_chair_backlog_is_None_not_zero():
    """"the chair has nothing waiting" is a claim; "nobody computed it" is not,
    and a zero would say the first while meaning the second."""
    from app.fund import desk
    load = desk.desk_load([], [], [])
    assert load["requests_approved_undispatched"] is None
    assert load["chair_backlog"] is None
    assert load["excluded_from_total"] == []


def test_the_existing_desk_load_components_are_UNRENAMED():
    """The UI reads these keys. The change is additive or it is a break."""
    from app.fund import desk
    load = desk.desk_load([], [], [])
    assert set(load["components"]) == {
        "open_recommendations", "pending_orders", "requests_awaiting_approval"}
    for key in ("total", "complete", "unreadable", "components", "by_actor",
                "open_elsewhere", "decided_awaiting_execution",
                "explicit_next_actor", "rules_version", "contract_digest",
                "threshold", "coo_triage_due", "note"):
        assert key in load, f"desk_load lost the key {key!r}"
