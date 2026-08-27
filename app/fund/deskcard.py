"""What a desk row LOOKS LIKE to the one human who has to decide it.

THE INCIDENT THIS MODULE IS NAMED AFTER (CEO, 2026-08-24, verbatim): *"Why is
this issue persisting; shakes my confidence that information is flowing
seemlessly in the org."*

His clicks land. The write path is event-sourced and sound — every accept in the
log is there, in order, with its actor. What fails is the READ path: the fold
that turns those events back into the sentences on his screen. Four separate
defects, all of the same shape and all measured against the live spine on
2026-08-24 before a line of this was written:

  * **2 of 227 rows on his desk rendered as a raw Python dict repr**
    (``run-cfo-8`` recs 1 and 2, both ``accepted``). ``deskstore.record_run``
    stored ``str(r.get("text") or r)``, so a recommendation filed with a
    ``title`` key and no ``text`` key stored its own ``{'id': 'O4', 'title':
    ...}`` as the display line.
  * **14 of the 34 rows on his decision list are at status ``accepted`` with
    the next move still his** — the constitution's preserved COO objection,
    41% of that page — and they render identically to the 20 nobody has
    decided. He accepted R39 (seq 1281) and the row came back looking exactly
    as it had. A successful click and a dead click were the same picture.
  * **52 rows were adjudicated by the chair alone** (``co-cto`` 39, ``cto``
    13) and 11 more by ``neelesh-via-cto``, against 122 by the CEO — and the
    desk labels every one of them the same way. CEO, same session: *"your desk
    on the UI only marks items as CEO approved... I cant form a view of whats
    closed and adjudicated by you."*
  * **A supersession stated in prose is invisible.** The edge TABLE is empty
    (``blocked: 0``, ``kill_shelf: 0`` live), while three decision notes and
    one resolution say in English that a row was superseded, naming the
    superseder.

EVERY FUNCTION HERE IS PURE AND READ-ONLY. Nothing writes, nothing decides,
nothing routes: this module turns a stored row into the fields a renderer
needs, and each one degrades to ABSENCE rather than to a guess. That is not
decoration — the last time this desk guessed, it guessed a completion out of
English prose, and the repair note in ``desk.next_actor`` is still there.

WHY A SEPARATE MODULE. ``desk.py`` is 2,461 lines and already carries the
routing fold, the counter, the matrix and the CEO surface. These are card
RENDERING questions, they are pure, and they want to be mutation-tested on
their own. ``deskengine.py`` and ``deskstore.py`` set the precedent: a focused
module beside ``desk.py``, imported by it, never importing it back.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Optional

# ============================================================================
# P-1 — a dict payload renders its text, never its repr
# ============================================================================

#: Where a display line may be read from, in order. ``text`` first because it is
#: what ``record_run`` asks for and what almost every seat writes; ``title``
#: second because it is what the two live broken rows actually carry; then the
#: request-card spec's own field names, so a row filed under the 2026-08-24
#: schema renders without a second rule.
#:
#: A CLOSED LIST, and deliberately short. The temptation is to add ``detail`` or
#: ``body`` as a last resort so that every row gets SOMETHING — that is how a
#: card ends up leading with a paragraph. A dict with none of these keys has no
#: headline, and this module says so.
DISPLAY_KEYS = ("text", "title", "headline", "summary")

#: Where the REST of a dict payload's prose lives once the headline is taken.
#: Rendered behind the details toggle, never on the card face.
DETAIL_KEYS = ("detail", "incident", "body", "note")

#: The longest string this module will try to read as a Python literal. A repr
#: is short by nature; a genuine memo is long. Bounding it means a seat that
#: legitimately writes a 40kB report starting with a brace costs one length
#: check rather than a parse of the whole thing.
_LITERAL_MAX = 20_000


def _clean(v: Any) -> Optional[str]:
    """A non-empty display string, or None. Never coerces a non-string."""
    if not isinstance(v, str):
        return None
    s = v.strip()
    return s or None


def _as_mapping(raw: Any) -> Optional[dict]:
    """``raw`` as a dict, INCLUDING the case where it is a dict's repr.

    The second case is the whole reason this exists. Two rows are already
    stored as ``"{'id': 'O4', 'title': ...}"`` — a string, in the database,
    that a fix at the filing door can never reach. ``ast.literal_eval`` parses
    exactly the constant literals Python's repr emits and executes nothing, so
    reading one back is safe in a way ``eval`` would not be.

    Anything that is not a dict when parsed — a list, a number, a malformed
    fragment — returns None and the caller keeps the original string verbatim.
    A partial parse is not a better guess than no parse.
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not (s.startswith("{") and s.endswith("}")) or len(s) > _LITERAL_MAX:
        return None
    try:
        parsed = ast.literal_eval(s)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return None
    return parsed if isinstance(parsed, dict) else None


