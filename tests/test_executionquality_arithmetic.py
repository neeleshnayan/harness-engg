"""Arithmetic tests for the pure functions in ``app.fund.executionquality``.

Scope, deliberately narrow: ``_num``, ``mid_of``, ``spread_bps_of``,
``effective_spread_bps``, ``signed_effective_spread_bps``,
``mark_shortfall_bps``, ``incremental_price``, ``_stats``. These are the
functions the module docstring calls out as "pure ... separated from the
store so the null tests can run without Postgres." The store, the fold and
the summaries are covered elsewhere.

No database, no fixtures beyond pytest's own — every test here is a plain
function call against a pure function.
"""

import math

import pytest

from app.fund.executionquality import (
    _num,
    _stats,
    effective_spread_bps,
    incremental_price,
    mark_shortfall_bps,
    mid_of,
    signed_effective_spread_bps,
    spread_bps_of,
)


# ===========================================================================
# 1. NULL TESTS — the three identities the instrument exists to satisfy.
# ===========================================================================

PRICE_LEVELS = [
    pytest.param(18.00, 0.02, id="18-dollar-stock"),
    pytest.param(100.00, 0.05, id="100-dollar-etf"),
    pytest.param(778.00, 0.40, id="778-dollar-etf"),
]


@pytest.mark.parametrize("mid_price, half_spread", PRICE_LEVELS)
def test_fill_at_mid_reads_zero_exactly(mid_price, half_spread):
    """A fill priced exactly at the midpoint must read 0.0 bps, exactly.

    If this drifted off exact zero, every "flat" fill in the fund's own log
    would show a phantom cost or a phantom saving that isn't there.
    """
    assert effective_spread_bps(mid_price, mid_price) == 0.0


@pytest.mark.parametrize("bid, ask", [
    (17.98, 18.02),
    (99.95, 100.05),
    (777.60, 778.40),
])
def test_fill_at_ask_equals_quoted_spread(bid, ask):
    """A fill exactly at the ask must read the same number as the quoted
    spread computed from the same bid/ask.

    This is the whole reason the factor of two exists in effective_spread_bps
    (crossing the full spread from mid to ask is half the quoted spread, so
    the identity only holds if the 2x is there). A hardcoded expected decimal
    would not catch a regression that scales both sides together, so the
    expected value is derived from spread_bps_of on the same inputs.
    """
    mid, reason = mid_of(bid, ask)
    assert reason is None
    quoted = spread_bps_of(bid, ask)
    got = effective_spread_bps(ask, mid)
    assert got == pytest.approx(quoted, rel=1e-9)


@pytest.mark.parametrize("bid, ask", [
    (17.98, 18.02),
    (99.95, 100.05),
    (777.60, 778.40),
])
def test_fill_at_bid_equals_quoted_spread(bid, ask):
    """A fill exactly at the bid must also read the quoted spread — a fund
    that sells into the bid pays the same full spread a fund that buys at
    the ask pays, just in the other direction.
    """
    mid, reason = mid_of(bid, ask)
    assert reason is None
    quoted = spread_bps_of(bid, ask)
    got = effective_spread_bps(bid, mid)
    assert got == pytest.approx(quoted, rel=1e-9)


@pytest.mark.parametrize("p1, q1, p2, q2", [
    (18.00, 3.0, 18.00, 7.0),
    (100.00, 1.5, 100.00, 9.5),
    (778.00, 0.5, 778.00, 4.5),
])
def test_incremental_price_identical_cumulative_price_derives_same_price(
    p1, q1, p2, q2
):
    """Two legs whose CUMULATIVE price never moved must derive that same
    price for the increment, regardless of the quantities involved.

    If the volume-weighted-average algebra in incremental_price were wrong,
    a flat run of fills at one unmoving price would report a fabricated
    increment price different from the price that was actually printed.
    """
    first = incremental_price(p1, q1)
    assert first == pytest.approx(p1, rel=1e-9)
    second = incremental_price(p2, q2, p1, q1)
    assert second == pytest.approx(p1, rel=1e-9)
    assert second == pytest.approx(p2, rel=1e-9)


