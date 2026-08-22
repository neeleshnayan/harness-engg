"""The exit you committed to before you owned the position.

Seven of the eight steps in a position's life were instrumented and this was the
missing one, which is unfortunate because it is the step where discipline is
hardest. `underwater_pct` raised an alarm and then waited for a human — and by
then the human is a human with a position, whose judgement about whether to sell
is contaminated by owning the thing.

So the rule is recorded as an EVENT at deployment. That single choice is what
makes it a commitment rather than a note: a rule in a document can be edited by
the person it constrains, and nobody would ever know. A rule in the append-only
log cannot be revised, only superseded, and the supersession is visible.

Three events, and the third matters as much as the first two:

  * EXIT_RULE_SET      — the commitment, made before the position exists
  * EXIT_RULE_TRIGGERED — the condition fired; a closing proposal goes to the desk
  * EXIT_RULE_OVERRIDDEN — it fired and the position was kept anyway, WITH a reason

Overrides are allowed. Silent overrides are not. A stop that can be ignored
without a trace is not a stop, it is a story you tell yourself about why this time
is different — and the whole point of writing it down first was to make that story
expensive to tell.

What this does NOT do: trade. When a rule fires it puts a closing order in the
approval queue with the rule quoted in the proposal. The machine's job is to make
the pre-committed exit unmissable, never to act on it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: The kinds of exit a rule can specify. Deliberately few — a long list invites
#: elaborate conditions, and an exit nobody can state in one sentence is one
#: nobody will honour under pressure.
KINDS = ("loss_pct", "gain_pct", "time", "thesis")


class ExitRuleError(ValueError):
    pass


def build(strategy_id: str, kind: str, *, threshold_pct: Optional[float] = None,
          on_date: Optional[str] = None, note: str = "",
          symbol: Optional[str] = None) -> dict[str, Any]:
    """Validate and shape one exit commitment.

    Refuses a rule it cannot later evaluate. A rule that sounds like a commitment
    but cannot be checked is worse than none: it produces the feeling of
    discipline without the mechanism, and it will be cited later as though it had
    been enforced.
    """
    if kind not in KINDS:
        raise ExitRuleError(f"kind must be one of {KINDS}, got {kind!r}")
    if kind in ("loss_pct", "gain_pct"):
        if threshold_pct is None:
            raise ExitRuleError(f"{kind} needs a threshold_pct")
        if threshold_pct <= 0:
            raise ExitRuleError(
                "threshold_pct is a magnitude and must be positive — the "
                "direction is carried by the kind, so a signed number here would "
                "make 'loss_pct: -10' and 'loss_pct: 10' both look plausible and "
                "mean opposite things")
    if kind == "time":
        if not on_date:
            raise ExitRuleError("a time exit needs on_date (YYYY-MM-DD)")
        try:
            date.fromisoformat(on_date)
        except ValueError as e:
            raise ExitRuleError(f"on_date must be YYYY-MM-DD: {e}") from e
    if kind == "thesis" and not note:
        raise ExitRuleError(
            "a thesis exit is only as good as its written condition — state what "
            "observation would mean the reason for holding is gone, or this is "
            "not a rule")
    return {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "kind": kind,
        "threshold_pct": threshold_pct,
        "on_date": on_date,
        "note": note,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }


def evaluate(rule: dict[str, Any], *, unrealised_pnl_pct: Optional[float] = None,
             today: Optional[str] = None) -> dict[str, Any]:
    """Has this rule fired? Returns the reason in words, or says why it cannot tell.

    An unevaluable rule reports `fired: None` rather than False. False means
    "checked, and the condition does not hold"; None means "could not check" — and
    collapsing them would let a missing mark read as a position in good standing,
    which is the failure mode every other part of this system refuses.
    """
    kind = rule.get("kind")
    thr = rule.get("threshold_pct")

    if kind == "loss_pct":
        if unrealised_pnl_pct is None:
            return {"fired": None, "reason": "no mark available, so the loss "
                                             "condition could not be checked"}
        if unrealised_pnl_pct <= -abs(thr):
            return {"fired": True,
                    "reason": f"down {unrealised_pnl_pct:.2f}%, past the "
                              f"{abs(thr):.2f}% loss exit committed to on "
                              f"{str(rule.get('set_at'))[:10]}"}
        return {"fired": False,
                "reason": f"down {unrealised_pnl_pct:.2f}% of {abs(thr):.2f}%"}

    if kind == "gain_pct":
        if unrealised_pnl_pct is None:
            return {"fired": None, "reason": "no mark available, so the gain "
                                             "condition could not be checked"}
        if unrealised_pnl_pct >= abs(thr):
            return {"fired": True,
                    "reason": f"up {unrealised_pnl_pct:.2f}%, past the "
                              f"{abs(thr):.2f}% gain exit committed to on "
                              f"{str(rule.get('set_at'))[:10]}"}
        return {"fired": False,
                "reason": f"up {unrealised_pnl_pct:.2f}% of {abs(thr):.2f}%"}

    if kind == "time":
        now = today or datetime.now(timezone.utc).date().isoformat()
        if now >= str(rule.get("on_date")):
            return {"fired": True,
                    "reason": f"reached {rule.get('on_date')}, the date this was "
                              f"committed to be closed or re-decided"}
        return {"fired": False, "reason": f"holds until {rule.get('on_date')}"}

    if kind == "thesis":
        # Deliberately never fires on its own. A thesis break is a judgement, and
        # a machine claiming to have detected one would be inventing the hardest
        # part. What the machine CAN do is put the written condition in front of
        # the operator at every review so it is answered rather than forgotten.
        return {"fired": None,
                "reason": f"a human must answer this at review: "
                          f"{rule.get('note')}"}

    return {"fired": None, "reason": f"unknown exit kind {kind!r}"}


class ExitRules:
    """Exit commitments, folded from the event log.

    Folded rather than stored so the rules obey the same rule as everything else
    that matters here: the log is the truth, and a table would be a second place
    to disagree with it.
    """

    def __init__(self, store: Any):
        self._store = store

    def _fold(self) -> dict[tuple, dict[str, Any]]:
        from app.fund.events import EventType

        rules: dict[tuple, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            # The store yields DICTS, not Event objects. Reading it with getattr
            # silently found nothing — every rule committed fine, the chain grew,
            # and the fold reported "no exit rule is recorded". The unit test
            # passed throughout because its fake yielded objects, so the fake was
            # the thing that was wrong. Both shapes are handled now, and the fake
            # was corrected to match the real contract.
            if isinstance(e, dict):
                t, p = e.get("type"), e.get("payload") or {}
            else:
                t = getattr(e, "type", None) or getattr(e, "event_type", None)
                p = getattr(e, "payload", None) or {}
            t = getattr(t, "value", t)
            if t == EventType.EXIT_RULE_SET.value:
                key = (p.get("strategy_id"), p.get("symbol"), p.get("kind"))
                # A later commitment on the same key SUPERSEDES the earlier one.
                # The old one stays in the log — that is the point — but only the
                # current one governs, and the history of revisions is readable.
                # Note this also CLEARS `triggered`: re-committing a rule is a
                # fresh commitment, and it should be able to fire again.
                rules[key] = {**p, "superseded": key in rules}
            elif t == EventType.EXIT_RULE_TRIGGERED.value:
                key = (p.get("strategy_id"), p.get("symbol"), p.get("kind"))
                if key in rules:
                    # Idempotency for `enforce()`. Without this the tick would
                    # raise a fresh closing proposal every 30 seconds for as long
                    # as the condition held, burying the approval queue under
                    # hundreds of copies of one decision — which is how a control
                    # that works becomes a control the operator turns off.
                    rules[key] = {**rules[key],
                                  "triggered_at": p.get("at"),
                                  "triggered_order_id": p.get("order_id")}
            elif t == EventType.EXIT_RULE_OVERRIDDEN.value:
                key = (p.get("strategy_id"), p.get("symbol"), p.get("kind"))
                if key in rules:
                    rules[key] = {**rules[key],
                                  "overridden_at": p.get("at"),
                                  "override_reason": p.get("reason")}
        return rules

    def active(self, strategy_id: Optional[str] = None) -> list[dict[str, Any]]:
        out = [r for r in self._fold().values()]
        if strategy_id:
            out = [r for r in out if r.get("strategy_id") == strategy_id]
        return out

    def check(self, positions: list[dict[str, Any]],
              strategy_id: Optional[str] = None, *,
              holdings: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        """Evaluate every active rule against current marks.

        ``positions`` are the risk monitor's rows: symbol and
        ``unrealized_pnl_pct``. Returns fired, holding and unevaluable
        separately, because "could not check" is not "fine".

        ``holdings`` is the book seen PER OWNER — ``{strategy_id, symbol, qty,
        usd_value}`` — and it is what makes the coverage half of this report
        mean anything. See ``_uncovered``: the monitor's rows name no owner, so
        a caller that passes only ``positions`` gets the weaker symbol-level
        test and is TOLD so in ``coverage_basis`` rather than left to assume.
        """
        pnl = {p.get("symbol"): p.get("unrealized_pnl_pct")
               for p in (positions or [])}
        rules = self.active(strategy_id)
        fired, holding, unevaluable = [], [], []
        for r in rules:
            got = evaluate(r, unrealised_pnl_pct=pnl.get(r.get("symbol")))
            row = {**r, **got}
            (fired if got["fired"] is True
             else holding if got["fired"] is False
             else unevaluable).append(row)

        held = _held_rows(holdings if holdings is not None else positions)
        cov = _uncovered(rules, held)
        uncovered = cov["uncovered"]
        coverage_known = bool(holdings) if holdings is not None else bool(positions)
        return {
            "fired": fired,
            "holding": holding,
            "unevaluable": unevaluable,
            "uncovered": uncovered,
            "uncovered_usd": cov["uncovered_usd"],
            "uncovered_unvalued": cov["uncovered_unvalued"],
            "coverage_known": coverage_known,
            "coverage_basis": cov["coverage_basis"],
            "rules_not_live": cov["rules_not_live"],
            "note": _note(fired, holding, unevaluable, uncovered,
                          coverage_known=coverage_known,
                          uncovered_usd=cov["uncovered_usd"],
                          unvalued=cov["uncovered_unvalued"],
                          rules_not_live=cov["rules_not_live"]),
        }


    def enforce(self, positions: list[dict[str, Any]], *, pipeline: Any,
                actor: str = "worker",
                strategy_id: Optional[str] = None) -> dict[str, Any]:
        """Act on fired rules: append the event, raise a closing proposal.

        This is the method whose absence made the rest of this module a document.
        Every piece existed — the commitment, the evaluation, the three event
        types — and nothing joined them, so `EXIT_RULE_TRIGGERED` was emitted by
        no code in the repository and a fired rule produced exactly nothing. The
        framework document claimed the rule "is evaluated on every mark and puts a
        closing proposal in the approval queue". Both halves were false.

        What it does NOT do, and must never do, is close the position. It raises a
        SELL through the ordinary proposal path, which means the pre-trade gate
        still runs and a human still clicks. The machine's whole job is to make the
        pre-committed exit unmissable.

        Two rules keep it honest:

        * **The trigger is appended UNCONDITIONALLY, whatever the proposal did.**
          The proposal is attempted first and its failure is caught, so the log
          records that the condition fired even when no order could be raised —
          halted trading, an unreachable venue, no position quantity. What must
          never happen is the append being skipped on failure, which would lose
          the trigger precisely when something was already wrong. (In the log this
          reads as OrderProposed then ExitRuleTriggered; the order_id on the
          trigger is None when nothing could be raised, and that is the signal to
          look.)
        * **Already-triggered rules are skipped**, so the tick does not re-raise
          the same decision every 30 seconds.
        """
        from app.fund.connectors.base import Order, Side
        from app.fund.events import Event, EventType

        checked = self.check(positions, strategy_id)
        qty_by_symbol = {p.get("symbol"): p.get("qty") or p.get("quantity")
                         for p in (positions or [])}
        raised, skipped, failed = [], [], []

        for rule in checked["fired"]:
            key = (rule.get("strategy_id"), rule.get("symbol"), rule.get("kind"))
            if rule.get("triggered_at"):
                skipped.append({**rule, "why_skipped": (
                    f"already triggered at {rule['triggered_at']}; a second "
                    f"proposal would be a duplicate of one decision")})
                continue
            if rule.get("overridden_at"):
                skipped.append({**rule, "why_skipped": (
                    f"deliberately overridden at {rule['overridden_at']} with a "
                    f"recorded reason: {rule.get('override_reason')}")})
                continue

            symbol = rule.get("symbol")
            qty = qty_by_symbol.get(symbol)
            reason = rule.get("reason") or "exit condition met"

            at = datetime.now(timezone.utc).isoformat()
            order_id = None
            proposal: dict[str, Any] = {}
            if not qty:
                # No quantity means no closable position. Recorded as a trigger
                # anyway: the condition DID fire, and a silent skip here would
                # leave the operator believing the rule never fired.
                failed.append({**rule, "error": (
                    f"exit fired for {symbol} but no position quantity was "
                    f"available, so no closing order could be sized")})
            else:
                try:
                    proposal = pipeline.propose_order(
                        Order(venue="paper", symbol=symbol, side=Side.SELL,
                              qty=abs(float(qty)),
                              strategy_id=rule.get("strategy_id"),
                              rationale=(
                                  f"PRE-COMMITTED EXIT FIRED. {reason}. This rule "
                                  f"was recorded on "
                                  f"{str(rule.get('set_at'))[:10]}, before the "
                                  f"position existed, precisely so this decision "
                                  f"would not be made by someone holding it."),
                              critique=(
                                  "Closing here is the commitment, not a view. If "
                                  "you keep the position, that is allowed and it "
                                  "will be recorded as an override with your "
                                  "reason — silent overrides are the one thing "
                                  "this mechanism exists to prevent.")),
                        actor=actor)
                    order_id = proposal.get("order_id")
                except Exception as e:  # noqa: BLE001
                    failed.append({**rule, "error": f"{type(e).__name__}: {e}"})

            self._store.append(Event(
                aggregate_id=str(rule.get("strategy_id") or "fund"),
                aggregate_type="strategy",
                type=EventType.EXIT_RULE_TRIGGERED,
                payload={"strategy_id": rule.get("strategy_id"),
                         "symbol": symbol, "kind": rule.get("kind"),
                         "reason": reason, "at": at, "order_id": order_id,
                         "proposal_status": proposal.get("status")},
                actor=actor))
            if order_id:
                raised.append({**rule, "order_id": order_id,
                               "proposal_status": proposal.get("status")})

        return {
            "raised": raised, "skipped": skipped, "failed": failed,
            "holding": checked["holding"],
            "unevaluable": checked["unevaluable"],
            "note": _enforce_note(raised, skipped, failed, checked),
        }


def _enforce_note(raised: list, skipped: list, failed: list,
                  checked: dict) -> str:
    bits = []
    if raised:
        bits.append(f"{len(raised)} closing proposal(s) raised and waiting on a "
                    f"human click")
    if failed:
        bits.append(f"{len(failed)} exit(s) fired but could NOT be turned into a "
                    f"proposal — this is the worst state and needs attention")
    if skipped:
        bits.append(f"{len(skipped)} already handled")
    if checked.get("unevaluable"):
        bits.append(f"{len(checked['unevaluable'])} could not be checked — not "
                    f"the same as fine")
    if not bits:
        bits.append(f"no exit fired; {len(checked.get('holding') or [])} rule(s) "
                    f"holding")
    return "; ".join(bits)


#: An exit rule that has already TRIGGERED, or has been explicitly OVERRIDDEN,
#: is a record of a decision. It is not a control and it will not fire again:
#: ``enforce()`` skips both (see the two ``skipped.append`` branches). Coverage
#: that counts one is coverage that does not exist.
#:
#: Measured, on the live rule set, 2026-08-22 (adversary review of builder D11,
#: finding K2 — the loosening that killed the diff): the coverage block reported
#: $674.10 uncovered against $1,165.44 actually uncovered —
#:   GLD  $179.70  machinery-test loss_pct, triggered 2026-08-20T08:01:26
#:                 (on the phantom mark) AND overridden 2026-08-20T11:00:13
#:   INTC $144.90  machinery-test gain_pct, overridden 2026-08-17T17:03:56
#:   SPY  $166.74  a live rule, but on a strategy that would no longer hold it
#:
#: ``superseded`` IS DELIBERATELY NOT IN THIS TEST, and that is a correction to
#: the review's own repair specification, which asked for "not-superseded /
#: not-triggered / not-overridden". Measured against the fold rather than
#: assumed: ``_fold`` keeps exactly ONE entry per (strategy, symbol, kind) and
#: sets ``superseded=True`` on the SURVIVOR when an earlier commitment existed.
#: The flag means "this key has been REVISED"; the rule carrying it is the
#: current, governing one. ``enforce()`` does not skip it, and the fold's own
#: comment on EXIT_RULE_TRIGGERED says re-committing exists precisely so a rule
#: CAN FIRE AGAIN — a re-commitment always sets this flag, so filtering on it
#: would make the one mechanism for restoring a fired rule invisible to the
#: coverage report, and an operator who correctly re-committed would see the
#: position still flagged with no way to clear it. Verified by folding two SETs
#: on one key: n=1, threshold=the revision, superseded=True.
#:
#: The INTC case the review attributed to supersession is still reported
#: uncovered — by the OWNERSHIP key. Its live ``wiring_verification`` rule
#: belongs to a strategy that does not hold the position.
def _rule_is_live(r: dict[str, Any]) -> bool:
    return not (r.get("triggered_at") or r.get("overridden_at"))


def _why_not_live(r: dict[str, Any]) -> str:
    if r.get("triggered_at"):
        return f"already triggered at {r.get('triggered_at')}"
    if r.get("overridden_at"):
        return f"overridden at {r.get('overridden_at')}"
    return "live"


def _held_rows(rows: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Normalise whatever the caller handed us into one holding shape.

    Reads BOTH ``usd_value`` and ``value_usd``, and that is a defect fix rather
    than politeness. ``RiskMonitor.assess()`` emits ``value_usd`` (riskmonitor.py,
    the ``positions_list.append`` block) while venuesync and the attribution
    projection emit ``usd_value``; the first version of the coverage block read
    only ``usd_value``, so on the LIVE path every uncovered row carried a null
    dollar figure — verified against the running spine 2026-08-22, whose rows
    are exactly {symbol, qty, mark, value_usd, weight_pct, unrealized_pnl_pct,
    shock_20_usd}. A coverage report whose money column is always absent cannot
    be ranked by money.

    Absent stays absent: a row with neither key gets ``usd_value=None`` and is
    counted in ``uncovered_unvalued``, never as zero.
    """
    out = []
    for r in (rows or []):
        symbol = r.get("symbol")
        if not symbol:
            continue
        value = r.get("usd_value")
        if value is None:
            value = r.get("value_usd")
        out.append({"symbol": symbol,
                    "strategy_id": r.get("strategy_id"),
                    "qty": r.get("qty"),
                    "usd_value": value})
    return out


