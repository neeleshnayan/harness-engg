"""THE TICKET FOLD — one entity, read-only.

Design: ``docs/design/TICKET_HIGHWAY_V1_2026-08-24.md`` (CEO-ratified
2026-08-24). This module implements §1.4's fold adapters and §2.2's fold, and
NOTHING ELSE: **there is no door here and no staging table.** Slice 1 shipped
value by itself — it made the desk's three existing species legible as one
lifecycle without migrating a byte of history.

SLICE 2 (2026-08-24) added the four adapters for the highway's OWN event types
— ``TicketOpened``, ``TicketTransitioned``, ``TicketLinked``,
``TicketConsumed`` (§2.1). It did NOT add a write path: the doors that append
those events live in ``app/api/v1/fund.py`` and read this fold to decide what
they may append. The direction of that dependency is the boundary — the fold
is the thing a door consults, never a thing a door is.

**THIS MODULE APPENDS NOTHING AND MUST NOT.** It reads ``store.stream`` and a
list of run rows; every function here is a pure reading. A test asserts the
absence of any write call by AST, because "read-only" is a claim and this fund
has a rule about claims nothing checks.

WHY A FOLD AND NOT A TABLE. The five species already agree on one string — the
``trace_id`` — at every joint: a request births a trace (``fund.py:1773-1777,
1818``), a dispatch continues the request's or births its own
(``fund.py:1857-1859``), a resolve carries it (``fund.py:1987``), and a
recommendation decision writes it onto the decision event
(``fund.py:2424``). What was missing was never the thread; it was that nothing
folded the thread into one thing with a state.

THE THREE LEGACY SPECIES AND THEIR MEASURED SIZES — **a dated snapshot of a
population that grows, not a constant.** Live record, 2026-08-24, reproduced by
``scratchpad/hw1_recount.py``:

  * 121 ``DeskRequested`` -> 121 ``ask`` tickets.
  * 36 ``DeskDispatched``: 12 name a ``request_id``, 24 do not. The 24 are
    chair-born work and become ``dispatch`` tickets born ``in_flight``; a 25th
    dispatch ticket comes from the one dispatch naming a request that was
    never filed.
  * 550 stored recommendations across 145 runs -> 550 ``recommendation``
    tickets, 252 of them still working.

Total 696 the moment that was run, and 695 forty minutes earlier — **the
numbers here move and the INVARIANT is what the tests pin**: one ticket per
species row, and the counts reconciling with ``desk_load``. A test asserting
"121 asks" would be red by tomorrow and would be measuring the desk's traffic
rather than this fold.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


#: Bumped when a state, a transition rule, or an adapter changes. Published in
#: the payload for the same reason ``NEXT_ACTOR_RULES_VERSION`` is: a reader
#: holding a count deserves to know which rules produced it.
TICKET_FOLD_VERSION = ("ticket fold v3 (2026-08-24) — v1's legacy adapters, "
                       "v2's four TICKET_* event types of §2.1, and v3's "
                       "decision lineage of §1.5 (one decision, one row)")

#: The type facets this fold can contain.
#:
#: ``ask`` / ``dispatch`` / ``recommendation`` have LEGACY ADAPTERS — every one
#: of them is read out of events that already exist. ``challenge`` has none and
#: never will: it is born only at the door (slice 2), and it is here because
#: §1.2's "terminal is terminal" rule points at it as the ONLY way to dispute a
#: closed ticket. Enforcing terminal-is-terminal at the transition door while
#: the escape hatch it names does not exist would be a dead end wearing a rule's
#: clothes.
#:
#: ``lesson`` ARRIVED IN SLICE 5, WITH ITS RECEIPT AND NOT BEFORE. Slice 2's
#: note here said it was deliberately absent because "a lesson ticket without
#: ``TICKET_CONSUMED`` being appended by the chair's resolve pipeline is a row
#: that can be filed and never read, which is the failure it exists to end" —
#: that condition is now met: ``POST /fund/tickets/{id}/consumed`` appends the
#: receipt and ``GET /fund/tickets/lessons`` makes the lag a number. Like
#: ``challenge`` it has NO legacy adapter and never will: pre-highway BINDS are
#: not retro-ticketed (memo §1.4), because a receipt invented for a lesson
#: nobody can prove was carried is worse than an honest absence.
TICKET_TYPES = ("ask", "dispatch", "recommendation", "challenge", "lesson")

#: The types a door may MINT. Identical to ``TICKET_TYPES`` today, and a
#: separate name rather than an alias because the two answer different
#: questions: one is "what can this fold hold", the other is "what may a caller
#: create". Slice 5 widens the first by one and the second by one, and they
#: could legitimately diverge (a species with a legacy adapter and no door).
OPENABLE_TYPES = TICKET_TYPES

#: The reversibility vocabulary, from the builder's D9 finding carried into the
#: run-record contract: ``kind`` is free text with 84 distinct values, so
#: routing on it moves 18.7% of rows. These three are a CLOSED set for exactly
#: that reason — a fourth value is a decision someone makes here, in writing,
#: rather than a string that appears one day and routes nothing.
REVERSIBILITY = ("irreversible", "hard", "reversible")

#: What a ``TICKET_LINKED`` event may assert (memo §2.1).
#:
#:   * ``parent`` — the tree: ask -> its run -> its recommendation children.
#:   * ``decision_ref`` — one decision, one row (§1.5). Slice 2 RECORDS it;
#:     slice 3 is where a decided ticket re-presented bare becomes a 409.
#:   * ``serves`` — this ticket is the artifact that serves that one.
LINK_KINDS = ("parent", "decision_ref", "serves")

#: The working states — a ticket in one of these is somebody's move.
WORKING_STATES = ("filed", "approved", "in_flight", "returned", "accepted")

#: The five terminals of memo §1.2. Terminal is terminal: no reopen transition
#: exists in this fold, and a dispute with a closed ticket is a NEW ticket.
TERMINAL_STATES = ("done", "declined", "superseded", "merged", "expired")

TICKET_STATES = WORKING_STATES + TERMINAL_STATES

#: WHICH STATES A TRANSITION MAY ADVANCE FROM — the terminal-precedence table.
#:
#: Lifted from ``desk._requests`` (desk.py:652-677) rather than re-derived, and
#: the three rules there are preserved exactly:
#:
#:   * an approval only moves an OPEN request forward (desk.py:656);
#:   * a decline lands while open or approved, never onto a resolved row
#:     (desk.py:664);
#:   * a resolution completes a request still on the path and MUST NOT
#:     overwrite a decline — executing a declined ask would be the chair
#:     overriding the CEO's no (desk.py:669-674).
#:
#: The fold is ORDER-HONEST, not last-write-wins: an event whose source state
#: is not in this table is recorded as REFUSED on the ticket, so a legacy
#: sequence that tried to revive a closed row is visible instead of applied.
#:
#: ``in_flight`` and ``returned`` are the two states ``desk._requests`` cannot
#: express. They extend the table rather than replace it: a request that is
#: dispatched keeps ``open``/``approved`` semantics in the legacy fold, which
#: is why ``done`` admits both of them and why ``legacy_status`` below collapses
#: them back for the reconciliation.
ALLOWED_FROM: dict[str, tuple[str, ...]] = {
    "approved": ("filed",),
    "in_flight": ("filed", "approved"),
    "returned": ("in_flight",),
    "accepted": ("filed", "approved", "returned"),
    "done": ("filed", "approved", "in_flight", "returned", "accepted"),
    "declined": ("filed", "approved", "in_flight", "returned", "accepted"),
    "superseded": ("filed", "approved", "in_flight", "returned", "accepted"),
    "merged": ("filed", "approved", "in_flight", "returned", "accepted"),
    "expired": ("filed", "approved"),
}

#: TRANSITIONS A HUMAN DECIDES, which therefore take the approval-channel
#: guard at the door (allowlist + confirm echo + the verbatim-instruction rule
#: for ``neelesh-via-*``). Memo §2.3 names them: ``approved``, ``accepted``,
#: ``declined``, and every terminal.
#:
#: ``in_flight`` and ``returned`` are the two that are NOT here, and the line
#: between them and the rest is "is this a judgement or a record of a fact":
#: firing a dispatch and recording that a seat came back are things the chair
#: DOES and then writes down, not permissions it grants itself.
#:
#: ``declined`` IS guarded here and is NOT guarded at the legacy
#: ``desk_decline`` door — a deliberate divergence, named rather than left to
#: be discovered. The legacy reasoning is sound for a legacy request ("closing
#: a door must never be harder than opening one", fund.py:1920-1925) and the
#: highway's terminals are stronger claims: a declined ticket is TERMINAL with
#: no reopen transition, so on this machine a decline is not the reversible act
#: it is over there. Direction is a TIGHTENING and the legacy door is
#: byte-identical, so nothing that worked yesterday works less well today.
DECISION_TRANSITIONS = ("approved", "accepted", "declined") + TERMINAL_STATES

#: TRANSITIONS THAT MOVE THE WORK FORWARD, which therefore take the
#: supersession refusal — the generalisation of ``ADVANCING_REC_STATUSES``
#: (fund.py:2552-2555, ``accepted``/``staged``/``done``).
#:
#: The three exclusions each have a reason and none of them is an oversight:
#:
#:   * ``declined`` / ``superseded`` / ``merged`` / ``expired`` — CLOSING a
#:     superseded row must stay easy. This is exactly why the legacy constant
#:     lists only the three advancing statuses; refusing to close a row because
#:     it has been superseded would strand it open forever.
#:   * ``returned`` — recording that a seat came back is a statement about
#:     something that ALREADY HAPPENED. Refusing it would leave a superseded
#:     in-flight ticket with no way to record what the seat actually produced,
#:     and the work would vanish from the record rather than from the queue.
#:     The step after it (``returned`` -> ``done``) IS advancing and IS
#:     refused, so nothing advances past a live edge.
ADVANCING_TICKET_STATES = ("approved", "in_flight", "accepted", "done")

#: WHAT EACH TERMINAL MUST CARRY (memo §1.2's table, made a door check).
#: "No citation, no close" is the Donna-sweep rule made mechanical; a decline
#: without its written reason reads identically to an unseen ask.
TERMINAL_REQUIREMENTS = {
    "done": ("citation", "the artifact or event that proves the work happened"),
    "declined": ("reason", "the written reason a human said no"),
    "superseded": ("superseder_ref", "the row that replaces this one"),
    "merged": ("decision_ref", "the canonical ticket this row duplicates"),
}

#: THE AGING POLICY, AND IT IS DELIBERATELY ABSENT.
#:
#: ``expired`` is the one terminal whose CAUSE is a sweep rather than a person,
#: and memo §1.2 says the policy behind that sweep is CEO-RATIFIED. No such
#: policy exists. So the door refuses ``expired`` while this is None, and
#: turning expiry on is a one-line versioned human change with a name in it
#: rather than a threshold nobody notices.
#:
#: Shipping the door WITHOUT this check would have given the chair a button
#: that closes aged work under no stated rule — which is how a queue gets
#: quietly emptied instead of quietly worked.
AGING_POLICY_VERSION: Optional[str] = None

#: LEGACY RECOMMENDATION STATUS -> TICKET STATE (memo §1.4).
#:
#: The memo names two of the six explicitly — ``rejected`` -> ``declined`` and
#: ``noted`` -> ``done`` (basis ``noted``), per ``desk.TERMINAL_STATUSES``
#: (desk.py:982). The other four are read off the state machine:
#:
#:   * ``open`` -> ``filed``: nobody has decided it.
#:   * ``accepted`` -> ``accepted``: decided yes, execution owed. Same word.
#:   * ``staged`` -> ``accepted``: DECISION MADE BY THIS MODULE, and named
#:     rather than buried. ``staged`` means the chair has put an accepted row
#:     through the propose path; the highway has no ``staged`` state, and
#:     ``desk.next_actor`` already treats ``accepted`` and ``staged``
#:     identically (desk.py:1098 — both route to the chair). Collapsing them
#:     therefore changes no routing answer, and the original word survives on
#:     the ticket as ``legacy_status`` so nothing is lost.
#:   * ``done`` -> ``done``.
LEGACY_REC_STATE = {
    "open": "filed",
    "accepted": "accepted",
    "staged": "accepted",
    "done": "done",
    "noted": "done",
    "rejected": "declined",
}

#: LEGACY REQUEST STATUS -> TICKET STATE, for a request that was never
#: dispatched. A dispatched one advances past these through ``in_flight``.
LEGACY_REQUEST_STATE = {
    "open": "filed",
    "approved": "approved",
    "declined": "declined",
    "resolved": "done",
}

#: WHOSE MOVE A ``dispatch`` TICKET IS.
#:
#: The one routing rule this module ADDS rather than reuses, so it is named and
#: versioned instead of inlined. A chair-born dispatch is work the chair fired
#: and owes a review on — the constitution's missing middle state — so a live
#: one is the chair's and a terminal one is nobody's, which is the same
#: terminal rule ``desk.next_actor`` applies (desk.py:1082).
#:
#: It is NOT ``desk.open_request_actor``: that function's vocabulary is
#: open/approved/resolved/declined and it defaults everything else to the CEO,
#: so an ``in_flight`` dispatch would land on the CEO's counter. Reusing a
#: function whose domain does not contain your input is how a count acquires a
#: wrong answer with a citation attached.
DISPATCH_ROUTING_VERSION = ("dispatch routing v1 (2026-08-24) — live -> chair, "
                            "terminal -> nobody")


def _payload(e: Any) -> dict[str, Any]:
    """One event's payload as a dict, for either row shape the stores use.

    The Postgres store yields dicts and the in-memory one yields ``Event``
    objects; every fold in this package handles both the same way (see
    ``desk._requests``), and a fold that handled one would be green in tests
    and blind in production.
    """
    p = (e.get("payload") if isinstance(e, dict)
         else getattr(e, "payload", None))
    return p if isinstance(p, dict) else {}


def _etype(e: Any) -> Any:
    t = e.get("type") if isinstance(e, dict) else getattr(e, "type", None)
    return getattr(t, "value", t)


def _new_ticket(ticket_id: str, *, type: str, state: str, subject: Any,
                filed_for: Any, actor: Any, at: Any, trace_id: Any,
                source: str, **extra: Any) -> dict[str, Any]:
    return {
        "ticket_id": ticket_id,
        "type": type,
        "state": state,
        "subject": subject,
        "filed_for": filed_for,
        "filed_by": actor,
        "filed_at": at,
        "trace_id": trace_id,
        "parent_id": None,
        "source": source,
        # Every state change that was APPLIED, oldest first. The list is the
        # ticket's history and the only source of every duration this module
        # publishes — no age here is ever computed from a clock the event did
        # not carry.
        "transitions": [{"from": None, "to": state, "at": at,
                         "actor": actor, "basis": "birth"}],
        # Every state change that was REFUSED by terminal precedence, kept
        # rather than dropped. A legacy sequence that tried to revive a closed
        # row is a fact about the record; silently ignoring it (which is what
        # `desk._requests` does today, correctly for its purpose) would make
        # the fold unable to report that it happened.
        "refused_transitions": [],
        **extra,
    }


def _advance(ticket: dict[str, Any], to: str, *, at: Any, actor: Any,
             basis: str, **fields: Any) -> bool:
    """Apply one transition if terminal precedence allows it. Never raises.

    Returns whether it was applied. A refused transition is RECORDED on the
    ticket — see ``refused_transitions`` — because "this never happened" and
    "this was attempted and correctly refused" are different facts and the
    second is the one that says the guard did its job.
    """
    frm = ticket["state"]
    if frm not in ALLOWED_FROM.get(to, ()):
        ticket["refused_transitions"].append(
            {"from": frm, "to": to, "at": at, "actor": actor, "basis": basis,
             "why": f"{frm!r} does not advance to {to!r} — terminal precedence "
                    "per desk.py:655-677; the fold is order-honest, not "
                    "last-write-wins"})
        return False
    ticket["state"] = to
    ticket["transitions"].append({"from": frm, "to": to, "at": at,
                                 "actor": actor, "basis": basis})
    for k, v in fields.items():
        ticket[k] = v
    return True


def _age_hours(frm: Any, to: Any) -> Optional[float]:
    """Hours between two ISO instants, or None if either cannot be read.

    Uses ``desk._ts``, which parses ``Z`` and ``+00:00`` alike and reads an
    unzoned stamp as UTC. None is the honest answer for an unparseable pair and
    every caller renders it with ``age_basis: "unknown"`` — an age this module
    cannot compute is NEVER zero, which is this fund's oldest rule.
    """
    from app.fund.desk import _ts
    a, b = _ts(frm), _ts(to)
    if a is None or b is None:
        return None
    return round((b - a).total_seconds() / 3600.0, 3)


def _ticket_next_actor(ticket: dict[str, Any],
                       row: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Whose move this ticket is: ``{actor, basis, why}``.

    REUSED, NOT REIMPLEMENTED, and that is the whole point of routing through
    here: ``desk.next_actor`` decides a recommendation's actor on the CEO's
    desk, in the COO counter and now on the highway, because a client that
    re-derived it in TypeScript once read 11 where the spine read 6
    (desk.py:1621-1625). Two answers to "whose move is it" is the defect this
    module exists to stop multiplying.
    """
    from app.fund.desk import next_actor, open_request_actor

    # A DOOR-BORN TICKET IS ROUTED BY ITS OWN DECLARATION FIRST, and this
    # branch is scoped to `source == "TicketOpened"` on purpose rather than
    # hoisted to the top: a terminal-first or declared-first rule applied to
    # the legacy species would silently move counts that slice 1's
    # reconciliation pins, and this fold's whole claim is that it agrees with
    # `desk_load`. Nothing below this block changed.
    if ticket.get("source") == "TicketOpened":
        if ticket["state"] in TERMINAL_STATES:
            return {"actor": "nobody", "basis": "lifecycle",
                    "why": f"state {ticket['state']!r} is terminal — nothing "
                           "follows it"}
        declared = ticket.get("next_actor_declared")
        if declared:
            return {"actor": declared, "basis": "explicit",
                    "why": "the ticket was filed naming whose move it is; "
                           "read, not inferred"}
        from app.fund.desk import UNDECIDED_ROUTES_TO
        # READ from desk, never copied. A ticket that names no actor is
        # undecided, and this fund already decided where undecided goes — to
        # the chair, whose job is working out whose move it is. Two copies of
        # that answer is how 54 rows landed on the CEO's desk by default.
        return {"actor": UNDECIDED_ROUTES_TO, "basis": "undecided_default",
                "why": "the ticket named no next actor; undecided routes to "
                       f"the {UNDECIDED_ROUTES_TO} (desk.UNDECIDED_ROUTES_TO)"}

    if ticket["type"] == "recommendation":
        return next_actor(row if isinstance(row, dict) else None)
    if ticket["type"] == "ask":
        actor = open_request_actor(ticket.get("legacy_status"))
        return {"actor": actor, "basis": "request_lifecycle",
                "why": f"a desk request at {ticket.get('legacy_status')!r} is "
                       f"the {actor}'s move (desk.open_request_actor)"}
    if ticket["state"] in TERMINAL_STATES:
        return {"actor": "nobody", "basis": "lifecycle",
                "why": f"state {ticket['state']!r} is terminal — nothing "
                       "follows it"}
    return {"actor": "chair", "basis": "dispatch_lifecycle",
            "why": "a chair-born dispatch is the chair's to see back and "
                   "close; see tickets.DISPATCH_ROUTING_VERSION"}


