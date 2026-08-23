# PRE-REGISTRATION — Monday 2026-08-24 reconciliation fills, TCA price-tier analysis

**Filed by the Fable chair from validator run `run-validator-census5`, dated
2026-08-23 (UTC), BEFORE any fill exists. This document is the declared
partition and null; a tier analysis that postdates the fills is not a
pre-registration. Findings-doc rules apply: never edited; the results get a
new section or file.**

## The sample (expected)

11 orders / 10 names, 2026-08-24 13:35–15:00 UTC (the R39 click sheet).
Closes of 2026-08-21 from the fund's own feed.

## The tiers, declared now

| tier | rule | names | n | **predicted half-spread at one $0.01 tick (= 50/P bps)** |
|---|---|---|---|---|
| T1 LOW | P < $50 | SOFI 18.91 · DBA 28.32 · DBC 31.26 | 3 | median **1.766 bps** |
| T2 MID | $50 ≤ P < $250 | XLE 63.64 · TLT 82.05 · INTC 90.07 (×2) · NVDA 214.72 | 5 | median **0.582 bps** |
| T3 HIGH | P ≥ $250 | GLD 423.36 · MSFT 483.24 · SPY 765.72 | 3 | median **0.103 bps** |

Boundaries are round numbers chosen for balance (3/5/3), declared before the
outcome exists.

## THE PRE-REGISTERED NULL — the point of this document

The fund's own J2 measurement: 9 of 14 names are pinned at the $0.01 tick
with no time-of-day curve. Under tick-pinning, half-spread in bps is
**exactly 50/P**. **A bps-denominated tier analysis will therefore
"discover" that cheap stocks cost ~17× more than expensive ones with
near-certainty, and it is pure arithmetic — a price-level statistic wearing
a liquidity label.** The prediction table above IS that arithmetic, written
in advance so it can never be presented as a finding.

## Primary statistic

**π = signed(fill − mid_at_submit) / NBBO_half_spread_at_submit** —
dimensionless, price-neutral (cost = π × spread, J1).
**H0: π constant across T1/T2/T3.** The bps table is SECONDARY and is
reported only beside its 50/P prediction; only a deviation from 50/P is
information.

## Exclusions (all causally prior, declared now)

1. `submit_to_fill_s > 60` → excluded from primary, reported separately
   (CEO-click latency is NOT random by symbol — GLD is clicked first, the
   sleeve last; this is the largest confound and it is not price).
2. Orders filling across >1 execution → excluded from primary.
3. Fills outside 13:30–20:00 UTC → excluded.
4. NBBO absent/crossed/locked at submit → **excluded and COUNTED, never
   imputed.**
5. Venue read from the connector-derived stamp on the fill event, never
   from order intent (tca.py:212 prefers intent — R23 unconfirmed).
6. SPY excluded from primary unless the reconciler records it per-lot
   (R39 expects two rows).

## Power, declared so nobody reads a result into it

Measurement error on an effective spread is ~one tick regardless of name,
so precision on π scales with the DOLLAR spread: **power is highest in T3
and lowest in T1 — the reverse of the bps intuition.** Fills for ±0.25 on
π: ~6 (MSFT-class), ~89 (SPY midday), ~355 (penny-tick name). With ~one
fill per name, **no tier reaches ±0.25. Pre-declared expected verdict:
CANNOT TELL on level, informative on design.** The achieved half-width per
tier is the deliverable, not a pass/fail.

Caveats that no design fixes: the one-tick error model is additive-in-cents
(n=5 basis); every historical fill this fund owns is fractional →
internalised, not lit-book — whether π transfers to whole-share flow is
untested.

## Day-of requirement (GAP 6)

**The NBBO at each submit must be captured ON THE DAY** — the fills persist,
the quotes do not; nothing the fund runs archives NBBO. If the quotes are
not captured, exclusions 4's count and the π denominator are unrecoverable
and this pre-registration degrades to the bps-beside-50/P comparison only.
