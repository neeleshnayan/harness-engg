# Gate v5, round 5 — MEASURED. Financing fixed; the rule is NOT adoptable.

**Measured by the validator on the co-CTO chair's dispatch, 2026-08-21 (UTC),
against `docs/GATE_V5_ROUND5_DESIGN_2026-08-21.md`. Filed by the chair.
Findings docs are never edited — a re-measurement gets a new file.**

**CHAIR VERIFICATION performed before filing (working protocol 2):**

- `GATE_VERSION = "v4.1"` at `app/fund/gate.py:157` — confirmed. The claim that
  no issued verdict is retrospectively affected stands: no verdict has ever
  used a v5 premia statistic.
- `scripts/gate_v5_audit_r5.py` exists (39,792 bytes) and
  `scripts/gate_v5_audit_r4.py` is **untouched** — `git status --porcelain
  scripts/` shows only `?? gate_v5_audit_r5.py`, no modification to r4. The
  never-edit-a-findings-instrument discipline held.
- **`select count(*), count(analytics) from fund_candidates` → `37 | 0`** —
  confirmed directly against Postgres. Zero of thirty-seven candidates carry
  captured analytics. Round 5 is a model of the instrument, not a run of it,
  exactly as the validator states.

---

## The headline

**G1 (financing) passed its acceptance test and could not be reopened.** On the
fund's own SPY/BIL history a zero-skill cash-and-index mix now scores exactly
zero at every cash weight and every rate assumption, where the round-4 rule
handed it up to +35%/yr of free money.

**The premia rule is still NOT adoptable**, on two measured grounds — and
neither is a threshold that is set wrong.

## 1. G1 — financing. PASSED.

Prediction stated in advance: the cash mix `w·bench + (1−w)·rf` has excess
stream exactly `w ×` the benchmark's, so after vol-matching its paired MPPM is
identically zero at every `w` and every `rf`.

Real SPY vs real BIL, 336 concatenated OOS sessions 2025-02-26→2026-06-25, ρ=5,
**no `--market-sharpe` assumption enters this table**:

| w | r5 excess, daily | r5 excess, 21d | r4 total, daily | r4 total, 21d | lever |
|---|---|---|---|---|---|
| 1.00 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.00 |
| 0.80 | 0.0000 | 0.2412 | 0.9794 | 1.2292 | 1.25 |
| 0.60 | 0.0000 | 0.4888 | 2.6126 | 3.1181 | 1.67 |
| 0.40 | **0.0000** | 0.7427 | **5.8814** | 6.6358 | 2.50 |
| 0.20 | 0.0000 | 1.0026 | 15.6999 | 16.5404 | 5.00 |
| 0.10 | 0.0000 | 0.8944 | 35.1126 | 34.9716 | 10.00 |
| 0.05 | −1.7628 | −3.8808 | 33.2481 | 30.3447 | 10.00 |

(%/yr. SPY 19.79%/yr, BIL 3.97%/yr, benchmark excess Sharpe 0.86 over this window.)

Monte Carlo, same geometry and seeds, 4 cash weights × 4 constant rf, 2,000
draws each: **r5 statistic 0.0% in all 16 cells** — `0 of 2000` bounds each
cell below **0.2% at 95% confidence** (Clopper-Pearson), not a claim of zero.
The **same cells through r4's statistic: 0.0% at rf=0, then 33.0–38.7% at
rf ∈ {2,4,6}%**, and `cashmix_w0.40` passes **98.6% conditional on the
walk-forward test running** — an independent reproduction of the adversary's
98.9%, in the geometry the belt can actually reach.

`MAX_LEVER=10` under excess returns **under**-levers (w=0.05 reads −1.76) —
conservative, the opposite direction from round 4.

**The 21-day residual is convexity, not financing.** At w=0.80 it reads
0.2667 / 0.2385 / 0.2136 at rf = 0 / 4 / 8%: it moves with `w`, barely with
`rf`, and *falls* as rf rises — the signature of daily-rebalancing convexity.
Maximum magnitude **1.11%/yr at w=0.20**, below the 2.0%/yr margin. It becomes
a live zero-skill pass if the margin ever drops below ~1.1%/yr, and the margin
decision must carry that fact.

## 2. H1 — THE NEW BLOCKING HOLE: no risk-free series exists in the gate path

The invariance above holds **only when the rule's rf is the rate the cash leg
actually earned.** A grep of the harness finds no risk-free series anywhere in
the gate path. The rule would have to assume one. Measured (cash leg earns real
BIL, rule assumes a constant):