# ===========================================================================
# 2. mid_of — XOR over (mid, reason), and the reason strings are contract.
# ===========================================================================

@pytest.mark.parametrize("bid, ask, expect_reason", [
    (None, None, "no_quote"),
    (None, 10.0, "one_sided_quote:bid_absent"),
    (10.0, None, "one_sided_quote:ask_absent"),
    (0.0, 10.0, "one_sided_quote:bid_absent"),
    (-5.0, 10.0, "one_sided_quote:bid_absent"),
    (5.0, 0.0, "one_sided_quote:ask_absent"),
    (5.0, -1.0, "one_sided_quote:ask_absent"),
    (10.0, 9.0, "crossed_quote"),
])
def test_mid_of_absent_reasons_are_exact_strings(bid, ask, expect_reason):
    """Every absent path returns the exact reason string the coverage report
    and the stored ``quote_absent_reason`` column depend on. A near-miss
    string (wrong punctuation, wrong casing) would silently break every
    reader that filters or counts on these strings.
    """
    mid, reason = mid_of(bid, ask)
    assert mid is None
    assert reason == expect_reason


@pytest.mark.parametrize("bid, ask", [
    (10.0, 10.0),   # locked market — valid, not absent
    (10.0, 10.5),   # ordinary quote
    (0.01, 0.02),   # tiny but positive
])
def test_mid_of_present_reason_is_none(bid, ask):
    """A usable quote — including a locked market where bid == ask — must
    return a real mid and a None reason. Locked is a valid measurement
    (spread of 0.0), not an absence.
    """
    mid, reason = mid_of(bid, ask)
    assert mid is not None
    assert reason is None


@pytest.mark.parametrize("bid, ask", [
    (None, None), (None, 10.0), (10.0, None),
    (0.0, 10.0), (5.0, 0.0), (10.0, 9.0),
    (10.0, 10.0), (10.0, 10.5), (0.01, 0.02),
])
def test_mid_of_exactly_one_of_mid_or_reason_is_none(bid, ask):
    """mid_of's whole contract: exactly one of (mid, reason) is None, always
    — never both None, never both set. A caller that trusted this to hold
    could otherwise silently store a mid alongside a stated absence reason,
    which is precisely the fabricated-price shape the schema's own CHECK
    constraint (fund_execution_quotes_absence_is_stated) exists to forbid.
    """
    mid, reason = mid_of(bid, ask)
    assert (mid is None) != (reason is None)


def test_mid_of_locked_market_spread_is_zero():
    """A locked market (bid == ask) is a real, valid mid with 0.0 quoted
    spread — not an error and not an absence.
    """
    mid, reason = mid_of(7.50, 7.50)
    assert mid == 7.50
    assert reason is None
    assert spread_bps_of(7.50, 7.50) == 0.0


def test_mid_of_dba_one_sided_quote_is_not_a_fabricated_price():
    """The measured live case: DBA quoted bid=27.49, ask=0.0 (no offer on
    the book). (27.49 + 0.0) / 2 = 13.745 would be a fabricated price for a
    real fund holding — a $27 stock cannot trade at $13.75 because a vendor
    spelled "no offer" as a zero. mid_of must refuse to average it and must
    name the ask as what's missing.
    """
    mid, reason = mid_of(27.49, 0.0)
    assert mid is None
    assert reason == "one_sided_quote:ask_absent"
    # The fabricated number itself, spelled out so nobody mistakes the guard
    # for an accident of arithmetic:
    assert (27.49 + 0.0) / 2 == 13.745


# ===========================================================================
# 3. BOUNDARY TABLES on every inequality.
# ===========================================================================

@pytest.mark.parametrize("bid, expect_absent", [
    (-0.01, True),   # strictly below 0
    (0.0, True),     # exactly at 0 (non-strict: bid <= 0)
    (0.01, False),   # strictly above 0
])
def test_boundary_bid_le_zero(bid, expect_absent):
    """mid_of's bid check is ``bid <= 0.0`` (non-strict). A test that only
    probes far from zero cannot tell this from ``bid < 0.0`` — a strict
    version would treat a zero bid as a real, tradeable price of $0.
    """
    mid, reason = mid_of(bid, 10.0)
    if expect_absent:
        assert mid is None
        assert reason == "one_sided_quote:bid_absent"
    else:
        assert mid is not None
        assert reason is None


