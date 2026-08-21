"""Auto-approval: a deterministic, versioned policy that executes inside an envelope.

THE AMENDMENT THIS IMPLEMENTS (CEO decision, 2026-08-20)

From the fund's first day its deepest invariant was "the machine proposes; the
human clicks." That was scaffolding for the phase in which the fund could not
trust its own controls — and that phase is over by measurement, not by mood: the
kill switches tick with heartbeats, exits fire unattended and are idempotent,
stale proposals expire themselves, and every one of those behaviours has tests
and a live demonstration on the event log.

The CEO's reasoning, recorded: a fund where every order waits for a human click
is not agentic — the human's job in a systematic fund is to govern the POLICY
that approves orders, not to click each order. The venue is Alpaca paper, chosen
deliberately as the hardening ground.

WHY A POLICY IN CODE AND NOT AN AGENT WITH A MOUSE

The per-order decision is deterministic on purpose. An LLM approving individual
orders would be nondeterministic, slow, unauditable, and promptable — four
properties an approval path must not have. So the split is:

  * THIS MODULE decides each order, deterministically, against a versioned
    envelope. Same inputs, same answer, forever.
  * THE RISK OFFICER AGENT supervises the policy: reviews every auto-approval
    after the fact, attacks the envelope, recommends version changes. Judgement
    where it is evaluative, code where it is mechanical.
  * THE HUMANS govern the envelope. It widens only by a versioned change with a
    written reason — the same rule as every threshold here.

ENVELOPE v1 — deliberately the narrowest slice that delivers real agency:

  ONLY exit-rule-triggered SELLs qualify. Closes commanded by a stop the
  operator committed to BEFORE the position existed. Risk-reducing by
  construction, and the exact case where waiting for a human already failed
  live: an INTC take-profit fired, aged 46 hours waiting for a click, and the
  gain it was taking no longer existed by the time anyone looked.

  Buys never qualify in v1. Rebalances never qualify in v1. Anything outside
  the envelope waits for the CEO exactly as before.

Every auto-approval records the FULL check-by-check evaluation in the approval
event payload, so the risk officer audits decisions, not summaries.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: Bumped only with a written reason. An approval made under v1 was made under
#: v1's envelope, and the payload says so forever.
#:
#: v1 -> v2 (2026-08-20, CEO-accepted riskofficer recommendations R1/R3/R4/R7
#: after the policy's first live fire executed on a fabricated mark —
#: docs/AUDIT_AUTOPOLICY_V1_FIRST_FIRE_2026-08-20.md). v1 verified everything
#: about the ORDER and nothing about the NUMBER or the RULE. v2 adds four
#: checks, none loosening, all fail-closed, all derived from the fund's own
#: event log:
#:
#:   * exit_trigger_linked  (R3): the marker string is forgeable free text;
#:     the EXIT_RULE_TRIGGERED event is not — only ExitRules.enforce() writes
#:     it. The order must be named by such an event, not merely worded like one.
#:   * rule_predates_position (R4): v1's stated premise ("a stop committed to
#:     BEFORE the position existed") was false for its first fire — the rule
#:     was set three days after the position opened, by a test harness. Now
#:     tested, not asserted.
#:   * mark_corroborated (R1): the triggering mark must agree with the fund's
#:     own last STRUCK mark within a versioned bound. GLD's true mark sat in
#:     the log 29m46s before the phantom; nothing consulted it.
#:   * notional_within_cap (R7): v1 bounded no size at all. The machine's blast
#:     radius is now an explicitly governed number.
#:
#: R5 (rule's owner strategy must own the position) is NOT in v2 — the CEO has
#: not decided it; the recommendation stays open on run-riskofficer-1.
#:
#: v2 -> v3 (2026-08-20, same day — CEO batch-yes on the COO's founding triage,
#: batch B): adds R5 as `rule_owner_holds_position` — the auto-approved
#: quantity must not exceed what the TRIGGERING RULE'S OWN STRATEGY holds in
#: the symbol, folded from the fill events' strategy_id. This is the check
#: that would have stopped the machinery-test rule liquidating ANOTHER
#: strategy's GLD (audit F2b): the test strategy held zero GLD. Blast radius
#: today is $0 (only the sleeve's rules can pass rule_predates_position, and
#: the sleeve owns its positions) — adopted as structure, not as an emergency,
#: exactly as the COO scoped it. v3 also fixes a v2 gatherer defect found
#: during this change: ORDER_FILLED payloads carry `filled_qty`, not `qty`, so
#: v2's position_opened_at never resolved and rule_predates_position failed
#: closed on EVERYTHING — over-tight (the sleeve's legitimate auto-path was
#: dead), never loose, but wrong, and now tested.
#:
#: v3 -> v4 (2026-08-21, riskofficer R19, spec at
#: docs/R19_ENVELOPE_V4_SPEC_2026-08-21.md). THE CORRECTION TO THE RECORD, as a
#: new dated note rather than an edit to the v3 note above — findings are never
#: edited, and v3's adoption premise is now MEASURED FALSE in both halves:
#:
#:   * "only the sleeve's rules can pass rule_predates_position" — the sleeve's
#:     rules DO pass it (TLT set_at 2026-08-18T02:11:39 against opened_at
#:     2026-08-19T18:20:54).
#:   * "and the sleeve owns its positions" — true of the LEDGER the check read
#:     and false of the WORLD. Measured at the broker: book 3.019871 TLT /
#:     8.122157 DBC / 5.314306 DBA against a broker holding 0 / 0 / 0.
#:
#: So "blast radius today is $0" was $750.35 armed, 39.79% of NAV, of which
#: $501.58 is date-certain: the TLT and DBC `kind: time` rules (ExitRuleSet seq
#: 178 and 181) fire on 2026-09-08 and v3 approves them TWELVE CHECKS OUT OF
#: TWELVE, selling shares the broker holds none of. Shorting is enabled.
#:
#: AND IT IS NOT ONLY DATED. TLT/DBC/SPY/DBA each ALSO carry an UNDATED
#: `loss_pct` rule (4.0 / 8.7 / 7.3 / 6.1 percent). Any one firing on an
#: ordinary drawdown hits the identical defect on any day. 2026-09-08 is when
#: part of the exposure becomes certain, not when it begins.
#:
#: (An earlier draft of this note said $652.09 date-certain. That summed two
#: DIFFERENT dates: DBA's and SPY's `time` exits are 2026-11-19. Per-leg
#: figures were exact; only the attribution was wrong. Corrected before merge
#: on the adversary's F1.)
#:
#: The envelope was not malfunctioning. Every check v3 makes is factually true.
#: It checks the fund's own books and never asks the broker what it holds.
#:
#: v4 adds three checks, RELAXES NONE, and generalises one:
#:
#:   * exit_reduces_exposure — the fund's own signed book must move TOWARD zero
#:     and never cross it. (New.)
#:   * venue_holds_position — the BROKER's own answer, over an authenticated
#:     round trip, must hold the quantity on the same side. (New. This is the
#:     one that refuses 2026-09-08.)
#:   * book_venue_in_sync — the two ledgers must agree within
#:     MAX_POSITION_DRIFT_QTY. A fund that does not know what it holds does not
#:     self-execute. (New.)
#:   * rule_owner_holds_position — v3's R5, made SIGN-AWARE via the same
#:     predicate rather than the old unsigned `qty <= held` comparison, which
#:     read a short as a zero (the max(0.0, ...) clamp in the gatherer) and read
#:     a missing qty as a free pass (`float(qty or 0.0)` -> 0 <= held).
#:
#: NOT DONE HERE, deliberately: `side_is_sell` is UNCHANGED. Relaxing it to a
#: side_reduces_exposure — which a shorting strategy needs before it can have
#: auto-exits at all — is a WIDENING and goes to the adversary blind first. v4
#: is strictly tightening: every order v4 approves, v3 would also have approved.
AUTOPOLICY_VERSION = "v4"

#: Marker the exit tick stamps into rationales it generates. Kept in v2 as a
#: cheap first filter; the authoritative provenance is exit_trigger_linked.
EXIT_MARKER = "PRE-COMMITTED EXIT FIRED"

#: R1's bound: the largest disagreement between the mark an exit fired on and
#: the fund's own last struck mark that the policy will still act on, in
#: percent. JUDGED, with the reason written: the phantom read 75.8% off the
#: strike made half an hour earlier; a genuine single-name crash can exceed
#: 30% — and when it does, the exit PROPOSAL still stands and a HUMAN clicks
#: it. Exceeding the bound never blocks the trade; it only removes the
#: machine's mandate to take it unattended. Failing closed on an
#: uncorroboratable mark is the entire lesson of the incident.
MAX_MARK_MOVE_VS_STRIKE_PCT = 30.0

#: R7's ceiling: max auto-approved order notional as a percent of last struck
#: NAV. JUDGED: set equal to the risk gate's max_position_pct (20%) because an
#: exit can never legitimately exceed one maximum-sized position — so the cap
#: bounds the blast radius to one position without ever disqualifying a
#: legitimate full-position close (the sleeve's TLT is ~12.5%). Tightening it
#: is a versioned change the CEO may make at any time.
MAX_AUTO_NOTIONAL_PCT = 20.0

#: Jobs that must be demonstrably alive before the policy may act. If the fund
#: cannot prove its own controls are ticking, it has no business executing
#: without a human — silence is not calm.
REQUIRED_HEARTBEATS = ("exit_check", "risk_monitor", "settlement")

#: Freshness ceiling for an auto-approval, deliberately far tighter than the
#: human staleness limit (120 min). A machine acting on a five-minute-old
#: proposal is acting on the mark that raised it; anything older waits for the
#: next tick to re-raise against fresh marks.
MAX_AGE_MINUTES = 10.0

#: v4: the quantity epsilon for the exposure predicate. Not a threshold anyone
#: tunes — it is float noise, and it was already the inline `1e-9` v3 used at
#: its `oqty <= held + 1e-9` comparison. Named so the three ledgers cannot
#: acquire three different ideas of "zero".
POSITION_EPS = 1e-9

#: v4: the largest book-vs-venue quantity disagreement the policy will still
#: call "in sync", per symbol. Set EQUAL TO THE RECONCILER'S OWN ``_TOL``
#: (reconcile.py:20) on purpose: two definitions of "in sync" is exactly the
#: second-opinion defect marksanity.py:12 was written to name, and a symbol the
#: reconciler flags as drifted while the approval policy calls it reconciled is
#: the fund holding two beliefs about the same number. tests/test_autopolicy.py
#: pins the two together so they cannot drift apart silently.
MAX_POSITION_DRIFT_QTY = 1e-6


def reduces_exposure(pre: Optional[float], delta: Optional[float]) -> bool:
    """THE v4 INVARIANT, as one predicate: an exit REDUCES exposure and never
    crosses zero into a position in the opposite direction.

    ``pre`` is the signed position on some ledger; ``delta`` is what the order
    would do to it (``+qty`` buy, ``−qty`` sell). Both conjuncts earn their keep:

    * ``pre * delta < -EPS`` — the order must push TOWARD zero. It does the sign
      work for free and, because a flat ledger yields exactly ``0``, it also
      kills the flat case. **That conjunct is what refuses 2026-09-08's TLT**:
      the broker holds 0, so ``0 * −3.019871 = 0``, which is not ``< −EPS``.
    * ``abs(delta) <= abs(pre) + EPS`` — it must not overshoot through zero and
      out the other side. Selling 10 against a long 3 closes 3 and SHORTS 7.

    Deliberately SIGN-AGNOSTIC: it is equally true of a long being sold and a
    short being bought back. That is a property of the invariant, not a
    widening — ``side_is_sell`` is a separate check and v4 does not touch it.
    Absence on either side is False: an unmeasurable position is never a
    permitted one.
    """
    if pre is None or delta is None:
        return False
    try:
        product = float(pre) * float(delta)
        # NaN fails every comparison, so a NaN on either side lands on False
        # without a special case. Verified in the tests rather than assumed.
        return (product < -POSITION_EPS
                and abs(float(delta)) <= abs(float(pre)) + POSITION_EPS)
    except (TypeError, ValueError, OverflowError):
        return False


def _as_float(value: Any) -> Optional[float]:
    """A context value as a float, or ABSENT. Never raises.

    ``evaluate()`` is the deterministic core of an execution path and must
    return a verdict for every input it is handed, including a malformed one —
    an exception there aborts the whole tick and leaves the remaining orders
    unevaluated. So a value that will not parse becomes ``None``, which every
    check fails closed on, rather than a traceback.
    """
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):  # NaN / ±inf
        return None
    return out


def order_delta(order: dict[str, Any]) -> Optional[float]:
    """Signed effect of an order on a position: ``+qty`` buy, ``−qty`` sell.

    ``None`` when the side or the quantity cannot be read — which every check
    downstream fails closed on. Note that v3 read the quantity as
    ``float(order.get("qty") or 0.0)``, so an order with NO quantity became
    ``0.0`` and sailed through ``0 <= held``; here it is absent instead, which
    is what it actually is.
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