| w | rf_a=0.0% | rf_a=2.0% | rf_a=4.0% | rf_a=5.0% | break-even rf error |
|---|---|---|---|---|---|
| 0.80 | 0.979 | 0.484 | −0.002 | −0.242 | 8.00% |
| 0.60 | 2.613 | 1.290 | −0.007 | −0.646 | 3.00% |
| 0.40 | **5.881** | **2.904** | −0.016 | −1.455 | 1.33% |
| 0.20 | 15.700 | 7.748 | −0.053 | −3.898 | 0.50% |
| 0.10 | 35.113 | 17.311 | −0.159 | −8.774 | 0.22% |

Closed form: the gift is `((1−w)/w)·(rf_true − rf_assumed)` %/yr; break-even
error is `margin·w/(1−w)`.

1. **rf_assumed = 0 reproduces round 4 exactly.** "Excess returns" is not a fix
   by itself — it is a fix *conditional on an rf source*. Ship v5 with an
   implicit zero and the adversary's Ground 1 is back, unchanged.
2. **A plausible static assumption is not safe.** rf=2% as a "long-run average"
   certifies a zero-skill 40/60 mix at +2.90%/yr against a 2.0%/yr margin.
3. **The cash proxy is NOT the risk.** BIL 3.97%/yr vs SHV 3.94%/yr over the
   same window — 0.03%/yr, three orders below the break-even error at any usable
   `w`. The risk is *static vs realised*, not *which bill fund*.

## 3. H2 — discrimination is below a coin, and no margin fixes it

Shipped geometry (`window_for_strategy` **imported and called**, live floor
2024-02-26 → 4 folds, 84-day test legs, 336 OOS sessions), 2,000 draws, ρ=5,
margin 2.0%/yr, **benchmark excess Sharpe 1.0 (ASSUMED)**, rf = real BIL,
dropout 20.8%.

**Nulls n=19. CLASS MAXIMUM 18.2%** (`sv_1000_30_b0`, the rare-disaster
seller), CP95 [16.5%, 20.0%]. Unweighted mean 6.1%, printed only for
comparability with round 4's headline.

| FPR basis | FPR | TP (premia_defensive) | break-even prior | **discrimination** |
|---|---|---|---|---|
| class maximum | 18.2% | 11.3% | **61.8%** | **0.62**, CI [0.53, 0.72] |
| class max excl. blindness class | 10.2% | 11.3% | 47.4% | **1.11**, CI [0.93, 1.32] |
| battery mean | 6.1% | 11.3% | 35.1% | 1.85 |
| class maximum, oracle SR 2.5 as TP | 18.2% | 25.9% | 41.4% | 1.42, CI [1.26, 1.60] |

**Discrimination 0.62 with a 95% CI excluding 1.0: at the class maximum the
worst plausible null passes MORE OFTEN than the designed premia claim.** Even
discarding the blindness class entirely — the most generous reading available —
it is 1.11 with a CI straddling 1. For scale: gate v3's 1.21 was judged "barely
distinguishable from a coin", and the benchmark-blindness fix moved v4 from 1.79
to 8.9.

**No margin fixes it** (1,500 draws, same geometry):

| margin %/yr | worst null | premia_defensive | oracle SR2.5 | disc. vs worst null |
|---|---|---|---|---|
| 1.0 | 21.2 | 13.0 | 26.5 | 0.61 |
| 2.0 | 17.3 | 12.0 | 27.3 | 0.69 |
| 3.0 | 18.8 | 10.2 | 26.4 | 0.54 |
| 5.0 | 17.7 | 8.6 | 21.7 | 0.49 |
| 8.0 | 16.6 | 4.3 | 24.1 | 0.26 |

Raising the margin costs the true claim and barely touches the worst null. This
is round 3's pattern in a new statistic.

**Before/after through identical geometry and seeds** (`--stat r4` vs default):
class max 39.8% → 18.2%, worst null moves from `cashmix_w0.40` (a pure financing
artifact) to `sv_1000_30_b0` (a blindness artifact), TP 15.1% → 11.3%,
discrimination 0.38 → 0.62. **The financing fix bought a real, measured
improvement — and left the round below a coin.**

### H3 — the mechanism: vol-matching is the amplifier

Median realised lever on the OOS stream (800 draws, no selection, no dropout):
`sv_1000_30_b0` **6.48** (p90 7.07), `premia_defensive` 1.72, `oracle_sr2.5`
1.99, beta-1 nulls ~0.9–1.0. A 3%-vol stream matched to a 20%-vol benchmark is
levered ~6.7×, turning a small event-free drift into a median +17.8%/yr.
**The statistic's own risk-adjustment mechanism is what promotes the worst
null.**

Unconditional distribution of the full-sample leg (1,500 draws, 336 sessions):

