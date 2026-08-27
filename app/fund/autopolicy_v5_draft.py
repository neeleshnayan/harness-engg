"""AUTOPOLICY v5 — DRAFT. NOT WIRED. NOTHING IMPORTS THIS AND NOTHING MAY.

================================================================================
THIS MODULE IS NOT PART OF THE APPROVAL PATH AND MUST NOT BECOME PART OF IT
WITHOUT THE FULL CHAIN: adversary blind -> riskofficer -> the CEO's click on the
version. It is a DESIGN ARTIFACT written to be attacked. `app/fund/autopolicy.py`
is untouched by the diff that introduced this file; `AUTOPOLICY_VERSION` is still
"v4" and this module's version string is deliberately not a version of anything.
================================================================================

WHAT IT IS FOR. v4's envelope admits exactly one thing: an exit-rule-triggered
SELL. That was the narrowest slice that delivered real agency, and it is now the
binding constraint on the CEO's decision that "funds dont manually approve each
trade" — because an ENGINE that can only be auto-approved when it is CLOSING is
an engine whose every entry waits for a human. v5 proposes a SECOND admission
class: an ENTRY raised by a LIVE ENGINE SESSION belonging to a DEPLOYED strategy,
inside an envelope that bounds what one bad day can cost.

--------------------------------------------------------------------------------
REVISION r2 (2026-08-27). THE FIRST DRAFT WAS KILLED BY THE ADVERSARY ON TWO
STRUCTURAL GROUNDS AND THE KILL WAS ACCEPTED. Both are answered here, in the
code rather than in prose, and both are recorded because a draft that quietly
absorbs a kill teaches the next reader nothing.

  KILL 1 — EVERY BOUND READ THE FILLED BOOK, SO IN-FLIGHT ORDERS WERE INVISIBLE
  AND STACKED. Measured on the shipped r1: two approved-unfilled orders each
  sized at 14.9% of NAV, each individually "inside" a 20% per-name ceiling,
  reached 29.8% of NAV in one name; five reached 74.5%. Every check green, every
  time, because the concentration bound was computed from a book that had not
  moved yet. The answer is a PENDING-APPROVED LEDGER carried in the context and
  folded, once, by ``in_flight`` — see THE IN-FLIGHT CONTRACT below.

  KILL 2 — A ZERO-CROSSING SELL WAS AUTO-APPROVABLE, AND THE FUND CANNOT EXIT A
  SHORT. ``exitrule.py:326`` can only raise SELLs, so a short position's own
  committed exit DEEPENS it: the pre-commitment check (15 in r1) was satisfied
  by a rule that makes the position worse. r1 approved a naked short of 14.9% of
  NAV from a flat book with all 23 checks green. The answer is
  ``post_fill_position_not_short``: SELLS ARE REDUCE-ONLY in this class, and the
  bound is taken over the WORST in-flight outcome, not the netted one.

  Four residuals from the same review are closed here too: an ISO timestamp
  compared as a raw string (a false ACCEPT, demonstrated); an unsigned mark
  move (a -75.9% mark passed a 30% bound — the GLD-phantom shape); context
  values accepted outside the unit their own name declares (a NAV of 1e308
  made every percentage vacuously tiny, and ``float(True) == 1.0`` made a
  boolean a number); and seventeen inputs that made ``evaluate`` RAISE, on a
  function whose whole contract is to return a verdict for every input.

WHAT IT DOES NOT DO, and this is deliberate rather than unfinished:

  * It does not replace v4. v4's exit envelope stands unchanged. An order is
    auto-approvable if it passes EITHER envelope, and this module implements
    only the new one.
  * It never widens anything on its own. Every check below either has no
    counterpart in v4 (it is new) or is strictly at least as tight.
  * It reads nothing. Every input arrives in ``context``, gathered by a caller
    that does not exist yet. That is what keeps it unreachable — and it is also
    how v4 is written, so the shape is the house idiom rather than a dodge.
  * It has NO CLOCK. Every age arrives already computed, in minutes, from the
    gatherer. A module that reads a clock is a module whose tests have to
    freeze one, and an envelope whose freshness depends on which machine ran it
    is not deterministic.
  * It admits no instrument with a contract multiplier. Notional is
    ``|qty| x mark``, which is true for equities and ETFs and false for
    futures and options. Admitting one of those is a versioned change that
    must add the multiplier to the contract first.

--------------------------------------------------------------------------------
THE IN-FLIGHT CONTRACT — the numbered specification the kill asked for.

  (1) DEFINITION. An order is IN FLIGHT when this envelope APPROVED it and the
      event log carries no TERMINAL event for it — no fill, no cancel, no
      rejection, no failure. It is neither in the fund's book (nothing filled)
      nor in the broker's position (the broker holds no unfilled order), so it
      is invisible to every ledger both v4 and r1 consulted. That invisibility
      IS the defect.

  (2) EVENT SOURCES, for the gatherer that does not exist yet. The set opens on
      the envelope's own approval record and closes on any terminal event for
      the same ``order_id``. It must be built from the ORDER AGGREGATE, never
      from a position fold: a fold cannot represent an order that has not moved
      anything.

  (3) SHAPE. ``context["pending_approved"]`` is a list of rows, or ``None``.
      ``None`` means THE LEDGER COULD NOT BE READ and refuses; ``[]`` means the
      ledger was read and nothing is in flight, which is a measured zero. These
      are different facts and giving the unreadable case its own value — rather
      than an empty list plus a flag patched in afterwards — is the whole
      lesson of ``leansessions``. Each row:

          {order_id, strategy_id, symbol, side, qty, mark_usd, age_minutes}

      Any row that cannot be parsed makes the WHOLE fold unreadable. A partial
      sum over in-flight exposure is worse than no sum: it looks like a
      measurement and bounds nothing.

  (4) DIRECTION OF EVERY FAILURE. Unreadable refuses. A stale row refuses
      (``in_flight_orders_fresh``) — not because counting it would be
      dangerous, but because a terminal event that has not arrived in
      ``MAX_PENDING_AGE_MINUTES`` means the ledger's OTHER direction is also
      suspect, and the direction we cannot see is the permissive one: an
      in-flight order the ledger has lost entirely.

  (5) WHERE IT IS ADDED, AND THE ONE PLACE IT IS NOT. It enters the three
      exposure bounds (name concentration, strategy allocation, gross against
      the throttle) and the reduce-only bound. It is EXCLUDED, deliberately and
      by construction, from ``book_venue_in_sync``: the broker cannot hold an
      unfilled order, so folding in-flight into the book side of that
      comparison would make every pending order look like a reconciliation
      break. The adversary probed exactly that naive fix and it fails closed on
      every order — a control that refuses everything is not a control.

  (6) WORST CASE, NOT NET. The bounds are taken over the corners of the
      in-flight set rather than its sum. For shortness the worst case is that
      every in-flight BUY fails and every in-flight SELL fills; for
      concentration it is whichever of {none, buys only, sells only, all} gives
      the largest magnitude. Netting a pending buy against a pending sell would
      let a cancellable order pay for a real one.

  (7) WHAT IT DOES NOT BOUND, stated so nobody reads more into it. In-flight
      orders in OTHER symbols are summed at their absolute notional rather than
      netted against those symbols' books, because this fold is not given those
      books. That OVER-states gross, which is the safe direction, and it is
      named here so the number is never mistaken for a measurement of gross.

--------------------------------------------------------------------------------
TWO HELPERS ARE DUPLICATED FROM ``autopolicy.py`` ON PURPOSE — ``_as_float``
and ``order_delta``, and no others. This fund's standing rule is to prove a
value is READ rather than COPIED, and copies are how two modules acquire two
ideas of one thing. The requirement here outranks it exactly once: a draft that
IMPORTS the live policy is a draft the live policy's import graph can reach.
**De-duplicating them is part of the wiring step, and the wiring step is the one
that goes through the chain.** ``tests/test_autopolicy_v5_draft.py`` compares
both against the originals by BEHAVIOUR over a shared table, so the drift is
visible for as long as the copy exists.

``_as_float`` IS THE COPY AND IS NOT WHERE v5's OWN RULES LIVE. Range and type
discipline belong to ``_number``, which is v5's and may tighten freely without
making the copy drift from its original — the two jobs were conflated in r1 and
that is why ``float(True)`` reached a threshold comparison.

THE FIVE ATTACKS THIS DRAFT EXPECTS, ANSWERED IN THE CODE RATHER THAN HERE:

  1. *"engine-raised" is a claim, and claims are forgeable.* v4 learned this
     about ``EXIT_MARKER``: a marker string is wording, an EVENT is provenance.
     ``signal_from_live_session`` is v5's answer — and the residual (the signal
     token is a bearer credential) is named on the payload, not buried.
  2. *An entry has no position to reduce, so v4's whole safety argument is
     gone.* Replaced by bounds that hold at the moment of the fill AND under
     every in-flight outcome: per-name concentration, per-strategy allocation,
     gross against the throttle, a per-order plus per-DAY notional ceiling, and
     a reduce-only rule that keeps the book on the side the fund can exit from.
  3. *An entry with no way out is the trade that kills a fund.*
     ``exit_committed_for_entry`` refuses it. An entry whose exit is written
     after the fill is not pre-commitment — and after r2 that ordering is
     decided by parsed instants, not by string comparison.
  4. *The unmeasurable case is where envelopes leak.* Every check fails closed,
     and the three that are easiest to get backwards — an unmeasurable regime,
     an empty asset scope, an unreadable day of history — are each asserted
     twice in the tests, once for the refusal and once for the reason.
  5. *A kill switch nobody calls is not a control.* ``engine_entries_armed`` is
     the FIRST check and it is read from the context on every single order, so
     turning it off reverts the book to manual on the next tick rather than at
     the next deploy.
"""

