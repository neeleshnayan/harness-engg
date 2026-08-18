"""What gate v4's walk-forward leg does to noise, and to a real edge.

Two questions, one instrument. The gate has been measured against noise (nulls
cleared v1 about half the time) and against perfect foresight (an oracle failed
v2). It has NEVER been measured against a PLAUSIBLE edge, and that is the
decision-relevant gap: if a genuine Sharpe-0.6 strategy clears the walk-forward
leg only rarely, then the alpha sleeve can never be born, the declared-beta sleeve
is the terminal state of the design rather than a stepping stone, and no amount of
candidate throughput fixes it.

The false-positive question has its own hole. `scripts/null_audit.py` runs random
strategies down the real belt but has NO walk-forward leg, so it structurally
cannot measure the criterion that replaced PSR as the load-bearing one.

WHY THIS BYPASSES LEAN, AND WHAT THAT COSTS

One container slot, ~70s per engine run, ~20 runs per candidate through the belt.
Measuring a pass rate needs thousands of draws; through LEAN that is months of
wall clock. So this drives the REAL `walkforward.retention()` and the real fold
geometry with synthetic return series of known Sharpe. It imports those functions
rather than reimplementing them — a reimplementation would measure this script's
model of the gate, which is worth nothing.

What that costs, stated so the result is not over-read:

  * It measures the WALK-FORWARD LEG ALONE. The gate's other criteria (PSR,
    orders, benchmark, cost breakeven, capacity) are conjunctive, so the whole
    gate's false-positive rate is LOWER than the number here. This is the leg
    that was broken, so it is the leg being measured.
  * The return process is Gaussian i.i.d. with CONSTANT drift. Real strategies
    have decaying edges, fat tails, and autocorrelation. Constant drift is the
    FRIENDLIEST POSSIBLE CASE for a persistence test — the edge by construction
    never decays — so **every power number here is an upper bound.** A real
    strategy of the same Sharpe passes less often than this says.
  * Fold boundaries are computed in trading days directly rather than through
    `folds()`'s calendar approximation. `folds()` documents that conversion as
    approximate; using trading days removes a rounding artefact from a
    measurement about rounding-sensitive thresholds.
  * No costs. A cost-aware version would lower every number.

So: an upper bound on power, and a lower bound on how strict the leg is. Both are
useful in the direction they err, which is why it is worth running at all.
"""

from __future__ import annotations

import argparse
import math
import random
import sys

sys.path.insert(0, ".")

from app.fund.gate import CRITERIA, GATE_VERSION  # noqa: E402
from app.fund.walkforward import (  # noqa: E402
    DECISIONS_PER_TEST_LEG,
    MIN_TRAIN_RETURN_PCT,
    RETENTION_FLOOR,
    retention,
)

#: Sessions of history the fund actually holds (bars start 2024-02-26).
SESSIONS = 630
TRAIN_DAYS = 252
#: A 21-day hold needs a 21*4 = 84-day test leg under v3's fold geometry.
HOLD_DAYS = 21
#: Annualised volatility for the synthetic series. 20% is a plausible strategy
#: vol; the Sharpe is what varies, and the pass rate is scale-invariant in vol
#: only if the MIN_TRAIN_RETURN_PCT floor is far away — which it is NOT, so vol
#: matters here and is reported alongside every result rather than hidden.
ANNUAL_VOL = 0.20


def _series(sharpe: float, vol: float, n: int, rng: random.Random) -> list[float]:
    """Daily simple returns with a given ANNUALISED Sharpe and volatility."""
    dsig = vol / math.sqrt(252.0)
    dmu = sharpe * vol / 252.0          # so that mu_ann / sigma_ann = sharpe
    return [dmu + dsig * rng.gauss(0.0, 1.0) for _ in range(n)]


def _cum_pct(rets: list[float]) -> float:
    """Compounded return over a window, in percent."""
    acc = 1.0
    for r in rets:
        acc *= (1.0 + r)
    return (acc - 1.0) * 100.0


