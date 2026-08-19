# VALIDATOR REVIEW — `MIN_TRAIN_RETURN_PCT` on the real belt

**Author: validator agent, 2026-08-20 (dispatch survived a mid-run host
restart; every number reproduced identically on resume). First actual execution
of the falsifier the threshold register itself specifies for this entry.
Status: FILED. CTO verification notes at the bottom — the three load-bearing
claims were checked against the shipped code and the live spine before this
doc was filed.**

**Verdict: the threshold is not the defect. The derivation behind it is wrong,
and the guard was installed in the wrong function. On the real belt the floor
has never removed a null fold and has never changed a verdict — while the
criterion it was created to fix is still unguarded today in gate v4, with a
sign-inversion hazard demonstrated by running the shipped code.**

## Method and sample

The per-fold train-leg returns the review needed do exist — not where anyone
looked. `fund_candidates.verdict.checks` stores only counts; the per-fold list
built by `WalkForward.evaluate()` is discarded at `gate.evaluate()`. But
`fund_lean_sweeps.holdout_result` carries `train.return_pct`,
`test.return_pct`, `test.total_orders` and the fold window for **every sweep
the belt ever ran**, plus `points[]` with each grid point's train return.

- **83 real belt sweeps** with a holdout window (53 walk-forward folds, 30
  single-window holdouts) across **34 candidates**: 57 null, 16 from the three
  deployed book strategies, 10 oracle. **224 individual null grid-point train
  legs.**
- Retention recomputed by importing the **live** `walkforward.retention()`,
  never reimplemented.
- Triple-sourced: LEAN's own `lean_workspace/results/*/MyAlgorithm.json`
  artifacts, the Postgres mirror, and the live REST API all agree (seed 55
  fold 4 = train +40.59% / test +19.17%; sweep `420a94db2621` = train
  +10.171% / test +140.219% in all three).

## 1. The motivating case is misstated, and neither 2.0 nor 5.0 would have caught it

`walkforward.py:56-57`, `judgement.py:313` and `docs/CALIBRATION_2026-08-17.md`
§4 all state the null trained at **+3.66%** and tested at **+50.5%**, "kept
1379% of its edge".

Candidate `e8ace8499908`, sweep `420a94db2621`, confirmed through all three
sources:

```
train.return_pct = 10.171     test.return_pct = 140.219
140.219 / 10.171 = 13.78615672008652   <- exactly the stored holdout_retention
```

**The train leg was +10.171%. The test leg was +140.219%.** The "+3.66%" was
back-solved as `50.504 / 13.786`, where 50.504 is the candidate's own
*verification-run* `return_pct` — the "return" column of that doc's table —
not the holdout test leg. The number was reverse-engineered from the wrong
numerator.

The written reason for the threshold — *"set to 2.0 first, then raised to 5.0
after noticing 2.0 did not exclude the 3.66% case that motivated it"* — is
therefore void. **A floor of 5.0 does not exclude a +10.171% train leg.
Neither does 10.0.** The threshold was raised on principle to catch an example
it never could have caught, and the example did not have the shape attributed
to it.

## 2. The floor was installed in the wrong function

The 13.79 explosion is the gate's **single-window `min_holdout_retention`**
criterion, not per-fold retention. The floor went into
`walkforward.retention()`. `gate.evaluate()` computes its own, at
**gate.py:322**:

```python
elif tr and te is not None:
    retention = te / tr if tr else None
```

Raw, unannualised, no `MIN_TRAIN_RETURN_PCT`, and `if tr` as the only
denominator guard — so a **negative** train leg passes the guard and inverts
the sign. Running the shipped `app.fund.gate.evaluate` (`GATE_VERSION = v4`,
`MIN_TRAIN_RETURN_PCT = 5.0`):

| train | test | stored `holdout_retention` | criterion |
|---|---|---|---|
| -10.0% | -8.0% | **0.80** | **PASSES** — "kept 80% of its edge" for a strategy that lost money in both legs |
| -1.0% | -50.0% | **50.0** | **PASSES** |
| +0.03% | +6.94% | **231.3** | **PASSES** (real `trend_sector_commodity` fold) |
| +10.171% | +140.219% | **13.786** | **PASSES** (the case the floor exists for) |
| -0.48% | +224.25% | -467.2 | fails (real: null seed 24, on record as `-465.26`) |

