"""The four knowledge-graph queries, rendered for a brief.

    ./venv/Scripts/python.exe -X utf8 scripts/kg/report.py ledger <family>
    ./venv/Scripts/python.exe -X utf8 scripts/kg/report.py calibration [seat]
    ./venv/Scripts/python.exe -X utf8 scripts/kg/report.py taxonomy
    ./venv/Scripts/python.exe -X utf8 scripts/kg/report.py cheap
    ./venv/Scripts/python.exe -X utf8 scripts/kg/report.py families

THIS EXISTS SO NO READER SHIPS UNWIRED. Four query functions with no caller are
the unwired-kill-switch pattern in a reporting costume: they would look done and
answer nobody. The chair runs this and pastes the relevant block into Ed's or
Stan's brief; there is deliberately NO endpoint and NO UI, because the graph
must not become something a decision path can reach by accident.

Every block prints its citations. A number from this graph without the run ids
behind it is not admissible in a brief.

**THIS SCRIPT ISSUES NO DDL AND TAKES NO LOCK.** It never calls
``ensure_schema()``. Until 2026-08-23 it did so implicitly, because
``KnowledgeGraph.__init__`` ran the schema — and the ``DROP TRIGGER IF EXISTS``
inside it needs ACCESS EXCLUSIVE on ``kg_outcome``, so running this report
wedged the table for ~5 minutes behind one ordinary open transaction during the
validator's spot-audit. A read-only instrument that can block the store it is
reading is not read-only. If the tables do not exist here, it says so and exits
non-zero rather than printing an empty graph.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _kg():
    from app.fund.knowledge import KnowledgeGraph
    return KnowledgeGraph()


def _cites(cs) -> str:
    return "cited by: " + (", ".join(cs) if cs else "NOTHING — inadmissible")


def ledger(family: str) -> str:
    d = _kg().family_ledger(family)
    L = [f"# family ledger: {d['family']}", "", f"status: {d['status']}",
         f"note:   {d['note']}"]
    if d["status"] == "UNTESTED":
        L.append("")
        L.append("Use the word UNTESTED in the grammar header. Do NOT write a "
                 "family count of 0 — the family-wise correction has no "
                 "denominator from the record.")
        return "\n".join(L)
    # RECORDED AND JUDGED ON SEPARATE LINES, because they are separate numbers
    # and printing one of them under the word "tested" is what let the fenced
    # family read as "tested: 6, not yet judged: 6".
    L.append(f"recorded: {d['recorded']}   (provenance {d['provenance']})")
    L.append(f"judged:   {d['judged']}   killed: {d['killed']}   "
             f"survivors: {len(d['survivors'])}   "
             f"not yet judged: {len(d['unjudged'])}")
    if d["status"] == "RECORDED_UNJUDGED":
        L.append("")
        L.append("RECORDED_UNJUDGED — variants of this family are in the "
                 "record and NOT ONE of them carries a live verdict. Do not "
                 "write a tested count in the grammar header from this: the "
                 "family-wise correction wants judged variants, and there are "
                 "none.")
    L.append("")
    if d["kills_by_reason"]:
        L.append("what killed them:")
        for k in d["kills_by_reason"]:
            L.append(f"    {k['n']:>3}  {k['slug']}")
            if k["example_verbatim"]:
                L.append(f"         e.g. {k['example_verbatim'][:120]}")
    elif d["voided_outcomes"]:
        L.append("what killed them: NOTHING IS COUNTABLE — every outcome in "
                 "this family is VOIDED. That is not 'nothing died'; it is "
                 "'the measurements may not be compared'.")
    else:
        L.append("what killed them: nothing yet — no kill outcome recorded.")
    if d["survivors"]:
        L.append("")
        L.append("survivors — WITH THE INSTRUMENT THAT PASSED THEM, because a "
                 "bare count hides that a family may have survived only an "
                 "older bar:")
        for s in d["survivors"]:
            L.append(f"    {s['hypothesis_id']}  passed by "
                     f"{', '.join(s['passed_by']) or 'UNRECORDED'}   "
                     f"({', '.join(s['cited_runs'])})")
    if d["voided_outcomes"]:
        L.append("")
        L.append(f"VOIDED and excluded from every count above: "
                 f"{d['voided_outcomes']} outcome(s)")
    L.append("")
    L.append(_cites(d["citations"]))
    return "\n".join(L)


def calibration(seat: str | None) -> str:
    d = _kg().prediction_calibration(seat)
    L = [f"# prediction calibration: seat={seat or 'ALL'}", "",
         f"note: {d['note']}", ""]
    for m in d["metrics"]:
        L.append(f"{m['metric']}:  {m['note']}")
        if m["mean_abs_error"] is not None:
            L.append(f"    mean |error| = {m['mean_abs_error']:.4g}")
        for p in m["pairs"][:10]:
            L.append(f"    {p['hypothesis_id']}  predicted {p['predicted']:g} "
                     f"-> measured {p['measured']:g}  (err {p['error']:+g})")
        L.append(f"    {_cites(m['citations'])}")
        L.append("")
    if not d["metrics"]:
        L.append("No metric has both a prediction and a measurement. This is "
                 "the reader working: the pre-committed numbers it grades are "
                 "not in the record yet, and it says so rather than scoring "
                 "zero.")
    if d["hypotheses_without_seat"]:
        L.append(f"{len(d['hypotheses_without_seat'])} hypothes(es) cite a run "
                 f"that is not in fund_agent_runs — no seat, not attributed.")
    return "\n".join(L)


def taxonomy() -> str:
    d = _kg().kill_taxonomy()
    L = [f"# kill taxonomy", "", f"note: {d['note']}", ""]
    L.append(f"{'n':>4}  {'cost/kill':>10}  slug")
    for c in d["causes"]:
        mean = c["container_seconds_mean"]
        L.append(f"{c['n']:>4}  "
                 f"{('%.0fs' % mean) if mean is not None else 'ABSENT':>10}  "
                 f"{c['slug']}"
                 + ("   <- earns a pre-flight card item"
                    if c["earns_preflight_card"] else ""))
        L.append(f"          {c['cost_note']}")
        L.append(f"          families: {', '.join(c['families']) or 'UNKNOWN'}")
    # UNCONDITIONAL. The block used to be printed only when the bucket was
    # non-empty, so a reader could not tell "every sentence matched" from
    # "the classifier never ran" — both printed nothing at all.
    u = d["unclassified"]
    L.append("")
    L.append(f"UNCLASSIFIED: {u['n']} of {u['checked']} kill sentence(s) checked")
    L.append(f"    {u['note']}")
    if u["example_verbatim"]:
        L.append(f"    e.g. {u['example_verbatim'][:150]}")
    L.append("")
    L.append(f"earning a pre-flight card item: "
             f"{', '.join(d['earning_preflight_card']) or 'none yet'}")
    return "\n".join(L)


def cheap() -> str:
    d = _kg().cheap_kills()
    L = ["# cheap-kill router", "", f"note: {d['note']}", "",
         "instruments, most lethal first; among equals cheapest first, and an",
         "instrument with no measured cost sorts LAST rather than first:"]
    for i in d["instruments_ranked"]:
        mean = i["container_seconds_mean"]
        L.append(f"    {i['kills']:>4} kills  "
                 f"{('%.0fs' % mean) if mean is not None else 'COST ABSENT':>12}"
                 f"  {i['instrument']}")
        L.append(f"           {i['cost_note']}")
        L.append(f"           families: {', '.join(i['families'])}")
    L.append("")
    L.append("instrument x family:")
    for c in d["matrix"]:
        L.append(f"    {c['instrument']:<18} {c['family']:<28} "
                 f"{c['kills']:>3} kill(s)"
                 + (f"   claim_type {','.join(c['claim_types'])}"
                    if c["claim_types"] else ""))
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    from app.fund.knowledge import SchemaAbsent
    try:
        return _dispatch(list(sys.argv[1:] if argv is None else argv))
    except SchemaAbsent as e:
        # AN ABSENT STORE IS NOT AN EMPTY ONE, and the exit code says so too:
        # a chair piping this into a brief gets a refusal, not a blank block
        # that reads like "the firm has killed nothing".
        print(f"THE GRAPH DOES NOT EXIST IN THIS STORE — {e}", file=sys.stderr)
        return 3


def _dispatch(a: list[str]) -> int:
    if not a:
        print(__doc__)
        return 2
    cmd = a[0]
    if cmd == "ledger":
        if len(a) < 2:
            print("usage: report.py ledger <family>", file=sys.stderr)
            return 2
        print(ledger(a[1]))
    elif cmd == "calibration":
        print(calibration(a[1] if len(a) > 1 else None))
    elif cmd == "taxonomy":
        print(taxonomy())
    elif cmd == "cheap":
        print(cheap())
    elif cmd == "families":
        fams = _kg().families()
        print("\n".join(fams) if fams
              else "NO FAMILIES RECORDED — the graph is empty, which is not "
                   "the same as the firm having tested nothing. Run "
                   "scripts/kg/backfill.py.")
    elif cmd == "json":
        kg = _kg()
        print(json.dumps({"taxonomy": kg.kill_taxonomy(),
                          "cheap_kills": kg.cheap_kills(),
                          "calibration": kg.prediction_calibration()},
                         indent=2, default=str))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