def card_text(raw: Any) -> dict[str, Any]:
    """The headline, the detail behind the toggle, and where each came from.

    Returns ``{headline, detail, basis, from_dict}``:

      * ``headline`` — the card's one line, or None when the payload carries no
        readable display key. **None is a fact, not a blank**: the caller
        renders "this row has no readable headline" rather than a repr, and
        rather than inventing one out of whatever field sorted first.
      * ``detail`` — the rest, for the collapsed section. None when there is
        none.
      * ``basis`` — which key the headline came from, or ``"verbatim"`` for a
        plain string, or ``"unreadable"``. Published so a reader who disagrees
        with the choice can see it without opening the source, exactly as
        ``next_actor`` publishes its basis.
      * ``from_dict`` — whether a dict (or a dict's repr) was found. This is
        the flag that says the P-1 repair FIRED on this row.

    NOTHING IS CONCATENATED AND NO PUNCTUATION IS INVENTED. The first cut
    joined title and detail into one string so the client's existing
    first-sentence splitter would produce the same two parts — and that
    splitter looks for terminal punctuation, which the live titles do not have,
    so the join would have put the headline boundary in the middle of the
    detail. Two fields out is honest; one field out with a fabricated full stop
    is a rendering bug wearing a convenience.
    """
    mapping = _as_mapping(raw)
    if mapping is None:
        s = _clean(raw)
        return {"headline": s, "detail": None,
                "basis": "verbatim" if s else "unreadable",
                "from_dict": False}

    headline = basis = None
    for k in DISPLAY_KEYS:
        headline = _clean(mapping.get(k))
        if headline:
            basis = k
            break

    detail = None
    for k in DETAIL_KEYS:
        detail = _clean(mapping.get(k))
        if detail:
            break

    return {"headline": headline, "detail": detail,
            "basis": basis or "unreadable", "from_dict": True}


def recommendation_text(raw: Any) -> str:
    """What the FILING DOOR stores as a recommendation's ``text``.

    The headline when one can be read; otherwise the raw rendering, UNCHANGED.

    The fallback keeps a repr rather than storing a blank, and that is a
    deliberate choice against this module's own absence rule. The rule says an
    absent value is reported absent — it does not say a present value may be
    deleted. A dict with no display key still contains everything the seat
    meant; storing "" would destroy the only copy, and the read path
    (``card_text`` again, on the way out) can still show the row honestly. The
    door narrows what gets written; it never throws away what was sent.
    """
    parts = card_text(raw)
    return parts["headline"] or str(raw).strip()


# ============================================================================
# P-3 — a supersession stated in prose, only when it NAMES its superseder
# ============================================================================

#: The phrasings the record actually uses, measured over the live corpus
#: (2026-08-24: 3 recommendation notes and 7 request resolutions matched a
#: word-level search). Anchored on a following ``by``/``as`` because the bare
#: word is a description — "Closed as SUPERSEDED, never cleared" states a
#: status, not an edge, and has no superseder to link to.
_SUPERSEDED_RE = re.compile(
    r"\b(?:supersed|supercid|supercede|superced)\w*\s+by\b"
    r"|\bre-?filed\s+as\b"
    r"|\breplaced\s+by\b",
    re.IGNORECASE,
)

