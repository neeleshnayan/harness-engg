"""Deterministic, versioned desk hygiene — the autopolicy pattern for bookkeeping.

CEO instruction 6 (2026-08-23, verbatim): *"we need a mechanism so the desk is
structured and maintained automatically without you handholding every clean and
message pass"*.

WHAT THIS IS ALLOWED TO DO, STATED FIRST BECAUSE IT IS THE WHOLE SAFETY
ARGUMENT. This policy closes BOOKKEEPING and nothing else. It may mark a desk
request RESOLVED and a recommendation DONE — the two terminal states that say
"this was served / this was executed" — and it may raise a FLAG for a human to
confirm. It may never approve, accept, stage, decline, or reject anything; it
may never touch an order, a threshold, an exit rule or the approval guard. The
allowlist is a module constant, the guard is a function, and a test walks every
rule and asserts the state it produces is on the list. That test exists because
two tests once ASSERTED a gate loosening: a rules table that can be read but
not violated is the only kind worth shipping near a decision surface.

WHY A RULES TABLE AND NOT A FUNCTION. Every rule carries its id, the version it
entered at, the EVIDENCE JOIN it fires on, the written reason, and what it
produces. The riskofficer audits this policy's closes exactly as it audits
auto-approvals, and an audit needs to read the rule that fired, not reconstruct
it from a diff. ``POLICY_VERSION`` moves when the table moves, and the version
travels in every payload the desk serves.

EVIDENCE JOINS ONLY, AND THE DIFFERENCE IS THE POINT. An evidence join is an
IDENTIFIER matching an identifier: this request's trace, this dispatch's
request_id, this run's declared ``serves_requests``. Prose matching is not an
evidence join — a rec whose text names a commit that is an ancestor of HEAD is
FLAGGED for one-click confirmation and never closed, because a heuristic over
free English rots silently and reports the rot as a count.

MEASURED ON THE LIVE RECORD BEFORE THE FIRST LINE WAS WRITTEN (2026-08-23,
92 desk requests / 97 runs), and it is the finding that shaped this module:
**not one of the 92 requests can be joined to a run today.** Zero runs carry a
request's trace_id; ``DeskDispatched`` has been written 24 times for 92
requests and not at all since 2026-08-21T19:02Z. So the rules below fire on
nothing until the LINK is written — and this module therefore reports
``unlinkable`` beside its proposals, loudly, because a hygiene engine that
returned "0 closes" against a desk of 92 open rows would be reporting a clean
desk when what it means is a missing edge. Absence is never zero, including
here.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)


#: Bumped whenever ``HYGIENE_RULES`` changes in any way a reader could act on:
#: a rule added, retired, or its evidence join widened or narrowed. Published
#: in the desk payload so a reader can tell WHICH policy produced a close they
#: are looking at — the same discipline the autopolicy envelope and the gate
#: version follow.
POLICY_VERSION = "hygiene v1 (2026-08-23)"

#: The ONLY states this policy may put a row into. Named as a constant so the
#: guard, the tests and the audit read the same list, and so widening it is a
#: visible one-line diff rather than a new branch somewhere.
#:
#: `resolved` — a desk request that was SERVED. Its terminal state already.
#:
#: Deliberately absent, and each for its own reason: `accepted`/`staged` are the
#: CEO's decision and the chair's staging; `rejected`/`declined` are a NO, and a
#: machine that can say no on the firm's behalf is a machine that can kill work
#: silently; `noted` and `done` mean a human read or executed something.
#:
#: A `mark_rec_done` action was written and then DELETED before this shipped:
#: the spec's three rules close requests and flag recommendations, so nothing
#: produced it. An action with no rule is an unwired branch that widens the
#: guard's surface for free, and it comes back the day a rule needs it.
BOOKKEEPING_STATUSES = ("resolved",)

#: What a rule may produce. `flag` writes nothing at all — it is a proposal for
#: a human's one click.
RULE_ACTIONS = ("close_request", "flag")

#: The actions that WRITE. Everything else is advisory.
CLOSING_ACTIONS = ("close_request",)

#: The status each closing action produces. One mapping, so the guard and the
#: applier cannot disagree about what a rule does.
ACTION_STATUS = {"close_request": "resolved"}


class Rule:
    """One hygiene rule, whole, so an auditor reads the rule and not a diff."""

    __slots__ = ("rule_id", "since", "title", "action", "evidence",
                 "written_reason", "authority")

    def __init__(self, rule_id: str, since: str, title: str, action: str,
                 evidence: str, written_reason: str, authority: str):
        if action not in RULE_ACTIONS:
            raise ValueError(f"action must be one of {RULE_ACTIONS}")
        self.rule_id = rule_id
        self.since = since
        self.title = title
        self.action = action
        self.evidence = evidence
        self.written_reason = written_reason
        self.authority = authority

    @property
    def produces(self) -> Optional[str]:
        return ACTION_STATUS.get(self.action)

    def as_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "since": self.since,
                "title": self.title, "action": self.action,
                "produces": self.produces, "evidence": self.evidence,
                "written_reason": self.written_reason,
                "authority": self.authority}


HYGIENE_RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="H1",
        since="v1 (2026-08-23)",
        title="a blind-review request whose verdict run has delivered is served",
        action="close_request",
        evidence="request.kind == 'attack' AND a run with seat='adversary', "
                 "status='delivered' and a non-empty verdict is joined to the "
                 "request by identifier (trace_id | DeskDispatched.request_id | "
                 "run.meta.serves_requests)",
        written_reason=(
            "MEASURED LEAK: two delivered adversary verdicts (requests "
            "1c53589f and b6f4a407, both served by run-adversary-batch2 on "
            "2026-08-22T19:35Z) were still status `open` on the live spine "
            "when this rule was written — the queue does not close on a "
            "verdict. A request whose named artifact exists is served; "
            "whether the verdict was a KILL or a SURVIVES is a different row "
            "and a different decision."),
        authority="DESK_ENGINE_V1_2026-08-23.md section 5, CEO instruction 6",
    ),
    Rule(
        rule_id="H2",
        since="v1 (2026-08-23)",
        title="an approved request whose dispatch delivered is served",
        action="close_request",
        evidence="request.status == 'approved' AND a run with status="
                 "'delivered' is joined to the request by identifier "
                 "(trace_id | DeskDispatched.request_id | "
                 "run.meta.serves_requests)",
        written_reason=(
            "MEASURED: 37 desk requests sat at status `approved` on "
            "2026-08-23. At least four of them (34338ef6, d7f38be2, 75ca57a7, "
            "252bce7b — all four confirmed `approved` on the live payload) "
            "name work this seat's own record says has merged: the belt bar "
            "cache (D15), the hazard batch and the sign-inverted exit trigger "
            "(D17/D18), the broker-drift alarm. A desk request records an ASK; a "
            "delivered run is the artifact that served it. Whether the work "
            "was any good is judged on the run's own recommendations, not by "
            "leaving the ask open forever."),
        authority="DESK_ENGINE_V1_2026-08-23.md section 5, CEO instruction 6",
    ),
    Rule(
        rule_id="H3",
        since="v1 (2026-08-23)",
        title="a recommendation citing a commit already in HEAD is PROBABLY DISCHARGED",
        action="flag",
        evidence="the recommendation's text contains a token git resolves to a "
                 "commit that is an ancestor of HEAD",
        written_reason=(
            "FLAG, NEVER CLOSE, and the distinction is the module's whole "
            "premise: a sha lifted out of prose is prose matching, and the "
            "emergency sweep that produced this engine found six finished "
            "rows by grepping their text for 'EXECUTED'. That was the right "
            "measure that day and is the wrong permanent one. A flag costs "
            "the chair one click and cannot close anything by itself."),
        authority="DESK_ENGINE_V1_2026-08-23.md section 5, CEO instruction 6",
    ),
)

RULES_BY_ID = {r.rule_id: r for r in HYGIENE_RULES}


def assert_bookkeeping_only(action: str, status: Optional[str]) -> None:
    """Refuse anything this policy is not allowed to write.

    THE ONE GUARD THAT MATTERS, and it is deliberately paranoid about its own
    inputs rather than trusting the rules table: a rule added later with the
    right shape and the wrong ``action`` must be stopped here, at the write,
    not at review. Called by the applier on every single proposal — a guard
    with no caller is the unwired kill switch, which this firm has priced.
    """
    if action not in RULE_ACTIONS:
        raise ValueError(
            f"unknown hygiene action {action!r} — refused; a policy that "
            f"guesses at an action it does not recognise is a policy that can "
            f"be widened by a typo")
    if action == "flag":
        if status is not None:
            raise ValueError(
                "a flag writes nothing — refusing to apply a status with it")
        return
    if status not in BOOKKEEPING_STATUSES:
        raise ValueError(
            f"auto-hygiene may only write {BOOKKEEPING_STATUSES}, not "
            f"{status!r}. Closing bookkeeping is this policy's whole mandate; "
            f"approving, accepting, staging or declining is not, and never "
            f"becomes so by a rule that says it does")
    if ACTION_STATUS.get(action) != status:
        raise ValueError(
            f"action {action!r} produces {ACTION_STATUS.get(action)!r}, not "
            f"{status!r} — refused rather than reconciled")


# ------------------------------------------------------- the evidence join --
#
# THREE WAYS A RUN CAN BE JOINED TO A REQUEST, ALL BY IDENTIFIER, none by prose.
# They are listed in order of how much they prove, and each proposal names the
# one it used (`join`) so an auditor can weigh it:
#
#   dispatch_request_id  a DeskDispatched event NAMES the request, and a run
#                        carries that dispatch's trace. The strongest: two
#                        independent writes agree.
#   trace_id             the run carries the request's own trace_id verbatim.
#   declared             the run's `meta.serves_requests` lists the request id.
#                        The chair's structured statement at record time — an
#                        id, not a sentence. Weakest of the three, and it is
#                        still an identifier: nothing here reads English.
#
# There WAS a `JOIN_KINDS` tuple here and it was deleted before shipping:
# nothing read it, each rule's `evidence` string already names all three, and
# a constant no code consults is a label. Every rule's `join` field is checked
# against this comment by review, not by a tuple nobody imports.


def _serves_requests(run: Any) -> list[str]:
    """Request ids a run DECLARES it served, from ``meta.serves_requests``.

    A list of ids, validated as strings and nothing else. If a chair writes a
    sentence into this field it yields no ids rather than a fuzzy match — the
    field is a join key or it is nothing.
    """
    meta = run.get("meta") if isinstance(run, dict) else None
    raw = (meta or {}).get("serves_requests") if isinstance(meta, dict) else None
    if not isinstance(raw, (list, tuple)):
        return []
    return [x.strip() for x in raw if isinstance(x, str) and x.strip()]


def serving_runs(request: dict[str, Any], runs: Iterable[dict[str, Any]],
                 dispatches: Iterable[dict[str, Any]] = ()) -> list[tuple[dict, str]]:
    """Every run joined to this request, with the join that found it.

    Returns ``[(run, join_kind), ...]``, newest-resolved first, or an empty
    list — which means UNLINKABLE, not "nothing happened". The caller must
    report the difference; see the module docstring for the measurement that
    makes this the common case today.
    """
    rid = str(request.get("request_id") or "").strip()
    if not rid:
        return []
    trace = str(request.get("trace_id") or "").strip()
    dispatch_traces = {
        str(d.get("trace_id") or "").strip()
        for d in dispatches
        if str(d.get("request_id") or "").strip() == rid
    } - {""}
    # A dispatch whose task_id IS the request id (the shape every 2026-08-20
    # dispatch used) also identifies runs that carry that id as their trace.
    dispatch_traces |= {
        str(d.get("task_id") or "").strip()
        for d in dispatches
        if str(d.get("request_id") or "").strip() == rid
    } - {""}

    out: list[tuple[dict, str]] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        rtrace = str(run.get("trace_id") or "").strip()
        if rtrace and rtrace in dispatch_traces:
            out.append((run, "dispatch_request_id"))
        elif trace and rtrace == trace:
            out.append((run, "trace_id"))
        elif rid in _serves_requests(run):
            out.append((run, "declared"))
    out.sort(key=lambda p: str(p[0].get("resolved_at") or ""), reverse=True)
    return out


def _delivered(run: dict[str, Any]) -> bool:
    """Did this run DELIVER?

    ``status`` is one of delivered / failed / aborted, and NULL means the chair
    recorded no outcome. Only ``delivered`` counts. An unrecorded outcome is
    not a delivery — reading NULL as success is exactly the absence-scored-as-
    value error, and here it would close a desk request on a dispatch that may
    have died.
    """
    return str(run.get("status") or "").strip().lower() == "delivered"


def _citation(run: dict[str, Any], join: str) -> str:
    return (f"run {run.get('run_id')} ({run.get('seat')}, "
            f"resolved {run.get('resolved_at')}) joined by {join}")


# --------------------------------------------------------- the sha reader ---
#
# Seven-to-forty hex characters, with AT LEAST ONE LETTER. The letter
# requirement is not cosmetic: `2026080` and `1885` are hex-legal and this desk
# is made of dates and dollar figures. Measured on the live corpus before the
# rule shipped — see tests/test_deskhygiene.py. Anything that survives here is
# still handed to git, which is the actual arbiter.
_SHA_RE = re.compile(r"\b(?=[0-9a-f]{7,40}\b)[0-9a-f]*[a-f][0-9a-f]*\b")


def cited_commits(text: Any) -> list[str]:
    """Candidate commit ids in a recommendation's prose, deduped, in order."""
    if not isinstance(text, str):
        return []
    seen, out = set(), []
    for m in _SHA_RE.finditer(text.lower()):
        tok = m.group(0)
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def evaluate(*, requests: Iterable[dict[str, Any]],
             runs: Iterable[dict[str, Any]],
             recommendations: Iterable[dict[str, Any]] = (),
             dispatches: Iterable[dict[str, Any]] = (),
             is_ancestor: Optional[Callable[[str], Optional[bool]]] = None,
             ) -> dict[str, Any]:
    """Run the policy. READ-ONLY: this function writes nothing, ever.

    Returns proposals (what H1/H2 would close, each with its citation), flags
    (what H3 noticed, for a human's click), and — as loudly as the proposals —
    the rows that could not be joined to any evidence at all.

    ``is_ancestor`` answers "is this token a commit already in HEAD": True,
    False, or **None for could-not-tell**. None is carried through as
    ``unresolvable`` rather than collapsed into False, because "git was not
    reachable" and "that commit is not in HEAD" are different facts and only
    one of them is about the recommendation.
    """
    requests = [r for r in requests if isinstance(r, dict)]
    runs = [r for r in runs if isinstance(r, dict)]
    dispatches = [d for d in dispatches if isinstance(d, dict)]

    proposals: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    unlinkable: list[dict[str, Any]] = []
    linked_but_undelivered: list[dict[str, Any]] = []

    for req in requests:
        status = str(req.get("status") or "").strip().lower()
        if status not in ("open", "approved"):
            continue
        joined = serving_runs(req, runs, dispatches)
        if not joined:
            unlinkable.append({
                "request_id": req.get("request_id"),
                "status": status,
                "seat": req.get("seat"),
                "task": req.get("task"),
                "why": ("no run carries this request's trace_id, no "
                        "DeskDispatched event names it, and no run declares "
                        "it in meta.serves_requests — there is no evidence "
                        "edge to read, which is NOT the same as no work "
                        "having been done"),
            })
            continue
        delivered = [(r, j) for r, j in joined if _delivered(r)]
        if not delivered:
            linked_but_undelivered.append({
                "request_id": req.get("request_id"),
                "status": status,
                "runs": [r.get("run_id") for r, _ in joined],
                "why": ("a run is joined but its recorded outcome is not "
                        "`delivered` — a failed, aborted or UNRECORDED "
                        "dispatch does not serve a request"),
            })
            continue
        run, join = delivered[0]
        kind = str(req.get("kind") or "").strip().lower()
        if kind == "attack":
            verdict = (run.get("verdict") or "").strip()
            if str(run.get("seat") or "").strip().lower() == "adversary" and verdict:
                proposals.append({
                    "rule_id": "H1",
                    "action": "close_request",
                    "status": ACTION_STATUS["close_request"],
                    "target": {"kind": "request",
                               "request_id": req.get("request_id")},
                    "join": join,
                    "citation": (f"{_citation(run, join)}; verdict: "
                                 f"{verdict[:200]}"),
                    "evidence": {"run_id": run.get("run_id"),
                                 "seat": run.get("seat"),
                                 "run_status": run.get("status"),
                                 "verdict_present": True},
                })
                continue
            # An attack request joined to a delivered run that carries NO
            # verdict falls through to H2 only if it is approved; otherwise it
            # is reported, not closed. A review with no recorded verdict is
            # the one case where "the seat returned" and "the question was
            # answered" come apart.
            if status != "approved":
                linked_but_undelivered.append({
                    "request_id": req.get("request_id"),
                    "status": status,
                    "runs": [run.get("run_id")],
                    "why": ("joined to a delivered run with no recorded "
                            "verdict — a blind review closes on its verdict, "
                            "not on the seat having returned"),
                })
                continue
        if status == "approved":
            proposals.append({
                "rule_id": "H2",
                "action": "close_request",
                "status": ACTION_STATUS["close_request"],
                "target": {"kind": "request", "request_id": req.get("request_id")},
                "join": join,
                "citation": _citation(run, join),
                "evidence": {"run_id": run.get("run_id"),
                             "seat": run.get("seat"),
                             "run_status": run.get("status")},
            })

    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        if str(rec.get("status") or "open") not in ("open", "accepted", "staged"):
            continue
        shas = cited_commits(rec.get("text"))
        if not shas or is_ancestor is None:
            continue
        for sha in shas:
            verdict = is_ancestor(sha)
            if verdict is True:
                flags.append({
                    "rule_id": "H3",
                    "action": "flag",
                    "status": None,
                    "flag": "probably_discharged",
                    "target": {"kind": "recommendation",
                               "run_id": rec.get("run_id"),
                               "rec_id": rec.get("rec_id")},
                    "citation": (f"cites {sha}, which is an ancestor of HEAD"),
                    "requires": "one-click chair confirmation — never auto-closed",
                })
                break
            if verdict is None:
                flags.append({
                    "rule_id": "H3",
                    "action": "flag",
                    "status": None,
                    "flag": "unresolvable_citation",
                    "target": {"kind": "recommendation",
                               "run_id": rec.get("run_id"),
                               "rec_id": rec.get("rec_id")},
                    "citation": (f"cites {sha}, and git could not be asked "
                                 f"whether it is in HEAD"),
                    "requires": "a human look — UNCHECKED, which is not 'not discharged'",
                })
                break

    n_req = sum(1 for r in requests
                if str(r.get("status") or "").lower() in ("open", "approved"))
    # WHICH RULES ACTUALLY RAN. H3 needs a git ancestry oracle; a caller that
    # cannot supply one (the desk read, which must not shell out to git on
    # every page load) gets H3 NOT EVALUATED — and says so, rather than
    # reporting zero flags. "No flags" and "the rule did not run" are
    # different facts and only one is about the desk.
    not_evaluated = ([] if is_ancestor is not None
                     else [{"rule_id": "H3",
                            "why": "no git ancestry oracle was supplied, so "
                                   "commit citations were not checked"}])
    evaluated = [r.rule_id for r in HYGIENE_RULES
                 if r.rule_id not in {x["rule_id"] for x in not_evaluated}]
    return {
        "policy_version": POLICY_VERSION,
        "rules": [r.as_dict() for r in HYGIENE_RULES],
        "rules_evaluated": evaluated,
        "rules_not_evaluated": not_evaluated,
        "proposals": proposals,
        "flags": flags,
        "unlinkable": unlinkable,
        "linked_but_undelivered": linked_but_undelivered,
        "counts": {
            "candidate_requests": n_req,
            "proposals": len(proposals),
            "flags": len(flags),
            "unlinkable": len(unlinkable),
            "linked_but_undelivered": len(linked_but_undelivered),
        },
        "note": (
            f"{len(proposals)} bookkeeping close(s) proposed under "
            f"{POLICY_VERSION} over {n_req} open/approved request(s)"
            + (f"; {len(unlinkable)} request(s) carry NO evidence edge at all "
               "— no trace match, no DeskDispatched naming them, no run "
               "declaring them — so the engine cannot tell served from "
               "unserved and reports neither"
               if unlinkable else "")
            + (f"; {len(flags)} recommendation(s) flagged for a chair click"
               if flags else "")
            + ("; H3 was NOT evaluated (no git oracle supplied), so commit "
               "citations are UNCHECKED rather than clean"
               if not_evaluated else "")
            + "."),
    }


