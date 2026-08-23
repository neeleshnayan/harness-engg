"""The episode store — a COPY of the seat memoranda, and every way that could
quietly stop being true.

Ticket ``92f98106``. What each group of tests pins:

  * **the round trip** — rejoining a file's sections reproduces the file BYTE
    FOR BYTE. A splitter that trims, normalises or skips turns the store into a
    paraphrase, and nobody would know which sections went missing;
  * **the memoranda are never written to** — asserted twice, once by walking
    the ingest's AST for a write call and once by hashing a fixture corpus
    before and after a real ingest;
  * **immutability** — the trigger, not the helper. Including the narrow hole:
    a statement that flips ``voided`` AND edits the text in one go;
  * **absence** — an absent table is not an empty store, an empty tag list is
    not "every market", an undated episode is excluded from a dated query and
    counted, a LIMIT says it truncated;
  * **the reader/writer split** — a reader issues no DDL, so a read-only query
    can never wedge the table the way ``scripts/kg/report.py`` wedged
    ``kg_outcome`` (validator spot-audit, run-validator-parity 2026-08-23).

**ITS OWN DATABASE, and the reason is a measured flake rather than
fastidiousness.** This module reads the WHOLE of ``fund_seat_episodes`` in its
coverage and census assertions, and it TRUNCATEs the table between tests. D21
measured a cross-process race of exactly that shape in ``krypton_fund_test``
(``test_factory.py`` truncating ``fund_candidates`` from a SECOND pytest process
under the two-builders arrangement; a different test failed on each of three
consecutive runs). ``krypton_fund_epitest`` is not any fund mode's ledger
(``tests/test_fund_mode.py`` K1 asserts that property for the mode databases,
and this name is none of them).
"""

import hashlib
import os
import pathlib

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

#: THIS MODULE'S OWN SCRATCH DATABASE. See the module docstring.
TEST_DB = "krypton_fund_epitest"

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The live memoranda, READ ONLY. Absent inside a builder worktree, which is
#: why every test that uses it also has a synthetic twin — a corpus test that
#: silently skips is a corpus test nobody runs.
LIVE_STATE = ROOT.parent / ".claude" / "state"


def _dsn() -> str:
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    return f"{head}/{TEST_DB}"


def _store():
    """A clean store per test.

    TRUNCATE rather than DELETE: the immutability trigger BLOCKS deletes by
    design, so a delete-based cleanup would fail — which is itself a small
    proof that the guard is on.
    """
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import dsn
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    from app.fund.episodes import EpisodeStore
    st = EpisodeStore(dsn=_dsn())
    st.ensure_schema()
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_seat_episodes")
        c.commit()
    return st


@pytest.fixture
def store():
    return _store()


def _add(store, seat="quant", kind="state", md="## a\n\nbody\n",
         cited_run="run-quant-1", **kw):
    return store.add_episode(seat=seat, kind=kind, episode_md=md,
                             cited_run=cited_run, **kw)


# --- the round trip: NOTHING IS LOST -----------------------------------------

#: Every shape the splitter has to survive. The live corpus supplies the
#: ordinary ones; these are the ones it does not, and a synthetic corpus is the
#: only way to test a shape nobody has written yet.
_HOSTILE = {
    "empty": "",
    "preamble only": "# builder\n\nsome prose with no heading at all\n",
    "starts with a heading": "## one\nbody\n## two\nbody\n",
    "no trailing newline": "## one\nbody",
    "CRLF": "# t\r\n\r\n## one\r\nbody\r\n## two\r\nbody\r\n",
    "heading with no body": "# t\n\n## one\n## two\n\nbody\n",
    "h3 does not split": "## one\n\n### inner\n\nbody\n\n### inner2\n\nb\n",
    "hash not at line start": "# t\n\nprose mentioning ## not a heading\n",
    "blank lines only": "\n\n\n",
    "heading is the whole file": "## just a heading",
}


@pytest.mark.parametrize("name", sorted(_HOSTILE))
def test_split_sections_REPRODUCES_the_input_byte_for_byte(name):
    """THE INVARIANT. ``"".join(s.text) == md``, for every input.

    This is what makes the store a copy rather than a paraphrase. A splitter
    that stripped a trailing blank line would look harmless and would make the
    episode text disagree with the memorandum it was copied from — and the
    disagreement would be invisible, because nobody diffs a database against a
    markdown file.
    """
    from app.fund.episodes import split_sections
    md = _HOSTILE[name]
    assert "".join(s.text for s in split_sections(md)) == md


def test_split_sections_reproduces_EVERY_LIVE_MEMORY_FILE():
    """The same invariant against the real corpus, which is where the shapes
    nobody anticipated actually live."""
    from app.fund.episodes import split_sections
    if not LIVE_STATE.is_dir():
        pytest.skip(f"no live state directory at {LIVE_STATE} "
                    f"(expected inside a builder worktree)")
    files = sorted(LIVE_STATE.glob("*.md"))
    assert len(files) >= 10, (
        f"only {len(files)} memory file(s) found — the glob is looking in the "
        f"wrong place rather than finding a small firm")
    for p in files:
        md = p.read_text(encoding="utf-8")
        assert "".join(s.text for s in split_sections(md)) == md, p.name


def test_the_PREAMBLE_becomes_an_episode_rather_than_being_dropped():
    """"The part nobody indexed" is where a silent loss hides."""
    from app.fund.episodes import split_sections
    secs = split_sections("# builder\n\nthe header\n\n## one\n\nbody\n")
    assert len(secs) == 2
    assert secs[0].ordinal == 0 and secs[0].heading is None
    assert "the header" in secs[0].text
    assert secs[1].heading == "## one"


