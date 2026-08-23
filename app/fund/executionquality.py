"""Execution quality — what the two-sided market looked like when we traded.

THE BLINDSPOT THIS CLOSES. ``app/fund/tca.py`` already folds implementation
shortfall out of the log: decision price, arrival price, fill price, signed so
positive is a cost. It is good and it is not the same measurement. Every price
it compares against is a price the FUND struck — and the fund strikes its marks
from the last TRADE (``connectors/alpaca.py::AlpacaConnector._fetch_price``
issues ``StockLatestTradeRequest``; named rather than numbered because line
numbers go stale and this one already had). A last trade is as likely to have
printed at the
bid as at the ask, so a shortfall measured against it carries roughly half a
spread of noise per observation and a bias in whichever direction trade
direction happens to be autocorrelated.

The industry number — the one a broker, a venue and a regulator all compute the
same way — is the EFFECTIVE SPREAD, and it is measured against the MIDPOINT of
the quoted market at the moment the order arrived::

    effective_spread_bps        = 2 * |fill - mid| / mid * 10_000
    signed_effective_spread_bps = 2 * (fill - mid) / mid * 10_000   (a buy)
                                  2 * (mid - fill) / mid * 10_000   (a sell)

The unsigned figure is what the brief and the P5 precondition ask for. The
signed one is kept beside it because they answer different questions and only
the signed one can say PRICE IMPROVEMENT: an unsigned mean cannot tell a fund
that crosses the spread from one that gets filled inside it, and those two
funds have opposite problems.

The fund has never computed either, because it has never held a quote.

WHAT FEED THIS ACTUALLY IS, AND WHY THE COLUMN EXISTS. The ticket says "NBBO".
Measured against the live subscription on 2026-08-23, the fund cannot query the
consolidated tape in real time::

    feed=sip, end=now-14min  ->  "subscription does not permit querying recent SIP data"
    feed=sip, end=now-16min  ->  200 OK
    feed=iex, end=now        ->  200 OK, bid_exchange='V' (IEX) on every side

So there are two different markets available at two different latencies, and
they are not interchangeable:

  * LIVE, at the moment of the event: the IEX book only. IEX is one venue of
    many; its best bid/offer is at or WIDER than the consolidated NBBO, so an
    effective spread measured against an IEX mid is an estimate with a sign we
    cannot predict, not the NBBO number.
  * FIFTEEN MINUTES LATER: the consolidated quote stream, ``bid_exchange`` in
    {P, K, N, ...}. This IS the NBBO input, and it is available for free.

Both are worth having and calling either one "the NBBO" would be the exact
absence-as-something-else move the non-negotiables forbid. Every stored row
carries the ``feed`` it came from and every summary is cut by feed. The 15
minutes is measured, reproducible (``scripts/execution/retro_spread.py
--probe-delay``) and is a vendor entitlement, not a constant of nature.

ONE-SIDED QUOTES ARE REAL AND THEY ARRIVE AS ZERO. Measured the same day, live::

    DBA  bid 27.49 x 100   ask 0.0 x 0     tape B

``ask=0.0`` is the vendor spelling of "no offer on this book", and
``(27.49 + 0.0) / 2 = 13.745`` is a fabricated price for a $27 fund holding.
:func:`mid_of` returns ``(None, reason)`` for it, the schema forbids a mid
without both sides, and the row is stored with the bid it really saw. An
unmeasurable fill is stored VISIBLY unmeasurable; it is never skipped, because
a skipped fill and a measured-at-zero fill look identical in a coverage count.

CONSTRUCTION ISSUES NO DDL. Inherited from ``episodes.py``, which inherited it
from the knowledge graph after a read-only report wedged ``kg_outcome`` for
~5 minutes behind one ordinary transaction. Readers go through :meth:`_read`;
writers call :meth:`QuoteStore.ensure_schema`.

THIS MODULE IS NOT A WORK-LAYER STORE. It does not declare
``WORK_LAYER_STORE``, deliberately: unlike the episode store and the knowledge
graph, execution quality is a fact about the fund's own money and the spine
serves it at ``GET /fund/execution/quality``.
"""

from __future__ import annotations

import statistics
from typing import Any, Iterable, Optional

#: Basis points. One place, so the two callers cannot drift.
BPS = 10_000.0

#: What the ``event_kind`` column may hold. The lifecycle types this instrument
#: snapshots, in the log's own spelling, lower-cased.
#:
#: ``partially_filled`` is here because MEASUREMENT SAYS IT HAS TO BE: the live
#: log holds 5 ``OrderPartiallyFilled`` events across 3 orders, and every one of
#: them is a real print at a real price. An instrument that watched only
#: ``OrderFilled`` would report those three orders as single fills at the
#: volume-weighted average and lose the three worst prints, which is where
#: execution cost lives.
EVENT_KINDS = ("submitted", "partially_filled", "filled")

#: Log event type -> ``event_kind``. The ONLY mapping; nothing infers a kind
#: from a string elsewhere.
#:
#: Measured against the live log 2026-08-23 (1,254 events): the order aggregate
#: carries OrderProposed 38 / OrderApproved 23 / OrderSubmitted 22 /
#: OrderFilled 29 / OrderPartiallyFilled 5 / OrderDeclined 15 / OrderRejected 3
#: / OrderFailed 1 / ApprovalRefused 2. Only the three below have a price and a
#: market to compare it against; the rest are decisions, not executions.
#: Reproduce: ``python scripts/execution/retro_spread.py --census``
EVENT_KIND_OF_TYPE = {
    "OrderSubmitted": "submitted",
    "OrderPartiallyFilled": "partially_filled",
    "OrderFilled": "filled",
}

#: Kinds that carry a price the fund actually got.
FILL_KINDS = ("partially_filled", "filled")

#: What a stored mid was measured from. NOT a free-text field: a reader that
#: cannot tell an IEX mid from a consolidated one cannot report either.
#:
#:   live-iex-bbo        the IEX book, read at the moment of the event by
#:                       scripts/execution/nbbo_capture.py. ONE venue.
#:   sip-quote-at-event  the consolidated quote in force at the event's own
#:                       timestamp, fetched at least 15 minutes later. THE NBBO.
BASES = ("live-iex-bbo", "sip-quote-at-event")

#: Feeds, as the vendor names them. Stored per row; never defaulted.
FEEDS = ("iex", "sip")