def apply_proposal(proposal: dict[str, Any], *,
                   close_request: Callable[[str, str], Any]) -> dict[str, Any]:
    """Apply ONE proposal, through the guard, with its citation attached.

    Deliberately NOT a bulk loop over ``evaluate``'s output: each proposal is
    guarded, applied and recorded on its own, so a refusal in the middle of a
    batch cannot leave half a sweep unrecorded. The caller (the route) loops.

    A ``flag`` is refused here rather than silently skipped. A flag has no
    write and the caller asking to apply one is a caller with the wrong idea
    about what this policy does.
    """
    action = str(proposal.get("action") or "")
    status = proposal.get("status")
    assert_bookkeeping_only(action, status)
    if action not in CLOSING_ACTIONS:
        raise ValueError(
            f"{action!r} writes nothing — a flag is a proposal for a human's "
            "click, and applying one would be this policy claiming a "
            "confirmation nobody gave")
    citation = str(proposal.get("citation") or "").strip()
    if not citation:
        raise ValueError(
            "refusing to apply a hygiene close with no citation — an "
            "unexplained auto-close is indistinguishable from a bug, and the "
            "riskofficer audits this policy from its citations")
    rule_id = str(proposal.get("rule_id") or "")
    if rule_id not in RULES_BY_ID:
        raise ValueError(f"unknown rule {rule_id!r}")
    target = proposal.get("target") or {}
    note = f"[{POLICY_VERSION} | {rule_id}] {citation}"
    rid = str(target.get("request_id") or "")
    if not rid:
        raise ValueError("close_request needs a request_id")
    result = close_request(rid, note)
    return {"applied": True, "rule_id": rule_id, "action": action,
            "status": status, "target": target, "citation": citation,
            "policy_version": POLICY_VERSION, "result": result}
