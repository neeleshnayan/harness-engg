# Calibrating the instruments

**Date:** 2026-08-17
**Headline: gate v1 passed random noise half the time.** Six strategies with no
information in them went down the belt; three cleared the bar. The gate has been
raised to **v2**, with the reasons below and a regression test per leak.

This is the most important negative result the fund has produced, because it is
not about a strategy. It is about the instrument every strategy was measured
with — and therefore about every verdict the fund has issued to date.

---

## Why this was run

The gate had failed every candidate it ever judged: five candidates, zero
passes. Read one way that is rigour. Read another it is a bar nothing could clear
on two years of daily data, and **nobody could tell those apart**. "The gate
works" was an assumption sitting underneath every result.

A null audit settles it from one side. A random-entry strategy has no edge by
construction, so it must fail; any that passes is a leak. The audit gave each
null exactly what a real candidate gets — the same universe, costs, clock,
holdout, and crucially the same **grid selection**, because picking the best of
four settings on one window is where an overfit is born and a calibration that
skipped it would be testing a gentler process than the one in use.

## What happened

`null_random_smallcap` — pick N of the 20 band names at random on the rebalance
clock, fully invested, same 5bps slippage. Six seeds, each swept over
top_n × hold_days, trained on 2025, tested on 2026 YTD.

| null | verdict | PSR | return | benchmark | retention |
|---|---|---|---|---|---|
| `0df7f8fe` | **PASSED** | 56.7% | +123.2% | +60.9% | 1.21 |
| `e8ace849` | failed | 28.3% | +50.5% | +60.9% | 13.79 |
| `ccea18c6` | failed | 39.1% | +61.2% | +60.9% | 0.33 |
| `46ead7e4` | **PASSED** | 92.1% | +247.0% | +60.9% | 0.54 |
| `293d04f2` | **PASSED** | 60.8% | +118.9% | +60.9% | 1.08 |
| `1a8afa7a` | failed | 56.4% | +99.0% | +60.9% | 0.41 |

**False positive rate: 3 of 6 = 50%.** A coin flip. One null returned +247% with
a probabilistic Sharpe of 92.1%.

Null PSR ranged **28.3% to 92.1%**, and **four of six cleared the 50% floor**.
For comparison, the real cross-sectional momentum candidate scored 26.9% — worse
than most of the noise.

## Why it happened — four distinct defects

**1. Two criteria passed when unmeasured.** Written as
`if be_bps is not None and be_bps < floor`, so a candidate that was never
cost-swept *satisfied* the cost-robustness bar by never being tested against it.
The same shape guarded capacity. In a gate whose stated doctrine is that missing
evidence fails, the doctrine was inverted in two places — and the passing null
used both.

**2. A 50% PSR floor does not separate noise at this sample length.** It was set
as "more likely real than not", which is a reasonable sentence about a
distribution and a poor threshold on 250 daily observations of a high-dispersion
basket. The nulls' own distribution shows the floor sitting inside the noise it
was meant to exclude.

**3. Beating the benchmark once is close to a coin flip.** A concentrated random
draw (3 of 20) from a basket with this much dispersion clears a 20-name
equal-weight bar about half the time. v1 had a notion of *ordering* and none of
*significance*.

**4. Retention explodes on a small denominator.** Null `e8ace849` trained at
+3.66% and tested at +50.5%, reporting that it "kept **1379%** of its edge" —
sailing through a criterion that asks for 50%. A ratio needs a denominator big
enough to divide by. v1 already refused negative training returns; near-zero ones
are the same failure with a friendlier face.

## Gate v2

The fix is deliberately **not** "raise the number". Luck scales with dispersion,
so a threshold race against it cannot be won. What noise cannot fake is
**consistency across independent windows**.

- `require_breakeven_measured` / `require_capacity_measured` — **new**. Absent
  evidence fails, restoring the gate's own rule. "Still profitable at every cost
  tested" is treated as the real answer it is, not as missing.
- `min_psr_pct` **50% → 65%**. A floor, no longer the load-bearing test.
- `require_walkforward`, `min_walkforward_folds: 3`,
  `min_walkforward_folds_retained_share: 0.5` — **new, and the actual test**. A
  candidate must keep its edge in a majority of at least three independent folds.
- Retention now refuses a training return under **5%** as an unusable
  denominator. That threshold is a *judgement*, labelled as one: below it an
  "edge" sits under the equal-weight benchmark (+14.8% in 2025) and inside
  single-name noise. It is not fitted to the audit — picking a number just large
  enough to catch one example would be fitting the instrument to its first
  reading.

`CRITERIA_V1` is retained in full, including the three `require_*` flags set to
`False`, so an old verdict stays interpretable. `evaluate()` merges a supplied
criteria dict over current defaults, so a version that merely *omitted* the new
keys would inherit v2's demands and make re-judging impossible — a version has to
be a complete description of its bar, including what it did not ask for.

**The belt was changed with it.** Gate v2 asks for walk-forward evidence, so
`CandidateFactory` now produces it — one grid per fold. Shipping the criterion
without the evidence would have made the gate unclearable, which is the same
pathology as passing noise arrived at from the other side, and it would have
looked like rigour.

## What this does not establish

The audit bounds the gate from **one side only**. It shows v1 was leaky; it
cannot show v2 is clearable. A floor no real edge could pass would also reject
every null, and the two are indistinguishable from failures alone.

`oracle_calibration_only` exists for the other side — a strategy with a tunable,
known amount of foresight, to find the minimum true edge the gate can detect. It
is written and **not yet run**. Until it is, v2's thresholds are defensible but
uncalibrated from above, and that is the next thing to do.

## Consequences for what we already believed

- **The five prior "FAILED" verdicts are weaker evidence than they read as.** A
  gate that passes noise half the time is not the reason those candidates died;
  the specific sentences still stand on their own, but "it failed the gate" is no
  longer a strong claim by itself.
- **Nothing was deployed on a false positive.** All three passing nulls are
  calibration instruments, and the digest now excludes them from the approval
  queue by name — a null that clears the bar is a finding about the gate, and it
  briefly appeared on the page asking a human to review it as an opportunity.
- **The cross-sectional momentum verdict survives.** It failed on PSR 26.9% and
  negative out-of-sample retention, neither of which the leaks touch. It would
  also fail v2.

## Reproduce

```bash
python scripts/null_audit.py 1,2,3,4,5,6
```

Verdicts persist in `fund_candidates`; the audit is re-derivable from Postgres
without re-running the engine.
