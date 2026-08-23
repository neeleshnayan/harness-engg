"""The desk engine's durable records: in-trays, supersession edges, briefing reviews.

THE DESK ENGINE v1 (docs/DESK_ENGINE_V1_2026-08-23.md), from six CEO
instructions given in one sitting. The engine's *rules* are pure functions in
``app.fund.deskhygiene`` and ``app.fund.desk``; this module is the three
things it must REMEMBER between requests:

  * **IN-TRAYS** — a seat may post a task to another seat's tray. It is an ASK,
    never a trigger: the chair drains the tray into the target seat's next
    brief and strikes-with-reason anything it disagrees with. Ignition stays
    human, unchanged.
  * **SUPERSESSION EDGES** — "this row replaces that one". The R37/R39 pair is
    the type specimen (docs/coo/TRIAGE7_2026-08-23.md decision 2): a staged
    recommendation whose premise dies at a NAMED FUTURE EVENT, which could
    otherwise be approved after the event that made it wrong.
  * **BRIEFING REVIEWS** — which seat memos the chair has verified, and the
    corrections found after publication. A correction is a new row, never an
    edit: the findings-doc rule applies to the shelf too.

WHY ONE MODULE AND NOT THREE. All three are small tables with the same
lifetime, the same connection story and the same audit requirement, and a
single ``_ensure`` means one place where the schema can be wrong. The logic
that reads them lives elsewhere precisely so that logic stays testable without
a database.

NOTHING HERE TOUCHES THE EVENT LOG, AND THAT IS DELIBERATE. Adding an
``EventType`` changes a lifecycle until proven otherwise (the D17 adversary
kill: a new order-aggregate type knocked orders out of ``pending()`` and made
them un-approvable). These three record types are work-layer bookkeeping with
no money path, so they get their own tables and their own audit rows rather
than a seat at the fund's ledger. The one place the engine DOES write events is
auto-hygiene closing a desk request, and that reuses the existing
``DeskRequestResolved`` lifecycle — no new type, no new fold.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


SCHEMA = """
-- SEAT IN-TRAYS (CEO instruction 4: "team members should be able to directly
-- add tasks to other desks which gets bundled in their next run; blessed by
-- you"). `to_seat` and `from_seat` are validated in Python against the roster
-- rather than by a foreign key, because the roster lives in a Python module
-- and a second copy in DDL would be a second thing to keep in step.
CREATE TABLE IF NOT EXISTS fund_desk_intray (
    item_id     TEXT PRIMARY KEY,
    to_seat     TEXT NOT NULL,
    from_seat   TEXT NOT NULL,
    task        TEXT NOT NULL,
    why         TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'posted',
    -- The chair's blessing, or its refusal. `struck_reason` is NOT NULL-able
    -- by convention rather than by constraint: `strike()` refuses an empty
    -- one, and a struck item with no reason would be exactly the silent
    -- rejection the desk request path already forbids.
    decided_by  TEXT,
    decided_at  TIMESTAMPTZ,
    reason      TEXT,
    -- A struck item goes back to the SENDER's next brief. Acknowledged when
    -- the sender has been told, so the return does not repeat forever.
    ack_at      TIMESTAMPTZ,
    posted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS fund_desk_intray_to_idx
    ON fund_desk_intray (to_seat, status, posted_at DESC);
CREATE INDEX IF NOT EXISTS fund_desk_intray_from_idx
    ON fund_desk_intray (from_seat, status, posted_at DESC);

-- EVERY TRANSITION, APPEND-ONLY. The item row carries current state; this
-- carries who moved it and why. Two tables rather than one because the
-- riskofficer audits the engine's writes the way it audits auto-approvals,
-- and a current-state row cannot answer "who struck this and when".
CREATE TABLE IF NOT EXISTS fund_desk_intray_log (
    log_id     BIGSERIAL PRIMARY KEY,
    item_id    TEXT NOT NULL,
    action     TEXT NOT NULL,
    actor      TEXT NOT NULL,
    reason     TEXT,
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fund_desk_intray_log_item_idx
    ON fund_desk_intray_log (item_id, at);

-- SUPERSESSION EDGES (CEO instruction 5: "where supersed happens; this r37
-- withdraw and r39 acceptance fills the same pattern").
--
-- `target_ref` is the row being superseded, `superseder_ref` the row doing it.
-- Both are desk row references (`rec:<run_id>#<rec_id>` / `req:<id>`), NOT
-- foreign keys: recommendations live inside a JSONB column on
-- `fund_agent_runs` and have no row of their own to point at.
--
-- RETRACTION IS A COLUMN, NOT A DELETE. A SUPERSEDED-PENDING edge exists
-- precisely because the premise MIGHT survive — "if R39 stops at the probe,
-- R37's premise revives intact" — so the revival path must leave a record that
-- the edge was applied and withdrawn, not erase it.
CREATE TABLE IF NOT EXISTS fund_desk_supersession (
    edge_id        TEXT PRIMARY KEY,
    target_ref     TEXT NOT NULL,
    -- NULLABLE, and the null means something: a `killed` row was not
    -- REPLACED by anything. Python refuses a null superseder on every other
    -- mode; a NOT NULL here would have forced the caller to invent a lineage
    -- for a row that has none, which is fabrication with a constraint's
    -- blessing.
    superseder_ref TEXT,
    mode           TEXT NOT NULL,
    reason         TEXT NOT NULL,
    dies_at_event  TEXT,
    revives_if     TEXT,
    applied_by     TEXT NOT NULL,
    applied_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    retracted_by   TEXT,
    retracted_at   TIMESTAMPTZ,
    retract_reason TEXT,
    confirmed_by   TEXT,
    confirmed_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS fund_desk_supersession_target_idx
    ON fund_desk_supersession (target_ref);
-- AT MOST ONE LIVE EDGE PER TARGET. A partial unique index rather than a
-- Python check, because two chairs applying an edge in the same second is
-- exactly the case a Python check loses. Postgres needs the predicate
-- repeated on the ON CONFLICT clause; see `Supersessions.add`.
CREATE UNIQUE INDEX IF NOT EXISTS fund_desk_supersession_live_idx
    ON fund_desk_supersession (target_ref) WHERE retracted_at IS NULL;

-- BRIEFING REVIEWS (the shelf's badge state). One row per (path, action):
-- `verified` flips the badge, `correction` appends a visible chip. The memo
-- itself is never edited — findings-doc rules apply to the shelf, so a
-- discrepancy found after publication becomes a row here.
CREATE TABLE IF NOT EXISTS fund_desk_briefing_review (
    review_id  TEXT PRIMARY KEY,
    path       TEXT NOT NULL,
    action     TEXT NOT NULL,
    actor      TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fund_desk_briefing_review_path_idx
    ON fund_desk_briefing_review (path, at DESC);
"""


# --------------------------------------------------------- row references ---
#
# A desk row is either a RECOMMENDATION (a run id plus an integer index into
# that run's JSONB list) or a REQUEST (a uuid). Supersession, hygiene and the
# UI all need to name one, so the name is defined ONCE here and parsed back the
# same way everywhere. A free-form string would have become two parsers.

_REC_REF_RE = re.compile(r"^rec:(?P<run_id>[^#\s]+)#(?P<rec_id>\d+)$")
_REQ_REF_RE = re.compile(r"^req:(?P<request_id>[^\s#]+)$")


def rec_ref(run_id: str, rec_id: Any) -> str:
    """The canonical reference to one recommendation."""
    return f"rec:{run_id}#{int(rec_id)}"


def req_ref(request_id: str) -> str:
    """The canonical reference to one desk request."""
    return f"req:{request_id}"


def parse_ref(ref: Any) -> Optional[dict[str, Any]]:
    """``{kind, run_id, rec_id}`` / ``{kind, request_id}``, or None.

    None for anything unparseable — and every caller treats that as "this is
    not a desk row" rather than as a row that happens to match nothing. A ref
    that silently matched nothing would let a supersession edge be filed
    against a target that cannot exist, and the row it was meant to protect
    would stay approvable.
    """
    if not isinstance(ref, str):
        return None
    m = _REC_REF_RE.match(ref.strip())
    if m:
        return {"kind": "rec", "run_id": m.group("run_id"),
                "rec_id": int(m.group("rec_id"))}
    m = _REQ_REF_RE.match(ref.strip())
    if m:
        return {"kind": "req", "request_id": m.group("request_id")}
    return None


# --------------------------------------------------------- in-tray states ---

#: What an in-tray item can be. Three, and none of them is "done": the tray
#: hands work to a BRIEF, and what the seat then does with it is the dispatch's
#: business, not the tray's. A fourth state claiming completion would be a
#: control reporting an outcome nobody observed.
INTRAY_STATUSES = ("posted", "blessed", "struck")

#: What a supersession edge asserts about its target.
#:
#:   superseded          dead now. The lineage is shown; the row cannot be
#:                       approved.
#:   superseded_pending  the premise dies at a NAMED FUTURE EVENT and the
#:                       revival branch is preserved. Also unapprovable — see
#:                       `Supersessions.add` for why the pending case is the
#:                       DANGEROUS one rather than the softer one.
#:   killed              killed on its merits (not replaced). Leaves the desk
#:                       for the floor's kill shelf.
SUPERSESSION_MODES = ("superseded", "superseded_pending", "killed")

#: Modes that make a row unapprovable. ALL of them, today — named as a set
#: rather than written as `mode is not None` so that adding a fourth mode is a
#: decision someone has to make here, in writing, instead of a default.
UNAPPROVABLE_MODES = ("superseded", "superseded_pending", "killed")

#: Modes that take the row OFF the desk entirely (to the floor's kill shelf).
#: `superseded_pending` is deliberately absent: its premise may revive, and a
#: row hidden from the desk cannot be revived by anyone who cannot see it.
SHELVED_MODES = ("superseded", "killed")

#: What a briefing review row can say.
BRIEFING_ACTIONS = ("verified", "correction")


def approval_refusal(ref: Optional[str],
                     edges_by_target: Optional[dict[str, dict[str, Any]]],
                     ) -> Optional[dict[str, Any]]:
    """Why this row may not be approved, or None.

    SERVER-SIDE, NOT A DISABLED BUTTON. The spec asks for the button to be
    disabled with the lineage rendered; a disabled button is a hint, and the
    thing that must not happen — R37 being clicked after the event that made
    it wrong — has to be impossible through the API, not merely awkward
    through the UI. The UI reads the same refusal to draw the disabled state,
    so the two cannot disagree.

    ``edges_by_target`` of None means the edge store could not be read. That
    returns None — NO refusal — and it is the one place in this module where
    an absence fails permissive, so it is stated out loud: refusing every
    approval whenever Postgres hiccups would take the CEO's whole approval
    path down for a bookkeeping table. The caller reports the degradation
    (``supersession_readable: false`` in the payload) so a click during an
    outage is visible in the record rather than silent.
    """
    if not ref or not edges_by_target:
        return None
    edge = edges_by_target.get(ref)
    if not edge or edge.get("retracted_at"):
        return None
    if edge.get("mode") not in UNAPPROVABLE_MODES:
        return None
    lineage = (f" It is superseded by {edge['superseder_ref']}."
               if edge.get("superseder_ref") else "")
    when = (f" Its premise dies at: {edge['dies_at_event']}."
            if edge.get("dies_at_event") else "")
    revive = (f" Revival branch: {edge['revives_if']}."
              if edge.get("revives_if") else "")
    return {
        "refused": True,
        "edge_id": edge.get("edge_id"),
        "mode": edge.get("mode"),
        "superseder_ref": edge.get("superseder_ref"),
        "dies_at_event": edge.get("dies_at_event"),
        "revives_if": edge.get("revives_if"),
        "reason": edge.get("reason"),
        "detail": (
            f"{ref} carries a live {edge.get('mode')} edge and cannot be "
            f"approved.{lineage}{when}{revive} Reason on file: "
            f"{edge.get('reason')}. To approve it anyway, retract the edge "
            f"first — with a written reason, as its own act."),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Table:
    """Shared Postgres plumbing for the engine's three record types."""

    def __init__(self, dsn: Optional[str] = None):
        from app.fund.pgstore import dsn as default_dsn
        self._dsn = dsn or default_dsn()
        self._ensure()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()


class InTray(_Table):
    """Seat-to-seat asks, and the chair's blessing of them."""

    def post(self, *, to_seat: str, from_seat: str, task: str,
             why: str = "", meta: Optional[dict] = None,
             item_id: Optional[str] = None) -> dict[str, Any]:
        """One seat asks another for something. An ASK, never a trigger.

        Refuses an empty task for the same reason ``desk_request`` does: "do
        research" is not an ask the bench can act on, and a blank row in
        somebody's brief costs a dispatch to discover.

        Refuses a seat posting to ITSELF. A self-post is a note, and the tray's
        whole purpose is the edge between two seats — a self-loop would appear
        in the target's brief as work somebody else asked for, which is false.
        """
        to_seat = (to_seat or "").strip().lower()
        from_seat = (from_seat or "").strip().lower()
        task = (task or "").strip()
        if not task:
            raise ValueError(
                "an in-tray item needs a task — a blank ask costs a dispatch "
                "to discover and tells the receiving seat nothing")
        if not to_seat or not from_seat:
            raise ValueError("both to_seat and from_seat are required")
        if to_seat == from_seat:
            raise ValueError(
                f"refusing a self-post to {to_seat!r} — an in-tray edge is "
                "between two seats, and a self-loop would render in the "
                "brief as work another seat asked for")
        iid = item_id or str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO fund_desk_intray "
                    "(item_id, to_seat, from_seat, task, why, meta) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (iid, to_seat, from_seat, task, (why or "").strip(),
                     json.dumps(meta or {})))
                cur.execute(
                    "INSERT INTO fund_desk_intray_log "
                    "(item_id, action, actor) VALUES (%s,'posted',%s)",
                    (iid, from_seat))
            conn.commit()
        return {"item_id": iid, "to_seat": to_seat, "from_seat": from_seat,
                "task": task, "why": (why or "").strip(), "status": "posted"}

    def items(self, seat: Optional[str] = None, status: Optional[str] = None,
              limit: int = 500) -> list[dict[str, Any]]:
        """Tray contents, oldest first — a queue is read in arrival order."""
        where, params = [], []
        if seat:
            where.append("to_seat = %s")
            params.append(seat.strip().lower())
        if status:
            where.append("status = %s")
            params.append(status)
        sql = ("SELECT item_id, to_seat, from_seat, task, why, status, "
               "decided_by, decided_at, reason, ack_at, posted_at, meta "
               "FROM fund_desk_intray"
               + (" WHERE " + " AND ".join(where) if where else "")
               + " ORDER BY posted_at ASC LIMIT %s")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (*params, limit))
                rows = cur.fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r) -> dict[str, Any]:
        return {"item_id": r[0], "to_seat": r[1], "from_seat": r[2],
                "task": r[3], "why": r[4], "status": r[5],
                "decided_by": r[6],
                "decided_at": r[7].isoformat() if r[7] else None,
                "reason": r[8],
                "ack_at": r[9].isoformat() if r[9] else None,
                "posted_at": r[10].isoformat() if r[10] else None,
                "meta": r[11] or {}}

    def returns_for(self, seat: str, limit: int = 200) -> list[dict[str, Any]]:
        """Items this seat POSTED that the chair struck and it has not been told about.

        The other half of the blessing: "struck items return to the sender's
        next brief with the reason". Unacknowledged only, so a return appears
        once rather than in every brief forever.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT item_id, to_seat, from_seat, task, why, status, "
                    "decided_by, decided_at, reason, ack_at, posted_at, meta "
                    "FROM fund_desk_intray "
                    "WHERE from_seat = %s AND status = 'struck' "
                    "  AND ack_at IS NULL "
                    "ORDER BY decided_at ASC LIMIT %s",
                    (seat.strip().lower(), limit))
                rows = cur.fetchall()
        return [self._row(r) for r in rows]

    def drain(self, seat: str, actor: str,
              strike: Optional[dict[str, str]] = None) -> dict[str, Any]:
        """The chair's ONE act at a seat's next dispatch: bless the tray, strike what it disagrees with.

        THE BLESSING IS THE BINDS PATTERN APPLIED TO TASKS. Everything posted
        and not named in ``strike`` is blessed into the brief; everything named
        is struck WITH ITS REASON and returns to the sender.

        Refuses a strike with no reason, and refuses a strike naming an item
        that is not in this tray — a typo'd id would otherwise bless an item
        the chair meant to remove, which is the failure direction that matters.
        """
        seat = (seat or "").strip().lower()
        strike = {str(k): (v or "").strip() for k, v in (strike or {}).items()}
        blank = sorted(k for k, v in strike.items() if not v)
        if blank:
            raise ValueError(
                f"strike needs a written reason for {blank} — a silent strike "
                "reads to the sending seat exactly like an unread ask")
        pending = [i for i in self.items(seat=seat, status="posted")]
        ids = {i["item_id"] for i in pending}
        unknown = sorted(set(strike) - ids)
        if unknown:
            raise ValueError(
                f"cannot strike {unknown}: not posted in {seat}'s tray — "
                "refused rather than ignored, because a mistyped id would "
                "silently BLESS the item the chair meant to remove")
        blessed, struck = [], []
        with self._connect() as conn:
            with conn.cursor() as cur:
                for item in pending:
                    iid = item["item_id"]
                    if iid in strike:
                        cur.execute(
                            "UPDATE fund_desk_intray SET status='struck', "
                            "decided_by=%s, decided_at=now(), reason=%s "
                            "WHERE item_id=%s", (actor, strike[iid], iid))
                        cur.execute(
                            "INSERT INTO fund_desk_intray_log "
                            "(item_id, action, actor, reason) "
                            "VALUES (%s,'struck',%s,%s)",
                            (iid, actor, strike[iid]))
                        struck.append({**item, "status": "struck",
                                       "reason": strike[iid],
                                       "decided_by": actor})
                    else:
                        cur.execute(
                            "UPDATE fund_desk_intray SET status='blessed', "
                            "decided_by=%s, decided_at=now() "
                            "WHERE item_id=%s", (actor, iid))
                        cur.execute(
                            "INSERT INTO fund_desk_intray_log "
                            "(item_id, action, actor) VALUES (%s,'blessed',%s)",
                            (iid, actor))
                        blessed.append({**item, "status": "blessed",
                                        "decided_by": actor})
            conn.commit()
        return {"seat": seat, "actor": actor, "at": _now(),
                "blessed": blessed, "struck": struck,
                "note": (f"{len(blessed)} item(s) blessed into {seat}'s next "
                         f"brief, {len(struck)} struck with a reason and "
                         f"returned to their senders"
                         if pending else
                         f"{seat}'s in-tray was empty — nothing to bless. An "
                         "empty tray is a measured fact, not a skipped step")}

    def acknowledge(self, item_ids: list[str], actor: str) -> int:
        """Mark struck items as delivered back to their sender. Returns the count."""
        if not item_ids:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fund_desk_intray SET ack_at = now() "
                    "WHERE item_id = ANY(%s) AND status='struck' "
                    "  AND ack_at IS NULL", (list(item_ids),))
                n = cur.rowcount
                for iid in item_ids:
                    cur.execute(
                        "INSERT INTO fund_desk_intray_log "
                        "(item_id, action, actor) VALUES (%s,'returned',%s)",
                        (iid, actor))
            conn.commit()
        return int(n)

    def history(self, item_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT action, actor, reason, at FROM fund_desk_intray_log "
                    "WHERE item_id = %s ORDER BY at ASC, log_id ASC", (item_id,))
                rows = cur.fetchall()
        return [{"action": r[0], "actor": r[1], "reason": r[2],
                 "at": r[3].isoformat() if r[3] else None} for r in rows]


class Supersessions(_Table):
    """`supersedes` edges between desk rows, and the refusal they carry."""

    def add(self, *, target_ref: str, mode: str, reason: str, actor: str,
            superseder_ref: Optional[str] = None,
            dies_at_event: Optional[str] = None,
            revives_if: Optional[str] = None,
            edge_id: Optional[str] = None) -> dict[str, Any]:
        """File one supersession edge.

        SUPERSEDED-PENDING REQUIRES BOTH A NAMED EVENT AND A REVIVAL BRANCH,
        and this is the rule the type specimen earned. R37's premise ("the
        broker holds zero of both") was true when it was filed and stops being
        true at R39 step 4; the COO's disposition was "retire, don't clear: if
        Monday stops at the probe, R37's premise revives intact". An edge that
        recorded only "pending" would lose BOTH halves — which event kills it,
        and what brings it back — and the row would then be resolved by
        whoever remembered, which is the state this engine replaces.

        A PENDING EDGE STILL BLOCKS APPROVAL, and that is a decision the spec
        did not make. The spec says "a superseded row cannot be approved"; the
        pending case is the one the CEO actually named, because the danger is
        not the row today but the row CLICKED AFTER the event that made it
        wrong ("it could clear and execute after Monday made it wrong"). So
        pending blocks too, and the revival path is ``retract`` — a written
        act by the chair when the event did not happen.

        ``superseder_ref`` is optional for ``killed``: a row killed on its
        merits is not replaced by anything, and inventing a superseder to fill
        the column would fabricate a lineage.
        """
        mode = (mode or "").strip().lower()
        if mode not in SUPERSESSION_MODES:
            raise ValueError(f"mode must be one of {SUPERSESSION_MODES}, got {mode!r}")
        if parse_ref(target_ref) is None:
            raise ValueError(
                f"target_ref {target_ref!r} is not a desk row reference "
                "(rec:<run_id>#<rec_id> or req:<request_id>) — refused rather "
                "than stored, because an edge against an unparseable target "
                "protects nothing while looking like it does")
        if superseder_ref is not None and parse_ref(superseder_ref) is None:
            raise ValueError(f"superseder_ref {superseder_ref!r} is not a desk row reference")
        if superseder_ref is not None and superseder_ref == target_ref:
            raise ValueError("a row cannot supersede itself")
        if mode != "killed" and not superseder_ref:
            raise ValueError(
                f"mode {mode!r} needs the row that supersedes this one — "
                "lineage is the whole point of the chip")
        if not (reason or "").strip():
            raise ValueError("a supersession needs its written reason")
        if mode == "superseded_pending":
            if not (dies_at_event or "").strip():
                raise ValueError(
                    "superseded_pending needs `dies_at_event`: the named "
                    "future event at which the premise dies. Without it the "
                    "chip says 'later' and nobody can tell when later arrived")
            if not (revives_if or "").strip():
                raise ValueError(
                    "superseded_pending needs `revives_if`: the branch in "
                    "which the premise survives. Retiring a row with no "
                    "revival branch recorded is a kill wearing a softer word")
        eid = edge_id or str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                # The partial unique index needs its predicate repeated here;
                # without it Postgres raises InvalidColumnReference rather than
                # using the index (measured on 16.15, builder D21).
                cur.execute(
                    "INSERT INTO fund_desk_supersession "
                    "(edge_id, target_ref, superseder_ref, mode, reason, "
                    " dies_at_event, revives_if, applied_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (target_ref) WHERE retracted_at IS NULL "
                    "DO NOTHING RETURNING edge_id",
                    (eid, target_ref, superseder_ref, mode, reason.strip(),
                     (dies_at_event or "").strip() or None,
                     (revives_if or "").strip() or None, actor))
                got = cur.fetchone()
            conn.commit()
        if got is None:
            raise ValueError(
                f"{target_ref} already carries a live supersession edge — "
                "retract the existing one first; two live edges on one row "
                "would make the chip depend on read order")
        return self.edge(eid) or {}

    def edge(self, edge_id: str) -> Optional[dict[str, Any]]:
        rows = self._select("WHERE edge_id = %s", (edge_id,))
        return rows[0] if rows else None

    def edges(self, include_retracted: bool = False,
              limit: int = 1000) -> list[dict[str, Any]]:
        where = "" if include_retracted else "WHERE retracted_at IS NULL"
        return self._select(where, (), limit=limit)

    def _select(self, where: str, params: tuple,
                limit: int = 1000) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT edge_id, target_ref, superseder_ref, mode, reason, "
                    "dies_at_event, revives_if, applied_by, applied_at, "
                    "retracted_by, retracted_at, retract_reason, "
                    "confirmed_by, confirmed_at "
                    f"FROM fund_desk_supersession {where} "
                    "ORDER BY applied_at DESC LIMIT %s", (*params, limit))
                rows = cur.fetchall()
        return [{"edge_id": r[0], "target_ref": r[1], "superseder_ref": r[2],
                 "mode": r[3], "reason": r[4], "dies_at_event": r[5],
                 "revives_if": r[6], "applied_by": r[7],
                 "applied_at": r[8].isoformat() if r[8] else None,
                 "retracted_by": r[9],
                 "retracted_at": r[10].isoformat() if r[10] else None,
                 "retract_reason": r[11], "confirmed_by": r[12],
                 "confirmed_at": r[13].isoformat() if r[13] else None}
                for r in rows]

    def by_target(self, include_retracted: bool = False) -> dict[str, dict[str, Any]]:
        """Live edges keyed by the row they act on — what every reader wants.

        At most one live edge per target is enforced by a partial unique index,
        so this mapping cannot silently drop a second edge that exists.
        """
        return {e["target_ref"]: e for e in self.edges(include_retracted)}

    def retract(self, edge_id: str, actor: str, reason: str) -> dict[str, Any]:
        """The revival branch: the named event did not happen, so the row lives.

        Recorded, never deleted. A reader must be able to see that a row was
        retired and brought back — the alternative is a row that silently
        reappears on the desk with no history, which is how the R37 pattern
        started.
        """
        if not (reason or "").strip():
            raise ValueError("a retraction needs its written reason — the "
                             "revival branch is a decision, not housekeeping")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fund_desk_supersession SET retracted_by=%s, "
                    "retracted_at=now(), retract_reason=%s "
                    "WHERE edge_id=%s AND retracted_at IS NULL",
                    (actor, reason.strip(), edge_id))
                n = cur.rowcount
            conn.commit()
        if not n:
            raise KeyError(f"no live supersession edge {edge_id}")
        return self.edge(edge_id) or {}

    def confirm(self, edge_id: str, actor: str,
                note: str = "") -> dict[str, Any]:
        """The named event HAPPENED: a pending edge becomes a plain supersession.

        Only pending edges move. Confirming anything else is refused rather
        than treated as a no-op, because "confirm" on an already-dead row would
        read in the log as an event that occurred.
        """
        row = self.edge(edge_id)
        if row is None or row.get("retracted_at"):
            raise KeyError(f"no live supersession edge {edge_id}")
        if row["mode"] != "superseded_pending":
            raise ValueError(
                f"edge {edge_id} is {row['mode']!r}, not pending — there is no "
                "future event left to confirm")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fund_desk_supersession SET mode='superseded', "
                    "confirmed_by=%s, confirmed_at=now(), "
                    "reason = reason || %s WHERE edge_id=%s",
                    (actor, f" | confirmed: {note.strip()}" if note.strip()
                     else " | confirmed", edge_id))
            conn.commit()
        return self.edge(edge_id) or {}


class BriefingLedger(_Table):
    """Which seat memos the chair has verified, and what it found afterwards."""

    def record(self, *, path: str, action: str, actor: str,
               note: str = "", review_id: Optional[str] = None) -> dict[str, Any]:
        action = (action or "").strip().lower()
        if action not in BRIEFING_ACTIONS:
            raise ValueError(f"action must be one of {BRIEFING_ACTIONS}")
        if not (path or "").strip():
            raise ValueError("a briefing review needs the memo's path")
        if action == "correction" and not (note or "").strip():
            raise ValueError(
                "a correction needs its text — an empty correction chip would "
                "warn a reader about nothing and train them to ignore the next")
        rid = review_id or str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO fund_desk_briefing_review "
                    "(review_id, path, action, actor, note) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (rid, path.strip().replace("\\", "/"), action, actor,
                     (note or "").strip()))
            conn.commit()
        return {"review_id": rid, "path": path, "action": action,
                "actor": actor, "note": note}

    def state(self, limit: int = 2000) -> dict[str, dict[str, Any]]:
        """Badge state per memo path: verification and every correction on it."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT path, action, actor, note, at "
                    "FROM fund_desk_briefing_review ORDER BY at ASC LIMIT %s",
                    (limit,))
                rows = cur.fetchall()
        out: dict[str, dict[str, Any]] = {}
        for path, action, actor, note, at in rows:
            slot = out.setdefault(path, {"verified_by": None,
                                         "verified_at": None,
                                         "corrections": []})
            if action == "verified":
                slot["verified_by"] = actor
                slot["verified_at"] = at.isoformat() if at else None
                if note:
                    slot["verification_note"] = note
            else:
                slot["corrections"].append(
                    {"actor": actor, "note": note,
                     "at": at.isoformat() if at else None})
        return out
