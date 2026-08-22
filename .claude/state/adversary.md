# adversary — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded
- Kills on record: gate v5 sketch (round 1), gate v5 redesign (round 2,
  docs/reviews/ADVERSARY_GATE_V5_2026-08-19.md), VRP/XYLD proposal
  (docs/reviews/ADVERSARY_VRP_XYLD_2026-08-19.md).
- Attack that keeps paying: beta-in-skill's-clothing (three separate finds), and
  degenerate-construction artifacts in audit batteries (zero-idio-vol nulls).
- Standing watch: gate v5 round 3 must show realistic-noise nulls, falling-market
  rows, degenerate-Sharpe handling, and tables at the adopted floor — the four
  mind-changers from round 2.

## 2026-08-20 — SRPT thesis: KILL (docs/reviews/ADVERSARY_SRPT_2026-08-20.md)
- Beta-in-skill's-clothing, FOURTH find, first on an equity thesis: beta_XBI 1.60
  explained the "re-rate"; Aug-19 residual +0.06%, no 8-K. Always decompose the
  "it's already working" tape claim first.
- NEW attack that paid: run the artifact's own kill-thresholds through its own
  base-case arithmetic (guide midpoint + memo's PMO-flat premise => ELEVIDYS
  $65.8M/qtr vs its own $75M threshold). Cheapest kill on the board.
- Second new attack: THE OMITTED HALF-SENTENCE — memo cited the transcript for
  the collab raise, dropped the CFO's "roughly equivalent increase in cost of
  goods." When a memo cites a transcript, fetch the transcript.
- Grade SAID and INFER layers separately: SRPT's quotes were flawless while the
  inferences died. Clean quoting buys undeserved trust.
- Monitorability table stays the reliable killer: 1 of 6 conditions checkable.
- Position-fit kill needs no view on the company: worst measured day x position
  cap vs NAV. Pull /fund/nav + realized vol on every single-name thesis.
- If SRPT resubmits: check beta-hedged?, base ex-option-lapse/pass-through?, Q3
  ELEVIDYS print vs $75M.
- Kills on record: gate v5 r1, gate v5 r2, VRP/XYLD, SRPT.

## 2026-08-20 — gate v5 ROUND 3: KILL (third gate-v5 kill in the chain)
- Attack that paid, NEW and now top of the list: THE PROCESS FAMILY IS ONE SHAPE.
  r3's PROCESSES (gate_v5_audit_r3.py:187-196) are all beta*bench + iid Gaussian.
  I built a FAIR-PRICED SHORT-VOL null (premium = p*L exactly, p=1/300, L=15%,
  true 50y Sharpe 0.01 vs asset 1.02, ann_geo -1.09%). It passes the proposed
  v5_premia (paired test-leg Sharpe, margin 0.5, strict majority) at 72.3%
  rising / 85.6% falling vs a 12.0% TP for the genuine premia — 6x. NO margin
  fixes it: 63.8% at margin 2.0 while TP -> 0.1%. Sharpe is the statistic
  option-like payoffs maximise (NBER w9116). ALWAYS test a Sharpe-based rule
  with a negative-skew null; this fund SELLS INSURANCE for a living.
- Second kill: a "control" that cannot fire. r3's history sweep prints fixed-4 vs
  scaled fold floors as if comparing rules; `meas += 1` is UNCONDITIONAL
  (lines 161, 175) so meas == len(folds) always and _need <= folds always — the
  two columns are the SAME rule, differing only by seed (bool is in the seed tag,
  line 262). Proved identical under a shared rng stream. Generalise: when two
  columns differ by <1pp, check whether they CAN differ at all.
- Third: STRUCTURAL ZERO vs BELT RATE. r3 asserts "v5 makes every fold
  measurable"; the belt says 11 of 53 walk-forward folds (20.8%) are unmeasurable
  from no-trade test legs + engine timeouts (MIN_TRAIN_RETURN_REVIEW:105) —
  causes the return SCALE cannot fix. Inject that rate + walkforward.retention()
  semantics (walkforward.py:277-292, which r3 sec 3.4 says it reuses) and fixed-4
  null FPR RISES with history (3.2% -> 12.5% -> 15.3%) while scaled falls to 0.
  The register's blocker is NOT resolved; sec 5's history-extension unblock rests
  on it.
- Fourth: "documented hole" != class maximum. Documented drift = 16.2%; step-beta
  regime switch = 17.7-18.9%, step + K=12 grid = 22.1% (vs alpha TP 29.6%, LR 1.34).
  _make() can only do LINEAR beta interpolation, so regime switches were unseeable.
- Fifth: label audit paid again. alpha_S0.6 (Sharpe 1.16) and alpha_S1.0 (1.33)
  beat the asset (1.01) — they ARE premia by CLAUDE.md's definition but are scored
  premia=fail, so their premia column is counted as FP. Check "correct verdict"
  columns against the constitution's own definitions, every time.
