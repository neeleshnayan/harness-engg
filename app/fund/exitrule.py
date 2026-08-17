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
                rules[key] = {**p, "superseded": key in rules}
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
              strategy_id: Optional[str] = None) -> dict[str, Any]:
        """Evaluate every active rule against current marks.

        ``positions`` are the risk monitor's rows: symbol and
        ``unrealized_pnl_pct``. Returns fired, holding and unevaluable
        separately, because "could not check" is not "fine".
        """
        pnl = {p.get("symbol"): p.get("unrealized_pnl_pct")
               for p in (positions or [])}
        fired, holding, unevaluable = [], [], []
        for r in self.active(strategy_id):
            got = evaluate(r, unrealised_pnl_pct=pnl.get(r.get("symbol")))
            row = {**r, **got}
            (fired if got["fired"] is True
             else holding if got["fired"] is False
             else unevaluable).append(row)
        return {
            "fired": fired,
            "holding": holding,
            "unevaluable": unevaluable,
            "note": _note(fired, holding, unevaluable),
        }


def _note(fired: list, holding: list, unevaluable: list) -> str:
    if not (fired or holding or unevaluable):
        return ("no exit rule is recorded — this position was deployed without a "
                "pre-committed exit, which is the state this module exists to "
                "make visible")
    bits = []
    if fired:
        bits.append(f"{len(fired)} exit rule(s) FIRED and need a decision")
    if holding:
        bits.append(f"{len(holding)} holding")
    if unevaluable:
        bits.append(f"{len(unevaluable)} could not be checked — not the same as "
                    f"fine")
    return "; ".join(bits)