def venue_snapshot(connector: Any) -> tuple[bool, dict[str, float]]:
    """One broker round trip, returning ``(readable, {symbol: signed_qty})``.

    ``readable`` is carried SEPARATELY from the dict, and that separation is
    the whole point: an empty dict is what a genuinely flat account returns AND
    what an unreachable broker returns, and reading the second as the first is
    precisely how "we could not look" becomes "everything is flat". Both
    connectors OMIT flat symbols (paper filters ``abs(qty) > 1e-9``; Alpaca
    simply does not return them), so a symbol's ABSENCE from a list we did read
    means zero — but only because we read it, which is what the flag records.

    Any failure — no connector, a raising ``positions()``, a row that will not
    parse — returns ``(False, {})`` and discards whatever was parsed so far. A
    partial read is not a read.

    Reads SETTLED positions, not positions net of working orders. Harmless
    today (the fund raises one exit order per rule and nothing else is in
    flight), and stated here rather than discovered later.
    """
    if connector is None:
        return False, {}
    try:
        rows = connector.positions() or []
    except Exception as e:  # noqa: BLE001 — unreachable venue -> not readable
        logger.warning("autopolicy: venue positions could not be read: %s", e)
        return False, {}
    out: dict[str, float] = {}
    try:
        for p in rows:
            if isinstance(p, dict):
                sym, qty = p.get("symbol"), p.get("qty")
            else:
                sym, qty = getattr(p, "symbol", None), getattr(p, "qty", None)
            if not sym or _as_float(qty) is None:
                # NOT skipped. A row we cannot read names a symbol that would
                # then be absent from the dict — and absent from a READ list
                # means flat. Silently dropping it is the absence-is-zero error
                # this entire function exists to prevent, so it fails the whole
                # read instead.
                raise ValueError(f"unreadable venue position row: {p!r}")
            # Summed rather than assigned: if a venue ever returns two rows for
            # one symbol, the fold is the honest answer and a last-write-wins
            # would silently drop half the position.
            out[str(sym)] = out.get(str(sym), 0.0) + float(qty)
    except Exception as e:  # noqa: BLE001 — a partial parse is not a read
        logger.warning("autopolicy: venue positions could not be parsed: %s", e)
        return False, {}
    return True, out


