"""THE AGENT->CTO->AGENT HOP — staging, and the ``## TICKETS`` parser.

Design: ``docs/design/TICKET_HIGHWAY_V1_2026-08-24.md`` §1.3, slice 4. The
CEO's commission, verbatim: *"how could we flow information seamlessly that
land into next execution pass. Agent->CTO->Agent."*

**THE BOUNDARY IS THE WHOLE POINT AND IT IS STRUCTURAL, NOT POLITE.** A seat's
output is PARSED into rows in a Postgres table. Nothing here appends to the
event log — this module does not import ``app.fund.events``, holds no reference
to a store, and ``tests/test_ticket_staging.py`` asserts both by AST rather
than by this sentence. Seats gain no pen. The chair's session appends every
real ``TICKET_TRANSITIONED``, at the resolve door, through the same guards a
hand-typed transition takes.

The split is ``deskstore``'s, reused rather than reinvented: *"the table holds
current state, the log holds who decided what and when, and they must agree"*
(deskstore.py:22-24). A staged row is working state. A resolved one is a
decision, and a decision goes on the log.

WHY A PARSER AND NOT A JSON FIELD, because the alternative was tried. Failure
#6 in the design's own table: **structured filing is 0 of 116** — the desk's
structured-request schema has existed for days and has never been used once
(builder D42, measured on the live record). Producers first: the format below
is what a seat can type at the end of a report without leaving prose, and every
line it cannot read is REPORTED as unparsed rather than dropped, so adoption is
a number instead of a hope.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_ticket_staged (
    staged_id         TEXT PRIMARY KEY,
    run_id            TEXT,
    seat              TEXT,
    kind              TEXT NOT NULL,
    ticket_id         TEXT,
    to_state          TEXT,
    fields            JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw               TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'staged',
    resolved_by       TEXT,
    resolved_at       TIMESTAMPTZ,
    resolution_reason TEXT,
    event_ref         TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fund_ticket_staged_status_idx
    ON fund_ticket_staged (status, created_at DESC);
CREATE INDEX IF NOT EXISTS fund_ticket_staged_run_idx
    ON fund_ticket_staged (run_id);
"""

#: What a staged row may be. Two verbs, deliberately, matching §1.3's two
#: sentences: *proposed transitions* and *proposed new tickets*. A third verb
#: is a decision somebody makes in writing, not a string that appears one day.
STAGED_KINDS = ("transition", "open")

#: THE THREE FATES OF A STAGED ROW, and ``struck`` is not ``deleted``.
#:
#: A proposal the chair disagrees with is RECORDED struck, with a reason. This
#: is the BINDS-review discipline given a table: *"the chair strikes what it
#: disagrees with"* — and a strike that leaves no row is indistinguishable from
#: a proposal nobody read, which is the failure the whole highway exists to
#: end. Nothing here ever DELETEs.
STAGED_STATUSES = ("staged", "accepted", "struck")

#: The heading a seat writes. Matched case-insensitively with any number of
#: leading hashes, because a producer typing ``### Tickets`` has done the
#: thing we asked and should not be silently ignored for it.
BLOCK_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*TICKETS\s*$", re.IGNORECASE)
_ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")

#: Bumped when the grammar changes. Published beside every parse, because a
#: seat that filed against v1 deserves to know its lines were read by v1.
TICKETS_BLOCK_VERSION = "## TICKETS grammar v1 (2026-08-24, highway slice 4)"

#: A verb the parser will accept as an alias for a transition to a named state.
#: ONE alias, and it earns its place: "close" is what a chair actually types,
#: and the design's own §1.2 note is that a close without a citation is the
#: thing that must be refused, not the word.
_ALIASES = {"close": "done", "decline": "declined", "merge": "merged"}


def parse_tickets_block(text: Optional[str]) -> dict[str, Any]:
    """Read a seat's ``## TICKETS`` block into staged-row shapes.

    Grammar, one proposal per line, ``|``-separated ``key: value`` pairs::

        ## TICKETS
        - transition: <ticket_id> -> done | citation: docs/x.md
        - close: <ticket_id> | citation: docs/x.md
        - open: ask | for: quant | subject: implement the survivor
          | next_actor: chair | due: 2026-08-25 | reversibility: reversible

    **AN ABSENT BLOCK IS NOT ZERO PROPOSALS.** ``block_present`` is False when
    the seat wrote no block at all and True when it wrote an empty one, and the
    two are different facts: the first says the producer has not adopted the
    format, the second says it had nothing to file. Collapsing them would make
    the adoption number — the ONLY thing that tells us whether slice 7 worked —
    unreadable.

    **EVERY LINE THIS CANNOT READ IS RETURNED IN ``unparsed``.** A parser that
    silently drops what it does not understand converts a producer's mistake
    into a fact nobody can find, and the failure it would hide is the one
    already measured: 0 structured filings of 116.
    """
    if text is None:
        return {"block_present": False, "proposals": [], "unparsed": [],
                "version": TICKETS_BLOCK_VERSION,
                "note": "no text was supplied — the block is UNKNOWN, which is "
                        "not the same as a seat that filed nothing"}
    lines = str(text).splitlines()
    start = None
    for i, line in enumerate(lines):
        if BLOCK_HEADING.match(line):
            start = i + 1
            break
    if start is None:
        return {"block_present": False, "proposals": [], "unparsed": [],
                "version": TICKETS_BLOCK_VERSION,
                "note": "this output carries no '## TICKETS' block; the seat "
                        "has not adopted the format (design §2.4 — advisory "
                        "first, and adoption is measured per run)"}

    body: list[str] = []
    for line in lines[start:]:
        if _ANY_HEADING.match(line):
            break
        body.append(line)

    proposals, unparsed = [], []
    for raw in _logical_lines(body):
        p = _parse_one(raw)
        (proposals if p.get("kind") in STAGED_KINDS else unparsed).append(
            p if p.get("kind") in STAGED_KINDS
            else {"raw": raw, "why": p.get("why")})
    return {"block_present": True, "proposals": proposals,
            "unparsed": unparsed, "version": TICKETS_BLOCK_VERSION,
            "note": (f"{len(proposals)} proposal(s) read, {len(unparsed)} "
                     "line(s) this grammar could not read and did NOT drop")}


