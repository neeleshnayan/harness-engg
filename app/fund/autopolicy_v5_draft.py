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

WHAT IT DOES NOT DO, and this is deliberate rather than unfinished:

  * It does not replace v4. v4's exit envelope stands unchanged. An order is
    auto-approvable if it passes EITHER envelope, and this module implements
    only the new one.
  * It never widens anything on its own. Every check below either has no
    counterpart in v4 (it is new) or is strictly at least as tight.
  * It reads nothing. Every input arrives in ``context``, gathered by a caller
    that does not exist yet. That is what keeps it unreachable — and it is also
    how v4 is written, so the shape is the house idiom rather than a dodge.

TWO HELPERS ARE DUPLICATED FROM ``autopolicy.py`` ON PURPOSE — ``_as_float``
and ``order_delta``, and no others. This fund's standing rule is to prove a
value is READ rather than COPIED, and copies are how two modules acquire two
ideas of one thing. The requirement here outranks it exactly once: a draft that
IMPORTS the live policy is a draft the live policy's import graph can reach.
**De-duplicating them is part of the wiring step, and the wiring step is the one
that goes through the chain.** ``tests/test_autopolicy_v5_draft.py`` compares
both against the originals by BEHAVIOUR over a shared table, so the drift is
visible for as long as the copy exists.

THE FIVE ATTACKS THIS DRAFT EXPECTS, ANSWERED IN THE CODE RATHER THAN HERE:

  1. *"engine-raised" is a claim, and claims are forgeable.* v4 learned this
     about ``EXIT_MARKER``: a marker string is wording, an EVENT is provenance.
     ``signal_from_live_session`` is v5's answer — and the residual (the signal
     token is a bearer credential) is named on the payload, not buried.
  2. *An entry has no position to reduce, so v4's whole safety argument is
     gone.* Replaced by four bounds that hold at the moment of the fill:
     per-name concentration, per-strategy allocation, gross against the
     throttle, and a per-order plus per-DAY notional ceiling.
  3. *An entry with no way out is the trade that kills a fund.*
     ``exit_committed_for_entry`` refuses it. An entry whose exit is written
     after the fill is not pre-commitment.
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
#: draft can never be mistaken for one recorded under a governed envelope.
AUTOPOLICY_V5_DRAFT_VERSION = "v5-draft-2026-08-27"

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
MAX_ENGINE_DAILY_NOTIONAL_PCT = 30.0

#: Freshness for the signal that raised the order. Deliberately tighter than
#: v4's 10 minutes for exits, because an ENTRY is discretionary in a way an exit
#: is not: nothing is lost by refusing a stale entry and waiting for the next
#: bar, whereas v4's own comment records that a refused exit does NOT come back.
MAX_SIGNAL_AGE_MINUTES = 5.0

#: Largest disagreement between the mark the order was priced at and the fund's
#: own last struck mark. SAME VALUE AND SAME REASON AS v4's
#: ``MAX_MARK_MOVE_VS_STRIKE_PCT``: two definitions of "the mark is sane" is the
#: second-opinion defect ``marksanity`` was written to name. If v4's moves, this
#: moves with it; the tests pin them together.
MAX_MARK_MOVE_VS_STRIKE_PCT = 30.0

#: Staleness ceiling for the risk monitor's own heartbeat, in seconds. NAMED
#: SEPARATELY from the ``liveness_*`` checks even though it looks redundant: the
#: heartbeat's ``ok`` flag is computed against a budget declared inside
#: ``heartbeat.BUDGETS_SECONDS``, and an envelope that self-executes on the
#: strength of a control being alive should state its OWN requirement rather
#: than inherit whatever that budget happens to be next year.
MAX_RISK_MONITOR_AGE_SECONDS = 300.0

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

#: The only venue an engine entry may execute on. Read from the RESOLVED
#: execution venue, never from ``order["venue"]`` — v4 learned that the hard
#: way: ``exitrule.py`` hardcodes ``"paper"`` on every exit it raises whatever
#: connector will actually execute it, so a check against the order's own field
#: would have passed the exact orders that went to Alpaca.
PERMITTED_VENUE = "alpaca"

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
                       symbol_after_usd: Optional[float]) -> Optional[float]:
    """GROSS exposure after this fill: swap this symbol's contribution out and
    the new one in. ABSENT if any term is.

    Written as a swap rather than as ``total + notional`` because ``+ notional``
    is only right when the order INCREASES a position it is already long. It is
    wrong for a sell that reduces one, wrong for a buy that closes a short, and
    catastrophically wrong for an order that crosses zero — all three of which
    an ENGINE entry can be, and none of which v4 ever had to consider because v4
    only ever closed a long.

    ABSOLUTE VALUES, because gross is what the throttle and the allocation both
    bound: a long and a short of equal size consume the same balance sheet, and
    a signed sum would report the pair as flat.
    """
    if (total_before is None or symbol_before_usd is None
            or symbol_after_usd is None):
        return None
    return (float(total_before) - abs(float(symbol_before_usd))
            + abs(float(symbol_after_usd)))


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