def _uncovered(rules: list[dict[str, Any]],
               held: list[dict[str, Any]]) -> dict[str, Any]:
    """Which holdings no LIVE exit rule covers, and why each one is exposed.

    Keyed on ``(strategy_id, symbol)`` when the holding names its owner. An
    exit rule is a commitment BY a strategy ABOUT a symbol: ``enforce()`` raises
    the closing SELL with ``strategy_id`` on it, and autopolicy v3 will only
    auto-approve that SELL if the rule's own strategy holds the quantity being
    sold. So a rule on strategy A does not cover strategy B's holding of the
    same ticker — it cannot even be executed against it — and scoring it as
    coverage is the same absence-as-value error in a different costume.

    When the holding does NOT name an owner (the risk monitor's rows do not),
    the weaker symbol-level test is used and ``coverage_basis`` says so. That
    is deliberately not silent: this is the exact place where a report can
    look reassuring for a reason that has nothing to do with the book.
    """
    live = [r for r in rules if _rule_is_live(r)]
    dead = [r for r in rules if not _rule_is_live(r)]
    live_pairs = {(r.get("strategy_id"), r.get("symbol"))
                  for r in live if r.get("symbol")}
    live_symbols = {r.get("symbol") for r in live if r.get("symbol")}
    any_symbols = {r.get("symbol") for r in rules if r.get("symbol")}

    uncovered: list[dict[str, Any]] = []
    bases: set[str] = set()
    for h in held:
        symbol, owner = h["symbol"], h.get("strategy_id")
        if owner:
            bases.add("strategy+symbol")
            covered = (owner, symbol) in live_pairs
        else:
            bases.add("symbol")
            covered = symbol in live_symbols
        if covered:
            continue
        if owner and symbol in live_symbols:
            others = sorted({str(r.get("strategy_id")) for r in live
                             if r.get("symbol") == symbol})
            why = (f"held by {owner}; the live exit rule(s) for {symbol} "
                   f"belong to {', '.join(others)} and cannot be executed "
                   f"against this holding")
        elif symbol in any_symbols:
            reasons = sorted({_why_not_live(r) for r in dead
                              if r.get("symbol") == symbol})
            why = (f"every exit rule for {symbol} is a record, not a control "
                   f"({'; '.join(reasons)})")
        else:
            why = "held with no pre-committed exit rule"
        uncovered.append({**h, "why": why})

    valued = [u["usd_value"] for u in uncovered if u["usd_value"] is not None]
    unvalued = [u["symbol"] for u in uncovered if u["usd_value"] is None]
    return {
        "uncovered": uncovered,
        # The sum of what could be valued, and separately WHAT COULD NOT. A
        # single total over a partly-unpriced set understates the exposure and
        # reads like a measurement of the whole thing.
        "uncovered_usd": round(sum(float(v) for v in valued), 2) if valued else None,
        "uncovered_unvalued": unvalued,
        "coverage_basis": ("strategy+symbol" if bases == {"strategy+symbol"}
                           else "symbol" if bases == {"symbol"}
                           else "mixed" if bases else "nothing held"),
        "rules_not_live": [
            {"strategy_id": r.get("strategy_id"), "symbol": r.get("symbol"),
             "kind": r.get("kind"), "why": _why_not_live(r)} for r in dead],
    }


