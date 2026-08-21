"""The research desk — the firm's agent bench, its artifacts, and its work queue.

The fund is built by a small firm: an operator, a CTO session, and a bench of
agents (mechanism / adversary / validator) whose working protocol lives in the
workspace constitution (.claude/CLAUDE.md). This module makes that firm VISIBLE
and TRIGGERABLE from the product:

  * the roster, with the measured failure that justifies each seat
  * the artifact chain — proposals and designs paired with the adversarial
    verdicts that killed or spared them, read from docs/ where they live
  * a request queue: the operator asks the desk for work (a proposal, an attack,
    an audit) and the request is recorded as an EVENT, so it survives restarts
    and shows up in the log like every other fact about the fund

One honesty rule, stated where the UI can render it: **the spine does not run
agents.** Requests are picked up and dispatched by the CTO session; what this
module guarantees is that a request, once clicked, is a durable fact that cannot
be quietly forgotten — not that it executes by itself. A button that implied the
spine could think would be the most dishonest control in the product.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DOCS = Path("docs")

#: The bench. Static by design: the roster changes by editing the constitution
#: and this file together, which is a versioned change with a written reason —
#: the same rule every threshold follows.
ROSTER = [
    {"agent": "mechanism",
     "lane": "Proposes edges with a named counterparty and a declared claim type",
     "emits": "a falsifiable proposal",
     "exists_because": "All five ideas this fund ever tested were textbook "
                       "parameter sweeps; zero passed. A proposal that cannot "
                       "say who is on the other side and why they keep paying "
                       "is rejected before it costs a container."},
    {"agent": "analyst",
     "lane": "Builds evidence-grounded theses from the filings corpus, market "
             "data, and the open web",
     "emits": "a thesis memo with verbatim evidence and invalidation conditions",
     "exists_because": "The fund read 863 observations from 201 tickers' filings "
                       "and nothing ever consumed one. A corpus nobody reads is "
                       "a cost, not an asset."},
    {"agent": "pm",
     "lane": "Owns the book analytically: mandate check, exceptions, exit "
             "coverage, TCA against the fills",
     "emits": "a decision memo with small, separate, clickable recommendations",
     "exists_because": "Seated the day the $500 sleeve filled: gross at ~83% "
                       "against a throttle asking for ~77%, three deployed "
                       "strategies failing the gate, and the trim decision open "
                       "- a book with real questions and nobody asking them "
                       "daily. Recommends only; the CEO accepts, the CTO "
                       "stages, the CEO clicks."},
    {"agent": "quant",
     "lane": "Translates approved proposals and theses into LEAN algorithms and "
             "runs them down the belt",
     "emits": "an implementation + the gate's verdict, failures verbatim",
     "exists_because": "The proposal-to-implementation step was the CTO's "
                       "personal bottleneck - every candidate so far was "
                       "hand-written by the CTO. Carries the firm's ONE scoped "
                       "code exception: Write/Edit inside "
                       "lean_workspace/algorithms/** only, which is already the "
                       "sandbox. Buy/sell inside backtests; never live orders."},
    {"agent": "adversary",
     "lane": "Tries to kill any artifact, blind to its author's reasoning",
     "emits": "KILL / SURVIVES / CANNOT TELL, with citations and repro",
     "exists_because": "Blind review found the unwired kill switches the fund's "
                       "own green test suite had blessed, and killed a gate "
                       "'improvement' that looked 50% better on its headline. "
                       "It has since killed two v5 designs in a row, each with "
                       "runnable demonstrations."},
    {"agent": "builder",
     "lane": "Batched harness engineering in an isolated worktree - diff + "
             "passing tests out, CTO merges",
     "emits": "a reviewed diff, test results verbatim, decisions named",
     "exists_because": "Every serious bug this fund made was HARNESS code - so "
                       "this seat gets throughput without trust: it never "
                       "touches the live tree, thresholds, or the approval "
                       "path, and nothing it writes runs before human review."},
    {"agent": "riskofficer",
     "lane": "Supervises the auto-approval policy: audits every auto-approval "
             "after the fact, attacks the envelope, recommends version changes",
     "emits": "audit findings with event seqs cited, or an envelope "
              "recommendation with the demonstration attached",
     "exists_because": "Seated 2026-08-20 by the same CEO decision that created "
                       "the auto-approval policy: an execution path without an "
                       "adversarial supervisor is the unwired kill switch "
                       "pattern in a new costume. Already flagged envelope v1's "
                       "weakest check at hiring (marker provenance)."},
    {"agent": "validator",
     "lane": "Audits the fund's own instruments — the gate, the audits, the "
             "registers",
     "emits": "measurements with method, sample size and confidence",
     "exists_because": "Every serious mistake this fund has made was a false "
                       "belief about itself: v1 passed noise, v2 failed an "
                       "oracle, v3 was an unnoticed loosening, v4 is "
                       "benchmark-blind, the controls were unwired, the verdict "
                       "column was write-only."},
    {"agent": "coo",
     "lane": "Triages the CEO's desk: batches every open item, checks each "
             "against the constitution and mandate, ranks by money, endorses "
             "or objects — the CEO decides batches, not items",
     "emits": "ONE batched decision memo with per-item recommended "
              "dispositions; an endorsement is never a decision",
     "exists_because": "Seated 2026-08-20 by demonstrated need: the CEO's desk "
                       "carried ~20 open recommendations in one day and an "
                       "overwhelmed approver becomes a rubber stamp — the "
                       "failure every control here exists to prevent. The "
                       "click stays the CEO's, always."},
    {"agent": "secretary",
     "lane": "Documents each day from the record at end of day: one short memo "
             "(the CEO's sixty-second read) and one detailed record, filed to "
             "docs/archives/YYYY-MM-DD.md",
     "emits": "two memos in one dated artifact, every claim cited to the log",
     "exists_because": "Seated 2026-08-20 (CEO decision). The Scribe seat's "
                       "'still nothing for them to do' condition ended the day "
                       "the firm shipped a guard, merged a dispatch, ran two "
                       "audits and filled four tickets, and no human could have "
                       "reconstructed it without an hour in the log. The seat "
                       "carries the name Donna; she documents and never "
                       "decides, and her one steering output is the factual "
                       "'awaits the CEO' list. ADDED TO THIS ROSTER 2026-08-21: "
                       "the seat existed in the constitution and was missing "
                       "here, so her seat page rendered a roster absence for a "
                       "colleague who had already run."},
]

#: Request kinds the desk accepts, mapped to the seat that serves them.
REQUEST_KINDS = {
    "proposal": "mechanism",
    "thesis": "analyst",
    "portfolio_review": "pm",
    "implement": "quant",
    "attack": "adversary",
    "audit": "validator",
    "policy_audit": "riskofficer",
    # Build work is the CTO's lane, queued here so that engineering asks flow
    # through the same durable, visible queue as research asks - everything
    # gates through the CEO and the CTO, and a queue with a side channel is
    # not a queue.
    "build": "builder",
    # The CEO asking for their own desk to be triaged into batch decisions.
    "triage": "coo",
    # The CTO's end-of-day trigger. A KIND rather than a schedule, deliberately:
    # the secretary runs when a human fires her, and naming it here is what puts
    # her in the activity fold and the per-seat telemetry — without it she is a
    # seat that has run and reports NO runs-today at all, which the floor draws
    # as an unmeasured "×?" beside colleagues showing real counts.
    "document_day": "secretary",
}

_STATUS_RE = re.compile(r"Status:\s*(KILLED|SURVIVES|under adversarial review"
                        r"|DESIGN under adversarial review)", re.IGNORECASE)
_ATTACKED_RE = re.compile(r"Artifact attacked:\*{0,2}\s*([^\s*]+)")
_VERDICT_RE = re.compile(r"VERDICT:\s*(KILL|SURVIVES|CANNOT TELL)", re.IGNORECASE)


def _title_of(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "(untitled)"


#: Where the secretary files. Append-only by convention: one dated file per day,
#: never an edit — see the constitution's third code exception (2026-08-21).
ARCHIVES = DOCS / "archives"

_ARCHIVE_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def archives() -> dict[str, Any]:
    """Every Daily the secretary has filed, newest first.

    Exists because the UI must not read the filesystem. Donna's seat page needs
    an index of `docs/archives/*.md` and the Studio has no business walking a
    directory — the spine owns what is on disk, the browser owns what is on
    screen, and a page that stats files is a page that breaks the moment it is
    served from anywhere but this machine.

    Read every call rather than cached, for the same reason `_artifacts` is: the
    files ARE the state, and an in-memory copy is a second place to disagree
    with them.

    THREE ABSENCES, kept apart:
      * the directory does not exist — nothing has ever been filed;
      * it exists and is empty — the secretary has run zero times;
      * it cannot be READ — unknown, which is not either of the above.
    A caller that cannot tell those apart will report "no dailies" for a
    permissions error.
    """
    if not ARCHIVES.exists():
        return {"archives": [], "readable": True, "exists": False,
                "note": "docs/archives/ does not exist — the secretary has "
                        "never filed. This is an absence, not an empty list"}
    try:
        entries = sorted(ARCHIVES.glob("*.md"))
    except OSError as e:
        return {"archives": [], "readable": False, "exists": True,
                "note": f"docs/archives/ could not be read ({e}) — whether "
                        f"anything is filed is UNKNOWN, not none"}

    out: list[dict[str, Any]] = []
    for p in entries:
        stem = p.stem
        pdf = p.with_suffix(".pdf")
        try:
            size = p.stat().st_size
        except OSError:
            size = None
        m = _ARCHIVE_NAME_RE.match(stem)
        out.append({
            "date": m.group(1) if m else None,
            "path": str(p).replace("\\", "/"),
            # The PDF is a RENDER of the markdown, not a separate artifact, so
            # its absence is normal rather than a fault: the secretary files the
            # .md and renders the .pdf, and a day rendered before that step
            # existed has only the first.
            "pdf_path": str(pdf).replace("\\", "/") if pdf.exists() else None,
            "title": _title_of(_read(p)),
            "bytes": size,
            # A file whose name is not a date is still listed — it is on disk and
            # hiding it would make the index disagree with the directory.
            "note": None if m else
                    "filename is not a YYYY-MM-DD date — listed as filed, but "
                    "which day it documents cannot be read from the name",
        })
    out.sort(key=lambda r: (r["date"] or "", r["path"]), reverse=True)
    return {
        "archives": out, "readable": True, "exists": True,
        "count": len(out),
        "with_pdf": sum(1 for r in out if r["pdf_path"]),
        "note": (f"{len(out)} daily archive(s) on file"
                 if out else
                 "docs/archives/ exists and holds no .md — the secretary has "
                 "filed nothing yet, which is different from never having run"),
    }


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _artifacts() -> list[dict[str, Any]]:
    """Proposals and designs, paired with the verdicts that reviewed them.

    Read from docs/ every call rather than cached, because the files ARE the
    state — an in-memory copy would be a second place to disagree with them.
    """
    reviews: dict[str, dict[str, Any]] = {}
    for p in sorted((DOCS / "reviews").glob("*.md")) if (DOCS / "reviews").exists() else []:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _ATTACKED_RE.search(text)
        v = _VERDICT_RE.search(text)
        target = (m.group(1).strip() if m else "").replace("\\", "/")
        reviews[target] = {
            "review_path": str(p).replace("\\", "/"),
            "review_title": _title_of(text),
            "verdict": (v.group(1).upper() if v else None),
        }

    out: list[dict[str, Any]] = []
    sources = []
    if (DOCS / "proposals").exists():
        sources += [("proposal", p) for p in sorted((DOCS / "proposals").glob("*.md"))]
    sources += [("design", p) for p in sorted(DOCS.glob("GATE_V5_DESIGN_*.md"))]
    for kind, p in sources:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        path = str(p).replace("\\", "/")
        rev = reviews.get(path)
        m = _STATUS_RE.search(text)
        status = "under_review"
        if rev and rev["verdict"] == "KILL":
            status = "killed"
        elif rev and rev["verdict"] == "SURVIVES":
            status = "survives"
        elif m and m.group(1).upper() == "KILLED":
            status = "killed"
        out.append({
            "kind": kind, "path": path, "title": _title_of(text),
            "status": status,
            "review": rev,
            # No review on file is stated as such — an unreviewed artifact is
            # not a surviving one, and rendering it green would be the
            # absence-scored-as-value error in a new costume.
            "note": None if rev else "no adversarial review on file — "
                                     "unreviewed is not the same as surviving",
        })
    return out


def _requests(store: Any) -> list[dict[str, Any]]:
    """Open and resolved desk requests, folded from the event log."""
    from app.fund.events import EventType

    rows: dict[str, dict[str, Any]] = {}
    for e in store.stream(since_seq=0, limit=100_000):
        t = e.get("type") if isinstance(e, dict) else getattr(e, "type", None)
        t = getattr(t, "value", t)
        p = (e.get("payload") if isinstance(e, dict)
             else getattr(e, "payload", None)) or {}
        if t == EventType.DESK_REQUESTED.value:
            rid = p.get("request_id")
            if rid:
                row = {**p, "status": "open"}
                # Seat-filed asks write subject/serves where CEO-typed
                # requests write task/seat. The desk's readers key on
                # task/seat, so an unnormalized seat ask is COUNTED by
                # desk_load but renders as a blank row — an invisible
                # item on the CEO's desk (found 2026-08-21: 2/20 open
                # with a visually clear desk).
                row["task"] = p.get("task") or p.get("subject")
                row["seat"] = p.get("seat") or p.get("serves")
                rows[rid] = row
        elif t == EventType.DESK_REQUEST_APPROVED.value:
            rid = p.get("request_id")
            # Approval only moves an OPEN request forward; a resolved one keeps
            # its terminal state (the fold is order-honest, not last-write-wins).
            if rid in rows and rows[rid].get("status") == "open":
                rows[rid] = {**rows[rid], "status": "approved",
                             "approved_by": p.get("actor"),
                             "approved_at": p.get("at")}
        elif t == EventType.DESK_REQUEST_DECLINED.value:
            rid = p.get("request_id")
            # A rejection lands while open or approved-but-untriggered; a
            # resolved request is history and keeps its terminal state.
            if rid in rows and rows[rid].get("status") in ("open", "approved"):
                rows[rid] = {**rows[rid], "status": "declined",
                             "declined_by": p.get("actor"),
                             "declined_at": p.get("at"),
                             "decline_reason": p.get("reason")}
        elif t == EventType.DESK_REQUEST_RESOLVED.value:
            rid = p.get("request_id")
            # Resolution only completes a request still on the path (open or
            # approved) — it must not overwrite a rejection: executing a
            # declined ask would be the CTO overriding the CEO's no.
            if rid in rows and rows[rid].get("status") in ("open", "approved"):
                rows[rid] = {**rows[rid], "status": "resolved",
                             "resolved_at": p.get("at"),
                             "resolution": p.get("resolution")}
    return sorted(rows.values(), key=lambda r: r.get("at") or "", reverse=True)


def _ts(value: Any):
    """An ISO timestamp as a comparable instant, or None if it is not one.

    Never a string compare: the log writes `+00:00` and hand-written fixtures
    write `Z`, and lexicographic order across the two is wrong exactly where it
    matters. Unparseable returns None, and every caller treats that as "cannot
    compare" rather than as an ordering that happens to sort.
    """
    from datetime import datetime
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _within_window(dispatched_at: Any, window_floor: Any) -> bool:
    """Could a return for this dispatch be inside the run window we searched?

    True when there is no floor (the recorder was read and holds no runs at
    all, so "nothing came back" is a MEASURED negative). False when either
    timestamp cannot be read — an incomparable pair is an unknown, and an
    unknown must not report as a clean look.
    """
    if window_floor is None:
        return True
    a, b = _ts(dispatched_at), _ts(window_floor)
    if a is None or b is None:
        return False
    return a >= b


def _activity(store: Any, runs: Optional[list[dict[str, Any]]] = None,
              runs_limit: Optional[int] = None) -> dict[str, dict[str, Any]]:
    """What each seat is doing RIGHT NOW, folded from dispatch/resolve events.

    The spine cannot see a Claude agent thinking; what it can see is the CTO
    session recording "dispatched X to seat Y" and "Y delivered Z". That is the
    truthful resolution available, and the UI renders exactly it - a spinner
    pretending to watch the agent's cursor would be theatre.

    THREE STATES, not two (constitution, from the CEO's instruction on desk
    request 907ecc74: *"no it should nto close automatically since the cto needs
    to review the work be satisified and then log or do what needs to be done
    and then close it"*):

      WORKING          dispatched, and nothing has come back.
      AWAITING REVIEW  the seat RETURNED — a run exists carrying this
                       dispatch's trace — and no resolution has been recorded.
                       An obligation on the CHAIR, not a busy seat.
      idle             neither. A real state, not a gap: a bench seat that is
                       never idle is a bottleneck.

    Measured on the live spine 2026-08-22, which is why this is not cosmetic:
    the builder's desk read `working` for 21 hours and the analyst's for 19,
    both after their dispatches had returned — and two agents in parallel are
    permitted as of the same week, so a chair reading this payload could not
    tell whether a slot was free.

    IT DOES NOT AUTO-CLOSE, and a test asserts it. Closing is the chair's
    judgement step — review the work, be satisfied, file what needs filing.
    Deriving `closed` from "a run came back" would make the board report a
    completion nobody performed.

    DETECTION IS IDENTIFIER-BASED AND INCOMPLETE, reported rather than hidden.
    A dispatch is matched to a run on EXACT identifiers only — the dispatch's
    `trace_id`, then its `task_id`, against the run's `trace_id` or `run_id`.
    Nothing is matched on seat plus a timestamp: a near-miss there would mark
    an unrelated run as this dispatch's return and invent an obligation the
    chair does not have. Measured over the live log: 17 of 24 dispatches match
    on trace_id, 8 on task_id, and 4 carry NO trace_id at all and therefore can
    never be matched. Those four report `review_detectable: false` and stay
    WORKING — "still running" and "we cannot see" must not render as the same
    confident word.

    ``runs_limit`` is the cap ``runs`` was fetched under, so a truncated list
    can be told from a complete one. See ``window_floor`` below.
    """
    from app.fund.events import EventType

    open_by_task: dict[str, dict[str, Any]] = {}
    seats: dict[str, dict[str, Any]] = {}
    for e in store.stream(since_seq=0, limit=100_000):
        t = e.get("type") if isinstance(e, dict) else getattr(e, "type", None)
        t = getattr(t, "value", t)
        p = (e.get("payload") if isinstance(e, dict)
             else getattr(e, "payload", None)) or {}
        if t == EventType.DESK_DISPATCHED.value:
            tid, seat = p.get("task_id"), p.get("seat")
            if tid and seat:
                open_by_task[tid] = p
                seats.setdefault(seat, {})["working_on"] = p
        elif t == EventType.DESK_REQUEST_RESOLVED.value:
            tid = p.get("request_id")
            d = open_by_task.pop(tid, None)
            if d:
                seat = d["seat"]
                row = seats.setdefault(seat, {})
                if (row.get("working_on") or {}).get("task_id") == tid:
                    row.pop("working_on", None)
                row["last_delivered"] = {"task": d.get("task"),
                                         "artifact": p.get("resolution"),
                                         "at": p.get("at")}

    # Which run identifiers exist at all, so a dispatch can be matched against
    # them. `runs` is None when the flight recorder could not be read — a
    # different fact from "it was read and held nothing", and the two must not
    # collapse: the first makes detection unavailable, the second makes it
    # available and negative.
    recorder_read = runs is not None
    run_by_key: dict[str, str] = {}
    resolved: list[str] = []
    for r in (runs or []):
        rid = r.get("run_id")
        if not rid:
            continue
        for key in (r.get("trace_id"), rid):
            if key:
                run_by_key.setdefault(key, rid)
        if r.get("resolved_at"):
            resolved.append(r["resolved_at"])
    # THE WINDOW'S FLOOR, and why it is load-bearing. `runs` is the newest N by
    # resolved_at, so when that list is TRUNCATED a dispatch made before its
    # oldest row may have a return that resolved outside it — invisible to us.
    # A run for a dispatch always resolves after the dispatch, so a dispatch at
    # or after the floor would have its return inside the window if one
    # existed; before the floor, a miss proves nothing. Without this the
    # payload would report `review_detectable: true, status: working` for every
    # old dispatch, which is a confident answer built on a truncated list.
    #
    # `runs_limit` is what makes the rule EXACT rather than merely careful: a
    # list shorter than the cap it was fetched under is the whole table, so
    # there is no outside to fall into and the floor does not apply. Without
    # that check the honest-unknown would fire on knowable cases, which is its
    # own kind of wrong answer.
    truncated = (runs_limit is not None and runs is not None
                 and len(runs) >= runs_limit)
    window_floor = min(resolved) if (resolved and truncated) else None

    out = {}
    for seat in list(REQUEST_KINDS.values()):
        row = seats.get(seat, {})
        w = row.get("working_on")
        # EXACT identifiers only, in the order that matches most on the live
        # log: the dispatch's own trace first (17 of 24), its task_id second
        # (8 of 24, the older convention where the two were the same string).
        keys = [k for k in ((w or {}).get("trace_id"), (w or {}).get("task_id"))
                if k]
        back = None
        for k in keys:
            back = run_by_key.get(k)
            if back:
                break
        out[seat] = {
            "status": ("awaiting_review" if back else "working") if w else "idle",
            "task": (w or {}).get("task"),
            "since": (w or {}).get("at"),
            "task_id": (w or {}).get("task_id"),
            # The run that came back, so the chair can open it and review.
            "returned_run_id": back,
            # Whether the spine could TELL a returned dispatch from a running
            # one FOR THIS DISPATCH. Per-dispatch and not per-payload: a
            # dispatch carrying no identifier is undetectable even with a
            # fully readable recorder, and reporting it as detectable would
            # dress "we never looked" as "nothing came back". None when the
            # seat is idle — there is nothing to detect. A positive match is
            # its own proof, so it short-circuits every other condition.
            "review_detectable": (
                True if back else
                (recorder_read and bool(keys)
                 and _within_window((w or {}).get("at"), window_floor))
            ) if w else None,
            "last_delivered": row.get("last_delivered"),
        }
    return out


#: The CEO's standing triage rule (2026-08-20, CEO instruction, registered as
#: a dispatch trigger): when OPEN items on the CEO's desk exceed this, a COO
#: triage dispatch is DUE. Registered here so the count and the rule live in
#: one place — the count crossing it is a SIGNAL for the CTO to dispatch, and
#: nothing in this module or the spine dispatches anything. The ignition keys
#: stay human; this is the dashboard light, not the starter motor.
#: VERSIONED CHANGE 2026-08-21: 20 -> 50, and the comparison moved from
#: `>` to `>=`, by CEO instruction verbatim: "Lets run coo on >=50 items or
#: we can trigger as needed." WRITTEN REASON (the rule requires one in
#: either direction, and this is a LOOSENING so it is recorded loudly):
#: COO triage #3 measured that 11 of 20 open recommendations were already
#: executed — the counter was summoning the seat on stale bookkeeping
#: rather than on decisions. Manual dispatch at any count remains available
#: and is the CEO's stated fallback. OBJECTION ON THE RECORD: the COO
#: (interest disclosed by the seat itself) recommended KEEPING 20, arguing
#: the number is not the defect — the counter is blind to items at status
#: `accepted` whose execution requires the CEO personally (three live that
#: day, including PM R1). Raising the threshold does NOT address that blind
#: spot; it remains open work. Applied by the co-CTO chair on the CEO's
#: explicit approval; the constitution carries the same amendment and the
#: objection beside it.
COO_TRIAGE_THRESHOLD = 50


# --------------------------------------------------- whose move is it? ------
#
# THE DEFECT THIS SECTION EXISTS TO FIX (CEO, 2026-08-22, verbatim): *"I maybe
# out of sync with whats happening across agents but they sustain on my queue
# even if that work has been done. this needs to be fixed."*
#
# `desk_load` promised to measure "how many things are actually waiting for the
# CEO" and measured something else: rows whose STATUS LABEL was open. A status
# label is written by a seat at filing time, not by the world, so an engineering
# ticket nobody would ever hand the CEO counted exactly like a decision only he
# can make. Measured on the live record by replaying the decision events: at
# 2026-08-21T20:39Z the counter read 18 (17 recommendations + 1 desk request)
# and the chair cleared every one of them by hand eight minutes later.
#
# So the question the counter asks changes: not "what status does this row
# carry" but **WHOSE MOVE IS IT**. Two independent facts answer that, and
# neither alone is sufficient — both failures are measured, not supposed:
#
#   * the LIFECYCLE says whether a decision is still outstanding. Status alone
#     is what produced the 18 above.
#   * the KIND says whose decision it is. Kind alone is worse: all 9 rows
#     carrying kind `awaits-ceo` on 2026-08-22 were already ACCEPTED, so a
#     status-blind kind predicate would have parked them on the CEO's counter
#     permanently — the complaint above, made structural.
#
# HONEST LIMIT, STATED HERE BECAUSE IT SETS EXPECTATIONS FOR THE TRIGGER: `kind`
# is free text and the corpus proves it — 84 distinct values across 219
# recommendations, 49 of them appearing exactly once, and the vocabulary grows
# every dispatch. So the table below routes only kinds whose NAME ALONE settles
# the actor, and everything else falls through to the CEO. Measured coverage:
# 41 of 219 rows (18.7%) route away from the CEO by kind. The kind axis is a
# real improvement and it is a small one; the lever that would actually decouple
# this counter from the bench's output volume is `next_actor` written at FILING
# time, which is why the explicit field below takes precedence over all of this.

#: The only actors this counter knows. `unknown` is a first-class member, not a
#: fallback that got away: a row whose next actor cannot be determined COUNTS,
#: because "I could not measure that" has been answered with "zero" by four
#: separate instruments in this fund already.
NEXT_ACTORS = ("ceo", "chair", "seat", "nobody", "unknown")

#: Kinds whose NAME ALONE settles who moves next. Deliberately short.
#:
#: The inclusion rule, applied to every entry and worth stating because it is
#: what stops this table rotting into prose-matching: a kind earns a row here
#: only if the WORD determines the actor without reading the recommendation.
#: `repair-required` is an engineering repair whoever wrote it; `fix` is not —
#: the corpus carries `fix` rows that are code changes and `fix` rows that are
#: portfolio decisions, so `fix` is absent and falls through to the CEO.
#:
#: The routing itself is the constitution's ownership table, not taste: the CTO
#: chair owns "what gets built next", and merging a builder diff is named as a
#: co-CTO action. Everything engineering-shaped therefore belongs to the chair.
KIND_ACTORS = {
    # The chair's own work — building, merging, dispatching.
    "build": "chair",
    "harness": "chair",
    "harness_gap": "chair",
    "engineering_ticket": "chair",
    "infra": "chair",
    "code_fix": "chair",
    "ui": "chair",
    "api_card": "chair",
    "docs": "chair",
    "repair_required": "chair",
    "block_merge": "chair",
    "dispatch_request": "chair",
    "next_dispatch": "chair",
    # A positive assertion rather than a default, so the common case is
    # readable in the table instead of implied by its absence.
    "awaits_ceo": "ceo",
    # Nothing is owed: the row records a fact or asks that a round NOT be spent.
    "no_action": "nobody",
    "measurement_recorded": "nobody",
}

#: Kind PREFIXES that name their own recipient. `handoff_to_mechanism` and
#: `note-to-riskofficer` both exist in the corpus and both are seat-to-seat.
_SEAT_KIND_PREFIXES = ("handoff_to_", "note_to_", "routed_to_")

#: Statuses after which nothing more is expected of anyone. Kept here rather
#: than imported from deskstore so this module stays importable without a
#: database, and asserted equal to deskstore's list by a test — one definition
#: with a guard beats two that drift.
TERMINAL_STATUSES = ("rejected", "done", "noted")

#: Bump when the table or the precedence changes. Published in the payload so a
#: reader can tell WHICH rules produced a count they are looking at — the same
#: discipline every threshold here follows.
NEXT_ACTOR_RULES_VERSION = "v1 (2026-08-22)"


def _norm_kind(kind: Any) -> str:
    """Lower-case, separator-insensitive. Seats write `harness-gap` and
    `engineering_ticket` in the same corpus; a table that cared would be a
    table with two entries per idea and one of them always missing."""
    if not isinstance(kind, str):
        return ""
    return kind.strip().lower().replace("-", "_").replace(" ", "_")


def next_actor(rec: Any) -> dict[str, Any]:
    """Whose move is it on this recommendation: {actor, basis, why}.

    PRECEDENCE:

      1. a TERMINAL status. Nothing follows a rejected, done or noted row, and
         no label may say otherwise — this rule sits ABOVE the explicit field
         on purpose. An explicit `next_actor` written while the row was live
         and never cleared would otherwise pin a closed row to the CEO's
         counter forever, which is the complaint this module is fixing, in a
         costume. (`decide_recommendation` also clears the field on a terminal
         move; this is the belt to that pair of braces, for rows written by any
         other path.)
      2. an EXPLICIT ``next_actor`` on the row. Authoritative below terminal,
         because it is a statement about the world made by whoever knew — and
         it is the only path that can express the COO's standing objection (a
         row the CEO has ACCEPTED whose execution is still the CEO's own act,
         of which there were three live on 2026-08-21). Nothing writes it yet;
         that is a fact about our capture, reported in the payload, not hidden.
      3. the rest of the LIFECYCLE. accepted/staged -> the chair, who executes
         what the CEO decided. A status outside the known vocabulary is
         UNKNOWN, never quietly one of the five.
      4. the KIND, for undecided rows only, against ``KIND_ACTORS``.
      5. otherwise the CEO — because a recommendation is by construction a
         thing a seat asks the firm to decide, and the decision channel is the
         CEO's. Failing toward "he must look" is the safe direction for a
         control; failing toward "nobody must look" is how work disappears.

    NOTHING HERE READS THE RECOMMENDATION'S PROSE. The emergency sweep that
    produced this brief found six finished rows by grepping their text for
    "EXECUTED"; that was the right measure at the time and is the wrong
    permanent one, because a heuristic over free English rots silently and
    reports the rot as a count.
    """
    if not isinstance(rec, dict):
        return {"actor": "unknown", "basis": "unreadable",
                "why": "the row is not a readable recommendation, so whose "
                       "move it is cannot be determined — counted as needing "
                       "attention rather than dropped"}

    status = rec.get("status")
    if status in TERMINAL_STATUSES:
        return {"actor": "nobody", "basis": "lifecycle",
                "why": f"status {status!r} is terminal — nothing follows it, "
                       "and no label may claim otherwise"}

    explicit = rec.get("next_actor")
    if explicit is not None:
        e = explicit.strip().lower() if isinstance(explicit, str) else ""
        if e in NEXT_ACTORS and e != "unknown":
            return {"actor": e, "basis": "explicit",
                    "why": f"the row states its next actor is the {e}"}
        return {"actor": "unknown", "basis": "explicit_unrecognised",
                "why": f"the row states next_actor={explicit!r}, which is not "
                       f"one of {NEXT_ACTORS} — an unreadable claim is UNKNOWN, "
                       "not an excuse to fall back to a guess"}

    if status in ("accepted", "staged"):
        return {"actor": "chair", "basis": "lifecycle",
                "why": f"status {status!r} means the CEO has already decided; "
                       "what remains is the chair's to execute"}
    if status not in (None, "open"):
        return {"actor": "unknown", "basis": "status_unrecognised",
                "why": f"status {status!r} is outside the known vocabulary, so "
                       "whether a decision is outstanding cannot be read"}

    kind = _norm_kind(rec.get("kind"))
    for prefix in _SEAT_KIND_PREFIXES:
        if kind.startswith(prefix) and len(kind) > len(prefix):
            return {"actor": "seat", "basis": "kind",
                    "why": f"kind {rec.get('kind')!r} names its own recipient — "
                           "a seat-to-seat handoff is not the CEO's load"}
    routed = KIND_ACTORS.get(kind)
    if routed:
        return {"actor": routed, "basis": "kind",
                "why": f"kind {rec.get('kind')!r} routes to the {routed}"}
    return {"actor": "ceo", "basis": "default",
            "why": "undecided, and nothing routes it elsewhere — a "
                   "recommendation awaiting a decision awaits the CEO's"}


def desk_load(open_recommendations: list[dict[str, Any]],
              pending_orders: Any, open_requests: Any) -> dict[str, Any]:
    """How many things are actually waiting for the CEO, and whether that is
    past the COO triage trigger.

    "Open items" is defined exactly, because a number whose definition drifts
    is worse than no number: recommendations whose NEXT REQUIRED ACTOR is the
    CEO (or cannot be determined) + pending orders + requests awaiting
    approval. Each component that cannot be counted is reported as None and
    named in ``unreadable`` — the total then carries ``complete: false``,
    because a partial count that reads like a full one is how a desk under the
    trigger looks quiet.

    THE OTHER TWO COMPONENTS WERE CHECKED AGAINST THE RECORD RATHER THAN
    ASSUMED, since the whole point of this change is that a component must
    earn its place on the CEO's counter:

      * pending orders — an order awaiting approval is the CEO's click by
        construction; anything the auto-approval envelope takes never appears
        here at all.
      * requests awaiting approval — all 25 `DeskRequestApproved` events in
        the log carry actor `ceo` or `neelesh-via-cto` (the CEO's instruction
        staged by the chair). Zero were approved by a chair on its own
        authority, so an open desk request is a CEO decision. Note that
        `view()`'s own note calls the same rows "waiting for the CTO session",
        which is about DISPATCH — a different step, after the approval.

    NOTHING IS HIDDEN TO MAKE THE NUMBER SMALLER. The rows that route away
    from the CEO are counted in ``by_actor`` and summarised in ``not_ceo_load``,
    the desk's own list of recommendations is untouched, and the note names the
    chair's backlog out loud. Solving a counting problem by dropping rows would
    be the same defect wearing the opposite sign.

    MEASURED EFFECT ON THE TRIGGER (this changes WHEN the COO is summoned, so
    it is recorded loudly): replayed against the live decision log at
    2026-08-21T20:39Z, the old predicate counted 18 and this one counts 13 —
    12 recommendations plus the 1 open desk request. Five recommendations moved
    off the CEO's counter: two adversary `repair-required` grounds and one
    `block-merge` to the chair, one `note-to-riskofficer` to a seat, one
    `no_action` to nobody. The trigger fires LATER, which is the loosening
    direction, and the reason is that those five were never the CEO's to
    decide.
    """
    def _count(x) -> Optional[int]:
        if x is None:
            return None
        try:
            return int(x if isinstance(x, int) else len(x))
        except (TypeError, ValueError):
            return None

    by_actor = {a: 0 for a in NEXT_ACTORS}
    explicit_rows = 0
    if isinstance(open_recommendations, list):
        for row in open_recommendations:
            verdict = next_actor(row)
            by_actor[verdict["actor"]] = by_actor[verdict["actor"]] + 1
            if verdict["basis"] == "explicit":
                explicit_rows = explicit_rows + 1
        # UNKNOWN counts. A row whose next actor could not be read is work the
        # CEO may still owe, and reporting it as zero would be this fund's
        # oldest mistake in a new place.
        open_recommendations = [r for r in open_recommendations
                                if next_actor(r)["actor"] in ("ceo", "unknown")]

    parts = {
        "open_recommendations": _count(open_recommendations),
        "pending_orders": _count(pending_orders),
        "requests_awaiting_approval": _count(open_requests),
    }
    unreadable = sorted(k for k, v in parts.items() if v is None)
    total = sum(v for v in parts.values() if v is not None)
    elsewhere = by_actor["chair"] + by_actor["seat"]
    return {
        "total": total,
        "complete": not unreadable,
        "unreadable": unreadable,
        "components": parts,
        # The full split, so nothing routed away from the CEO becomes invisible.
        "by_actor": by_actor,
        # Work that is real and is somebody else's. Rendered beside the CEO
        # figure, never folded into it.
        "not_ceo_load": elsewhere,
        # How many rows STATED their next actor instead of being inferred.
        # Zero today: nothing writes the field yet, and a reader deserves to
        # know the count rests on inference rather than on declaration.
        "explicit_next_actor": explicit_rows,
        "rules_version": NEXT_ACTOR_RULES_VERSION,
        "threshold": COO_TRIAGE_THRESHOLD,
        "coo_triage_due": total >= COO_TRIAGE_THRESHOLD,
        "note": (
            f"{total} item(s) awaiting the CEO against a triage trigger of "
            f"{COO_TRIAGE_THRESHOLD}"
            + (f"; {by_actor['unknown']} of them because their next actor could "
               "not be determined, which counts rather than disappears"
               if by_actor["unknown"] else "")
            + (f". {elsewhere} further recommendation(s) are open work owned by "
               "the chair or another seat, counted here so they stay visible "
               "and excluded from the CEO's figure because they were never his "
               "to decide" if elsewhere else "")
            + (f" — {', '.join(unreadable)} could not be counted, so the real "
               "total is at least this" if unreadable else "")
            + (". A COO triage dispatch is DUE; the CTO fires it when a session "
               "is live — crossing this line triggers nothing by itself."
               if total >= COO_TRIAGE_THRESHOLD else ".")
        ),
    }


def utc_day_bounds(now: Any = None) -> tuple[str, str, str]:
    """(day, start, end) for the UTC day containing ``now``.

    UTC because the event log is UTC and the fund's day boundary is the
    venue's, not the reader's — a local bucket would move a dispatch to a
    different day depending on who opened the page.
    """
    from datetime import datetime, timedelta, timezone
    n = now or datetime.now(timezone.utc)
    start = n.replace(hour=0, minute=0, second=0, microsecond=0)
    return (start.date().isoformat(), start.isoformat(),
            (start + timedelta(days=1)).isoformat())


def seat_telemetry(day_runs: Optional[list[dict[str, Any]]],
                   activity: dict[str, dict[str, Any]],
                   day: str,
                   seats: Optional[list[str]] = None) -> dict[str, Any]:
    """Per-seat: is it running now, how often today, at what token cost.

    The CEO's question, verbatim in intent: "is it running, how often today, at
    what token cost". Three facts, and each has a different way of being absent,
    so each carries its own absence rather than a shared zero:

      * ``running_now`` — the dispatch/resolve fold the desk already computes.
        A dispatch with nothing back IS a working seat; the spine cannot watch
        a model think and does not pretend to. A seat whose dispatch has
        RETURNED is not running: ``running_now`` is False and
        ``awaiting_review`` is True. Measured 2026-08-22 before this split
        existed: `running_now` was True for the builder and the analyst
        simultaneously, 21 and 19 hours after both had returned and been
        recorded — a chair reading the payload to see whether a parallel slot
        was free would have been told the bench was full.
      * ``runs_today`` — exact, from a SQL day window, NOT from the capped
        25-run payload. On a day with 26 runs the capped fold would quietly
        drop one, and the dropped one would look like a seat that did nothing.
      * ``tokens_today`` — ``None`` when NO run reported a figure, and
        ``tokens_partial`` when some did and some did not. A sum over 2 of 5
        runs is a FLOOR, and rendering it as a total understates the bill by
        whatever the missing runs cost. The client renders it with a "≥".

    ``day_runs`` is None when the flight recorder could not be read at all. The
    whole block then reports ``readable: false`` and every figure is absent —
    an unreadable recorder must never render as a quiet day.

    Token totals are also broken out BY MODEL, because pricing lives in the UI
    (docs/COST_MODEL_2026-08-20.md's table, mirrored in seatLib.ts) and a blended
    dollar figure computed here would need a second copy of that table. One
    price table, in the place that renders the dollars.
    """
    names = list(seats or REQUEST_KINDS.values())
    readable = day_runs is not None
    out: dict[str, Any] = {}
    for seat in names:
        act = activity.get(seat) or {}
        working = act.get("status") == "working"
        awaiting = act.get("status") == "awaiting_review"
        row: dict[str, Any] = {
            "running_now": working,
            # The third state, carried here too: a returned dispatch is an
            # obligation on the chair, and a telemetry block that dropped it
            # would render the seat as idle — which is how a review queue
            # becomes invisible.
            "awaiting_review": awaiting,
            "returned_run_id": act.get("returned_run_id") if awaiting else None,
            # The task and the clock belong to the dispatch, which is still
            # open in BOTH live states — so they survive the return rather
            # than blanking the moment the run lands.
            "running_task": act.get("task") if (working or awaiting) else None,
            "running_since": act.get("since") if (working or awaiting) else None,
            "runs_today": None,
            "tokens_today": None,
            "tokens_partial": False,
            "runs_missing_tokens": None,
            "tokens_by_model": {},
            "last_run_at": None,
        }
        if readable:
            mine = [r for r in (day_runs or []) if r.get("seat") == seat]
            toks = [r.get("tokens") for r in mine
                    if isinstance(r.get("tokens"), int)]
            by_model: dict[str, int] = {}
            for r in mine:
                t = r.get("tokens")
                if isinstance(t, int):
                    m = (r.get("model") or "unknown").strip() or "unknown"
                    by_model[m] = by_model.get(m, 0) + t
            row["runs_today"] = len(mine)
            row["tokens_today"] = sum(toks) if toks else None
            row["runs_missing_tokens"] = len(mine) - len(toks)
            # Partial only when there IS a figure that is incomplete. With no
            # figure at all the total is absent, which is a stronger statement
            # than "at least zero".
            row["tokens_partial"] = bool(toks) and len(toks) < len(mine)
            row["tokens_by_model"] = by_model
            times = sorted(r.get("resolved_at") or "" for r in mine)
            row["last_run_at"] = times[-1] if times and times[-1] else None
        out[seat] = row

    return {
        "day": day,
        "readable": readable,
        "seats": out,
        "note": (
            f"Per-seat telemetry for {day} (UTC). Runs and tokens are folded "
            "from the flight recorder over that day's window, not from the "
            "capped run list the payload carries."
            if readable else
            "The flight recorder could not be read, so no seat's run count or "
            "token cost is known for today. This is an absence, not a quiet "
            "day."
        ),
    }


#: How many runs the desk payload carries. Named because it is TWO things: the
#: list the UI renders, and the window review-detection searches — so a reader
#: changing it should see both consequences in one place.
_RUNS_IN_PAYLOAD = 25


def view(store: Any, deskstore: Any = None,
         pending_orders: Any = None) -> dict[str, Any]:
    artifacts = _artifacts()
    reqs = _requests(store)
    runs, open_recs = [], []
    # None, not [] — an unreadable recorder must not fold into "no runs today".
    day, day_start, day_end = utc_day_bounds()
    day_runs: Optional[list[dict[str, Any]]] = None
    # None until proven otherwise, for the same reason: `_activity` must be
    # able to tell "the recorder could not be read" from "it was read and held
    # no matching run", and only the first makes review-detection unavailable.
    seen_runs: Optional[list[dict[str, Any]]] = None
    if deskstore is not None:
        try:
            runs = deskstore.runs(limit=_RUNS_IN_PAYLOAD)
            seen_runs = runs
            open_recs = deskstore.open_recommendations()
        except Exception as e:  # noqa: BLE001
            logger.info("desk runs unavailable: %s", e)
        # Separate try: the day window is a different query and a store that
        # predates `runs_between` (or a failure on just this one) must degrade
        # to "telemetry unreadable", never to a fabricated zero, and must not
        # take the rest of the payload down with it.
        try:
            day_runs = deskstore.runs_between(day_start, day_end)
        except Exception as e:  # noqa: BLE001
            logger.info("desk day window unavailable: %s", e)
    # AFTER the runs are loaded, because the third dispatch state is detected
    # by matching an open dispatch's identifiers against a recorded run. Passed
    # None when the recorder could not be read, which makes `review_detectable`
    # false rather than reporting WORKING as a confident answer.
    activity = _activity(store, runs=seen_runs, runs_limit=_RUNS_IN_PAYLOAD)
    open_reqs = [r for r in reqs if r["status"] == "open"]
    killed = [a for a in artifacts if a["status"] == "killed"]
    return {
        "roster": [{**r, "activity": activity.get(r["agent"],
                                             {"status": "idle", "task": None,
                                              "since": None,
                                              "last_delivered": None})}
                   for r in ROSTER],
        "protocol": [
            "every artifact is falsifiable or it is rejected",
            "nothing an agent claims is acted on until verified against the "
            "repo or the data",
            "adversary review is blind — the artifact, never the reasoning",
            "the chain (mechanism -> adversary -> CTO verifies -> belt -> gate "
            "-> operator's click) skips no stage",
            "agents never propose orders, click approvals, write to the event "
            "log, or tune thresholds",
        ],
        "artifacts": artifacts,
        "requests": reqs,
        # The flight recorder: every dispatch whole, and every recommendation
        # with the seat that made it - attribution is the point.
        "runs": runs,
        "open_recommendations": open_recs,
        "open_requests": len(open_reqs),
        # The COO triage counter (CEO's standing rule, >=50 items awaiting the
        # CEO). Rendered as a chip on the CEO desk and the CTO console; it
        # signals, never fires. Since 2026-08-22 it counts rows whose NEXT
        # ACTOR is the CEO rather than rows whose status label reads open —
        # `by_actor` in the payload carries everyone else's, so nothing that
        # left this number left the surface.
        "desk_load": desk_load(open_recs, pending_orders, open_reqs),
        # Per-seat: running now, runs today, tokens today (CEO ask, 2026-08-21).
        # Rolled up here rather than on the client so the day count is exact
        # instead of folded from the capped 25-run list above.
        "seat_telemetry": seat_telemetry(day_runs, activity, day),
        "kills": len(killed),
        "execution_note": (
            "The spine records requests; it does not run agents. Requests are "
            "picked up by the CTO session and dispatched to the bench — what "
            "the button guarantees is that the ask is a durable fact in the "
            "event log, not that it executes by itself."),
        "note": (f"{len(artifacts)} artifact(s) on the desk, {len(killed)} "
                 f"killed by adversarial review, {len(open_reqs)} request(s) "
                 f"waiting for the CTO session"),
    }