#: The two (basis, feed) pairs, named HERE so the capture script and the retro
#: reader import them rather than each keeping a literal. Two copies of a
#: constant is the same defect as two copies of a predicate (D18): care cannot
#: hold two literals in step, construction can.
LIVE_BASIS, LIVE_FEED = "live-iex-bbo", "iex"
RETRO_BASIS, RETRO_FEED = "sip-quote-at-event", "sip"
assert LIVE_BASIS in BASES and RETRO_BASIS in BASES
assert LIVE_FEED in FEEDS and RETRO_FEED in FEEDS

#: THE ARRIVAL MARK IS NOT A QUOTE AND IT NEVER ENTERS THIS TABLE.
#:
#: ``OrderSubmitted.arrival_price`` is the fund's own struck mark. Computing
#: ``2*|fill - arrival|/arrival`` produces a number in basis points that looks
#: exactly like an effective spread and is not one — it has no bid, no ask, and
#: no midpoint. :func:`retro_mark_rows` computes it because it is the only
#: thing that CAN be said about a fill whose quote was never captured, and it
#: is reported under this name, in its own section, and stored nowhere.
MARK_BASIS = "arrival-mark"

#: Venues whose fills carry NO execution-cost information, because the venue
#: prints at the mark it was handed rather than against a book.
#:
#: ``app/fund/tca.py:131`` holds an INDEPENDENT copy of this judgement
#: (``(self.venue or "") != "paper"``). Two copies of a predicate is the defect
#: this codebase has priced twice, and it cannot be derived away here — the
#: other copy is a string literal inside a property. So it is pinned
#: BEHAVIOURALLY instead: ``tests/test_executionquality.py`` builds a real
#: ``tca.OrderCost`` on each venue and asserts the two modules agree, which
#: fails on whoever changes either one.
SIMULATED_VENUES = ("paper",)

#: What a fill leg IS, for the purpose of averaging it with other fill legs.
#: Derived from the log, never stored as a verdict — the store keeps the raw
#: ``submitted_venue`` and every reader derives the class from it.
#:
#:   executed        submitted to a real venue. THE population whose effective
#:                   spread is the fund's execution cost.
#:   simulated       submitted to a venue in :data:`SIMULATED_VENUES`. Its
#:                   effective spread against a real quote is a measurement of
#:                   OUR MARK's distance from the market, which is worth having
#:                   and is not a trading cost.
#:   not_submitted   no ``OrderSubmitted`` exists. The fund never sent this to
#:                   anybody; the fill is a bookkeeping backfill of a position
#:                   that already existed, and its "price" was never struck
#:                   against a market.
#:
#: MEASURED PARTITION of the live log 2026-08-23, 29 filled orders / 34 legs:
#: executed 10 orders / 15 legs (alpaca), simulated 12 / 12 (paper),
#: not_submitted 7 / 7.
#:
#: THE PARTITION IS WHY THIS EXISTS. Over the consolidated tape, effective
#: spread by class on that log — best to worst, 31 of the 34 legs measurable::
#:
#:     executed        n=15  0.67 -  46.95 bps   (single-leg n=7: 0.67 - 7.21)
#:     simulated       n=9   2.42 - 15146.04 bps
#:     not_submitted   n=7   7.19 -  591.40 bps
#:
#: A flat mean over all 31 measured legs is **560.58 bps**. That is a real
#: number computed from real quotes and it is not the fund's execution cost,
#: which is 2.89 bps mean / 1.99 median over the seven clean single-leg
#: executed fills.
#:
#: REPRODUCE ALL OF IT: ``scripts/execution/retro_spread.py --quotes``.
#: These are a GROWING POPULATION — the denominator rises with every fill the
#: fund makes — so read the shape (three classes, three orders of magnitude
#: apart) as the durable claim and the digits as a dated snapshot. An earlier
#: draft of this comment said "0.7-6.6" and "0.9-591"; both were read off the
#: table by eye rather than off the summary, and both were wrong.
EXECUTION_CLASSES = ("executed", "simulated", "not_submitted")

#: A retro mark row whose arrival mark EQUALS its fill price to this tolerance
#: is an arithmetic identity, not a measurement.
#:
#: Measured on the FULL live log 2026-08-23 (1,254 events): 12 of the 20 orders
#: carrying both prices have ``arrival_price == avg_price`` bit-for-bit
#: (82.78500366210938, 30.780000686645508, 100.0, 769.0599975585938, ...),
#: because the simulated venue fills at the mark it was handed. Reproduce with
#: ``scripts/execution/retro_spread.py`` and read the ``identity`` count.
#:
#: ``app/fund/tca.py`` reaches the same exclusion by a different road — it drops
#: the ``paper`` venue — and on today's log the two partitions coincide exactly,
#: 12 and 12, same order ids. They are NOT the same rule and both are kept: a
#: real venue that happens to print at our mark is informative and the venue
#: rule keeps it; a simulated venue that ever prints away from the mark is noise
#: and only the identity rule catches it.
#:
#: READ THAT PAIR FROM THE WHOLE LOG OR IT IS 10 AND 10. ``GET /fund/tca``
#: defaults to ``limit=500`` EVENTS (``fund.py``), and ``tca._lifecycles``
#: passes it to ``stream(limit=...)``, which serves the OLDEST 500 — so the
#: default view silently drops the fund's two most recent filled orders and the
#: whole DBA symbol. Reported as a separate finding; nothing here depends on it.
#:
#: Absolute, not relative, and tiny: these are float equalities, not near
#: misses. Anything larger would start swallowing genuine sub-basis-point fills.
MARK_IDENTITY_TOLERANCE = 1e-12


class SchemaAbsent(RuntimeError):
    """``fund_execution_quotes`` does not exist in this store.

    Raised rather than returning ``[]``, because "the capture service has never
    run here" and "the capture service ran and saw nothing" are different
    facts, and only one of them is a reason to go and start it.
    """


# --- the arithmetic -------------------------------------------------------
#
# Every function below is pure, takes floats, and returns None with a reason
# rather than a number it cannot stand behind. They are separated from the
# store so the null tests can run without Postgres.


