"""The knowledge graph — every hypothesis this firm has tested, and what killed it.

Designed in ``docs/research/KNOWLEDGE_GRAPH_V1_2026-08-23.md``; this is v1 of
that design. Three tables, four readers, one mutation path.

**IT NEVER GATES, AND THAT IS A STRUCTURAL CLAIM, NOT AN INTENTION.** No
threshold reads this module, the gate does not consult it, and nothing on a
decision path imports it — ``tests/test_knowledge_isolation.py`` walks the AST
of every module under ``app/`` and fails if one appears. The graph shapes what
Ed PROPOSES and what a chair puts in a BRIEF; it is work layer, one commit to
revert, and the control layer may not grow a dependency on it without a
versioned human decision.

WHAT IT IS FOR. Four questions, each of which the firm has been answering from
memory:

  1. ``family_ledger(family)`` — how many variants of this family were EVER
     tested and what killed each. Ed's grammar header needs a family count for
     the family-wise discovery correction; today that number comes from recall.
     An untested family reads UNTESTED, never zero.
  2. ``prediction_calibration(seat)`` — pre-committed numbers against measured
     ones. The leading indicator made queryable.
  3. ``kill_taxonomy()`` — recurring death causes ranked by frequency and by
     the container cost paid before the kill landed.
  4. ``cheap_kills()`` — which instrument killed which family, at what cost, so
     the historically lethal cheap instrument runs FIRST.

THREE RULES INHERITED AT BIRTH, each enforced rather than documented:

  * **Every row cites a run.** ``run_id`` / ``cited_run`` are NOT NULL in the
    schema AND rejected when blank in Python — a NOT NULL column happily
    accepts ``''``, and an empty citation is the same lie as an absent one.
    The graph is an INDEX OVER THE RECORD, never a second record.
  * **Outcomes are immutable except by voiding.** ``void_outcome`` is the only
    mutation path and a Postgres trigger enforces it: any other UPDATE and any
    DELETE raise. A re-measurement is a NEW row. This is the findings-are-never-
    edited rule with a foreign key on it. A convention that only the author
    honours is the unwired-kill-switch pattern, so the guard is in the database.
  * **Absence renders as absence.** A prediction with no measured counterpart
    is NULL and the calibration reader says "n of m scoreable"; an outcome whose
    container cost cannot be attributed reports the reason, never 0.0; a family
    with no rows reads UNTESTED.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# --- vocabularies ---------------------------------------------------------

#: Where a hypothesis came from. Closed set, per the design.
#:
#: NULLABLE in the schema and that is deliberate: a pre-grammar candidate
#: recovered by the backfill has no recorded source, and picking one of these
#: four for it would be a reconstructed guess. NULL reads "not stated".
SOURCES = ("menu", "shelf-lead", "kill-descendant", "paper")

#: Where in the chain a verdict was reached.
STAGES = ("adversary", "belt", "gate", "deploy")

#: What a stage concluded. ``voided`` is terminal and is only ever reached
#: through :meth:`KnowledgeGraph.void_outcome`.
VERDICTS = ("kill", "survives", "pass", "fail", "cannot_tell", "voided")

#: The verdict that excludes a row from every comparison query.
VOIDED = "voided"

#: Verdicts that mean the hypothesis died at this stage.
KILL_VERDICTS = ("kill", "fail")

#: Verdicts that mean it lived through this stage.
SURVIVE_VERDICTS = ("survives", "pass")

#: Edge kinds, per the design.
EDGE_KINDS = ("descendant_of_kill", "same_family", "prior_art",
              "control_kills", "supersedes")

#: How a row got here. ``grammar`` = written by a seat under the grammar
#: header; ``backfill`` = recovered from stored verdicts, best effort, partial.
#: They are NEVER silently mixed: every reader reports the split.
PROVENANCES = ("grammar", "backfill")

#: How a container cost was attributed to an outcome. Named rather than left as
#: a bare number, because three of these four mean "the number is absent" and
#: they are absent for different reasons.
#:
#:   exclusive   no other candidate of the same algorithm shared the window, so
#:               the containers in it are this candidate's and only this one's.
#:   ambiguous   a sibling ran concurrently on the same algorithm. MEASURED
#:               2026-08-23: 20 of 41 live candidates. Dividing the seconds
#:               between them would invent an allocation; the cost is reported
#:               ABSENT with this basis.
#:   no_jobs     the window contains no stored container at all — five 2026-08-16/17
#:               candidates predate `fund_lean_jobs`. Not zero cost; unrecorded cost.
#:   unmeasured  nobody looked.
#:
#: Reproduce the two counts:
#:   ./venv/Scripts/python.exe scripts/kg/backfill.py --run-id <id> --dry-run
COST_BASES = ("exclusive", "ambiguous", "no_jobs", "unmeasured")

#: How many times a death cause must recur before it earns a pre-flight card
#: item. From the design doc ("when a cause recurs three times"). A WORK-LAYER
#: number: it changes what a brief says, never what a gate does.
PREFLIGHT_CARD_RECURRENCE = 3

#: The bucket a kill sentence lands in when no rule matches it. Counted and
#: reported with its verbatim text on every taxonomy read — an unrecognised
#: cause must send someone to look, not vanish into the modal one.
UNCLASSIFIED_KILL_SLUG = "unclassified"

#: Ordered (slug, pattern) rules mapping a gate failure sentence to a stable
#: slug. FIRST MATCH WINS, so the order is part of the specification.
#:
#: Deliberately a LOCAL table matched against STORED TEXT rather than an import
#: from ``gate.py``. Two reasons: the stored sentences are history and must keep
#: their slugs even after the gate rewords itself, and this module must not
#: import a control-layer module in either direction. The patterns were written
#: against ``app/fund/gate.py`` as of 2026-08-23 and against all 41 stored
#: verdicts; the backfill prints the unclassified count so drift is visible.
KILL_REASON_RULES: tuple[tuple[str, str], ...] = (
    ("not_priced", r"^not priced:"),
    ("too_few_fills", r"^only \S+ fills;"),
    ("psr_below_floor", r"^probabilistic Sharpe "),
    ("benchmark_absent", r"^no benchmark to compare against"),
    ("benchmark_not_beaten", r"^returns .* for simply owning it"),
    ("holdout_dates_ignored", r"^the held-out test ran the SAME dates twice"),
    ("holdout_no_trades", r"^the held-out test placed no trades at all"),
    ("holdout_retention_unmeasurable",
     r"^the held-out retention could not be measured"),
    ("holdout_absent", r"^no held-out test"),
    ("holdout_retention_below_floor",
     r"^kept only .* of its edge out of sample"),
    ("cost_tested_range_unreadable",
     r"^the cost sweep says the edge survived every cost it tested"),
    ("cost_grid_too_narrow", r"^cost robustness was tested only to"),
    ("cost_robustness_unmeasured", r"^cost robustness was never measured"),
    ("breakeven_below_floor", r"^dies at .*bps of slippage"),
    ("capacity_unmeasured", r"^capacity was never estimated"),
    ("capacity_below_floor", r"^capacity \$"),
    ("walkforward_absent", r"^no walk-forward test"),
    ("not_testable_on_history", r"^NOT TESTABLE on the history available"),
    ("walkforward_folds_unmeasurable",
     r"^only \S+ fold\(s\) could be measured"),
    ("walkforward_minority_folds",
     r"^kept its edge in only \d+ of \d+ independent folds"),
)

_COMPILED_KILL_RULES = tuple(
    (slug, re.compile(pat)) for slug, pat in KILL_REASON_RULES)


def slug_for_kill(verbatim: Any) -> str:
    """The stable slug for one death sentence, or ``unclassified``.

    Never returns None for a non-empty sentence: a cause the table does not
    recognise is still a cause, and burying it would make the taxonomy claim a
    completeness it does not have.
    """
    text = (verbatim or "").strip() if isinstance(verbatim, str) else ""
    if not text:
        return UNCLASSIFIED_KILL_SLUG
    for slug, rx in _COMPILED_KILL_RULES:
        if rx.search(text):
            return slug
    return UNCLASSIFIED_KILL_SLUG


SCHEMA = """
-- ONE ROW PER PROPOSAL — the grammar header, persisted.
--
-- Every optional field is genuinely NULLABLE and NULL means "not stated".
-- Backfilled pre-grammar rows carry NULLs across most of the header rather
-- than a reconstruction: a mechanism sentence invented for a 2026-08-17
-- candidate would read exactly like one a seat wrote, and the graph would then
-- be a second record instead of an index over the first.
CREATE TABLE IF NOT EXISTS kg_hypothesis (
    id            TEXT PRIMARY KEY,
    family        TEXT        NOT NULL,
    mechanism     TEXT,
    counterparty  TEXT,
    claim_type    TEXT,
    entities      JSONB,
    observable    TEXT,
    horizon       TEXT,
    predictions   JSONB,
    falsifier     TEXT,
    source        TEXT,
    source_ref    TEXT,
    provenance    TEXT        NOT NULL DEFAULT 'grammar',
    proposed_at   TIMESTAMPTZ,
    -- MANDATORY CITATION. Design rule 1: a graph entry without a run is
    -- inadmissible. NOT NULL is half the enforcement — the other half is in
    -- Python, because NOT NULL accepts the empty string.
    run_id        TEXT        NOT NULL,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT kg_hypothesis_run_id_nonblank CHECK (btrim(run_id) <> ''),
    CONSTRAINT kg_hypothesis_family_nonblank CHECK (btrim(family) <> ''),
    CONSTRAINT kg_hypothesis_provenance CHECK (provenance IN ('grammar','backfill')),
    CONSTRAINT kg_hypothesis_source CHECK (
        source IS NULL OR source IN ('menu','shelf-lead','kill-descendant','paper'))
);

