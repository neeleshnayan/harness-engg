# Adversary — Entry 20 blind review, 2026-08-22

**Filed verbatim-in-substance by the CTO chair from run `run-adversary-entry20`.
Two verdicts, kept strictly separate. Chair verification at the end.**

```
TL;DR
The strategy's core signal is real and could not be broken: 200 name-shuffle
placebos, none beat it, every number reproduced exactly. But its PREMIA label
fails the author's OWN pre-committed test — on its declared window the vol ratio
is 1.001 against a limit of 1.0. It goes to the belt now, as ALPHA. The attached
governance challenge must be REJECTED: 83% of randomly-weighted, skill-free
portfolios pass all three of its conditions.
```

## (a) THE PROPOSAL — SURVIVES as a belt candidate; its PREMIA claim type is KILLED by its own pre-commitment.

## (b) THE CHALLENGE — KILL. Measured zero-skill false-pass rate 83.4% (full feed) / 71.2% (belt window).

## Reproduction

All ten headline claims reproduced **exactly** on an independent numpy rewrite
(0.4 s vs the original 7 min): the active leg (+3.77%/yr, IR +0.80, t +2.54),
the k-dial invariance, the cost sweep, the split-half, the event panel (n
5,779, t +2.96), the vol quintiles, the §3 premia block, the belt OOS union,
the turnover. *"The cleanest artifact this bench has been handed."* The kills
are about what the numbers MEAN, never whether they are real.

## Six attacks that FAILED (do not re-spend)

Name-shuffle placebo at **200 seeds** (memo used 8): 0 of 200 exceed base,
p < 0.005. Point-in-time clean. Bars carry no split phantom (adjclose, 12
sub-−40% days all real events, zero near split ratios). Window [−1,+3] ranks
**8th of 70** swept — the disclosure was conservative, not the argmax. All 25
foreign-issuer exclusions verified by name. And a **self-caught near-miss**:
a survivorship probe looked lethal (+2.06% decile spread) until the adversary
saw the forward return *contained the window*; measured from ip+3 it reverses
to −0.305%. Survivorship not demonstrated in this construction.

## GROUND 1 — the proposal's own pre-commitment fires

§3 verbatim: *"if the belt reports a vol ratio above 1.0 on its own window,
the premia sufficiency argument breaks and this re-declares as alpha before
any verdict is read."* Measured on the declared window (hold=21,
2024-12-22..2026-08-19): **vol ratio 1.0011** — >1.0 in 6 of 7 start-date
variations, at k=20/30, and at every cost. The full-feed 0.962 does not
transfer; the vol advantage that carries the *risk-adjusted* half of the
premia claim does not exist on the belt window. And the trigger is
unevaluable — the belt computes no volatility (one hit in `leanrunner.py`, a
comment at :1559). **By its own rule, the candidate re-declares ALPHA before
any verdict is read** — which also voids the challenge's "this candidate
satisfies it on measurement."

## GROUND 2 — §3 credits a rebalancing bonus the mechanism doesn't produce

The belt bar is equal-weight **buy-and-hold** (`leanrunner.py:1291`) — the most
concentrated portfolio of the family. A zero-information EW *daily-rebalance* of
the same names earns **+19.15%/yr at vol 19.81%, ret/vol 0.967 — better
risk-adjusted than the candidate's 0.933.** 36% of the candidate's excess and
*all* its vol advantage belong to the bar's construction, not the announcement
premium. Constructive corollary: the identical tilt on an EW-rebalanced base
gives ret/vol 1.071 (vol 20.25%) — strictly better; the sleeve should rebalance.

## GROUND 3 — the vol-scaling signature is not diagnostic as written

Falsifier #1 needs a null it doesn't have. With **no events at all** (n=79,214),
the vol-normalised profile already rises monotonically to Q5 +0.0034 at **t
+3.65** — 27.9% of the headline gradient is a universe property. An
announcement-specific increment (~70%) remains, so the mechanism is **degraded,
not refuted**; but the reported number does not measure what its label says.

## GROUND 4 — "5.56 bps/side measured" is n=8, reliable:false, and the edge dies at 12.2 bps

The live `/fund/tca` verdict is `sample: 8, reliable: false`, sd 35.35 (SE ≈
12.5). The correct comparator is not zero but the zero-skill rebalance, against
which **breakeven is 12.2 bps/side** — inside one SE of the cost input. The
mechanism's own story compounds it: the counterparty's revenue *is* the
strategy's cost, paid on both legs when it is highest.

## THE CHALLENGE — KILL, with a number

**NULL A** (EW daily-rebalance of the benchmark's own constituents, zero skill)
passes all three conditions with a *better* vol ratio than the candidate. Then
**500 random Dirichlet weight vectors**, daily rebalanced, information-free:
all three conditions pass **83.4%** (full feed) / **71.2%** (belt window).
`vol(s) ≤ vol(b)` passed **100%/95%** across ~1,100 zero-skill portfolios — the
vol leg carries zero discrimination, so the test collapses to
`must_beat_benchmark`, *the alpha criterion the constitution says premia must
not be judged by.* Break-even prior for a pass to mean anything ≥ **45.5%**.
The direction label "TIGHTENS" is wrong — it removes the requirement that a
premia claim pass gate v5, which is a LOOSENING, and the exact shape the
excess-returns amendment exists to prevent.

## Two instrument defects found en route (chair-verified line-exact)

- **`daily_returns` carries the DISCARDED benchmark.** `_read_result` builds it
  at `:1370` from the engine benchmark; `_add_benchmark` pops that at `:1218`
  and recomputes the EW bar at `:1291`; `daily_returns` is never recomputed.
  So the only volatility-capable stored object is judged against a *different*
  benchmark than `must_beat_benchmark`. Measured `corr(daily_returns.benchmark,
  SPY) = 1.0000` on a candidate whose bar is EW(SPY,TLT). **Gate v5's premia
  statistics consume this object.**
- **Calendar-day clock**: 167 of 536 `daily_returns` are exactly 0.0, so
  `pstdev × √252` understates SPY's vol 14.79% vs 17.80% — permissive direction
  for a `σ_s ≤ σ_b` test. (The r4 undownsampled-series finding WAS fixed; these
  are new.)

---

# CHAIR VERIFICATION & DECISION

Line-exact: `leanrunner.py:1218` pops `benchmark_curve`; `:1291` recomputes the
EW bar; `:1370` builds `daily_returns` from the engine `bench`, not recomputed.
The daily_returns/benchmark divergence is real and it is what gate v5's premia
work would stand on.

**The convergence is the headline.** Two seats, blind to each other, killed the
premia-bypass challenge by different nulls — the validator's monthly-rebalance
(18.2% zero-skill pass) and the adversary's random-Dirichlet (83.4%). Same
verdict, independent constructions. **The challenge is rejected with a number;
re-filing requires new evidence** (a version with a rebalanced bar, machine-
checked premises, and both σ on one date-aligned pair — the adversary named the
bar for a re-look).

**Entry 20 the candidate SURVIVES and re-labels ALPHA by its own §3
pre-commitment** — not a CEO judgment call, the candidate's own committed
fallback. It goes to the belt under the full gate. Chair staging: the quant
implements it as alpha, **sequenced behind the v2 builder** (one heavy job in
flight; quant runs LEAN containers). The belt run is a test, not a deploy — the
gate judges, the CEO clicks only to deploy. Six attacks failed and are reported
as failures; that ratio, not the kill count, is the seat working.