@pytest.mark.parametrize("ask, expect_absent", [
    (-0.01, True),   # strictly below 0
    (0.0, True),     # exactly at 0 (non-strict: ask <= 0)
    (0.01, False),   # strictly above 0
])
def test_boundary_ask_le_zero(ask, expect_absent):
    """mid_of's ask check is ``ask <= 0.0`` (non-strict), mirroring the bid
    check. bid is fixed well below every candidate ask so the crossed-quote
    branch cannot mask this boundary.
    """
    mid, reason = mid_of(0.005, ask)
    if expect_absent:
        assert mid is None
        assert reason == "one_sided_quote:ask_absent"
    else:
        assert mid is not None
        assert reason is None


@pytest.mark.parametrize("ask, expect_crossed, expect_reason", [
    (9.99, True, "crossed_quote"),   # ask strictly below bid
    (10.00, False, None),            # ask == bid: locked, VALID, not crossed
    (10.01, False, None),            # ask strictly above bid
])
def test_boundary_ask_lt_bid_crossed(ask, expect_crossed, expect_reason):
    """The crossed-quote check is ``ask < bid`` (strict). At ask == bid the
    market is locked, which is a valid measurement, not a crossed one — a
    non-strict ``<=`` version would wrongly reject every locked market.
    """
    mid, reason = mid_of(10.00, ask)
    if expect_crossed:
        assert mid is None
    else:
        assert mid is not None
    assert reason == expect_reason


@pytest.mark.parametrize("mid_value, expect_none", [
    (-0.01, True),   # strictly below 0
    (0.0, True),      # exactly at 0 (non-strict: mid <= 0)
    (0.01, False),    # strictly above 0
])
def test_boundary_mid_le_zero_in_effective_spread(mid_value, expect_none):
    """effective_spread_bps refuses a non-positive mid with ``mid <= 0.0``
    (non-strict) rather than dividing by a zero or negative denominator.
    """
    got = effective_spread_bps(1.0, mid_value)
    if expect_none:
        assert got is None
    else:
        assert got is not None


@pytest.mark.parametrize("mid_value, expect_none", [
    (-0.01, True),
    (0.0, True),
    (0.01, False),
])
def test_boundary_mid_le_zero_in_signed_effective_spread(mid_value, expect_none):
    """signed_effective_spread_bps has the same non-strict ``mid <= 0.0``
    guard as the unsigned version — checked independently since the two
    functions duplicate the guard rather than sharing one code path.
    """
    got = signed_effective_spread_bps(1.0, mid_value, "buy")
    if expect_none:
        assert got is None
    else:
        assert got is not None


@pytest.mark.parametrize("mark_value, expect_none", [
    (-0.01, True),
    (0.0, True),
    (0.01, False),
])
def test_boundary_mark_le_zero_in_mark_shortfall(mark_value, expect_none):
    """mark_shortfall_bps guards its own denominator the same way: a
    non-positive mark (``mark <= 0.0``) is refused rather than divided by.
    """
    got = mark_shortfall_bps(1.0, mark_value, "buy")
    if expect_none:
        assert got is None
    else:
        assert got is not None


@pytest.mark.parametrize("q, expect_none", [
    (4.99, True),   # strictly below prev_qty
    (5.00, True),   # exactly equal to prev_qty (non-strict: q <= pq)
    (5.01, False),  # strictly above prev_qty
])
def test_boundary_q_le_prev_qty_in_incremental_price(q, expect_none):
    """incremental_price refuses to compute an increment when the new
    cumulative quantity does not exceed the previous one — ``q <= pq``
    (non-strict). At q == pq no shares arrived in this leg and dividing by
    (q - pq) == 0 would be dividing by zero; below pq the quantity went
    backwards, which is not a real fill. Only strictly above pq is a real
    increment.
    """
    got = incremental_price(cum_price=100.0, cum_qty=q,
                            prev_price=90.0, prev_qty=5.00)
    if expect_none:
        assert got is None
    else:
        assert got is not None
        assert got == pytest.approx((100.0 * q - 90.0 * 5.00) / (q - 5.00),
                                    rel=1e-9)