#: How far past the phrase an identifier may sit and still be its object.
#:
#: SIXTY, and the number is measured rather than chosen for roundness. The one
#: true edge in the live corpus reads "SUPERSEDED BY THE R39 PLAN
#: (run-pm-r39)" — 21 characters from the phrase to the id. The nearest false
#: positive is "SUPERSEDED BY THE RECORD, closed under v2: ... the v4.3 bundle
#: (882a660" at 96 characters, and it is not an identifier under the rules
#: below in any case. Sixty clears the real one twice over and still refuses a
#: sentence that wandered off.
_TARGET_WINDOW = 60

#: What counts as NAMING a row. Three shapes, all of them things this firm
#: actually mints; anything else is prose.
#:
#:   * a canonical ref — ``rec:run-x#3`` / ``req:<id>`` (``deskengine`` mints
#:     these and they are unambiguous);
#:   * a run id — ``run-pm-r39``;
#:   * a request id — the 8-or-more hex head of a uuid.
#:
#: THE HEX RULE REQUIRES A DIGIT, and that is not fussiness. ``[0-9a-f]{8}``
#: matches ordinary English words — ``defaced``, ``facade`` with a letter
#: either side — and a parser that linked a desk row to the word "deadbeef"
#: would be fabricating an edge on the CEO's control surface, which is the
#: exact failure this whole dispatch exists to remove. Requiring one digit
#: costs nothing (every real id has several) and removes the whole class.
_TARGET_RES = (
    re.compile(r"\b(rec:[A-Za-z0-9][\w.\-]*#\d+)"),
    re.compile(r"\b(req:[0-9a-fA-F][0-9a-fA-F\-]{5,})"),
    re.compile(r"\b(run-[a-z0-9][a-z0-9.\-]{2,})", re.IGNORECASE),
    re.compile(r"\b(?=[0-9a-fA-F]*\d)([0-9a-fA-F]{8,}(?:-[0-9a-fA-F]{4,}){0,4})\b"),
)


def superseded_by(note: Any) -> Optional[dict[str, Any]]:
    """The row this note says superseded it, or None.

    ``{ref, phrase, quote}`` when the note both SAYS a supersession and NAMES
    the superseder within ``_TARGET_WINDOW`` characters of saying it. None
    otherwise — and "otherwise" is the common case by a factor of nine.

    THE NULL RESULT IS THE POINT, AND IT IS MEASURED. A word-level search for
    "supersed" over the live corpus returns 10 hits. **Six of them are one
    boilerplate sentence appended to unrelated resolutions** — *"they are
    inert - they resolve nothing and were superseded by this correctly-
    addressed event minutes later"* — which is about two stray EVENTS, not
    about the request it is stapled to. Three more say "SUPERSEDED BY THE
    RECORD" / "BY BUILD" / "BY THE R39 PLAN". A parser that rendered an edge on
    every hit would have drawn six wrong supersession links on the CEO's desk
    and one right one.

    Requiring a NAMED TARGET takes that to 1 of 10, and the one it keeps is the
    one a reader can follow. An unparseable note is absence; absence is never a
    guess, and on this surface a guess is worse than a gap, because a gap is
    visibly a gap and a wrong link looks exactly like a right one.
    """
    if not isinstance(note, str) or not note.strip():
        return None
    m = _SUPERSEDED_RE.search(note)
    if m is None:
        return None
    window = note[m.end():m.end() + _TARGET_WINDOW]
    best: Optional[tuple[int, str]] = None
    for rx in _TARGET_RES:
        hit = rx.search(window)
        if hit and (best is None or hit.start() < best[0]):
            best = (hit.start(), hit.group(1))
    if best is None:
        return None
    quote = note[m.start():m.end() + best[0] + len(best[1])].strip()
    return {"ref": best[1], "phrase": m.group(0).strip(), "quote": quote}


# ============================================================================
# Item 4 — "accepted, execution yours" is a state, not a synonym for undecided
# ============================================================================

