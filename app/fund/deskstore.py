"""Every agent run, stored whole in Postgres — the desk's flight recorder.

Until now a run's full output lived in two places, both wrong for learning: the
curated artifact in docs/ (edited, summarised) and the session transcript
(ephemeral, unqueryable). The CEO's requirement is the right one: **log every
run, whole, per seat, in the same durable store as the fund's facts** — so the
firm can ask "what did the pm recommend in June and what did we do about it"
and get an answer from SQL rather than archaeology.

Two things live here:

  * RUNS — one row per dispatch: seat, task, model, tokens, the FULL output
    text, and the artifact path it was distilled into. Written by the CTO at
    resolve time.
  * RECOMMENDATIONS — structured rows extracted from a run's output, each
    carrying the seat that made it. This is what the UI renders with
    attribution chips, and what order rationales cite when a recommendation is
    staged ("[pm · rec 6]"), so the approval card itself shows which agent's
    judgement you are clicking on.

Decisions on recommendations (accept / reject) are CEO governance and therefore
also EVENTS (DESK_RECOMMENDATION_DECIDED) — the table holds current state, the
log holds who decided what and when, and they must agree.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_agent_runs (
    run_id          TEXT PRIMARY KEY,
    seat            TEXT NOT NULL,
    task            TEXT NOT NULL,
    model           TEXT,
    tokens          INTEGER,
    tool_uses       INTEGER,
    dispatched_at   TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ DEFAULT now(),
    artifact_path   TEXT,
    verdict         TEXT,
    reasoning       TEXT,
    output          TEXT,
    trace_id        TEXT,
    recommendations JSONB DEFAULT '[]'::jsonb,
    meta            JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS fund_agent_runs_seat_idx
    ON fund_agent_runs (seat, resolved_at DESC);
ALTER TABLE fund_agent_runs ADD COLUMN IF NOT EXISTS reasoning TEXT;
ALTER TABLE fund_agent_runs ADD COLUMN IF NOT EXISTS trace_id TEXT;
CREATE INDEX IF NOT EXISTS fund_agent_runs_trace_idx
    ON fund_agent_runs (trace_id);

-- THE INTERACTION ITSELF (CEO decision, 2026-08-21).
--
-- `fund_agent_runs.output` holds what a seat CONCLUDED. It does not hold the
-- brief the seat was given, nor the turn-by-turn transcript of how it got
-- there — and those are the two things needed to ask why a seat reached a
-- conclusion, or to re-run a dispatch against a changed harness and compare.
-- Both currently live only in a session that ends.
--
-- Kinds, deliberately three rather than a free string: `brief` (what we asked),
-- `report` (what came back, verbatim, before any editing into an artifact), and
-- `transcript` (the turn log). A run may have any subset; the absence of one is
-- a fact about our capture, not about the run.
--
-- NO RETENTION POLICY, and that is a decision rather than an oversight — the
-- CEO said so explicitly. Cleanup is a later versioned change with a written
-- reason. A table that silently aged out the record of how a decision was
-- reached would be the write-only-verdict-column defect wearing a janitor's
-- coat.
CREATE TABLE IF NOT EXISTS fund_agent_transcripts (
    transcript_id BIGSERIAL PRIMARY KEY,
    run_id        TEXT NOT NULL,
    kind          TEXT NOT NULL,
    content       TEXT NOT NULL,
    meta          JSONB DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fund_agent_transcripts_run_idx
    ON fund_agent_transcripts (run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS fund_agent_transcripts_kind_idx
    ON fund_agent_transcripts (kind, created_at DESC);
"""

#: What a transcript row may be. A closed set because the three answer different
#: questions and a free-text kind would make "did we keep the brief" unanswerable
#: by query.
TRANSCRIPT_KINDS = ("brief", "report", "transcript")

#: Statuses a recommendation moves through. `open` -> CEO decides -> `accepted`
#: or `rejected`; an accepted one the CTO stages becomes `staged`, and `done`
#: when the click lands. Never deleted — a rejected recommendation is a record
#: of judgement, not clutter.
#:
#: `noted` added 2026-08-22. The secretary files `note` rows that ask to be READ
#: rather than decided, and there was no terminal status for one — so both chairs
#: had been marking them `done`, which says EXECUTED. Reading an observation and
#: executing a change are not the same act, and a vocabulary that cannot tell
#: them apart makes the distinction unrecordable.
REC_STATUSES = ("open", "accepted", "rejected", "staged", "done", "noted")

