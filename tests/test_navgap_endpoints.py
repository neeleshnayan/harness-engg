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
    assert [w["key"] for w in body["warnings"]] == ["nav_record_unreadable"]


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
    nav = FakeNav(OUTAGE)
    client = _client(monkeypatch, nav)
    live = client.get("/api/v1/fund/liveness").json()["nav_record"]
    hist = client.get("/api/v1/fund/nav/history").json()["completeness"]
    for key in ("state", "hole_count", "note", "newest_strike_at",
                "tolerance_seconds", "gaps_measured"):
        assert live[key] == hist[key], key


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


# --- the warnings -----------------------------------------------------------

def test_a_healthy_record_produces_an_empty_measured_warning_list(monkeypatch):
    """Empty means it LOOKED. The key is present either way, so a consumer can
    never mistake "no warnings" for "this payload has no warnings field"."""
    # A single strike seconds ago. There is no LEADING gap by design — the
    # fund's own beginning is not a hole — so this really is a clean record.
    client = _client(monkeypatch, FakeNav([{"ts": _recent(0.01)}]))
    body = client.get("/api/v1/fund/liveness").json()
    assert "warnings" in body
    assert body["warnings"] == []


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
    assert body["holes"][0]["from"] == "2026-08-24T19:14:46.808135+00:00"
    assert "2026-08-25" in body["holes"][0]["trading_days"]


def test_an_empty_history_is_readable_and_not_silently_clean(monkeypatch):
    """An empty list and an unreadable one are DIFFERENT inputs and must not
    produce the same payload."""
    empty = _client(monkeypatch, FakeNav([])).get(
        "/api/v1/fund/liveness").json()["nav_record"]
    assert empty["readable"] is True
    assert empty["state"] != navgap.STATE_UNREADABLE