from __future__ import annotations

from typing import Any, Optional

#: Not a version of anything live. It exists so an evaluation recorded from a
#: draft can never be mistaken for one recorded under a governed envelope. The
#: ``r2`` suffix is load-bearing: r1's payloads and r2's answer differently on
#: the same order, and an audit that could not tell them apart would be
#: comparing two envelopes under one name.
AUTOPOLICY_V5_DRAFT_VERSION = "v5-draft-2026-08-27r2"

# =============================================================================
# THE PROPOSED NUMBERS. Every one is a THRESHOLD, which means every one is the
# CEO's to set and none of them is decided here. What is decided here is which
# quantity each bounds and which direction it fails. The values below are
# STARTING PROPOSALS with the reasoning attached, and the design memo
# (docs/design/AUTOPOLICY_V5_2026-08-27.md) carries the same table for the
# riskofficer to attack.
# =============================================================================

#: Per-order ceiling, as a percent of last struck NAV. Proposed EQUAL TO the
#: pre-trade gate's ``max_order_notional_pct`` (0.15 -> 15%), on the same
#: reasoning v4 used for its own cap: an auto-approved order that a HUMAN could
#: not have submitted through the ordinary gate would be a second, looser door
#: into the same book. This one can only ever be tighter than that door or the
#: same width; it must never be wider.
MAX_ENGINE_ORDER_NOTIONAL_PCT = 15.0

#: THE NUMBER THAT DECIDES WORST-CASE DAILY DAMAGE, and the one the CEO should
#: argue with first. Cumulative auto-approved ENTRY notional per UTC day, as a
#: percent of last struck NAV. Proposed at 30% = two full-size orders.
#:
#: WHY A DAILY CAP AT ALL, stated because a per-order cap looks like it already
#: bounds the damage and does not: an engine on a daily bar raises one signal a
#: day, but an engine in a loop raises as many as it likes, and the per-order
#: cap bounds each one rather than the day. The failure this stops is not a
#: large order; it is a hundred small ones.
#:
#: IT IS NOT THE IN-FLIGHT BOUND AND MUST NOT BE READ AS ONE. It counts a UTC
#: day of approvals; the in-flight ledger counts orders whose outcome is still
#: unknown. r1 had only this one, and the adversary showed it catching the
#: stacking case at 29.8% of NAV against a 20% per-name ceiling — a bound that
#: fires after the ceiling it was supposed to protect has already been broken.
MAX_ENGINE_DAILY_NOTIONAL_PCT = 30.0

#: Freshness for the signal that raised the order. Deliberately tighter than
#: v4's 10 minutes for exits, because an ENTRY is discretionary in a way an exit
#: is not: nothing is lost by refusing a stale entry and waiting for the next
#: bar, whereas v4's own comment records that a refused exit does NOT come back.
MAX_SIGNAL_AGE_MINUTES = 5.0

#: How old an APPROVED-BUT-UNFILLED order may be before this envelope stops
#: trusting its own in-flight ledger. Proposed at 30 minutes.
#:
#: THE REASONING, because the number looks arbitrary and is not. Settlement
#: polls every ``SETTLE_INTERVAL_SECONDS`` (30s in the deployed worker), so a
#: submitted order's terminal event should arrive within one or two polls;
#: thirty minutes is sixty poll cycles. An order still open after that has
#: either been lost by the venue or lost by our own fold, and in both cases the
#: in-flight set we are about to bound exposure with is not the in-flight set
#: that exists. Refusing is the honest response to a ledger that has stopped
#: agreeing with the world — and it costs a human click, not a position.
MAX_PENDING_AGE_MINUTES = 30.0

#: Largest disagreement between the mark the order was priced at and the fund's
#: own last struck mark. SAME VALUE AND SAME REASON AS v4's
#: ``MAX_MARK_MOVE_VS_STRIKE_PCT``: two definitions of "the mark is sane" is the
#: second-opinion defect ``marksanity`` was written to name. If v4's moves, this
#: moves with it; the tests pin them together.
#:
#: r2 takes its ABSOLUTE VALUE before comparing. r1 did not, so a mark reported
#: as -75.9% of the struck mark satisfied ``<= 30`` — the same shape as the GLD
#: phantom, in the check written to catch it.
MAX_MARK_MOVE_VS_STRIKE_PCT = 30.0

#: Staleness ceiling for the risk monitor's own heartbeat, in seconds. NAMED
#: SEPARATELY from the ``liveness_*`` checks even though it looks redundant: the
#: heartbeat's ``ok`` flag is computed against a budget declared inside
#: ``heartbeat.BUDGETS_SECONDS``, and an envelope that self-executes on the
#: strength of a control being alive should state its OWN requirement rather
#: than inherit whatever that budget happens to be next year.
MAX_RISK_MONITOR_AGE_SECONDS = 300.0

#: A CORRUPTION DETECTOR, NOT A RISK LIMIT, and the distinction decides how it
#: should be argued with. NAV is the denominator of every cap in this module, so
#: a NAV that is absurdly large makes every percentage vacuously small and every
#: bound vacuously satisfied — the one input whose corruption fails OPEN. r1
#: accepted ``nav_usd = 1e308`` and approved on it.
#:
#: There is no principled ceiling on a fund's NAV, so this is deliberately far
#: above anything this fund can reach ($1 trillion) and exists only to separate
#: a number from a corrupted field. A fund that genuinely approaches it should
#: raise it as a versioned change and will have larger questions that day.
MAX_PLAUSIBLE_NAV_USD = 1e12

#: The controls that must be demonstrably alive. Same three as v4 plus
#: ``nav_strike`` — v5's caps are ALL percentages of NAV, so a stale NAV makes
#: every one of them a percentage of a number nobody struck today, which v4
#: never depended on to the same degree (its one NAV-relative cap sat behind
#: three position checks that do not use NAV at all).
#:
#: MEASURED CAVEAT FOR THE RISKOFFICER, because adding the job is not the same
#: as bounding it: ``heartbeat.BUDGETS_SECONDS["nav_strike"]`` is **5400s**
#: (heartbeat.py:50), so ``liveness_nav_strike`` passing means the strike ran
#: within NINETY MINUTES. Whether that is fresh enough for a cap that decides
#: unattended execution is a judgement this draft does NOT make; it names the
#: number so the judgement can be made with it in view.
REQUIRED_HEARTBEATS = ("exit_check", "risk_monitor", "settlement", "nav_strike")

#: The only venue an engine entry may execute on, as a ``mode.VenueKind``
#: VALUE — not a connector name, not a label, not a mode name.
#:
#: **THE THREE SPELLINGS ARE NOT INTERCHANGEABLE AND ONE OF THEM DOES NOT
#: DISCRIMINATE. Measured against the live spine, 2026-08-27,
#: `GET /fund/mode`:**
#:
#:     mode           kind            label          permitted_connectors
#:     alpaca-paper   alpaca_paper    alpaca         ["alpaca"]
#:     alpaca-prod    alpaca_live     alpaca-live    ["alpaca"]
#:
#: **The paper account and the REAL-MONEY account permit the SAME CONNECTOR** —
#: and ``mode.py:167-170`` says so in its own words: *"``connector.name`` is
#: 'alpaca' for both"*. That comment is about ``venue_label``; ``venue_kind``
#: and ``real_money`` are two further fields that separate them, and this draft
#: reads both rather than either.
#: An earlier draft of this constant was the string ``"alpaca"``, which is the
#: connector name and the paper mode's label — and a gatherer that supplied
#: either of those from ``alpaca-prod`` would have passed this check with real
#: money behind it. The kind is the only field that separates them, and
#: ``real_money`` is the second, independent one.
#:
#: Read from the RESOLVED venue, never from ``order["venue"]`` — v4 learned
#: that the hard way: ``exitrule.py`` hardcodes ``"paper"`` on every exit it
#: raises whatever connector will actually execute it, so a check against the
#: order's own field would have passed the exact orders that went to Alpaca.
PERMITTED_VENUE_KIND = "alpaca_paper"