`walkforward.retention()`'s own docstring names this exact failure — *"a ratio
against a negative denominator would report a loss as a triumph"* — and guards
it. `gate.py` does not. `GATE_V5_DESIGN` kill point 6 caught that this leg
"stayed raw" on the benchmark axis; the missing denominator guard on the same
line was not caught.

**Effect on verdicts already issued: none retroactively.** Of 34 candidates, 5
recorded a negative `holdout_retention` and all 5 failed that criterion anyway;
the 3 that ever passed a gate (all v1 nulls) had train legs of +42.7%, +77.8%,
+52.7%. The hazard is **latent, not realised** — but live in v4, and it
survives into v5 unless the holdout leg is fixed alongside the fold leg.

## 3. On real folds the floor has never bound on a null, and has never changed a verdict

| population | n | measurable | **train in (0,5) — FLOOR ONLY** | train <= 0 | no orders in test | engine failure |
|---|---|---|---|---|---|---|
| all | 83 | 63 (75.9%) | **3 (3.6%)** | 2 | 5 | 10 |
| walk-forward folds only | 53 | 39 (73.6%) | **2 (3.8%)** | 1 | 4 | 7 |
| **nulls only** | 57 | 47 (82.5%) | **0 (0.0%)** | 2 | 0 | 8 |
| null walk-forward folds | 34 | 28 (82.4%) | **0 (0.0%)** | 1 | 0 | 5 |
| 3 deployed book strategies | 16 | 8 | **3** | 0 | 5 | 0 |
| oracle (v2-era geometry) | 10 | 8 | 0 | 0 | 0 | 2 |

Of 77 folds with a recorded train leg: 71 cleared 5.0%, **4 landed in
(0, 5.0)**, 2 were <= 0 (already removed by the pre-existing strict-positive
guard). **Zero of the 57 null sweeps landed in the floor's band.** Three of the
four belong to one deployed strategy, `trend_sector_commodity`.

Counterfactual, applying the v4 rule (`min_walkforward_folds=4`, strict
majority) to the real folds:

| floor | null cands | null PASS | null starved | book PASS | book starved |
|---|---|---|---|---|---|
| 0.0 (strict-positive only) | 8 | **2** | **2** | 0 | 1 |
| 2.0 | 8 | **2** | **2** | 0 | 2 |
| **5.0 (live)** | 8 | **2** | **2** | 0 | 2 |
| 10.0 | 8 | **2** | **2** | 0 | 2 |
| 20.0 | 8 | 2 | 4 | 0 | 3 |

**Not one verdict moves between 0 and 10.** The floor's entire measured effect
is one *reason* change: `trend_sector_commodity` (candidate `6f0ac252c6bf`,
gate v2) was rejected with *"only 2 fold(s) could be measured, below the 3
required — the consistency test did not run"*. At floor 0 it has 4 measurable
folds, 2 retained -> *"kept its edge in only 2 of 4 — not a majority"*. Same
rejection, strictly more informative reason. Per the fund's own mode-splitting
doctrine, the floor is currently converting a "ran and failed" into a "never
ran".

**The aggregate claim in `GATE_CALIBRATION_2026-08-18` §7 and in the register —
that this threshold is the fund's main noise filter, rejecting 89.6% of nulls
by starvation — is false on the real belt.** It rejected 0 of 57 null folds.
The belt's actual starvation is engine timeouts (10 folds; LEAN killed at the
isolator limit, `statistics: {}`, which `retention()` reports as *"a leg
produced no return figure"* — indistinguishable in the stored fold count from
a floor rejection) and no-trade test legs (5 folds, all
`mean_reversion_cyclicals`).

## 4. Retention is not unstable below 5%. It is unstable at 10-20%, and the cause is the numerator

| train-leg band | n | median retention | min | max | IQR width | >3.0 ("absurd") | retained |
|---|---|---|---|---|---|---|---|
| 0-5% | **0** | — | — | — | — | — | — |
| 5-10% | 2 | 0.004 | -0.502 | 0.510 | 0.51 | 0 | 1 |
| **10-20%** | 6 | 6.407 | -0.343 | **30.823** | **14.05** | **4** | 5 |
| 20-40% | 17 | 1.671 | -1.029 | 10.826 | 4.55 | 6 | 12 |
| 40-80% | 26 | 0.865 | -0.687 | 4.234 | 1.34 | 1 | 17 |
| >80% | 12 | 0.119 | -0.216 | 4.390 | 0.59 | 2 | 4 |

