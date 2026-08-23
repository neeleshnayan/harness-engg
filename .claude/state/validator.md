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


## 2026-08-20 — walk-forward window geometry for short holds (trace 5fc56190; first
   seat-filed ask to complete the full chain: mechanism filed -> CEO approved -> CTO fired).
   All numbers are runs of the shipped function or local-mirror queries.

- INVERSION REPRODUCED, WITH TWO EXACT CLOSED FORMS (verified 276/276 and 23/23):
    span_oos(h,K) = K * floor(4h * 365/252) calendar days
    K(h)          = (cal(252+20h) - 366) // cal(4h)     [cal(d)=int(d*365/252)]
  At gate v4.1 (min_folds=4, floor 2024-02-26, end 2026-08-19): hold-1 -> 5 folds / 25d;
  hold-3 -> 5 folds / 85d (2026-05-26..08-19); hold-21 -> 4 folds / 484d; hold >=24 -> <4
  folds -> NOT TESTABLE. Effective belt hold range is 1..23.
  Fold count is NON-MONOTONE: K drops 5->4 at holds 4, 9, 14, 19 — pure cal() rounding beat.
  walkforward.py:123-124 docstring ("6 folds for a 5-day hold") reproduces at min_folds=5,
  not the shipped 4 (measured 5/4/1).
- THE BIGGEST FINDING, NOT THE ONE ASKED FOR: window_for fold count is INVARIANT TO
  AVAILABLE HISTORY. floor 2024-02-26 -> 2016-08-22 (905 -> 3649 cal days) leaves hold-3 at
  5 folds / 85d, unchanged. walkforward.py:223-228 fixes reach-back at train+test*(K+1);
  the floor only CLIPS, never extends. Belt fold counts for TEST=84 at 630/1260/2520
  trading days are 4/5/5, versus 4/12/27 in scripts/gate_v5_audit_r4.py:224-230 (_folds(n)
  PACKS the history). Therefore GATE_V5_ROUND4 §3's history table — the sole cited evidence
  for the WALKFORWARD_HISTORY_FLOOR change and the 10y backfill sequencing (§144-147, §218-223)
  — measures a fold generator the belt does not implement. §7's `available` is undefined
  against any function: read one way the scaled floor is a permanent no-op (window_for
  returns ~5 at every depth so the floor stays 4); read the other it needs 17 of 27 and makes
  every 21-day strategy NOT TESTABLE. The backfill through window_for adds ZERO folds and
  ZERO out-of-sample coverage; it extends TRAIN legs only. v5's MPPM/VR/margin work (§1,§4)
  is untouched by this. NOT re-run: what the corrected r4 tables would say.
- ITEM 4 ANSWERED, STRONGER THAN THE MECHANISM CLAIMED: span(hold-21)/span(hold-1) = 24.2x
  at K = 4, 6, 8, 12, 17 AND 27 — exactly cal(84)/cal(4)=121/5. Count-scaling multiplies both
  sides by K and closes nothing. Also, at TODAY's floor, raising min_folds to 6/8/12/17 gives
  short holds 6/8/12/17 folds while hold-21 stays pinned at 4 and flips to NOT TESTABLE —
  the scaled floor before the backfill INVERTS testability toward the least-covered rules.
- REGIME COVERAGE (fund's own turbulence, regime.mahalanobis_series over SECTOR_BASKET, 11/11,
  1004 scored days; reachable window 2024-02-26..2026-08-19 = 623 sessions, 143 elevated
  >=p80 16.12, 39 extreme >=p95 29.60): hold-1 sees 21 sessions / 7.7% of elevated;
  hold-3 63 / 25.9%; hold-10 198 / 55.2%; hold-21 336 / 60.1%. THE LARGEST STRESS EVENT IN
  REACHABLE HISTORY (turb 86.9, 2025-04-03..05-13) IS INVISIBLE TO EVERY HOLD <= 17.
  Episode counts monotone at merge gaps 3/5/10/20 but level is merge-dependent — do not
  headline them. HONEST COUNTER-POINT: hold-3 covers 41% of EXTREME days in 10% of sessions
  because the last quarter was hot — narrow coverage can land hot or cold, which is the
  one-draw property, not an argument that short holds are uniformly worse.
- THE RECORD IS CLEAN — NO ISSUED VERDICT IS AFFECTED. fund_candidates n=34, 19 carry a
  walk-forward check. Stored test legs group as: 91d n=19 (the five gate-v2-era candidates,
  2026-08-17 13:12-16:11), 121d n=34 (all null_random_smallcap, gate v4, = exactly the hold-21
  4-fold set), 225d n=30 (single-window holdout, not walk-forward). ZERO verdicts ever ran a
  leg shorter than 91d. The inversion is PROSPECTIVE. The 6 not_testable=True nulls are the
  hold-63 grid behaving correctly.
- QUALIFIER IS A RENDERING CHANGE, AND I VERIFIED THE PLUMBING: fold rows already carry
  train/test start+end (walkforward.py:347-358 spreads **f), dates_honoured, measurable,
  test_orders; summarise() (375-408) receives them and computes nothing from the dates.
  BUT factory._run (165-171) DISCARDS `walk` after judging — _finish stores verdict+winner
  only — so the qualifier must be written into verdict["checks"] by gate.evaluate (next to
  gate.py:447-449) to survive. factory.history (366-372) serves FIVE count fields only;
  confirmed live on :8090 (folds_measurable/folds_retained/median_retention/retained_share/
  not_testable). Recommend headline statistic = oos_span_days (+ oos_start/oos_end/oos_folds/
  oos_folds_dishonoured/hold_days/hold_days_source), computed over MEASURABLE folds with
  dates_honoured True only. NOT quarter-count (boundary luck) and NOT episode-count (merge
  parameter). Trust check: of 79 stored holdout_results, 73 dates_honoured=True / 4 False /
  2 skipped, median (engine-actual / requested test days) = 1.000.
- API CARD DEFECTS TO FIX: (a) the fold-planning bullet should add "fold count is INVARIANT
  to available history — the floor only clips; deeper history does NOT buy folds";
  (b) holdout_result.test.window is the ENGINE-ACTUAL window and is NOT copied into the
  fold row — requested dates are the only per-fold record downstream.
- DECISIONS_PER_TEST_LEG=4 IS UNVALIDATED. It sizes every test leg in the fund. total_orders
  on the 121d legs reads min 20 / median 67 / max 136 because it counts symbol fills, not
  rebalances. Neither confirmed nor refuted; no counter exists.
- Scratchpad (session bbc88cbf-...): wf_geometry.py, wf_regime.py, wf_episodes.py (+ep3/5/20),
  wf_counterfactual.py, deep.py, kscale.py, issued.py, holds.py, wins.py, hw.py, hw2.py,
  orders.py. Captures: wf_rows.json, wf_regime.json, cand.json.
