# What our gate can and cannot detect

**Measured 2026-08-18 with `scripts/gate_power_audit.py`. Reproduce with:**

```bash
venv/Scripts/python.exe scripts/gate_power_audit.py --draws 4000 --adversary --history
```

The gate had been measured against noise (nulls cleared v1 about half the time)
and against perfect foresight (an oracle failed v2). It had never been measured
against a **plausible** edge — and that turned out to be the question that
mattered, because it decides whether the alpha sleeve can ever be born at all.

---

## 1. The headline

Gate v4's walk-forward leg, 630 sessions (the history we actually hold), 4 folds,
20% annualised vol, 4,000 draws per level:

| true Sharpe | passes | NOT TESTABLE | mean measurable folds |
|---|---|---|---|
| **0.0 (noise)** | **2.9%** | 90.7% | 1.43 |
| 0.4 | 7.5% | 80.0% | 2.08 |
| 0.6 | 11.6% | 71.5% | 2.39 |
| 0.8 | 16.4% | 62.1% | 2.71 |
| 1.0 | 22.8% | 53.0% | 2.99 |
| 1.5 | 37.8% | 30.0% | 3.52 |
| 2.0 | 53.5% | 14.2% | 3.80 |

**False-positive rate: 2.9%.** Far better than the 31.2% my arithmetic predicted —
the arithmetic assumed independent folds and a per-fold retention probability of
0.5, and both were wrong in the strict direction.

**Power: never reaches 80%, at any Sharpe up to 2.0.** A genuinely good
Sharpe-1.0 strategy clears this leg fewer than one time in four.

And the third column is the real story. At Sharpe 0.6, **71.5% of draws are NOT
TESTABLE** — too few measurable folds to judge at all. The gate is not mostly
saying no. It is mostly declining to answer, because `MIN_TRAIN_RETURN_PCT = 5.0`
makes a fold unmeasurable whenever its training year happened to be flat.

Every power figure here is an **upper bound**: the synthetic process has constant
drift, so its edge never decays. A real strategy of the same Sharpe passes less
often than shown.

## 2. Relaxing the thresholds makes it worse

The obvious response is to loosen something. Measured, it does not work —
discrimination (power at Sharpe 1.0 divided by FPR) falls in every direction:

| variant | FPR | power @ 1.0 | discrimination |
|---|---|---|---|
| **v4 as shipped** | 3.3% | 21.2% | **6.4** |
| `MIN_TRAIN_RETURN_PCT` → 0 | 5.0% | 25.4% | 5.1 |
| require only 2 measurable folds | 9.4% | 32.9% | 3.5 |
| both relaxed | 12.8% | 35.9% | 2.8 |

v4 is the best of the four. The problem is not a mis-set threshold.

## 3. A better statistic was proposed, measured, and rejected

The retention ratio is a weak statistic on its face: it binarises each fold
(retained / not) and counts, discarding magnitude, and it divides two noisy
numbers. The textbook improvement is to **pool every test leg into one
out-of-sample series** and test its Sharpe, which uses all the data instead of
throwing most of it away.

It measured well:

| design | FPR | power @ 1.0 | discrimination |
|---|---|---|---|
| v4 majority rule | 3.3% | 21.2% | 6.4 |
| pooled OOS Sharpe ≥ 1.4 | 5.1% | **32.2%** | 6.3 |

**50% more power at identical discrimination.** The recommendation was going to be
to replace the majority rule.

Then it was run against the adversary the criterion exists for — a **one-fold
wonder**, all its edge in a single test leg, a lucky window wearing a track
record. Every draw is a fake, so a lower pass rate is better:

| design | boost 2.0 | boost 3.0 | boost 5.0 |
|---|---|---|---|
| **v4 majority rule** | **13.6%** | **19.9%** | **25.5%** |
| pooled OOS Sharpe | 28.0% | 46.2% | 74.8% |
| pooled + concentration guard | 26.8% | 43.7% | 67.3% |

The pooled statistic is **2–3× easier to fool by exactly the thing walk-forward
was built to catch**, and at boost 5.0 it swallows three fakes in four. Its extra
power *was* that weakness — the same information-pooling that raised power also
let one good window carry the whole verdict.

