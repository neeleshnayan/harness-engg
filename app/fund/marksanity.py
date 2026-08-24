"""Mark sanity on a MANUALLY approved order — the check whose absence cost $128.26.

On 2026-08-20 a GLD sell was proposed against a quote of $100.00 while the
fund's own last struck mark for GLD was $415.04 — a 75.9% disagreement — and a
human approved it. The auto-approval policy has refused exactly this since v2
(``mark_corroborated``, ``MAX_MARK_MOVE_VS_STRIKE_PCT``); the MANUAL path, which
is the path the phantom actually took, had no such check at all. The machine was
held to a standard the human was not, and the incident went through the gap.

This module is that check, and nothing else. Three properties it keeps:

  1. **ONE constant.** The bound is imported from ``autopolicy.py``. A second
     copy would be a second thing to move, and a threshold that exists twice is
     a threshold that has already drifted once.
  2. **Comparison, not valuation.** It compares the price the order was RAISED
     at (``impact_preview.quote_price``, written by the pipeline at propose
     time) against the fund's own last STRUCK mark. Both numbers are quoted in
     the refusal, because "refused: mark sanity" tells the CEO nothing and
     "$100.00 against a struck $415.04, 75.9% apart" tells them everything.
  3. **Fail closed on the case that bit us, open on the case that never can.**
     See ``NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES`` below — the one judgement in
     this file, written out because it is the one a reader will want to argue
     with.

AMENDED 2026-08-24 (ticket d79f65b1), and a reader should know this before the
three properties above are trusted: the check's ANSWER to "does the fund hold
this symbol" was wrong in both directions for a day. It summed fills itself
instead of reading the fund's one true holdings fold, so after a venue sync it
refused repurchases of positions the fund no longer held — naming a remedy that
cannot exist — and waved through positions the sync had adopted without any fill
history. The bound did not move and no branch was added to the price comparison;
one INPUT was repaired. See ``gather`` for the measured state that proved it.

Scope, stated so nobody assumes more: this guards the HTTP approval endpoint,
which is the manual path and the path the incident took. ``pipeline.approve_order``
itself is unchanged, so the auto-policy keeps reaching it through its own
(already tighter) R1 check and nothing else acquires a second, disagreeing
gate.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.fund.autopolicy import MAX_MARK_MOVE_VS_STRIKE_PCT

logger = logging.getLogger(__name__)

#: What to do when the fund has NO struck mark for the symbol AND holds none of
#: it — an ordinary first purchase.
#:
#: FALSE, and this is the file's one judgement call. The brief that commissioned
#: this check says "no struck mark for the symbol → refuse", and for a symbol
#: the fund HOLDS that is exactly right: a held position missing from the last
#: strike is an integrity failure, and the remedy the brief names (re-strike NAV
#: first) works. But NAV is struck over positions the fund HOLDS, so re-striking
#: can never mint a reference for a symbol it has never owned — under a literal
#: reading, every first purchase of every new instrument would be refused
#: forever, with no operator action able to clear it. That is not fail-closed,
#: it is fail-shut: it would freeze new deployment entirely, which is a defect
#: against the fund's own third metric (capital deployed under mandate).
#:
#: So the three cases are kept apart:
#:   * a reference exists and disagrees      -> REFUSE (the phantom's path)
#:   * the fund HOLDS the symbol, no mark    -> REFUSE (integrity; re-strike)
#:   * the fund holds none and has no mark   -> ALLOW, and SAY SO on the record
#:
#: The residual risk of the third case is named rather than hidden: a fabricated
#: price on a first-ever purchase is NOT caught here, because the fund has
#: nothing of its own to compare against. Closing that needs a different control
#: (corroboration against an independent quote source), not a tighter bound on
#: this one. Flipping this flag to True makes the check strict in one line, and
#: is a versioned change for the CEO, not for this module.
NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES = False


def _num(v: Any) -> Optional[float]:
    """A finite float, or None. Never a zero standing in for a missing price —
    a zero mark would make every comparison look like a 100% disagreement."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def gather(store: Any, order_id: str) -> dict[str, Any]:
    """Everything this check needs: one pass for the order and the marks, plus
    the fund's own holdings fold.

    Returns, all optional and all absent-not-zero:
      symbol, quote_price   from the order's ORDER_PROPOSED payload
      reference_mark, struck_at   from the LAST NavStruck that priced the symbol
      held_qty              the fund's holding, from ``PositionsProjection``
      held_qty_from_fills   DIAGNOSTIC ONLY — see below. No branch reads it.

    ``reference_mark`` comes from the LAST strike only, never from an older one
    that happened to carry the symbol: a mark from three strikes ago is stale by
    an unknown amount, and a comparison against it would produce a confident
    number about nothing. Absent is the honest answer there.

    **HOLDINGS COME FROM THE ONE TRUE FOLD (ticket d79f65b1, 2026-08-24).**
    This function used to answer "does the fund hold it" by summing
    ``OrderFilled`` events itself. That is a SECOND, thinner fold of a quantity
    the fund already folds in exactly one place, and the two disagree the moment
    anything other than a fill moves the book. ``BookReconciledToVenue`` does
    precisely that — it SETS quantities absolutely
    (``projections/positions.py:196-229``) — so after a venue sync the fill-sum
    describes a book that no longer exists.

    Measured on the live log the morning this was fixed, at the sync (seq 1414,
    2026-08-24T12:36:46Z): of the eleven symbols either fold mentions, NINE were
    CLASSIFIED DIFFERENTLY by the two — held by one and not by the other, which
    is the disagreement that changes a branch. (Of the remaining two, F was flat
    in both; SPY was held in both but at different QUANTITIES — 0.346119 against
    0.217757 — which changes no branch but is quoted verbatim in the refusal the
    CEO reads.) The nine, in both directions:

      * DBA / DBC / TLT — fill-sum 5.314306 / 8.122157 / 3.019871, true book
        ZERO. The guard refused three approved repurchases as
        ``held_but_unpriced`` and named a remedy that cannot exist: NAV marks
        only what the book HOLDS (``projections/nav.py``'s compute iterates
        ``book.positions``), so no strike can ever mint a mark for a symbol the
        sync erased. The fund was told to do something structurally impossible.
      * GLD / INTC / MSFT / NVDA / SOFI / XLE — fill-sum ZERO, true book
        0.424471 / 1.608762 / 0.340051 / 0.749886 / 9.188190 / 2.749912. These
        are positions the sync ADOPTED with no fill history — the custody
        schema's ``foreign`` class, an actor outside the harness. The guard read
        them as never-owned and took the new-symbol branch, skipping
        corroboration on six real positions. That is the integrity case this
        module exists to catch, and the wrong input walked it straight past.

    So the number is READ from ``PositionsProjection`` now, not re-derived. The
    projection is constructed WITHOUT a snapshot store deliberately: this guard
    folds the log itself rather than trusting a cache, because a cache is one
    more thing that can be stale in the direction that approves an order.

    ``held_qty_from_fills`` is kept beside it as a DIAGNOSTIC, never an input —
    the Clean Field Rule's "preserve the contaminated value beside the new one".
    It is what makes a future divergence visible in the refusal record instead
    of silent. ``tests/test_marksanity.py`` pins that no branch reads it.
    """
    from app.fund.events import EventType

    out: dict[str, Any] = {
        "symbol": None, "quote_price": None, "side": None, "qty": None,
        "reference_mark": None, "struck_at": None,
        # ABSENT until the book fold answers. NOT 0.0: a zero here would mean
        # "the fund holds none", which is a claim, and an unread book has not
        # made any claim. Absence is never zero — and here the difference is
        # the difference between refusing and approving.
        "held_qty": None,
        "held_qty_from_fills": None,
        "holdings_basis": None,
        "gather_error": None,
        "holdings_error": None,
    }
    struck_marks: dict[str, float] = {}
    struck_at: Optional[str] = None
    fills: list[tuple[str, float, Any]] = []   # (side, filled_qty, symbol)

    try:
        for e in store.stream(since_seq=0, limit=100_000):
            t = e.get("type") if isinstance(e, dict) else getattr(e, "type", None)
            t = getattr(t, "value", t)
            p = (e.get("payload") if isinstance(e, dict)
                 else getattr(e, "payload", None)) or {}
            agg = (e.get("aggregate_id") if isinstance(e, dict)
                   else getattr(e, "aggregate_id", None))
            ts = e.get("ts") if isinstance(e, dict) else getattr(e, "ts", None)

            if t == EventType.ORDER_PROPOSED.value and agg == order_id:
                out["symbol"] = p.get("symbol")
                out["side"] = p.get("side")
                out["qty"] = _num(p.get("qty"))
                out["quote_price"] = _num(
                    (p.get("impact_preview") or {}).get("quote_price"))
            elif t == EventType.NAV_STRUCK.value:
                rows = p.get("positions") or []
                if rows:
                    struck_marks = {r["symbol"]: _num(r.get("mark"))
                                    for r in rows if r.get("symbol")}
                    struck_at = str(p.get("ts") or ts or "")
            elif t == EventType.ORDER_FILLED.value:
                # `filled_qty`, NOT `qty` — reading the wrong key is how
                # autopolicy v2 failed closed on everything for a day.
                fills.append((str(p.get("side") or "").lower(),
                              _num(p.get("filled_qty")) or 0.0,
                              p.get("symbol")))
    except Exception as e:  # noqa: BLE001
        # A broken gather produces ABSENT fields, and absent fields refuse.
        # The gatherer can only narrow this check by failing, never widen it.
        logger.warning("mark-sanity gather failed for %s: %s", order_id, e)
        out["gather_error"] = str(e)
        return out

    sym = out["symbol"]
    if sym:
        out["reference_mark"] = struck_marks.get(sym)
        out["struck_at"] = struck_at if sym in struck_marks else None
        from_fills = 0.0
        for side, q, fsym in fills:
            if fsym != sym:
                continue
            from_fills += q if side == "buy" else -q
        out["held_qty_from_fills"] = from_fills

        # THE BOOK. Read, never re-derived — see this function's docstring for
        # the nine live symbols the two folds disagreed about. Its own try/except
        # because it is a SEPARATE read from the stream above: a fold that raises
        # must leave `held_qty` absent (and absent refuses), never fall back to
        # the number the stream happened to have. Falling back would restore the
        # exact defect this repair removes, quietly, on the failure path.
        try:
            from app.fund.projections.positions import PositionsProjection

            book = PositionsProjection(store).build()
            pos = book.positions.get(sym)
            # `pop`-ped by a reconciliation, or never present: the fund holds
            # none. That is a MEASURED zero — the fold looked — which is why it
            # is written here and not defaulted above.
            out["held_qty"] = float(pos["qty"]) if pos else 0.0
            out["holdings_basis"] = "positions_projection"
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "mark-sanity could not fold the book for %s (%s): %s",
                order_id, sym, e)
            out["holdings_error"] = str(e)
    return out


