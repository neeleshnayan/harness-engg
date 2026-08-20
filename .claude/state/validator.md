# validator — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded
- Instruments under watch: gate v4 (benchmark-blind, v5 pending round 3);
  min_walkforward_folds non-scaling defect (FPR rises to ~12% at 5y history —
  blocking review before any data purchase); MIN_TRAIN_RETURN_PCT load-bearing
  beyond stated job (review BEFORE v5); sieve signal-path never compared against
  LEAN (prescreen trusted to reject only).
- Measurement debts: real-belt null audit under v5 once it lands (model != run);
  29 clean nulls needed to bound FPR under 10%.

## 2026-08-20 — MIN_TRAIN_RETURN_PCT blocking review COMPLETE (real belt; first execution of the register's own falsifier). Re-verified after a mid-dispatch host restart: every number reproduced identically.

- FOUND THE DATA SOURCE nobody was using: fund_lean_sweeps.holdout_result in the local Postgres
  mirror (krypton-pg :5433) carries per-fold train/test return_pct + fold window for every belt
  sweep ever run (84 rows, 83 with a holdout). Use it for ANY future fold-level question.
  Sweep rows carry NO candidate_id — link by (algorithm, holdout window, submitted_at).
  Triple-source any headline number: LEAN artifacts in lean_workspace/results/*/MyAlgorithm.json
  (algorithmConfiguration.parameters has seed/start/end), Postgres, and the live API all agree.
- API REPORTING GAP, verified live on :8090, not inferred from source:
  /api/v1/fund/factory/candidates  -> walkforward block is COUNTS ONLY; the strings
    'train_return_pct'/'test_return_pct' appear nowhere in the whole response.
  /api/v1/fund/lean/sweeps         -> lists only 25 of 84 and STRIPS holdout_result.
  /api/v1/fund/lean/sweeps/{id}    -> DOES carry holdout_result.train/test.return_pct.
  So the evidence is reachable one sweep at a time by an ID nothing else exposes. That is why
  this review read as un-executable for two days. Fixing the list endpoint would turn the next
  fold-level review into a query.
- Four findings, in order of money at risk:
  1. gate.py:322 computes holdout_retention = te/tr RAW, guarded only by `if tr` — no floor, no
     annualisation, and a NEGATIVE train leg inverts the sign. Demonstrated on the live shipped
     gate (GATE_VERSION=v4): train -10% / test -8% -> "kept 80% of its edge" -> PASSES. Latent,
     not realised (no issued verdict turns on it). This is where the 1379% bug actually lives;
     the floor was installed in walkforward.retention() instead. HIGHEST-VALUE OPEN ITEM.
  2. The motivating case is misstated everywhere (walkforward.py:56, judgement.py:313,
     CALIBRATION_2026-08-17 §4): candidate e8ace8499908 / sweep 420a94db2621 trained at +10.171%
     and tested at +140.219%. The "+3.66%" was back-solved as 50.504/13.786, where 50.504 is the
     candidate's own verification return, not the test leg. Neither 2.0 nor 5.0 nor 10.0 excludes
     it. The 2.0->5.0 derivation is void.
  3. Floor is inert on the belt: 0 of 57 null sweeps landed in (0,5); 4 of 77 folds total, 3 of
     them one strategy (trend_sector_commodity). Counterfactual floors 0/2/5/10 give IDENTICAL
     null pass (2/8) and starved (2/8). Only effect on record: turned one candidate's rejection
     from "ran and failed majority" into "never ran". The §7 claim that this is the fund's main
     noise filter (89.6%) is FALSE on the belt.
  4. Retention instability is a NUMERATOR problem. All 13 folds with retention >3 have train legs
     >=10%; worst is 30.8 at train +10.17%. IQR peaks in the 10-20% train band (14.0) and falls
     monotonically. The floor sits BELOW the unstable region. n=0 measurable folds under 5%.
- Sim-vs-belt reconciled, and it generalises: scripts/gate_power_audit.py models the train leg as
  ONE driftless draw (mu=0, 20% vol). Belt null grid points are mean +22.0%, sd 28.3%, AND
  leanrunner._sweep_summary hands retention the MAX over ~4 surviving grid points. 28.6% of points
  are under 5%; only 5.5% of maxima are. Belt null WF pass 2/8 = 25% (CP 95% CI 8.5-65.1%) vs model
  2.9% — CI excludes it. ANY future audit script must model drift AND grid-max selection.
- v5 CARRY-FORWARD (blocking; hand to whoever runs round 3): the --floor-sweep table concluding
  "MIN_TRAIN_EXCESS = 0, nulls 0.0% at every floor" came from that same defective null, so its 0.0%
  rows bound the model, not the belt. AND _sweep_summary still picks the winner by max RAW train
  return while v5 judges on excess — selection statistic != judging statistic, unmentioned in the
  design. Retiring 5.0 on the excess scale: supported. Bare strict-positive as sole guard: NOT
  supported until both are re-measured. Note +0.03% is strictly positive, so strict-positive alone
  would NOT have caught the one real explosion the raw-scale floor did catch.
- Belt starvation modes are NOT the floor: 10 engine timeouts (LEAN isolator kill ~5min,
  statistics:{}, which retention() reports as "a leg produced no return figure" — indistinguishable
  from a floor rejection in the stored fold count) and 5 no-trade test legs (all
  mean_reversion_cyclicals). A mode field on the stored fold count would have made this review a
  query instead of an excavation.
- Instruments still under watch, unchanged: min_walkforward_folds non-scaling (~12% FPR at 5y);
  sieve signal-path never compared against LEAN; real-belt null audit under v5 once it lands.
- Measurement debts NOW: 29 clean nulls to bound FPR under 10% (still open, and the belt's 25% point
  estimate makes it more urgent); a null audit that CAPTURES per-fold train returns into the
  candidate record; oracle discrimination inversion (nulls 25% pass, oracle 0 of 5 folds retained)
  — v2-era geometry, needs its own v4 run before it is asserted.
- Scratchpad (survives session): min_train_return_review.py + pull/analyse/plot/counterfact/points/
  final.py in .../bbc88cbf-5b81-4236-8781-b009121ec21f/scratchpad. folds.json is the 83-fold extract;
  api_candidates.json / api_sweeps.json are the live endpoint captures.
- [CTO note at resolve, 2026-08-20]: all four findings CEO-accepted and implemented same night as
  gate v4.1 (commit cc11c6f): gate.py holdout leg now calls walkforward.retention(); register +
  comments corrected; GATE_CALIBRATION §9 correction filed; sweeps list serves holdout_result
  (84 rows, verified live). Your recs 1-4 are marked done on run-validator-floor.

## 2026-08-20 — batched dispatch 8b863152: R6 register review, D2 cost measurement, strategy-attribution oddity. All three measured live on :8090 + local Postgres (dsn default postgresql://krypton:krypton_local@127.0.0.1:5433/krypton_fund, FUND_STORE=postgres, 395 events at time of audit).

- EVENT-TYPE STRINGS ARE PASCALCASE IN PG, not the enum's SCREAMING_CASE: 'OrderFilled',
  'OrderProposed', 'NavStruck', 'StrategyArchived'. Querying type='ORDER_FILLED' returns 0 rows
  and looks like an empty log. Whole log is small (395 rows, 27 OrderFilled + 5 OrderPartiallyFilled)
  so a full pull is cheap. GET /fund/events maxes limit=1000 and since_seq does NOT page backwards
  (fund.py:711 streams all then takes the last `limit`) — use Postgres for anything historical.
- ITEM 1 (R6). min_effective_bets=2.0: reads 2.47 live (NOT "near the floor" — brief was wrong by 24%).
  effective_bets = DR^2 (correlation.py:243-244) so a hedged pair EXCEEDS n; naive_bets=2.00.
  On this book the floor is exactly "DBC/TLT correlation <= -0.209" (solved + verified numerically:
  eff_bets=2.001 at rho=-0.209). Discriminates the accident cleanly (90/10 -> 1.18, 100/0 -> 1.00).
  Known limitation: NOT monotone in book risk — 10/90 DBC/TLT (lower vol) reads 1.84 and would fire.
  VERDICT: measuring risk. Leave alone.
  max_risk_concentration_pct=0.50: BROKEN, inverted discrimination. A 100% single-name book reads
  100.00% — LOWER than the current hedged book's 102.49%. Risk shares sum to 100% by Euler
  (riskmetrics.py:99-152), so a negative contributor pushes the top above 100%. Alarm gets LOUDER as
  the hedge improves (rho=+0.9 -> 71.7%, rho=-0.9 -> 147.1%). Healthy books span 68-147%, accidents
  100-109% — NOT SEPARABLE by any threshold. Tightest passing threshold beats 90/10 by 0.31pp, which
  is less than the 1.17pp gap between the two estimators the same view uses. VERDICT: retire or
  re-specify the statistic; no number fixes it.
  2-asset risk parity is CORRELATION-INDEPENDENT: contributions differ by (w1s1)^2-(w2s2)^2, so parity
  requires w1s1=w2s2 -> DBC 29.5/TLT 70.5 (sample vols), 33.4/66.6 (EWMA). Even at sample-parity the
  EWMA alarm reads 68.5% — the estimator that sets weights is not the one that alarms.
  BIGGEST R6 FINDING: NEITHER THRESHOLD GATES ANYTHING. RiskGuard.check (risk.py:101-176) reads only
  max_order_notional_pct / max_position_pct / min_cash_buffer / min_cash_pct. Both limits are consumed
  ONLY by riskengine.structural_alarms (riskengine.py:530-586) -> /fund/risk/advanced -> UI
  (fund_api.ts:1834). Auto-halt is critical drawdown/daily_loss only (riskmonitor.py:575-577);
  throttle reads absorption+turbulence only. Zero verdicts have ever been issued under either.
  Also: /fund/risk/monitor PUBLISHES both limits but never evaluates them (its alarms() covers
  drawdown/daily_loss/concentration/cash_floor/underwater/strategy_cap only) — reads as "passing"
  while /fund/risk/advanced is raising the alarm.
  Better accident detector, already computed and unread: top-name component_risk_pct (9.78% live ->
  20.09% at 90/10 -> 22.35% at 100/0, 4.87% at parity). Cardinality-free, hedge-monotone.
- REGISTER DEFECT (found in passing, generalises): Judgement.due() (judgement.py:131-133) is
  `now >= review_by` — DATE ONLY. review_trigger is free text NO CODE EVALUATES. /fund/judgement
  returns due_for_review: [] while min_effective_bets' trigger ("first drawdown episode over 3%")
  had fired — /fund/risk/monitor max_drawdown_pct = 7.7467. 17 entries, 16 with triggers, 0 checked.
  Same write-only pattern as the old verdict column. ALSO: max_risk_concentration_pct is NOT
  REGISTERED AT ALL (verified against the 17 keys). ALSO: the min_effective_bets entry's own text
  says "Measured now: 2.93 on 172 sessions"; today it is 2.47 on 174. drift() only compares the
  constant, so a stale justification reads clean.
- ITEM 2 (D2). THE PAPER VENUE CANNOT MEASURE COST, EVER. PaperConnector.execute fills at
  self.quote(order).price (paper.py:116,139); pipeline.py:215 records arrival_price from the SAME
  call. arrival == fill to the last float bit in all 10 paper fills. Venue split of execution_bps:
  paper n=10, all exactly 0.00; alpaca n=8 (2 more lack arrival_price), mean +5.56, median +2.61.
  ALL FOUR of today's named fills (SOFI/NVDA/XLE/SPY) were venue='paper' — informative sample = 0,
  not 4. Per-instrument informative counts vs the 20-fill bar: SPY 2 distinct price events (the two
  13:30 SPY buys share arrival 778.30 / fill 778.58 — ONE event, not two), GLD 1, INTC 1, SOFI 1,
  NVDA 1, XLE 1, MSFT 0, F 0, TLT 0, DBC 0. SPY mean +1.52 bps, 95% CI +/-26.5 (t1=12.706) — contains
  0, 1, 5 and 20. TLT: zero observations, so P1's "SPY/TLT half-spread ~1bp" is unmeasurable for TLT
  at any confidence. P1 REFUSED, and structurally: more paper fills produce more zeros.
  GLD +81.22 and INTC -48.45 are both partial-fill sequences (OrderPartiallyFilled seq 79, 93) —
  intra-order drift, not spread. With them sd=35.4 -> n=4802 for a +/-1bps bound; without,
  mean 1.96 sd 2.48 -> n=24 (which is why RELIABLE_SAMPLE=20 is defensible on clean fills only).
  LIVE WRONG SIGNAL, ACT ON THIS: /fund/tca vs_assumption now reads sample=20, reliable=TRUE,
  realised -12.59bps, "cheaper than modelled, so the backtests are conservative". total_bps is
  decision->fill (tca.py:181) and includes approval latency (mean 523.6s, worst 2063.3s); the four
  biggest delay_bps (-165.93 XLE, -93.77 NVDA, -76.00 SOFI, +24.32 SPY) all have execution_bps == 0.
  It measures market drift during the human pause on a venue that charges no slippage. Lowering
  DEFAULT_SLIPPAGE_BPS on that verdict flatters every backtest Sharpe.
  PROVENANCE CORRECTION (fix API_CARD.md gotcha 4 and MECHANISM_CYCLE1:122,142): the "ten fills"
  behind 5.95bps are [MSFT, F, SPY, GLD, SPY, INTC, SOFI, NVDA, XLE, SPY] — FIVE ETF fills, three
  mega-cap, two small/mid. NOT "ten small-cap fills". Mean reproduces exactly at 5.9497; median 3.53;
  drop the two partial-fill outliers and it is 3.34 on eight. "5.95 ~ 5.0" rests on two artifacts
  cancelling. D2's substantive claim (one global constant, costassumption.py:33, consumed at
  leanrunner.py:399-400 and tca.py:57) STANDS; D2's ARGUMENT does not. The "3-5x overcharge on
  mega-liquid ETFs" figure has no measurement behind it in our data.
  entry-11 money: spec's own arithmetic gives 0.24%/yr of modelled return per 1bps of slip, vs a
  1.0-1.8%/yr gross claim. 5.0 -> 1.0 returns 0.96%/yr = 53-96% of the edge. The verdict flips on
  this constant, which is exactly why it must not move on our fills. Replacing it needs PUBLISHED
  quote/NBBO data = a versioned cost-model change with a written reason.
- ITEM 3 (phantom +/-$174.47). ROOT CAUSE, exact: seq 76 GLD BUY 0.424471 @402.18 sid=e54f40af
  (Trend — Sector & Commodity); seq 258 GLD SELL 0.424471 @100.00 sid='machinery-test'. Same qty,
  same symbol, DIFFERENT strategy tag. StrategyAttribution._apply keys on payload['strategy_id']
  (projections/strategy.py:79), so Trend keeps a phantom LONG and machinery-test opens a phantom
  SHORT. machinery-test pnl -132.00 reconciles to the cent: exposure -174.45 minus short basis
  -42.45 (= 0.424471 x 100.00), per strategy.py:157. Residue of the phantom-price incident; the
  realised loss closed, the LEDGER ARTIFACT IS PERMANENT because the fold is over the whole log.
  NAV/positions unaffected (the qtys net to zero).
  MONEY PATH IS REAL AND MEASURED: RebalanceService._composition (rebalance.py:68-82) reads
  attribution. POST /fund/rebalance/preview {"e54f40af-...":20.0,"sleeve_beta_500":26.57} returned
  a $376.84 GLD BUY with current_usd: 0.0 and limit_warnings: []. Event count 395 before and after —
  preview genuinely writes nothing. At the max_strategy_pct 0.40 cap that is $753.68 = 40% of NAV
  into a symbol no live strategy holds. Still needs propose -> CEO approve -> pre-trade gate, but
  RiskGuard sees only max_position_pct=0.20 and the 20% target sits exactly on the line.
  NO AUTOMATIC CONTROL reads per-strategy exposure: strategy_cap is severity=warn
  (riskmonitor.py:505-521), auto-halt is drawdown/daily_loss only. correlation.analyse takes weights
  from the NAV position fold, not attribution (live symbols ["DBC","TLT"], coverage 100%), so
  effective bets and risk shares are CLEAN.
  TWO STRUCTURAL GAPS: (a) riskmonitor.py:511 is `if weight > strat_limit` — a NEGATIVE strategy
  weight can never breach, so a phantom short of any size is invisible; the 40% cap is one-sided.
  (b) ARCHIVE IS COSMETIC: Trend was archived 2026-08-20T13:48:51 (payload {}, no reason);
  /fund/strategies returns archived:true, state:paused, allocation_pct:0.0 — and rebalance/preview
  STILL accepted it as a target. No consumer enforces the flag.
  Repair shape (I do not write code): compensating event, never a log rewrite. Prefer the general
  fix — build()/_composition refuse a strategy whose folded position disagrees with the
  authoritative NAV position fold for that symbol; catches every future mistag, not just this one.
  Add the archived filter in the same change.
- USEFUL SPINE FACTS FOR NEXT TIME: /fund/strategies rows DO carry `archived` and `state` (the
  earlier "status: None" I printed was a wrong key). /fund/rebalance/preview is a genuinely
  read-only POST — verified by event count. /fund/risk/advanced carries correlation,
  risk_contribution, tail, loss_surface, factor_map, headlines, alarms in one call; it is the
  ONLY consumer of min_effective_bets and max_risk_concentration_pct.
- Scratchpad (session bbc88cbf-...): r6.py + r6b.py (ITEM 1 accident tables, sample and EWMA),
  d2.py + d2b.py (ITEM 2 per-instrument and per-venue cost), fills2.py (all fills with strategy
  tags), venue.py, evtypes.py (event-type histogram). Captures: risk_monitor.json, adv.json,
  tca.json, judg.json, strategies.json, reb.json.
- CARRY-FORWARD MEASUREMENT DEBTS, unchanged from the floor review plus new: 29 clean nulls to
  bound gate FPR under 10%; v5's floor-sweep tables must be regenerated with a drifted, grid-max
  null; oracle discrimination inversion needs its own v4 run. NEW: a cost measurement is impossible
  until either real alpaca fills accumulate (>=20 clean single-fill orders per instrument) or
  published spread data is purchased — and the second is the only route that does not take months.

- [CTO note at resolve, 2026-08-20]: three claims verified line-by-line before acting
  (paper.py:116 own-quote fill, riskmonitor.py:511 one-sided '>', judgement.py:131-133 date-only)
  — all exact. Your tca fix was implemented the same hour: the verdict now grades execution_bps on
  non-paper venues only (live reading flipped from "reliable:true, -12.59, cheaper than modelled"
  to "+5.56 on 8 fills, an anecdote, not a measurement"), pinned by 4 new tests. API card gotcha
  corrected (five-ETF provenance + the paper-venue tautology added as gotcha 6), MECHANISM_CYCLE1
  gained a correction section, REVIVAL_REGISTER entry-11 records P1's structural refusal with the
  slip-band interim route. Your 8 recommendations are on run-validator-r6d2 for the CEO; the
  threshold and attribution/archive/two-sided-cap changes wait for those clicks. Both requests
  (8b863152, b0bd0489) resolved. The audit was filed verbatim as
  docs/AUDIT_R6_D2_ATTRIBUTION_2026-08-20.md.

