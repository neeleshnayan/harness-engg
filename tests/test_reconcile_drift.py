"""C4 — broker-vs-book drift SIGNAL (read-only).

Guards the regression where NavService.compute() returned live broker equity AS
the NAV (reverted in f0b18c9). Broker equity is a COMPARISON, never the truth,
and reading it must never write to the append-only log.
"""

from decimal import Decimal

from app.fund.reconcile import Reconciler


class _Pos:
    def __init__(self, symbol, qty):
        self.symbol = symbol
        self.qty = qty


class _Connector:
    """Stub broker. `info=None` simulates an unconfigured venue."""

    def __init__(self, info, positions=()):
        self._info = info
        self._positions = list(positions)

    def account_info(self):
        return self._info

    def positions(self):
        return self._positions


class _Snap:
    def __init__(self, nav):
        self.total_nav_usd = Decimal(str(nav))


class _Nav:
    def __init__(self, nav):
        self._nav = nav

    def compute(self):
        return _Snap(self._nav)


class _Book:
    def __init__(self, positions):
        self.positions = positions


class _Proj:
    def __init__(self, positions):
        self._positions = positions

    def build(self):
        return _Book(self._positions)


class _RecordingStore:
    """Any append() here is a test failure — this path must be read-only."""

    def __init__(self):
        self.appended = []

    def append(self, event):
        self.appended.append(event)
        return event


def _reconciler(info, broker_positions=(), book_positions=None, nav=None):
    store = _RecordingStore()
    r = Reconciler(
        connector=_Connector(info, broker_positions),
        store=store,
        projection=_Proj(book_positions or {}),
        nav_service=_Nav(nav) if nav is not None else None,
    )
    return r, store


def test_drift_reports_delta_and_writes_no_events():
    info = {"configured": True, "equity": 105000.0, "cash": 5000.0}
    book = {"AAPL": {"qty": Decimal("10")}}
    r, store = _reconciler(info, [_Pos("AAPL", Decimal("10"))], book, nav=100000.0)

    out = r.drift()

    assert out["configured"] is True
    assert float(out["broker_equity"]) == 105000.0
    assert float(out["book_nav"]) == 100000.0
    # broker is 5k above book => +5% drift, surfaced not silently absorbed
    assert float(out["delta_usd"]) == 5000.0
    assert out["delta_pct"] == 5.0
    # the whole point: a read must never mutate the event log
    assert store.appended == []


def test_unconfigured_broker_is_honest_not_zeros():
    """Zeros would read as 'book and broker agree'. It must say it doesn't know."""
    r, store = _reconciler({"configured": False, "message": "creds missing"})

    out = r.drift()

    assert out["configured"] is False
    assert "book_nav" not in out or out.get("book_nav") is None
    assert out.get("delta_usd") is None
    assert store.appended == []


def test_scheduled_run_skips_ephemeral_venue():
    """A venue that forgets its positions on restart cannot contradict the book.

    A spine accidentally started in mock mode ran the hourly reconcile against
    the in-memory paper connector and appended a false ReconciliationMismatch
    for every real holding (seq 119-141 of the local book). run() must skip a
    venue that is not independently persistent, and skip means writing NOTHING.
    """
    book = {"AAPL": {"qty": Decimal("10")}}

    # Connector with no account_info at all (the paper connector's shape).
    class _Ephemeral:
        def positions(self):
            return []
    store = _RecordingStore()
    r = Reconciler(connector=_Ephemeral(), store=store, projection=_Proj(book))
    out = r.run()
    assert out["mismatches"] == []
    assert "skipped" in out
    assert store.appended == []

    # Explicitly unconfigured broker: same refusal.
    r, store = _reconciler({"configured": False, "message": "creds missing"},
                           [], book)
    out = r.run()
    assert out["mismatches"] == []
    assert "skipped" in out
    assert store.appended == []


def test_scheduled_run_still_writes_on_real_divergence():
    """The guard must not neuter the check: a configured broker that really
    disagrees still produces the mismatch event."""
    info = {"configured": True, "equity": 100000.0, "cash": 0.0}
    book = {"AAPL": {"qty": Decimal("10")}}
    r, store = _reconciler(info, [_Pos("AAPL", Decimal("8"))], book)

    out = r.run()

    assert len(out["mismatches"]) == 1
    assert out["mismatches"][0]["symbol"] == "AAPL"
    assert len(store.appended) == 1


def test_per_symbol_drift_flags_out_of_sync():
    info = {"configured": True, "equity": 100000.0, "cash": 0.0}
    book = {"AAPL": {"qty": Decimal("10")}, "MSFT": {"qty": Decimal("5")}}
    # broker holds 8 AAPL (short 2) and no MSFT (short 5)
    r, store = _reconciler(info, [_Pos("AAPL", Decimal("8"))], book, nav=100000.0)

    out = r.drift()

    by_sym = {p["symbol"]: p for p in out["per_symbol"]}
    assert float(by_sym["AAPL"]["drift"]) == -2.0
    assert by_sym["AAPL"]["in_sync"] is False
    assert float(by_sym["MSFT"]["drift"]) == -5.0
    assert out["symbols_out_of_sync"] == 2
    assert store.appended == []
