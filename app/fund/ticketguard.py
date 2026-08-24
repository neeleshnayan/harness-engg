"""ONE DECISION, ONE ROW — the decision_ref guard (ticket highway slice 3).

Design: ``docs/design/TICKET_HIGHWAY_V1_2026-08-24.md`` §1.5, failure #2 in its
own falsifiability table: *"One decision, eight rows (R39)"*.

**THE MEASUREMENT THIS MODULE EXISTS FOR, AND ITS SHAPE IS NOT WHAT THE PHRASE
SUGGESTS.** Pulled from the live record 2026-08-24 and reproducible with
``python scripts/instruments/hw3/r39_census.py --subject R39`` (the instrument
is shelved in the repo, not in a session scratchpad, and it REFUSES on an
empty population), the R39 approval decision appears as:

  * **EIGHT ``DeskRecommendationDecided`` events at seq 1122, 1123, 1195, 1201,
    1202, 1203, 1253, 1281 — all naming the SAME identity**
    (``run_id="run-triage7-decisions"``, ``rec_id=1``, status ``accepted``
    every time). One row, decided eight times. That is the RE-DECISION shape.
  * **Separately, the same subject re-presented across a DOZEN-ODD DISTINCT
    identities** — ``run-pm-r39#1``, ``run-coo-triage7#1``, ``run-cfo-6#2``,
    ``run-pm-0908#1``, ``run-coo-3#2``, ``run-riskofficer-6#1``,
    ``run-pm-programme#2``, ``run-secretary-0823#1``, ``run-builder-d35#2``,
    ``run-adversary-d11#1``, ``run-pm-goldsizing#3`` and the two
    ``run-triage7-decisions`` rows above. That is the RE-PRESENTATION shape,
    and it is the one the memo's ``decision_ref`` sentence is written against.

  **DO NOT QUOTE THE SECONDARY TOTALS; QUOTE THE INVARIANT.** Two readings
  taken about an hour apart on 2026-08-24 gave *23 decision events over 12
  identities* and then *24 over 13* — a new row (``run-pm-goldsizing#3``)
  appeared and ``run-pm-0908#1`` gained a second decision between them. That is
  a live desk on an append-only log, so these numbers can only GROW, and the
  first version of this docstring went stale inside the same dispatch that
  wrote it (found by the Gauntlet's number re-count). What does not move is
  ``decision_events > distinct_identities`` — the statement "something here was
  decided more than once" — and the eight seqs above, which are fixed history.

  BOTH READINGS ARE ALSO LOWER BOUNDS. ``GET /fund/events`` caps at 1000 and
  serves the NEWEST 1000; the window these came from spanned seq 543-1542, so
  everything before 543 was never compared. The instrument now prints
  ``covers_whole_log: false`` and says so.

Both are the same defect wearing two costumes: **a decision that was already
made being asked for again**, once against its own row and once against a fresh
one. Neither is visible to any existing control, because nothing anywhere holds
"this has already been decided" as a first-class fact.

WHAT THIS MODULE IS. Pure functions over a ticket dict produced by
``app.fund.tickets.fold``. It reads; it never appends, never opens a
connection, and never imports the API layer — the door calls IT, which is the
same direction of dependency the fold already insists on. That is what makes it
testable against a replay of the eight real events without a spine.

WHAT IT DELIBERATELY DOES NOT DO, stated so nobody reads more into it. **The
legacy ``POST /fund/desk/runs/{run_id}/recommendations/{rec_id}/decide`` door —
where all eight of those events actually landed — is UNTOUCHED by this module.**
Wiring the guard into that door would change the behaviour of a live,
approval-adjacent path that the CEO's desk posts to today, and would refuse
decisions that the record shows the chair genuinely makes. That is a decision
for a human with the numbers in front of them, not a side effect of a slice.
This guard protects the ticket door, which has no legacy callers at all.
"""

from __future__ import annotations

from typing import Any, Optional