#: The three stages the desk-stage contract already binds both repos to. MOVED
#: HERE from ``scripts/gen_desk_contract.py`` (2026-08-24) so the mapping has
#: one home instead of living in a generator script that the running spine does
#: not import. The generator now imports it; the values are unchanged and the
#: contract's digest is unaffected by the move, which a test asserts.
STAGE_AWAITING_DECISION = "awaiting_decision"
STAGE_AWAITING_EXECUTION = "awaiting_execution"
STAGE_OWNED_ELSEWHERE = "owned_elsewhere"

#: Statuses that mean the CEO already said yes. Mirrored from
#: ``deskstore.REC_STATUSES``' decided pair rather than imported, for the reason
#: ``desk.TERMINAL_STATUSES`` already gives — a rendering module must not import
#: a database module — and pinned equal by a test.
DECIDED_STATUSES = ("accepted", "staged")

#: Actors whose rows count toward the CEO's figure. The client half of
#: ``desk_load``'s partition, stated once.
CEO_ACTORS = ("ceo", "unknown")

#: THE FIVE ACTION TAGS (CEO instruction 2026-08-28, verbatim: "I want simpler
#: action oriented tags. Pending, In FLight, Executed, Deprioritised,
#: Completed"). One vocabulary for every desk surface, folded HERE once — the
#: band fold's own argument: three client copies of a status rule is three
#: status rules, and the day they disagree the disagreement is invisible.
ACTION_TAGS = ("pending", "in_flight", "executed", "deprioritised", "completed")

ACTION_TAG_LABELS = {
    "pending": "Pending",
    "in_flight": "In flight",
    "executed": "Executed",
    "deprioritised": "Deprioritised",
    "completed": "Completed",
}

#: Statuses that mean "the record says this was carried out" vs "closed with
#: nothing further owed". ``done`` is the execution word on this desk (the
#: resolve pipeline marks an actioned item ``done`` with its citation);
#: ``resolved``/``noted`` close a thing without claiming an act was performed.
_EXECUTED_STATUSES = ("done",)
_COMPLETED_STATUSES = ("resolved", "noted")
_DEPRIORITISED_STATUSES = ("rejected", "declined", "shelved", "deferred",
                           "superseded", "killed")


def action_tag(row: Any) -> dict[str, Any]:
    """Which of the CEO's five action tags this row wears, and why.

    The mapping, stated so a reader can disagree with it in one place:

      ``pending``        nobody has decided it — status ``open`` (or absent)
                         with no supersession edge.
      ``in_flight``      a decision landed and the follow-through is owed or
                         underway — ``accepted``/``staged``/``approved``/
                         ``dispatched``. An accepted row that was ALREADY
                         executed but never marked ``done`` also lands here:
                         that is the closure gap being visible, not a bug in
                         the tag — the fix is marking the record, never
                         guessing at it from here.
      ``executed``       the record says the act was performed (``done``).
      ``deprioritised``  a human chose not to do it now — rejected, declined,
                         shelved, superseded, killed.
      ``completed``      closed with nothing further owed (``resolved``,
                         ``noted``).

    An unreadable status reports ``basis: "unreadable"`` and lands in
    ``pending`` — the same direction rule as the band fold: coercion must not
    quietly retire a row from the desk.
    """
    if not isinstance(row, dict):
        return {"action_tag": "pending", "action_tag_label": "Pending",
                "action_tag_basis": "unreadable"}
    # A supersession edge outranks the stored status: a superseded row is not
    # actionable whatever its status field still says.
    if row.get("supersession"):
        return {"action_tag": "deprioritised",
                "action_tag_label": ACTION_TAG_LABELS["deprioritised"],
                "action_tag_basis": "supersession"}
    st = row.get("status")
    s = str(st).strip().lower() if isinstance(st, str) else ""
    if s in _EXECUTED_STATUSES:
        tag = "executed"
    elif s in _COMPLETED_STATUSES:
        tag = "completed"
    elif s in _DEPRIORITISED_STATUSES:
        tag = "deprioritised"
    elif s in DECIDED_STATUSES or s in ("approved", "dispatched"):
        tag = "in_flight"
    elif s in ("open", ""):
        tag = "pending"
    else:
        return {"action_tag": "pending", "action_tag_label": "Pending",
                "action_tag_basis": f"unreadable:{s[:24]}"}
    return {"action_tag": tag, "action_tag_label": ACTION_TAG_LABELS[tag],
            "action_tag_basis": "status"}