#: Statuses after which nothing more is expected of anyone. Named rather than
#: inferred, so a surface counting "what is still owed" does not keep a list of
#: its own that drifts from this one. `desk.TERMINAL_STATUSES` mirrors it for
#: callers that must not import a database module, and a test pins them equal.
TERMINAL_REC_STATUSES = ("rejected", "done", "noted")


def _next_actor(raw: Any) -> Optional[str]:
    """The seat's OWN statement of whose move is next, or None.

    Optional, and the absence is meaningful rather than a default: with no
    statement the desk INFERS the actor from the row's lifecycle and kind
    (`desk.next_actor`), and the payload publishes how many rows were declared
    versus inferred so a reader knows which they are looking at.

    Written because the desk counter's whole defect class is labels standing in
    for facts. The one thing inference provably cannot express is the COO's
    standing objection: a recommendation the CEO has ACCEPTED whose EXECUTION is
    still the CEO's own act — three of those were live on 2026-08-21 and the
    counter could not see any of them. `next_actor="ceo"` says it in one field.

    An unrecognised value is kept, not silently dropped: `desk.next_actor`
    renders it UNKNOWN and counts it, which sends someone to look. Discarding it
    here would turn a garbled claim into no claim at all.
    """
    if not isinstance(raw, str):
        return None
    v = raw.strip().lower()
    return v or None


#: How hard a recommendation is to undo, as the SEAT states it.
#:
#: The desk currently INFERS this from `kind` against a table, and the inference
#: is thin where it matters most: `awaits-ceo`, `batch` and `challenge` are
#: routing words that say nothing about the act, so the CEO's own rows render
#: "unclassified kind — ranked as if hard to undo" on almost every line. That is
#: honest and it is noise, and noise on every row is how a warning stops being
#: read.
#:
#: A seat knows whether its own recommendation can be taken back. This is the
#: same pattern as `money_at_stake`, `due_date` and `next_actor`: optional,
#: validated, never inferred from prose, and absent means the desk falls back to
#: the kind table rather than to a guess.
REVERSIBILITY = ("irreversible", "hard", "reversible")


def _reversibility(raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    v = raw.strip().lower()
    return v if v in REVERSIBILITY else None


_DUE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _due_date(raw: Any) -> Optional[str]:
    """A dated commitment as YYYY-MM-DD, or None.

    The day something happens whether or not anybody clicks — an auto-close, a
    time exit, a expiring authorisation. It is the CEO desk's top ranking key,
    because a deadline is the one thing on that page that does not wait.

    VALIDATED, and anything else is None rather than stored: a malformed date
    would sort lexicographically against real ones and silently put a row in
    the wrong place, which is worse than the row having no date at all. It is
    never parsed out of the recommendation's text — a deadline read out of
    English is the same class of mistake as a completion read out of English,
    and this desk is being repaired from exactly that.
    """
    if not isinstance(raw, str):
        return None
    v = raw.strip()
    return v if _DUE_DATE_RE.match(v) else None


def _money_at_stake(r: Any) -> Optional[float]:
    """The dollars a recommendation moves, if the seat stated one.

    Returns None for anything that is not a finite number the seat put there
    ON PURPOSE. Never parsed out of the text: prose contains dollar figures
    that are evidence, not stakes ("a $376.84 BUY" is the SIZE OF A BUG in one
    recommendation and the size of the ask in another), and a ranking built on
    that would be confidently wrong rather than honestly blank.
    """
    if not isinstance(r, dict):
        return None
    raw = r.get("money_at_stake")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):   # NaN / inf
        return None
    return round(v, 2)


