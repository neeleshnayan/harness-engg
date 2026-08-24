# DRAFT — replacement `why` / `falsified_by` for the `min_psr_pct` register entry

**Status: DRAFT. Nothing here is applied.** A register change is a human's act
(`app/fund/judgement.py` is control-layer), so this dispatch delivers the text
and not the diff. Written by the builder in D37, **rewritten in D38 after the
adversary read LEAN's source and the D37 text's central claim failed**, and
**rewritten again in D41 after the same reviewer showed that the D38 text
stated the hurdle in the engine's ANNUALISATION CONVENTION rather than in the
units of the series being judged** — the chair applies, amends or discards it.

**What it replaces:** the `Judgement("min_psr_pct", ...)` entry at
`app/fund/judgement.py:381-393` (the constructor call opens on 381; `why`,
`falsified_by`, `review_trigger` and `review_by` are 385-393).

---

## WHAT CHANGED IN D41 — the second correction to the same sentence

The D38 draft said the criterion reads **"P(this strategy's true excess Sharpe
> 1.00) >= 65%"**, and built the whole `why` on that 1.00.

**The 1.00 is real and it is not the hurdle a candidate faces.** It is the
engine's own restatement of its per-observation target in the engine's own
252-day annualisation convention, and it is true of every value of
`tradingDaysPerYear`: `(1/sqrt(K)) * sqrt(K) = 1.00` for every K, which is why
LEAN's source comment calls it *"deannualize a 1 sharpe ratio"*. A number that
cannot take any other value is an identity, not a measurement of this fund's
candidates.

What a candidate actually faces is that per-observation target applied to the
series LEAN was handed — and this fund's stored series are sampled once per
CALENDAR day, weekends included. **Measured on all 339 stored belt results
carrying a usable series: 365.25 observations a year on every one of them
(min = median = max), which puts the hurdle at an annualised excess Sharpe of
1.2039 on every one of them.** Stating 1.00 instead understates it by a FACTOR
of sqrt(365.25/252) = 1.2039 — in the permissive direction, in the sentence
that explains a verdict decided against the larger number.

So the correction is not a new fact about the engine. It is the same fact
stated in the units of the thing being judged, with the engine's convention
kept beside it and LABELLED as a conversion. Two drafts of this entry have now
had to be corrected for saying a true thing in the wrong units, which is worth
recording: the register is where a threshold's reason is supposed to be
checkable, and a reason on the wrong clock is not checkable.

## WHAT CHANGED BETWEEN THE D37 DRAFT AND THE D38 ONE — the first correction

The D37 draft said the criterion applies **"not one hurdle but a different one
for every candidate"**, running from an annualised Sharpe of 1.17 to 2.26 with
a median of 1.695, and it built the whole `why` and the whole reopening path on
that. **That was wrong, and the error was ours, not the engine's.** The spread
was an artifact of the fund's own inversion. The engine's TARGET is a constant
per observation and it is published — in LEAN's source rather than in its
statistics block, which is a different thing from unpublished and the D37 draft
conflated the two.

(Note the word, since D41 turns on it: the per-observation TARGET is constant.
The annualised HURDLE that constant implies is not — it depends on how often
the series being judged was sampled, which is the correction above. The D37
spread was false because it varied with the candidate's own volatility and
risk-free rate; a hurdle that varies with the candidate's SAMPLING RATE is a
different and real thing.)

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
Sharpe Ratio**, which is **P(true EXCESS Sharpe > 0.062994 per observation)** —
an annualised 1.2039 on the calendar-daily series this fund's belt produces.
Against that, "nulls clear 65%" describes nothing: a null strategy does not
clear a skill hurdle of that size, and re-running that audit on a longer
history would answer a question this criterion is not asking.

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

So the target is: **`1 / sqrt(252) = 0.062994` PER OBSERVATION, on excess
returns, identical for every candidate.** The per-observation form is the one
that needs no clock and is therefore the one this entry states first.

### THE CLOCK, which is what turns that constant into a hurdle

LEAN applies that per-observation target to whatever series it was handed. This
fund's runs hand it `listPerformance` sampled once per CALENDAR day — a run of
zeros across every weekend — so the annualisation factor is not 252.

`statistics.observations_per_year` derives the rate from each run's own dates as
`(n - 1) / (span_days / 365.25)`, where `n - 1` is the INTERVAL count. Over
**every stored belt result carrying both a series and readable dates (n = 339)**:

| quantity | min | median | max |
|---|---|---|---|
| observations per year | 365.25 | **365.25** | 365.25 |
| the same, if divided by `n` instead of `n - 1` | 365.43 | *366.25* | 368.35 |
| the hurdle on that clock (annualised excess Sharpe) | 1.2039 | **1.2039** | 1.2039 |
| what 65% demands on that clock | 1.3659 | **1.5853** | 2.0135 |

The second row is in the table on purpose. A figure of **"366.3" has been quoted
for this same population**, and it is not a different measurement — it is the
`n`-instead-of-`n-1` convention, which overstates the rate by 1/(n-1) and which
`observations_per_year`'s own docstring rejects with that reason. Printing both
means nobody has to reconstruct which convention produced which number, which
is how the two got confused in the first place.

