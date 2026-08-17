# Cross-sectional momentum in the capacity band

**Date:** 2026-08-17, before the open
**Verdict: DO NOT DEPLOY** — it fails the gate.

It beats holding the same names in-sample (+21.7% vs +10.9% on 2025) and then
keeps only **33%** of that edge out of sample, trailing the no-opinion bar by ~30
points over 2026. Probabilistic Sharpe 41.9% against a 50% floor: not
distinguishable from luck. Textbook overfitting, caught by the holdout — which is
the harness working, not the harness failing.

This is a negative result, written up as carefully as a positive one would be.
The point of the harness is that a candidate can be killed in an afternoon with
evidence, rather than argued about.

---

## Why this shape was tried

Every candidate this fund has tested so far was a long-only **timing** rule on a
single name, and every one failed the gate on the same criterion: *an expensive
way to hold the underlying*. That is structural, not bad luck. A rule that sits
in cash part of the time cannot beat holding an asset that drifts up, so the
whole family fails and the gate is right to reject it.

**Selection** is a different shape. Holding the strongest few of a basket *can*
beat holding the whole basket, because the comparison stops being "in the market
versus out of it" and becomes "these names versus those names". It also fits a
$2k fund: the edge is meant to come from looking at names nobody large can act
on, which is what the capacity-filtered hunting ground measures.

So: rank a small universe by trailing return, hold the top few, always fully
invested, rebalance on a fixed clock.

## How the universe was chosen

By **rule**, not by eye — the rule matters more than the names. I could see how
these names traded, so picking favourites by hand would be look-ahead bias
committed by the analyst rather than by the code, and it would not show up in
any holdout, because a holdout only ever tests the rule and never the person who
chose its inputs.

> The 20 highest-ADV **operating companies** inside the $2M–$25M ADV capacity
> band, SIC-filtered to drop funds/trusts/shells, each with ≥400 daily bars.

Reproduce with `scripts/build_xs_universe.py`. The band holds **2,363** names;
12 of the top candidates were rejected as ETFs, 0 as funds by SIC.

Result — 20 names across deliberately unrelated industries, so the test is
selection and not a disguised sector bet: ALKT, CON, ATRC, SOBO, ADMA, CLOV,
BLZE, ZIM, GHM, NBR, GCT, DEI, PRVA, KOPN, AVPT, LINC, CRAI, ANIP, NTCT, TRN
(software, outpatient care, surgical instruments, pipelines, biologics, health
plans, shipping, industrial machinery, drilling, mail-order retail, a REIT,
health services, semiconductors, education, legal services, pharma, systems
integration, railroad equipment).

**Not driven by filings.** Of the 20, only ALKT appears in the observation
corpus (4 observations). The corpus covers 84 tickers, a different slice of the
market. This candidate rests on measured capacity and structural reasoning, and
saying otherwise would be dressing it up.

## The bar it had to clear

A benchmark of "the name it traded most" is the wrong question for a selection
rule — see *Harness fixes* below. The honest counterfactual is the **whole
universe held without opinion**: same feed, same costs, same window, the only
difference being the absence of a decision. That is `xs_universe_control`.

## Results