#: Float noise, not a threshold. Same constant and same value as
#: ``autopolicy.POSITION_EPS`` so three ledgers cannot acquire three ideas of
#: zero.
POSITION_EPS = 1e-9

#: Same value and same reason as ``autopolicy.MAX_POSITION_DRIFT_QTY``: equal to
#: the reconciler's own tolerance, because a symbol the reconciler calls drifted
#: while this policy calls it reconciled is the fund holding two beliefs about
#: one number.
MAX_POSITION_DRIFT_QTY = 1e-6


def _as_float(value: Any) -> Optional[float]:
    """A context value as a float, or ABSENT. Never raises.

    Duplicated from ``autopolicy._as_float`` — see the module header for why the
    copy exists and when it must be removed. Identical semantics on purpose,
    including NaN and infinity landing on ABSENT: ``evaluate`` is the
    deterministic core of an execution path and must return a verdict for every
    input it is handed, because an exception here would abort the tick and leave
    the remaining orders unevaluated.

    IT IS NOT WHERE v5's RANGE OR TYPE RULES LIVE. Those are ``_number``'s, so
    tightening them cannot make this copy drift from the original it is pinned
    against.
    """
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def order_delta(order: dict[str, Any]) -> Optional[float]:
    """Signed effect of an order on a position: ``+qty`` buy, ``-qty`` sell.

    ``None`` when side or quantity cannot be read. Duplicated from
    ``autopolicy.order_delta``; the note about ``float(qty or 0.0)`` turning an
    absent quantity into a free pass applies here identically and is why the
    absent case is ``None`` rather than ``0.0``.
    """
    qty = _as_float(order.get("qty"))
    if qty is None:
        return None
    side = str(order.get("side") or "").lower()
    if side == "buy":
        return abs(qty)
    if side == "sell":
        return -abs(qty)
    return None


def _number(value: Any, *, lo: Optional[float] = None,
            hi: Optional[float] = None) -> Optional[float]:
    """A context value as a number INSIDE ITS DECLARED RANGE, or ABSENT.

    v5's own reader, and the place r1's two range defects are closed.

    **A BOOLEAN IS NOT A NUMBER HERE, even though Python says it is.** ``bool``
    subclasses ``int``, so ``float(True) == 1.0`` and r1 accepted ``True`` as a
    position fraction (100% of NAV), as a throttle multiplier (full gross) and
    as a dollar figure. Every one of those readings was permissive, and none of
    them was a number anybody wrote down. A gatherer that hands a flag where a
    quantity belongs has a defect, and the envelope's job is to refuse rather
    than to interpret.

    **THE RANGE IS THE FIELD'S OWN UNIT, NOT A NEW THRESHOLD.** The contract in
    ``evaluate`` already says ``_fraction`` means 0..1 and ``_pct`` means
    0..100; r1 stated it and did not enforce it, so ``max_position_fraction =
    1e308`` produced a ceiling of 1e310 percent and every concentration bound
    passed vacuously. Enforcing a documented unit is not a threshold change; it
    is the difference between a contract and a comment.

    Out of range lands on ABSENT rather than on a clamp, because a value we
    cannot trust must make its checks say "this could not be read" — which is a
    different sentence from "it was too big", and the audit reads the sentence.
    """
    if isinstance(value, bool):
        return None
    out = _as_float(value)
    if out is None:
        return None
    if lo is not None and out < lo:
        return None
    if hi is not None and out > hi:
        return None
    return out


def post_fill_position(pre: Optional[float],
                       delta: Optional[float]) -> Optional[float]:
    """Where the book ends up if this order fills. ABSENT if either side is.

    THE WHOLE OF v5's SAFETY ARGUMENT IS COMPUTED FROM THIS, so it is one
    function rather than three additions in three checks. v4 could reason about
    an exit purely from the sign of what already existed; an entry has nothing
    to reduce, so every bound v5 sets is a bound on the position AFTER the fill,
    and computing that in three places is how two of them end up disagreeing.
    """
    if pre is None or delta is None:
        return None
    return float(pre) + float(delta)


def _usd(qty: Optional[float], mark: Optional[float]) -> Optional[float]:
    """A signed quantity valued at a mark, or ABSENT — never zero for absent."""
    if qty is None or mark is None:
        return None
    return float(qty) * float(mark)


def post_fill_exposure(total_before: Optional[float],
                       symbol_before_usd: Optional[float],
                       symbol_after_usd: Optional[float],
                       other_pending_usd: Optional[float] = 0.0
                       ) -> Optional[float]:
    """GROSS exposure after this fill: swap this symbol's contribution out and
    the new one in, then add whatever is in flight ELSEWHERE. ABSENT if any
    term is.

    Written as a swap rather than as ``total + notional`` because ``+ notional``
    is only right when the order INCREASES a position it is already long. It is
    wrong for a sell that reduces one, wrong for a buy that closes a short, and
    catastrophically wrong for an order that crosses zero — all three of which
    an ENGINE entry can be, and none of which v4 ever had to consider because v4
    only ever closed a long.

    ABSOLUTE VALUES, because gross is what the throttle and the allocation both
    bound: a long and a short of equal size consume the same balance sheet, and
    a signed sum would report the pair as flat.

    ``other_pending_usd`` is r2's addition and it is an OVER-STATEMENT BY
    DESIGN (contract item 7): in-flight orders in other symbols are added at
    their absolute notional rather than netted against those symbols' books,
    which this function is not given. Over-stating gross refuses more orders,
    never fewer. It defaults to 0.0 so the pure swap can still be tested on its
    own, and every caller in ``evaluate`` passes it explicitly.
    """
    if (total_before is None or symbol_before_usd is None
            or symbol_after_usd is None or other_pending_usd is None):
        return None
    return (float(total_before) - abs(float(symbol_before_usd))
            + abs(float(symbol_after_usd)) + abs(float(other_pending_usd)))


def within(value: Optional[float], ceiling: Optional[float]) -> Optional[bool]:
    """``|value| <= ceiling``, or ``None`` when either is unreadable.

    THREE-VALUED ON PURPOSE. A caller that gets ``None`` must fail its check
    with a reason that says the number could not be read, which is a different
    sentence from "the number was too big" — and the audit reads the sentence.
    Returning ``False`` for both would make an unreadable NAV indistinguishable
    from an oversized order in the record the riskofficer works from.
    """
    if value is None or ceiling is None:
        return None
    return abs(value) <= ceiling + POSITION_EPS


# =============================================================================
# THE IN-FLIGHT FOLD. ONE function, ONE input, every quantity the envelope
# needs about orders it has approved and not yet seen the end of.
#
# WHY ONE FUNCTION AND NOT FIVE READS. This fund shipped a payload whose five
# fields described one condition and whose caller computed two of them —
# ``leansessions`` exists because of it. The in-flight state is the same shape:
# readable-ness, freshness, four exposure quantities and a sentence, all
# derived from one list. A caller that computed any of them separately would
# be the one that forgot to update it, because the fields nobody looks at are
# the fields nobody patches.
# =============================================================================

#: Returned when the ledger itself was ``None``. Named so the refusal sentence
#: can distinguish "we could not ask" from "a row was malformed".
IN_FLIGHT_UNREADABLE = "the in-flight ledger could not be read"