- MEASUREMENT DEBTS, carried + new: 29 clean nulls to bound gate FPR under 10% (open);
  v5 floor-sweep tables need a drifted, grid-max null (open); oracle discrimination inversion
  needs its own v4 run (open); cost measurement blocked on alpaca fills or published spreads
  (open). NEW AND BLOCKING: re-run scripts/gate_v5_audit_r4.py --history-sweep against
  window_for's ACTUAL fold generator before any WALKFORWARD_HISTORY_FLOOR change or backfill.

- [CTO note at resolve, 2026-08-20]: the invariance claim was reproduced independently
  the same hour (hold-3: identical fold dates at floors 2024-02-26 and 2016-08-22; hold-21
  gains only the one clipped fold, 4 -> 5, then caps). The defect in the r4 audit was MINE;
  GATE_V5_ROUND4 now carries §8 correcting and reframing its history limb (window-function
  change + 'available' definition + scaled floor + backfill as ONE versioned package), and
  your blocking recommendation is honored: no floor change and no backfill until that
  package is specified and measured against the real generator. The API card bullet was
  corrected per your (a) and (b). Audit filed verbatim as
  docs/AUDIT_WF_GEOMETRY_2026-08-20.md; recorded as run-validator-wfgeom; your 6
  recommendations are on the CEO's desk. The first seat-filed ask closed its full loop —
  and its answer found a defect in the CTO's own instrument, which is the metric working.



## 2026-08-22 — BINDING CONSTRAINT ON YOUR NEXT ARTIFACT (chair note, co-CTO)

**Our own price history carries a ~44%/yr phantom factor. Do not sort on
price level, market cap, dollar volume or share count until told otherwise.**

Measured by the analyst and VERIFIED independently by the chair before this
note was written:

- Monthly-rebalanced price-quintile LOW-minus-HIGH over the fund's 200-name
  universe returns **+49.68%/yr (t=5.69) on adjusted closes and +43.84%/yr
  (t=4.62) on nominal closes, positive in all seven years.** None of it is
  a market effect.
- **Cause (a) — the anchor is TODAY, not the bar's own date.** Closes are
  split-back-adjusted from the present. `GET /fund/marketdata/bars?symbol=TENX`
  returns `closes[0] = 2320.0` for 2020-06-01 and a 2020 high of 3168.0 for a
  sub-$2 biotech, because 1:20 (2023-01-05) and 1:80 (2024-01-03) reverse
  splits are projected backwards. Changing `end_date` does NOT move the
  anchor. The payload carries `adjusted: None` — it does not even name what
  it is anchored to. Yahoo's raw `quote.close` is ALSO adjusted, so exposing
  a raw field is not the fix; the SPLIT EVENTS are.
- **Cause (b), the larger half — survivorship.** Re-counted by the chair
  from the cached 5-year bar set: **203 of 203 symbols have a last bar of
  2026-08-20 or 2026-08-21.** Zero attrition across six years of small and
  mid caps — no bankruptcy, no delisting, no going-private, not one name.
  `GET /fund/universe/hunting-ground` is `operating_only: true` off Polygon's
  CURRENT reference data, so membership is conditioned on being alive today.

**What is safe and what is not:**

- **SAFE — anything built from RETURNS.** Momentum, reversal, event abnormal
  returns, volatility. Returns are adjustment-invariant; that is what
  adjustment is for.
- **NOT SAFE — any cross-sectional sort on price level, market cap, dollar
  volume or share count, and any comparison of a filing's nominal dollar
  figure to one of our closes.** A candidate built on one of these will
  present roughly +44%/yr with a good IR, positive in every walk-forward
  fold, and the gate will pass it — because every fold reads the same
  today-anchored, survivor-only series. **The gate is structurally blind to
  this class of defect.** It is not a filter you can lean on here.
- Long-horizon ABSOLUTE-return studies on this universe are inflated by
  survivorship regardless of what they sort on.

This lifts when the split-event fix lands (filed as a builder ticket:
`&events=div,split` gives numerator/denominator; `nominal(t) =
split_adjusted(t) x product of (num/den) for splits after t`, verified
working on 202/202 symbols). Survivorship does not lift — no point-in-time
universe membership exists in the fund, so that half is fenced, not fixed.

**And the method rule that found it, which now binds you too: every
cross-sectional conditioning claim carries an EVENT-INDEPENDENT PLACEBO
(the same names, dates shifted +/-60/120/250 sessions) before it is
believed.** It killed two |t|>3 "findings" in the dispatch that produced
this note — including one that looked like a clean tradeable short.


## 2026-08-22 — gate v5 ROUND 5 measured (dispatch from the co-CTO chair; CEO: "close gate v5 so we can keep testing").
   New instrument: scripts/gate_v5_audit_r5.py (885 lines, mine, r4 NOT edited). Repro:
   ./venv/Scripts/python.exe scripts/gate_v5_audit_r5.py --all --draws 2000
   Variants that matter: --stat r4 (before/after, identical geometry+seeds), --floor none,
   --real-bench, --draws N. Bar cache defaults to %TEMP%/krypton_r5_bars_cache.json — the repo
   stays clean (git status showed only the one authorized new file).

- G1 FINANCING IS FIXED AND I COULD NOT REOPEN IT. GISW form implemented as excess ratio
  returns e=(1+r)/(1+rf)-1 (r5:161,202); levering multiplies e by k, which IS rf+k(r-rf).
  Real SPY/BIL, 336 OOS sessions: cash mix w*bench+(1-w)*rf scores 0.0000 %/yr at every w
  (daily leg) vs r4's +0.98/+2.61/+5.88/+15.70/+35.11. MC: 0.0% in all 16 (w x rf) cells,
  0/2000 => CP95 upper bound 0.2% per cell. Same cells through r4's statistic: 33-38.7% at
  rf>=2, 0.0% at rf=0. cashmix_w0.40 under r4-stat with real BIL = 39.8% uncond / 98.6%
  CONDITIONAL ON RUNNING — reproduces the adversary's 98.9% in the REACHABLE geometry.
  MAX_LEVER=10 under excess UNDER-levers (w=0.05 reads -1.76) — conservative, opposite
  direction from r4. 21-day residual (<=1.11%/yr at w=0.20) is REBALANCING CONVEXITY not
  financing: it moves with w, falls as rf rises (0.267/0.239/0.214 at rf 0/4/8 at w=0.80).
  It would bind if the margin ever went below ~1.1%/yr.