# ===========================================================================
# 4. _num — what it rejects and what it accepts.
# ===========================================================================

class _Opaque:
    """A plain object with no numeric conversion — the "an object" case."""


@pytest.mark.parametrize("value", [
    None,
    float("nan"),
    float("inf"),
    float("-inf"),
    True,
    False,
    "abc",
    _Opaque(),
], ids=["none", "nan", "posinf", "neginf", "true", "false", "abc", "object"])
def test_num_rejects(value):
    """_num must reject None, NaN, both infinities, booleans (bool is a
    Python int subclass and would otherwise silently arrive as 1.0/0.0), a
    non-numeric string, and an arbitrary object. A NaN slipping through
    would poison every downstream mean, since NaN compares false against
    itself and corrupts any aggregate it enters.
    """
    assert _num(value) is None


@pytest.mark.parametrize("value, expect", [
    (5, 5.0),
    (5.5, 5.5),
    (0, 0.0),
    (-3.25, -3.25),
    ("28.3799991607666", 28.3799991607666),
    ("0", 0.0),
    ("-1.5", -1.5),
])
def test_num_accepts(value, expect):
    """_num accepts plain ints, plain floats, and numeric strings — the
    string case matters because the live log stores ``avg_price`` as a
    string on most rows, and a reader that only handled numeric types would
    silently drop most of the fund's own fills.
    """
    got = _num(value)
    assert got == expect


def test_num_accepts_numeric_string_matches_live_log_shape():
    """Named explicitly per the contract: a numeric string shaped exactly
    like the live log's stored avg_price must parse to the same float
    Python's own float() would produce.
    """
    assert _num("28.3799991607666") == float("28.3799991607666")


# ===========================================================================
# 5. signed_effective_spread_bps — sign convention.
# ===========================================================================

@pytest.mark.parametrize("side, fill, mid, expect_sign", [
    ("buy", 100.10, 100.00, 1),    # buy above mid -> paid -> positive
    ("buy", 99.90, 100.00, -1),    # buy below mid -> improvement -> negative
    ("sell", 99.90, 100.00, 1),    # sell below mid -> paid -> positive
    ("sell", 100.10, 100.00, -1),  # sell above mid -> improvement -> negative
])
def test_signed_effective_spread_sign_convention(side, fill, mid, expect_sign):
    """The sign convention that lets the signed figure answer "did we pay or
    get improvement": a buy that fills above mid or a sell that fills below
    mid COST the fund and must read positive; the mirror cases are price
    improvement and must read negative. Flipping either sign would make the
    fund's cost panel report savings as costs and vice versa.
    """
    got = signed_effective_spread_bps(fill, mid, side)
    assert got is not None
    if expect_sign > 0:
        assert got > 0.0
    else:
        assert got < 0.0


@pytest.mark.parametrize("side", ["buy", "BUY", "BUY ", " buy ", "Buy", "bUy"])
def test_signed_side_buy_normalizes_whitespace_and_case(side):
    """The function lowercases and strips ``side`` before comparing, so any
    casing or surrounding whitespace on "buy" must produce the identical
    result as the canonical lowercase form.
    """
    canonical = signed_effective_spread_bps(101.0, 100.0, "buy")
    got = signed_effective_spread_bps(101.0, 100.0, side)
    assert got == canonical


@pytest.mark.parametrize("side", ["sell", "SELL", "SELL ", " sell ", "Sell"])
def test_signed_side_sell_normalizes_whitespace_and_case(side):
    """Same normalization check as the buy case, for "sell"."""
    canonical = signed_effective_spread_bps(99.0, 100.0, "sell")
    got = signed_effective_spread_bps(99.0, 100.0, side)
    assert got == canonical


@pytest.mark.parametrize("side", [None, "", "  ", "unknown", "buys", "sel"])
def test_signed_unknown_or_absent_side_returns_none_never_a_guess(side):
    """An unknown or absent side must return None, never a guessed
    direction. Guessing "buy" for an unrecognised side would silently turn
    a fund's real saving into a reported cost (or vice versa) whenever the
    side field is missing or misspelled in the log.
    """
    assert signed_effective_spread_bps(101.0, 100.0, side) is None