def _logical_lines(body: list[str]) -> list[str]:
    """Join continuation lines, so one proposal may wrap.

    A proposal wraps in real reports — the ``open:`` example above is 80
    characters past a sensible margin — and a grammar that punished wrapping
    would be a grammar nobody uses. A line starting a new bullet starts a new
    proposal; anything else continues the previous one.
    """
    out: list[str] = []
    for line in body:
        s = line.strip()
        if not s:
            continue
        if s.startswith(("-", "*")) or not out:
            out.append(s.lstrip("-*").strip())
        elif s.startswith("|"):
            # THE SEPARATOR SURVIVES THE JOIN. Stripping the leading ``|`` and
            # joining with a space merged two fields into one — a wrapped
            # ``| for: quant`` / ``| subject: x`` became the single field
            # ``for: "quant subject: x"``, which parses, stores, and is wrong.
            # Caught by the wrapping test, not by reading.
            out[-1] = out[-1] + " " + s
        else:
            out[-1] = out[-1] + " " + s
    return [o for o in out if o]


def _parse_one(raw: str) -> dict[str, Any]:
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    if not parts:
        return {"why": "empty line"}
    head, _, rest = parts[0].partition(":")
    verb = head.strip().lower()
    rest = rest.strip()
    fields: dict[str, Any] = {}
    for p in parts[1:]:
        k, sep, v = p.partition(":")
        if not sep:
            # A fragment with no key. Kept in `fields["_extra"]` rather than
            # dropped: a proposal that lost half its text at the door is worse
            # than one the chair has to read twice.
            fields.setdefault("_extra", []).append(p)
            continue
        fields[k.strip().lower()] = v.strip()

    if verb in ("transition",) or verb in _ALIASES:
        to = _ALIASES.get(verb)
        target = rest
        if to is None:
            m = re.match(r"^(\S+)\s*(?:->|=>|to)\s*(\S+)$", rest)
            if not m:
                return {"why": ("a transition needs '<ticket_id> -> <state>'; "
                                f"could not read {rest!r}")}
            target, to = m.group(1), m.group(2)
        if not target:
            return {"why": f"{verb!r} names no ticket"}
        return {"kind": "transition", "ticket_id": target, "to_state": to,
                "fields": fields, "raw": raw}

    if verb == "open":
        if not rest:
            return {"why": "'open' needs a ticket type (open: ask | ...)"}
        return {"kind": "open", "ticket_id": None, "to_state": None,
                "fields": {**fields, "type": rest}, "raw": raw}

    return {"why": f"unknown verb {verb!r}; this grammar knows "
                   f"{sorted(set(['transition', 'open']) | set(_ALIASES))}"}


# ------------------------------------------------------------- the table --

