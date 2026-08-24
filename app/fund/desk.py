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
from typing import Any, Iterable, Optional

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
    {"agent": "coo",
     "lane": "Triages the CEO's desk: batches every open item, checks each "
             "against the constitution and mandate, ranks by money, endorses "
             "or objects — the CEO decides batches, not items",
     "emits": "ONE batched decision memo with per-item recommended "
              "dispositions; an endorsement is never a decision",
     "exists_because": "Seated 2026-08-20 by demonstrated need: the CEO's desk "
                       "carried ~20 open recommendations in one day and an "
                       "overwhelmed approver becomes a rubber stamp — the "
                       "failure every control here exists to prevent. The "
                       "click stays the CEO's, always."},
    {"agent": "secretary",
     "lane": "Documents each day from the record at end of day: one short memo "
             "(the CEO's sixty-second read) and one detailed record, filed to "
             "docs/archives/YYYY-MM-DD.md",
     "emits": "two memos in one dated artifact, every claim cited to the log",
     "exists_because": "Seated 2026-08-20 (CEO decision). The Scribe seat's "
                       "'still nothing for them to do' condition ended the day "
                       "the firm shipped a guard, merged a dispatch, ran two "
                       "audits and filled four tickets, and no human could have "
                       "reconstructed it without an hour in the log. The seat "
                       "carries the name Donna; she documents and never "
                       "decides, and her one steering output is the factual "
                       "'awaits the CEO' list. ADDED TO THIS ROSTER 2026-08-21: "
                       "the seat existed in the constitution and was missing "
                       "here, so her seat page rendered a roster absence for a "
                       "colleague who had already run."},
    {"agent": "cfo",
     "lane": "The economics of an agentic firm: what each resource costs, what "
             "it returns, and where the next unit should go. Maps the levers "
             "that compress the critical path, each with a measured effect",
     "emits": "ONE memo in the COO's house format — the meter, the lever map, "
              "the allocation call, and a critical path with a named date",
     "exists_because": "Seated 2026-08-22 (CEO decision). The seat carries the "
                       "name Grace, for Hopper. THE SCARCE RESOURCE IS THE "
                       "CLOCK, NOT THE MONEY: every allocation is judged on "
                       "whether it moves the date this fund can honestly ask "
                       "for more capital, and good work off the critical path "
                       "is not urgent. Demonstrated need, measured the same "
                       "day: 6.0M subagent tokens across 25 runs and nothing "
                       "computing what they bought, while allocation decisions "
                       "were made continuously by the chair in dispatch order "
                       "with no framework and no record. ADDED TO THIS ROSTER "
                       "2026-08-22, and this is the SECOND time the same "
                       "omission has happened — the secretary entry above "
                       "records the first. A seat is created in the "
                       "constitution, dispatched, and runs, while its desk "
                       "renders a roster absence, because adding it here is a "
                       "manual step nobody is prompted for. Twice is a "
                       "pattern: seating a seat should fail loudly if this "
                       "list does not know it."},
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
    # The CEO asking for their own desk to be triaged into batch decisions.
    "triage": "coo",
    # The CTO's end-of-day trigger. A KIND rather than a schedule, deliberately:
    # the secretary runs when a human fires her, and naming it here is what puts
    # her in the activity fold and the per-seat telemetry — without it she is a
    # seat that has run and reports NO runs-today at all, which the floor draws
    # as an unmeasured "×?" beside colleagues showing real counts.
    "document_day": "secretary",
    # The CFO's kind, added 2026-08-22 when the floor gained her desk and the
    # builder found no request could reach it: seat_telemetry enumerates THIS
    # map, so a seat absent here has no runs-today row and the floor draws an
    # unmeasured x? beside colleagues showing real counts — the exact absence
    # the secretary's comment above predicts. Named for what the seat does
    # (the meter, the lever map, the allocation call), like portfolio_review.
    "allocation_review": "cfo",
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


#: Where the secretary files. Append-only by convention: one dated file per day,
#: never an edit — see the constitution's third code exception (2026-08-21).
ARCHIVES = DOCS / "archives"

_ARCHIVE_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def archives() -> dict[str, Any]:
    """Every Daily the secretary has filed, newest first.

    Exists because the UI must not read the filesystem. Donna's seat page needs
    an index of `docs/archives/*.md` and the Studio has no business walking a
    directory — the spine owns what is on disk, the browser owns what is on
    screen, and a page that stats files is a page that breaks the moment it is
    served from anywhere but this machine.

    Read every call rather than cached, for the same reason `_artifacts` is: the
    files ARE the state, and an in-memory copy is a second place to disagree
    with them.

    THREE ABSENCES, kept apart:
      * the directory does not exist — nothing has ever been filed;
      * it exists and is empty — the secretary has run zero times;
      * it cannot be READ — unknown, which is not either of the above.
    A caller that cannot tell those apart will report "no dailies" for a
    permissions error.
    """
    if not ARCHIVES.exists():
        return {"archives": [], "readable": True, "exists": False,
                "note": "docs/archives/ does not exist — the secretary has "
                        "never filed. This is an absence, not an empty list"}
    try:
        entries = sorted(ARCHIVES.glob("*.md"))
    except OSError as e:
        return {"archives": [], "readable": False, "exists": True,
                "note": f"docs/archives/ could not be read ({e}) — whether "
                        f"anything is filed is UNKNOWN, not none"}

    out: list[dict[str, Any]] = []
    for p in entries:
        stem = p.stem
        pdf = p.with_suffix(".pdf")
        try:
            size = p.stat().st_size
        except OSError:
            size = None
        m = _ARCHIVE_NAME_RE.match(stem)
        out.append({
            "date": m.group(1) if m else None,
            "path": str(p).replace("\\", "/"),
            # The PDF is a RENDER of the markdown, not a separate artifact, so
            # its absence is normal rather than a fault: the secretary files the
            # .md and renders the .pdf, and a day rendered before that step
            # existed has only the first.
            "pdf_path": str(pdf).replace("\\", "/") if pdf.exists() else None,
            "title": _title_of(_read(p)),
            "bytes": size,
            # A file whose name is not a date is still listed — it is on disk and
            # hiding it would make the index disagree with the directory.
            "note": None if m else
                    "filename is not a YYYY-MM-DD date — listed as filed, but "
                    "which day it documents cannot be read from the name",
        })
    out.sort(key=lambda r: (r["date"] or "", r["path"]), reverse=True)
    return {
        "archives": out, "readable": True, "exists": True,
        "count": len(out),
        "with_pdf": sum(1 for r in out if r["pdf_path"]),
        "note": (f"{len(out)} daily archive(s) on file"
                 if out else
                 "docs/archives/ exists and holds no .md — the secretary has "
                 "filed nothing yet, which is different from never having run"),
    }


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ----------------------------------------------------- the secretary's memo --

#: A fence line: ``` or ~~~, optionally with an info string.
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*(\S*)\s*$")

#: The TL;DR label, however it is spelled. Matched on a line of its own, either
#: as the first line INSIDE the fence or the last line BEFORE it — the two real
#: archives on disk do it differently, which is the whole reason this is a
#: regex and not a string comparison. See `archive_memo`.
_TLDR_LABEL_RE = re.compile(r"^\s*\**\s*TL\s*;?\s*DR\s*:?\s*\**\s*$", re.I)

#: A level-1 heading and its text.
_H1_RE = re.compile(r"^#\s+(.*?)\s*$")