def _num(v: Any) -> Optional[float]:
    """A float, or None. Rejects NaN, which compares false against itself and
    would otherwise flow into a mean and poison every figure downstream."""
    if v is None or isinstance(v, bool):
        # bool is an int in Python and True would arrive as 1.0. A boolean in a
        # price field is a shape error, not a price.
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def mid_of(bid: Any, ask: Any) -> tuple[Optional[float], Optional[str]]:
    """``(mid, absent_reason)`` — exactly one of the two is None.

    The reason strings are part of the contract: they are stored verbatim in
    ``quote_absent_reason`` and counted by the coverage report, so a fund that
    cannot measure its fills can say WHY in a table rather than in prose.
    """
    b, a = _num(bid), _num(ask)
    if b is None and a is None:
        return None, "no_quote"
    if b is None or b <= 0.0:
        # A zero bid is the vendor's spelling of "no bid on this book" — see
        # the DBA observation in the module docstring. Treated as absent, and
        # the raw value is still stored so a reader can see what arrived.
        return None, "one_sided_quote:bid_absent"
    if a is None or a <= 0.0:
        return None, "one_sided_quote:ask_absent"
    if a < b:
        # A crossed book is a real, brief market state and also the shape of a
        # stale-feed bug. Either way the midpoint of a crossed quote is not a
        # price anyone could have traded at.
        return None, "crossed_quote"
    return (b + a) / 2.0, None


def spread_bps_of(bid: Any, ask: Any) -> Optional[float]:
    """The quoted spread in basis points of the mid, or None if there is no mid.

    A locked market (bid == ask) is 0.0 and that is a measurement, not an
    absence — which is why this returns the number rather than falling into the
    absent branch.

    THERE IS NO ``m <= 0`` GUARD HERE AND THAT IS DELIBERATE. A first draft
    carried one; it is UNREACHABLE. :func:`mid_of` returns a mid only when
    ``bid > 0`` and ``ask >= bid``, so a returned mid is strictly positive by
    that function's own contract. An unreachable branch is worse than no
    branch: nothing can ever cover it, so it is a permanent hole in any
    coverage figure and a permanent survivor in any mutation pass — which is
    exactly how the Gauntlet found it. The invariant is stated as an assert
    instead, where it documents the dependency without pretending to handle a
    case that cannot arrive.
    """
    m, _reason = mid_of(bid, ask)
    if m is None:
        return None
    b, a = _num(bid), _num(ask)
    assert b is not None and a is not None and m > 0.0  # mid_of's contract
    return (a - b) / m * BPS


def effective_spread_bps(fill_price: Any, mid: Any) -> Optional[float]:
    """``2 * |fill - mid| / mid`` in basis points. The P5 measurement.

    NULL TEST, and it is in the test suite by name: a fill AT the mid reads
    0.0; a fill AT the ask reads exactly the quoted spread. Those two identities
    are the whole reason the factor of two is there, and an instrument that
    fails either of them is reporting half or double the fund's trading cost.
    """
    f, m = _num(fill_price), _num(mid)
    if f is None or m is None or m <= 0.0:
        return None
    return 2.0 * abs(f - m) / m * BPS


def signed_effective_spread_bps(fill_price: Any, mid: Any,
                                side: Any) -> Optional[float]:
    """Positive = we paid the spread. Negative = PRICE IMPROVEMENT.

    Unsigned effective spread cannot distinguish a fund that crosses from one
    filled inside the quote, and those have opposite remedies. Returns None on
    an unknown side rather than guessing ``buy``: a sign convention silently
    applied to the wrong direction turns a saving into a cost.
    """
    f, m = _num(fill_price), _num(mid)
    if f is None or m is None or m <= 0.0:
        return None
    s = str(side or "").strip().lower()
    if s == "buy":
        return 2.0 * (f - m) / m * BPS
    if s == "sell":
        return 2.0 * (m - f) / m * BPS
    return None


def mark_shortfall_bps(fill_price: Any, mark: Any,
                       side: Any) -> Optional[float]:
    """Signed cost against the fund's OWN struck mark. NOT an effective spread.

    Same arithmetic shape as :func:`signed_effective_spread_bps` and a
    different meaning, which is why it has a different name and lives under
    :data:`MARK_BASIS`. There is no factor of two: the factor of two in an
    effective spread exists to express the cost as a full round-trip spread
    against a MIDPOINT, and a mark is not a midpoint of anything.
    """
    f, k = _num(fill_price), _num(mark)
    if f is None or k is None or k <= 0.0:
        return None
    s = str(side or "").strip().lower()
    if s == "buy":
        return (f - k) / k * BPS
    if s == "sell":
        return (k - f) / k * BPS
    return None


# --- folding the log ------------------------------------------------------


