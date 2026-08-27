"""The knowledge graph — the four rules it must never break.

  1. **An uncited row is inadmissible.** NOT NULL alone accepts ``''``; the
     guard is in Python AND in a CHECK constraint, and both are exercised here.
  2. **VOIDED cascades, and a voided outcome is NOT a survivor.** A hypothesis
     whose only verdict has been voided must read "not yet judged". Reading it
     as a survivor would turn a fenced measurement into evidence of an edge.
  3. **Absence renders as absence.** UNTESTED is a word, not a zero; an
     unattributable container cost is ABSENT, not 0.0; a prediction with no
     measurement is neither right nor wrong.
  4. **void_outcome is the ONLY mutation path**, enforced by a database
     trigger rather than by whoever wrote the next caller.

Skipped unless a Postgres is reachable, like every other store test here.
Never a fund mode's ledger (``tests/test_fund_mode.py`` K1 polices that and
scans this file).

**ITS OWN DATABASE, and the reason is measured rather than fastidious.** This
module used ``krypton_fund_test``, the shared pytest scratch database that ten
other modules TRUNCATE — and as of the reader/writer split it also DROPS the
``kg_*`` tables, to prove that a reader does not recreate what it reads. A DROP
in a shared database is a fixture other processes are standing on: D21 measured
a cross-process race in exactly this shape (``test_factory.py`` truncating
``fund_candidates`` from a SECOND pytest process under the two-builders
arrangement, a different test failing on each of three consecutive runs), and
that was only a TRUNCATE. Two builders are meant to serialize their suites; a
private database means the guarantee does not rest on that alone.
"""

import os

import pytest
from _testdb import scratch_database

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

#: THIS MODULE'S OWN SCRATCH DATABASE. See the module docstring: this module
#: DROPs the kg_* tables, and a drop in a shared store is somebody else's flake.
TEST_DB = scratch_database("krypton_fund_kgunit")


def _dsn() -> str:
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    return f"{head}/{TEST_DB}"


