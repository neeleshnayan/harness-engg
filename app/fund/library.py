"""THE READING ROOM — the shelf of finished research, made reachable.

CEO, 2026-08-27, verbatim: *"I thought we gave dedicated reading rooms aka like
a file vault to teams generating research or actual work product that I could
go in and read"*.

He was right that it was promised and right that it was not there. House-styled
research PDFs have been rendering to ``data/library/`` at resolve since
2026-08-23 — six of them the day this was written — and **nothing in the studio
linked to a single one.** A shelf nobody can reach is not a library; it is a
directory.

THIS IS THE VISIBLE HALF ONLY. The durable half of the reading-room charter
(a Postgres table, ingest from ``docs/research``, per-seat partitioning) stays
chartered separately and is deliberately NOT built here. What this module does
is list a directory and hand back bytes, and it is written to be boring.

TWO RULES SHAPE EVERY LINE BELOW.

**AN UNREADABLE SHELF IS NOT AN EMPTY ONE.** ``shelf()`` returns a `readable`
flag beside its rows. A directory that does not exist, cannot be listed, or
raises is reported as UNREADABLE with the reason — never as a library with no
books in it. This is the absence-as-zero rule at the one place a reader would
never think to doubt it: an empty shelf looks exactly like a shelf you cannot
open.

**THE PATH IS RESOLVED AND FENCED, NOT PATTERN-MATCHED.** ``resolve_document``
refuses anything whose RESOLVED path is not inside the library directory. It
does not blocklist ``..``; it resolves and compares, because a blocklist is a
guess about every encoding of every escape and a resolve is an answer. It also
refuses anything that is not a regular ``.pdf`` file, so a symlink pointing out
of the tree fails on the resolve and a directory named ``x.pdf`` fails on the
file check.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

#: Where the render step already writes. One constant, so the endpoint and the
#: renderer cannot drift to two directories that both look right.
LIBRARY_DIRNAME = os.path.join("data", "library")

#: The only extension this room serves. Not a filter over a wider set: the
#: shelf holds rendered documents, and serving anything else from a directory
#: reachable by name is a different feature with a different risk.
SUFFIX = ".pdf"

#: Trailing `_v2`-style revision markers, kept out of the date parse.
_REV = re.compile(r"_v(\d+)$", re.IGNORECASE)
_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

#: Words sentence case would turn into different words. Extended by hand when
#: a real filename needs it — never by a heuristic, because "is it all-caps"
#: is true of every word in these filenames.
ACRONYMS = frozenset({"ETH", "BTC", "PIT", "SEC", "NAV", "PDT", "TCA", "ADV",
                      "LEAN", "ETF", "SPY", "GLD", "TLT", "DBC", "US", "UK",
                      "EU", "AI", "ML", "IPO", "PM", "CEO", "CTO", "COO",
                      "CFO", "P&L", "OHLC", "API", "PDF", "QC", "FRED"})


def library_dir(root: Optional[str] = None) -> Path:
    """The shelf's directory, resolved once."""
    base = Path(root) if root else Path(__file__).resolve().parents[2]
    return (base / LIBRARY_DIRNAME).resolve()


def _pretty_date(iso: str) -> Optional[str]:
    """``2026-08-24`` -> ``Aug 24``. None when it is not a date we can read."""
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        if not 1 <= m <= 12:
            return None
        return f"{_MONTHS[m - 1]} {d}"
    except (ValueError, IndexError):
        return None


def title_of(name: str) -> dict[str, Any]:
    """A filename, read as a title a person would say out loud.

    ``GOLD_DOSSIER_V1_2026-08-24.pdf`` -> *"Gold dossier — Aug 24"*.

    PLAIN ENGLISH (CEO, the same day: *"plain english should be a direction for
    all teams"*). The raw filename is CARRIED alongside rather than replaced —
    it is the thing you type to find the file again, and a room that hid it
    would be tidier and less useful. The title is what the shelf shows; the
    filename is what the fold shows.

    A name this cannot parse returns the stem with underscores opened out. That
    is a degraded title, never a blank one, and ``parsed`` says which it is so
    a surface can tell a read title from a guessed one.
    """
    stem = name[:-len(SUFFIX)] if name.lower().endswith(SUFFIX) else name

    date_iso: Optional[str] = None
    m = _DATE.search(stem)
    if m:
        date_iso = m.group(1)
        stem = (stem[:m.start()] + stem[m.end():])

    rev: Optional[str] = None
    stem = stem.strip("_- ")
    rm = _REV.search(stem)
    if rm:
        rev = f"v{rm.group(1)}"
        stem = stem[:rm.start()]

    words = [w for w in re.split(r"[_\-\s]+", stem) if w]
    # `V1` is a version marker inside the name, not a word of the title.
    version = None
    if words and re.fullmatch(r"[Vv]\d+", words[-1]):
        version = words[-1].lower()
        words = words[:-1]
    if rev and not version:
        version = rev

    if words:
        # Sentence case: the first word capitalised, the rest lowered — an
        # ALL-CAPS filename shouted on screen and read as an alarm.
        #
        # EXCEPT the acronyms, which sentence case turns into words that mean
        # something else: "Eth dossier" and "Pit universe" are both wrong, and
        # the second is actively misleading — PIT is point-in-time, not a hole.
        # A NAMED SET rather than a heuristic (all-caps? four letters?): a
        # guess here would capitalise the next unlucky word, and the set is
        # cheap to extend when a real name needs it.
        title = " ".join(
            w.upper() if w.upper() in ACRONYMS
            else (w.capitalize() if i == 0 else w.lower())
            for i, w in enumerate(words))
    else:
        title = stem or name

    pretty = _pretty_date(date_iso) if date_iso else None
    display = title
    if version:
        display = f"{display} {version}"
    if pretty:
        display = f"{display} — {pretty}"

    return {
        "title": title,
        "display": display,
        "version": version,
        "date": date_iso,
        "date_display": pretty,
        # False when nothing dated and nothing wordy came out — the surface can
        # then show the filename rather than a title we invented.
        "parsed": bool(words),
    }