def fold_order_lifecycles(events: Iterable[dict]) -> dict[str, dict]:
    """order_id -> the pieces this instrument needs, from raw log rows.

    Accepts events in ANY order and sorts by ``seq``; the spine serves
    ``/fund/events`` NEWEST FIRST while ``EventStore.stream`` is oldest-first,
    and a fold that silently assumed either one would be right half the time.

    SYMBOL AND SIDE COME FROM WHEREVER THEY EXIST, and the reason is measured:
    ``OrderSubmitted.payload`` is ``{venue, venue_ref, arrival_price}`` with no
    symbol at all, and ``OrderPartiallyFilled.payload`` is
    ``{avg_price, cumulative_qty}`` with neither symbol nor side. Four order
    event types carry a symbol in the live log — ``OrderProposed``,
    ``OrderFilled``, ``OrderRejected`` and ``OrderFailed`` — and only the first
    two can coexist with a fill, but the fold reads ANY of them rather than a
    named pair, because a list of type names is the kind of guard that goes
    stale silently. It takes the LOWEST-seq event that names one, and reports
    None when nothing does: 7 of the 29 filled orders in the live log have no
    ``OrderProposed`` at all (they predate the propose path). An order whose
    symbol is unknown cannot be quoted, and saying so is the whole job.

    A RE-SUBMITTED ORDER'S LAST ``OrderSubmitted`` WINS — its arrival price,
    its venue and its seq together, so the record describes one submission
    rather than a blend of two. No order in the live log has been submitted
    twice (checked), so this is a choice with no data behind it yet; it is
    written down because the alternative (first wins) is equally arguable and
    the next reader should not have to infer which was meant.
    """
    rows = sorted(
        (e for e in events if (e or {}).get("aggregate_type") == "order"),
        key=lambda e: int(e.get("seq") or 0))
    out: dict[str, dict] = {}
    for e in rows:
        oid = str(e.get("aggregate_id") or "")
        if not oid:
            continue
        pay = e.get("payload") or {}
        rec = out.setdefault(oid, {
            "order_id": oid, "symbol": None, "side": None,
            "arrival_price": None, "submitted_seq": None, "submitted_ts": None,
            "venue_ref": None, "submitted_venue": None, "filled_venue": None,
            "was_submitted": False, "legs": [],
        })
        if rec["symbol"] is None and pay.get("symbol"):
            rec["symbol"] = str(pay["symbol"])
        if rec["side"] is None and pay.get("side"):
            rec["side"] = str(pay["side"]).strip().lower()
        etype = str(e.get("type") or "")
        kind = EVENT_KIND_OF_TYPE.get(etype)
        if kind == "submitted":
            rec["arrival_price"] = _num(pay.get("arrival_price"))
            rec["submitted_seq"] = int(e.get("seq") or 0)
            rec["submitted_ts"] = e.get("ts")
            rec["venue_ref"] = pay.get("venue_ref")
            # THE SUBMITTED LEG, NOT THE FILLED ONE. OrderSubmitted.venue is
            # the handle the CONNECTOR THAT RAN THE ORDER handed back;
            # OrderFilled.venue is a string the proposer put on the request.
            # Those are a fact and a wish, and the live log holds one order
            # (17d64dcd, DBA) where they disagree - submitted `paper`, filled
            # labelled `alpaca`. tca.py made exactly this mistake and counted
            # it informative for a day. Both are recorded; only the fact is
            # classified on.
            rec["submitted_venue"] = pay.get("venue")
            rec["was_submitted"] = True
        if kind == "filled" and pay.get("venue") and rec["filled_venue"] is None:
            rec["filled_venue"] = pay.get("venue")
        if kind is None:
            continue
        # `filled_qty` on a terminal fill, `cumulative_qty` on a partial - the
        # two payloads spell the same fact differently and only one is ever
        # present. Written as an explicit None test rather than `a or b`: a
        # genuine quantity of ZERO is falsy, and `or` would silently reach past
        # it to the other key and then to None. No fill in the log carries a
        # zero quantity today (checked), which is exactly the condition under
        # which this defect would have shipped unnoticed.
        qty = _num(pay.get("filled_qty"))
        if qty is None:
            qty = _num(pay.get("cumulative_qty"))
        rec["legs"].append({
            "kind": kind,
            "seq": int(e.get("seq") or 0),
            "ts": e.get("ts"),
            "price": _num(pay.get("avg_price")),
            "qty": qty,
        })
    return out


def fill_legs(lifecycles: dict[str, dict]) -> list[dict]:
    """Every leg that has a PRICE — the denominator of every coverage figure.

    One row per fill event, not per order. Computed from the LOG rather than
    from the capture table, so a capture that missed an event shows up as an
    uncovered row instead of vanishing from both sides of the fraction.

    ``avg_price`` IS A RUNNING AVERAGE, NOT A PRINT, AND THAT IS MEASURED.
    Verified against the live log 2026-08-23, order ``5d495c88`` (SOFI, sell)::

        OrderPartiallyFilled  avg 18.410000  cumulative_qty 2.000000
        OrderPartiallyFilled  avg 18.446000  cumulative_qty 5.000000
        OrderPartiallyFilled  avg 18.438178  cumulative_qty 5.811810
        OrderFilled           avg 18.431105  filled_qty     6.811810

    The quantities are cumulative and the prices are the volume-weighted
    average so far — so the terminal ``OrderFilled`` of a partially filled
    order is a RESTATEMENT of the whole order, not a fresh print, and three of
    the fund's orders (8 of its 34 fill legs) look like several fills while
    being one. Two consequences, both handled rather than assumed away:

      * ``multi_leg`` marks every leg of such an order. The retro summary
        REPORTS them and does not average them, because an effective spread
        computed against a running average is not an effective spread.
      * ``incremental_price`` is the price of the shares that arrived in THIS
        leg, derived from the pair of cumulative figures. It is the number a
        future round should measure against; it is computed and shown here and
        deliberately does not yet drive any summary, because a derived price in
        a money measurement wants its own review.
    """
    out = []
    for rec in lifecycles.values():
        legs = [l for l in rec["legs"] if l["kind"] in FILL_KINDS]
        multi = len(legs) > 1
        prev_price = prev_qty = None
        for leg in legs:
            out.append({
                "order_id": rec["order_id"], "symbol": rec["symbol"],
                "side": rec["side"], "event_kind": leg["kind"],
                "event_seq": leg["seq"], "event_ts": leg["ts"],
                "fill_price": leg["price"], "filled_qty": leg["qty"],
                "arrival_price": rec["arrival_price"],
                "submitted_venue": rec["submitted_venue"],
                "filled_venue": rec["filled_venue"],
                "was_submitted": rec["was_submitted"],
                "execution_class": execution_class(rec["submitted_venue"],
                                                   rec["was_submitted"]),
                "multi_leg": multi,
                "incremental_price": incremental_price(
                    leg["price"], leg["qty"], prev_price, prev_qty),
            })
            prev_price, prev_qty = leg["price"], leg["qty"]
    out.sort(key=lambda r: r["event_seq"])
    return out


def execution_class(submitted_venue: Any, was_submitted: bool) -> str:
    """Which of :data:`EXECUTION_CLASSES` a fill belongs to.

    ``was_submitted`` is passed separately and is NOT inferred from
    ``submitted_venue`` being None, because those are two different facts: an
    order that was never submitted, and one that was submitted by a connector
    that recorded no venue name. The first is a backfill; the second is a real
    execution whose venue we cannot name — and calling the second one a
    backfill would silently drop a genuine fill out of the cost sample.
    An unnamed venue on a real submission is treated as EXECUTED, which is the
    conservative direction: it keeps the observation in the population that is
    scrutinised rather than in the one that is discarded.
    """
    if not was_submitted:
        return "not_submitted"
    if str(submitted_venue or "").strip().lower() in SIMULATED_VENUES:
        return "simulated"
    return "executed"


def incremental_price(cum_price: Any, cum_qty: Any,
                      prev_price: Any = None,
                      prev_qty: Any = None) -> Optional[float]:
    """The price of the shares that arrived in THIS leg.

    ``(P_n*Q_n - P_{n-1}*Q_{n-1}) / (Q_n - Q_{n-1})``, and the first leg of an
    order is its own increment. Returns None — never a fabricated price —
    when the quantities do not increase, which is the shape of a restatement
    that added no shares, and when either pair is unreadable.

    NULL TEST, in the suite by name: two legs at the same cumulative price must
    derive that same price for the increment, at any quantities.
    """
    p, q = _num(cum_price), _num(cum_qty)
    if p is None:
        return None
    pp, pq = _num(prev_price), _num(prev_qty)
    if pp is None or pq is None:
        return p
    if q is None or q <= pq:
        return None
    return (p * q - pp * pq) / (q - pq)


