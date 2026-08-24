"""THE LUCK-FILTER CALIBRATION. The level is DATA, not taste.

WHAT THIS ANSWERS. The chair's ruling (cto.md, 2026-08-24) restored `min_psr_pct`
to its documented job — a target-ZERO luck filter — and set the level by
measurement under a hard invariant: **full-gauntlet zero-skill false passes may
not rise above today's measured rate**. With its own falsifier attached: if no
level holds, the shipped configuration keeps the ~1.34-equivalent hurdle with the
sentence corrected to say what it is.

THE POPULATION is the adversary's: Dirichlet random weights over a risky
universe, rebalanced monthly, judged against equal-weight buy-and-hold of the
same universe (`scripts/instruments/adv23/probe8.py`). Zero skill by
construction — the weights are noise — so every pass is a false pass.

=== THE INVARIANT IS TESTED BY SET INCLUSION, NOT BY A RATE ===

Comparing two false-pass RATES on the same sample answers a weaker question than
the ruling asks, because the other eleven criteria are what actually refuse most
of this population and their behaviour is not modelled here. So the harness
reports, per draw, whether the SHIPPED configuration passed and whether the
CANDIDATE configuration passed, and checks

    {draws the candidate admits}  subset-of  {draws the shipped bar admits}

If that holds, the full-gauntlet pass set is a subset of today's WHATEVER the
other criteria do — they are unchanged and are applied to both arms identically,
so they can only remove members from both sides. That is a set argument and it
does not depend on modelling the rest of the gauntlet at all. The rates are
reported beside it because they are what a reader wants to see; the inclusion is
what the decision rests on.

=== THE SHIPPED ARM IS AN EMULATION, AND THAT IS SAID LOUDLY ===

Today's criterion reads LEAN's published `Probabilistic Sharpe Ratio`, and LEAN
is not run over a synthetic series — there is no engine figure for a draw that
never entered a container. So the shipped arm is EMULATED as a PSR at the target
the engine's own statistic was inverted to on this fund's real candidates:
0.0755 per observation (quant, run-quant-metacontrols; independently reproduced
here on the four controls at 0.0700 / 0.0780 / 0.0748 / 0.0792, mean 0.0755).
The emulation is swept across that whole measured range, so a conclusion that
depends on the exact target shows up as a disagreement between the endpoints
rather than as a number nobody questioned.

=== THE SECOND TABLE: THE PREMIA MARGIN ===

The adversary's blind KILL of the cash-carry credit (trace 9fb82050) measured the
correction moving this same population from 36.0% to 50.5% false passes at the
700-day window, because `premia_min_sharpe_advantage` is 0.0 — a margin silently
calibrated against the bias the credit removes. So the same harness runs the
premia inequality under BOTH arms (uncredited = shipped, credited) across
candidate margins, by the same rule: the lowest margin holding the credited arm's
false passes at or below the shipped arm's measured rate.

Usage:
    python scripts/instruments/d36/calibrate.py --data <dir> [--draws N] [--seed S]

The data directory holds one `<SYMBOL>.json` per name, in the shape
`{"dates": [...], "closes": [...]}` — the adversary's pinned fixtures.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..", "..")))

from app.fund import gate                                    # noqa: E402
from app.fund import statistics as st                        # noqa: E402
from app.fund.leanrunner import premia_inputs                # noqa: E402

#: The universe the adversary's zero-skill population is drawn over, and the
#: cash name the premia bar reads. Held here rather than passed in: a population
#: that changes between runs is not a population, it is two.
RISKY = ["SPY", "QQQ", "IWM", "TLT", "XLK", "XLE", "XLF", "XLV"]
CASH = "BIL"

#: The engine's implied target, per observation, and the measured range it moved
#: over on the four control candidates. The shipped arm is emulated at all three
#: so a conclusion resting on the midpoint is visible as such.
ENGINE_TARGET_MID = 0.0755
ENGINE_TARGET_RANGE = (0.0700, 0.0792)

#: THE LEVEL THE SHIPPED ARM IS MEASURED AT, PINNED — not read from
#: `gate.CRITERIA`.
#:
#: This instrument's whole job is to compare a candidate configuration against
#: the bar AS IT STOOD, and the change it justified moves that bar. Reading the
#: live criterion would make the script compare the new bar with itself the
#: moment the diff merges: the table in the `GATE_VERSION` note would stop being
#: reproducible by the instrument that produced it, and a re-calibration months
#: from now would silently measure nothing. 65.0 is the engine-statistic level
#: that shipped from gate v2 to v4.3 inclusive; override with --shipped-level to
#: re-baseline against a different past.
SHIPPED_ENGINE_LEVEL = 65.0

#: Belt-window geometries, in trading days, matching what the fleet declares
#: (`_declared_lookback_days`: 11 algorithms at 700, three at 900, two at 2000).
#: `"full"` is whatever the pinned feed actually shares across the universe and
#: is resolved at run time — the 2000-day geometry two algorithms declare is
#: NOT reachable on this feed (1,378 shared sessions), and a table that silently
#: omitted it would be reporting an absence as a non-result.
WINDOWS = {"700d": 700, "2000d": 2000, "full": None}


def load(data_dir: str, symbol: str) -> dict[str, float]:
    with open(os.path.join(data_dir, f"{symbol}.json"), encoding="utf-8") as fh:
        o = json.load(fh)
    return dict(zip(o["dates"], o["closes"]))


def equal_weight_curve(dates: list[str], px: dict, syms: list[str]
                       ) -> list[float]:
    """Equal-weight buy-and-hold of the universe: what `_add_benchmark` builds."""
    return [100.0 * sum(px[s][d] / px[s][dates[0]] for s in syms) / len(syms)
            for d in dates]


def dirichlet_returns(dates: list[str], px: dict, syms: list[str],
                      rnd: random.Random, every: int = 21,
                      with_cash: bool = False
                      ) -> tuple[list[float], dict[str, float], float]:
    """One zero-skill draw: Dirichlet weights, re-drawn monthly. No signal.

    ``with_cash`` gives the draw an INVESTED FRACTION drawn uniformly on
    [0.05, 1.0], and the cash remainder earns ZERO — which is what the engine
    pays on an idle balance and the whole reason the credit exists.

    THE CASH WEIGHT IS DRAWN SEPARATELY, NOT AS ONE MORE SIMPLEX SLOT. A cash
    slot inside a Dirichlet(1,...,1) over nine names gives a mean cash weight of
    exactly 1/9 — measured at 0.112 on the first run of this harness, against a
    kill that lives at 50-95%. That is probe8's population, and sampling it here
    would have measured the correction where it barely bites while a comment
    claimed otherwise (D29's lesson, and this time the harness's own output
    caught the claim). Uniform on [0.05, 1.0] spans the range the kill describes
    and keeps every draw genuinely invested in something.

    Returns the return series, the per-date INVESTED weight, and the average
    turnover per rebalance (which is what a cost sweep charges against).
    """
    def draw() -> list[float]:
        x = [rnd.gammavariate(1.0, 1.0) for _ in syms]
        t = sum(x)
        return [v / t for v in x]

    w = draw()
    invested = rnd.uniform(0.05, 1.0) if with_cash else 1.0
    out: list[float] = []
    weights: dict[str, float] = {dates[0]: invested}
    turnovers: list[float] = []
    for i in range(1, len(dates)):
        if i % every == 0:
            new = draw()
            turnovers.append(invested * sum(abs(a - b) for a, b in zip(new, w)))
            w = new
        out.append(invested * sum(
            w[j] * (px[s][dates[i]] / px[s][dates[i - 1]] - 1.0)
            for j, s in enumerate(syms)))
        weights[dates[i]] = invested
    turnover = (sum(turnovers) / len(turnovers)) if turnovers else 0.0
    return out, weights, turnover


def compounded_pct(returns: list[float]) -> float:
    total = 1.0
    for r in returns:
        total *= (1.0 + r)
    return (total - 1.0) * 100.0


def breakeven_bps(strat: list[float], bench: list[float], turnover: float,
                  rebalances: int) -> float | None:
    """The per-trade cost at which this draw stops beating its bar.

    Charged the way the belt's sweep charges it: a proportional cost on the
    turnover of each rebalance. Zero or negative when the draw never beat the
    bar in the first place — which is not a fragile edge, it is no edge, and the
    two must not share a number.
    """
    if turnover <= 0 or rebalances <= 0:
        return None
    gross = compounded_pct(strat) - compounded_pct(bench)
    if gross <= 0:
        return 0.0
    # Total cost in return points for c bps: rebalances * turnover * c/10_000,
    # compounding ignored at these magnitudes (the sweep's own approximation).
    return gross / (rebalances * turnover) * 100.0


def build_result(dates: list[str], strat: list[float], bench_rets: list[float],
                 bench_curve: list[float], weights: dict[str, float] | None,
                 turnover: float, rebalances: int, engine_psr: float | None
                 ) -> dict:
    """A belt result carrying this draw, with every field the gate reads DERIVED
    from the draw itself rather than stubbed clean.

    THE FULL GAUNTLET MEANS THE FULL GAUNTLET. An earlier version of this
    harness set the benchmark, the orders and the cost sweep to values that
    clear, on the argument that the other criteria are unchanged in both arms
    and therefore cancel. They do not cancel: the ruling's invariant is a
    SYSTEM rate, and a criterion that newly admits a draw the rest of the
    gauntlet would have refused anyway costs the system nothing. Measuring the
    marginal criterion in isolation answers a question nobody asked.
    """
    res = {
        "total_return_pct": compounded_pct(strat),
        "benchmark_return_pct": compounded_pct(bench_rets),
        "capacity": {"capacity_usd": 5_000_000.0},
        # ORDERS ARE COUNTED FROM THE CONSTRUCTION, not asserted: one order per
        # name per rebalance is what a monthly reweight of this basket places.
        "robustness": {"total_orders": rebalances * len(RISKY),
                       "psr_pct": engine_psr,
                       "costs": {"slippage_modelled": True}},
        "daily_returns": {"present": True, "dates": dates[1:],
                          "strategy": strat, "benchmark": bench_rets,
                          "benchmark_present": True, "n": len(strat)},
        "benchmark_curve": bench_curve,
        "benchmark_dates": dates,
        "benchmark_series_source": "recomputed_basket",
        "exposure": {"measurable": True, "max_gross": 1.0, "max_long": 1.0,
                     "max_short": 0.0, "observations": len(dates),
                     "series": [], "unclassified_series": [], "reason": None},
    }
    if weights is not None:
        res["invested_weight"] = {"measurable": True, "weights": weights,
                                  "n": len(weights), "reason": None}
    return res


def build_holdout(dates: list[str], strat: list[float], bench_rets: list[float],
                  rebalances: int) -> dict:
    """A 70/30 train/test split of the DRAW'S OWN series.

    The holdout criterion asks whether the edge survived data it was not chosen
    on. For a zero-skill draw there was no choosing, so retention is whatever
    noise hands back — which is the point: this is the criterion doing real work
    on the population, not a stub asserting it did.
    """
    cut = int(len(strat) * 0.7)
    tr, te = strat[:cut], strat[cut:]
    return {
        "state": "done", "dates_honoured": True,
        "train": {"return_pct": compounded_pct(tr),
                  "window": [dates[0], dates[cut]]},
        "test": {"return_pct": compounded_pct(te),
                 "total_orders": max(1, int(rebalances * 0.3) * len(RISKY)),
                 "window": [dates[cut], dates[-1]]},
    }


def build_walkforward(dates: list[str], strat: list[float], hold_days: int = 21
                      ) -> dict:
    """Four contiguous folds over the draw's own window, scored by the SHIPPED
    retention rule (`walkforward.retention`) rather than by a copy of it."""
    from app.fund.walkforward import retention as _retention

    n_folds = 4
    span = len(strat) // (n_folds + 1)
    folds, retentions, measurable = [], [], 0
    for i in range(n_folds):
        tr = strat[i * span:(i + 1) * span]
        te = strat[(i + 1) * span:(i + 2) * span]
        if len(tr) < 2 or len(te) < 2:
            continue
        r = _retention(compounded_pct(tr), compounded_pct(te),
                       max(1, len(te) // hold_days), len(tr), len(te))
        folds.append({"train_start": dates[i * span],
                      "train_end": dates[(i + 1) * span],
                      "test_start": dates[(i + 1) * span],
                      "test_end": dates[min((i + 2) * span, len(dates) - 1)]})
        if r.get("retention") is not None:
            measurable += 1
            retentions.append(r["retention"])
    retained = sum(1 for x in retentions if x >= 0.5)
    med = (sorted(retentions)[len(retentions) // 2] if retentions else None)
    return {"folds_attempted": n_folds, "folds_measurable": measurable,
            "folds_retained": retained, "median_retention": med,
            "requested_folds": folds}


#: Failure sentences carry the candidate's own numbers, so grouping on the text
#: gives one bucket per draw and answers nothing. These are the criteria, keyed
#: by a phrase that appears in exactly one of them. UNCLASSIFIED IS REPORTED,
#: never dropped: a sentence this list does not know is a criterion the census is
#: blind to, and a blind census reads as a criterion that never fires.
_CRITERION_PHRASES = (
    ("expensive way to hold", "must_beat_benchmark"),
    ("distinguishable from luck", "luck filter (target zero)"),
    ("SKILL HURDLE, NOT A LUCK TEST", "luck filter (engine hurdle)"),
    ("luck filter could not be applied", "luck filter UNMEASURABLE"),
    ("kept only", "min_holdout_retention"),
    ("of its edge", "min_holdout_retention"),
    ("retention could not be measured", "holdout retention UNMEASURABLE"),
    ("fold(s) could be measured", "walk-forward folds measurable"),
    ("bps floor", "min_breakeven_bps"),
    ("never cost-swept", "require_breakeven_measured"),
    ("unprofitable at every cost", "min_breakeven_bps (no edge at any cost)"),
    ("fills;", "min_orders"),
    ("capacity", "min_capacity_usd"),
    ("folds", "walk-forward folds"),
    ("retained", "walk-forward majority"),
    ("not priced", "require_priced"),
    ("premia", "premia leg"),
)


def classify(sentence: str) -> str:
    for phrase, name in _CRITERION_PHRASES:
        if phrase in sentence:
            return name
    return f"UNCLASSIFIED: {sentence[:44]}"


def psr_arm(strat: list[float], target: float) -> float | None:
    """The luck reading of one draw at one target. None when unmeasurable."""
    got = st.psr_from_series(strat, target)
    return got["psr_pct"] if got["measurable"] else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--draws", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20260824)
    ap.add_argument("--levels",
                    default="50,55,60,65,70,75,80,85,90,95,97.5,99,99.9")
    ap.add_argument("--margins", default="0.0,0.05,0.10,0.15,0.20,0.25,0.30")
    ap.add_argument("--shipped-level", type=float, default=SHIPPED_ENGINE_LEVEL)
    args = ap.parse_args()
    if args.draws < 2:
        # A population of one has no rate. Refused rather than divided by.
        ap.error("--draws must be at least 2; a false-pass RATE needs a "
                 "population and one draw is an anecdote")
    if not all(0.0 < lv < 100.0 for lv in
               [float(x) for x in args.levels.split(",")]):
        ap.error("every level must be a probability strictly inside (0, 100); "
                 "a level outside it is not a confidence, and the sweep would "
                 "report the impossible one as the answer")

    px = {s: load(args.data, s) for s in RISKY + [CASH]}
    all_dates = sorted(set.intersection(*[set(v) for v in px.values()]))
    levels = [float(x) for x in args.levels.split(",")]
    margins = [float(x) for x in args.margins.split(",")]

    print(f"population: Dirichlet zero-skill, {args.draws} draws/window, "
          f"seed {args.seed}, universe {'+'.join(RISKY)}")
    print(f"shipped arm EMULATED at target {ENGINE_TARGET_MID}/obs "
          f"(range {ENGINE_TARGET_RANGE[0]}..{ENGINE_TARGET_RANGE[1]}); "
          f"at the PINNED shipped level {args.shipped_level}% — "
          f"gate.CRITERIA reads {gate.CRITERIA['min_psr_pct']}% today, on a "
          f"DIFFERENT statistic, and is deliberately not used here\n")

    verdicts: dict[str, tuple] = {}
    for wname, wdays in WINDOWS.items():
        if wdays is None:
            wdays = len(all_dates) - 1
            print(f"NOTE  full: {wdays} shared sessions on the pinned feed")
        if len(all_dates) < wdays + 1:
            # STATED, NEVER SKIPPED SILENTLY. A window the data cannot reach is
            # a gap in the calibration, and a table that quietly omits a row a
            # reader expects is the absence-as-zero shape.
            print(f"NOTE  {wname}: the pinned feed shares only "
                  f"{len(all_dates)} sessions across this universe, so this "
                  f"geometry CANNOT BE MEASURED here and is absent from both "
                  f"tables — not passing, not failing, absent.")
            continue
        dates = all_dates[-(wdays + 1):]
        bench_curve = equal_weight_curve(dates, px, RISKY)
        bench_rets = [bench_curve[i] / bench_curve[i - 1] - 1.0
                      for i in range(1, len(bench_curve))]
        rebalances = max(1, (len(dates) - 1) // 21)
        rnd = random.Random(args.seed)
        rows = []
        for _ in range(args.draws):
            strat, weights, turnover = dirichlet_returns(
                dates, px, RISKY, rnd, with_cash=True)
            be = breakeven_bps(strat, bench_rets, turnover, rebalances)
            rows.append({
                "strat": strat, "weights": weights, "turnover": turnover,
                "breakeven_bps": be,
                "psr_engine_mid": psr_arm(strat, ENGINE_TARGET_MID),
                "psr_engine_lo": psr_arm(strat, ENGINE_TARGET_RANGE[0]),
                "psr_engine_hi": psr_arm(strat, ENGINE_TARGET_RANGE[1]),
                "psr_zero": psr_arm(strat, 0.0),
                "holdout": build_holdout(dates, strat, bench_rets, rebalances),
                "walkforward": build_walkforward(dates, strat),
                "sweep": {"breakeven_cost": {"breakeven_bps": be}},
            })
        verdicts[wname] = (dates, bench_curve, bench_rets, rebalances, rows)

    # === TABLE 1: the alpha luck level, THROUGH THE WHOLE GATE =============
    print("=== TABLE 1 — FULL-GAUNTLET zero-skill FALSE PASSES (alpha) ===")
    print("every draw is judged by `gate.evaluate` with its holdout, folds, "
          "cost sweep, orders and benchmark all derived from the draw itself.")
    print("the criterion-only column isolates what the luck filter alone "
          "admits, so the two can be told apart.\n")
    hdr = (f"{'window':8s} {'arm':32s} {'luck only':>10s} "
           f"{'FULL GATE':>10s} {'n':>6s} {'subset?':>8s}")
    print(hdr)
    print("-" * len(hdr))
    chosen: dict[str, float | None] = {}
    for wname, (dates, bcurve, brets, rebal, rows) in verdicts.items():
        n = len(rows)
        lvl_now = float(args.shipped_level)

        census: dict[str, int] = {}

        def run(basis: str, level: float, engine_key: str,
                tally: bool = False) -> tuple[set, set]:
            """(draws the luck filter alone admits, draws the WHOLE gate passes)"""
            luck_ok, gate_ok = set(), set()
            for i, r in enumerate(rows):
                val = r[engine_key] if basis == "engine_reported" else r["psr_zero"]
                if val is not None and val >= level:
                    luck_ok.add(i)
                res = build_result(dates, r["strat"], brets, bcurve,
                                   r["weights"], r["turnover"], rebal,
                                   r[engine_key])
                out = gate.evaluate(
                    res, r["holdout"], r["sweep"], walkforward=r["walkforward"],
                    criteria={"psr_basis": basis, "min_psr_pct": level})
                if out["passed"]:
                    gate_ok.add(i)
                elif tally:
                    # WHICH CRITERION ACTUALLY BINDS. Without this the table
                    # reports a flat full-gate rate and cannot say whether the
                    # luck filter is holding it or is irrelevant to it — and
                    # those two readings imply opposite decisions.
                    for f in out["failures"]:
                        key = classify(f)
                        census[key] = census.get(key, 0) + 1
            return luck_ok, gate_ok

        ship_luck, ship_gate = run("engine_reported", lvl_now, "psr_engine_mid",
                                   tally=True)
        print(f"{wname:8s} {'SHIPPED engine-equiv @ ' + str(lvl_now) + '%':32s} "
              f"{len(ship_luck) / n * 100:9.1f}% {len(ship_gate) / n * 100:9.1f}% "
              f"{n:6d} {'—':>8s}")
        for key, label in (("psr_engine_lo", "  same, target 0.0700"),
                           ("psr_engine_hi", "  same, target 0.0792")):
            lk, gt = run("engine_reported", lvl_now, key)
            print(f"{'':8s} {label:32s} {len(lk) / n * 100:9.1f}% "
                  f"{len(gt) / n * 100:9.1f}% {n:6d} {'—':>8s}")
        best = None
        for lv in levels:
            lk, gt = run("target_zero_module", lv, "psr_engine_mid")
            ok = gt <= ship_gate
            if ok and best is None:
                best = lv
            print(f"{'':8s} {'  target-0 @ ' + str(lv) + '%':32s} "
                  f"{len(lk) / n * 100:9.1f}% {len(gt) / n * 100:9.1f}% "
                  f"{n:6d} {('YES' if ok else 'no'):>8s}")
        chosen[wname] = best
        print(f"{'':8s} {'LOWEST LEVEL HOLDING THE INVARIANT':32s} "
              f"{str(best):>21s}")
        print(f"{'':8s} what refuses this population under the SHIPPED bar "
              f"({n - len(ship_gate)} of {n} refused):")
        for sentence, count in sorted(census.items(), key=lambda kv: -kv[1]):
            print(f"{'':10s} {count:4d}  {sentence}")
        print()

    # === TABLE 1b: POWER. A level chosen on false passes alone is half a
    # calibration, and the half it leaves out is the one the north star is
    # about. The positive arm is the SAME basket plus a genuine per-observation
    # edge, so the only thing that differs from the null population is skill.
    print("=== TABLE 1b — POWER: what each level does to a GENUINE edge ===")
    print("positive arm = the zero-skill basket plus a constant per-observation "
          "alpha, sized to the annualised Sharpe shown. Luck filter only — the "
          "other criteria are what Table 1 already measured.\n")
    hdr3 = (f"{'window':8s} {'true Sharpe':>11s} " +
            "".join(f"{('@' + str(lv)):>8s}" for lv in levels))
    print(hdr3)
    print("-" * len(hdr3))
    for wname, (dates, bcurve, brets, rebal, rows) in verdicts.items():
        for ann_sharpe in (0.5, 1.0, 1.5):
            rnd = random.Random(args.seed + 991)
            kept = {lv: 0 for lv in levels}
            trials = max(30, args.draws // 2)
            for _ in range(trials):
                strat, _w, _t = dirichlet_returns(dates, px, RISKY, rnd,
                                                  with_cash=True)
                _mu, sd = st.mean_std(strat)
                # A per-observation alpha that puts the TRUE Sharpe at the row's
                # figure, on the series' own clock (252 sessions here, since the
                # pinned feed is session-dated rather than calendar-padded).
                edge = ann_sharpe * sd / math.sqrt(252.0)
                boosted = [x + edge for x in strat]
                for lv in levels:
                    got = st.psr_from_series(boosted, 0.0)
                    if got["measurable"] and got["psr_pct"] >= lv:
                        kept[lv] += 1
            print(f"{wname:8s} {ann_sharpe:11.1f} " +
                  "".join(f"{kept[lv] / trials * 100:7.0f}%" for lv in levels))
    print()

    # === TABLE 2: the premia margin, both credit arms ======================
    print("=== TABLE 2 — premia inequality, zero-skill FALSE PASSES by margin ===")
    print("shipped arm = uncredited excess (premia_credit_idle_cash False); "
          "credited arm = idle cash credited.\n")
    hdr2 = (f"{'window':8s} {'margin':>7s} {'uncredited':>11s} "
            f"{'credited':>10s} {'<= shipped?':>12s}")
    print(hdr2)
    print("-" * len(hdr2))
    for wname, (dates, bcurve, brets, rebal, rows) in verdicts.items():
        # ONE rf source per window, read from the pinned cash file. The credit
        # and the subtraction are then the SAME SERIES by construction — there
        # is no second rate anywhere in this harness to drift from it, which is
        # the property the adversary's clearance condition 1 names.
        cashmap = {d: px[CASH][d] for d in dates}

        def rf_bars(sym, start, end, _c=cashmap):
            ds = [d for d in sorted(_c) if start <= d <= end]

            class _B:
                dates = ds
                closes = [_c[d] for d in ds]
                source = "pinned-fixture"
            return _B()

        built = []
        for r in rows:
            res = build_result(dates, r["strat"], brets, bcurve, r["weights"],
                               r["turnover"], rebal, r["psr_engine_mid"])
            res["premia_inputs"] = premia_inputs(res, rf_bars=rf_bars,
                                                 rf_symbol=CASH)
            built.append(res)
        n = len(built)
        cashw = [1.0 - sum(r["weights"].values()) / len(r["weights"])
                 for r in rows]
        print(f"{wname}: mean cash weight across draws "
              f"{sum(cashw) / len(cashw):.3f} "
              f"(min {min(cashw):.3f}, max {max(cashw):.3f}) — the population "
              f"the kill describes, not probe8's 11%")
        counts: dict[float, tuple[int, int]] = {}
        for m in margins:
            u = c = 0
            for res in built:
                for credit_on in (False, True):
                    pc = {**gate.PREMIA_CRITERIA,
                          "premia_min_sharpe_advantage": m,
                          "premia_credit_idle_cash": credit_on}
                    _leg, fails = gate._premia_leg(res, pc)
                    if not fails:
                        if credit_on:
                            c += 1
                        else:
                            u += 1
            counts[m] = (u, c)
        shipped_rate = counts[margins[0]][0] / n * 100 if n else 0.0
        for m in margins:
            u, cc = counts[m]
            ok = (cc / n * 100) <= shipped_rate + 1e-9 if n else False
            print(f"{wname:8s} {m:7.2f} {u / n * 100:10.1f}% "
                  f"{cc / n * 100:9.1f}% {('YES' if ok else 'no'):>12s}")
        holding = [m for m in margins
                   if (counts[m][1] / n * 100) <= shipped_rate + 1e-9]
        print(f"{'':8s} shipped (uncredited, margin {margins[0]:.2f}) rate = "
              f"{shipped_rate:.1f}%; LOWEST CREDITED MARGIN HOLDING IT: "
              f"{holding[0] if holding else 'NONE IN THE SWEEP'}\n")

    print("=== THE CHOICE ===")
    for wname, best in chosen.items():
        print(f"  {wname}: lowest target-0 level holding the inclusion = {best}")
    worst = [v for v in chosen.values() if v is not None]
    if len(worst) != len(chosen) or not worst:
        print("  NO LEVEL HOLDS ON EVERY WINDOW — the ruling's falsifier FIRES: "
              "ship engine_reported with the corrected sentence.")
        # THE FALSIFIER IS AN EXIT CODE, NOT A SENTENCE. A conclusion printed
        # into a log nobody greps is the unwired-kill-switch shape, and this
        # instrument exists to make exactly one decision.
        return 1
    print(f"  binding across windows (the strictest): {max(worst)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
