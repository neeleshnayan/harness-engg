"""Fees, so NAV per unit is what an investor would actually receive.

Until now the fund reported a gross return. Nothing in the codebase matched
management_fee, performance_fee or high_water — so every NAV per unit shown to
an LP overstated what they would get back, by exactly the amount nobody had
decided to charge.

The fix is not "add a fee". It is to make the fee an explicit, auditable
decision with a recorded value, which may well be zero. A zero rate written
into the log is a decision anyone can check; an absent one is indistinguishable
from an oversight, and the two look identical on a screen.

Accrual, not billing. A fee is earned continuously and paid occasionally, so
NAV must reflect what is *owed* from the moment it is owed. Otherwise NAV
drifts up all quarter and drops on payment day, and every unit issued in
between is priced wrong — an investor subscribing the day before a fee payment
buys into a liability the price does not show.

The order of operations matters and is the usual source of quiet errors:

    gross          = positions + cash
    management     = gross x rate x elapsed/365
    after_mgmt     = gross - already_accrued - management
    performance    = max(0, after_mgmt/units - high_water) x units x rate
    net            = after_mgmt - performance

Performance is charged on NAV *after* the management fee, never on the gross,
or the manager is paid a performance fee on money already taken as management.

The high-water mark is what stops the same gains being charged twice. Without
it, a fund that rises 10%, falls 10% and rises 10% again pays a performance fee
on the second recovery even though the investor is no worse off than at the
first peak. It is per-unit rather than absolute so that subscriptions and
redemptions do not move it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from app.fund.money import D, f, money

#: Fees accrue on calendar days, matching how the rates are quoted.
DAYS_PER_YEAR = Decimal("365")

_EPS = Decimal("1e-12")


@dataclass
class FeeTerms:
    """The mandate's fee schedule. Zero is a valid, and recorded, answer."""

    #: Annual management fee as a fraction of NAV. 0.02 = 2%/yr.
    management_annual_pct: float = 0.0
    #: Share of gains above the high-water mark. 0.20 = 20%.
    performance_pct: float = 0.0
    #: Where the high-water mark starts. NAV per unit begins at 1.00.
    initial_high_water: float = 1.0
    #: Free-text so the log records WHY, not just what.
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "management_annual_pct": self.management_annual_pct,
            "performance_pct": self.performance_pct,
            "initial_high_water": self.initial_high_water,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "FeeTerms":
        base = cls()
        for k, v in (d or {}).items():
            if k == "note" and v is not None:
                base.note = str(v)
            elif hasattr(base, k) and v is not None and k != "note":
                setattr(base, k, float(v))
        return base

    @property
    def charges_anything(self) -> bool:
        return self.management_annual_pct > 0 or self.performance_pct > 0


@dataclass
class Accrual:
    """What is owed as of a moment, and how it was arrived at."""

    gross_nav_usd: Decimal
    already_accrued_usd: Decimal
    management_usd: Decimal
    performance_usd: Decimal
    net_nav_usd: Decimal
    nav_per_unit_gross: Decimal
    nav_per_unit_net: Decimal
    high_water: Decimal
    new_high_water: Decimal
    elapsed_days: Decimal
    units_outstanding: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "gross_nav_usd": f(self.gross_nav_usd),
            "already_accrued_usd": f(self.already_accrued_usd),
            "management_usd": f(self.management_usd),
            "performance_usd": f(self.performance_usd),
            "total_accrued_usd": f(money(
                self.already_accrued_usd + self.management_usd + self.performance_usd)),
            "net_nav_usd": f(self.net_nav_usd),
            "nav_per_unit_gross": f(self.nav_per_unit_gross),
            "nav_per_unit_net": f(self.nav_per_unit_net),
            "high_water": f(self.high_water),
            "new_high_water": f(self.new_high_water),
            "elapsed_days": f(self.elapsed_days),
            "units_outstanding": f(self.units_outstanding),
        }


def compute(
    gross_nav: Decimal,
    units_outstanding: Decimal,
    terms: FeeTerms,
    elapsed_days: Decimal,
    already_accrued: Decimal = Decimal("0"),
    high_water: Optional[Decimal] = None,
) -> Accrual:
    """What the fund owes, given the book and the terms. Pure.

    ``already_accrued`` is fees earned in previous periods and not yet paid —
    a liability that is already suppressing NAV, so the new management charge
    is computed on the gross and the old accrual is subtracted alongside it
    rather than compounding on top.
    """
    gross = D(gross_nav)
    units = D(units_outstanding)
    prior = D(already_accrued)
    hw = D(terms.initial_high_water) if high_water is None else D(high_water)
    days = max(D(elapsed_days), Decimal("0"))

    navpu_gross = (gross / units) if units > _EPS else D(terms.initial_high_water)

    mgmt = Decimal("0")
    if terms.management_annual_pct > 0 and gross > 0:
        mgmt = gross * D(terms.management_annual_pct) * days / DAYS_PER_YEAR

    after_mgmt = gross - prior - mgmt

    # Performance is charged on NAV after the management fee. Charging it on
    # the gross would pay a performance fee on money already taken as
    # management.
    perf = Decimal("0")
    navpu_after = (after_mgmt / units) if units > _EPS else Decimal("0")
    if terms.performance_pct > 0 and units > _EPS and navpu_after > hw:
        perf = (navpu_after - hw) * units * D(terms.performance_pct)

    net = after_mgmt - perf
    navpu_net = (net / units) if units > _EPS else D(terms.initial_high_water)

    # The mark only ratchets up, and only on NET performance — crediting it
    # with gross gains would raise the bar for gains the investor never got.
    new_hw = max(hw, navpu_net)

    return Accrual(
        gross_nav_usd=money(gross),
        already_accrued_usd=money(prior),
        management_usd=money(mgmt),
        performance_usd=money(perf),
        net_nav_usd=money(net),
        nav_per_unit_gross=navpu_gross,
        nav_per_unit_net=navpu_net,
        high_water=hw,
        new_high_water=new_hw,
        elapsed_days=days,
        units_outstanding=units,
    )


