"""Gate v5 ROUND 5 - the measurement. Financing charged, shipped geometry.

Round 4 was killed on four grounds
(docs/reviews/ADVERSARY_GATE_V5_R4_2026-08-21.md). Round 5's design
(docs/GATE_V5_ROUND5_DESIGN_2026-08-21.md) names one change per ground.
This script MEASURES that design. It does not adopt it and it moves no
threshold. scripts/gate_v5_audit_r4.py is NOT edited - findings and their
instruments are never edited here.

WHAT CHANGED FROM ROUND 4, mechanically:

  G1 FINANCING. Every leg runs on EXCESS returns in the
     Goetzmann/Ingersoll/Spiegel/Welch form: the measure is computed over
     the ratio return e = (1+r)/(1+rf) - 1, and a k-levered position earns
     rf + k*(r - rf), i.e. its ratio return is exactly k*e. Round 4
     levered TOTAL returns with no risk-free divisor, so levering handed a
     candidate a deterministic (k-1)*rf per year against a 2%/yr margin.
     Constitution, amended 2026-08-21: "'risk-adjusted' is measured over
     EXCESS returns - above the risk-free rate, with financing charged on
     any leverage."

  G2 THE MASKED FAMILY IS A FIRST-CLASS NULL. AR(1) rho=.98 wander diluted
     to a share w of idiosyncratic VARIANCE and carried on beta b, at
     w in {1.0, .25, .10, .05} x b in {0, 1}. The headline is the CLASS
     MAXIMUM, never the battery mean.

  G3 GEOMETRY. There is exactly one fold generator and it is
     app.fund.walkforward.window_for_strategy, imported and CALLED. Folds
     are placed on the fund's OWN session calendar (SPY bars from the
     spine) by date, never packed by index.

  G4 THE FULL-SAMPLE LEGS ARE COMPUTED OOS-ONLY. The shipped data path
     (runanalytics.daily_return_legs, commit 76784c2) captures test legs
     only; train legs are never captured. The r4-style whole-window leg is
     also available behind full_window=True and is labelled UNMEASURABLE
     ON THE BELT wherever it is used.

DISCLOSURES THAT TRAVEL WITH EVERY TABLE: --market-sharpe is the
BENCHMARK'S EXCESS Sharpe and is a conditioning assumption, not a
measurement; the risk-free series is real BIL unless stated; the grid-max
selection statistic is the RAW train return (the belt's own behaviour),
while the judging statistic is excess - a disclosed asymmetry, not one
introduced here.

Reproduction:
  python scripts/gate_v5_audit_r5.py --geometry
  python scripts/gate_v5_audit_r5.py --acceptance
  python scripts/gate_v5_audit_r5.py --rf-sensitivity
  python scripts/gate_v5_audit_r5.py --battery
  python scripts/gate_v5_audit_r5.py --measurability
  python scripts/gate_v5_audit_r5.py --all
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import random
import sys
import tempfile
import urllib.request
import zlib

sys.path.insert(0, ".")

BASE = os.getenv("FUND_API", "http://127.0.0.1:8090/api/v1")
# The bar cache lives OUTSIDE the repo on purpose: this dispatch's write
# authorisation covers scripts/gate_v5_audit_r5.py and nothing else.
CACHE = os.getenv("R5_CACHE", os.path.join(tempfile.gettempdir(),
                                           "krypton_r5_bars_cache.json"))

TRAIN_DAYS = 252
HOLD_DAYS = 21            # the belt's 21-day hold: 84-day test legs
MIN_FOLDS = 4             # gate v4.1 min_walkforward_folds (gate.py:183)
HISTORY_FLOOR = "2024-02-26"   # factory.py:38 WALKFORWARD_HISTORY_FLOOR
MPPM_RHO = 5.0            # design 4.3: kept at 5, explicitly near-decorative
PREMIA_MARGIN = 2.0       # %/yr on the paired MPPM, all legs
VR_MAX = 2.0
MAX_LEVER = 10.0
BELT_DROPOUT = 0.208      # measured: 11 of 53 real belt folds, exogenous
K_GRID = 4                # surviving grid points the belt averages


# --- data --------------------------------------------------------------------

def _bars(symbol: str, start: str, end: str) -> tuple[list[str], list[float]]:
    key = f"{symbol}|{start}|{end}"
    try:
        with open(CACHE) as fh:
            cache = json.load(fh)
    except Exception:  # noqa: BLE001
        cache = {}
    if key in cache:
        return cache[key]["dates"], cache[key]["closes"]
    url = (f"{BASE}/fund/marketdata/bars?symbol={symbol}"
           f"&start_date={start}&end_date={end}")
    with urllib.request.urlopen(url, timeout=60) as fh:
        d = json.load(fh)
    cache[key] = {"dates": d["dates"], "closes": d["closes"]}
    try:
        with open(CACHE, "w") as fh:
            json.dump(cache, fh)
    except Exception:  # noqa: BLE001
        pass
    return d["dates"], d["closes"]


def _rets(dates: list[str], closes: list[float]) -> tuple[list[str], list[float]]:
    """Close-to-close returns stamped with the LATER date. Bars are
    split/dividend adjusted, so this is a total return."""
    rd, rr = [], []
    for i in range(1, len(closes)):
        p0, p1 = closes[i - 1], closes[i]
        if p0 and p0 > 0 and p1 and p1 > 0:
            rd.append(dates[i])
            rr.append(p1 / p0 - 1.0)
    return rd, rr


class Feed:
    """The fund's own sessions, with a real risk-free series beside them."""

    def __init__(self, bench_symbol: str = "SPY", rf_symbol: str = "BIL",
                 start: str = "2015-08-01", end: str = "2026-08-21"):
        bd, bc = _bars(bench_symbol, start, end)
        fd, fc = _bars(rf_symbol, start, end)
        brd, brr = _rets(bd, bc)
        frd, frr = _rets(fd, fc)
        fmap = dict(zip(frd, frr))
        self.dates = [d for d in brd if d in fmap]
        self.bench = [r for d, r in zip(brd, brr) if d in fmap]
        self.rf = [fmap[d] for d in self.dates]
        self.bench_symbol, self.rf_symbol = bench_symbol, rf_symbol
        self.n_dropped = len(brd) - len(self.dates)

    def idx(self, start: str, end: str) -> tuple[int, int]:
        return (bisect.bisect_left(self.dates, start),
                bisect.bisect_right(self.dates, end))


