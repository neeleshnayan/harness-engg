"""Gate v5 candidate rules, measured against the fakes that killed v4 and the sketch.

The v5 sketch in BENCHMARK_BLIND_WALKFORWARD_2026-08-18.md was KILLED by
adversarial review on four demonstrated counts:

  1. subtracting 1x the benchmark removes beta = 1 only — a 2x levered null
     passed 4-of-4 folds under the "fix"
  2. plain excess kills every defensive PREMIA candidate by construction
     (negative excess in every rising fold -> unexaminable forever)
  3. MIN_TRAIN_RETURN_PCT was left unresolved on the excess scale
  4. the doc's tables had no reproduction path

This script is the reproduction path, and it measures the REDESIGN:

  * ALPHA claims: BETA-ADJUSTED excess. Beta is estimated on the train leg only
    (OLS on daily returns) and applied out-of-sample to both legs:
    excess_t = strat_t - beta_train * bench_t. On the excess scale a train leg
    below the floor is a FAILED fold for an alpha claim, not an absence — with
    beta removed, "no excess in training" IS evidence of no alpha, which was
    not true on raw returns where a flat market was ambiguous.
  * PREMIA claims: no excess at all. A fold is retained if the strategy's
    TEST-leg Sharpe exceeds the benchmark's test-leg Sharpe. Paired, per fold,
    majority rule — the criterion the premia mandate actually states.

Every arm is seeded. Every table in GATE_V5_DESIGN_2026-08-19.md comes from
running this file with its printed command line.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import zlib

sys.path.insert(0, ".")

TRAIN, TEST, N = 252, 84, 630
NEED_FOLDS = 4           # v4's min_walkforward_folds at a 21-day hold
RETENTION_FLOOR = 0.5    # same floor as walkforward.RETENTION_FLOOR


def _series(sharpe: float, vol: float, n: int, rng: random.Random) -> list[float]:
    dsig = vol / math.sqrt(252.0)
    dmu = sharpe * vol / 252.0
    return [dmu + dsig * rng.gauss(0.0, 1.0) for _ in range(n)]


def _make(bench: list[float], beta: float, a_sharpe: float, a_vol: float,
          rng: random.Random) -> list[float]:
    """A strategy = beta x benchmark + an independent alpha stream."""
    alpha = _series(a_sharpe, a_vol, len(bench), rng)
    return [beta * b + a for b, a in zip(bench, alpha)]


def _cum_pct(rets, a, b) -> float:
    acc = 1.0
    for r in rets[a:b]:
        acc *= (1.0 + r)
    return (acc - 1.0) * 100.0


def _ann_pct(rets, a, b) -> float:
    days = b - a
    if days <= 0:
        return 0.0
    cum = _cum_pct(rets, a, b) / 100.0
    return ((1.0 + cum) ** (252.0 / days) - 1.0) * 100.0


def _sharpe(rets, a, b) -> float:
    xs = rets[a:b]
    n = len(xs)
    if n < 20:
        return 0.0
    mu = sum(xs) / n
    var = sum((x - mu) ** 2 for x in xs) / n
    return (mu / math.sqrt(var) * math.sqrt(252.0)) if var > 1e-18 else 0.0


def _beta(strat, bench, a, b) -> float:
    """OLS slope on daily returns, train leg only. Out-of-sample thereafter."""
    xs, ys = bench[a:b], strat[a:b]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var <= 1e-18:
        return 1.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / var


def _folds():
    out, k = [], 0
    while (k + 1) * TEST + TRAIN <= N:
        t0 = k * TEST
        out.append((t0, t0 + TRAIN, t0 + TRAIN + TEST))
        k += 1
    return out


# --- the four rules under measurement ------------------------------------------

def rule_v4_raw(strat, bench, floor_pct: float) -> bool:
    """What v4 does today: raw retention, MIN_TRAIN_RETURN_PCT on raw scale."""
    meas = ret = 0
    for t0, t1, t2 in _folds():
        tr = _cum_pct(strat, t0, t1)
        if tr < 5.0:                      # the raw-scale floor in force
            continue                      # unmeasurable
        tr_a, te_a = _ann_pct(strat, t0, t1), _ann_pct(strat, t1, t2)
        meas += 1
        if tr_a > 0 and te_a / tr_a >= RETENTION_FLOOR:
            ret += 1
    return meas >= NEED_FOLDS and ret * 2 > meas


def rule_naive_excess(strat, bench, floor_pct: float) -> bool:
    """The KILLED sketch: subtract 1x benchmark; floor question unresolved
    (kept at the raw-scale 5.0, which is what an unthinking port would do)."""
    exc = [s - b for s, b in zip(strat, bench)]
    return rule_v4_raw(exc, bench, floor_pct)


def rule_v5_alpha(strat, bench, floor_pct: float) -> bool:
    """Beta-adjusted excess. Train excess below floor = FAILED fold, not absent."""
    meas = ret = 0
    for t0, t1, t2 in _folds():
        beta = _beta(strat, bench, t0, t1)
        exc = [s - beta * b for s, b in zip(strat, bench)]
        tr_a, te_a = _ann_pct(exc, t0, t1), _ann_pct(exc, t1, t2)
        meas += 1                          # ALWAYS measurable for an alpha claim
        # The strict-positive guard is separate from the floor and survives a
        # floor of 0: a ratio against a zero-or-negative denominator is the
        # 1379%-retention disease, and it reappears on the excess scale the
        # moment the floor alone is trusted to prevent it.
        if tr_a <= 0.0 or tr_a < floor_pct:
            continue                       # measurable and NOT retained
        if te_a / tr_a >= RETENTION_FLOOR:
            ret += 1
    return meas >= NEED_FOLDS and ret * 2 > meas


def rule_v5_premia(strat, bench, floor_pct: float) -> bool:
    """Paired test-leg Sharpe vs the benchmark, per fold, strict majority."""
    meas = ret = 0
    for t0, t1, t2 in _folds():
        meas += 1
        if _sharpe(strat, t1, t2) > _sharpe(bench, t1, t2):
            ret += 1
    return meas >= NEED_FOLDS and ret * 2 > meas


RULES = {"v4_raw": rule_v4_raw, "naive_excess": rule_naive_excess,
         "v5_alpha": rule_v5_alpha, "v5_premia": rule_v5_premia}

#: The processes. Every one is labelled with the verdict a correct gate should
#: reach for it under each claim type.
PROCESSES = [
    # name              beta  a_sharpe a_vol  should pass: alpha?  premia?
    ("null_beta1",       1.0,   0.0,   0.00,  False,  False),
    ("null_beta2",       2.0,   0.0,   0.00,  False,  False),   # the kill's fake
    ("premia_defensive", 0.5,   0.5,   0.06,  False,  True),    # lower raw return, better Sharpe
    ("alpha_S0.6",       1.0,   0.6,   0.10,  True,   False),   # real alpha, modest
    ("alpha_S1.0",       1.0,   1.0,   0.10,  True,   False),   # real alpha, good
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--market-sharpe", type=float, default=1.0,
                    help="drift of the benchmark; 1.0 matches the regime that "
                         "produced seed 55")
    ap.add_argument("--vol", type=float, default=0.20)
    ap.add_argument("--seed", type=int, default=20260819)
    ap.add_argument("--alpha-floor", type=float, default=2.0,
                    help="MIN_TRAIN_EXCESS floor (annualised pct) for v5_alpha")
    ap.add_argument("--floor-sweep", action="store_true",
                    help="sweep the v5_alpha floor instead of the main table")
    a = ap.parse_args()

    if a.floor_sweep:
        print(f"v5_alpha floor sweep | market Sharpe {a.market_sharpe} | "
              f"{a.draws} draws")
        names = [p for p in PROCESSES if p[0] != "premia_defensive"]
        header = "".join(f"{p[0]:>14}" for p in names)
        print(f"{'floor%':>8}{header}")
        for floor in (0.0, 1.0, 2.0, 3.0, 5.0):
            cells = []
            for name, beta, ash, avol, *_ in names:
                rng = random.Random(a.seed + int(floor * 100))
                hits = 0
                for _ in range(a.draws):
                    bench = _series(a.market_sharpe, a.vol, N, rng)
                    strat = _make(bench, beta, ash, avol, rng)
                    hits += rule_v5_alpha(strat, bench, floor)
                cells.append(f"{100.0 * hits / a.draws:>13.1f}%")
            print(f"{floor:>8.1f}{''.join(cells)}")
        print()
        print("pick the floor from this table, in the open - the raw-scale 5.0")
        print("was never re-derived for the excess scale, which was kill point 3.")
        return 0

    print(f"gate v5 audit | market Sharpe {a.market_sharpe} | vol {a.vol:.0%} | "
          f"{a.draws} draws | alpha floor {a.alpha_floor}%")
    print(f"{'process':>18}{'v4_raw':>9}{'naive_exc':>11}{'v5_alpha':>10}"
          f"{'v5_premia':>11}   correct verdict")
    for name, beta, ash, avol, ok_alpha, ok_premia in PROCESSES:
        row = {}
        for rname, rule in RULES.items():
            # zlib.crc32, not hash(): Python salts hash() per process, which
            # would make "seeded" a lie — the exact class of unreproducible
            # number the adversary killed the previous doc over.
            rng = random.Random(a.seed + zlib.crc32((name + rname).encode()))
            hits = 0
            for _ in range(a.draws):
                bench = _series(a.market_sharpe, a.vol, N, rng)
                strat = _make(bench, beta, ash, avol, rng)
                floor = a.alpha_floor if rname == "v5_alpha" else 5.0
                hits += rule(strat, bench, floor)
            row[rname] = 100.0 * hits / a.draws
        want = (f"alpha={'PASS' if ok_alpha else 'fail'} "
                f"premia={'PASS' if ok_premia else 'fail'}")
        print(f"{name:>18}{row['v4_raw']:>8.1f}%{row['naive_excess']:>10.1f}%"
              f"{row['v5_alpha']:>9.1f}%{row['v5_premia']:>10.1f}%   {want}")
    print()
    print("read the null_beta2 column: v4_raw and naive_excess both pass the")
    print("levered fake at high rates - that is the demonstrated kill. v5_alpha")
    print("must hold it near the false-positive floor, and v5_premia must reject")
    print("it because leverage preserves Sharpe (it cannot BEAT the benchmark's).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
