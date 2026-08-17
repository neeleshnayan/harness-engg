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
