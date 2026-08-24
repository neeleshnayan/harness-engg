# ENTRY 20 — THE FIRST PREMIA PASS

**Candidate `a9db39fdfab5` · `announcement_premium` · claim_type `premia` · gate `v5r3-premia` · PASSED, zero failures**
**Belt run 2026-08-23 19:26Z → 23:58Z (4h32m) · resolved by the chair 2026-08-24 · verdict row in `fund_candidates`, preserved by design**

> The gate's own sentence, quoted exactly because it is precisely bounded:
> *"clears every criterion — worth a human look, which is a different claim from 'deploy it'."*

This is the first full premia-gate pass in the firm's history, and the first
pass of any kind under the excess-returns machinery (D23 + D29 + D32) that
the adversary spent three kill rounds hardening. Every number below is read
from the candidate's own stored verdict; nothing is recomputed here.

---

## 1 · What the claim is

**Premia** (constitution, 2026-08-19, amended 2026-08-21): *better
risk-adjusted return than holding the asset*, judged over **excess returns**
— both legs net of the realised risk-free series, so T-bill carry cannot
impersonate edge. A premia claim does **not** need to beat buy-and-hold and
must not be judged as if it should. (This one happens to anyway — see §2.)

Entry 20 was ruled a premia claim by the CEO on 2026-08-23 ("Yes as premia
makes sense"), with the reopening falsifier recorded: Ed's authoritative
vol-ratio computation reading ≥ 1.0 reopens the ruling. It reads 0.962.

## 2 · The headline numbers

| | Strategy | Benchmark (recomputed basket) |
|---|---|---|
| **Excess Sharpe** (net of realised BIL) | **1.956** | 1.085 |
| Raw Sharpe | 2.262 | 1.286 |
| Annualised volatility | **14.02%** | 21.36% |
| Max drawdown | **15.31%** | 23.88% |
| Total return (window) | 111.45% | 84.78% |

| Criterion | Required | Measured |
|---|---|---|
| Sharpe advantage (excess basis) | > 0.0 | **+0.871** |
| Gross exposure (engine chart, 908 obs) | ≤ 1.0, fail-closed | **0.9987** (max, 2025-04-24) |
| Drawdown not worse than the asset | true | **true** |
| Window coverage (session basis) | majority | **97.9%** (611 of 624 sessions) |
| PSR | ≥ 65% | **77.75%** |
| Walkforward folds retained | ≥ 50% of measurable | **8 of 9 (88.9%)**, median retention 0.94 |
| Holdout retention (annualised) | ≥ 0.5 | **1.34** |
| Orders (priced) | ≥ 20 | **7,001** |
| Capacity | ≥ $100k | **$20.5M** |
| Breakeven cost | ≥ 10 bps measured | **beyond the tested range** (> 10 bps — a floor read; see caveat 4) |

**The excess conversion did its job and the candidate cleared anyway**: the
raw advantage is 0.976; netting realised BIL (4.363%/yr over the window,
611 observations, fetched live — the cash leg is never snapshot-pinned)
costs the strategy's cash-holding leg ~0.105 of advantage, and +0.871
remains. The rf-breakeven is **48.85%/yr** — the premium would survive a
cash rate ten times today's before vanishing into carry.

## 3 · The walkforward, fold by fold

12 folds planned, 9 measurable, 8 retained. Three folds were **refused**
rather than fabricated — the harness declines to divide by a negative or
undersized train leg, so a loss can never report as a triumph:

| Fold | Test end | Retention | Note |
|---|---|---|---|
| 1 | 2022-12-29 | — | refused: train leg −4.81%, no edge to retain |
| 2 | 2023-04-29 | — | refused: train leg −8.15% |
| 3 | 2023-08-28 | — | refused: train leg +3.16%, under the 5.0% measurability floor |
| 4 | 2023-12-27 | 0.94 | |
| 5 | 2024-04-26 | 0.82 | |
| 6 | 2024-08-25 | 1.05 | |
| 7 | 2024-12-24 | 2.48 | |
| 8 | 2025-04-24 | **−0.54** | the one miss — the edge inverted in the test leg |
| 9 | 2025-08-23 | 6.27 | |
| 10 | 2025-12-22 | 0.54 | |
| 11 | 2026-04-22 | 3.74 | |
| 12 | 2026-08-21 | 0.90 | |

Grid: slip ∈ {1, 3, 5, 10} bps; the winner is **3 bps slip**. Required
folds were scaled to the covered window (9 required for 1,818 covered
days); the history floor deepened to the data path's own reach (2021-03-02,
zero folds lost to it).