def _note(fired: list, holding: list, unevaluable: list,
          uncovered: Optional[list] = None, *, coverage_known: bool = True,
          uncovered_usd: Optional[float] = None,
          unvalued: Optional[list] = None,
          rules_not_live: Optional[list] = None) -> str:
    uncovered = uncovered or []
    bits = []
    if not (fired or holding or unevaluable):
        bits.append("no exit rule is recorded — this position was deployed "
                    "without a pre-committed exit, which is the state this "
                    "module exists to make visible")
    if fired:
        bits.append(f"{len(fired)} exit rule(s) FIRED and need a decision")
    if holding:
        bits.append(f"{len(holding)} holding")
    if unevaluable:
        bits.append(f"{len(unevaluable)} could not be checked — not the same as "
                    f"fine")
    if uncovered:
        money = (f", ${uncovered_usd:,.2f}" if uncovered_usd is not None else "")
        # Unvalued names are called out beside the total rather than folded
        # into it: a dollar figure over a partly-unpriced set is an
        # understatement wearing a decimal point.
        gap = (f" (plus {len(unvalued)} with no readable value: "
               f"{', '.join(unvalued)})" if unvalued else "")
        bits.append(f"{len(uncovered)} held position(s) carry NO LIVE exit rule"
                    f"{money}{gap} — "
                    f"{', '.join(str(u['symbol']) for u in uncovered)}")
    elif not coverage_known:
        # The distinction the whole module is built on, applied to itself:
        # "nothing uncovered" and "we could not read the book" are different
        # claims and only one of them is reassuring.
        bits.append("coverage of held positions UNKNOWN — the book could not "
                    "be read, so this is not a report of full coverage")
    if rules_not_live:
        # Said out loud on every reading, not only when something is uncovered.
        # This is the sentence that makes the K2 correction visible instead of
        # quiet: a reader comparing today's coverage against last week's needs
        # to know that four rules stopped counting because they were never
        # controls, rather than concluding the book got worse.
        bits.append(f"{len(rules_not_live)} recorded rule(s) are NOT controls "
                    f"(superseded / already triggered / overridden) and are "
                    f"excluded from coverage")
    return "; ".join(bits)