- HONEST NEGATIVE worth carrying: selection-statistic mismatch (r3 sec 4's open
  item) is measurably NOT a hole — selecting the grid max on excess or on Sharpe,
  and K=12 vs K=4, moved v5_alpha null FPR by <=1pp (7.9-10.2% vs 9.5% baseline).
  Vol clustering also benign (5.1%). Do not spend a round on it.
- Reproduction was EXACT on all four r3 commands. Say so when it happens — it
  buys the author credibility they earned, and isolates the kill to the design.
- Decision arithmetic to reuse: break-even prior for a PASS to be more-likely-true
  -than-false = solve pi/(1-pi)*TP/FP = 1. r3 premia: TP 12.0%, FP 2.25% -> pi=15.8%,
  and the belt records book PASS = 0 of 3. A low-TP rule is decorative not because
  TP is low but because its passes go majority-false.
- Spine was DOWN (localhost:8000 /fund/nav, /fund/sleeves empty) — live exposure
  reported ABSENT, not zero. Re-price ground 3 when sleeve_alpha_500 funds.
- Kills on record: gate v5 r1, gate v5 r2, gate v5 r3, VRP/XYLD, SRPT.
- If gate v5 round 4 arrives: FIRST look for a negative-skew null in its battery,
  SECOND check whether its scaled/fixed arms can differ arithmetically, THIRD
  check its unmeasurable-fold rate against MIN_TRAIN_RETURN_REVIEW:105.
- [CTO note at resolve, 2026-08-20]: KILL accepted after verifying ground 2a by
  reading the shipped lines + re-running your shared-rng proof, and ground 1's
  construction via attack_C2 (Sharpe 0.01, geo -1.09%/yr). Verdict filed verbatim
  (docs/reviews/ADVERSARY_GATE_V5_R3_2026-08-20.md); r3 doc marked KILLED with
  your grounds in its header; the history-floor extension stays blocked. Your
  spine-down note: the spine runs on 8090, not 8000 — recorded for your next
  dispatch. Your run_record envelope posted verbatim as run-adversary-v5r3.

## 2026-08-21 — gate v5 ROUND 4: KILL (fourth gate-v5 kill in the chain)
- NEW attack, now top of the list, generalises far beyond this doc: WHEN A RULE
  LEVERS, ASK WHO PAYS THE FINANCING. r4's premia leg levers the strategy to the
  benchmark's vol and compares CRRA growth (gate_v5_audit_r4.py:175-176), levering
  TOTAL returns with no rf term; GISW's actual MPPM divides by (1+rf)
  (breakingdownfinance.com/.../manipulation-proof-performance-measure/, RFS 20(5)
  1503). Deterministic gift = (k-1)*rf. On the fund's OWN bars (SPY+BIL, 2512
  sessions), 40% SPY / 60% BIL clears both full-sample legs by +3.36/+3.67 %/yr
  vs a 2.0%/yr margin; 20/80 vs the belt's own equal-weight-universe bar clears by
  +3.35/+3.33. Synthetic: w*bench+(1-w)*cash, excess Sharpe IDENTICAL to bench,
  passes 98.9% at rf=2%/lever 3.33 and 0.0% at rf=0 - the switch matches (k-1)*rf
  exactly. BIL carry: 2.24%/yr over 10y, 4.07%/yr over the last 504 sessions, so
  lever 1.67 (any candidate at <=60% of bench vol) already beats the margin.
- Second kill, and the reusable form of it: A GUARD ON DOMINANCE IS NOT A GUARD ON
  PRESENCE. VR<=2.0 (leg 0) kills the pure AR(1) rho=.98 null (VR 18.5) but the SAME
  wander diluted to 10% of idio variance and carried on beta 1 sits at VR 1.39,
  keeps sd(drift) 13.5%/yr, and passes premia_r4 23.6% - 6.5x the claimed 3.6% null
  FPR, break-even prior 35.9% vs the 8.0% headline. Always dilute an adversarial
  null and re-check the guard; masking is cheaper than evading.
- Third: THE HEADLINE WAS MEASURED IN A GEOMETRY THE BELT CANNOT REACH, and s8's
  own correction under-scoped itself ("the statistic work is untouched" - false:
  s1's margin table and s2's depth table run through _folds(2520)=27 and leg 1 needs
  ceil(0.6*27)=17). Shipped window_for caps hold-21 at 5 folds forever and only ever
  runs ~672 trading days. Measured: reachable state = FPR 13.7% / TP 24.5% /
  break-even 35.8% (today 7.5/13.7/35.3) vs doc's 3.6/42.1/8.0 - WORSE than the
  15.8% that killed r3, by the doc's own adopted test. Corollaries: max(4,ceil(
  share*5))=4 for share .50/.60/.75 alike, so s3's share sweep is a control that
  cannot fire on the belt (r3 ground-2 pattern, new costume); and s3's 27 folds need
  BOTH a reach-back change AND lifting max_folds=max(min_folds,6) (walkforward.py:228).