def retro_mark_rows(events: Iterable[dict]) -> list[dict]:
    """The honest retro table: what CAN be said about fills with no quote.

    Every fill leg in the log, each one classified into exactly one of:

      ``measured``     an arrival mark exists and differs from the fill.
      ``identity``     the mark equals the fill to :data:`MARK_IDENTITY_TOLERANCE`.
                       Its shortfall is 0.0 and that zero is arithmetic, not
                       execution. Reported, counted, and EXCLUDED from every
                       summary statistic.
      ``cumulative``   a leg of a multi-leg order, whose ``avg_price`` is the
                       order's running average rather than this leg's print
                       (see :func:`fill_legs`). The shortfall is computed and
                       shown; it is EXCLUDED from the summary because it
                       compares a running average with a point-in-time mark.
      ``no_mark``      no ``OrderSubmitted``, or one without ``arrival_price``.
                       Nothing can be said. Not zero.
      ``unusable``     a mark or fill price that is not a positive number.

    ORDER MATTERS AND IS PART OF THE SPECIFICATION. ``no_mark`` and
    ``unusable`` are checked first because they say nothing CAN be computed;
    ``cumulative`` before ``identity`` because a multi-leg order whose running
    average happens to equal the mark is still a running average. The
    classification is exclusive and every leg gets exactly one.

    The basis is :data:`MARK_BASIS` on every row, and no row from this function
    is ever written to ``fund_execution_quotes``.
    """
    legs = fill_legs(fold_order_lifecycles(events))
    out = []
    for leg in legs:
        mark, fill = leg["arrival_price"], leg["fill_price"]
        row = dict(leg)
        row["basis"] = MARK_BASIS
        row["shortfall_bps"] = None
        if mark is None:
            row["classification"] = "no_mark"
            row["reason"] = "no OrderSubmitted.arrival_price for this order"
        elif fill is None or mark <= 0.0:
            row["classification"] = "unusable"
            row["reason"] = f"fill={fill!r} mark={mark!r} is not a positive pair"
        elif leg["multi_leg"]:
            row["classification"] = "cumulative"
            row["reason"] = ("avg_price on a multi-leg order is the order's "
                             "RUNNING AVERAGE, not this leg's print - shown, "
                             "not averaged; incremental_price is the figure a "
                             "future round should measure")
            row["shortfall_bps"] = mark_shortfall_bps(fill, mark, leg["side"])
        elif abs(fill - mark) <= MARK_IDENTITY_TOLERANCE:
            row["classification"] = "identity"
            row["reason"] = ("fill equals the struck mark to within "
                             f"{MARK_IDENTITY_TOLERANCE:g} - the venue filled "
                             "at the mark it was handed, so 0.0 bps is an "
                             "arithmetic identity and not a measurement")
            row["shortfall_bps"] = mark_shortfall_bps(fill, mark, leg["side"])
        else:
            row["classification"] = "measured"
            row["reason"] = None
            row["shortfall_bps"] = mark_shortfall_bps(fill, mark, leg["side"])
            if row["shortfall_bps"] is None:
                # A real difference we cannot sign, because the side is
                # unknown. Measured in magnitude, unmeasured in direction.
                row["classification"] = "unusable"
                row["reason"] = f"side is {leg['side']!r}; a cost has no sign without one"
        out.append(row)
    return out


def _stats(values: list[float]) -> Optional[dict]:
    """mean/median/worst/best over a non-empty list, or None.

    None rather than a dict of zeros. An empty sample has no mean, and a fund
    whose execution-cost panel reads 0.0 because nothing was measured is the
    absence-as-zero failure at the top of the non-negotiables.
    """
    if not values:
        return None
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "worst": round(max(values), 4),
        "best": round(min(values), 4),
    }


def class_of_row(row: dict) -> str:
    """The execution class of a STORED row, derived from its raw columns."""
    return execution_class(row.get("submitted_venue"),
                           bool(row.get("was_submitted")))