| process | p10 | median | p90 | P(> 2%/yr) |
|---|---|---|---|---|
| sv_1000_30_b0 | −47.3 | +14.3 | +55.9 | **61.7%** |
| masked_w0.10_b1 | −31.2 | −0.5 | +30.9 | 45.6% |
| premia_defensive | −10.0 | +2.8 | +13.9 | **53.5%** |
| oracle_b0_sr2.5 | −2.2 | +29.6 | +62.5 | 86.3% |
| cashmix_w0.40 | −0.00 | 0.00 | 0.00 | 0.0% |
| null_noise10 | −12.7 | −2.3 | +8.0 | 29.7% |

On 336 sessions the full-sample leg is a 53% coin flip for the genuine premia
claim and a 62% coin flip for the worst null. **The margin sits inside the
statistic's own noise band.**

Blindness bound: `P(0 loss events in 336 OOS sessions) = 71.5%` at p=1/1000
(91.9% within a single 84-day leg). This is not a statistic defect — no
backward-looking measure can see a risk absent from the sample. It is still the
number a gate is chosen by, because we cannot tell the two apart from a backtest.

## 4. H4 — the masked wander survives the round

Peak **10.2% unconditional / 26.0% conditional on running** — statistically
indistinguishable from round 4's 23.6%. The financing fix did nothing for it;
its apparent improvement is **entirely the starvation ceiling.** The design
deliberately deferred a residual-based guard rather than invent a statistic in
the same round that fixed financing; that deferral is now measured, and the hole
is real.

The VR guard is **not broken** where it can see: it kills 100% of *running*
pure-wander draws at w=1.00 and degrades to 3.2% caught at w=0.10/β=1, exactly
as the adversary showed.

## 5. H5 — the starvation ceiling

`gate.py:183` requires `folds_measurable >= 4`. At the live floor
(`factory.py:38`, 2024-02-26) the geometry supplies **exactly 4 — slack zero.**
At the measured 20.8% exogenous dropout, `P(≥4 of 4) = 39.3%`, so **60.7% of
candidates are never judged**; lifting the floor to the feed's start gives
`P(≥4 of 5) = 72.1%`.

Because it is common-mode it does **not** rescue discrimination: floor `none`
moves FPR 18.2→35.2% and TP 11.3→23.9%, and discrimination only 0.62→0.68.

## 6. H6 — G4 measurability: the data path exists and has never run

The path is code-complete (`76784c2`, merged 2026-08-21) and data-empty:

- Candidates on the belt **37**; with analytics captured **0**.
- Legs computable belt-wide: **0**. Missing by name: `verification` ×37,
  `holdout_test` ×37; absence reason `{'not_captured': 37}` on all 37.
- Postgres cross-check: `fund_candidates` 37 rows, `count(analytics)` = **0**
  — *independently confirmed by the chair.* Latest candidate finished
  2026-08-20T20:05Z, **before** the merge.

**A reporting defect found in passing, in the reader itself**: when analytics is
absent entirely, `daily_return_legs` names only `verification` and
`holdout_test` as missing, because `folds()` learns the fold count from the same
absent payload and returns `None` (`runanalytics.py:267-276`, `:312`). The
honest count is 2 + K per candidate (6 at K=4, i.e. **222 belt-wide**); the
reader says 74. **This is the same shape as the write-only verdict column — the
absence is under-reported by the thing whose job is to report absences.**

## 7. VERDICT

**The premia rule is NOT adoptable on this measurement.** G1 is fixed and stays
fixed; G3 is honoured; G2 and the decision arithmetic are not clear.

Named holes, in the order round 6 must take them:

- **H1 — no rf source (blocking, arithmetic).** The constitution's excess-return
  amendment is not implementable today.
- **H2 — discrimination below 1 at the class maximum (blocking, power).** No
  margin in 1.0–8.0 %/yr fixes it; raising it makes it worse.
- **H3 — vol-matching amplifies low-vol nulls (mechanism).** Round 6 should
  measure discrimination as a function of `MAX_LEVER` and of a lever-aware
  margin. **The highest-value single experiment left.**
- **H4 — the masked wander survives**, 26.0% conditional.
- **H5 — starvation and depth.** 4 folds with zero slack; 336 OOS sessions put
  the margin inside the noise band.
- **H6 — zero real legs.** A model of the instrument, not a run of it.

**Nothing retrospective.** `GATE_VERSION = "v4.1"`; stored verdicts are v1 ×11,
v2 ×5, v4 ×14, v4.1 ×3, null ×4 — no candidate has ever been judged by a v5
premia statistic. The only three passes on the entire belt are
`null_random_smallcap` under **v1**, the known v1 failure. The cost is
prospective, and it is a **leg-2/leg-3 cost, not a leg-1 one**: the premia sleeve
has had no criterion at all since the identity decision of 2026-08-19, and round
5 does not give it one.