- THE NEW BLOCKING HOLE, H1: NO rf SERIES EXISTS ANYWHERE IN THE GATE PATH. The rule must
  assume one, and the gift is ((1-w)/w)*(rf_true - rf_assumed) %/yr; break-even error is
  margin*w/(1-w). Measured: rf_a=0 reproduces r4 EXACTLY (+5.88 at w=0.40); rf_a=2% while
  BIL earned 3.97% gives +2.90 vs a 2.0 margin = zero-skill pass. Choice of cash PROXY is
  NOT the risk (BIL 3.97 vs SHV 3.94 over the same window). Static-vs-realised is the risk.
- DISCRIMINATION IS BELOW A COIN AND NO MARGIN FIXES IT. Shipped geometry (window_for_strategy
  CALLED, floor 2024-02-26 => 4 folds / 84d legs / 336 OOS sessions; floor none => 5 / 416),
  2000 draws, rho 5, margin 2.0, mktSharpe 1.0 ASSUMED, rf real BIL, dropout 20.8%:
  class max 18.2% CP95[16.5,20.0] = sv_1000_30_b0; TP premia_defensive 11.3% CP95[9.9,12.8];
  break-even 61.8%; DISCRIMINATION 0.62 CI[0.53,0.72] — CI excludes 1. Excluding the blindness
  class: 10.2% vs 11.3% = 1.11 CI[0.93,1.32]. Oracle SR2.5 as TP: 1.42 CI[1.26,1.60].
  Margin sweep 1/2/3/5/8 %/yr: worst null 21.2/17.3/18.8/17.7/16.6, TP 13.0/12.0/10.2/8.6/4.3
  — discrimination 0.61/0.69/0.54/0.49/0.26. Round 3's pattern in a new statistic.
  Before/after, identical geometry+seeds: r4-stat class max 39.8% / TP 15.1% / disc 0.38 ->
  r5 18.2 / 11.3 / 0.62. The fix is real AND leaves the round below a coin.
- MECHANISM OF THE CLASS MAX (H3, the highest-value unrun experiment): VOL-MATCHING IS THE
  AMPLIFIER. Median realised lever sv_1000_30_b0 6.48 (p90 7.07) vs premia_defensive 1.72,
  oracle_sr2.5 1.99, beta-1 nulls ~0.9. A 3%-vol stream matched to 20% is levered 6.7x and a
  tiny event-free drift becomes +17.8%/yr median. ROUND 6 MUST MEASURE DISCRIMINATION AS A
  FUNCTION OF MAX_LEVER AND OF A LEVER-AWARE MARGIN. Blindness: P(0 events in 336 OOS
  sessions) = 71.5% at p=1/1000, 91.9% within one 84d leg. Unconditional full-sample leg
  P(>2%/yr): worst null 61.7%, premia_defensive 53.5% — the margin sits INSIDE the noise band
  (premia_defensive p10 -10.0 / p90 +13.9 %/yr on 336 sessions).
- MASKED FAMILY SURVIVES ROUND 5 (H4): peak 10.2% uncond / 26.0% CONDITIONAL, statistically
  unchanged from r4's 23.6%. Its apparent improvement is entirely the starvation ceiling.
  VR guard is NOT broken — it kills 100% of RUNNING pure-wander draws at w=1.00 and degrades
  to 3.2% caught at w=0.10/beta=1, exactly as the adversary showed.
- STARVATION CEILING, common-mode: gate.py:183 needs 4 measurable; the live floor supplies
  EXACTLY 4 (slack 0) => P(>=4 of 4) = 39.3%, so 60.7% never judged; floor none gives
  P(>=4 of 5) = 72.1%. Lifting the floor moves FPR 18.2->35.2 and TP 11.3->23.9 and
  discrimination only 0.62->0.68. neverRan is 55-63% of every battery row.
- MEASURABILITY: THE DATA PATH EXISTS AND HAS NEVER RUN. 37 candidates, 0 with analytics;
  0 legs computable belt-wide; missing by name {verification:37, holdout_test:37};
  runanalytics.view() reason 'not_captured' x37. Postgres: count(analytics)=0 of 37;
  0 of 99 fund_lean_sweeps contain 'daily_returns'. Last candidate finished 2026-08-20T20:05Z,
  BEFORE 76784c2 merged 2026-08-21 17:29 IST. NEW READER DEFECT: when analytics is absent
  entirely, daily_return_legs names only 2 missing legs because folds() (runanalytics.py:267-276,
  :312) learns K from the same absent payload — true absent count is 2+K (222 belt-wide vs 74
  reported). Same shape as the write-only verdict column.
- RECORD IS CLEAN, PROSPECTIVE ONLY: GATE_VERSION v4.1 (gate.py:157); stored verdicts v1 x11,
  v2 x5, v4 x14, v4.1 x3, null x4. NO verdict has ever used a v5 premia statistic. The only
  three passes on the whole belt are null_random_smallcap under v1. The cost is leg-2/leg-3:
  the premia sleeve has had no criterion since 2026-08-19.
- HONEST NEGATIVES, DO NOT RE-SPEND: financing could not be reopened by any w / rf / lever
  cap / aggregation. GRID-MAX SELECTION ON RAW TRAIN RETURN HAS NO MATERIAL EFFECT on the OOS
  excess statistic (<=3pp on P(>margin) across 7 processes, n=1500) — MY OWN CARRIED
  MEASUREMENT DEBT FROM THE FLOOR REVIEW IS CLOSED. --real-bench (no market-Sharpe assumption)
  gives disc 0.43, so the conclusion does not rest on --market-sharpe 1.0. Do not re-run the
  beta-nonstationarity class maximum (7.1%) or the 20.8% dropout provenance.
- CAVEAT I DID NOT CORRECT: concatenating surviving test legs is contiguous by construction at
  the live floor (any dropout => never_ran), but at floor=none a survivable dropout leaves an
  84-day hole and the 21-day blocks straddling it are wider than they look. Applies to the
  floor-lifted table only.
- COULD NOT RECONCILE: the adversary's r4 reachable-state figures (FPR 13.7 / TP 24.5 /
  break-even 35.8) exist only in review prose — no committed script produces them. r4's own
  630-day table gives class max 19.3 / TP 12.3 / disc 0.64, which MY r5 numbers do match
  (18.2 / 11.3 / 0.62).
- MEASUREMENT DEBTS carried + new: 29 clean nulls to bound gate FPR under 10% (open);
  oracle discrimination inversion needs its own v4 run (open); cost measurement blocked on
  alpaca fills or published spreads (open). NEW: discrimination vs MAX_LEVER and a lever-aware
  margin (H3, highest value); a residual-based VR guard measured against the masked family
  (H4); DECISIONS_PER_TEST_LEG=4 still unvalidated and it SETS the 336-session window that
  puts the margin inside the noise band.
- Scratchpad (session bbc88cbf-...): r5/full_run.txt (--all --draws 2000), r5/margin.py
  (margin sweep), r5/dist.py (unconditional full-leg distribution + grid-selection negative),
  r5/lever.py (realised vol-match levers).

