"""Best-effort ingestion of what the firm already tested into the knowledge graph.

    ./venv/Scripts/python.exe -X utf8 scripts/kg/backfill.py --run-id <run> [--dry-run]

WHAT IT READS, AND WHAT EACH SOURCE CAN AND CANNOT GIVE.

  * ``fund_candidates`` — the gate's stored verdicts. THE ONLY SOURCE THAT
    YIELDS ROWS. One ``kg_hypothesis`` per candidate (partial header: family =
    algorithm slug, everything else NULL, because a mechanism sentence invented
    for a 2026-08-17 candidate would read exactly like one a seat wrote) and one
    ``kg_outcome`` per JUDGED candidate. A candidate that was orphaned or is
    still running gets its hypothesis and NO outcome — an interrupted run
    produced no evidence, and scoring it either way would invent one.

  * ``fund_agent_runs`` — the seat verdicts. YIELDS ZERO OUTCOME ROWS, and that
    is a finding rather than an omission: **the table has no column linking a
    run to a hypothesis or a candidate.** The only deterministic link available
    is a candidate id appearing verbatim in a run's text, which is true of 6 of
    41 candidates (measured 2026-08-23) and carries no per-candidate verdict.
    So runs are used to RESOLVE THE CITATION of a hypothesis — a real citing run
    beats the ingestion run — and the count that could not be interpreted as an
    outcome is printed rather than left implicit.
    Reproduce: ``--dry-run`` prints both counts.

  * ``fund_lean_jobs`` — the belt results, for the container cost at kill. There
    is no candidate key on a job either, so the join is (algorithm, window).
    **THAT JOIN IS AMBIGUOUS FOR 20 OF 41 CANDIDATES** (measured 2026-08-23):
    siblings of the same algorithm ran concurrently, and dividing a shared
    window between them would invent an allocation. Those report ABSENT with
    basis ``ambiguous``; five 2026-08-16/17 candidates predate the jobs table
    and report ``no_jobs``. Absence is never zero, and it is never free either.

THE FENCE. The three 2026-08-20 and three 2026-08-21 ``monthend_rebalance_flow``
rows are the cohort the constitution's clean-field amendment names: "six
independent measurements, not three before/after pairs", comparison forbidden.
They are ingested and then VOIDED with the amendment quoted as the reason, so
they stay visible, stay counted as "ever tested", and are excluded from every
comparison query automatically. The set is DERIVED from ``started_at``, and the
script REFUSES if the derivation does not yield exactly six — a fence that
silently fenced a different set would be worse than no fence.

NO EDGES ARE WRITTEN. ``same_family`` is already a column (writing it as edges
would put 253 rows into `null_random_smallcap` alone -- 23 candidates,
reproduce with `SELECT algorithm, count(*)*(count(*)-1)/2 FROM
fund_candidates GROUP BY 1 ORDER BY 2 DESC`); ``descendant_of_kill``,
``prior_art`` and ``supersedes`` are grammar-era facts nobody recorded before
the grammar existed, and reconstructing them is exactly the guess this backfill
refuses to make. In particular NO ``supersedes`` edge is written between the
2026-08-20 and 2026-08-21 monthend rows: the constitution's amendment is that a
re-run creates a NEW candidate and never recovers the old one, and an edge
saying otherwise would encode the misreading the amendment forbids.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: The dates whose candidates the clean-field amendment fences, and how many it
#: must find. Written as data so the derivation is checkable, and asserted so a
#: changed store cannot silently fence a different cohort.
FENCED_DATES = ("2026-08-20", "2026-08-21")
FENCED_EXPECTED = 6
FENCE_REASON = (
    "FENCED by the clean-field amendment of 2026-08-21: the three 2026-08-20 "
    "rows and the three 2026-08-21 rows are six independent measurements, not "
    "three before/after pairs. A re-run of a pre-instrument candidate creates a "
    "NEW candidate on a NEW window and never recovers the old row, so these "
    "measurements are excluded from every comparison query.")


def _rows(cur, sql: str, params: tuple = ()) -> list[tuple]:
    cur.execute(sql, params)
    return cur.fetchall()


def table_exists(cur, name: str) -> bool:
    """Is this relation present in the target store?

    Checked rather than assumed, because a MISSING source and an EMPTY one are
    different facts and only one of them is a statement about the fund. An
    earlier draft simply crashed on a store without ``fund_lean_jobs``, which is
    the same defect in a louder costume: unreadable is not unchanged.
    """
    cur.execute("SELECT to_regclass(%s)", (name,))
    return cur.fetchone()[0] is not None


def read_candidates(cur, with_jobs: bool = True) -> list[dict[str, Any]]:
    """Every candidate, with its container window folded in ONE query.

    The three sub-selects are the whole belt join: how many containers ran in
    this candidate's window, what they cost, and whether a sibling of the same
    algorithm was running at the same time. The last one is what makes the cost
    honest.

    ``with_jobs=False`` when the belt table is absent: every cost then reports
    basis ``unmeasured``, never ``no_jobs`` — "we did not look" and "we looked
    and there were none" are different answers.
    """
    cost_cols = ("""
               (SELECT count(*) FROM fund_lean_jobs j
                 WHERE j.algorithm = c.algorithm
                   AND j.submitted_at >= c.started_at
                   AND j.submitted_at <= COALESCE(c.finished_at, c.started_at)),
               (SELECT sum(j.wall_seconds) FROM fund_lean_jobs j
                 WHERE j.algorithm = c.algorithm
                   AND j.submitted_at >= c.started_at
                   AND j.submitted_at <= COALESCE(c.finished_at, c.started_at)),
    """ if with_jobs else " NULL::bigint, NULL::numeric,\n")
    sql = f"""
        SELECT c.candidate_id, c.algorithm, c.state, c.passed, c.failures,
               c.verdict, c.started_at, c.finished_at,
               (c.analytics IS NOT NULL) AS has_analytics,
               {cost_cols}
               (SELECT count(*) FROM fund_candidates s
                 WHERE s.algorithm = c.algorithm
                   AND s.candidate_id <> c.candidate_id
                   AND s.started_at <= COALESCE(c.finished_at, c.started_at)
                   AND COALESCE(s.finished_at, s.started_at) >= c.started_at)
          FROM fund_candidates c
         ORDER BY c.started_at, c.candidate_id
    """
    out = []
    for r in _rows(cur, sql):
        jobs, secs, siblings = r[9], r[10], int(r[11] or 0)
        if not with_jobs:
            basis, seconds = "unmeasured", None
        elif siblings:
            basis, seconds = "ambiguous", None
        elif not int(jobs or 0):
            basis, seconds = "no_jobs", None
        elif secs is None:
            basis, seconds = "unmeasured", None
        else:
            basis, seconds = "exclusive", float(secs)
        jobs = int(jobs or 0)
        out.append({
            "candidate_id": r[0], "algorithm": r[1], "state": r[2],
            "passed": r[3], "failures": r[4] or [], "verdict": r[5] or {},
            "started_at": r[6], "finished_at": r[7], "has_analytics": r[8],
            "jobs_in_window": jobs, "sibling_overlap": siblings,
            "container_seconds": seconds, "container_cost_basis": basis,
        })
    return out


def citing_runs(cur, candidate_ids: list[str]) -> dict[str, str]:
    """candidate_id -> the EARLIEST run that names it verbatim.

    An exact 12-hex-character id is a deterministic link, not a reading of
    prose: the collision probability is 2^-48 and every hit is checkable by
    grepping the stored text. Earliest-first, tie-broken on run_id, so two
    ingestions of the same store agree.
    """
    rows = _rows(cur, "SELECT run_id, COALESCE(output,'') || ' ' || "
                      "COALESCE(verdict,'') || ' ' || COALESCE(task,'') "
                      "FROM fund_agent_runs "
                      "ORDER BY resolved_at NULLS LAST, run_id")
    found: dict[str, str] = {}
    for run_id, blob in rows:
        for cid in candidate_ids:
            if cid not in found and cid in blob:
                found[cid] = run_id
    return found


def ingest(dsn: str, run_id: str, dry_run: bool = False,
           expect_fenced: int = FENCED_EXPECTED) -> dict[str, Any]:
    import psycopg
    from app.fund.knowledge import (UNCLASSIFIED_KILL_SLUG, KnowledgeGraph,
                                    slug_for_kill)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            have_cands = table_exists(cur, "fund_candidates")
            have_runs = table_exists(cur, "fund_agent_runs")
            have_jobs = table_exists(cur, "fund_lean_jobs")
            cands = read_candidates(cur, with_jobs=have_jobs) if have_cands else []
            cited = (citing_runs(cur, [c["candidate_id"] for c in cands])
                     if have_runs else {})
            runs_total = (_rows(cur, "SELECT count(*) FROM fund_agent_runs")[0][0]
                          if have_runs else None)
            jobs_total = (_rows(cur, "SELECT count(*) FROM fund_lean_jobs")[0][0]
                          if have_jobs else None)

    fenced = [c for c in cands
              if c["started_at"] and c["started_at"].date().isoformat()
              in FENCED_DATES]
    if len(fenced) != expect_fenced:
        raise SystemExit(
            f"REFUSING: the fence derivation on {FENCED_DATES} found "
            f"{len(fenced)} candidate(s), not {expect_fenced}. The cohort the "
            f"clean-field amendment names is a fixed set of six; a derivation "
            f"that returns a different number is fencing something else, and "
            f"fencing the wrong rows is worse than fencing none. Pass "
            f"--expect-fenced N deliberately if you are ingesting a store that "
            f"is not the operational one.")
    fenced_ids = {c["candidate_id"] for c in fenced}

    report: dict[str, Any] = {
        "run_id": run_id, "dry_run": dry_run,
        "sources": {}, "unclassified_kill_reasons": [],
        "cost_basis": {}, "fenced": sorted(fenced_ids),
    }

    hyp_new = out_new = 0
    judged = unjudged = 0
    voided = 0
    real_citation = 0
    slug_counts: dict[str, int] = {}
    unclassified: list[str] = []
    basis_counts: dict[str, int] = {}

    kg = None if dry_run else KnowledgeGraph(dsn=dsn)

    for c in cands:
        hid = f"cand-{c['candidate_id']}"
        cite = cited.get(c["candidate_id"])
        if cite:
            real_citation += 1
        basis_counts[c["container_cost_basis"]] = (
            basis_counts.get(c["container_cost_basis"], 0) + 1)

        if kg is not None:
            r = kg.add_hypothesis(
                id=hid, family=c["algorithm"],
                # A REAL citing run when one exists, the ingestion run
                # otherwise. Both are honest citations of DIFFERENT things and
                # the split is counted below.
                run_id=cite or run_id,
                source=None,            # unknown; never reconstructed
                source_ref=f"fund_candidates:{c['candidate_id']}",
                provenance="backfill",
                proposed_at=c["started_at"].isoformat() if c["started_at"] else None,
                on_conflict="ignore")
            hyp_new += 1 if r["created"] else 0

        # A VERDICT ONLY WHERE THE GATE REACHED ONE. `orphaned` / `running` /
        # `failed` produced no evidence; a hypothesis with no outcome reads as
        # not-yet-judged, which is what happened.
        if c["state"] != "done":
            unjudged += 1
            continue
        judged += 1

        reasons = [str(f) for f in (c["failures"] or [])]
        for f in reasons:
            s = slug_for_kill(f)
            slug_counts[s] = slug_counts.get(s, 0) + 1
            if s == UNCLASSIFIED_KILL_SLUG:
                unclassified.append(f)
        gv = (c["verdict"] or {}).get("gate_version")
        checks = (c["verdict"] or {}).get("checks")

        if kg is not None:
            o = kg.add_outcome(
                hypothesis_id=hid, stage="gate",
                verdict="pass" if c["passed"] else "fail",
                cited_run=cite or run_id,
                kill_reasons=reasons or None,
                killing_instrument=f"gate:{gv}" if gv else "gate:unrecorded",
                measured=checks if checks else None,
                container_seconds=c["container_seconds"],
                container_cost_basis=c["container_cost_basis"],
                provenance="backfill",
                at=c["finished_at"].isoformat() if c["finished_at"] else None,
                dedupe_key=f"backfill:gate:{c['candidate_id']}",
                on_conflict="ignore")
            out_new += 1 if o["created"] else 0
            if o["created"] and c["candidate_id"] in fenced_ids:
                kg.void_outcome(o["outcome_id"], FENCE_REASON, run_id)
                voided += 1

    report["sources"] = {
        "fund_candidates": {
            "present": have_cands,
            "rows_read": len(cands) if have_cands else None,
            "hypotheses_written": hyp_new,
            "outcomes_written": out_new,
            "judged": judged,
            "uninterpretable_no_verdict": unjudged,
            "with_real_citing_run": real_citation,
            "citing_the_ingestion_run": len(cands) - real_citation,
        },
        "fund_agent_runs": {
            "present": have_runs,
            "rows_read": runs_total,
            "outcomes_written": 0,
            "uninterpretable_as_outcomes": runs_total,
            "why": ("no column links a run to a hypothesis or a candidate; the "
                    "only deterministic link is a candidate id appearing "
                    "verbatim, which carries no per-candidate verdict. Used to "
                    "resolve citations only."
                    if have_runs else
                    "TABLE ABSENT from this store — every citation falls back "
                    "to the ingestion run. Unreadable, not empty."),
        },
        "fund_lean_jobs": {
            "present": have_jobs,
            "rows_read": jobs_total,
            "outcomes_written": 0,
            "uninterpretable_as_outcomes": jobs_total,
            "why": ("no candidate key on a job; joined by (algorithm, window) "
                    "to price an outcome, never to create one."
                    if have_jobs else
                    "TABLE ABSENT from this store — every container cost reads "
                    "`unmeasured`, which is not `no_jobs` and is not zero."),
        },
    }
    report["cost_basis"] = basis_counts
    report["kill_reason_slugs"] = dict(sorted(slug_counts.items(),
                                              key=lambda kv: (-kv[1], kv[0])))
    report["unclassified_kill_reasons"] = unclassified
    report["voided_by_fence"] = voided
    report["edges_written"] = 0
    return report


def render(rep: dict[str, Any]) -> str:
    L = []
    mode = "DRY RUN (nothing written)" if rep["dry_run"] else "WRITE"
    L.append(f"# knowledge-graph backfill   mode={mode}   run_id={rep['run_id']}")
    L.append("")
    for name, s in rep["sources"].items():
        L.append(f"{name}:" + ("" if s.get("present", True)
                               else "   *** TABLE ABSENT — UNREADABLE, NOT EMPTY"))
        rr = s["rows_read"]
        L.append(f"    rows read                     "
                 f"{'UNREADABLE' if rr is None else rr}")
        for k in ("hypotheses_written", "outcomes_written", "judged"):
            if k in s:
                L.append(f"    {k:<30}{s[k]}")
        bad = s.get("uninterpretable_as_outcomes",
                    s.get("uninterpretable_no_verdict"))
        L.append(f"    COULD NOT INTERPRET           "
                 f"{'UNREADABLE' if bad is None else bad}")
        if s.get("why"):
            L.append(f"        why: {s['why']}")
        if "with_real_citing_run" in s:
            L.append(f"    cited by a real run           "
                     f"{s['with_real_citing_run']}")
            L.append(f"    cited by the ingestion run    "
                     f"{s['citing_the_ingestion_run']}  "
                     f"(no run in the record names them)")
        L.append("")
    L.append("container cost attribution (basis -> candidates):")
    for k in ("exclusive", "ambiguous", "no_jobs", "unmeasured"):
        if k in rep["cost_basis"]:
            L.append(f"    {k:<12}{rep['cost_basis'][k]}"
                     + ("   <- cost ABSENT, not zero" if k != "exclusive" else ""))
    L.append("")
    L.append("kill reasons classified:")
    for slug, n in rep["kill_reason_slugs"].items():
        L.append(f"    {n:>4}  {slug}")
    unc = rep["unclassified_kill_reasons"]
    L.append("")
    L.append(f"UNCLASSIFIED kill sentences: {len(unc)}"
             + ("" if unc else "  (every stored sentence matched a rule)"))
    for u in unc[:10]:
        L.append(f"    ! {u[:150]}")
    L.append("")
    L.append(f"fenced (VOIDED, comparison forbidden): {rep['voided_by_fence']} "
             f"outcome(s) -> {', '.join(rep['fenced'])}")
    L.append(f"edges written: {rep['edges_written']}  "
             f"(family membership is a column; the rest would be reconstruction)")
    return "\n".join(L)


def main(argv: Optional[list[str]] = None) -> int:
    from app.fund.pgstore import dsn as default_dsn

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # REQUIRED, with no default. A default would manufacture the one thing the
    # graph refuses to do without: a citation.
    p.add_argument("--run-id", required=True,
                   help="the run that cites this ingestion; mandatory")
    p.add_argument("--dsn", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true", help="machine-readable report")
    p.add_argument("--expect-fenced", type=int, default=FENCED_EXPECTED,
                   help=("how many candidates the fence derivation must find; "
                         "the script REFUSES on any other number"))
    a = p.parse_args(argv)

    rep = ingest(a.dsn or default_dsn(), a.run_id, dry_run=a.dry_run,
                 expect_fenced=a.expect_fenced)
    print(json.dumps(rep, indent=2) if a.json else render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
