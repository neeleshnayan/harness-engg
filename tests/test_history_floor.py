"""How far back a candidate may look, and which leg decides — item (b) of 58c4fff5.

WHAT MOVED: ``WALKFORWARD_HISTORY_FLOOR`` went from 2024-02-26 to 1993-01-29.
MEASURED, not inherited — ``GET /fund/marketdata/bars?symbol=SPY&
start_date=1990-01-01&end_date=2026-08-23&format=csv`` returns 8,448 rows
beginning 1993-01-29. The old value was never the feed's start; it was the reach
of a trailing window nobody re-measured.

WHY THIS FILE EXISTS RATHER THAN A ONE-LINE CONSTANT CHANGE. Two facts measured
on 2026-08-23 make the naive flip harmful:

  * PER-SYMBOL HISTORY IS NOT UNIFORM. On this fund's own feed SPY serves from
    1993-01-29 and UUP from 2007-03-01 — fourteen years apart (TLT 2002-07-30,
    IBB 2001-02-12, GLD 2004-11-18, DBA 2007-01-05). A single global floor is
    right for one symbol and wrong for the rest.
  * THE CONTAINERS CANNOT REACH 1993. Counted, not eyeballed: of the sixteen
    algorithms in this repo ELEVEN fetch ``lookback_days=700``, three fetch
    900 and two fetch 2000 — and the bars endpoint caps the parameter at 2000.
    So a fold planned in 1993 would be fed nothing, and one planned in 2023 is
    fed partially.

Enforcing the container reach as a floor would take a 21-day hold's span from
850 days to 700 — two folds against a requirement of four — and return NOT
TESTABLE for every 21-day-hold candidate in the repo, including the Entry 20
re-judge this pair was sequenced in front of. So the floor RATCHETS: it deepens
where the candidate's own declared data path can serve the depth, never
shortens a window that already exists, and the reach is REPORTED with a count
of the folds that fall outside it.

The first live reading of that count, on a 700-day algorithm: 2 of 4 planned
folds already begin before the reach. That was true before this change and
nothing said so.

D20 CORRECTED THE ANCHOR OF THAT REACH. The bar URLs carry ``lookback_days`` and
no end date, so a container's fetch window ends WHEN IT RUNS, not when the
holdout ends. Anchoring on ``holdout.test_end`` made a backdated holdout look
deeper than the data path really is — the window opened before the first bar the
container would ever see, and the starved-fold count then reported ZERO because
it was comparing against a reach that does not exist. The anchor is now the
LATER of the run date and the holdout end, which is the conservative side in
both directions, and ``run_date`` is a parameter so the tests below do not
measure the clock.
"""

from __future__ import annotations

import pytest

from app.fund.factory import (HISTORY_FLOOR_RATCHET, WALKFORWARD_HISTORY_FLOOR,
                              effective_history_floor)

END = "2026-08-04"


def _code(lookback):
    return (f'url = f"{{SPINE}}/marketdata/bars?symbol={{s}}'
            f'&lookback_days={lookback}&format=csv"')


def test_the_configured_floor_is_the_feeds_measured_start():
    """8,448 SPY bars from 1993-01-29 on the start_date/end_date route."""
    assert WALKFORWARD_HISTORY_FLOOR == "1993-01-29"
    assert HISTORY_FLOOR_RATCHET == "2024-02-26"


# --- the ratchet ------------------------------------------------------------


def test_a_shallow_container_cannot_shorten_the_window():
    """The majority case: eleven of the sixteen algorithms declare 700 days.

    Their reach is LATER than the floor this fund already enforces. A floor may
    deepen a window and never shorten one, so the ratchet holds and the reach
    is reported instead of applied.
    """
    out = effective_history_floor(_code(700), END, run_date=END)
    assert out["data_path"] == "2024-09-03"
    assert out["effective"] == HISTORY_FLOOR_RATCHET
    assert out["deepened"] is False
    assert out["ratcheted_from"] == "2024-09-03"
    assert "may deepen a window and never shorten one" in out["ratchet_note"]
    assert "PARTIALLY fed, not" in out["ratchet_note"]


def test_a_deep_container_deepens_the_window():
    """A 2000-day declaration is proof the containers can be fed to 2021."""
    out = effective_history_floor(_code(2000), END, run_date=END)
    assert out["effective"] == "2021-02-11"
    assert out["deepened"] is True
    assert out["binding_leg"] == "data_path"
    assert "ratcheted_from" not in out