# --- the shipped fold generator, CALLED ---------------------------------------

def shipped_folds(feed: Feed, *, end: str, hold: int, min_folds: int,
                  floor: str | None) -> dict:
    from app.fund.walkforward import window_for_strategy
    plan = window_for_strategy(end, hold, min_folds, train_days=TRAIN_DAYS,
                               floor=floor)
    rows = []
    for f in plan["folds"]:
        a, b = feed.idx(f["train_start"], f["train_end"])
        c, d = feed.idx(f["test_start"], f["test_end"])
        rows.append({"train": (a, b), "test": (c, d), **f})
    return {"plan": plan, "rows": rows}


# --- excess-return primitives (GISW form) -------------------------------------

def _excess(r: list[float], rf: list[float], a: int, b: int) -> list[float]:
    """Ratio return e = (1+r)/(1+rf) - 1. Levering by k multiplies e by k,
    which IS 'rf + k(r-rf)' expressed as a ratio return - financing charged."""
    return [(1.0 + r[i]) / (1.0 + rf[i]) - 1.0 for i in range(a, b)]


def _compound(xs: list[float], block: int) -> list[float]:
    out = []
    for i in range(0, len(xs) - block + 1, block):
        acc = 1.0
        for x in xs[i:i + block]:
            acc *= (1.0 + x)
        out.append(acc - 1.0)
    return out


def _vol_p(xs: list[float], periods: float) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mu = sum(xs) / n
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / n * periods)


def _mppm(es: list[float], rho: float, periods: float) -> float | None:
    """(1/((1-rho)dt)) ln E[(1+e)^(1-rho)] in %/yr, e the EXCESS ratio return.

    GISW RFS 2007 with the (1+rf) divisor already applied by _excess. Ruin
    (1+e <= 0) is terminal and returns -100."""
    n = len(es)
    if n < 10:
        return None
    acc = 0.0
    for e in es:
        g = 1.0 + e
        if g <= 0.0:
            return -100.0
        acc += g ** (1.0 - rho)
    return math.log(acc / n) * (periods / (1.0 - rho)) * 100.0


def paired_mppm(es: list[float], eb: list[float], rho: float = MPPM_RHO,
                agg: int = 1, lever_cap: float = MAX_LEVER
                ) -> tuple[float | None, float]:
    """MPPM(strategy levered to the benchmark's excess vol) - MPPM(benchmark).

    Both legs are excess; the lever multiplies the excess stream only, so the
    cash a levered position borrows is charged at exactly rf."""
    s, m = es, eb
    if agg > 1:
        s, m = _compound(s, agg), _compound(m, agg)
    periods = 252.0 / agg
    vs, vm = _vol_p(s, periods), _vol_p(m, periods)
    lever = lever_cap if vs <= 1e-12 else min(lever_cap, vm / vs)
    ts = _mppm([lever * x for x in s], rho, periods)
    tm = _mppm(m, rho, periods)
    if ts is None or tm is None:
        return None, lever
    return ts - tm, lever


def paired_mppm_r4(rs: list[float], rb: list[float], rho: float = MPPM_RHO,
                   agg: int = 1) -> float | None:
    """ROUND 4's statistic, kept ONLY as the comparison column: TOTAL returns,
    no risk-free divisor, lever applied to the whole return (r4 :175-176)."""
    s, m = list(rs), list(rb)
    if agg > 1:
        s, m = _compound(s, agg), _compound(m, agg)
    periods = 252.0 / agg
    vs, vm = _vol_p(s, periods), _vol_p(m, periods)
    lever = MAX_LEVER if vs <= 1e-12 else min(MAX_LEVER, vm / vs)

    def mp(xs):
        acc = 0.0
        for x in xs:
            g = 1.0 + x
            if g <= 0.0:
                return -100.0
            acc += g ** (1.0 - rho)
        return math.log(acc / len(xs)) * (periods / (1.0 - rho)) * 100.0

    if len(s) < 10 or len(m) < 10:
        return None
    return mp([lever * x for x in s]) - mp(m)


def vr21(es: list[float]) -> float:
    vd = _vol_p(es, 252.0)
    if vd <= 1e-15:
        return float("inf")
    vc = _vol_p(_compound(es, 21), 252.0 / 21)
    return (vc / vd) ** 2


def excess_sharpe(es: list[float]) -> float:
    n = len(es)
    if n < 20:
        return 0.0
    mu = sum(es) / n
    var = sum((x - mu) ** 2 for x in es) / n
    return (mu / math.sqrt(var) * math.sqrt(252.0)) if var > 1e-20 else 0.0