CREATE INDEX IF NOT EXISTS kg_hypothesis_family_idx
    ON kg_hypothesis (family, proposed_at DESC);
CREATE INDEX IF NOT EXISTS kg_hypothesis_run_idx ON kg_hypothesis (run_id);

-- ONE ROW PER JUDGEMENT. A gate verdict with four failure sentences is ONE
-- judgement, not four: `kill_reasons` holds the ordered list and the singular
-- columns are DERIVED from its head at write time. Two columns holding the
-- same fact drift; one derived from the other cannot.
CREATE TABLE IF NOT EXISTS kg_outcome (
    outcome_id           BIGSERIAL PRIMARY KEY,
    hypothesis_id        TEXT NOT NULL REFERENCES kg_hypothesis(id),
    stage                TEXT NOT NULL,
    verdict              TEXT NOT NULL,
    kill_reason_slug     TEXT,
    kill_reason_verbatim TEXT,
    kill_reasons         JSONB,
    killing_instrument   TEXT,
    measured             JSONB,
    container_seconds    NUMERIC,
    container_cost_basis TEXT,
    provenance           TEXT NOT NULL DEFAULT 'grammar',
    cited_run            TEXT NOT NULL,
    at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- THE VOID TRAIL. Clean-field guard rail 2: the value being replaced is
    -- preserved beside the new one, never erased.
    voided_from          TEXT,
    void_reason          TEXT,
    voided_at            TIMESTAMPTZ,
    voided_by_run        TEXT,
    -- Natural key for idempotent ingestion. NULL for seat-written rows, and
    -- Postgres treats NULLs as distinct in a UNIQUE index, so many may coexist.
    dedupe_key           TEXT,
    CONSTRAINT kg_outcome_cited_run_nonblank CHECK (btrim(cited_run) <> ''),
    CONSTRAINT kg_outcome_stage CHECK (stage IN ('adversary','belt','gate','deploy')),
    CONSTRAINT kg_outcome_verdict CHECK (
        verdict IN ('kill','survives','pass','fail','cannot_tell','voided')),
    CONSTRAINT kg_outcome_provenance CHECK (provenance IN ('grammar','backfill')),
    CONSTRAINT kg_outcome_cost_basis CHECK (
        container_cost_basis IS NULL
        OR container_cost_basis IN ('exclusive','ambiguous','no_jobs','unmeasured'))
);