def test_a_file_that_STARTS_with_a_heading_yields_no_empty_preamble():
    from app.fund.episodes import split_sections
    secs = split_sections("## one\nbody\n")
    assert len(secs) == 1 and secs[0].heading == "## one"


def test_ONLY_h2_SPLITS__h3_and_h1_are_structure_INSIDE_an_episode():
    """The round-trip invariant CANNOT catch this, which is why it is its own
    test: splitting on ``###`` as well still rejoins to the original bytes
    exactly, so a store fragmented into sub-sections would look perfectly
    healthy. Mutation proved it — ``^(?=##)`` survived every other test here.

    ``analyst.md`` carries 12 ``###`` subheadings and ``cto.md`` carries 8; at
    ``^(?=##)`` those become 20 extra episodes whose headings are fragments of
    someone else's argument.
    """
    from app.fund.episodes import split_sections
    md = ("# title\n\nintro\n\n## one\n\n### inner\n\nbody\n\n"
          "### inner two\n\nmore\n\n## two\n\nb\n")
    secs = split_sections(md)
    assert [s.heading for s in secs] == [None, "## one", "## two"]
    assert "### inner" in secs[1].text, (
        "a subheading belongs to the episode it sits in, not to one of its own")


def test_line_numbers_point_at_the_real_lines():
    """The source_ref is the provenance link back to the memorandum; a wrong
    line range makes it a decoration."""
    from app.fund.episodes import split_sections
    md = "# t\n\n## one\nbody\n\n## two\nmore\n"
    lines = md.splitlines()
    for s in split_sections(md):
        assert lines[s.line_start - 1] == s.text.splitlines()[0]
        assert lines[s.line_end - 1] == s.text.splitlines()[-1]


# --- classification ----------------------------------------------------------

@pytest.mark.parametrize("heading,kind", [
    ("## 2026-08-22 — STATE from run-builder-d13, appended by the chair", "state"),
    ("## STATE", "state"),
    ("## EVOLVE (both accepted by the chair at resolve)", "evolve"),
    ("## 2026-08-22 — CARRIED BY THE CHAIR (BINDS from four seats)", "bind"),
    ("## 2026-08-23 - CARRIED FROM GRACE (run-cfo-7) BY THE CHAIR", "bind"),
    ("## BINDS", "bind"),
    ("## 2026-08-20 — seeded at hiring", "lesson"),
    ("## Cold-start sequence (measured, not guessed)", "lesson"),
    (None, "lesson"),
])
def test_kind_for_heading(heading, kind):
    from app.fund.episodes import kind_for_heading
    assert kind_for_heading(heading) == kind


def test_the_kind_RULE_ORDER_is_part_of_the_specification():
    """A STATE the chair carried is a STATE, not a bind.

    Live example: "STATE from run-builder-d12 (the room), appended verbatim by
    the chair". If BINDS/CARRIED were tested first this would be filed as a
    bind, and the seat would look like it was told what it in fact measured.
    """
    from app.fund.episodes import kind_for_heading
    assert kind_for_heading(
        "## STATE from run-builder-d12, CARRIED by the chair") == "state"
    # ...and the classification is on the HEADING, never the body: a state
    # section that discusses BINDS is still a state.
    assert kind_for_heading("## STATE") == "state"


@pytest.mark.parametrize("tag,text", [
    ("equities", "SPY led the tape"),
    ("equities", "a small-cap effect"),
    ("bonds", "TLT is the leg"),
    ("bonds", "the yield curve inverted"),
    ("commodities", "GLD phantom price"),
    ("fx", "UUP is the dollar leg"),
    ("fx", "an FX carry trade"),
    ("crypto", "fetch_daily_bars(\"BTC\") returns CoinGecko bitcoin"),
    ("futures", "the managed-futures wrapper"),
    ("options", "implied vol is the observable"),
    ("etf", "asset exposure via ETFs"),
])
def test_every_market_tag_in_the_vocabulary_CAN_fire(tag, text):
    """Including ``options``, which matches NOTHING in today's corpus.

    A tag with no hits is not a tag with no rule. Dropping it because the count
    is zero would silently route the first options episode to UNTAGGED — and
    a rule that has never fired is proven by a planted sentence, not by
    absence.
    """
    from app.fund.episodes import tags_for_text
    assert tag in tags_for_text(text)


@pytest.mark.parametrize("text", [
    "the file lives at data/gld/bars.csv",     # lowercase ticker in a path
    "two options for the fix",                 # the English word
    "there are several option flags",
    "he ran the eth0 interface",
])
def test_the_tag_rules_do_NOT_fire_on_these(text):
    """The measured false positives, pinned so they cannot come back.

    A bare ``\\boptions?\\b`` was in the first draft of the table and produced
    NINE hits in the corpus, every one of them the English word. Ticker rules
    are case-SENSITIVE for the same reason: lowercase "gld" in a file path is
    not a claim about gold.
    """
    from app.fund.episodes import tags_for_text
    assert tags_for_text(text) == []


def test_an_untagged_episode_has_an_EMPTY_list_not_a_wildcard(store):
    """Empty means NO MARKET WAS NAMED, and a tag query must not return it."""
    from app.fund.episodes import tags_for_text
    assert tags_for_text("the merge gate reported three constants") == []
    _add(store, md="## x\n\nthe merge gate reported three constants\n",
         market_tags=[])
    d = store.episodes(tag="equities")
    assert d["matched"] == 0
    assert d["total_in_store"] == 1
    assert "NO MATCH" in d["note"] and "is on NO episode" in d["note"]