def desk_stage(actor: Any, status: Any) -> str:
    """How a spine verdict maps onto the page's three stages.

    Unchanged behaviour, new address. ``status`` is read for ONE thing and it
    is not routing: telling a row the CEO DECIDED and the firm owes back
    (``awaiting_execution``) from an open row that was never his
    (``owned_elsewhere``). Both are uncounted; they are different facts and the
    desk has already paid once for confusing them.
    """
    if actor in CEO_ACTORS:
        return STAGE_AWAITING_DECISION
    return (STAGE_AWAITING_EXECUTION if status in DECIDED_STATUSES
            else STAGE_OWNED_ELSEWHERE)


def execution_yours(actor: Any, status: Any) -> bool:
    """Is this a row the CEO DECIDED whose next act is still his own?

    ``accepted``/``staged`` AND the next actor is still the CEO (or could not
    be read). The constitution's preserved COO objection, verbatim: *"items at
    status `accepted` whose execution requires the CEO personally (three live
    today, including PM R1, the largest-money decision in the firm)"*. Fourteen
    of the thirty-four rows on his live decision list are this, measured
    2026-08-24.

    **IT CHANGES NO COUNT, AND THAT IS A CONSTRAINT RATHER THAN A SIDE
    EFFECT.** These rows are inside ``awaiting_decision`` and must stay there:
    ``desk_load.total`` counts ``ceo`` + ``unknown``, the desk-stage contract
    pins the page's ``awaitingTotal`` to it, and a fourth stage would have
    moved a threshold's population while claiming to be a rendering change.
    This is a PREDICATE the renderer asks in addition to the stage, never a
    replacement for it — a distinct picture over an unchanged number.

    The picture is the whole deliverable. His accept on R39 landed, the fold
    was correct, the row refetched, and it came back with an Accept button on
    it because nothing on screen could tell "you decided this and now you must
    execute it" from "nobody has decided this". One second of feedback is the
    acceptance criterion; the number was never wrong.
    """
    return actor in CEO_ACTORS and status in DECIDED_STATUSES


# ============================================================================
# Addition B — a disposition the CHAIR made is its own visible category
# ============================================================================

#: The CEO in person.
CHANNEL_CEO = "ceo"
#: The chair acting on a CEO instruction it quotes (delegation v2's
#: ``neelesh-via-cto`` / ``neelesh-via-co-cto``). His decision, chair's hand.
CHANNEL_VIA_CHAIR = "via_chair"
#: The chair on its own authority under delegation v2. **The category the CEO
#: asked for by name**: *"I cant form a view of whats closed and adjudicated by
#: you."* Fifty-two live rows on 2026-08-24 (``co-cto`` 39, ``cto`` 13).
CHANNEL_CHAIR = "chair"

_VIA_RE = re.compile(r"^(?:neelesh|ceo)-via-(co-)?cto$", re.IGNORECASE)
_CHAIR_ACTORS = ("cto", "co-cto", "chair")
_CEO_ACTORS_LITERAL = ("ceo", "neelesh")