def test_the_reach_follows_the_wall_clock_when_the_holdout_is_backdated():
    """THE D20 REPAIR. The container's bar URL has no end date.

    A holdout ending 2025-01-01 (the date 34 of the 41 stored candidates use)
    run today does NOT get bars back to 2019: it gets the last 2,000 days ending
    at the run date. Anchoring on the holdout made the window open before the
    first bar the container would ever see, and made the starved-fold counter
    below report zero.
    """
    backdated = effective_history_floor(_code(2000), "2025-01-01",
                                        run_date="2026-08-23")
    assert backdated["data_path"] == "2021-03-02"
    assert backdated["data_path_reach_asof"] == "2026-08-23"
    assert backdated["data_path_reach_basis"] == "wall clock"
    # The defect, stated as the comparison: the old anchor claimed 2019-07-12,
    # computed here rather than written down so the assertion cannot drift.
    from datetime import date, timedelta
    old = (date.fromisoformat("2025-01-01") - timedelta(days=2000)).isoformat()
    assert old.startswith("2019")
    assert backdated["data_path"] > old


def test_an_unknown_reach_deepens_nothing():
    """UNKNOWN IS NOT UNLIMITED, and this is where that rule is enforced.

    An algorithm declaring no lookback gets the endpoint's 180-day default —
    the SHALLOWEST data path in the repo, not the deepest. Treating the unknown
    as non-binding would hand it a 33-year window fed by six months of bars.
    """
    out = effective_history_floor("class X: pass", END)
    assert out["data_path"] is None
    assert out["effective"] == HISTORY_FLOOR_RATCHET
    assert out["deepened"] is False
    assert "UNKNOWN" in out["data_path_note"]
    assert out["binding_leg"] == "ratchet (data-path reach unknown)"


def test_two_different_declared_lookbacks_are_unknown_not_the_larger():
    """The static reader declines on ambiguity; the floor must decline with it."""
    code = 'a = f"?lookback_days=700"\nb = f"?lookback_days=2000"\n'
    out = effective_history_floor(code, END)
    assert out["data_path"] is None
    assert out["effective"] == HISTORY_FLOOR_RATCHET


def test_a_genuinely_shallower_feed_beats_every_other_leg():
    """No container can serve a bar that does not exist."""
    out = effective_history_floor(_code(2000), END, floor="2025-01-01")
    assert out["effective"] == "2025-01-01"
    assert out["binding_leg"] == "configured"


def test_the_floor_is_READ_from_the_constants_not_hardcoded():
    """MOVE both constants and the answer must move with them."""
    out = effective_history_floor(_code(2000), END, floor="1999-09-09",
                                  ratchet="2010-01-01", run_date=END)
    assert out["ratchet"] == "2010-01-01"
    assert out["configured"] == "1999-09-09"
    # data path 2021-02-11 is LATER than a 2010 ratchet, so it is refused
    assert out["effective"] == "2010-01-01"
    assert out["ratcheted_from"] == "2021-02-11"


def test_the_ratchet_default_is_the_one_walkforward_holds(monkeypatch):
    """MOVE IT AT THE SOURCE. The value lives in walkforward now and factory
    re-exports it; a factory-local copy would agree today and drift tomorrow.

    Moved rather than compared, because ``factory.HISTORY_FLOOR_RATCHET ==
    walkforward.HISTORY_FLOOR_RATCHET`` cannot distinguish one object from two
    literals that happen to match.
    """
    import app.fund.factory as f
    import app.fund.walkforward as wf
    assert f.HISTORY_FLOOR_RATCHET is wf.HISTORY_FLOOR_RATCHET
    # `is` alone rests on CPython not interning this literal, which is true for
    # a dashed date and is not a guarantee. So the SHAPE is asserted too: the
    # factory-side assignment must bind a NAME, never spell the date again.
    import ast
    from pathlib import Path
    tree = ast.parse((Path(f.__file__)).read_text(encoding="utf-8"))
    rhs = [n.value for n in tree.body if isinstance(n, ast.Assign)
           and any(getattr(t, "id", None) == "HISTORY_FLOOR_RATCHET"
                   for t in n.targets)]
    assert len(rhs) == 1 and isinstance(rhs[0], ast.Name), (
        "factory re-declares the ratchet date instead of re-exporting it")
    monkeypatch.setattr(f, "HISTORY_FLOOR_RATCHET", "2018-03-04")
    out = f.effective_history_floor(_code(700), END, run_date=END)
    assert out["ratchet"] == "2018-03-04"
    # 700 days reaches 2024-09-03, LATER than a 2018 ratchet, so still refused.
    assert out["effective"] == "2018-03-04"


