# Gate v5 design — beta-adjusted alpha, paired-Sharpe premia

**Status: KILLED, round 2 — see docs/reviews/ADVERSARY_GATE_V5_2026-08-19.md.
The premia rule's 0.0% null rows were an artifact of zero-idio-vol nulls: with any
tracking noise the strict Sharpe comparison is a per-fold coin flip (~30% false
pass), all-cash passes 68% in falling markets, and the main table measured a floor
the doc did not adopt. Round 3 must add a significance margin to the paired
comparison, define falling-market and degenerate-Sharpe behaviour, and regenerate
every table at the adopted floor with realistic nulls. The previous sketch (in
BENCHMARK_BLIND_WALKFORWARD_2026-08-18.md) was round 1's kill; each round is
narrowing the design against demonstrations, which is the process working.**

## What the kill demonstrated

1. Subtracting 1× the benchmark removes beta = 1 only — a 2× levered null passed
   4-of-4 folds *under the sketch's own fix*.
2. Plain excess kills every defensive premia candidate by construction: negative
   excess in every rising fold, unexaminable forever — while the fund had just
   adopted a premia mandate.
3. `MIN_TRAIN_RETURN_PCT` was never re-derived for the excess scale, and the
   gate's 0-measurable branch converts benchmark absence into a failure sentence.
4. The "benchmark is already refused" premise was false on the sweep path
   (`enrich=False`), and the sketch would have threaded an unvalidated number.
5. The sketch's tables had no reproduction path.
6. The single-window holdout retention stayed raw — the same bug one criterion up.

## The redesign, rule by rule

### Alpha claims: beta-adjusted excess

Beta is estimated on the **train leg only** (OLS on daily returns) and applied
out-of-sample to both legs: `excess_t = strat_t − β_train · bench_t`. Retention is
then computed on the excess series exactly as today.

Semantics change with the scale, deliberately: **for an alpha claim, a train leg
whose excess is not strictly positive is a FAILED fold, not an absent one.** On raw
returns a flat train leg was ambiguous (flat market vs bad strategy), which is why
"unmeasurable" was honest there. With beta removed, "no excess in training" *is*
evidence of no alpha. This is what dissolves the starvation amplification the kill
predicted: alpha folds are always measurable.

### Premia claims: paired Sharpe, no subtraction at all

A fold is retained if the strategy's **test-leg Sharpe exceeds the benchmark's
test-leg Sharpe**. Strict majority of folds, as in v4. No ratio, no denominator, no
floor. This is literally the premia mandate's success criterion ("better
risk-adjusted return than holding the asset"), applied per fold.

Leverage and de-leverage exactly preserve Sharpe, so a levered or watered null can
*match* but never *beat* the benchmark's Sharpe — the strict inequality is what
makes the β=2 fake structurally unable to pass.

### Claim routing

A candidate **declares its claim type** (`CLAIM_TYPE = "premia" | "alpha"` as a
module constant, read the same way `HOLD_DAYS` already is). Undeclared candidates
default to `alpha` — the stricter reading, and the correct one for every historical
candidate. `evaluate()` gains a `claim_type` parameter; `CRITERIA` gains
`premia_min_folds_beaten` alongside the existing walk-forward keys. `CRITERIA_V4`
is preserved complete.

### Benchmark plumbing (kill point 4)

A candidate **declares its benchmark symbol** (`BENCHMARK = "SPY"`, module
constant). The daily series is fetched **once per candidate** through
`marketdata.fetch_daily_bars` — the validated path — and sliced per fold window
outside `_sweep_point`. Zero per-point fetches; the engine's unvalidated benchmark
curve is never used for judging.

