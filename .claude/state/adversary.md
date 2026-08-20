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
