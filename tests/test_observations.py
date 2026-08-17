"""Reading filings at breadth — and refusing to hallucinate at breadth.

The quote check is the whole difference between the two, so most of this file
is about it. An observation whose citation cannot be found in the source is
DISCARDED, not flagged: a "probably real" finding gets quoted later without its
caveat, which is worse than never having had it.
"""

import os

import pytest

from app.fund.observations import CATEGORIES, _parse, verify_quote

pytestmark_pg = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

SOURCE = """Item 2. Management's Discussion and Analysis

As of June 30, 2026, we had $81.0 million in cash and cash equivalents and
marketable securities, and an accumulated deficit of $542.7 million.

Gross margin was 61.2% compared to 64.8% in the prior year period.
"""


# --- the citation check -----------------------------------------------------

def test_a_real_quote_verifies():
    assert verify_quote("we had $81.0 million in cash and cash equivalents", SOURCE)


def test_an_invented_quote_is_rejected():
    """The failure this catches: a plausible sentence the filing never said."""
    assert not verify_quote(
        "gross margin decreased to 56.8% driven by third-party partner costs", SOURCE)


def test_reflowed_whitespace_still_verifies():
    """The document is reflowed HTML, so holding a model to byte equality
    across line breaks would reject honest citations."""
    assert verify_quote(
        "cash   and cash equivalents\n and marketable    securities", SOURCE)


def test_case_differences_still_verify():
    assert verify_quote("GROSS MARGIN WAS 61.2% COMPARED TO 64.8%", SOURCE)


def test_a_short_fragment_cannot_pass_as_a_citation():
    """Four words appear in almost any document by chance, so accepting one
    would make the check pass without proving anything."""
    assert not verify_quote("as of June", SOURCE)
    assert not verify_quote("million in cash", SOURCE)


def test_an_empty_quote_is_not_a_citation():
    assert not verify_quote("", SOURCE)
    assert not verify_quote(None, SOURCE)


# --- reading the model's reply ----------------------------------------------

def test_a_plain_json_object_parses():
    out = _parse('{"observations": [{"category": "margin", "observation": "x", "quote": "y"}]}')
    assert out and out[0]["category"] == "margin"


def test_a_fenced_reply_parses():
    out = _parse('```json\n{"observations": [{"observation": "x", "quote": "y"}]}\n```')
    assert out and out[0]["observation"] == "x"


def test_thinking_is_stripped_before_parsing():
    """A reasoning model drafts JSON inside <think>; parsing the draft would
    store observations it went on to discard."""
    out = _parse('<think>{"observations": [{"observation": "DRAFT"}]}</think>\n'
                 '{"observations": [{"observation": "final", "quote": "q"}]}')
    assert out and out[0]["observation"] == "final"


def test_an_empty_list_is_a_valid_answer():
    """A filing that says nothing notable must be allowed to say nothing.
    Forcing output is how a cover page becomes an insight."""
    assert _parse('{"observations": []}') == []


def test_unusable_output_is_none_not_an_empty_list():
    """None means 'the model failed'; [] means 'nothing to report'. Collapsing
    them would make a broken model look like a quiet quarter."""
    assert _parse("I could not find anything useful.") is None
    assert _parse("") is None


# --- storage ----------------------------------------------------------------

def _store():
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    test_dsn = f"{head}/krypton_fund_test"
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'krypton_fund_test'")
            if not cur.fetchone():
                cur.execute('CREATE DATABASE "krypton_fund_test"')
    from app.fund.observations import Observations
    o = Observations(test_dsn)
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_observations")
        c.commit()
    return o


DOC = {"ticker": "TEST", "form": "10-Q", "filed": "2026-06-30",
       "accession": "0001-26-000001", "url": "https://sec.gov/x",
       "text": SOURCE, "truncated": False}


def _model(payload):
    import json as _j
    return lambda system, user: _j.dumps(payload)


@pytestmark_pg
def test_only_verifiable_observations_are_stored():
    o = _store()
    out = o.extract(DOC, model_fn=_model({"observations": [
        {"category": "liquidity", "observation": "held $81.0m cash",
         "quote": "we had $81.0 million in cash and cash equivalents"},
        {"category": "margin", "observation": "margin fell to 56.8%",
         "quote": "gross margin decreased to 56.8% on partner costs"},
    ]}))
    assert out["stored"] == 1
    assert out["rejected_unverifiable"] == 1
    rows = o.recent(ticker="TEST")
    assert len(rows) == 1 and "81.0m" in rows[0]["observation"]


@pytestmark_pg
def test_an_unknown_category_falls_back_rather_than_failing():
    o = _store()
    o.extract(DOC, model_fn=_model({"observations": [
        {"category": "vibes", "observation": "x",
         "quote": "we had $81.0 million in cash and cash equivalents"}]}))
    assert o.recent(ticker="TEST")[0]["category"] == "other"


@pytestmark_pg
def test_a_model_failure_stores_nothing_and_says_so():
    o = _store()
    def boom(system, user):
        raise RuntimeError("model down")
    out = o.extract(DOC, model_fn=boom)
    assert out["stored"] == 0 and "model down" in out["error"]
    assert o.recent(ticker="TEST") == []


@pytestmark_pg
def test_seen_accessions_lets_a_sweep_skip_what_it_read():
    o = _store()
    o.extract(DOC, model_fn=_model({"observations": [
        {"category": "liquidity", "observation": "x",
         "quote": "we had $81.0 million in cash and cash equivalents"}]}))
    assert "0001-26-000001" in o.seen_accessions("TEST")


@pytestmark_pg
def test_reading_a_partial_filing_is_recorded_on_the_observation():
    """A finding from the first third of a 10-K and one from all of it must
    not look identical in the record."""
    o = _store()
    o.extract({**DOC, "truncated": True}, model_fn=_model({"observations": [
        {"category": "liquidity", "observation": "x",
         "quote": "we had $81.0 million in cash and cash equivalents"}]}))
    assert o.recent(ticker="TEST")[0]["read_partial_filing"] is True
