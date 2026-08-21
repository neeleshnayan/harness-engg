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


def _activity(store: Any) -> dict[str, dict[str, Any]]:
    """What each seat is doing RIGHT NOW, folded from dispatch/resolve events.

    The spine cannot see a Claude agent thinking; what it can see is the CTO
    session recording "dispatched X to seat Y" and "Y delivered Z". That is the
    truthful resolution available, and the UI renders exactly it - a spinner
    pretending to watch the agent's cursor would be theatre.

    A dispatch with no matching resolution is WORKING. Resolution clears it and
    becomes last_delivered. A seat with neither is idle - and idle is a real
    state, not a gap: a bench seat that is never idle is a bottleneck.
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
    out = {}
    for seat in list(REQUEST_KINDS.values()):
        row = seats.get(seat, {})
        w = row.get("working_on")
        out[seat] = {
            "status": "working" if w else "idle",
            "task": (w or {}).get("task"),
            "since": (w or {}).get("at"),
            "last_delivered": row.get("last_delivered"),
        }
    return out


#: The CEO's standing triage rule (2026-08-20, CEO instruction, registered as
#: a dispatch trigger): when OPEN items on the CEO's desk exceed this, a COO
#: triage dispatch is DUE. Registered here so the count and the rule live in
#: one place — the count crossing it is a SIGNAL for the CTO to dispatch, and
#: nothing in this module or the spine dispatches anything. The ignition keys
#: stay human; this is the dashboard light, not the starter motor.
COO_TRIAGE_THRESHOLD = 20


def desk_load(open_recommendations: list[dict[str, Any]],
              pending_orders: Any, open_requests: Any) -> dict[str, Any]:
    """How many things are actually waiting for the CEO, and whether that is
    past the COO triage trigger.

    "Open items" is defined exactly, because a number whose definition drifts
    is worse than no number: open recommendations + pending orders + requests
    awaiting approval. Each component that cannot be counted is reported as
    None and named in ``unreadable`` — the total then carries ``complete:
    false``, because a partial count that reads like a full one is how a desk
    under the trigger looks quiet.
    """
    def _count(x) -> Optional[int]:
        if x is None:
            return None
        try:
            return int(x if isinstance(x, int) else len(x))
        except (TypeError, ValueError):
            return None

    if isinstance(open_recommendations, list):
        # The upstream `open_recommendations` feed includes accepted+staged
        # rows (the UI needs them to render "decided, awaiting execution");
        # the CEO's triage trigger counts only what still AWAITS the CEO.
        # Measured on this counter's first live day: it read 73 against 10
        # truly open — 3.65x the real load — and fired a triage whose own
        # memo found the miscount (COO triage #2, 2026-08-20). Same defect
        # class as CDO D4, one layer down.
        # A row with NO status counts toward load (dropping a malformed row
        # would hide work); a row explicitly decided does not.
        open_recommendations = [r for r in open_recommendations
                                if r.get("status") in (None, "open")]

    parts = {
        "open_recommendations": _count(open_recommendations),
        "pending_orders": _count(pending_orders),
        "requests_awaiting_approval": _count(open_requests),
    }
    unreadable = sorted(k for k, v in parts.items() if v is None)
    total = sum(v for v in parts.values() if v is not None)
    return {
        "total": total,
        "complete": not unreadable,
        "unreadable": unreadable,
        "components": parts,
        "threshold": COO_TRIAGE_THRESHOLD,
        "coo_triage_due": total > COO_TRIAGE_THRESHOLD,
        "note": (
            f"{total} open item(s) on the CEO's desk against a triage trigger of "
            f"{COO_TRIAGE_THRESHOLD}"
            + (f" — {', '.join(unreadable)} could not be counted, so the real "
               "total is at least this" if unreadable else "")
            + (". A COO triage dispatch is DUE; the CTO fires it when a session "
               "is live — crossing this line triggers nothing by itself."
               if total > COO_TRIAGE_THRESHOLD else ".")
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
        A dispatch with no matching resolution IS a working seat; the spine
        cannot watch a model think and does not pretend to.
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
        row: dict[str, Any] = {
            "running_now": working,
            "running_task": act.get("task") if working else None,
            "running_since": act.get("since") if working else None,
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


def view(store: Any, deskstore: Any = None,
         pending_orders: Any = None) -> dict[str, Any]:
    artifacts = _artifacts()
    reqs = _requests(store)
    activity = _activity(store)
    runs, open_recs = [], []
    # None, not [] — an unreadable recorder must not fold into "no runs today".
    day, day_start, day_end = utc_day_bounds()
    day_runs: Optional[list[dict[str, Any]]] = None
    if deskstore is not None:
        try:
            runs = deskstore.runs(limit=25)
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
        # The COO triage counter (CEO's standing rule, >20 open items). Rendered
        # as a chip on the CEO desk and the CTO console; it signals, never fires.
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