# --- per-symbol availability is reported absent, never assumed --------------


def test_per_symbol_availability_is_declared_unmeasured():
    """SPY 1993-01-29 vs UUP 2007-03-01 is fourteen years of spread.

    The belt does not measure it at plan time and must say so rather than let a
    reader assume every leg reaches the floor. Reporting the archive's earliest
    row instead would be worse than silence: it is a lower bound on
    availability, so it would shorten windows on the strength of our own fetch
    history.
    """
    out = effective_history_floor(_code(2000), END)
    assert out["per_symbol"] is None
    assert "LOWER BOUND" in out["per_symbol_note"]
    assert "truncation detector" in out["per_symbol_note"]


# --- the verdict records the window it looked at ----------------------------


def test_the_gate_records_how_deep_the_belt_looked():
    from app.fund.gate import evaluate
    out = evaluate({}, walkforward={
        "folds_measurable": 4, "folds_retained": 3,
        "history_floor": {"effective": "2021-02-11", "binding_leg": "data_path",
                          "data_path": "2021-02-11", "deepened": True},
        "folds_before_data_path_reach": 0})
    got = out["checks"]["walkforward_history_floor"]
    assert got["effective"] == "2021-02-11"
    assert got["deepened"] is True
    assert got["folds_before_data_path_reach"] == 0


def test_a_walkforward_that_never_stated_its_window_says_UNSTATED():
    """Every verdict stored before this shipped is in this branch."""
    from app.fund.gate import evaluate
    out = evaluate({}, walkforward={"folds_measurable": 4, "folds_retained": 3})
    got = out["checks"]["walkforward_history_floor"]
    assert got["effective"] is None
    assert "UNSTATED, not default" in got["note"]


def test_no_walkforward_means_no_window_label():
    from app.fund.gate import evaluate
    assert "walkforward_history_floor" not in evaluate({})["checks"]


# --- the pair is ordered, and the order is checkable ------------------------


def test_the_deeper_floor_is_judged_by_the_scaled_requirement():
    """(b) MUST NEVER SHIP ALONE — the flip alone is a measured loosening, and
    the single copy of that measurement is in ``gate.py`` beside
    ``GATE_VERSION``. This asserts the MECHANISM that prevents it: a window
    deepened past what the pre-v4.3 floor supplied is required to produce
    proportionally more folds."""
    from app.fund.gate import folds_required
    from app.fund.walkforward import window_for_strategy

    deep = effective_history_floor(_code(2000), END, run_date=END)["effective"]
    plan = window_for_strategy(END, 21, min_folds=4, floor=deep)
    need = folds_required({"requested_folds": plan["folds"]})
    assert need["scaled"] is True
    assert need["required"] > 4, need


@pytest.mark.parametrize("hold", list(range(1, 200)))
def test_a_ratcheted_candidate_is_planned_exactly_as_before(hold):
    """The 700-day majority — and every algorithm that declares nothing — must
    see the identical fold plan they saw under the old constant.

    Widened from eight holds to the generator's real domain in D20, for the same
    reason the fold-density acceptance test was: the adversary broke the eight.
    """
    from app.fund.walkforward import window_for_strategy
    floor = effective_history_floor(_code(700), END, run_date=END)["effective"]
    before = window_for_strategy(END, hold, min_folds=4, floor="2024-02-26")
    after = window_for_strategy(END, hold, min_folds=4, floor=floor)
    assert after["folds"] == before["folds"]


# --- THE GEOMETRY CENSUS: what actually ships, and nothing else --------------