### Honest negatives — attacks that did not land, recorded so nobody re-spends a round

- Financing could not be reopened by any `w`, any constant `rf`, the lever cap,
  or the 21-day aggregation.
- **Grid-max selection on the RAW train return has no material effect** on the
  OOS excess statistic: `P(>margin)` moves ≤3pp between grid=1 and grid=4 across
  seven processes, within MC error at n=1,500. *The validator's own carried
  measurement debt from the floor review is now closed.*
- The VR guard is not broken where it can see.
- Lifting the history floor does not fix discrimination (0.62 → 0.68).
- `--real-bench` (no market-Sharpe assumption) gives class max 19.9% / TP 8.6% /
  discrimination **0.43** — the conclusion does not depend on
  `--market-sharpe 1.0`; if anything the assumption flatters it.

### What this does NOT cover

Costs are absent everywhere: no slippage, no financing spread over rf, no
borrow. Real leverage is charged *above* rf in practice, so H1's arithmetic is a
**lower** bound on the gift. Survivorship is untouched — the nulls are
generated, not sampled from surviving strategies. Everything except §1 and §2 is
conditional on a synthetic Gaussian benchmark at an assumed excess Sharpe of 1.0
(the fund's own feed gives SPY 0.86 over the OOS window, 0.88 over 10y). The
20.8% dropout is applied as an independent per-fold Bernoulli; on the belt the
causes are plausibly correlated within a candidate, which makes the ceiling
worse, not better.

**One geometry caveat the validator states and did not correct**: concatenating
surviving test legs is contiguous by construction at the live floor (any dropout
⇒ `never_ran`), but at floor `none` a survivable dropout leaves an 84-day hole
and the 21-day blocks straddling it are wider than they look. Applies to the
floor-lifted table only.

**Could not reconcile**: the adversary's round-4 reachable-state figures
(FPR 13.7 / TP 24.5 / break-even 35.8) exist only in review prose — no committed
script produces them. Round 4's own 630-day table gives class max 19.3 / TP 12.3
/ discrimination 0.64, which the round-5 numbers **do** match (18.2 / 11.3 /
0.62).

## 8. Reproduction

New instrument: `scripts/gate_v5_audit_r5.py` (885 lines; `gate_v5_audit_r4.py`
untouched — chair-verified). From `ClarkHarness`:

```
./venv/Scripts/python.exe scripts/gate_v5_audit_r5.py --all --draws 2000
./venv/Scripts/python.exe scripts/gate_v5_audit_r5.py --battery --draws 2000 --stat r4
./venv/Scripts/python.exe scripts/gate_v5_audit_r5.py --battery --draws 1500 --floor none
./venv/Scripts/python.exe scripts/gate_v5_audit_r5.py --battery --draws 2000 --real-bench
```

Every table's header prints its conditioning assumptions inline: ρ, margin,
draws, seed, **benchmark excess Sharpe (ASSUMED)**, rf source, fold geometry,
dropout, and the grid-selection statistic — adopted from round 4's judgement
call 5, and the reason this round's assumptions can be audited without reading
the code.

## 9. GAPS — what this leaves unanswered that STRATEGY GENERATION needs

1. **A risk-free series in the spine.** There is none. This blocks the
   constitution's own excess-return amendment and the premia claim type end to
   end. `/fund/marketdata/bars?symbol=BIL` already serves 2,779 sessions — the
   gap is that nothing in the gate path consumes it. *Gives generation*: premia
   candidates the gate can actually judge, instead of every premia idea being
   judged by the alpha bar it was explicitly exempted from.
2. **One belt run after `76784c2`.** Zero legs captured means round 6 will
   re-argue round 5 in simulation. *The cheapest unblocking action on the list.*
3. **The class-maximum null library should be a committed artifact, not a script
   constant.** *Gives generation*: a mechanism proposing a low-vol premia edge
   could ask "which known null does my idea most resemble?" before it costs a
   belt run.
4. **`daily_return_legs` under-reports absent fold legs** (§6). *Gives
   generation*: a quant reading "2 legs missing" when 6 are missing will size a
   premia statistic on a third of the data it thinks it has.
5. **The round-4 kill's decisive arithmetic has no reproduction command in the
   repo.** *Gives generation*: a finding the funnel is blocked on should be
   re-runnable by the next seat in one command.
6. **`DECISIONS_PER_TEST_LEG = 4` is still unvalidated**, and it sets the 84-day
   test leg that sets the 336-session OOS window that puts the margin inside the
   noise band. H5 traces directly to it.