[CHAIR NOTE — co-CTO. Three claims verified independently before filing:
GATE_VERSION = "v4.1" at gate.py:157 (so "nothing retrospective" stands);
`git status --porcelain scripts/` shows ONLY `?? gate_v5_audit_r5.py`, so r4
really was left untouched; and `select count(*), count(analytics) from
fund_candidates` returns `37 | 0` against Postgres directly — zero of
thirty-seven. The measurability finding is the one I most wanted to be wrong
and it is exactly right. Filed as docs/GATE_V5_ROUND5_MEASURED_2026-08-21.md.
DATING: the STATE header above says 2026-08-22 (local IST); the UTC day was
still 2026-08-21 when this ran, and the doc is named for UTC. Both are the
same moment.
ROUND 5 IS CLOSED, NOT ADOPTED — the CEO asked to "close gate v5 so we can
keep testing", and the honest close is a measured NO with named holes, which
is what round 5 produced. H1 (the rf source) is routed to the CEO as the one
decision he owns. H3 (discrimination vs MAX_LEVER) is registered as round 6's
first experiment. The analyst's price-anchor finding is registered as a
SEPARATE round-6 input (4698dee7) and was deliberately kept out of round 5.]

## 2026-08-21 — CARRIED FROM THE MECHANISM (cycle 3) BY THE CHAIR

First use of the `## BINDS` protocol. The seat named you; the chair verified the underlying code claim and carried it.

**`breakeven_cost` (`leanrunner.py:271-315`) interpolates on TOTAL RETURN, so
any candidate holding cash between signals has its cost robustness inflated by
risk-free carry.** Chair-verified: the function skips points where
`total_return_pct is None` and finds the zero crossing on that field.

Measured instance: a candidate's edge dies at **7.3 bps/side**, the gate reads
**14.55** against a 10.0 floor and passes it — and at that floor the strategy
earns +1.09%/yr against BIL's +2.05%/yr.

**Your task: of the 40 belt candidates, how many passed `min_breakeven_bps` on
that inflation?** One query plus one re-interpolation on
return-minus-cash-leg. This is the gate-v5 round-4/5 risk-free leak living
inside **v4.1**, and it is one of the cheapest leg-1 measurements available.


## 2026-08-21 — **STOP TREATING LOCAL COMPUTE AS SCARCE. IT IS NOT. MEASURE WHICH RESOURCE YOU MEAN.**

**CEO instruction, verbatim: "I am seeing concerns with the team of their
being a upper bound to compute which is not true; we have a very capable PC
and whats stopping them?"** He is right, and the chair measured the machine
rather than assuming either way.

**THE MACHINE, measured 2026-08-21:**

| resource | actual | verdict |
|---|---|---|
| CPU | **Ryzen 9 7900X — 12 cores / 24 threads, running at 11%** | **NOT SCARCE** |
| GPU | **RTX 4090**, idle except during local-model work | **NOT SCARCE** |
| Disk | 74 GB free of 421 | not scarce |
| **RAM** | **15.2 GB total, 0.8 GB FREE** | **THIS IS THE WALL** |

**THREE DIFFERENT SCARCITIES HAVE BEEN COLLAPSING INTO ONE WORD, AND ONLY TWO
ARE REAL:**

1. **TOKENS — genuinely scarce and structural.** This is what the quota-era
   dispatch rules protect: batch by seat, one human trigger, an idle seat costs
   zero. Frugality here is correct and is not up for revision.
2. **RAM — genuinely scarce at 15.2 GB, and it is the real container
   ceiling.** `MAX_CONCURRENT_CONTAINERS = 6` is registered with basis
   `measured` and falsified-by *"a WinError 1455 or any host-memory kill"* —
   the paging-file error. That limit came from an actual out-of-memory event.
   It is a RAM limit wearing the word "container".
3. **CPU, GPU AND WALL-CLOCK — NOT SCARCE, AND THIS IS WHERE THE FALSE CAUTION
   LIVES.** Twenty-four threads at 11% and a 4090 doing nothing.

**THE RULE THIS BUYS: before you cite a compute cost as a reason to narrow a
recommendation, say WHICH resource you mean and what you measured.** "12.6×
compute" is not a cost statement — it is three different claims wearing one
number, and on this machine two of the three are free.

**THE WORKED EXAMPLE, and it is a live one.** The mechanism's D5 fix would take
a 1-day rule from 5 folds to 63. The seat called it *"~12.6× compute per
candidate"* and declined to recommend it without a cap. But the quant measured
real container wall-clock at **12.8s average, 18.4s maximum**, including a
5.47-year verification. Sixty-three folds × two legs × ~13s is **roughly 27
minutes, run sequentially, on a machine at 11% CPU.**

**That is not a cost. That is a coffee break, and it is exactly what the
market-closed queue exists for.** The cap the seat hesitated over is probably
unnecessary, and the hesitation came from reasoning about CPU-seconds in the
token frame.

**WHAT IS STILL TRUE AND MUST NOT BE THROWN OUT WITH THIS:**

- **Run candidates SEQUENTIALLY when wall-clock is an output.** The quant
  established this and it stands: the constitution's dependency test says a
  wall-clock measured under unadvertised contention is corrupted, not slow. The
  300s censored tail that justified raising the timeout ceiling was recorded
  under three concurrent candidates; sequentially there was no tail at all.
  **Parallelism is what costs here, not duration.**
- **Concurrency still hits the RAM wall at 6 containers.** Do not raise that
  limit as a consequence of this note; it is a registered value with a measured
  basis and moving it is a versioned change.
- **Tokens remain the real budget.** An 8-hour local extraction is cheap; an
  8-hour Opus dispatch is not. When you defer something for cost, be explicit
  about which one you mean.


## 2026-08-21 — CARRIED FROM THE BUILDER (D9) BY THE CHAIR: three fields you should now state

**When you file a recommendation in your `run_record`, state these when you
know them. All three are optional, all three are validated, and NONE is ever
read out of your prose.**

- **`next_actor`** — `ceo` | `chair` | `seat` | `nobody`. Whose move is it?
- **`due_date`** — `YYYY-MM-DD`, if the thing happens on a date **whether or
  not anyone clicks.**
- **`reversibility`** — `irreversible` | `hard` | `reversible`, for your own
  recommendation.

**Why this matters more than it looks.** The CEO's desk counter now routes by
next actor, and the builder measured that **`kind` is free text — 84 distinct
values across 219 recommendations, 49 of them appearing exactly once.** Routing
on it moves only 18.7% of rows, so the counter currently rests almost entirely
on inference. **These three fields are the only lever that fixes it.** The
desk's top ranking key is `due_date`, and it separated **zero** rows because
nothing writes it.