def test_the_repo_ships_exactly_the_geometries_that_were_measured():
    """FAIL ON THE NEXT AUTHOR, not on the next reviewer.

    The v4.3 false-pass table (gate.py, beside GATE_VERSION) is measured PER
    WINDOW GEOMETRY, and the CEO's acceptance criterion is per geometry too. It
    covers exactly two, because every algorithm in this repo holds 21 days and
    only the two that declare ``lookback_days=2000`` reach past the ratchet.

    An algorithm with a different HOLD_DAYS, or a deeper declared lookback,
    creates a geometry NOBODY HAS MEASURED — and it would ship silently under a
    table that does not describe it. This is the census pattern: enumerate the
    real population, classify every member, fail on the unclassified.

    To extend the set you must MEASURE the new geometry
    (``scratchpad/d20_fp.py``) and add its row to the gate's table. Editing this
    list without that is the thing it exists to stop.
    """
    from pathlib import Path

    from app.fund.gate import CRITERIA, folds_required
    from app.fund.walkforward import declared_hold_days, window_for_strategy

    measured = {
        # (hold_days, effective floor, folds planned, folds required)
        (21, "2024-02-26", 4, 4),
        (21, "2021-03-02", 12, 9),
    }
    root = Path(__file__).resolve().parents[1] / "lean_workspace" / "algorithms"
    end = "2026-08-23"          # the fixed date the table was measured at
    anchor = int(CRITERIA["min_walkforward_folds"])
    # "The repo SHIPS" means tracked files: the quant's sandbox also holds
    # UNTRACKED one-off instrument-calibration algorithms (the meta_ctrl_*
    # positive controls, 2026-08-23) whose geometry deliberately has no
    # false-pass row — they measure the instrument, they are not candidates.
    # Sweeping untracked scratch made this test red on the live tree only,
    # while every worktree (tracked files only) stayed green.
    import subprocess
    tracked = subprocess.run(
        ["git", "ls-files", "lean_workspace/algorithms"],
        capture_output=True, text=True, cwd=root.parents[1]).stdout
    tracked_dirs = {line.split("/")[2] for line in tracked.splitlines()
                    if line.count("/") >= 2}
    # MACHINERY INSTRUMENTS ARE A CLASS, NOT AN OMISSION (2026-08-27). The
    # hyg_fast_flip_probe became TRACKED the night its session went live —
    # the algorithm trading the book belongs in the record — which promoted
    # it into this census. It is deliberately barred from the belt (no gate
    # verdict, by argument; quant dispatch #7), so its geometry will never
    # judge a candidate and a false-pass row for it would be a measurement
    # nothing consumes. The exemption is DOUBLE-KEYED so neither key alone
    # suffices: the name must be in this list (a reviewed diff) AND the
    # file's own first line must declare it an instrument. An algorithm
    # claiming the docstring without the list fails the census; a list entry
    # whose file dropped the claim fails loudly here.
    INSTRUMENTS_NOT_CANDIDATES = {"hyg_fast_flip_probe"}
    seen, missing = set(), []
    for d in sorted(p for p in root.iterdir()
                    if p.is_dir() and p.name in tracked_dirs):
        src = sorted(d.glob("*.py"))
        if not src:
            continue
        code = (d / "main.py").read_text(encoding="utf-8", errors="replace") \
            if (d / "main.py").exists() else \
            src[0].read_text(encoding="utf-8", errors="replace")
        if d.name in INSTRUMENTS_NOT_CANDIDATES:
            head = "\n".join(code.splitlines()[:5])
            assert "MACHINERY INSTRUMENT, NOT A CANDIDATE" in head, (
                f"{d.name} is exempted as a machinery instrument but its file "
                f"no longer declares itself one — re-measure or re-declare.")
            continue
        hold = declared_hold_days(code)["hold_days"]
        floor = effective_history_floor(code, end, run_date=end)["effective"]
        need = anchor
        plan = window_for_strategy(end, hold, min_folds=need, floor=floor)
        for _ in range(4):
            req = int(folds_required({"requested_folds": plan["folds"]})["required"])
            if req <= need:
                break
            need = req
            plan = window_for_strategy(end, hold, min_folds=need, floor=floor)
        key = (hold, floor, len(plan["folds"]), need)
        seen.add(key)
        if key not in measured:
            missing.append((d.name, key))
    assert not missing, (
        f"these algorithms ship a window geometry with no measured false-pass "
        f"row: {missing}. Measure it before it ships.")
    assert seen == measured, (
        f"the measured set has rows nothing ships any more: {measured - seen}. "
        f"A table describing geometries the fleet no longer produces is the "
        f"stale-number defect, so remove the row with the algorithm.")


