"""What an observation led to — the only thing that can settle the map's shape.

Every judgement about what to surface is currently taste. We cannot say whether
the liquidity cluster is the market having one story or the extractor
preferring one kind of sentence, so we cannot fix it with evidence, so we argue
about it instead. This is the link that ends that argument: record which
observations motivated a candidate, and what became of the candidate.

Then the question answers itself. If no liquidity observation has ever led to
something that cleared the bar, the skew is an artifact and the extractor needs
changing. If they are the only ones that do, the map is right and the empty
margin region matters less than it looks.

The second half is quieter and matters as much: recording what a human LOOKED
AT and passed on. Under a laziness assumption a dismissal and an unread are
indistinguishable by behaviour — both are simply absent — so a dismissal has to
be DECLARED rather than inferred. An inferred exclusion hardens silently into a
blind spot; a declared one can be revisited, and shows up in the legend as a
choice somebody made.

Cheap now, impossible later. None of this can be reconstructed after the fact,
because it only exists at the moment of use.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
-- What a human did with an observation they actually saw.
CREATE TABLE IF NOT EXISTS fund_observation_reviews (
    observation_id TEXT PRIMARY KEY,
    outcome        TEXT        NOT NULL,
    note           TEXT,
    actor          TEXT        NOT NULL DEFAULT 'operator',
    reviewed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which observations motivated which candidate. Many-to-many on purpose: a
-- hypothesis usually comes from noticing two things at once, and recording
-- only the "main" one would lose the pattern that actually prompted it.
CREATE TABLE IF NOT EXISTS fund_candidate_sources (
    candidate_id   TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    linked_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (candidate_id, observation_id)
);

CREATE INDEX IF NOT EXISTS fund_candidate_sources_obs_idx
    ON fund_candidate_sources (observation_id);
"""

#: What a reviewer can say. Deliberately short — a long list invites people to
#: agonise over which box, and the only distinction that matters downstream is
#: whether the observation led anywhere.
OUTCOMES = ("acted", "interesting", "dismissed", "not_relevant")