def ann_pct(rs: list[float]) -> float:
    acc = 1.0
    for r in rs:
        acc *= (1.0 + r)
    if acc <= 0 or not rs:
        return -100.0
    return (acc ** (252.0 / len(rs)) - 1.0) * 100.0


# --- the rule under measurement ----------------------------------------------

def rule_premia_r5(rs: list[float], rb: list[float], rf: list[float],
                   folds: list[dict], *, rho: float = MPPM_RHO,
                   margin: float = PREMIA_MARGIN, need: int = MIN_FOLDS,
                   drops: tuple = (), two_scale: bool = True,
                   vr_max: float = VR_MAX, full_window: bool = False,
                   stat: str = "r5") -> dict:
    """FOUR legs, all required, all on excess returns with financing charged.

      0. structure guard: 21-day variance ratio of the strategy's EXCESS
         stream under vr_max, else CANNOT TELL (counted as a non-pass);
      1. strict majority of measurable per-fold test-leg paired MPPMs
         above the margin, with at least `need` measurable;
      2. full-sample daily paired MPPM above the margin;
      3. full-sample 21-day-aggregated paired MPPM above the margin.

    full_window=False (the default, and the only belt-computable choice)
    builds legs 0/2/3 from the CONCATENATED SURVIVING TEST LEGS - the only
    daily series runanalytics.daily_return_legs() can ever serve. True
    reproduces round 4's whole-window (train+test) leg, which no belt run
    can supply.

    Returns a dict so the caller can split rejections BY MODE: 'rejects 97%
    of nulls' is much less useful than knowing whether they failed the test
    or never ran it."""
    keep = [f for j, f in enumerate(folds)
            if not (j < len(drops) and drops[j])]
    meas = ret = 0
    for f in keep:
        c, d = f["test"]
        if stat == "r4":
            val = paired_mppm_r4(rs[c:d], rb[c:d], rho)
        else:
            val, _ = paired_mppm(_excess(rs, rf, c, d),
                                 _excess(rb, rf, c, d), rho)
        if val is None:
            continue
        meas += 1
        if val > margin:
            ret += 1
    if meas < need:
        return {"pass": False, "mode": "never_ran", "meas": meas, "ret": ret}

    if full_window:
        idxs = [(min(f["train"][0] for f in keep),
                 max(f["test"][1] for f in keep))]
    else:
        idxs = [f["test"] for f in keep]
    fs, fb = [], []
    for a, b in idxs:
        if stat == "r4":
            fs.extend(rs[a:b])
            fb.extend(rb[a:b])
        else:
            fs.extend(_excess(rs, rf, a, b))
            fb.extend(_excess(rb, rf, a, b))

    if vr21(fs) > vr_max:
        return {"pass": False, "mode": "cannot_tell_vr", "meas": meas,
                "ret": ret}
    if ret * 2 <= meas:
        return {"pass": False, "mode": "no_majority", "meas": meas, "ret": ret}
    if stat == "r4":
        full = paired_mppm_r4(fs, fb, rho)
    else:
        full, _ = paired_mppm(fs, fb, rho)
    if full is None or full <= margin:
        return {"pass": False, "mode": "full_daily", "meas": meas, "ret": ret,
                "full": full}
    if two_scale:
        coarse = (paired_mppm_r4(fs, fb, rho, agg=21) if stat == "r4"
                  else paired_mppm(fs, fb, rho, agg=21)[0])
        if coarse is None or coarse <= margin:
            return {"pass": False, "mode": "full_21d", "meas": meas,
                    "ret": ret, "full": full}
    return {"pass": True, "mode": "pass", "meas": meas, "ret": ret,
            "full": full}


# --- process makers -----------------------------------------------------------
# Each maker(eb, rf, a, rng) -> the strategy's TOTAL daily returns, so the RULE
# must do its own excess conversion. Building processes in excess space and
# handing the rule excess would make rf-invariance true by construction and
# the acceptance test vacuous.

def _from_excess(es, rf, a):
    return [(1.0 + e) * (1.0 + rf[a + i]) - 1.0 for i, e in enumerate(es)]


def _noise(vol, n, rng):
    d = vol / math.sqrt(252.0)
    return [d * rng.gauss(0.0, 1.0) for _ in range(n)]


def mk_linear(b0, b1, ash, avol):
    def make(eb, rf, a, rng):
        n = len(eb)
        al = [ash * avol / 252.0 + x for x in _noise(avol, n, rng)]
        if b0 == b1:
            es = [b0 * b + x for b, x in zip(eb, al)]
        else:
            es = [(b0 + (b1 - b0) * i / (n - 1)) * b + x
                  for i, (b, x) in enumerate(zip(eb, al))]
        return _from_excess(es, rf, a)
    return make