**Absent is honest; wrong is not.** And note the default: **a `kind` nobody has
seen before routes to the CEO.** Pick one that says who must act, or state
`next_actor` and stop relying on the word.


## 2026-08-21 — CARRIED FROM THE BUILDER (D10): state `reversibility` on your rows

The CEO's desk ranks **deadline → reversibility → money → age**, and `due_date`
currently separates **zero** rows because nothing writes it. **That makes
reversibility the top LIVE ranking key — and it is a lookup on your free-text
`kind` against a ~30-entry table.**

If your kind is not in that table, your row ranks with the urgent half
regardless of size. And a **$500k row whose kind IS in the table as
`reversible` sorts BELOW it.** State `reversibility` explicitly rather than
relying on the word you happened to pick.


## 2026-08-22 — STATE from run-validator-costmodel (cost-criterion audit), appended verbatim by the chair — the append this STATE itself demanded

- CFO's TABLE REPRODUCES EXACTLY (n/mean/sd to 3dp); her CIs are z on n≤8 —
  correct t-intervals are 18–42% wider; conclusions unaffected.
- MY BIGGEST NEW FINDING: execution_bps is contaminated by RESTING TIME —
  5 of 8 fills rested 4,466–4,707s (premarket submit → opening auction);
  arrival is captured at SUBMIT so the number is overnight drift, not
  spread. HONEST SAMPLE n=3: mean −0.088, sd 1.528, CI [−3.89,+3.71] —
  contains 0 AND 5. Same defect one layer down from my 2026-08-20
  total_bps finding.
- SELF-CORRECTION to validator.md:137: GLD has ZERO OrderPartiallyFilled;
  the partial-fill orders are SOFI(3), INTC(1), XLE(1); GLD's +81.22 is a
  75-min overnight gap.
- `reliable` IS A COUNT WHERE IT MUST BE A PRECISION BOUND — CONFIRMED. At
  n=20, half-width ±16.55 bps (sd 35.354). And sd is itself an estimate:
  chi2 95% CI on σ at n=8 is [23.4,72.0] — any n-projection is a scale,
  not a number. Consumer: ExecutionQuality.tsx:158 removes the banner at
  n=20.
- PROVENANCE OF 20: inherited from gate.py:167 min_orders=20, an
  incommensurable quantity; and the comment's "written a test for" is
  FALSE — patched 11/20/30/100/500 all pass; the suite constrains from
  BELOW only. Same failure family: min_orders, min_walkforward_folds=4,
  retained_share=0.5, DECISIONS_PER_TEST_LEG=4. The counter-example the
  fund owns: min_psr_pct — precision-aware by construction. THE MODEL.
- REGIME SPLIT ADJUDICATED: the CFO's is POST-HOC (selection on outcome;
  GLD, the largest outlier, has no partial fills so the story fails). A
  legitimate covariate split exists — submit_to_fill_s, causally prior,
  partitions cleanly. Supports her DIRECTION, refutes her LEVEL. CANNOT
  TELL between 0, 2 and 5; the settling measurement: 20 immediate-fill
  orders across ≥10 sessions incl ≥3 elevated-turbulence days.
- THE BRIEF WAS WRONG ON BREAKEVEN, THREE WAYS: min_breakeven_bps=10.0 is
  fixed (gate.py:172); DEFAULT_SLIPPAGE_BPS appears nowhere in
  gate.py:401-420; breakeven_bps is NULL for all 40 candidates — the 25
  are the NEVER-RAN mode. Where the constant DOES bind: leanrunner injects
  slip into 34/40 candidates → all RETURN-based criteria. Slip slope
  measured with zero containers: −0.27 %-return/bp per ~4-month leg,
  −1.17 on full verification; 5.0→2.0 = +0.80pp/leg. n=1 algorithm, pure
  turnover statistic, does not transfer.
- DIRECTION: my measurement does NOT support lowering DEFAULT_SLIPPAGE_BPS.
- MY MEMORY WAS STALE AND IT COST THIS DISPATCH: check /fund/desk runs +
  open recommendations for seat=validator at the START of every dispatch;
  do not trust this file to be complete.
- MEASUREMENT DEBTS: 29 clean nulls for gate FPR; oracle discrimination
  inversion needs a v4 run; DECISIONS_PER_TEST_LEG unvalidated; the
  20-immediate-fill collection is the ONLY thing that settles the
  ordinary-regime level. The mechanism's breakeven-carry ask is CLOSED:
  zero of 40.

## 2026-08-22 — CARRIED BY THE CHAIR (BINDS from three seats)

- **From the PM**: when you audit a measurement instrument, state which
  field is the BENCHMARK and check what it actually is — here
  get_stock_latest_trade, and the whole variance problem follows from that
  line. Re-rank quote-at-FILL against quote-at-SUBMIT: submit fixes the
  benchmark for every observation we keep; fill only rescues observations
  a correct rule excludes.
- **From the adversary (D11)**: (1) for any reachable/open/due boolean,
  find the line that actually DECIDES and check the boolean reads THAT
  line; (2) grep every new EventType for a producer before accepting the
  fold that consumes it.
- **From the riskofficer**: census the suite for tests whose assertion
  target is not the object production consumes —
  test_riskmonitor_unpriced.py:50 asserts on assess() output for an alarm
  that can never be raised; test_halt_classes.py:68 asserts a mapping no
  input can reach. A test reading a display dict passes forever over a
  dead control.
- **From the adversary (insider)**: for calendar-time overlay portfolios,
  build the date-shift placebo with shifts that are MULTIPLES of the hold
  length and report the z beside the NW t — NW understated noise by 27%.


## 2026-08-22 — CARRIED BY THE CHAIR (from Grace v0.2 and the analyst)

- **From Grace**: the whole quote-based instrument layer is testable
  against a free external reference — when you audit tca.py, pull the NBBO
  for the same timestamps and check execution_bps against a real mid, not
  against itself. Her weakest claim, flagged by her: the 38× SPY figure is
  from ONE 60s window at 17:00Z; spreads are wider at the open, when we
  trade. Re-measure across the session.
- **From the analyst, two standards now standing for event studies**:
  report the date-shift placebo BY SHIFT SIGN (negative shifts here sat on
  a real −7.7%/yr pre-filing run-up), and report placebo-sd / NW-SE (2.47×
  here — NW understates this class ~2.5×; anchor on the placebo z).
- **From the analyst, an instrument pass worth a dispatch**:
  insider_parse.py joins the universe on ticker symbol; quantify the
  coverage error on the 2021–2026 panel (bounded job — the 2016–2020
  measurement is 4,106 missed / 1,048 aliens).


## 2026-08-22 — STATE from run-validator-settling (three settling measurements), appended by the chair

