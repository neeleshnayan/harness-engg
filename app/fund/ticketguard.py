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

TWO DOORS, TWO RULES, AND THE DIFFERENCE IS DELIBERATE.

``check_representation`` guards the TICKET door (slice 3). It is the broader
rule: it refuses a decided ticket presented BARE for a decision it has already
recorded, and it accepts two escapes — cite the canonical row (``merged`` +
``decision_ref``) or name the replacement (``superseded`` + ``superseder_ref``).

``check_redecision`` guards the LEGACY door
``POST /fund/desk/runs/{run_id}/recommendations/{rec_id}`` — where all eight
R39 events actually landed. **This module abstained from that door until
2026-08-24, when the CEO decided to wire it with the numbers in front of him**
(the abstention paragraph that stood here is preserved in this file's history
and in ``git log`` for ``tests/test_ticket_decision_ref.py``, whose
``TestTheLegacyDoorIsUntouched`` existed precisely to make the day of the
change loud). The legacy rule is NARROWER than the ticket rule and the
narrowness is the whole safety argument — see ``check_redecision``.
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


# ===========================================================================
# THE LEGACY DOOR — the narrow form, wired 2026-08-24 on the CEO's decision.
# ===========================================================================

#: Bumped when the LEGACY rule changes, published on every refusal beside the
#: ticket door's own version. TWO DOORS, TWO VERSION STRINGS, on purpose: an
#: auditor reading an ``ApprovalRefused`` off ``/fund/events`` must be able to
#: tell which rule refused without inspecting the aggregate type, and the two
#: rules are genuinely different (see ``check_redecision``).
LEGACY_REDECISION_GUARD_VERSION = (
    "decision_ref_v1-legacy (2026-08-24, narrow re-decision form)")

#: The event type the legacy door writes, and therefore the only one that
#: counts as a decision on a recommendation row. Named rather than inlined
#: because ``decisions_for`` and the door's own append must agree about it, and
#: two spellings of one event name is a fold that reads zero for a year.
LEGACY_DECISION_EVENT = "DeskRecommendationDecided"


def decisions_for(events: Any, run_id: Any, rec_id: Any) -> list[dict[str, Any]]:
    """Every decision this ONE recommendation row has recorded, oldest first.

    Takes the raw event dicts for a ``desk_run`` aggregate — what
    ``EventStore.by_aggregate(run_id)`` returns — and narrows them to the
    decisions on one ``rec_id``. Pure: no store, no connection, no API import,
    so the guard is testable against a replay of the eight real R39 events
    without a spine, exactly as ``lineage`` is.

    ``rec_id`` IS COMPARED AS A STRING. The path parameter arrives as an
    ``int``, the JSONB payload round-trips whatever was written, and the
    record holds both spellings; an ``==`` on mixed types silently matches
    nothing, which would make this guard read "never decided" on every row and
    fail open forever with a green suite. That is the ``54 of 56`` linkage
    shape, and it costs one ``str()`` to not have.

    ORDER COMES FROM ``seq``, not from the payload's ``at``. ``at`` is written
    by the door from its own clock and two doors on two hosts can disagree;
    ``seq`` is the store's own total order and is what "already recorded"
    means here. Events without a ``seq`` sort last in arrival order rather
    than being dropped — an unsequenced event is still a decision.
    """
    out: list[dict[str, Any]] = []
    for i, e in enumerate(events or []):
        if not isinstance(e, dict):
            continue
        if e.get("type") != LEGACY_DECISION_EVENT:
            continue
        p = e.get("payload")
        p = p if isinstance(p, dict) else {}
        if str(p.get("rec_id")) != str(rec_id):
            continue
        if p.get("run_id") is not None and str(p.get("run_id")) != str(run_id):
            continue
        seq = e.get("seq")
        out.append({
            "seq": seq,
            "status": p.get("status"),
            "at": p.get("at"),
            # The DECIDER is the event's actor. The payload has no actor field
            # of its own, so reading `payload["actor"]` would give None on
            # every real row and put "by None" in a refusal message.
            "actor": e.get("actor"),
            "_order": (0, seq, i) if isinstance(seq, int) else (1, 0, i),
        })
    out.sort(key=lambda d: d["_order"])
    for d in out:
        d.pop("_order", None)
    return out


