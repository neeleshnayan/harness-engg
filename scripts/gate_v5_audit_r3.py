"""Gate v5 ROUND 3 — the audit rebuilt on the two model defects the belt proved.

Round 2 died because its null generator could not produce the belt's nulls
(ADVERSARY_GATE_V5_2026-08-19.md): every 0.0% row came from fakes with EXACTLY
ZERO idiosyncratic vol, and the floor-sweep conclusions inherited it. The
validator's real-belt review (MIN_TRAIN_RETURN_REVIEW_2026-08-20.md) then
falsified the model twice more: belt null grid-point train legs average +22%
(the sim drew driftless), and the number every rule sees is a MAXIMUM over
surviving grid points (the sim drew once). Model 2.9% null pass vs belt 25%
(CI 8.5-65.1%) — the CI excludes the model.

This script fixes the generator and re-measures. Three upgrades, each mapped
to a named kill/finding:

  1. NOISY NULLS (round-2 kill, headline): every null carries idiosyncratic
     tracking vol. The round-2 table's own constructions are included verbatim
     (bench+3% noise, watered 0.9x+3%, the levered 2x+10%, beta drift
     0.5->2.0).
  2. GRID-MAX SELECTION (validator §5): each candidate is K=4 independent
     variants; the one with the best RAW cumulative return on the initial
     train window is selected, and the rules judge THAT one — matching
     leanrunner._sweep_summary's max(total_return_pct). --no-select measures
     the old single-draw behaviour for the delta.
  3. HISTORY SCALING (the register's blocking defect on min_walkforward_folds):
     --n parameterises history length; --scale-folds requires measurable folds
     >= ceil(SHARE * available) instead of the fixed 4, so a data extension
     cannot let a null win a majority of a small measurable subset.

Premia rule: round 2 measured strict paired-Sharpe as a per-fold coin flip on
noise (majority-of-4 ~31%). --premia-margin adds the significance margin the
kill demanded; the sweep prints the trade against the defensive-premia true
positive so the number is picked in the open.

Every arm is seeded (zlib.crc32, not salted hash()). Nothing here edits round
2's script or tables — this is a new measurement with its own file.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import zlib

sys.path.insert(0, ".")

TRAIN, TEST = 252, 84
RETENTION_FLOOR = 0.5
K_GRID = 4                    # surviving grid points the belt averages (~4 of 6)
MEASURABLE_SHARE = 0.75       # --scale-folds: measurable >= ceil(share*available)
FIXED_NEED = 4                # v4's fixed floor, for the unscaled comparison


def _series(sharpe: float, vol: float, n: int, rng: random.Random) -> list[float]:
    dsig = vol / math.sqrt(252.0)
    dmu = sharpe * vol / 252.0
    return [dmu + dsig * rng.gauss(0.0, 1.0) for _ in range(n)]


def _make(bench, beta0, beta1, a_sharpe, a_vol, rng) -> list[float]:
    """beta may DRIFT linearly beta0->beta1 across the series (round-2 fake #4);
    equal values = constant beta. Alpha stream independent of the bench."""
    n = len(bench)
    alpha = _series(a_sharpe, a_vol, n, rng)
    if beta0 == beta1:
        return [beta0 * b + a for b, a in zip(bench, alpha)]
    return [(beta0 + (beta1 - beta0) * i / (n - 1)) * b + a
            for i, (b, a) in enumerate(zip(bench, alpha))]


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
    if cum <= -1.0:
        return -100.0
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
    xs, ys = bench[a:b], strat[a:b]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var <= 1e-18:
        return 1.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / var


def _folds(n):
    out, k = [], 0
    while (k + 1) * TEST + TRAIN <= n:
        t0 = k * TEST
        out.append((t0, t0 + TRAIN, t0 + TRAIN + TEST))
        k += 1
    return out


def _select(bench, spec, rng, k_grid: int) -> list[float]:
    """Grid-max: K variants of the same process; the belt keeps the best RAW
    cumulative return on the initial train window. k_grid=1 = no selection."""
    beta0, beta1, ash, avol = spec
    best, best_ret = None, None
    for _ in range(max(1, k_grid)):
        s = _make(bench, beta0, beta1, ash, avol, rng)
        r = _cum_pct(s, 0, TRAIN)
        if best_ret is None or r > best_ret:
            best, best_ret = s, r
    return best


def _need(n_folds: int, scale: bool) -> int:
    if not scale:
        return FIXED_NEED
    return max(FIXED_NEED, math.ceil(MEASURABLE_SHARE * n_folds))


# --- the rules under measurement --------------------------------------------

def rule_v4_raw(strat, bench, n, *, floor=5.0, scale=False, margin=0.0) -> bool:
    folds = _folds(n)
    meas = ret = 0
    for t0, t1, t2 in folds:
        tr = _cum_pct(strat, t0, t1)
        if tr < floor:
            continue
        tr_a, te_a = _ann_pct(strat, t0, t1), _ann_pct(strat, t1, t2)
        meas += 1
        if tr_a > 0 and te_a / tr_a >= RETENTION_FLOOR:
            ret += 1
    return meas >= _need(len(folds), scale) and ret * 2 > meas


def rule_v5_alpha(strat, bench, n, *, floor=2.0, scale=False, margin=0.0) -> bool:
    folds = _folds(n)
    meas = ret = 0
    for t0, t1, t2 in folds:
        beta = _beta(strat, bench, t0, t1)
        exc = [s - beta * b for s, b in zip(strat, bench)]
        tr_a, te_a = _ann_pct(exc, t0, t1), _ann_pct(exc, t1, t2)
        meas += 1
        if tr_a <= 0.0 or tr_a < floor:
            continue
        if te_a / tr_a >= RETENTION_FLOOR:
            ret += 1
    return meas >= _need(len(folds), scale) and ret * 2 > meas


def rule_v5_premia(strat, bench, n, *, floor=0.0, scale=False,
                   margin=0.0) -> bool:
    """Paired TEST-leg Sharpe with a significance MARGIN — round 2 measured the
    strict inequality as a coin flip on any noisy null (majority ~31%)."""
    folds = _folds(n)
    meas = ret = 0
    for t0, t1, t2 in folds:
        meas += 1
        if _sharpe(strat, t1, t2) > _sharpe(bench, t1, t2) + margin:
            ret += 1
    return meas >= _need(len(folds), scale) and ret * 2 > meas


RULES = {"v4_raw": rule_v4_raw, "v5_alpha": rule_v5_alpha,
         "v5_premia": rule_v5_premia}

#: (name, beta0, beta1, a_sharpe, a_vol, should_alpha, should_premia)
#: The first five are the round-2 verdict's own constructions, verbatim.
PROCESSES = [
    ("null_noise3",      1.0, 1.0, 0.0, 0.03, False, False),
    ("null_watered",     0.9, 0.9, 0.0, 0.03, False, False),
    ("null_lev2_n10",    2.0, 2.0, 0.0, 0.10, False, False),
    ("null_drift.5-2",   0.5, 2.0, 0.0, 0.10, False, False),
    ("null_noise10",     1.0, 1.0, 0.0, 0.10, False, False),
    ("premia_defensive", 0.5, 0.5, 0.5, 0.06, False, True),
    ("alpha_S0.6",       1.0, 1.0, 0.6, 0.10, True,  False),
    ("alpha_S1.0",       1.0, 1.0, 1.0, 0.10, True,  False),
]


def _run_cell(rule, spec, args, n, seed_tag, *, floor, scale, margin,
              k_grid) -> float:
    rng = random.Random(args.seed + zlib.crc32(seed_tag.encode()))
    hits = 0
    for _ in range(args.draws):
        bench = _series(args.market_sharpe, args.vol, n, rng)
        strat = _select(bench, spec, rng, k_grid)
        hits += rule(strat, bench, n, floor=floor, scale=scale, margin=margin)
    return 100.0 * hits / args.draws


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=1500)
    ap.add_argument("--market-sharpe", type=float, default=1.0)
    ap.add_argument("--vol", type=float, default=0.20)
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--n", type=int, default=630, help="history length in days")
    ap.add_argument("--alpha-floor", type=float, default=2.0)
    ap.add_argument("--premia-margin", type=float, default=0.0)
    ap.add_argument("--no-select", action="store_true",
                    help="single draw per candidate (the round-2 model), for the delta")
    ap.add_argument("--scale-folds", action="store_true",
                    help="measurable >= ceil(0.75*available) instead of fixed 4")
    ap.add_argument("--margin-sweep", action="store_true")
    ap.add_argument("--history-sweep", action="store_true")
    args = ap.parse_args()
    k_grid = 1 if args.no_select else K_GRID

    hdr = (f"r3 audit | mktSharpe {args.market_sharpe} | vol {args.vol:.0%} | "
           f"n {args.n} ({len(_folds(args.n))} folds) | draws {args.draws} | "
           f"grid {'off' if k_grid == 1 else f'max-of-{k_grid}'} | "
           f"folds {'scaled' if args.scale_folds else 'fixed 4'} | "
           f"premia margin {args.premia_margin}")
    print(hdr)

    if args.margin_sweep:
        print(f"{'margin':>8}{'null_noise10':>14}{'null_lev2_n10':>15}"
              f"{'premia_defensive':>18}  (v5_premia pass rates)")
        for m in (0.0, 0.25, 0.5, 0.75, 1.0):
            cells = []
            for name in ("null_noise10", "null_lev2_n10", "premia_defensive"):
                spec = next(p[1:5] for p in PROCESSES if p[0] == name)
                cells.append(_run_cell(rule_v5_premia, spec, args, args.n,
                                       f"m{m}{name}", floor=0.0,
                                       scale=args.scale_folds, margin=m,
                                       k_grid=k_grid))
            print(f"{m:>8.2f}{cells[0]:>13.1f}%{cells[1]:>14.1f}%"
                  f"{cells[2]:>17.1f}%")
        print("pick the margin in the open: the null columns must reach the FP")
        print("budget while premia_defensive keeps a usable true-positive rate.")
        return 0

    if args.history_sweep:
        print(f"{'n(days)':>9}{'folds':>7}{'fixed4 null FPR':>17}"
              f"{'scaled null FPR':>17}{'fixed4 alphaS1 TP':>19}"
              f"{'scaled alphaS1 TP':>19}   (v5_alpha)")
        for n in (630, 1260, 2520):
            nulls = [p for p in PROCESSES if p[0].startswith("null_")]
            def fpr(scale):
                tot = 0.0
                for p in nulls:
                    tot += _run_cell(rule_v5_alpha, p[1:5], args, n,
                                     f"h{n}{scale}{p[0]}",
                                     floor=args.alpha_floor, scale=scale,
                                     margin=0.0, k_grid=k_grid)
                return tot / len(nulls)
            spec_a = next(p[1:5] for p in PROCESSES if p[0] == "alpha_S1.0")
            def tp(scale):
                return _run_cell(rule_v5_alpha, spec_a, args, n,
                                 f"h{n}{scale}a", floor=args.alpha_floor,
                                 scale=scale, margin=0.0, k_grid=k_grid)
            print(f"{n:>9}{len(_folds(n)):>7}{fpr(False):>16.1f}%"
                  f"{fpr(True):>16.1f}%{tp(False):>18.1f}%{tp(True):>18.1f}%")
        print("the register's defect, measured: the fixed-4 column must rise")
        print("with n if the defect is real; the scaled column must not.")
        return 0

    print(f"{'process':>18}{'v4_raw':>9}{'v5_alpha':>10}{'v5_premia':>11}"
          f"   correct verdict")
    for name, b0, b1, ash, avol, ok_a, ok_p in PROCESSES:
        row = {}
        for rname, rule in RULES.items():
            floor = (args.alpha_floor if rname == "v5_alpha"
                     else 0.0 if rname == "v5_premia" else 5.0)
            margin = args.premia_margin if rname == "v5_premia" else 0.0
            row[rname] = _run_cell(rule, (b0, b1, ash, avol), args, args.n,
                                   name + rname, floor=floor,
                                   scale=args.scale_folds, margin=margin,
                                   k_grid=k_grid)
        want = (f"alpha={'PASS' if ok_a else 'fail'} "
                f"premia={'PASS' if ok_p else 'fail'}")
        print(f"{name:>18}{row['v4_raw']:>8.1f}%{row['v5_alpha']:>9.1f}%"
              f"{row['v5_premia']:>10.1f}%   {want}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