def summarise_quote_rows(rows: list[dict]) -> dict:
    """Effective spread over stored quote rows, CUT THREE WAYS.

    By execution class, by symbol, and by feed — and there is no fourth,
    undivided number anywhere in the output, deliberately.

    THE HEADLINE IS ``executed`` AND ONLY ``executed``. The three classes on
    this fund's own log, over the consolidated tape on 2026-08-23, are three
    orders of magnitude apart — see :data:`EXECUTION_CLASSES` for the measured
    table and its reproduction command. The flat mean over all 31 measurable
    legs is 560.58 bps; the fund's actual execution cost is 2.89. Both are real
    numbers computed from real quotes and only one of them is the answer.

    The simulated class contains the known GLD phantom-price incident, which
    this instrument re-detects from first principles at 15,146 bps without
    being told to look for it, and the not_submitted class is bookkeeping
    backfills whose prices were never struck against a market at all.

    ``by_symbol`` reports the unmeasured count beside the measured one, so a
    symbol with three fills and no quotes cannot read as a symbol with no fills.
    Feeds are never mixed: an IEX mid and a consolidated mid describe different
    markets.
    """
    fills = [r for r in rows if r.get("event_kind") in FILL_KINDS]
    # MULTI-LEG IS DERIVED FROM THE ROW SET, NOT STORED. It cannot be captured:
    # at the moment of an order's FIRST partial fill nobody knows another leg
    # is coming, so a `multi_leg` column written live would be false on exactly
    # the row that most needs it. Counted here instead, where the whole set is
    # in hand.
    per_order: dict[str, int] = {}
    for r in fills:
        oid = str(r.get("order_id"))
        per_order[oid] = per_order.get(oid, 0) + 1

    def _bucket(subset: list[dict]) -> dict:
        vals, signed_vals, absent = [], [], 0
        for r in subset:
            eff = _num(r.get("effective_spread_bps"))
            if eff is None:
                absent += 1
                continue
            vals.append(eff)
            sg = _num(r.get("signed_effective_spread_bps"))
            if sg is not None:
                signed_vals.append(sg)
        return {"fills": len(vals) + absent, "measured": len(vals),
                "unmeasured": absent,
                "effective_spread_bps": _stats(vals),
                "signed_effective_spread_bps": _stats(signed_vals)}

    by_class: dict[str, dict] = {}
    for cls in EXECUTION_CLASSES:
        subset = [r for r in fills if class_of_row(r) == cls]
        single = [r for r in subset if per_order.get(str(r.get("order_id")), 0) == 1]
        multi = [r for r in subset if per_order.get(str(r.get("order_id")), 0) > 1]
        by_class[cls] = {
            **_bucket(subset),
            # THE CLEANEST FIGURE IN THE WHOLE REPORT, and the reason for the
            # split: on a single-leg order `avg_price` IS the print, so its
            # effective spread is the textbook quantity. On a multi-leg order
            # it is the order's running average against a point-in-time mid,
            # which is a biased estimator of the same thing (see fill_legs).
            # Reported apart rather than averaged together.
            "single_leg": _bucket(single),
            "multi_leg": _bucket(multi),
        }
    by_symbol: dict[str, dict] = {}
    for r in fills:
        sym = r.get("symbol") or "?"
        b = by_symbol.setdefault(sym, {"symbol": sym, "measured": [],
                                       "signed": [], "absent": 0,
                                       "classes": {}, "feeds": {}})
        cls = class_of_row(r)
        b["classes"][cls] = b["classes"].get(cls, 0) + 1
        feed = r.get("feed")
        if feed:
            b["feeds"][feed] = b["feeds"].get(feed, 0) + 1
        eff = _num(r.get("effective_spread_bps"))
        if eff is None:
            b["absent"] += 1
            continue
        b["measured"].append(eff)
        sg = _num(r.get("signed_effective_spread_bps"))
        if sg is not None:
            b["signed"].append(sg)
    out_syms = []
    for sym in sorted(by_symbol):
        b = by_symbol[sym]
        out_syms.append({
            "symbol": sym,
            "fills": len(b["measured"]) + b["absent"],
            "measured": len(b["measured"]),
            "unmeasured": b["absent"],
            "classes": b["classes"],
            "feeds": b["feeds"],
            "effective_spread_bps": _stats(b["measured"]),
            "signed_effective_spread_bps": _stats(b["signed"]),
        })
    by_feed = {}
    for feed in FEEDS:
        vals = [v for v in (_num(r.get("effective_spread_bps"))
                            for r in fills if r.get("feed") == feed)
                if v is not None]
        by_feed[feed] = _stats(vals)
    return {"headline_class": "executed",
            "by_execution_class": by_class,
            "by_symbol": out_syms, "by_feed": by_feed,
            "quote_rows_over_fills": len(fills)}


def summarise_mark_rows(rows: list[dict]) -> dict:
    """The retro table's own summary. Identities are counted, never averaged."""
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(r["classification"], []).append(r)
    measured = [r for r in buckets.get("measured", [])
                if _num(r.get("shortfall_bps")) is not None]
    return {
        "basis": MARK_BASIS,
        "fills": len(rows),
        "classifications": {k: len(v) for k, v in sorted(buckets.items())},
        # THE SUMMARY IS OVER `measured` ONLY, and the exclusions are named and
        # counted beside it rather than being quietly absent from a denominator.
        # On the log as measured 2026-08-23: 34 legs = 12 identity + 8
        # cumulative + 9 no_mark + 5 measured. Folding the identities' zeros in
        # would move the reported cost of trading with no fill having moved,
        # which is the whole reason this function refuses to average them.
        # Reproduce: scripts/execution/retro_spread.py
        "shortfall_bps": _stats([r["shortfall_bps"] for r in measured]),
        "excluded_identities": len(buckets.get("identity", [])),
        "excluded_cumulative": len(buckets.get("cumulative", [])),
        "excluded_no_mark": len(buckets.get("no_mark", [])),
        "excluded_unusable": len(buckets.get("unusable", [])),
    }


def coverage(fill_legs_from_log: list[dict],
             quote_rows: Optional[list[dict]]) -> dict:
    """fills measured / fills total — the P5 precondition's own number.

    ``quote_rows=None`` means the store could not be read AT ALL, and that is
    reported as ``readable: False`` with every count None. It is NOT zero: a
    store we cannot read and a store with nothing in it are different facts and
    only one of them is a reason to go and look at Postgres.
    """
    total = len(fill_legs_from_log)
    if quote_rows is None:
        return {"readable": False, "fill_events_total": total,
                "measured": None, "quote_absent": None, "uncaptured": None,
                "pct_measured": None,
                "reason": "the execution-quote store could not be read"}
    def _key(r):
        # `int(x or -1)` would map a genuine seq of 0 onto the sentinel. Seq 0
        # does not exist in this log, which is precisely why the bug would have
        # shipped; written as an explicit None test because the next store to
        # be counted here may number differently.
        s = r.get("event_seq")
        return (r.get("order_id"), -1 if s is None else int(s))

    # TWO ROWS FOR ONE EVENT COLLAPSE TO ONE, deliberately. The live IEX row
    # and the consolidated row describe the same fill from two markets; a fill
    # is MEASURED if any basis measured it, and counting both would let the
    # coverage figure exceed the number of fills.
    fills = [r for r in quote_rows if r.get("event_kind") in FILL_KINDS]
    seen = {_key(r) for r in fills}
    measured_keys = {_key(r) for r in fills
                     if _num(r.get("effective_spread_bps")) is not None}
    log_keys = {(r["order_id"], r["event_seq"]) for r in fill_legs_from_log}
    measured = len(log_keys & measured_keys)
    captured = len(log_keys & seen)
    return {
        "readable": True,
        "fill_events_total": total,
        "measured": measured,
        # Captured but with no usable mid: the honest middle state.
        "quote_absent": captured - measured,
        # Never reached by the capture service at all.
        "uncaptured": total - captured,
        "pct_measured": round(measured / total * 100.0, 2) if total else None,
    }


# --- the store ------------------------------------------------------------