@pytest.mark.parametrize("side, fill, mid", [
    ("buy", 100.10, 100.00),
    ("buy", 99.90, 100.00),
    ("sell", 99.90, 100.00),
    ("sell", 100.10, 100.00),
    ("buy", 18.02, 18.00),
    ("sell", 777.60, 778.00),
])
def test_abs_signed_equals_unsigned_effective_spread(side, fill, mid):
    """abs(signed_effective_spread_bps(...)) must equal
    effective_spread_bps(...) for every side/fill/mid combination where the
    signed figure is not None — the signed number is a directional split of
    the same magnitude, never a different magnitude.
    """
    signed = signed_effective_spread_bps(fill, mid, side)
    unsigned = effective_spread_bps(fill, mid)
    assert signed is not None
    assert unsigned is not None
    assert abs(signed) == unsigned


# ===========================================================================
# 6. mark_shortfall_bps — no factor of two.
# ===========================================================================

@pytest.mark.parametrize("side, fill, reference", [
    ("buy", 100.10, 100.00),
    ("buy", 99.90, 100.00),
    ("sell", 99.90, 100.00),
    ("sell", 100.10, 100.00),
    ("buy", 18.05, 18.00),
    ("sell", 777.20, 778.00),
])
def test_mark_shortfall_has_no_factor_of_two(side, fill, reference):
    """effective_spread_bps expresses cost as a full round-trip spread
    against a MIDPOINT (hence the 2x: crossing from mid to the far side of
    the quote is only half the quoted spread). mark_shortfall_bps compares
    against the fund's own struck mark, which is not a midpoint of
    anything, so it carries no such factor. Pinned directly: for the same
    fill/reference/side, effective_spread_bps must equal exactly twice
    abs(mark_shortfall_bps) — treating a mark like a midpoint and adding a
    stray factor of two (or dropping the one on the effective side) would
    make this fail immediately.
    """
    effective = effective_spread_bps(fill, reference)
    shortfall = mark_shortfall_bps(fill, reference, side)
    assert effective is not None
    assert shortfall is not None
    assert effective == pytest.approx(2.0 * abs(shortfall), rel=1e-9)


# ===========================================================================
# 7. _stats — empty is None, not a dict of zeros; worst is max, best is min.
# ===========================================================================

def test_stats_empty_list_returns_none():
    """An empty sample has no mean. Returning a dict of zeros instead of
    None would be the absence-as-zero failure the module docstring calls
    out explicitly: a fund whose execution-cost panel reads 0.0 because
    nothing was measured looks identical to a fund that measured a
    genuinely costless day.
    """
    assert _stats([]) is None


def test_stats_single_value():
    """A single-observation sample has n=1 and mean == median == worst ==
    best, all equal to that one value.
    """
    got = _stats([7.25])
    assert got is not None
    assert got["n"] == 1
    assert got["mean"] == pytest.approx(7.25, rel=1e-9)
    assert got["median"] == pytest.approx(7.25, rel=1e-9)
    assert got["worst"] == pytest.approx(7.25, rel=1e-9)
    assert got["best"] == pytest.approx(7.25, rel=1e-9)


def test_stats_worst_is_max_best_is_min_with_negatives():
    """These are costs, so a BIGGER number is WORSE — worst must be the
    max of the sample and best must be the min, never their absolute
    values. Uses negative numbers specifically so that max/min cannot be
    confused with a magnitude-based (abs) selection: if worst were picked
    by abs() instead of a true max, -50.0 would wrongly win over 12.0.
    """
    values = [-50.0, -10.0, 12.0, -30.0]
    got = _stats(values)
    assert got is not None
    assert got["worst"] == pytest.approx(max(values), rel=1e-9)
    assert got["best"] == pytest.approx(min(values), rel=1e-9)
    assert got["worst"] == pytest.approx(12.0, rel=1e-9)
    assert got["best"] == pytest.approx(-50.0, rel=1e-9)