def test_the_tag_vocabulary_is_DERIVED_from_the_rules():
    """Two structures that must agree are derived, never maintained in
    parallel — D18's lesson, applied at construction."""
    from app.fund.episodes import MARKET_TAG_RULES, MARKET_TAGS
    assert set(MARKET_TAGS) == {t for t, _, _ in MARKET_TAG_RULES}
    assert len(MARKET_TAGS) == len(set(MARKET_TAGS)), "no tag appears twice"


# --- citations ---------------------------------------------------------------

def test_a_run_shaped_token_that_is_NOT_IN_THE_RECORDER_is_not_a_citation():
    """``run-riskofficer-N`` is in the live corpus and is a placeholder.

    Shape is not provenance. This is the same rule as the knowledge graph's:
    the store is an INDEX OVER THE RECORD, so a citation has to be findable in
    the record.
    """
    from app.fund.episodes import run_ids_in
    cited, rejected = run_ids_in(
        "see run-cfo-7 and also run-riskofficer-N",
        known={"run-cfo-7", "run-builder-d27"})
    assert cited == ["run-cfo-7"]
    assert rejected == ["run-riskofficer-N"]


def test_an_UNREADABLE_recorder_accepts_NOTHING_as_a_citation():
    """``known=None`` is "we could not check", and an unverifiable citation
    that looks verified is worse than an honest fallback to the ingestion
    run."""
    from app.fund.episodes import run_ids_in
    cited, rejected = run_ids_in("see run-cfo-7", known=None)
    assert cited == []
    assert rejected == ["run-cfo-7"]


@pytest.mark.parametrize("text", ["a run-up in prices", "at run-time",
                                  "no ids here at all"])
def test_english_words_are_not_run_ids(text):
    """Measured: the one-segment form ``run-\\w+`` matched "run-up" in the live
    corpus. Every one of the recorder's 107 ids on 2026-08-23 has at least two
    segments."""
    from app.fund.episodes import run_ids_in
    assert run_ids_in(text, known={"run-up", "run-time"})[0] == []


def test_the_run_id_shape_matches_every_id_the_recorder_holds():
    """Traceability for the pattern, against the real recorder rather than
    against my memory of it. Skipped, loudly, if it cannot be read."""
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.episodes import RUN_ID_RE
    from app.fund.pgstore import dsn
    try:
        with psycopg.connect(dsn(), connect_timeout=3) as c:
            with c.cursor() as cur:
                cur.execute("SELECT to_regclass('fund_agent_runs')")
                if cur.fetchone()[0] is None:
                    pytest.skip("fund_agent_runs absent")
                cur.execute("SELECT run_id FROM fund_agent_runs")
                ids = [r[0] for r in cur.fetchall()]
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    assert ids, "the recorder is empty — this test proves nothing today"
    bad = [i for i in ids if RUN_ID_RE.fullmatch(i) is None]
    assert bad == [], (
        f"{len(bad)} recorded run id(s) do not match RUN_ID_RE, so the ingest "
        f"would never recognise them as citations: {bad[:5]}")


@pytest.mark.parametrize("heading,date", [
    ("## 2026-08-22 — STATE from run-x", "2026-08-22"),
    ("## 2026-08-23 (~08:30Z) - STATE", "2026-08-23"),
    ("## Cold-start sequence", None),
    (None, None),
])
def test_date_in_heading(heading, date):
    from app.fund.episodes import date_in_heading
    assert date_in_heading(heading) == date


# --- the store: refusals -----------------------------------------------------

@pytest.mark.parametrize("bad", [None, "", "   ", "\t\n"])
def test_an_episode_whose_citation_is_blank_is_REFUSED(store, bad):
    with pytest.raises(ValueError, match="cited_run is mandatory"):
        _add(store, cited_run=bad)


def test_the_DATABASE_refuses_a_blank_citation_too(store):
    """A direct INSERT bypasses ``add_episode`` entirely."""
    import psycopg
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(_dsn()) as c:
            with c.cursor() as cur:
                cur.execute("INSERT INTO fund_seat_episodes "
                            "(seat, kind, episode_md, cited_run) "
                            "VALUES ('quant','state','x','  ')")
            c.commit()


def test_an_unknown_market_tag_is_REFUSED_rather_than_dropped(store):
    """A mistyped tag that silently became "no market named" would hide the
    episode from exactly the query it was tagged for."""
    with pytest.raises(ValueError, match="unknown market tag"):
        _add(store, market_tags=["equites"])


def test_an_unknown_kind_and_an_unknown_provenance_are_REFUSED(store):
    with pytest.raises(ValueError, match="kind must be one of"):
        _add(store, kind="anecdote")
    with pytest.raises(ValueError, match="provenance must be one of"):
        _add(store, provenance="hearsay")


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_an_EMPTY_episode_is_REFUSED(store, bad):
    """An empty row would say a seat wrote nothing, which is not what an empty
    section means — the section still has bytes, and those bytes are stored."""
    with pytest.raises(ValueError, match="episode_md is the episode"):
        _add(store, md=bad)


# --- immutability: THE TRIGGER, not the helper -------------------------------

def test_a_stored_episode_CANNOT_BE_DELETED(store):
    import psycopg
    e = _add(store)
    with pytest.raises(psycopg.errors.RaiseException, match="never deleted"):
        with psycopg.connect(_dsn()) as c:
            with c.cursor() as cur:
                cur.execute("DELETE FROM fund_seat_episodes WHERE episode_id=%s",
                            (e["episode_id"],))
            c.commit()


