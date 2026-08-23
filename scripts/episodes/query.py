"""Read the episode store — by seat, by market tag, by date, by cited run.

    ./venv/Scripts/python.exe -X utf8 scripts/episodes/query.py coverage
    ./venv/Scripts/python.exe -X utf8 scripts/episodes/query.py find --seat quant --tag futures
    ./venv/Scripts/python.exe -X utf8 scripts/episodes/query.py find --since 2026-08-22 --kind bind
    ./venv/Scripts/python.exe -X utf8 scripts/episodes/query.py find --cited-run run-cfo-7
    ./venv/Scripts/python.exe -X utf8 scripts/episodes/query.py vocabulary

THIS EXISTS SO THE STORE DOES NOT SHIP UNWIRED. A table with an ingest and no
reader is the unwired-kill-switch pattern in a storage costume: it would look
done and answer nobody. There is deliberately NO endpoint and NO UI — the
episode store must not become something a decision path can reach by accident,
and ``tests/test_knowledge_isolation.py`` asserts that no module under ``app/``
imports it.

**IT ISSUES NO DDL AND TAKES NO LOCK.** It never calls ``ensure_schema()``. On a
store where the table does not exist it says so and exits non-zero, rather than
printing an empty result that reads like "no seat has learned anything".

EVERY ANSWER CARRIES ITS ABSENCES. An empty result prints what the store DOES
hold, so "this seat has no episodes about futures" and "this seat has no
episodes at all" are never the same page.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _store(dsn: str | None = None):
    from app.fund.episodes import EpisodeStore
    return EpisodeStore(dsn=dsn)


def _head(md: str, heading: str | None, width: int = 96) -> str:
    """The heading, or the first non-blank line when there is none."""
    if heading:
        return heading[:width]
    for line in (md or "").splitlines():
        if line.strip():
            return line.strip()[:width]
    return "(no heading, no text)"


def find(d: dict, full: bool = False) -> str:
    L = ["# episodes", "",
         "filters: " + ", ".join(f"{k}={v}" for k, v in d["filters"].items()
                                 if v not in (None, False)) or "filters: none",
         f"note: {d['note']}", ""]
    for e in d["episodes"]:
        tags = ",".join(e["market_tags"]) or "NO MARKET NAMED"
        L.append(f"{(e['episode_at'] or 'UNDATED')[:10]}  {e['seat']:<12}"
                 f"{e['kind']:<8}{tags:<26}{e['cited_run']}"
                 + ("   [VOIDED]" if e["voided"] else ""))
        L.append(f"    {_head(e['episode_md'], e['heading'])}")
        L.append(f"    {e['source_ref'] or 'NO SOURCE REF'}")
        if full:
            L.append("")
            L.extend("      " + ln for ln in e["episode_md"].splitlines())
        L.append("")
    # THE ABSENCES, ALWAYS PRINTED — not only when the answer is empty. A short
    # answer with a large store is the case a reader misreads most.
    L.append(f"matched {d['matched']} of {d['total_in_store']} episode(s) in "
             f"the store")
    if d["truncated"]:
        L.append(f"    TRUNCATED at limit={d['filters']['limit']} — this is a "
                 f"page, not a census")
    if d["voided_excluded"]:
        L.append(f"    {d['voided_excluded']} VOIDED episode(s) excluded "
                 f"(--include-voided to see them)")
    if d["undated_excluded"]:
        L.append(f"    {d['undated_excluded']} episode(s) state NO DATE in "
                 f"their heading and are EXCLUDED from a dated query — they "
                 f"are not undated-therefore-recent")
    L.append(f"    seats in store: {', '.join(d['seats_in_store']) or 'none'}")
    L.append(f"    tags in store:  {', '.join(d['tags_in_store']) or 'none'}")
    return "\n".join(L)


def coverage(d: dict) -> str:
    L = ["# episode coverage", "", f"note: {d['note']}", "",
         f"{'seat':<14}{'eps':>5}{'tagged':>8}{'untag':>7}{'undated':>9}"
         f"{'voided':>8}  kinds / provenance / span"]
    for s in d["seats"]:
        kinds = " ".join(f"{k}:{n}" for k, n in sorted(s["kinds"].items()))
        prov = " ".join(f"{k}:{n}" for k, n in sorted(s["provenance"].items()))
        span = f"{(s['earliest'] or 'UNDATED')[:10]}..{(s['latest'] or 'UNDATED')[:10]}"
        L.append(f"{s['seat']:<14}{s['episodes']:>5}{s['tagged']:>8}"
                 f"{s['untagged']:>7}{s['undated']:>9}{s['voided']:>8}  "
                 f"{kinds} | {prov} | {span}")
    L.append("")
    L.append("UNTAGGED means no market was named in the episode. It does NOT "
             "mean the episode applies to every market, and a tag query never "
             "returns these rows.")
    return "\n".join(L)


def vocabulary() -> str:
    from app.fund.episodes import KINDS, MARKET_TAG_RULES, MARKET_TAGS
    L = ["# episode vocabulary", "", f"kinds: {', '.join(KINDS)}", "",
         "market tags, with the patterns that produce them (a tag is always "
         "traceable to a token somebody wrote):"]
    for tag in MARKET_TAGS:
        pats = [p for t, p, _ in MARKET_TAG_RULES if t == tag]
        L.append(f"    {tag}")
        for p in pats:
            L.append(f"        {p}")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    from app.fund.episodes import SchemaAbsent
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=("find", "coverage", "vocabulary"))
    p.add_argument("--dsn", default=None)
    p.add_argument("--seat", default=None)
    p.add_argument("--tag", default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--since", default=None, help="YYYY-MM-DD, on episode_at")
    p.add_argument("--until", default=None, help="YYYY-MM-DD, on episode_at")
    p.add_argument("--cited-run", default=None)
    p.add_argument("--include-voided", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--full", action="store_true",
                   help="print each episode's full verbatim text")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.command == "vocabulary":
        print(vocabulary())
        return 0
    try:
        store = _store(a.dsn)
        if a.command == "coverage":
            d = store.coverage()
            print(json.dumps(d, indent=2) if a.json else coverage(d))
        else:
            d = store.episodes(seat=a.seat, tag=a.tag, kind=a.kind,
                               since=a.since, until=a.until,
                               cited_run=a.cited_run,
                               include_voided=a.include_voided,
                               limit=a.limit)
            print(json.dumps(d, indent=2) if a.json else find(d, full=a.full))
    except SchemaAbsent as e:
        # AN ABSENT STORE IS NOT AN EMPTY ONE, and the exit code says so too.
        print(f"THE EPISODE STORE DOES NOT EXIST HERE — {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