def redecision_lineage(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """What this row has already recorded — ``{}``-shaped, always readable.

    ``recorded_status`` is the status the row currently holds ACCORDING TO THE
    LOG, which is the fact the narrow rule compares against. Measured
    2026-08-24 over the whole log: that agrees with the ``fund_agent_runs``
    row's ``status`` column on **491 of 491** rows that carry a decision event,
    with zero disagreements — so the two instruments say the same thing today.
    The guard reads the LOG rather than the column because only the log carries
    the lineage (when, by whom, how many times); the column holds one value and
    has already been overwritten seven times on R39's row. Reproduce the
    agreement with ``scripts/instruments/hw4/redecision_census.py``.

    ``same_status_run`` is the CURRENT unbroken run of that status, not every
    occurrence of it ever. The difference is the reopen: one row in the record
    (``run-pm-sleeve-v2#15``) went ``accepted -> done -> open -> accepted ->
    staged``, and citing the pre-reopen acceptance as "when this was decided"
    would point a reader at a decision the reopen already undid.
    """
    if not decisions:
        return {"decided": False, "decision_count": 0, "recorded_status": None,
                "recorded_at": None, "recorded_by": None, "same_status_run": 0,
                "first_ever_at": None, "basis": "no_decision_events"}
    last = decisions[-1]
    status = last.get("status")
    # Walk back from the end; the run ENDS at the first event whose status
    # differs. A comprehension over every match would count the pre-reopen
    # acceptances too, which is the ever-repeat rule this one is not.
    run_len = 0
    for d in reversed(decisions):
        if d.get("status") != status:
            break
        run_len += 1
    first_of_run = decisions[len(decisions) - run_len]
    ever = [d for d in decisions if d.get("status") == status]
    return {
        "decided": True,
        "decision_count": len(decisions),
        "recorded_status": status,
        "recorded_at": first_of_run.get("at"),
        "recorded_by": first_of_run.get("actor"),
        "same_status_run": run_len,
        # DIFFERS FROM `recorded_at` ONLY ON A REOPEN, and is published anyway
        # rather than conditionally: a field that appears only sometimes is a
        # field every consumer must branch on, and the branch is where the
        # absence gets read as a zero.
        "first_ever_at": ever[0].get("at") if ever else None,
        "seqs": [d.get("seq") for d in decisions],
        "basis": "decision_events",
    }


def check_redecision(decisions: list[dict[str, Any]], *, to: Any,
                     run_id: Any, rec_id: Any) -> Optional[dict[str, Any]]:
    """The NARROW rule for the legacy door. ``None`` to allow; a dict to 409.

    **REFUSE A DECISION THAT RE-RECORDS THE STATUS THIS ROW ALREADY HOLDS.
    EVERY STATUS CHANGE PASSES UNTOUCHED.** That is the whole rule, and its
    two halves were measured before it was written
    (``scripts/instruments/hw4/redecision_census.py``, whole log, seq 1-1545,
    2026-08-24):

      * It refuses **37 of 678** decision events over five months — the
        consecutive-repeat population. Those 37 sit on **27 rows**; the worst
        is R39's ``run-triage7-decisions#1``, eight ``accepted`` events at seqs
        1122, 1123, 1195, 1201, 1202, 1203, 1253, 1281, of which this rule
        refuses the last seven.
      * It touches **none** of the **136 rows carrying a genuine multi-status
        progression** (``accepted -> done`` and its kin), because none of those
        transitions re-records a status the row already holds.

    NOTE THE NUMBER THE BRIEF FOR THIS WORK CARRIED, because it is a label
    slip worth not repeating: "28 same-status repeats — 13 accepted, 12 done,
    3 staged". Those three legs are exact, but they count **ROWS carrying at
    least one repeat**, not events. The event figures are 37 (consecutive) and
    38 (ever-repeat). The refusal count of this control is 37.

    **WHY CONSECUTIVE AND NOT "EVER RECORDED".** Exactly one row in the whole
    record is ``A -> B -> A``: ``run-pm-sleeve-v2#15`` went ``accepted ->
    done -> open -> accepted -> staged``. A rule reading "has this row ever
    recorded ``accepted``" would have refused that fourth event — a genuine
    re-acceptance after a genuine reopen. A control that refuses correct work
    is not a stricter control; it is a broken one, and this module's own first
    draft made exactly that mistake one dispatch ago (see the paragraph inside
    ``check_representation``). The measured cost of getting it wrong is one
    real row; the measured benefit of the narrow form is 37 of the 38.

    **WHY THERE IS NO STATUS CARVE-OUT, unlike ``REDECISION_GUARDED``.** The
    ticket rule excludes ``declined`` and the terminals so that closing a row
    never becomes harder than opening it. That concern does not arise here,
    and the reason is structural rather than a judgement call: this rule
    refuses status ``S`` only when the row ALREADY holds ``S``, so for every
    row and every other status the door is exactly as open as it was. No row
    can be trapped, because the only thing refused is the transition that
    would change nothing. A ``done`` row can still be reopened, rejected,
    re-accepted or noted; it merely cannot be marked ``done`` twice.

    **THIS GUARD CANNOT STOP A RE-PRESENTATION** — the same subject filed as a
    fresh ``(run_id, rec_id)``, which is the OTHER half of the R39 defect and
    the larger one (a dozen-odd distinct identities). Nothing about a new row
    is visible from this row's history. Named here so the control is not read
    as doing more than it does; ``check_representation`` and the ticket
    highway are where that half lives.
    """
    # A blank or absent target cannot equal a recorded status in any
    # meaningful sense, and comparing two Nones would refuse every decision on
    # a row whose last payload was malformed. Fail open, loudly, on nonsense.
    if not isinstance(to, str) or not to:
        return None
    lin = redecision_lineage(decisions)
    if lin["recorded_status"] != to:
        return None
    prior = lin["same_status_run"]
    return {
        "refused": True,
        "guard": LEGACY_REDECISION_GUARD_VERSION,
        "hint": "already_at_this_status",
        "kind": "desk_recommendation",
        "run_id": run_id,
        "rec_id": rec_id,
        "row_ref": f"{run_id}#{rec_id}",
        "attempted": to,
        "recorded_status": lin["recorded_status"],
        "recorded_at": lin["recorded_at"],
        "recorded_by": lin["recorded_by"],
        "prior_same_status": prior,
        "decision_count": lin["decision_count"],
        "first_ever_at": lin["first_ever_at"],
        # `prior` COUNTS THE EVENTS ALREADY ON THE RECORD, so it is 1 the first
        # time this refusal fires and 8 on R39's ninth attempt. An earlier
        # draft said "N time(s) since", which read as "N MORE times after the
        # first" and was wrong by one at every value — the kind of sentence a
        # suite cannot see and a reader trusts.
        "detail": (
            f"ONE DECISION, ONE ROW. {run_id}#{rec_id} already records "
            f"{to!r} — recorded {prior} time(s), first at "
            f"{lin['recorded_at']} by {lin['recorded_by']}, out of "
            f"{lin['decision_count']} decision(s) on this row in total. "
            f"Re-recording a status the row already holds writes a second "
            f"event that changes nothing and makes one decision look like "
            f"two. Any status CHANGE is accepted as before; if this row needs "
            f"to move, send the status it should move TO."),
    }


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