def adjudication(row: Any) -> Optional[dict[str, Any]]:
    """Who closed this row, through which channel, quoting what.

    ``{channel, actor, at, label, citation, instruction}`` for a decided row,
    or None for a row nobody has decided. None is "undecided", never "decided
    by nobody" — the two are different and the desk renders them differently.

    ``instruction`` is the CEO's own words when the actor string carries them:
    the approval guard writes ``neelesh-via-cto [Agree]``, and that bracketed
    quote is the audit trail delegation v2 promised. It is lifted VERBATIM and
    never summarised.

    An actor outside the known vocabulary is ``unknown`` with the raw string
    kept. A desk that quietly filed a stranger's decision under "the chair"
    would be laundering exactly the attribution this section exists to expose.
    """
    if not isinstance(row, dict):
        return None
    actor = _clean(row.get("decided_by"))
    if actor is None:
        return None

    instruction = None
    base = actor
    br = actor.find("[")
    if br != -1 and actor.rstrip().endswith("]"):
        base = actor[:br].strip()
        instruction = actor[br + 1:actor.rstrip().rfind("]")].strip() or None

    key = base.strip().lower()
    if _VIA_RE.match(key):
        channel, label = CHANNEL_VIA_CHAIR, "approved by the CEO, staged by the chair"
    elif key in _CEO_ACTORS_LITERAL:
        channel, label = CHANNEL_CEO, "approved by the CEO"
    elif key in _CHAIR_ACTORS:
        channel, label = CHANNEL_CHAIR, "closed by the chair"
    else:
        channel, label = "unknown", f"decided by {base}"

    return {"channel": channel, "actor": base, "at": _clean(row.get("decided_at")),
            "label": label,
            # THE CITATION IS THE DECISION NOTE, VERBATIM AND UNTRUNCATED. The
            # CEO asked for it "one click away", not summarised: a chair that
            # paraphrased its own reason on the surface auditing that reason
            # would be marking its own homework.
            "citation": _clean(row.get("note")),
            "instruction": instruction}


# ============================================================================
# Item 5 — the cascade rule, which has had no machinery since it was written
# ============================================================================

#: Constitution, 2026-08-21: *"a batch acceptance CASCADES — when the CEO
#: accepts a COO batch, the CTO executes the underlying items and marks them
#: done; the CEO never re-decides item by item."* Written as governance, never
#: given a field: nothing in the schema could say WHICH items a batch row
#: carried, so "did the cascade actually happen" was unanswerable except by a
#: human reading prose.
#:
#: A member is ``{run_id, rec_id}`` (a recommendation) or ``{request_id}`` (a
#: desk request). Nothing else — a free-text member would put this fold back
#: where the rest of the desk started.
MAX_MEMBERS = 100


def member_ref(m: Any) -> Optional[str]:
    """One member as a canonical ref, or None if it does not name a row."""
    if not isinstance(m, dict):
        return None
    rid = _clean(m.get("request_id"))
    if rid:
        return f"req:{rid}"
    run = _clean(m.get("run_id"))
    rec = m.get("rec_id")
    if run and isinstance(rec, int) and not isinstance(rec, bool):
        return f"rec:{run}#{rec}"
    return None


def normalise_members(raw: Any) -> list[dict[str, Any]]:
    """The ``members`` field as filed, validated, unreadable entries DROPPED
    but COUNTED by the caller.

    Refuses silently-wrong shapes rather than storing them: a member that names
    no row is a member the cascade block could never resolve, and rendering
    "0 of 3 done" over an unresolvable third is worse than rendering "2".
    """
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in raw[:MAX_MEMBERS]:
        ref = member_ref(m)
        if ref is None or ref in seen:
            continue
        seen.add(ref)
        entry: dict[str, Any] = {"ref": ref}
        if isinstance(m, dict):
            if _clean(m.get("request_id")):
                entry["request_id"] = _clean(m.get("request_id"))
            else:
                entry["run_id"] = _clean(m.get("run_id"))
                entry["rec_id"] = m.get("rec_id")
            note = _clean(m.get("note"))
            if note:
                entry["note"] = note
        out.append(entry)
    return out


#: Statuses at which a member is finished and owes nothing further. Mirrors
#: ``desk.TERMINAL_STATUSES`` plus the request vocabulary, because a bundle may
#: carry both kinds and one list keeps the arithmetic honest.
_MEMBER_DONE = ("rejected", "done", "noted", "resolved", "declined")