A concentration guard (cap the best leg's share of total OOS profit) barely
helped. Under a Gaussian process no leg dominates, so the guard never binds and
is **unevaluated** rather than useless; against the adversary it recovered only a
few points, because with one lucky leg in four the concentration sits around 0.6,
comfortably under any threshold loose enough not to reject real strategies.

**The majority rule was kept.** This is the outcome the process is for: a
plausible improvement, measured against an adversary, lost.

## 4. More history helps, and exposes a defect

| history | folds | FPR | S=0.6 | S=1.0 | S=1.5 |
|---|---|---|---|---|---|
| 30 months (today) | 4 | 3.3% | 12.3% | 22.2% | 38.7% |
| 5 years | 12 | **12.5%** | 30.5% | 51.6% | 73.7% |
| 10 years | 27 | **11.4%** | 31.4% | 60.6% | **84.7%** |
| 20 years | 57 | 5.2% | 30.6% | 67.0% | 96.1% |

Power roughly triples. 80% power becomes reachable at **Sharpe 1.5 with 10 years**
of history — never at 30 months.

**But the false-positive rate rises to ~12% in the middle, and that is a defect in
the criterion rather than in the data.** `min_walkforward_folds` is a fixed floor
of 4 while the number of available folds grows, so a null can end up with only a
handful of *measurable* folds and win a majority of that small subset. The rule
does not scale with history.

This would have bitten us on the first day of a data purchase, silently, in the
loosening direction. The review trigger recorded against
`min_walkforward_folds` in `app/fund/judgement.py` is exactly "history extended
beyond 2024-02-26" — it must be honoured before any new data is trusted.

## 5. What this means for the fund

1. **At 30 months we can only confirm strong edges.** Sharpe ≥ 2 is detectable
   about half the time; Sharpe 1.0 fewer than one time in four. Hunting modest
   edges with this gate produces NOT TESTABLE, not knowledge.
2. **The alpha sleeve's birth condition is hard but not impossible** — and its
   rarity is now a measured fact rather than an accusation. If nothing is admitted
   for months, that is the instrument working within its resolution, not the
   pipeline being broken.
3. **This is the strongest argument for paid data yet made, with numbers.** Not
   "more history would be nice": 80% power on a Sharpe-1.5 strategy is
   unreachable at 30 months and reachable at 10 years.
4. **The FPR is genuinely good (2.9%).** Whatever else is true, this gate does not
   wave noise through — which was the founding complaint about v1, and it is fixed.
5. **NOT TESTABLE is the modal outcome, and it is not a failure.** Two thirds of
   real Sharpe-0.6 strategies will get it. Any dashboard that renders that as a
   rejection is lying about what happened.

## 6. What this does NOT measure

- **The walk-forward leg alone.** PSR, order count, benchmark, cost breakeven and
  capacity are conjunctive, so the whole gate's FPR is *lower* than 2.9%, and its
  whole-gate power is *lower* than the figures above.
- **Gaussian i.i.d. returns with constant drift.** No fat tails, no
  autocorrelation, no decaying edge, no regime change. This is the friendliest
  possible world for a persistence test.
- **No transaction costs.** A cost-aware version lowers every number.
- **`scripts/null_audit.py` still has no walk-forward leg**, so the real belt —
  LEAN, real prices, real costs — has still never produced a v4 false-positive
  rate. This measurement is a model of the gate's statistics, not a run of the
  gate. Both are worth having and they are not the same thing.

---

## 7. Which criterion is actually doing the work

*Added later the same day, after a live null audit rejected a candidate with
"only 3 fold(s) could be measured" rather than for failing to persist. Nothing
above is edited; this is a new measurement of the same instrument.*

Reproduce with:

```bash
venv/Scripts/python.exe scripts/gate_power_audit.py --draws 3000 --modes
```

The gate's stated doctrine is that **"what noise cannot fake is CONSISTENCY ACROSS
INDEPENDENT WINDOWS"**. Splitting the rejections by mode shows that at pure noise
the consistency test mostly *never runs*:

| true Sharpe | passes | **starved** | failed majority | mean measurable folds |
|---|---|---|---|---|
| **0.0 (noise)** | 3.3% | **89.6%** | 7.1% | 1.46 |
| 0.4 | 8.3% | 78.4% | 13.4% | 2.12 |
| 0.6 | 11.4% | 70.4% | 18.1% | 2.45 |
| 1.0 | 21.5% | 53.6% | 24.9% | 2.98 |
| 1.5 | 37.9% | 29.9% | 32.2% | 3.53 |
| 2.0 | 51.6% | 13.2% | 35.1% | 3.81 |

- **starved** — fewer than `min_walkforward_folds` were *measurable*, so the
  consistency test never ran
- **failed majority** — it ran, and the edge did not persist in a majority

**A null gets 1.46 measurable folds out of 4.** Its training legs rarely clear
`MIN_TRAIN_RETURN_PCT = 5.0`, because a null makes no money by construction. So the
2.9% false-positive rate is delivered overwhelmingly by an **evidence threshold**,
and only marginally by the persistence test.

### What this does and does not change

**It does not make the false-positive rate wrong.** 2.9% stands, and every
per-candidate message was already precise — *"only 3 fold(s) could be measured,
below the 4 required — the consistency test did not run, which is not the same as
passing it"* is a different sentence from *"kept its edge in only 1 of 4"*, and the
gate has always emitted the right one.

**What was wrong was the aggregate story.** Crediting the FPR to a consistency test
that, for nine nulls in ten, did not happen. The honest characterisation is that
v4's walk-forward leg is **primarily an evidence requirement with a persistence
test attached** — and the two are not interchangeable, because they fail for
different reasons and are fixed by different things. Starvation is fixed by more
history; failed persistence is fixed by a better strategy.

### The consequence worth acting on

This is the same phenomenon as the NOT TESTABLE result and as the 22.8% power
figure, seen from a third angle: **`MIN_TRAIN_RETURN_PCT` is load-bearing far
beyond its stated job.** It was introduced to stop a retention ratio exploding
against a near-zero denominator — a real and narrow bug — and it has quietly become
the fund's main noise filter.

That is not obviously wrong. A rule that only judges strategies which made money in
training is defensible. But it was never *chosen*, and a 70% starvation rate at
Sharpe 0.6 means the same threshold is discarding real candidates at a rate nobody
decided on. It is registered in `app/fund/judgement.py` with this measurement
attached, and it should be reviewed before the next gate version rather than after.

---

## §9 — CORRECTION (2026-08-20): the §7 mode-split does not hold on the real belt

Added per the never-edit rule; §7 stands above as written, and this section
records its falsification. §7's claim — that a null is rejected 89.6% of the
time by fold starvation, making `MIN_TRAIN_RETURN_PCT` the fund's main noise
filter — was a property of the simulation's null generator, not of the belt.
Measured on all 83 real belt sweeps (docs/MIN_TRAIN_RETURN_REVIEW_2026-08-20.md):

- **0 of 57 null sweeps** landed in the floor's band (0, 5.0). Null grid-point
  train legs average **+22.0%** (sd 28.3%, n=224) because the market rose and
  the sweep reports a **maximum over surviving grid points** — two things the
  simulation's driftless, single-draw null omits, both pushing loose.
- Real belt null walk-forward pass rate: **2/8 = 25%** (Clopper-Pearson 95% CI
  8.5%–65.1%), against the simulated 2.9%. The CI excludes the simulation.
- The belt's actual starvation modes are engine timeouts (10 folds) and
  no-trade test legs (5 folds), which the stored fold count cannot distinguish
  from a floor rejection.

Consequence for this doc's 2.9% FPR headline: it is a statement about the
model, not the belt, and must not be quoted as the fund's operating
false-positive rate. The 22.8%-power figure is unaffected in direction but
carries the same generator caveat. Any regenerated table must model market
drift and grid-max selection before its rows are quoted (blocking requirement
on gate v5 round 3).