def test_the_null_audit_preflight_plans_the_window_the_belt_would_plan():
    """The calibration instrument must run the gate's geometry, not its own.

    ``scripts/null_audit.py`` read ``WALKFORWARD_HISTORY_FLOOR`` directly, which
    since v4.3 is the FEED's start (1993) and not the depth any candidate is
    allowed. A false-positive rate measured over a window the belt would never
    plan calibrates a gate the fund does not run.
    """
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "_null_audit", root / "scripts" / "null_audit.py")
    mod = importlib.util.module_from_spec(spec)
    argv = sys.argv
    sys.argv = ["null_audit.py"]      # it parses seeds out of argv at import
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = argv
    # READ THE AST, NOT THE TEXT. A text scan finds the constant's NAME in the
    # docstring that explains why it is no longer used — this test failed on its
    # own prose the first time it ran.
    import ast
    tree = ast.parse((root / "scripts" / "null_audit.py").read_text(encoding="utf-8"))
    imported = {a.name for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "effective_history_floor" in imported
    assert "WALKFORWARD_HISTORY_FLOOR" not in imported, (
        "the preflight is reading the raw feed floor again")
    # And it RUNS: a preflight that raises is a two-hour measurement that never
    # starts, so the smoke pass is part of the guard.
    mod.preflight()


# --- the count of starved folds is a count or an absence, never a zero -------


def test_an_uncountable_reach_reports_absent_not_zero():
    """The gate's own history-floor block used to render this as nothing.

    An algorithm that declares no lookback has an UNKNOWN reach, so the number
    of folds starting before it cannot be counted. Until D20 the key was simply
    absent from the payload, which reads as "no fold was starved" to a human and
    to the verdict block that carries it.
    """
    from app.fund.gate import evaluate
    out = evaluate({}, walkforward={
        "folds_measurable": 4, "folds_retained": 3,
        "history_floor": {"effective": "2024-02-26", "binding_leg":
                          "ratchet (data-path reach unknown)", "data_path": None,
                          "deepened": False},
        "folds_before_data_path_reach": None,
        "folds_before_data_path_reach_note":
            "UNCOUNTABLE: this algorithm declares no single lookback_days"})
    got = out["checks"]["walkforward_history_floor"]
    assert got["folds_before_data_path_reach"] is None
    assert "UNCOUNTABLE" in got["folds_before_data_path_reach_note"]


def test_the_belt_writes_the_uncountable_marker_itself():
    """Not just the gate carrying it — the PRODUCER has to emit it.

    A test that hands the gate a hand-built payload proves the gate reads the
    key; it cannot prove anything writes it (D17's uncalled-helper lesson). This
    drives the real ``CandidateFactory._walkforward`` with an algorithm that
    declares no lookback, on a holdout too short to fit the folds — the NOT
    TESTABLE exit, which until D20 emitted no reach report at all.
    """
    from app.fund.factory import CandidateFactory

    class _Runner:
        def get_algorithm(self, name):
            return {"code": "class X:\n    pass\n"}

        def submit_sweep(self, *a, **k):
            raise AssertionError("a not-testable plan must never reach the engine")

    f = CandidateFactory.__new__(CandidateFactory)
    f._runner = _Runner()
    out, err = f._walkforward(
        "x", {"slip": ["0.0005"]},
        {"train_start": "2024-02-26", "train_end": "2025-02-25",
         "test_start": "2025-02-26", "test_end": "2025-06-27"})
    assert err is None, err
    assert out["not_testable"] is True
    assert out["folds_before_data_path_reach"] is None
    assert "not a count of zero" in out["folds_before_data_path_reach_note"]


def test_the_belt_counts_starved_folds_on_the_real_path():
    """The other half: a declared reach gives a NUMBER, and the number is real.

    Measured on the 700-day majority — two of the four planned folds already
    begin before the containers' first bar, and nothing said so before v4.3.
    """
    from app.fund.factory import CandidateFactory

    class _Runner:
        def get_algorithm(self, name):
            return {"code": _code(700)}

        def submit_sweep(self, *a, **k):
            raise AssertionError("this test must not reach the engine")

    f = CandidateFactory.__new__(CandidateFactory)
    f._runner = _Runner()
    # A holdout too short to fit four folds, so the not-testable exit is taken
    # before any container is asked for; the reach report is what is under test.
    out, err = f._walkforward(
        "x", {"slip": ["0.0005"]},
        {"train_start": "2024-02-26", "train_end": "2025-02-25",
         "test_start": "2025-02-26", "test_end": "2025-06-27"})
    assert err is None, err
    assert out["folds_before_data_path_reach"] == len(out["requested_folds"])
    assert out["history_floor"]["data_path_lookback_days"] == 700