def test_an_ORDINARY_UPDATE_is_refused_by_the_database(store):
    """The rule lives under every writer, including a psql session and a
    future module — not only inside the one function that honours it."""
    import psycopg
    e = _add(store)
    with pytest.raises(psycopg.errors.RaiseException,
                       match="only permitted UPDATE"):
        with psycopg.connect(_dsn()) as c:
            with c.cursor() as cur:
                cur.execute("UPDATE fund_seat_episodes SET episode_md='edited' "
                            "WHERE episode_id=%s", (e["episode_id"],))
            c.commit()


#: EVERY column the void flip must leave alone, with a value that differs from
#: the fixture's. Written as data because a test that checks ONE of them is
#: half a guard: mutation proved it — dropping ``market_tags`` from the
#: trigger's comparison list survived a narrow-hole test that only edited
#: ``episode_md``.
_PROTECTED_COLUMNS = {
    "seat": "'someone_else'",
    "kind": "'lesson'",
    "heading": "'## rewritten'",
    "episode_md": "'quietly rewritten'",
    "market_tags": "ARRAY['crypto']::text[]",
    "cited_run": "'run-somebody-else'",
    "source_ref": "'state/other.md#L1-L2'",
    "provenance": "'backfill'",
    "episode_at": "'2001-01-01T00:00:00+00:00'::timestamptz",
    "filed_at": "'2001-01-01T00:00:00+00:00'::timestamptz",
    "dedupe_key": "'episodes:forged:0000:deadbeef'",
}


@pytest.mark.parametrize("column", sorted(_PROTECTED_COLUMNS))
def test_the_NARROW_HOLE_is_closed__voiding_may_not_edit_ANY_field(store, column):
    """A statement that flips ``voided`` AND edits a stored field in one go.

    A naive guard checks only that the new state is a void and waves this
    through. The trigger compares every other column explicitly — and this
    test walks every one of them, because a guard list is exactly the kind of
    thing that loses an entry in a refactor and never says so.
    """
    import psycopg
    e = _add(store, seat="quant", kind="state", heading="## a",
             market_tags=["bonds"], source_ref="state/quant.md#L1-L4",
             episode_at="2026-08-20T00:00:00+00:00",
             dedupe_key="episodes:quant:0001:abc")
    with pytest.raises(psycopg.errors.RaiseException,
                       match="may not alter a stored episode"):
        with psycopg.connect(_dsn()) as c:
            with c.cursor() as cur:
                cur.execute(
                    f"UPDATE fund_seat_episodes SET voided=true, "
                    f"void_reason='r', voided_by_run='run-x', "
                    f"{column}={_PROTECTED_COLUMNS[column]} "
                    f"WHERE episode_id=%s", (e["episode_id"],))
            c.commit()


def test_the_protected_column_list_matches_the_TRIGGER(store):
    """Traceability for the list above, against the DDL rather than my memory.

    The parametrized test can only walk the columns it is given; if the
    trigger grows a column and this list does not, the new one is unguarded
    and every test still passes. So the list is checked against the SQL.
    """
    import re

    from app.fund.episodes import SCHEMA
    # Every `NEW.x IS DISTINCT FROM OLD.x` pair, wherever it sits. The first
    # draft split the string on "IF NEW.seat" and silently dropped `seat` from
    # its own census — a scan that cannot see the first item it is scanning.
    in_trigger = {m.group(1) for m in re.finditer(
        r"NEW\.(\w+)\s+IS DISTINCT FROM OLD\.\1\b", SCHEMA)}
    assert in_trigger == set(_PROTECTED_COLUMNS), (
        f"only-in-trigger={sorted(in_trigger - set(_PROTECTED_COLUMNS))} "
        f"only-in-test={sorted(set(_PROTECTED_COLUMNS) - in_trigger)}")


def test_a_void_with_NO_REASON_is_refused_by_the_database(store):
    import psycopg
    e = _add(store)
    with pytest.raises(psycopg.errors.RaiseException,
                       match="a void needs a written reason"):
        with psycopg.connect(_dsn()) as c:
            with c.cursor() as cur:
                cur.execute("UPDATE fund_seat_episodes SET voided=true, "
                            "voided_by_run='run-x' WHERE episode_id=%s",
                            (e["episode_id"],))
            c.commit()


def test_a_void_that_CITES_NOTHING_is_refused_by_the_database(store):
    import psycopg
    e = _add(store)
    with pytest.raises(psycopg.errors.RaiseException, match="must cite the run"):
        with psycopg.connect(_dsn()) as c:
            with c.cursor() as cur:
                cur.execute("UPDATE fund_seat_episodes SET voided=true, "
                            "void_reason='r' WHERE episode_id=%s",
                            (e["episode_id"],))
            c.commit()


def test_voiding_TWICE_is_refused(store):
    """Re-voiding would overwrite the reason and the run that decided."""
    import psycopg
    e = _add(store)
    store.void_episode(e["episode_id"], "superseded by a later section",
                       "run-builder-d27")
    with pytest.raises(psycopg.errors.RaiseException, match="already voided"):
        store.void_episode(e["episode_id"], "again", "run-builder-d27")


def test_void_episode_PRESERVES_everything_and_records_who(store):
    e = _add(store, md="## x\n\nthe original words\n", market_tags=["bonds"])
    before = store.episodes(include_voided=True)["episodes"][0]
    store.void_episode(e["episode_id"], "the chair retracted it",
                       "run-builder-d27")
    after = store.episodes(include_voided=True)["episodes"][0]
    assert after["voided"] is True
    assert after["void_reason"] == "the chair retracted it"
    assert after["voided_by_run"] == "run-builder-d27"
    for field in ("seat", "kind", "heading", "episode_md", "market_tags",
                  "cited_run", "source_ref", "provenance", "episode_at",
                  "filed_at"):
        assert after[field] == before[field], f"{field} changed across a void"


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_void_episode_needs_a_written_reason_in_python_too(store, bad):
    e = _add(store)
    with pytest.raises(ValueError, match="a void needs a written reason"):
        store.void_episode(e["episode_id"], bad, "run-x")