def in_flight(pending: Any, symbol: Any, strategy_id: Any) -> dict[str, Any]:
    """Fold the pending-approved ledger into the quantities the bounds need.

    ``pending`` is a list of rows, or ``None`` when the ledger is unreadable.
    ``[]`` is a MEASURED ZERO and is readable; the two are never collapsed.

    Every returned quantity is ``None`` when the fold is unreadable, so a caller
    that forgets to check ``readable`` still fails closed through ``within``
    rather than silently bounding against a partial sum.

    THE FOUR QUANTITIES, and why each is separate:

      ``symbol_buy_qty``  / ``symbol_sell_qty``  — this symbol, fund-wide,
          split by direction rather than netted, because the worst case for
          shortness (only the sells fill) and the worst case for concentration
          (whichever corner is largest) need different corners of the same set.
          A net would let a cancellable buy pay for a real sell.
      ``strategy_buy_qty`` / ``strategy_sell_qty`` — the same for this
          strategy alone, because the allocation bound is per-strategy and
          another strategy's in-flight order does not consume it.
      ``other_gross_usd`` / ``strategy_other_gross_usd`` — every OTHER symbol's
          in-flight notional, absolute, valued at each row's own mark. Absolute
          and un-netted by design (contract item 7).

    A row is parseable only if it names a symbol, a side we understand, a
    strictly positive quantity, a strictly positive mark and a non-negative
    age. ONE BAD ROW MAKES THE WHOLE FOLD UNREADABLE: a sum with an unknown
    term is unknown, not the sum of its known terms — the same rule the engine
    ledger applies to an unquantified signal.
    """
    absent = {
        "readable": False,
        "rows": None,
        "symbol_buy_qty": None,
        "symbol_sell_qty": None,
        "strategy_buy_qty": None,
        "strategy_sell_qty": None,
        "other_gross_usd": None,
        "strategy_other_gross_usd": None,
        "stale_rows": None,
        "oldest_age_minutes": None,
        "fresh": None,
    }
    if pending is None:
        return {**absent, "reason": IN_FLIGHT_UNREADABLE}
    # A string is iterable and is not a ledger. ``dict`` is iterable too and
    # would yield its keys. Only a genuine sequence of rows is accepted.
    if not isinstance(pending, (list, tuple)):
        return {**absent,
                "reason": f"the in-flight ledger is a {type(pending).__name__}, "
                          f"not a list of orders"}

    want_sym = str(symbol or "").strip().upper()
    want_sid = str(strategy_id or "").strip()
    sym_buy = sym_sell = st_buy = st_sell = 0.0
    other_gross = st_other_gross = 0.0
    stale = 0
    oldest: Optional[float] = None

    for i, row in enumerate(pending):
        if not isinstance(row, dict):
            return {**absent,
                    "reason": f"in-flight row {i} is a {type(row).__name__}, "
                              f"not an order"}
        oid = str(row.get("order_id") or "").strip() or f"#{i}"
        r_sym = str(row.get("symbol") or "").strip().upper()
        r_side = str(row.get("side") or "").strip().lower()
        r_qty = _number(row.get("qty"), lo=0.0)
        r_mark = _number(row.get("mark_usd"), lo=0.0)
        r_age = _number(row.get("age_minutes"), lo=0.0)
        if not r_sym:
            return {**absent, "reason": f"in-flight order {oid} names no symbol"}
        if r_side not in ("buy", "sell"):
            return {**absent,
                    "reason": f"in-flight order {oid} has side "
                              f"{row.get('side')!r}, which is neither buy nor sell"}
        if r_qty is None or r_qty <= POSITION_EPS:
            return {**absent,
                    "reason": f"in-flight order {oid} has an unreadable or "
                              f"non-positive quantity ({row.get('qty')!r})"}
        if r_mark is None or r_mark <= POSITION_EPS:
            return {**absent,
                    "reason": f"in-flight order {oid} has an unreadable or "
                              f"non-positive mark ({row.get('mark_usd')!r})"}
        # AN UNREADABLE AGE IS STALE, NOT FRESH. It does not make the fold
        # unreadable — the exposure arithmetic does not need it — but it must
        # never buy the order a pass on the freshness check.
        if r_age is None:
            stale += 1
        else:
            if oldest is None or r_age > oldest:
                oldest = r_age
            if r_age > MAX_PENDING_AGE_MINUTES:
                stale += 1

        r_sid = str(row.get("strategy_id") or "").strip()
        mine = bool(want_sid) and r_sid == want_sid
        if r_sym == want_sym and want_sym:
            if r_side == "buy":
                sym_buy += r_qty
                if mine:
                    st_buy += r_qty
            else:
                sym_sell -= r_qty
                if mine:
                    st_sell -= r_qty
        else:
            other_gross += r_qty * r_mark
            if mine:
                st_other_gross += r_qty * r_mark

    return {
        "readable": True,
        "reason": None,
        "rows": len(pending),
        "symbol_buy_qty": sym_buy,
        "symbol_sell_qty": sym_sell,
        "strategy_buy_qty": st_buy,
        "strategy_sell_qty": st_sell,
        "other_gross_usd": other_gross,
        "strategy_other_gross_usd": st_other_gross,
        "stale_rows": stale,
        "oldest_age_minutes": oldest,
        "fresh": stale == 0,
    }


def worst_short_position(pre: Optional[float], pending_sell_qty: Optional[float],
                         delta: Optional[float]) -> Optional[float]:
    """The most NEGATIVE the book can be once everything resolves.

    Every in-flight BUY fails and every in-flight SELL fills. That is the
    corner that decides whether this order can leave the fund short, and it is
    not the netted one: netting would let a buy that may never fill pay for a
    sell that will.
    """
    if pre is None or pending_sell_qty is None or delta is None:
        return None
    return float(pre) + float(pending_sell_qty) + float(delta)


def worst_abs_position(pre: Optional[float], pending_buy_qty: Optional[float],
                       pending_sell_qty: Optional[float],
                       delta: Optional[float]) -> Optional[float]:
    """The largest MAGNITUDE the book can reach once everything resolves.

    Four corners — nothing else fills, only the buys fill, only the sells fill,
    everything fills — and the largest absolute value among them. Concentration
    bounds a magnitude, and the magnitude is not monotone in the in-flight set:
    a pending sell shrinks a long and grows a short.
    """
    if (pre is None or pending_buy_qty is None or pending_sell_qty is None
            or delta is None):
        return None
    base = float(pre) + float(delta)
    b, s = float(pending_buy_qty), float(pending_sell_qty)
    corners = (base, base + b, base + s, base + b + s)
    return max(corners, key=abs)


def evaluate(order: Any, *, halted: bool,
             heartbeats: Any,
             signal_age_minutes: Any,
             context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """One ENGINE ENTRY against the proposed v5 envelope. Deterministic.

    APPROVE only when EVERY check is exactly ``True``. Any check that cannot be
    evaluated fails closed; an absence is never a yes. Non-short-circuiting like
    v4: every check is evaluated and recorded even after an earlier one has
    failed, because that is what made v4's first audit possible from the log
    alone — a policy that stops at the first refusal tells the riskofficer
    nothing about the other twenty.

    **IT RETURNS A VERDICT FOR EVERY INPUT AND NEVER RAISES.** r1 promised that
    in this docstring and did not deliver it: seventeen context values made it
    throw, because a non-dict ``strategy`` reached ``.get`` and a non-iterable
    ``live_sessions`` reached a ``for``. An exception here aborts the tick and
    leaves every remaining order unevaluated, which is a fund-wide outage
    raised by one malformed field. r2 normalises each input to its own type and
    wraps the whole body in ``evaluate_completed`` — a check that appears on
    every payload and is ``False``, with the exception named, if anything
    unforeseen still escapes. Refusing loudly is the point; swallowing is not.

    ``context`` carries everything read from the world. The gatherer does not
    exist yet, and the fields are named here so it can be written against a
    contract rather than against a guess:

    **EVERY FIELD CARRIES ITS UNIT IN ITS NAME AND THE UNITS ARE NOT UNIFORM,
    BECAUSE THE SOURCES ARE NOT.** ``RiskLimits.max_position_pct`` is a FRACTION
    (0.20) and ``StrategyRegistry.allocation_pct`` is a PERCENT (25). A policy
    that silently assumed one of those would be wrong by 100x in the permissive
    direction on whichever it got wrong, so the suffix is load-bearing:
    ``_fraction`` means 0..1, ``_pct`` means 0..100, ``_usd`` means dollars.
    **r2 ENFORCES those units** through ``_number`` instead of stating them.

      engine_entries_enabled       — the arming flag; anything but True is manual
      execution_venue_kind         — the RESOLVED ``mode.VenueKind`` VALUE
      execution_venue_real_money   — the mode spec's own real_money flag
      strategy                     — {strategy_id, state, archived, assets}
      strategy_allocation_pct      — the strategy's envelope, PERCENT of NAV
      live_sessions                — session rows, or None when unreadable
      pending_approved             — in-flight orders, or None when unreadable
      signal_raised_at             — ISO-8601 UTC, when the engine raised it
      nav_usd                      — last STRUCK NAV, > 0
      order_mark_usd               — the mark this order is priced at, > 0
      mark_move_vs_strike_pct      — |order mark / last struck mark - 1| x 100
      day_auto_notional_usd        — auto-approved entry notional already today
      book_qty_signed              — the FUND's signed position in this symbol
      strategy_qty_signed          — THIS STRATEGY's signed position in it
      venue_qty_signed             — the broker's, or None
      venue_readable               — did the broker round trip succeed AT ALL
      strategy_exposure_usd        — this strategy's gross exposure, before
      gross_exposure_usd           — the fund's gross exposure, before
      mandate_gross_fraction       — gross the mandate permits, FRACTION of NAV
      throttle_multiplier          — regime throttle, FRACTION, or None
      throttle_measurable          — whether the regime could be read AT ALL
      max_position_fraction        — the risk limit in force, FRACTION of NAV
      committed_exit               — {set_at, live} for (strategy, symbol), or None

    **``notional_usd`` IS NO LONGER AN INPUT.** r1 accepted it beside the
    quantity and the mark that determine it, which is two ideas of one number
    in a module whose header warns against exactly that — and r1 approved an
    order carrying ``qty=1.18, mark=80, notional_usd=0``. r2 computes it as
    ``|qty| x mark``. A gatherer that still supplies the key is ignored, which
    is the safe direction: the computed figure cannot be talked down.

    A missing context, or any missing field, fails the corresponding check. The
    gatherer can only ever narrow this envelope by breaking, never widen it.
    """
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: Any, detail: str) -> None:
        # ``ok`` is coerced to a strict bool HERE and nowhere else: a check that
        # recorded ``None`` would be counted by ``all(... is True)`` as a
        # failure anyway, but the payload would carry a third value the audit's
        # own tooling has to learn. One place, one coercion.
        checks.append({"check": name, "ok": ok is True, "detail": detail})

    try:
        _evaluate_into(checks, check, order, halted, heartbeats,
                       signal_age_minutes, context)
        check("evaluate_completed", True,
              "every check above was evaluated")
    except Exception as e:  # noqa: BLE001 — a verdict for every input, always
        # LOUD AND REFUSING, NEVER SWALLOWED. The partial check list is kept:
        # whatever was evaluated before the fault is exactly what the
        # riskofficer needs to find where it happened.
        check("evaluate_completed", False,
              f"the envelope raised {type(e).__name__}: {e} — an order whose "
              f"evaluation did not finish is refused, and this check exists so "
              f"the failure is a REFUSAL on the record rather than an exception "
              f"that aborts the tick and leaves every later order unevaluated")

    approve = all(c["ok"] is True for c in checks)
    return {
        "policy_version": AUTOPOLICY_V5_DRAFT_VERSION,
        # SAYS SO ON EVERY SINGLE EVALUATION. If this module is ever wired by
        # accident, every record it writes carries the word DRAFT and the
        # riskofficer's first audit finds it in one query.
        "draft": True,
        "wired": False,
        "class": "engine_entry",
        "approve": approve,
        "checks": checks,
        "failed": [c["check"] for c in checks if c["ok"] is not True],
        "note": ("every proposed v5 check passed — this order would be inside "
                 "the engine-entry envelope IF v5 were ever adopted; nothing "
                 "here approves anything" if approve else
                 "outside the proposed engine-entry envelope — waits for the "
                 "CEO like any other order"),
    }


