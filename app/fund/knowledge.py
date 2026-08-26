"""THE KNOWLEDGE GRAPH — the firm's compounding understanding, as queryable rows.

Chartered 2026-08-27 by the CEO, in two sentences that are the whole design:
*"Our research, the essence, the learnings, the mistakes and corrections all
need to compound into an operator guide for us"* and, on the shape, *"build
it and refine as we go... you could just fire a query and give an answer
thats grounded in our research and so could every agent leveraging on our
past work."*

So: a graph — CLAIMS (typed nodes) and EDGES (typed relations) — living in
the SAME Postgres the fund already runs, watches, and snapshots. Not a second
database: the graph model is tables + recursive CTEs behind a stable API, and
the day a traversal outgrows SQL the backend swaps behind that API without
the callers noticing. The markdown books under ``docs/guide/`` are RENDERED
VIEWS of these rows (``render_book``), never hand-maintained — written once,
in rows, which is the CEO's triple-work point honoured in the schema.

THE ENTRY DISCIPLINE (working protocol 1, applied to knowledge):
a claim enters with its RECEIPT (a citation into the record — a run id, a
doc, a commit, an endpoint reading) and its FALSIFIER. A claim without a
receipt is refused at the door — the founding lesson of the judgement
register was that a register of notes reviews nothing.

CONTRADICTION FLAGS, NEVER OVERWRITES: new evidence against a claim marks it
``contested`` and links the challenger with a ``contradicts`` edge; retiring
a claim is an explicit act with an actor. History is never edited — the
findings-doc rule, inherited.

WHO WRITES: the chair (and the distillation process it reviews). Seats READ —
their truth path is ``GET /fund/knowledge/search`` before re-deriving what
the firm already paid to learn. The pen boundary is unchanged.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("clarkharness")

#: Node kinds. ``entity`` is a thing claims attach to (a market, a strategy,
#: an instrument); the rest are knowledge with receipts.
CLAIM_KINDS = ("market_fact", "runbook", "failure_class", "edge_lesson",
               "doctrine", "entity")

#: Edge relations. Kept few and meaningful; a vocabulary that grows a synonym
#: per author indexes nothing (the ``kind`` free-text lesson, 84 variants).
EDGE_RELS = ("applies_to", "grounds", "contradicts", "supersedes",
             "derived_from", "taught_by", "compounds_into", "guards_against")

CLAIM_STATUSES = ("active", "contested", "retired")

KNOWLEDGE_VERSION = "knowledge graph v1 (2026-08-27, CEO charter)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS kf_claims (
    claim_id    text PRIMARY KEY,
    kind        text NOT NULL,
    title       text NOT NULL,
    body        text NOT NULL DEFAULT '',
    tags        jsonb NOT NULL DEFAULT '[]',
    receipt     text NOT NULL,
    falsifier   text,
    status      text NOT NULL DEFAULT 'active',
    actor       text NOT NULL,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS kf_edges (
    edge_id     text PRIMARY KEY,
    from_id     text NOT NULL REFERENCES kf_claims(claim_id),
    to_id       text NOT NULL REFERENCES kf_claims(claim_id),
    rel         text NOT NULL,
    note        text NOT NULL DEFAULT '',
    actor       text NOT NULL,
    created_at  timestamptz NOT NULL,
    UNIQUE (from_id, to_id, rel)
);
CREATE INDEX IF NOT EXISTS kf_claims_kind_idx ON kf_claims (kind);
CREATE INDEX IF NOT EXISTS kf_claims_status_idx ON kf_claims (status);
CREATE INDEX IF NOT EXISTS kf_claims_tags_idx ON kf_claims USING gin (tags);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeError(ValueError):
    pass


class KnowledgeStore:
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

    # ------------------------------------------------------------- writes --
    def add_claim(self, *, kind: str, title: str, receipt: str, actor: str,
                  body: str = "", tags: Optional[list[str]] = None,
                  falsifier: Optional[str] = None,
                  claim_id: Optional[str] = None) -> dict[str, Any]:
        """A claim enters with its receipt or it does not enter.

        ``entity`` nodes are the one exception to the falsifier expectation —
        a market is not a claim about the world — but even an entity carries
        a receipt saying why it exists here.
        """
        if kind not in CLAIM_KINDS:
            raise KnowledgeError(f"unknown kind {kind!r}; kinds are {CLAIM_KINDS}")
        if not (receipt or "").strip():
            raise KnowledgeError(
                "a claim without a receipt is a note, and a register of notes "
                "reviews nothing — cite the run, doc, commit, or endpoint")
        if not (title or "").strip():
            raise KnowledgeError("a claim needs a title")
        cid = claim_id or uuid.uuid4().hex[:12]
        now = _now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kf_claims (claim_id, kind, title, body, tags,
                                           receipt, falsifier, status, actor,
                                           created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s,%s,%s)
                    ON CONFLICT (claim_id) DO NOTHING
                    RETURNING claim_id
                    """,
                    (cid, kind, title.strip(), body, json.dumps(tags or []),
                     receipt.strip(), falsifier, actor, now, now))
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise KnowledgeError(f"claim_id {cid!r} already exists — a re-"
                                 "measurement gets a new claim and a "
                                 "supersedes edge, never an overwrite")
        return {"claim_id": cid, "kind": kind, "title": title.strip()}

    def add_edge(self, *, from_id: str, to_id: str, rel: str, actor: str,
                 note: str = "") -> dict[str, Any]:
        if rel not in EDGE_RELS:
            raise KnowledgeError(f"unknown rel {rel!r}; rels are {EDGE_RELS}")
        eid = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            with conn.cursor() as cur:
                for cid in (from_id, to_id):
                    cur.execute("SELECT 1 FROM kf_claims WHERE claim_id=%s", (cid,))
                    if cur.fetchone() is None:
                        raise KnowledgeError(f"no such claim {cid!r} — an edge "
                                             "to a phantom indexes nothing")
                cur.execute(
                    """
                    INSERT INTO kf_edges (edge_id, from_id, to_id, rel, note,
                                          actor, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (from_id, to_id, rel) DO NOTHING
                    RETURNING edge_id
                    """,
                    (eid, from_id, to_id, rel, note, actor, _now()))
                row = cur.fetchone()
            conn.commit()
        return {"edge_id": row[0] if row else None,
                "already": row is None, "rel": rel}

    def set_status(self, claim_id: str, status: str, actor: str,
                   note: str = "") -> dict[str, Any]:
        """Contest or retire — explicit acts with actors, never silent edits."""
        if status not in CLAIM_STATUSES:
            raise KnowledgeError(f"unknown status {status!r}")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE kf_claims
                    SET status=%s, updated_at=%s,
                        body = body || %s
                    WHERE claim_id=%s
                    RETURNING claim_id
                    """,
                    (status, _now(),
                     f"\n\n[{status.upper()} {_now().date().isoformat()} by "
                     f"{actor}: {note}]" if note else "",
                     claim_id))
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise KnowledgeError(f"no such claim {claim_id!r}")
        return {"claim_id": claim_id, "status": status}

    # -------------------------------------------------------------- reads --
    def search(self, q: str = "", kind: Optional[str] = None,
               tag: Optional[str] = None, status: Optional[str] = None,
               limit: int = 50) -> dict[str, Any]:
        """The query every agent fires before re-deriving paid-for knowledge.

        v1 is ILIKE over title+body+receipt — honest about being substring
        search, not semantics. The API shape is the contract; the matcher can
        grow behind it.
        """
        clauses, params = [], []
        if q.strip():
            clauses.append("(title ILIKE %s OR body ILIKE %s OR receipt ILIKE %s)")
            like = f"%{q.strip()}%"
            params += [like, like, like]
        if kind:
            clauses.append("kind = %s"); params.append(kind)
        if tag:
            clauses.append("tags ? %s"); params.append(tag)
        if status:
            clauses.append("status = %s"); params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM kf_claims")
                total = cur.fetchone()[0]
                cur.execute(
                    f"""
                    SELECT claim_id, kind, title, body, tags, receipt,
                           falsifier, status, actor, created_at
                    FROM kf_claims {where}
                    ORDER BY created_at DESC LIMIT %s
                    """, (*params, limit))
                rows = [self._claim_row(r) for r in cur.fetchall()]
        return {"claims": rows, "matched": len(rows), "corpus_total": total,
                "matcher": "ILIKE substring v1 — not semantic; absence of a "
                           "match is not absence of knowledge",
                "version": KNOWLEDGE_VERSION}

    def neighborhood(self, claim_id: str, depth: int = 2,
                     limit: int = 100) -> dict[str, Any]:
        """The graph query: everything within ``depth`` hops, both directions."""
        depth = max(1, min(int(depth), 4))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM kf_claims WHERE claim_id=%s", (claim_id,))
                if cur.fetchone() is None:
                    raise KnowledgeError(f"no such claim {claim_id!r}")
                cur.execute(
                    """
                    WITH RECURSIVE hops AS (
                        SELECT %s::text AS cid, 0 AS d
                        UNION
                        SELECT CASE WHEN e.from_id = h.cid THEN e.to_id
                                    ELSE e.from_id END, h.d + 1
                        FROM kf_edges e
                        JOIN hops h ON h.cid IN (e.from_id, e.to_id)
                        WHERE h.d < %s
                    )
                    SELECT DISTINCT cid FROM hops LIMIT %s
                    """, (claim_id, depth, limit))
                ids = [r[0] for r in cur.fetchall()]
                cur.execute(
                    """
                    SELECT claim_id, kind, title, body, tags, receipt,
                           falsifier, status, actor, created_at
                    FROM kf_claims WHERE claim_id = ANY(%s)
                    """, (ids,))
                nodes = [self._claim_row(r) for r in cur.fetchall()]
                cur.execute(
                    """
                    SELECT from_id, to_id, rel, note FROM kf_edges
                    WHERE from_id = ANY(%s) AND to_id = ANY(%s)
                    """, (ids, ids))
                edges = [{"from": r[0], "to": r[1], "rel": r[2], "note": r[3]}
                         for r in cur.fetchall()]
        return {"center": claim_id, "depth": depth, "nodes": nodes,
                "edges": edges,
                "truncated": len(ids) >= limit,
                "version": KNOWLEDGE_VERSION}

    @staticmethod
    def _claim_row(r) -> dict[str, Any]:
        return {"claim_id": r[0], "kind": r[1], "title": r[2], "body": r[3],
                "tags": r[4] if isinstance(r[4], list) else json.loads(r[4] or "[]"),
                "receipt": r[5], "falsifier": r[6], "status": r[7],
                "actor": r[8],
                "created_at": r[9].isoformat() if r[9] else None}

    # ------------------------------------------------------------- render --
    def render_book(self, kind: str) -> str:
        """A markdown book as a VIEW of the rows — generated, never edited."""
        found = self.search(kind=kind, limit=500)
        lines = [f"# {kind} — rendered from the knowledge graph "
                 f"({_now().date().isoformat()})",
                 "",
                 "GENERATED FILE — edit the graph, never this file. "
                 f"{KNOWLEDGE_VERSION}.", ""]
        for c in found["claims"]:
            flag = "" if c["status"] == "active" else f" **[{c['status'].upper()}]**"
            lines.append(f"## {c['title']}{flag}")
            if c["body"]:
                lines.append(c["body"])
            lines.append(f"*receipt*: {c['receipt']}")
            if c["falsifier"]:
                lines.append(f"*falsifier*: {c['falsifier']}")
            if c["tags"]:
                lines.append(f"*tags*: {', '.join(c['tags'])}")
            lines.append("")
        return "\n".join(lines)