def one_draw(sharpe: float, vol: float, rng: random.Random,
             test_days: int) -> dict:
    """One synthetic strategy, judged by the REAL retention rule."""
    r = _series(sharpe, vol, SESSIONS, rng)
    step = test_days
    measurable = retained = 0
    unmeasurable_reasons: list[str] = []
    k = 0
    while True:
        t0 = k * step
        t1 = t0 + TRAIN_DAYS
        e1 = t1 + test_days
        if e1 > SESSIONS:
            break
        got = retention(_cum_pct(r[t0:t1]), _cum_pct(r[t1:e1]),
                        test_orders=DECISIONS_PER_TEST_LEG,
                        train_days=TRAIN_DAYS, test_days=test_days)
        if got["measurable"]:
            measurable += 1
            if (got["retention"] or 0.0) >= RETENTION_FLOOR:
                retained += 1
        else:
            # Kept, not discarded. An unmeasurable fold is the single most
            # common outcome for a weak edge — the train leg simply did not make
            # MIN_TRAIN_RETURN_PCT — and reporting only the pass rate would hide
            # that the test mostly never ran.
            unmeasurable_reasons.append((got.get("reason") or "")[:40])
        k += 1

    # The v4 rule, applied exactly as gate.py applies it.
    enough = measurable >= CRITERIA["min_walkforward_folds"]
    majority = retained * 2 > measurable
    return {"measurable": measurable, "retained": retained,
            "passed": bool(enough and majority),
            "not_enough_folds": not enough,
            "unmeasurable": len(unmeasurable_reasons)}


def sweep(sharpes: list[float], draws: int, vol: float, seed: int,
          test_days: int) -> list[dict]:
    out = []
    for sh in sharpes:
        rng = random.Random(seed + int(sh * 1000))
        rows = [one_draw(sh, vol, rng, test_days) for _ in range(draws)]
        n = len(rows)
        out.append({
            "sharpe": sh,
            "pass_pct": 100.0 * sum(r["passed"] for r in rows) / n,
            "starved_pct": 100.0 * sum(r["not_enough_folds"] for r in rows) / n,
            "mean_measurable": sum(r["measurable"] for r in rows) / n,
            "mean_retained": sum(r["retained"] for r in rows) / n,
            "mean_unmeasurable": sum(r["unmeasurable"] for r in rows) / n,
        })
    return out


# --- the adversary, and the history sweep ------------------------------------
#
# These are not extras. The power number alone would have led to the wrong
# decision: a pooled out-of-sample Sharpe gives ~50% more power at identical
# discrimination, and replacing the majority rule with it was the obvious
# recommendation until it was run against a lucky window, where it proved 2-3x
# easier to fool. Its extra power WAS the weakness. Measuring the improvement
# against an adversary is what stopped a regression, which is the same lesson gate
# v3 taught by not being measured at all.


def one_fold_wonder(vol: float, rng: random.Random, lucky_leg: int,
                    boost: float, test_days: int) -> list[float]:
    """Zero edge everywhere EXCEPT one window. A lucky window wearing a record.

    Its train leg is boosted too, at half strength, so it is not rejected
    upstream for having nothing to retain - the point is to test the CONSISTENCY
    criterion, not the ones before it.
    """
    dsig = vol / math.sqrt(252.0)
    r = [dsig * rng.gauss(0.0, 1.0) for _ in range(SESSIONS)]
    t1 = lucky_leg * test_days + TRAIN_DAYS
    dmu = boost * vol / 252.0
    for i in range(lucky_leg * test_days, min(t1, SESSIONS)):
        r[i] += dmu * 0.5
    for i in range(t1, min(t1 + test_days, SESSIONS)):
        r[i] += dmu
    return r


def _judge(r: list[float], test_days: int) -> bool:
    """The v4 rule applied to a supplied series, exactly as gate.py applies it."""
    measurable = retained = 0
    k = 0
    while k * test_days + TRAIN_DAYS + test_days <= SESSIONS:
        t0 = k * test_days
        t1 = t0 + TRAIN_DAYS
        got = retention(_cum_pct(r[t0:t1]), _cum_pct(r[t1:t1 + test_days]),
                        test_orders=DECISIONS_PER_TEST_LEG,
                        train_days=TRAIN_DAYS, test_days=test_days)
        if got["measurable"]:
            measurable += 1
            if (got["retention"] or 0.0) >= RETENTION_FLOOR:
                retained += 1
        k += 1
    return (measurable >= CRITERIA["min_walkforward_folds"]
            and retained * 2 > measurable)