SCHEMA = """
-- ONE ROW PER (order lifecycle event, basis). APPEND-ONLY by convention and by
-- key: a re-run of the capture service conflicts on the natural key and writes
-- nothing rather than doubling the denominator of every coverage figure.
--
-- A LATER, BETTER MEASUREMENT OF THE SAME EVENT IS A NEW ROW, NOT AN EDIT.
-- The live pass can only see the IEX book; the consolidated quote for the same
-- instant becomes available fifteen minutes later. Those are two rows with two
-- bases, both true, and a reader that wants the NBBO number filters on basis
-- rather than trusting that somebody overwrote the worse one.
CREATE TABLE IF NOT EXISTS fund_execution_quotes (
    quote_row_id   BIGSERIAL PRIMARY KEY,
    order_id       TEXT   NOT NULL,
    event_kind     TEXT   NOT NULL,
    -- The log sequence number of the event this row snapshots. This is the
    -- capture service's checkpoint unit and the join key back to the ledger.
    event_seq      BIGINT NOT NULL,
    -- The EVENT's timestamp, verbatim from the log. Distinct from quote_ts
    -- (when the market printed) and from captured_at (when we wrote the row).
    -- Three clocks, named separately, because the gaps between them are the
    -- measurement's own error bars.
    event_ts       TEXT   NOT NULL,
    -- NULL = no event in this order's lifecycle named a symbol. Measured: the
    -- submitted and partially-filled payloads carry none, so this is a real
    -- state, not a defensive one.
    symbol         TEXT,
    side           TEXT,
    -- THE VENUE THE CONNECTOR HANDED BACK at OrderSubmitted, verbatim, and
    -- NULL when the order has no OrderSubmitted at all. Stored raw rather than
    -- as a verdict: readers derive `execution_class` from it, so a change to
    -- what counts as a simulated venue reclassifies history instead of
    -- leaving a stale label frozen in a column.
    submitted_venue TEXT,
    -- WHETHER AN OrderSubmitted EXISTS AT ALL, stored separately because
    -- submitted_venue IS NULL cannot tell "never sent to anybody" from "sent
    -- by a connector that recorded no venue name". Those classify differently
    -- and only one of them is a real execution.
    was_submitted  BOOLEAN NOT NULL DEFAULT false,

    bid            DOUBLE PRECISION,
    ask            DOUBLE PRECISION,
    bid_size       DOUBLE PRECISION,
    ask_size       DOUBLE PRECISION,
    mid            DOUBLE PRECISION,
    spread_bps     DOUBLE PRECISION,
    quote_ts       TEXT,
    -- WHICH MARKET. 'iex' is one venue's book; 'sip' is the consolidated tape.
    -- Never defaulted: a row that cannot say which market it describes cannot
    -- be compared with any other row.
    feed           TEXT,
    -- Set exactly when there is no usable midpoint, and never blank.
    quote_absent_reason TEXT,

    fill_price     DOUBLE PRECISION,
    filled_qty     DOUBLE PRECISION,
    effective_spread_bps        DOUBLE PRECISION,
    signed_effective_spread_bps DOUBLE PRECISION,

    basis          TEXT   NOT NULL,
    capture_run    TEXT   NOT NULL,
    captured_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fund_execution_quotes_kind
        CHECK (event_kind IN ('submitted','partially_filled','filled')),
    CONSTRAINT fund_execution_quotes_basis
        CHECK (basis IN ('live-iex-bbo','sip-quote-at-event')),
    CONSTRAINT fund_execution_quotes_feed
        CHECK (feed IS NULL OR feed IN ('iex','sip')),
    CONSTRAINT fund_execution_quotes_run_nonblank
        CHECK (btrim(capture_run) <> ''),
    -- ABSENCE IS ENFORCED IN THE DATABASE, not in whoever writes the next
    -- caller. A mid requires both sides; no mid requires a stated reason. The
    -- one thing that must never exist is a row with a midpoint and no quote
    -- behind it, because that is a fabricated price with a basis-point figure
    -- computed off it.
    CONSTRAINT fund_execution_quotes_mid_needs_both_sides
        CHECK ((mid IS NULL) OR (bid IS NOT NULL AND ask IS NOT NULL AND mid > 0)),
    CONSTRAINT fund_execution_quotes_absence_is_stated
        CHECK ((mid IS NOT NULL AND quote_absent_reason IS NULL)
            OR (mid IS NULL AND btrim(coalesce(quote_absent_reason,'')) <> '')),
    -- A basis-point figure with no midpoint under it is the whole failure this
    -- instrument exists to prevent.
    CONSTRAINT fund_execution_quotes_spread_needs_mid
        CHECK (effective_spread_bps IS NULL OR mid IS NOT NULL),
    CONSTRAINT fund_execution_quotes_signed_needs_mid
        CHECK (signed_effective_spread_bps IS NULL OR mid IS NOT NULL),
    CONSTRAINT fund_execution_quotes_natural_key
        UNIQUE (order_id, event_seq, basis)
);

CREATE INDEX IF NOT EXISTS fund_execution_quotes_symbol_idx
    ON fund_execution_quotes (symbol, event_seq);
CREATE INDEX IF NOT EXISTS fund_execution_quotes_seq_idx
    ON fund_execution_quotes (event_seq);
"""

#: Columns :meth:`QuoteStore.rows` selects, in order. One tuple, so the SELECT
#: and the dict it builds cannot drift into disagreeing about column order —
#: the D18 rule: when two structures must agree, DERIVE one from the other.
ROW_COLUMNS = (
    "quote_row_id", "order_id", "event_kind", "event_seq", "event_ts",
    "symbol", "side", "submitted_venue", "was_submitted", "bid", "ask",
    "bid_size", "ask_size", "mid", "spread_bps", "quote_ts", "feed",
    "quote_absent_reason", "fill_price", "filled_qty",
    "effective_spread_bps", "signed_effective_spread_bps",
    "basis", "capture_run", "captured_at",
)

#: The display cap. Fetched as ``limit + 1`` so truncation is a measured fact
#: rather than the ambiguity of ``len(rows) == limit`` (D24).
ROW_QUERY_LIMIT = 1000

#: How far a SUMMARY reads. Deliberately far above the display cap, because a
#: page and a statistic are two different jobs on a capped read (D24): the
#: display may honestly show a thousand rows and say ``truncated``, but a mean
#: computed over "the newest page" is a different number wearing the same
#: label — the exact defect measured in ``GET /fund/tca`` on 2026-08-23.
#:
#: A summary that hits even THIS cap reports ``complete: false`` rather than
#: quietly describing a prefix. One row per fill event per basis, and the fund
#: has made 34 fill events in eleven days, so 100,000 is a very long way off;
#: the flag exists because "a long way off" is not "never".
SUMMARY_SCAN_LIMIT = 100_000


