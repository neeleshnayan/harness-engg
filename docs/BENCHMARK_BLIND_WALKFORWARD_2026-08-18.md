# The walk-forward leg cannot tell alpha from beta

**Found by the v4 null audit on the real belt, 2026-08-17. This is what a
simulation could not have told us, and it is the reason that audit was worth
running.**

## What happened

Six random-entry nulls went down the belt. All six were rejected, so the headline
reads **"FALSE POSITIVE RATE 0%"** — and that headline is the least useful sentence
in the report.

**Seed 55, a pure random-entry strategy, retained its edge in 4 of 4 independent
walk-forward folds.** It passed the consistency test outright. What stopped it was
`probabilistic Sharpe 43.113% is below 65.0%` — PSR, the criterion that
walk-forward was introduced in v2 to *supersede*.

That inverts the entire v1 → v2 argument. The reasoning then was: *a PSR floor does
not separate noise at this sample length, so v2 requires consistency across
independent windows, which is what noise cannot fake.* Noise faked it perfectly,
and the floor it was supposed to replace is what caught it.

## Why

`walkforward.retention()` compares the strategy's **raw** train return to its
**raw** test return. It never subtracts a benchmark — the word appears twice in the
module and neither is in the retention path.

So in a rising market a random long-only strategy makes money in every window, and
retention faithfully reports that the edge persisted. It never had an edge. It had
beta.

The benchmark over the audit window returned **60.88%**. Simulated, with a null
that holds a market of the given drift:

| market drift (Sharpe) | walk-forward leg passes a NULL |
|---|---|
| 0.0 — driftless | 3.2% |
| 0.4 | 8.5% |
| 0.8 | 15.7% |
| 1.2 | **26.9%** |

Seed 55 going 4-of-4 is not a fluke. It is the expected behaviour of this criterion
in a bull market.

**Every previous calibration of this leg used a driftless null**, including the
2.9% false-positive rate in `GATE_CALIBRATION_2026-08-18.md`. A driftless null is
the one thing a real null never is. That number describes a world we do not trade
in.

## The fix, measured

Subtract the benchmark and compute retention on **excess** return — which is what
`must_beat_benchmark` already asks for elsewhere in the same gate. Simulated at
market Sharpe 1.0, 2,000 draws:

| strategy | RAW (today) | EXCESS (proposed) |
|---|---|---|
| **null — pure beta** | **18.4%** | **2.3%** |
| real edge, Sharpe 0.6 | 26.6% | 10.2% |
| real edge, Sharpe 1.0 | 33.0% | 20.5% |
| **discrimination @ Sharpe 1.0** | **1.79** | **8.9** |

Discrimination improves five-fold. Power falls (33.0% → 20.5%) and that is the
correct trade: the power the raw version showed was largely the ability to detect
beta, which we do not want detected.

For scale, gate **v3** — the loosening caught and reverted this morning — scored
1.21. The current v4 leg, on a realistic market, scores **1.79**. The load-bearing
criterion has been running only marginally better than the version we called nearly
uninformative, for a completely different reason.

## Why this is not shipped yet

It is a change to what the criterion *means*, not a threshold, and the plumbing is
not there. A fold's result carries only `return_pct`, `sharpe` and `window` —
`_sweep_point` never captured a benchmark. Implementing this needs:

1. benchmark return threaded through `_sweep_point` into each fold's train and test
2. a decision for strategies where **no valid benchmark exists**. The benchmark is
   already refused unless it is single-symbol and strictly positive throughout, so
   multi-name strategies may have none — and "no benchmark" must become NOT
   MEASURABLE rather than silently falling back to raw, which would reintroduce the
   bug for exactly the strategies most likely to be beta in disguise
3. a re-run of the null audit and the power audit under the new definition
4. gate v5, with `CRITERIA_V4` preserved complete

Point 2 is the real design question and is worth deciding together rather than at
02:00 by one party.

## The pattern, said plainly

This is the **third** appearance of the same bug in one day:

1. The pre-screen killed only 16% of a real grid until it screened on excess return
   — in a rising market almost any long-only rule shows a positive Sharpe
2. Real nulls cleared `MIN_TRAIN_RETURN_PCT` on market drift, contradicting a
   simulation that predicted they would be starved of measurable folds
3. And now: a null retains its "edge" in 4 of 4 folds because all four windows rose

Every measurement this fund makes against **raw return** in a rising market is
measuring beta and calling it skill. The gate has a `must_beat_benchmark` criterion
precisely because somebody understood this — and the criterion that replaced it as
load-bearing does not apply the same discipline.

Worth checking every other place a raw return is compared to anything.