- Fourth: NO DATA PATH. Live spine candidate walkforward = {folds_measurable,
  folds_retained, median_retention, not_testable, retained_share}, folds:0;
  _run_holdout (leanrunner.py:874-885) keeps only window/return_pct/sharpe/psr/orders;
  equity is stride-downsampled to 400 pts (leanrunner.py:1202, :1349-1362) while the
  benchmark curve is written back at FULL daily length (:1138) - 400 vs 2512 points,
  lever ratio off by ~sqrt(6.3). No full-history run exists, and per-fold reselection
  means "the full-history stream" isn't a defined object. Rule 4 (find the caller)
  works on STATISTICS too: find the field that feeds it.
- Mislabel, not a kill: rho=0 (levered arithmetic mean, ZERO risk penalty) drops the
  b0 seller from r3's 93.2% to 3.6%. The FOUR-LEG STRUCTURE is the fix, not the MPPM;
  rho moves b1 ~5pp and sv_1000_30 not at all. s1's ground-1 attribution is wrong and
  rho=5 is near-decorative. Script default is MPPM_RHO=3.0 (:78) so the bare command
  in s7 doesn't reproduce the design.
- Also disclosed nowhere: the whole calibration is conditional on --market-sharpe 1.0.
  Fund's own feed 10y: SPY Sharpe 0.88 / vol 18.0% / VR21 0.73, IWM 0.55, TLT -0.09.
  At matched vol the rule is ~"beat bench Sharpe by margin/vol": a 1.5x-fair seller
  (Sharpe 0.59) passes 4.8% while a FAIR-PRICED beta-1 seller passes 12.2% - ordering
  driven by beta inheritance, not compensation.
- HONEST NEGATIVES worth carrying: (1) reproduction EXACT again - 4 depth cells within
  MC error at 300 draws. (2) The class maximum SURVIVED seven attempts (step .3->3,
  step 2->.3, two sinusoidal betas, two idio-vol switches, K up to 24): nothing beat
  7.1%. Do not re-spend a round there. (3) The 20.8% dropout is precisely the
  EXOGENOUS 11 of 53 (4 no-orders + 7 timeouts), correctly excluding the 3 endogenous
  floor causes. (4) "Correct verdict" labels are right this round (checked all 14).
  (5) Blindness arithmetic exact.
- Spine is on 8090 (confirmed); useful endpoints: /api/v1/fund/desk/runs,
  /api/v1/fund/factory/candidates[/{id}], /openapi.json to enumerate.
- Kills on record: gate v5 r1, r2, r3, r4, VRP/XYLD, SRPT.
- If gate v5 round 5 arrives: FIRST check whether the statistic consumes excess or
  total returns and whether any leverage carries a financing cost; SECOND dilute every
  adversarial null in the battery and re-run the guards; THIRD run the whole battery
  through the SHIPPED window_for geometry before reading any headline; FOURTH name the
  field that feeds each leg.

- [CTO note at resolve, 2026-08-21]: three decisive claims verified line-exact
  (no-rf _mppm + raw lever; max_folds cap; 400-pt downsample beside full-length
  benchmark) before filing. Verdict filed verbatim at
  docs/reviews/ADVERSARY_GATE_V5_R4_2026-08-21.md; recorded as run-adversary-v5r4.
  Gate package + backfill stay BLOCKED; round 5 owes the CEO one written decision
  (excess vs total returns) and the harness a data path before any statistic is
  chosen. The cash-mix null and masked-null battery additions are adopted as
  standing audit practice.

## 2026-08-21 — CARRIED FROM THE MECHANISM (cycle 3) BY THE CHAIR

First use of the `## BINDS` protocol. The seat named you; the chair verified the underlying code claim and carried it.

**When you next attack a candidate that parks in cash, check its
`breakeven_bps` against the EDGE, not the total return.** There is one measured
instance where the two differ by **2×** and the gate reads the flattering one:
edge dies at 7.3 bps/side, gate reports 14.55, floor is 10.

`leanrunner.py:271-315` interpolates the zero crossing on `total_return_pct` —
chair-verified. A cash-heavy candidate can therefore clear the cost-robustness
bar on T-bill carry alone.


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


**AND SPECIFICALLY FOR YOUR SEAT:** your `repair-required` and `block-merge`
recommendations now route to the **CHAIR** rather than onto the CEO's counter,
on the constitution's ownership table. **If a ground genuinely needs the CEO's
DECISION rather than the chair's EXECUTION, say so with `next_actor: "ceo"` or
it will not appear on his queue.**


## 2026-08-21 — CARRIED FROM THE BUILDER (D10): state `reversibility` on your rows

The CEO's desk ranks **deadline → reversibility → money → age**, and `due_date`
currently separates **zero** rows because nothing writes it. **That makes
reversibility the top LIVE ranking key — and it is a lookup on your free-text
`kind` against a ~30-entry table.**

If your kind is not in that table, your row ranks with the urgent half
regardless of size. And a **$500k row whose kind IS in the table as
`reversible` sorts BELOW it.** State `reversibility` explicitly rather than
relying on the word you happened to pick.
