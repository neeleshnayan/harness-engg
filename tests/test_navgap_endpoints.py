"""The two surfaces that carry the NAV-record verdict, and the trap in each.

THE SHARPEST THING IN THIS FILE IS ``test_liveness_survives_an_exploding_fold``.
``GET /fund/liveness`` is what ``scripts/host_watchdog.ps1`` polls every five
minutes, and a non-200 there makes the watchdog restart Docker, Postgres and the
spine. An exception raised by a READ-ONLY completeness fold would therefore not
surface a bug — it would bounce the whole stack, every five minutes, forever.
The fold is total by construction and this pins it.

The second trap: the two surfaces must never disagree. Both read ONE report
produced by ONE function, and ``test_both_surfaces_report_the_same_state``
proves it rather than assuming it — the fund has already shipped a payload whose
five fields described one condition and contradicted each other, because a
caller computed half of them.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.fund import navgap


class FakeNav:
    """Just enough NavService for the completeness path."""

    def __init__(self, rows=None, raises=None):
        self._rows = rows
        self._raises = raises
        self.calls = []

    def history(self, limit=90):
        self.calls.append(limit)
        if self._raises is not None:
            raise self._raises
        return list(self._rows or [])


@pytest.fixture(autouse=True)
def _cold_cache(monkeypatch):
    """Every test in this file starts with an empty verdict cache.

    Without this, one test's cached payload is served to the next and the file
    measures its own ordering rather than the code.
    """
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_nav_completeness_cache", None)


def _client(monkeypatch, nav):
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_nav", nav)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


def _recent(hours_ago: float) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(hours=hours_ago)).isoformat()


OUTAGE = [{"ts": "2026-08-24T19:14:46.808135+00:00"},
          {"ts": "2026-08-26T13:52:04.644736+00:00"}]


# --- the watchdog trap ------------------------------------------------------

def test_liveness_survives_an_exploding_fold(monkeypatch):
    """A read-only fold must never be able to take the liveness route down.

    The host watchdog restarts the whole stack on a non-200 here. If this test
    ever fails, the failure mode is not a 500 on a page — it is a machine that
    reboots its own database every five minutes.
    """
    client = _client(monkeypatch, FakeNav(raises=RuntimeError("postgres gone")))
    r = client.get("/api/v1/fund/liveness")
    assert r.status_code == 200
    body = r.json()
    assert body["nav_record"]["state"] == navgap.STATE_UNREADABLE
    assert body["nav_record"]["readable"] is False
    # Filtered to the record's own warnings: in a fresh process no heartbeat
    # has beaten yet, so the merged list legitimately also carries one
    # job_unobserved row per scheduled job.
    assert [w["key"] for w in body["nav_record"]["warnings"]] == [
        "nav_record_unreadable"]
    assert "nav_record_unreadable" in [w["key"] for w in body["warnings"]]


def test_the_completeness_fold_is_total(monkeypatch):
    """The fold itself never raises, whatever the store does.

    Asserted on the helper rather than through ``/fund/nav/history``, because
    that route reads the series for the CHART through the same store and has
    always propagated a store failure as a 500. That is pre-existing behaviour
    this diff deliberately leaves alone — a chart that renders an empty series
    when the database is unreachable would be absence dressed as data. What
    must not happen is the ANNOTATION taking a route down, and that is what is
    pinned here and, for the watchdog's route, in the test above.
    """
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_nav",
                        FakeNav(raises=RuntimeError("postgres gone")))
    got = fundapi._nav_completeness()
    assert got["state"] == navgap.STATE_UNREADABLE
    assert got["scan_limit"] == fundapi.NAV_COMPLETENESS_SCAN


def test_an_unreadable_history_never_reports_zero_holes(monkeypatch):
    """Absence is never zero, at the endpoint boundary as much as in the fold."""
    client = _client(monkeypatch, FakeNav(raises=OSError("no db")))
    body = client.get("/api/v1/fund/liveness").json()
    assert body["nav_record"]["hole_count"] is None
    assert body["nav_record"]["stale"] is None


# --- the two surfaces agree -------------------------------------------------

def test_both_surfaces_report_the_same_state(monkeypatch):
    """CALENDAR-PROOFED 2026-08-27 (chair): the original loop compared `note`
    byte-for-byte, but both surfaces fold against the REAL clock and the
    note's trailing-gap sentence embeds an age that ticks between the two
    HTTP calls — so the test failed as a function of wall time, red on an
    untouched base (found by B2, proven in a throwaway worktree). The
    deterministic keys keep exact equality; the note keeps a PROPERTY
    equality (same hole count named, both non-empty)."""
    nav = FakeNav(OUTAGE)
    client = _client(monkeypatch, nav)
    live = client.get("/api/v1/fund/liveness").json()["nav_record"]
    hist = client.get("/api/v1/fund/nav/history").json()["completeness"]
    for key in ("state", "hole_count", "newest_strike_at",
                "tolerance_seconds", "gaps_measured"):
        assert live[key] == hist[key], key
    assert live["note"] and hist["note"]
    assert str(live["hole_count"]) in live["note"]
    assert str(hist["hole_count"]) in hist["note"]


def test_the_history_fold_ignores_the_display_limit(monkeypatch):
    """``limit`` decides how much series a chart draws. A hole outside the drawn
    window is still a hole in the record, so the fold reads the full history.

    Mutant: passing ``limit`` through to the fold makes a 90-point chart blind
    to every hole older than 90 strikes.
    """
    nav = FakeNav(OUTAGE)
    client = _client(monkeypatch, nav)
    client.get("/api/v1/fund/nav/history?limit=2")
    from app.api.v1 import fund as fundapi
    assert fundapi.NAV_COMPLETENESS_SCAN in nav.calls
    assert 2 in nav.calls


def test_the_scan_cap_is_named_and_says_whether_it_bound(monkeypatch):
    """A count that agrees with another instrument agrees only inside that
    instrument's cap. Both numbers ride the payload."""
    client = _client(monkeypatch, FakeNav(OUTAGE))
    body = client.get("/api/v1/fund/liveness").json()["nav_record"]
    assert body["scan_limit"] == 5_000
    assert body["scan_limit_bound"] is False