def test_voiding_an_episode_that_does_not_exist_says_so(store):
    with pytest.raises(KeyError):
        store.void_episode(999999, "r", "run-x")


# --- reading: every answer carries its absences ------------------------------

def test_an_EMPTY_STORE_says_empty_rather_than_no_match(store):
    d = store.episodes(seat="quant")
    assert d["matched"] == 0 and d["total_in_store"] == 0
    assert "THE STORE IS EMPTY" in d["note"]
    assert "run scripts/episodes/ingest.py" in d["note"]


def test_a_seat_WITH_NO_EPISODES_is_distinguished_from_a_seat_with_none_today(store):
    """Two zeroes that mean different things, and the note separates them."""
    _add(store, seat="quant", episode_at="2026-08-20T00:00:00+00:00")
    never = store.episodes(seat="pm")
    assert never["matched"] == 0
    assert "seat 'pm' has NO episodes at all" in never["note"]
    assert "quant" in never["note"]
    quiet = store.episodes(seat="quant", since="2026-08-22")
    assert quiet["matched"] == 0
    assert "has NO episodes at all" not in quiet["note"], (
        "quant HAS episodes — just none in this window, which is a different "
        "answer and must not read the same")


def test_VOIDED_episodes_are_excluded_and_the_exclusion_is_COUNTED(store):
    a = _add(store, seat="quant")
    _add(store, seat="quant", md="## b\n\nsecond\n")
    store.void_episode(a["episode_id"], "retracted", "run-x")
    d = store.episodes(seat="quant")
    assert d["matched"] == 1
    assert d["voided_excluded"] == 1, (
        "a silent shrink is the failure the void trail exists to stop")
    wide = store.episodes(seat="quant", include_voided=True)
    assert wide["matched"] == 2 and wide["voided_excluded"] == 0


def test_an_UNDATED_episode_is_excluded_from_a_dated_query_AND_COUNTED(store):
    """It is not undated-therefore-recent and not undated-therefore-old."""
    _add(store, seat="quant", episode_at="2026-08-20T00:00:00+00:00")
    _add(store, seat="quant", md="## u\n\nno date in the heading\n",
         episode_at=None)
    plain = store.episodes(seat="quant")
    assert plain["matched"] == 2 and plain["undated_excluded"] == 0
    dated = store.episodes(seat="quant", since="2026-08-01")
    assert dated["matched"] == 1
    assert dated["undated_in_store"] == 1
    assert dated["undated_excluded"] == 1


def test_a_LIMIT_says_that_it_TRUNCATED(store):
    """A LIMIT on a reader is a silent off-switch unless the caller can tell —
    carried from the D22 review."""
    for i in range(4):
        _add(store, md=f"## s{i}\n\nbody\n")
    page = store.episodes(limit=2)
    assert page["matched"] == 2 and page["truncated"] is True
    assert "TRUNCATED" in page["note"]
    whole = store.episodes(limit=4)
    assert whole["matched"] == 4 and whole["truncated"] is False
    assert "TRUNCATED" not in whole["note"]


def test_the_filters_compose(store):
    _add(store, seat="quant", kind="state", market_tags=["bonds"],
         cited_run="run-quant-1", episode_at="2026-08-20T00:00:00+00:00")
    _add(store, seat="quant", kind="bind", md="## b\n\nx\n",
         market_tags=["bonds", "equities"], cited_run="run-cfo-7",
         episode_at="2026-08-22T00:00:00+00:00")
    _add(store, seat="pm", kind="state", md="## c\n\nx\n",
         market_tags=["equities"], cited_run="run-pm-1",
         episode_at="2026-08-22T00:00:00+00:00")
    assert store.episodes(seat="quant")["matched"] == 2
    assert store.episodes(tag="equities")["matched"] == 2
    assert store.episodes(kind="state")["matched"] == 2
    assert store.episodes(cited_run="run-cfo-7")["matched"] == 1
    assert store.episodes(seat="quant", tag="equities")["matched"] == 1
    assert store.episodes(since="2026-08-21")["matched"] == 2
    assert store.episodes(until="2026-08-21")["matched"] == 1
    assert store.episodes(seat="QUANT")["matched"] == 2, "seat is case-folded"


def test_an_unknown_kind_filter_is_REFUSED_rather_than_matching_nothing(store):
    """A typo'd filter that returns zero rows looks exactly like a true
    negative. Refuse it."""
    with pytest.raises(ValueError, match="kind must be one of"):
        store.episodes(kind="anecdote")


def test_coverage_splits_PROVENANCE_and_never_sums_it_away(store):
    _add(store, seat="quant", provenance="backfill")
    _add(store, seat="quant", md="## b\n\nx\n", provenance="seat",
         market_tags=["fx"])
    c = store.coverage()
    assert c["total"] == 2
    row = [s for s in c["seats"] if s["seat"] == "quant"][0]
    assert row["provenance"] == {"seat": 1, "backfill": 1}
    assert row["tagged"] == 1 and row["untagged"] == 1


def test_coverage_of_an_empty_store_says_EMPTY_not_zero(store):
    c = store.coverage()
    assert c["total"] == 0 and c["seats"] == []
    assert "THE STORE IS EMPTY" in c["note"]
    assert "not 'the seats have learned nothing'" in c["note"].lower()