#: Bumped when the rule changes, published on every refusal. A caller told
#: "refused" deserves to know which version of the rule refused it — the same
#: reason ``approval-channel guard v1`` names itself inside its own reason
#: string (``_guard_approval`` in app/api/v1/fund.py).
DECISION_REF_GUARD_VERSION = "decision_ref_v1 (2026-08-24, highway slice 3)"

#: THE TRANSITIONS THAT ASSERT A DECISION ON THE SUBSTANCE, and therefore the
#: ones a SECOND RECORDING OF THE SAME ONE is a re-presentation. Note the
#: precision: the guard fires on ``to`` matching a decision this ticket has
#: ALREADY recorded, not on the ticket having been decided at all — see
#: ``check_representation`` for the lifecycle the looser reading broke.
#:
#: ``approved`` and ``accepted`` only. The line is between DECIDING and
#: CLOSING, and it is drawn exactly where ``ADVANCING_REC_STATUSES`` draws its
#: own (``ADVANCING_REC_STATUSES`` in app/api/v1/fund.py, and the reason
#: written above it):
#:
#:   * ``declined`` is EXCLUDED even though ``tickets.DECISION_TRANSITIONS``
#:     contains it. A decline after an acceptance is a REVERSAL — the memo's
#:     own state machine has ``accepted --> declined : human reverses before
#:     execution`` (§1.2) — and it CLOSES the row. Refusing it bare would make
#:     a wrongly-accepted ticket harder to withdraw than it was to accept,
#:     which is the strand-open failure the legacy constant exists to avoid.
#:     Its mandatory written reason is the record of the reversal.
#:   * The four terminals are EXCLUDED for the same reason: closing must never
#:     be harder than opening. ``merged`` and ``superseded`` are moreover the
#:     two LEGAL outcomes this guard steers a re-presentation toward, so
#:     refusing them would leave a decided ticket with nowhere to go.
#:
#: The consequence, named rather than left to be discovered: this guard cannot
#: stop a decided ticket being CLOSED twice in different ways. Terminal
#: precedence in ``tickets._advance`` is what stops that, and it stops it in
#: the fold where a race cannot get past it.
REDECISION_GUARDED = ("approved", "accepted")


