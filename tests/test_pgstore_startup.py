"""The boot race, and why only the boot gets a retry.

The spine died on startup with a ConnectionTimeout against a Postgres that had
come up three minutes earlier. The store connects inside __init__, so a
connection failure there kills the process.

The tempting fix — retry every query — would have been wrong, and these tests pin
the distinction: a boot race is waited out, a runtime outage still fails loudly.
Making an outage look like slowness would let the health check report a fund that
was fine while nothing worked.
"""

from __future__ import annotations

import pytest

from app.fund.pgstore import PostgresEventStore


class _Conn:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self

    def execute(self, *a):
        return None

    def commit(self):
        self.committed = True


def _store_with(connect_results, monkeypatch, retry_seconds=5.0):
    """A store whose _connect yields the given sequence of outcomes."""
    calls = {"n": 0}

    def fake_connect(self):
        i = calls["n"]
        calls["n"] += 1
        outcome = connect_results[min(i, len(connect_results) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(PostgresEventStore, "_connect", fake_connect)
    monkeypatch.setattr(PostgresEventStore, "STARTUP_RETRY_SECONDS", retry_seconds)
    monkeypatch.setattr(PostgresEventStore, "STARTUP_RETRY_DELAY", 0.001)
    return calls


def test_a_boot_race_is_waited_out_rather_than_crashed_on(monkeypatch):
    calls = _store_with(
        [ConnectionError("not ready"), ConnectionError("not ready"), _Conn()],
        monkeypatch)
    PostgresEventStore(dsn_str="postgresql://x/y")   # must not raise
    assert calls["n"] == 3


def test_the_original_error_survives_the_retries(monkeypatch):
    """Not a summary of it.

    "could not connect after 30s" hides whether this was a wrong password, a
    wrong port, or an absent server — and those need different fixes.
    """
    boom = PermissionError("password authentication failed for user krypton")
    _store_with([boom], monkeypatch, retry_seconds=0.01)
    with pytest.raises(PermissionError, match="password authentication failed"):
        PostgresEventStore(dsn_str="postgresql://x/y")


def test_a_runtime_call_does_not_retry(monkeypatch):
    """Only the handshake gets patience. An outage must not present as slowness."""
    calls = _store_with([_Conn()], monkeypatch)
    store = PostgresEventStore(dsn_str="postgresql://x/y")
    assert calls["n"] == 1

    def always_fail(self):
        calls["n"] += 1
        raise ConnectionError("postgres went away")

    monkeypatch.setattr(PostgresEventStore, "_connect", always_fail)
    before = calls["n"]
    with pytest.raises(ConnectionError):
        store.ensure_schema()          # default retry_seconds=0.0
    assert calls["n"] == before + 1, "a runtime call retried; it must not"


def test_first_attempt_success_does_not_sleep(monkeypatch):
    calls = _store_with([_Conn()], monkeypatch)
    PostgresEventStore(dsn_str="postgresql://x/y")
    assert calls["n"] == 1