# --- the reader/writer split -------------------------------------------------

def test_CONSTRUCTING_a_store_creates_no_tables(store):
    """Proven by MOVING the store: point a fresh one at a database that does
    not exist. If the constructor connects or issues DDL, this raises."""
    from app.fund.episodes import EpisodeStore
    s = EpisodeStore(dsn=f"{_dsn()}_no_such_database_d27")
    assert s is not None


def test_a_READER_on_a_store_with_no_table_says_ABSENT_not_ZERO(store):
    import psycopg
    from app.fund.episodes import EpisodeStore, SchemaAbsent
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS fund_seat_episodes CASCADE")
        c.commit()
    reader = EpisodeStore(dsn=_dsn())
    for call in (reader.episodes, reader.coverage, reader.seats, reader.tags):
        with pytest.raises(SchemaAbsent):
            call()
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("SELECT to_regclass('fund_seat_episodes')")
            assert cur.fetchone()[0] is None, (
                "a reader recreated the table it was reading — that is the "
                "DDL-on-construct defect this store was built to avoid")


def test_a_WRITER_on_a_store_with_no_table_creates_it(store):
    import psycopg
    from app.fund.episodes import EpisodeStore
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS fund_seat_episodes CASCADE")
        c.commit()
    writer = EpisodeStore(dsn=_dsn())
    _add(writer, seat="quant")
    assert writer.episodes(seat="quant")["matched"] == 1


def test_ensure_schema_is_MEMOISED_per_instance(store):
    from app.fund.episodes import EpisodeStore
    s = EpisodeStore(dsn=_dsn())
    assert s.ensure_schema() is True
    assert s.ensure_schema() is False
    _add(s)
    assert s.ensure_schema() is False
    assert EpisodeStore(dsn=_dsn()).ensure_schema() is True


def test_a_READ_DOES_NOT_WAIT_FOR_A_LOCK_ON_the_episode_table(store):
    """The kg incident, prevented rather than repeated.

    One connection holds an ordinary read transaction open. Under a 1.5s lock
    timeout every reader completes, and ``ensure_schema()`` does not — the
    second arm is what proves the first one means something rather than that
    there was no contention.
    """
    import psycopg
    from app.fund.episodes import EpisodeStore
    _add(store, seat="quant")
    impatient = f"{_dsn()}?options=-c%20lock_timeout%3D1500"

    blocker = psycopg.connect(_dsn(), autocommit=False)
    try:
        with blocker.cursor() as cur:
            cur.execute("SELECT count(*) FROM fund_seat_episodes")
            assert cur.fetchone()[0] == 1
        reader = EpisodeStore(dsn=impatient)
        assert reader.episodes(seat="quant")["matched"] == 1
        assert reader.coverage()["total"] == 1
        assert reader.seats() == ["quant"]
        with pytest.raises(psycopg.errors.LockNotAvailable):
            EpisodeStore(dsn=impatient).ensure_schema()
    finally:
        blocker.rollback()
        blocker.close()


# --- the ingest --------------------------------------------------------------

_FIXTURE_FILES = {
    "quant.md": (
        "# quant — working state\n"
        "(appended by the CTO at each dispatch resolution)\n"
        "\n"
        "## 2026-08-20 — seeded\n"
        "\n"
        "Nothing yet. TLT is the only leg the belt has priced.\n"
        "\n"
        "## 2026-08-22 — STATE from run-cfo-7\n"
        "\n"
        "The managed-futures wrapper failed ex-ante selection.\n"
        "\n"
        "## heading with no body\n"
        "## 2026-08-23 — CARRIED FROM GRACE BY THE CHAIR\n"
        "\n"
        "Cited run-riskofficer-N, which is a placeholder.\n"),
    "pm.md": (
        "# pm — working state\n"
        "\n"
        "## 2026-08-21 — EVOLVE proposed\n"
        "\n"
        "SPY and IWM both.\n"),
    "API_CARD.md": "# API card\n\n## not a seat\n\nprose\n",
}


