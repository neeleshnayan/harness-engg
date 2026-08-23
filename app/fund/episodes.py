"""The episode store — every seat's memory, verbatim, in queryable storage.

Ticket ``92f98106``; the CEO's design. v1 is the STORE and the BACKFILL. The
distillation of an operating memorandum out of these rows is chair-led work and
is deliberately NOT here — building the distiller before the corpus exists would
be designing against an imagined shape.

**IT IS A COPY, NOT A MIGRATION, AND THAT DISTINCTION IS THE WHOLE DESIGN.**
``.claude/state/<seat>.md`` remains the operating memorandum: the file a seat
reads on every dispatch and the chair appends to at resolve. The ingest reads
those files and writes nothing back to them. If this table were deleted the firm
would lose a query, not a memory — which is the property that lets it be work
layer, one commit to revert.

WHAT IT IS FOR. A seat's memory file answers "what do I know" in reading order
and answers nothing else. Four questions it cannot answer, that this can:

  1. what has any seat learned about FUTURES / FX / CRYPTO — the market-specialist
     trigger's evidence base (constitution, dispatch rule 4, 2026-08-23:
     "market-tagged EPISODES in the experience layer");
  2. what did seat X know on date D, and what has been added since;
  3. which episodes cite run R — the reverse index the flight recorder does not
     have;
  4. how much of the corpus is BINDS carried from other seats versus a seat's
     own STATE.

**NOTHING GATES ON IT AND NOTHING IN ``app/`` READS IT.** No endpoint, no UI, no
consumer — ``tests/test_knowledge_isolation.py`` walks the AST of every module
under ``app/`` and fails if this one appears, exactly as it does for the
knowledge graph. That is a structural claim, not an intention.

THREE RULES, INHERITED FROM THE KNOWLEDGE GRAPH BECAUSE THEY WERE EARNED THERE:

  * **Every row cites a run.** ``cited_run`` is NOT NULL in the schema AND
    rejected when blank in Python, because NOT NULL happily accepts ``''``.
  * **Rows are immutable except by voiding**, enforced by a Postgres trigger
    rather than by whoever writes the next caller. A correction is a NEW
    episode; the old one stays visible and voided.
  * **Absence renders as absence.** A section that names no run cites the
    INGESTION run and is counted separately from one that names a real run; a
    section with no market keyword has NO tags, which is not "all markets"; a
    query with no matches says which filter emptied it.

CONSTRUCTION ISSUES NO DDL. The knowledge graph shipped with ``_ensure()`` in
``__init__`` and a read-only report consequently wedged ``kg_outcome`` for ~5
minutes behind one ordinary transaction (validator spot-audit,
run-validator-parity, 2026-08-23). Same shape, same fix, from birth here:
readers are SELECT-only, writers call :meth:`EpisodeStore.ensure_schema`.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, NamedTuple, Optional

# NO MODULE LOGGER, deliberately. The knowledge graph has one because a reader
# there degrades (an unreadable fund_agent_runs is warned about and the read
# continues). Nothing here degrades: every failure is a raise the caller must
# handle, and an unused logger is an invitation to make the next one a
# logger.warning nobody reads — the riskofficer's carried rule, "audible means
# in the record, never logger.warning".

#: THE MODULE DECLARES ITS OWN LAYER, and the guard reads the declaration.
#:
#: ``tests/test_knowledge_isolation.py`` derives the set of modules the spine
#: may not import by scanning ``app/fund`` for this flag, rather than keeping a
#: list somebody has to remember to extend. Mutation showed why: deleting the
#: episode store from a hand-kept tuple simply ran one fewer test case and
#: nothing failed. A guard whose scope is a literal is a guard with a quiet
#: off-switch; a guard whose scope is a declaration fails on the author who
#: removes the declaration.
WORK_LAYER_STORE = True

# --- vocabularies ---------------------------------------------------------

#: What an episode IS. Closed set, per the ticket.
#:
#:   state   a seat's own STATE section — what its future self must know.
#:   bind    a lesson CARRIED from another seat by the chair (the `## BINDS`
#:           protocol). Kept distinct from `state` because a bind is evidence
#:           about the OTHER seat, and counting the two together would make a
#:           seat look like it learned what it was merely told.
#:   evolve  a proposed or applied amendment to the seat's own file.
#:   lesson  everything else a chair wrote into a seat's memory.
KINDS = ("state", "bind", "evolve", "lesson")

#: How a row got here. ``seat`` = written at resolve from a live dispatch;
#: ``backfill`` = recovered by splitting a memory file, best effort, partial.
#: Never silently mixed: every reader reports the split.
PROVENANCES = ("seat", "backfill")

#: Ordered (kind, pattern) rules mapping a section HEADING to a kind.
#: FIRST MATCH WINS, so the order is part of the specification — a heading
#: reading "STATE ... appended by the chair" is a state, not a bind.
#:
#: Matched against the heading only, never the body: a STATE section that
#: quotes the word BINDS is still a STATE.
#:
#: SNAPSHOT, 2026-08-23 ~17:00Z, 417 sections across 14 files:
#:     bind 222 · lesson 124 · state 67 · evolve 4
#: **THE CORPUS GROWS WHILE YOU READ IT** — it went 391 -> 406 -> 417 during
#: the dispatch that wrote this, because a chair appends at every resolve. The
#: snapshot is dated for that reason and nothing may be derived from it;
#: re-measure with ``scripts/episodes/ingest.py --dry-run --run-id <id>``,
#: which prints exactly this table from the SHIPPED classifier.
KIND_RULES: tuple[tuple[str, str], ...] = (
    ("state", r"\bSTATE\b"),
    ("evolve", r"\bEVOLVE\b"),
    ("bind", r"\bBINDS?\b|\bCARRIED\b"),
)

_COMPILED_KIND_RULES = tuple((k, re.compile(p)) for k, p in KIND_RULES)

#: The kind a heading lands in when no rule matches. Not "unknown": a chair
#: note that is neither a state nor a bind nor an amendment is a lesson, which
#: is what these files are mostly made of.
DEFAULT_KIND = "lesson"

#: Market tags. A CLOSED vocabulary, matched by explicit patterns against the
#: section text, so a tag is always traceable to a token somebody wrote.
#:
#: (tag, pattern, case_sensitive). Tickers are case-SENSITIVE — lowercase "gld"
#: in a file path is not a claim about gold — and English terms are not.
#:
#: SNAPSHOT, 2026-08-23 ~17:00Z, 417 sections across 14 seat files — and the
#: corpus grows, so re-measure rather than quote this:
#:     equities 59 · bonds 42 · commodities 30 · etf 11 · crypto 3 · fx 3 ·
#:     futures 1 · options 0 · TAGGED 77 · UNTAGGED 340 (81%)
#: Reproduce: ``scripts/episodes/ingest.py --dry-run --run-id <id>``.
#:
#: **81% UNTAGGED IS THE HONEST NUMBER AND IT IS NOT A DEFECT.** Most of what
#: these seats write is about the harness, not about a market. An untagged
#: episode means "no market was named in it" — never "it applies to every
#: market", and the query reader says so rather than returning everything.
#:
#: ``options`` matches NOTHING in today's corpus and is kept deliberately: the
#: vocabulary has to be able to tag an episode the firm has not written yet,
#: and a rule that has never fired is proven by a planted test rather than by
#: a hit count. Dropping it would silently route the first options episode to
#: UNTAGGED.
MARKET_TAG_RULES: tuple[tuple[str, str, bool], ...] = (
    ("equities", r"\bSPY\b|\bIWM\b|\bXBI\b|\bIBB\b|\bSRPT\b", True),
    ("equities", r"\bequit(?:y|ies)\b|\bsmall[- ]?cap\b|\bstocks?\b", False),
    ("bonds", r"\bTLT\b", True),
    ("bonds", r"\btreasur(?:y|ies)\b|\bbonds?\b|\byield curve\b", False),
    ("commodities", r"\bGLD\b|\bDBC\b|\bDBA\b", True),
    ("commodities", r"\bgold\b|\bcommodit(?:y|ies)\b", False),
    ("fx", r"\bUUP\b|\bFX\b", True),
    ("fx", r"\bcurrenc(?:y|ies)\b|\bdollar index\b", False),
    ("crypto", r"\bBTC\b|\bETH\b", True),
    ("crypto", r"\bcrypto\b|\bbitcoin\b|\bethereum\b", False),
    ("futures", r"\bfutures\b|\bcontango\b|\bbackwardation\b|\broll yield\b",
     False),
    # Deliberately NARROW. A bare ``\boptions?\b`` matches 13 times across 6
    # seat files in the 2026-08-23 corpus and NOT ONE of them is an episode
    # about the options market: "three regulatory options", "two options for
    # the fix", "options data" in a data-source list, "option-like payoffs"
    # in a Sharpe argument. Counted match by match before this table shipped —
    # a first pass said "nine", which was the number of SECTIONS, not matches.
    ("options", r"\bimplied vol|\bstraddle\b|\boption chain\b|"
                r"\bcall spread\b|\bput spread\b", False),
    ("etf", r"\bETFs?\b", True),
)

#: The tag vocabulary, derived from the rules so the two cannot drift.
MARKET_TAGS: tuple[str, ...] = tuple(
    dict.fromkeys(tag for tag, _, _ in MARKET_TAG_RULES))

_COMPILED_TAG_RULES = tuple(
    (tag, re.compile(pat, 0 if cs else re.IGNORECASE))
    for tag, pat, cs in MARKET_TAG_RULES)

#: A run id as this firm writes them. At least two hyphen-separated segments
#: after ``run-``. MEASURED against the recorder rather than assumed: every row
#: of ``fund_agent_runs`` fullmatches this pattern (110 rows at the last
#: reading, and rising — ``tests/test_episodes.py`` re-checks it against the
#: LIVE table on every run rather than trusting the count written here). The
#: looser one-segment form matched the English words "run-up" and "run-time"
#: in the corpus, which is why the second segment is required.
#:
#: Shape is not enough on its own. :func:`run_ids_in` is given the recorder's
#: real id set and returns only tokens that are IN it — the corpus contains
#: ``run-riskofficer-N``, a placeholder that is shaped exactly like a citation
#: and is not one.
RUN_ID_RE = re.compile(r"\brun-[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)+")

#: The ISO date a heading opens with, if it has one. Most do — 371 of 417 at
#: the 2026-08-23 reading — and the rest are genuinely undated in the heading,
#: which is why every dated query reports what it excluded.
_HEADING_DATE_RE = re.compile(r"(20\d\d-\d\d-\d\d)")

#: A markdown h2 at the start of a line. The ONLY split point.
_SECTION_SPLIT_RE = re.compile(r"(?m)^(?=## )")


class SchemaAbsent(RuntimeError):
    """``fund_seat_episodes`` does not exist in the store this reader was
    pointed at.

    Raised instead of returning an empty result: "no episodes have been
    ingested here" and "nobody has ever asked this question" are different
    facts, and a reader that answers 0 for the second one is reporting absence
    as zero.

    Defined here rather than imported from ``app.fund.knowledge``:
    ``tests/test_knowledge_isolation.py`` forbids any module under ``app/``
    from importing the knowledge graph, and this module is under ``app/``. Two
    work-layer stores sharing an exception class would be one import away from
    breaking the guard that keeps either of them out of a decision path.
    """


class Section(NamedTuple):
    """One ``## `` section of a memory file, with its place in the file.

    ``text`` is VERBATIM and includes the heading line and the trailing blank
    lines. That is what makes the round-trip invariant hold — see
    :func:`split_sections`.
    """

    ordinal: int          #: 0-based position in the file. 0 is the preamble.
    heading: Optional[str]   #: the ``## `` line, or None for the preamble
    text: str             #: the section verbatim, heading included
    line_start: int       #: 1-based first line of the section in the file
    line_end: int         #: 1-based last line


def split_sections(markdown: str) -> list[Section]:
    """Split a memory file on its ``## `` headings, LOSING NOTHING.

    THE INVARIANT, and it is the reason this returns verbatim text rather than
    a parsed body: ``"".join(s.text for s in split_sections(md)) == md``, for
    every input. ``tests/test_episodes.py`` asserts it over all fourteen live
    memory files. A splitter that trimmed, normalised or skipped would make the
    store a paraphrase of the memoranda instead of a copy of them, and nobody
    would know which sections went missing.

    Section 0 is the PREAMBLE — everything before the first heading, which in
    every current file is the ``# <seat> — working state`` title and a line of
    instruction. It is stored like any other section rather than dropped,
    because "the part of the file nobody indexed" is exactly where a silent
    loss hides. Its ``heading`` is None.

    A file that begins with ``## `` yields no preamble section (not an empty
    one): ``re.split`` on a zero-width match at position 0 does not produce a
    leading empty piece, and an empty episode row would be a lie about the
    file's shape.
    """
    if not markdown:
        return []
    pieces = [p for p in _SECTION_SPLIT_RE.split(markdown) if p != ""]
    out: list[Section] = []
    line = 1
    for i, piece in enumerate(pieces):
        n_lines = piece.count("\n") + (0 if piece.endswith("\n") else 1)
        head = piece.splitlines()[0] if piece.startswith("## ") else None
        out.append(Section(ordinal=i, heading=head, text=piece,
                           line_start=line, line_end=line + n_lines - 1))
        line += n_lines
    return out


def kind_for_heading(heading: Optional[str]) -> str:
    """The episode kind for one section heading. FIRST MATCH WINS.

    A section with no heading (the preamble) is a ``lesson``: it is prose a
    chair or a seat wrote, and calling it a state would put a file header in
    the same bucket as a dispatch's findings.
    """
    text = heading or ""
    for kind, rx in _COMPILED_KIND_RULES:
        if rx.search(text):
            return kind
    return DEFAULT_KIND


def tags_for_text(text: str) -> list[str]:
    """Market tags for one section, sorted, possibly empty.

    EMPTY MEANS NO MARKET WAS NAMED. It does not mean the episode is about
    every market, and :meth:`EpisodeStore.episodes` never returns untagged rows
    for a tag query.
    """
    hit = {tag for tag, rx in _COMPILED_TAG_RULES if rx.search(text or "")}
    return sorted(hit)


def run_ids_in(text: str, known: Optional[Iterable[str]] = None
               ) -> tuple[list[str], list[str]]:
    """``(cited, rejected)`` — run ids in this text, split by whether they exist.

    ``known`` is the recorder's real id set. A token shaped like a run id is
    not a citation: the corpus contains ``run-riskofficer-N``, a placeholder in
    a chair's note. Passing ``known=None`` means the recorder could not be read
    and NOTHING is accepted — an unverifiable citation is worse than an honest
    fallback to the ingestion run, because it would look verified.
    """
    seen: list[str] = []
    for t in RUN_ID_RE.findall(text or ""):
        if t not in seen:
            seen.append(t)
    if known is None:
        return [], seen
    ks = set(known)
    return [t for t in seen if t in ks], [t for t in seen if t not in ks]


def date_in_heading(heading: Optional[str]) -> Optional[str]:
    """The ISO date a heading opens with, or None.

    None is "the heading states no date", not "undated forever": ``filed_at``
    always exists and says when the row was written. Two clocks, named
    separately, because a section written today about 2026-08-20 is both.
    """
    m = _HEADING_DATE_RE.search(heading or "")
    return m.group(1) if m else None


SCHEMA = """
-- ONE ROW PER EPISODE — a `## ` section of a seat's memory, verbatim.
--
-- APPEND-ONLY. There is no UPDATE path except the void flip below, and no
-- DELETE path at all; both are enforced by a trigger rather than by whoever
-- writes the next caller. A convention only its author honours is the
-- unwired-kill-switch pattern, so the guard sits in the database.
CREATE TABLE IF NOT EXISTS fund_seat_episodes (
    episode_id    BIGSERIAL PRIMARY KEY,
    seat          TEXT NOT NULL,
    kind          TEXT NOT NULL,
    -- The `## ` line verbatim. NULL for a file's preamble, which has none —
    -- NULL reads "this section carried no heading", never "untitled".
    heading       TEXT,
    -- THE SECTION, BYTE FOR BYTE, heading included. Never normalised: this
    -- table is a copy of the memoranda, and a paraphrase would quietly become
    -- a second record.
    episode_md    TEXT NOT NULL,
    -- Empty array = NO MARKET WAS NAMED. Not "every market"; the reader never
    -- returns these rows for a tag query.
    market_tags   TEXT[] NOT NULL DEFAULT '{}',
    -- MANDATORY CITATION, exactly as in the knowledge graph. NOT NULL is half
    -- the enforcement; the other half is in Python, because NOT NULL accepts
    -- the empty string.
    cited_run     TEXT NOT NULL,
    -- Where this text was copied from, as "state/<seat>.md#L120-L188".
    -- Built by scripts/episodes/ingest.py, which is the only thing in the
    -- firm that opens a seat memorandum; nothing under app/ names that
    -- directory, and tests/test_knowledge_isolation.py enforces it over
    -- string literals (which is why this comment does not spell the path).
    source_ref    TEXT,
    provenance    TEXT NOT NULL DEFAULT 'seat',
    -- The date the heading states, if it states one. NULL is "undated in the
    -- heading" and is different from filed_at, which is always known.
    episode_at    TIMESTAMPTZ,
    filed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- THE VOID TRAIL. Clean-field guard rail 2: annotate, never erase.
    voided        BOOLEAN NOT NULL DEFAULT false,
    void_reason   TEXT,
    voided_at     TIMESTAMPTZ,
    voided_by_run TEXT,
    -- Natural key for idempotent ingestion. NULL for seat-written rows, and
    -- Postgres treats NULLs as distinct in a UNIQUE index, so many coexist.
    dedupe_key    TEXT,
    CONSTRAINT fund_seat_episodes_seat_nonblank CHECK (btrim(seat) <> ''),
    CONSTRAINT fund_seat_episodes_run_nonblank CHECK (btrim(cited_run) <> ''),
    CONSTRAINT fund_seat_episodes_md_nonblank CHECK (episode_md <> ''),
    CONSTRAINT fund_seat_episodes_kind
        CHECK (kind IN ('state','bind','evolve','lesson')),
    CONSTRAINT fund_seat_episodes_provenance
        CHECK (provenance IN ('seat','backfill'))
);

