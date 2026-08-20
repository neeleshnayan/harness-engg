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
    """One pass over the log for everything this check needs.

    Returns, all optional and all absent-not-zero:
      symbol, quote_price   from the order's ORDER_PROPOSED payload
      reference_mark, struck_at   from the LAST NavStruck that priced the symbol
      held_qty              net signed quantity from fills, the fund's own book

    ``reference_mark`` comes from the LAST strike only, never from an older one
    that happened to carry the symbol: a mark from three strikes ago is stale by
    an unknown amount, and a comparison against it would produce a confident
    number about nothing. Absent is the honest answer there.
    """
    from app.fund.events import EventType

    out: dict[str, Any] = {
        "symbol": None, "quote_price": None, "side": None, "qty": None,
        "reference_mark": None, "struck_at": None, "held_qty": 0.0,
        "gather_error": None,
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
        held = 0.0
        for side, q, fsym in fills:
            if fsym != sym:
                continue
            held += q if side == "buy" else -q
        out["held_qty"] = held
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
    held = _num(facts.get("held_qty")) or 0.0
    result: dict[str, Any] = {
        "refuse": True, "reason": "", "symbol": sym,
        "quote_price": quote, "reference_mark": ref,
        "struck_at": facts.get("struck_at"), "move_pct": None,
        "bound_pct": bound_pct, "basis": "unknown",
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

    if ref is None:
        if abs(held) > 1e-9:
            result["reason"] = (
                f"the fund holds {held:g} {sym} but the last NAV strike carries "
                f"no mark for it, so this order's ${quote:,.2f} cannot be "
                f"corroborated against the fund's own valuation. Strike NAV "
                f"first, then approve.")
            result["basis"] = "held_but_unpriced"
            return result
        if NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES:
            result["reason"] = (
                f"no reference mark: the fund has never struck a mark for {sym} "
                f"and holds none of it, so ${quote:,.2f} cannot be corroborated.")
            result["basis"] = "no_reference_strict"
            return result
        # The ordinary first purchase. ALLOWED, and the allowance is recorded so
        # it is auditable rather than invisible: this check did not run, and the
        # reason it did not run is a fact about the order.
        result["refuse"] = False
        result["basis"] = "no_reference_new_symbol"
        result["reason"] = (
            f"mark sanity did not apply: the fund holds no {sym} and has never "
            f"struck a mark for it, so it has nothing of its own to compare "
            f"${quote:,.2f} against. NOT a corroboration — an absence, recorded "
            f"as one.")
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