def _corpus(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "state"
    d.mkdir()
    for name, text in _FIXTURE_FILES.items():
        (d / name).write_text(text, encoding="utf-8")
    return d


def _ingest(state_dir, **kw):
    from scripts.episodes.ingest import ingest
    return ingest(_dsn(), "run-builder-d27", pathlib.Path(state_dir), **kw)


@pytest.fixture(autouse=True)
def _sys_path():
    """``scripts/`` is on sys.path via tests/conftest.py; the repo root needs an
    entry too so ``scripts.episodes.ingest`` imports."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def test_the_ingest_reads_every_seat_file_and_NAMES_what_it_skipped(store, tmp_path):
    rep = _ingest(_corpus(tmp_path))
    assert [s["seat"] for s in rep["per_seat"]] == ["pm", "quant"]
    assert [s["file"] for s in rep["skipped_files"]] == ["API_CARD.md"]
    assert "not a seat memory file" in rep["skipped_files"][0]["why"]
    assert rep["totals"]["sections"] == 2 + 5
    assert rep["totals"]["created"] == 7


def test_the_ingest_stores_the_section_VERBATIM(store, tmp_path):
    """Byte for byte, heading included. This is the copy property at the
    database boundary rather than inside the splitter."""
    d = _corpus(tmp_path)
    _ingest(d)
    from app.fund.episodes import split_sections
    expected = {s.text for s in
                split_sections((d / "quant.md").read_text(encoding="utf-8"))}
    got = {e["episode_md"] for e in
           store.episodes(seat="quant", limit=100)["episodes"]}
    assert got == expected


def test_the_ingest_NEVER_WRITES_TO_A_MEMORY_FILE(store, tmp_path):
    """Measured, not promised: hash every file before and after a real ingest.

    The seat memoranda stay the operating memory. This is a COPY into queryable
    storage, and the day it becomes a migration is the day a seat's file starts
    disagreeing with what the seat actually wrote.
    """
    d = _corpus(tmp_path)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(d.glob("*.md"))}
    _ingest(d)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(d.glob("*.md"))}
    assert after == before
    assert len(before) == 3, "the hash census read the wrong directory"


def test_the_ingest_has_no_WRITE_PATH_into_the_state_dir():
    """The other half, and the one that fails on the AUTHOR of the next change.

    Walks the ingest module's AST for any call that could write a file. A
    behavioural test only proves that today's code path did not write; this
    proves there is no path at all.
    """
    import ast
    src = (ROOT / "scripts" / "episodes" / "ingest.py")
    tree = ast.parse(src.read_text(encoding="utf-8"), filename=str(src))
    banned = {"write_text", "write_bytes", "writelines", "unlink", "rename",
              "replace", "mkdir", "rmdir", "touch", "chmod"}
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr in banned:
            offenders.append(fn.attr)
        if isinstance(fn, ast.Name) and fn.id == "open":
            mode = next((a for a in node.args[1:2]), None)
            offenders.append(f"open(mode={getattr(mode, 'value', 'r')})")
    assert offenders == [], (
        "scripts/episodes/ingest.py can write to the filesystem: "
        + ", ".join(offenders)
        + ". The seat memoranda are the operating memory and this is a copy.")


def test_TWO_IDENTICAL_SECTIONS_in_one_file_are_TWO_episodes(store, tmp_path):
    """The dedupe key carries the section's ORDINAL as well as its hash.

    ``builder.md`` holds five sections that are exactly ``## STATE`` and
    nothing else. On a key hashed over the text alone they collapse into one
    row and four disappear — a silent loss, in the store whose whole claim is
    that it loses nothing. Mutation proved the earlier tests could not see it:
    the fixture had no repeated section.
    """
    d = tmp_path / "state"
    d.mkdir()
    (d / "builder.md").write_text(
        "# builder\n\n## STATE\n\n## STATE\n\n## STATE\n", encoding="utf-8")
    rep = _ingest(d)
    assert rep["totals"]["sections"] == 4      # preamble + three
    assert rep["totals"]["created"] == 4, (
        "three byte-identical sections collapsed into one row")
    rows = store.episodes(seat="builder", limit=100)["episodes"]
    assert sum(1 for r in rows if r["heading"] == "## STATE") == 3
    assert len({r["source_ref"] for r in rows}) == 4, (
        "each row must point at its own lines in the file")


def test_the_ingest_is_IDEMPOTENT(store, tmp_path):
    d = _corpus(tmp_path)
    first = _ingest(d)
    second = _ingest(d)
    assert first["totals"]["created"] == 7
    assert second["totals"]["created"] == 0
    assert second["totals"]["already_present"] == 7
    assert store.episodes(limit=100)["matched"] == 7


def test_an_APPENDED_section_is_the_only_thing_a_re_ingest_writes(store, tmp_path):
    """MEASURED DEFECT, fixed and pinned: this wrote TWO rows.

    Appending a section gives the previously-last section the blank line that
    now separates it from the new heading. Its bytes change, so a key hashed
    over the verbatim text changes too — and the store would accumulate one
    duplicate tail row per file per append, forever. Identity is now the
    rstripped text; the stored copy stays verbatim.
    """
    d = _corpus(tmp_path)
    _ingest(d)
    p = d / "pm.md"
    p.write_text(p.read_text(encoding="utf-8")
                 + "\n## 2026-08-23 — a new lesson\n\nGLD again.\n",
                 encoding="utf-8")
    again = _ingest(d)
    assert again["totals"]["created"] == 1
    assert store.episodes(seat="pm", limit=100)["matched"] == 3


def test_a_section_EDITED_IN_PLACE_becomes_a_NEW_episode_and_keeps_the_old(
        store, tmp_path):
    """The surprising half of an append-only store, pinned so it is a decision
    rather than a discovery.

    The dedupe key carries the section's hash, so an edit does not match and a
    second row is written. The old one stays: the store accumulates versions of
    an edited section, and a chair reading it sees both.
    """
    d = _corpus(tmp_path)
    _ingest(d)
    p = d / "pm.md"
    p.write_text(p.read_text(encoding="utf-8").replace("SPY and IWM both.",
                                                       "SPY, IWM and TLT."),
                 encoding="utf-8")
    again = _ingest(d)
    assert again["totals"]["created"] == 1
    rows = store.episodes(seat="pm", limit=100)["episodes"]
    assert len(rows) == 3
    bodies = " ".join(r["episode_md"] for r in rows)
    assert "SPY and IWM both." in bodies and "SPY, IWM and TLT." in bodies


def test_a_section_with_a_heading_and_NO_BODY_is_STORED_and_COUNTED(store, tmp_path):
    """Never dropped silently. Four exist in the live corpus today, including
    two halves of a heading somebody wrapped across two lines in cto.md."""
    rep = _ingest(_corpus(tmp_path))
    assert rep["totals"]["empty_body"] == 1
    assert len(rep["uninterpretable"]) == 1
    u = rep["uninterpretable"][0]
    assert u["heading"] == "## heading with no body"
    assert "#L" in u["source_ref"]
    stored = [e for e in store.episodes(limit=100)["episodes"]
              if e["heading"] == "## heading with no body"]
    assert len(stored) == 1, "counted AND stored, not counted instead of stored"


def test_the_PREAMBLE_of_each_file_is_ingested_with_no_heading(store, tmp_path):
    _ingest(_corpus(tmp_path))
    pre = [e for e in store.episodes(limit=100)["episodes"]
           if e["heading"] is None]
    assert {e["seat"] for e in pre} == {"pm", "quant"}
    assert all(e["kind"] == "lesson" for e in pre)


def test_the_ingest_splits_REAL_citations_from_the_ingestion_run(store, tmp_path):
    """A real citing run beats the ingestion run; the placeholder is rejected
    and NAMED."""
    rep = _ingest(_corpus(tmp_path))
    assert rep["recorder_readable"] in (True, False)
    total = rep["totals"]["real_citation"] + rep["totals"]["ingestion_citation"]
    assert total == rep["totals"]["sections"]
    assert rep["rejected_run_tokens"].get("run-riskofficer-N") == 1


def test_the_ingest_REFUSES_an_absent_state_directory(store, tmp_path):
    """A path derived from __file__ that fails permissive is a control nobody
    notices has stopped working. Measured: the default resolves wrongly inside
    a builder worktree, and printed a clean table of zeroes before this.

    Matched on the SPECIFIC message, not on "REFUSING". Mutation caught that:
    deleting this refusal let the NEXT one (no seat files) fire instead, and a
    test keyed on the shared word went green against the wrong branch.
    """
    with pytest.raises(SystemExit, match="no directory at") as ei:
        _ingest(tmp_path / "does_not_exist")
    assert "FUND_SEAT_STATE_DIR" in str(ei.value), (
        "the refusal has to tell the operator how to point it somewhere real")


def test_the_ingest_REFUSES_a_directory_with_no_seat_file(store, tmp_path):
    d = tmp_path / "state"
    d.mkdir()
    (d / "DAY_LOG.md").write_text("# log\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no seat memory file"):
        _ingest(d)
    # ...and it names what it DID find, so the misconfiguration is diagnosable.
    try:
        _ingest(d)
    except SystemExit as e:
        assert "DAY_LOG.md" in str(e)


def test_the_DRY_RUN_writes_nothing_but_still_counts(store, tmp_path):
    rep = _ingest(_corpus(tmp_path), dry_run=True)
    assert rep["dry_run"] is True
    assert rep["totals"]["sections"] == 7
    assert rep["totals"]["created"] == 0
    assert rep["kinds"] and rep["totals"]["empty_body"] == 1
    assert store.episodes(limit=100)["matched"] == 0


def test_the_report_RENDERS_and_shows_a_zero_tag_explicitly(store, tmp_path):
    from scripts.episodes.ingest import render
    text = render(_ingest(_corpus(tmp_path), dry_run=True))
    assert "UNTAGGED" in text
    assert "options" in text and "no episode names this market" in text, (
        "the WHOLE vocabulary is printed so a zero is visible; a tag that "
        "simply does not appear reads as a tag nobody defined")
    assert "API_CARD.md" in text
    assert "UNINTERPRETABLE sections: 1" in text


# --- the query renderer ------------------------------------------------------
#
# Both defects below were in code I had just written and were found by LOOKING
# at the rendered output, not by the diff and not by the suite. Eleventh
# consecutive dispatch.

def test_the_renderer_says_NONE_when_there_are_no_filters(store):
    """``"a: " + x or "b"`` parses as ``("a: " + x) or "b"`` and ``"a: "`` is
    truthy, so the fallback never fired: an unfiltered query printed a bare
    ``filters:`` and read like a query whose filters had been lost."""
    from scripts.episodes.query import find
    _add(store)
    text = find(store.episodes())
    assert "filters: NONE — the whole store" in text


def test_the_renderer_does_not_GLUE_a_long_tag_list_to_the_run_id(store):
    """Measured: four tags ran 27 characters into a 26-wide column and
    produced "...futuresrun-mechanism-cycle2". A reader could not see where
    the tags ended."""
    from scripts.episodes.query import find
    _add(store, market_tags=["bonds", "commodities", "equities", "etf", "fx"],
         cited_run="run-mechanism-cycle2")
    line = [ln for ln in find(store.episodes()).splitlines()
            if "run-mechanism-cycle2" in ln][0]
    assert "fxrun-" not in line
    assert "fx  run-mechanism-cycle2" in line


def test_the_renderer_prints_the_absences_even_on_a_NON_empty_answer(store):
    """A short answer against a large store is the case a reader misreads
    most, so the counts are printed always and not only when empty."""
    from scripts.episodes.query import find
    for i in range(3):
        _add(store, md=f"## s{i}\n\nbody\n", seat="quant")
    _add(store, seat="pm", md="## p\n\nbody\n", market_tags=["bonds"])
    text = find(store.episodes(seat="quant"))
    assert "matched 3 of 4 episode(s) in the store" in text
    assert "seats in store: pm, quant" in text
    assert "tags in store:  bonds" in text


def test_the_coverage_renderer_names_the_untagged_meaning(store):
    from scripts.episodes.query import coverage
    _add(store, seat="quant")
    text = coverage(store.coverage())
    assert "UNTAGGED means no market was named" in text
    assert "does NOT mean the episode applies to every market" in text


def test_the_vocabulary_command_prints_every_tag_with_its_patterns():
    """The tags are a classification this firm invented; a reader must be able
    to see what produced one without reading the module."""
    from app.fund.episodes import MARKET_TAGS
    from scripts.episodes.query import vocabulary
    text = vocabulary()
    for tag in MARKET_TAGS:
        assert f"    {tag}\n" in text + "\n"
    assert "SPY" in text and "implied vol" in text