def _applied_decisions(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    """Every APPLIED transition on this ticket that asserted a decision.

    Reads ``transitions`` — the list ``tickets._advance`` appends to only when
    a transition was actually applied — and never ``refused_transitions``. A
    refused attempt is a fact about the record, not a decision that was made,
    and counting one as a prior decision would let a rejected event lock a row.

    ``DECISION_TRANSITIONS`` is READ from ``tickets``, never restated here.
    Two copies of "which transitions are decisions" is the shape that let one
    client read 11 where the spine read 6 (app/fund/desk.py, the comment
    above ``next_actor``'s re-derivation warning).
    """
    from app.fund.tickets import DECISION_TRANSITIONS
    out = []
    for t in ticket.get("transitions") or []:
        if not isinstance(t, dict):
            continue
        # The birth row is not a decision: `_new_ticket` writes
        # `{"from": None, "to": <birth state>, "basis": "birth"}`, and a
        # recommendation folded straight into `accepted` from its legacy
        # status is born there. Filtering on `from is None` would ALSO drop a
        # genuine `filed -> accepted`, so the filter is on the basis.
        if t.get("basis") == "birth":
            continue
        if t.get("to") in DECISION_TRANSITIONS:
            out.append(t)
    return out


def lineage(ticket: dict[str, Any]) -> dict[str, Any]:
    """What this ticket's decision history is — ``{}``-shaped, always readable.

    A TICKET THAT HAS EVER RECEIVED A DECISION CARRIES IT FOREVER (memo §1.5).
    This is the fold-side half of that sentence: the state field can move on
    (``accepted`` -> ``done``), and the fact that a human decided remains
    derivable from the transition list, which is append-only by construction.

    ``canonical_ticket_id`` is the row a reader should go to: the
    ``decision_ref`` if this row was merged into another, otherwise itself. It
    does NOT chase a chain — a decision_ref pointing at a row that was itself
    merged returns that row, and the caller may follow it again. One hop per
    call, because a cycle in the data would otherwise hang the door, and the
    door is not the place to discover that the record has a cycle.
    """
    decisions = _applied_decisions(ticket)
    last = decisions[-1] if decisions else None
    ref = ticket.get("decision_ref")
    return {
        "decided": bool(decisions),
        "decision_count": len(decisions),
        "decided_state": last.get("to") if last else None,
        "decided_at": last.get("at") if last else None,
        "decided_by": last.get("actor") if last else None,
        "decisions": decisions,
        "decision_ref": ref,
        "superseder_ref": ticket.get("superseder_ref"),
        "canonical_ticket_id": ref or ticket.get("ticket_id"),
        # Absence is never zero and never silent: a ticket with no transition
        # list at all (an unreadable or hand-built row) reports that it could
        # not be read rather than "never decided".
        "basis": ("transitions" if ticket.get("transitions") is not None
                  else "unknown"),
    }


def check_representation(ticket: dict[str, Any], *, to: str,
                         decision_ref: Optional[str] = None,
                         superseder_ref: Optional[str] = None,
                         ) -> Optional[dict[str, Any]]:
    """The §1.5 rule. ``None`` to allow; a refusal dict to 409.

    A TICKET ASKED FOR A DECISION IT HAS ALREADY RECORDED IS REFUSED, and the
    two escapes are the memo's own: cite the canonical decision (``merged`` +
    ``decision_ref``) or say what this replaces (``superseded`` +
    ``superseder_ref``). Presenting the same acceptance a second time with
    neither is the R39 shape, and it is the whole of what this function stops.
    Note the precision — ALREADY RECORDED **THIS** DECISION, not "has ever been
    decided"; the paragraph inside the function says what the looser reading
    broke.

    THE REFUSAL CARRIES THE LINEAGE, not just a no. The caller's next move is
    almost always "merge into the row that already holds this decision", and it
    cannot make that move without the id — so the id is on the refusal. That is
    the ``_refuse_if_superseded`` shape and the ``did_you_mean`` shape applied
    to a third guard: a refusal that does not tell you what to do instead is a
    puzzle. (Both are in ``app/api/v1/fund.py``; cited by NAME rather than by
    line because that file is being edited by two builders today and a line
    number written now is wrong by the time it is read.)
    """
    if to not in REDECISION_GUARDED:
        return None
    lin = lineage(ticket)
    # THE SAME DECISION AGAIN — not merely a second decision. This distinction
    # is a DEFECT I wrote and then caught in the read-through, and it is worth
    # the paragraph because the wrong version passed 57 tests.
    #
    # The first version refused any guarded transition on a ticket that had
    # EVER been decided. That breaks the ordinary lifecycle: `filed ->
    # approved -> in_flight -> returned -> accepted` contains two legitimate
    # decisions (the CEO blessing the ask, then the human deciding yes on the
    # output), and the guard would have refused the second on every ticket that
    # ever got approved. A control that refuses correct work is not a stricter
    # control; it is a broken one, and it would have been discovered by the
    # first real user rather than by me.
    #
    # R39's shape is narrower and exact: the row is ALREADY at `accepted` and
    # is asked for `accepted` again — eight times. So the predicate is "this
    # ticket has already recorded a decision to THIS state".
    prior = [t for t in lin["decisions"] if t.get("to") == to]
    if not prior:
        return None
    # AN ACCOMPANIED RE-PRESENTATION IS NOT A BARE ONE — but it must land on
    # the terminal that matches what it claims. Supplying `decision_ref` while
    # asking for a second `accepted` is the worst shape available: it looks
    # like compliance and produces a second live row anyway.
    if decision_ref or superseder_ref:
        return _refusal(
            ticket, lin, to, prior=prior,
            detail=(
                f"ticket {ticket.get('ticket_id')} already recorded {to!r} "
                f"(at {prior[-1].get('at')} by {prior[-1].get('actor')}), and "
                f"a re-presentation that cites a "
                f"reference must land on the terminal that reference means: "
                f"decision_ref -> 'merged', superseder_ref -> 'superseded'. "
                f"You asked for {to!r}, which would leave a second live row "
                f"holding the same decision — the exact outcome the reference "
                f"was supposed to prevent."),
            hint="wrong_terminal_for_reference")
    return _refusal(
        ticket, lin, to,
        detail=(
            f"ONE DECISION, ONE ROW. Ticket {ticket.get('ticket_id')} has "
            f"already recorded {to!r} — {len(prior)} time(s), most recently at "
            f"{prior[-1].get('at')} by {prior[-1].get('actor')}. "
            f"A decided ticket may not be presented bare for {to!r}. Two legal "
            f"outcomes: transition to 'merged' with decision_ref="
            f"{lin['canonical_ticket_id']!r} if this is the SAME decision, or "
            f"to 'superseded' with a superseder_ref naming the row that "
            f"replaces it if it is a NEW one. Design §1.5."),
        hint="bare_representation", prior=prior)


def _refusal(ticket: dict[str, Any], lin: dict[str, Any], to: str, *,
             detail: str, hint: str,
             prior: Optional[list] = None) -> dict[str, Any]:
    return {
        # HOW MANY TIMES THIS EXACT DECISION WAS ALREADY RECORDED, beside the
        # total. R39 is 8 of one; a ticket with two different decisions in a
        # normal lifecycle is 2 of the total and 1 of this one, and the two
        # numbers are the difference between the defect and the lifecycle.
        "prior_same_state": len(prior or []),
        "refused": True,
        "guard": DECISION_REF_GUARD_VERSION,
        "hint": hint,
        "ticket_id": ticket.get("ticket_id"),
        "attempted": to,
        "state": ticket.get("state"),
        "decided_state": lin["decided_state"],
        "decided_at": lin["decided_at"],
        "decided_by": lin["decided_by"],
        "decision_count": lin["decision_count"],
        "canonical_ticket_id": lin["canonical_ticket_id"],
        "decision_ref": lin["decision_ref"],
        "detail": detail,
    }


# THE ORPHAN THAT WAS HERE — deleted, and the deletion is the finding.
#
# `terminal_requirement(to, fields)` lived here for most of this dispatch: a
# pure re-implementation of §1.2's terminal table ("no citation, no close") with
# six tests over it. The Gauntlet's shared-word pass found that NOTHING CALLED
# IT. Slice 2's `ticket_transition` had landed its own inline version of the
# same rule, reading the same two constants, while I had deleted the door that
# would have called mine.
#
# So it was a control with no caller sitting beside a control with one — the
# unwired-kill-switch pattern in its politest costume, made worse by having a
# green test class that LOOKED like the door was guarded from here. Two copies
# of "no citation, no close" is exactly what the docstring of the deleted
# function warned against, one paragraph above its own duplication.
#
# Deleted rather than wired, because slice 2's version is strictly better: it
# also requires an `expired` sweep to NAME its policy version. `merge_target_
# error` below stays, and stays because `ticket_transition` calls it.


def merge_target_error(ticket_id: str, decision_ref: Optional[str],
                       known_ids: set[str]) -> Optional[str]:
    """Why this ``merged`` may not point where it points, or ``None``.

    THE LINEAGE MUST LAND SOMEWHERE REAL. A ``decision_ref`` naming a ticket
    the fold has never seen is a phantom link — the same defect
    ``_refuse_unknown_request`` was built to stop at the resolve door, one
    layer up: it would return 200, write an edge to nothing, and leave a reader
    following a pointer into empty space. And a row cannot merge into itself;
    ``Supersessions.add`` already refuses the self-edge for the same reason
    (deskengine.py:729-730).
    """
    ref = (decision_ref or "").strip()
    if not ref:
        return None          # the door's own terminal-requirement check
                             # already refuses the empty field, with its own
                             # message; two sentences for one missing field is
                             # worse than one
    if ref == ticket_id:
        return ("a ticket cannot be merged into itself — decision_ref must "
                "name the canonical row that already holds the decision")
    if ref not in known_ids:
        return (f"decision_ref {ref!r} names no ticket this fold has ever "
                f"seen. Refused rather than recorded: an edge pointing at "
                f"nothing returns 200 and leaves a reader following a pointer "
                f"into empty space")
    return None