def cascade(row: Any, status_by_ref: Any) -> Optional[dict[str, Any]]:
    """The cascade block under a DECIDED bundle, or None.

    ``{total, done, pending, not_open, members, note}``. Rendered only when the
    parent has members AND has been decided — an undecided bundle owes nothing
    yet, and a reminder that fires before the decision is a reminder that gets
    ignored.

    **A REMINDER SURFACE AND NOTHING ELSE.** It executes nothing, approves
    nothing and moves no status. The constitution's cascade rule says the chair
    VALIDATES each item against the record and then executes; this fold only
    makes the outstanding count visible so that step cannot be forgotten
    silently. Auto-executing members would be the unwired-kill-switch pattern
    inverted — a control that ACTS where it was only ever asked to report.

    THREE OUTCOMES, NOT TWO, AND THE THIRD ONE IS THE HONEST PART — it was
    found by the contract fixture disagreeing with its own docstring before any
    of this shipped. ``status_by_ref`` is built from the desk's populations,
    and ``DeskStore.open_recommendations`` returns only open / accepted /
    staged. So a recommendation member that has been FINISHED is simply absent
    from the lookup, and the first cut called that ``unresolvable`` — which
    would have rendered a fully-executed cascade as "3 members could not be
    read", the good case wearing an error's face.

    It is not readable as done either: absent means "finished, or never
    existed, and this fold cannot tell which". So it is ``not_open``, named for
    exactly what was observed, and the ONE number the CEO needs —
    ``pending``, the members demonstrably still undecided — is exact, because
    it is counted only over rows that are actually present. Request members
    resolve fully (``desk._requests`` keeps terminal rows), so ``done`` is real
    where the data supports it and absent where it does not.
    """
    if not isinstance(row, dict):
        return None
    members = normalise_members(row.get("members"))
    if not members:
        return None
    if row.get("status") not in DECIDED_STATUSES:
        return None

    lookup = status_by_ref if isinstance(status_by_ref, dict) else {}
    done = pending = not_open = 0
    out = []
    for m in members:
        st = lookup.get(m["ref"])
        st = st.strip().lower() if isinstance(st, str) else None
        if st is None:
            state, not_open = "not_open", not_open + 1
        elif st in _MEMBER_DONE:
            state, done = "done", done + 1
        else:
            state, pending = "pending", pending + 1
        out.append({**m, "status": st, "state": state})

    bits = []
    if pending:
        bits.append(f"CASCADE PENDING: {pending} member(s) undecided")
    if not_open:
        bits.append(f"{not_open} member(s) are no longer on the open desk — "
                    f"finished, or never filed; this fold cannot tell which "
                    f"and does not count them as done")
    if not bits:
        bits.append(f"all {done} member(s) closed")
    return {"total": len(members), "done": done, "pending": pending,
            "not_open": not_open, "members": out,
            "note": "; ".join(bits) + ". The chair validates and executes each "
                    "one; nothing here executes anything."}


# ============================================================================
# Addition A — the structured request card (spec: KryptonPay/docs/design/
# REQUEST_CARD_2026-08-24.md, CEO-ratified)
# ============================================================================

#: The lifecycle rail, in order. The CURRENT stage carries its age; the spec's
#: worked example is request ``0c295ec7`` — approved 22 minutes after filing,
#: then idle 2.5 days, which the old card rendered as gray footer text.
LIFECYCLE = ("filed", "approved", "awaiting_dispatch", "dispatched",
             "delivered")

#: What a ``wanted`` item's state may be. Three, because partial progress is
#: the thing the checklist exists to show — a card is not binary.
WANTED_STATES = ("open", "in_progress", "done")


def normalise_wanted(raw: Any) -> list[dict[str, Any]]:
    """The ``wanted`` checklist as filed. An unrecognised state is ``open``.

    Down-grading rather than refusing, and only here: this field is ADVISORY
    (it renders a tick, it gates nothing), and an item whose state was typoed
    should still appear on the list as something still owed. The safe direction
    for a checklist is "not done yet".
    """
    if not isinstance(raw, list):
        return []
    out = []
    for w in raw[:MAX_MEMBERS]:
        if isinstance(w, str):
            text = _clean(w)
            state, note = "open", None
        elif isinstance(w, dict):
            text = _clean(w.get("text"))
            st = w.get("state")
            st = st.strip().lower() if isinstance(st, str) else None
            state = st if st in WANTED_STATES else "open"
            note = _clean(w.get("note"))
        else:
            continue
        if not text:
            continue
        entry = {"text": text, "state": state}
        if note:
            entry["note"] = note
        out.append(entry)
    return out


