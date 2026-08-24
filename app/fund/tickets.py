"""THE TICKET FOLD, slice 1 of the ticket highway — one entity, read-only.

Design: ``docs/design/TICKET_HIGHWAY_V1_2026-08-24.md`` (CEO-ratified
2026-08-24). This module implements §1.4's fold adapters and §2.2's fold, and
NOTHING ELSE: there is no door here, no event type, no staging table. Slice 1
ships value by itself — it makes the desk's three existing species legible as
one lifecycle without migrating a byte of history.

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
TICKET_FOLD_VERSION = "ticket fold v1 (2026-08-24)"

#: The type facets slice 1 can read. ``lesson`` and ``challenge`` are in the
#: design's table and are DELIBERATELY ABSENT here: they have no historical
#: carrier at all (memo §1.4), so retro-ticketing them would be inventing
#: rows. Absence reported as absence — they enter the highway from slice 5 on.
TICKET_TYPES = ("ask", "dispatch", "recommendation")

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

    out: list[dict[str, Any]] = []
    for tid, tk in tickets.items():
        verdict = _ticket_next_actor(tk, rows_for_actor.get(tid))
        age = _age_hours(tk.get("filed_at"), at_now)
        last_at = (tk["transitions"][-1] or {}).get("at")
        in_state = _age_hours(last_at, at_now)
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
    by_state = {s: 0 for s in TICKET_STATES}
    by_type = {t: 0 for t in TICKET_TYPES}
    by_actor: dict[str, int] = {}
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
    return {
        "total": len(tickets),
        "working": sum(1 for t in tickets if not t["terminal"]),
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

    **THE ONE CONDITION UNDER WHICH THESE LEGS CAN DIVERGE, named here rather
    than left to be discovered when they do.** ``open_recommendations`` selects
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
    elsewhere = len(rec_working) - ceo - decided
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
