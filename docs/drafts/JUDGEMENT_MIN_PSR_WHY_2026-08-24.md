# DRAFT — replacement `why` / `falsified_by` for the `min_psr_pct` register entry

**Status: DRAFT. Nothing here is applied.** A register change is a human's act
(`app/fund/judgement.py` is control-layer), so this dispatch delivers the text
and not the diff. Written by the builder in D37; the chair applies, amends or
discards it.

**What it replaces:** the `Judgement("min_psr_pct", ...)` entry at
`app/fund/judgement.py:381-393`.

---

## Why the entry needs replacing (the case, before the text)

The **VALUE** in the register is correct and stays at **65.0** — D37 reverted
the v4.4 draft's move to 50.0 and `judgement.review()["drifted"]` is empty on
that tree. This draft is not about the number.

It is about the `why` and the `falsified_by`, which describe a **different
statistic from the one the number now guards**, and have since v4.4 made that
explicit. Verbatim, the text on file today:

> **why:** "Nulls reached ~57% PSR on this history, so the original 50% sat
> inside the noise. The floor is measured; the 15-point margin above it is a
> judgement wearing a measurement's clothes."
>
> **falsified_by:** "Re-run the null audit on a longer history. If nulls clear
> 65%, the margin was too thin and noise has been passing. If they top out near
> 57% across many more draws, 65 is costing us real candidates for nothing."

Both sentences are about **P(true Sharpe > 0)** — a luck filter, where "nulls
reach 57%" and "noise has been passing" are meaningful things to say. The
criterion `min_psr_pct` actually governs is **LEAN's published Probabilistic
Sharpe Ratio**, whose target is neither zero nor published, and which v4.4
identified as a **skill hurdle** by inverting it per candidate. Against a skill
hurdle the phrase "nulls clear 65%" does not describe anything: a null strategy
does not clear a hurdle of an annualised Sharpe near 1.7, and re-running that
audit on longer history would answer a question this criterion is not asking.

So the register currently carries a **correct number with a reason about
something else** — which is the register's own founding failure mode in a new
costume, and it is the half of the drift message (*"either the reason or the
number is stale"*) that survives after the number was restored.

## The measurement the new text rests on

Method: `app/fund/statistics.py::implied_target_sharpe` — the engine's own
published PSR inverted on each run's own return series — over **every stored
belt result the fund holds**. Reproduction:
`scratchpad/d37probe/target_census.py` and `target_annualised.py`, one
read-only `SELECT` over `fund_lean_jobs` each.

| population step | n |
|---|---|
| stored results with a result payload | 765 |
| …carrying a `psr_pct` | 765 |
| …also carrying an undownsampled daily series (n ≥ 2) | 339 |
| …whose PSR is invertible (3 publish exactly 0.0%, which pins the target at infinity) | **336** |
| …of those, clocked by their own dates | 336 (0 unclocked) |

**Implied engine target, annualised on each candidate's own clock, n = 336:**

| min | p05 | p25 | median | p75 | p95 | max |
|---|---|---|---|---|---|---|
| 1.171 | 1.260 | 1.478 | **1.695** | 1.808 | 2.026 | 2.262 |

Per observation the same population reads min 0.0613 / median **0.0887** / max
0.1184. The four positive controls the v4.4 calibration was built on
(1.34, 1.43, 1.49, 1.51 annualised; 0.0700–0.0792 per observation) sit at the
**17.9th to 28.6th percentile** — the population's bottom quartile — and
**71.4% of stored candidates imply a target at or above the range that
calibration swept**.

## PROPOSED REPLACEMENT TEXT

> **why:**
> "65.0 guards LEAN's published Probabilistic Sharpe Ratio, which is a SKILL
> HURDLE and not a luck filter: its target is not zero and the engine does not
> publish it. Inverted per candidate over the 336 stored results that carry both
> a PSR and an undownsampled series
> (`statistics.implied_target_sharpe`), the target this criterion is really
> applying runs from an annualised Sharpe of 1.17 to 2.26, median 1.695 — it is
> not one hurdle but a different one for every candidate, moving with each run's
> own sample size and shape. The 65.0 itself is INHERITED, not calibrated: it
> was set in gate v2 against a target-zero reading (nulls reached ~57% on the
> then-available history, and the 15-point margin above that was a judgement
> wearing a measurement's clothes), and the statistic it was set against is not
> the statistic it now governs. It is kept because the alternative was measured
> and found worse, not because it is right: gate v4.4 swept a target-zero
> criterion at every level from 50 to 99.9 and the full-gauntlet zero-skill
> false-pass rate did not move at any of them, because on a long-only equity
> population an absolute Sharpe is market beta in disguise. A flat curve cannot
> calibrate a level, so the ruling's own falsifier path was taken: keep the
> hurdle, correct its words. `gate._luck_leg` now states the inverted target and
> the Sharpe the level demands against it on every verdict, and captures the
> target-zero reading beside the judged one."
>
> **falsified_by:**
> "The engine-target pin experiment — one LEAN container over a synthetic series
> of KNOWN Sharpe, reading the engine's target directly instead of inverting it
> out of runs. If it produces a measured target that supports a calibrated
> target-zero level, the level question REOPENS and this pair should move to
> that statistic at a level chosen on the measurement rather than on a tie-break.
> Failing that: a zero-skill population on which the full-gauntlet false-pass
> rate MOVES with this level — any market-neutral or short-capable universe,
> where absolute Sharpe is no longer beta — makes the level load-bearing and it
> must then be re-calibrated rather than inherited. Or, in the other direction,
> a single candidate refused by THIS criterion alone: over all 765 stored belt
> results, moving the pair between engine@65 and target-zero@50 flips ZERO
> verdicts, so today the criterion costs nothing and proves nothing."
>
> **review_trigger:** "the engine-target pin experiment reports, or a
> market-neutral / short-capable candidate reaches the belt"

## Notes for whoever applies this

1. **`registered_value` stays 65.0** and `expected=65.0` is unchanged. This is
   not a threshold change and must not be staged as one.
2. **`review_by` 2026-12-01 is inherited and this draft does not move it.** It
   was set for the null-audit re-run, which the new `falsified_by` retires. A
   date kept for a trigger that no longer exists is the kind of thing this
   register was built to stop, so it wants a decision — not a silent carry.
3. **The `review_trigger` above is still free text no code evaluates.** That is
   the known register-wide defect (17 of 19 entries, COO challenge #2,
   2026-08-21) and the constitution fixes it in a stated order: make an
   unevaluable trigger render UNCHECKED first, register governance entries
   second. This draft does not jump that queue; it just does not pretend
   otherwise.