All 13 folds with retention > 3.0 have a train leg **>= 10%**. The worst —
retention **30.8** — is a null with a train leg of **+10.17%**, twice the
floor. Instability decreases monotonically in train return and the floor sits
**below** it, not at its edge.

The mechanism is the numerator. Test legs are 84-121 days (fold) or 225 days
(holdout) against a 365-day train leg; `_annualise` raises a +140% 225-day
test leg to +313%/yr. Every explosion on record is a short lucky test leg
annualised, divided by an ordinary train leg. **A train-return floor cannot
fix a numerator problem** — which is why 2.0 -> 5.0 changed nothing
measurable, and 10.0 would not either.

## 5. Why simulation and belt disagree by 8x — and what it costs the v5 tables

The floor is not applied to a draw. `leanrunner._sweep_summary` selects
`best = max(scored, key=lambda p: p["total_return_pct"])` on the **train
window**, and `_run_holdout` reports that point's return as
`train.return_pct`. **The number the floor tests is a maximum over the
surviving grid.**

| | model (`gate_power_audit.py`) | real belt |
|---|---|---|
| null train-leg distribution | 252 iid draws, mu=0, 20% annual vol | mean **+22.0%**, sd **28.3%** (n=224 points) |
| what the floor sees | one draw | **max over ~4 surviving grid points** (nominal 6) |
| share below 5.0% | ~60% | 28.6% per point -> **5.5% of maxima** |
| mean measurable folds of 4 | 1.46 (36%) | **3.38 (82.5%)** |
| null walk-forward pass rate | 2.9% (4,000 draws) | **25.0%, 2/8** (Clopper-Pearson 95% CI **8.5%-65.1%**) |

The CI excludes 2.9%. Two multiplicative model defects: a **driftless** null in
a market that rose hard (already the finding in
`BENCHMARK_BLIND_WALKFORWARD_2026-08-18`), and **no grid-max selection at
all**. Both push in the loosening direction.

This bears directly on `GATE_V5_DESIGN_2026-08-19` §"The floor on the excess
scale — measured, answer: zero". That table (`gate_v5_audit.py --floor-sweep`,
"null beta=1 / beta=2 -> 0.0% at every floor") came from the same generator
with the same two defects; its 0.0% rows bound the *model*, not the belt. And
critically: **`_sweep_summary` still picks the winner by maximum RAW train
return.** v5 judges on beta-adjusted excess but does not change what is
selected, so v5's strict-positive excess guard would be applied to a point
chosen to maximise a *different* statistic — in a rising market, systematically
the highest-beta one. v5's power and FPR tables assume no selection at all.

## 6. The reporting cannot report — confirmed against the live spine

- `GET /api/v1/fund/factory/candidates` — 34 candidates, walk-forward block is
  **counts only**: the strings `train_return_pct` / `test_return_pct` appear
  nowhere in the entire response.
- `GET /api/v1/fund/lean/sweeps` — the **list** returns 25 of 84 sweeps and
  strips `holdout_result` entirely.
- `GET /api/v1/fund/lean/sweeps/{sweep_id}` — the **detail** *does* carry
  `holdout_result.train.return_pct` and `.test.return_pct`.

So the evidence exists but is reachable only one sweep at a time, by an ID no
candidate record carries and the list endpoint mostly does not return.
Executing the register's own falsifier required going around the API to
Postgres directly. That is the reason this review read as un-executable for
two days.

## The review's answers

**For raw-scale v4, which remains in force until v5 lands — KEEP the floor,
and stop crediting it.** It costs nothing measurable (no verdict on record
turns on it), and it is the only thing standing between the fund and one
demonstrated real explosion (`trend_sector_commodity`, train +0.03% -> raw
ratio 231, annualised 1187) that a strict-positive guard would **not** catch,
because +0.03% is strictly positive. Retiring it on the raw scale would be a
quiet loosening for no gain. Three versioned corrections belong with it, none
of them a threshold move:

1. **Install the denominator discipline where the bug actually lives** —
   `gate.py:322` needs the strict-positive guard, the floor, and annualisation,
   exactly as `walkforward.retention()` has them. Today a strategy that lost
   10% in training and 8% out of sample is recorded as "kept 80% of its edge"
   and passes. Highest-value item in this review.
2. **Correct the register entry and the source comments.** The motivating case
   was train **+10.171%** / test **+140.219%**; the +3.66% never occurred.
   Strike the 2.0 -> 5.0 derivation; keep basis `judged` with an honest
   "undemonstrated" rather than a false provenance.
