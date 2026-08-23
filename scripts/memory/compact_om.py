# -*- coding: utf-8 -*-
"""THE OM COMPACTOR — archival, never summarization.

CEO question 2026-08-24: "is there a compact function that can be used?"
The safe answer for seat memories: separate the WORKING SET from the
AUTOBIOGRAPHY without paraphrasing either. A summarizer can silently drop a
load-bearing caveat (the bad-learnings rule); an archiver cannot.

What it does, per seat file:
  1. Splits the file into '## '-headed sections (the episode store's own
     splitter contract — every byte lands in exactly one section).
  2. KEEPS: the preamble, the newest KEEP_STATES dated sections, any section
     whose heading matches KEEP_PATTERNS (opens, standing protocol notes),
     and anything it cannot confidently date.
  3. ARCHIVES the rest to .claude/state/archive/<seat>.md (append-only),
     but ONLY sections whose rstripped text byte-matches a row already in
     fund_seat_episodes — an unverified section is NEVER archived (absence
     of ingestion is never treated as ingested).
  4. Writes the compacted OM with a pointer block naming the archive file
     and the episode-store query that recovers full history.
  5. DRY RUN by default; --apply writes. The chair reviews the diff either
     way; git keeps every pre-compact version forever.

Never run while the seat is mid-dispatch on the file.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(r"C:\Users\user\Documents\Krypton Fund\.claude\state")
ARCHIVE = ROOT / "archive"
KEEP_STATES = 6  # newest dated sections kept in the OM
KEEP_PATTERNS = [
    r"open, mine", r"OPEN FOR", r"standing", r"protocol", r"RUN-RECORD PROTOCOL",
]
DATED = re.compile(r"^## .*20\d\d-\d\d-\d\d", re.I)


def split_sections(md: str):
    """The episode store's contract: '' .join(sections) == md, byte for byte."""
    lines = md.split("\n")
    sections, cur = [], []
    for ln in lines:
        if ln.startswith("## ") and cur:
            sections.append("\n".join(cur) + "\n")
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        sections.append("\n".join(cur))
    return sections


def _norm(s: str) -> str:
    """One normalization for BOTH arms: CRLF->LF, trailing whitespace off.
    Postgres rtrim() trims only spaces and the on-disk files are CRLF, so any
    SQL-side hash silently disagrees with a Python-side one - both arms must
    normalize HERE, in one function, or the verification lies."""
    return s.replace("\r\n", "\n").rstrip()


def ingested_keys(dsn: str):
    import hashlib
    import psycopg
    with psycopg.connect(dsn) as c:
        rows = c.execute("select episode_md from fund_seat_episodes").fetchall()
    return {hashlib.md5(_norm(r[0]).encode("utf-8")).hexdigest() for r in rows}


def compact(seat: str, dsn: str, apply: bool) -> None:
    import hashlib
    p = ROOT / f"{seat}.md"
    md = p.read_text(encoding="utf-8")
    sections = split_sections(md)
    assert "".join(sections) == md, "splitter broke the round-trip - refusing"

    keys = ingested_keys(dsn)
    dated_idx = [i for i, s in enumerate(sections) if DATED.match(s)]
    keep_newest = set(dated_idx[-KEEP_STATES:])

    keep, archive, unverified = [], [], []
    for i, s in enumerate(sections):
        head = s.split("\n", 1)[0]
        if i not in dated_idx or i in keep_newest or any(
                re.search(pat, head, re.I) for pat in KEEP_PATTERNS):
            keep.append(s)
            continue
        h = hashlib.md5(_norm(s).encode("utf-8")).hexdigest()
        if h in keys:
            archive.append(s)
        else:
            keep.append(s)          # not provably ingested -> stays, loudly
            unverified.append(head[:80])

    pointer = (f"\n## ARCHIVED HISTORY — compacted {'' if apply else '(DRY RUN) '}by the chair\n\n"
               f"{len(archive)} dated sections moved to `state/archive/{seat}.md` after "
               f"byte-verification against the episode store. Full history: the archive file, "
               f"git, or `scripts/episodes/query.py --seat {seat}`. Nothing was summarized.\n")
    new_md = "".join(keep) + pointer

    old_kb, new_kb = len(md) // 1024, len(new_md) // 1024
    print(f"{seat}: {old_kb} KB -> {new_kb} KB | kept {len(keep)} sections | "
          f"archived {len(archive)} | UNVERIFIED-kept {len(unverified)}")
    for u in unverified:
        print(f"   ! not in episode store, kept: {u}")
    if apply:
        ARCHIVE.mkdir(exist_ok=True)
        with open(ARCHIVE / f"{seat}.md", "a", encoding="utf-8") as f:
            f.write(f"\n<!-- compacted from {seat}.md, {len(archive)} sections -->\n")
            f.writelines(archive)
        p.write_text(new_md, encoding="utf-8")
        print(f"   applied. Re-run scripts/episodes/ingest.py so the pointer section is stored.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("seats", nargs="+")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dsn", default=None, help="Postgres DSN; read from ClarkHarness/.env FUND_PG_DSN if absent")
    a = ap.parse_args()
    dsn = a.dsn
    if not dsn:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
        from app.fund.pgstore import dsn as default_dsn
        dsn = default_dsn()
    for seat in a.seats:
        compact(seat, dsn, a.apply)
