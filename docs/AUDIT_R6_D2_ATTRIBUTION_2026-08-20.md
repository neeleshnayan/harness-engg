# Validator batch — R6 thresholds, D2 cost measurement, attribution phantom

**Author: validator (batched dispatch 8b863152, 2026-08-20). Filed verbatim
by the CTO at resolve; CTO verification note at the bottom. All three items
measured on the live spine and the Postgres event log (395 rows).
Reproduction scripts in the session scratchpad, named per item.**

## ITEM 1 — R6: `min_effective_bets` and `max_risk_concentration_pct` on the sleeve-only book

Live readings (`GET /fund/risk/advanced` — DBC $251.86 / TLT $248.81, NAV
$1,884.21, 174 obs): `effective_bets` **2.47** (limit ≥ 2.0, not firing);
`avg_pairwise_correlation` **−0.4388**; `concentration_of_risk_pct` (DBC)
**102.5%** (limit ≤ 50%, FIRING — the only structural alarm).

**The two thresholds give opposite answers.**

`min_effective_bets = 2.0` **measures risk**. The premise "effective bets
sit near the 2.0 floor" was wrong by 24%: `effective_bets =
diversification_ratio²` (correlation.py:243-244), so a negatively-correlated
pair scores ABOVE its position count (naive_bets 2.00, effective 2.47). On
this book the floor is exactly "DBC/TLT correlation ≤ −0.209" (verified
numerically: eff_bets 2.001 at ρ=−0.209) — it fires when the hedge stops
hedging, with 0.23 bets of headroom. It separates the accident cleanly:
90/10 book → 1.18, 100/0 → 1.00. Known false-positive mode: a low-vol
lopsided book (10/90 reads 1.84 at LOWER portfolio vol) — the tolerable
direction. **Verdict: leave unchanged.**

`max_risk_concentration_pct = 0.50` **has inverted discrimination and no
number fixes it**: risk shares sum to 100% by Euler decomposition
(riskmetrics.py:99-152), so a 100%-single-name book reads exactly 100.00% —
LOWER than the current healthy hedged book's 102.49% — and the alarm gets
louder as the hedge improves (ρ=+0.9 → 71.7%, ρ=−0.9 → 147.1%). Healthy
books span 68–147%, accidents 100–109%: not separable by any threshold, and
the tightest passing threshold beats 90/10 by 0.31pp — less than the 1.17pp
disagreement between the two covariance estimators the same response uses.
Even a correctly risk-parity sleeve (DBC 29.5/TLT 70.5 at sample vols)
fails the 50% limit under the live instrument. **Verdict: retire or
re-specify.** A ready replacement exists, already computed and unread:
top-name `component_risk_pct` (9.78% live → 20.09% at 90/10 → 22.35% at
100/0; 4.87% at parity) — cardinality-free and hedge-monotone.

**The finding that outranks both: NEITHER threshold gates anything.**
`RiskGuard.check` (risk.py:101-176) reads only the four order-level limits;
auto-halt fires only on critical drawdown/daily_loss (riskmonitor.py:575-577);
the throttle reads absorption+turbulence. The two limits' only consumer is
`riskengine.structural_alarms` → `/fund/risk/advanced` → the UI. Zero
verdicts have ever been issued under either — any change is display
calibration until a consumer is wired. Second-order: `/fund/risk/monitor`
PUBLISHES both limits but never evaluates them, so one endpoint implies
"passing" while the other raises the alarm.

**Register defect found in passing**: `Judgement.due()` (judgement.py:131-133)
is date-only; `review_trigger` is free text no code evaluates.
`/fund/judgement` returned `due_for_review: []` while R6's own trigger
("first drawdown episode over 3% from peak") had demonstrably fired at
7.75% drawdown. Seventeen entries, sixteen triggers, zero machine-checked.
Also: `max_risk_concentration_pct` is not registered at all, and the
`min_effective_bets` entry's justification text is stale ("2.93 on 172
sessions"; today 2.47 on 174) — `drift()` compares only the constant, so a
stale justification reads clean.

## ITEM 2 — D2: per-instrument realised cost. **P1 REFUSED, structurally.**

**The paper venue produces zero cost information by construction, in our
own code**: `paper.py:116` fills at `self.quote(order).price` — the same
call `pipeline.py:215` records as `arrival_price`. All 10 paper-venue fills
have arrival == fill to the last float bit; execution slippage is
identically zero at any sample size. **All four of today's named fills
(SOFI/NVDA/XLE/SPY) were `venue="paper"` — informative sample from them:
0, not 4.**

The informative history is 8 alpaca fills (2026-08-13/14), max **2 distinct
price events per instrument** against `RELIABLE_SAMPLE = 20`. SPY: mean
+1.52bps, 95% CI ±26.5bps (contains 0, 1, 5 and 20). **TLT: zero
observations** — P1's "SPY/TLT half-spread ≈ 1bp" is unmeasurable for TLT
at any confidence. The GLD (+81.2) and INTC (−48.5) outliers are
partial-fill drift, not spread; with them the n needed for ±1bps is 4,802
fills, without them 24.

**`/fund/tca` was emitting a live wrong signal**: `reliable: true, realised
−12.59bps, "cheaper than modelled"` — but `total_bps` is decision→fill and
the four largest `delay_bps` (−165.93 XLE … +24.32 SPY) all ride ~30-minute
approval waits with `execution_bps == 0`. The −12.59 is market drift during
human latency on a venue that charges no slippage. Lowering
`DEFAULT_SLIPPAGE_BPS` on that verdict would flatter every backtest Sharpe.
*(Fixed by the CTO at resolve — see verification note.)*

**Provenance corrections**: the "ten fills" behind the 5.95bps figure are
five ETF, three mega-cap, two small/mid — "ten small-cap fills" in the API
card and MECHANISM_CYCLE1 was wrong (both corrected); drop the two
partial-fill outliers and the mean is 3.34 on eight; the "3–5× ETF
overcharge" figure has no measurement behind it in our data. D2's
substantive claim (ONE global constant, costassumption.py:33, consumed by
leanrunner and tca) stands; its argument does not.

**Refusal, stated precisely**: a per-instrument cost model cannot be derived
from Krypton's own fills — not "not yet", but not on this venue at any n.
Entry-11 money: 0.24%/yr of modelled return per 1bps of slip against a
1.0–1.8%/yr gross claim — the verdict flips inside the plausible range,
which is exactly why the constant must not move on our fills. Unblocks, in
order: (1) run entry-11 at slip ∈ {1, 3, 5}bps and disclose all three
verdicts as a band; (2) fix the tca verdict leg *(done)*; (3) published
quote/NBBO spread data as a versioned cost-model change (CEO decision).

## ITEM 3 — the phantom ±$174.47: found, and it can move real money

**Root cause, exact**: seq 76 GLD BUY 0.424471 @ 402.18 under
`e54f40af` (Trend — Sector & Commodity); seq 258 GLD SELL 0.424471 @ 100.00
under `machinery-test` (the phantom-price incident's mark). Attribution
keys on `payload["strategy_id"]` (projections/strategy.py:79), so Trend
keeps a phantom LONG and machinery-test a phantom SHORT forever — the fold
is over the whole log and nothing corrects it. machinery-test's `pnl_usd:
−132.00` reconciles to the cent. NAV and positions are unaffected (the
quantities net to zero).

**The money path is real and measured**: `RebalanceService._composition`
(rebalance.py:68-82) reads attribution. A `POST /fund/rebalance/preview`
targeting Trend at 20% returned **a $376.84 GLD BUY with `current_usd: 0.0`
and zero limit warnings** — an order into a symbol the fund holds none of,
bounded at $753.68 (40% of NAV) at the strategy cap. The chain still holds
(propose → CEO approve → pre-trade gate), but the plan the CEO would click
is wrong at the symbol level and the only on-page tell is `current_usd: 0`.

**Two structural gaps**: (a) `riskmonitor.py:511` uses `weight >
strat_limit` — a NEGATIVE strategy weight can never breach; the 40% cap is
one-sided. (b) **Archive is cosmetic**: Trend was archived today (payload
`{}`, no reason recorded) and `rebalance/preview` still accepted it as a
target. No consumer enforces the flag.

**Repair shape** (validator writes no code): a compensating event, never a
log rewrite — and the general fix is `build()`/`_composition` refusing any
strategy whose folded position disagrees with the authoritative NAV
position fold for that symbol, which catches every future mistag. Add the
archived filter and the two-sided cap in the same change.

## What these measurements do NOT cover

Covariances estimated from 174 daily obs of two ETFs (the −0.209 crossing
is a point estimate, no interval; DBC/TLT correlation has been positive in
past regimes); the accident table runs the fund's instrument code on real
bars, not the live engine's caching/coverage paths; nothing here says 2.0
is the right floor for a 5-name book; no external spread data by
construction (local-only seat); the 8 informative fills are from two days
in one regime; the $753.68 is an upper bound on one plan, not an expected
loss — the pre-trade gate was read, not run.

## GAPS (aimed at strategy generation, per the standing mandate)

1. `OrderFilled` carries no `venue` — without it every future TCA number
   silently averages real fills with tautologies. *(The tca verdict now
   joins venue from OrderSubmitted — the field on OrderFilled itself is
   still the right fix.)*
2. No `by_symbol` TCA cut — the funnel charges an ETF-scale strategy a
   small-cap-scale cost and calls the result a verdict.
3. The register's `review_trigger` is write-only — gate constants can age
   silently between v-numbers; the next loosening arrives as housekeeping.
4. `max_risk_concentration_pct` judges nothing and is registered nowhere —
   a threshold without provenance cannot be audited on schedule.
5. `StrategyArchived` has an empty payload and no consumer — retirement
   must actually retire, or the funnel's denominator and the book's target
   space disagree (the phantom order is that disagreement made concrete).
6. Two covariance estimators inside one response, unlabelled (sample-cov
   effective bets vs EWMA risk shares, 25% apart) — which one is the
   fund's answer is undecided and undocumented.
7. No cross-check between the per-strategy fold and the authoritative
   position fold — an attribution ledger that can carry a permanent
   phantom pair cannot be trusted to say a strategy stopped working.

---

## CTO verification note (2026-08-20, at resolve)

Spot-checked before acting, line by line: `paper.py:116` fills at its own
quote (exactly as claimed), `riskmonitor.py:511` is one-sided `>`,
`judgement.py:131-133` is date-only — all three verified verbatim. Acted
in the CTO lane same hour: **the `/fund/tca` verdict leg is fixed** (grades
`execution_bps` on non-paper venues only; paper-only history yields no
verdict; the −12.59bps incident is pinned by four new tests, suite green),
the API card's "ten small-cap fills" gotcha corrected, MECHANISM_CYCLE1
carries a correction section, and the revival register's entry-11 status
records P1's structural refusal with the slip-band interim route. The
threshold recommendations (retire/re-specify `max_risk_concentration_pct`,
leave `min_effective_bets`, decide controls-vs-decoration), the register
trigger defect, and the attribution/archive/two-sided-cap repairs go to
the CEO as decidable recommendations on run 8b863152 — thresholds and
money-adjacent behavior move only by CEO decision. Recorded as
run-validator-r6d2 (trace 8b863152).