def request_card(payload: Any) -> dict[str, Any]:
    """A desk request rendered as the four questions, structured or not.

    ``{headline, summary, incident, wanted, next_move, structured}``.

    **PROSE-ONLY STAYS VALID FOREVER** (the spec says so in as many words), and
    ``structured: false`` is how the renderer knows to use the old one-blob
    fallback. No migration of old rows: 109 requests exist, none of them was
    filed under a schema that did not exist, and rewriting their subjects to
    look structured would be inventing a headline the filer never wrote.

    The fallback headline is the subject's FIRST LINE, untouched and
    untruncated — a cut is the renderer's job, where the available width is
    known. Splitting on the first sentence here would do to a subject what the
    first cut of ``card_text`` nearly did to a title.
    """
    if not isinstance(payload, dict):
        return {"headline": None, "summary": None, "incident": None,
                "wanted": [], "next_move": None, "structured": False}

    headline = _clean(payload.get("headline"))
    summary = _clean(payload.get("summary"))
    incident = _clean(payload.get("incident"))
    wanted = normalise_wanted(payload.get("wanted"))

    nm = payload.get("next_move")
    next_move = None
    if isinstance(nm, dict):
        actor, act = _clean(nm.get("actor")), _clean(nm.get("act"))
        # BOTH OR NEITHER. "Next move: the chair" without the act is the old
        # CEO-APPROVED chip's defect in a new field — it names an owner and
        # leaves the reader to guess the obligation. The spec's whole complaint
        # was that the chip "implied the CEO's move when it was the chair's".
        if actor and act:
            next_move = {"actor": actor, "act": act}

    structured = any([headline, summary, incident, wanted, next_move])
    if not headline:
        subject = _clean(payload.get("subject")) or _clean(payload.get("task"))
        headline = subject.splitlines()[0].strip() if subject else None
        if subject and not incident and not structured:
            incident = subject
    return {"headline": headline, "summary": summary, "incident": incident,
            "wanted": wanted, "next_move": next_move, "structured": structured}


def lifecycle_rail(row: Any, now: Any = None) -> Optional[dict[str, Any]]:
    """Where a request stands on the rail, and how long it has stood there.

    ``{stages: [{stage, at, reached, current}], current, age_hours}``.

    ``age_hours`` is None when the current stage carries no timestamp — the
    rail then renders the stage without an age rather than with a zero. A desk
    that printed "awaiting dispatch · 0.0h" over a row that had been idle for
    two and a half days would be this fund's oldest mistake on its newest
    surface.
    """
    from app.fund.desk import _ts

    if not isinstance(row, dict):
        return None
    status = (row.get("status") or "open").strip().lower()
    dispatched = bool(row.get("dispatched"))

    at = {
        "filed": row.get("at"),
        "approved": row.get("approved_at"),
        "dispatched": row.get("dispatched_at"),
        "delivered": row.get("resolved_at"),
    }
    # `awaiting_dispatch` is not an event, it is a GAP: approved and not yet
    # dispatched. It inherits the approval's timestamp, because the clock the
    # CEO cares about started when he said yes.
    at["awaiting_dispatch"] = at["approved"]

    if status == "resolved":
        current = "delivered"
    elif dispatched:
        current = "dispatched"
    elif status == "approved":
        current = "awaiting_dispatch"
    elif status == "declined":
        current = "filed"
    else:
        current = "filed"

    idx = LIFECYCLE.index(current)
    stages = [{"stage": s, "at": at.get(s), "reached": i <= idx,
               "current": s == current}
              for i, s in enumerate(LIFECYCLE)]

    age = None
    started = _ts(at.get(current))
    if started is not None:
        from datetime import datetime, timezone
        end = _ts(now) if now is not None else datetime.now(timezone.utc)
        if end is not None:
            age = round((end - started).total_seconds() / 3600.0, 1)
            if age < 0:
                # A stage stamped in the future is a clock disagreement, not a
                # negative age. Reported as unknown; never clamped to zero.
                age = None
    return {"stages": stages, "current": current, "age_hours": age,
            "declined": status == "declined"}