def evaluate(order: dict[str, Any], *, halted: bool,
             heartbeats: dict[str, Any],
             age_minutes: Optional[float],
             context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """One order against the envelope. Deterministic; returns every check.

    The result is APPROVE only when every check passes. Any check that cannot be
    evaluated fails closed — an absence is never a yes.

    ``context`` carries the v2 inputs, gathered from the event log and the
    pricer by ``context_for``:
      trigger_order_id     — order_id on the matching EXIT_RULE_TRIGGERED event
      trigger_symbol       — symbol on that event
      rule_set_at          — when the firing rule was committed (event ts)
      position_opened_at   — ts of the fill that opened the current position
      mark_move_vs_strike_pct — |current mark / last struck mark − 1| × 100
      notional_pct_of_nav  — order notional as % of last struck NAV
    and the v4 inputs:
      rule_strategy_holding_qty — SIGNED qty the rule's own strategy holds
      book_qty_signed      — SIGNED qty the fund's book holds, folded fund-wide
      venue_readable       — did the broker round trip succeed AT ALL
      venue_qty_signed     — SIGNED qty the broker says it holds; 0.0 when the
                             list was read and the symbol is absent, None when
                             it could not be read. The two are different facts
                             and v4 reports them differently.
    A missing context, or any missing field, fails the corresponding check —
    the policy never widens because the gatherer broke.
    """
    ctx = context or {}
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: Optional[bool], detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    side = str(order.get("side") or "").lower()
    check("side_is_sell", side == "sell",
          f"side={side!r}; the policy auto-approves risk-reducing closes only")

    rationale = str(order.get("rationale") or "")
    is_exit = EXIT_MARKER in rationale
    check("exit_rule_provenance", is_exit,
          "order carries the exit-tick marker" if is_exit else
          "not raised by a pre-committed exit rule — outside the envelope")

    # R3: the marker is a string anyone can type; the trigger EVENT is written
    # only by ExitRules.enforce(). Both forged orders from the audit fail here.
    oid = str(order.get("order_id") or "")
    linked = (bool(oid)
              and ctx.get("trigger_order_id") == oid
              and ctx.get("trigger_symbol") == order.get("symbol"))
    check("exit_trigger_linked", linked,
          "an EXIT_RULE_TRIGGERED event names this exact order" if linked else
          "no EXIT_RULE_TRIGGERED event names this order — a marker without "
          "its event is wording, not provenance; fails closed")

    # R4: pre-commitment is tested, not asserted. The policy's own doctrine —
    # "a stop committed to BEFORE the position existed" — declined its first
    # live fire retroactively (rule set 08-17, position opened 08-14).
    set_at, opened_at = ctx.get("rule_set_at"), ctx.get("position_opened_at")
    if not set_at or not opened_at:
        check("rule_predates_position", False,
              f"rule set_at={set_at!r}, position opened_at={opened_at!r} — "
              f"undeterminable is not pre-committed; fails closed")
    else:
        ok = str(set_at) < str(opened_at)
        check("rule_predates_position", ok,
              f"rule committed {set_at} vs position opened {opened_at}" +
              ("" if ok else " — the rule was set AGAINST an existing "
                             "position, which is the psychology pre-commitment "
                             "exists to defeat"))

    # R1: the number itself, corroborated against the fund's own last strike.
    move = ctx.get("mark_move_vs_strike_pct")
    if move is None:
        check("mark_corroborated", False,
              "the triggering mark could not be compared to the last struck "
              "mark — an uncorroboratable number does not self-execute; the "
              "proposal waits for a human")
    else:
        ok = move <= MAX_MARK_MOVE_VS_STRIKE_PCT
        check("mark_corroborated", ok,
              f"mark is {move:.1f}% from the last struck mark against a "
              f"{MAX_MARK_MOVE_VS_STRIKE_PCT:.0f}% bound" +
              ("" if ok else " — a move this size is either a data fault or a "
                             "crash, and both deserve the human's eyes"))

    # THE THREE LEDGERS (v4), asked in the order a human would ask them: does
    # the rule's own strategy hold this, does the FUND hold it, does the BROKER
    # hold it — and do the last two agree. One predicate, `reduces_exposure`,
    # applied to each. Non-short-circuiting like everything else here: each is
    # evaluated and recorded even when an earlier one has already failed, which
    # is what made the first audit possible from the log alone.
    delta = order_delta(order)
    symbol = order.get("symbol")

    # R5 (v3, made sign-aware in v4): the rule's own strategy must hold what the
    # order sells. A rule registered under one strategy_id must never liquidate
    # another strategy's position — which is literally what the first live fire
    # did. v3 compared unsigned quantities against a gatherer that clamped the
    # holding at zero, so a SHORT held by the strategy read as flat.
    # Coerced through _as_float so a malformed context value lands on ABSENT —
    # which fails closed — rather than on an exception that would abort the
    # tick and leave every remaining order unevaluated.
    held = _as_float(ctx.get("rule_strategy_holding_qty"))
    if held is None or delta is None:
        check("rule_owner_holds_position", False,
              f"the triggering rule's strategy holding could not be determined "
              f"(held={held!r}, order delta={delta!r}) — an unownable close "
              f"does not self-execute")
    else:
        ok = reduces_exposure(held, delta)
        check("rule_owner_holds_position", ok,
              f"order delta {delta} against {held} held by the rule's own "
              f"strategy" +
              ("" if ok else " — the rule would be closing a position its "
                             "strategy does not hold, or crossing it into the "
                             "opposite direction"))

    # v4 / the fund's own book: the exit must move the FUND's signed position
    # toward zero. Folded fund-wide from the fills, which the gatherer already
    # computed and threw away.
    book = _as_float(ctx.get("book_qty_signed"))
    if book is None or delta is None:
        check("exit_reduces_exposure", False,
              f"the fund's own signed position in {symbol} could not be "
              f"determined (book={book!r}, order delta={delta!r}) — an "
              f"unmeasurable position is not a closable one; fails closed")
    else:
        ok = reduces_exposure(book, delta)
        check("exit_reduces_exposure", ok,
              f"the fund's book holds {book} {symbol}; this order moves it by "
              f"{delta}" +
              ("" if ok else " — which does not reduce exposure, or crosses "
                             "zero into a position in the opposite direction"))

    # v4 / THE VENUE — the check that refuses 2026-09-08. Note what is read and
    # what is NOT: `connector.positions()`, the broker's own answer over an
    # authenticated round trip. NEVER `order["venue"]`, which is a client string
    # the proposer supplies and which exitrule.py hardcodes to "paper" on every
    # exit it raises, whatever connector will execute it — a venue == "paper"
    # check would have passed the exact orders that go to Alpaca.
    #
    # Three outcomes with three DISTINCT detail strings, because "we could not
    # look" and "we looked and it is zero" have completely different fixes and
    # the audit reads the detail, not the boolean.
    readable = ctx.get("venue_readable")
    vqty = _as_float(ctx.get("venue_qty_signed"))
    if readable is not True:
        check("venue_holds_position", False,
              "the venue's positions could not be read — an unmeasurable "
              "position is not a zero position")
    elif vqty is None:
        check("venue_holds_position", False,
              f"the venue read succeeded but carried no quantity for {symbol} "
              f"— a gap in a read is not a reading of zero")
    elif abs(vqty) <= POSITION_EPS:
        opens = "a short" if side == "sell" else "a position"
        check("venue_holds_position", False,
              f"the venue holds ZERO {symbol}; this {side.upper() or 'ORDER'} "
              f"of {order.get('qty')} would open {opens}, not close an "
              f"existing one")
    else:
        ok = reduces_exposure(vqty, delta)
        check("venue_holds_position", ok,
              f"the venue holds {vqty} {symbol}; this order moves it by "
              f"{delta}" +
              ("" if ok else " — the venue does not hold that quantity on that "
                             "side, so the order would open or increase an "
                             "opposite position"))

    # v4 / the two ledgers against each other. A fund whose book and broker
    # disagree does not know what it holds, and an order sized off the wrong one
    # is wrong by exactly the drift.
    if book is None or readable is not True or vqty is None:
        check("book_venue_in_sync", False,
              f"book={book!r} against venue={vqty!r} (venue readable="
              f"{readable!r}) — the two ledgers could not be compared, and an "
              f"uncomparable book is not a reconciled one")
    else:
        drift = abs(book - vqty)
        ok = drift <= MAX_POSITION_DRIFT_QTY
        check("book_venue_in_sync", ok,
              f"book holds {book} {symbol} against {vqty} at the venue — drift "
              f"{drift:.9f} against a {MAX_POSITION_DRIFT_QTY:g} tolerance" +
              ("" if ok else " — the fund does not know what it holds; an "
                             "unreconciled position does not self-execute"))

    # R7: the blast radius, governed.
    npct = ctx.get("notional_pct_of_nav")
    if npct is None:
        check("notional_within_cap", False,
              "order notional vs NAV could not be computed; fails closed")
    else:
        check("notional_within_cap", npct <= MAX_AUTO_NOTIONAL_PCT,
              f"notional is {npct:.1f}% of last struck NAV against a "
              f"{MAX_AUTO_NOTIONAL_PCT:.0f}% auto ceiling")

    check("not_halted", not halted,
          "kill switch engaged — nothing executes" if halted else
          "trading not halted")

    for job in REQUIRED_HEARTBEATS:
        row = heartbeats.get(job) or {}
        ok = row.get("ok")
        # ok can be True / False / None(unobserved). Only True passes: a fund
        # that cannot prove its controls are alive does not self-execute.
        check(f"liveness_{job}", ok is True,
              f"{job}: ok={ok} age={row.get('age_seconds')}s")

    if age_minutes is None:
        check("freshness", False,
              "proposal age UNKNOWN — unknown is not fresh; fails closed")
    else:
        check("freshness", age_minutes <= MAX_AGE_MINUTES,
              f"proposed {age_minutes:.1f} min ago against a "
              f"{MAX_AGE_MINUTES:.0f}-min auto ceiling")

    approve = all(c["ok"] is True for c in checks)
    return {
        "policy_version": AUTOPOLICY_VERSION,
        "approve": approve,
        "checks": checks,
        "note": ("every envelope check passed — auto-approving a pre-committed, "
                 "risk-reducing close" if approve else
                 "outside the envelope — waits for the CEO like any other order"),
    }


def context_for(store: Any, order: dict[str, Any],
                pricer: Optional[Callable[[str], float]], *,
                venue_positions: Optional[dict[str, float]] = None,
                venue_readable: bool = False) -> dict[str, Any]:
    """Gather the envelope's inputs for one order from the log, the pricer and
    the venue snapshot.

    One pass over the log; every failure degrades to an ABSENT field, which
    evaluate() fails closed on. The gatherer can only narrow the envelope by
    breaking, never widen it.

    ``venue_positions`` / ``venue_readable`` come from ``venue_snapshot()``,
    taken ONCE PER TICK by the caller rather than once per order — a broker
    round trip per order would make the policy's cost a function of the queue
    length. They default to *unreadable*, so a caller that has not been updated
    to pass them declines everything rather than approving on a phantom flat
    book. Fail-closed defaults are the only safe ones on this path.
    """
    from app.fund.events import EventType

    oid = str(order.get("order_id") or "")
    symbol = order.get("symbol")
    ctx: dict[str, Any] = {}

    # Set BEFORE the log walk, deliberately: the venue read is independent of
    # the event log, so an exception below must not erase what the broker said.
    # `venue_readable` is a separate field from the dict and is never inferred
    # from it — an empty dict means "flat" only when we know we read one.
    ctx["venue_readable"] = venue_readable is True
    if ctx["venue_readable"] and symbol:
        try:
            ctx["venue_qty_signed"] = float((venue_positions or {}).get(symbol, 0.0))
        except (TypeError, ValueError):
            ctx["venue_qty_signed"] = None
    else:
        ctx["venue_qty_signed"] = None

    trigger = None
    rule_sets: dict[tuple, str] = {}      # (strategy_id,symbol,kind) -> last set ts
    struck_marks: dict[str, float] = {}
    struck_nav: Optional[float] = None
    opened_at: Optional[str] = None
    qty_running = 0.0
    #: (strategy_id) -> signed qty held in THIS order's symbol, from fills.
    qty_by_strategy: dict[Any, float] = {}

    try:
        for e in store.stream(since_seq=0, limit=100_000):
            t = e.get("type") if isinstance(e, dict) else getattr(e, "type", None)
            t = getattr(t, "value", t)
            p = (e.get("payload") if isinstance(e, dict)
                 else getattr(e, "payload", None)) or {}
            ts = e.get("ts") if isinstance(e, dict) else getattr(e, "ts", None)
            if t == EventType.EXIT_RULE_SET.value:
                key = (p.get("strategy_id"), p.get("symbol"), p.get("kind"))
                rule_sets[key] = str(p.get("at") or ts or "")
            elif t == EventType.EXIT_RULE_TRIGGERED.value and p.get("order_id") == oid:
                trigger = {**p, "ts": ts}
            elif t == EventType.NAV_STRUCK.value:
                rows = p.get("positions") or []
                if rows:
                    struck_marks = {r["symbol"]: float(r["mark"]) for r in rows
                                    if r.get("symbol") and r.get("mark") is not None}
                if p.get("total_nav_usd") is not None:
                    struck_nav = float(p["total_nav_usd"])
            elif t == EventType.ORDER_FILLED.value and p.get("symbol") == symbol:
                # v3 fix: fill payloads carry `filled_qty` (v2 read `qty`,
                # which does not exist — position_opened_at never resolved and
                # every order failed the pre-commitment check closed).
                q = float(p.get("filled_qty") or p.get("qty") or 0.0)
                signed = q if str(p.get("side") or "").lower() == "buy" else -q
                was_flat = abs(qty_running) < 1e-9
                qty_running += signed
                if was_flat and abs(qty_running) >= 1e-9:
                    opened_at = str(p.get("at") or ts or "")
                sid = p.get("strategy_id")
                qty_by_strategy[sid] = qty_by_strategy.get(sid, 0.0) + signed
    except Exception as e:  # noqa: BLE001 — absent fields fail closed downstream
        logger.warning("autopolicy context gather failed for %s: %s", oid, e)
        return ctx

    if trigger:
        ctx["trigger_order_id"] = trigger.get("order_id")
        ctx["trigger_symbol"] = trigger.get("symbol")
        key = (trigger.get("strategy_id"), trigger.get("symbol"),
               trigger.get("kind"))
        ctx["rule_set_at"] = rule_sets.get(key)
        # R5: what the rule's OWN strategy holds in this symbol, from fills.
        # v4 drops v3's `max(0.0, ...)` clamp. The clamp made a strategy that is
        # SHORT the symbol read as flat — which is the same "absence is zero"
        # error the venue check exists to fix, one ledger over. The sign now
        # travels to `reduces_exposure`, which is what needs it.
        ctx["rule_strategy_holding_qty"] = qty_by_strategy.get(
            trigger.get("strategy_id"), 0.0)
    ctx["position_opened_at"] = opened_at
    # v4: the fund-wide signed position. Already computed above as the running
    # fold; v3 computed it and threw it away, so exposing it costs no new pass
    # over the log.
    #
    # KNOWN AND DELIBERATE NARROWNESS, stated rather than discovered later: this
    # folds ORDER_FILLED only, while PositionsProjection ALSO folds
    # CORPORATE_ACTION_APPLIED (positions.py:101-114), which rewrites a symbol's
    # quantity outright on a split. So after a split this number would disagree
    # with the fund's official book until a fill re-based it.
    #
    # It is left this way because the disagreement can only fail CLOSED. A split
    # the venue has applied and this fold has not makes `book_qty_signed` differ
    # from `venue_qty_signed` by the split ratio, which trips
    # `book_venue_in_sync` and DECLINES — an order waiting for the CEO, which is
    # the correct outcome for a book the fund cannot reconcile. And the check
    # that actually refuses 2026-09-08 reads the broker directly and does not
    # depend on this number at all. The fund has had no corporate action to
    # date; if that changes, fold this from PositionsProjection instead of
    # widening the tolerance. tests/test_autopolicy.py pins the current
    # behaviour so the narrowness cannot be mistaken for an oversight.
    ctx["book_qty_signed"] = qty_running

    mark = None
    if pricer is not None and symbol:
        try:
            mark = float(pricer(symbol))
        except Exception:  # noqa: BLE001 — unpriceable -> absent -> fails closed
            mark = None
    strike = struck_marks.get(symbol) if symbol else None
    if mark is not None and strike:
        ctx["mark_move_vs_strike_pct"] = abs(mark / strike - 1.0) * 100.0
    if mark is not None and struck_nav:
        try:
            qty = float(order.get("qty") or 0.0)
            ctx["notional_pct_of_nav"] = abs(qty * mark) / struck_nav * 100.0
        except Exception:  # noqa: BLE001
            pass
    return ctx


def run(pipeline: Any, pending: list[dict[str, Any]], *, halted: bool,
        heartbeats: dict[str, Any],
        context_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None
        ) -> dict[str, Any]:
    """Scan the queue and approve what the envelope covers. Everything is logged.

    Approval goes through the ORDINARY pipeline.approve_order path — the same
    staleness guard, the same arrival-price capture, the same idempotency key —
    with the approver naming the policy and its version. An auto path with its
    own bespoke execution would be a second pipeline to disagree with the first.
    """
    approved, skipped, failed = [], [], []
    for row in pending or []:
        oid = row.get("order_id")
        if not oid:
            continue
        try:
            ctx = context_fn(row) if context_fn is not None else None
        except Exception as e:  # noqa: BLE001 — a broken gatherer fails closed
            logger.warning("autopolicy context_fn failed for %s: %s", oid, e)
            ctx = None
        verdict = evaluate(row, halted=halted, heartbeats=heartbeats,
                           age_minutes=row.get("age_minutes"), context=ctx)
        if not verdict["approve"]:
            failed_checks = [c["check"] for c in verdict["checks"]
                             if c["ok"] is not True]
            skipped.append({"order_id": oid, "symbol": row.get("symbol"),
                            "failed_checks": failed_checks})
            # A DECLINE MUST BE AUDIBLE. Until v4 this branch logged nothing:
            # run() logged approvals and errors only, and the worker discards
            # this return value entirely, so an order the envelope refused
            # produced no event, no log line and no alarm. That was survivable
            # while the envelope refused nothing; v4 refuses the 2026-09-08 TLT
            # and DBC time exits, and a silent refusal there is the unwired
            # kill switch wearing the opposite costume — "the machine quietly
            # stops honouring the fund's own exits" instead of "the machine
            # quietly opens a short". The proposal then expires at 120 minutes
            # and does NOT come back on its own (exitrule.py:275 skips any rule
            # carrying `triggered_at`; only a fresh EXIT_RULE_SET clears it), so
            # this line is the only thing standing between a refused exit and
            # nobody ever knowing. Strictly additive: it changes no behaviour.
            logger.warning(
                "AUTOPOLICY DECLINED %s %s %s under %s — outside the envelope, "
                "waiting for the CEO. Failed checks: %s", row.get("side"),
                row.get("qty"), row.get("symbol"), AUTOPOLICY_VERSION,
                ", ".join(failed_checks) or "(none recorded)")
            continue
        try:
            pipeline.approve_order(
                oid, approver=f"auto-policy-{AUTOPOLICY_VERSION}",
                policy_evaluation=verdict)
            approved.append({"order_id": oid, "symbol": row.get("symbol"),
                             "side": row.get("side"), "qty": row.get("qty")})
            logger.warning(
                "AUTO-APPROVED %s %s %s under %s — exit-rule close, all "
                "envelope checks green", row.get("side"), row.get("qty"),
                row.get("symbol"), AUTOPOLICY_VERSION)
        except Exception as e:  # noqa: BLE001
            # A failed auto-approval leaves the order PENDING for a human — the
            # policy failing must degrade to the old behaviour, never to a lost
            # order.
            failed.append({"order_id": oid, "error": f"{type(e).__name__}: {e}"})
            logger.warning("auto-approval failed for %s, order left for a "
                           "human: %s", oid, e)
    return {
        "policy_version": AUTOPOLICY_VERSION,
        "approved": approved, "skipped": skipped, "failed": failed,
        "note": (f"{len(approved)} auto-approved, {len(skipped)} outside the "
                 f"envelope (waiting for the CEO), {len(failed)} errored and "
                 f"left pending"),
    }
