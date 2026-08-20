# ADVERSARY VERDICT: KILL — gate v5 round 3

**Artifact attacked:** docs/GATE_V5_ROUND3_2026-08-20.md (+ scripts/gate_v5_audit_r3.py)
**Reviewer: adversary agent (blind), 2026-08-20. Third kill in the v5 chain.
Ran the committed script (all four reproduction commands reproduced EXACTLY)
plus eight of its own attack constructions (scratch copies; committed file
untouched). CTO verification note at the bottom.**

Three independent grounds, plus one honest negative in the doc's favour.

## GROUND 1 (fatal) — the premia criterion certifies a zero-edge insurance seller 6× more often than a real premia strategy, and no margin fixes it

The PROCESSES list contains one shape: beta × bench + iid Gaussian idio. The
proposed premia rule is a paired test-leg Sharpe — and Sharpe's known failure
mode is not beta, it is negative skew. Constructed: a **fair-priced insurance
seller** (collects p·L per day, loses L=15% with probability p=1/300; expected
excess exactly zero by construction; true 50-year Sharpe **0.01** vs the
asset's 1.02; **−1.09%/yr geometric**). Through the committed rules, unmodified,
at the proposed settings:

| process | v5_alpha | v5_premia (m=0.5) | v4_raw |
|---|---|---|---|
| baseline null_noise10 | 9.5% | 2.8% | 21.3% |
| step-beta 0.5→2.0 @mid | 18.8% | 1.0% | 30.8% |
| AR(1) idio ρ=.98, zero-mean | 13.0% | 31.9% | 16.5% |
| **fair short-vol, beta 0** | 40.3% | **74.4%** | 36.4% |
| fair short-vol, beta 1 | 36.5% | 44.0% | 24.6% |
| TRUE premia_defensive | 18.1% | 11.4% | 26.5% |

**72–75% vs a 12% true-positive rate**, stable across four seeds. The margin
axis — round 3's whole remedy — is orthogonal: at margin **2.0** (4× the
proposal) the zero-edge fake still passes **63.8% rising / 74.2% falling**
while the genuine premia passes 0.1%. The doc's falling-regime claim ("closed
by the margin") holds only inside the linear-beta family; outside it the
falling regime is WORSE (85.6%). This is the 2002 result (Goetzmann/Ingersoll/
Spiegel/Welch, NBER w9116; RFS 2007 manipulation-proof measures): Sharpe is
the statistic option-like payoffs are built to maximise — at a fund whose
declared business is selling insurance.

Decision arithmetic: at TP 12.0% / FP 2.25% (the doc's own best case), the
break-even prior for a PASS to be more-likely-true-than-false is **π = 15.8%**,
and the record puts the genuine-candidate base rate at 0-for-3 on the book.
A 12%-TP instrument is decorative not because 12% is low but because its
passes go majority-false against nulls it was never shown.

## GROUND 2 (fatal) — §3.3 and §5 rest on a table that cannot detect the defect it is named after

**(a)** `rule_v5_alpha:161` and `rule_v5_premia:175` increment `meas`
UNCONDITIONALLY, so `meas == len(folds)` always and the scaled floor
`_need = max(4, ceil(0.75·folds)) ≤ folds` can never bind. The fixed and
scaled columns are **arithmetically the same rule**, differing in print only
because the boolean sits in the seed tag. Proved under a shared rng stream:
185/185, 33/33, 3/3 of 2000 — identical at every n. The published "9.1% vs
9.4%" was Monte Carlo noise reported as a rule comparison; the script's own
caption describes a test that can never fire. *(CTO: confirmed by reading the
lines and re-running the proof.)*

**(b)** §3.3's premise — "v5 makes every fold measurable" — is falsified by
the belt: **11 of 53 walk-forward folds (20.8%)** are unmeasurable from
no-trade test legs and engine timeouts (MIN_TRAIN_RETURN_REVIEW:105), causes
the return SCALE cannot fix. And §3.4's "same function, excess series" reuses
`walkforward.retention()`, whose own semantics return `measurable: False` for
a sub-floor train leg — §3.1 and §3.4 cannot both hold. Re-run with
retention() semantics on the excess scale plus the belt's 20.8% dropout:

| n | folds | fixed-4 null FPR | scaled null FPR |
|---|---|---|---|
| 630 | 4 | 3.2% | 3.3% |
| 1260 | 12 | **12.5%** | 1.7% |
| 2520 | 27 | **15.3%** | 0.0% |

**The fixed floor loosens with history exactly as the register feared**, inside
a v5-shaped rule state — the exact inverse of §3.3's table. §5's unblocking of
`WALKFORWARD_HISTORY_FLOOR` rests on an unmeasured claim.

## GROUND 3 (serious) — "documented" documents the mildest member of the class

The 16.2% drift hole is one sampled member: step-shaped beta regime switches
reach 17.7–18.9%, and step + K=12 grid reaches **22.1%** vs an alpha TP of
29.6% (likelihood ratio 1.34, near coin-flip). `_make()` only interpolates
beta linearly, so regime switches were structurally unseeable. The class
maximum, not one member, is the hole's size.

## GROUND 4 (labelling) — two "correct verdict" labels contradict the constitution's own premia definition

alpha_S0.6 (measured 50y Sharpe 1.16) and alpha_S1.0 (1.33) deliver strictly
better risk-adjusted return than holding the asset (1.01) — premia by
CLAUDE.md's definition — yet are scored premia=fail, so their premia column is
counted as false positives, mis-pricing the margin sweep in both directions.
Defensible as a mutually-exclusive claim-type convention, but unstated.

## Honest negative — one §4 open item is measurably NOT a hole

Selection-statistic mismatch: re-deriving grid selection on excess or on
Sharpe, and K=12 vs K=4, moved v5_alpha null FPR by ≤1pp (7.9–10.2% vs 9.5%).
Vol clustering also benign (5.1%). Do not spend a round on it. §1's model
correction (v4_raw 21–30% vs the belt's 25%) reproduces and holds — with the
stated scope that it calibrates the LEVEL of null train returns, not the
SHAPE of null distributions, which is precisely Ground 1's axis.

## What would change the verdict

1. A premia criterion measured against a negative-skew battery (fair short-vol
   at several (p, L) points + zero-mean AR(1)) with the fake at or below the
   true premia's pass rate.
2. A history table whose fixed and scaled arms CAN differ (requires the rule
   state to change first), plus a written implementation commitment on fold
   measurability reconciled against walkforward.py:277-292 and the belt's
   11-of-53.
3. The beta-nonstationarity hole quoted at its class maximum over shape × K.
4. One sentence fixing the claim-type taxonomy, and the counts recomputed.

Attack scripts (scratch, committed file untouched): attack_A_scaling.py,
attack_B_nulls.py, attack_C2.py, attack_D2.py, attack_E_margin.py,
attack_F_labels.py, attack_G_class.py in the session scratchpad.

---

## CTO verification note (2026-08-20, at resolve)

Ground 2a verified two ways before accepting the kill: read the shipped lines
(161, 175 — `meas += 1` unconditional, exactly as claimed) and re-ran the
adversary's shared-rng proof (identical columns at every n, both rules).
Ground 1's construction verified by re-running attack_C2.py: the fair
short-vol null's true 50y Sharpe is 0.01 ± 0.15 with −1.09%/yr geometric — an
unambiguous null — and the reviewer's reproduction of the committed tables was
digit-exact, so its pass-rate tables are accepted. Round 3 is KILLED on the
criteria and the sequencing; §1's generator corrections survive into round 4.
The history-floor extension stays BLOCKED per the register.
