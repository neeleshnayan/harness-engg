"""Fees, and the arithmetic that decides what an investor actually gets back.

The high-water mark is the test that matters most: without it a fund that
rises, falls and recovers charges twice for the same gain, and the investor
pays a performance fee for getting back to where they already were.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.fund.events import EventType
from app.fund.fees import (
    FeeLedger,
    FeeTerms,
    compute,
    elapsed_days_between,
)

D = Decimal


class MemStore:
    def __init__(self):
        self.events: list[dict] = []
        self._seq = 0

    def append(self, e):
        self._seq += 1
        self.events.append({
            "seq": self._seq, "aggregate_id": e.aggregate_id,
            "aggregate_type": e.aggregate_type,
            "type": e.type.value if hasattr(e.type, "value") else e.type,
            "payload": e.payload, "actor": e.actor,
            "ts": f"2026-08-{13 + self._seq // 24:02d}T00:00:00+00:00",
        })
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)


# ------------------------------------------------------------------ nothing
def test_zero_terms_charge_nothing():
    a = compute(D("2000"), D("2000"), FeeTerms(), elapsed_days=D("365"))
    assert a.management_usd == 0 and a.performance_usd == 0
    assert a.net_nav_usd == D("2000")


def test_a_recorded_zero_is_distinguishable_from_no_decision():
    """The whole point: an explicit zero is auditable, an absence is not."""
    s = MemStore()
    led = FeeLedger(s)
    assert led.state()["terms_recorded"] is False
    led.set_terms(FeeTerms(note="F&F fund charges nothing"), actor="operator")
    st = led.state()
    assert st["terms_recorded"] is True
    assert st["charges_anything"] is False
    assert st["terms"]["note"] == "F&F fund charges nothing"


# --------------------------------------------------------------- management
def test_a_full_year_of_management_fee():
    a = compute(D("2000"), D("2000"), FeeTerms(management_annual_pct=0.02),
                elapsed_days=D("365"))
    assert a.management_usd == pytest.approx(D("40"))


def test_management_prorates_by_days():
    a = compute(D("2000"), D("2000"), FeeTerms(management_annual_pct=0.02),
                elapsed_days=D("1"))
    assert float(a.management_usd) == pytest.approx(40 / 365, abs=0.001)


def test_no_elapsed_time_means_no_management_fee():
    a = compute(D("2000"), D("2000"), FeeTerms(management_annual_pct=0.02),
                elapsed_days=D("0"))
    assert a.management_usd == 0


def test_management_reduces_nav_per_unit():
    a = compute(D("2000"), D("2000"), FeeTerms(management_annual_pct=0.02),
                elapsed_days=D("365"))
    assert a.nav_per_unit_gross == D("1")
    assert a.nav_per_unit_net < a.nav_per_unit_gross


# -------------------------------------------------------------- performance
def test_performance_fee_on_gains_above_the_mark():
    """2200 on 2000 units = 1.10/unit, 0.10 above a 1.00 mark, 20% of that."""
    a = compute(D("2200"), D("2000"), FeeTerms(performance_pct=0.20),
                elapsed_days=D("30"), high_water=D("1.0"))
    assert a.performance_usd == pytest.approx(D("40"))


def test_no_performance_fee_below_the_mark():
    a = compute(D("1800"), D("2000"), FeeTerms(performance_pct=0.20),
                elapsed_days=D("30"), high_water=D("1.0"))
    assert a.performance_usd == 0


def test_no_performance_fee_exactly_at_the_mark():
    a = compute(D("2000"), D("2000"), FeeTerms(performance_pct=0.20),
                elapsed_days=D("30"), high_water=D("1.0"))
    assert a.performance_usd == 0


def test_performance_is_charged_after_management_not_on_the_gross():
    """Otherwise the manager takes a performance fee on money already taken as
    a management fee."""
    both = compute(D("2200"), D("2000"),
                   FeeTerms(management_annual_pct=0.02, performance_pct=0.20),
                   elapsed_days=D("365"), high_water=D("1.0"))
    perf_only = compute(D("2200"), D("2000"), FeeTerms(performance_pct=0.20),
                        elapsed_days=D("365"), high_water=D("1.0"))
    assert both.performance_usd < perf_only.performance_usd


# ------------------------------------------------------------- high water
def test_the_mark_ratchets_up_on_a_gain():
    a = compute(D("2200"), D("2000"), FeeTerms(performance_pct=0.20),
                elapsed_days=D("30"), high_water=D("1.0"))
    assert a.new_high_water > D("1.0")


def test_the_mark_does_not_fall_on_a_loss():
    a = compute(D("1800"), D("2000"), FeeTerms(performance_pct=0.20),
                elapsed_days=D("30"), high_water=D("1.10"))
    assert a.new_high_water == D("1.10")


def test_the_same_gain_is_not_charged_twice_after_a_round_trip():
    """Up 10%, back to flat, up 10% again. The recovery must be free — the
    investor is no better off than they were at the first peak.

    The accrual has to be carried between periods for this to hold. The already
    accrued 40 is a liability still suppressing NAV, so on the second visit to
    2200 gross the per-unit value net of it is exactly the mark and there is
    nothing new to charge. Dropping that carry is how a fund quietly bills the
    same gain twice.
    """
    terms = FeeTerms(performance_pct=0.20)

    up = compute(D("2200"), D("2000"), terms, elapsed_days=D("30"),
                 high_water=D("1.0"))
    assert up.performance_usd == pytest.approx(D("40"))
    owed, mark = up.performance_usd, up.new_high_water

    down = compute(D("2000"), D("2000"), terms, elapsed_days=D("30"),
                   already_accrued=owed, high_water=mark)
    assert down.performance_usd == 0                  # below the mark: nothing

    back = compute(D("2200"), D("2000"), terms, elapsed_days=D("30"),
                   already_accrued=owed, high_water=mark)
    assert back.performance_usd == 0                  # the recovery is free
    assert back.new_high_water == mark                # and the bar is unchanged


def test_the_mark_is_credited_with_net_not_gross_performance():
    """Crediting gross would raise the bar for gains the investor never got."""
    a = compute(D("2200"), D("2000"),
                FeeTerms(management_annual_pct=0.02, performance_pct=0.20),
                elapsed_days=D("365"), high_water=D("1.0"))
    assert a.new_high_water == a.nav_per_unit_net
    assert a.new_high_water < a.nav_per_unit_gross


# ------------------------------------------------------------ prior accrual
def test_an_existing_accrual_is_subtracted_not_compounded():
    a = compute(D("2000"), D("2000"), FeeTerms(management_annual_pct=0.02),
                elapsed_days=D("365"), already_accrued=D("10"))
    assert a.management_usd == pytest.approx(D("40"))     # on the gross
    assert a.net_nav_usd == pytest.approx(D("1950"))      # 2000 - 10 - 40


def test_no_units_does_not_divide_by_zero():
    a = compute(D("0"), D("0"), FeeTerms(management_annual_pct=0.02),
                elapsed_days=D("365"))
    assert a.nav_per_unit_net == D("1")


# -------------------------------------------------------------------- days
def test_elapsed_days_between_two_timestamps():
    d = elapsed_days_between("2026-08-01T00:00:00+00:00", "2026-08-11T00:00:00+00:00")
    assert float(d) == pytest.approx(10.0)


def test_an_unknown_start_charges_for_no_time():
    """A first accrual with no prior mark must not invent a period."""
    assert elapsed_days_between(None) == 0


def test_a_naive_timestamp_charges_for_no_time():
    assert elapsed_days_between("2026-08-01T00:00:00") == 0


def test_a_backwards_period_is_floored_at_zero():
    d = elapsed_days_between("2026-08-11T00:00:00+00:00", "2026-08-01T00:00:00+00:00")
    assert d == 0


# ------------------------------------------------------------------ ledger
def test_the_ledger_defaults_to_charging_nothing():
    assert FeeLedger(MemStore()).terms().charges_anything is False


def test_the_ledger_reads_back_the_latest_terms():
    s = MemStore()
    led = FeeLedger(s)
    led.set_terms(FeeTerms(management_annual_pct=0.02))
    led.set_terms(FeeTerms(management_annual_pct=0.01))
    assert led.terms().management_annual_pct == 0.01


def test_accrual_is_a_noop_when_terms_charge_nothing():
    s = MemStore()
    led = FeeLedger(s)
    led.set_terms(FeeTerms())
    out = led.accrue(D("2000"), D("2000"))
    assert out["accrued"] is False
    assert not [e for e in s.events if e["type"] == EventType.FEE_ACCRUED.value]


def test_accruing_writes_one_event_and_raises_the_outstanding_balance():
    s = MemStore()
    led = FeeLedger(s)
    led.set_terms(FeeTerms(management_annual_pct=0.02))
    out = led.accrue(D("2000"), D("2000"))
    assert out["accrued"] is True
    assert len([e for e in s.events if e["type"] == EventType.FEE_ACCRUED.value]) == 1
    assert led.outstanding() > 0


def test_crystallising_reduces_the_outstanding_balance():
    from app.fund.events import Event

    s = MemStore()
    led = FeeLedger(s)
    led.set_terms(FeeTerms(management_annual_pct=0.02))
    led.accrue(D("2000"), D("2000"))
    owed = led.outstanding()
    s.append(Event(aggregate_id="fund", aggregate_type="fund",
                   type=EventType.FEE_CRYSTALLISED,
                   payload={"amount_usd": str(owed)}, actor="operator"))
    assert led.outstanding() == 0


def test_an_unreadable_log_reports_no_fees_rather_than_raising():
    """NAV must never fail to compute because the fee ledger is unavailable."""
    class Broken(MemStore):
        def stream(self, since_seq=0, limit=100_000):
            raise RuntimeError("unavailable")

    assert FeeLedger(Broken()).outstanding() == 0
