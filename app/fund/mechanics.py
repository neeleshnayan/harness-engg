"""How a hunch becomes a position, and what dies on the way.

The Studio's other surfaces answer operational questions — anything broken, anything
waiting on me. This one answers a different question: **what is this system
actually doing, and how is it changing?** It is the mechanics of the fund read as a
process rather than a state.

Structured as selection, because that is genuinely what the machinery does:

  * VARIATION      a candidate is a grid, not a strategy. `{top_n: [3,5],
                   hold_days: [21,63]}` is four organisms, and the sweep is the
                   population.
  * SELECTION      the gate kills. 19 submitted, 16 judged, 3 passed — and the
                   interesting artefact is not the survivors, it is the ranked
                   list of what did the killing.
  * INHERITANCE    strategies carry parent_id / children / members, so groups
                   compose out of other groups.
  * THE SELECTOR   itself under selection. v1 passed noise half the time, v2 was
                   failed by perfect foresight, v3 was a loosening nobody noticed,
                   v4 was measured against an adversary. Four generations of the
                   thing doing the judging.

One honesty rule runs through it, and it is the reason this module exists rather
than a nicer chart of the same numbers: **the evolution layer does not exist yet.**
There is no population search, no inheritance between candidates, no
specialisation. Two sleeves with a comparison rule is selection with a population
of two — the minimum that can be called selection at all. Anything here that is
scaffolded-but-not-running says so in the payload, because a page that drew a
phylogenetic tree we do not have would be the most persuasive lie the fund has
ever told about itself.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Criterion names, shortened for display, keyed by a phrase in the failure text.
#: The gate returns sentences rather than codes on purpose — a score invites
#: negotiation — so grouping them for a chart means matching on the sentence.
_CAUSES = (
    ("cost robustness was never measured", "Cost never swept"),
    ("breakeven", "Dies at realistic costs"),
    ("independent folds", "Edge did not persist across folds"),
    ("fold(s) could be measured", "Too few folds to judge"),
    ("NOT TESTABLE", "Not testable on our history"),
    ("for simply owning it", "Loses to buy & hold"),
    ("probabilistic Sharpe", "Sharpe inside the noise"),
    ("is the minimum before a Sharpe", "Too few trades"),
    ("capacity", "Capacity too small"),
    # Kept SEPARATE from the retention failure below, and that separation is the
    # whole point. "Placed no trades" is an absence — the test did not happen —
    # while "kept 14% of its edge" is a measurement that came back bad. Bucketing
    # them together would put the absence-is-never-zero error into the chart the
    # operator uses to decide what to fix.
    ("placed no trades at all", "Holdout never traded (absence, not failure)"),
    ("of its edge out of sample", "Edge did not survive out of sample"),
    ("holdout", "Did not survive the holdout"),
)


def _cause(failure: str) -> str:
    low = (failure or "").lower()
    for needle, label in _CAUSES:
        if needle.lower() in low:
            return label
    return "Other"


#: The selector's own lineage. Each generation, what killed it, and the measured
#: number that did the killing. Encoded here rather than parsed out of gate.py's
#: docstring because a display should not depend on prose formatting — but every
#: figure below is recorded in that docstring and in docs/GATE_CALIBRATION.
GATE_LINEAGE = [
    {"version": "v1", "died_of": "Passed noise about half the time",
     "evidence": "Random-entry strategies cleared it ~50% of the time. Two "
                 "criteria passed BY never having been measured.",
     "metric": "~50% false positives"},
    {"version": "v2", "died_of": "Failed perfect foresight",
     "evidence": "An oracle that could see the future failed it, on two counts "
                 "that were ours: retention divided a 12-month return by a "
                 "3-month one, and a 91-day test leg gave a 63-day hold ONE "
                 "decision.",
     "metric": "oracle rejected"},
    {"version": "v3", "died_of": "Was a loosening nobody noticed",
     "evidence": "Dropped to 2 folds and left the share floor at `<`, so 1-of-2 "
                 "passed as a 'majority'. Shipped with a commit message about "
                 "rigour. Found by outside review.",
     "metric": "discrimination 1.21"},
    {"version": "v4", "died_of": None,
     "evidence": "4 folds, strict majority in integer arithmetic. Measured "
                 "against noise, against a real edge, and against a lucky-window "
                 "adversary that killed the proposed replacement.",
     "metric": "2.9% false positives · 22.8% power at Sharpe 1.0"},
]

#: What the fund has and has not built of the evolutionary idea. Present so the
#: page can show the ladder honestly instead of implying the top rung exists.
EVOLUTION_LADDER = [
    {"rung": "Variation within a candidate", "status": "running",
     "detail": "A grid sweep IS a population. Every candidate ships as several "
               "parameter organisms and the sweep picks one."},
    {"rung": "Selection by a calibrated gate", "status": "running",
     "detail": "The gate kills, and it has been measured from both sides plus "
               "against an adversary. This is the part that works."},
    {"rung": "Inheritance / composition", "status": "partial",
     "detail": "Strategies carry parent_id, children and member weights, so "
               "groups compose. Nothing yet BREEDS a new candidate from two "
               "survivors — composition is authored, not inherited."},
    {"rung": "Two competing sleeves", "status": "scaffolded",
     "detail": "sleeve_beta_500 pre-registered; sleeve_alpha_500 constituted at "
               "$0, admitted only by passing the gate and retired if it cannot "
               "beat its beta sibling net of costs. Neither is funded yet."},
    {"rung": "Population search", "status": "blocked",
     "detail": "Blocked on hardware, not design: one LEAN container on 15.2 GB, "
               "~20 engine runs per candidate. A population of 50 across 20 "
               "generations is ~230 hours. A vectorised pre-screen is the unlock."},
    {"rung": "Specialisation by domain", "status": "not started",
     "detail": "Nothing yet gives a lineage its own universe or horizon to "
               "specialise into."},
]


#: Event types worth a mark on a timeline, with the phase of the machinery each
#: one belongs to. Deliberately a small subset: the log carries thousands of
#: NavStruck and OrderFilled rows, and a timeline that plotted all of them would
#: bury the four events a month that actually changed how this fund works.
MILESTONES: dict[str, tuple[str, str]] = {
    "StrategyRegistered": ("born", "a strategy entered the world"),
    "StrategyBacktested": ("judged", "a verdict was recorded against it"),
    "StrategyStateChanged": ("promoted", "its state moved — research to deployed, "
                                         "or out"),
    "StrategyArchived": ("died", "retired from the book"),
    "StrategyAddedToParent": ("composed", "a group took a member"),
    "StrategyMembershipWeighted": ("composed", "member weights were set"),
    "ExitRuleSet": ("committed", "an exit was promised before the position existed"),
    "ExitRuleTriggered": ("fired", "the pre-committed exit fired and raised a "
                                   "closing proposal"),
    "ExitRuleOverridden": ("overridden", "a fired exit was deliberately not taken, "
                                         "with a recorded reason"),
    "RiskLimitsSet": ("mandate", "the risk mandate changed"),
    "TradingHalted": ("halted", "the kill switch engaged"),
    "TradingResumed": ("resumed", "trading was allowed again by a human"),
    "PostmortemRecorded": ("learned", "a postmortem was written"),
    "ThesisCreated": ("thesis", "an investment thesis was formed"),
}

#: Changes to the MACHINERY, which the event log cannot know about — it records
#: what the fund did, not what was built. Every figure here is recorded in
#: gate.py's version history and in docs/GATE_CALIBRATION_2026-08-18.md.
#:
#: Dated in **UTC**, to match the event log. This matters more than it sounds: the
#: log timestamps the exit wiring at 2026-08-17T19:58Z while the local calendar
#: had already rolled to the 18th, so dating these marks by the authoring day put
#: every cause a full day AFTER the effects it produced. An axis that inverts
#: causality is worse than no axis, because it reads perfectly well.
BUILD_MARKS = [
    {"at": "2026-08-17", "phase": "selector", "label": "Gate v2",
     "detail": "A null audit measured v1 passing random strategies ~50% of the "
               "time. v2 added the walk-forward requirement and closed two "
               "criteria that had passed BY never being measured."},
    {"at": "2026-08-17", "phase": "selector", "label": "Gate v3",
     "detail": "Fold geometry made conditional on the strategy's own holding "
               "period, after perfect foresight failed v2. This change was also a "
               "LOOSENING that nobody noticed at the time."},
    {"at": "2026-08-17", "phase": "selector", "label": "Gate v4",
     "detail": "Outside review found v3's 1-of-2 'majority'. v4 requires 4 folds "
               "and a strict majority in integer arithmetic. Measured: 2.9% false "
               "positives, 22.8% power at Sharpe 1.0."},
    {"at": "2026-08-17", "phase": "controls", "label": "Exits wired",
     "detail": "ExitRuleTriggered had been emitted by no code at all. The exit "
               "check and the risk monitor were connected to the scheduler, with a "
               "heartbeat so a missing tick reads as an absence. Verified live at "
               "19:58Z: ExitRuleSet, OrderProposed, ExitRuleTriggered."},
    {"at": "2026-08-17", "phase": "controls", "label": "Judgement register",
     "detail": "Every self-chosen threshold registered with its basis, "
               "falsification and review trigger. Immediately caught three risk "
               "defaults looser than the mandate in force."},
]


def _timeline(events: Any, candidates: Any) -> dict[str, Any]:
    """The fund's own history, on one axis, from the log rather than from memory.

    Uses the event log as the spine because that IS the fund's history — an
    event-sourced system does not need a separate chronology, and building one
    would create a second place to disagree with the truth.

    Two streams share the axis and are labelled differently, because they answer
    different questions. `events` are things the FUND did, and they carry a seq
    from the hash chain, so each is independently verifiable. `builds` are changes
    to the MACHINERY, which the log cannot know about — it records behaviour, not
    construction — so those are dated claims rather than chained facts.
    """
    rows = (events or {}).get("events") or []
    marks: list[dict[str, Any]] = []
    per_day: Counter = Counter()
    kinds: Counter = Counter()

    for e in rows:
        t = e.get("type")
        ts = str(e.get("ts") or "")
        day = ts[:10]
        if day:
            per_day[day] += 1
        if t not in MILESTONES:
            continue
        phase, meaning = MILESTONES[t]
        kinds[phase] += 1
        p = e.get("payload") or {}
        marks.append({
            "at": ts, "day": day, "seq": e.get("seq"), "type": t,
            "phase": phase, "meaning": meaning,
            "subject": (p.get("name") or p.get("symbol")
                        or p.get("strategy_id") or p.get("aggregate_id")),
            "reason": p.get("reason") or p.get("note") or p.get("override_reason"),
            "verifiable": True,
        })

    # Candidate verdicts, which are the actual test runs the operator asked to see
    # against the axis. Kept separate from `marks`: a verdict is produced by the
    # factory rather than appended as one of the milestone types above.
    verdicts = []
    for c in ((candidates or {}).get("candidates") or []):
        fin = str(c.get("finished_at") or "")
        if not fin:
            continue
        verdicts.append({
            "at": fin, "day": fin[:10],
            "algorithm": c.get("algorithm"),
            "candidate_id": c.get("candidate_id"),
            "passed": c.get("passed"),
            "causes": sorted({_cause(f) for f in (c.get("failures") or [])}),
            "is_calibration": str(c.get("algorithm") or "").startswith(
                ("null_", "oracle_")),
        })
    verdicts.sort(key=lambda r: r["at"])
    marks.sort(key=lambda r: (r["at"] or ""))

    days = sorted(set(list(per_day) + [v["day"] for v in verdicts]
                      + [b["at"] for b in BUILD_MARKS]) - {""})
    return {
        "days": [{"day": d, "events": per_day.get(d, 0),
                  "verdicts": sum(1 for v in verdicts if v["day"] == d),
                  "builds": sum(1 for b in BUILD_MARKS if b["at"] == d)}
                 for d in days],
        "marks": marks,
        "verdicts": verdicts,
        "builds": BUILD_MARKS,
        "phases": dict(kinds),
        "window": {"first": days[0] if days else None,
                   "last": days[-1] if days else None,
                   "days": len(days)},
        "note": (f"{len(marks)} milestone event(s) and {len(verdicts)} test "
                 f"verdict(s) across {len(days)} day(s). Events carry a chain seq "
                 f"and are independently verifiable; build marks are dated claims "
                 f"about the machinery, which the log cannot know about."),
        "caveat": "Days are UTC, for both streams — the log timestamps the exit "
                  "wiring at 2026-08-17T19:58Z while the local calendar had "
                  "already rolled over, so mixing the two would place causes a day "
                  "after their effects. The axis only reaches back to this fund's "
                  "first event and the machinery it describes is days old: a short "
                  "axis is the honest picture of a system this young, not a "
                  "sampling window.",
    }


def build(candidates: Any = None, strategies: Any = None,
          observations: Any = None, approvals: Any = None,
          exits: Any = None, events: Any = None,
          gate_version: str = "") -> dict[str, Any]:
    """Assemble the mechanics view. Every block degrades to a stated absence.

    Facts arrive already resolved, on the same reasoning as the digest: this is a
    reading over the machinery, not a second place that knows how to run it.
    """
    out: dict[str, Any] = {"gate_version": gate_version}
    for name, fn in (
        ("funnel", lambda: _funnel(observations, candidates, strategies)),
        ("selection_pressure", lambda: _pressure(candidates)),
        ("cohort", lambda: _cohort(candidates)),
        ("lineage", lambda: _lineage(strategies)),
        ("selector", lambda: {"generations": GATE_LINEAGE,
                              "current": gate_version}),
        ("ladder", lambda: {"rungs": EVOLUTION_LADDER,
                            "note": _ladder_note()}),
        ("timeline", lambda: _timeline(events, candidates)),
        ("waiting_on_you", lambda: _waiting(approvals, exits)),
    ):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001
            logger.warning("mechanics block %s unavailable: %s", name, e)
            out[name] = {"unavailable": f"{type(e).__name__}: {e}"[:200]}
    return out


def _funnel(observations: Any, candidates: Any, strategies: Any) -> dict[str, Any]:
    """Where things go from and where they stop.

    Each step reports its own count or says it could not be counted. A funnel with
    a silent zero in the middle reads as a pipeline nobody is feeding, which is a
    very different claim from a subsystem being unavailable.
    """
    steps: list[dict[str, Any]] = []

    read: Optional[int] = None
    if observations is not None:
        cov = observations or {}
        read = cov.get("observations") if isinstance(cov, dict) else None
    steps.append({"step": "Read", "count": read,
                  "what": "filings and transcripts extracted, each with the "
                          "verbatim quote that proves it",
                  "absent_note": None if read is not None else
                  "the research store is unavailable, so this is UNCOUNTED "
                  "rather than zero"})

    # RESEARCH ONLY. The scoreboard counts every candidate, instruments included,
    # and using it here told a flatly false story: "19 swept -> 3 survived ->
    # 3 deployed". All three passes were `null_random_smallcap` — RANDOM NOISE
    # leaking through an older gate — and the three deployed strategies are not
    # those three, they predate the gate and currently FAIL it. Two separate
    # misreadings stacked into one plausible funnel, which is exactly why the
    # calibration organisms are split out below instead of averaged in.
    rows = (candidates or {}).get("candidates") or []
    research = [c for c in rows
                if not str(c.get("algorithm") or "").startswith(("null_", "oracle_"))]
    calib = [c for c in rows if c not in research]
    r_judged = [c for c in research if c.get("passed") is not None]
    r_passed = [c for c in research if c.get("passed") is True]
    variants = 0
    for c in research:
        v = 1
        for vals in (c.get("grid") or {}).values():
            v *= max(1, len(vals or []))
        variants += v

    steps.append({"step": "Swept", "count": len(research),
                  "what": f"research candidates submitted — each one a GRID, so "
                          f"the population actually explored is {variants} "
                          f"parameter variants"})
    steps.append({"step": "Judged", "count": len(r_judged),
                  "what": "reached a verdict. The gap to Swept is runs still in "
                          "flight, not failures"})
    steps.append({"step": "Survived", "count": len(r_passed),
                  "what": "cleared every criterion. Passing is not deployment — it "
                          "means worth a human look"})

    deployed = None
    if strategies is not None:
        srows = (strategies or {}).get("strategies")
        if isinstance(srows, list):
            deployed = sum(1 for s in srows
                           if str(s.get("state") or "").lower() == "deployed")
    steps.append({"step": "Deployed", "count": deployed,
                  "what": "carrying real (paper) risk, each behind a human click",
                  "absent_note": (
                      "NOT downstream of Survived. These predate the gate and all "
                      "three currently FAIL it — the arrow does not connect, and "
                      "drawing it as a funnel step would imply they earned their "
                      "place")})

    return {
        "steps": steps,
        "killed": len(r_judged) - len(r_passed),
        "note": (candidates or {}).get("scoreboard", {}).get("note") or "",
        "honest_note": (
            f"A low survival rate is the factory working — the bar exists to kill "
            f"things cheaply. But read the two numbers that matter: {len(r_passed)} "
            f"of {len(r_judged)} research candidates have ever cleared the gate, "
            f"and the strategies the fund actually holds are not among them."),
        "calibration": {
            "submitted": len(calib),
            "judged": sum(1 for c in calib if c.get("passed") is not None),
            "passed": sum(1 for c in calib if c.get("passed") is True),
            "note": (
                "Instruments, not attempts to make money. Nulls are random by "
                "construction, so a null PASSING is a measured leak in the gate "
                "rather than a discovery — and three of them did, which is the "
                "evidence that drove the gate from v1 to v4. They are excluded "
                "from the funnel above because averaging an instrument in with a "
                "research attempt corrupts the rate in both directions."),
            "caveat": (
                "A stored verdict does not currently record WHICH gate version "
                "judged it, so these passes cannot be attributed to a version from "
                "the data alone — only dated. gate.py exists to make that "
                "attribution possible and the candidate record does not carry it "
                "through, which is a real gap."),
        },
    }


def _pressure(candidates: Any) -> dict[str, Any]:
    """What actually does the killing, ranked. The most useful chart here.

    A gate that only ever fires one rule is a one-rule gate wearing five, and
    that is worth seeing at a glance.
    """
    rows = (candidates or {}).get("candidates") or []
    causes: Counter = Counter()
    for c in rows:
        for f in (c.get("failures") or []):
            causes[_cause(f)] += 1
    total = sum(causes.values())
    judged = sum(1 for c in rows if c.get("passed") is not None)
    return {
        "causes": [{"cause": k, "count": v,
                    "share_pct": round(100.0 * v / total, 1) if total else None}
                   for k, v in causes.most_common()],
        "total_failures": total,
        "judged": judged,
        "distinct_causes": len(causes),
        "note": (f"{len(causes)} distinct criteria have killed something. A gate "
                 f"that only ever fires one rule is a one-rule gate wearing five."
                 if causes else
                 "nothing has been killed yet, which at this stage means nothing "
                 "has been judged rather than that everything passed"),
    }


def _cohort(candidates: Any) -> dict[str, Any]:
    """Every candidate as an organism: its variants, its verdict, its cause of death.

    ``variants`` is the product of the grid — the population size the sweep
    actually explored, which is the number that makes 'variation' concrete.
    """
    rows = (candidates or {}).get("candidates") or []
    out = []
    for c in rows:
        grid = c.get("grid") or {}
        variants = 1
        for vals in grid.values():
            variants *= max(1, len(vals or []))
        failures = c.get("failures") or []
        out.append({
            "candidate_id": c.get("candidate_id"),
            "algorithm": c.get("algorithm"),
            "state": c.get("state"),
            "passed": c.get("passed"),
            "variants": variants,
            "grid": {k: list(v or []) for k, v in grid.items()},
            "winner": c.get("winner"),
            "causes": sorted({_cause(f) for f in failures}),
            "failures": failures,
            "finished_at": c.get("finished_at"),
            # A calibration organism is not a research candidate. Mixing them
            # would make the survival rate meaningless in both directions.
            "is_calibration": str(c.get("algorithm") or "").startswith(
                ("null_", "oracle_")),
        })
    out.sort(key=lambda r: (r.get("finished_at") or ""), reverse=True)
    return {"candidates": out,
            "calibration_count": sum(1 for r in out if r["is_calibration"]),
            "note": "calibration organisms (nulls, oracles) are flagged: they are "
                    "instruments for measuring the gate, not attempts to make "
                    "money, and counting them in a survival rate corrupts it"}


def _lineage(strategies: Any) -> dict[str, Any]:
    """Groups and their members — the inheritance that does exist.

    Honest about its own limit: composition here is AUTHORED. Nothing breeds a
    new candidate from two survivors, so this is a hierarchy, not descent.
    """
    rows = (strategies or {}).get("strategies") or []
    nodes = []
    for s in rows:
        nodes.append({
            "strategy_id": s.get("strategy_id"),
            "name": s.get("name"),
            "state": s.get("state"),
            "depth": s.get("depth") or 0,
            "parent_id": s.get("parent_id"),
            "is_container": bool(s.get("is_container")),
            "members": list(s.get("members") or []),
            "children": [c.get("strategy_id") if isinstance(c, dict) else c
                         for c in (s.get("children") or [])],
            "allocation_pct": s.get("allocation_pct"),
            "actual_pct": s.get("actual_pct"),
            "pnl_usd": s.get("pnl_usd"),
            "assets": list(s.get("assets") or []),
        })
    containers = [n for n in nodes if n["is_container"]]
    return {"nodes": nodes, "containers": len(containers),
            "note": "parent/child and member weights are real, so groups compose "
                    "out of groups. But composition is AUTHORED — nothing here "
                    "breeds a new candidate from two survivors, so this is a "
                    "hierarchy rather than descent."}


def _ladder_note() -> str:
    running = sum(1 for r in EVOLUTION_LADDER if r["status"] == "running")
    return (f"{running} of {len(EVOLUTION_LADDER)} rungs are actually running. The "
            f"upper rungs are named so the ladder can be read honestly — drawing a "
            f"phylogeny we do not have would be the most persuasive lie this fund "
            f"could tell about itself.")


def _waiting(approvals: Any, exits: Any) -> dict[str, Any]:
    """The end of the pipeline: what has reached a human and stopped.

    This is the only place the machinery genuinely halts, and it halts on purpose.
    """
    items = []
    pending = (approvals or {}).get("pending") or []
    for o in pending:
        items.append({
            "kind": "approval",
            "symbol": o.get("symbol"), "side": o.get("side"),
            "qty": o.get("qty"), "strategy_id": o.get("strategy_id"),
            "rationale": o.get("rationale"),
            "why_here": "the machine proposed this and stopped. Nothing executes "
                        "without a human click — that is the property the whole "
                        "harness is built on",
        })
    fired = (exits or {}).get("fired") or []
    for r in fired:
        items.append({
            "kind": "exit_fired",
            "symbol": r.get("symbol"), "strategy_id": r.get("strategy_id"),
            "rationale": r.get("reason"),
            "why_here": "a pre-committed exit fired. It was written down before "
                        "the position existed, so this decision is not being made "
                        "by someone holding it",
        })
    return {"items": items, "count": len(items),
            "note": (f"{len(items)} decision(s) waiting on you"
                     if items else
                     "nothing is waiting on a human right now")}
