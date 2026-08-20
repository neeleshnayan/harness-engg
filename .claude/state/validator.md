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
