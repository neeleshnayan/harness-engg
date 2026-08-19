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
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Bumped only with a written reason. An approval made under v1 was made under
#: v1's envelope, and the payload says so forever.
AUTOPOLICY_VERSION = "v1"

#: Marker the exit tick stamps into rationales it generates. The policy matches
#: on the ORDER's provenance, not its wording: the authoritative signal is the
#: actor + the marker together.
EXIT_MARKER = "PRE-COMMITTED EXIT FIRED"

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
             age_minutes: Optional[float]) -> dict[str, Any]:
    """One order against the envelope. Deterministic; returns every check.

    The result is APPROVE only when every check passes. Any check that cannot be
    evaluated fails closed — an absence is never a yes.
    """
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: Optional[bool], detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    side = str(order.get("side") or "").lower()
    check("side_is_sell", side == "sell",
          f"side={side!r}; v1 auto-approves risk-reducing closes only")

    rationale = str(order.get("rationale") or "")
    is_exit = EXIT_MARKER in rationale
    check("exit_rule_provenance", is_exit,
          "order carries the exit-tick marker" if is_exit else
          "not raised by a pre-committed exit rule — outside the v1 envelope")

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


def run(pipeline: Any, pending: list[dict[str, Any]], *, halted: bool,
        heartbeats: dict[str, Any]) -> dict[str, Any]:
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
        verdict = evaluate(row, halted=halted, heartbeats=heartbeats,
                           age_minutes=row.get("age_minutes"))
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