CREATE UNIQUE INDEX IF NOT EXISTS kg_outcome_dedupe_idx
    ON kg_outcome (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS kg_outcome_hyp_idx ON kg_outcome (hypothesis_id, at);
CREATE INDEX IF NOT EXISTS kg_outcome_slug_idx
    ON kg_outcome (kill_reason_slug) WHERE kill_reason_slug IS NOT NULL;

CREATE TABLE IF NOT EXISTS kg_edge (
    edge_id     BIGSERIAL PRIMARY KEY,
    from_id     TEXT NOT NULL REFERENCES kg_hypothesis(id),
    to_id       TEXT NOT NULL REFERENCES kg_hypothesis(id),
    kind        TEXT NOT NULL,
    note        TEXT,
    cited_run   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    dedupe_key  TEXT,
    CONSTRAINT kg_edge_kind CHECK (kind IN (
        'descendant_of_kill','same_family','prior_art','control_kills','supersedes')),
    CONSTRAINT kg_edge_not_self CHECK (from_id <> to_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS kg_edge_dedupe_idx
    ON kg_edge (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS kg_edge_from_idx ON kg_edge (from_id, kind);
CREATE INDEX IF NOT EXISTS kg_edge_to_idx   ON kg_edge (to_id, kind);

-- IMMUTABILITY, ENFORCED IN THE DATABASE RATHER THAN PROMISED IN A DOCSTRING.
--
-- The design's rule is "VOIDED cascades ... no UPDATE of measured values,
-- ever; a re-measurement is a NEW outcome row". A rule that lives only in the
-- one function that honours it is the unwired-kill-switch pattern: the next
-- caller writes its own UPDATE and nothing notices. So the guard sits under
-- every writer, including a psql session and a future module.
--
-- TRUNCATE deliberately still works: it is a row-level trigger, and the test
-- suite's cleanup is not a mutation of a finding.
CREATE OR REPLACE FUNCTION kg_outcome_guard() RETURNS trigger AS $kgguard$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'kg_outcome rows are never deleted — a finding that '
            'turned out wrong is VOIDED, which keeps it visible and cited';
    END IF;
    IF OLD.verdict = 'voided' THEN
        RAISE EXCEPTION 'outcome % is already voided — re-voiding would '
            'overwrite the reason and the run that voided it', OLD.outcome_id;
    END IF;
    IF NEW.verdict IS DISTINCT FROM 'voided' THEN
        RAISE EXCEPTION 'the only permitted UPDATE on kg_outcome is void_outcome '
            '(verdict -> voided); a re-measurement is a NEW row';
    END IF;
    IF NEW.hypothesis_id  IS DISTINCT FROM OLD.hypothesis_id
    OR NEW.stage          IS DISTINCT FROM OLD.stage
    OR NEW.measured       IS DISTINCT FROM OLD.measured
    OR NEW.kill_reason_slug     IS DISTINCT FROM OLD.kill_reason_slug
    OR NEW.kill_reason_verbatim IS DISTINCT FROM OLD.kill_reason_verbatim
    OR NEW.kill_reasons         IS DISTINCT FROM OLD.kill_reasons
    OR NEW.killing_instrument   IS DISTINCT FROM OLD.killing_instrument
    OR NEW.container_seconds    IS DISTINCT FROM OLD.container_seconds
    OR NEW.container_cost_basis IS DISTINCT FROM OLD.container_cost_basis
    OR NEW.provenance     IS DISTINCT FROM OLD.provenance
    OR NEW.cited_run      IS DISTINCT FROM OLD.cited_run
    OR NEW.at             IS DISTINCT FROM OLD.at
    OR NEW.dedupe_key     IS DISTINCT FROM OLD.dedupe_key THEN
        RAISE EXCEPTION 'voiding may not alter a stored measurement — every '
            'field except the void trail must survive the flip unchanged';
    END IF;
    IF NEW.voided_from IS DISTINCT FROM OLD.verdict THEN
        RAISE EXCEPTION 'voided_from must preserve the verdict being replaced '
            '(clean-field rule: annotate, never erase)';
    END IF;
    RETURN NEW;
END;
$kgguard$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS kg_outcome_immutable ON kg_outcome;
CREATE TRIGGER kg_outcome_immutable
    BEFORE UPDATE OR DELETE ON kg_outcome
    FOR EACH ROW EXECUTE FUNCTION kg_outcome_guard();
"""


class SchemaAbsent(RuntimeError):
    """The ``kg_*`` tables do not exist in the store this reader was pointed at.

    Raised instead of returning an empty result, because "the graph has no
    kills" and "the graph has never been created here" are different facts and
    only one of them is a statement about the fund. Before the reader/writer
    split a reader could not hit this — it created the tables on the way past,
    which is how a read-only report came to hold an ACCESS EXCLUSIVE lock.
    """


def _cite(value: Any, field: str) -> str:
    """A citation, or a refusal.

    NOT NULL alone would accept ``''`` and ``'   '``, and a blank citation is
    indistinguishable downstream from a real one that happens to be empty. The
    design calls an uncited row inadmissible; this is where it is made so.
    """
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError(
            f"{field} is mandatory — the graph is an index over the record, "
            f"so a row that cannot name the run it came from is inadmissible "
            f"(got {value!r})")
    return text


def _slugify(raw: Any, field: str) -> str:
    text = raw.strip().lower() if isinstance(raw, str) else ""
    if not text:
        raise ValueError(f"{field} is mandatory and may not be blank")
    slug = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if not slug:
        # e.g. "!!!" — non-empty input that canonicalises to nothing. Raised
        # here rather than left to the CHECK constraint so the caller gets the
        # field name and its own value back.
        raise ValueError(
            f"{field}={raw!r} contains no slug-able characters — a family that "
            f"canonicalises to the empty string would merge with every other "
            f"such family")
    return slug


def _clean_reasons(reasons: Any) -> Optional[list[dict[str, str]]]:
    """The ordered death sentences for one judgement, each with its slug.

    Accepts a list of strings (verbatim sentences) or of dicts already carrying
    a slug. Returns None — not [] — when there are none, because an empty list
    would read as "we looked and there were no reasons" on a row that survived.
    """
    if not reasons:
        return None
    out: list[dict[str, str]] = []
    for r in reasons:
        if isinstance(r, dict):
            verbatim = str(r.get("verbatim") or "").strip()
            slug = str(r.get("slug") or "").strip() or slug_for_kill(verbatim)
        else:
            verbatim = str(r or "").strip()
            slug = slug_for_kill(verbatim)
        if verbatim or slug != UNCLASSIFIED_KILL_SLUG:
            out.append({"slug": slug, "verbatim": verbatim})
    return out or None


def _unclassified_block(slot: Optional[dict[str, Any]],
                        checked: int) -> dict[str, Any]:
    """The taxonomy's unclassified report — ALWAYS a block, never None.

    Three states the caller must be able to tell apart, and v1 collapsed two of
    them into ``None``:

      * ``n > 0``    — sentences no rule matched. Go and look.
      * ``n == 0``, ``checked > 0`` — every stored sentence matched. A real,
        earned zero, and worth printing: it is the evidence that
        KILL_REASON_RULES still covers the gate's vocabulary.
      * ``n == 0``, ``checked == 0`` — NOTHING WAS CHECKED. No kill outcome is
        stored, so the classifier never ran. Reporting this as a clean sweep is
        the "absence is never zero" rule broken at the one place the module
        exists to notice drift.
    """
    n = slot["n"] if slot else 0
    if n:
        note = ("kill sentences no rule in KILL_REASON_RULES matched — either "
                "the gate reworded itself or a new cause exists. Reported "
                "rather than folded into the modal cause.")
    elif checked:
        note = (f"0 unclassified — every sentence matched: all {checked} "
                f"stored kill sentence(s) were classified by a rule in "
                f"KILL_REASON_RULES.")
    else:
        note = ("0 unclassified because NOTHING WAS CHECKED — no kill outcome "
                "is stored, so the classifier has not run. This is an empty "
                "graph, not a clean sweep.")
    return {"n": n,
            "checked": checked,
            "example_verbatim": slot["example_verbatim"] if slot else None,
            "note": note}


def _num(x: Any) -> Optional[float]:
    """A finite float, or None. Booleans are NOT numbers here."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


class KnowledgeGraph:
    """Reader/writer over the three ``kg_*`` tables.

    **CONSTRUCTING ONE ISSUES NO DDL AND TAKES NO LOCK.** v1 called ``_ensure()``
    from ``__init__``, so every reader — including ``scripts/kg/report.py``,
    which only ever SELECTs — ran the whole ``SCHEMA`` string on the way past.
    That wedged ``kg_outcome`` for ~5 minutes behind one ordinary transaction
    during the validator's spot-audit (run-validator-parity, 2026-08-23).

    MEASURED, not reasoned about (``scratchpad/d27probe_lock2.py``, one
    connection holding a plain ``SELECT count(*) FROM kg_outcome`` open):

        CREATE TABLE IF NOT EXISTS kg_outcome ...      free, 0.03s
        CREATE INDEX IF NOT EXISTS kg_outcome_hyp_idx  free, 0.03s
        CREATE OR REPLACE FUNCTION kg_outcome_guard    free, 0.03s
        DROP TRIGGER IF EXISTS kg_outcome_immutable    BLOCKED  <-- the wedge
        (SELECT-only reader path)                      free, 0.03s

    So one statement of the five takes ACCESS EXCLUSIVE, and it is the one the
    immutability guard needs. It stays exactly where it is — the fix is that
    only a WRITER pays for it:

      * readers go through :meth:`_read`, which is SELECT-only and raises
        :class:`SchemaAbsent` on a store where the tables were never created;
      * every write calls :meth:`ensure_schema`, memoised per instance, so a
        backfill of 41 candidates issues the DDL once and not forty-one times.

    Never instantiate at import time: ``pgstore.dsn()`` resolves to the LIVE
    database in a unit-test process. That hazard is smaller than it was — a
    construction no longer writes anything — but a module-level instance would
    still hold a DSN nobody chose.
    """

    def __init__(self, dsn: Optional[str] = None):
        from app.fund.pgstore import dsn as default_dsn
        self._dsn = dsn or default_dsn()
        self._ensured = False

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def ensure_schema(self) -> bool:
        """Issue the DDL. THE ONLY PLACE THIS MODULE TAKES A WRITE LOCK.

        Idempotent in Postgres and memoised here: returns True the first time
        this instance ran it, False every time after. The memo is per-instance
        and deliberately not per-process — two graphs pointed at two databases
        must each create their own.

        Callers are the four writers and ``scripts/kg/backfill.py``. A READER
        must never call it; ``tests/test_knowledge.py`` holds an open
        transaction and proves the read path completes while this one does not.
        """
        if self._ensured:
            return False
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()
        self._ensured = True
        return True

    def _read(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Every SELECT this module makes against a ``kg_*`` table.

        SELECT-only by construction. An absent table surfaces as
        :class:`SchemaAbsent` rather than as an empty list, because a reader
        that answers "0 kills" for a store it has never been ingested into is
        reporting absence as zero.
        """
        import psycopg
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
        except psycopg.errors.UndefinedTable as e:
            raise SchemaAbsent(
                f"the kg_* tables do not exist in this store — nothing has "
                f"been ingested here, which is NOT the same as a graph with no "
                f"rows. Run scripts/kg/backfill.py, or call ensure_schema() if "
                f"you meant to create them ({e})") from e

    # --- writes -----------------------------------------------------------

    def add_hypothesis(self, *, family: str, run_id: str,
                       id: Optional[str] = None,
                       mechanism: Optional[str] = None,
                       counterparty: Optional[str] = None,
                       claim_type: Optional[str] = None,
                       entities: Optional[Iterable[str]] = None,
                       observable: Optional[str] = None,
                       horizon: Optional[str] = None,
                       predictions: Optional[dict[str, Any]] = None,
                       falsifier: Optional[str] = None,
                       source: Optional[str] = None,
                       source_ref: Optional[str] = None,
                       provenance: str = "grammar",
                       proposed_at: Optional[str] = None,
                       on_conflict: str = "raise") -> dict[str, Any]:
        """One proposal, header intact. ``run_id`` is mandatory and validated.

        ``on_conflict='ignore'`` makes ingestion idempotent — the backfill can
        be re-run after a merge without duplicating the graph. It returns
        ``created: False`` rather than pretending it wrote.
        """
        cited = _cite(run_id, "run_id")
        fam = _slugify(family, "family")
        if source is not None and source not in SOURCES:
            raise ValueError(
                f"source must be one of {SOURCES} or absent, got {source!r} — "
                "refused rather than nulled, because a mistyped source that "
                "became 'not stated' would hide where an idea came from")
        if provenance not in PROVENANCES:
            raise ValueError(f"provenance must be one of {PROVENANCES}")
        hid = (id or "").strip() or f"kg-{uuid.uuid4().hex[:12]}"
        self.ensure_schema()
        conflict = ("ON CONFLICT (id) DO NOTHING"
                    if on_conflict == "ignore" else "")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO kg_hypothesis
                        (id, family, mechanism, counterparty, claim_type,
                         entities, observable, horizon, predictions, falsifier,
                         source, source_ref, provenance, proposed_at, run_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    {conflict}
                    RETURNING id
                    """,
                    (hid, fam, mechanism, counterparty, claim_type,
                     json.dumps(list(entities)) if entities is not None else None,
                     observable, horizon,
                     json.dumps(predictions) if predictions is not None else None,
                     falsifier, source, source_ref, provenance, proposed_at,
                     cited))
                row = cur.fetchone()
            conn.commit()
        return {"id": hid, "family": fam, "created": row is not None}

    def add_outcome(self, *, hypothesis_id: str, stage: str, verdict: str,
                    cited_run: str,
                    kill_reasons: Optional[Iterable[Any]] = None,
                    killing_instrument: Optional[str] = None,
                    measured: Optional[dict[str, Any]] = None,
                    container_seconds: Optional[float] = None,
                    container_cost_basis: Optional[str] = None,
                    provenance: str = "grammar",
                    at: Optional[str] = None,
                    dedupe_key: Optional[str] = None,
                    on_conflict: str = "raise") -> dict[str, Any]:
        """One judgement. The singular kill columns are DERIVED, never passed.

        Callers supply ``kill_reasons`` (the ordered sentences) and the head of
        that list becomes ``kill_reason_slug`` / ``kill_reason_verbatim``. Two
        columns that must agree with a third are two chances to disagree; a
        derivation cannot drift.

        ``verdict='voided'`` is REFUSED here. A row is voided by
        :meth:`void_outcome`, which records who voided it and what it said
        before — writing one straight in would create a void with no trail.
        """
        cited = _cite(cited_run, "cited_run")
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}, got {stage!r}")
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
        if verdict == VOIDED:
            raise ValueError(
                "an outcome may not be written as voided — void_outcome() is "
                "the only path, because a void with no prior verdict and no "
                "reason erases exactly what the void is supposed to preserve")
        if provenance not in PROVENANCES:
            raise ValueError(f"provenance must be one of {PROVENANCES}")
        if (container_cost_basis is not None
                and container_cost_basis not in COST_BASES):
            raise ValueError(
                f"container_cost_basis must be one of {COST_BASES} or absent")
        secs = _num(container_seconds)
        if container_seconds is not None and secs is None:
            # UNREADABLE IS NOT ABSENT. Silently nulling a cost the caller
            # tried to state would put "no attributable cost" on a row whose
            # cost somebody measured and mistyped.
            raise ValueError(
                f"container_seconds must be a finite number or absent, got "
                f"{container_seconds!r} — refused rather than nulled")
        if secs is not None and container_cost_basis in (None, "ambiguous",
                                                         "no_jobs", "unmeasured"):
            raise ValueError(
                f"a container cost of {secs} cannot carry basis "
                f"{container_cost_basis!r} — a number whose attribution is "
                "unknown or shared is not this outcome's cost. The live worst "
                "case is candidate 14c0af2073d5: 205 containers and 25,043 "
                "seconds in a window that overlaps EIGHT siblings of the same "
                "algorithm, so accepting it would bill 25,043s nine times.")
        reasons = _clean_reasons(kill_reasons)
        head = reasons[0] if reasons else None
        self.ensure_schema()
        conflict = ("ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING"
                    if on_conflict == "ignore" and dedupe_key else "")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO kg_outcome
                        (hypothesis_id, stage, verdict, kill_reason_slug,
                         kill_reason_verbatim, kill_reasons, killing_instrument,
                         measured, container_seconds, container_cost_basis,
                         provenance, cited_run, at, dedupe_key)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            COALESCE(%s::timestamptz, now()), %s)
                    {conflict}
                    RETURNING outcome_id
                    """,
                    (hypothesis_id, stage, verdict,
                     head["slug"] if head else None,
                     head["verbatim"] if head else None,
                     json.dumps(reasons) if reasons is not None else None,
                     killing_instrument,
                     json.dumps(measured) if measured is not None else None,
                     secs, container_cost_basis, provenance, cited, at,
                     dedupe_key))
                row = cur.fetchone()
            conn.commit()
        return {"outcome_id": int(row[0]) if row else None,
                "created": row is not None,
                "kill_reason_slug": head["slug"] if head else None,
                "reasons": len(reasons or [])}

    def add_edge(self, *, from_id: str, to_id: str, kind: str,
                 note: Optional[str] = None, cited_run: Optional[str] = None,
                 dedupe_key: Optional[str] = None,
                 on_conflict: str = "raise") -> dict[str, Any]:
        if kind not in EDGE_KINDS:
            raise ValueError(f"kind must be one of {EDGE_KINDS}, got {kind!r}")
        self.ensure_schema()
        conflict = ("ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING"
                    if on_conflict == "ignore" and dedupe_key else "")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO kg_edge (from_id, to_id, kind, note, cited_run,
                                         dedupe_key)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    {conflict}
                    RETURNING edge_id
                    """,
                    (from_id, to_id, kind, note, cited_run, dedupe_key))
                row = cur.fetchone()
            conn.commit()
        return {"edge_id": int(row[0]) if row else None,
                "created": row is not None}

    def void_outcome(self, outcome_id: int, reason: str,
                     cited_run: str) -> dict[str, Any]:
        """THE ONLY MUTATION PATH FOR A STORED OUTCOME.

        Flips the verdict to ``voided``, preserves what it said before in
        ``voided_from``, and records the reason and the run that decided. Every
        reader excludes voided rows from comparison and REPORTS how many it
        excluded — a silent shrink is the failure this column exists to stop.

        A measured value is never touched. If a measurement was re-taken, the
        new measurement is a new row: findings are not edited here any more
        than they are in ``docs/``.
        """
        cited = _cite(cited_run, "cited_run")
        why = reason.strip() if isinstance(reason, str) else ""
        if not why:
            raise ValueError(
                "a void needs a written reason — an unexplained void is a "
                "deleted finding with extra steps")
        # A WRITER, so it pays the DDL like the other three. On a store with no
        # kg_* tables this then raises KeyError("no outcome N") — which is the
        # true answer, rather than an UndefinedTable from three frames down.
        self.ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT verdict FROM kg_outcome WHERE outcome_id = %s "
                            "FOR UPDATE", (outcome_id,))
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"no outcome {outcome_id}")
                prior = row[0]
                cur.execute(
                    """
                    UPDATE kg_outcome
                       SET verdict = 'voided', voided_from = %s,
                           void_reason = %s, voided_at = now(),
                           voided_by_run = %s
                     WHERE outcome_id = %s
                    """,
                    (prior, why, cited, outcome_id))
            conn.commit()
        return {"outcome_id": int(outcome_id), "verdict": VOIDED,
                "voided_from": prior, "void_reason": why,
                "voided_by_run": cited}

    # --- raw reads ---------------------------------------------------------

    _HYP_COLS = ("id, family, mechanism, counterparty, claim_type, entities, "
                 "observable, horizon, predictions, falsifier, source, "
                 "source_ref, provenance, proposed_at, run_id")

    def _hyp_rows(self, where: str = "", params: tuple = ()) -> list[dict[str, Any]]:
        rows = self._read(f"SELECT {self._HYP_COLS} FROM kg_hypothesis {where}",
                          params)
        return [{"id": r[0], "family": r[1], "mechanism": r[2],
                 "counterparty": r[3], "claim_type": r[4], "entities": r[5],
                 "observable": r[6], "horizon": r[7], "predictions": r[8],
                 "falsifier": r[9], "source": r[10], "source_ref": r[11],
                 "provenance": r[12],
                 "proposed_at": r[13].isoformat() if r[13] else None,
                 "run_id": r[14]} for r in rows]

    _OUT_COLS = ("outcome_id, hypothesis_id, stage, verdict, kill_reason_slug, "
                 "kill_reason_verbatim, kill_reasons, killing_instrument, "
                 "measured, container_seconds, container_cost_basis, "
                 "provenance, cited_run, at, voided_from, void_reason")

    def _out_rows(self, where: str = "", params: tuple = ()) -> list[dict[str, Any]]:
        rows = self._read(f"SELECT {self._OUT_COLS} FROM kg_outcome {where}",
                          params)
        return [{"outcome_id": int(r[0]), "hypothesis_id": r[1], "stage": r[2],
                 "verdict": r[3], "kill_reason_slug": r[4],
                 "kill_reason_verbatim": r[5], "kill_reasons": r[6],
                 "killing_instrument": r[7], "measured": r[8],
                 "container_seconds": _num(r[9]), "container_cost_basis": r[10],
                 "provenance": r[11], "cited_run": r[12],
                 "at": r[13].isoformat() if r[13] else None,
                 "voided_from": r[14], "void_reason": r[15]} for r in rows]

    def edges(self, hypothesis_id: Optional[str] = None) -> list[dict[str, Any]]:
        where, params = "", ()
        if hypothesis_id:
            where = "WHERE from_id = %s OR to_id = %s"
            params = (hypothesis_id, hypothesis_id)
        rows = self._read("SELECT edge_id, from_id, to_id, kind, note, "
                          f"cited_run FROM kg_edge {where} ORDER BY edge_id",
                          params)
        return [{"edge_id": int(r[0]), "from_id": r[1], "to_id": r[2],
                 "kind": r[3], "note": r[4], "cited_run": r[5]} for r in rows]

    def families(self) -> list[str]:
        return [r[0] for r in self._read(
            "SELECT DISTINCT family FROM kg_hypothesis ORDER BY family")]

    # --- reader 1: THE FAMILY LEDGER ---------------------------------------

    def family_ledger(self, family: str) -> dict[str, Any]:
        """How many variants of this family are RECORDED, how many were JUDGED,
        and what killed them.

        Ed's grammar header needs a family count for the family-wise discovery
        correction. Today that number comes from recall; this is the same number
        from the record, with the run ids that support it.

        **``recorded`` AND ``judged`` ARE TWO NUMBERS AND v1 SHIPPED ONE.** The
        field was called ``tested`` and counted rows in ``kg_hypothesis`` — i.e.
        proposals the graph knows about, judged or not. The validator's
        spot-audit (run-validator-parity, 2026-08-23) read the fenced family
        back as ``status: TESTED, tested: 6, not yet judged: 6``: six things
        tested, none of them judged, in one sentence. A family-wise correction
        divided by that number is dividing by proposals, which is not the
        multiple-comparisons denominator anybody meant.

        So: ``recorded`` counts hypotheses; ``judged`` counts hypotheses
        carrying at least one NON-VOIDED outcome. Two invariants hold and
        ``tests/test_knowledge.py`` pins both —
        ``killed + len(survivors) == judged`` and
        ``judged + len(unjudged) == recorded``.

        THREE STATUSES, because two could not say this:

          ``UNTESTED``           nothing recorded. Not ``0`` — zero rows and
                                 zero survivors look identical in a count, and
                                 one means "nobody asked".
          ``RECORDED_UNJUDGED``  variants exist, none has a live verdict. This
                                 is the state the fenced family is actually in.
          ``TESTED``             at least one variant has been judged.
        """
        fam = _slugify(family, "family")
        hyps = self._hyp_rows("WHERE family = %s ORDER BY proposed_at NULLS LAST, id",
                              (fam,))
        if not hyps:
            # THE SAME KEY SET AS THE POPULATED BRANCH, on purpose: a shape that
            # changes with the status makes every consumer write a status check
            # it will one day forget. `status` carries the meaning; the zeroes
            # are only safe to read once it has been consulted, and the note
            # says so in words.
            return {
                "family": fam,
                "status": "UNTESTED",
                "recorded": 0,
                "judged": 0,
                "killed": 0,
                "provenance": {p: 0 for p in PROVENANCES},
                "note": (f"UNTESTED — no hypothesis in family {fam!r} has ever "
                         f"been recorded. This is not 'zero survived': nobody "
                         f"has asked, so the family-wise correction has no "
                         f"denominator from the record and must say so."),
                "kills_by_reason": [], "survivors": [], "unjudged": [],
                "unjudged_because_voided": [],
                "voided_outcomes": 0, "citations": [],
            }
        ids = [h["id"] for h in hyps]
        outs = self._out_rows(
            "WHERE hypothesis_id = ANY(%s) ORDER BY at, outcome_id", (ids,))
        voided = [o for o in outs if o["verdict"] == VOIDED]
        live = [o for o in outs if o["verdict"] != VOIDED]

        by_reason: dict[str, dict[str, Any]] = {}
        killed_ids: set[str] = set()
        for o in live:
            if o["verdict"] not in KILL_VERDICTS:
                continue
            killed_ids.add(o["hypothesis_id"])
            for r in (o["kill_reasons"] or [{"slug": UNCLASSIFIED_KILL_SLUG,
                                             "verbatim": ""}]):
                slot = by_reason.setdefault(r["slug"], {
                    "slug": r["slug"], "n": 0, "hypotheses": [],
                    "example_verbatim": r.get("verbatim") or None,
                    "citations": []})
                slot["n"] += 1
                if o["hypothesis_id"] not in slot["hypotheses"]:
                    slot["hypotheses"].append(o["hypothesis_id"])
                if o["cited_run"] not in slot["citations"]:
                    slot["citations"].append(o["cited_run"])

        judged_ids = {o["hypothesis_id"] for o in live}
        # A SURVIVOR CARRIES THE INSTRUMENT THAT PASSED IT, always. Three
        # `null_random_smallcap` variants survive in the live graph and all
        # three passed gate v1 — the bar that random strategies cleared about
        # half the time, which is why v2 exists. A bare id list would put
        # "3 survived" in a brief with no way to see that.
        survivors = [
            {"hypothesis_id": h["id"],
             "passed_by": sorted({o["killing_instrument"] or "UNRECORDED"
                                  for o in live
                                  if o["hypothesis_id"] == h["id"]
                                  and o["verdict"] in SURVIVE_VERDICTS}),
             "cited_runs": sorted({o["cited_run"] for o in live
                                   if o["hypothesis_id"] == h["id"]})}
            for h in hyps
            if h["id"] in judged_ids and h["id"] not in killed_ids]
        unjudged = [h["id"] for h in hyps if h["id"] not in judged_ids]
        voided_only = sorted({o["hypothesis_id"] for o in voided}
                             & set(unjudged))

        citations = []
        for c in [h["run_id"] for h in hyps] + [o["cited_run"] for o in outs]:
            if c and c not in citations:
                citations.append(c)

        note = (f"{len(hyps)} recorded, {len(judged_ids)} judged; "
                f"{len(killed_ids)} killed, {len(survivors)} survived, "
                f"{len(unjudged)} not yet judged")
        if voided:
            note += (f"; {len(voided)} outcome(s) VOIDED and excluded from "
                     f"every count above")
        if voided_only:
            note += (f", of which {len(voided_only)} hypothes(es) now have NO "
                     f"live verdict at all and read as not-yet-judged rather "
                     f"than as survivors")

        return {
            "family": fam,
            # RECORDED_UNJUDGED is not a cosmetic third value. A brief that
            # reads "TESTED" for a family whose every outcome is fenced has
            # been told the opposite of what the record says.
            "status": "TESTED" if judged_ids else "RECORDED_UNJUDGED",
            "recorded": len(hyps),
            "judged": len(judged_ids),
            "provenance": {
                p: sum(1 for h in hyps if h["provenance"] == p)
                for p in PROVENANCES},
            "killed": len(killed_ids),
            "kills_by_reason": sorted(by_reason.values(),
                                      key=lambda d: (-d["n"], d["slug"])),
            "survivors": survivors,
            "unjudged": unjudged,
            "unjudged_because_voided": voided_only,
            "voided_outcomes": len(voided),
            "note": note,
            "citations": citations,
        }

    # --- reader 2: PREDICTION CALIBRATION ----------------------------------

    def prediction_calibration(self, seat: Optional[str] = None
                               ) -> dict[str, Any]:
        """Pre-committed numbers against measured ones, joined on the jsonb keys.

        ``seat`` filters by the seat that wrote the citing run, read from
        ``fund_agent_runs``. A hypothesis whose run is not in that table has NO
        seat — it is reported in ``hypotheses_without_seat`` and EXCLUDED from a
        seat-filtered read, never quietly attributed.

        Reports "n of m scoreable" per metric and overall. m counts predictions
        that were MADE; n counts those with a numeric measured counterpart on a
        non-voided outcome. The gap is the honest part: a calibration that
        silently dropped unmeasured predictions would flatter whichever seat
        predicts the things we do not measure.
        """
        seats = self._seat_by_run()
        hyps = [h for h in self._hyp_rows() if h["predictions"]]
        for h in hyps:
            h["seat"] = seats.get(h["run_id"])
        without_seat = [h["id"] for h in hyps if h["seat"] is None]
        if seat is not None:
            hyps = [h for h in hyps if h["seat"] == seat]

        ids = [h["id"] for h in hyps]
        outs = self._out_rows("WHERE hypothesis_id = ANY(%s)", (ids,)) if ids else []
        voided_n = sum(1 for o in outs if o["verdict"] == VOIDED)
        measured_by_hyp: dict[str, list[dict[str, Any]]] = {}
        for o in outs:
            if o["verdict"] == VOIDED or not o["measured"]:
                continue
            measured_by_hyp.setdefault(o["hypothesis_id"], []).append(o)

        metrics: dict[str, dict[str, Any]] = {}
        unscoreable_non_numeric = 0
        for h in hyps:
            for key, predicted in (h["predictions"] or {}).items():
                slot = metrics.setdefault(key, {
                    "metric": key, "m_predicted": 0, "n_scoreable": 0,
                    "pairs": [], "unmeasured": [], "citations": []})
                slot["m_predicted"] += 1
                pv = _num(predicted)
                # The LAST non-voided outcome that carries this key wins: a
                # later stage re-measures what an earlier one guessed at.
                mv, cited = None, None
                for o in sorted(measured_by_hyp.get(h["id"], []),
                                key=lambda d: (d["at"] or "", d["outcome_id"])):
                    if key in (o["measured"] or {}):
                        cand = _num((o["measured"] or {})[key])
                        if cand is not None:
                            mv, cited = cand, o["cited_run"]
                if pv is None:
                    # A prediction that is PRESENT but not a number is not a
                    # missing one, and merging the two would let a stringly
                    # typed prediction hide inside "not yet measured".
                    if predicted is not None:
                        unscoreable_non_numeric += 1
                    slot["unmeasured"].append(h["id"])
                    continue
                if mv is None:
                    slot["unmeasured"].append(h["id"])
                    continue
                slot["n_scoreable"] += 1
                slot["pairs"].append({
                    "hypothesis_id": h["id"], "predicted": pv, "measured": mv,
                    "error": mv - pv,
                    "abs_error": abs(mv - pv),
                    "run_id": h["run_id"], "cited_run": cited})
                for c in (h["run_id"], cited):
                    if c and c not in slot["citations"]:
                        slot["citations"].append(c)

        out_metrics = []
        for slot in metrics.values():
            n, m = slot["n_scoreable"], slot["m_predicted"]
            errs = [p["abs_error"] for p in slot["pairs"]]
            out_metrics.append({
                **slot,
                "mean_abs_error": (sum(errs) / len(errs)) if errs else None,
                "note": (f"{n} of {m} scoreable"
                         + ("" if n == m else
                            f"; {m - n} prediction(s) have no measured "
                            f"counterpart and are EXCLUDED — not scored as "
                            f"correct, not scored as wrong")),
            })
        out_metrics.sort(key=lambda d: (-d["n_scoreable"], d["metric"]))

        total_m = sum(d["m_predicted"] for d in out_metrics)
        total_n = sum(d["n_scoreable"] for d in out_metrics)
        return {
            "seat": seat,
            "hypotheses_with_predictions": len(hyps),
            "scoreable": total_n,
            "predicted": total_m,
            "metrics": out_metrics,
            "excluded_voided_outcomes": voided_n,
            "unscoreable_non_numeric": unscoreable_non_numeric,
            "hypotheses_without_seat": without_seat,
            "note": (
                f"{total_n} of {total_m} predicted values scoreable across "
                f"{len(out_metrics)} metric(s)"
                + (f"; {voided_n} outcome(s) VOIDED and excluded automatically"
                   if voided_n else "")
                + (f"; {len(without_seat)} hypothes(es) cite a run that is not "
                   f"in fund_agent_runs, so they have no seat and are not "
                   f"attributed to one" if without_seat else "")
                if total_m else
                "NO PREDICTIONS RECORDED — nothing to calibrate. This is not a "
                "score of zero; it says the pre-committed numbers this reader "
                "exists to grade have not been written down yet."),
        }

    def _seat_by_run(self) -> dict[str, str]:
        """run_id -> seat, from the flight recorder. Read-only, best effort.

        The runs table lives in the same database and is the only place a run's
        seat is recorded. If it cannot be read, every hypothesis reports NO
        SEAT rather than a guessed one.

        Deliberately NOT routed through :meth:`_read`: ``fund_agent_runs`` is
        not a ``kg_*`` table, and raising SchemaAbsent — "run the kg backfill"
        — for a missing flight recorder would send the reader somewhere the
        problem is not.
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT run_id, seat FROM fund_agent_runs")
                    return {r[0]: r[1] for r in cur.fetchall()}
        except Exception as e:  # noqa: BLE001
            logger.warning("fund_agent_runs unreadable (%s) — every hypothesis "
                           "will report NO SEAT, which is not the same as "
                           "belonging to no seat", e)
            return {}

    # --- reader 3: THE KILL TAXONOMY ---------------------------------------

    def kill_taxonomy(self) -> dict[str, Any]:
        """Death causes, ranked by frequency and by container cost at the kill.

        The design's rule: a cause that recurs three times earns a pre-flight
        card item. ``earns_preflight_card`` says which ones have, so the card
        evolves from the record rather than from anecdote.

        THE COST COLUMN IS DELIBERATELY INCOMPLETE AND SAYS SO. A container
        cost is attributed only where the candidate's window contained no
        concurrently-running sibling on the same algorithm — measured 2026-08-23,
        20 of 41 live candidates fail that test. Splitting a shared window
        between siblings would invent an allocation, so those outcomes report
        ABSENT and are counted in ``cost_absent``.
        """
        outs = self._out_rows("ORDER BY at, outcome_id")
        hyp_family = {h["id"]: h["family"] for h in self._hyp_rows()}
        voided_n = sum(1 for o in outs if o["verdict"] == VOIDED)
        live = [o for o in outs
                if o["verdict"] in KILL_VERDICTS and o["verdict"] != VOIDED]

        causes: dict[str, dict[str, Any]] = {}
        for o in live:
            for r in (o["kill_reasons"] or [{"slug": UNCLASSIFIED_KILL_SLUG,
                                             "verbatim": ""}]):
                slot = causes.setdefault(r["slug"], {
                    "slug": r["slug"], "n": 0, "families": [],
                    "instruments": [], "example_verbatim": r.get("verbatim") or None,
                    "container_seconds_total": 0.0,
                    "cost_attributed": 0, "cost_absent": 0,
                    "citations": []})
                slot["n"] += 1
                fam = hyp_family.get(o["hypothesis_id"])
                if fam and fam not in slot["families"]:
                    slot["families"].append(fam)
                inst = o["killing_instrument"]
                if inst and inst not in slot["instruments"]:
                    slot["instruments"].append(inst)
                if (o["container_seconds"] is not None
                        and o["container_cost_basis"] == "exclusive"):
                    slot["container_seconds_total"] += o["container_seconds"]
                    slot["cost_attributed"] += 1
                else:
                    slot["cost_absent"] += 1
                if o["cited_run"] not in slot["citations"]:
                    slot["citations"].append(o["cited_run"])

        out_causes = []
        for slot in causes.values():
            attributed = slot["cost_attributed"]
            out_causes.append({
                **slot,
                # None, never 0.0, when nothing could be attributed: an
                # unattributed cost is not a free kill.
                "container_seconds_total": (slot["container_seconds_total"]
                                            if attributed else None),
                "container_seconds_mean": (slot["container_seconds_total"]
                                           / attributed) if attributed else None,
                "earns_preflight_card": slot["n"] >= PREFLIGHT_CARD_RECURRENCE,
                "cost_note": (
                    f"{attributed} of {attributed + slot['cost_absent']} kills "
                    f"carry an attributable container cost"
                    + ("" if not slot["cost_absent"] else
                       f"; {slot['cost_absent']} ABSENT (shared window, no "
                       f"stored containers, or never measured)")),
            })
        out_causes.sort(key=lambda d: (-d["n"], d["slug"]))

        unclassified = next((c for c in out_causes
                             if c["slug"] == UNCLASSIFIED_KILL_SLUG), None)
        counted = sum(c["n"] for c in out_causes)
        return {
            "causes": out_causes,
            "total_kill_outcomes": len(live),
            "total_causes_counted": counted,
            "distinct_causes": len(out_causes),
            "earning_preflight_card": [c["slug"] for c in out_causes
                                       if c["earns_preflight_card"]],
            "excluded_voided_outcomes": voided_n,
            # A GENUINE ZERO IS RENDERED, NEVER NULLED. v1 returned None here
            # whenever the bucket was empty, and scripts/kg/report.py gated its
            # whole block on truthiness — so a taxonomy where every sentence
            # matched printed EXACTLY the same thing as one where the
            # classifier had never run: nothing. Found by the validator's
            # spot-audit, run-validator-parity 2026-08-23. The three states are
            # distinguishable now, and `checked` is what distinguishes the last
            # two: 0 of 0 is not a clean sweep.
            "unclassified": _unclassified_block(unclassified, counted),
            "note": (f"{len(live)} kill outcome(s) carrying "
                     f"{sum(c['n'] for c in out_causes)} cause(s) across "
                     f"{len(out_causes)} distinct slug(s)"
                     + (f"; {voided_n} outcome(s) VOIDED and excluded"
                        if voided_n else "")
                     if live else
                     "NO KILLS RECORDED — the taxonomy has nothing to rank. "
                     "Not 'nothing dies here'; nothing has been ingested."),
        }

    # --- reader 4: THE CHEAP-KILL ROUTER -----------------------------------

    def cheap_kills(self) -> dict[str, Any]:
        """Which instrument killed which family, at what cost.

        The router: attack a new proposal with the historically lethal CHEAP
        instrument first. Entry 21 died at zero containers; this makes that
        ordering systematic instead of remembered.

        ``family-kind`` in the design is rendered here as the FAMILY SLUG, with
        ``claim_type`` carried per cell where a hypothesis stated one. There is
        no coarser "kind" in the record to group by, and inventing one would be
        a classification nobody wrote down.

        AN INSTRUMENT WITH NO MEASURED COST SORTS LAST AMONG EQUALS, never
        first. Unknown cost is not zero cost, and a router that treated it as
        zero would recommend the instrument it knows least about.
        """
        outs = self._out_rows("ORDER BY at, outcome_id")
        hyps = {h["id"]: h for h in self._hyp_rows()}
        voided_n = sum(1 for o in outs if o["verdict"] == VOIDED)
        live = [o for o in outs
                if o["verdict"] in KILL_VERDICTS and o["verdict"] != VOIDED]

        cells: dict[tuple[str, str], dict[str, Any]] = {}
        insts: dict[str, dict[str, Any]] = {}
        for o in live:
            h = hyps.get(o["hypothesis_id"]) or {}
            fam = h.get("family") or "UNKNOWN_FAMILY"
            inst = o["killing_instrument"] or "UNRECORDED_INSTRUMENT"
            cell = cells.setdefault((inst, fam), {
                "instrument": inst, "family": fam, "kills": 0,
                "hypotheses": [], "claim_types": [], "seconds": [],
                "citations": []})
            cell["kills"] += 1
            if o["hypothesis_id"] not in cell["hypotheses"]:
                cell["hypotheses"].append(o["hypothesis_id"])
            ct = h.get("claim_type")
            if ct and ct not in cell["claim_types"]:
                cell["claim_types"].append(ct)
            if o["cited_run"] not in cell["citations"]:
                cell["citations"].append(o["cited_run"])
            slot = insts.setdefault(inst, {
                "instrument": inst, "kills": 0, "families": [],
                "seconds": [], "cost_absent": 0, "citations": []})
            slot["kills"] += 1
            if fam not in slot["families"]:
                slot["families"].append(fam)
            if o["cited_run"] not in slot["citations"]:
                slot["citations"].append(o["cited_run"])
            if (o["container_seconds"] is not None
                    and o["container_cost_basis"] == "exclusive"):
                cell["seconds"].append(o["container_seconds"])
                slot["seconds"].append(o["container_seconds"])
            else:
                slot["cost_absent"] += 1

        matrix = []
        for cell in cells.values():
            secs = cell.pop("seconds")
            matrix.append({**cell,
                           "container_seconds_mean": (sum(secs) / len(secs))
                           if secs else None,
                           "cost_measured_on": len(secs)})
        matrix.sort(key=lambda d: (d["instrument"], -d["kills"], d["family"]))

        ranked = []
        for slot in insts.values():
            secs = slot.pop("seconds")
            mean = (sum(secs) / len(secs)) if secs else None
            ranked.append({**slot, "container_seconds_mean": mean,
                           "cost_measured_on": len(secs),
                           "cost_note": (
                               f"cost measured on {len(secs)} of "
                               f"{slot['kills']} kill(s)"
                               + ("" if secs else
                                  " — NO attributable cost, so this instrument "
                                  "ranks last among equally lethal ones rather "
                                  "than first"))})
        # Most lethal first; among equally lethal, cheapest first — and an
        # instrument whose cost is UNKNOWN sorts behind every measured one
        # (the `mean is None` flag leads the cost key).
        ranked.sort(key=lambda d: (-d["kills"],
                                   d["container_seconds_mean"] is None,
                                   d["container_seconds_mean"] or 0.0,
                                   d["instrument"]))

        return {
            "matrix": matrix,
            "instruments_ranked": ranked,
            "distinct_instruments": len(ranked),
            "distinct_families": len({f for _, f in cells}),
            "excluded_voided_outcomes": voided_n,
            "note": (f"{len(live)} kill(s) across {len(ranked)} instrument(s) "
                     f"and {len({f for _, f in cells})} family(ies)"
                     + (f"; {voided_n} outcome(s) VOIDED and excluded"
                        if voided_n else "")
                     if live else
                     "NO KILLS RECORDED — the router has no history to route "
                     "on and must not be read as 'no instrument kills'."),
        }
