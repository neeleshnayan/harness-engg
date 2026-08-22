# PM — the graduated deployment path, sizing half

**Filed by the CTO chair from run `run-pm-graduated-sizing`, 2026-08-22.
Read-only. One half of an executive-table pair; the riskofficer holds the
bounding half (dispatched in parallel, blind). The PM's `## WHERE I DIFFER`
on the riskofficer is OWED next round — this memo is its independent view,
by design. Chair verification at the end.**

## TL;DR

The gate has never passed in 40+ tries not because it is strict but because
it is BLURRY (validator: discrimination 0.62 vs 0.5 coin-flip; adversary: a
zero-skill portfolio passes `must_beat_benchmark` 83%). This design turns a
gate CONFIDENCE into a notional, so a blurry gate stops being a pass/fail
wall and becomes a dial: low confidence buys a ~$135 measurement position,
full confidence buys the $500 sleeve. **While the gate is this blurry, early
size leans on the adversary's per-candidate verdict MORE than on the gate
score, by construction; the weight shifts to the gate only as its
discrimination is re-measured upward.** Nothing here deploys capital or moves
a threshold — it is an instrument the CEO sets the appetite on.

## Part 1 — confidence → size

**A composite confidence that degrades gracefully to the adversary when the
gate is blind:**

```
C   = w_g · G + (1 − w_g) · A
G   = gate score ∈ [0,1]   (coarse {0,0.5,1} until v5 makes it continuous)
A   = adversary  {KILL→0, CANNOT TELL→0.5, SURVIVES→1.0}
w_g = clamp( (D − 0.5) / (D_bar − 0.5), 0, 1 )   D = measured discrimination, D_bar = 0.75
```

Today D=0.62 → **w_g = 0.48**: the gate carries ~48% of the size weight, the
adversary ~52%. Below D=0.5 the gate carries zero — noise sized as noise. As
the gate sharpens toward 0.75, sizing shifts onto it.

**Confidence picks a TIER; the tier sets two caps:**

| Tier | Confidence | Sleeve cap | Tuition cap (loss at stop) | Notional @7% stop |
|---|---|---|---|---|
| 0 MEASUREMENT | < 0.35, not KILLed | 30% = $150 | 0.5% NAV = $9.43 | ~$135 |
| 1 PILOT | 0.35–0.55 | 50% = $250 | 1.5% NAV = $28.29 | ~$250 |
| 2 SLEEVE | 0.55–0.75 | 80% = $400 | 3.0% NAV = $56.57 | $400 |
| 3 FULL MANDATE | ≥ 0.75 | 100% = $500 ×throttle | stop × $500 | ~$394 after throttle |

**Confidence is a CEILING, not the size.** Actual deployed size is the MIN
across sleeve-fraction, tuition budget, capacity, order granularity, PDT,
throttle room and the riskofficer's envelope — **and the binding leg is named
on every deployment** (the quant's least-capacious-leg lesson, applied to
sizing).

**Hard floors that override the function (size = 0, no scaling):** adversary
KILL; no exit rule committed before entry; claim type not pre-committed; and
**Tier 3 requires D ≥ D_bar** — full mandate needs a gate that discriminates,
so an un-KILLed candidate is capped by the adversary alone at Tier 2. *"The
single most important line in the design."*

## Part 2 — the living re-tuning mechanism

**Cadence is evidence-driven, not calendar-driven**: re-tune every 5
closed/matured deployments, or quarterly if fewer close. Before moving any
tier break, measure the per-observation precision of realised-vs-predicted at
that tier and require the CI to actually separate the break (validator's
precision lesson). **Forced off-cadence triggers**: a realised loss breaching
its tier's assumed stop → tighten immediately; a 5% drawdown → freeze new
deploys to Tier 0; the fill count crossing the cost-model precision bar →
re-tune cost inputs; gate discrimination re-measured → re-tune `w_g`.
**Direction guard (anti-quiet-loosening):** any re-tune that INCREASES size
at a given confidence goes to the adversary blind then the CEO; any that
DECREASES size is immediate.