class StagedTickets:
    """The staging table. **APPENDS NOTHING TO THE EVENT LOG, EVER.**

    Deliberately does NOT subclass ``deskengine._Table``: that base owns the
    desk engine's ``SCHEMA``, and a staging table that created the engine's
    tables as a side effect would couple two lifecycles that have no reason to
    share one. The plumbing is six lines; the coupling would have been
    permanent.
    """

    def __init__(self, dsn: Optional[str] = None):
        from app.fund.pgstore import dsn as default_dsn
        self._dsn = dsn or default_dsn()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def stage(self, proposals: list[dict[str, Any]], *, run_id: Optional[str],
              seat: Optional[str]) -> list[dict[str, Any]]:
        """Write parsed proposals as staged rows. Returns what was written.

        Refuses an unknown ``kind`` rather than storing it: a row no resolve
        path can act on would sit on the chair's console forever looking like
        work.
        """
        rows = []
        with self._connect() as conn:
            with conn.cursor() as cur:
                for p in proposals:
                    if p.get("kind") not in STAGED_KINDS:
                        raise ValueError(
                            f"unknown staged kind {p.get('kind')!r} — "
                            f"expected one of {STAGED_KINDS}")
                    sid = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO fund_ticket_staged (staged_id, run_id, "
                        "seat, kind, ticket_id, to_state, fields, raw) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (sid, run_id, seat, p["kind"], p.get("ticket_id"),
                         p.get("to_state"), json.dumps(p.get("fields") or {}),
                         p.get("raw") or ""))
                    rows.append({**p, "staged_id": sid, "run_id": run_id,
                                 "seat": seat, "status": "staged"})
            conn.commit()
        return rows

    def staged(self, status: str = "staged", limit: int = 500
               ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT staged_id, run_id, seat, kind, ticket_id, "
                    "to_state, fields, raw, status, resolved_by, resolved_at, "
                    "resolution_reason, event_ref, created_at "
                    # CAST BOTH PLACEHOLDERS. Postgres cannot infer a
                    # parameter's type from `%s IS NULL` alone and raises
                    # "could not determine data type of parameter $1" — which
                    # this endpoint's own except-clause would have swallowed
                    # into `readable: false`, i.e. a coding error rendering as
                    # a database outage. Found by the console test, which
                    # asserted `readable is True`.
                    "FROM fund_ticket_staged "
                    "WHERE (%s::text IS NULL OR status = %s::text) "
                    "ORDER BY created_at DESC LIMIT %s",
                    (status, status, limit))
                cols = [c.name for c in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def resolve(self, staged_id: str, *, verdict: str, actor: str,
                reason: Optional[str] = None,
                event_ref: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Record one staged row's fate. Never DELETEs; never re-resolves.

        A STRIKE IS A RECORD, NOT A REMOVAL — see ``STAGED_STATUSES``. And the
        ``status = 'staged'`` predicate in the UPDATE is what makes a double
        resolve impossible in the DATABASE rather than in a check-then-write
        the way ``Supersessions`` learned to: two chair sessions clicking the
        same batch would otherwise both append an event.

        Returns None when nothing was updated — the row does not exist, or it
        was already resolved. The caller must distinguish that from success,
        which is why it is None and not an empty dict.
        """
        if verdict not in ("accepted", "struck"):
            raise ValueError(f"verdict must be 'accepted' or 'struck', "
                             f"got {verdict!r}")
        if verdict == "struck" and not (reason or "").strip():
            raise ValueError(
                "a strike needs its written reason — a struck proposal with no "
                "reason reads identically to one nobody looked at, which is "
                "the failure this table exists to end")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fund_ticket_staged SET status=%s, resolved_by=%s, "
                    "resolved_at=now(), resolution_reason=%s, event_ref=%s "
                    "WHERE staged_id=%s AND status='staged' "
                    "RETURNING staged_id, kind, ticket_id, to_state, fields, "
                    "raw, status, resolved_by, resolution_reason, event_ref",
                    (verdict, actor, reason, event_ref, staged_id))
                row = cur.fetchone()
                cols = [c.name for c in cur.description] if row else []
            conn.commit()
        return dict(zip(cols, row)) if row else None

    def attach_event(self, staged_id: str, *, event_ref: Optional[str],
                     note: Optional[str] = None) -> None:
        """Record what the append produced for a row already claimed.

        THE ORDER IS CLAIM-THEN-APPEND, AND THE FAILURE STATE IS NAMED. The
        row is marked ``accepted`` first, in one UPDATE predicated on
        ``status='staged'``, so two chair sessions clicking the same batch
        cannot both append. If the door then REFUSES, the row stays
        ``accepted`` with ``event_ref`` NULL and the refusal in
        ``resolution_reason`` — the console reports that as
        ``accepted_without_event`` rather than as a success.

        The alternative order (append, then mark) has the opposite failure: an
        event on the log with the row still staged, which is a proposal that
        can be applied twice. A visible orphan beats a silent duplicate on a
        log nothing can un-append.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fund_ticket_staged SET event_ref=%s, "
                    "resolution_reason=COALESCE(%s, resolution_reason) "
                    "WHERE staged_id=%s", (event_ref, note, staged_id))
            conn.commit()

    def get(self, staged_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT staged_id, run_id, seat, kind, ticket_id, "
                    "to_state, fields, raw, status, resolved_by, "
                    "resolution_reason, event_ref FROM fund_ticket_staged "
                    "WHERE staged_id = %s", (staged_id,))
                row = cur.fetchone()
                cols = [c.name for c in cur.description] if row else []
        return dict(zip(cols, row)) if row else None

    def counts(self) -> dict[str, int]:
        """Every status seeded, so a status with no rows reads 0 rather than
        vanishing from the dict — a key that disappears when its count reaches
        zero is absence-as-silence."""
        out = {s: 0 for s in STAGED_STATUSES}
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status, count(*) FROM fund_ticket_staged "
                            "GROUP BY status")
                for status, n in cur.fetchall():
                    out[status] = int(n)
        return out