def elapsed_days_between(earlier: str | None, later: str | None = None) -> Decimal:
    """Calendar days between two ISO timestamps, floored at zero.

    Returns 0 when the earlier bound is unknown: a first accrual with no prior
    mark must not invent a period and charge for it.
    """
    if not earlier:
        return Decimal("0")
    try:
        a = datetime.fromisoformat(str(earlier).replace("Z", "+00:00"))
    except ValueError:
        return Decimal("0")
    if later:
        try:
            b = datetime.fromisoformat(str(later).replace("Z", "+00:00"))
        except ValueError:
            b = datetime.now(timezone.utc)
    else:
        b = datetime.now(timezone.utc)
    if a.tzinfo is None or b.tzinfo is None:
        return Decimal("0")
    seconds = (b - a).total_seconds()
    return max(D(seconds / 86400.0), Decimal("0"))


class FeeLedger:
    """Fee terms and outstanding accruals, folded from the event log.

    Terms are event-sourced for the same reason risk limits are: a rate that
    lives in a config file cannot be tied to the period it applied to, and
    "what were we charging in March" is a question an investor is entitled to
    ask.
    """

    def __init__(self, store=None):
        if store is None:
            from app.fund.events import EventStore
            store = EventStore()
        self._store = store

    def _events(self) -> list[dict[str, Any]]:
        from app.fund.events import EventType
        want = {EventType.FEE_TERMS_SET.value, EventType.FEE_ACCRUED.value,
                EventType.FEE_CRYSTALLISED.value}
        try:
            return [e for e in self._store.stream(limit=100_000)
                    if e.get("type") in want]
        except Exception:  # noqa: BLE001
            return []

    def terms(self) -> FeeTerms:
        """The latest terms, or an all-zero default.

        The default is NOT a silent "no fees" — state() reports whether terms
        were ever recorded, so the UI can distinguish a decided zero from an
        undecided one.
        """
        latest = None
        from app.fund.events import EventType
        for e in self._events():
            if e.get("type") == EventType.FEE_TERMS_SET.value:
                latest = e.get("payload") or {}
        return FeeTerms.from_dict(latest)

    def state(self) -> dict[str, Any]:
        """Outstanding accrual, high-water mark, and when we last accrued."""
        from app.fund.events import EventType

        accrued = Decimal("0")
        high_water: Optional[Decimal] = None
        last_ts: Optional[str] = None
        terms_recorded = False

        for e in self._events():
            t = e.get("type")
            p = e.get("payload") or {}
            if t == EventType.FEE_TERMS_SET.value:
                terms_recorded = True
            elif t == EventType.FEE_ACCRUED.value:
                accrued += D(p.get("total_usd") or 0)
                if p.get("new_high_water") is not None:
                    high_water = D(p["new_high_water"])
                last_ts = e.get("ts") or last_ts
            elif t == EventType.FEE_CRYSTALLISED.value:
                accrued -= D(p.get("amount_usd") or 0)

        terms = self.terms()
        return {
            "terms": terms.to_dict(),
            "terms_recorded": terms_recorded,
            "charges_anything": terms.charges_anything,
            "accrued_usd": f(money(max(accrued, Decimal("0")))),
            "high_water": f(high_water if high_water is not None
                            else D(terms.initial_high_water)),
            "last_accrued_ts": last_ts,
        }

    def outstanding(self) -> Decimal:
        return D(self.state()["accrued_usd"])

    def high_water(self) -> Decimal:
        return D(self.state()["high_water"])

    def set_terms(self, terms: FeeTerms, actor: str = "operator") -> dict[str, Any]:
        from app.fund.events import Event, EventType
        self._store.append(Event(
            aggregate_id="fund", aggregate_type="fund",
            type=EventType.FEE_TERMS_SET, payload=terms.to_dict(), actor=actor,
        ))
        return self.state()

    def accrue(self, gross_nav: Decimal, units_outstanding: Decimal,
               actor: str = "system") -> dict[str, Any]:
        """Record fees earned since the last accrual.

        A no-op when the terms charge nothing — writing a stream of zero-value
        events would bury the log in noise that says the same thing the terms
        already say. It is also a no-op on the first call, because there is no
        prior mark to measure a period from and inventing one would charge for
        time before the terms existed.
        """
        from app.fund.events import Event, EventType

        terms = self.terms()
        st = self.state()
        if not terms.charges_anything:
            return {"accrued": False, "reason": "terms charge nothing", **st}

        last = st.get("last_accrued_ts")
        if last is None:
            # Anchor from the terms being set, so the first real accrual covers
            # the period since the fund started charging and not since epoch.
            for e in self._events():
                if e.get("type") == EventType.FEE_TERMS_SET.value:
                    last = e.get("ts")
                    break

        days = elapsed_days_between(last)
        a = compute(
            gross_nav=gross_nav, units_outstanding=units_outstanding, terms=terms,
            elapsed_days=days, already_accrued=D(st["accrued_usd"]),
            high_water=D(st["high_water"]),
        )
        total = a.management_usd + a.performance_usd
        if total <= _EPS:
            return {"accrued": False, "reason": "nothing earned since the last accrual",
                    **st}

        self._store.append(Event(
            aggregate_id="fund", aggregate_type="fund", type=EventType.FEE_ACCRUED,
            payload={**a.to_dict(), "total_usd": f(money(total))}, actor=actor,
        ))
        return {"accrued": True, **a.to_dict()}