def _evaluate_into(checks: list[dict[str, Any]], check: Any, order: Any,
                   halted: bool, heartbeats: Any, signal_age_minutes: Any,
                   context: Optional[dict[str, Any]]) -> None:
    """The body of ``evaluate``, split out so the outer guard is one line.

    Split rather than nested because a 250-line ``try`` is a try nobody can
    read the extent of, and because the guard must wrap EVERY check rather
    than the ones somebody remembered to indent.
    """
    ctx = context if isinstance(context, dict) else {}
    ord_ = order if isinstance(order, dict) else {}
    beats = heartbeats if isinstance(heartbeats, dict) else {}

    # --- 1. the kill switch, first and read every time ----------------------
    armed = ctx.get("engine_entries_enabled")
    check("engine_entries_armed", armed is True,
          "engine entries are ARMED" if armed is True else
          f"engine entries are not armed (flag={armed!r}) — every order in this "
          f"class goes to the CEO queue, which is what flipping it off is for")

    # --- 2. THE CONTEXT ITSELF, before anything is computed from it ----------
    #
    # ONE CHECK, ONE SENTENCE, EVERY OFFENDING FIELD NAMED. Each malformed value
    # ALSO becomes ABSENT below, so its own check fails independently — two
    # refusals for one cause, on purpose. This one exists because "the order
    # notional could not be computed" does not tell the riskofficer that the
    # gatherer handed a boolean where a fraction belongs, and that is the
    # sentence that gets the defect fixed.
    malformed: list[str] = []

    def num(key: str, *, lo: Optional[float] = None,
            hi: Optional[float] = None) -> Optional[float]:
        """Read a context number, record it if it is outside its own unit."""
        raw = ctx.get(key)
        out = _number(raw, lo=lo, hi=hi)
        if out is None and raw is not None:
            malformed.append(f"{key}={raw!r}")
        return out

    if not isinstance(context, dict) and context is not None:
        malformed.append(f"context is a {type(context).__name__}")
    if not isinstance(order, dict):
        malformed.append(f"order is a {type(order).__name__}")
    if heartbeats is not None and not isinstance(heartbeats, dict):
        malformed.append(f"heartbeats is a {type(heartbeats).__name__}")

    nav = num("nav_usd", lo=POSITION_EPS, hi=MAX_PLAUSIBLE_NAV_USD)
    mark = num("order_mark_usd", lo=POSITION_EPS)
    day_so_far = num("day_auto_notional_usd", lo=0.0)
    move = num("mark_move_vs_strike_pct")
    name_fraction = num("max_position_fraction", lo=0.0, hi=1.0)
    alloc_pct = num("strategy_allocation_pct", lo=0.0, hi=100.0)
    mandate = num("mandate_gross_fraction", lo=0.0, hi=1.0)
    # 0..1 because ``throttle.target_gross`` is REDUCTION ONLY and says so in
    # its own note: the multiplier is ``1.0 - reduction`` and can never exceed
    # 1.0. A multiplier above one would be the regime feed authorising MORE
    # gross than the mandate, which nothing in this fund may do.
    mult = num("throttle_multiplier", lo=0.0, hi=1.0)
    book = num("book_qty_signed")
    strat_qty = num("strategy_qty_signed")
    vqty = num("venue_qty_signed")
    strat_gross_before = num("strategy_exposure_usd", lo=0.0)
    gross_before = num("gross_exposure_usd", lo=0.0)

    raw_qty = ord_.get("qty")
    qty = _number(raw_qty, lo=POSITION_EPS)
    if qty is None and raw_qty is not None:
        malformed.append(f"order.qty={raw_qty!r}")

    check("context_values_in_range", not malformed,
          "every context value is a number inside the unit its name declares"
          if not malformed else
          "these context values are not numbers in their declared unit and are "
          "treated as ABSENT: " + "; ".join(sorted(malformed)) +
          " — a fraction is 0..1, a percent is 0..100, a dollar figure and a "
          "quantity are finite and positive, and a boolean is not a number "
          "however willingly float() converts it")

    symbol = ord_.get("symbol")
    # ``order_delta`` reads the ORIGINAL quantity so it stays pinned to v4's
    # copy; the range-checked ``qty`` is what everything else uses, and
    # ``side_is_readable`` refuses when they disagree about readability.
    delta = order_delta(ord_)
    if qty is None:
        delta = None
    elif delta is not None:
        # Re-derive from the validated quantity so a negative or boolean qty
        # cannot reach the arithmetic through ``abs()``.
        delta = qty if delta > 0 else -qty

    # --- 3. the venue, TWICE, from two independent fields --------------------
    #
    # Two checks for one condition, deliberately, and only here. Everywhere else
    # in this fund a second opinion is a defect; on the one boundary where being
    # wrong costs REAL MONEY it is the cheapest insurance available — the kind
    # and the real-money flag come from different fields of the mode spec, so a
    # gatherer that gets one wrong has to get the other wrong the same way.
    kind = str(ctx.get("execution_venue_kind") or "").lower()
    check("venue_kind_is_permitted", kind == PERMITTED_VENUE_KIND,
          f"resolved venue kind is {kind!r} against a permitted "
          f"{PERMITTED_VENUE_KIND!r}" +
          ("" if kind == PERMITTED_VENUE_KIND else
           " — the KIND, not the connector name: alpaca-paper and alpaca-prod "
           "both permit the connector 'alpaca', so a name check passes under "
           "real money. order['venue'] is never read here at all"))
    real_money = ctx.get("execution_venue_real_money")
    check("venue_is_not_real_money", real_money is False,
          f"the resolved venue reports real_money={real_money!r}" +
          ("" if real_money is False else
           " — anything but an explicit False refuses; an unreadable venue is "
           "not a paper one"))

    # --- 4. the strategy is real, deployed and not archived ------------------
    #
    # NORMALISED TO A DICT FIRST. r1 called ``.get`` on whatever arrived and
    # nine of the seventeen exceptions came from here.
    raw_strat = ctx.get("strategy")
    strat = raw_strat if isinstance(raw_strat, dict) else {}
    strat_readable = isinstance(raw_strat, dict)
    state = str(strat.get("state") or "")
    archived = strat.get("archived")
    deployed = (strat_readable and bool(strat) and state == "deployed"
                and archived is False)
    check("strategy_deployed", deployed,
          (f"strategy state={state!r} archived={archived!r}" if strat_readable
           else f"the strategy row is a {type(raw_strat).__name__}, not a "
                f"registry row") +
          ("" if deployed else " — only a DEPLOYED, unarchived strategy may "
                              "have its entries taken unattended; absent or "
                              "unreadable is neither"))

    # --- 5. the symbol is inside the strategy's declared scope ---------------
    assets = strat.get("assets")
    if not isinstance(assets, (list, tuple, set)) or not assets:
        # AN EMPTY SCOPE IS NOT "EVERYTHING", AND THIS IS MEASURED RATHER THAN
        # HYPOTHETICAL: on 2026-08-27 the live registry held GLD with
        # ``assets: []`` and only ``definition.symbol``, beside HYG with
        # ``assets: ["HYG"]``. A policy that read the empty list as "no
        # restriction" would have given the least-specified strategy the widest
        # mandate — the inversion this fund's absence rules exist to prevent.
        check("symbol_in_scoped_assets", False,
              f"strategy declares no asset scope ({assets!r}) — an empty scope "
              f"is an unstated one, not an unlimited one")
    else:
        inside = str(symbol or "").strip().upper() in {
            str(a).strip().upper() for a in assets}
        check("symbol_in_scoped_assets", inside,
              f"{symbol!r} against scope {sorted(str(a) for a in assets)}" +
              ("" if inside else " — a deployed strategy trading outside its "
                                 "declared universe is the case a human reads"))

    # --- 6. PROVENANCE: a LIVE session actually raised this ------------------
    #
    # v4's hardest-won lesson, applied to the new class. The marker string was
    # forgeable and only the EXIT_RULE_TRIGGERED event was provenance; here the
    # equivalent of a marker is the actor prefix `external:`, which anything
    # holding the signal token can write. The nearest thing to provenance is a
    # session row that (a) belongs to this strategy and (b) was already running
    # when the signal was raised — a LEAN container starts FLAT, so a signal
    # predating the session moved a book that no longer exists.
    #
    # THE RESIDUAL, NAMED: the token is a BEARER CREDENTIAL. Anything that holds
    # it can raise a signal that matches a genuinely live session, and this
    # check cannot tell that from the session itself. What it DOES close is the
    # much larger hole of a signal with no live session behind it at all. Per-
    # session tokens would close the rest and are not proposed here because
    # rotating them is an operational design, not a policy check.
    raw_sessions = ctx.get("live_sessions")
    # A LIST OR A TUPLE, NOTHING ELSE. r1 accepted anything and eight of the
    # seventeen exceptions came from iterating a float or calling ``len`` on an
    # int. A string is iterable and a dict is iterable, and neither is a
    # session list — accepting either would fold a session table out of
    # characters or keys.
    sessions = (raw_sessions if isinstance(raw_sessions, (list, tuple))
                else None)
    raised = str(ctx.get("signal_raised_at") or "").strip()
    # THE STRATEGY THE ROW DESCRIBES MUST BE THE STRATEGY THE ORDER NAMES.
    # Without this, a gatherer that fetched the wrong registry row would have
    # checks 4, 5, 6 and the allocation bound all evaluating strategy A while
    # the order moved strategy B's book — every check passing, about the wrong
    # strategy. The gatherer does not exist yet, which is exactly when to write
    # the check that bounds its mistakes.
    row_sid = str(strat.get("strategy_id") or "").strip()
    order_sid = str(ord_.get("strategy_id") or "").strip()
    check("strategy_matches_the_order",
          bool(row_sid) and bool(order_sid) and row_sid == order_sid,
          f"the strategy row describes {row_sid!r} and the order names "
          f"{order_sid!r}" +
          ("" if row_sid and order_sid and row_sid == order_sid else
           " — every strategy-scoped check below would otherwise be answered "
           "about a strategy this order does not belong to"))
    sid = row_sid or order_sid
    if sessions is None:
        check("signal_from_live_session", False,
              (f"the live-session registry is a {type(raw_sessions).__name__} "
               f"rather than a list of sessions"
               if raw_sessions is not None else
               "the live-session registry could not be read") +
              " — an unreadable registry proves no engine, and unproven "
              "provenance does not self-execute")
    elif not raised:
        check("signal_from_live_session", False,
              "the signal carries no readable raised_at, so it cannot be placed "
              "against any session's start")
    else:
        claim = _claiming_session(sessions, sid, raised)
        check("signal_from_live_session", claim is not None,
              f"session {claim.get('session_id')!r} for strategy {sid!r} was "
              f"running at {raised}" if claim else
              f"no live session for strategy {sid!r} was running at {raised} "
              f"— of {len(sessions)} session(s) on record, none accounts for "
              f"this signal")

    # --- 7. freshness --------------------------------------------------------
    #
    # ``lo=0.0``: A NEGATIVE AGE IS A SIGNAL FROM THE FUTURE, and r1's
    # ``age <= 5.0`` accepted one. Found while writing r2's own never-raises
    # table, not by the review — a clock skew or a gatherer subtracting the
    # wrong way round would have bought an arbitrarily stale signal a pass on
    # the exact check that exists to stop that.
    age = _number(signal_age_minutes, lo=0.0)
    if age is None:
        check("signal_fresh", False,
              "signal age UNKNOWN — unknown is not fresh; fails closed")
    else:
        check("signal_fresh", age <= MAX_SIGNAL_AGE_MINUTES,
              f"raised {age:.1f} min ago against a {MAX_SIGNAL_AGE_MINUTES:.0f}"
              f"-min ceiling" +
              ("" if age <= MAX_SIGNAL_AGE_MINUTES else
               " — an entry has no deadline, so a stale one waits for the next "
               "bar rather than executing on an old mark"))

    # --- 8. the side is one of the two we understand -------------------------
    side = str(ord_.get("side") or "").lower()
    check("side_is_readable", side in ("buy", "sell") and delta is not None,
          f"side={side!r} qty={raw_qty!r} delta={delta!r}" +
          ("" if delta is not None else
           " — an order whose effect on the book cannot be computed cannot be "
           "bounded by anything below; a quantity must be a finite positive "
           "number, and the SIDE decides the sign"))

    # --- 9. per-order notional, COMPUTED rather than accepted ----------------
    #
    # r1 read ``notional_usd`` from the context beside the ``qty`` and
    # ``order_mark_usd`` that determine it, and approved an order declaring
    # ``notional_usd = 0`` for 1.18 shares at $80. Two ideas of one number is
    # the defect this module's own header warns about; the fix is to keep one.
    notional = None if (qty is None or mark is None) else abs(qty) * mark
    order_pct = _pct_of(notional, nav)
    check("order_notional_within_cap",
          within(order_pct, MAX_ENGINE_ORDER_NOTIONAL_PCT),
          _cap_detail("order notional", order_pct,
                      MAX_ENGINE_ORDER_NOTIONAL_PCT, notional, nav))

    # --- 10. THE DAILY CAP: worst-case daily damage, chosen ------------------
    if day_so_far is None:
        # An unreadable day is not an empty one. Reading a failed history query
        # as "nothing yet today" is the absence-is-zero error, and it lands on
        # precisely the number that bounds the worst day.
        check("daily_cumulative_within_cap", False,
              "today's auto-approved notional could not be read — an unreadable "
              "day is not an empty day, and this is the one number that bounds "
              "what a bad day costs")
    else:
        day_usd = None if notional is None else notional + day_so_far
        day_pct = _pct_of(day_usd, nav)
        check("daily_cumulative_within_cap",
              within(day_pct, MAX_ENGINE_DAILY_NOTIONAL_PCT),
              _cap_detail("today's cumulative auto notional including this "
                          "order", day_pct, MAX_ENGINE_DAILY_NOTIONAL_PCT,
                          day_usd, nav))

    # --- 11. THE IN-FLIGHT LEDGER -------------------------------------------
    #
    # THE FIX FOR THE KILL. One fold, one input, and its readability and
    # freshness are two checks rather than a flag patched onto an exposure
    # sentence — the audit needs to know WHICH of the two failed, because the
    # first is a broken query and the second is a broken venue.
    flight = in_flight(ctx.get("pending_approved"), symbol, sid)
    check("in_flight_ledger_readable", flight["readable"],
          (f"{flight['rows']} approved order(s) still in flight" +
           (" — none" if flight["rows"] == 0 else ""))
          if flight["readable"] else
          f"{flight['reason']} — every exposure bound below is computed from "
          f"the book PLUS what this envelope has already authorised and not "
          f"yet seen the end of, so an unreadable in-flight ledger makes all "
          f"of them arithmetic on a set nobody counted")
    if not flight["readable"]:
        check("in_flight_orders_fresh", False,
              "the in-flight ledger could not be read, so how old its oldest "
              "order is cannot be known either — unknown is not fresh")
    else:
        oldest = flight["oldest_age_minutes"]
        check("in_flight_orders_fresh", flight["fresh"],
              f"oldest in-flight order is "
              f"{'unmeasurable' if oldest is None else format(oldest, '.1f') + ' min'}"
              f" old against a {MAX_PENDING_AGE_MINUTES:.0f}-min ceiling" +
              ("" if flight["fresh"] else
               f" — {flight['stale_rows']} order(s) have gone that long without "
               f"a fill, a cancel or a rejection, which means the ledger has "
               f"stopped agreeing with the venue; the direction we CANNOT see "
               f"from here is an in-flight order it has lost altogether, and "
               f"that one is the permissive one"))

    # --- 12. REDUCE-ONLY: the book may not end up short ----------------------
    #
    # THE SECOND KILL. ``exitrule.py:326`` can only raise a SELL, so a short
    # position's own committed exit DEEPENS it — the pre-commitment check below
    # is satisfied by a rule that makes the position worse. Until a cover path
    # exists (control-layer work, not this draft's), a position this envelope
    # opens must be one the fund's own exit machinery can close.
    #
    # THE BOUND IS THE WORST IN-FLIGHT CORNER, not the netted one: every
    # pending buy fails, every pending sell fills. Two sells that each take a
    # long to exactly zero take it to twice negative together.
    # THE FILLED BOOK IS ANSWERED FIRST AND ON ITS OWN. An unreadable in-flight
    # ledger refuses this check too, and if that were the ONLY sentence it
    # could produce, an order that goes short on the settled book alone would
    # be reported as "could not be bounded" — a defect described as a gap. The
    # two facts get two sentences, and the definite one wins.
    book_only = post_fill_position(book, delta)
    worst_short = worst_short_position(book, flight["symbol_sell_qty"], delta)
    pre = 0.0 if book is None else book
    if book_only is not None and book_only < -POSITION_EPS:
        check("post_fill_position_not_short", False,
              f"post-fill position in {symbol} is {book_only:.6f} on the "
              f"SETTLED book alone — SHORT, with nothing in flight needed to "
              f"make it so. This envelope is reduce-only on the sell side: the "
              f"fund's exit machinery can only SELL, so a short's own committed "
              f"exit DEEPENS it and the position has no way out. This order is "
              + ("crossing zero from a long" if pre > POSITION_EPS else
                 "opening a short from a flat book" if abs(pre) <= POSITION_EPS
                 else "deepening a position that is already short") + ".")
    elif worst_short is None:
        check("post_fill_position_not_short", False,
              f"the post-fill position in {symbol} could not be bounded "
              f"(book={ctx.get('book_qty_signed')!r}, delta={delta!r}, "
              f"in-flight sells={flight['symbol_sell_qty']!r}) — the settled "
              f"book alone does not go short, but an unbounded number of "
              f"unseen in-flight sells could take it there")
    else:
        ok = worst_short >= -POSITION_EPS
        check("post_fill_position_not_short", ok,
              f"worst-case post-fill position in {symbol} is {worst_short:.6f} "
              f"(book {pre:.6f}, in-flight sells "
              f"{flight['symbol_sell_qty']:.6f}, this order {delta:.6f})"
              if ok else
              f"worst-case post-fill position in {symbol} is {worst_short:.6f} "
              f"— SHORT once every in-flight SELL fills and every in-flight BUY "
              f"does not, which is the corner that decides this. The fund's "
              f"exit machinery can only SELL, so a short has no way out; "
              f"{flight['symbol_sell_qty']:.6f} is already in flight against a "
              f"book of {pre:.6f} and this order adds {delta:.6f}.")

    # --- 13. post-fill concentration in the name -----------------------------
    #
    # EVERY EXPOSURE BOUND BELOW IS COMPUTED FROM ONE PAIR OF NUMBERS — the
    # symbol's value before the fill and after it — through ONE helper, with the
    # in-flight set entering through ONE fold. Three additions in three checks
    # is how two of them end up disagreeing about the same book, which is the
    # defect this fund has already paid for twice.
    worst_book = worst_abs_position(book, flight["symbol_buy_qty"],
                                    flight["symbol_sell_qty"], delta)
    book_before_usd = _usd(book, mark)
    book_after_usd = _usd(worst_book, mark)
    name_ceiling_pct = None if name_fraction is None else name_fraction * 100.0
    check("post_fill_name_within_concentration",
          within(_pct_of(book_after_usd, nav), name_ceiling_pct),
          _cap_detail(f"worst-case post-fill position in {symbol} "
                      f"(book + everything in flight)",
                      _pct_of(book_after_usd, nav), name_ceiling_pct,
                      book_after_usd, nav))

    # --- 14. post-fill exposure against the strategy's own allocation --------
    worst_strat = worst_abs_position(strat_qty, flight["strategy_buy_qty"],
                                     flight["strategy_sell_qty"], delta)
    strat_after = post_fill_exposure(
        strat_gross_before, _usd(strat_qty, mark), _usd(worst_strat, mark),
        flight["strategy_other_gross_usd"])
    check("post_fill_strategy_within_allocation",
          within(_pct_of(strat_after, nav), alloc_pct),
          _cap_detail("worst-case post-fill strategy exposure",
                      _pct_of(strat_after, nav), alloc_pct, strat_after, nav))

    # --- 15. post-fill gross against the throttle ----------------------------
    #
    # THE UNMEASURABLE REGIME IS THE TRAP HERE AND IT POINTS THE PERMISSIVE WAY.
    # `throttle.target_gross` returns `gross_multiplier: 1.0` when NEITHER
    # signal is measurable — correct for that module, whose doctrine is
    # "reduction only", and exactly wrong to read here: it would let an
    # unreadable regime feed authorise FULL gross unattended. So an unmeasurable
    # throttle refuses. The cost is real and is stated: the auto-entry path dies
    # whenever the regime feed is down, and a human clicks instead.
    measurable = ctx.get("throttle_measurable")
    gross_after = post_fill_exposure(gross_before, book_before_usd,
                                     book_after_usd, flight["other_gross_usd"])
    if measurable is not True or mult is None or mandate is None:
        check("post_fill_gross_within_throttle", False,
              f"the regime throttle could not be measured (measurable="
              f"{measurable!r}, multiplier={ctx.get('throttle_multiplier')!r}, "
              f"mandate ceiling={ctx.get('mandate_gross_fraction')!r}) — an "
              f"unmeasurable regime reads as FULL gross in the throttle's own "
              f"output, and a policy that self-executes on that has read "
              f"absence as permission")
    else:
        ceiling_pct = mandate * mult * 100.0
        check("post_fill_gross_within_throttle",
              within(_pct_of(gross_after, nav), ceiling_pct),
              _cap_detail("worst-case post-fill gross",
                          _pct_of(gross_after, nav),
                          ceiling_pct, gross_after, nav) +
              f" (mandate {mandate:.2f} x throttle {mult:.2f})")

    # --- 16. the exposure ledgers are internally coherent --------------------
    #
    # A NECESSARY CONDITION, NOT A RECONCILIATION. Gross exposure includes this
    # symbol, so it cannot be smaller than this symbol's own absolute value —
    # and r1 approved a context declaring a strategy short one share at $80
    # with a strategy exposure of $0, which made the allocation bound arithmetic
    # on a ledger that contradicted itself. It cannot prove the exposures are
    # RIGHT; it refuses the ones that are provably wrong, which is all a
    # deterministic check on someone else's fold can honestly claim.
    legs = []
    if gross_before is not None and book_before_usd is not None:
        legs.append(("fund gross", gross_before, abs(book_before_usd)))
    if strat_gross_before is not None and strat_qty is not None and mark is not None:
        legs.append(("strategy gross", strat_gross_before,
                     abs(strat_qty * mark)))
    bad = [(w, t, m) for (w, t, m) in legs if t + POSITION_EPS < m]
    coherent = bool(legs) and not bad and len(legs) == 2
    check("exposure_ledgers_coherent", coherent,
          "fund and strategy gross each cover this symbol's own value"
          if coherent else
          ("; ".join(f"{w} is ${t:,.2f} but {symbol} alone is worth ${m:,.2f}"
                     for (w, t, m) in bad) +
           " — an exposure smaller than one of its own positions is a fold that "
           "contradicts itself, and every bound above divides by it"
           if bad else
           "the exposure ledgers could not both be read, so their coherence is "
           "UNKNOWN rather than fine"))

    # --- 17. the mark itself, corroborated -----------------------------------
    if move is None:
        check("mark_corroborated", False,
              f"the order's mark could not be compared to the fund's last "
              f"struck mark (move={ctx.get('mark_move_vs_strike_pct')!r}) — an "
              f"uncorroboratable number does not self-execute")
    else:
        # ABSOLUTE VALUE. r1 compared the signed figure, so a mark reported as
        # -75.9% of the struck mark satisfied ``<= 30``. The field's own name
        # says it is already a magnitude; taking it again costs nothing and
        # removes the gatherer's ability to be wrong about it in the one
        # direction that matters.
        ok = abs(move) <= MAX_MARK_MOVE_VS_STRIKE_PCT
        check("mark_corroborated", ok,
              f"mark is {abs(move):.1f}% from the last struck mark against a "
              f"{MAX_MARK_MOVE_VS_STRIKE_PCT:.0f}% bound" +
              ("" if ok else " — the magnitude is what is bounded; a mark far "
                             "BELOW the struck one is the phantom-price shape"))

    # --- 18. the two ledgers agree about what we already hold ----------------
    #
    # IN-FLIGHT ORDERS ARE EXCLUDED HERE, DELIBERATELY AND BY CONSTRUCTION.
    # The broker cannot hold an unfilled order, so adding in-flight quantity to
    # the book side would make every pending order look like a reconciliation
    # break — the adversary probed exactly that naive fix and it refuses every
    # order, which is not a control. The in-flight set is bounded above, where
    # it belongs; this check compares two ledgers of what has actually settled.
    readable = ctx.get("venue_readable")
    if book is None or readable is not True or vqty is None:
        check("book_venue_in_sync", False,
              f"book={ctx.get('book_qty_signed')!r} against "
              f"venue={ctx.get('venue_qty_signed')!r} (venue readable="
              f"{readable!r}) — every bound above is computed from the position "
              f"BEFORE the fill, so a book the venue does not confirm makes all "
              f"of them arithmetic on a number nobody verified")
    else:
        drift = abs(book - vqty)
        check("book_venue_in_sync", drift <= MAX_POSITION_DRIFT_QTY,
              f"book holds {book} {symbol} against {vqty} at the venue — drift "
              f"{drift:.9f} against a {MAX_POSITION_DRIFT_QTY:g} tolerance "
              f"(orders in flight are excluded from BOTH sides: the broker "
              f"cannot hold an unfilled order)")

    # --- 19. THE WAY OUT, COMMITTED BEFORE THE WAY IN ------------------------
    #
    # An entry without a standing risk exit is the trade that turns a bad
    # position into a bad fund, and it is the one v4 never had to think about
    # because v4 only ever closed. The rule must be LIVE and must have been
    # committed BEFORE this order: an exit written after the fill is not
    # pre-commitment, it is regret with a timestamp.
    exit_rule = ctx.get("committed_exit")
    if not isinstance(exit_rule, dict):
        check("exit_committed_for_entry", False,
              f"no pre-committed risk exit stands for {symbol} under this "
              f"strategy — an entry with no committed way out fails closed")
    else:
        set_at = str(exit_rule.get("set_at") or "").strip()
        live = exit_rule.get("live")
        # STRICTLY BEFORE, ON PARSED INSTANTS. ``<=`` would let an exit written
        # in the same instant as the signal count as pre-commitment, and the
        # whole content of the word "pre" is that ordering.
        #
        # r1 COMPARED THE STRINGS, which is a false ACCEPT and not merely a
        # sloppy one: ``"2026-08-28T05:00:00+00:00" < "2026-08-28T06:00:00+05:00"``
        # is True as text and False as time (05:00Z is four hours AFTER 01:00Z),
        # so an exit committed four hours after the signal counted as
        # pre-commitment. A naive instant beside an aware one raises inside
        # ``datetime`` and lands on False, which is the refusing direction.
        raised_ok = bool(set_at) and bool(raised) and _iso_lt(set_at, raised)
        ok = live is True and raised_ok
        check("exit_committed_for_entry", ok,
              f"exit set_at={set_at!r} live={live!r} against a signal raised "
              f"{raised!r}" +
              ("" if ok else " — the exit must be LIVE and must predate the "
                             "order it protects, compared as INSTANTS: an "
                             "unparseable timestamp on either side proves no "
                             "ordering and refuses"))

    # --- 20. the controls are alive ------------------------------------------
    check("not_halted", not halted,
          "kill switch engaged — nothing executes" if halted else
          "trading not halted")

    for job in REQUIRED_HEARTBEATS:
        row = beats.get(job)
        row = row if isinstance(row, dict) else {}
        ok = row.get("ok")
        # ok is True / False / None(unobserved). Only True passes: a fund that
        # cannot prove its controls are alive does not self-execute, and
        # "unobserved" is the value heartbeat.status returns for a job that has
        # never run in this process — which is neither broken nor fine.
        check(f"liveness_{job}", ok is True,
              f"{job}: ok={ok} age={row.get('age_seconds')}s")

    rm_row = beats.get("risk_monitor")
    rm_age = _number((rm_row if isinstance(rm_row, dict) else {})
                     .get("age_seconds"), lo=0.0)
    if rm_age is None:
        check("risk_monitor_fresh", False,
              "the risk monitor's heartbeat age could not be read — "
              "unmeasurable is not recent")
    else:
        check("risk_monitor_fresh", rm_age <= MAX_RISK_MONITOR_AGE_SECONDS,
              f"risk monitor beat {rm_age:.0f}s ago against this envelope's own "
              f"{MAX_RISK_MONITOR_AGE_SECONDS:.0f}s requirement")