class QuoteStore:
    """Reader/writer over ``fund_execution_quotes``.

    CONSTRUCTING ONE ISSUES NO DDL AND TAKES NO LOCK. Readers use
    :meth:`_read`; the capture service calls :meth:`ensure_schema` once before
    its first write.
    """

    def __init__(self, dsn: Optional[str] = None):
        from app.fund.pgstore import dsn as default_dsn
        self._dsn = dsn or default_dsn()
        self._ensured = False

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def ensure_schema(self) -> bool:
        """Issue the DDL. THE ONLY PLACE THIS MODULE TAKES A WRITE LOCK.

        True the time it ran, False after — memoised per instance so a capture
        loop polling every few seconds issues it once, not once a tick.
        """
        if self._ensured:
            return False
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()
        self._ensured = True
        return True

    def _read(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Every SELECT this module makes. SELECT-only by construction."""
        import psycopg
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
        except psycopg.errors.UndefinedTable as e:
            raise SchemaAbsent(
                "fund_execution_quotes does not exist in this store - the "
                "capture service has never run here, which is NOT the same as "
                "a store with no captured quotes. Start "
                f"scripts/execution/nbbo_capture.py ({e})") from e

    def record(self, *, order_id: str, event_kind: str, event_seq: int,
               event_ts: str, basis: str, capture_run: str,
               symbol: Optional[str] = None, side: Optional[str] = None,
               submitted_venue: Optional[str] = None,
               was_submitted: bool = False,
               bid: Any = None, ask: Any = None,
               bid_size: Any = None, ask_size: Any = None,
               quote_ts: Optional[str] = None, feed: Optional[str] = None,
               quote_absent_reason: Optional[str] = None,
               fill_price: Any = None, filled_qty: Any = None) -> dict:
        """One captured row. Derives the mid and both spreads HERE.

        The caller hands over what it observed — a bid, an ask, a fill — and
        never a computed figure, so there is exactly one implementation of the
        arithmetic and a second caller cannot ship a second convention.

        ``quote_absent_reason`` passed by the caller WINS over a derived one:
        "the vendor call raised a timeout" is more informative than "no_quote",
        and both are true.
        """
        if event_kind not in EVENT_KINDS:
            raise ValueError(f"event_kind must be one of {EVENT_KINDS}, got {event_kind!r}")
        if basis not in BASES:
            raise ValueError(f"basis must be one of {BASES}, got {basis!r}")
        if feed is not None and feed not in FEEDS:
            raise ValueError(f"feed must be one of {FEEDS} or None, got {feed!r}")
        if not (isinstance(capture_run, str) and capture_run.strip()):
            raise ValueError(
                "capture_run identifies the process that wrote this row; a "
                "blank one makes a bad capture impossible to fence off later")
        mid, derived_reason = mid_of(bid, ask)
        reason = quote_absent_reason or derived_reason
        if mid is not None and quote_absent_reason:
            # The caller says the quote is not usable. Believe the caller and
            # DROP the mid rather than storing a figure it disowned.
            mid, reason = None, quote_absent_reason
        spread = spread_bps_of(bid, ask) if mid is not None else None
        eff = effective_spread_bps(fill_price, mid) if mid is not None else None
        signed = (signed_effective_spread_bps(fill_price, mid, side)
                  if mid is not None else None)
        self.ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fund_execution_quotes
                        (order_id, event_kind, event_seq, event_ts, symbol,
                         side, submitted_venue, was_submitted, bid, ask,
                         bid_size, ask_size, mid, spread_bps,
                         quote_ts, feed, quote_absent_reason, fill_price,
                         filled_qty, effective_spread_bps,
                         signed_effective_spread_bps, basis, capture_run)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            %s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (order_id, event_seq, basis) DO NOTHING
                    RETURNING quote_row_id
                    """,
                    (order_id, event_kind, int(event_seq), event_ts, symbol,
                     side, submitted_venue, bool(was_submitted),
                     _num(bid), _num(ask), _num(bid_size), _num(ask_size),
                     mid, spread, quote_ts, feed, reason, _num(fill_price),
                     _num(filled_qty), eff, signed, basis, capture_run))
                got = cur.fetchone()
            conn.commit()
        return {"quote_row_id": int(got[0]) if got else None,
                "created": got is not None, "order_id": order_id,
                "event_seq": int(event_seq), "basis": basis, "mid": mid,
                "event_kind": event_kind, "symbol": symbol, "side": side,
                "submitted_venue": submitted_venue,
                "was_submitted": bool(was_submitted),
                "effective_spread_bps": eff,
                "signed_effective_spread_bps": signed,
                "quote_absent_reason": reason}

    def rows(self, limit: int = ROW_QUERY_LIMIT,
             basis: Optional[str] = None) -> tuple[list[dict], bool]:
        """``(rows, truncated)``, newest event first.

        Fetches ``limit + 1`` so truncation is measured. ``len(rows) == limit``
        cannot tell a full page from a cut one, and ``>=`` reports an outage on
        a merely-full table (D24, mutant N9).
        """
        where, params = "", []
        if basis is not None:
            where, params = "WHERE basis = %s", [basis]
        raw = self._read(
            f"SELECT {', '.join(ROW_COLUMNS)} FROM fund_execution_quotes "
            f"{where} ORDER BY event_seq DESC, quote_row_id DESC LIMIT %s",
            tuple(params) + (int(limit) + 1,))
        truncated = len(raw) > limit
        out = []
        for r in raw[:limit]:
            d = dict(zip(ROW_COLUMNS, r))
            d["captured_at"] = (d["captured_at"].isoformat()
                                if d["captured_at"] is not None else None)
            out.append(d)
        return out, truncated

    def count(self, basis: Optional[str] = None) -> int:
        """The whole table's size, not the page's. One ``count(*)``."""
        if basis is None:
            return int(self._read(
                "SELECT count(*) FROM fund_execution_quotes")[0][0])
        return int(self._read(
            "SELECT count(*) FROM fund_execution_quotes WHERE basis = %s",
            (basis,))[0][0])

    def max_event_seq(self, basis: Optional[str] = None) -> Optional[int]:
        """The highest log seq this store has captured, or None if it has none.

        None is "nothing captured", never 0 — seq 0 does not exist in the log
        and returning it would silently mean "start from the beginning".
        """
        if basis is None:
            got = self._read("SELECT max(event_seq) FROM fund_execution_quotes")
        else:
            got = self._read(
                "SELECT max(event_seq) FROM fund_execution_quotes WHERE basis = %s",
                (basis,))
        v = got[0][0] if got else None
        return int(v) if v is not None else None