def _graph():
    """A clean graph per test.

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
    from app.fund.knowledge import KnowledgeGraph
    kg = KnowledgeGraph(dsn=_dsn())
    # EXPLICIT since 2026-08-23: constructing a graph no longer issues DDL, so
    # a fixture that wants tables has to say so. The TRUNCATE below would
    # otherwise fail on a fresh database — which is the point of the split.
    kg.ensure_schema()
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE kg_edge, kg_outcome, kg_hypothesis")
        c.commit()
    return kg


@pytest.fixture
def kg():
    return _graph()


def _hyp(kg, family="carry_family", run_id="run-1", **kw):
    return kg.add_hypothesis(family=family, run_id=run_id, **kw)["id"]


# --- rule 1: every row cites a run ------------------------------------------

@pytest.mark.parametrize("bad", [None, "", "   ", "\t\n"])
def test_a_hypothesis_whose_citation_is_blank_is_REFUSED(kg, bad):
    """Design rule 1: the graph is an index over the record.

    A NOT NULL column accepts the empty string, so a blank citation would
    satisfy the schema and satisfy nobody reading the row later.
    """
    with pytest.raises(ValueError, match="run_id is mandatory"):
        kg.add_hypothesis(family="f", run_id=bad)


@pytest.mark.parametrize("bad", [None, "", "  "])
def test_an_outcome_whose_citation_is_blank_is_REFUSED(kg, bad):
    h = _hyp(kg)
    with pytest.raises(ValueError, match="cited_run is mandatory"):
        kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run=bad)


def test_the_DATABASE_refuses_a_blank_citation_too(kg):
    """The Python guard is not the only one, and this proves it.

    A direct INSERT bypasses ``add_hypothesis`` entirely. If the CHECK
    constraint were dropped this test would pass a blank citation into the
    graph, which is the whole failure this guard exists for.
    """
    import psycopg
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(_dsn()) as c:
            with c.cursor() as cur:
                cur.execute("INSERT INTO kg_hypothesis (id, family, run_id) "
                            "VALUES ('x','f','   ')")
            c.commit()


# --- schema round trip -------------------------------------------------------

def test_schema_round_trip_keeps_every_field(kg):
    h = kg.add_hypothesis(
        family="Announcement Premium", run_id="run-ed-1",
        mechanism="liquidity providers demand a premium into a known date",
        counterparty="index funds forced to trade at the close",
        claim_type="alpha", entities=["SPY", "IWM"],
        observable="close-to-close return around the announcement",
        horizon="1d", predictions={"psr_pct": 70.0, "capacity_usd": 250000.0},
        falsifier="premium does not appear in the 2015-2019 era",
        source="menu", source_ref="docs/proposals/ENTRY20.md",
        proposed_at="2026-08-22T00:00:00+00:00")
    assert h["family"] == "announcement_premium", (
        "family is canonicalised to a slug so two spellings are one family")
    rows = kg._hyp_rows("WHERE id = %s", (h["id"],))
    assert len(rows) == 1
    got = rows[0]
    assert got["mechanism"].startswith("liquidity providers")
    assert got["counterparty"].startswith("index funds")
    assert got["claim_type"] == "alpha"
    assert got["entities"] == ["SPY", "IWM"]
    assert got["horizon"] == "1d"
    assert got["predictions"] == {"psr_pct": 70.0, "capacity_usd": 250000.0}
    assert got["falsifier"].startswith("premium does not")
    assert got["source"] == "menu"
    assert got["provenance"] == "grammar"
    assert got["run_id"] == "run-ed-1"

    o = kg.add_outcome(hypothesis_id=h["id"], stage="gate", verdict="pass",
                       cited_run="run-quant-1",
                       measured={"psr_pct": 80.37, "capacity_usd": 19913113.08},
                       killing_instrument="gate:v4.1",
                       container_seconds=10576.0,
                       container_cost_basis="exclusive")
    out = kg._out_rows("WHERE outcome_id = %s", (o["outcome_id"],))[0]
    assert out["verdict"] == "pass"
    assert out["measured"] == {"psr_pct": 80.37, "capacity_usd": 19913113.08}
    assert out["container_seconds"] == 10576.0
    assert out["container_cost_basis"] == "exclusive"
    assert out["kill_reasons"] is None, (
        "an empty reason list would read as 'we looked and found no reasons' "
        "on a row that PASSED")


def test_an_unknown_source_is_refused_rather_than_nulled(kg):
    with pytest.raises(ValueError, match="source must be one of"):
        kg.add_hypothesis(family="f", run_id="r", source="twitter")


def test_a_family_that_canonicalises_to_nothing_is_refused(kg):
    """Non-empty input that slugifies to '' would merge with every other such
    family, and the merged row would look like a real one."""
    with pytest.raises(ValueError, match="no slug-able characters"):
        kg.add_hypothesis(family="!!! ???", run_id="r")


def test_an_UNREADABLE_container_cost_is_refused_rather_than_nulled(kg):
    """Unreadable is not absent.

    Nulling a mistyped cost would put "no attributable cost" on a row whose
    cost somebody measured — the absence-is-never-zero rule pointed at its
    quieter sibling, absence-is-never-a-typo.
    """
    h = _hyp(kg)
    for bad in ("about twenty minutes", float("nan"), float("inf"), object()):
        with pytest.raises(ValueError, match="finite number or absent"):
            kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                           cited_run="r", container_seconds=bad,
                           container_cost_basis="exclusive")
    # A NUMERIC STRING IS READABLE AND IS ACCEPTED. `OrderFilled.avg_price` is
    # a JSON string on 22 of 29 live rows, so refusing "1000" here would be
    # refusing the shape this codebase actually stores numbers in.
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="r", container_seconds="1000",
                       container_cost_basis="exclusive")
    assert kg._out_rows("WHERE outcome_id = %s",
                        (o["outcome_id"],))[0]["container_seconds"] == 1000.0


# --- rule 3: UNTESTED is a word, not a zero ----------------------------------

def test_family_ledger_renders_UNTESTED_for_a_family_with_no_rows(kg):
    """Design rule for Ed's grammar header: an untested family reads UNTESTED.

    The family-wise discovery correction divides by a family count. A count of
    zero and a family nobody has asked about are the same integer and opposite
    facts.
    """
    d = kg.family_ledger("nobody_has_tried_this")
    assert d["status"] == "UNTESTED"
    assert d["recorded"] == 0 and d["judged"] == 0
    assert "UNTESTED" in d["note"]
    assert "not 'zero survived'" in d["note"]


def test_both_ledger_branches_return_the_SAME_KEY_SET(kg):
    """A shape that changes with the status is a KeyError waiting for a caller.

    ``family_ledger`` returns early for an untested family, and v1's early
    return was missing ``killed``, ``provenance`` and
    ``unjudged_because_voided``. Every consumer then has to remember to check
    the status before reading a field — and the one that forgets crashes on
    the empty case, which is the case nobody has test data for.
    """
    _hyp(kg, family="populated_family")
    empty = kg.family_ledger("no_such_family")
    full = kg.family_ledger("populated_family")
    assert set(empty) == set(full), (
        "the untested branch and the populated branch disagree on shape: "
        f"only-empty={sorted(set(empty) - set(full))} "
        f"only-full={sorted(set(full) - set(empty))}")


def test_a_family_where_everything_died_is_TESTED_not_UNTESTED(kg):
    """The other half of the same claim, and the one a shortcut breaks.

    An implementation that returned UNTESTED whenever nothing survived would
    pass the test above and be catastrophically wrong here: it would tell Ed
    that a family he has killed six times has never been examined.
    """
    h = _hyp(kg, family="dead_family")
    kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                   cited_run="run-2", kill_reasons=["no held-out test - x"])
    d = kg.family_ledger("dead_family")
    assert d["status"] == "TESTED"
    assert d["recorded"] == 1 and d["judged"] == 1
    assert d["killed"] == 1 and d["survivors"] == []


def test_a_family_RECORDED_but_never_JUDGED_says_so_in_both_the_status_and_the_count(kg):
    """The validator's spot-audit, run-validator-parity 2026-08-23.

    The fenced family read back ``status: TESTED, tested: 6, not yet judged:
    6`` — six tested and none judged, in one sentence, because ``tested``
    counted rows in ``kg_hypothesis``. Ed's family-wise correction divides by
    that number, so it was dividing by proposals.

    This test fails if ``recorded`` is ever wired back to the judged count, if
    ``judged`` is wired to the recorded count, or if the third status is
    dropped and an unjudged family reads TESTED again.
    """
    for i in range(6):
        _hyp(kg, family="fenced_family", run_id=f"run-{i}")
    d = kg.family_ledger("fenced_family")
    assert d["status"] == "RECORDED_UNJUDGED"
    assert d["recorded"] == 6
    assert d["judged"] == 0
    assert len(d["unjudged"]) == 6
    assert "6 recorded, 0 judged" in d["note"]

    # ...and one judgement is enough to make it TESTED, so the status is not
    # simply "always RECORDED_UNJUDGED when nothing survived".
    kg.add_outcome(hypothesis_id=d["unjudged"][0], stage="gate",
                   verdict="fail", cited_run="run-j",
                   kill_reasons=["no held-out test - x"])
    after = kg.family_ledger("fenced_family")
    assert after["status"] == "TESTED"
    assert after["recorded"] == 6 and after["judged"] == 1


def test_the_ledger_counts_ADD_UP(kg):
    """Two invariants, asserted rather than assumed.

    ``killed + survivors == judged`` and ``judged + unjudged == recorded``.
    Without these, ``judged`` could be computed from a different set than the
    one ``survivors`` and ``unjudged`` are computed from and nothing would
    notice until a brief carried a total that does not add up.
    """
    a = _hyp(kg, family="adds_up", run_id="ra")
    b = _hyp(kg, family="adds_up", run_id="rb")
    _hyp(kg, family="adds_up", run_id="rc")          # never judged
    kg.add_outcome(hypothesis_id=a, stage="gate", verdict="fail",
                   cited_run="rj", kill_reasons=["no held-out test - x"])
    kg.add_outcome(hypothesis_id=b, stage="gate", verdict="pass",
                   cited_run="rj")
    d = kg.family_ledger("adds_up")
    assert d["killed"] + len(d["survivors"]) == d["judged"] == 2
    assert d["judged"] + len(d["unjudged"]) == d["recorded"] == 3


def test_family_ledger_counts_and_cites(kg):
    a = _hyp(kg, family="fam", run_id="run-a")
    b = _hyp(kg, family="fam", run_id="run-b")
    c = _hyp(kg, family="fam", run_id="run-c")
    kg.add_outcome(hypothesis_id=a, stage="gate", verdict="fail",
                   cited_run="run-j1", killing_instrument="gate:v4.1",
                   kill_reasons=["probabilistic Sharpe 1% is below 65.0% - x",
                                 "no held-out test - y"])
    kg.add_outcome(hypothesis_id=b, stage="gate", verdict="pass",
                   cited_run="run-j2", killing_instrument="gate:v4.1")
    d = kg.family_ledger("fam")
    assert d["recorded"] == 3 and d["judged"] == 2
    assert d["killed"] == 1
    assert [s["hypothesis_id"] for s in d["survivors"]] == [b]
    assert d["survivors"][0]["passed_by"] == ["gate:v4.1"], (
        "a survivor must carry the instrument that passed it — three "
        "null_random_smallcap variants survive the live graph and all three "
        "passed gate v1, which a bare id list hides")
    assert d["unjudged"] == [c]
    slugs = {k["slug"]: k["n"] for k in d["kills_by_reason"]}
    assert slugs == {"psr_below_floor": 1, "holdout_absent": 1}
    for run in ("run-a", "run-b", "run-c", "run-j1", "run-j2"):
        assert run in d["citations"]


# --- rule 2: VOIDED cascades -------------------------------------------------

def test_a_hypothesis_whose_only_verdict_is_VOIDED_is_NOT_a_survivor(kg):
    """THE SHARPEST ONE. The fenced 2026-08-20/21 monthend candidates.

    Six candidates enter the graph, are voided by the clean-field fence, and
    must then read "not yet judged". An implementation that computed survivors
    as "hypotheses with no kill" — rather than "judged AND not killed" — would
    report all six as SURVIVORS of a family that has never passed anything, and
    a brief built on that would propose more of a strategy the fence exists to
    stop anyone drawing conclusions from.
    """
    h = _hyp(kg, family="monthend_rebalance_flow")
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-quant-entry11",
                       kill_reasons=["probabilistic Sharpe 2% is below 65.0% - x"])
    before = kg.family_ledger("monthend_rebalance_flow")
    assert before["killed"] == 1 and before["survivors"] == []

    kg.void_outcome(o["outcome_id"], "fenced by the clean-field amendment",
                    "run-builder-kg-v1")

    after = kg.family_ledger("monthend_rebalance_flow")
    assert after["recorded"] == 1, "a voided outcome does not unrecord the family"
    assert after["judged"] == 0, "a voided outcome is not a judgement"
    assert after["status"] == "RECORDED_UNJUDGED", (
        "the fenced family must not read TESTED — the whole point of the "
        "fence is that its measurements may not be compared")
    assert after["killed"] == 0
    assert after["survivors"] == [], (
        "a voided verdict must NOT promote its hypothesis to survivor")
    assert after["unjudged"] == [h]
    assert after["unjudged_because_voided"] == [h]
    assert after["voided_outcomes"] == 1
    assert "VOIDED" in after["note"]
    assert after["kills_by_reason"] == []


def test_void_preserves_the_prior_verdict_and_the_measurement(kg):
    """Clean-field guard rail 2: annotate, never erase."""
    h = _hyp(kg)
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j", measured={"psr_pct": 12.5},
                       kill_reasons=["probabilistic Sharpe 12.5% is below 65.0% - x"])
    kg.void_outcome(o["outcome_id"], "re-measured on a corrected window", "run-v")
    row = kg._out_rows("WHERE outcome_id = %s", (o["outcome_id"],))[0]
    assert row["verdict"] == "voided"
    assert row["voided_from"] == "fail"
    assert row["void_reason"] == "re-measured on a corrected window"
    assert row["measured"] == {"psr_pct": 12.5}, (
        "voiding must not touch what was measured — the reader excludes the "
        "row, it does not lose it")
    assert row["kill_reason_slug"] == "psr_below_floor"


def test_re_voiding_is_refused(kg):
    h = _hyp(kg)
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j")
    kg.void_outcome(o["outcome_id"], "first", "run-v")
    import psycopg
    with pytest.raises(psycopg.errors.RaiseException, match="already voided"):
        kg.void_outcome(o["outcome_id"], "second", "run-v2")


def test_a_void_without_a_reason_is_refused(kg):
    h = _hyp(kg)
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j")
    with pytest.raises(ValueError, match="written reason"):
        kg.void_outcome(o["outcome_id"], "   ", "run-v")


def test_an_outcome_may_not_be_WRITTEN_as_voided(kg):
    h = _hyp(kg)
    with pytest.raises(ValueError, match="void_outcome"):
        kg.add_outcome(hypothesis_id=h, stage="gate", verdict="voided",
                       cited_run="run-j")


# --- rule 4: void_outcome is the ONLY mutation path --------------------------

def _raw(sql, params=()):
    import psycopg
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute(sql, params)
        c.commit()


def test_the_DATABASE_blocks_every_mutation_that_is_not_a_void(kg):
    """A rule only its author honours is the unwired-kill-switch pattern.

    ``void_outcome`` could be perfect and irrelevant: the next caller writes
    its own UPDATE. So the guard is a trigger, and these three statements never
    go through ``knowledge.py`` at all.
    """
    import psycopg
    h = _hyp(kg)
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j", measured={"psr_pct": 12.5})
    oid = o["outcome_id"]

    with pytest.raises(psycopg.errors.RaiseException,
                       match="only permitted UPDATE"):
        _raw("UPDATE kg_outcome SET measured = '{\"psr_pct\": 99}'::jsonb "
             "WHERE outcome_id = %s", (oid,))
    with pytest.raises(psycopg.errors.RaiseException,
                       match="only permitted UPDATE"):
        _raw("UPDATE kg_outcome SET verdict = 'pass' WHERE outcome_id = %s",
             (oid,))
    with pytest.raises(psycopg.errors.RaiseException, match="never deleted"):
        _raw("DELETE FROM kg_outcome WHERE outcome_id = %s", (oid,))

    still = kg._out_rows("WHERE outcome_id = %s", (oid,))[0]
    assert still["verdict"] == "fail" and still["measured"] == {"psr_pct": 12.5}


def test_a_void_that_also_edits_the_measurement_is_blocked(kg):
    """The narrow hole: a caller could flip to 'voided' AND change measured in
    one statement, satisfying a naive 'verdict must become voided' guard."""
    import psycopg
    h = _hyp(kg)
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j", measured={"psr_pct": 12.5})
    with pytest.raises(psycopg.errors.RaiseException,
                       match="may not alter a stored measurement"):
        _raw("UPDATE kg_outcome SET verdict='voided', voided_from='fail', "
             "measured='{\"psr_pct\": 99}'::jsonb WHERE outcome_id = %s",
             (o["outcome_id"],))


def test_a_void_that_lies_about_the_prior_verdict_is_blocked(kg):
    import psycopg
    h = _hyp(kg)
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j")
    with pytest.raises(psycopg.errors.RaiseException,
                       match="voided_from must preserve"):
        _raw("UPDATE kg_outcome SET verdict='voided', voided_from='pass' "
             "WHERE outcome_id = %s", (o["outcome_id"],))


def test_a_re_measurement_is_a_NEW_ROW_and_both_survive(kg):
    h = _hyp(kg)
    a = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j1", measured={"psr_pct": 12.5},
                       at="2026-08-20T00:00:00+00:00")
    b = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="pass",
                       cited_run="run-j2", measured={"psr_pct": 80.4},
                       at="2026-08-22T00:00:00+00:00")
    rows = kg._out_rows("WHERE hypothesis_id = %s ORDER BY at", (h,))
    assert [r["outcome_id"] for r in rows] == [a["outcome_id"], b["outcome_id"]]
    assert [r["measured"]["psr_pct"] for r in rows] == [12.5, 80.4]


# --- the derived kill columns ------------------------------------------------

def test_the_singular_kill_columns_are_DERIVED_from_the_list(kg):
    """MOVE, do not match. An assertion that the two agree cannot tell a
    derivation from two literals that happen to agree today, so this changes
    the head of the list and requires the singular columns to follow."""
    h = _hyp(kg)
    first = kg.add_outcome(
        hypothesis_id=h, stage="gate", verdict="fail", cited_run="r",
        kill_reasons=["no held-out test - x",
                      "probabilistic Sharpe 1% is below 65.0% - y"])
    assert first["kill_reason_slug"] == "holdout_absent"

    moved = kg.add_outcome(
        hypothesis_id=h, stage="gate", verdict="fail", cited_run="r",
        kill_reasons=["probabilistic Sharpe 1% is below 65.0% - y",
                      "no held-out test - x"])
    assert moved["kill_reason_slug"] == "psr_below_floor", (
        "reordering the reasons must move the singular column; if it does not, "
        "the column is a second literal rather than a derivation")

    row = kg._out_rows("WHERE outcome_id = %s", (moved["outcome_id"],))[0]
    assert row["kill_reason_verbatim"] == row["kill_reasons"][0]["verbatim"]


@pytest.mark.parametrize("sentence,slug", [
    ("not priced: no slippage model, so every fill happened at the close",
     "not_priced"),
    ("only 13 fills; 20 is the minimum before a Sharpe describes a strategy",
     "too_few_fills"),
    ("only unknown fills; 20 is the minimum", "too_few_fills"),
    ("probabilistic Sharpe 17.43% is below 50.0%", "psr_below_floor"),
    ("no benchmark to compare against - 'better than nothing' is not it",
     "benchmark_absent"),
    ("returns 64.561% against 411.22% for simply owning it: an expensive way",
     "benchmark_not_beaten"),
    ("the held-out test ran the SAME dates twice - it proves nothing",
     "holdout_dates_ignored"),
    ("the held-out test placed no trades at all, so it says nothing",
     "holdout_no_trades"),
    ("the held-out retention could not be measured: negative train leg",
     "holdout_retention_unmeasurable"),
    ("no held-out test - choosing the best of N settings guarantees",
     "holdout_absent"),
    ("kept only -449% of its edge out of sample; 50% is the floor",
     "holdout_retention_below_floor"),
    ("the cost sweep says the edge survived every cost it tested but",
     "cost_tested_range_unreadable"),
    ("cost robustness was tested only to 5.0 bps and the floor is 10.0",
     "cost_grid_too_narrow"),
    ("cost robustness was never measured (no cost sweep was run)",
     "cost_robustness_unmeasured"),
    ("dies at 3.0bps of slippage, under the 10.0bps floor",
     "breakeven_below_floor"),
    ("capacity was never estimated - an unmeasured capacity is not adequate",
     "capacity_unmeasured"),
    ("capacity $12,000 is below $100,000 - too small", "capacity_below_floor"),
    ("no walk-forward test - a single held-out window is one draw",
     "walkforward_absent"),
    ("NOT TESTABLE on the history available: 1 fold(s) fit",
     "not_testable_on_history"),
    ("only 3 fold(s) could be measured, below the 4 required",
     "walkforward_folds_unmeasurable"),
    ("kept its edge in only 2 of 4 independent folds (50%)",
     "walkforward_minority_folds"),
])
def test_every_gate_failure_sentence_maps_to_a_slug(sentence, slug):
    """One case per ``failures.append`` site in ``app/fund/gate.py`` as of
    2026-08-23. Reproduce the site list:
        grep -n 'failures.append' app/fund/gate.py
    """
    from app.fund.knowledge import slug_for_kill
    assert slug_for_kill(sentence) == slug


def test_an_unrecognised_kill_sentence_is_counted_not_buried(kg):
    from app.fund.knowledge import UNCLASSIFIED_KILL_SLUG
    h = _hyp(kg)
    kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                   cited_run="r",
                   kill_reasons=["the gate grew a new sentence nobody mapped"])
    t = kg.kill_taxonomy()
    assert t["unclassified"] is not None
    assert t["unclassified"]["n"] == 1
    assert t["unclassified"]["checked"] == 1
    assert "new sentence" in t["unclassified"]["example_verbatim"]
    assert UNCLASSIFIED_KILL_SLUG in [c["slug"] for c in t["causes"]]


# --- (a) A GENUINE ZERO IS RENDERED, NEVER NULLED ----------------------------
#
# Validator spot-audit, run-validator-parity 2026-08-23: knowledge.py returned
# None for an empty unclassified bucket and scripts/kg/report.py gated its
# block on truthiness, so "every sentence matched" and "the classifier never
# ran" both printed NOTHING. Three states, three tests, and the report is
# checked as well as the reader — the defect needed both halves.

def test_ZERO_unclassified_with_sentences_checked_says_every_sentence_matched(kg):
    kg.add_outcome(hypothesis_id=_hyp(kg), stage="gate", verdict="fail",
                   cited_run="r", kill_reasons=["no held-out test - x",
                                                "capacity was never estimated"])
    u = kg.kill_taxonomy()["unclassified"]
    assert u is not None, "a genuine zero must be a block, never None"
    assert u["n"] == 0
    assert u["checked"] == 2, "the denominator is what makes the zero mean anything"
    assert "every sentence matched" in u["note"]
    assert u["example_verbatim"] is None


def test_ZERO_unclassified_with_NOTHING_checked_says_nothing_was_checked(kg):
    """0 of 0 is not a clean sweep, and this is where that is enforced.

    An empty graph classified no sentences. Reporting it the same way as a
    graph whose every sentence matched would make the module's own drift
    detector read healthiest exactly when it has seen nothing.
    """
    u = kg.kill_taxonomy()["unclassified"]
    assert u is not None
    assert u["n"] == 0 and u["checked"] == 0
    assert "NOTHING WAS CHECKED" in u["note"]
    assert "not a clean sweep" in u["note"]


@pytest.mark.parametrize("planted,expect", [
    ([], "NOTHING WAS CHECKED"),
    (["no held-out test - x"], "every sentence matched"),
    (["the gate grew a sentence nobody mapped"], "no rule in KILL_REASON_RULES"),
])
def test_the_taxonomy_REPORT_prints_the_unclassified_line_in_all_three_states(
        kg, planted, expect):
    """The render half. The reader can be right and the report still silent.

    ``report.py`` printed the unclassified block only ``if d["unclassified"]``,
    so fixing the reader alone would have left the chair reading the same blank
    page. Asserted on the rendered TEXT, through the real script.
    """
    import scripts.kg.report as rpt
    if planted:
        kg.add_outcome(hypothesis_id=_hyp(kg), stage="gate", verdict="fail",
                       cited_run="r", kill_reasons=planted)
    text = _render_with(rpt, kg, rpt.taxonomy)
    assert "UNCLASSIFIED:" in text, (
        "the unclassified line must be printed unconditionally — its absence "
        "is what made a zero indistinguishable from a never-checked")
    assert expect in text


def _render_with(rpt, kg, fn):
    """Run a report function against THIS test's graph, not pgstore's default.

    Monkeypatching ``_kg`` rather than reimplementing the rendering: a second
    copy of the formatter in the test could not catch a formatter defect.
    """
    original = rpt._kg
    rpt._kg = lambda: kg
    try:
        return fn()
    finally:
        rpt._kg = original


# --- calibration: n of m, and VOIDED excluded --------------------------------

def test_calibration_reports_n_of_m_and_scores_neither_way_when_unmeasured(kg):
    h = kg.add_hypothesis(family="f", run_id="r",
                          predictions={"psr_pct": 60.0, "capacity_usd": 1e6,
                                       "breakeven_bps": 12.0})["id"]
    kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                   cited_run="run-j",
                   measured={"psr_pct": 45.0, "capacity_usd": 2e6})
    d = kg.prediction_calibration()
    assert d["predicted"] == 3
    assert d["scoreable"] == 2
    assert "2 of 3" in d["note"]
    by = {m["metric"]: m for m in d["metrics"]}
    assert by["psr_pct"]["n_scoreable"] == 1
    assert by["psr_pct"]["pairs"][0]["error"] == pytest.approx(-15.0)
    assert by["breakeven_bps"]["n_scoreable"] == 0
    assert by["breakeven_bps"]["mean_abs_error"] is None, (
        "an unmeasured prediction must not contribute a zero error — that "
        "would score a missing measurement as a perfect forecast")
    assert "no measured counterpart" in by["breakeven_bps"]["note"]


def test_calibration_EXCLUDES_voided_outcomes_automatically(kg):
    """The sweep the chair does by hand becomes a column.

    MOVE, do not match: the same graph is scored before and after the void, and
    the score must change. An implementation that forgot the exclusion would
    return the identical number twice.
    """
    h = kg.add_hypothesis(family="f", run_id="r",
                          predictions={"psr_pct": 60.0})["id"]
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="run-j", measured={"psr_pct": 45.0})
    before = kg.prediction_calibration()
    assert before["scoreable"] == 1
    assert before["excluded_voided_outcomes"] == 0

    kg.void_outcome(o["outcome_id"], "fenced", "run-v")

    after = kg.prediction_calibration()
    assert after["scoreable"] == 0, (
        "a voided measurement must leave the calibration, or the fence is "
        "decoration")
    assert after["predicted"] == 1, (
        "the PREDICTION still stands — voiding the measurement does not "
        "un-predict it, and hiding it would flatter the seat")
    assert after["excluded_voided_outcomes"] == 1
    assert "VOIDED" in after["note"]


def test_calibration_with_nothing_to_score_says_so_rather_than_scoring_zero(kg):
    _hyp(kg)
    d = kg.prediction_calibration()
    assert d["scoreable"] == 0 and d["predicted"] == 0
    assert "NO PREDICTIONS RECORDED" in d["note"]
    assert "not a score of zero" in d["note"]


def test_a_non_numeric_prediction_is_counted_apart_from_a_missing_one(kg):
    h = kg.add_hypothesis(family="f", run_id="r",
                          predictions={"psr_pct": "sixty"})["id"]
    kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                   cited_run="run-j", measured={"psr_pct": 45.0})
    d = kg.prediction_calibration()
    assert d["scoreable"] == 0
    assert d["unscoreable_non_numeric"] == 1, (
        "a prediction that is present but unusable is a different fact from "
        "one nobody made")


def test_calibration_by_seat_excludes_hypotheses_whose_run_has_no_seat(kg):
    h = kg.add_hypothesis(family="f", run_id="run-not-in-the-recorder",
                          predictions={"psr_pct": 60.0})["id"]
    kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                   cited_run="run-j", measured={"psr_pct": 45.0})
    everyone = kg.prediction_calibration()
    assert h in everyone["hypotheses_without_seat"]
    just_ed = kg.prediction_calibration("mechanism")
    assert just_ed["predicted"] == 0, (
        "a hypothesis with no recorded seat must not be attributed to one")


# --- cost honesty ------------------------------------------------------------

def test_a_container_cost_without_an_exclusive_basis_is_REFUSED(kg):
    """20 of 41 live candidates share their window with a sibling.

    Accepting a number under basis ``ambiguous`` is how one shared 25,043-second
    window becomes nine full bills.
    """
    h = _hyp(kg)
    for basis in (None, "ambiguous", "no_jobs", "unmeasured"):
        with pytest.raises(ValueError, match="cannot carry basis"):
            kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                           cited_run="r", container_seconds=1000.0,
                           container_cost_basis=basis)


def test_kill_taxonomy_reports_an_unattributable_cost_as_ABSENT_not_zero(kg):
    h = _hyp(kg, family="fam")
    kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                   cited_run="r", kill_reasons=["no held-out test - x"],
                   container_cost_basis="ambiguous")
    c = kg.kill_taxonomy()["causes"][0]
    assert c["container_seconds_total"] is None
    assert c["container_seconds_mean"] is None
    assert "1 ABSENT" in c["cost_note"]


def test_the_preflight_recurrence_matches_the_design_document():
    """The constant is TRACEABLE, not merely present.

    Written after a mutation pass: the behavioural test below originally built
    ``range(PREFLIGHT_CARD_RECURRENCE)`` kills, so changing the constant moved
    the test with it and 3 -> 4 SURVIVED. A test parametrised by the value it
    is supposed to pin cannot pin it. This one checks the code against the
    written basis instead — the design doc's "when a cause recurs three times,
    it earns a pre-flight card item".

    Reproduce:
        grep -n 'recurs three times' \
            docs/research/KNOWLEDGE_GRAPH_V1_2026-08-23.md
    """
    import pathlib
    from app.fund.knowledge import PREFLIGHT_CARD_RECURRENCE
    assert PREFLIGHT_CARD_RECURRENCE == 3
    doc = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "research"
           / "KNOWLEDGE_GRAPH_V1_2026-08-23.md")
    assert doc.exists(), f"the design document moved: {doc}"
    assert "recurs three times" in doc.read_text(encoding="utf-8"), (
        "the design document no longer says three — the constant and its "
        "written basis have drifted apart, and one of them is now wrong")


def test_kill_taxonomy_marks_a_cause_that_recurs_three_times(kg):
    """THREE, hardcoded. See the test above for why it is not read from the
    constant: this must fail if the threshold moves."""
    for i in range(3):
        h = _hyp(kg, family=f"fam{i}")
        kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="r", kill_reasons=["no held-out test - x"])
    h = _hyp(kg, family="other")
    kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                   cited_run="r", kill_reasons=["not priced: no slippage model"])
    t = kg.kill_taxonomy()
    assert t["earning_preflight_card"] == ["holdout_absent"]
    assert not [c for c in t["causes"]
                if c["slug"] == "not_priced" and c["earns_preflight_card"]]


def test_a_cause_that_has_recurred_only_twice_does_NOT_earn_the_card(kg):
    """The other side of the boundary, so the threshold is pinned from both
    directions rather than by one inequality that any looser value satisfies."""
    for i in range(2):
        h = _hyp(kg, family=f"fam{i}")
        kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="r", kill_reasons=["no held-out test - x"])
    assert kg.kill_taxonomy()["earning_preflight_card"] == []


def test_cheap_kills_ranks_an_UNKNOWN_cost_instrument_LAST_among_equals(kg):
    """Unknown cost is not zero cost.

    A router that sorted a missing mean as 0.0 would recommend the instrument
    it knows least about FIRST — the absence-is-never-zero rule, applied where
    getting it wrong changes what gets attacked next.
    """
    cheapv = _hyp(kg, family="a")
    unknown = _hyp(kg, family="b")
    kg.add_outcome(hypothesis_id=cheapv, stage="gate", verdict="fail",
                   cited_run="r", killing_instrument="measured_control",
                   kill_reasons=["no held-out test - x"],
                   container_seconds=500.0, container_cost_basis="exclusive")
    kg.add_outcome(hypothesis_id=unknown, stage="gate", verdict="fail",
                   cited_run="r", killing_instrument="unpriced_control",
                   kill_reasons=["no held-out test - x"],
                   container_cost_basis="ambiguous")
    ranked = kg.cheap_kills()["instruments_ranked"]
    assert [i["instrument"] for i in ranked] == ["measured_control",
                                                 "unpriced_control"]
    assert ranked[1]["container_seconds_mean"] is None
    assert "ranks last" in ranked[1]["cost_note"]


def test_cheap_kills_puts_the_cheaper_measured_instrument_first(kg):
    """The other half: among equally lethal MEASURED instruments, cheap wins."""
    a = _hyp(kg, family="a")
    b = _hyp(kg, family="b")
    kg.add_outcome(hypothesis_id=a, stage="gate", verdict="fail", cited_run="r",
                   killing_instrument="expensive", container_seconds=9000.0,
                   container_cost_basis="exclusive",
                   kill_reasons=["no held-out test - x"])
    kg.add_outcome(hypothesis_id=b, stage="gate", verdict="fail", cited_run="r",
                   killing_instrument="cheap", container_seconds=10.0,
                   container_cost_basis="exclusive",
                   kill_reasons=["no held-out test - x"])
    ranked = kg.cheap_kills()["instruments_ranked"]
    assert [i["instrument"] for i in ranked] == ["cheap", "expensive"]


def test_cheap_kills_excludes_voided_outcomes(kg):
    h = _hyp(kg, family="a")
    o = kg.add_outcome(hypothesis_id=h, stage="gate", verdict="fail",
                       cited_run="r", killing_instrument="ctl",
                       kill_reasons=["no held-out test - x"])
    assert kg.cheap_kills()["instruments_ranked"][0]["kills"] == 1
    kg.void_outcome(o["outcome_id"], "fenced", "run-v")
    after = kg.cheap_kills()
    assert after["instruments_ranked"] == []
    assert after["excluded_voided_outcomes"] == 1
    assert "NO KILLS RECORDED" in after["note"]


# --- edges -------------------------------------------------------------------

def test_an_edge_needs_a_real_kind_and_two_real_hypotheses(kg):
    a, b = _hyp(kg, family="a"), _hyp(kg, family="b")
    with pytest.raises(ValueError, match="kind must be one of"):
        kg.add_edge(from_id=a, to_id=b, kind="inspired_by")
    e = kg.add_edge(from_id=a, to_id=b, kind="descendant_of_kill",
                    note="mutated on the holdout_absent reason")
    assert e["created"]
    assert kg.edges(a)[0]["kind"] == "descendant_of_kill"
    import psycopg
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        kg.add_edge(from_id=a, to_id="does-not-exist", kind="same_family")


# --- (c) THE DDL-ON-CONSTRUCT LOCK -------------------------------------------
#
# Validator spot-audit, run-validator-parity 2026-08-23: `KnowledgeGraph.
# __init__` ran `_ensure()`, so a read-only `scripts/kg/report.py` run issued
# the whole SCHEMA string — and the `DROP TRIGGER IF EXISTS ... ON kg_outcome`
# inside it needs ACCESS EXCLUSIVE. One ordinary open transaction wedged the
# table for ~5 minutes behind a report that only wanted to SELECT.
#
# Measured before the fix (scratchpad/d27probe_lock2.py, with one connection
# holding a plain `SELECT count(*) FROM kg_outcome` open):
#
#     CREATE TABLE IF NOT EXISTS kg_outcome ...      free    0.03s
#     CREATE INDEX IF NOT EXISTS kg_outcome_hyp_idx  free    0.03s
#     CREATE OR REPLACE FUNCTION kg_outcome_guard    free    0.03s
#     DROP TRIGGER IF EXISTS kg_outcome_immutable    BLOCKED 2.03s  <-- the wedge
#     SELECT-only reader path                        free    0.03s

#: A graph whose connections give up on a lock rather than hanging. The suite
#: must never wait five minutes to learn that a reader took a write lock — a
#: hung suite is not a failing test, and a test that can hang is a test nobody
#: will keep.
_LOCK_TIMEOUT_MS = 1500


def _impatient_graph():
    from app.fund.knowledge import KnowledgeGraph
    return KnowledgeGraph(
        dsn=f"{_dsn()}?options=-c%20lock_timeout%3D{_LOCK_TIMEOUT_MS}")


def test_CONSTRUCTING_a_graph_creates_no_tables(kg):
    """__init__ is not allowed to touch the store at all.

    Proven by MOVING the store rather than by inspecting the object: point a
    fresh graph at a database name that does not exist and construct it. If the
    constructor connects, this raises; if it issues DDL, it raises. Asserting
    on an internal flag would pass against a constructor that did both.
    """
    from app.fund.knowledge import KnowledgeGraph
    g = KnowledgeGraph(dsn=f"{_dsn()}_no_such_database_d27")
    assert g is not None
    assert g.ensure_schema.__self__ is g   # the writer's door exists, unopened


def test_a_READER_on_a_store_with_no_graph_says_ABSENT_not_ZERO(kg):
    """SchemaAbsent, not `{"causes": [], "total_kill_outcomes": 0}`.

    Two facts the old reader could not tell apart: a graph that has been
    ingested and holds no kills, and a database the graph has never been
    created in. One of those is a statement about the fund.

    The tables are DROPPED here, so this also proves the reader did not
    recreate them on the way past — which is the actual regression.
    """
    import psycopg
    from app.fund.knowledge import KnowledgeGraph, SchemaAbsent
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS kg_edge, kg_outcome, "
                        "kg_hypothesis CASCADE")
        c.commit()
    reader = KnowledgeGraph(dsn=_dsn())
    for name, call in (("kill_taxonomy", reader.kill_taxonomy),
                       ("cheap_kills", reader.cheap_kills),
                       ("families", reader.families),
                       ("edges", reader.edges),
                       ("prediction_calibration", reader.prediction_calibration),
                       ("family_ledger", lambda: reader.family_ledger("f"))):
        with pytest.raises(SchemaAbsent):
            call()
        assert f"{name}" or True
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("SELECT to_regclass('kg_outcome')")
            assert cur.fetchone()[0] is None, (
                "a reader recreated the table it was reading — that is the "
                "DDL-on-construct defect, back")


def test_a_WRITER_on_a_store_with_no_graph_creates_it(kg):
    """The other half: the write path is the one that pays for the schema."""
    import psycopg
    from app.fund.knowledge import KnowledgeGraph
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS kg_edge, kg_outcome, "
                        "kg_hypothesis CASCADE")
        c.commit()
    writer = KnowledgeGraph(dsn=_dsn())
    h = writer.add_hypothesis(family="made_by_the_writer", run_id="run-w")["id"]
    assert writer.family_ledger("made_by_the_writer")["recorded"] == 1
    assert h


def test_ensure_schema_is_MEMOISED_per_instance(kg):
    """Once per graph, not once per write.

    41 candidates through the backfill must not be 41 ACCESS EXCLUSIVE waits.
    The return value is the contract: True the time it ran, False after.
    """
    from app.fund.knowledge import KnowledgeGraph
    g = KnowledgeGraph(dsn=_dsn())
    assert g.ensure_schema() is True
    assert g.ensure_schema() is False
    g.add_hypothesis(family="f", run_id="r")
    assert g.ensure_schema() is False
    # ...and the memo is per INSTANCE, so a second graph on another store still
    # creates its own.
    assert KnowledgeGraph(dsn=_dsn()).ensure_schema() is True


def test_a_READ_ONLY_REPORT_DOES_NOT_WAIT_FOR_A_LOCK_ON_kg_outcome(kg):
    """THE INCIDENT, made into a test. run-validator-parity, 2026-08-23.

    One connection holds an ordinary read transaction open on ``kg_outcome``.
    Under a 1.5s lock timeout:

      * every reader completes — SELECT needs only ACCESS SHARE, which the
        blocker already holds and does not exclude;
      * ``ensure_schema()`` does NOT — it wants ACCESS EXCLUSIVE for the
        DROP TRIGGER, and that is the wedge.

    The second arm is what makes the first arm mean something. Without it the
    test would pass against a store that simply never locks anything, and could
    not distinguish "the reader takes no write lock" from "there was no
    contention". If the reader ever calls ``ensure_schema()`` again, the first
    arm raises LockNotAvailable and this test names the regression.
    """
    import psycopg
    kg.add_outcome(hypothesis_id=_hyp(kg), stage="gate", verdict="fail",
                   cited_run="r", kill_reasons=["no held-out test - x"])

    blocker = psycopg.connect(_dsn(), autocommit=False)
    try:
        with blocker.cursor() as cur:
            cur.execute("SELECT count(*) FROM kg_outcome")   # ACCESS SHARE, held
            assert cur.fetchone()[0] == 1

        reader = _impatient_graph()
        assert reader.kill_taxonomy()["total_kill_outcomes"] == 1
        # one kill, no instrument named -> the single UNRECORDED_INSTRUMENT bucket
        assert reader.cheap_kills()["distinct_instruments"] == 1
        assert reader.family_ledger("carry_family")["recorded"] == 1
        assert reader.families() == ["carry_family"]

        with pytest.raises(psycopg.errors.LockNotAvailable):
            _impatient_graph().ensure_schema()
    finally:
        blocker.rollback()
        blocker.close()