3. **Correct the aggregate story in `GATE_CALIBRATION_2026-08-18` §7** (new
   section, per the never-edit rule). "The fund's main noise filter" is not
   true on the belt: 0 of 57 null folds.

**For v5 — retiring the 5.0 on the excess scale is supported; a bare
strict-positive guard as sole protection is NOT yet supported.** Two
prerequisites, both measurements rather than arguments:

- Regenerate `--floor-sweep` with a null that carries **market drift** and is
  a **maximum over a grid**. Without both, the "0.0% at every floor" rows
  carry the exact model defect the belt has now falsified twice (89.6%
  predicted starvation vs 0%; 2.9% predicted FPR vs 25%).
- Re-derive `_sweep_summary`'s winner selection on the excess scale, or
  measure the cost of leaving it on raw. A guard applied to a point selected
  on a different statistic is not the guard that was measured.

If the fund wants retention *stability* rather than a denominator guard, this
data says the lever is the **test leg**: the annualisation of an 84-121-day
window, or reporting retention with an interval. Every explosion on record is
a short lucky test leg annualised. The measurement is supplied; the threshold
is the humans' versioned call.

## What this measurement does NOT cover

- **Small n, and not a fresh draw.** 83 sweeps, 34 candidates, 8 null
  candidates with a complete 4-fold set. The 25% belt null pass rate has a 95%
  CI of 8.5%-65.1% — it refutes 2.9%, it does not pin down the true rate.
- **One regime, one universe.** All folds sit in 2024-02-26 -> 2026-08-14, a
  strongly rising small-cap tape, on the 20-name band universe. The floor's
  behaviour in a falling market is unmeasured — and that is exactly where a
  train-leg floor would start to bind on real candidates.
- **Mixed gate versions.** The 83 sweeps span v1, v2 and v4 fold geometries
  (91-, 84-, 225-day test legs). Retention was recomputed with today's code;
  candidate-level verdicts quoted are the ones actually issued at the time.
- **Oracle rows are v2-era geometry.** Perfect foresight retained 0 of 5
  measurable folds (0.086-0.159). A leg passing 25% of nulls and 0% of an
  oracle is a discrimination inversion worth its own review, but the geometry
  differs and it is not asserted under v4.
- **10 folds have no result at all** (LEAN isolator kill, `statistics: {}`).
  Their train legs are unknown. Assigning all 10 adversarially to the floor's
  band still does not move the counterfactual table — those candidates are
  starved either way.
- **Nothing here measures the excess scale.** No fold on record carries a
  benchmark series, so every v5 statement above is about the *model that
  produced v5's tables*, not v5's behaviour.
- **No new belt folds were run.** All recorded history. A fresh null audit
  that captures fold-level train returns would settle the small-n problem.

## Reproduction

Read-only; no writes to the event log, no code changed. Scripts in the CTO
session scratchpad (`min_train_return_review.py` + pull/analyse/plot/
counterfact/points/final.py); `folds.json` is the 83-fold extract. The single
most load-bearing line, verifiable by hand three ways:

```bash
curl -s http://127.0.0.1:8090/api/v1/fund/lean/sweeps/420a94db2621 | grep -o '"return_pct":[0-9.]*'
# -> 10.171 / 140.219.  The "1379% case".  Not 3.66%.
```

---

## CTO verification notes (2026-08-20, before filing)

Three load-bearing claims spot-checked against primary sources; all three
CONFIRMED:

1. **gate.py:322** reads exactly `retention = te / tr if tr else None` inside
   `elif tr and te is not None:` — raw ratio, `if tr` as the only denominator
   guard. A negative train leg is truthy and passes; the sign inverts.
   Verified by reading the shipped file.
2. **walkforward.py:54-57** does state the "+3.66% / +50.5% / 1379%"
   motivating case, as the review claims.
3. **Live spine**, `GET /fund/lean/sweeps/420a94db2621`: train +10.171 /
   test +140.219. 140.219/10.171 = 13.786 (the stored retention);
   50.504/13.786 = 3.663 — the back-solve explanation holds arithmetically.
   The register's provenance contradicts the primary record.

Not independently re-run by the CTO: the 83-fold counterfactual tables, the
band analysis, and the sim-vs-belt reconciliation (methods and reproduction
path are recorded above; the triple-sourcing described was accepted after the
three spot-checks passed). Run recorded as `run-validator-floor`
(trace `trace-floor-review`) with four recommendations staged for CEO
decision.