def _split_memo(text: str) -> dict[str, Any]:
    """Pull the TL;DR fence and the DAILY section out of a filed archive.

    RE-DERIVED FROM THE TWO REAL FILES ON DISK, not from any earlier draft,
    and the derivation immediately earned itself: **the two archives are not
    the same shape.**

        docs/archives/2026-08-21.md      docs/archives/2026-08-20.md
        ```                              TL;DR
        TL;DR                            ```
        <five lines>                     <ten lines>
        ```                              ```

    The label is INSIDE the fence in one and OUTSIDE it in the other. A parser
    written against either file alone gets the other wrong — it would return
    the label as the memo's first line, or miss the memo entirely. Both
    positions are accepted, and neither is guessed at: the label must be
    present in one of the two places, or there is no TL;DR here.

    WHY THE LABEL IS REQUIRED. A fenced block before the first heading is
    *probably* the TL;DR by convention. Convention-matching over prose is what
    the CEO's desk was just repaired FROM — six rows found by grepping their
    text for "EXECUTED" — and the TL;DR is the sixty-second read, the one
    paragraph the CEO is promised he can act on. Presenting an arbitrary code
    block as his headline is a worse failure than saying the headline is
    absent, so an unlabelled fence yields ``tldr: None`` and a note that says
    a fence was found and not identified.

    Returns the pieces plus ``notes``, a list of things a reader should know
    about how this particular file was read.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    notes: list[str] = []

    # --- the TL;DR fence, which must come before the first level-1 heading ---
    first_h1 = next((i for i, l in enumerate(lines) if _H1_RE.match(l)), len(lines))
    tldr: Optional[str] = None
    fence_seen = False
    i = 0
    while i < first_h1:
        m = _FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        fence_seen = True
        marker = m.group(1)
        # The closing fence is the next line using the SAME marker character.
        close = next((j for j in range(i + 1, first_h1)
                      if _FENCE_RE.match(lines[j])
                      and _FENCE_RE.match(lines[j]).group(1)[0] == marker[0]),
                     None)
        if close is None:
            notes.append("a code fence before the first heading is never "
                         "closed — the TL;DR could not be delimited")
            break
        body = lines[i + 1:close]
        labelled_inside = bool(body) and _TLDR_LABEL_RE.match(body[0])
        # The label on its own line above the fence, ignoring blanks.
        above = next((lines[j] for j in range(i - 1, -1, -1) if lines[j].strip()),
                     "")
        labelled_above = bool(_TLDR_LABEL_RE.match(above))
        if labelled_inside:
            body = body[1:]
        if labelled_inside or labelled_above:
            tldr = "\n".join(body).strip() or None
            if tldr is None:
                notes.append("the TL;DR fence is labelled and empty")
            break
        i = close + 1

    if tldr is None and fence_seen and not notes:
        notes.append("a fenced block sits before the first heading but carries "
                     "no TL;DR label, so it is NOT reported as the memo's "
                     "headline — an unlabelled block could be anything, and "
                     "the wrong five lines is worse than none")

    # --- the DAILY section: `# THE DAILY` up to but never including the next
    #     level-1 heading (which is `# THE RECORD` in every archive so far).
    h1s = [(i, m.group(1)) for i, l in enumerate(lines) if (m := _H1_RE.match(l))]
    daily_at = next((i for i, t in h1s if t.upper().startswith("THE DAILY")), None)
    record_at = next((i for i, t in h1s if t.upper().startswith("THE RECORD")),
                     None)
    if daily_at is None and h1s:
        # A renamed heading is still a memo. Reporting "no memo section" for a
        # file that plainly has one would send the reader to the wrong place —
        # the exact collapse the four absence reasons exist to prevent. So it
        # degrades to "the first section", and SAYS it degraded.
        daily_at = h1s[0][0]
        notes.append(
            f"no `# THE DAILY` heading; read the first section "
            f"({h1s[0][1]!r}) as the memo instead — the heading convention "
            "changed, or this file is not a Daily")

    daily: Optional[str] = None
    if daily_at is not None:
        # THE RECORD ends it when there is one; otherwise the next level-1
        # heading of any name; otherwise the end of the file. Stated as three
        # cases rather than one clever expression, because "and never
        # including `# THE RECORD`" is a promise in the client's own type.
        if record_at is not None and record_at > daily_at:
            end = record_at
        else:
            end = next((i for i, _ in h1s if i > daily_at), len(lines))
        daily = "\n".join(lines[daily_at:end]).strip() or None

    return {"tldr": tldr, "daily": daily,
            "has_long_record": record_at is not None, "notes": notes}


def archive_memo(date: Optional[str] = None) -> dict[str, Any]:
    """The secretary's Daily, parsed for the CEO's desk card.

    THE CEO SAW A PERMANENT ABSENCE AND ASKED ABOUT IT: the memo card on his
    page has been rendering "no memo" since it merged, because the route it
    reads — `GET /fund/desk/archives/memo` — did not exist. The consumer, the
    TypeScript type and the four-way absence vocabulary were all merged; only
    this was missing. A card that reports an absence caused by its own missing
    endpoint is the unwired-control pattern with a friendly face.

    FIVE ABSENCES, KEPT APART, because a surface that collapses them sends the
    reader somewhere useless:

      * ``never_filed``    — docs/archives/ does not exist. She has never run.
      * ``none_yet``       — it exists and holds no Daily. She has run zero
                             times, which is different from never having been
                             seated.
      * ``no_such_day``    — an explicit date nobody documented. NOT the same
                             as a quiet day: the fund has days with no archive
                             because no session was live, and saying "no memo"
                             would imply she filed an empty one.
      * ``unreadable``     — the file is there and could not be read. UNKNOWN,
                             not absent. This fund has answered an
                             unmeasurable with a zero four separate times.
      * ``no_memo_section``— filed and readable, carrying neither a headline
                             nor a Daily section. That is a defect in the
                             ARTIFACT, not a missing memo, and it points at
                             the secretary rather than at the plumbing.

    ON THE QUERY PARAMETER, stated precisely rather than dramatically. ``date``
    is never joined into a path: the row is looked up in the index `archives()`
    already built by globbing ``docs/archives/*.md``, so a traversal string
    matches nothing by construction and the endpoint reads only files that
    directory listed. The anchored ``YYYY-MM-DD`` check is a SECOND lock on
    that — and it earns its place for a different reason: it lets a malformed
    parameter (a broken client) be told apart from a day nobody documented (a
    quiet day), which the note does and the closed `reason` enum cannot.
    """
    if date is not None:
        if not _ARCHIVE_NAME_RE.match(date.strip()):
            # NOT `no_such_day`: the caller asked something malformed, which is
            # a different fact from a day nobody documented, and answering it
            # with a day-shaped absence would hide a broken client.
            return {"available": False, "reason": "no_such_day",
                    "date": None, "path": None, "pdf_path": None,
                    "title": None, "tldr": None, "daily_markdown": None,
                    "has_long_record": False,
                    "note": f"{date!r} is not a YYYY-MM-DD date, so no archive "
                            "was looked for. Nothing was read from disk."}
        date = date.strip()

    index = archives()
    if not index["exists"]:
        return {"available": False, "reason": "never_filed",
                "date": None, "path": None, "pdf_path": None, "title": None,
                "tldr": None, "daily_markdown": None, "has_long_record": False,
                "note": index["note"]}
    if not index["readable"]:
        return {"available": False, "reason": "unreadable",
                "date": None, "path": None, "pdf_path": None, "title": None,
                "tldr": None, "daily_markdown": None, "has_long_record": False,
                "note": index["note"]}

    rows = index["archives"]
    if not rows:
        return {"available": False, "reason": "none_yet",
                "date": None, "path": None, "pdf_path": None, "title": None,
                "tldr": None, "daily_markdown": None, "has_long_record": False,
                "note": "docs/archives/ exists and holds no Daily — the "
                        "secretary has filed nothing yet. She runs at end of "
                        "day on the chair's trigger, so a day with no live "
                        "session has no memo by design."}

    if date is None:
        # `archives()` already sorted newest first, and undated files sort last
        # by construction. Take the newest DATED one: an undated file cannot be
        # presented as "today's memo" when nothing says which day it is.
        row = next((r for r in rows if r["date"]), None)
        if row is None:
            return {"available": False, "reason": "no_memo_section",
                    "date": None, "path": None, "pdf_path": None,
                    "title": None, "tldr": None, "daily_markdown": None,
                    "has_long_record": False,
                    "note": f"{len(rows)} file(s) in docs/archives/ and not one "
                            "of them is named for a day, so which memo is the "
                            "latest cannot be read from disk"}
    else:
        row = next((r for r in rows if r["date"] == date), None)
        if row is None:
            return {"available": False, "reason": "no_such_day",
                    "date": date, "path": None, "pdf_path": None,
                    "title": None, "tldr": None, "daily_markdown": None,
                    "has_long_record": False,
                    "note": f"no Daily is filed for {date}. That is an absence, "
                            "not an empty day: the secretary runs when a "
                            "session is live, and a day nobody documented has "
                            "no memo rather than a blank one."}

    p = Path(row["path"])
    try:
        # Distinguished from `_read`'s silent "" on purpose: this endpoint must
        # be able to say UNREADABLE, and a helper that returns empty string for
        # a permissions error would make that indistinguishable from an empty
        # file. Same reason `archives()` keeps its three absences apart.
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"available": False, "reason": "unreadable",
                "date": row["date"], "path": row["path"],
                "pdf_path": row["pdf_path"], "title": None, "tldr": None,
                "daily_markdown": None, "has_long_record": False,
                "note": f"{row['path']} is on disk and could not be read "
                        f"({e}). Whether a memo exists for {row['date']} is "
                        "UNKNOWN, not no."}

    parts = _split_memo(text)
    title = _title_of(text)
    notes = list(parts["notes"])

    # AVAILABLE TURNS ON THE DAILY SECTION, NOT ON THE TL;DR. Section 1 is what
    # makes the file a memo; the headline is a summary OF it. A memo whose
    # author skipped the fence is still a memo the CEO should see, and a file
    # carrying only a headline is not a Daily — it is a fragment, and calling
    # it available would put five unanchored lines on his desk as though the
    # day were documented.
    if parts["daily"] is None:
        return {"available": False, "reason": "no_memo_section",
                "date": row["date"], "path": row["path"],
                "pdf_path": row["pdf_path"], "title": title,
                # The headline is still returned when there is one: it was
                # read, it is real, and withholding a fact because a
                # neighbouring one is missing is its own kind of dishonesty.
                "tldr": parts["tldr"],
                "daily_markdown": None,
                "has_long_record": parts["has_long_record"],
                "note": f"{row['path']} is filed and readable and carries no "
                        + ("Daily section, only a TL;DR headline"
                           if parts["tldr"] else
                           "Daily section and no TL;DR headline")
                        + ". That is a defect in the ARTIFACT, not a missing "
                          "memo — the file is there, and this points at the "
                          "secretary rather than at the plumbing."
                        + ("" if not notes else " " + "; ".join(notes) + ".")}

    note = (f"Donna's Daily for {row['date']}"
            + ("" if parts["tldr"] else
               ", with no TL;DR headline — the card shows the Daily itself")
            + ("" if parts["has_long_record"] else
               ". No long record section is present in the file")
            + ".")
    if notes:
        note = note + " " + "; ".join(notes) + "."

    return {
        "available": True,
        "reason": None,
        "date": row["date"],
        "path": row["path"],
        "pdf_path": row["pdf_path"],
        "title": title,
        "tldr": parts["tldr"],
        "daily_markdown": parts["daily"],
        "has_long_record": parts["has_long_record"],
        "note": note,
    }


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
                row = {**p, "status": "open"}
                # Seat-filed asks write subject/serves where CEO-typed
                # requests write task/seat. The desk's readers key on
                # task/seat, so an unnormalized seat ask is COUNTED by
                # desk_load but renders as a blank row — an invisible
                # item on the CEO's desk (found 2026-08-21: 2/20 open
                # with a visually clear desk).
                row["task"] = p.get("task") or p.get("subject")
                row["seat"] = p.get("seat") or p.get("serves")
                rows[rid] = row
        elif t == EventType.DESK_REQUEST_APPROVED.value:
            rid = p.get("request_id")
            # Approval only moves an OPEN request forward; a resolved one keeps
            # its terminal state (the fold is order-honest, not last-write-wins).
            if rid in rows and rows[rid].get("status") == "open":
                rows[rid] = {**rows[rid], "status": "approved",
                             "approved_by": p.get("actor"),
                             "approved_at": p.get("at")}
        elif t == EventType.DESK_REQUEST_DECLINED.value:
            rid = p.get("request_id")
            # A rejection lands while open or approved-but-untriggered; a
            # resolved request is history and keeps its terminal state.
            if rid in rows and rows[rid].get("status") in ("open", "approved"):
                rows[rid] = {**rows[rid], "status": "declined",
                             "declined_by": p.get("actor"),
                             "declined_at": p.get("at"),
                             "decline_reason": p.get("reason")}
        elif t == EventType.DESK_REQUEST_RESOLVED.value:
            rid = p.get("request_id")
            # Resolution only completes a request still on the path (open or
            # approved) — it must not overwrite a rejection: executing a
            # declined ask would be the CTO overriding the CEO's no.
            if rid in rows and rows[rid].get("status") in ("open", "approved"):
                rows[rid] = {**rows[rid], "status": "resolved",
                             "resolved_at": p.get("at"),
                             "resolution": p.get("resolution")}
    return sorted(rows.values(), key=lambda r: r.get("at") or "", reverse=True)


def _ts(value: Any):
    """An ISO timestamp as a comparable instant, or None if it is not one.

    Never a string compare: the log writes `+00:00` and hand-written fixtures
    write `Z`, and lexicographic order across the two is wrong exactly where it
    matters. Unparseable returns None, and every caller treats that as "cannot
    compare" rather than as an ordering that happens to sort.

    A timestamp with NO zone is read as UTC — the same assumption
    ``utc_day_bounds`` already makes, and stated here rather than left to
    whichever comparison hits it first. The alternative is worse than an
    assumption: Python refuses to order a naive datetime against an aware one,
    so a single unzoned string would raise from inside a payload builder.
    """
    from datetime import datetime, timezone
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        t = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _within_window(dispatched_at: Any, window_floor: Any) -> bool:
    """Could a return for this dispatch be inside the run window we searched?

    True when there is no floor (the recorder was read and holds no runs at
    all, so "nothing came back" is a MEASURED negative). False when either
    timestamp cannot be read — an incomparable pair is an unknown, and an
    unknown must not report as a clean look.
    """
    if window_floor is None:
        return True
    a, b = _ts(dispatched_at), _ts(window_floor)
    if a is None or b is None:
        return False
    return a >= b


def _activity(store: Any, runs: Optional[list[dict[str, Any]]] = None,
              runs_limit: Optional[int] = None) -> dict[str, dict[str, Any]]:
    """What each seat is doing RIGHT NOW, folded from dispatch/resolve events.

    The spine cannot see a Claude agent thinking; what it can see is the CTO
    session recording "dispatched X to seat Y" and "Y delivered Z". That is the
    truthful resolution available, and the UI renders exactly it - a spinner
    pretending to watch the agent's cursor would be theatre.

    THREE STATES, not two (constitution, from the CEO's instruction on desk
    request 907ecc74: *"no it should nto close automatically since the cto needs
    to review the work be satisified and then log or do what needs to be done
    and then close it"*):

      WORKING          dispatched, and nothing has come back.
      AWAITING REVIEW  the seat RETURNED — a run exists carrying this
                       dispatch's trace — and no resolution has been recorded.
                       An obligation on the CHAIR, not a busy seat.
      idle             neither. A real state, not a gap: a bench seat that is
                       never idle is a bottleneck.

    Measured on the live spine 2026-08-22, which is why this is not cosmetic:
    the builder's desk read `working` for 21 hours and the analyst's for 19,
    both after their dispatches had returned — and two agents in parallel are
    permitted as of the same week, so a chair reading this payload could not
    tell whether a slot was free.

    IT DOES NOT AUTO-CLOSE, and a test asserts it. Closing is the chair's
    judgement step — review the work, be satisfied, file what needs filing.
    Deriving `closed` from "a run came back" would make the board report a
    completion nobody performed.

    DETECTION IS IDENTIFIER-BASED AND INCOMPLETE, reported rather than hidden.
    A dispatch is matched to a run on EXACT identifiers only — the dispatch's
    `trace_id`, then its `task_id`, against the run's `trace_id` or `run_id`.
    Nothing is matched on seat plus a timestamp: a near-miss there would mark
    an unrelated run as this dispatch's return and invent an obligation the
    chair does not have. Measured over the live log: 17 of 24 dispatches match
    on trace_id, 8 on task_id, and 4 carry NO trace_id at all and therefore can
    never be matched. Those four report `review_detectable: false` and stay
    WORKING — "still running" and "we cannot see" must not render as the same
    confident word.

    ``runs_limit`` is the cap ``runs`` was fetched under, so a truncated list
    can be told from a complete one. See ``window_floor`` below.
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

    # Which run identifiers exist at all, so a dispatch can be matched against
    # them. `runs` is None when the flight recorder could not be read — a
    # different fact from "it was read and held nothing", and the two must not
    # collapse: the first makes detection unavailable, the second makes it
    # available and negative.
    recorder_read = runs is not None
    run_by_key: dict[str, str] = {}
    resolved: list[str] = []
    for r in (runs or []):
        rid = r.get("run_id")
        if not rid:
            continue
        for key in (r.get("trace_id"), rid):
            if key:
                run_by_key.setdefault(key, rid)
        if r.get("resolved_at"):
            resolved.append(r["resolved_at"])
    # THE WINDOW'S FLOOR, and why it is load-bearing. `runs` is the newest N by
    # resolved_at, so when that list is TRUNCATED a dispatch made before its
    # oldest row may have a return that resolved outside it — invisible to us.
    # A run for a dispatch always resolves after the dispatch, so a dispatch at
    # or after the floor would have its return inside the window if one
    # existed; before the floor, a miss proves nothing. Without this the
    # payload would report `review_detectable: true, status: working` for every
    # old dispatch, which is a confident answer built on a truncated list.
    #
    # `runs_limit` is what makes the rule EXACT rather than merely careful: a
    # list shorter than the cap it was fetched under is the whole table, so
    # there is no outside to fall into and the floor does not apply. Without
    # that check the honest-unknown would fire on knowable cases, which is its
    # own kind of wrong answer.
    #
    # The floor is chosen by parsed INSTANT, not by string order — `Z` and
    # `+00:00` sort wrongly against each other, and picking the floor with the
    # comparison this function exists to avoid would be a neat way to be
    # careful in one line and careless in the one above it.
    truncated = (runs_limit is not None and runs is not None
                 and len(runs) >= runs_limit)
    window_floor = None
    if resolved and truncated:
        dated = [(t, s) for s in resolved if (t := _ts(s)) is not None]
        window_floor = min(dated)[1] if dated else None

    out = {}
    for seat in list(REQUEST_KINDS.values()):
        row = seats.get(seat, {})
        w = row.get("working_on")
        # EXACT identifiers only, in the order that matches most on the live
        # log: the dispatch's own trace first (17 of 24), its task_id second
        # (8 of 24, the older convention where the two were the same string).
        keys = [k for k in ((w or {}).get("trace_id"), (w or {}).get("task_id"))
                if k]
        back = None
        for k in keys:
            back = run_by_key.get(k)
            if back:
                break
        out[seat] = {
            "status": ("awaiting_review" if back else "working") if w else "idle",
            "task": (w or {}).get("task"),
            "since": (w or {}).get("at"),
            "task_id": (w or {}).get("task_id"),
            # The run that came back, so the chair can open it and review.
            "returned_run_id": back,
            # Whether the spine could TELL a returned dispatch from a running
            # one FOR THIS DISPATCH. Per-dispatch and not per-payload: a
            # dispatch carrying no identifier is undetectable even with a
            # fully readable recorder, and reporting it as detectable would
            # dress "we never looked" as "nothing came back". None when the
            # seat is idle — there is nothing to detect. A positive match is
            # its own proof, so it short-circuits every other condition.
            "review_detectable": (
                True if back else
                (recorder_read and bool(keys)
                 and _within_window((w or {}).get("at"), window_floor))
            ) if w else None,
            "last_delivered": row.get("last_delivered"),
        }
    return out


#: The CEO's standing triage rule (2026-08-20, CEO instruction, registered as
#: a dispatch trigger): when OPEN items on the CEO's desk exceed this, a COO
#: triage dispatch is DUE. Registered here so the count and the rule live in
#: one place — the count crossing it is a SIGNAL for the CTO to dispatch, and
#: nothing in this module or the spine dispatches anything. The ignition keys
#: stay human; this is the dashboard light, not the starter motor.
#: VERSIONED CHANGE 2026-08-21: 20 -> 50, and the comparison moved from
#: `>` to `>=`, by CEO instruction verbatim: "Lets run coo on >=50 items or
#: we can trigger as needed." WRITTEN REASON (the rule requires one in
#: either direction, and this is a LOOSENING so it is recorded loudly):
#: COO triage #3 measured that 11 of 20 open recommendations were already
#: executed — the counter was summoning the seat on stale bookkeeping
#: rather than on decisions. Manual dispatch at any count remains available
#: and is the CEO's stated fallback. OBJECTION ON THE RECORD: the COO
#: (interest disclosed by the seat itself) recommended KEEPING 20, arguing
#: the number is not the defect — the counter is blind to items at status
#: `accepted` whose execution requires the CEO personally (three live that
#: day, including PM R1). Raising the threshold does NOT address that blind
#: spot; it remains open work. Applied by the co-CTO chair on the CEO's
#: explicit approval; the constitution carries the same amendment and the
#: objection beside it.
COO_TRIAGE_THRESHOLD = 50


# --------------------------------------------------- whose move is it? ------
#
# THE DEFECT THIS SECTION EXISTS TO FIX (CEO, 2026-08-22, verbatim): *"I maybe
# out of sync with whats happening across agents but they sustain on my queue
# even if that work has been done. this needs to be fixed."*
#
# `desk_load` promised to measure "how many things are actually waiting for the
# CEO" and measured something else: rows whose STATUS LABEL was open. A status
# label is written by a seat at filing time, not by the world, so an engineering
# ticket nobody would ever hand the CEO counted exactly like a decision only he
# can make. Measured on the live record by replaying the decision events: at
# 2026-08-21T20:39Z the counter read 18 (17 recommendations + 1 desk request)
# and the chair cleared every one of them by hand eight minutes later.
#
# So the question the counter asks changes: not "what status does this row
# carry" but **WHOSE MOVE IS IT**. Two independent facts answer that, and
# neither alone is sufficient — both failures are measured, not supposed:
#
#   * the LIFECYCLE says whether a decision is still outstanding. Status alone
#     is what produced the 18 above.
#   * the KIND says whose decision it is. Kind alone is worse: all 9 rows
#     carrying kind `awaits-ceo` on 2026-08-22 were already ACCEPTED, so a
#     status-blind kind predicate would have parked them on the CEO's counter
#     permanently — the complaint above, made structural.
#
# HONEST LIMIT, STATED HERE BECAUSE IT SETS EXPECTATIONS FOR THE TRIGGER: `kind`
# is free text and the corpus proves it — 84 distinct values across 219
# recommendations, 49 of them appearing exactly once, and the vocabulary grows
# every dispatch. So the table below routes only kinds whose NAME ALONE settles
# the actor, and everything else falls through to the CEO. Measured coverage:
# 41 of 219 rows (18.7%) route away from the CEO by kind. The kind axis is a
# real improvement and it is a small one; the lever that would actually decouple
# this counter from the bench's output volume is `next_actor` written at FILING
# time, which is why the explicit field below takes precedence over all of this.

#: The only actors this counter knows. `unknown` is a first-class member, not a
#: fallback that got away: a row whose next actor cannot be determined COUNTS,
#: because "I could not measure that" has been answered with "zero" by four
#: separate instruments in this fund already.
NEXT_ACTORS = ("ceo", "chair", "seat", "nobody", "unknown")

#: Kinds whose NAME ALONE settles who moves next. Deliberately short.
#:
#: The inclusion rule, applied to every entry and worth stating because it is
#: what stops this table rotting into prose-matching: a kind earns a row here
#: only if the WORD determines the actor without reading the recommendation.
#: `repair-required` is an engineering repair whoever wrote it; `fix` is not —
#: the corpus carries `fix` rows that are code changes and `fix` rows that are
#: portfolio decisions, so `fix` is absent and falls through to the CEO.
#:
#: The routing itself is the constitution's ownership table, not taste: the CTO
#: chair owns "what gets built next", and merging a builder diff is named as a
#: co-CTO action. Everything engineering-shaped therefore belongs to the chair.
KIND_ACTORS = {
    # The chair's own work — building, merging, dispatching.
    "build": "chair",
    "harness": "chair",
    "harness_gap": "chair",
    "engineering_ticket": "chair",
    "infra": "chair",
    "code_fix": "chair",
    "ui": "chair",
    "api_card": "chair",
    "docs": "chair",
    "repair_required": "chair",
    "block_merge": "chair",
    "dispatch_request": "chair",
    "next_dispatch": "chair",
    # A positive assertion rather than a default, so the common case is
    # readable in the table instead of implied by its absence.
    "awaits_ceo": "ceo",
    # Nothing is owed: the row records a fact or asks that a round NOT be spent.
    "no_action": "nobody",
    "measurement_recorded": "nobody",
}

#: Kind PREFIXES that name their own recipient. `handoff_to_mechanism` and
#: `note-to-riskofficer` both exist in the corpus and both are seat-to-seat.
_SEAT_KIND_PREFIXES = ("handoff_to_", "note_to_", "routed_to_")

#: Statuses after which nothing more is expected of anyone. Kept here rather
#: than imported from deskstore so this module stays importable without a
#: database, and asserted equal to deskstore's list by a test — one definition
#: with a guard beats two that drift.
TERMINAL_STATUSES = ("rejected", "done", "noted")

#: Bump when the table or the precedence changes. Published in the payload so a
#: reader can tell WHICH rules produced a count they are looking at — the same
#: discipline every threshold here follows.
NEXT_ACTOR_RULES_VERSION = "v1 (2026-08-22)"


def _contract_digest() -> Optional[str]:
    """The digest of the desk-stage contract this build was generated against.

    THE ONE DRIFT A HERMETIC TEST CANNOT SEE. The contract file
    (``contract/desk_stage_contract.v1.json``) is checked in to BOTH this repo
    and KryptonPay, and each repo's suite pins its own copy — which catches an
    edit on either side, and does NOT catch this repo being regenerated while
    the other copy stays stale. There is no shared build to catch it in.

    So it is detected where it can be: the digest travels in the payload, the
    CEO page compares it against the one its own fixture carries, and a
    mismatch renders as a visible warning. A silent drift between the counter
    and the page is precisely the 11-vs-6 defect, and it has now shipped twice.

    ``None`` when the file is missing or unreadable — reported absent, never
    defaulted to a value that would read as agreement. A spine deployed without
    the contract file must not claim a digest it does not have.
    """
    try:
        import hashlib
        import json as _json
        p = Path(__file__).resolve().parents[2] / "contract" \
            / "desk_stage_contract.v1.json"
        body = _json.loads(p.read_text(encoding="utf-8"))
        stated = body.get("digest")
        # Recompute rather than trust the field: a self-declared digest that
        # nobody checks is a label, and this fund has a rule about those.
        body.pop("digest", None)
        actual = hashlib.sha256(_json.dumps(
            body, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False).encode("utf-8")).hexdigest()
        return actual if actual == stated else None
    except Exception as e:  # noqa: BLE001
        logger.info("desk stage contract unreadable: %s", e)
        return None


#: Read once at import — the file does not change under a running process, and
#: a per-request stat on the CEO's desk buys nothing.
CONTRACT_DIGEST = _contract_digest()


def _norm_kind(kind: Any) -> str:
    """Lower-case, separator-insensitive. Seats write `harness-gap` and
    `engineering_ticket` in the same corpus; a table that cared would be a
    table with two entries per idea and one of them always missing."""
    if not isinstance(kind, str):
        return ""
    return kind.strip().lower().replace("-", "_").replace(" ", "_")


def next_actor(rec: Any) -> dict[str, Any]:
    """Whose move is it on this recommendation: {actor, basis, why}.

    PRECEDENCE:

      1. a TERMINAL status. Nothing follows a rejected, done or noted row, and
         no label may say otherwise — this rule sits ABOVE the explicit field
         on purpose. An explicit `next_actor` written while the row was live
         and never cleared would otherwise pin a closed row to the CEO's
         counter forever, which is the complaint this module is fixing, in a
         costume. (`decide_recommendation` also clears the field on a terminal
         move; this is the belt to that pair of braces, for rows written by any
         other path.)
      2. an EXPLICIT ``next_actor`` on the row. Authoritative below terminal,
         because it is a statement about the world made by whoever knew — and
         it is the only path that can express the COO's standing objection (a
         row the CEO has ACCEPTED whose execution is still the CEO's own act,
         of which there were three live on 2026-08-21). Nothing writes it yet;
         that is a fact about our capture, reported in the payload, not hidden.
      3. the rest of the LIFECYCLE. accepted/staged -> the chair, who executes
         what the CEO decided. A status outside the known vocabulary is
         UNKNOWN, never quietly one of the five.
      4. the KIND, for undecided rows only, against ``KIND_ACTORS``.
      5. otherwise the CEO — because a recommendation is by construction a
         thing a seat asks the firm to decide, and the decision channel is the
         CEO's. Failing toward "he must look" is the safe direction for a
         control; failing toward "nobody must look" is how work disappears.

    NOTHING HERE READS THE RECOMMENDATION'S PROSE. The emergency sweep that
    produced this brief found six finished rows by grepping their text for
    "EXECUTED"; that was the right measure at the time and is the wrong
    permanent one, because a heuristic over free English rots silently and
    reports the rot as a count.
    """
    if not isinstance(rec, dict):
        return {"actor": "unknown", "basis": "unreadable",
                "why": "the row is not a readable recommendation, so whose "
                       "move it is cannot be determined — counted as needing "
                       "attention rather than dropped"}

    status = rec.get("status")
    if status in TERMINAL_STATUSES:
        return {"actor": "nobody", "basis": "lifecycle",
                "why": f"status {status!r} is terminal — nothing follows it, "
                       "and no label may claim otherwise"}

    explicit = rec.get("next_actor")
    if explicit is not None:
        e = explicit.strip().lower() if isinstance(explicit, str) else ""
        if e in NEXT_ACTORS and e != "unknown":
            return {"actor": e, "basis": "explicit",
                    "why": f"the row states its next actor is the {e}"}
        return {"actor": "unknown", "basis": "explicit_unrecognised",
                "why": f"the row states next_actor={explicit!r}, which is not "
                       f"one of {NEXT_ACTORS} — an unreadable claim is UNKNOWN, "
                       "not an excuse to fall back to a guess"}

    if status in ("accepted", "staged"):
        return {"actor": "chair", "basis": "lifecycle",
                "why": f"status {status!r} means the CEO has already decided; "
                       "what remains is the chair's to execute"}
    if status not in (None, "open"):
        return {"actor": "unknown", "basis": "status_unrecognised",
                "why": f"status {status!r} is outside the known vocabulary, so "
                       "whether a decision is outstanding cannot be read"}

    kind = _norm_kind(rec.get("kind"))
    for prefix in _SEAT_KIND_PREFIXES:
        if kind.startswith(prefix) and len(kind) > len(prefix):
            return {"actor": "seat", "basis": "kind",
                    "why": f"kind {rec.get('kind')!r} names its own recipient — "
                           "a seat-to-seat handoff is not the CEO's load"}
    routed = KIND_ACTORS.get(kind)
    if routed:
        return {"actor": routed, "basis": "kind",
                "why": f"kind {rec.get('kind')!r} routes to the {routed}"}
    return {"actor": "ceo", "basis": "default",
            "why": "undecided, and nothing routes it elsewhere — a "
                   "recommendation awaiting a decision awaits the CEO's"}


#: WHOSE MOVE AN OPEN DESK REQUEST IS.
#:
#: **SHIPPED AS ``ceo`` — THE EXISTING BEHAVIOUR, UNCHANGED. The change the
#: brief asked for is NOT applied, and the reason is a consequence the brief
#: did not have.**
#:
#: P-2/H-2 asked for `chair` here, flagged as a loosening (it takes rows off
#: the CEO's counter, so the COO triage trigger fires later). It was built,
#: measured, rendered — and the rendered page showed a second consequence
#: nobody had priced: **it removes the CEO's ask-approval control from his own
#: page.** His page routes asks to a card that carries Approve/Decline only
#: while the ask is on his list; route them to the chair and they render in the
#: chair's dispatch lane, which is a one-line summary view with no approval
#: control anywhere in it. The counter would have gone quiet and so would the
#: button.
#:
#: A loosening that also REMOVES A CONTROL is not a builder's call. The
#: constitution routes it to the adversary blind and then to the CEO's click,
#: and it is filed that way with the measurements below attached, rather than
#: applied here and mentioned in a diff.
#:
#: WHAT THE MEASUREMENTS STILL SAY, because they are the reason to revisit it:
#:
#: THE OLD READING RESTED ON A CIRCULAR MEASUREMENT, AND THAT IS THE NEW
#: EVIDENCE. Both this module and ``desk_items`` justified ``ceo`` with: "all
#: 25 DeskRequestApproved events carry `ceo` or a via-chair identity, none a
#: chair acting alone." Re-measured 2026-08-24 at n=90 the ratio still holds —
#: and it proves nothing, because ``DESK_APPROVAL_ALLOWLIST`` in
#: ``app/api/v1/fund.py`` admits ONLY ``{ceo, neelesh, neelesh-via-cto,
#: neelesh-via-co-cto}``. No other actor CAN approve a desk request. "Every
#: approval came from the CEO" is a restatement of the allowlist, not a finding
#: about whose move it is.
#:
#: THE NON-CIRCULAR MEASUREMENT SAYS THE OPPOSITE, and it is two counts over
#: the live log (2026-08-24, ``GET /fund/events?limit=1000``, seq 335-1334):
#:
#:   * **28 of the 49 requests resolved in the window were NEVER approved.**
#:     The modal path for an open request is that the chair picks it up and
#:     serves it; 57% of served requests carry no approval event at all.
#:   * **11 of the 11 currently-open requests were filed by ``cto``,
#:     ``neelesh-via-cto`` or ``operator``** — the chair or the operator,
#:     addressed to a seat. Not one is a seat-filed ask waiting for a blessing.
#:
#: The desk's own ``execution_note`` has said so since it was written:
#: "Requests are picked up by the CTO session and dispatched to the bench."
#: The approval step exists and remains the CEO's when it happens; it is not
#: what an open request is BLOCKED on, and a counter that says otherwise puts
#: the chair's dispatch queue on the CEO's desk.
#:
#: WHAT WOULD CHANGE THIS DECISION'S MIND, recorded at decision time: a
#: placement for the CEO's ask-approval control that survives the rows leaving
#: his list. Then this constant becomes ``"chair"`` in a one-line versioned
#: change, and the measurements above are already the written reason.
OPEN_REQUEST_ACTOR = "ceo"

#: Bumped when the line above moves, so a client can tell which rule produced
#: the number it is holding. v1 IS the pre-existing behaviour, named for the
#: first time — the rule used to live untitled inside ``desk_items``.
REQUEST_ROUTING_VERSION = ("request routing v1 (named 2026-08-24) — open -> "
                           "ceo, approved -> chair")


def open_request_actor(status: Any) -> str:
    """Whose move a desk request is, from its status alone.

    ``open`` -> the CEO (his blessing is the next act on the record's own
    reading). ``approved`` -> the chair, which must dispatch it. Terminal ->
    nobody, the same rule ``next_actor`` applies to a terminal recommendation.

    NET BEHAVIOUR CHANGE FROM THE BASE COMMIT: ZERO. This is the rule
    ``desk_items`` already applied inline, lifted into one named function so
    that the spine, the counter and the CEO's page read one answer instead of
    three — which is the repair that actually shipped here. The routing MOVE
    that P-2/H-2 asked for is filed as a recommendation with its measurements;
    see ``OPEN_REQUEST_ACTOR`` for why a builder did not apply it.
    """
    s = (status or "open").strip().lower() if isinstance(status, str) else "open"
    if s in _TERMINAL_REQUEST_STATUSES:
        return "nobody"
    if s == "approved":
        return "chair"
    return OPEN_REQUEST_ACTOR


def desk_load(open_recommendations: list[dict[str, Any]],
              pending_orders: Any, open_requests: Any,
              chair_backlog: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """How many things are actually waiting for the CEO, and whether that is
    past the COO triage trigger.

    "Open items" is defined exactly, because a number whose definition drifts
    is worse than no number: recommendations whose NEXT REQUIRED ACTOR is the
    CEO (or cannot be determined) + pending orders + requests awaiting
    approval. Each component that cannot be counted is reported as None and
    named in ``unreadable`` — the total then carries ``complete: false``,
    because a partial count that reads like a full one is how a desk under the
    trigger looks quiet.

    THE OTHER TWO COMPONENTS WERE CHECKED AGAINST THE RECORD RATHER THAN
    ASSUMED, since the whole point of this change is that a component must
    earn its place on the CEO's counter:

      * pending orders — an order awaiting approval is the CEO's click by
        construction; anything the auto-approval envelope takes never appears
        here at all.
      * requests awaiting approval — all 25 `DeskRequestApproved` events in
        the log carry actor `ceo` or `neelesh-via-cto` (the CEO's instruction
        staged by the chair). Zero were approved by a chair on its own
        authority, so an open desk request is a CEO decision. Note that
        `view()`'s own note calls the same rows "waiting for the CTO session",
        which is about DISPATCH — a different step, after the approval.

    NOTHING IS HIDDEN TO MAKE THE NUMBER SMALLER. Every row is counted in
    ``by_actor``; the ones that left the CEO's figure are summed in
    ``open_elsewhere`` and ``decided_awaiting_execution``; the desk's own list
    of recommendations is untouched; and the note names the chair's backlog out
    loud. Solving a counting problem by dropping rows would be the same defect
    wearing the opposite sign.

    MEASURED EFFECT ON THE TRIGGER (this changes WHEN the COO is summoned, so
    it is recorded loudly): replayed against the live decision log at
    2026-08-21T20:39Z, the old predicate counted 18 and this one counts 13 —
    12 recommendations plus the 1 open desk request. Five recommendations moved
    off the CEO's counter: two adversary `repair-required` grounds and one
    `block-merge` to the chair, one `note-to-riskofficer` to a seat, one
    `no_action` to nobody. The trigger fires LATER, which is the loosening
    direction, and the reason is that those five were never the CEO's to
    decide.

    ``chair_backlog`` (added 2026-08-22, from the secretary's friction ledger)
    IS REPORTED AND IS DELIBERATELY NOT SUMMED INTO ``total``. The dict is
    published whole, listed in ``excluded_from_total``, and named in the note.

    THE REASON IS THE SAME ONE THE PARAGRAPH ABOVE RESTS ON, POINTED THE OTHER
    WAY. An approved-but-undispatched request is waiting on the CHAIR to
    dispatch it; the CEO already said yes. This number's stated definition is
    "awaiting the CEO", and a component whose next actor is not the CEO does
    not belong in it — the module's own rule is that nothing is hidden to make
    the figure smaller, and the mirror of that rule is that nothing is added to
    make it larger.

    IT ALSO WOULD HAVE MOVED A CONTROL WITHOUT MOVING ITS THRESHOLD, WHICH IS
    THE MEASURED PART. Against the live desk on 2026-08-22 the CEO's total is
    38 with ``coo_triage_due: false``; folding in the 30 approved-undispatched
    requests makes it 68 and flips the trigger TRUE the same second. Changing
    what a threshold counts is a threshold change wearing a schema change's
    clothes, and it points at exactly the failure the COO already named: the
    counter would then be calibrated against BENCH OUTPUT VOLUME rather than
    CEO load. Including it in ``total`` is therefore a CEO decision, not a
    builder's — and it is one line here if he takes it.
    """
    def _count(x) -> Optional[int]:
        if x is None:
            return None
        try:
            return int(x if isinstance(x, int) else len(x))
        except (TypeError, ValueError):
            return None

    by_actor = {a: 0 for a in NEXT_ACTORS}
    explicit_rows = 0
    # A PARTITION, not overlapping tallies: every row lands in exactly one of
    # the CEO's figure, `decided_awaiting_execution`, or `open_elsewhere`.
    # Written this way because the first attempt reported "26 elsewhere" beside
    # a page saying "6 with the chair" — both true, both counting different
    # things, one label apart. Two numbers that sound like the same number are
    # the defect this whole module is being repaired from.
    decided_rows = 0
    open_elsewhere = 0
    if isinstance(open_recommendations, list):
        # ONE classification pass, and the CEO's rows are collected in it. The
        # first version classified twice — once to tally, once to filter — and
        # two calls to the same predicate over the same row is two chances for
        # the count and the list to disagree, which is the defect above.
        mine = []
        for row in open_recommendations:
            verdict = next_actor(row)
            actor = verdict["actor"]
            by_actor[actor] = by_actor[actor] + 1
            if verdict["basis"] == "explicit":
                explicit_rows = explicit_rows + 1
            status = row.get("status") if isinstance(row, dict) else None
            # UNKNOWN counts toward the CEO. A row whose next actor could not
            # be read is work he may still owe, and reporting it as zero would
            # be this fund's oldest mistake in a new place.
            if actor in ("ceo", "unknown"):
                mine.append(row)
            elif status in ("accepted", "staged"):
                decided_rows = decided_rows + 1
            else:
                open_elsewhere = open_elsewhere + 1
        open_recommendations = mine

    parts = {
        "open_recommendations": _count(open_recommendations),
        "pending_orders": _count(pending_orders),
        "requests_awaiting_approval": _count(open_requests),
    }
    unreadable = sorted(k for k, v in parts.items() if v is None)
    # THE OPEN-REQUEST LEG STILL COUNTS, and that is the shipped state rather
    # than the one P-2/H-2 asked for. See `OPEN_REQUEST_ACTOR`: the move was
    # built and measured, and the rendered page showed it would also remove the
    # CEO's ask-approval control, which makes it a decision for the adversary
    # blind and the CEO rather than for a builder. `requests_by_actor` below
    # publishes the finding without acting on it.
    total = sum(v for v in parts.values() if v is not None)
    backlog = chair_backlog if isinstance(chair_backlog, dict) else None
    undispatched = (backlog or {}).get("requests_approved_undispatched")
    return {
        "total": total,
        "complete": not unreadable,
        "unreadable": unreadable,
        "components": parts,
        # The full census by actor, so nothing routed away becomes invisible.
        "by_actor": by_actor,
        # The other two legs of the partition. OPEN work owned by the chair or
        # a seat is a different fact from work the CEO already DECIDED and is
        # waiting to see executed, and the desk page renders them as two
        # different sentences — so they are two numbers here, not one.
        "open_elsewhere": open_elsewhere,
        "decided_awaiting_execution": decided_rows,
        # How many rows STATED their next actor instead of being inferred.
        # Zero today: nothing writes the field yet, and a reader deserves to
        # know the count rests on inference rather than on declaration.
        "explicit_next_actor": explicit_rows,
        # THE CHAIR'S OWN QUEUE, reported and NOT summed into `total`. See the
        # docstring: these are approved requests awaiting dispatch, so the CEO
        # has already decided them and folding them into a figure defined as
        # "awaiting the CEO" would move a control without moving its threshold.
        # None means it was not supplied — never zero, because "the chair has
        # nothing waiting" is a claim and "nobody computed it" is not.
        "requests_approved_undispatched": undispatched,
        "chair_backlog": backlog,
        # OPEN DESK REQUESTS, BY WHOSE MOVE IT IS. Kept apart from `by_actor`
        # rather than folded into it: `by_actor` is documented as the
        # recommendation census, and quietly widening what a published number
        # counts is the "two numbers wearing one label" defect this module
        # spends four paragraphs warning about.
        "requests_by_actor": (
            {a: sum(1 for r in open_requests
                    if open_request_actor(
                        (r or {}).get("status") if isinstance(r, dict)
                        else None) == a)
             for a in NEXT_ACTORS}
            if isinstance(open_requests, list) else None),
        # Named explicitly so a reader of the payload can see WHAT was left out
        # of the total rather than having to diff two versions of this file.
        "excluded_from_total": (["requests_approved_undispatched"]
                                if undispatched else []),
        "rules_version": NEXT_ACTOR_RULES_VERSION,
        "request_routing_version": REQUEST_ROUTING_VERSION,
        # The shared contract this spine's routing was generated against, so a
        # client can tell whether its own copy still agrees. `None` = the file
        # could not be read or did not match itself; the page then says the
        # agreement is UNVERIFIED rather than assuming it holds. See
        # `_contract_digest`. Purely informational — it changes no count and
        # cannot change `coo_triage_due`.
        "contract_digest": CONTRACT_DIGEST,
        "threshold": COO_TRIAGE_THRESHOLD,
        "coo_triage_due": total >= COO_TRIAGE_THRESHOLD,
        "note": (
            f"{total} item(s) awaiting the CEO against a triage trigger of "
            f"{COO_TRIAGE_THRESHOLD}"
            + (f"; {by_actor['unknown']} of them because their next actor could "
               "not be determined, which counts rather than disappears"
               if by_actor["unknown"] else "")
            + (f". {open_elsewhere} further recommendation(s) are OPEN work "
               "owned by the chair or another seat — counted here so they stay "
               "visible, and excluded from the CEO's figure because they were "
               "never his to decide" if open_elsewhere else "")
            + (f". {decided_rows} are decided and awaiting execution"
               if decided_rows else "")
            + (f". {parts['requests_awaiting_approval']} of them are open desk "
               "request(s), counted as his — MEASURED AND DISPUTED: 28 of the "
               "49 requests resolved in the last log window carry no approval "
               "event at all, so the modal path is the chair serving them. "
               "Moving them is a CEO decision because it would also take his "
               "approve control off the page; see desk.OPEN_REQUEST_ACTOR"
               if parts["requests_awaiting_approval"] else "")
            + (f". Separately, {undispatched} approved desk request(s) await "
               "DISPATCH by the chair — reported, and deliberately not added "
               "to the CEO's figure, because he already decided them"
               if undispatched else "")
            + (f" — {', '.join(unreadable)} could not be counted, so the real "
               "total is at least this" if unreadable else "")
            + (". A COO triage dispatch is DUE; the CTO fires it when a session "
               "is live — crossing this line triggers nothing by itself."
               if total >= COO_TRIAGE_THRESHOLD else ".")
        ),
    }


def _chair_backlog(store: Any) -> Optional[dict[str, Any]]:
    """Approved desk requests still awaiting dispatch — the chair's own queue.

    DELEGATES TO ``metrics.friction`` RATHER THAN RE-FOLDING HERE, and that is
    the point of the whole 2026-08-22 metrics change: the request lifecycle is
    folded in ONE place. A second copy in this module would drift within a
    week, and the drift would be invisible because both copies would look
    plausible. Measured cost of the extra pass over the log: 0.03s at 965
    events, against a desk payload that already takes 0.20s.

    Returns None — not an empty dict and never a zero — when the fold cannot
    be computed. ``desk_load`` renders that as absent.
    """
    try:
        from app.fund import metrics
        f = metrics.friction(store)
    except Exception as e:  # noqa: BLE001
        logger.warning("desk: chair backlog unreadable: %s", e)
        return None
    rows = [r for r in f["requests"] if r["state"] == "approved_undispatched"]
    cov = f["dispatch_link_coverage"]
    return {
        "requests_approved_undispatched": len(rows),
        "oldest_hours": rows[0]["age_hours"] if rows else None,
        "oldest_request_id": rows[0]["request_id"] if rows else None,
        # The figure is a CEILING while any dispatch event cannot be linked to
        # its request: such a request looks undispatched here even if it was
        # dispatched. Stated on the number rather than in a footnote.
        "upper_bound": not cov["complete"],
        "dispatch_link_coverage": cov,
        "note": (f"{len(rows)} approved request(s) await dispatch by the chair"
                 + (f", oldest {rows[0]['age_hours']:.1f}h since filing"
                    if rows and rows[0]["age_hours"] is not None else "")
                 + ("; an UPPER BOUND — "
                    f"{cov['unlinkable_no_request_id']} of "
                    f"{cov['dispatch_events']} dispatch events carry no "
                    "request_id" if not cov["complete"] else "")
                 + ". Not counted toward the CEO's figure: he already "
                   "approved them."),
    }


def utc_day_bounds(now: Any = None) -> tuple[str, str, str]:
    """(day, start, end) for the UTC day containing ``now``.

    UTC because the event log is UTC and the fund's day boundary is the
    venue's, not the reader's — a local bucket would move a dispatch to a
    different day depending on who opened the page.

    THE ARITHMETIC LIVES IN ``metrics.day_bounds`` AND IS NOT REPEATED HERE
    (2026-08-22). Two copies of a day boundary is two chances to disagree about
    which day a dispatch happened on, and the disagreement would be invisible
    because both copies would look right. This function survives for its
    three-tuple shape, which its callers use; the bounds themselves come from
    one place.
    """
    from datetime import datetime, timezone
    from app.fund.metrics import day_bounds
    n = now or datetime.now(timezone.utc)
    day = (n if getattr(n, "tzinfo", None) else n.replace(tzinfo=timezone.utc)) \
        .astimezone(timezone.utc).date()
    start, end = day_bounds(day)
    return (day.isoformat(), start, end)


def seat_telemetry(day_runs: Optional[list[dict[str, Any]]],
                   activity: dict[str, dict[str, Any]],
                   day: str,
                   seats: Optional[list[str]] = None) -> dict[str, Any]:
    """Per-seat: is it running now, how often today, at what token cost.

    The CEO's question, verbatim in intent: "is it running, how often today, at
    what token cost". Three facts, and each has a different way of being absent,
    so each carries its own absence rather than a shared zero:

      * ``running_now`` — the dispatch/resolve fold the desk already computes.
        A dispatch with nothing back IS a working seat; the spine cannot watch
        a model think and does not pretend to. A seat whose dispatch has
        RETURNED is not running: ``running_now`` is False and
        ``awaiting_review`` is True. Measured 2026-08-22 before this split
        existed: `running_now` was True for the builder and the analyst
        simultaneously, 21 and 19 hours after both had returned and been
        recorded — a chair reading the payload to see whether a parallel slot
        was free would have been told the bench was full.
      * ``runs_today`` — exact, from a SQL day window, NOT from the capped
        25-run payload. On a day with 26 runs the capped fold would quietly
        drop one, and the dropped one would look like a seat that did nothing.
      * ``tokens_today`` — ``None`` when NO run reported a figure, and
        ``tokens_partial`` when some did and some did not. A sum over 2 of 5
        runs is a FLOOR, and rendering it as a total understates the bill by
        whatever the missing runs cost. The client renders it with a "≥".

    ``day_runs`` is None when the flight recorder could not be read at all. The
    whole block then reports ``readable: false`` and every figure is absent —
    an unreadable recorder must never render as a quiet day.

    Token totals are also broken out BY MODEL, because pricing lives in the UI
    (docs/COST_MODEL_2026-08-20.md's table, mirrored in seatLib.ts) and a blended
    dollar figure computed here would need a second copy of that table. One
    price table, in the place that renders the dollars.
    """
    names = list(seats or REQUEST_KINDS.values())
    readable = day_runs is not None
    out: dict[str, Any] = {}
    for seat in names:
        act = activity.get(seat) or {}
        working = act.get("status") == "working"
        awaiting = act.get("status") == "awaiting_review"
        row: dict[str, Any] = {
            "running_now": working,
            # The third state, carried here too: a returned dispatch is an
            # obligation on the chair, and a telemetry block that dropped it
            # would render the seat as idle — which is how a review queue
            # becomes invisible.
            "awaiting_review": awaiting,
            "returned_run_id": act.get("returned_run_id") if awaiting else None,
            # The task and the clock belong to the dispatch, which is still
            # open in BOTH live states — so they survive the return rather
            # than blanking the moment the run lands.
            "running_task": act.get("task") if (working or awaiting) else None,
            "running_since": act.get("since") if (working or awaiting) else None,
            "runs_today": None,
            "tokens_today": None,
            "tokens_partial": False,
            "runs_missing_tokens": None,
            "tokens_by_model": {},
            "last_run_at": None,
        }
        if readable:
            mine = [r for r in (day_runs or []) if r.get("seat") == seat]
            toks = [r.get("tokens") for r in mine
                    if isinstance(r.get("tokens"), int)]
            by_model: dict[str, int] = {}
            for r in mine:
                t = r.get("tokens")
                if isinstance(t, int):
                    m = (r.get("model") or "unknown").strip() or "unknown"
                    by_model[m] = by_model.get(m, 0) + t
            row["runs_today"] = len(mine)
            row["tokens_today"] = sum(toks) if toks else None
            row["runs_missing_tokens"] = len(mine) - len(toks)
            # Partial only when there IS a figure that is incomplete. With no
            # figure at all the total is absent, which is a stronger statement
            # than "at least zero".
            row["tokens_partial"] = bool(toks) and len(toks) < len(mine)
            row["tokens_by_model"] = by_model
            times = sorted(r.get("resolved_at") or "" for r in mine)
            row["last_run_at"] = times[-1] if times and times[-1] else None
        out[seat] = row

    return {
        "day": day,
        "readable": readable,
        "seats": out,
        "note": (
            f"Per-seat telemetry for {day} (UTC). Runs and tokens are folded "
            "from the flight recorder over that day's window, not from the "
            "capped run list the payload carries."
            if readable else
            "The flight recorder could not be read, so no seat's run count or "
            "token cost is known for today. This is an absence, not a quiet "
            "day."
        ),
    }


def dispatched_request_ids(store: Any) -> set:
    """Request ids a ``DeskDispatched`` event has ever named.

    MOVED HERE 2026-08-24 from ``app/api/v1/fund.py``, which now delegates: the
    lifecycle rail needs this fold on the ``/fund/desk`` path and the CEO
    engine already needed it on the other, and two copies of a fold over the
    same event type is how the request lifecycle drifts. Same reasoning
    ``_chair_backlog`` already gives for delegating to ``metrics.friction``.

    Returns an EMPTY SET when the store cannot be read, and the caller renders
    the rail's `dispatched` stage as not-reached. That is the honest
    degradation here: an unreadable dispatch log cannot prove a dispatch
    happened, and claiming one would advance a stage on no evidence.
    """
    from app.fund.events import EventType

    out: set = set()
    try:
        for e in store.stream(since_seq=0, limit=100_000):
            t = e.get("type") if isinstance(e, dict) else getattr(e, "type", None)
            if getattr(t, "value", t) != EventType.DESK_DISPATCHED.value:
                continue
            p = (e.get("payload") if isinstance(e, dict)
                 else getattr(e, "payload", None)) or {}
            if p.get("request_id"):
                out.add(str(p["request_id"]))
    except Exception as e:  # noqa: BLE001
        logger.info("dispatch fold unavailable: %s", e)
    return out


def _annotated_request(req: Any, dispatched_ids: Any = ()) -> Any:
    """One desk request with its card fields and its lifecycle rail attached.

    THE CARD SPEC (``KryptonPay/docs/design/REQUEST_CARD_2026-08-24.md``,
    CEO-ratified after request ``0c295ec7`` rendered as a wall of prose: *"it
    could have been designed in a far more intuitive and cleaner way"*). The
    four questions a card must answer — what is this, where does it stand, what
    is owed, whose move is it — are computed HERE, from the same two functions
    ``desk_items`` uses, so the two surfaces cannot answer them differently.

    ``next_actor_resolved`` is here for a measured reason. The CEO page derived
    it in TypeScript, so when ``OPEN_REQUEST_ACTOR`` moved on this side the
    page went on listing eleven asks as decisions he owed and its own
    reconciliation banner reported the counts disagreeing by exactly that many
    — both suites green. One rule, published, read by the client.

    EVERY FIELD IS ADDITIVE AND PROSE-ONLY STAYS VALID FOREVER: a request filed
    as a subject renders through the fallback with ``structured: false``, which
    is what all 109 rows filed before the schema existed do. No migration.
    """
    from app.fund import deskcard

    if not isinstance(req, dict):
        return req
    dispatched = {str(x) for x in (dispatched_ids or ())}
    row = {**req, "dispatched": str(req.get("request_id")) in dispatched}
    card = deskcard.request_card(req)
    return {**row,
            "next_actor_resolved": open_request_actor(req.get("status")),
            "next_actor_basis": "request_lifecycle",
            "headline": card["headline"],
            "summary": card["summary"],
            "incident": card["incident"],
            "wanted": card["wanted"],
            "next_move": card["next_move"],
            "structured": card["structured"],
            "lifecycle": deskcard.lifecycle_rail(row)}


def status_index(open_recommendations: Any = (), requests: Any = ()) -> dict[str, Any]:
    """Every row on this desk keyed by canonical ref, for the cascade fold.

    Built ONCE over both populations rather than queried per member: a cascade
    block that issued a lookup per member would make the CEO's page cost
    O(members) round trips to render a reminder.
    """
    from app.fund.deskengine import rec_ref, req_ref

    out: dict[str, Any] = {}
    for rec in open_recommendations or []:
        if isinstance(rec, dict) and rec.get("run_id") is not None:
            out[rec_ref(rec["run_id"], rec.get("rec_id") or 0)] = \
                rec.get("status") or "open"
    for req in requests or []:
        if isinstance(req, dict) and req.get("request_id"):
            out[req_ref(req["request_id"])] = req.get("status") or "open"
    return out


def _annotated(rec: Any, status_by_ref: Optional[dict[str, Any]] = None) -> Any:
    """One recommendation with its resolved next actor and its card fields.

    Three routing fields rather than one, because a reader who disagrees with
    the routing needs to see WHY without opening the source: the actor, the
    basis it was decided on (explicit / lifecycle / kind / default), and the
    sentence. A surface that showed only the verdict would be asking to be
    trusted.

    THE CARD FIELDS (2026-08-24) ARE ADDITIVE AND NONE OF THEM CHANGES A COUNT.
    Every one is a rendering answer the CEO's page had to guess at or could not
    ask: what does this row SAY (``text_display`` — 2 live rows were showing a
    Python dict repr), is it a decision he still owes or one he already made
    (``execution_yours`` — 14 of the 34 rows on his list), who closed it
    (``adjudication`` — 52 rows closed by the chair, indistinguishable from his
    own 122), and what replaced it (``superseded_by``). ``text`` itself is
    NEVER rewritten: the stored value is what was stored, and a fold that
    edited the record to make the screen tidier would be repairing the wrong
    layer.
    """
    from app.fund import deskcard

    if not isinstance(rec, dict):
        return rec
    v = next_actor(rec)
    parts = deskcard.card_text(rec.get("text"))
    out = {**rec, "next_actor_resolved": v["actor"],
           "next_actor_basis": v["basis"], "next_actor_why": v["why"],
           # THE REPAIR FOR ROWS ALREADY IN THE DATABASE. Fixing the filing
           # door cannot reach a repr that was written last week; this can, and
           # it does it on the way out without touching what is stored.
           "text_display": parts["headline"],
           "text_basis": parts["basis"],
           "execution_yours": deskcard.execution_yours(v["actor"],
                                                       rec.get("status")),
           "desk_stage": deskcard.desk_stage(v["actor"], rec.get("status")),
           "adjudication": deskcard.adjudication(rec),
           "superseded_by": deskcard.superseded_by(rec.get("note")),
           # THE CASCADE MUST BE ON *THIS* PATH, and it was not on the first
           # cut — caught by looking at the rendered page rather than by any
           # test. The CEO's cards are built from `/fund/desk`'s
           # `open_recommendations`, which flow through here; `desk_items`
           # (the `/fund/desk/ceo` engine) had the fold and this did not, so
           # the cascade chip could never have appeared on the surface it was
           # written for. A control with no caller is this firm's named worst
           # failure, and it had reached a diff again.
           #
           # `status_by_ref` absent = the caller did not build the index, so
           # membership CANNOT be resolved and the block is omitted entirely.
           # Rendering it against an empty index would report every member as
           # `not_open`, which reads as "nothing is outstanding" — an absence
           # dressed as an answer.
           "cascade": (deskcard.cascade(rec, status_by_ref)
                       if status_by_ref is not None else None)}
    # Only when there is one: an absent detail must be absent, not "".
    detail = rec.get("detail") or parts["detail"]
    if detail:
        out["text_detail"] = detail
    return out


#: How many runs the desk payload carries. Named because it is TWO things: the
#: list the UI renders, and the window review-detection searches — so a reader
#: changing it should see both consequences in one place.
_RUNS_IN_PAYLOAD = 25


def view(store: Any, deskstore: Any = None,
         pending_orders: Any = None) -> dict[str, Any]:
    artifacts = _artifacts()
    reqs = _requests(store)
    runs, open_recs = [], []
    # None, not [] — an unreadable recorder must not fold into "no runs today".
    day, day_start, day_end = utc_day_bounds()
    day_runs: Optional[list[dict[str, Any]]] = None
    # None until proven otherwise, for the same reason: `_activity` must be
    # able to tell "the recorder could not be read" from "it was read and held
    # no matching run", and only the first makes review-detection unavailable.
    seen_runs: Optional[list[dict[str, Any]]] = None
    if deskstore is not None:
        try:
            runs = deskstore.runs(limit=_RUNS_IN_PAYLOAD)
            seen_runs = runs
            open_recs = deskstore.open_recommendations()
        except Exception as e:  # noqa: BLE001
            logger.info("desk runs unavailable: %s", e)
        # Separate try: the day window is a different query and a store that
        # predates `runs_between` (or a failure on just this one) must degrade
        # to "telemetry unreadable", never to a fabricated zero, and must not
        # take the rest of the payload down with it.
        try:
            day_runs = deskstore.runs_between(day_start, day_end)
        except Exception as e:  # noqa: BLE001
            logger.info("desk day window unavailable: %s", e)
    # AFTER the runs are loaded, because the third dispatch state is detected
    # by matching an open dispatch's identifiers against a recorded run. Passed
    # None when the recorder could not be read, which makes `review_detectable`
    # false rather than reporting WORKING as a confident answer.
    activity = _activity(store, runs=seen_runs, runs_limit=_RUNS_IN_PAYLOAD)
    # Whose move it is, resolved ONCE and attached to the row, so the count and
    # the list cannot disagree. The CEO's desk page had its own status-label
    # rule and the counter had another; on the same payload they read 11 and 6,
    # two numbers claiming the same thing eight pixels apart. A client that
    # re-implemented this predicate in TypeScript would be a second definition
    # free to drift from the first — the defect class this module is fixing.
    open_recs = open_recs or []
    open_reqs = [r for r in reqs if r["status"] == "open"]
    # ONCE, not once per row. The index is built from the RAW rows before
    # annotation and covers BOTH populations — a bundle may name a
    # recommendation or a desk request. (Hoisted after the first version put
    # the call inside the comprehension: 227 recommendations against 336 rows
    # is ~76k dict writes to render one reminder chip.)
    dispatched_ids = dispatched_request_ids(store)
    index = status_index(open_recs, reqs)
    open_recs = [_annotated(r, index) for r in open_recs]
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
        # ANNOTATED WITH WHOSE MOVE IT IS, for the same reason recommendations
        # are (2026-08-24). The CEO page derived this itself — an open request
        # was `awaiting_ceo` in TypeScript — so when `OPEN_REQUEST_ACTOR` moved
        # to the chair on this side, the page went on listing eleven asks as
        # decisions he owed and its own reconciliation banner reported the two
        # counts disagreeing by exactly that many. Caught by looking at the
        # rendered page, which is the only place a divergence of this shape has
        # ever been visible: both suites were green over it.
        #
        # One rule, published, read by the client. The client keeps its old
        # derivation as the fallback for a spine that predates the field.
        "requests": [_annotated_request(r, dispatched_ids) for r in reqs],
        # The flight recorder: every dispatch whole, and every recommendation
        # with the seat that made it - attribution is the point.
        "runs": runs,
        "open_recommendations": open_recs,
        "open_requests": len(open_reqs),
        # The COO triage counter (CEO's standing rule, >=50 items awaiting the
        # CEO). Rendered as a chip on the CEO desk and the CTO console; it
        # signals, never fires. Since 2026-08-22 it counts rows whose NEXT
        # ACTOR is the CEO rather than rows whose status label reads open —
        # `by_actor` in the payload carries everyone else's, so nothing that
        # left this number left the surface.
        "desk_load": desk_load(open_recs, pending_orders, open_reqs,
                               chair_backlog=_chair_backlog(store)),
        # Per-seat: running now, runs today, tokens today (CEO ask, 2026-08-21).
        # Rolled up here rather than on the client so the day count is exact
        # instead of folded from the capped 25-run list above.
        "seat_telemetry": seat_telemetry(day_runs, activity, day),
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


# ============================================================================
# THE DESK ENGINE v1 — docs/DESK_ENGINE_V1_2026-08-23.md
#
# Six CEO instructions in one sitting, of which the first two are the whole
# problem: *"my desk is more cluttered than before... Why is everything
# hitting my desk?"* and *"the agents dont get access to me directly, it makes
# me a bottleneck for a team running 24x7"*.
#
# Everything below is a READING over folds that already exist. Not one of these
# functions writes, and not one of them re-implements a predicate the desk
# already owns: `next_actor` decides whose move it is, here and on the CTO
# console and in the counter, because a client that re-implemented it in
# TypeScript once read 11 where the spine read 6.
# ============================================================================


# ------------------------------------------------------ routing at birth ----

#: Bumped when the required-field set or the undecided default changes.
ROUTING_RULES_VERSION = "routing v1 (2026-08-23)"

#: THE FOUR FIELDS EVERY NEW FILING MUST CARRY. Required means the KEY is
#: present, not that the value is a number: `due_date` and `money_at_stake` may
#: be null, because a recommendation that genuinely has no dated commitment and
#: no quantifiable stake is a real thing and forcing a figure would fabricate
#: one. What is refused is SILENCE — the seat must have considered each of the
#: four and said so, which is the Stan R39 standard enforced by schema instead
#: of by chair diligence.
#:
#: MEASURED BASIS — counted by this seat on the live corpus at 2026-08-23
#: (167 open recommendations), not carried from a memo:
#:
#:   * **28 of the 54 rows on the CEO's counter are there by DEFAULT** — the
#:     `next_actor` fold's rule 5, "nothing routed it elsewhere". A further 19
#:     arrive by the kind `awaits-ceo`, and only **7 by an explicit
#:     `next_actor`**. So better than half of his queue is a fall-through.
#:   * `money_at_stake` reached 150 of 167 rows and `due_date` reached **4** —
#:     the desk's TOP ranking key separates four rows out of a hundred and
#:     sixty-seven, which is why the payload publishes `ranked_on_nothing`
#:     rather than presenting arrival order as a ranking.
#:
#: (The spec quotes "54 of 91 CEO-routed rows arrived by default" from COO
#: triage #7. That was a different day and a different population; the figures
#: above are this seat's own count and are the ones the code rests on.)
ROUTING_REQUIRED_FIELDS = ("next_actor", "due_date", "reversibility",
                           "money_at_stake")

#: What a seat may WRITE as `next_actor` at filing. `unknown` is absent on
#: purpose: it is a reading the desk produces when a stored value cannot be
#: understood, never a claim a filer is allowed to make.
FILEABLE_NEXT_ACTORS = ("ceo", "chair", "seat", "nobody")

#: The word a seat uses when it does not know whose move it is.
UNDECIDED = "undecided"

#: THE DEFAULT FLIPS, AND THIS CONSTANT IS THE FLIP. Before the engine, a row
#: that said nothing fell through to the CEO (`next_actor`'s rule 5); 54 of the
#: 91 rows on his desk arrived that way. Undecided now routes to the CHAIR,
#: whose job is to work out whose move it is — which is what the chair was
#: doing by hand anyway, one sweep at a time.
#:
#: THIS IS NOT A LOOSENING OF A CONTROL, and the distinction matters because
#: the direction rule is strict here. Nothing about it changes who may approve
#: anything, and no work leaves the record: an undecided row is on the chair's
#: queue, counted in `by_actor`, and visible in the matrix's OPEN column. It
#: moves ATTENTION, not authority. The inference default in `next_actor` (rule
#: 5, still the CEO) is deliberately untouched, so a row filed before this
#: engine still fails toward "he must look".
UNDECIDED_ROUTES_TO = "chair"


#: WHETHER ROUTING v1 IS ENFORCED AT THE DOOR. Shipped **False**, and the
#: number that made it False is the reason it is a flag rather than a
#: judgement call. Run over the last day of live traffic by the D22 blind
#: review, routing v1's 422 would have REJECTED **16 of the 17 runs** recorded
#: that day, across eight seats — every seat but the chair-composed one.
#: Re-measured TWICE by this seat during the repair round, on the reviewer's
#: own unchanged instrument (`scratchpad/advd22/probeB5.py`): **16 of 20**,
#: then an hour later **16 of 21**, the same eight seats both times. The
#: denominator grows with the day; the numerator has not moved once.
#:
#: The schema half shipped without its companion half (the seat protocols and
#: the run-record format that teach seats to file the four fields), and a
#: contract enforced on one side only does not tighten anything: it stops the
#: record from being written at all, which is worse than a badly routed
#: record.
#:
#: So the enforcement ships dark and the chair flips it in a one-line
#: versioned change once the seat-protocol companion lands. Until then every
#: filing is still MEASURED — `routing_errors` runs regardless and the
#: endpoint returns the advisory — so the day the flag flips is a day whose
#: cost is already known rather than discovered.
#:
#: A single run may opt IN ahead of the flag by declaring `routing_version`
#: (see `record_agent_run`): a seat that has adopted the format gets the full
#: refusal it is asking for without waiting for the fleet.
DESK_ROUTING_ENFORCE = False

#: The `routing_version` a run must declare to be validated under routing v1
#: while `DESK_ROUTING_ENFORCE` is False.
ROUTING_ENFORCED_FROM_VERSION = 1


def validate_routing(rec: Any, index: Optional[int] = None,
                     enforce: Optional[bool] = None) -> list[str]:
    """Every reason this filing is REFUSED, or an empty list.

    The enforcement gate lives here rather than at the endpoint so that every
    caller asking "would this be rejected?" — the endpoint, a probe, a seat's
    own pre-flight — gets one answer, and it is the answer the door will
    actually give. `routing_errors` is the ungated measurement underneath;
    when enforcement is off this function returns [] and the errors are still
    computable, reported, and counted.
    """
    if enforce is None:
        enforce = DESK_ROUTING_ENFORCE
    if not enforce:
        return []
    return routing_errors(rec, index)


def routing_errors(rec: Any, index: Optional[int] = None) -> list[str]:
    """Every reason this filing is not routable, or an empty list.

    Returns ALL the errors rather than the first, because a seat re-posting a
    run to discover a second missing field one at a time is a seat spending
    four round trips on one form.

    ALWAYS COMPUTED, ENFORCED ONLY BEHIND THE FLAG. Measuring what a rule
    would refuse is free and is how the flip stops being a leap.
    """
    from app.fund.deskstore import REVERSIBILITY, _due_date, _money_at_stake

    where = "" if index is None else f"recommendations[{index}]: "
    if not isinstance(rec, dict):
        return [f"{where}not an object — a recommendation must be "
                f"{{text, kind, {', '.join(ROUTING_REQUIRED_FIELDS)}}}"]
    errors: list[str] = []
    missing = [f for f in ROUTING_REQUIRED_FIELDS if f not in rec]
    if missing:
        errors.append(
            f"{where}missing {missing}. All four are REQUIRED KEYS; "
            f"`due_date` and `money_at_stake` may be null when there honestly "
            f"is none, but the silence is refused — the desk ranks on these "
            f"two and ranked on nothing for three weeks because no seat wrote "
            f"them")

    na = rec.get("next_actor")
    if "next_actor" in rec:
        v = na.strip().lower() if isinstance(na, str) else None
        if v not in FILEABLE_NEXT_ACTORS and v != UNDECIDED:
            errors.append(
                f"{where}next_actor={na!r} is not one of "
                f"{FILEABLE_NEXT_ACTORS} or {UNDECIDED!r}. Say "
                f"{UNDECIDED!r} if you do not know — it routes to the "
                f"{UNDECIDED_ROUTES_TO}, never to the CEO")

    if "reversibility" in rec:
        rv = rec.get("reversibility")
        if not isinstance(rv, str) or rv.strip().lower() not in REVERSIBILITY:
            errors.append(
                f"{where}reversibility={rv!r} must be one of {REVERSIBILITY}. "
                f"The seat knows whether its own recommendation can be taken "
                f"back; the desk's kind-table inference does not")

    if "due_date" in rec and rec.get("due_date") is not None:
        if _due_date(rec.get("due_date")) is None:
            errors.append(
                f"{where}due_date={rec.get('due_date')!r} must be YYYY-MM-DD "
                f"or null. Refused rather than nulled: a malformed date used "
                f"to sort lexicographically against real ones and put the row "
                f"in the wrong place silently")

    if "money_at_stake" in rec and rec.get("money_at_stake") is not None:
        raw = rec.get("money_at_stake")
        # STRICTER AT THE DOOR THAN IN STORAGE, on purpose. `_money_at_stake`
        # coerces a numeric STRING because it also reads rows that were
        # already written that way; a NEW filing has no such excuse, and JSON
        # has a number type. A quoted figure is the shape a seat produces when
        # it lifted the number out of its own prose, which is the one thing
        # this field exists to prevent.
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) \
                or _money_at_stake(rec) is None:
            errors.append(
                f"{where}money_at_stake={raw!r} must be a JSON number or "
                f"null — never a string, never NaN, never a boolean. A "
                f"quoted figure is what a number lifted out of prose looks "
                f"like, and this field exists so the desk never ranks on one")
    return errors


def route_at_birth(rec: dict[str, Any]) -> dict[str, Any]:
    """The filed row with `undecided` resolved and the resolution recorded.

    ``routed_from`` is kept beside the resolved actor so a reader can tell a
    seat that SAID "chair" from a seat that said "I do not know" — and so the
    payload can report how much of the chair's queue is genuine delegation
    versus how much is the default doing its job. Overwriting the seat's own
    word would delete the one measurement that says whether the flip is
    working.
    """
    if not isinstance(rec, dict):
        return rec
    na = rec.get("next_actor")
    v = na.strip().lower() if isinstance(na, str) else None
    if v == UNDECIDED:
        return {**rec, "next_actor": UNDECIDED_ROUTES_TO,
                "routed_from": UNDECIDED,
                "routing_rules_version": ROUTING_RULES_VERSION}
    if v in FILEABLE_NEXT_ACTORS:
        return {**rec, "next_actor": v,
                "routing_rules_version": ROUTING_RULES_VERSION}
    return rec


# ------------------------------------------------------- the matrix view ----
#
# CEO instruction, 2026-08-23, verbatim: *"like put a matrix view that shows
# intra-team ticket count -> I click it expands the list; then different
# categories for whats closed, whats ticking, whats blocking, whats open"* —
# after the previous desk page earned *"this feels like an infine scroll"*.
#
# ONE FOLD, ONE PREDICATE. The count in a cell and the list behind it are the
# same list, computed once here, so a cell can never say 6 and open onto 11.
# That is not hypothetical: it is exactly what the CEO desk and the counter did
# to each other before `next_actor` moved into the spine.

#: The four columns, in the CEO's own order.
DESK_CATEGORIES = ("open", "ticking", "blocking", "closed")

#: What each column MEANS, published in the payload so the UI renders the
#: definition beside the number instead of a tooltip somebody wrote once.
CATEGORY_DEFINITIONS = {
    "open": "undecided — somebody still has to decide this",
    "ticking": "decided and in motion — a clock is running on execution",
    "blocking": "cannot move until something else does — a live supersession "
                "edge, an approved request nobody has dispatched, or a row "
                "whose next actor cannot be determined",
    # THE ONE COLUMN THAT UNDERSTATES ITSELF, and it says so rather than
    # letting a reader take it for the firm's closure rate. The desk's
    # recommendation read (`DeskStore.open_recommendations`) returns only
    # open / accepted / staged, so a recommendation that has been rejected,
    # done or noted is not in this fold at all. Requests and in-tray items ARE
    # complete here. Fixing it means a second query and a decision about how
    # far back "closed" should reach, which is a scope question for a human,
    # not a default for a builder.
    "closed": ("terminal — decided, served, struck or withdrawn. INCOMPLETE "
               "for recommendations: the desk's read returns only undecided "
               "and in-flight rows, so closed RECOMMENDATIONS are not counted "
               "here. Requests and in-tray items are complete"),
}

#: Terminal states per source. Mirrored here rather than imported from the
#: database module for the reason `TERMINAL_STATUSES` already gives, and pinned
#: equal to it by a test.
_TERMINAL_REQUEST_STATUSES = ("resolved", "declined")


def classify_item(item: dict[str, Any]) -> dict[str, str]:
    """Which of the four columns this desk item belongs in, and why.

    PRECEDENCE, and it is load-bearing:

      1. TERMINAL wins over everything. A row that is done is not blocked, is
         not ticking, and does not need a decision — and a superseded row that
         was already rejected must not reappear under BLOCKING.
      2. A live SUPERSESSION edge blocks. This is the R37 case: the row is
         formally still `staged`, and treating it as "in motion" is exactly
         the reading that would let it be clicked after the event that made it
         wrong.
      3. UNKNOWN next actor blocks. Nobody can act on a row whose owner cannot
         be read, and parking it under OPEN would tell the CEO it is his.
      4. Otherwise the lifecycle decides.

    Every item lands in exactly one column. A partition, not four filters —
    overlapping tallies is how "26 elsewhere" ended up beside "6 with the
    chair", both true and one label apart.
    """
    source = item.get("source")
    status = (item.get("status") or "").strip().lower() or "open"

    if source == "request":
        if status in _TERMINAL_REQUEST_STATUSES:
            return {"category": "closed",
                    "why": f"request status {status!r} is terminal"}
    elif source == "intray":
        if status == "struck":
            return {"category": "closed",
                    "why": "struck by the chair, with its reason, and "
                           "returned to the sending seat"}
    elif status in TERMINAL_STATUSES:
        return {"category": "closed",
                "why": f"status {status!r} is terminal — nothing follows it"}

    if item.get("supersession"):
        mode = (item["supersession"] or {}).get("mode")
        return {"category": "blocking",
                "why": f"carries a live {mode} edge — it cannot be approved "
                       f"until the edge is confirmed or retracted"}

    if item.get("next_actor_resolved") == "unknown":
        return {"category": "blocking",
                "why": "whose move it is could not be determined, so nobody "
                       "can act on it — counted, never dropped"}

    if source == "request":
        if status == "approved":
            if item.get("dispatched"):
                return {"category": "ticking",
                        "why": "approved and dispatched — a seat is on it"}
            return {"category": "blocking",
                    "why": "approved by the CEO and never dispatched — "
                           "blocked on the chair firing it"}
        return {"category": "open", "why": "filed and undecided"}

    if source == "intray":
        if status == "blessed":
            return {"category": "ticking",
                    "why": "blessed into the receiving seat's next brief"}
        return {"category": "open",
                "why": "posted, awaiting the chair's blessing at the "
                       "receiving seat's next dispatch"}

    if status in ("accepted", "staged"):
        return {"category": "ticking",
                "why": f"status {status!r} — the CEO decided; execution is "
                       f"running"}
    if status == "open":
        return {"category": "open", "why": "filed and undecided"}
    return {"category": "blocking",
            "why": f"status {status!r} is outside the known vocabulary, so "
                   f"whether anything is owed cannot be read"}


#: How many rows a single matrix cell carries in the payload. A cap, not a
#: count: `total` beside it is the true figure and `truncated` says which is
#: which. Named because the last cap this desk shipped (25 runs) was read as a
#: count and truncated the firm's first spend meter.
MATRIX_CELL_LIMIT = 25


def desk_matrix(items: Iterable[dict[str, Any]],
                cell_limit: int = MATRIX_CELL_LIMIT) -> dict[str, Any]:
    """Seats x {open, ticking, blocking, closed}, counts with their rows attached.

    ``items`` are normalised desk items (see ``desk_items``): each carries a
    ``seat``, a ``source`` and enough state for ``classify_item``. A row with
    no readable seat lands under ``unattributed`` rather than being dropped —
    the matrix must total to the desk.
    """
    cells: dict[str, dict[str, dict[str, Any]]] = {}
    totals = {c: 0 for c in DESK_CATEGORIES}
    n = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        n += 1
        verdict = classify_item(item)
        cat = verdict["category"]
        seat = (item.get("seat") or "").strip().lower() or "unattributed"
        row = {**item, "category": cat, "category_why": verdict["why"]}
        slot = cells.setdefault(seat, {c: {"count": 0, "items": []}
                                       for c in DESK_CATEGORIES})
        slot[cat]["count"] += 1
        if len(slot[cat]["items"]) < cell_limit:
            slot[cat]["items"].append(row)
        totals[cat] += 1
    for seat_cells in cells.values():
        for cat, cell in seat_cells.items():
            cell["truncated"] = cell["count"] > len(cell["items"])
            cell["shown"] = len(cell["items"])
    # Seats ordered by how much is OPEN then how much there is at all: the
    # thing the CEO clicks first should be the thing with the most undecided
    # work, not whoever sorts first alphabetically.
    order = sorted(cells, key=lambda s: (-cells[s]["open"]["count"],
                                         -sum(c["count"] for c in cells[s].values()),
                                         s))
    return {
        "categories": list(DESK_CATEGORIES),
        "definitions": dict(CATEGORY_DEFINITIONS),
        "seats": order,
        "cells": cells,
        "totals": totals,
        "items_classified": n,
        "cell_limit": cell_limit,
        "note": (f"{n} desk item(s) across {len(order)} seat(s); every item is "
                 f"in exactly one column, so the four totals sum to the desk"),
    }


def desk_items(open_recommendations: Iterable[dict[str, Any]],
               requests: Iterable[dict[str, Any]],
               intray_items: Iterable[dict[str, Any]] = (),
               supersessions: Optional[dict[str, dict[str, Any]]] = None,
               dispatched_request_ids: Iterable[str] = (),
               pending_orders: Iterable[dict[str, Any]] = (),
               ) -> list[dict[str, Any]]:
    """One flat, uniform list of desk items from the four sources that have them.

    THE UNITS ARE THE SAME IN EVERY CELL, and that is the reason this function
    exists rather than four parallel matrices. "Intra-team ticket count" is
    one number or it is a chart nobody can read: a recommendation, a desk
    request, an in-tray posting and a pending order are all TICKETS, and mixing
    seat-activity states in with them would put two different things behind one
    figure.

    PENDING ORDERS ARE IN THIS LIST AND WERE NOT IN THE FIRST CUT, and the
    reason is worth stating because it was caught by LOOKING at the rendered
    page rather than by any test. ``desk_load`` counts pending orders; this
    fold did not — so the CEO's page carried a fourth number claiming to be the
    same thing as the other three. This desk has now shipped
    one-quantity-computed-twice twice, and the fix is not another warning
    banner, it is the same population.

    Attribution, stated because it is a choice: a recommendation belongs to the
    seat that FILED it (which is also the seat that must retire it when it is
    superseded — the standing PM instruction); a request belongs to the seat it
    SERVES (whoever must do the work); an in-tray item belongs to the seat it
    was posted TO; a pending order belongs to nobody on the bench and is
    attributed to ``execution`` — a machine-produced row on a human's queue.
    """
    from app.fund import deskcard
    from app.fund.deskengine import rec_ref, req_ref

    sup = supersessions or {}
    dispatched = {str(x) for x in dispatched_request_ids}
    out: list[dict[str, Any]] = []

    # WHAT EVERY ROW ON THIS DESK CURRENTLY IS, keyed by canonical ref, so a
    # decided bundle can report its members' real states instead of the word
    # "pending". `status_index` is the ONE definition — `view()` builds the
    # same index for the `/fund/desk` path, and two copies of this loop would
    # be two answers to "is that member still open" within one payload.
    status_by_ref = status_index(open_recommendations, requests)

    for rec in open_recommendations or []:
        if not isinstance(rec, dict):
            continue
        ref = rec_ref(rec.get("run_id") or "", rec.get("rec_id") or 0) \
            if rec.get("run_id") is not None else None
        v = next_actor(rec)
        parts = deskcard.card_text(rec.get("text"))
        out.append({
            "source": "recommendation", "ref": ref,
            "seat": rec.get("seat"),
            "run_id": rec.get("run_id"), "rec_id": rec.get("rec_id"),
            # UNCHANGED, verbatim from the record. `title_display` beside it is
            # the repaired rendering; keeping both means a reader can always
            # see what was actually stored.
            "title": rec.get("text"),
            "title_display": parts["headline"],
            "detail": rec.get("detail") or parts["detail"],
            "kind": rec.get("kind"),
            "status": rec.get("status") or "open",
            "due_date": rec.get("due_date"),
            "money_at_stake": rec.get("money_at_stake"),
            "reversibility": rec.get("reversibility"),
            "next_actor_resolved": v["actor"],
            "next_actor_basis": v["basis"],
            # THE THREE FIELDS THE `on_fire` PROJECTION WAS MISSING. A row at
            # `accepted` whose next move is still the CEO's own was
            # indistinguishable on screen from one nobody had decided; his R39
            # accept (seq 1281, 2026-08-24) landed and looked exactly like a
            # dead click. `status` was already here; who decided it and when
            # were not, so no renderer could say "you did this, at 09:12".
            "decided_by": rec.get("decided_by"),
            "decided_at": rec.get("decided_at"),
            "execution_yours": deskcard.execution_yours(v["actor"],
                                                        rec.get("status")),
            "adjudication": deskcard.adjudication(rec),
            # A supersession the TABLE does not know about because it was
            # written in English. Only when the note names its superseder —
            # see `deskcard.superseded_by`, where 6 of 10 word-level hits in
            # the live corpus are one boilerplate sentence about something
            # else entirely.
            "superseded_by": deskcard.superseded_by(rec.get("note")),
            "cascade": deskcard.cascade(rec, status_by_ref),
            "supersession": sup.get(ref) if ref else None,
        })

    for req in requests or []:
        if not isinstance(req, dict):
            continue
        rid = req.get("request_id")
        ref = req_ref(rid) if rid else None
        row = {**req, "dispatched": str(rid) in dispatched}
        card = deskcard.request_card(req)
        out.append({
            "source": "request", "ref": ref,
            "seat": req.get("seat") or req.get("serves"),
            "request_id": rid,
            "title": req.get("task") or req.get("subject"),
            "title_display": card["headline"],
            "summary": card["summary"],
            "detail": card["incident"],
            "wanted": card["wanted"],
            "next_move": card["next_move"],
            "structured": card["structured"],
            "lifecycle": deskcard.lifecycle_rail(row),
            "kind": req.get("kind"),
            "status": req.get("status") or "open",
            "due_date": None,
            "money_at_stake": None,
            "reversibility": None,
            "next_actor_resolved": open_request_actor(req.get("status")),
            "next_actor_basis": "request_lifecycle",
            "at": req.get("at"),
            "dispatched": str(rid) in dispatched,
            "decided_by": req.get("approved_by") or req.get("declined_by"),
            "decided_at": req.get("approved_at") or req.get("declined_at"),
            "adjudication": deskcard.adjudication(
                {"decided_by": req.get("approved_by")
                 or req.get("declined_by"),
                 "decided_at": req.get("approved_at")
                 or req.get("declined_at"),
                 "note": req.get("resolution")
                 or req.get("decline_reason")}),
            "superseded_by": deskcard.superseded_by(req.get("resolution")),
            "cascade": None,
            "supersession": sup.get(ref) if ref else None,
        })

    for item in intray_items or []:
        if not isinstance(item, dict):
            continue
        out.append({
            "source": "intray", "ref": None,
            "seat": item.get("to_seat"),
            "item_id": item.get("item_id"),
            "title": item.get("task"),
            "kind": "intray",
            "status": item.get("status") or "posted",
            "due_date": None, "money_at_stake": None, "reversibility": None,
            # SEAT-TO-SEAT TRAFFIC NEVER REACHES THE CEO'S DESK (the spec says
            # so in as many words). It is in the matrix because the matrix is
            # the FIRM's ticket board, and it is `seat` here so no fold can
            # accidentally count it onto his figure.
            "next_actor_resolved": "seat",
            "next_actor_basis": "intray",
            "at": item.get("posted_at"),
            "from_seat": item.get("from_seat"),
            "supersession": None,
        })

    for o in pending_orders or []:
        if not isinstance(o, dict):
            continue
        oid = o.get("order_id") or o.get("id")
        impact = o.get("impact_preview") if isinstance(o.get("impact_preview"),
                                                       dict) else {}
        notional = (impact or {}).get("notional_usd")
        out.append({
            "source": "order", "ref": None,
            # Not a bench seat. An order is machine-produced and lands on a
            # human's queue; filing it under whichever strategy proposed it
            # would put execution rows in a seat's ticket count.
            "seat": "execution",
            "order_id": oid,
            "title": (f"{str(o.get('side') or '').upper()} {o.get('qty')} "
                      f"{o.get('symbol')}").strip(),
            "kind": "order",
            "status": "open",
            "due_date": None,
            "money_at_stake": (float(notional)
                               if isinstance(notional, (int, float))
                               and not isinstance(notional, bool) else None),
            # An order that cannot be taken back once it fills. Stated rather
            # than inferred from a kind table — this one is not a judgement.
            "reversibility": "irreversible",
            # AN ORDER AWAITING APPROVAL IS THE CEO'S CLICK BY CONSTRUCTION;
            # anything the auto-approval envelope takes never appears here at
            # all. Same reasoning `desk_load` already rests on.
            "next_actor_resolved": "ceo",
            "next_actor_basis": "order_lifecycle",
            "at": o.get("created_at") or o.get("at"),
            "supersession": None,
        })
    return out


# --------------------------------------------------- the CEO's own surface --

def _rank_key(item: dict[str, Any]) -> tuple:
    """Due date first, then money — with ABSENT LAST on both, deliberately.

    A row with no date must not sort as though its date were the epoch, and a
    row with no dollar figure must not sort as though it were worth zero. Both
    are absences and both rank behind every row that stated something; the
    payload says how many rows are ranked on nothing so the reader knows how
    much of the order is real.
    """
    due = item.get("due_date")
    has_due = isinstance(due, str) and bool(due.strip())
    money = item.get("money_at_stake")
    has_money = isinstance(money, (int, float)) and not isinstance(money, bool)
    # The two ABSENCE FLAGS lead their own key rather than trailing it. With
    # the money magnitude first, a row stating a NEGATIVE stake would sort
    # behind a row stating nothing — an absence beating a number, which is the
    # error this whole ordering exists to avoid, hiding in a sign.
    return (0 if has_due else 1,
            due if has_due else "",
            0 if has_money else 1,
            -float(money) if has_money else 0.0,
            str(item.get("at") or ""))


def greeting(*, ceo_items: list[dict[str, Any]],
             on_fire: list[dict[str, Any]],
             since: Optional[str] = None,
             changed: Optional[dict[str, Any]] = None,
             hygiene: Optional[dict[str, Any]] = None,
             now: Optional[str] = None) -> dict[str, Any]:
    """The executive greeting: what changed, what needs you, what is on fire.

    GENERATED FROM THE SAME FOLDS THE PAGE RENDERS, never hand-written and
    never a second count. Three sentences, each backed by a number that
    appears elsewhere in the payload — if the greeting and the list ever
    disagree, one of them is reading a different fold and that is a defect,
    not a rounding.

    ``since`` ABSENT IS SAID OUT LOUD. "Nothing has changed since your last
    visit" and "we do not know when your last visit was" are different
    sentences and only one of them is a fact. The client supplies its own last
    visit; the spine does not stamp one, because a GET that writes is a GET
    that lies about being safe.
    """
    n = len(ceo_items)
    fire = len(on_fire)
    changed = changed or {}
    if since:
        bits = [f"{v} {k.replace('_', ' ')}" for k, v in sorted(changed.items())
                if isinstance(v, int) and v]
        changed_line = (f"Since {since}: " + ", ".join(bits) + "."
                        if bits else
                        f"Nothing has been recorded since {since}.")
    else:
        changed_line = ("No previous visit was supplied, so nothing is marked "
                        "new — this is everything currently open, not a diff.")
    needs_line = (
        f"{n} item(s) need you." if n else
        "Nothing is waiting on you right now.")
    if fire:
        fire_line = (f"{fire} on fire: " + "; ".join(
            f"{(i.get('title') or '')[:90]}"
            + (f" (due {i['due_date']})" if i.get("due_date") else "")
            for i in on_fire[:3]) + ".")
    else:
        fire_line = ("Nothing dated is overdue and no loss alarm is "
                     "standing.")
    hyg = ""
    if hygiene:
        c = hygiene.get("counts") or {}
        if c.get("proposals"):
            hyg = (f" Auto-hygiene has {c['proposals']} bookkeeping close(s) "
                   f"waiting for one click.")
        elif c.get("unlinkable"):
            hyg = (f" Auto-hygiene could not read {c['unlinkable']} request(s) "
                   f"— they carry no evidence edge, which is not the same as "
                   f"being open.")
    return {
        "at": now,
        "since": since,
        "changed": changed_line,
        "needs_you": needs_line,
        "on_fire": fire_line,
        "hygiene": hyg.strip() or None,
        "text": " ".join(x for x in [changed_line, needs_line, fire_line,
                                     hyg.strip()] if x),
    }


def _overdue(item: dict[str, Any], today: str) -> bool:
    due = item.get("due_date")
    return isinstance(due, str) and bool(due.strip()) and due.strip() <= today


def ceo_desk(*, open_recommendations: Iterable[dict[str, Any]],
             requests: Iterable[dict[str, Any]],
             intray_items: Iterable[dict[str, Any]] = (),
             supersessions: Optional[dict[str, dict[str, Any]]] = None,
             dispatched_request_ids: Iterable[str] = (),
             pending_orders: Iterable[dict[str, Any]] = (),
             briefings_shelf: Optional[dict[str, Any]] = None,
             hygiene: Optional[dict[str, Any]] = None,
             halted: Optional[bool] = None,
             since: Optional[str] = None,
             changed: Optional[dict[str, Any]] = None,
             now: Optional[str] = None,
             decisions_limit: int = 50) -> dict[str, Any]:
    """The CEO's decision surface: his rows, ranked, plus the shelf and the matrix.

    THE TARGET IS SINGLE DIGITS and the falsifier is written into the spec: if
    this page still exceeds ~15 rows at steady state after a week, the engine
    failed its one job. So the payload reports ``decisions.total`` beside
    what it shows — a page that quietly paginated its way to looking calm
    would defeat its own measurement.

    ``decisions.total`` IS THE SAME NUMBER ``desk_load.total`` REPORTS, and a
    test pins the two equal over the live corpus. That equality is not a
    coincidence to be maintained by care: both count rows whose next actor is
    the CEO or cannot be read, over the same four sources, and the only
    documented difference is rows this fold removes because the SERVER WOULD
    REFUSE the click (a live supersession edge). Anything else is a defect.

    The first cut of this function got that wrong and the SCREENSHOT is what
    caught it: it filtered to categories `open` and `blocking`, which silently
    dropped every `accepted`/`staged` row whose EXECUTION is still the CEO's
    own act — the COO's standing objection of 2026-08-21, and the exact case
    the explicit `next_actor` field exists for.

    MEASURED, on the live corpus of 167 open recommendations and 92 requests
    (2026-08-23, and re-counted at bundling time rather than inferred from two
    figures taken at different moments): the old filter dropped **exactly one
    row** — `run-pm-0908` rec 1, the 2026-09-08 exit package, staged, $1,847.36
    at stake, the largest single figure on the desk. One row is the whole
    defect and it is the one that mattered most, which is the argument for the
    invariant rather than for the count.

    NOTHING RENDERS UNBOUNDED. Every list here carries `shown`, `total` and
    `truncated`; the matrix caps each cell; the shelf is capped by its own
    fold. The previous desk earned *"this feels like an infine scroll"* and the
    fix belongs on the server, where the count and the list are the same fold.
    """
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc).isoformat()
    today = now[:10]

    items = desk_items(open_recommendations, requests, intray_items,
                       supersessions=supersessions,
                       dispatched_request_ids=dispatched_request_ids,
                       pending_orders=pending_orders)
    matrix = desk_matrix(items)

    # HIS rows: next actor is the CEO (or could not be read — an unreadable
    # owner counts toward him, which is this desk's oldest rule), the row is
    # not terminal, and it is not blocked behind a supersession edge. A
    # superseded row is not a decision he can take: the server refuses the
    # approval, so putting it on the decision list would be offering a button
    # that fails.
    #
    # NOTE WHAT IS *NOT* IN THAT LIST: a category filter. A `ticking` row whose
    # next actor is the CEO is a row he must still act on — see the docstring.
    mine = [i for i in items
            if i.get("next_actor_resolved") in ("ceo", "unknown")
            and classify_item(i)["category"] != "closed"
            and not i.get("supersession")]
    mine.sort(key=_rank_key)

    on_fire = [i for i in mine if _overdue(i, today)]
    ranked_on_nothing = sum(
        1 for i in mine
        if not (isinstance(i.get("due_date"), str) and i["due_date"].strip())
        and not isinstance(i.get("money_at_stake"), (int, float)))

    blocked = [i for i in items if i.get("supersession")]
    from app.fund.deskengine import SHELVED_MODES
    kill_shelf = [i for i in blocked
                  if ((i.get("supersession") or {}).get("mode")
                      in SHELVED_MODES)]

    return {
        "at": now,
        "rules_version": ROUTING_RULES_VERSION,
        "greeting": greeting(ceo_items=mine, on_fire=on_fire, since=since,
                             changed=changed, hygiene=hygiene, now=now),
        "decisions": {
            "shown": len(mine[:decisions_limit]),
            "total": len(mine),
            "truncated": len(mine) > decisions_limit,
            "ranked_by": "due_date, then money_at_stake — absent last on both",
            "ranked_on_nothing": ranked_on_nothing,
            "items": mine[:decisions_limit],
            "note": (f"{len(mine)} row(s) await the CEO"
                     + (f"; {ranked_on_nothing} of them state neither a date "
                        "nor a dollar figure, so their order is arrival "
                        "order and not a ranking"
                        if ranked_on_nothing else "")
                     + "."),
        },
        "on_fire": {
            "shown": len(on_fire), "total": len(on_fire),
            "items": on_fire,
            # `halted` is passed in from the risk monitor and may be None. None
            # is UNKNOWN and says so: a desk that renders "not halted" because
            # it could not reach the monitor is the absence-as-zero error on
            # the one control that stops losses.
            "risk_halted": halted,
            "definition": ("dated and due today or earlier, or the risk "
                           "monitor is halted. Nothing else goes here"),
        },
        "briefings": briefings_shelf,
        "matrix": matrix,
        "hygiene": hygiene,
        # EVERY row carrying a live edge, UNCAPPED and listed separately from
        # the matrix. The matrix caps each cell at 25, so a client that read
        # its blocked rows from there would silently miss the 26th — and the
        # one thing a client must never miss is a row whose approve button has
        # to be disabled. Uncapped is safe here because an edge is a chair
        # action, not a bench output; `total` is published so the day that
        # stops being true is visible.
        "blocked": {
            "shown": len(blocked), "total": len(blocked), "items": blocked,
            "note": ("rows carrying a live supersession edge — unapprovable "
                     "at the server, and listed whole so no surface can offer "
                     "a button the spine would refuse"),
        },
        "kill_shelf": {
            "shown": len(kill_shelf), "total": len(kill_shelf),
            "items": kill_shelf,
            "note": ("rows superseded or killed — off the desk, kept whole "
                     "with their lineage"),
        },
        "elsewhere": {
            # COUNTS ONLY, on purpose. Everything not his is summarised so it
            # cannot become a scroll; the matrix is where it is read.
            "by_actor": {a: sum(1 for i in items
                                if i.get("next_actor_resolved") == a)
                         for a in NEXT_ACTORS},
            "by_source": {s: sum(1 for i in items if i.get("source") == s)
                          for s in ("recommendation", "request", "intray")},
        },
    }


# ----------------------------------------------------- the briefings shelf --

#: WHOSE MEMOS REACH THE CEO DIRECTLY, and only these three. The spec names
#: them: Donna's archives, the COO's triages, Grace's ledgers. Deliberately
#: absent: `docs/reviews` (adversarial verdicts already render in `artifacts`,
#: paired with what they attacked, which is the more useful shape) and
#: `docs/pm` (Stan's memos reach the desk as recommendations with money and
#: dates on them — a second copy on the shelf would be one artifact in two
#: places disagreeing about its own status).
BRIEFING_SOURCES = (
    {"seat": "secretary", "who": "Donna", "label": "Daily archive",
     "dir": "archives"},
    {"seat": "coo", "who": "Vishesh", "label": "Triage", "dir": "coo"},
    {"seat": "cfo", "who": "Grace", "label": "Ledger", "dir": "cfo"},
)

#: How many memos the shelf carries. Newest first, so the cap drops the oldest
#: — and `total` beside it says how many there are. Bounded on the server for
#: the same reason every other list here is.
SHELF_LIMIT = 12

_DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def briefings(review_state: Optional[dict[str, dict[str, Any]]] = None,
              limit: int = SHELF_LIMIT) -> dict[str, Any]:
    """Seat memos, newest first, each with its chair-verification badge.

    AUTO-PUBLISHED AT FILING. A memo appears here the moment the seat files it,
    stamped ``chair-unverified`` — the chair is CC, never relay (CEO
    instruction 3: *"COO reaches to me directly with you in CC"*). The badge
    flips when the chair records a verification; a discrepancy found after
    publication becomes a visible CORRECTION chip and never a silent edit,
    because the findings-doc rule applies to the shelf too.

    ``review_state`` is what the chair has recorded (see
    ``deskengine.BriefingLedger.state``). Passing ``None`` means the ledger
    could not be read, and every badge then reads ``unknown`` rather than
    ``unverified`` — an unreadable ledger is not an unverified memo, and
    collapsing the two would put a false badge on work the chair HAS checked.
    """
    ledger_readable = review_state is not None
    review_state = review_state or {}
    memos: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for src in BRIEFING_SOURCES:
        d = DOCS / src["dir"]
        if not d.exists():
            continue
        try:
            paths = sorted(d.glob("*.md"))
        except OSError as e:  # noqa: BLE001
            logger.info("briefings: %s unreadable: %s", d, e)
            unreadable.append(str(d).replace("\\", "/"))
            continue
        for p in paths:
            path = str(p).replace("\\", "/")
            m = _DATE_IN_NAME_RE.search(p.name)
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError as e:  # noqa: BLE001
                logger.info("briefings: %s unreadable: %s", p, e)
                unreadable.append(path)
                continue
            state = review_state.get(path) or {}
            memos.append({
                "path": path,
                "seat": src["seat"], "who": src["who"], "label": src["label"],
                "title": _title_of(head),
                "date": m.group(1) if m else None,
                "badge": ("unknown" if not ledger_readable
                          else "chair-verified" if state.get("verified_by")
                          else "chair-unverified"),
                "verified_by": state.get("verified_by"),
                "verified_at": state.get("verified_at"),
                "corrections": state.get("corrections") or [],
            })
    # Newest first by the date IN THE FILENAME, not by mtime: a PDF re-render
    # or a `git checkout` moves mtime and would silently reorder the shelf.
    # ONE sort, and the leading flag is what keeps undated memos LAST under a
    # descending order — an undated memo is not new.
    memos.sort(key=lambda x: (1 if x["date"] else 0, x["date"] or "",
                              x["path"]), reverse=True)
    total = len(memos)
    unverified = sum(1 for m in memos if m["badge"] == "chair-unverified")
    corrected = sum(1 for m in memos if m["corrections"])
    return {
        "memos": memos[:limit],
        "shown": len(memos[:limit]),
        "total": total,
        "truncated": total > limit,
        "ledger_readable": ledger_readable,
        "unreadable": sorted(set(unreadable)),
        "sources": [dict(s) for s in BRIEFING_SOURCES],
        "note": (
            f"{total} seat memo(s) on the shelf"
            + (f", {unverified} still chair-unverified" if unverified else "")
            + (f", {corrected} carrying a correction" if corrected else "")
            + ("" if ledger_readable else
               " — the verification ledger could not be read, so every badge "
               "reads UNKNOWN rather than unverified")
            + (f"; {len(set(unreadable))} file(s) could not be read"
               if unreadable else "")
            + "."),
    }
