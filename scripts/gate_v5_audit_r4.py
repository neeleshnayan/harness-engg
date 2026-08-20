"""Gate v5 ROUND 4 — rebuilt on the four conditions of the round-3 kill.

Round 3 died three ways (docs/reviews/ADVERSARY_GATE_V5_R3_2026-08-20.md):
its premia statistic (paired test-leg Sharpe) certified a fair-priced
insurance seller 6x more often than a real premia strategy and no margin
fixed it; its history table could not detect the defect it was named after
(`meas += 1` was unconditional, so the fixed and scaled arms were the same
rule); and its drift hole was quoted at the mildest member of the class.

This script is the round-4 measurement, one fix per kill ground:

  1. SKEW-ROBUST PREMIA (Ground 1): the premia statistic is a vol-matched
     paired MPPM — the manipulation-proof performance measure of
     Goetzmann/Ingersoll/Spiegel/Welch (RFS 2007), a CRRA(rho=3) certainty-
     equivalent growth rate. Sharpe is the statistic option-like payoffs
     maximise; MPPM is the statistic built so they cannot. The strategy's
     returns are levered to the benchmark's realised vol over the same
     window before comparison, so "risk-adjusted" is enforced by
     construction rather than assumed. The rule requires BOTH a majority of
     measurable per-fold test-leg comparisons AND a full-history paired
     MPPM above the margin — the full-sample guard exists because a rare
     loss can miss any individual 84-day leg. The battery includes fair
     short-vol at three (p, L) points, at beta 0 and 1, plus the zero-mean
     AR(1) that round 3's premia rule passed 31.9%.

  2. MEASURABILITY, HONESTLY (Ground 2): `meas` now counts ONLY measurable
     folds, per app.fund.walkforward.retention() semantics (a sub-floor or
     non-positive train leg is unmeasurable, walkforward.py:277-292), and
     every fold independently drops out with the belt's MEASURED exogenous
     unmeasurable rate (11 of 53 = 20.8%: no-trade test legs, engine
     timeouts — MIN_TRAIN_RETURN_REVIEW:105). The fixed and scaled floors
     can therefore genuinely differ, and the history sweep re-measures the
     register's defect inside a v5-shaped rule state.

  3. THE CLASS MAXIMUM (Ground 3): beta nonstationarity is measured over
     shape (linear drift AND step regime-switch) x grid size K (4 and 12),
     and the hole is quoted at the class maximum, not one sampled member.

  4. THE TAXONOMY (Ground 4): claim types are DECLARATIONS, mutually
     exclusive per artifact — the gate judges only the declared claim. A
     declared-alpha process therefore has no premia verdict (n/a, excluded
     from premia FP/TP counts), even where its realised Sharpe would
     satisfy the constitution's premia definition. FP/TP are recomputed
     under this convention.

What this round does NOT claim: no statistic can see a risk that never
manifests in the sample. --blindness prints, per (p, L), the probability
that an n-day history contains zero loss events — the residual the doc
must quote instead of hiding.

Reproduction commands (each is a committed table in the round-4 doc):
  python scripts/gate_v5_audit_r4.py
  python scripts/gate_v5_audit_r4.py --margin-sweep
  python scripts/gate_v5_audit_r4.py --history-sweep
  python scripts/gate_v5_audit_r4.py --class-table
  python scripts/gate_v5_audit_r4.py --blindness

Every arm is seeded (zlib.crc32). Round 3's script and tables are not
edited — this is a new measurement with its own file, per the findings
protocol.
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
K_GRID = 4                # surviving grid points the belt averages (~4 of 6)
MEASURABLE_SHARE = 0.75   # scaled floor: measurable >= ceil(share * available)
FIXED_NEED = 4            # the register's fixed floor, for the comparison arm
MPPM_RHO = 3.0            # CRRA risk aversion for the manipulation-proof measure
BELT_DROPOUT = 0.208      # measured: 11 of 53 real belt folds unmeasurable
MAX_LEVER = 10.0          # vol-matching cap (a near-zero-vol series is not
                          # granted infinite leverage; the cap is reported)


# --- primitives --------------------------------------------------------------

def _series(sharpe: float, vol: float, n: int, rng: random.Random) -> list[float]:
    dsig = vol / math.sqrt(252.0)
    dmu = sharpe * vol / 252.0
    return [dmu + dsig * rng.gauss(0.0, 1.0) for _ in range(n)]


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


def _vol_ann(xs) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mu = sum(xs) / n
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / n * 252.0)


def _beta(strat, bench, a, b) -> float:
    xs, ys = bench[a:b], strat[a:b]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var <= 1e-18:
        return 1.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / var


def _mppm(xs, rho: float, periods: float = 252.0) -> float | None:
    """Manipulation-proof measure, %/yr: (1/((1-rho)dt)) ln E[(1+r)^(1-rho)].

    A window containing ruin (1+r <= 0 after levering) returns -100 — the
    CRRA verdict on ruin is terminal, which is the point of the measure.
    """
    n = len(xs)
    if n < 10:
        return None
    acc = 0.0
    for r in xs:
        g = 1.0 + r
        if g <= 0.0:
            return -100.0
        acc += g ** (1.0 - rho)
    return math.log(acc / n) * (periods / (1.0 - rho)) * 100.0


def _vol_p(xs, periods: float) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mu = sum(xs) / n
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / n * periods)


def _paired_mppm(strat, bench, a, b, rho: float = MPPM_RHO,
                 agg: int = 1) -> float | None:
    """MPPM(strat levered to bench's realised vol) - MPPM(bench), %/yr.

    Vol-matching enforces 'risk-adjusted' by construction: an insurance
    seller's rare losses are levered up with its premium, so the CRRA
    penalty prices exactly the tail its Sharpe hides. Because both legs are
    at the same vol, the Gaussian variance penalty CANCELS in the pair —
    raising rho raises only the skew/tail discrimination.

    ``agg`` > 1 compounds non-overlapping agg-day blocks first and measures
    at that horizon. Daily MPPM is blind to autocorrelation (a slow wander
    has tiny daily vol and levers into a fake trend); at a 21-day horizon
    the wander's variance shows up in the vol that matching must respect.
    """
    s, m = strat[a:b], bench[a:b]
    if agg > 1:
        s = _compound(s, agg)
        m = _compound(m, agg)
    periods = 252.0 / agg
    vs, vm = _vol_p(s, periods), _vol_p(m, periods)
    lever = MAX_LEVER if vs <= 1e-9 else min(MAX_LEVER, vm / vs)
    ts = _mppm([lever * x for x in s], rho, periods)
    tm = _mppm(m, rho, periods)
    if ts is None or tm is None:
        return None
    return ts - tm


def _compound(xs, block: int) -> list[float]:
    out = []
    for i in range(0, len(xs) - block + 1, block):
        acc = 1.0
        for r in xs[i:i + block]:
            acc *= (1.0 + r)
        out.append(acc - 1.0)
    return out


def _sharpe(rets, a, b) -> float:
    xs = rets[a:b]
    n = len(xs)
    if n < 20:
        return 0.0
    mu = sum(xs) / n
    var = sum((x - mu) ** 2 for x in xs) / n
    return (mu / math.sqrt(var) * math.sqrt(252.0)) if var > 1e-18 else 0.0


def _folds(n):
    out, k = [], 0
    while (k + 1) * TEST + TRAIN <= n:
        t0 = k * TEST
        out.append((t0, t0 + TRAIN, t0 + TRAIN + TEST))
        k += 1
    return out


_SHARE = [MEASURABLE_SHARE]  # mutable so --share can sweep it


def _need(n_folds: int, scale: bool) -> int:
    if not scale:
        return FIXED_NEED
    return max(FIXED_NEED, math.ceil(_SHARE[0] * n_folds))


# --- process makers ----------------------------------------------------------
# Each maker(bench, rng) -> daily return series. Grid-max selection calls the
# maker K times and keeps the best raw train-window return (the belt's
# max(total_return_pct) behaviour, validator §5).

def mk_linear(beta0, beta1, ash, avol):
    def make(bench, rng):
        n = len(bench)
        alpha = _series(ash, avol, n, rng)
        if beta0 == beta1:
            return [beta0 * b + a for b, a in zip(bench, alpha)]
        return [(beta0 + (beta1 - beta0) * i / (n - 1)) * b + a
                for i, (b, a) in enumerate(zip(bench, alpha))]
    return make


def mk_step(beta0, beta1, ash, avol):
    """Step regime-switch at a random point in the middle third — the shape
    round 3's linear-only generator was structurally unable to produce."""
    def make(bench, rng):
        n = len(bench)
        alpha = _series(ash, avol, n, rng)
        sw = rng.randrange(n // 3, 2 * n // 3)
        return [(beta0 if i < sw else beta1) * b + a
                for i, (b, a) in enumerate(zip(bench, alpha))]
    return make


def mk_ar1(rho_ar, vol):
    """Zero-mean AR(1) idio (stationary ann. vol = vol) — round 3's premia
    rule passed this null 31.9%."""
    def make(bench, rng):
        n = len(bench)
        dsig = vol / math.sqrt(252.0)
        sig_e = dsig * math.sqrt(1.0 - rho_ar * rho_ar)
        out, prev = [], 0.0
        for _ in range(n):
            prev = rho_ar * prev + sig_e * rng.gauss(0.0, 1.0)
            out.append(prev)
        return out
    return make


def mk_shortvol(p, L, beta, noise):
    """Fair-priced insurance seller (adversary Ground 1, generalised):
    collects p*L per day, loses L with probability p — expected excess
    EXACTLY zero by construction — plus small idio noise so realised vol is
    well-defined in event-free windows."""
    def make(bench, rng):
        dnoise = noise / math.sqrt(252.0)
        out = []
        for b in bench:
            hit = -L if rng.random() < p else 0.0
            out.append(beta * b + p * L + hit + dnoise * rng.gauss(0.0, 1.0))
        return out
    return make


#: (name, maker, want_alpha, want_premia) — want_premia None = n/a under the
#: Ground-4 taxonomy (declared-alpha artifacts have no premia verdict).
PROCESSES = [
    ("null_noise3",      mk_linear(1.0, 1.0, 0.0, 0.03), False, False),
    ("null_watered",     mk_linear(0.9, 0.9, 0.0, 0.03), False, False),
    ("null_lev2_n10",    mk_linear(2.0, 2.0, 0.0, 0.10), False, False),
    ("null_drift.5-2",   mk_linear(0.5, 2.0, 0.0, 0.10), False, False),
    ("null_step.5-2",    mk_step(0.5, 2.0, 0.0, 0.10),   False, False),
    ("null_noise10",     mk_linear(1.0, 1.0, 0.0, 0.10), False, False),
    ("null_ar1_.98",     mk_ar1(0.98, 0.10),             False, False),
    ("sv_300_15_b0",     mk_shortvol(1 / 300, 0.15, 0.0, 0.03), False, False),
    ("sv_300_15_b1",     mk_shortvol(1 / 300, 0.15, 1.0, 0.03), False, False),
    ("sv_60_5_b0",       mk_shortvol(1 / 60, 0.05, 0.0, 0.03),  False, False),
    ("sv_1000_30_b0",    mk_shortvol(1 / 1000, 0.30, 0.0, 0.03), False, False),
    ("premia_defensive", mk_linear(0.5, 0.5, 0.5, 0.06), False, True),
    ("alpha_S0.6",       mk_linear(1.0, 1.0, 0.6, 0.10), True,  None),
    ("alpha_S1.0",       mk_linear(1.0, 1.0, 1.0, 0.10), True,  None),
]

SV_POINTS = [("sv_300_15", 1 / 300, 0.15), ("sv_60_5", 1 / 60, 0.05),
             ("sv_1000_30", 1 / 1000, 0.30)]


# --- the rules under measurement --------------------------------------------

def rule_v4_raw(strat, bench, n, *, floor=5.0, scale=False, margin=0.0,
                drops=()) -> bool:
    folds = _folds(n)
    meas = ret = 0
    for j, (t0, t1, t2) in enumerate(folds):
        if j < len(drops) and drops[j]:
            continue
        tr = _cum_pct(strat, t0, t1)
        if tr < floor:
            continue  # unmeasurable per retention() — NOT counted
        tr_a, te_a = _ann_pct(strat, t0, t1), _ann_pct(strat, t1, t2)
        meas += 1
        if tr_a > 0 and te_a / tr_a >= RETENTION_FLOOR:
            ret += 1
    return meas >= _need(len(folds), scale) and ret * 2 > meas


def rule_v5_alpha(strat, bench, n, *, floor=2.0, scale=False, margin=0.0,
                  drops=()) -> bool:
    """Round 3's alpha rule with the Ground-2a defect FIXED: meas counts only
    measurable folds (retention() semantics), so the floors can bind."""
    folds = _folds(n)
    meas = ret = 0
    for j, (t0, t1, t2) in enumerate(folds):
        if j < len(drops) and drops[j]:
            continue  # exogenous: no-trade test leg / engine timeout
        beta = _beta(strat, bench, t0, t1)
        exc = [s - beta * b for s, b in zip(strat, bench)]
        tr_a, te_a = _ann_pct(exc, t0, t1), _ann_pct(exc, t1, t2)
        if tr_a <= 0.0 or tr_a < floor:
            continue  # sub-floor train leg: unmeasurable, walkforward.py:277-292
        meas += 1
        if te_a / tr_a >= RETENTION_FLOOR:
            ret += 1
    return meas >= _need(len(folds), scale) and ret * 2 > meas


def rule_premia_r3(strat, bench, n, *, floor=0.0, scale=False, margin=0.5,
                   drops=()) -> bool:
    """Round 3's killed statistic (paired test-leg Sharpe + margin), kept as
    the comparison column so the fix's delta is measured, not asserted."""
    folds = _folds(n)
    meas = ret = 0
    for j, (t0, t1, t2) in enumerate(folds):
        if j < len(drops) and drops[j]:
            continue
        meas += 1
        if _sharpe(strat, t1, t2) > _sharpe(bench, t1, t2) + margin:
            ret += 1
    return meas >= _need(len(folds), scale) and ret * 2 > meas


def rule_premia_r4(strat, bench, n, *, floor=0.0, scale=False, margin=2.0,
                   drops=(), rho=MPPM_RHO, two_scale=True) -> bool:
    """Round 4: vol-matched paired MPPM. THREE legs, all required:
      1. majority of measurable per-fold test-leg comparisons (daily scale);
      2. full-history daily-scale comparison above the margin — a rare loss
         cannot dodge the full sample: if it happened at all, the CRRA
         average carries it;
      3. full-history 21-day-aggregated comparison above the margin — the
         horizon where autocorrelation shows up in the vol that matching
         must respect (daily MPPM is structurally blind to it).
    """
    folds = _folds(n)
    meas = ret = 0
    for j, (t0, t1, t2) in enumerate(folds):
        if j < len(drops) and drops[j]:
            continue
        d = _paired_mppm(strat, bench, t1, t2, rho)
        if d is None:
            continue
        meas += 1
        if d > margin:
            ret += 1
    if not (meas >= _need(len(folds), scale) and ret * 2 > meas):
        return False
    full = _paired_mppm(strat, bench, 0, n, rho)
    if full is None or full <= margin:
        return False
    if two_scale:
        coarse = _paired_mppm(strat, bench, 0, n, rho, agg=21)
        if coarse is None or coarse <= margin:
            return False
    return True


RULES = {"v4_raw": rule_v4_raw, "v5_alpha": rule_v5_alpha,
         "premia_r3": rule_premia_r3, "premia_r4": rule_premia_r4}


# --- measurement machinery ---------------------------------------------------

def _select(bench, maker, rng, k_grid: int) -> list[float]:
    best, best_ret = None, None
    for _ in range(max(1, k_grid)):
        s = maker(bench, rng)
        r = _cum_pct(s, 0, TRAIN)
        if best_ret is None or r > best_ret:
            best, best_ret = s, r
    return best


def _run_cell(rule, maker, args, n, seed_tag, *, floor, scale, margin,
              k_grid, dropout, extra=None) -> float:
    rng = random.Random(args.seed + zlib.crc32(seed_tag.encode()))
    n_folds = len(_folds(n))
    hits = 0
    for _ in range(args.draws):
        bench = _series(args.market_sharpe, args.vol, n, rng)
        strat = _select(bench, maker, rng, k_grid)
        drops = [rng.random() < dropout for _ in range(n_folds)]
        hits += rule(strat, bench, n, floor=floor, scale=scale, margin=margin,
                     drops=drops, **(extra or {}))
    return 100.0 * hits / args.draws


def _floor_margin(rname, args):
    if rname == "v5_alpha":
        return args.alpha_floor, 0.0
    if rname == "premia_r3":
        return 0.0, 0.5           # round 3's shipped setting
    if rname == "premia_r4":
        return 0.0, args.premia_margin
    return 5.0, 0.0               # v4_raw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--market-sharpe", type=float, default=1.0)
    ap.add_argument("--vol", type=float, default=0.20)
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--n", type=int, default=630)
    ap.add_argument("--alpha-floor", type=float, default=2.0)
    ap.add_argument("--premia-margin", type=float, default=2.0,
                    help="%%/yr on the paired MPPM (all legs of the rule)")
    ap.add_argument("--rho", type=float, default=MPPM_RHO,
                    help="CRRA risk aversion for the MPPM")
    ap.add_argument("--no-two-scale", action="store_true",
                    help="drop the 21-day-aggregated full-sample leg")
    ap.add_argument("--rho-sweep", action="store_true")
    ap.add_argument("--share", type=float, default=MEASURABLE_SHARE,
                    help="scaled floor: measurable >= ceil(share*available). "
                         "Must sit below (1 - dropout) or judgeability halves "
                         "on the binomial knife-edge.")
    ap.add_argument("--share-sweep", action="store_true")
    ap.add_argument("--dropout", type=float, default=BELT_DROPOUT,
                    help="exogenous unmeasurable-fold rate (belt: 0.208)")
    ap.add_argument("--scale-folds", action="store_true")
    ap.add_argument("--no-select", action="store_true")
    ap.add_argument("--margin-sweep", action="store_true")
    ap.add_argument("--history-sweep", action="store_true")
    ap.add_argument("--class-table", action="store_true")
    ap.add_argument("--blindness", action="store_true")
    args = ap.parse_args()
    _SHARE[0] = args.share
    k_grid = 1 if args.no_select else K_GRID

    hdr = (f"r4 audit | mktSharpe {args.market_sharpe} | vol {args.vol:.0%} | "
           f"n {args.n} ({len(_folds(args.n))} folds) | draws {args.draws} | "
           f"grid {'off' if k_grid == 1 else f'max-of-{k_grid}'} | "
           f"folds {'scaled' if args.scale_folds else f'fixed {FIXED_NEED}'} | "
           f"dropout {args.dropout:.1%} | mppm rho {args.rho} | "
           f"two-scale {'off' if args.no_two_scale else 'on'} | "
           f"premia margin {args.premia_margin}%/yr")
    print(hdr)
    prem_extra = {"rho": args.rho, "two_scale": not args.no_two_scale}

    if args.rho_sweep:
        cols = ("sv_300_15_b0", "sv_300_15_b1", "null_ar1_.98",
                "premia_defensive")
        print(f"{'rho':>6}" + "".join(f"{c:>18}" for c in cols)
              + f"   (premia_r4, margin {args.premia_margin}, "
              + f"two-scale {'off' if args.no_two_scale else 'on'})")
        for rho in (3.0, 5.0, 8.0):
            cells = []
            for cname in cols:
                maker = next(p[1] for p in PROCESSES if p[0] == cname)
                cells.append(_run_cell(
                    rule_premia_r4, maker, args, args.n, f"rho{rho}{cname}",
                    floor=0.0, scale=args.scale_folds,
                    margin=args.premia_margin, k_grid=k_grid,
                    dropout=args.dropout,
                    extra={"rho": rho, "two_scale": not args.no_two_scale}))
            print(f"{rho:>6.1f}" + "".join(f"{c:>17.1f}%" for c in cells))
        print("the Gaussian penalty cancels in the vol-matched pair, so rho")
        print("moves only skew/tail discrimination; pick it in the open.")
        return 0

    if args.blindness:
        print(f"{'(p, L)':>14}{'P(0 events, n days)':>22}"
              f"{'P(0 events, 84d leg)':>22}")
        for name, p, L in SV_POINTS:
            pn = (1.0 - p) ** args.n
            pl = (1.0 - p) ** TEST
            print(f"{name:>14}{pn:>21.1%}{pl:>21.1%}")
        print("no statistic can see a risk absent from the sample — these are")
        print("the residual blind rates the round-4 doc quotes, not hides.")
        return 0

    if args.margin_sweep:
        cols = ("sv_300_15_b0", "sv_300_15_b1", "null_ar1_.98",
                "premia_defensive")
        print(f"{'margin':>8}" + "".join(f"{c:>18}" for c in cols)
              + "   (premia_r4 pass rates)")
        for m in (0.0, 1.0, 2.0, 3.0, 5.0):
            cells = []
            for cname in cols:
                maker = next(p[1] for p in PROCESSES if p[0] == cname)
                cells.append(_run_cell(rule_premia_r4, maker, args, args.n,
                                       f"m{m}{cname}", floor=0.0,
                                       scale=args.scale_folds, margin=m,
                                       k_grid=k_grid, dropout=args.dropout,
                                       extra=prem_extra))
            print(f"{m:>8.1f}" + "".join(f"{c:>17.1f}%" for c in cells))
        print("pick the margin in the open: every null column at or below the")
        print("FP budget with premia_defensive keeping a usable TP.")
        return 0

    if args.share_sweep:
        nulls = [p for p in PROCESSES if p[3] is False and not p[2]]
        spec_a = next(p[1] for p in PROCESSES if p[0] == "alpha_S1.0")
        prem = next(p[1] for p in PROCESSES if p[0] == "premia_defensive")
        print(f"{'share':>7}{'need':>6}{'null FPR (alpha)':>18}"
              f"{'alphaS1 TP':>12}{'premia TP':>11}   "
              f"(n {args.n}, scaled floor, dropout {args.dropout:.1%})")
        for share in (0.5, 0.6, 0.75):
            _SHARE[0] = share
            need = _need(len(_folds(args.n)), True)
            fpr = sum(_run_cell(rule_v5_alpha, p[1], args, args.n,
                                f"s{share}{p[0]}", floor=args.alpha_floor,
                                scale=True, margin=0.0, k_grid=k_grid,
                                dropout=args.dropout)
                      for p in nulls) / len(nulls)
            tp_a = _run_cell(rule_v5_alpha, spec_a, args, args.n,
                             f"s{share}a", floor=args.alpha_floor, scale=True,
                             margin=0.0, k_grid=k_grid, dropout=args.dropout)
            tp_p = _run_cell(rule_premia_r4, prem, args, args.n,
                             f"s{share}p", floor=0.0, scale=True,
                             margin=args.premia_margin, k_grid=k_grid,
                             dropout=args.dropout, extra=prem_extra)
            print(f"{share:>7.2f}{need:>6}{fpr:>17.1f}%{tp_a:>11.1f}%"
                  f"{tp_p:>10.1f}%")
        _SHARE[0] = args.share
        print("the share must sit BELOW (1 - dropout): at 0.75 vs a 20.8%")
        print("dropout the floor rides the binomial knife-edge and halves TP.")
        return 0

    if args.history_sweep:
        nulls = [p for p in PROCESSES if p[3] is False and not p[2]]
        spec_a = next(p[1] for p in PROCESSES if p[0] == "alpha_S1.0")
        print(f"{'n(days)':>9}{'folds':>7}{'fixed null FPR':>16}"
              f"{'scaled null FPR':>17}{'fixed alphaS1 TP':>18}"
              f"{'scaled alphaS1 TP':>19}   (v5_alpha, dropout on)")
        for n in (630, 1260, 2520):
            def fpr(scale):
                tot = 0.0
                for p in nulls:
                    tot += _run_cell(rule_v5_alpha, p[1], args, n,
                                     f"h{n}{scale}{p[0]}",
                                     floor=args.alpha_floor, scale=scale,
                                     margin=0.0, k_grid=k_grid,
                                     dropout=args.dropout)
                return tot / len(nulls)
            def tp(scale):
                return _run_cell(rule_v5_alpha, spec_a, args, n,
                                 f"h{n}{scale}a", floor=args.alpha_floor,
                                 scale=scale, margin=0.0, k_grid=k_grid,
                                 dropout=args.dropout)
            print(f"{n:>9}{len(_folds(n)):>7}{fpr(False):>15.1f}%"
                  f"{fpr(True):>16.1f}%{tp(False):>17.1f}%{tp(True):>18.1f}%")
        print("the arms can now differ (meas counts measurable folds only);")
        print("the fixed column rising with n is the register's defect, live.")
        return 0

    if args.class_table:
        print(f"{'shape':>12}{'K':>5}{'v5_alpha pass':>15}   "
              f"(beta 0.5->2.0 nonstationarity, class maximum in bold prose)")
        worst = (None, 0.0)
        for shape, mk in (("linear", mk_linear(0.5, 2.0, 0.0, 0.10)),
                          ("step", mk_step(0.5, 2.0, 0.0, 0.10))):
            for K in (4, 12):
                r = _run_cell(rule_v5_alpha, mk, args, args.n,
                              f"c{shape}{K}", floor=args.alpha_floor,
                              scale=args.scale_folds, margin=0.0,
                              k_grid=K, dropout=args.dropout)
                if r > worst[1]:
                    worst = (f"{shape} K={K}", r)
                print(f"{shape:>12}{K:>5}{r:>14.1f}%")
        print(f"CLASS MAXIMUM: {worst[0]} at {worst[1]:.1f}% — quote THIS "
              f"number as the hole, never the mildest member.")
        return 0

    # --- main table ---------------------------------------------------------
    print(f"{'process':>18}{'v4_raw':>9}{'v5_alpha':>10}{'premia_r3':>11}"
          f"{'premia_r4':>11}   correct verdict (taxonomy: declared claim only)")
    agg = {r: {"fp": [], "tp": []} for r in ("premia_r3", "premia_r4")}
    for name, maker, ok_a, ok_p in PROCESSES:
        row = {}
        for rname, rule in RULES.items():
            floor, margin = _floor_margin(rname, args)
            row[rname] = _run_cell(rule, maker, args, args.n, name + rname,
                                   floor=floor, scale=args.scale_folds,
                                   margin=margin, k_grid=k_grid,
                                   dropout=args.dropout,
                                   extra=(prem_extra if rname == "premia_r4"
                                          else None))
        for r in ("premia_r3", "premia_r4"):
            if ok_p is True:
                agg[r]["tp"].append(row[r])
            elif ok_p is False:
                agg[r]["fp"].append(row[r])
        want_p = "n/a" if ok_p is None else ("PASS" if ok_p else "fail")
        want = f"alpha={'PASS' if ok_a else 'fail'} premia={want_p}"
        print(f"{name:>18}{row['v4_raw']:>8.1f}%{row['v5_alpha']:>9.1f}%"
              f"{row['premia_r3']:>10.1f}%{row['premia_r4']:>10.1f}%   {want}")
    for r in ("premia_r3", "premia_r4"):
        fp = sum(agg[r]["fp"]) / max(1, len(agg[r]["fp"]))
        tp = sum(agg[r]["tp"]) / max(1, len(agg[r]["tp"]))
        be = 100.0 * fp / (fp + tp) if (fp + tp) > 0 else float("nan")
        print(f"{r}: mean null FPR {fp:.1f}% | premia TP {tp:.1f}% | "
              f"break-even prior {be:.1f}% (a PASS is more-likely-true-than-"
              f"false only if the candidate base rate exceeds this)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