**Five dials become watched entries in `app/fund/judgement.py`:**
`SIZING_GATE_WEIGHT_D_BAR` (0.75), `SIZING_TUITION_TIER_PCT`
([0.5,1.5,3.0]%), `SIZING_CONFIDENCE_TIER_BREAKS` ([0.35,0.55,0.75]),
`SIZING_SLEEVE_FRACTION_CAPS` ([30,50,80,100]%), `SIZING_RECAL_CADENCE`
(5 deploys OR quarterly) — each with a `falsified_by` and a `review_trigger`.

## Entry 20 through the path — appetite set FIRST

Suppose Entry 20 clears with a decent G and the adversary at CANNOT TELL →
C lands in **Tier 1 (pilot), ceiling $250**. But the MIN does not clear
there: 40 slots × ($250/40) = **$6.25/slot** — whole-share names un-buyable,
fractional names signal-free noise under the per-order cost floor, and 40
positions turning every 3 days annihilates PDT (3 day-trades / 7 sessions).
**The binding leg is PDT + granularity, NOT confidence.** Honest output:
Entry 20 cannot pilot in its native 40-slot form — it needs a reduced-breadth
restructure (top-N by signal, staggered entries to survive PDT, held to the
mechanical ip+3 exit) before any size is set. **The tier caps were set before
Entry 20 was on the table and do not move for it.**

## NUANCES AND UNKNOWNS

1. **The adversary is also not a calibrated probability.** SURVIVES means
   "one attacker did not find the kill," not P(real) — so while D<D_bar,
   leaning on A is itself a weakness, which is why Tier 3 is locked behind
   D≥D_bar, not behind an un-KILLed verdict. *Unknown: whether D even reaches
   0.75 on v5; if it plateaus at ~0.62, this design permanently caps the
   alpha sleeve at Tier 2 — the correct, honest ceiling, not a bug to tune
   away.*
2. **Confidence→size is non-monotone** when capacity/cost-tier/turnover
   interact — the binding leg can change between pilot and sleeve size
   (Entry 20: PDT-bound at 40 slots, granularity-bound at 8, confidence-bound
   at 3). Re-derive it at each tier; never assume it carries.
3. **Small-size distortion — "worked small, size up" is unsafe.** Tier-0's
   job is fill-quality/realised-vs-predicted data, NOT a P&L verdict; you do
   not promote on Tier-0 P&L, and promotion is a new hypothesis tested at the
   destination tier's cost stratum. *Unknown: the cost model is n=3 honest
   today, so every stop-distance input to tuition is wide-error; early
   tuition caps are upper bounds, not point estimates.*
4. **Meta-calibration is the same sin one level up** — too-frequent re-tuning
   fits the dial to noise, too-rare is the frozen rule. N=5 is a judgement,
   registered with its own falsifier (dial moves then reverts = too eager;
   triggers fire while frozen = too slow). The recursion stops by human
   decision, not another dial.

## Recommendations (for the CEO's batch)

- **P1** — accept the four-tier ceiling function and its caps (CEO's risk-appetite dial). reversible.
- **P2** — accept that early size leans on the adversary (`w_g=f(D)`) and Tier 3 is locked until D≥0.75. reversible.
- **P3** — register the five sizing dials (CTO-chair action after CEO accept). reversible.
- **P4** — accept the evidence-driven cadence + forced triggers + direction guard. reversible.
- **P5** — when Entry 20 clears the belt, size via the MIN, record PDT+granularity as the binding leg, and request a reduced-breadth restructure before any pilot; do NOT lower a tier break to admit it. waits on the gate verdict.

---

# CHAIR VERIFICATION

`/fund/judgement` confirmed live: 19 entries carrying exactly the field shape
the PM cited (`falsified_by`, `review_trigger`, `registered_value`,
`trigger_spec`), so the five proposed sizing dials slot into a real
structure. The design is a proposal for the CEO's decision — it deploys
nothing and moves no threshold. The **executive-table engagement is
incomplete by design**: the riskofficer's bounding-envelope half is still in
flight, and the PM owes `## WHERE I DIFFER` on it next round — the PM itself
predicts the tension ("expect it on the Tier-3 cap and on whether the
adversary may carry ANY early size"). The two halves reach the CEO as a pair
only after that engagement; this is the independent view, filed first, which
is the discipline working, not a gap.