Reproduce: `scripts/instruments/d41/clocks.py <tree> [jobs.json]`. It carries
its own NULL TEST — a synthetic series with exactly 252 observations a year
must put the hurdle at exactly 1.000000, and a business-day series reads 261.04
observations a year and a hurdle of 1.0178. Without that arm the table above
cannot distinguish "measured the clock" from "printed a constant". It also
REFUSES when the jobs dump is missing rather than printing bands over zero rows,
because an empty population and a perfectly uniform one look identical in a
min/median/max table — which is exactly what the first row of this table is.

**Min = median = max is not a coincidence and must not be read as a law about
the engine.** It is what one-observation-per-calendar-day looks like when
measured: `n - 1` equals the calendar span to the day, so the ratio is exactly
365.25 for every such run. A series sampled any other way faces a different
number, which is why `gate._luck_leg` COMPUTES this per run instead of writing
1.2039 down. A constant there would be a fact about today's belt wearing the
clothes of a fact about the engine.

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
> target of 1/sqrt(tradingDaysPerYear) = 0.062994 PER OBSERVATION, the same for
> every candidate, on EXCESS returns, subtracting a daily risk-free rate inside
> the statistic (QuantConnect/Lean, Common/Statistics/PortfolioStatistics.cs:
> 311-312 and Statistics.cs:231-237; tradingDaysPerYear is 252 on 276 of 276 of
> this fund's stored results).
> THE ANNUALISED FORM DEPENDS ON THE SERIES, NOT ON THE ENGINE, and stating it
> otherwise understated this criterion twice. LEAN applies that per-observation
> target to the series it is handed, and this fund's runs are sampled once per
> CALENDAR day: measured on all 339 stored results carrying readable dates, the
> observation rate is 365.25 a year on every one of them, so the hurdle is an
> annualised excess Sharpe of 1.2039 and what 65% demands runs 1.37 to 2.01
> (median 1.59). The engine's own 252-day convention restates the same target as
> an annualised 1.00 — that is a CONVERSION, true for every clock by
> construction ((1/sqrt(K))*sqrt(K) = 1.00), and it is not the bar any candidate
> here faced. `gate._luck_leg` states the per-observation target on every
> verdict, computes the annualised restatement from the run's OWN measured
> observation rate, carries the engine's convention beside it labelled as a
> conversion, and never puts two clocks on one payload.
> The target is not published in the engine's statistics block, which is why the
> fund inverted it out of runs for two dispatches and reported a spurious
> per-candidate spread of 1.17 to 2.26; corrected for the risk-free rate and the
> clock, that inversion recovers the per-observation constant (median 0.9996 in
> the engine's own convention, over 336 stored candidates) and now exists only
> as a check on the constant.
> The 65.0 itself is INHERITED, not calibrated: it was set in gate v2 against a
> target-zero reading (nulls reached ~57% on the then-available history, and the
> 15-point margin above that was a judgement wearing a measurement's clothes),
> and the statistic it was set against is not the statistic it now governs. It
> is kept because the alternative was measured and found worse, not because it
> is right: gate v4.4 swept a target-zero criterion at every level from 50 to
> 99.9 and the full-gauntlet zero-skill false-pass rate did not move at any of
> them, because on a long-only equity population an absolute Sharpe is market
> beta in disguise. A flat curve cannot calibrate a level, so the ruling's own
> falsifier path was taken: keep the hurdle, correct its words — which is all
> the last three revisions of this entry have done."
>
> **falsified_by:**
> "THE HURDLE MOVES IF THE ENGINE MOVES IT, and that is now mechanical rather
> than a grep — a trigger nothing evaluates is a note, and this one is
> evaluated on every suite run. Every belt result stores
> `robustness.psr_inputs.trading_days_per_year` from its own
> `algorithmConfiguration`, and `robustness.psr_inputs.target` states the hurdle
> that follows. `tests/test_lean_psr_target.py` (section M) inverts the target
> back out of THREE STORED LEAN RUNS' own bytes and requires it to land on
> `statistics.lean_psr_target()`; a LEAN image shipping a different
> tradingDaysPerYear, or changing the `1.0d` benchmark-Sharpe numerator on
> PortfolioStatistics.cs:311, breaks that agreement and fails the test by name.
> Verified by planting both mutants — and once for real, when a stray `1.1`
> numerator left in a bytecode cache was caught by exactly that test.
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
3. **The `review_trigger` above is still free text THE REGISTER does not
   evaluate, and that is not the same sentence as the `falsified_by` claim —
   read both before deciding this is a contradiction.** The engine half of the
   falsifier IS evaluated, by the test suite, on every run
   (`tests/test_lean_psr_target.py` section M, three stored LEAN runs). What
   remains unevaluated is `judgement.review()`'s own reading of the trigger
   string: nothing in `judgement.py` consumes it, so `GET /fund/judgement` will
   still not report this entry due when the condition fires. That is the known
   register-wide defect (17 of 19 entries, COO challenge #2, 2026-08-21) and
   the constitution fixes it in a stated order: make an unevaluable trigger
   render UNCHECKED first, register governance entries second. This draft does
   not jump that queue. **It does make the entry EVALUABLE in shape** — the
   first half of the new `falsified_by` reads a stored field with a known
   expected value, which is what `TriggerSpec` can consume when someone gets to
   it, and there is now a passing test to point it at.
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