Costs: 5bps slippage (the fund's single cost assumption), zero commission
(Alpaca genuinely charges none). Both legs use the same feed, costs and window;
the only difference is the presence of a decision.

**A correction, recorded because it changed the conclusion's reasoning.** My
first read of this was that the strategy lost to equal-weight in-sample too.
That was an artifact: on a window starting 2024-03-01 there are only **4 bars of
history before the start**, so the algorithm spent its first ~180 sessions in
cash filling its lookback window while the control was fully invested from day
one. Warm-up cannot fix that — the data itself does not go back far enough. The
comparison below therefore runs on **2025**, where ~210 prior bars exist and both
legs are invested from the first day.

### In-sample, 2025 (parameters chosen on data including this window)

| | Return | Sharpe | PSR | Max DD |
|---|---|---|---|---|
| Strategy (180/5/63) | **+21.7%** | 0.56 | 26.9% | 17.4% |
| Hold all 20, equally weighted | +10.9% | 0.21 | 16.4% | 21.1% |
| *(harness bar: equal-weight basket)* | *+14.8%* | | | |

In-sample the selection **does** beat holding everything — by ~11 points, with a
smaller drawdown and a better Sharpe. That is the result the idea was hoping for.

### Out-of-sample, 2026-01-01 → 2026-08-14 (both warmed up)

| | Return | Sharpe | PSR | Max DD |
|---|---|---|---|---|
| Strategy, same parameters | +7.1% | 0.23 | 22.8% | 17.5% |
| Hold all 20, equally weighted | **+37.0%** | 2.35 | 80.7% | 8.6% |

It kept **33%** of its edge out of sample against a 50% floor, and trailed the
no-opinion bar by ~30 points. This is the textbook overfitting signature: good on
the window the parameters were chosen on, gone on the next one. The holdout is
doing precisely the job it exists to do, and the in-sample win above is exactly
the number that would have been believed without it.

### The grid: island, not plateau

24 combinations of lookback × top_n × hold_days. Best +21.7%, **median +3.6%**,
worst −38.4%, and only 62% profitable at all. Best-minus-median is 18 points —
the good cell has losing neighbours, which is the shape of a fit to history
rather than an effect. Note also that this grid is *not* a clean comparison
across lookbacks, for the warm-up reason above: a 60-day lookback began trading
months earlier than a 250-day one, so the cells measure different periods.

### Formal gate verdict: **FAILED**

Two substantive failures, on gate v1:

- probabilistic Sharpe 41.9% is below the 50% floor — the edge is not
  distinguishable from luck on this much history;
- no held-out test on the re-judged sweep (see below).

It *passes* the criteria it can: costs are modelled, capacity is $13.3M (ample
for $2k), and it is **still profitable at 50bps of slippage** — tested 5 to 50bps
without crossing zero, so it is not a rounding error with good marketing. The
edge is robust to cost assumptions; it simply is not reliably there.

*The re-judged sweep's holdout leg died with `WinError 1455: the paging file is
too small` — LEAN containers exhausted this machine's 15.2GB. The gate refused to
score it rather than treating a crash as a 0%, which is correct. The 33%
retention above comes from the earlier full-grid holdout, which completed.*

### What this does *not* say

The control's +37% is **not** a strategy recommendation. It is contaminated by the
bias stated in the algorithm's own docstring: the capacity band is measured
*today*, so all 20 names survived to today and anything delisted over the window
is absent. That flatters a hold-everything rule *more* than a selective one, so
the true gap is smaller than 30 points — it runs with the conclusion, not against
it. One eight-month window of small-cap beta is not evidence of anything.

**This is now fixable.** Polygon/Massive's `active=false` reference endpoint
serves delisted tickers with a `delisted_utc` stamp, so the survivorship bias can
be *priced* rather than merely disclosed. See `app/fund/polygon.py`.

## Harness fixes this exposed

Four defects, each of which would have quietly mis-scored a candidate — three
flattering, one condemning. All have regression tests.

1. **A benchmark of zeros was believed.** LEAN emits a full-length benchmark
   curve of `0.0` for custom data types, and that list is truthy — so the guard
   `if result.get("benchmark_curve")` accepted it and the fund would have been
   measured against a **0% bar that every profitable strategy clears**. It also
   zero-*pads* real price series before the subscription starts, and a return
   computed off a zero base is not a number. Now the engine's series is trusted
   only if it is strictly positive throughout.

2. **A multi-name strategy was judged against one constituent.** The benchmark
   picked `max(set(symbols), key=symbols.count)` — the most-traded name. For a
   selection rule that is close to meaningless: it flatters a rule that dodged
   the worst name and punishes one that held the best. Now a multi-name strategy
   is measured against the equal-weight basket of the **universe it declared**
   (read statically from a module-level `UNIVERSE`), not the subset it happened
   to buy — those answer different questions, and the traded-subset version lets
   a rule be graded on a curve it drew itself. A bar missing most of its legs is
   refused outright rather than reported as thin.
   *This changed an existing test's contract, deliberately.*

3. **The gate's verdict was timing-dependent.** A job's `state` flipped to
   `done` *before* enrichment ran, so a caller that polled for completion and
   judged immediately saw a half-built result — and the gate failed this
   candidate for "not priced" and "no benchmark to compare against" when the run
   genuinely had `slippage_modelled: true` and a benchmark of +60.9%. Missing
   evidence must fail, but only when it is actually missing; a verdict that
   depends on who polled first is not a verdict. `state` is now published last.

4. **The holdout silently starved long-lookback strategies.** The test window
   starts the algorithm cold, so a 180-day lookback cannot fill its window
   inside a 155-day test run: it placed **zero orders** and scored a flat 0%,
   which the gate reported as *"kept only 0% of its edge out of sample"*. That
   sentence is false and it would fail a genuinely good strategy while sounding
   like evidence. The gate now separates *lost its edge* from *never traded*,
   and the algorithm reserves warm-up. **This likely explains the earlier
   Mean-Reversion/INTC verdict (2 fills, "kept 0% OOS") — that candidate may
   never have been examined at all.** Worth re-running before trusting it.

Warm-up fixed the holdout (0 orders → 10) but **could not** fix the in-sample
grid, because only 4 bars precede 2024-03-01 — there is nothing to warm up
*from*. That is a data-coverage limit, not a code bug, and it is why the results
above were re-run on 2025 instead. Polygon's free tier is also ~2 years, so
deeper history needs a paid tier or a different source.

## What I would try next

The failure is informative. Trailing return is a *momentum* signal, and in a
universe of 20 small caps over this window it selected badly — plausibly because
at this size single-name idiosyncratic risk swamps any cross-sectional signal,
and 5 names is not enough diversification to average it out (17% drawdowns on a
fully-invested book say the same thing).

Directions, in the order I would take them:

1. **Price the survivorship bias first.** Now possible via delisted-ticker
   reference data, and it conditions everything else — if the control's edge is
   mostly survivors, the bar this had to clear was never real.
2. **Reversal rather than continuation.** Small caps are where mean-reversion
   usually lives; the sweep's worst cells were the shortest lookbacks, which is
   weak evidence in that direction.
3. **A signal that is not price.** The filings corpus already has 376
   observations across 84 tickers — margin, dilution, customer concentration.
   That is the fund's actual differentiator, and the overlap problem is fixable
   by pointing the next filings sweep *at the capacity band* instead of at
   whatever came next alphabetically.
4. **More names, smaller weights.** 5 of 20 concentrates idiosyncratic risk.

## Reproduce

```bash
python scripts/build_xs_universe.py     # regenerate the universe from the band
```

Algorithms: `lean_workspace/algorithms/xs_momentum_smallcap/`,
`lean_workspace/algorithms/xs_universe_control/`.
