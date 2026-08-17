# Pricing the survivorship bias

**Date:** 2026-08-17
**Result: the bias is real, modest, and was described wrongly.** The
survivor-only benchmark of **+60.88%** becomes about **+54.0%** when the vanished
names are included — a haircut of **−6.9 percentage points ± 2.4** from sampling.

The verdict it was feared might overturn does not overturn. The strategy trailed
that benchmark by roughly 30 points; a 7-point correction does not close that.

---

## The correction that matters more than the number

The previous research note said the bias flatters a hold-everything rule *because
the missing names are dead names*. That reasoning is wrong, and it is worth
stating plainly because it was stated confidently.

**Delisting is not failure.** Of 26 band-eligible vanished names measured, the
mean return was **+12.1%** and the median **+19.9%**. Thirteen gained more than
20%; two lost more than half. Most were acquisitions, and an acquisition delists
at a premium.

The bias is still in the flattering direction, but for a different reason: the
vanished names **gained less than the survivors did** (+12.1% against +60.9%).
A portfolio that held them would have earned less than one holding only the
companies that made it — not because they died, but because they left early at
prices below where the survivors ended up.

Getting the direction right by accident would have been worse than getting it
wrong, because the reasoning would have gone unexamined.

## Method

1. **Point-in-time membership.** The vendor's reference endpoint takes a `date`,
   so "who was listed on 2025-01-01" is answered directly rather than inferred:
   **5,546** operating companies (CS + ADRC). Captured in `fund_universe_asof`.
2. **Who left.** 23,307 delisted records pulled; **902** names listed then are
   absent from today's reference (852 CS, 50 ADRC) — **16.3%** of the market in
   twenty months.
3. **Band eligibility decided on prior information.** For a random sample of
   vanished CS names, ADV was measured over 2024-H2 — *before* the window opens —
   so membership is not decided with hindsight. 105 sampled, **27 band-eligible
   (25.7%)**, 26 with a measurable return, 1 unmeasured.
4. **Return to last print**, then the haircut as the difference between a
   survivor-only equal-weight return and one including the vanished at their
   measured returns.

## The haircut

| | |
|---|---|
| vanished band names, mean return | **+12.1%** (sd 44.2, se 8.7, n=26) |
| band names today | 1,330 |
| estimated band names that vanished | ~219 |
| implied vanish rate inside the band | **14.1%** |
| survivor-only equal-weight return | **+60.88%** |
| including the vanished | **+53.98%** |
| **haircut** | **−6.90 pct pts ± 2.40** |

## What the interval does not cover

The ±2.4 is sampling error on the vanished names' mean return **only**. Two
structural assumptions sit outside it and are larger:

- **The sample represents the vanished population.** It was drawn at random, but
  it is 105 of 852.
- **Band entries balance band exits.** The band population "then" is estimated as
  today's band plus the vanished. In a rising market a band defined by a fixed
  dollar range probably *gains* members, which would lower the vanish rate and
  shrink the haircut.

A further known bias, in the conservative direction: return is measured to the
**last print**, which cannot see cash received after a merger closes or a
liquidation paying nothing. A name whose value arrived entirely post-delisting is
understated here.

**So this is a magnitude with a sign, not a correction to apply.** Subtracting 6.9
points from future benchmarks would turn an estimate resting on two unverified
assumptions into a fact.

## What is now possible

As-of membership exists (`app/fund/asof.py`), so a backtest can ask "who was in
the band *then*" instead of inheriting today's survivors. Two limits stand: the
free tier serves ~2 years of history, and historical *volume* for delisted names
must be fetched name-by-name at four calls a minute — so a fully point-in-time
band rebuild is hours of vendor budget, not a screen refresh.

## A bug this work exposed

The vendor throttle was **per-process**, so a second script burst into a minute
the vendor was still counting — and the 429s that came back were being written
into the sample as *"this company has no history"*. A rate limit was entering a
research dataset as absence. The window now lives in Postgres so every process
draws from one budget, 429s are retried, and `RateLimited` is a distinct type so a
caller can never mistake vendor impatience for a missing company. Three polluted
rows were purged.

## Reproduce

```bash
python scripts/capture_asof.py 2025-01-01
python scripts/measure_survivorship.py 120 7
python scripts/survivorship_haircut.py 60.88
```

Resumable: measured names are skipped, so the sample can be grown incrementally
to tighten the interval.
