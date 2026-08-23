"""Copy every seat's memory file into the episode store, section by section.

    ./venv/Scripts/python.exe -X utf8 scripts/episodes/ingest.py --run-id <run> [--dry-run]

**THE SEAT MEMORY FILES ARE NEVER WRITTEN TO.** This is a COPY into queryable
storage, not a migration. ``.claude/state/<seat>.md`` stays the operating
memorandum — the file a seat reads on every dispatch and the chair appends to at
resolve — and nothing here opens one for writing.
``tests/test_episodes.py::test_the_ingest_has_no_WRITE_PATH_into_the_state_dir``
walks this module's AST and fails on any write call, so the claim is checked
rather than promised.

WHAT IS A SEAT FILE, AND WHAT IS NOT. Every ``*.md`` in ``.claude/state`` whose
stem is lowercase (``builder``, ``co-cto``, ``cdo``, ...). The upper-case names
in that directory are INSTRUMENTS, not memories — ``API_CARD.md`` is a reference
card, ``DAY_LOG.md`` is the chair's handover, ``CTO_REVIEW_QUEUE.md`` is a
ledger — and each is NAMED in the report as skipped, with the reason, rather
than quietly not appearing.

HOW A FILE BECOMES EPISODES. Split on ``## `` at the start of a line, and
nothing else. The invariant is that rejoining a file's sections in order
reproduces the file BYTE FOR BYTE (``app.fund.episodes.split_sections``,
asserted over all fourteen live files in ``tests/test_episodes.py``). So:

  * the PREAMBLE — everything before the first heading — becomes episode 0 with
    no heading, rather than being dropped. "The part nobody indexed" is where a
    silent loss hides;
  * a section whose body is blank (five exist today, including two halves of a
    heading somebody wrapped across two lines in ``cto.md``) is stored AND
    counted in ``uninterpretable`` — never dropped;
  * ``### `` subheadings do not split. They are structure inside an episode.

CITATIONS. A section that names a run id which EXISTS in ``fund_agent_runs``
cites that run; every other section cites the ingestion run, and the two counts
are printed separately. Shape alone is not enough — the corpus contains
``run-riskofficer-N``, a placeholder shaped exactly like a citation. If the
recorder cannot be read, NOTHING is accepted as a real citation and the report
says the table was unreadable, because an unverifiable citation that looks
verified is worse than an honest fallback.

IDEMPOTENCE. ``dedupe_key = episodes:<seat>:<ordinal>:<sha256(text)[:16]>``.
Re-running after a chair appends a section writes only the new sections.
**A section EDITED IN PLACE writes a NEW episode and leaves the old one**, which
is correct for an append-only store and is stated here because it is the
surprising half: the store accumulates versions of an edited section rather than
replacing one. And because the ordinal is part of the key, a section INSERTED in
the middle of a file re-writes every section below it. These files are appended
to at the bottom, so that is rare; when it happens the report's
``created`` count is the tell.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from typing import Any, Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: Where the seat memoranda live: the workspace root, which is the PARENT of
#: ClarkHarness, because ``.claude/`` belongs to the workspace and not to this
#: repository.
#:
#: **THIS DEFAULT IS WRONG IN A BUILDER WORKTREE** — a worktree lives in a
#: scratchpad with no workspace above it — and that is why the script REFUSES
#: on an absent directory instead of printing a clean table of zeroes. A path
#: derived from ``__file__`` that fails permissive is a control nobody notices
#: has stopped working; this one fails loud. Override with ``--state-dir`` or
#: ``FUND_SEAT_STATE_DIR``.
DEFAULT_STATE_DIR = pathlib.Path(
    os.getenv("FUND_SEAT_STATE_DIR") or (ROOT.parent / ".claude" / "state"))

#: A seat file's stem. Lowercase letters and hyphens: `builder`, `co-cto`.
SEAT_STEM_RE = re.compile(r"^[a-z][a-z-]*$")


def seat_files(state_dir: pathlib.Path) -> tuple[list[pathlib.Path],
                                                 list[pathlib.Path]]:
    """``(seat files, skipped files)`` — both returned, because the skipped
    list is reported by name and never left implicit."""
    if not state_dir.is_dir():
        return [], []
    md = sorted(state_dir.glob("*.md"))
    return ([p for p in md if SEAT_STEM_RE.match(p.stem)],
            [p for p in md if not SEAT_STEM_RE.match(p.stem)])


def known_run_ids(dsn: str) -> Optional[set[str]]:
    """Every run id the flight recorder holds, or None if it cannot be read.

    None is propagated all the way to the citation logic, which then accepts
    NOTHING as a real citation. Absence is never zero and it is never a free
    hand either.
    """
    import psycopg
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('fund_agent_runs')")
                if cur.fetchone()[0] is None:
                    return None
                cur.execute("SELECT run_id FROM fund_agent_runs")
                return {r[0] for r in cur.fetchall()}
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: fund_agent_runs unreadable ({e}) - every episode will "
              f"cite the ingestion run, which is not the same as every episode "
              f"being uncited", file=sys.stderr)
        return None


def plan_file(path: pathlib.Path, seat: str, known: Optional[set[str]],
              ingest_run: str) -> list[dict[str, Any]]:
    """Every episode this file yields, as rows ready to write.

    Pure: reads the file, touches no database, writes nothing. That is what
    makes ``--dry-run`` a real dry run rather than a promise.
    """
    from app.fund.episodes import (date_in_heading, kind_for_heading,
                                   run_ids_in, split_sections, tags_for_text)

    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for s in split_sections(text):
        cited, rejected = run_ids_in(s.text, known)
        body = s.text[len(s.heading):].strip() if s.heading else s.text.strip()
        # IDENTITY IS THE RSTRIPPED TEXT; THE STORED COPY IS VERBATIM.
        #
        # Measured while writing the test for this: appending a section to a
        # file writes TWO rows, not one. The previously-last section gains the
        # blank line that now separates it from the new heading, so its bytes
        # change and its key changes — and a store that duplicates its tail
        # section on every append accumulates one junk row per file per
        # append. Hashing the rstripped text is the right question ("is this
        # the same episode?"); a newline that arrived because the NEXT section
        # did is not a new episode.
        #
        # THE CONSEQUENCE, stated because it is the surprising half: the
        # stored ``episode_md`` for a file's last section keeps the trailing
        # bytes it had when first copied, and a later append does not rewrite
        # it. The store is a copy taken at a moment, not a mirror.
        digest = hashlib.sha256(
            s.text.rstrip().encode("utf-8")).hexdigest()[:16]
        rows.append({
            "seat": seat,
            "kind": kind_for_heading(s.heading),
            "heading": s.heading,
            "episode_md": s.text,
            "market_tags": tags_for_text(s.text),
            "cited_run": cited[0] if cited else ingest_run,
            "real_citation": bool(cited),
            "rejected_run_tokens": rejected,
            "source_ref": (f".claude/state/{path.name}"
                           f"#L{s.line_start}-L{s.line_end}"),
            "provenance": "backfill",
            "episode_at": (f"{date_in_heading(s.heading)}T00:00:00+00:00"
                           if date_in_heading(s.heading) else None),
            "dedupe_key": f"episodes:{seat}:{s.ordinal:04d}:{digest}",
            "empty_body": not body,
            "ordinal": s.ordinal,
        })
    return rows


def ingest(dsn: str, run_id: str, state_dir: pathlib.Path,
           dry_run: bool = False) -> dict[str, Any]:
    from app.fund.episodes import EpisodeStore

    # REFUSE RATHER THAN REPORT A CLEAN ZERO. An ingest pointed at a directory
    # that is not there, or at one holding no seat memoranda, has measured
    # nothing — and "0 sections across 0 seats" is the shape a successful run
    # of an empty corpus would take. Two indistinguishable answers, one of them
    # a misconfiguration, is exactly the absence-as-zero failure.
    if not state_dir.is_dir():
        raise SystemExit(
            f"REFUSING: no directory at {state_dir}. That is UNREADABLE, not "
            f"empty, and printing a table of zeroes for it would be a clean "
            f"bill of health for a run that read nothing. The default is the "
            f"workspace's .claude/state, which does not exist inside a "
            f"builder worktree — pass --state-dir or set FUND_SEAT_STATE_DIR.")
    files, skipped = seat_files(state_dir)
    if not files:
        raise SystemExit(
            f"REFUSING: {state_dir} holds no seat memory file (a *.md whose "
            f"stem is lower-case). It does hold: "
            f"{', '.join(p.name for p in skipped) or 'nothing at all'}.")
    known = known_run_ids(dsn)

    store = None
    if not dry_run:
        store = EpisodeStore(dsn=dsn)
        # THE INGEST IS A WRITER, so it is the one that pays the DDL, once.
        store.ensure_schema()

    per_seat: list[dict[str, Any]] = []
    totals = {"sections": 0, "created": 0, "already_present": 0,
              "empty_body": 0, "real_citation": 0, "ingestion_citation": 0,
              "tagged": 0, "untagged": 0}
    kinds: dict[str, int] = {}
    tags: dict[str, int] = {}
    rejected_tokens: dict[str, int] = {}
    uninterpretable: list[dict[str, Any]] = []

    for path in files:
        seat = path.stem
        rows = plan_file(path, seat, known, run_id)
        created = present = 0
        for r in rows:
            totals["sections"] += 1
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
            if r["market_tags"]:
                totals["tagged"] += 1
            else:
                totals["untagged"] += 1
            for t in r["market_tags"]:
                tags[t] = tags.get(t, 0) + 1
            for t in r["rejected_run_tokens"]:
                rejected_tokens[t] = rejected_tokens.get(t, 0) + 1
            if r["real_citation"]:
                totals["real_citation"] += 1
            else:
                totals["ingestion_citation"] += 1
            if r["empty_body"]:
                totals["empty_body"] += 1
                # COUNTED AND NAMED, never dropped. A section with a heading
                # and no body is usually a heading somebody wrapped over two
                # lines; it is still bytes of the memorandum.
                uninterpretable.append({
                    "seat": seat, "source_ref": r["source_ref"],
                    "heading": r["heading"],
                    "why": ("the section has a heading and no body - stored "
                            "verbatim anyway, because the round-trip must "
                            "reproduce the file")})
            if store is not None:
                res = store.add_episode(
                    seat=r["seat"], kind=r["kind"],
                    episode_md=r["episode_md"], cited_run=r["cited_run"],
                    heading=r["heading"], market_tags=r["market_tags"],
                    source_ref=r["source_ref"], provenance=r["provenance"],
                    episode_at=r["episode_at"], dedupe_key=r["dedupe_key"],
                    on_conflict="ignore")
                if res["created"]:
                    created += 1
                else:
                    present += 1
        totals["created"] += created
        totals["already_present"] += present
        per_seat.append({
            "seat": seat, "file": path.name, "bytes": path.stat().st_size,
            "sections": len(rows), "created": created,
            "already_present": present,
            "empty_body": sum(1 for r in rows if r["empty_body"]),
            "real_citation": sum(1 for r in rows if r["real_citation"]),
            "tagged": sum(1 for r in rows if r["market_tags"]),
        })

    return {
        "run_id": run_id,
        "dry_run": dry_run,
        "state_dir": str(state_dir),
        "state_dir_present": state_dir.is_dir(),
        "recorder_readable": known is not None,
        "known_run_ids": len(known) if known is not None else None,
        "per_seat": per_seat,
        "skipped_files": [
            {"file": p.name,
             "why": ("not a seat memory file - the lower-case stems in "
                     ".claude/state are seat memoranda, the upper-case ones "
                     "are instruments (a reference card, a handover log, a "
                     "review ledger)")}
            for p in skipped],
        "totals": totals,
        "kinds": dict(sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))),
        "market_tags": {t: tags.get(t, 0) for t in _tag_vocabulary()},
        "rejected_run_tokens": dict(sorted(rejected_tokens.items())),
        "uninterpretable": uninterpretable,
    }


def _tag_vocabulary() -> tuple[str, ...]:
    from app.fund.episodes import MARKET_TAGS
    return MARKET_TAGS


def render(rep: dict[str, Any]) -> str:
    L: list[str] = []
    mode = "DRY RUN (nothing written)" if rep["dry_run"] else "WRITE"
    L.append(f"# seat-episode ingest   mode={mode}   run_id={rep['run_id']}")
    L.append(f"  state dir: {rep['state_dir']}"
             + ("" if rep["state_dir_present"]
                else "   *** DIRECTORY ABSENT - UNREADABLE, NOT EMPTY"))
    L.append(f"  flight recorder: "
             + (f"{rep['known_run_ids']} run id(s) known"
                if rep["recorder_readable"] else
                "UNREADABLE - no citation can be verified, so every episode "
                "cites the ingestion run"))
    L.append("")
    L.append(f"{'seat':<14}{'file':<20}{'sect':>5}{'new':>6}{'seen':>6}"
             f"{'empty':>7}{'cited':>7}{'tagged':>8}")
    for s in rep["per_seat"]:
        L.append(f"{s['seat']:<14}{s['file']:<20}{s['sections']:>5}"
                 f"{s['created']:>6}{s['already_present']:>6}"
                 f"{s['empty_body']:>7}{s['real_citation']:>7}"
                 f"{s['tagged']:>8}")
    t = rep["totals"]
    L.append(f"{'TOTAL':<34}{t['sections']:>5}{t['created']:>6}"
             f"{t['already_present']:>6}{t['empty_body']:>7}"
             f"{t['real_citation']:>7}{t['tagged']:>8}")
    L.append("")
    L.append("skipped (NOT seat memory files, named rather than omitted):")
    for s in rep["skipped_files"]:
        L.append(f"    {s['file']}")
    if not rep["skipped_files"]:
        L.append("    none")
    L.append("")
    L.append("kinds:")
    for k, n in rep["kinds"].items():
        L.append(f"    {n:>5}  {k}")
    L.append("")
    L.append("market tags (the WHOLE vocabulary, so a zero is visible):")
    for k, n in rep["market_tags"].items():
        L.append(f"    {n:>5}  {k}"
                 + ("   <- no episode names this market" if not n else ""))
    L.append(f"    {t['untagged']:>5}  UNTAGGED  (no market named - this is "
             f"NOT 'applies to every market')")
    L.append("")
    L.append(f"citations: {t['real_citation']} name a run that exists in "
             f"fund_agent_runs; {t['ingestion_citation']} cite the ingestion "
             f"run because no run in the record names them")
    if rep["rejected_run_tokens"]:
        L.append("    run-shaped tokens REJECTED (not in the recorder):")
        for tok, n in rep["rejected_run_tokens"].items():
            L.append(f"        {n:>3}  {tok}")
    L.append("")
    L.append(f"UNINTERPRETABLE sections: {len(rep['uninterpretable'])} "
             f"(counted and STORED verbatim, never dropped)")
    for u in rep["uninterpretable"]:
        L.append(f"    ! {u['source_ref']}  {(u['heading'] or '')[:70]}")
        L.append(f"      {u['why']}")
    return "\n".join(L)


def main(argv: Optional[list[str]] = None) -> int:
    from app.fund.pgstore import dsn as default_dsn

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # REQUIRED, no default. A default would manufacture the one thing the
    # store refuses to do without: a citation.
    p.add_argument("--run-id", required=True,
                   help="the run that cites this ingestion; mandatory")
    p.add_argument("--dsn", default=None)
    p.add_argument("--state-dir", default=None,
                   help=f"default {DEFAULT_STATE_DIR}")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    rep = ingest(a.dsn or default_dsn(), a.run_id,
                 pathlib.Path(a.state_dir) if a.state_dir else DEFAULT_STATE_DIR,
                 dry_run=a.dry_run)
    print(json.dumps(rep, indent=2) if a.json else render(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