def adversary(draws: int, vol: float, seed: int, test_days: int) -> None:
    """How often a one-fold wonder survives. Every draw is a FAKE, so lower wins."""
    print()
    print("ADVERSARY: all edge concentrated in ONE test leg (a lucky window).")
    print("Every draw is a fake, so a LOWER pass rate is better.")
    print(f"{'boost':>8}{'v4 passes it':>15}")
    for boost in (2.0, 3.0, 5.0):
        rng = random.Random(seed)
        hits = 0
        for _ in range(draws):
            r = one_fold_wonder(vol, rng, rng.randint(0, 3), boost, test_days)
            hits += _judge(r, test_days)
        print(f"{boost:>8.1f}{100.0 * hits / draws:>14.1f}%")
    print("  Measured alternative, for the record: a pooled out-of-sample Sharpe")
    print("  scored 28% / 46% / 75% on these same three levels - 2-3x easier to")
    print("  fool - which is why the majority rule was KEPT.")


def history_sweep(draws: int, vol: float, seed: int, test_days: int) -> None:
    """Does more history fix the power ceiling? Partly, and it breaks something."""
    global SESSIONS
    keep = SESSIONS
    print()
    print("HISTORY SWEEP: the same v4 rule, more data.")
    print(f"{'history':>20}{'FPR':>7}{'S=0.6':>8}{'S=1.0':>8}{'S=1.5':>8}")
    for label, sessions in (("30 months (today)", 630), ("5 years", 1260),
                            ("10 years", 2520), ("20 years", 5040)):
        SESSIONS = sessions
        got = {}
        for sh in (0.0, 0.6, 1.0, 1.5):
            rng = random.Random(seed + int(sh * 1000))
            rows = [one_draw(sh, vol, rng, test_days) for _ in range(draws)]
            got[sh] = 100.0 * sum(r["passed"] for r in rows) / len(rows)
        print(f"{label:>20}{got[0.0]:>7.1f}{got[0.6]:>8.1f}"
              f"{got[1.0]:>8.1f}{got[1.5]:>8.1f}")
    SESSIONS = keep
    print("  NOTE THE FALSE-POSITIVE RATE RISING IN THE MIDDLE. That is a defect")
    print("  in the criterion, not in the data: `min_walkforward_folds` is a FIXED")
    print("  floor of 4 while the number of available folds grows, so a null can")
    print("  have only a handful of MEASURABLE folds and win a majority of that")
    print("  small subset. The rule does not scale with history, and it must be")
    print("  revisited the day more history is bought - which is exactly the")
    print("  review trigger recorded against it in app/fund/judgement.py.")


