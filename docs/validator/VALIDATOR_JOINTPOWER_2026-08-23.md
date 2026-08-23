# Validator — THE JOINT GATE POWER MEASUREMENT (run-validator-jointpower), 2026-08-23
**Filed by the chair; full report with all tables verbatim in the run
record; harness `val24/` (reusable). A MODEL of the instrument driving
the SHIPPED evaluator (n=20,000 CRN-paired per cell), not a belt run —
the caveat that has been worth 8× before.**

## THE GOVERNING FINDING: the gate's most binding criterion judges an UNIDENTIFIED statistic
`min_psr_pct` reads LEAN's "Probabilistic Sharpe Ratio" verbatim
(gate.py:655 ← leanrunner.py:1536). Our own module and the criterion's
comment describe a target-0 "luck filter" — **provably wrong with no
fitting**: a positive-mean strategy scores >50% against a zero target at
any n, yet three stored candidates with positive means scored
0.5–0.9% where our module gives 91–94% on the same returns. Inverting
the shipped form: **the effective bar is annualised Sharpe ≈ 1.39–1.49**
(four candidates, two windows). A THIRD implementation with the same
name (tearsheet.py:361, target 0) is what humans read at /fund/backtest.
**Consequence: the gate's true-positive rate at Sharpe 1.0 is unknown by
15× — 24.7% (documented reading) vs 1.6% (calibrated). Zero passes in 42
candidates is a 1-in-150,000 event under the first and a COIN FLIP
(0.504) under the second. The record points hard at "the machine can
barely say yes."** One instrumented belt run identifies it (capture
LEAN's PSR inputs) — the cheapest largest-effect item on the floor.

## The headline power table (true Sharpe 1.0, shipped geometries)
| | 4f/4 ratchet | 12f/9 deep |
|---|---|---|
| TPR, documented PSR | 13.4% | 24.7% |
| TPR, calibrated PSR | 3.9% | **1.6%** |
| null FP | 0.7% / 0.04% | 0.3% / 0-in-20,000 |

**Where good strategies die**: SR≤1.0 → `must_beat_benchmark` (50–88%);
SR≥1.5 → **the single 70/30 holdout (SOLE killer of 11.6% of Sharpe-2.0
strategies that PASSED all twelve folds)** + the majority rule; under the
calibrated PSR → PSR and nothing else. **Four criteria (min_orders,
capacity, priced, capacity_measured) kill exactly ZERO in every cell.**

## Three more structural findings
1. **The vol lever: 12× pass-rate swing at FIXED skill** (2.6% at 8% vol
   → 29.7% at 25%), entirely via must_beat_benchmark. The gate prefers
   the levered mediocre edge to the unlevered good one — and no field
   records a candidate's volatility.
2. **The realistic null passes 34%**: a zero-alpha beta-1.0 index-hugger
   clears the gate a third of the time. Discrimination is 2.1–2.7
   against that null vs 19–75 against a driftless walk — **D is not a
   number without its null** (CHALLENGE filed on S4's D≥0.75; CEO).
3. **The belt cannot see before 2021-03-02** (lookback capped at 2000
   days, fund.py:1159) — 63% of META's history and everything pre-2021
   is un-examinable, not failed. start_date/end_date on bar URLs is the
   unlock.

## THE META POSITIVE CONTROL (pre-registered; the quant runs it next)
Four archetypes computed on real META bars through the shipped gate.
**DDLIMIT — the hindsight oracle (+713% vs META's +114%, Sharpe 1.37,
PSR 99.9%, cleared benchmark/costs/orders, 12-fold walk-forward RAN AND
PASSED 8-of-12) — dies on exactly ONE criterion: the single one-shot
holdout at 5% retention.** The gate's own comment says "one holdout is
one draw"; the one draw holds a veto over the twelve. CEO DECISION
FILED: should it? On the shipped default floor, the consistency test
runs for NONE of the four positive controls (3 measurable vs 4
required) — declaring lookback=2000 is a submission-format lottery.

## THE PREMIA GAP — the fork CONFIRMED, quantified
2 of 4 testable archetypes are premia-shaped (VOLSCALE: SR 0.57 on 27%
vol vs holding's 0.54 on 44% — the exact shape the constitution
protects). **gate.py contains ZERO volatility statistics** (one grep,
one comment hit); `must_beat_benchmark` is unconditional; no claim-type
field exists. **0 of 2 premia claims certifiable BY CONSTRUCTION.** The
premia sleeve has had no criterion since 2026-08-19. **The CEO's
conditional pre-approval fires: the v5 premia gate goes to build via the
kill→repair→blind loop.**

**Primary record: run `run-validator-jointpower`; STATE in
`.claude/state/validator.md`. Two CEO decisions on the desk (the
single-holdout veto; D-with-named-null). Repro commands in the record.**
