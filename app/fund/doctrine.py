"""The seven stages, and whether the fund satisfies them RIGHT NOW.

`docs/FUND_GENESIS.md` is the canon. This module exists so the workflow can be
rendered as a live surface rather than a static page, and it is built on the same
property that makes `judgement.py` worth having: **status is READ, not restated.**

A doctrine page that hardcoded "stage 02: HOLDS" would be the exact failure the
doctrine is about. Stage 02 exists because a control was documented as operating
while nothing called it — reproducing that shape in the page that describes it
would be almost funny, and would certainly be the thing that decays first.

So each stage carries one of two kinds of status, and says which:

  measured  — a `check` callable reads the live system. If it raises, the stage
              reports UNKNOWN rather than passing or failing, because "could not
              tell" is its own answer (see the absence doctrine).
  attested  — a human claim with no automatic reading available, carrying the
              evidence that supports it. Honest, and weaker, and labelled weaker.

Stages 03 and 07 are attested GAPS today. That is deliberate: an operating manual
that cannot report its own violations is an aspiration with numbering.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CANON = "docs/FUND_GENESIS.md"

#: Statuses. `unknown` is a first-class answer, not an error state.
HOLDS, GAP, UNKNOWN = "holds", "gap", "unknown"


class Stage:
    def __init__(self, n: int, title: str, *, ask: str, why: str,
                 earned_by: str, mechanism: str = "",
                 check: Optional[Callable[[], dict[str, Any]]] = None,
                 attested: Optional[str] = None, gap: str = ""):
        self.n = n
        self.title = title
        self.ask = ask
        self.why = why
        self.earned_by = earned_by
        self.mechanism = mechanism
        self._check = check
        self.attested = attested
        self.gap = gap

    def status(self) -> dict[str, Any]:
        if self._check is None:
            return {"status": self.attested or UNKNOWN, "basis": "attested",
                    "detail": self.gap or "no automatic reading exists for this "
                                          "stage; the status is a human claim"}
        try:
            got = self._check()
            return {"basis": "measured", **got}
        except Exception as e:  # noqa: BLE001
            logger.info("doctrine stage %s: could not read: %s", self.n, e)
            return {"status": UNKNOWN, "basis": "measured",
                    "detail": f"could not read the live system ({e}). UNKNOWN is "
                              f"not the same as satisfied"}

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "title": self.title, "ask": self.ask,
                "why": self.why, "earned_by": self.earned_by,
                "mechanism": self.mechanism, **self.status()}


# --- the readings -------------------------------------------------------------

def _check_wiring() -> dict[str, Any]:
    """Stage 02. Are the scheduled controls actually ticking?

    Reads the heartbeat rather than the code. The question is not "does a caller
    exist" — that was true of the endpoint nobody hit — but "did it run".
    """
    from app.fund import heartbeat
    rep = heartbeat.report()
    critical = ("risk_monitor", "exit_check")
    rows = {r["job"]: r for r in rep["jobs"]}
    unknown = [j for j in critical if rows.get(j, {}).get("ok") is None]
    stale = [j for j in critical if rows.get(j, {}).get("ok") is False]
    if stale:
        return {"status": GAP,
                "detail": f"{', '.join(stale)} overdue — whatever they enforce is "
                          f"currently unenforced, and their silence is not calm"}
    if unknown:
        return {"status": UNKNOWN,
                "detail": f"{', '.join(unknown)} not yet observed in this process. "
                          f"Another process may hold the scheduler lease, so this "
                          f"is neither broken nor fine"}
    return {"status": HOLDS,
            "detail": "the risk monitor and the exit check are both ticking; a "
                      "missing tick would show here as an absence"}


def _check_register() -> dict[str, Any]:
    """Stage 05. Does every self-chosen number still match its written reason?"""
    from app.fund.judgement import review
    r = review()
    if r["drifted"]:
        keys = ", ".join(d["key"] for d in r["drifted"])
        return {"status": GAP,
                "detail": f"{keys} drifted from the registered value — the reason "
                          f"on file describes a different number"}
    due = [d["key"] for d in r["due_for_review"]]
    if due:
        return {"status": GAP,
                "detail": f"{len(due)} past its backstop review date: "
                          f"{', '.join(due[:4])}"}
    judged = r["by_basis"].get("judged", 0)
    return {"status": HOLDS,
            "detail": f"{r['count']} decisions registered, none drifted, none "
                      f"overdue. {judged} are JUDGED — chosen and undemonstrated, "
                      f"which is fine while it stays visible"}


def _check_open_change() -> dict[str, Any]:
    """Stage 07. Is every prior gate version still readable?

    A weak reading of a strong rule, and labelled as such below. It cannot tell
    whether a change had a written reason — only whether history was preserved
    COMPLETE, which is the mechanical half. A partial historical copy silently
    inherits current defaults, so an old verdict would be re-read against today's
    bar without anyone noticing.
    """
    from app.fund import gate
    current = set(gate.CRITERIA)
    versions = {n: getattr(gate, n) for n in dir(gate)
                if n.startswith("CRITERIA_V")}
    if not versions:
        return {"status": GAP, "detail": "no prior gate version is preserved, so "
                                         "old verdicts cannot be re-read against "
                                         "the bar they actually cleared"}
    partial = [n for n, c in versions.items() if set(c) != current]
    if partial:
        return {"status": GAP,
                "detail": f"{', '.join(sorted(partial))} preserved only partially "
                          f"— evaluate() merges over current defaults, so these "
                          f"would silently inherit {gate.GATE_VERSION} values"}
    return {"status": HOLDS,
            "detail": f"gate is {gate.GATE_VERSION}; "
                      f"{len(versions)} prior version(s) preserved complete, so an "
                      f"old verdict can be re-read against its own bar. This checks "
                      f"only that history survived — not that each change carried a "
                      f"written reason, which no code can check"}


def stages() -> list[Stage]:
    return [
        Stage(1, "Build with a falsification",
              ask="What would I see if this were wrong — and would I see it?",
              why="A mechanism ships with the observation that would prove it "
                  "wrong, not just with tests. Tests check what you thought of; a "
                  "falsification commits you in advance to what would change your "
                  "mind.",
              earned_by="A position with no falsification cannot be wrong, only "
                        "unlucky. This is also what produced NOT TESTABLE as a "
                        "verdict distinct from failure — absence of evidence had "
                        "been silently scored as evidence.",
              mechanism="every gate criterion; docs/FUND_GENESIS.md",
              attested=HOLDS,
              gap="Attested. No code can check that a falsification condition is "
                  "a good one, only that somebody wrote it down."),
        Stage(2, "Wire it to a clock",
              ask="Who calls this, on what schedule, and how would I know if it "
                  "stopped?",
              why="A control nobody calls is a document. Find the caller, confirm "
                  "it runs unattended, and make a MISSING tick visible as an "
                  "absence rather than as silence.",
              earned_by="2026-08-18. RiskMonitor.run() — the only code that trips "
                        "the -10% drawdown and -4% daily-loss halts — had ZERO "
                        "callers, while the framework document said the kill "
                        "switches would act without asking. EXIT_RULE_TRIGGERED "
                        "was emitted by no code at all.",
              mechanism="app/fund/heartbeat.py; GET /fund/liveness",
              check=_check_wiring),
        Stage(3, "Calibrate from both sides",
              ask="What does this say about noise, and about a real edge?",
              why="Bound the instrument below and above. An instrument that passes "
                  "noise is decoration; one that rejects perfect foresight is "
                  "broken. Report the DISCRIMINATION, never one side alone.",
              earned_by="Gate v1 passed random strategies ~50% of the time. An "
                        "oracle with perfect foreknowledge failed v2 on our own "
                        "arithmetic. v4 measures at 2.9% false positives and only "
                        "22.8% power against a real Sharpe-1.0 strategy.",
              mechanism="scripts/null_audit.py, oracle_audit.py, "
                        "gate_power_audit.py",
              attested=GAP,
              gap="The simulation is done (4,000 draws). The REAL belt has still "
                  "never produced a v4 false-positive rate — a model of an "
                  "instrument is not a run of it. A LEAN null audit under v4 is "
                  "in flight; 6 clean nulls bound the rate under ~39%, and "
                  "bounding it under 10% needs about 29."),
        Stage(4, "Beat the incumbent against an adversary",
              ask="What is this mechanism FOR, and is my replacement better at "
                  "that?",
              why="A candidate improvement does not ship on being better on the "
                  "headline metric. It must survive the specific adversary the "
                  "mechanism exists to defeat, constructed on purpose, every draw "
                  "a known fake.",
              earned_by="2026-08-18. A pooled out-of-sample Sharpe gave 50% more "
                        "power at identical discrimination and the recommendation "
                        "was written. Against a one-fold wonder it was 2-3x easier "
                        "to fool, swallowing three fakes in four at the strongest "
                        "level. The extra power WAS the weakness. The incumbent "
                        "was kept.",
              mechanism="scripts/gate_power_audit.py --adversary",
              attested=HOLDS,
              gap="Attested. Whether an adversary was run is a fact about a "
                  "session, not a readable property of the system."),
        Stage(5, "Register the value and the wiring",
              ask="Did I choose this number, and does anything check that it still "
                  "means what I wrote?",
              why="Every self-chosen number carries its basis, what would falsify "
                  "it, a review trigger and a backstop date. The register READS "
                  "live values — a second copy of a number is a second place to "
                  "disagree with the code. It registers WIRING too: a "
                  "correctly-configured unreachable control is the same class of "
                  "lie as a threshold that silently moved.",
              earned_by="2026-08-18. Within minutes of existing it caught three "
                        "risk defaults LOOSER than the mandate in force — "
                        "drawdown 0.15 against 0.10 — so a restore from an old "
                        "snapshot would have widened the kill switch by half with "
                        "nobody deciding to. It then flagged the v3->v4 gate "
                        "change unprompted.",
              mechanism="app/fund/judgement.py; GET /fund/judgement",
              check=_check_register),
        Stage(6, "Get reviewed by someone blind to your reasoning",
              ask="Who checked this who could not see how I got here?",
              why="Two standing lenses — one macro/diversification/drawdown, one "
                  "microstructure/execution/capacity — review independently. Then "
                  "every claim is verified in the repo before it is acted on, "
                  "including the flattering ones.",
              earned_by="2026-08-18. Both lenses independently found the unwired "
                        "controls. Our own suite stayed green through the gate "
                        "regression because two tests had been written to ASSERT "
                        "the loosening — a test can only catch what it was not "
                        "written to bless.",
              mechanism="two consultant lenses, advisory only",
              attested=HOLDS,
              gap="Attested. These are analytical lenses derived from public "
                  "investment philosophies, never presented as the views of the "
                  "real individuals."),
        Stage(7, "Change it in the open, in either direction",
              ask="Is this a loosening, and does the written reason say so?",
              why="A threshold moves only by a versioned change with a written "
                  "reason. Tightenings attract scrutiny naturally; loosenings pass "
                  "as housekeeping, and quiet loosening is the single forbidden "
                  "move.",
              earned_by="2026-08-18. Gate v3 dropped the fold requirement to 2 and "
                        "left the share floor compared with '<', so 1-of-2 folds "
                        "passed as a majority. Its discrimination was 1.21 — "
                        "barely distinguishable from a coin — and it shipped with "
                        "a commit message about rigour.",
              mechanism="app/fund/gate.py GATE_VERSION + CRITERIA_V*",
              check=_check_open_change),
    ]


#: The absence doctrine. One rule under all seven, and the source of most of the
#: bugs above: missing information has to LOOK missing. Every collapse here was
#: found in live code, which is why it is data rather than prose.
ABSENCE = [
    ("No trades", "0% retention",
     "A test leg that never traded says nothing either way — usually warm-up "
     "starvation"),
    ("Unmeasurable", "Failed",
     "NOT TESTABLE means the fund cannot examine this yet; the answer is more "
     "history, not a lower bar"),
    ("Unreadable", "Unchanged",
     "A register falling back to a remembered value asserts knowledge it does not "
     "have"),
    ("Silence", "Calm",
     "No alarm is evidence of calm only if something was looking"),
    ("Not yet observed", "Fine or broken",
     "Another process may hold the lease; both other answers are claims the "
     "process cannot support"),
    ("Never measured", "Robust",
     "Two gate criteria once passed by never having been tested against"),
    ("Unreviewed", "Dismissed",
     "376 observations carried one review, made by the person testing the review "
     "button"),
    ("Limit not breached", "Limit works",
     "A control that has never fired is a control nobody has verified"),
]

#: Not preferences. Stated here so they are surfaced next to the workflow rather
#: than living only in a builder's working memory, which is what erodes.
INVARIANTS = [
    "The machine proposes; the human clicks. No automated path executes. The "
    "moment an agent path completes a trade, every claim this system makes about "
    "itself stops being true.",
    "The builder does not select securities. Analysis of measured properties — "
    "shortlists, correlations, sizing arithmetic — yes. The instrument choice and "
    "the click stay with the operator.",
]


def review() -> dict[str, Any]:
    """The whole doctrine with live status, worst news first in the summary."""
    rows = [s.to_dict() for s in stages()]
    gaps = [r for r in rows if r["status"] == GAP]
    unknown = [r for r in rows if r["status"] == UNKNOWN]
    measured = [r for r in rows if r["basis"] == "measured"]
    return {
        "canon": CANON,
        "stages": rows,
        "absence_doctrine": [{"this": a, "is_never": b, "because": c}
                             for a, b, c in ABSENCE],
        "invariants": INVARIANTS,
        "gaps": [r["n"] for r in gaps],
        "unknown": [r["n"] for r in unknown],
        "measured_count": len(measured),
        "note": _note(rows, gaps, unknown, measured),
    }


def _note(rows: list, gaps: list, unknown: list, measured: list) -> str:
    bits = [f"{len(measured)} of {len(rows)} stages have a live reading; the rest "
            f"are attested"]
    if gaps:
        bits.append(f"stage(s) {', '.join(str(r['n']) for r in gaps)} are GAPS "
                    f"right now")
    if unknown:
        bits.append(f"stage(s) {', '.join(str(r['n']) for r in unknown)} could not "
                    f"be read — unknown, which is not satisfied")
    if not (gaps or unknown):
        bits.append("every stage either holds or is attested to hold")
    return "; ".join(bits)