- **J1 (R27-vs-G2): CANNOT TELL on level, SETTLED on design.** Admissible
  fills = 4 (immediate/RTH/alpaca) + 1 marginal; pooled frac mean +0.663 sd
  1.478 CI [-1.69,+3.02]. **Measurement error on an effective spread is ONE
  TICK regardless of name** ($0.0120 residual sd vs $0.0100 tick, constant
  across 56x price range, n=5) — so precision on pi scales with DOLLAR
  spread, not bps. Fills for +/-0.25: MSFT-midday 6, SPY-midday ~89,
  penny-tick name ~355. Both seats' sizing is on the wrong axis; the value
  is in the FREE spread data (cost = pi x spread), fills are second-order.
  CAVEAT I cannot close at n=5: additive-in-cents vs multiplicative
  residuals; the whole table rests on the former.
- **Every fill we own is FRACTIONAL** (0.052-2.75 shares) → internalised,
  not lit-book; whether pi transfers to whole-share flow is untested and I
  cannot test it.
- **J2: 38x reproduces (SPY 0.1299 bps @17:00Z), survives the open at 19.2x
  / 15.3x worst.** 9 of 14 names PINNED at the $0.01 tick with NO time-of-day
  curve. 5.00 is at/below the half-spread on 6 of 14 at the open — DO NOT
  LOWER, REPLACE per-name. "quoted half-spread in bps" is, for most of a
  realistic universe, half a tick over the price — a price-level statistic
  wearing a liquidity label.
- **J3: the premia inequality is CORRECT (rf cancels under arithmetic/GISW/
  continuous) and NOT SUFFICIENT.** Zero-skill monthly-rebalanced EW clears
  all three conditions in 18.2% of independent gate-length windows (4/22).
  Two of three conditions nearly free (vol<=bench 91/91 in two universes;
  bench-excess>0 92.8%). Sign flips with the window (buy-and-hold beats the
  rebalancer 1893% vs 934% over 2016-2026) — a single-window inequality is
  one draw, which is why the gate has four folds. condition (b) is
  UNMEASURABLE belt-wide: gate.py has 0 volatility fields (chair-verified).
- **RECORD GAP: 0 of 40 verdicts store benchmark_basis/kind/symbol/legs**
  (leanrunner computes all four at :1297-1302, gate discards) — no verdict's
  bar is auditable. Third write-only instance.
- **D1/D2 confirmed** (tca oldest-500 default 5.56 vs 4.95 at limit=5000;
  order 17d64dcd submitted=paper filed=alpaca, tca.py:212 prefers intent
  over execution). Both already staged R24/R23; D2 fix = swap precedence at
  tca.py:212 + a divergence flag.
- METHOD THAT PAID: read the PRODUCING code before trusting any summary —
  caught D1 and D2, neither of which was the assigned question. It is a
  GENERATOR of findings, not just a guard.


## 2026-08-22 — CARRIED FROM THE ADVERSARY (Entry 20) BY THE CHAIR

Your monthly-rebalance kill of the premia-sufficiency conjunction (18.2%
zero-skill pass) and the adversary's Dirichlet kill (83.4%) CONVERGE blind —
same verdict, different nulls. Two instrument defects the adversary found
that are yours to fold into the breakeven/analytics census: daily_returns
carries the DISCARDED engine benchmark (leanrunner :1370 vs the recomputed
:1291 bar; corr 1.0000 with SPY on an EW(SPY,TLT)-bar candidate) and runs on
a calendar-day clock (167 of 536 zeros, vol understated ~17%). Gate v5's
premia statistics consume this object, so when you next audit v5's
measurability, this is the field to check first — it is worse than "no
volatility computed"; it is "the wrong benchmark's volatility, computable."


## 2026-08-22 — CARRIED FROM THE READINESS MATRIX (PM) BY THE CHAIR

Gate discrimination D is now a STAGE-GATE, not just a finding: S4 full mandate is locked behind D>=0.75 and D sets w_g at every stage. When you re-measure D, report a CI and flag material change as a forced re-tune trigger — the number moves real notional and gates the top stage.


## 2026-08-22 — CARRIED FROM THE ADVERSARY (D11 v2) BY THE CHAIR

A standing consistency invariant worth a one-line property test: the
exit-coverage `_rule_is_live` predicate (exitrule.py:417) must filter EXACTLY
the flags enforce() skips (triggered_at, overridden_at) and no others - if
they diverge, coverage lies in one direction or the other. The D11 K2 remedy
added `superseded` to the filter and it was wrong precisely because enforce()
does not skip superseded. Pin coverage==enforce with a property test.


## 2026-08-22 — CARRIED FROM THE QUANT (Entry 20 belt run) BY THE CHAIR

1. `gate.py:405-412` makes `min_breakeven_bps` **unreachable** whenever the
sweep reports "still profitable at every cost tested": the gate writes a string
into the check and appends no failure. Your breakeven census counted verdicts
that read "cost robustness was never measured"; this is the opposite branch and
it is silent. Census how many of the 37 judged candidates took the string path
and passed a floor nobody evaluated.