def _claiming_session(sessions: Any, strategy_id: str,
                      raised_at: str) -> Optional[dict[str, Any]]:
    """The live session that could have raised this, or ``None``.

    STRICTER THAN THE ENGINE FENCE'S VERSION OF THE SAME QUESTION, and the
    difference is the direction each one serves. ``engineledger._claiming_session``
    is deliberately GENEROUS — a false claim there costs a divergence a human
    dismisses, a false refusal there silently fences a live divergence. Here the
    costs are reversed: a false claim EXECUTES AN ORDER. So this one requires
    the strategy to match explicitly, refuses a session that names no strategy,
    and refuses an unparseable timestamp on either side.
    """
    for s in sessions or ():
        if not isinstance(s, dict):
            continue
        if str(s.get("state") or "") not in ("starting", "running"):
            continue
        s_sid = str(s.get("strategy_id") or "").strip()
        if not s_sid or not strategy_id or s_sid != strategy_id:
            continue
        started = str(s.get("started_at") or "").strip()
        if not started or not _iso_le(started, raised_at):
            continue
        return s
    return None


def _iso_le(a: str, b: str) -> bool:
    """``a`` is at or before ``b``; ``False`` when either cannot be parsed.

    Mixed naive/aware comparison raises ``TypeError`` in ``datetime`` and lands
    here on ``False``, which is the refusing direction — the OPPOSITE of the
    engine fence's use of the same primitive, where ``False`` means "did not
    predate" and keeps a signal LIVE. Same arithmetic, opposite safe answer,
    which is exactly why it is written out here instead of imported.
    """
    from datetime import datetime
    try:
        return datetime.fromisoformat(a) <= datetime.fromisoformat(b)
    except (TypeError, ValueError):
        return False


