# Gate v5, round 5 — the design, and why each change exists

**2026-08-21. Written by the CO-CTO chair on the CEO's explicit
instruction ("Lets close gate v5 so we can keep testing"), which overrides
this chair's Tier-3 parking of gate architecture. Fable: the override, its
reasoning and every judgement call are recorded here and in
CTO_REVIEW_QUEUE.md so you can audit it cold and reverse any of it.**

**STATUS: DESIGN ONLY. Nothing is adopted. This document specifies what
round 5 must measure; the measurement is dispatched to the validator, and
the result goes to the adversary blind before any adoption. Round 4 was
killed on four grounds and I am not repeating its mistake of arriving
with tables and a conclusion in the same artifact.**

---

## 1. What survived round 4, and must not be re-litigated

The adversary's round-4 verdict
(`docs/reviews/ADVERSARY_GATE_V5_R4_2026-08-21.md`) killed the round on
three demonstrated grounds plus an unmeasurability finding — and was
explicit about what it did NOT kill. Round 5 keeps all of it:

- **The four-leg structure.** Proven by the ρ=0 row to be what actually
  fixed round 3: at zero risk aversion the fair-priced seller still falls
  from 93.2% to 3.6%. The structure does the work; the risk-aversion
  constant is near-decorative.
- **The `rule_v5_alpha` measurability fix** — `retention()` returning
  `measurable: False` with a named reason, so an unmeasurable fold is
  never a zero and never a free pass.
- **The taxonomy** (§5 of round 4) — sound and correctly applied.
- **The class maximum, 7.1%.** Seven constructed members failed to beat
  it (step 0.3→3.0, step 2.0→0.3, two sinusoidal betas, two idio-vol
  regime switches, K to 24). **Do not re-spend a round there.**
- **The 20.8% dropout provenance** — correctly the exogenous 11 of 53,
  excluding the three endogenous floor causes.

## 2. The four grounds, and the change each forces

### G1 — financing. THE ONE THAT MATTERS MOST.

`_paired_mppm` levers the strategy to the benchmark's realised vol and
compares CRRA growth on **total** returns with no risk-free divisor
(`gate_v5_audit_r4.py:128-143`, `:175-176`). The cited measure
(Goetzmann/Ingersoll/Spiegel/Welch) divides by (1+rf). The deterministic
gift is **(k−1)·rf per year** against a 2.0%/yr margin — so on the fund's
own bars a zero-skill 40% SPY / 60% BIL sleeve cleared both full-sample
legs by +3.36 and +3.67 %/yr.

**Round 5 change**: every leg computes on **EXCESS returns with financing
charged on leverage**. This is not a modelling preference; it is the
constitution as amended by the CEO on 2026-08-21: *"'risk-adjusted' is
measured over EXCESS returns — above the risk-free rate, with financing
charged on any leverage… Every gate round from v5r5 onward must consume
excess returns end-to-end."*

Concretely: a levered position returns `rf + k·(r − rf)`, not `k·r`. Where
`k` is the vol-match multiplier, the levered excess stream is
`k · (r − rf)` and the MPPM is computed over `1 + rf + k·(r − rf)`.

**This also settles the mechanism's defect D4 from the other side.** D4:
under excess returns Sharpe is invariant to constant leverage, so a
long-only de-risking rule cannot be a premia claim. Two seats reached the
same arithmetic independently, blind, from opposite sides of the gate —
the judge saying "free leverage certifies T-bills as skill", the proposer
saying "charged financing means de-risking earns nothing". Round 5 must be
consistent with both.

**Acceptance test for G1, and it is the round's headline**: the cash-mix
family — `w·benchmark + (1−w)·T-bills`, whose excess Sharpe is identical
to the benchmark's **by construction** — must pass at approximately the
benchmark's own rate at EVERY w and EVERY rf. Round 4 passed it 98.9% at
rf=2% / lever 3.33 and 0.0% at rf=0. If round 5 still shows an rf
dependence, financing is still not charged and the round is dead again.

### G2 — the masked wander. The guard tests dominance, not presence.

`_vr21 ≤ VR_MAX` kills the pure AR(1) ρ=.98 null (VR 18.5) but the same
wander diluted to 10% of idio variance and carried on beta 1 sits at
**VR 1.39** — inside the ceiling, below real SPY's neighbourhood — keeps
13.5%/yr of spurious drift, and passed the premia rule **23.6%** of the
time on a zero-mean process.

**Round 5 change — and I am deliberately NOT proposing a cleverer guard.**
The adversary's suggested fix (a variance ratio on the beta- and
noise-filtered residual) is a real candidate, but inventing a new
statistic in the same round that fixes financing is how round 4 got four
grounds instead of one. Round 5 does two things instead:

1. **The masked family joins the standing battery** as first-class nulls,
   at the dilution levels the adversary demonstrated (w ∈ {1.0, 0.25,
   0.10, 0.05} × β ∈ {0, 1}), so every future round is measured against
   them by default. Adopted from the adversary's own recommendation 5.