class DeskStore:
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

    def record_run(self, *, run_id: str, seat: str, task: str,
                   output: str, model: Optional[str] = None,
                   tokens: Optional[int] = None,
                   tool_uses: Optional[int] = None,
                   dispatched_at: Optional[str] = None,
                   artifact_path: Optional[str] = None,
                   verdict: Optional[str] = None,
                   reasoning: Optional[str] = None,
                   trace_id: Optional[str] = None,
                   recommendations: Optional[list[dict]] = None,
                   meta: Optional[dict] = None) -> dict[str, Any]:
        """One dispatch, stored whole. Recommendations get ids and open status.

        trace_id is the chatter thread: born at the desk request (or minted at
        dispatch), carried verbatim onto the run, its recommendations, and the
        decision events — so one id filters the whole conversation between
        desks out of SQL and the event log.
        """
        recs = []
        for i, r in enumerate(recommendations or [], 1):
            recs.append({"rec_id": i, "seat": seat, "status": "open",
                         "trace_id": trace_id,
                         "text": str(r.get("text") or r).strip(),
                         "kind": r.get("kind") if isinstance(r, dict) else None,
                         # OPTIONAL. 47 of 47 open recommendations carried no
                         # dollar figure, so the CEO's desk ranked its queue by
                         # arrival order while claiming to rank by money
                         # (builder dispatch 3). None means the seat did not
                         # state a figure — it does NOT mean $0, and the desk
                         # ranks absent-last and says the gap out loud rather
                         # than scraping a number out of prose.
                         "money_at_stake": _money_at_stake(r),
                         # OPTIONAL. The seat's own statement of whose move is
                         # next; absent means the desk infers it. See
                         # `_next_actor` for why the field exists at all.
                         "next_actor": _next_actor(
                             r.get("next_actor") if isinstance(r, dict) else None),
                         # OPTIONAL YYYY-MM-DD. A DATED COMMITMENT — the day
                         # something happens whether or not anybody clicks —
                         # and the CEO desk's top ranking key. Absent means the
                         # seat stated no date; it is never parsed out of the
                         # text, because a deadline read out of English is the
                         # same mistake as a completion read out of English.
                         "due_date": _due_date(
                             r.get("due_date") if isinstance(r, dict) else None),
                         # OPTIONAL. The desk's SECOND ranking key, stated by
                         # the seat rather than guessed from its kind. Absent
                         # falls back to the kind table.
                         "reversibility": _reversibility(
                             r.get("reversibility") if isinstance(r, dict)
                             else None)})
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fund_agent_runs
                        (run_id, seat, task, model, tokens, tool_uses,
                         dispatched_at, artifact_path, verdict, reasoning,
                         output, trace_id, recommendations, meta)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        output = EXCLUDED.output,
                        artifact_path = EXCLUDED.artifact_path,
                        verdict = EXCLUDED.verdict,
                        reasoning = EXCLUDED.reasoning,
                        tokens = EXCLUDED.tokens,
                        trace_id = COALESCE(EXCLUDED.trace_id,
                                            fund_agent_runs.trace_id),
                        recommendations = EXCLUDED.recommendations,
                        meta = EXCLUDED.meta
                    """,
                    (run_id, seat, task, model, tokens, tool_uses,
                     dispatched_at, artifact_path, verdict, reasoning, output,
                     trace_id, json.dumps(recs), json.dumps(meta or {})))
            conn.commit()
        return {"run_id": run_id, "recommendations": len(recs)}

    def runs(self, seat: Optional[str] = None, limit: int = 50,
             with_output: bool = False) -> list[dict[str, Any]]:
        cols = ("run_id, seat, task, model, tokens, tool_uses, dispatched_at, "
                "resolved_at, artifact_path, verdict, reasoning, trace_id, "
                "recommendations"
                + (", output" if with_output else ""))
        where, params = "", ()
        if seat:
            where, params = "WHERE seat = %s", (seat,)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {cols} FROM fund_agent_runs {where} "
                            f"ORDER BY resolved_at DESC LIMIT %s",
                            (*params, limit))
                rows = cur.fetchall()
        out = []
        for r in rows:
            d = {"run_id": r[0], "seat": r[1], "task": r[2], "model": r[3],
                 "tokens": r[4], "tool_uses": r[5],
                 "dispatched_at": r[6].isoformat() if r[6] else None,
                 "resolved_at": r[7].isoformat() if r[7] else None,
                 "artifact_path": r[8], "verdict": r[9],
                 # The distilled WHY - 3-6 bullets the CTO writes at resolve,
                 # rendered in the UI so a decision's reasoning is readable
                 # without opening the full artifact. The full output stays
                 # below it for the audit.
                 "reasoning": r[10],
                 "trace_id": r[11],
                 "recommendations": r[12] or []}
            if with_output:
                d["output"] = r[13]
            out.append(d)
        return out

    def runs_between(self, start_iso: str, end_iso: str,
                     limit: int = 500) -> list[dict[str, Any]]:
        """Every run RESOLVED inside a half-open window [start, end).

        Additive, and it exists for one reason: `runs(limit=25)` — what the desk
        payload carries — is capped ACROSS ALL SEATS, so a per-seat "runs today"
        folded from it is a FLOOR wearing the costume of a count. On a busy day
        the 26th run silently stops existing and the quietest seat is the one
        that gets truncated first.

        Filtering in SQL rather than in Python keeps the answer exact without
        shipping the whole table: the window is small (a day) and the
        (seat, resolved_at) index already covers it.

        `resolved_at` is TIMESTAMPTZ, so the caller supplies UTC boundaries and
        gets the venue's day, not the reader's — the same rule the UI's dayKey
        follows. A run with a NULL resolved_at is not in any window; it is not
        counted anywhere and that is correct, because a run with no resolution
        time has not been placed on a day.
        """
        cols = ("run_id, seat, task, model, tokens, tool_uses, dispatched_at, "
                "resolved_at, artifact_path, verdict, trace_id")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {cols} FROM fund_agent_runs "
                    "WHERE resolved_at >= %s AND resolved_at < %s "
                    "ORDER BY resolved_at DESC LIMIT %s",
                    (start_iso, end_iso, limit))
                rows = cur.fetchall()
        return [{"run_id": r[0], "seat": r[1], "task": r[2], "model": r[3],
                 "tokens": r[4], "tool_uses": r[5],
                 "dispatched_at": r[6].isoformat() if r[6] else None,
                 "resolved_at": r[7].isoformat() if r[7] else None,
                 "artifact_path": r[8], "verdict": r[9], "trace_id": r[10]}
                for r in rows]

    def run(self, run_id: str) -> Optional[dict[str, Any]]:
        rows = [r for r in self.runs(limit=1000, with_output=False)
                if r["run_id"] == run_id]
        if not rows:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT output FROM fund_agent_runs "
                            "WHERE run_id = %s", (run_id,))
                got = cur.fetchone()
        rows[0]["output"] = got[0] if got else None
        return rows[0]

    # --- the interaction itself (2026-08-21) -------------------------------

    def add_transcript(self, *, run_id: str, kind: str, content: str,
                       meta: Optional[dict] = None) -> dict[str, Any]:
        """Store a brief, a verbatim report, or a turn log against a run.

        APPEND-ONLY and deliberately NOT upserted on (run_id, kind). A dispatch
        can legitimately carry two briefs — the original and a mid-flight course
        correction — and collapsing them onto one row would erase the fact that
        the scope moved, which is exactly the thing a later reader needs to see.
        Each row carries its own `created_at`, so the sequence is recoverable.

        The run does NOT have to exist yet: a brief is written before a run
        resolves, and refusing it until the run row lands would mean the one
        artifact written first is the one that cannot be stored.
        """
        k = (kind or "").strip().lower()
        if k not in TRANSCRIPT_KINDS:
            raise ValueError(f"kind must be one of {TRANSCRIPT_KINDS}, got {kind!r}")
        if not (content or "").strip():
            raise ValueError("refusing to store an empty transcript — an empty "
                             "row would read as 'we captured this' when nothing "
                             "was captured")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO fund_agent_transcripts (run_id, kind, content, meta) "
                    "VALUES (%s,%s,%s,%s) RETURNING transcript_id, created_at",
                    (run_id, k, content, json.dumps(meta or {})))
                tid, created = cur.fetchone()
            conn.commit()
        return {"transcript_id": int(tid), "run_id": run_id, "kind": k,
                "chars": len(content),
                "created_at": created.isoformat() if created else None}

    def transcripts(self, run_id: str, kind: Optional[str] = None,
                    with_content: bool = True) -> dict[str, Any]:
        """Everything captured for one run, oldest first.

        Oldest first, unlike `runs()`: this is a CHRONOLOGY — brief, then
        transcript, then report — and reading a conversation backwards is a
        different thing from reading a list of runs newest-first.

        `kinds_present` / `kinds_missing` are returned rather than left to the
        caller to derive, because "no brief was captured for this run" is the
        answer a reader most often wants and the easiest one to mistake for
        "this run had no brief".
        """
        sql = ("SELECT transcript_id, run_id, kind, created_at, meta, "
               "       length(content), " + ("content" if with_content else "NULL") +
               " FROM fund_agent_transcripts WHERE run_id = %s")
        params: list[Any] = [run_id]
        if kind:
            sql += " AND kind = %s"
            params.append(kind.strip().lower())
        sql += " ORDER BY created_at ASC, transcript_id ASC"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        out = [{"transcript_id": int(r[0]), "run_id": r[1], "kind": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "meta": r[4] or {}, "chars": int(r[5] or 0),
                "content": r[6]} for r in rows]
        present = sorted({r["kind"] for r in out})
        missing = [k for k in TRANSCRIPT_KINDS if k not in present]
        return {
            "run_id": run_id, "transcripts": out, "count": len(out),
            "kinds_present": present,
            "kinds_missing": missing,
            "note": (f"{len(out)} captured ({', '.join(present)})"
                     + (f"; NOT captured: {', '.join(missing)} — absent from the "
                        f"record, which is not the same as the run not having had one"
                        if missing else "")
                     if out else
                     "nothing was captured for this run — the interaction is "
                     "gone, not empty"),
        }

    def decide_recommendation(self, run_id: str, rec_id: int, status: str,
                              actor: str, note: str = "",
                              next_actor: Optional[str] = None) -> dict[str, Any]:
        """Move one recommendation's status. State here, the decision as an event
        at the caller — both, and they must agree.

        ``next_actor`` is how a decision says whose move it is NEXT, which is a
        different question from what the decision was. Its one indispensable use:
        an `accepted` row whose EXECUTION is still the CEO's own act stays on the
        CEO's counter instead of being inferred onto the chair's — the COO's
        objection of 2026-08-21, which had no field to live in until now.

        A decision that makes the row TERMINAL clears any standing next_actor,
        because a label written while the row was live outlives its truth and a
        stale one would keep a closed row on somebody's queue. Passing an
        explicit value alongside a terminal status is refused rather than
        quietly ignored: it is a contradiction, and the caller should see it.
        """
        if status not in REC_STATUSES:
            raise ValueError(f"status must be one of {REC_STATUSES}")
        na = _next_actor(next_actor)
        if na and status in TERMINAL_REC_STATUSES:
            raise ValueError(
                f"refusing next_actor={na!r} on terminal status {status!r} — "
                "nothing follows a terminal row, and recording an owner for one "
                "would put closed work back on a queue")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT recommendations FROM fund_agent_runs "
                            "WHERE run_id = %s FOR UPDATE", (run_id,))
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"no run {run_id}")
                recs = row[0] or []
                hit = None
                for r in recs:
                    if r.get("rec_id") == rec_id:
                        r["status"] = status
                        r["decided_by"] = actor
                        r["decided_at"] = datetime.now(timezone.utc).isoformat()
                        if note:
                            r["note"] = note
                        if na:
                            r["next_actor"] = na
                        elif status in TERMINAL_REC_STATUSES:
                            # The label outlived its truth the moment the row
                            # closed. Clearing beats carrying.
                            r.pop("next_actor", None)
                        hit = r
                if hit is None:
                    raise KeyError(f"no rec {rec_id} on run {run_id}")
                cur.execute("UPDATE fund_agent_runs SET recommendations = %s "
                            "WHERE run_id = %s", (json.dumps(recs), run_id))
            conn.commit()
        return hit

    def open_recommendations(self) -> list[dict[str, Any]]:
        """Every rec awaiting a decision, across all runs — attribution attached."""
        out = []
        for run in self.runs(limit=200):
            for r in run["recommendations"]:
                if r.get("status") in ("open", "accepted", "staged"):
                    out.append({**r, "run_id": run["run_id"],
                                "task": run["task"],
                                "trace_id": r.get("trace_id")
                                            or run.get("trace_id"),
                                "artifact_path": run["artifact_path"]})
        return out