## 4 · The gauntlet this pass survived — why it is worth more than the passes before it

1. Entry 20's earlier v4.1 pass (`144387901688`) was **revoked** by gate
   v4.2 the same day it happened, on a breakeven read the criterion could
   not support. That row is preserved; a re-judge is a new row.
2. The premia **label** was killed by the adversary; the CEO re-ruled it
   premia with a falsifier attached (vol-ratio ≥ 1.0 reopens; reads 0.962).
3. Gate v5r1-premia was **killed** (a 4.0% rf constant where a realised
   series belonged). v5r2 fixed it and was **killed again** (unfinanced
   leverage: a zero-skill 1.25× cash book collected free Sharpe;
   plus a union denominator). v5r3 closed both — exposure read from the
   engine's own chart, refuse-if-absent, ceiling 1.0 fail-closed — and
   **survived the re-blind**. That is the gate this run was judged by.
4. The run itself was submitted **snapshot-off** (`FUND_BAR_SNAPSHOT=0`)
   after the A/B that pinned the container-hang pathology on the snapshot
   layer; zero timeouts on live fetches.

## 5 · THE FIVE CAVEATS — filed beside the pass, kill-direction annotated

1. **Survivor-only universe (direction UNKNOWN — the honest one).**
   `benchmark_population`: 170 names as of 2024-02-26,
   `point_in_time: false`, `survivorship_corrected: false`. Both legs draw
   from the same survivor universe, but the strategy also *selected* from
   it. The PIT membership corpus (fja05680/sp500 + the 124-name delisted
   Tiingo panel, 564,609 bars) exists to re-run this honestly; until then
   the pass is fenced to its stated population.
2. **Cash-carry understatement (CONSERVATIVE).** The engine pays 0% on
   idle cash while the gate subtracts realised BIL from both legs, so a
   cash-holding strategy leg is *understated* by (1−w̄)·rf/σ. The pass
   happened despite this bias, not because of it. D36 is building the
   credit with its paired margin machinery; any re-judge creates a new
   row, never amends this one.
3. **PSR construction (CONSERVATIVE).** 77.75% was cleared under the
   current construction, whose implied target is ~1.34 Sharpe — harsher
   than the documented target-0 meaning. D36 restores target-0 with a
   calibrated level; both values will be captured going forward.
4. **Cost realism — THE ONE THAT BINDS.** Breakeven reads "beyond the
   tested range": a floor of >10 bps against a flat 5 bps/side assumption
   with 3 bps winner slip. The retro quote instrument, live since this
   morning, measures **real** effective spreads at 1–4 bps median on
   liquid names but **38–308 bps mean on small names** (SOFI, INTC).
   7,001 orders across a 170-name universe must be checked against
   per-name measured spreads before any sizing conversation. This is the
   caveat that gates deployment arithmetic.
5. **Null-distance (CONSERVATIVE, stated for scale).** The adversary's
   zero-skill artifacts on the advantage statistic measure ~0.01, with a
   ±0.05 measured noise band. +0.871 sits roughly **17× outside the
   band** — far beyond the reach of every null measured to date.

## 6 · What this is, and what it is not

**It is**: the first candidate to clear every criterion of the hardened
premia gate, on excess returns, inside the exposure ceiling, with an honest
walkforward — the thing this firm was built to produce a truthful verdict
about.

**It is not**: a deployment. The gate's sentence draws the line itself. The
human look is the CEO's (desk item **E20-1**). If the look leads toward an
experimental deployment, that path is unchanged and versioned: explicit
learning goal written down, alpaca venue, exit rules committed before
entry, notional capped, the CEO's click per deploy — and caveat 4 is the
input to any sizing.

---

*Filed by the CTO chair 2026-08-24. Sources: `GET
/fund/factory/candidates/a9db39fdfab5` (verdict, checks, walkforward,
analytics), `fund_candidates` row, `docs/reviews/ADVERSARY_*` for the gate
lineage, `run-cto-entry20-premia-resolve` for the resolution record. Per
the non-negotiables this document is never edited — a re-measurement gets
a new section or a new file.*