2. **The decision arithmetic is reported against the CLASS MAXIMUM, not
   the battery mean.** Round 4's headline 3.6% FPR was an unweighted
   average over eleven processes, two of which the guard zeroes by
   construction. A gate is chosen by its worst plausible null, not its
   average one. If the masked family is the new worst member, the
   break-even prior must say so out loud.

**If the masked family still passes above the class maximum after G1's
financing fix, round 5 reports that as a survival, not a pass.** The
honest outcome may be "the premia rule needs a residual-based guard, and
here is the measured hole" — which is a complete result and the right
input to round 6.

### G3 — geometry. Every table runs through the SHIPPED generator.

Round 4's headline tables ran through `_folds(2520)` = **27 packed
folds**, while the shipped `window_for_strategy` fixes reach-back at
`train + test·(K+1)` (`walkforward.py:223`) and caps at
`max_folds=max(min_folds, 6)` (`:228`) — a 21-day hold gets **5 folds and
~672 trading days, forever, at any backfill depth.** In the reachable
state round 4 measured FPR 13.7% / TP 24.5% / break-even **35.8%** —
worse than the 15.8% that killed round 3, by round 4's own adopted test.

**Round 5 change**: there is exactly one fold generator, and it is
`app.fund.walkforward.window_for_strategy`, imported and CALLED — never
re-implemented in the audit script. Any table measuring a *proposed*
generator must be labelled as such in its own caption. Adopted from the
adversary's recommendation 3.

**Corollary already measured, carried forward**: `max(4, ceil(share×5))`
= 4 for share 0.50, 0.60 AND 0.75, so round 4's share sweep chose among
values identical on the belt. Round 5 must not present a sweep over a
constant that cannot bind; either the share leg binds on the shipped
geometry or it is reported as inoperative.

### G4 — the data path. CLOSED, and this is what unblocks the round.

Round 4 could not be computed at all: no per-fold daily return series
existed, `_run_holdout` kept only scalars, and equity was stride-sampled
to 400 points against a full-length benchmark curve.

**Builder dispatch 7 shipped it and it is merged** (commit `76784c2`,
"Gate data path: aligned daily returns, undownsampled"): series computed
in `_parse_results` immediately BEFORE the downsample, aligned by DATE
rather than index, days present on only one side dropped and counted
rather than zero-filled, non-positive levels breaking the chain rather
than dividing, and `runanalytics.daily_return_legs()` as the reader that
**names what was not captured**.

**Two limits round 5 must respect rather than paper over:**
- **Only the out-of-sample legs are captured.** Train legs carry no daily
  series — their jobs are released after the grid runs. Round 5's
  full-history legs must be computed from what exists, and any leg that
  cannot be must be reported unmeasurable, not approximated.
- `dropped_unmatched_days` is normally 0 but a dropped day makes the next
  return a two-day return wearing a daily label. Any volatility computed
  from these series must read that field and say so.

## 3. What round 5 must produce

1. **The cash-mix acceptance test** (G1's headline) — pass rates across
   w and rf, with the prediction stated in advance: no rf dependence.
2. **The battery, including the masked family**, run through the shipped
   geometry, reporting the **class maximum** alongside the mean.
3. **The decision arithmetic** — FPR, TP, break-even prior — computed in
   the reachable state and only the reachable state.
4. **The measurability accounting** — how many legs were computable from
   the real data path, and which were not, by name.
5. **An explicit verdict on whether the premia rule is adoptable**, and if
   not, the named hole and what round 6 would have to fix.

## 4. Judgement calls I made, so Fable can reverse any of them

1. **Fix financing, not the guard, in this round.** Two structural
   changes in one round is what produced four grounds last time. The
   masked family becomes a measured, standing null instead — so if the
   guard is still holed, round 5 *reports the hole* rather than papering
   it with an untested statistic.
2. **Report the class maximum as the headline, not the mean.** A gate is
   chosen by its worst plausible null. Round 4's mean diluted with
   battery composition.
3. **ρ stays at 5 and is explicitly labelled near-decorative** — the ρ=0
   row proves the four-leg structure does the work. Adopting ρ=5 as
   load-bearing would be adopting a constant that isn't.
4. **Design and measurement are separated on purpose.** This document
   specifies; the validator measures; the adversary attacks the result
   blind. Round 4 arrived with its own tables and its author's
   conclusion in one artifact, and the tables were honest measurements of
   the wrong thing.
5. **`--market-sharpe 1.0` must be disclosed as a conditioning
   assumption** in every round-5 table. Round 4's entire calibration
   depended on it and said so nowhere; the fund's own feed gives SPY
   0.88, IWM 0.55, TLT −0.09 over the same ten years.

## 5. What this does NOT do

It does not adopt a gate. It does not move a threshold. It does not
unblock the `WALKFORWARD_HISTORY_FLOOR` change or the 10-year backfill —
those remain ONE package with the window-function change and the
`available` definition, and that package is unchanged by this round.
Nothing here touches `app/fund/gate.py`, `judgement.py`, or any registered
value.