def test_the_bound_flag_flips_when_the_cap_ACTUALLY_binds(monkeypatch):
    """Mutant: hardcoding ``scan_limit_bound`` False.

    ``is False`` on today's data is satisfied by a constant. The day the cap
    binds is the day this payload silently starts describing a shorter history
    than it claims, so the flag is exercised on BOTH sides — the cap is moved
    down until it bites rather than waiting five thousand strikes to find out.
    """
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "NAV_COMPLETENESS_SCAN", 2)
    client = _client(monkeypatch, FakeNav(OUTAGE))
    body = client.get("/api/v1/fund/liveness").json()["nav_record"]
    assert body["scan_limit"] == 2
    assert body["scan_limit_bound"] is True


def test_liveness_survives_a_fold_that_explodes_inside_navgap(monkeypatch):
    """The second belt on the watchdog's route.

    ``_nav_strike_history_or_none`` already swallows a store failure, so the
    outer guard only ever fires if the READER itself raises — which is exactly
    the case no store fixture can reach. Mutation found that gap: without this,
    the outer ``except`` had no test at all and a bug in ``navgap`` would have
    rebooted Docker, Postgres and the spine every five minutes.
    """
    from app.api.v1 import fund as fundapi

    real = navgap.completeness
    calls = {"n": 0}

    def explode_once(rows, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ZeroDivisionError("a bug in the reader")
        return real(rows, **kw)

    monkeypatch.setattr(fundapi, "_nav", FakeNav(OUTAGE))
    monkeypatch.setattr(navgap, "completeness", explode_once)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    r = TestClient(app).get("/api/v1/fund/liveness")
    assert r.status_code == 200
    body = r.json()["nav_record"]
    assert body["state"] == navgap.STATE_UNREADABLE
    assert body["scan_limit_bound"] is None
    assert "ZeroDivisionError" in body["reason"]


def test_liveness_survives_a_reader_that_ALWAYS_explodes(monkeypatch):
    """The recovery path must not run the code it is recovering from.

    The first version of this guard answered a reader failure by calling the
    SAME reader again for its unreadable payload, and recursed straight back
    into the failure — a safety net that fails exactly when it is needed, on the
    one route whose non-200 reboots the host's database. ``blank_summary`` is a
    literal with no computation, which is why the reader here explodes on EVERY
    call and the route still answers.
    """
    from app.api.v1 import fund as fundapi

    def always_explode(*a, **kw):
        raise ZeroDivisionError("the reader is comprehensively broken")

    monkeypatch.setattr(fundapi, "_nav", FakeNav(OUTAGE))
    monkeypatch.setattr(navgap, "completeness", always_explode)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    r = TestClient(app).get("/api/v1/fund/liveness")
    assert r.status_code == 200
    body = r.json()
    assert body["nav_record"]["state"] == "unreadable"
    assert body["nav_record"]["hole_count"] is None
    assert body["nav_record"]["scan_limit_bound"] is None
    assert "ZeroDivisionError" in body["nav_record"]["reason"]
    assert [w["key"] for w in body["nav_record"]["warnings"]] == [
        "nav_record_unreadable"]


# --- the warnings -----------------------------------------------------------

def test_a_healthy_record_produces_an_empty_measured_warning_list(monkeypatch):
    """Empty means it LOOKED. The key is present either way, so a consumer can
    never mistake "no warnings" for "this payload has no warnings field"."""
    # A single strike seconds ago. There is no LEADING gap by design — the
    # fund's own beginning is not a hole — so this really is a clean record.
    from app.fund import heartbeat
    monkeypatch.setattr(heartbeat, "report", lambda: {
        "jobs": [], "stale": [], "unobserved": [], "note": "all fine"})
    client = _client(monkeypatch, FakeNav([{"ts": _recent(0.01)}]))
    body = client.get("/api/v1/fund/liveness").json()
    assert "warnings" in body
    assert body["warnings"] == []


def test_the_warnings_list_covers_the_JOBS_as_well_as_the_record(monkeypatch):
    """A top-level key called "warnings" that ignored the payload's own
    ``stale`` list would be a half-truth in exactly the shape this route exists
    to remove. Read-through catch, not a suite catch.
    """
    from app.fund import heartbeat
    monkeypatch.setattr(heartbeat, "report", lambda: {
        "jobs": [], "stale": ["exit_check"], "unobserved": ["snapshot"],
        "note": "x"})
    client = _client(monkeypatch, FakeNav(OUTAGE))
    keys = [w["key"] for w in client.get("/api/v1/fund/liveness").json()["warnings"]]
    assert "nav_record_holes" in keys
    assert "job_overdue" in keys
    assert "job_unobserved" in keys


def test_the_heartbeat_report_does_not_already_own_the_warnings_key(monkeypatch):
    """If it ever does, this route silently replaces it. Pinned rather than
    assumed — the collision would be invisible in both files."""
    from app.fund import heartbeat
    assert "warnings" not in heartbeat.report()


def test_a_healthy_payload_has_no_job_warnings(monkeypatch):
    """The null arm: an empty warnings list means BOTH halves were looked at."""
    from app.fund import heartbeat
    monkeypatch.setattr(heartbeat, "report", lambda: {
        "jobs": [], "stale": [], "unobserved": [], "note": "all fine"})
    client = _client(monkeypatch, FakeNav([{"ts": _recent(0.01)}]))
    assert client.get("/api/v1/fund/liveness").json()["warnings"] == []


def test_the_heartbeat_rows_are_untouched(monkeypatch):
    """The nav record is ADDED, never substituted. A green ``nav_strike`` row
    and a holed record are both true at once, and the payload says both."""
    client = _client(monkeypatch, FakeNav(OUTAGE))
    body = client.get("/api/v1/fund/liveness").json()
    assert {"jobs", "stale", "unobserved", "note"} <= set(body)
    assert any(j["job"] == "nav_strike" for j in body["jobs"])
    assert body["nav_record"]["state"] == navgap.STATE_HOLES


def test_the_outage_is_visible_through_the_endpoint(monkeypatch):
    """End to end: the real incident, through the real route."""
    client = _client(monkeypatch, FakeNav(OUTAGE))
    body = client.get("/api/v1/fund/nav/history").json()["completeness"]
    assert body["hole_count"] >= 1
    # CALENDAR-PROOFED 2026-08-27 (chair): the original asserted the incident
    # was holes[0], but the fold's window slides with the real clock, so hole
    # ORDER changes as days pass — red on an untouched base (B2's finding).
    # The property that matters: THE incident appears among the holes, with
    # its swallowed trading day named.
    outage = [h for h in body["holes"]
              if h["from"] == "2026-08-24T19:14:46.808135+00:00"]
    assert outage, [h["from"] for h in body["holes"]]
    assert "2026-08-25" in outage[0]["trading_days"]


# --- the cache, which exists for the watchdog ------------------------------

def test_liveness_serves_a_CACHED_verdict_and_says_how_old_it_is(monkeypatch):
    """The watchdog polls this route every five minutes with an 8s timeout and
    restarts Docker, Postgres and the spine when it does not get a 200.

    Found by the Gauntlet: the guards in this diff catch a fold that RAISES and
    do nothing for one that is merely SLOW — and to a dead-man switch those are
    the same event. Caching for longer than the watchdog's cadence makes the
    steady state one fold per cache miss instead of one per poll. A cached
    answer served as a live one would be a lie about freshness inside a module
    whose entire subject is freshness, so the age rides the payload.
    """
    nav = FakeNav(OUTAGE)
    client = _client(monkeypatch, nav)
    first = client.get("/api/v1/fund/liveness").json()["nav_record"]
    second = client.get("/api/v1/fund/liveness").json()["nav_record"]
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["age_seconds"] >= 0.0
    assert len(nav.calls) == 1, "the second poll must not refold the event log"
    assert second["ttl_seconds"] == 300.0
    assert second["compute_seconds"] >= 0.0
    assert second["watchdog_timeout_seconds"] == 8.0


def test_the_history_route_forces_a_FRESH_verdict(monkeypatch):
    """A human looking at the chart is asking about the record now, and this
    route already pays the event-log fold for its own series."""
    nav = FakeNav(OUTAGE)
    client = _client(monkeypatch, nav)
    client.get("/api/v1/fund/liveness")
    body = client.get("/api/v1/fund/nav/history").json()["completeness"]
    assert body["cached"] is False
    assert body["age_seconds"] == 0.0


def test_an_expired_cache_is_refolded(monkeypatch):
    """Mutant: comparing age the wrong way round serves a verdict forever."""
    from app.api.v1 import fund as fundapi
    nav = FakeNav(OUTAGE)
    client = _client(monkeypatch, nav)
    client.get("/api/v1/fund/liveness")
    monkeypatch.setattr(fundapi, "NAV_COMPLETENESS_TTL_SECONDS", -1.0)
    again = client.get("/api/v1/fund/liveness").json()["nav_record"]
    assert again["cached"] is False
    assert len(nav.calls) == 2


def test_the_bound_flag_is_UNKNOWN_when_the_record_is_unreadable(monkeypatch):
    """Found by the Gauntlet: a concrete ``scan_limit_bound: false`` sat beside
    ``state: unreadable`` and three null fields — a confident answer inside a
    payload that had just said it cannot say. That is the exact collapse this
    module exists to prevent, reproduced inside the module."""
    unreadable = [{"ts": "not a timestamp"}]
    client = _client(monkeypatch, FakeNav(unreadable))
    body = client.get("/api/v1/fund/liveness").json()["nav_record"]
    assert body["state"] == navgap.STATE_UNREADABLE
    assert body["readable"] is False
    assert body["scan_limit_bound"] is None
    assert body["scan_limit"] == 5_000


def test_every_failure_tier_carries_the_same_key_set(monkeypatch):
    """Three paths reach this payload — readable, unreadable-input, and
    reader-broke — and a consumer must not have to ask which one it holds."""
    from app.api.v1 import fund as fundapi
    keys = set(navgap.SUMMARY_KEYS) | {
        "scan_limit", "scan_limit_bound", "compute_seconds",
        "watchdog_timeout_seconds", "ttl_seconds", "computed_at",
        "age_seconds", "cached"}

    ok = _client(monkeypatch, FakeNav(OUTAGE)).get(
        "/api/v1/fund/liveness").json()["nav_record"]
    monkeypatch.setattr(fundapi, "_nav_completeness_cache", None)
    unread = _client(monkeypatch, FakeNav(raises=OSError("no db"))).get(
        "/api/v1/fund/liveness").json()["nav_record"]
    monkeypatch.setattr(fundapi, "_nav_completeness_cache", None)
    monkeypatch.setattr(navgap, "completeness",
                        lambda *a, **k: (_ for _ in ()).throw(
                            ZeroDivisionError("broken")))
    broke = _client(monkeypatch, FakeNav(OUTAGE)).get(
        "/api/v1/fund/liveness").json()["nav_record"]

    assert set(ok) == keys
    assert set(unread) == keys
    assert set(broke) == keys | {"reason"}


def test_an_empty_history_is_readable_and_not_silently_clean(monkeypatch):
    """An empty list and an unreadable one are DIFFERENT inputs and must not
    produce the same payload."""
    empty = _client(monkeypatch, FakeNav([])).get(
        "/api/v1/fund/liveness").json()["nav_record"]
    assert empty["readable"] is True
    assert empty["state"] != navgap.STATE_UNREADABLE