# ---------------------------------------------------------------- the fold --

def fold(store: Any, runs: Optional[Iterable[dict[str, Any]]] = None,
         runs_limit: Optional[int] = None,
         now: Optional[str] = None) -> dict[str, Any]:
    """Every legacy desk species, read as one ticket population.

    ``runs`` are deskstore run rows carrying their ``recommendations``. They
    are PASSED IN rather than fetched, for two reasons: this module must stay
    importable without a database (the rule ``desk.TERMINAL_STATUSES`` already
    follows), and the caller owns the cap.

    **``runs=None`` MEANS THE RECOMMENDATION LEG WAS NOT READ, AND IT IS
    REPORTED THAT WAY — never as zero recommendations.** The distinction is
    not hypothetical: ``DeskStore.all_runs`` does not SELECT the
    ``recommendations`` column (deskstore.py:563-575), so a fold built on it
    reports 0 recommendation tickets against a live record holding 550. That
    is a plausible, stable, entirely false number, which is the worst shape
    available. Any run row lacking the key is therefore counted in
    ``recommendations_unreadable_runs`` and flips ``recommendations_complete``
    to false, instead of contributing a silent zero.

    ``now`` is the instant ages are measured against, injectable so a test can
    pin it. Absent, it is read from the clock once, here, rather than per
    ticket — the ~700 tickets on the live record would otherwise carry ~700
    slightly different nows.
    """
    from datetime import datetime, timezone

    from app.fund.deskengine import rec_ref
    from app.fund.events import EventType

    at_now = now or datetime.now(timezone.utc).isoformat()
    # MATERIALISED ONCE, because this function iterates `runs` twice — the
    # child loop below and the census in `_counts`. Measured with a generator
    # before the fix: 550 recommendations folded and `runs_seen: 0`, because
    # the census re-listed an iterator the fold had already drained. A count
    # of zero beside 550 rows read from those same zero runs is the silent-
    # zero shape again, this time about the instrument's own coverage.
    runs = None if runs is None else list(runs)

    tickets: dict[str, dict[str, Any]] = {}
    # THE ALIAS INDEX, and it is load-bearing rather than defensive. A ticket's
    # id is its trace thread, but the legacy doors address rows by
    # ``request_id`` / ``task_id``. Measured on the live record: 10 of the 24
    # chair-born dispatches carry a ``trace_id`` DIFFERENT from their
    # ``task_id``, so a fold that keyed only on the trace would fail to apply
    # 10 dispatches' resolutions. Keying only on the task_id would instead
    # break the thread. Both, indexed.
    by_alias: dict[str, str] = {}
    rows_for_actor: dict[str, dict[str, Any]] = {}
    # Events naming an id no adapter has ever seen. THE PHANTOM COHORT: 17 on
    # the live record — 10 DeskRequestResolved and 7 DeskRequestApproved —
    # mostly the 8-character shorthand the desk itself prints, which is the
    # defect `_refuse_unknown_request` was built to stop. Counted and listed
    # here; never turned into a ticket, because a ticket born from a phantom
    # would launder the defect into a row.
    #
    # THE NUMBER IS THE FOLD'S, NOT THE CENSUS'S, and the difference is the
    # point: a raw census keyed on request_id and task_id alone calls 12
    # resolutions phantom, and this fold recovers two of them through the
    # alias index because their ids are TRACE strings. Reproduce:
    # `scratchpad/hw1_probe2.py`.
    phantom: list[dict[str, Any]] = []

    def _resolve(ident: Any) -> Optional[dict[str, Any]]:
        tid = by_alias.get(str(ident)) if ident else None
        return tickets.get(tid) if tid else None

    try:
        stream = list(store.stream(since_seq=0, limit=100_000))
    except Exception as e:  # noqa: BLE001
        # An unreadable stream makes the whole population unknown. `tickets`
        # is None, not [] — "we could not look" must never render as "there is
        # nothing there", and every consumer of this payload branches on
        # `readable` before it branches on a count.
        logger.warning("ticket fold: event stream unreadable: %s", e)
        return {"readable": False, "tickets": None, "counts": None,
                "reconciliation": None, "phantom_events": None,
                "fold_version": TICKET_FOLD_VERSION,
                "note": f"the event stream could not be read ({e}); the ticket "
                        "population is UNKNOWN, which is not the same as empty"}

    for e in stream:
        t, p = _etype(e), _payload(e)

        if t == EventType.DESK_REQUESTED.value:
            rid = p.get("request_id")
            if not rid:
                continue
            # The trace IS the id (memo §1.1). It defaults to the request_id at
            # the door (fund.py:1818); 1 live row of 121 predates the field
            # entirely, so the fallback is exercised, not decorative.
            tid = str(p.get("trace_id") or rid)
            tickets[tid] = _new_ticket(
                tid, type="ask", state="filed",
                # Seat-filed asks write `subject`/`serves` where CEO-typed ones
                # write `task`/`seat` — the same normalisation `desk._requests`
                # does at desk.py:649-650, for the same reason: an
                # unnormalized seat ask renders as a blank row.
                subject=p.get("task") or p.get("subject"),
                filed_for=p.get("seat") or p.get("serves"),
                actor=p.get("actor"), at=p.get("at"), trace_id=p.get("trace_id"),
                source="DeskRequested", request_id=rid,
                kind=p.get("kind"), legacy_status="open")
            by_alias[str(rid)] = tid
            by_alias.setdefault(tid, tid)

        elif t == EventType.DESK_DISPATCHED.value:
            task_id, seat = p.get("task_id"), p.get("seat")
            if not task_id:
                continue
            existing = _resolve(p.get("request_id"))
            if existing is not None:
                _advance(existing, "in_flight", at=p.get("at"),
                         actor=p.get("actor"), basis="dispatch",
                         dispatched_at=p.get("at"), dispatched_to=seat,
                         task_id=task_id)
                by_alias.setdefault(str(task_id), existing["ticket_id"])
                continue
            # BORN in_flight. Two populations land here and both are chair-born
            # work by the record's own reading: a dispatch with no request_id
            # (24 live), and a dispatch naming a request_id that was never
            # filed (1 live — measured, not hypothesised). The second could
            # have been dropped; giving it a ticket is what makes "every
            # existing dispatch appears exactly once" true rather than nearly
            # true, and its `orphan_request_id` says why it is here.
            tid = str(p.get("trace_id") or task_id)
            if tid in tickets:
                # Two dispatches on one trace: the second is a re-dispatch of
                # the same thread, not a second ticket.
                _advance(tickets[tid], "in_flight", at=p.get("at"),
                         actor=p.get("actor"), basis="dispatch")
                by_alias.setdefault(str(task_id), tid)
                continue
            tickets[tid] = _new_ticket(
                tid, type="dispatch", state="in_flight", subject=p.get("task"),
                filed_for=seat, actor=p.get("actor"), at=p.get("at"),
                trace_id=p.get("trace_id"), source="DeskDispatched",
                task_id=task_id, dispatched_at=p.get("at"), dispatched_to=seat,
                legacy_status=None,
                **({"orphan_request_id": p["request_id"]}
                   if p.get("request_id") else {}))
            by_alias[str(task_id)] = tid
            by_alias.setdefault(tid, tid)

        elif t == EventType.DESK_REQUEST_APPROVED.value:
            hit = _resolve(p.get("request_id"))
            if hit is None:
                phantom.append({"event": t, "id": p.get("request_id"),
                                "at": p.get("at")})
                continue
            if _advance(hit, "approved", at=p.get("at"), actor=p.get("actor"),
                        basis="decision", approved_by=p.get("actor"),
                        approved_at=p.get("at")):
                hit["legacy_status"] = "approved"

        elif t == EventType.DESK_REQUEST_DECLINED.value:
            hit = _resolve(p.get("request_id"))
            if hit is None:
                phantom.append({"event": t, "id": p.get("request_id"),
                                "at": p.get("at")})
                continue
            if _advance(hit, "declined", at=p.get("at"), actor=p.get("actor"),
                        basis="decision", reason=p.get("reason"),
                        declined_by=p.get("actor"), declined_at=p.get("at")):
                hit["legacy_status"] = "declined"

        elif t == EventType.DESK_REQUEST_RESOLVED.value:
            hit = _resolve(p.get("request_id"))
            if hit is None:
                phantom.append({"event": t, "id": p.get("request_id"),
                                "at": p.get("at")})
                continue
            # `citation` is the artifact that served it — the design's "no
            # citation, no close" rule (memo §1.2) has its field from day one
            # even though slice 1 only READS closes it did not make.
            # `DeskRequestResolved.resolution` is the ONLY field in the whole
            # log recording that something was carried out.
            if _advance(hit, "done", at=p.get("at"), actor=p.get("actor"),
                        basis="review-close", citation=p.get("resolution"),
                        resolved_at=p.get("at")):
                if hit["type"] == "ask":
                    hit["legacy_status"] = "resolved"
                # RETURNED IS NOT FABRICATED. Legacy resolves carry no separate
                # returned stage, so the fold reports it UNKNOWN rather than
                # inventing the instant the seat came back (memo §1.4).
                hit["returned_at"] = None
                hit["returned_basis"] = "unknown"

        # ------------------------------------------- the highway's own events

        elif t == EventType.TICKET_OPENED.value:
            tid = str(p.get("ticket_id") or "")
            if not tid:
                continue
            if tid in tickets:
                # AN OPEN AGAINST AN ID THAT ALREADY EXISTS DOES NOT OVERWRITE.
                # The door mints a fresh uuid4 so this cannot arrive from it;
                # it is recorded rather than dropped because a second birth on
                # one id is a fact about the record, and first-write-wins is
                # the same order-honesty `_advance` applies to every other
                # transition. A silent overwrite would let a later event
                # rewrite an earlier ticket's subject and filer.
                tickets[tid]["refused_transitions"].append(
                    {"from": tickets[tid]["state"], "to": "filed",
                     "at": p.get("at"), "actor": p.get("actor"),
                     "basis": "duplicate-open",
                     "why": "a TicketOpened named an id this fold already "
                            "holds; first write wins"})
                continue
            tickets[tid] = _new_ticket(
                tid, type=p.get("type"), state="filed",
                subject=p.get("subject"), filed_for=p.get("filed_for"),
                actor=p.get("actor"), at=p.get("at"),
                trace_id=p.get("trace_id") or tid, source="TicketOpened",
                legacy_status=None,
                # THE THREE ROUTING FIELDS, WRITTEN AT BIRTH. This is the whole
                # reason the door exists: the builder's D9 measurement found
                # `due_date` separating ZERO rows on the CEO's desk because
                # nothing has ever written it, and `kind` moving 18.7% because
                # it is free text with 84 values. Declared here, they are read
                # rather than inferred.
                next_actor_declared=p.get("next_actor"),
                due_date=p.get("due_date"),
                reversibility=p.get("reversibility"),
                money_at_stake=p.get("money_at_stake"),
                kind=p.get("kind"))
            if p.get("parent_id"):
                tickets[tid]["parent_id"] = str(p["parent_id"])
                tickets[tid]["parent_basis"] = "declared_at_birth"
            by_alias[tid] = tid

        elif t == EventType.TICKET_TRANSITIONED.value:
            hit = _resolve(p.get("ticket_id"))
            if hit is None:
                phantom.append({"event": t, "id": p.get("ticket_id"),
                                "at": p.get("at")})
                continue
            to = p.get("to")
            # THE FOLD RE-CHECKS WHAT THE DOOR ALREADY CHECKED, and that is not
            # redundant: the door reads the fold at request time and the record
            # is replayed forever afterwards. Two events racing the same ticket
            # both pass the door and only one may land, so legality has to be
            # decided HERE as well, against the state the replay actually
            # reached. `_advance` records the loser as refused rather than
            # dropping it.
            extra = {k: p.get(k) for k in
                     ("citation", "reason", "decision_ref", "superseder_ref",
                      "staged_ref", "policy_version")
                     if p.get(k) is not None}
            if _advance(hit, str(to), at=p.get("at"), actor=p.get("actor"),
                        basis=p.get("basis") or "transition", **extra):
                # The three fields the design asks a ``returned`` transition to
                # make real — the constitution's missing middle state, given a
                # timestamp that came from the event rather than from a clock.
                if to == "returned":
                    hit["returned_at"] = p.get("at")
                    hit["returned_basis"] = "ticket_transition"

        elif t == EventType.TICKET_LINKED.value:
            hit = _resolve(p.get("ticket_id"))
            if hit is None:
                phantom.append({"event": t, "id": p.get("ticket_id"),
                                "at": p.get("at")})
                continue
            kind, target = p.get("link_kind"), p.get("target_id")
            if kind not in LINK_KINDS or not target:
                continue
            if kind == "parent":
                hit["parent_id"] = str(target)
                hit["parent_basis"] = "ticket_linked"
            elif kind == "decision_ref":
                # ONE DECISION, ONE ROW (§1.5). Slice 2 RECORDS the reference;
                # the 409 that refuses a decided ticket presented bare is
                # slice 3's. Written down here so the next builder does not
                # have to infer which half exists.
                hit["decision_ref"] = str(target)
            else:
                hit.setdefault("serves", []).append(str(target))
            hit.setdefault("links", []).append(
                {"link_kind": kind, "target_id": str(target),
                 "basis": p.get("basis"), "at": p.get("at"),
                 "actor": p.get("actor")})

        elif t == EventType.TICKET_CONSUMED.value:
            hit = _resolve(p.get("ticket_id"))
            if hit is None:
                phantom.append({"event": t, "id": p.get("ticket_id"),
                                "at": p.get("at")})
                continue
            # A RECEIPT, NOT A TRANSITION. Consumption records that a lesson
            # reached a seat's brief; whether the lesson is DONE is the chair's
            # judgement at resolve and takes a transition of its own (§1.5).
            # Folding it as a state change would close the loop automatically,
            # and "the system's contribution is staging, never appending" is
            # the one rule this highway does not bend.
            hit.setdefault("consumptions", []).append(
                {"consumed_by_dispatch": p.get("consumed_by_dispatch"),
                 "seat": p.get("seat"), "at": p.get("at"),
                 "actor": p.get("actor")})

    # ------------------------------------------- recommendations as children

    recommendations_read = runs is not None
    unreadable_runs = 0
    rec_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if recommendations_read:
        for run in (runs or []):
            if not isinstance(run, dict):
                continue
            if "recommendations" not in run:
                # THE ALL_RUNS TRAP, made structural. A run row that does not
                # carry the column has UNKNOWN recommendations; counting it as
                # a run with none is exactly the silent zero this fund forbids.
                unreadable_runs += 1
                continue
            for r in (run.get("recommendations") or []):
                if isinstance(r, dict):
                    rec_rows.append((run, r))

    for run, r in rec_rows:
        run_id = run.get("run_id")
        if run_id is None or r.get("rec_id") is None:
            continue
        # THE ID IS THE CANONICAL REF, not a fresh uuid, and this is a decision
        # the memo left open. §1.1 says ids are full uuid4 "always" — true for
        # tickets BORN at a door (slice 2). A legacy recommendation has no uuid
        # of its own, and `rec_ref` is already the identity the supersession
        # store, `status_index` and the refusal machinery all key on
        # (deskengine.py:164). Minting a second identity for a row that already
        # has one is how 54 of 56 linkages rotted.
        tid = rec_ref(run_id, r["rec_id"])
        legacy = r.get("status") or "open"
        state = LEGACY_REC_STATE.get(legacy)
        if state is None:
            # AN UNRECOGNISED STATUS LANDS IN `filed` AND SAYS SO. It is NOT
            # read as one of the ten quietly: `legacy_state_recognised` goes
            # false on the row and the count rides the reconciliation, so a
            # reader can see the fold could not read it. `filed` is the safe
            # landing because it is WORKING — the row stays visible and owed,
            # where a terminal guess would delete it from every queue.
            # (An earlier version of this comment claimed the status was
            # rendered UNKNOWN and the line below then made it `filed`; the
            # comment and the code disagreed, and the code was the honest one.)
            state = "filed"
        t_row = _new_ticket(
            tid, type="recommendation", state="filed", subject=r.get("text"),
            filed_for=r.get("seat"), actor=r.get("seat"),
            at=run.get("resolved_at"),
            trace_id=r.get("trace_id") or run.get("trace_id"),
            source="deskstore.recommendations",
            run_id=run_id, rec_id=r.get("rec_id"), legacy_status=legacy,
            kind=r.get("kind"), money_at_stake=r.get("money_at_stake"),
            due_date=r.get("due_date"), reversibility=r.get("reversibility"),
            legacy_state_recognised=legacy in LEGACY_REC_STATE)
        # PARENT = THE RUN'S TICKET (memo §1.5), joined on the run's trace.
        #
        # MEASURED COVERAGE, and the denominator is the part worth stating: of
        # the 135 runs that CARRY recommendations, 18 have a trace that lands
        # on a ticket and 117 do not. (An earlier version of this comment said
        # "18 of 145 ... the other 127" — 145 is the run table's whole size,
        # and subtracting a figure counted over one population from the size of
        # another is how two numbers acquire one label.) The 117 are the FENCED
        # pre-highway cohort of memo §2.5 — counted, labelled, NEVER guessed
        # at. Reproduce: `scratchpad/hw1_recount.py`.
        parent = _resolve(run.get("trace_id"))
        if parent is not None:
            t_row["parent_id"] = parent["ticket_id"]
            t_row["parent_basis"] = "run_trace_id"
        else:
            t_row["parent_basis"] = "unlinkable_pre_highway"
        if state != "filed":
            _advance(t_row, state, at=r.get("decided_at"),
                     actor=r.get("decided_by"), basis="decision",
                     decided_by=r.get("decided_by"),
                     decided_at=r.get("decided_at"),
                     **({"basis_note": "legacy status 'noted'"}
                        if legacy == "noted" else {}))
        tickets[tid] = t_row
        rows_for_actor[tid] = r

    # ------------------------------------------------------------- finishing

    from app.fund import ticketguard

    out: list[dict[str, Any]] = []
    for tid, tk in tickets.items():
        verdict = _ticket_next_actor(tk, rows_for_actor.get(tid))
        age = _age_hours(tk.get("filed_at"), at_now)
        last_at = (tk["transitions"][-1] or {}).get("at")
        in_state = _age_hours(last_at, at_now)
        # ONE DECISION, ONE ROW, MADE VISIBLE (slice 3, memo §1.5). A ticket
        # that has ever received a decision carries it forever; `state` moves
        # on (`accepted` -> `done`) and `decided` does not. Derived here rather
        # than stored so it cannot drift from the transition list it is read
        # from, and published on the row because the door, the console and the
        # CEO's exceptions view all need the same answer — two derivations of
        # "has this been decided" is the defect this highway exists to stop
        # multiplying.
        lin = ticketguard.lineage(tk)
        tk.update({
            "decided": lin["decided"],
            "decision_count": lin["decision_count"],
            "decided_state": lin["decided_state"],
            "decided_at": lin["decided_at"],
            "decided_by": lin["decided_by"],
            "canonical_ticket_id": lin["canonical_ticket_id"],
            "decision_basis": lin["basis"],
        })
        tk.update({
            "next_actor": verdict["actor"],
            "next_actor_basis": verdict["basis"],
            "next_actor_why": verdict["why"],
            "terminal": tk["state"] in TERMINAL_STATES,
            "age_hours": age,
            # Absence is never zero, and it is never silent either: an age this
            # fold could not compute says WHY on the row.
            "age_basis": "event_timestamps" if age is not None else "unknown",
            "age_in_state_hours": in_state,
            "age_in_state_basis": ("event_timestamps" if in_state is not None
                                   else "unknown"),
        })
        out.append(tk)

    out.sort(key=lambda t: (t.get("filed_at") or ""), reverse=True)
    return {
        "readable": True,
        "tickets": out,
        "counts": _counts(out, recommendations_read, unreadable_runs,
                          runs, runs_limit),
        "reconciliation": _reconciliation(out),
        "phantom_events": phantom,
        "fold_version": TICKET_FOLD_VERSION,
        "dispatch_routing_version": DISPATCH_ROUTING_VERSION,
        "note": (
            f"{len(out)} ticket(s) folded from the existing record; nothing "
            "was migrated and nothing was written. "
            + (f"{len(phantom)} event(s) name an id no adapter has ever seen "
               "and are listed rather than ticketed — a ticket born from a "
               "phantom would launder the defect into a row. "
               if phantom else "")
            + ("recommendations were NOT read, so the recommendation leg is "
               "UNKNOWN rather than zero"
               if not recommendations_read else
               f"{unreadable_runs} run row(s) carried no recommendations "
               "column, so their recommendations are UNKNOWN rather than zero"
               if unreadable_runs else
               "every supplied run carried its recommendations column")),
    }


