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
AUTOPOLICY_VERSION = "v3"

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

    # R5 (v3): the rule's own strategy must hold what the order sells. A rule
    # registered under one strategy_id must never liquidate another strategy's
    # position — which is literally what the first live fire did.
    held = ctx.get("rule_strategy_holding_qty")
    try:
        oqty = float(order.get("qty") or 0.0)
    except (TypeError, ValueError):
        oqty = None
    if held is None or oqty is None:
        check("rule_owner_holds_position", False,
              f"the triggering rule's strategy holding could not be determined "
              f"(held={held!r}) — an unownable close does not self-execute")
    else:
        ok = oqty <= held + 1e-9
        check("rule_owner_holds_position", ok,
              f"order qty {oqty} vs {held} held by the rule's own strategy" +
              ("" if ok else " — the rule would be closing a position its "
                             "strategy does not hold"))

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
                pricer: Optional[Callable[[str], float]]) -> dict[str, Any]:
    """Gather the v2 inputs for one order from the event log and the pricer.

    One pass over the log; every failure degrades to an ABSENT field, which
    evaluate() fails closed on. The gatherer can only narrow the envelope by
    breaking, never widen it.
    """
    from app.fund.events import EventType

    oid = str(order.get("order_id") or "")
    symbol = order.get("symbol")
    ctx: dict[str, Any] = {}
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
        ctx["rule_strategy_holding_qty"] = max(
            0.0, qty_by_strategy.get(trigger.get("strategy_id"), 0.0))
    ctx["position_opened_at"] = opened_at

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
            skipped.append({"order_id": oid, "symbol": row.get("symbol"),
                            "failed_checks": [c["check"] for c in
                                              verdict["checks"]
                                              if c["ok"] is not True]})
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