No declared benchmark → the walk-forward leg reports **BENCHMARK ABSENT**, its own
verdict with its own sentence ("declare a benchmark or the claim cannot be
judged"), never folded into starvation and never a silent fallback to raw — a raw
fallback would reintroduce the bug for exactly the strategies most likely to be
beta in disguise.

### The floor on the excess scale (kill point 3) — measured, answer: zero

```
venv/Scripts/python.exe scripts/gate_v5_audit.py --draws 1500 --floor-sweep
```

| floor % | null β=1 | null β=2 | alpha S0.6 | alpha S1.0 |
|---|---|---|---|---|
| 0.0 | 0.0% | 0.0% | 19.3% | 31.7% |
| 1.0 | 0.0% | 0.0% | 15.9% | 27.3% |
| 2.0 | 0.0% | 0.0% | 14.3% | 26.5% |
| 5.0 | 0.0% | 0.0% | 10.5% | 22.1% |

Beta-adjustment plus a **strict-positive denominator guard** already hold both
nulls at 0.0% at every floor level; every point of floor above zero only destroys
power. So `MIN_TRAIN_EXCESS` is **0 (strictly positive)** — the guard does the
ratio-stability job the old 5.0 was invented for, and the 5.0 is retired on this
path rather than ported. (At 1,500 draws, "0.0%" means < ~0.2% at 95% confidence —
a bound, not a zero.)

The guard earned its keep during this very audit: the first sweep run crashed with
`ZeroDivisionError` at floor 0 — the 1379%-retention disease reappearing on the
excess scale the moment the floor alone was trusted.

### The main table

```
venv/Scripts/python.exe scripts/gate_v5_audit.py --draws 1500
```

Market Sharpe 1.0 (the regime that produced seed 55), 630 sessions, 4 folds:

| process | v4 raw (today) | naive excess (killed sketch) | v5 alpha | v5 premia | correct verdict |
|---|---|---|---|---|---|
| null β=1 | 22.5% | 0.0% | **0.0%** | **0.0%** | fail / fail |
| **null β=2** | 22.5% | **21.4%** | **0.0%** | **0.0%** | fail / fail |
| premia (defensive, β=0.5 + real premium) | 24.2% | **0.3%** | 11.1% | **39.3%** | fail / **PASS** |
| alpha S0.6 | 26.7% | 10.5% | 15.9% | 44.4% | **PASS** / — |
| alpha S1.0 | 33.7% | 19.6% | 28.3% | 60.3% | **PASS** / — |

Reading it against the kill:

- **β=2 null: 21.4% under the killed sketch → 0.0% under both v5 rules.** The
  levered fake cannot pass alpha (its beta is estimated and removed) and cannot
  pass premia (leverage preserves Sharpe; strict `>` never fires).
- **The defensive premia candidate: 0.3% under the sketch → 39.3% under the premia
  rule.** Examinable again. 39.3% is modest because this synthetic premia's true
  Sharpe edge is small (≈1.11 vs 1.0); power rises with the edge.
- An alpha strategy passing the premia rule (44–60%) is **correct, not a leak**: a
  strategy with genuine alpha at β=1 really does have better risk-adjusted returns
  than the benchmark. The claim types are claims, not disjoint species — alpha
  implies premia-quality, never the reverse.

### The single-window holdout (kill point 6)

Same routing as the folds: alpha → beta-adjusted excess retention with the same
guard; premia → paired Sharpe on the holdout test window. No raw comparison
survives anywhere in the gate.

## Implementation items (in order, each with its test)

1. `marketdata`-sourced benchmark series per candidate; slicing helper with fold
   windows; validation (single symbol, strictly positive throughout) at
   declaration time.
2. `declared_claim_type()` and `declared_benchmark()` beside `declared_hold_days()`
   in the same AST-constant pattern.
3. `walkforward.retention_excess()` (beta-adjusted, strict-positive guard) and
   `walkforward.fold_sharpe_pair()`; both driven by the daily series, which the
   fold results must now carry.
4. Gate v5: `claim_type` routing, `BENCHMARK ABSENT` as a distinct verdict,
   `CRITERIA_V4` preserved complete, `GATE_VERSION = "v5"`.
5. Re-run: the null audit (β=1 *and* a levered variant) and the power audit under
   v5 on the real belt. The tables above are a **model** of the gate; the belt run
   is the gate. Both, per FUND_GENESIS stage 03.
6. Register entries: the premia criterion, the retired floor (with this doc as the
   written reason), and `min_walkforward_folds`'s known non-scaling defect carries
   over unchanged.

## What this design does NOT fix, stated so it is not over-read

- Gaussian iid, constant beta within a fold, one benchmark per candidate. A
  strategy whose beta *varies* inside a fold is only partially cleaned by a single
  train-leg OLS beta; real-belt calibration (item 5) is what checks whether that
  matters at our scale.
- The premia rule compares against the **declared** benchmark. A strategy that
  holds gold and declares SPY is making an apples-to-oranges claim the gate cannot
  detect; the declaration must name the asset the strategy actually trades, and
  the adversary should attack any candidate whose declaration looks convenient.
- Premia power at ~39% for a thin edge means honest premia candidates will often
  be NOT RETAINED on our history. That is the instrument's resolution, not a
  verdict — same as the alpha side.
- `min_walkforward_folds` still does not scale with history (measured defect,
  registered); v5 inherits it knowingly.