CREATE UNIQUE INDEX IF NOT EXISTS fund_seat_episodes_dedupe_idx
    ON fund_seat_episodes (dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS fund_seat_episodes_seat_idx
    ON fund_seat_episodes (seat, episode_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS fund_seat_episodes_run_idx
    ON fund_seat_episodes (cited_run);
CREATE INDEX IF NOT EXISTS fund_seat_episodes_tags_idx
    ON fund_seat_episodes USING GIN (market_tags);

-- IMMUTABILITY, ENFORCED IN THE DATABASE. Copied from kg_outcome_guard, which
-- earned every clause: the narrow hole is a statement that flips `voided` AND
-- edits the text in one go, so every other column is compared explicitly
-- rather than trusted to the flip.
--
-- TRUNCATE deliberately still works: it is a row-level trigger, and the test
-- suite's cleanup is not a mutation of a memory.
CREATE OR REPLACE FUNCTION fund_seat_episodes_guard() RETURNS trigger
AS $epguard$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'fund_seat_episodes rows are never deleted - an '
            'episode that turned out wrong is VOIDED, which keeps it visible '
            'and cited';
    END IF;
    IF OLD.voided THEN
        RAISE EXCEPTION 'episode % is already voided - re-voiding would '
            'overwrite the reason and the run that voided it', OLD.episode_id;
    END IF;
    IF NEW.voided IS NOT TRUE THEN
        RAISE EXCEPTION 'the only permitted UPDATE on fund_seat_episodes is '
            'void_episode (voided -> true); a correction is a NEW episode';
    END IF;
    IF btrim(COALESCE(NEW.void_reason, '')) = '' THEN
        RAISE EXCEPTION 'a void needs a written reason - an unexplained void '
            'is a deleted memory with extra steps';
    END IF;
    IF btrim(COALESCE(NEW.voided_by_run, '')) = '' THEN
        RAISE EXCEPTION 'a void must cite the run that decided it';
    END IF;
    IF NEW.seat        IS DISTINCT FROM OLD.seat
    OR NEW.kind        IS DISTINCT FROM OLD.kind
    OR NEW.heading     IS DISTINCT FROM OLD.heading
    OR NEW.episode_md  IS DISTINCT FROM OLD.episode_md
    OR NEW.market_tags IS DISTINCT FROM OLD.market_tags
    OR NEW.cited_run   IS DISTINCT FROM OLD.cited_run
    OR NEW.source_ref  IS DISTINCT FROM OLD.source_ref
    OR NEW.provenance  IS DISTINCT FROM OLD.provenance
    OR NEW.episode_at  IS DISTINCT FROM OLD.episode_at
    OR NEW.filed_at    IS DISTINCT FROM OLD.filed_at
    OR NEW.dedupe_key  IS DISTINCT FROM OLD.dedupe_key THEN
        RAISE EXCEPTION 'voiding may not alter a stored episode - every field '
            'except the void trail must survive the flip unchanged';
    END IF;
    RETURN NEW;
END;
$epguard$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS fund_seat_episodes_immutable ON fund_seat_episodes;
CREATE TRIGGER fund_seat_episodes_immutable
    BEFORE UPDATE OR DELETE ON fund_seat_episodes
    FOR EACH ROW EXECUTE FUNCTION fund_seat_episodes_guard();
"""


def _cite(value: Any, field: str) -> str:
    """A citation, or a refusal. See ``knowledge._cite`` — same rule, and it is
    restated rather than imported because this module may not import that one.
    """
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError(
            f"{field} is mandatory - an episode that cannot name the run it "
            f"came from is inadmissible (got {value!r})")
    return text


def _seat(value: Any) -> str:
    text = value.strip().lower() if isinstance(value, str) else ""
    if not text:
        raise ValueError("seat is mandatory and may not be blank")
    return text


class EpisodeStore:
    """Reader/writer over ``fund_seat_episodes``.

    **CONSTRUCTING ONE ISSUES NO DDL AND TAKES NO LOCK**, from birth. The
    knowledge graph shipped the other way and a read-only report wedged
    ``kg_outcome`` for ~5 minutes behind one ordinary transaction — measured
    2026-08-23 over all six DDL forms in that schema: exactly one,
    ``DROP TRIGGER IF EXISTS``, takes ACCESS EXCLUSIVE. This schema has one
    too, for the same reason (the immutability guard).
    Readers go through :meth:`_read`; writers call :meth:`ensure_schema`.
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

        Memoised per instance: True the time it ran, False after. A backfill
        issues the DDL ONCE however many sections it writes — several hundred
        today, and the count is deliberately not written here because the
        corpus grows every time a chair resolves a dispatch.
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
        """Every SELECT this module makes. SELECT-only by construction."""
        import psycopg
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchall()
        except psycopg.errors.UndefinedTable as e:
            raise SchemaAbsent(
                f"fund_seat_episodes does not exist in this store - nothing "
                f"has been ingested here, which is NOT the same as a store "
                f"with no episodes. Run scripts/episodes/ingest.py ({e})"
            ) from e

    # --- writes -----------------------------------------------------------

    def add_episode(self, *, seat: str, kind: str, episode_md: str,
                    cited_run: str,
                    heading: Optional[str] = None,
                    market_tags: Optional[Iterable[str]] = None,
                    source_ref: Optional[str] = None,
                    provenance: str = "seat",
                    episode_at: Optional[str] = None,
                    dedupe_key: Optional[str] = None,
                    on_conflict: str = "raise") -> dict[str, Any]:
        """One episode, text intact.

        ``on_conflict='ignore'`` makes ingestion idempotent and returns
        ``created: False`` rather than pretending it wrote.

        An unknown market tag is REFUSED, not dropped: a mistyped tag that
        became "no market named" would hide an episode from exactly the query
        it was tagged for.
        """
        cited = _cite(cited_run, "cited_run")
        who = _seat(seat)
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        if provenance not in PROVENANCES:
            raise ValueError(f"provenance must be one of {PROVENANCES}")
        if not (isinstance(episode_md, str) and episode_md.strip()):
            raise ValueError(
                "episode_md is the episode - an empty one is a row that says "
                "a seat wrote nothing, which is not what an empty section "
                "means. Store the verbatim text or store no row.")
        tags = sorted(set(market_tags or ()))
        unknown = [t for t in tags if t not in MARKET_TAGS]
        if unknown:
            raise ValueError(
                f"unknown market tag(s) {unknown} - the vocabulary is "
                f"{MARKET_TAGS}. Refused rather than dropped, because a "
                f"mistyped tag that silently became 'no market named' would "
                f"hide the episode from the query it was written for.")
        self.ensure_schema()
        conflict = ("ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL "
                    "DO NOTHING"
                    if on_conflict == "ignore" and dedupe_key else "")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO fund_seat_episodes
                        (seat, kind, heading, episode_md, market_tags,
                         cited_run, source_ref, provenance, episode_at,
                         dedupe_key)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::timestamptz,%s)
                    {conflict}
                    RETURNING episode_id
                    """,
                    (who, kind, heading, episode_md, tags, cited, source_ref,
                     provenance, episode_at, dedupe_key))
                row = cur.fetchone()
            conn.commit()
        return {"episode_id": int(row[0]) if row else None,
                "created": row is not None,
                "seat": who, "kind": kind, "market_tags": tags}

    def void_episode(self, episode_id: int, reason: str,
                     cited_run: str) -> dict[str, Any]:
        """THE ONLY MUTATION PATH FOR A STORED EPISODE.

        Flips ``voided``, records the reason and the run that decided. The text
        is never touched: a correction is a NEW episode, because these rows are
        a copy of what a seat actually wrote and rewriting one would make the
        copy disagree with the memorandum it came from.
        """
        cited = _cite(cited_run, "cited_run")
        why = reason.strip() if isinstance(reason, str) else ""
        if not why:
            raise ValueError(
                "a void needs a written reason - an unexplained void is a "
                "deleted memory with extra steps")
        self.ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT voided FROM fund_seat_episodes "
                            "WHERE episode_id = %s FOR UPDATE", (episode_id,))
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"no episode {episode_id}")
                cur.execute(
                    """
                    UPDATE fund_seat_episodes
                       SET voided = true, void_reason = %s, voided_at = now(),
                           voided_by_run = %s
                     WHERE episode_id = %s
                    """,
                    (why, cited, episode_id))
            conn.commit()
        return {"episode_id": int(episode_id), "voided": True,
                "void_reason": why, "voided_by_run": cited}

    # --- reads --------------------------------------------------------------

    _COLS = ("episode_id, seat, kind, heading, episode_md, market_tags, "
             "cited_run, source_ref, provenance, episode_at, filed_at, "
             "voided, void_reason, voided_by_run")

    @staticmethod
    def _row(r: tuple) -> dict[str, Any]:
        return {"episode_id": int(r[0]), "seat": r[1], "kind": r[2],
                "heading": r[3], "episode_md": r[4],
                "market_tags": list(r[5] or []), "cited_run": r[6],
                "source_ref": r[7], "provenance": r[8],
                "episode_at": r[9].isoformat() if r[9] else None,
                "filed_at": r[10].isoformat() if r[10] else None,
                "voided": bool(r[11]), "void_reason": r[12],
                "voided_by_run": r[13]}

    def episodes(self, *, seat: Optional[str] = None,
                 tag: Optional[str] = None,
                 kind: Optional[str] = None,
                 since: Optional[str] = None,
                 until: Optional[str] = None,
                 cited_run: Optional[str] = None,
                 include_voided: bool = False,
                 limit: Optional[int] = None) -> dict[str, Any]:
        """Episodes matching every filter given, newest first.

        **THE EMPTY ANSWER IS THE ONE THAT HAS TO BE HONEST**, so it comes with
        the evidence to read it:

          * ``matched`` — rows returned.
          * ``total_in_store`` — rows the store holds at all. Zero here and
            zero matched is an EMPTY STORE, not a failed query, and the note
            says which.
          * ``seats_in_store`` / ``tags_in_store`` — what a filter COULD have
            matched. A query for a seat nobody has ingested is a different
            answer from a seat with no episodes on that date, and without this
            they look identical.
          * ``voided_excluded`` — how many rows the void filter removed. A
            silent shrink is the failure the void trail exists to stop.
          * ``truncated`` — whether ``limit`` cut the answer. A LIMIT on a
            reader is a silent off-switch unless the caller can tell.

        ``since`` / ``until`` filter on ``episode_at``, the date the heading
        states. Rows with NO stated date are EXCLUDED from a dated query and
        counted in ``undated_excluded`` — they are not undated-therefore-recent
        and they are not undated-therefore-old.
        """
        where, params = [], []
        if seat:
            where.append("seat = %s")
            params.append(seat.strip().lower())
        if tag:
            where.append("%s = ANY(market_tags)")
            params.append(tag)
        if kind:
            if kind not in KINDS:
                raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
            where.append("kind = %s")
            params.append(kind)
        if cited_run:
            where.append("cited_run = %s")
            params.append(cited_run)
        dated = bool(since or until)
        if since:
            where.append("episode_at >= %s::timestamptz")
            params.append(since)
        if until:
            where.append("episode_at <= %s::timestamptz")
            params.append(until)
        if not include_voided:
            where.append("NOT voided")
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        sql = (f"SELECT {self._COLS} FROM fund_seat_episodes {clause} "
               f"ORDER BY episode_at DESC NULLS LAST, episode_id DESC")
        if limit:
            sql += f" LIMIT {int(limit) + 1}"
        rows = [self._row(r) for r in self._read(sql, tuple(params))]
        truncated = bool(limit) and len(rows) > int(limit or 0)
        if truncated:
            rows = rows[:int(limit)]

        census = self._read(
            "SELECT count(*), count(*) FILTER (WHERE voided), "
            "       count(*) FILTER (WHERE episode_at IS NULL) "
            "  FROM fund_seat_episodes")[0]
        total, voided_total, undated_total = (int(census[0]), int(census[1]),
                                              int(census[2]))
        seats_in_store = self.seats()
        tags_in_store = self.tags()

        if total == 0:
            note = ("THE STORE IS EMPTY - no episode has ever been ingested "
                    "here. This is not 'the filters matched nothing'; run "
                    "scripts/episodes/ingest.py.")
        elif rows:
            note = f"{len(rows)} of {total} episode(s) matched"
            if truncated:
                note += (f"; TRUNCATED at limit={limit} - there are more, and "
                         f"this answer is a page, not a census")
        else:
            note = (f"NO MATCH - the store holds {total} episode(s), so the "
                    f"filters are what emptied this")
            if seat and seat.strip().lower() not in seats_in_store:
                note += (f"; seat {seat!r} has NO episodes at all "
                         f"(known: {', '.join(seats_in_store) or 'none'})")
            if tag and tag not in tags_in_store:
                note += (f"; tag {tag!r} is on NO episode "
                         f"(present: {', '.join(tags_in_store) or 'none'})")
        return {
            "filters": {"seat": seat, "tag": tag, "kind": kind,
                        "since": since, "until": until,
                        "cited_run": cited_run,
                        "include_voided": include_voided, "limit": limit},
            "episodes": rows,
            "matched": len(rows),
            "truncated": truncated,
            "total_in_store": total,
            "seats_in_store": seats_in_store,
            "tags_in_store": tags_in_store,
            "voided_in_store": voided_total,
            "voided_excluded": 0 if include_voided else voided_total,
            "undated_in_store": undated_total,
            "undated_excluded": undated_total if dated else 0,
            "note": note,
        }

    def seats(self) -> list[str]:
        return [r[0] for r in self._read(
            "SELECT DISTINCT seat FROM fund_seat_episodes ORDER BY seat")]

    def tags(self) -> list[str]:
        return [r[0] for r in self._read(
            "SELECT DISTINCT unnest(market_tags) AS t FROM fund_seat_episodes "
            "ORDER BY t")]

    def coverage(self) -> dict[str, Any]:
        """Per seat: how many episodes, of what kinds, tagged how, cited how.

        The provenance split is reported per seat and never summed away: a seat
        whose episodes are entirely ``backfill`` has written none since the
        store existed, and that is a fact about the store's freshness rather
        than about the seat.
        """
        rows = self._read(
            "SELECT seat, kind, provenance, "
            "       count(*), "
            "       count(*) FILTER (WHERE cardinality(market_tags) > 0), "
            "       count(*) FILTER (WHERE voided), "
            "       count(*) FILTER (WHERE episode_at IS NULL), "
            "       min(episode_at), max(episode_at) "
            "  FROM fund_seat_episodes GROUP BY 1,2,3 ORDER BY 1,2,3")
        by_seat: dict[str, dict[str, Any]] = {}
        for seat, kind, prov, n, tagged, voided, undated, lo, hi in rows:
            slot = by_seat.setdefault(seat, {
                "seat": seat, "episodes": 0, "kinds": {},
                "provenance": {p: 0 for p in PROVENANCES},
                "tagged": 0, "untagged": 0, "voided": 0, "undated": 0,
                "earliest": None, "latest": None})
            slot["episodes"] += n
            slot["kinds"][kind] = slot["kinds"].get(kind, 0) + n
            slot["provenance"][prov] = slot["provenance"].get(prov, 0) + n
            slot["tagged"] += tagged
            slot["untagged"] += n - tagged
            slot["voided"] += voided
            slot["undated"] += undated
            for key, val in (("earliest", lo), ("latest", hi)):
                if val is None:
                    continue
                cur = slot[key]
                iso = val.isoformat()
                if cur is None or (iso < cur if key == "earliest" else iso > cur):
                    slot[key] = iso
        total = sum(s["episodes"] for s in by_seat.values())
        return {
            "seats": sorted(by_seat.values(), key=lambda d: d["seat"]),
            "total": total,
            "note": (f"{total} episode(s) across {len(by_seat)} seat(s)"
                     if total else
                     "THE STORE IS EMPTY - no episode has ever been ingested "
                     "here. Not 'the seats have learned nothing'."),
        }
