# DRAFT — replacement `why` / `falsified_by` for the `min_psr_pct` register entry

**Status: DRAFT. Nothing here is applied.** A register change is a human's act
(`app/fund/judgement.py` is control-layer), so this dispatch delivers the text
and not the diff. Written by the builder in D37, **rewritten in D38 after the
adversary read LEAN's source and the D37 text's central claim failed** — the
chair applies, amends or discards it.

**What it replaces:** the `Judgement("min_psr_pct", ...)` entry at
`app/fund/judgement.py:381-393` (the constructor call opens on 381; `why`,
`falsified_by`, `review_trigger` and `review_by` are 385-393).

---

## WHAT CHANGED BETWEEN THE D37 DRAFT AND THIS ONE, stated first

The D37 draft said the criterion applies **"not one hurdle but a different one
for every candidate"**, running from an annualised Sharpe of 1.17 to 2.26 with
a median of 1.695, and it built the whole `why` and the whole reopening path on
that. **That was wrong, and the error was ours, not the engine's.** The spread
was an artifact of the fund's own inversion. The hurdle is a CONSTANT and it is
published — in LEAN's source rather than in its statistics block, which is a
different thing from unpublished and the D37 draft conflated the two.

A draft that survived one review round and was refuted by the next is worth
saying out loud, because the refuted text was one chair action away from
entering the register as the reason a threshold exists.

## Why the entry needs replacing (the case, before the text)

The **VALUE** in the register is correct and stays at **65.0** — D37 reverted
the v4.4 draft's move to 50.0 and `judgement.review()["drifted"]` is empty on
that tree. This draft is not about the number.

It is about the `why` and the `falsified_by`, which describe a **different
statistic from the one the number guards**. Verbatim, the text on file today:

> **why:** "Nulls reached ~57% PSR on this history, so the original 50% sat
> inside the noise. The floor is measured; the 15-point margin above it is a
> judgement wearing a measurement's clothes."
>
> **falsified_by:** "Re-run the null audit on a longer history. If nulls clear
> 65%, the margin was too thin and noise has been passing. If they top out near
> 57% across many more draws, 65 is costing us real candidates for nothing."
>
> **review_trigger:** "null audit re-run on >5 years of history"

Both sentences are about **P(true Sharpe > 0)** — a luck filter, where "nulls
reach 57%" and "noise has been passing" are meaningful things to say. The
criterion `min_psr_pct` actually governs is **LEAN's published Probabilistic
Sharpe Ratio**, which is **P(true EXCESS Sharpe > an annualised 1.00)**.
Against that, "nulls clear 65%" describes nothing: a null strategy does not
clear a hurdle of an annualised Sharpe of 1.00, and re-running that audit on a
longer history would answer a question this criterion is not asking.

So the register carries a **correct number with a reason about something
else** — the register's own founding failure mode in a new costume, and the
half of the drift message (*"either the reason or the number is stale"*) that
survives after the number was restored.

## The measurement the new text rests on

**THE TARGET IS READ, NOT INFERRED.** LEAN, `Common/Statistics/
PortfolioStatistics.cs:311-312` (master, fetched 2026-08-24), verbatim:

```csharp
// deannualize a 1 sharpe ratio
var benchmarkSharpeRatio = 1.0d / Math.Sqrt(tradingDaysPerYear);
ProbabilisticSharpeRatio = Statistics.ProbabilisticSharpeRatio(
    listPerformance, benchmarkSharpeRatio, (double)riskFreeRate / tradingDaysPerYear)
        .SafeDecimalCast();
```

and `Common/Statistics/Statistics.cs:231-237`, which is what makes it an
EXCESS-return statistic:

```csharp
public static double ObservedSharpeRatio(List<double> listPerformance, double riskFreeRate = 0)
{
    var performanceAverage = listPerformance.Average() - riskFreeRate;
    ...
}
```

`tradingDaysPerYear` is **252 on 276 of 276** of this fund's stored
`-summary.json` files, and on the result payloads themselves — read from
`algorithmConfiguration.tradingDaysPerYear`. (An earlier count the same day read
273/273; the population grows with the belt and the unanimity has not moved.)
Reproduce: `json.load(f)["algorithmConfiguration"]["tradingDaysPerYear"]` over
`lean_workspace/results/**/*-summary.json`.

So the hurdle is: **an annualised Sharpe of exactly 1.00, on excess returns,
identical for every candidate.**

**AND THE FUND'S OWN ARITHMETIC CONFIRMS IT, which is the check that matters
more than the citation.** `statistics.implied_target_sharpe`, corrected to
subtract the daily risk-free rate the engine charges and to annualise on the
engine's clock, re-derives the target from each run's own series. Over every
stored belt result carrying both a PSR and an undownsampled series
(n = 336; reproduce `scratchpad/d38probe/recover.py`, one read-only `SELECT`
over `fund_lean_jobs`):

| inversion | min | median | max | within ±0.01 of 1.00 |
|---|---|---|---|---|
| as v4.4 shipped it (raw returns, candidate clock) | 1.171 | 1.696 | 2.262 | 0% |
| **corrected (excess returns, 252 clock)** | 0.786 | **0.9996** | 1.058 | **78.6%** |