def _counts(tickets: list[dict[str, Any]], recommendations_read: bool,
            unreadable_runs: int, runs: Any,
            runs_limit: Optional[int]) -> dict[str, Any]:
    """The census. Every ticket lands in exactly one bucket of each partition."""
    from app.fund.desk import NEXT_ACTORS

    by_state = {s: 0 for s in TICKET_STATES}
    by_type = {t: 0 for t in TICKET_TYPES}
    # SEEDED WITH EVERY ACTOR, like its two siblings above. An actor with no
    # tickets must render as 0, not vanish from the dict — a key that
    # disappears when its count reaches zero is absence-as-silence, and a
    # client reading `by_next_actor["ceo"]` would raise on the good news.
    # Seeded FROM `desk.NEXT_ACTORS` rather than a local list, so the two
    # vocabularies cannot drift.
    by_actor = {a: 0 for a in NEXT_ACTORS}
    for t in tickets:
        by_state[t["state"]] = by_state.get(t["state"], 0) + 1
        by_type[t["type"]] = by_type.get(t["type"], 0) + 1
        by_actor[t["next_actor"]] = by_actor.get(t["next_actor"], 0) + 1
    n_runs = None
    if runs is not None:
        try:
            n_runs = len(list(runs))
        except TypeError:
            n_runs = None
    # THE SECOND WAY THE RECONCILIATION CAN SILENTLY BREAK, and unlike the
    # first it is a matter of WHEN, not IF. `desk_load`'s recommendation
    # population comes from `DeskStore.open_recommendations`, which scans the
    # newest `OPEN_RECS_RUN_CAP` runs; this fold is handed runs under the
    # caller's own, larger cap. Below the cap the two populations are the same
    # rows and the invariant holds; above it, `desk_load` is reading a strict
    # SUBSET and every leg would drift with nothing on either surface to point
    # at. The cap is READ from deskstore rather than copied — a duplicate that
    # happens to agree today is exactly what this field exists to prevent.
    from app.fund.deskstore import OPEN_RECS_RUN_CAP
    within = None if n_runs is None else n_runs <= OPEN_RECS_RUN_CAP
    return {
        "total": len(tickets),
        "working": sum(1 for t in tickets if not t["terminal"]),
        "desk_load_runs_cap": OPEN_RECS_RUN_CAP,
        # None when the run count is unknown — never True, because "we did not
        # look" must not render as "the instruments agree".
        "reconciles_with_desk_load": within,
        "terminal": sum(1 for t in tickets if t["terminal"]),
        "by_state": by_state,
        "by_type": by_type,
        "by_next_actor": by_actor,
        "unlinked_children": sum(
            1 for t in tickets
            if t["type"] == "recommendation"
            and t.get("parent_basis") == "unlinkable_pre_highway"),
        # THE COVERAGE DENOMINATOR'S HONEST HALF (memo §2.5): the fenced
        # pre-highway cohort is reported BESIDE coverage, never inside it.
        "recommendations_read": recommendations_read,
        "recommendations_complete": recommendations_read and not unreadable_runs,
        "recommendations_unreadable_runs": unreadable_runs,
        "runs_seen": n_runs,
        "runs_limit": runs_limit,
        # A run list as long as the cap it was fetched under may be truncated;
        # shorter than the cap is the whole table. The exact rule `_activity`
        # already uses for its window floor (desk.py:829-830).
        "runs_truncated": (runs_limit is not None and n_runs is not None
                           and n_runs >= runs_limit),
    }