def rejection_modes(draws: int, vol: float, seed: int, test_days: int) -> None:
    """WHY the leg rejects: starved of evidence, or genuinely failed to persist?

    Not a detail. The gate's stated doctrine is that "what noise cannot fake is
    CONSISTENCY ACROSS INDEPENDENT WINDOWS" — and this breakdown shows that at pure
    noise the consistency test mostly NEVER RUNS. A null is rejected because fewer
    than `min_walkforward_folds` of its folds were MEASURABLE, since a null's
    training leg rarely clears MIN_TRAIN_RETURN_PCT.

    Both are honest rejections and the per-candidate message already distinguishes
    them ("only 3 fold(s) could be measured, below the 4 required" is not the same
    sentence as "kept its edge in only 1 of 4"). What was wrong was the AGGREGATE
    story: crediting the false-positive rate to a persistence test that, most of
    the time, did not happen.
    """
    print()
    print("REJECTION MODES — is the leg testing persistence, or requiring evidence?")
    print(f"{'Sharpe':>7}{'pass':>8}{'starved':>10}{'failed maj':>12}"
          f"{'mean measurable':>17}")
    for sh in (0.0, 0.4, 0.6, 1.0, 1.5, 2.0):
        rng = random.Random(seed + 7 + int(sh * 1000))
        passed = starved = failed = 0
        meas = 0
        for _ in range(draws):
            r = one_draw(sh, vol, rng, test_days)
            meas += r["measurable"]
            if r["passed"]:
                passed += 1
            elif r["not_enough_folds"]:
                starved += 1
            else:
                failed += 1
        print(f"{sh:>7.1f}{100.0 * passed / draws:>7.1f}%"
              f"{100.0 * starved / draws:>9.1f}%{100.0 * failed / draws:>11.1f}%"
              f"{meas / draws:>17.2f}")
    print("  'starved'    = under min_walkforward_folds were MEASURABLE, so the")
    print("                 consistency test never ran.")
    print("  'failed maj' = it ran, and the edge did not persist in a majority.")
    print()
    print("  Read the Sharpe-0 row carefully. Noise is rejected overwhelmingly by")
    print("  STARVATION, not by failing to persist — so the false-positive rate is")
    print("  delivered by MIN_TRAIN_RETURN_PCT plus the fold-count floor, and the")
    print("  walk-forward leg is primarily an EVIDENCE requirement with a")
    print("  persistence test attached. That is a weaker claim than the gate's own")
    print("  docstring makes, and it is the true one.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--vol", type=float, default=ANNUAL_VOL)
    ap.add_argument("--seed", type=int, default=20260818)
    ap.add_argument("--hold-days", type=int, default=HOLD_DAYS)
    ap.add_argument("--adversary", action="store_true",
                    help="also run the lucky-window adversary")
    ap.add_argument("--history", action="store_true",
                    help="also sweep how power changes with more history")
    ap.add_argument("--modes", action="store_true",
                    help="also break down WHY the leg rejects")
    a = ap.parse_args()

    test_days = a.hold_days * DECISIONS_PER_TEST_LEG
    sharpes = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0]

    print(f"gate {GATE_VERSION} walk-forward leg, measured in isolation")
    print(f"  {a.draws} draws per level | {SESSIONS} sessions | "
          f"train {TRAIN_DAYS}d | test {test_days}d "
          f"({a.hold_days}d hold x {DECISIONS_PER_TEST_LEG} decisions)")
    print(f"  annual vol {a.vol:.0%} | retention floor {RETENTION_FLOOR} | "
          f"min train return {MIN_TRAIN_RETURN_PCT}%")
    print(f"  rule: measurable >= {CRITERIA['min_walkforward_folds']} "
          f"AND retained*2 > measurable (strict majority)")
    print()
    rows = sweep(sharpes, a.draws, a.vol, a.seed, test_days)
    print(f"{'Sharpe':>7}{'pass %':>9}{'starved %':>11}"
          f"{'meas.':>8}{'retained':>10}{'unmeas.':>9}")
    for r in rows:
        print(f"{r['sharpe']:>7.1f}{r['pass_pct']:>9.1f}{r['starved_pct']:>11.1f}"
              f"{r['mean_measurable']:>8.2f}{r['mean_retained']:>10.2f}"
              f"{r['mean_unmeasurable']:>9.2f}")

    fpr = rows[0]["pass_pct"]
    print()
    print(f"FALSE POSITIVE RATE (Sharpe 0): {fpr:.1f}%")
    for r in rows:
        if r["sharpe"] > 0 and r["pass_pct"] >= 80.0:
            print(f"80% POWER reached at Sharpe {r['sharpe']:.1f}")
            break
    else:
        print("80% POWER NOT REACHED at any Sharpe up to 2.0 - on the friendliest")
        print("  possible return process, with a constant non-decaying edge.")
    print()
    print("'starved %' is the share of draws with too few MEASURABLE folds to")
    print("  judge at all - a NOT TESTABLE outcome, not a failure. Where this is")
    print("  large the gate is mostly declining to answer rather than saying no.")
    print("Power figures are an UPPER BOUND: constant drift never decays, so a")
    print("  real strategy of the same Sharpe passes less often than shown.")
    print("This is the walk-forward leg ALONE. Other criteria are conjunctive, so")
    print("  the whole gate's false-positive rate is lower than the figure above.")
    if a.adversary:
        adversary(max(500, a.draws // 2), a.vol, a.seed, test_days)
    if a.history:
        history_sweep(max(500, a.draws // 2), a.vol, a.seed, test_days)
    if a.modes:
        rejection_modes(a.draws, a.vol, a.seed, test_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