The residual is the reconstruction, not the target: this module's skew and
kurtosis estimators are not byte-identical to MathNet's, and the stored series
reproduces the engine's published annual volatility to 5e-4 on 227 of 339 runs.
The risk-free rate each run was charged is recovered from the Sharpe the engine
published (`statistics.engine_risk_free_per_obs`) and reads −0.0065 / 0.0538 /
0.0713 (min / median / max, annual) — a policy-rate history, not an arithmetic
accident.

**The 1.17–2.26 "per-candidate hurdle" was `1/sqrt(252) + rf_daily/sd_daily`,
annualised on the wrong clock.** Both terms are ours.

## PROPOSED REPLACEMENT TEXT

> **why:**
> "65.0 guards LEAN's published Probabilistic Sharpe Ratio, which is a SKILL
> HURDLE and not a luck filter. The engine measures it against a HARDCODED
> target of 1/sqrt(tradingDaysPerYear) — an annualised Sharpe of exactly 1.00,
> the same for every candidate — on EXCESS returns, subtracting a daily
> risk-free rate inside the statistic
> (QuantConnect/Lean, Common/Statistics/PortfolioStatistics.cs:311-312 and
> Statistics.cs:231-237; tradingDaysPerYear is 252 on 276 of 276 of this fund's
> stored results). So the criterion reads: P(this strategy's true excess Sharpe
> > 1.00) >= 65%. The target is not published in the engine's statistics block,
> which is why the fund inverted it out of runs for two dispatches and reported
> a spurious per-candidate spread of 1.17 to 2.26; corrected for the risk-free
> rate and the clock, that inversion recovers 1.00 (median 0.9996 over 336
> stored candidates) and now exists only as a check on the constant.
> The 65.0 itself is INHERITED, not calibrated: it was set in gate v2 against a
> target-zero reading (nulls reached ~57% on the then-available history, and the
> 15-point margin above that was a judgement wearing a measurement's clothes),
> and the statistic it was set against is not the statistic it now governs. It
> is kept because the alternative was measured and found worse, not because it
> is right: gate v4.4 swept a target-zero criterion at every level from 50 to
> 99.9 and the full-gauntlet zero-skill false-pass rate did not move at any of
> them, because on a long-only equity population an absolute Sharpe is market
> beta in disguise. A flat curve cannot calibrate a level, so the ruling's own
> falsifier path was taken: keep the hurdle, correct its words. `gate._luck_leg`
> now states the target, its source clock and the excess-return basis on every
> verdict, states the Sharpe the level demands against it, and captures the
> target-zero reading beside the judged one."
>
> **falsified_by:**
> "THE HURDLE MOVES IF THE ENGINE MOVES IT, and that is now mechanical rather
> than a grep: every belt result stores
> `robustness.psr_inputs.trading_days_per_year` from its own
> `algorithmConfiguration`, and `robustness.psr_inputs.target` states the hurdle
> that follows. A LEAN image shipping a different tradingDaysPerYear, or
> changing the benchmark-Sharpe constant on PortfolioStatistics.cs:311, changes
> what 65% is asking for; `statistics.implied_target_sharpe` re-derives the
> target from stored runs and would stop landing at 1.00.
> SEPARATELY, the LEVEL reopens on either of two measurements. A zero-skill
> population on which the full-gauntlet false-pass rate MOVES with this level —
> any market-neutral or short-capable universe, where absolute Sharpe is no
> longer beta — makes the level load-bearing and it must then be re-calibrated
> rather than inherited. Or, in the other direction, a single candidate refused
> by THIS criterion alone: over all 765 stored belt results, moving the pair
> between engine@65 and target-zero@50 flips ZERO verdicts, so today the
> criterion costs nothing and proves nothing.
> NOT A REOPENING PATH ANY MORE: 'measure the engine's target with a pinned
> container'. It is measured — the target was an arithmetic question about our
> own inversion, not an empirical question about the engine, and the answer is
> in the engine's source."
>
> **review_trigger:** "a LEAN image change that moves
> `algorithmConfiguration.tradingDaysPerYear` or the PSR benchmark constant, or
> a market-neutral / short-capable candidate reaching the belt"

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
   otherwise. **It is, however, now EVALUABLE in principle** — the first half of
   the new `falsified_by` reads a stored field with a known expected value,
   which is exactly the shape `TriggerSpec` can consume when someone gets to it.
4. **The engine-target pin experiment is RETIRED, not deferred.** It was filed
   to the quant's queue at D37's resolve as the unlock for any target-zero
   level. Its question — "what target does the engine actually use" — is
   answered by five lines of the engine's own source plus a 336-candidate
   arithmetic confirmation, at zero container cost. What it would still be good
   for is a different question nobody has asked yet (does OUR reconstruction of
   the engine's skew and kurtosis agree with MathNet's on a series of known
   shape), and that is worth a ticket only if the ~4% reconstruction tail ever
   matters to a decision. It does not today: nothing reads
   `implied_target_sharpe` on a decision path any more.