2. Add a leg to your benchmark audit: `benchmark_dates[-1]` vs
`equity_dates[-1]`. `_add_benchmark` truncates to the shortest of N legs at run
time (leanrunner.py:1289, labelled at :1295 with the longest leg's dates), and
the quant measured an 11.85 pp over-credit (35% of the reported excess) from an
18-day gap that **had already healed 40 minutes later**. Non-reproducible by
construction, so it must be caught per-run, not by re-running.


## 2026-08-22 — CHAIR FINDING (while charting Entry 20 for the CEO)

`daily_returns.benchmark` in the candidate verification payload is UNUSABLE:
it compounds to +19.76% while `benchmark_curve` (the true series) shows
+84.78% on the same candidate (144387901688). The dict claims "907 aligned
daily observations, dropped_unmatched_days: 0" — so the alignment REPORTS
clean while the benchmark leg is deflated, likely absence-rendered-as-zero
on the calendar-daily grid. Anything that consumes daily_returns.benchmark
(vol ratios, active stats, IR) silently inflates the strategy. Add to your
benchmark audit: compound daily_returns.benchmark and diff it against
benchmark_return_pct — they must agree within rounding.


## 2026-08-22 — CARRIED FROM BUILDER D15 BY THE CHAIR

1. Belt results now carry `analytics.bar_snapshot.uniform_data_path` with
`misses[]` naming any leg that fell back live. Absent snapshot renders as
`{"taken": false}`, never as zero misses. Ask of every belt result: was this
measured on a uniform data path?
2. The vendor split (marketdata.py:381 — Yahoo for start+end calls, Alpaca
for lookback) means EVERY historical benchmark covered one session less than
its strategy curve. Your benchmark audit gains a leg: `benchmark_feeds` must
be single-vendor and match the strategy's.
3. Independent pass worth running: `/fund/marketdata/bars?as_of=` reads the
fund's own Postgres point-in-time archive at ~0.03s (60x the live path) and
NOTHING in the belt uses it — a candidate that should be reproducible is
reading a wall-clock-following window instead.


## 2026-08-23 — CARRIED FROM THE EXEC PAIR BY THE CHAIR

1. (Grace) Add to your instrument audits: **does this measurement have a consumer?** asof.py corrects a measured −6.90pp bias and has one consumer in the repo (a capture script) — a finding nothing reads reviews nothing, the register-of-notes lesson's sibling.
2. (Vishesh) When a recommendation of yours self-declares a loosening, file its adversary ticket in the same dispatch — your per-name slippage replacement was RETURNED for lacking one.
3. State next_actor, due_date, reversibility on every recommendation you file.


## 2026-08-23 — CARRIED FROM BUILDER D16 BY THE CHAIR

Gate v4.2 changes which candidates pass with NO threshold moved — any null-audit, power-audit or calibration figure computed under v4.1 now measures a different bar. **Re-run rather than compare; never put a v4.1 row beside a v4.2 row in one table.** Your reachable-criterion census gains a confirmed member: min_breakeven_bps was unevaluable-and-reported-passed — the register-of-notes pattern live inside the gate itself, not only judgement.py.


## 2026-08-23 — CARRIED FROM THE ADVERSARY (batch 2) BY THE CHAIR

`fund.py:688` computes `"diverges": broker is not None and broker != own` — an UNREADABLE broker day-trade count renders as AGREEMENT, not as unchecked. Add to your absence-as-value census (same shape as judgement's triggers_unchecked: [] and the bar_snapshot absent-as-zero-misses case); it is what made a downstream memo misread a null as a broker statement. Ticketed with the v4.2 repair batch.


## 2026-08-23 — CARRIED FROM PM R39 BY THE CHAIR

~Ten real Alpaca fills land Monday across $18.91–$765.55 — the price-stratified TCA sample you specified, free. **Design the tiers BEFORE the fills exist** (from the NBBO history Grace named) so the sample is judged against a pre-registered cut. Also: the venue reconciler NETS BY SYMBOL (a $362 two-sided SPY error rendered as $98 one-sided) — add lot-vs-symbol keying to your instrument audits; the custody projection (ticket filed) is the fix.


## 2026-08-23 — CARRIED FROM THE ADVERSARY (D17) BY THE CHAIR

A "control that cannot fire" has a second, cheaper signature: **an input the guard tests for PRESENCE that the producer ALWAYS supplies** (UNEVALUATED_ON_ABSENT unreachable because assess() always emits the key). When you audit a new guard, do not check that it fires in its test — check whether any REAL caller can reach the state it guards against. Same family as the meas+=1 unconditional-increment, one layer up.


## 2026-08-22 (~22:20Z) — CARRIED FROM THE ADVERSARY (D18 re-review) BY THE CHAIR

When you audit an instrument whose output is "all clear", ENUMERATE THE SHAPES ITS MATCHER CANNOT SEE before recording the clear — two guards on this branch report clean partly because of what they cannot parse (the order-event census; the retired-flag scanner matching only os.getenv with a Name base). A clean from a narrow matcher and a clean from a complete one are different measurements with different confidence.


## 2026-08-22 (~23:00Z) — CARRIED FROM THE CEO'S CATCH ON ED'S BATCH #1

FAMILY-WISE DISCOVERY RISK is now a named instrument question for you: the
gate's criteria bound each candidate's own overfitting; NOTHING bounds the
family (the more proposals tried per week, the higher the false-discovery
rate among gate survivors, mechanically). As generation throughput rises
toward 3-5/week, measure and propose: does the gate need a family-wise
adjustment (e.g., a stricter bar as tries accumulate, or a
discovery-rate ledger)? A funnel that speeds up without this becomes a
selection-effect factory with excellent paperwork.


## 2026-08-22 (~23:15Z) — CARRIED FROM ED (batch #1) BY THE CHAIR

A NEW FAILURE CLASS for your audits: **a registered value whose basis is "measured" but whose measurement was never re-taken after the world changed.** factory.py:39's floor asserts a data fact (chair-verified false: bars from 1993 on the live feed) — different from an unevaluable trigger, and nothing currently looks for it. Census the registered constants whose founding measurements are re-takeable in one call.


## 2026-08-22 (~23:50Z) — CARRIED FROM THE ADVERSARY (Entry 21 review) BY THE CHAIR — two measurement requests

1. **Measure the total-vs-active breakeven ratio across the stored candidate set** (two observed points: 2.0× and 1.35×) so the firm knows the bias its only cost criterion carries BEFORE anyone proposes moving the floor again.
2. **Publish what the fund can and cannot compute about its own execution cost** (quotes carry no bid/ask; a loosening was filed this week keyed to a quantity that does not exist). Both fold into your next dispatch.


## 2026-08-23 (~00:30Z) — CARRIED FROM DOC AND GRACE BY THE CHAIR

1. (Doc) The desk's event-study path has no unconditional-baseline requirement: the no-event 20-session t on the hunting-ground panel is +15.36. The belt is protected; nothing protects a memo. **"State the no-event baseline" is proposed for the artifact checklist — yours to adopt.**
2. (Grace) **mode.py's five precondition evaluators are your next audit target with money behind it**: two have evaluators (one unfenced — P1 reads met on pre-D11v2 mock fires), three have none. Attack her claim that exit_sign_fixed and kill_switch_wired are machine-checkable (suite/AST) before a builder acts on it.


## 2026-08-23 (~00:50Z) — STATE from run-validator-census5 (the five-census batch), appended by the chair

- **BREAKEVEN STRING PATH: 1 of 26** (exposure window v2 7c22e36 → v4.2 cbdf9cc; v2 ×5, v4 ×14, v4.1 ×7). The one: **144387901688, the fund's only substantive pass** — stored tested_range [0.0001,0.0005] → max 5.0 bps vs floor 10.0 → FAILS shipped v4.2. The other 25 took the branch that DOES append the failure sentence. The belt has 4 passes ever (3 = v1 nulls). Counted by CODE PATH, version-independent — never table v4.1 beside v4.2 as bars.
- **ABSENCE CENSUS: 61 mechanical sites, 14 adjudicated, 47 not (~30 defensible SQL aggregates) — the coverage bound stated.** HIGHEST-VALUE NEW: **PBO serves 0.0 from SIX sites on no-measurement paths** (a random-walk pair genuinely measures 0.6); folds[] is the discriminator and the cv projection discards it; the consumer at compose/page.tsx:490 wrote the correct '—' branch and the producer made it UNREACHABLE → green "0%" under "Overfitting Risk", one click from Save & Deploy. **NEW SUB-METHOD: when a consumer contains an absence branch, check whether the producer can ever reach it.** Also: fund.py:698 diverges (the CORRECT form is 13 lines above at :685 — one function, both patterns); fund.py:3007/:3497 attribution-absent-as-flat (the same dict comments the principle 3 lines later); **LATENT: pipeline.py:380/:456 writes avg_price 0 into ORDER_FILLED on an absent price — 0 of 34 fills affected, CP95 upper 10.3%**; all 29 fills carry fees=0, unfalsifiable from the log. CITE AS THE MODEL: fund.py:2362, riskmonitor.py:507-518, leanrunner.py:1528, health.py:135, stress.py:182.
- **REGISTER: 13 of 15 read-hooks read the CONSTANT** — drift detects an EDIT, never an ERROR. Only _wired() ×2 (judgement.py:325-347) reads the WORLD and raises → UNVERIFIED. **THAT IS THE FIX PATTERN.** WALKFORWARD_HISTORY_FLOOR claims "nothing to falsify; a fact about the data" and is FALSE BY 31.1 YEARS (SPY 8,448 bars from 1993-01-29, one call — note /fund/marketdata/bars caps lookback_days at 2000, use start_date). **A fact about the world is the MOST falsifiable entry, not the least.** TWO TRIGGERS FIRED AND REPORT NOT-DUE (min_effective_bets "grows past two names"; max_component_vol_pct "gains a third name" — book went 2→4 at DBA's first fill 2026-08-21T06:51:30Z; both limits advisory, read by nothing). 17/19 unevaluated, unchanged.
- **MATCHER PROBES (scratchpad/audit/matcher_probe.py)**: census blind to positional/kwargs/qualified/alias/variable shapes — realised at fund.py:2684 (variable aggregate_type continue'd while unreadable type IS surfaced — asymmetry in one function; right by luck); 27 positional Event() sites; scripts/adopt_alpaca_portfolio.py:69-79 is an order-event producer OUTSIDE the scanned tree (0 events so far, and it hardcodes fees 0.0). test_fund_mode.py:879: blind 5 of 7 shapes, swallows SyntaxError, **and its falsifier :917-925 tests a RE-IMPLEMENTATION, never the scan — the assertion-target defect inside a falsifier.** test_venue_ledger_decoupling.py:166: blind 6 of 8 BUT the missed shapes appear 0 times in app/ (house style os.getenv ×62) — **clean TRUE today, not guaranteed; the two confidences are different measurements.** The broad model: _executable_references (:62-88).
- **MONDAY TCA PRE-REGISTERED AND FILED** (docs/research/TCA_PREREG_2026-08-24.md, before the fills): tiers <$50/$50-250/≥$250 (3/5/3); **THE TICK NULL WRITTEN FIRST: under tick-pinning bps half-spread = 50/P exactly → 1.766/0.582/0.103 predicted — a 17× "finding" that is arithmetic**; primary statistic π (price-neutral); six causally-prior exclusions (rest>60s is CEO-click latency, NOT random by symbol); **power is highest in the EXPENSIVE tier (reverse of intuition); pre-declared verdict CANNOT TELL on level.** DAY-OF REQUIREMENT: NBBO at submit must be captured ON THE DAY or the π denominator is unrecoverable.
- **FAMILY-WISE, FORMAL: FDP = (1−π₀)α/[(1−π₀)α+π₀β] — INDEPENDENT OF K.** K multiplies the false-discovery COUNT; the RATE moves only through the marginal proposal's quality. At measured α=0.182/β=0.113: FDP 82.9% at π₀=0.25, 61.7% at 0.50. **EVERY margin tightening RAISES FDP** (α/β minimized at the shipped 2%/yr) — **DISCRIMINATION IS THE LEVER, NOT A STRICTER BAR.** Corollary: with β<α the expected pass rate DECREASES in edge prevalence — π₀ is not estimable from the pass rate, and passing the current gate is weak evidence AGAINST an edge. (MODEL of the instrument — r5 classes, 2000 draws — not a run; the 29-clean-nulls debt now also blocks belt-measured α/β, which stage-gate S4's D≥0.75 needs.)
- **GAPS carried**: fund_candidate_sources has 0 ROWS (no proposal/seat/family id on candidates — K countable, the FAMILY not; the discovery ledger is the missing instrument); sweep points enrich=False → no active breakeven for alpha claims; 0/40 verdicts store benchmark basis/kind/legs; no rf series (H1, the CEO's); Monday's NBBO capture.
- **METHOD THAT PAID AGAIN**: reading the PRODUCING code found PBO — not the assigned question. Second time the generator rather than the guard.

## 2026-08-23 - CARRIED FROM BUILDER D19 BY THE CHAIR

Your 2.9%->12.5% figure reproduces (3.03%/11.30%) but its MODEL does not match the shipped belt: gate_power_audit.py slides folds across all SESSIONS while window_for caps reach-back at train + test*(min_folds+1) with max_folds = max(min_folds, 6). When you simulate a gate criterion, drive the SHIPPED plan generator, never a loop that re-expresses it - the real geometry gave 6 folds where the model gave 12, and the shipped loosening (3.03%->6.87%) was invisible to the model. Reusable sim: scratchpad/fpsim.py. Next measurement worth having: the majority rule's PARITY effect at every fold count (3-of-4 = 31.2% under noise, 3-of-5 = 50.0%) - now the binding residual, and a CEO threshold decision.

## 2026-08-23 - CARRIED FROM THE ADVERSARY (D19 review) BY THE CHAIR

scripts/null_audit.py:132-143 reads WALKFORWARD_HISTORY_FLOOR raw while the belt (under any merged form of D19) reads factory.effective_history_floor. Before your next gate-calibration measurement, NAME which floor your harness used and check it against what the belt planned - otherwise the instrument that calibrates the gate's false-pass rate stops running the gate's geometry.

## 2026-08-23 - CARRIED FROM ED (batch #2) BY THE CHAIR

The +80.7 -> +39.56 non-reproduction is a live instance of desk-study numbers with no surviving script (cycle-1 Entry 11; correction section now on the doc). When auditing any desk figure that feeds a status - Entry 11's deferral rested partly on cycle-1 numbers - ask for the script, or treat the number as unverified until recomputed.

## 2026-08-23 - CARRIED FROM THE ADVERSARY (Ed batch #2 review) BY THE CHAIR

Two instruments enter your battery, both cheap, both reusable: (1) the CONSTANT-OBSERVABLE CONTROL for any conditional rule in the register (adv22/p1c.py is the harness); (2) the TRAILING-WINDOW LADDER (24/36/48/72/96m) as the standard replacement for author-chosen era splits - the E21 era-split check PASSED on both of these proposals while the ladder failed one. An era check that passes where the ladder fails is your next census candidate.
