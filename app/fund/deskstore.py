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
    output          TEXT,
    recommendations JSONB DEFAULT '[]'::jsonb,
    meta            JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS fund_agent_runs_seat_idx
    ON fund_agent_runs (seat, resolved_at DESC);
"""

#: Statuses a recommendation moves through. `open` -> CEO decides -> `accepted`
#: or `rejected`; an accepted one the CTO stages becomes `staged`, and `done`
#: when the click lands. Never deleted — a rejected recommendation is a record
#: of judgement, not clutter.
REC_STATUSES = ("open", "accepted", "rejected", "staged", "done")


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
                   recommendations: Optional[list[dict]] = None,
                   meta: Optional[dict] = None) -> dict[str, Any]:
        """One dispatch, stored whole. Recommendations get ids and open status."""
        recs = []
        for i, r in enumerate(recommendations or [], 1):
            recs.append({"rec_id": i, "seat": seat, "status": "open",
                         "text": str(r.get("text") or r).strip(),
                         "kind": r.get("kind") if isinstance(r, dict) else None})
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fund_agent_runs
                        (run_id, seat, task, model, tokens, tool_uses,
                         dispatched_at, artifact_path, verdict, output,
                         recommendations, meta)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        output = EXCLUDED.output,
                        artifact_path = EXCLUDED.artifact_path,
                        verdict = EXCLUDED.verdict,
                        tokens = EXCLUDED.tokens,
                        recommendations = EXCLUDED.recommendations,
                        meta = EXCLUDED.meta
                    """,
                    (run_id, seat, task, model, tokens, tool_uses,
                     dispatched_at, artifact_path, verdict, output,
                     json.dumps(recs), json.dumps(meta or {})))
            conn.commit()
        return {"run_id": run_id, "recommendations": len(recs)}

    def runs(self, seat: Optional[str] = None, limit: int = 50,
             with_output: bool = False) -> list[dict[str, Any]]:
        cols = ("run_id, seat, task, model, tokens, tool_uses, dispatched_at, "
                "resolved_at, artifact_path, verdict, recommendations"
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
                 "recommendations": r[10] or []}
            if with_output:
                d["output"] = r[11]
            out.append(d)
        return out

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

    def decide_recommendation(self, run_id: str, rec_id: int, status: str,
                              actor: str, note: str = "") -> dict[str, Any]:
        """Move one recommendation's status. State here, the decision as an event
        at the caller — both, and they must agree."""
        if status not in REC_STATUSES:
            raise ValueError(f"status must be one of {REC_STATUSES}")
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
                                "artifact_path": run["artifact_path"]})
        return out