def _reconciliation(tickets: list[dict[str, Any]]) -> dict[str, Any]:
    """THE ARITHMETIC THAT TIES THIS FOLD TO ``desk.desk_load``.

    Slice 1's acceptance criterion, made a payload field rather than a claim in
    a report: every leg below is derivable from the ticket population alone,
    and each names the ``desk_load`` figure it must equal. A test asserts the
    equalities against a ``desk_load`` computed independently from the same
    store — if the two instruments ever disagree, one of them is wrong and the
    suite says which legs.

    The three that matter, and why each is the one it is:

      * ``ask_legacy_open`` == ``desk_load.components.requests_awaiting_approval``.
        ``desk.view`` passes only ``status == "open"`` requests
        (desk.py:1776). It is NOT ``ask_filed``, and the gap between them is a
        MEASURED FINDING rather than a rounding: ``desk._requests`` has no
        ``in_flight`` state, so a request that has already been DISPATCHED
        still reads ``open`` there and still counts as a decision awaiting the
        CEO. One live row on 2026-08-24 (request ``fccb9cf3``, a UI ask with a
        builder dispatch in flight on it). The fold publishes the identity
        ``ask_legacy_open == ask_filed + ask_dispatched_while_open`` so the
        two instruments reconcile EXACTLY and the disagreement is a named
        number instead of an off-by-one somebody has to explain. Whether
        ``desk_load`` should stop counting a dispatched ask is a change to
        what a threshold counts, so it is filed, not applied here.
      * ``recommendation_working`` == ``len(open_recommendations())``. That
        call returns exactly the three non-terminal statuses
        (deskstore.py:743), which are exactly the three that fold to a working
        ticket state.
      * ``recommendation_ceo`` == ``desk_load.components.open_recommendations``
        — the CEO's own figure. ``desk_load`` counts a working row toward the
        CEO when its actor is ``ceo`` OR ``unknown`` (desk.py:1307), because a
        row whose next actor could not be read is work he may still owe.

    ``desk_load.total`` is then ``recommendation_ceo + pending_orders +
    ask_filed``, and pending orders are the one leg this fold cannot see: they
    are not a desk species. The field is named ``total_less_pending_orders``
    rather than ``total`` so nobody reads it as the whole figure.

    **TWO CONDITIONS UNDER WHICH THESE LEGS CAN DIVERGE, named here rather
    than left to be discovered when they do.**

    THE SECOND IS A MATTER OF WHEN, NOT IF, and it is the sharper of the two:
    ``open_recommendations`` scans the newest ``deskstore.OPEN_RECS_RUN_CAP``
    runs while this fold is handed runs under the caller's own, larger cap.
    Below the cap they are the same rows; above it ``desk_load`` reads a strict
    subset and every leg drifts. ``counts.reconciles_with_desk_load`` publishes
    which side of that line the payload is on — 145 runs against a cap of 200
    on 2026-08-24, so the margin is 55 runs and shrinking.

    THE FIRST: ``open_recommendations`` selects
    the three statuses it knows (deskstore.py:743); a row carrying a status
    outside the vocabulary is invisible to it and therefore to ``desk_load``,
    while this fold lands it in ``filed`` and counts it. The fold's figure is
    the more complete one, and ``recommendation_unrecognised_status`` publishes
    the difference so a reader can reconcile by subtraction instead of
    wondering. Zero on the live record 2026-08-24 — all 550 stored rows carry
    one of the six known statuses — which is exactly why it needed writing down
    before it stops being zero.
    """
    working = [t for t in tickets if not t["terminal"]]
    recs = [t for t in tickets if t["type"] == "recommendation"]
    rec_working = [t for t in recs if not t["terminal"]]
    asks = [t for t in tickets if t["type"] == "ask"]
    ceo = sum(1 for t in rec_working if t["next_actor"] in ("ceo", "unknown"))
    decided = sum(1 for t in rec_working
                  if t["next_actor"] not in ("ceo", "unknown")
                  and t.get("legacy_status") in ("accepted", "staged"))
    # COUNTED DIRECTLY, NOT BY SUBTRACTION — the same rule stated for
    # `ask_dispatched_while_open` below, which the first version of this
    # function failed to apply to its own third leg. `len(working) - ceo -
    # decided` makes the exhaustiveness test a pure arithmetic tautology: it
    # cannot fail however badly `ceo` and `decided` misclassify, because the
    # remainder absorbs every error by construction. Three independent tallies
    # that must sum is a check; two tallies and a remainder is a restatement.
    #
    # HONEST NOTE ON WHAT THIS DOES AND DOES NOT BUY, because the mutation pass
    # forced the question: the two forms are PROVABLY EQUIVALENT on today's
    # code — the three predicates are mutually exclusive and exhaustive over
    # `rec_working`, so the remainder always equals this count and reverting
    # the line kills no test (mutant M39, retired with this proof). The change
    # is not a behaviour fix. It buys the exhaustiveness test its MEANING for
    # the next edit: the day a fourth category is added, or a predicate stops
    # partitioning, the direct form fails and the remainder form absorbs it.
    elsewhere = sum(1 for t in rec_working
                    if t["next_actor"] not in ("ceo", "unknown")
                    and t.get("legacy_status") not in ("accepted", "staged"))
    ask_filed = sum(1 for t in asks if t["state"] == "filed")
    # Counted directly rather than by subtraction, so the identity below is a
    # real invariant two independent tallies must satisfy — a leg derived by
    # subtracting the other two can never disagree with them and therefore
    # tests nothing.
    ask_dispatched_open = sum(1 for t in asks if t["state"] == "in_flight"
                              and t.get("legacy_status") == "open")
    ask_legacy_open = sum(1 for t in asks
                          if t.get("legacy_status") == "open")
    return {
        "ask_tickets": len(asks),
        "ask_filed": ask_filed,
        "ask_in_flight": sum(1 for t in asks if t["state"] == "in_flight"),
        "ask_legacy_open": ask_legacy_open,
        "ask_dispatched_while_open": ask_dispatched_open,
        "dispatch_tickets": sum(1 for t in tickets if t["type"] == "dispatch"),
        "recommendation_tickets": len(recs),
        "recommendation_working": len(rec_working),
        "recommendation_ceo": ceo,
        "recommendation_decided_awaiting_execution": decided,
        "recommendation_open_elsewhere": elsewhere,
        # The named divergence condition; see this function's docstring.
        "recommendation_unrecognised_status": sum(
            1 for t in recs if t.get("legacy_state_recognised") is False),
        "total_less_pending_orders": ceo + ask_legacy_open,
        "working_tickets": len(working),
        "arithmetic": (
            "desk_load.total = recommendation_ceo + pending_orders + "
            "ask_legacy_open; ask_legacy_open = ask_filed + "
            "ask_dispatched_while_open; recommendation_working = "
            "recommendation_ceo + recommendation_decided_awaiting_execution + "
            "recommendation_open_elsewhere"),
    }