def shelf(root: Optional[str] = None) -> dict[str, Any]:
    """Every document on the shelf, newest first.

    ``readable`` is the first field for a reason: an unreadable directory and
    an empty one are different facts, and the second is the one a reader
    assumes. When the shelf cannot be read the row list is EMPTY and
    ``readable`` is False with a ``note`` saying why — a caller that renders
    the rows without checking the flag will show nothing, which is at least not
    a claim; a caller that reads the flag says "we could not open the shelf".

    Sorted by DATE where the name carries one, then by the file's own mtime.
    A document whose name has no date sorts by mtime alone and is not silently
    treated as undated-therefore-oldest — its mtime is a real measurement.
    """
    d = library_dir(root)
    try:
        entries = list(d.iterdir())
    except FileNotFoundError:
        return {"readable": False, "documents": [], "count": 0,
                "directory": str(d),
                "note": "The reading room's shelf has not been created yet. "
                        "That is a missing directory, not an empty library."}
    except OSError as e:
        return {"readable": False, "documents": [], "count": 0,
                "directory": str(d),
                "note": f"The shelf could not be read ({type(e).__name__}). "
                        "What is on it is unknown, not nothing."}

    docs: list[dict[str, Any]] = []
    unreadable_rows = 0
    for p in entries:
        if not p.name.lower().endswith(SUFFIX):
            continue
        try:
            if not p.is_file():
                continue
            size = p.stat().st_size
            mtime = p.stat().st_mtime
        except OSError:
            # A file we can see and cannot stat is COUNTED, not dropped: a
            # shelf that quietly shortens itself is the failure this module's
            # first rule is about.
            unreadable_rows += 1
            continue
        meta = title_of(p.name)
        docs.append({
            "name": p.name,
            "title": meta["title"],
            "display": meta["display"],
            "version": meta["version"],
            "date": meta["date"],
            "date_display": meta["date_display"],
            "title_parsed": meta["parsed"],
            "size_bytes": size,
            "modified_at": mtime,
        })

    docs.sort(key=lambda r: (r["date"] or "", r["modified_at"]), reverse=True)

    note = (f"{len(docs)} document(s) on the shelf."
            if docs else
            "The shelf is readable and holds no documents yet.")
    if unreadable_rows:
        note += (f" {unreadable_rows} file(s) are on the shelf and could not "
                 "be read — they are missing from the list below, and that is "
                 "a fault rather than an absence.")

    return {"readable": True, "documents": docs, "count": len(docs),
            "directory": str(d), "unreadable": unreadable_rows, "note": note}


def resolve_document(name: str, root: Optional[str] = None) -> Optional[Path]:
    """The path to one document, or ``None`` if it is not this room's to serve.

    FENCED BY RESOLUTION, NOT BY PATTERN. The candidate is joined to the
    library directory and resolved, and the result must be INSIDE the resolved
    library directory. A blocklist of ``..`` and friends is a guess about every
    encoding of every escape; a resolve is an answer, and it also catches a
    symlink that points out of the tree, which no string check can see.

    Refusals, all returning ``None`` rather than raising, because "not found"
    and "not allowed" must look identical from outside — a 404 that is
    distinguishable from a 403 is a directory listing for anyone patient:

      * anything that resolves outside the library directory;
      * anything not ending ``.pdf``;
      * anything that is not a regular file (a directory named ``x.pdf``, a
        dangling symlink, a device node).
    """
    if not isinstance(name, str) or not name.strip():
        return None
    if not name.lower().endswith(SUFFIX):
        return None
    d = library_dir(root)
    try:
        candidate = (d / name).resolve()
    except (OSError, ValueError):
        return None
    # `is_relative_to` rather than a string prefix: `.../library2/x.pdf` starts
    # with `.../library` as a STRING and is a different directory.
    if not candidate.is_relative_to(d):
        return None
    try:
        if not candidate.is_file():
            return None
    except OSError:
        return None
    return candidate