class Provenance:
    """The trail from a filing sentence to a verdict."""

    def __init__(self, dsn_str: Optional[str] = None):
        from app.fund.pgstore import dsn
        self._dsn = dsn_str or dsn()
        self._ensure_schema()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    # --- recording ----------------------------------------------------------

    def review(self, observation_id: str, outcome: str,
               note: Optional[str] = None, actor: str = "operator") -> dict[str, Any]:
        """Record that a human saw this and decided something.

        Re-reviewing overwrites: a later opinion supersedes an earlier one, and
        keeping both would make "what does the operator think of this" a
        question with two answers.
        """
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO fund_observation_reviews "
                    "(observation_id, outcome, note, actor) VALUES (%s,%s,%s,%s) "
                    "ON CONFLICT (observation_id) DO UPDATE SET "
                    "outcome = EXCLUDED.outcome, note = EXCLUDED.note, "
                    "actor = EXCLUDED.actor, reviewed_at = now()",
                    (observation_id, outcome, note, actor))
            conn.commit()
        return {"observation_id": observation_id, "outcome": outcome}

    def link(self, candidate_id: str, observation_ids: list[str]) -> dict[str, Any]:
        """Record which observations motivated a candidate.

        Linking also marks them acted, because it would be strange to say "this
        prompted a hypothesis" and separately have to say "and I read it".
        """
        ids = [i for i in (observation_ids or []) if i]
        if not ids:
            return {"linked": 0}
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO fund_candidate_sources (candidate_id, observation_id) "
                    "VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    [(candidate_id, i) for i in ids])
                cur.executemany(
                    "INSERT INTO fund_observation_reviews (observation_id, outcome) "
                    "VALUES (%s,'acted') ON CONFLICT (observation_id) DO UPDATE "
                    "SET outcome = 'acted', reviewed_at = now()",
                    [(i,) for i in ids])
            conn.commit()
        return {"candidate_id": candidate_id, "linked": len(ids)}

    # --- the question this exists to answer ---------------------------------

    def yield_by_category(self) -> dict[str, Any]:
        """Which kinds of observation actually lead anywhere.

        The report that settles the liquidity argument. Reads the whole chain —
        observation to review to candidate to verdict — and reports, per
        category, how many were seen, how many a human acted on, and how many
        of those produced something that cleared the bar.

        A category with many observations and no passes is a category the
        extractor is good at finding and nobody can use.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT o.category,
                           count(*)                                   AS observed,
                           count(r.observation_id)                    AS reviewed,
                           count(*) FILTER (WHERE r.outcome = 'acted') AS acted,
                           count(DISTINCT s.candidate_id)             AS candidates,
                           count(DISTINCT s.candidate_id)
                               FILTER (WHERE c.passed)                AS passed
                    FROM fund_observations o
                    LEFT JOIN fund_observation_reviews r
                           ON r.observation_id = o.observation_id
                    LEFT JOIN fund_candidate_sources s
                           ON s.observation_id = o.observation_id
                    LEFT JOIN fund_candidates c
                           ON c.candidate_id = s.candidate_id
                    GROUP BY o.category
                    ORDER BY count(*) DESC
                """)
                rows = cur.fetchall()

        out = []
        for cat, observed, reviewed, acted, candidates, passed in rows:
            out.append({
                "category": cat,
                "observed": int(observed or 0),
                "reviewed": int(reviewed or 0),
                "unreviewed": int(observed or 0) - int(reviewed or 0),
                "acted": int(acted or 0),
                "candidates": int(candidates or 0),
                "passed_gate": int(passed or 0),
                "verdict": _category_verdict(observed, reviewed, acted, passed),
            })
        return {"by_category": out, "note": _overall_note(out)}

    def unreviewed(self, limit: int = 50) -> list[dict[str, Any]]:
        """Seen by nobody. Distinct from seen-and-passed-on, which is a decision."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT o.observation_id, o.ticker, o.category, o.filed,
                           o.observation
                    FROM fund_observations o
                    LEFT JOIN fund_observation_reviews r
                           ON r.observation_id = o.observation_id
                    WHERE r.observation_id IS NULL
                    ORDER BY o.filed DESC LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
        return [{"observation_id": r[0], "ticker": r[1], "category": r[2],
                 "filed": r[3].isoformat(), "observation": r[4]} for r in rows]

    def trail(self, candidate_id: str) -> list[dict[str, Any]]:
        """What prompted this candidate — the audit trail, backwards."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT o.ticker, o.category, o.filed, o.observation,
                           o.quote, o.url
                    FROM fund_candidate_sources s
                    JOIN fund_observations o ON o.observation_id = s.observation_id
                    WHERE s.candidate_id = %s
                    ORDER BY o.filed DESC
                """, (candidate_id,))
                rows = cur.fetchall()
        return [{"ticker": r[0], "category": r[1], "filed": r[2].isoformat(),
                 "observation": r[3], "quote": r[4], "url": r[5]} for r in rows]


def _category_verdict(observed: int, reviewed: int, acted: int,
                      passed: Optional[int]) -> str:
    observed, reviewed, acted, passed = (int(observed or 0), int(reviewed or 0),
                                         int(acted or 0), int(passed or 0))
    if reviewed == 0:
        return ("nobody has looked at any of these yet — no evidence either way, "
                "which is different from evidence of nothing")
    if passed:
        return f"{passed} candidate(s) from this category cleared the bar"
    if acted:
        return (f"{acted} acted on, none cleared the bar yet — worth watching "
                f"before concluding anything")
    return (f"{reviewed} looked at, none acted on — the extractor finds these "
            f"readily and so far nobody can use them")


def _overall_note(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "no observations yet"
    total = sum(r["observed"] for r in rows)
    reviewed = sum(r["reviewed"] for r in rows)
    if reviewed == 0:
        return (f"{total} observations, none reviewed. Until some are, the map's "
                f"shape is a matter of taste — nothing here can yet say whether "
                f"a big category is signal or an artifact of how we extract")
    passed = sum(r["passed_gate"] for r in rows)
    return (f"{reviewed} of {total} observations reviewed, {passed} candidate(s) "
            f"through the gate — enough to start asking which categories pay")
