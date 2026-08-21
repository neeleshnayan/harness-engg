"""The fractional-fill switch, and the lie it exists to prevent.

The engine fills WHOLE shares; the venue does not. Measured on the real engine
2026-08-21 (`lean_workspace/algorithms/frac_probe`, two runs, same window, $2,000
book, a 49% target in each of SPY and TLT):

    fractional:0    SPY 1.0000    TLT 11.0000
    fractional:1    SPY 1.4298    TLT 11.1207

SPY printed at $685, so 49% of the book is $980 = 1.43 shares. Whole-share
rounding holds ONE — 34% against a 49% target. That 15-percentage-point error is
an order of magnitude larger than the 1-2%/yr effects the belt tests for, and it
is why entry 11 had to be run at a $100k notional (run-quant-entry11).

THE FAILURE THIS GUARDS is not the rounding. It is that the runner can SET a
parameter while only the ALGORITHM can act on it — so a `fractional=True` on a
file that ignores the switch would leave a caller believing a whole-share run was
fractional. That is a silent lie about the conditions a verdict was produced
under, which is the same class as an unpriced backtest passing as a priced one.
Verified against the real engine: monthend_rebalance_flow asked for fractional,
reported honoured=False, and filled 1.0 / 11.0.
"""

import pytest

from app.fund.leanrunner import (FRACTIONAL_PARAM, LeanRunner,
                                 honours_fractional)

OPTED_IN = '''
class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        sec = self.add_data(SpineBars, "SPY", Resolution.DAILY)
        if str(self.get_parameter("fractional") or "0") == "1":
            old = sec.symbol_properties
            sec.symbol_properties = SymbolProperties(
                old.description, old.quote_currency, old.contract_multiplier,
                old.minimum_price_variation, 0.0001, old.market_ticker)
'''

IGNORES = '''
class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        self.add_data(SpineBars, "SPY", Resolution.DAILY)
'''


def test_the_parameter_is_named_once_and_reused():
    assert FRACTIONAL_PARAM == "fractional"
    assert FRACTIONAL_PARAM in OPTED_IN


def test_an_algorithm_that_reads_the_switch_is_recognised():
    assert honours_fractional(OPTED_IN) is True


def test_an_algorithm_that_ignores_it_is_NOT_recognised():
    assert honours_fractional(IGNORES) is False


def test_recognition_needs_BOTH_tokens_not_either():
    """Conservative in the safe direction. A file mentioning the parameter
    without overriding the lot size is not honouring the switch, and reporting
    that it might be puts the caller back where they started."""
    mentions_only = 'x = self.get_parameter("fractional")'
    overrides_only = 'sec.symbol_properties = SymbolProperties(1)'
    assert honours_fractional(mentions_only) is False
    assert honours_fractional(overrides_only) is False


def test_absent_source_is_not_honouring_it():
    assert honours_fractional(None) is False
    assert honours_fractional("") is False


class _Runner(LeanRunner):
    """A runner that never starts a container — only the bookkeeping is tested."""

    def __init__(self, code):
        self._code = code
        self._jobs, self._sweeps = {}, {}
        import threading
        self._lock = threading.Lock()

    def get_algorithm(self, name):
        return {"name": name, "code": self._code}

    def _mirror_job(self, job):
        pass

    def _run(self, job_id):          # never runs the engine
        pass


def _submit(code, **kw):
    r = _Runner(code)
    import threading
    started = []
    real = threading.Thread

    class _NoThread:
        def __init__(self, *a, **k):
            started.append(k)

        def start(self):
            pass
    threading.Thread = _NoThread
    try:
        jid = r.submit_backtest("algo", **kw)["job_id"]
    finally:
        threading.Thread = real
    return r._jobs[jid]


def test_not_asking_records_None_rather_than_False():
    """None means nobody asked either way. That IS the engine's whole-share
    default, and it is not the same as having asked for whole shares — a caller
    reading the record must be able to tell a default from a decision."""
    job = _submit(OPTED_IN)
    assert job["fractional_requested"] is None
    assert job["fractional_honoured"] is None
    assert FRACTIONAL_PARAM not in job["parameters"]


def test_asking_an_algorithm_that_honours_it_sets_the_parameter():
    job = _submit(OPTED_IN, fractional=True)
    assert job["parameters"][FRACTIONAL_PARAM] == "1"
    assert job["fractional_requested"] is True
    assert job["fractional_honoured"] is True
    assert job["fractional_note"] is None


def test_asking_an_algorithm_that_IGNORES_it_is_reported_not_assumed():
    """THE test. Verified against the real engine the same day:
    monthend_rebalance_flow asked for fractional and filled 1.0 / 11.0."""
    job = _submit(IGNORES, fractional=True)
    assert job["fractional_requested"] is True
    assert job["fractional_honoured"] is False
    assert "WHOLE-SHARE" in job["fractional_note"]
    assert "re-run" in job["fractional_note"]


def test_explicitly_asking_for_whole_shares_is_not_a_warning():
    """`fractional=False` is a deliberate choice, recorded, and never scolded —
    a note on it would train the reader to ignore the note that matters."""
    job = _submit(IGNORES, fractional=False)
    assert job["parameters"][FRACTIONAL_PARAM] == "0"
    assert job["fractional_requested"] is False
    assert job["fractional_note"] is None


def test_the_switch_never_touches_the_cost_assumption():
    """slip travels with every run and must not be disturbed by this."""
    job = _submit(OPTED_IN, fractional=True)
    assert "slip" in job["parameters"]


def test_the_shipped_falsifier_still_honours_the_switch():
    """`frac_probe` is the only thing that can falsify the engine claim in
    FRACTIONAL_PARAM. If it stops reading the switch, the proof is gone."""
    from pathlib import Path
    p = Path("lean_workspace/algorithms/frac_probe/main.py")
    if not p.exists():
        pytest.skip("frac_probe not present in this checkout")
    assert honours_fractional(p.read_text(encoding="utf-8")) is True