def evaluate(facts: dict[str, Any],
             bound_pct: float = MAX_MARK_MOVE_VS_STRIKE_PCT) -> dict[str, Any]:
    """Decide, from gathered facts alone. Pure — the tests drive this directly.

    Returns ``{refuse, reason, ...}``. ``refuse`` is the only field the caller
    branches on; everything else exists so the refusal event and the error the
    CEO reads carry BOTH numbers rather than a verdict word.
    """
    quote = _num(facts.get("quote_price"))
    ref = _num(facts.get("reference_mark"))
    sym = facts.get("symbol") or "?"
    # NO `or 0.0`. That idiom turned an unread book into "the fund holds none",
    # which is the new-symbol branch, which APPROVES. An absent holding is a
    # refusal, not a zero.
    held = _num(facts.get("held_qty"))
    result: dict[str, Any] = {
        "refuse": True, "reason": "", "symbol": sym,
        "quote_price": quote, "reference_mark": ref,
        "struck_at": facts.get("struck_at"), "move_pct": None,
        "bound_pct": bound_pct, "basis": "unknown",
        # Both holdings numbers travel with the verdict so the refusal event
        # carries the divergence rather than only its consequence.
        "held_qty": held,
        "held_qty_from_fills": _num(facts.get("held_qty_from_fills")),
        "holdings_basis": facts.get("holdings_basis"),
    }

    if facts.get("gather_error"):
        result["reason"] = (
            f"the fund's own marks could not be read to corroborate this order "
            f"({facts['gather_error']}) — an uncheckable price does not get "
            f"approved; fix the read and try again")
        result["basis"] = "gather_failed"
        return result

    if quote is None:
        result["reason"] = (
            f"this order's proposal carries no impact_preview.quote_price, so "
            f"there is no price to corroborate. An order whose own raising "
            f"price is unknown is not approvable — re-propose it.")
        result["basis"] = "no_quote_price"
        return result

    if held is None:
        # The book could not be folded. Every remaining branch is a statement
        # about what the fund holds, so none of them can be reached honestly.
        #
        # Placed AFTER the quote check and BEFORE the reference check, and both
        # positions are deliberate. After, because an order with no raising
        # price is unapprovable whatever the book says, and that refusal names
        # the operator's actual next step. Before, because an unreadable book
        # must not reach the reference branches at all — including the
        # `corroborated` one, which does not read `held`. This is a TIGHTENING:
        # a well-corroborated order now refuses when the book is unreadable. It
        # is the right direction and it is cheap, because a fund whose
        # PositionsProjection raises cannot strike NAV either, so its marks are
        # going stale in the same minute.
        result["reason"] = (
            f"the fund's own book could not be folded"
            f"{' (' + str(facts.get('holdings_error')) + ')' if facts.get('holdings_error') else ''}"
            f", so whether the fund holds {sym} is unknown — and an order "
            f"cannot be corroborated against a book nobody can read. Fix the "
            f"read and try again.")
        result["basis"] = "holdings_unreadable"
        return result

    if ref is None:
        if abs(held) > 1e-9:
            # The remedy in this sentence is only TRUE because `held` now comes
            # from the book NAV itself marks. When it came from the fill-sum,
            # this branch could fire for a symbol the book does not hold, and
            # "strike NAV first" was then unreachable advice — NAV marks
            # `book.positions`, so it can never mark what the book has popped.
            # A refusal naming an impossible remedy is a deadlock, and that
            # deadlock stopped three approved repurchases on 2026-08-24.
            result["reason"] = (
                f"the fund holds {held:g} {sym} but the last NAV strike carries "
                f"no mark for it, so this order's ${quote:,.2f} cannot be "
                f"corroborated against the fund's own valuation. Strike NAV "
                f"first, then approve.")
            result["basis"] = "held_but_unpriced"
            return result
        if NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES:
            # Same correction as the branch below: the check reads the LAST
            # strike, so "never" is more than it knows.
            result["reason"] = (
                f"no reference mark: the last NAV strike carries no mark for "
                f"{sym} and the fund holds none of it, so ${quote:,.2f} cannot "
                f"be corroborated.")
            result["basis"] = "no_reference_strict"
            return result
        # The ordinary first purchase. ALLOWED, and the allowance is recorded so
        # it is auditable rather than invisible: this check did not run, and the
        # reason it did not run is a fact about the order.
        result["refuse"] = False
        result["basis"] = "no_reference_new_symbol"
        # "has never struck a mark for it" was the old wording, and this repair
        # made it a lie the guard could tell. The check reads the LAST strike
        # only, so all it can honestly claim is that THAT strike carries no
        # mark. Before d79f65b1 this branch was reachable only for genuinely
        # never-owned symbols; now a position the venue sync erased lands here
        # too — DBC, TLT and DBA all have marks in earlier strikes. Claiming
        # "never" about a symbol the fund priced last week is the kind of
        # confident sentence this module exists to stop printing.
        result["reason"] = (
            f"mark sanity did not apply: the fund holds no {sym} and the last "
            f"NAV strike carries no mark for it, so it has nothing of its own "
            f"to compare ${quote:,.2f} against. NOT a corroboration — an "
            f"absence, recorded as one.")
        return result

    if ref == 0:
        # A zero reference cannot be divided by, and a mark of zero is itself a
        # data fault. Never treated as "the price is 0 and everything disagrees".
        result["reason"] = (
            f"the last struck mark for {sym} is 0, which is a data fault rather "
            f"than a price — nothing can be corroborated against it.")
        result["basis"] = "zero_reference"
        return result

    move = abs(quote / ref - 1.0) * 100.0
    result["move_pct"] = move
    result["basis"] = "corroborated"
    # `> bound + eps`, matching autopolicy's own `move <= BOUND` semantics:
    # exactly AT the bound passes there, so it must pass here or the two
    # guards would disagree about the same number. The epsilon exists because
    # binary floats do not put it there: 130.0/100.0 - 1 is 0.30000000000000004,
    # so a plain `> 30.0` refuses a move that is 30.0% by every definition a
    # human uses. This is not a loosening — it is the declared semantics made
    # true. At the fund's largest mark it is a tolerance of about 4e-9 cents.
    if move > bound_pct + 1e-9:
        result["refuse"] = True
        result["reason"] = (
            f"mark sanity: this order was raised at ${quote:,.2f} for {sym}, "
            f"against the fund's own last struck mark of ${ref:,.2f} "
            f"({facts.get('struck_at') or 'time unknown'}) — {move:.1f}% apart, "
            f"past the {bound_pct:.0f}% bound. A disagreement this size is "
            f"either a bad feed or a genuine crash; both are reasons to look "
            f"before executing, not to click through. Re-strike NAV or "
            f"re-propose against a fresh quote.")
        return result

    result["refuse"] = False
    result["reason"] = (
        f"${quote:,.2f} is {move:.1f}% from the fund's own last struck mark of "
        f"${ref:,.2f}, inside the {bound_pct:.0f}% bound.")
    return result


def check(store: Any, order_id: str,
          bound_pct: float = MAX_MARK_MOVE_VS_STRIKE_PCT) -> dict[str, Any]:
    """Gather then evaluate. The one call an endpoint needs."""
    return evaluate(gather(store, order_id), bound_pct=bound_pct)
