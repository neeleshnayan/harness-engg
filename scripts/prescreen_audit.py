"""Does the sieve throw away real edges? That number is its licence to exist.

A pre-screen's cheap error is wasting a container on a dud. Its expensive error is
**rejecting something real**, because nothing downstream will ever look at that
candidate again — the edge is destroyed silently and permanently. So the only
measurement that matters is the FALSE-NEGATIVE rate: how often does the sieve
discard a series the gate's own walk-forward leg would have kept?

Measured the way gate_power_audit measures power: synthetic series of known Sharpe
driven through the sieve's fold logic and the gate's fold logic side by side, so the
comparison is between two rules rather than between a rule and an opinion.

Also reports throughput, which is the entire point of the exercise: how many
organisms per second, and what that does to the 230-hour population estimate.

WHAT THIS DOES NOT COVER, stated so the result is not over-read:

  * The sieve's SIGNAL path (`_equity_curve`) is not compared against LEAN. This
    audit tests the accept/reject logic, not whether a vectorised cross-sectional
    rule reproduces what the engine does with the same spec. That comparison needs
    real engine runs and is the obvious next audit.
  * Gaussian iid returns with constant drift, as in the power audit. Friendliest
    possible world for any persistence test.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import time

sys.path.insert(0, ".")

from app.fund.gate import CRITERIA  # noqa: E402
from app.fund.prescreen import (  # noqa: E402
    MIN_FOLD_SHARE, MIN_SHARPE, MIN_TRADES, grid_to_specs, population,
)
from app.fund.walkforward import (  # noqa: E402
    DECISIONS_PER_TEST_LEG, RETENTION_FLOOR, retention,
)

SESSIONS = 630
TRAIN = 252
HOLD = 21


def _series(sharpe: float, vol: float, n: int, rng: random.Random) -> list[float]:
    dsig = vol / math.sqrt(252.0)
    dmu = sharpe * vol / 252.0
    return [dmu + dsig * rng.gauss(0.0, 1.0) for _ in range(n)]


def _cum(rets, a, b) -> float:
    acc = 1.0
    for r in rets[a:b]:
        acc *= (1.0 + r)
    return (acc - 1.0) * 100.0


def _folds(rets, test_days: int):
    measurable = retained = 0
    k = 0
    while (k + 1) * test_days + TRAIN <= len(rets):
        t0 = k * test_days
        t1 = t0 + TRAIN
        got = retention(_cum(rets, t0, t1), _cum(rets, t1, t1 + test_days),
                        test_orders=DECISIONS_PER_TEST_LEG,
                        train_days=TRAIN, test_days=test_days)
        if got["measurable"]:
            measurable += 1
            if (got["retention"] or 0.0) >= RETENTION_FLOOR:
                retained += 1
        k += 1
    return measurable, retained


def _sharpe(rets) -> float:
    n = len(rets)
    mu = sum(rets) / n
    var = sum((r - mu) ** 2 for r in rets) / n
    return (mu / math.sqrt(var) * math.sqrt(252.0)) if var > 1e-18 else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=3000)
    ap.add_argument("--vol", type=float, default=0.20)
    ap.add_argument("--seed", type=int, default=20260818)
    a = ap.parse_args()

    test_days = HOLD * DECISIONS_PER_TEST_LEG
    need_folds = CRITERIA["min_walkforward_folds"]

    print("PRE-SCREEN vs GATE, on the same synthetic series")
    print(f"  {a.draws} draws per level | {SESSIONS} sessions | vol {a.vol:.0%}")
    print(f"  sieve floors: Sharpe {MIN_SHARPE}, {MIN_TRADES} rebalances, "
          f"{MIN_FOLD_SHARE:.0%} of folds")
    print(f"  gate: {need_folds} measurable folds AND a strict majority")
    print()
    print(f"{'Sharpe':>7}{'gate keeps':>12}{'sieve keeps':>13}"
          f"{'FALSE NEG':>11}{'wasted runs':>13}")

    worst_fn = 0.0
    for sh in (0.0, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0):
        rng = random.Random(a.seed + int(sh * 1000))
        gate_keep = sieve_keep = both = gate_only = sieve_only = 0
        for _ in range(a.draws):
            r = _series(sh, a.vol, SESSIONS, rng)
            meas, ret = _folds(r, test_days)

            g = meas >= need_folds and ret * 2 > meas
            share = (ret / meas) if meas else None
            s = (_sharpe(r) >= MIN_SHARPE
                 and (share is None or share >= MIN_FOLD_SHARE))

            gate_keep += g
            sieve_keep += s
            both += (g and s)
            gate_only += (g and not s)
            sieve_only += (s and not g)

        # The expensive error: the gate WOULD have kept it and the sieve killed it.
        fn = (100.0 * gate_only / gate_keep) if gate_keep else 0.0
        # Counted ONLY where a real edge exists. At Sharpe 0 every "gate keeps" is a
        # gate FALSE POSITIVE, so the sieve rejecting one is the sieve being right —
        # including that level pushed the headline from 4.2% to 6.8% and would have
        # penalised the sieve for catching noise the gate let through. The Sharpe-0
        # row is still printed, and read as a feature rather than a fault.
        if sh > 0.0:
            worst_fn = max(worst_fn, fn)
        # The cheap error: sieve passes something the gate then kills. This is the
        # cost of the sieve being loose, and it is supposed to be large.
        waste = (100.0 * sieve_only / sieve_keep) if sieve_keep else 0.0
        print(f"{sh:>7.1f}{100.0 * gate_keep / a.draws:>11.1f}%"
              f"{100.0 * sieve_keep / a.draws:>12.1f}%"
              f"{fn:>10.1f}%{waste:>12.1f}%")

    print()
    print(f"WORST FALSE-NEGATIVE RATE (Sharpe > 0 only): {worst_fn:.1f}%")
    print("  The Sharpe-0 row above is NOT a false-negative rate. There is no edge")
    print("  to lose at Sharpe 0, so every 'gate keeps' on that row is a gate false")
    print("  POSITIVE, and the sieve disagreeing is the sieve catching noise the")
    print("  gate let through.")
    if worst_fn > 5.0:
        print("  ABOVE 5%. The sieve is discarding real edges too often; loosen the")
        print("  floors before using it to gate a population.")
    else:
        print("  Under 5%. The sieve is safe to place in front of the belt: almost")
        print("  nothing the gate would have kept gets thrown away first.")
    print("  'wasted runs' is the sieve passing things the gate then kills. It is")
    print("  SUPPOSED to be high — that is what being loose buys.")

    # --- throughput, which is the whole reason this exists -------------------
    print()
    print("THROUGHPUT on real bars")
    from app.fund.correlation import aligned_returns
    from app.fund.marketdata import fetch_daily_bars

    universe = ["SPY", "GLD", "XLE", "MSFT", "NVDA", "INTC", "SOFI",
                "TLT", "IWM", "XLV", "XLU", "DBC"]
    closes: dict[str, list[float]] = {}
    t0 = time.monotonic()
    for sym in universe:
        try:
            b = fetch_daily_bars(sym, lookback_days=900)
            if b and b.closes:
                closes[sym] = list(b.closes)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: no history ({type(e).__name__})")
    load_s = time.monotonic() - t0
    print(f"  loaded {len(closes)} symbols in {load_s:.1f}s (ONCE, not per organism)")
    if len(closes) < 2:
        print("  not enough history to benchmark the sieve")
        return 0

    specs = grid_to_specs("xs_momentum", lookbacks=(20, 40, 60, 90, 120),
                          holds=(5, 10, 21, 42), top_ns=(2, 3, 4, 5),
                          long_short=(False, True))
    specs += grid_to_specs("xs_meanrev", lookbacks=(5, 10, 20, 40),
                           holds=(5, 10, 21), top_ns=(2, 3, 4))
    t0 = time.monotonic()
    out = population(specs, list(closes), closes)
    dt = time.monotonic() - t0

    per = dt / max(1, len(specs))
    print(f"  {len(specs)} organisms sieved in {dt:.2f}s "
          f"({per * 1000:.1f} ms each)")
    print(f"  kept {len(out['worth_a_container'])}, "
          f"rejected {len(out['rejected'])}, refused {len(out['refused'])} "
          f"(kill rate {out['kill_rate_pct']}%)")
    print()
    # The comparison the operator actually cares about.
    lean_min = 14.0            # ~20 engine runs at ~70s, measured
    pop = 50 * 20
    kept_share = (len(out["worth_a_container"]) / max(1, len(specs)))
    before = pop * lean_min / 60
    after = pop * kept_share * lean_min / 60
    print(f"  A {pop}-organism population (50 x 20 generations):")
    print(f"    LEAN only:      {before:.0f} hours")
    print(f"    sieve first:    {pop * per / 60:.1f} min to sieve, then "
          f"{after:.0f} hours on the {kept_share:.0%} that survived")
    print(f"    saving:         {before - after:.0f} hours "
          f"({100 * (1 - after / before):.0f}%)")
    print(f"  One generation of 50, which is the unit that matters day to day: "
          f"{50 * lean_min / 60:.1f}h -> {50 * kept_share * lean_min / 60:.1f}h.")
    print()
    print("  Read honestly: the sieve does not make the survivors cheaper, it makes")
    print(f"  the {1 - kept_share:.0%} it kills free. That turns a single generation")
    print("  into an overnight run and a full 20-generation search into days rather")
    print("  than weeks — a real unblock, and NOT the same as making it cheap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
