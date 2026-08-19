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
                rows[rid] = {**p, "status": "open"}
        elif t == EventType.DESK_REQUEST_RESOLVED.value:
            rid = p.get("request_id")
            if rid in rows:
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


def view(store: Any, deskstore: Any = None) -> dict[str, Any]:
    artifacts = _artifacts()
    reqs = _requests(store)
    activity = _activity(store)
    runs, open_recs = [], []
    if deskstore is not None:
        try:
            runs = deskstore.runs(limit=25)
            open_recs = deskstore.open_recommendations()
        except Exception as e:  # noqa: BLE001
            logger.info("desk runs unavailable: %s", e)
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
