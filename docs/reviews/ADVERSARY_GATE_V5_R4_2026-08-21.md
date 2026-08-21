# Adversary round 4 — gate v5 — KILL (filed verbatim)

**Blind review, 2026-08-21. Artifact attacked: docs/GATE_V5_ROUND4_2026-08-20.md
(including its §8 correction). Field evidence admitted: the three gate-related
recommendations on run-quant-entry11 and docs/research/QUANT_ENTRY11_2026-08-21.md.
The reviewer saw the artifact and the field evidence, never the author's
reasoning. Filed verbatim below; CTO verification note at the end.**

---

## TL;DR

The round-4 premia gate can be passed, at ~99%, by a portfolio that is part
index fund and part Treasury bills — no skill at all — because the design
levers a strategy up to the benchmark's volatility without charging it the
cost of borrowing. I demonstrated this on the fund's own real SPY/BIL price
history using the design's own code. Two further legs fail: the new
"structure guard" is defeated by mixing the same lucky-drift process with
ordinary noise (a zero-edge process then passes 23.6%), and the headline
pass/fail rates are measured in a fold layout the belt cannot produce — in
the layout it actually can reach, the decision arithmetic comes out worse
than the version that was killed last round. Separately, nothing in the
harness records the daily return series this rule needs, so it cannot be
computed today at all. Verdict: KILL. No human decision is needed beyond not
adopting this as v5's premia criterion yet; the four-leg *structure* is a
genuine advance and is worth rebuilding on.

---

**Overall verdict: KILL** (fourth in the chain). Three independent grounds,
each demonstrated by execution, plus one unmeasurability finding.

Reproduction fidelity first: four depth cells re-run at 300 draws landed
within Monte-Carlo error of the doc's 1000-draw figures (39.0/11.7/0.0/10.0
vs 42.1/12.6/0.0/8.9). The tables are honest measurements of what the script
computes. The kills are about **what the script computes not being what the
doc claims it is, or not being reachable on the belt.**

## GROUND 1 — KILL. Vol-matching levers TOTAL returns, so any cash-heavy portfolio is certified as premia

`_paired_mppm` levers the strategy to the benchmark's realised vol
(gate_v5_audit_r4.py:175-176) and `_mppm` (:128-143) computes
`ln E[(1+r)^(1-rho)]` with **no risk-free divisor**. The cited measure
(Goetzmann/Ingersoll/Spiegel/Welch, RFS 20(5) 1503) divides by (1+rf).
Levering a return stream by k is credited with k·r when the financed
position earns rf + k·(r − rf). **The deterministic gift is (k−1)·rf/yr**
against a 2.0%/yr margin.

Measured on the fund's own feed (2512 aligned SPY/BIL sessions,
2016-08-23 → 2026-08-20): a 40% SPY / 60% BIL sleeve — zero skill by
construction — clears both full-sample legs by **+3.36 and +3.67 %/yr**.
Against the belt's own equal-weight declared-universe bar
(leanrunner.py:1076-1094), 20/80 SPY/BIL clears by +3.35/+3.33. BIL's
measured carry: 2.24%/yr over 10y, **4.07%/yr over the last 504 sessions** —
at the recent carry, any candidate at ≤60% of benchmark vol clears the
entire margin on the omitted term alone. Synthetic confirmation: a cash-mix
whose excess Sharpe is IDENTICAL to the benchmark's passes 98.9% at
rf=2%/lever 3.33 and 0.0% at rf=0. `MAX_LEVER = 10.0` (:81) is the only
bound on the gift and appears nowhere in the doc.

What would change the verdict: the belt feeding the gate excess returns, or
`_paired_mppm` levering `rf + k(r − rf)` — neither is true anywhere. Or a
written, versioned CEO decision that "risk-adjusted" deliberately means
rf=0 — under which the gate's honest conclusion is that the premia sleeve
should hold T-bills.

## GROUND 2 — KILL. VR ≤ 2.0 guards dominance, not presence

The guard (_vr21, :196-211) kills the pure AR(1) rho=.98 null (VR 18.5) but
the SAME wander diluted to 10% of idio variance and carried on beta 1 sits
at **VR 1.39** — inside the ceiling, below real SPY's neighbourhood — keeps
13.5%/yr of spurious drift, and passes the premia rule **23.6%** of the
time on a zero-mean process: 6.5× the claimed 3.6% null FPR, break-even
prior 35.9% vs the 8.0% headline. The masked shape (beta 1 + slow idio
component) is what any long-market strategy with slowly-varying exposures
looks like. The alpha rule is more robust (4–6%) at every row.

## GROUND 3 — KILL. The headline was measured in a geometry the belt cannot reach