def mk_step(b0, b1, ash, avol):
    def make(eb, rf, a, rng):
        n = len(eb)
        al = [ash * avol / 252.0 + x for x in _noise(avol, n, rng)]
        sw = rng.randrange(n // 3, 2 * n // 3)
        es = [(b0 if i < sw else b1) * b + x
              for i, (b, x) in enumerate(zip(eb, al))]
        return _from_excess(es, rf, a)
    return make


def mk_masked(w, beta, rho_ar=0.98, idio_vol=0.10):
    """The adversary's ground-2 process: a share `w` of the IDIOSYNCRATIC
    VARIANCE is AR(1) rho=.98 wander, the rest iid, carried on beta. Zero
    expected excess return by construction at every w and beta. w=1.0, b=0
    is exactly round 4's null_ar1_.98."""
    def make(eb, rf, a, rng):
        n = len(eb)
        d = idio_vol / math.sqrt(252.0)
        sw = d * math.sqrt(w)
        si = d * math.sqrt(max(0.0, 1.0 - w))
        se = sw * math.sqrt(1.0 - rho_ar * rho_ar)
        prev, es = 0.0, []
        for i in range(n):
            prev = rho_ar * prev + se * rng.gauss(0.0, 1.0)
            es.append(beta * eb[i] + prev + si * rng.gauss(0.0, 1.0))
        return _from_excess(es, rf, a)
    return make


def mk_shortvol(p, L, beta, noise):
    """Fair-priced insurance seller: collects p*L daily, loses L with
    probability p - expected EXCESS return exactly zero by construction."""
    def make(eb, rf, a, rng):
        d = noise / math.sqrt(252.0)
        es = []
        for b in eb:
            hit = -L if rng.random() < p else 0.0
            es.append(beta * b + p * L + hit + d * rng.gauss(0.0, 1.0))
        return _from_excess(es, rf, a)
    return make


def mk_cashmix(w):
    """w * benchmark + (1-w) * risk-free, in TOTAL returns. Its EXCESS
    stream is exactly w x the benchmark's, so its excess Sharpe is IDENTICAL
    to the benchmark's at every w and every rf - zero skill, by
    construction. THE ACCEPTANCE TEST."""
    def make(eb, rf, a, rng):
        return [w * ((1.0 + e) * (1.0 + rf[a + i]) - 1.0)
                + (1.0 - w) * rf[a + i] for i, e in enumerate(eb)]
    return make


def battery() -> list[tuple]:
    """(name, maker, is_null). is_null False = a genuine premia claim (TP)."""
    ps = [
        ("null_noise3", mk_linear(1.0, 1.0, 0.0, 0.03), True),
        ("null_watered", mk_linear(0.9, 0.9, 0.0, 0.03), True),
        ("null_lev2_n10", mk_linear(2.0, 2.0, 0.0, 0.10), True),
        ("null_drift.5-2", mk_linear(0.5, 2.0, 0.0, 0.10), True),
        ("null_step.5-2", mk_step(0.5, 2.0, 0.0, 0.10), True),
        ("null_noise10", mk_linear(1.0, 1.0, 0.0, 0.10), True),
    ]
    for w in (1.0, 0.25, 0.10, 0.05):
        for b in (0, 1):
            ps.append((f"masked_w{w:.2f}_b{b}", mk_masked(w, float(b)), True))
    ps += [
        ("sv_300_15_b0", mk_shortvol(1 / 300, 0.15, 0.0, 0.03), True),
        ("sv_300_15_b1", mk_shortvol(1 / 300, 0.15, 1.0, 0.03), True),
        ("sv_60_5_b0", mk_shortvol(1 / 60, 0.05, 0.0, 0.03), True),
        ("sv_1000_30_b0", mk_shortvol(1 / 1000, 0.30, 0.0, 0.03), True),
        ("cashmix_w0.40", mk_cashmix(0.40), True),
        ("premia_defensive", mk_linear(0.5, 0.5, 0.5, 0.06), False),
        ("oracle_b0_sr1.5", mk_linear(0.0, 0.0, 1.5, 0.10), False),
        ("oracle_b0_sr2.5", mk_linear(0.0, 0.0, 2.5, 0.10), False),
    ]
    return ps


# --- measurement machinery ----------------------------------------------------

def _bench_excess(feed: Feed, lo: int, hi: int, args, rng) -> list[float]:
    if args.real_bench:
        return _excess(feed.bench, feed.rf, lo, hi)
    n = hi - lo
    dsig = args.vol / math.sqrt(252.0)
    dmu = args.market_sharpe * args.vol / 252.0
    return [dmu + dsig * rng.gauss(0.0, 1.0) for _ in range(n)]


def run_cell(maker, feed, folds, lo, hi, args, tag, *, need, dropout,
             margin=None, rho=None, full_window=False, k_grid=None,
             rf_assumed=None, stat="r5") -> dict:
    """One process x one geometry. Pass rate AND the rejection-mode split."""
    rng = random.Random(args.seed + zlib.crc32(tag.encode()))
    margin = args.margin if margin is None else margin
    rho = args.rho if rho is None else rho
    k_grid = (1 if args.no_select else K_GRID) if k_grid is None else k_grid
    rf_rule = feed.rf if rf_assumed is None else rf_assumed
    modes: dict[str, int] = {}
    hits = 0
    srs, fulls = [], []
    tr0, tr1 = folds[0]["train"]
    for _ in range(args.draws):
        eb = _bench_excess(feed, lo, hi, args, rng)
        rb = _from_excess(eb, feed.rf, lo)
        best, best_r = None, None
        for _g in range(max(1, k_grid)):
            cand = maker(eb, feed.rf, lo, rng)
            acc = 1.0
            for x in cand[tr0 - lo:tr1 - lo]:
                acc *= (1.0 + x)          # the belt selects on RAW train return
            if best_r is None or acc > best_r:
                best, best_r = cand, acc
        rs_full = [0.0] * lo + best
        rb_full = [0.0] * lo + rb
        drops = tuple(rng.random() < dropout for _ in folds)
        out = rule_premia_r5(rs_full, rb_full, rf_rule, folds, rho=rho,
                             margin=margin, need=need, drops=drops,
                             two_scale=not args.no_two_scale,
                             full_window=full_window, stat=stat)
        modes[out["mode"]] = modes.get(out["mode"], 0) + 1
        hits += bool(out["pass"])
        if out.get("full") is not None:
            fulls.append(out["full"])
        oos = []
        for f in folds:
            c, d = f["test"]
            oos.extend(_excess(rs_full, feed.rf, c, d))
        srs.append(excess_sharpe(oos))
    n = args.draws
    return {
        "pass_pct": 100.0 * hits / n,
        "modes": {k: 100.0 * v / n for k, v in modes.items()},
        "true_excess_sharpe": sum(srs) / len(srs) if srs else float("nan"),
        "median_full_mppm": (sorted(fulls)[len(fulls) // 2]
                             if fulls else float("nan")),
    }


def _hdr(args, feed, folds, label) -> str:
    if args.real_bench:
        bench = "REAL " + feed.bench_symbol + " excess (no --market-sharpe)"
    else:
        bench = (f"synthetic, ASSUMED excess Sharpe {args.market_sharpe} / "
                 f"vol {args.vol:.0%}")
    grid = "off" if args.no_select else f"max-of-{K_GRID} on RAW train return"
    label = f"{label}, statistic {getattr(args, 'stat', 'r5')}"
    return (f"[{label}] rho {args.rho} | margin {args.margin}%/yr | draws "
            f"{args.draws} | seed {args.seed} | bench {bench} | rf = real "
            f"{feed.rf_symbol} | folds {len(folds)} (SHIPPED "
            f"window_for_strategy, hold {HOLD_DAYS}, min_folds {MIN_FOLDS}, "
            f"floor {args.floor}) | dropout {args.dropout:.1%} | grid {grid}")


# --- sections -----------------------------------------------------------------

def sec_geometry(feed: Feed, args) -> None:
    print("\n=== 1. THE SHIPPED GEOMETRY (app.fund.walkforward."
          "window_for_strategy, CALLED) ===")
    print(f"session calendar: {feed.bench_symbol} bars from the spine, "
          f"{len(feed.dates)} returns {feed.dates[0]}..{feed.dates[-1]}; "
          f"{feed.n_dropped} session(s) dropped for having no "
          f"{feed.rf_symbol} bar")
    for floor in (HISTORY_FLOOR, None):
        g = shipped_folds(feed, end=args.end, hold=HOLD_DAYS,
                          min_folds=MIN_FOLDS, floor=floor)
        rows = g["rows"]
        oos = sum(b - a for a, b in (f["test"] for f in rows))
        label = floor or "none (full 11y feed)"
        print(f"\nfloor {label} -> {len(rows)} folds, test_days "
              f"{g['plan']['test_days']}, enough={g['plan']['enough']}, "
              f"OOS sessions {oos}")
        print(f"{'#':>2}{'train':>26}{'trn':>5}{'test':>26}{'tst':>5}")
        for i, f in enumerate(rows, 1):
            a, b = f["train"]
            c, d = f["test"]
            print(f"{i:>2}  {f['train_start']}..{f['train_end']}{b - a:>5}"
                  f"  {f['test_start']}..{f['test_end']}{d - c:>5}")
        K, q = len(rows), 1.0 - args.dropout
        p_ok = sum(math.comb(K, k) * q ** k * (1 - q) ** (K - k)
                   for k in range(MIN_FOLDS, K + 1))
        print(f"gate v4.1 needs folds_measurable >= {MIN_FOLDS} (gate.py:183) "
              f"and the geometry supplies {K}: slack {K - MIN_FOLDS}. At the "
              f"belt's measured {args.dropout:.1%} exogenous dropout, "
              f"P(>= {MIN_FOLDS} of {K} measurable) = {p_ok:.1%} - a hard "
              f"CEILING on any pass rate, true and false alike.")


def sec_acceptance(feed: Feed, args) -> None:
    print("\n=== 2. THE HEADLINE ACCEPTANCE TEST - FINANCING (G1) ===")
    print("prediction, stated in advance: the cash mix w*benchmark + (1-w)*rf "
          "has an excess stream exactly w x the benchmark's, so after "
          "vol-matching its paired MPPM is IDENTICALLY ZERO at every w and "
          "every rf. Any surviving rf dependence means financing is still "
          "not charged and round 5 is dead.")
    g = shipped_folds(feed, end=args.end, hold=HOLD_DAYS, min_folds=MIN_FOLDS,
                      floor=args.floor)
    rows = g["rows"]
    lo = min(f["train"][0] for f in rows)
    hi = max(f["test"][1] for f in rows)
    oos = [f["test"] for f in rows]
    eb, rbt, rft = [], [], []
    for a, b in oos:
        eb.extend(_excess(feed.bench, feed.rf, a, b))
        rbt.extend(feed.bench[a:b])
        rft.extend(feed.rf[a:b])
    print(f"\n2a. ON THE FUND'S OWN FEED - real {feed.bench_symbol} vs real "
          f"{feed.rf_symbol}, no simulation, over the CONCATENATED OOS legs "
          f"({len(rbt)} sessions, {rows[0]['test_start']}.."
          f"{rows[-1]['test_end']}). rho {args.rho}. NO --market-sharpe "
          f"assumption enters this table.")
    print(f"{'w':>6}{'r5 excess d':>14}{'r5 excess 21d':>15}"
          f"{'r4 total d':>13}{'r4 total 21d':>14}{'lever':>8}")
    for w in (1.00, 0.80, 0.60, 0.40, 0.20, 0.10, 0.05):
        rs = [w * rbt[i] + (1 - w) * rft[i] for i in range(len(rbt))]
        es = [(1 + rs[i]) / (1 + rft[i]) - 1 for i in range(len(rs))]
        d5, lev = paired_mppm(es, eb, args.rho)
        c5, _ = paired_mppm(es, eb, args.rho, agg=21)
        d4 = paired_mppm_r4(rs, rbt, args.rho)
        c4 = paired_mppm_r4(rs, rbt, args.rho, agg=21)
        print(f"{w:>6.2f}{d5:>14.4f}{c5:>15.4f}{d4:>13.4f}{c4:>14.4f}"
              f"{lev:>8.2f}")
    print(f"units %/yr. Margin {args.margin}%/yr: an r5 entry above it is a "
          f"zero-skill pass. MAX_LEVER {MAX_LEVER} binds below w = "
          f"{1 / MAX_LEVER:.2f} and under excess returns it UNDER-levers - "
          f"conservative, the opposite direction from round 4.")
    print(f"measured over the same OOS window: {feed.bench_symbol} "
          f"{ann_pct(rbt):.2f}%/yr, {feed.rf_symbol} {ann_pct(rft):.2f}%/yr, "
          f"benchmark excess Sharpe {excess_sharpe(eb):.2f}")

    print("")
    print("2a-bis. IS THE 21-DAY RESIDUAL FINANCING, OR REBALANCING "
          "CONVEXITY? Same real SPY path, with the cash leg AND the rule "
          "moved onto one CONSTANT rf. If the residual is financing it moves "
          "with rf; if it is convexity it does not.")
    print(f"{'w':>6}" + "".join(f"{'rf=' + format(x, '.0f') + '% d/21d':>20}"
                                for x in (0.0, 4.0, 8.0)))
    for w in (0.80, 0.60, 0.40, 0.20):
        cells = []
        for rfa in (0.0, 4.0, 8.0):
            dd = (1.0 + rfa / 100.0) ** (1 / 252.0) - 1.0
            rfs = [dd] * len(rbt)
            rs = [w * rbt[i] + (1 - w) * dd for i in range(len(rbt))]
            es = [(1 + rs[i]) / (1 + dd) - 1 for i in range(len(rs))]
            ebx = [(1 + rbt[i]) / (1 + dd) - 1 for i in range(len(rbt))]
            v1, _ = paired_mppm(es, ebx, args.rho)
            v2, _ = paired_mppm(es, ebx, args.rho, agg=21)
            cells.append(f"{v1:8.4f} /{v2:8.4f}")
        print(f"{w:>6.2f}" + "".join(f"{c:>20}" for c in cells))

    print("NOTE: in 2b the header rf = real BIL is OVERRIDDEN "
          "per row by the constant rf named in the first column.")
    print("\n2b. MONTE CARLO, pass rates across w x an ASSUMED CONSTANT rf "
          "that replaces the real BIL series on BOTH the cash leg and the "
          "rule (a correctly-specified rf).")
    print(_hdr(args, feed, rows, "acceptance"))
    ws = (1.00, 0.60, 0.40, 0.20)
    print(f"{'rf %/yr':>9}" + "".join(f"{'w=' + format(w, '.2f'):>10}"
                                      for w in ws))
    real_rf = feed.rf
    for rfa in (0.0, 2.0, 4.0, 6.0):
        feed.rf = [(1.0 + rfa / 100.0) ** (1 / 252.0) - 1.0] * len(real_rf)
        cells = [run_cell(mk_cashmix(w), feed, rows, lo, hi, args,
                          f"acc{rfa}{w}", need=MIN_FOLDS,
                          dropout=args.dropout)["pass_pct"] for w in ws]
        print(f"{rfa:>9.1f}" + "".join(f"{c:>9.1f}%" for c in cells))
    print("  --- the SAME cells, same seeds, through ROUND 4's statistic "
          "(total returns, no risk-free divisor) ---")
    for rfa in (0.0, 2.0, 4.0, 6.0):
        feed.rf = [(1.0 + rfa / 100.0) ** (1 / 252.0) - 1.0] * len(real_rf)
        cells = [run_cell(mk_cashmix(w), feed, rows, lo, hi, args,
                          f"acc{rfa}{w}", need=MIN_FOLDS,
                          dropout=args.dropout, stat="r4")["pass_pct"]
                 for w in ws]
        print(f"{rfa:>9.1f}" + "".join(f"{c:>9.1f}%" for c in cells))
    feed.rf = real_rf
    print("round 4 on this family: 98.9% at rf=2%/lever 3.33 and 0.0% at "
          "rf=0. A flat, rf-independent row is the pass condition; the "
          "benchmark's OWN rate against itself is 0.0%, because a paired "
          "MPPM of exactly 0 does not clear a positive margin.")


def _shv(feed: Feed, oos) -> float:
    """A second cash proxy, for the SCALE of 'which rf did you pick'."""
    try:
        d, c = _bars("SHV", "2015-08-01", "2026-08-21")
        rd, rr = _rets(d, c)
        m = dict(zip(rd, rr))
        xs = []
        for a, b in oos:
            xs.extend([m[dt] for dt in feed.dates[a:b] if dt in m])
        return ann_pct(xs)
    except Exception:  # noqa: BLE001
        return float("nan")


def sec_rf_sensitivity(feed: Feed, args) -> None:
    print("\n=== 3. WHAT THE ACCEPTANCE TEST DOES NOT COVER: rf "
          "MISSPECIFICATION ===")
    print("section 2's invariance holds when the rule's rf is the rate the "
          "cash leg actually earned. Nothing in the harness supplies an rf "
          "series today, so the rule must assume one. Closed form: a cash "
          "mix at weight w whose cash leg earns rf_true while the rule "
          "assumes rf_assumed is credited ((1-w)/w)*(rf_true - rf_assumed) "
          "%/yr of pure arithmetic.")
    g = shipped_folds(feed, end=args.end, hold=HOLD_DAYS, min_folds=MIN_FOLDS,
                      floor=args.floor)
    rows = g["rows"]
    oos = [f["test"] for f in rows]
    rbt, rft = [], []
    for a, b in oos:
        rbt.extend(feed.bench[a:b])
        rft.extend(feed.rf[a:b])
    print(f"\nMEASURED (not derived): paired MPPM %/yr of a zero-skill cash "
          f"mix whose cash leg earns real {feed.rf_symbol} while the rule "
          f"assumes a constant rf. rho {args.rho}, OOS window as in 2a, no "
          f"--market-sharpe assumption.")
    hdr = "".join(f"{'rf_a=' + format(x, '.1f') + '%':>12}"
                  for x in (0.0, 2.0, 4.0, 5.0))
    print(f"{'w':>6}" + hdr + f"{'break-even d':>14}")
    for w in (0.80, 0.60, 0.40, 0.20, 0.10):
        rs = [w * rbt[i] + (1 - w) * rft[i] for i in range(len(rbt))]
        cells = []
        for rfa in (0.0, 2.0, 4.0, 5.0):
            d = (1.0 + rfa / 100.0) ** (1 / 252.0) - 1.0
            es = [(1 + rs[i]) / (1 + d) - 1 for i in range(len(rs))]
            ebx = [(1 + rbt[i]) / (1 + d) - 1 for i in range(len(rbt))]
            v, _ = paired_mppm(es, ebx, args.rho)
            cells.append(v)
        delta = args.margin * w / (1.0 - w)
        print(f"{w:>6.2f}" + "".join(f"{c:>12.3f}" for c in cells)
              + f"{delta:>13.2f}%")
    print(f"'break-even d' is the rf error (%/yr) at which a zero-skill mix "
          f"clears the {args.margin}%/yr margin on arithmetic alone: "
          f"margin*w/(1-w). Scale reference for how wrong an rf choice can "
          f"be - two cash ETFs on the fund's own feed over the same window: "
          f"{feed.rf_symbol} {ann_pct(rft):.2f}%/yr vs SHV "
          f"{_shv(feed, oos):.2f}%/yr.")


def sec_battery(feed: Feed, args) -> None:
    print("\n=== 4. THE BATTERY INCLUDING THE MASKED FAMILY (G2), IN THE "
          "SHIPPED GEOMETRY (G3) ===")
    g = shipped_folds(feed, end=args.end, hold=HOLD_DAYS, min_folds=MIN_FOLDS,
                      floor=args.floor)
    rows = g["rows"]
    lo = min(f["train"][0] for f in rows)
    hi = max(f["test"][1] for f in rows)
    print(_hdr(args, feed, rows, "battery"))
    print("full-sample legs are computed over the CONCATENATED SURVIVING "
          "TEST LEGS - the only daily series the shipped data path can ever "
          "serve (runanalytics.daily_return_legs: train legs are never "
          "captured). Columns after 'pass' are the REJECTION MODE split and "
          "sum with 'pass' to 100%.")
    print(f"\n{'process':>18}{'pass':>8}{'pass|ran':>10}{'neverRan':>10}{'vrCannotTell':>14}"
          f"{'noMajority':>12}{'fullDaily':>11}{'full21d':>9}"
          f"{'trueExcSR':>11}{'medFullMPPM':>13}")
    nulls, tps = [], []
    for name, maker, is_null in battery():
        r = run_cell(maker, feed, rows, lo, hi, args, name,
                     need=MIN_FOLDS, dropout=args.dropout, stat=args.stat)
        m = r["modes"]
        ran = 100.0 - m.get('never_ran', 0.0)
        cond = (100.0 * r['pass_pct'] / ran) if ran > 0 else float('nan')
        print(f"{name:>18}{r['pass_pct']:>7.1f}%"
              f"{cond:>9.1f}%"
              f"{m.get('never_ran', 0.0):>9.1f}%"
              f"{m.get('cannot_tell_vr', 0.0):>13.1f}%"
              f"{m.get('no_majority', 0.0):>11.1f}%"
              f"{m.get('full_daily', 0.0):>10.1f}%"
              f"{m.get('full_21d', 0.0):>8.1f}%"
              f"{r['true_excess_sharpe']:>11.2f}"
              f"{r['median_full_mppm']:>13.2f}")
        (nulls if is_null else tps).append((name, r["pass_pct"]))
    fp_max = max(nulls, key=lambda x: x[1])
    fp_mean = sum(x[1] for x in nulls) / len(nulls)
    tp = dict(tps).get("premia_defensive", 0.0)
    print(f"\nnulls n={len(nulls)}: CLASS MAXIMUM {fp_max[1]:.1f}% "
          f"({fp_max[0]}) | unweighted mean {fp_mean:.1f}% - the mean is "
          f"printed only so it can be compared with round 4's headline; the "
          f"maximum is the number a gate is chosen by.")
    print("\n=== 5. THE DECISION ARITHMETIC, REACHABLE STATE ONLY (G3) ===")
    print(_hdr(args, feed, rows, "decision"))
    for label, fpr in (("class maximum", fp_max[1]),
                       ("battery mean", fp_mean)):
        be = 100.0 * fpr / (fpr + tp) if (fpr + tp) > 0 else float("nan")
        disc = (tp / fpr) if fpr > 0 else float("inf")
        print(f"  FPR ({label}) {fpr:.1f}% | TP (premia_defensive) {tp:.1f}% "
              f"| break-even prior {be:.1f}% | discrimination {disc:.2f}")
    for nm, v in tps:
        if nm == "premia_defensive":
            continue
        be = (100.0 * fp_max[1] / (fp_max[1] + v)) if (fp_max[1] + v) else 0.0
        disc = (v / fp_max[1]) if fp_max[1] > 0 else float("inf")
        print(f"  with {nm} as the TP leg: TP {v:.1f}% -> break-even "
              f"{be:.1f}%, discrimination {disc:.2f} (vs the class maximum)")
    print("round 3 was killed at a 15.8% break-even prior; round 4's "
          "reachable-state numbers were FPR 13.7% / TP 24.5% / break-even "
          "35.8%.")


def sec_measurability(args) -> None:
    print("\n=== 6. MEASURABILITY ACCOUNTING - THE REAL DATA PATH (G4) ===")
    from app.fund import runanalytics
    with urllib.request.urlopen(f"{BASE}/fund/factory/candidates?limit=500",
                                timeout=60) as fh:
        cands = json.load(fh)["candidates"]
    have = [c for c in cands if c.get("analytics_available")]
    print(f"candidates on the belt: {len(cands)}; with analytics captured: "
          f"{len(have)}")
    legs_total = 0
    names_missing: dict[str, int] = {}
    for c in cands:
        det = {}
        try:
            url = f"{BASE}/fund/factory/candidates/{c['candidate_id']}"
            with urllib.request.urlopen(url, timeout=30) as fh:
                det = json.load(fh)
        except Exception:  # noqa: BLE001
            det = {}
        a = det.get("analytics")
        rep = runanalytics.daily_return_legs(
            a if isinstance(a, dict) and a.get("available") else None)
        legs_total += len(rep["captured"])
        for m in rep["missing"]:
            names_missing[m] = names_missing.get(m, 0) + 1
        if rep["captured"]:
            print(f"  {c['candidate_id']} {c['algorithm']}: captured "
                  f"{rep['captured']} | with benchmark "
                  f"{rep['legs_with_benchmark']} | n="
                  f"{rep['total_observations']}")
    print(f"legs COMPUTABLE from the shipped path across the whole belt: "
          f"{legs_total}")
    print(f"legs NOT computable, BY NAME (count of candidates): "
          f"{names_missing if names_missing else 'n/a'}")
    seen: dict[str, int] = {}
    for c in cands:
        r = ((c.get("analytics_absence") or {}).get("reason")) or "available"
        seen[r] = seen.get(r, 0) + 1
    print(f"absence reason reported by runanalytics.view(): {seen}")
    print("dropped_unmatched_days cannot be read where no leg exists; any "
          "volatility computed from a captured leg MUST read that field "
          "(leanrunner._daily_returns) because a dropped day makes the next "
          "return a two-day return wearing a daily label.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260821)
    ap.add_argument("--market-sharpe", type=float, default=1.0,
                    help="the BENCHMARK'S EXCESS Sharpe. A CONDITIONING "
                         "ASSUMPTION, printed in every header.")
    ap.add_argument("--vol", type=float, default=0.20)
    ap.add_argument("--rho", type=float, default=MPPM_RHO)
    ap.add_argument("--margin", type=float, default=PREMIA_MARGIN)
    ap.add_argument("--dropout", type=float, default=BELT_DROPOUT)
    ap.add_argument("--floor", default=HISTORY_FLOOR)
    ap.add_argument("--end", default="2026-08-20")
    ap.add_argument("--real-bench", action="store_true",
                    help="use the fund's REAL benchmark excess series instead "
                         "of a synthetic one - removes the --market-sharpe "
                         "assumption at the cost of a single realisation")
    ap.add_argument("--stat", default="r5", choices=("r5", "r4"),
                    help="r5 = excess returns with financing charged; r4 = "
                         "round 4's total-return statistic, for the "
                         "before/after through IDENTICAL geometry and seeds")
    ap.add_argument("--no-select", action="store_true")
    ap.add_argument("--no-two-scale", action="store_true")
    ap.add_argument("--geometry", action="store_true")
    ap.add_argument("--acceptance", action="store_true")
    ap.add_argument("--rf-sensitivity", action="store_true")
    ap.add_argument("--battery", action="store_true")
    ap.add_argument("--measurability", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if (args.floor or "").lower() in ("none", ""):
        args.floor = None

    any_sec = (args.geometry or args.acceptance or args.rf_sensitivity
               or args.battery or args.measurability)
    if args.all or not any_sec:
        args.geometry = args.acceptance = args.rf_sensitivity = True
        args.battery = args.measurability = True

    feed = Feed()
    print("gate v5 round 5 audit - MEASUREMENT ONLY. Adopts nothing, moves "
          "no threshold.")
    if args.geometry:
        sec_geometry(feed, args)
    if args.acceptance:
        sec_acceptance(feed, args)
    if args.rf_sensitivity:
        sec_rf_sensitivity(feed, args)
    if args.battery:
        sec_battery(feed, args)
    if args.measurability:
        sec_measurability(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