def evaluate(order: dict[str, Any], *, halted: bool,
             heartbeats: dict[str, Any],
             signal_age_minutes: Optional[float],
             context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """One ENGINE ENTRY against the proposed v5 envelope. Deterministic.

    APPROVE only when EVERY check is exactly ``True``. Any check that cannot be
    evaluated fails closed; an absence is never a yes. Non-short-circuiting like
    v4: every check is evaluated and recorded even after an earlier one has
    failed, because that is what made v4's first audit possible from the log
    alone — a policy that stops at the first refusal tells the riskofficer
    nothing about the other eleven.

    ``context`` carries everything read from the world. The gatherer does not
    exist yet, and the fields are named here so it can be written against a
    contract rather than against a guess:

    **EVERY FIELD CARRIES ITS UNIT IN ITS NAME AND THE UNITS ARE NOT UNIFORM,
    BECAUSE THE SOURCES ARE NOT.** ``RiskLimits.max_position_pct`` is a FRACTION
    (0.20) and ``StrategyRegistry.allocation_pct`` is a PERCENT (25). A policy
    that silently assumed one of those would be wrong by 100x in the permissive
    direction on whichever it got wrong, so the suffix is load-bearing:
    ``_fraction`` means 0..1, ``_pct`` means 0..100, ``_usd`` means dollars.

      engine_entries_enabled       — the arming flag; anything but True is manual
      execution_venue              — the RESOLVED venue, from the connector/mode
      strategy                     — {strategy_id, state, archived, assets}
      strategy_allocation_pct      — the strategy's envelope, PERCENT of NAV
      live_sessions                — session rows, or None when unreadable
      signal_raised_at             — ISO-8601 UTC, when the engine raised it
      nav_usd                      — last STRUCK NAV
      order_mark_usd               — the mark this order is priced at
      mark_move_vs_strike_pct      — |order mark / last struck mark - 1| x 100
      notional_usd                 — this order's notional
      day_auto_notional_usd        — auto-approved entry notional already today
      book_qty_signed              — the FUND's signed position in this symbol
      strategy_qty_signed          — THIS STRATEGY's signed position in it
      venue_qty_signed             — the broker's, or None
      venue_readable               — did the broker round trip succeed AT ALL
      strategy_exposure_usd        — this strategy's gross exposure, before
      gross_exposure_usd           — the fund's gross exposure, before
      mandate_gross_fraction       — gross the mandate permits, FRACTION of NAV
      throttle_multiplier          — regime throttle, or None when unmeasurable
      throttle_measurable          — whether the regime could be read AT ALL
      max_position_fraction        — the risk limit in force, FRACTION of NAV
      committed_exit               — {set_at, live} for (strategy, symbol), or None

    A missing context, or any missing field, fails the corresponding check. The
    gatherer can only ever narrow this envelope by breaking, never widen it.
    """
    ctx = context or {}
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: Any, detail: str) -> None:
        # ``ok`` is coerced to a strict bool HERE and nowhere else: a check that
        # recorded ``None`` would be counted by ``all(... is True)`` as a
        # failure anyway, but the payload would carry a third value the audit's
        # own tooling has to learn. One place, one coercion.
        checks.append({"check": name, "ok": ok is True, "detail": detail})

    symbol = order.get("symbol")
    delta = order_delta(order)
    nav = _as_float(ctx.get("nav_usd"))

    # --- 1. the kill switch, first and read every time ----------------------
    armed = ctx.get("engine_entries_enabled")
    check("engine_entries_armed", armed is True,
          "engine entries are ARMED" if armed is True else
          f"engine entries are not armed (flag={armed!r}) — every order in this "
          f"class goes to the CEO queue, which is what flipping it off is for")

    # --- 2. the venue, from the resolved connector and not from the order ----
    venue = str(ctx.get("execution_venue") or "").lower()
    check("venue_is_permitted", venue == PERMITTED_VENUE,
          f"resolved execution venue is {venue!r} against a permitted "
          f"{PERMITTED_VENUE!r}" +
          ("" if venue == PERMITTED_VENUE else
           " — note this is the RESOLVED venue; order['venue'] is a string the "
           "proposer supplies and is never read here"))

    # --- 3. the strategy is real, deployed and not archived ------------------
    strat = ctx.get("strategy") or {}
    state = str(strat.get("state") or "")
    archived = strat.get("archived")
    deployed = bool(strat) and state == "deployed" and archived is False
    check("strategy_deployed", deployed,
          f"strategy state={state!r} archived={archived!r}" +
          ("" if deployed else " — only a DEPLOYED, unarchived strategy may "
                              "have its entries taken unattended; absent or "
                              "unreadable is neither"))

    # --- 4. the symbol is inside the strategy's declared scope ---------------
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

    # --- 5. PROVENANCE: a LIVE session actually raised this ------------------
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
    sessions = ctx.get("live_sessions")
    raised = str(ctx.get("signal_raised_at") or "").strip()
    sid = str(strat.get("strategy_id") or order.get("strategy_id") or "").strip()
    if sessions is None:
        check("signal_from_live_session", False,
              "the live-session registry could not be read — an unreadable "
              "registry proves no engine, and unproven provenance does not "
              "self-execute")
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

    # --- 6. freshness --------------------------------------------------------
    age = _as_float(signal_age_minutes)
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

    # --- 7. the side is one of the two we understand -------------------------
    side = str(order.get("side") or "").lower()
    check("side_is_readable", side in ("buy", "sell") and delta is not None,
          f"side={side!r} qty={order.get('qty')!r} delta={delta!r}" +
          ("" if delta is not None else
           " — an order whose effect on the book cannot be computed cannot be "
           "bounded by anything below"))

    # --- 8. per-order notional ----------------------------------------------
    notional = _as_float(ctx.get("notional_usd"))
    order_pct = _pct_of(notional, nav)
    ok = within(order_pct, MAX_ENGINE_ORDER_NOTIONAL_PCT)
    check("order_notional_within_cap", ok,
          _cap_detail("order notional", order_pct,
                      MAX_ENGINE_ORDER_NOTIONAL_PCT, notional, nav))

    # --- 9. THE DAILY CAP: worst-case daily damage, chosen --------------------
    day_so_far = _as_float(ctx.get("day_auto_notional_usd"))
    if day_so_far is None:
        # An unreadable day is not an empty one. Reading a failed history query
        # as "nothing yet today" is the absence-is-zero error, and it lands on
        # precisely the number that bounds the worst day.
        check("daily_cumulative_within_cap", False,
              "today's auto-approved notional could not be read — an unreadable "
              "day is not an empty day, and this is the one number that bounds "
              "what a bad day costs")
    else:
        day_pct = _pct_of((notional or 0.0) + day_so_far
                          if notional is not None else None, nav)
        ok = within(day_pct, MAX_ENGINE_DAILY_NOTIONAL_PCT)
        check("daily_cumulative_within_cap", ok,
              _cap_detail("today's cumulative auto notional including this "
                          "order", day_pct, MAX_ENGINE_DAILY_NOTIONAL_PCT,
                          None if notional is None else notional + day_so_far,
                          nav))

    # --- 10. post-fill concentration in the name -----------------------------
    #
    # EVERY EXPOSURE BOUND BELOW IS COMPUTED FROM ONE PAIR OF NUMBERS — the
    # symbol's value before the fill and after it — through ONE helper. Three
    # additions in three checks is how two of them end up disagreeing about the
    # same book, which is the defect this fund has already paid for twice.
    book = _as_float(ctx.get("book_qty_signed"))
    mark = _as_float(ctx.get("order_mark_usd"))
    post_book = post_fill_position(book, delta)
    book_before_usd = _usd(book, mark)
    book_after_usd = _usd(post_book, mark)

    name_fraction = _as_float(ctx.get("max_position_fraction"))
    name_ceiling_pct = None if name_fraction is None else name_fraction * 100.0
    ok = within(_pct_of(book_after_usd, nav), name_ceiling_pct)
    check("post_fill_name_within_concentration", ok,
          _cap_detail(f"post-fill position in {symbol}",
                      _pct_of(book_after_usd, nav), name_ceiling_pct,
                      book_after_usd, nav))

    # --- 11. post-fill exposure against the strategy's own allocation --------
    strat_qty = _as_float(ctx.get("strategy_qty_signed"))
    strat_after = post_fill_exposure(
        _as_float(ctx.get("strategy_exposure_usd")),
        _usd(strat_qty, mark),
        _usd(post_fill_position(strat_qty, delta), mark))
    alloc_pct = _as_float(ctx.get("strategy_allocation_pct"))
    ok = within(_pct_of(strat_after, nav), alloc_pct)
    check("post_fill_strategy_within_allocation", ok,
          _cap_detail("post-fill strategy exposure", _pct_of(strat_after, nav),
                      alloc_pct, strat_after, nav))

    # --- 12. post-fill gross against the throttle ----------------------------
    #
    # THE UNMEASURABLE REGIME IS THE TRAP HERE AND IT POINTS THE PERMISSIVE WAY.
    # `throttle.target_gross` returns `gross_multiplier: 1.0` when NEITHER
    # signal is measurable — correct for that module, whose doctrine is
    # "reduction only", and exactly wrong to read here: it would let an
    # unreadable regime feed authorise FULL gross unattended. So an unmeasurable
    # throttle refuses. The cost is real and is stated: the auto-entry path dies
    # whenever the regime feed is down, and a human clicks instead.
    measurable = ctx.get("throttle_measurable")
    mult = _as_float(ctx.get("throttle_multiplier"))
    mandate = _as_float(ctx.get("mandate_gross_fraction"))
    gross_after = post_fill_exposure(_as_float(ctx.get("gross_exposure_usd")),
                                     book_before_usd, book_after_usd)
    if measurable is not True or mult is None or mandate is None:
        check("post_fill_gross_within_throttle", False,
              f"the regime throttle could not be measured (measurable="
              f"{measurable!r}, multiplier={mult!r}, mandate ceiling="
              f"{mandate!r}) — an unmeasurable regime reads as FULL gross in "
              f"the throttle's own output, and a policy that self-executes on "
              f"that has read absence as permission")
    else:
        ceiling_pct = mandate * mult * 100.0
        ok = within(_pct_of(gross_after, nav), ceiling_pct)
        check("post_fill_gross_within_throttle", ok,
              _cap_detail("post-fill gross", _pct_of(gross_after, nav),
                          ceiling_pct, gross_after, nav) +
              f" (mandate {mandate:.2f} x throttle {mult:.2f})")

    # --- 13. the mark itself, corroborated -----------------------------------
    move = _as_float(ctx.get("mark_move_vs_strike_pct"))
    if move is None:
        check("mark_corroborated", False,
              "the order's mark could not be compared to the fund's last struck "
              "mark — an uncorroboratable number does not self-execute")
    else:
        ok = move <= MAX_MARK_MOVE_VS_STRIKE_PCT
        check("mark_corroborated", ok,
              f"mark is {move:.1f}% from the last struck mark against a "
              f"{MAX_MARK_MOVE_VS_STRIKE_PCT:.0f}% bound")

    # --- 14. the two ledgers agree about what we already hold ----------------
    readable = ctx.get("venue_readable")
    vqty = _as_float(ctx.get("venue_qty_signed"))
    if book is None or readable is not True or vqty is None:
        check("book_venue_in_sync", False,
              f"book={book!r} against venue={vqty!r} (venue readable="
              f"{readable!r}) — every bound above is computed from the position "
              f"BEFORE the fill, so a book the venue does not confirm makes all "
              f"of them arithmetic on a number nobody verified")
    else:
        drift = abs(book - vqty)
        ok = drift <= MAX_POSITION_DRIFT_QTY
        check("book_venue_in_sync", ok,
              f"book holds {book} {symbol} against {vqty} at the venue — drift "
              f"{drift:.9f} against a {MAX_POSITION_DRIFT_QTY:g} tolerance")

    # --- 15. THE WAY OUT, COMMITTED BEFORE THE WAY IN ------------------------
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
        raised_ok = bool(set_at) and bool(raised) and set_at < raised
        ok = live is True and raised_ok
        check("exit_committed_for_entry", ok,
              f"exit set_at={set_at!r} live={live!r} against a signal raised "
              f"{raised!r}" +
              ("" if ok else " — the exit must be LIVE and must predate the "
                             "order it protects"))

    # --- 16. the controls are alive ------------------------------------------
    check("not_halted", not halted,
          "kill switch engaged — nothing executes" if halted else
          "trading not halted")

    for job in REQUIRED_HEARTBEATS:
        row = (heartbeats or {}).get(job) or {}
        ok = row.get("ok")
        # ok is True / False / None(unobserved). Only True passes: a fund that
        # cannot prove its controls are alive does not self-execute, and
        # "unobserved" is the value heartbeat.status returns for a job that has
        # never run in this process — which is neither broken nor fine.
        check(f"liveness_{job}", ok is True,
              f"{job}: ok={ok} age={row.get('age_seconds')}s")

    rm_age = _as_float(((heartbeats or {}).get("risk_monitor") or {})
                       .get("age_seconds"))
    if rm_age is None:
        check("risk_monitor_fresh", False,
              "the risk monitor's heartbeat age could not be read — "
              "unmeasurable is not recent")
    else:
        check("risk_monitor_fresh", rm_age <= MAX_RISK_MONITOR_AGE_SECONDS,
              f"risk monitor beat {rm_age:.0f}s ago against this envelope's own "
              f"{MAX_RISK_MONITOR_AGE_SECONDS:.0f}s requirement")

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