§8¶4's claim that the statistic work is generator-independent is wrong:
§1's margin table and §2's depth table run through `_folds(2520)` = 27
packed folds, and leg 1 requires ceil(0.6×27)=17 measurable. The shipped
`window_for` fixes reach-back at train + test·(K+1) (walkforward.py:223)
and caps at `max_folds=max(min_folds, 6)` (walkforward.py:228): a 21-day
hold gets 5 folds and ~672 trading days FOREVER, at any backfill depth.
Re-measured in the reachable geometry: **FPR 13.7% / TP 24.5% / break-even
prior 35.8%** (today, floor 2024-02-26: 7.5/13.7/35.3) against the doc's
3.6/42.1/8.0 — worse than the 15.8% break-even that killed round 3, by the
doc's own adopted test. Corollaries: `max(4, ceil(share×5))` = 4 for share
0.50/0.60/0.75 alike, so §3's share sweep chooses among values identical on
the belt (the r3 ground-2 pattern in a new costume); and §3's 27-fold row
needs BOTH a reach-back change AND the max_folds cap lifted — §8 names only
the first.

## GROUND 4 — CANNOT BE COMPUTED. No data path exists for any leg

Verified at three levels: the live candidate walkforward carries five
scalars and `folds: 0`; `_run_holdout` (leanrunner.py:874-885) keeps only
window/return_pct/sharpe/psr/orders per leg; and where a curve exists,
strategy equity is stride-downsampled to 400 points (leanrunner.py:1202,
_downsample2 :1349-1362) while the benchmark curve is written at FULL daily
length — 400 vs 2512 points, a vol-ratio lever wrong by ~√6.3. No
full-history engine run exists, and per-fold parameter reselection means
"the full-history stream" is not a defined object. Adjacent (quant field
evidence): the benchmark is struck on yahoo while returns trade alpaca
closes — a paired daily vol ratio does not tolerate a two-feed comparison.

## Ground 5 — mislabel, not a kill: the MPPM is not what fixed round 3

At rho=0 (levered arithmetic mean, ZERO risk penalty) the fair-priced b0
seller still falls from r3's 93.2% to 3.6% — the four-leg structure is the
fix; rho=5 is near-decorative (moves b1 ~5pp, sv_1000_30 not at all). The
script default is MPPM_RHO=3.0 (:78), so §7's bare reproduction command
does not reproduce the design. Undisclosed: the whole calibration is
conditional on --market-sharpe 1.0; on the fund's own feed SPY's 10y Sharpe
is 0.88 (IWM 0.55, TLT −0.09), and at matched vol a fair-priced beta-1
seller passes 12.2% while a 1.5×-fair-priced genuine insurance edge passes
4.8% — ordering driven by beta inheritance, not compensation.

## Honest negatives (attacks that did NOT land)

The class maximum survived seven constructed members (nothing beat 7.1%).
The 20.8% dropout provenance is precise (the exogenous 11 of 53, correctly
excluding endogenous floor causes). All 14 correct-verdict labels check out
against the constitution. The blindness arithmetic is exact. Reproduction
was exact.

## What survives, and is worth keeping

The four-leg structure (per-fold majority + two full-sample legs at two
horizons) — proven by the rho=0 row to be what actually killed the round-3
seller. The v5_alpha measurability fix. The taxonomy. The disclosed 46.9%
v5_alpha hole (which also means §7's alpha limb is unmeasured and cannot be
adopted as specified).

None of this argues the premia gate should be harder: grounds 1 and 2 are
the gate passing what it should not, and ground 3 says it is weaker in
practice than advertised. Fixing these should raise deployable throughput.

---

## CTO verification note (2026-08-21, at resolve)

Three decisive claims verified line-exact before filing: (1)
gate_v5_audit_r4.py:128-143 — `_mppm` computes on raw `1+r` with no
risk-free divisor, and :175-176 levers `lever * x` with no financing term,
exactly as charged; (2) walkforward.py:223,228 — reach-back
train+test·(K+1) and `max_folds=max(min_folds, 6)`, so the 27-fold geometry
behind the headline tables is unreachable on the shipped code, as charged;
(3) leanrunner.py — `_downsample2(equity, dates, 400)` beside a full-length
`benchmark_curve`, as charged. The reviewer also reproduced the doc's own
tables within Monte-Carlo error before attacking them, and recorded seven
attacks that failed — both marks of the standard this seat is held to.
Consequences executed at resolve: gate v5 round 4 is DEAD as a criterion;
the WALKFORWARD_HISTORY_FLOOR change and 10y backfill REMAIN BLOCKED (the
one-package rule now needs a round 5 that also scopes the data path); the
round-5 prerequisites are the adversary's four named checks plus one CEO
decision (excess-vs-total returns) now on the desk via the run record. The
kill arithmetic favours the north star: every ground found here is a way
the fund could have deployed premia capital into nothing.