def _iso_lt(a: str, b: str) -> bool:
    """``a`` is STRICTLY before ``b``; ``False`` when either cannot be parsed.

    A SECOND FUNCTION RATHER THAN A FLAG, because the two callers need opposite
    boundary behaviour and a boolean argument at the call site is how the wrong
    one gets chosen. ``_iso_le`` answers "was the session already running when
    the signal was raised", where equality is a YES — a container that starts
    and signals in the same instant genuinely raised it. This one answers "was
    the exit committed BEFORE the signal", where equality is a NO, because the
    whole content of the word "pre" is that ordering and sub-second timestamps
    make equality rare rather than impossible.
    """
    from datetime import datetime
    try:
        return datetime.fromisoformat(a) < datetime.fromisoformat(b)
    except (TypeError, ValueError):
        return False


def _pct_of(value: Optional[float], nav: Optional[float]) -> Optional[float]:
    """``value`` as a percent of NAV, or ABSENT.

    A NAV of zero returns ABSENT rather than infinity or zero. A fund with no
    struck NAV has no percentage to be inside, and both of the numeric answers
    would be a lie with a different sign.
    """
    if value is None or nav is None or abs(nav) <= POSITION_EPS:
        return None
    return float(value) / float(nav) * 100.0


def _cap_detail(what: str, pct: Optional[float], ceiling: Optional[float],
                usd: Optional[float], nav: Optional[float]) -> str:
    """One sentence per cap, with the unreadable case saying WHICH side was
    unreadable — the audit reads the detail, not the boolean, and "we could not
    measure it" and "it was too big" have completely different fixes."""
    if pct is None or ceiling is None:
        return (f"{what} could not be computed (usd={usd!r}, nav={nav!r}, "
                f"ceiling={ceiling!r}) — an unmeasurable exposure is not a "
                f"permitted one")
    verdict = "inside" if abs(pct) <= ceiling + POSITION_EPS else "OVER"
    return (f"{what} is {pct:.2f}% of NAV against a {ceiling:.2f}% ceiling "
            f"({verdict})")
