# Validator — three settling measurements, 2026-08-22

**Filed verbatim-in-substance by the CTO chair from run `run-validator-settling`.
Read-only, 105 NBBO calls, zero containers. Scripts and captures at
`scratchpad/val3/`. Chair verification at the end.**

Three questions, each settling a live disagreement before the CEO's breakfast:
the Grace-G2-vs-PM-R27 fill-programme design, the 38× cost-constant claim
across the session, and the mechanism's premia-sufficiency inequality.

## Job 1 — R27 vs G2: CANNOT TELL on the level, SETTLED on the design

Admissible fills are **4**, not 10: seven are backfills whose event timestamp
is the *logging* time (INTC reads −285 bps against the NBBO at that instant),
five rested through the opening auction. Pooled fraction-of-half-spread-paid:
mean **+0.663**, sd 1.478, 95% t-CI **[−1.69, +3.02]** — holds 0, 0.5 and 1.0.
No tier has an interval.

**The design is settled and it refutes both seats' shared premise.**
Measurement error on an effective spread is **one tick, the same dollar size
on a $14 stock and a $778 ETF** (residual sd $0.0120 vs a $0.0100 tick,
constant across a 56× price range). So per-fill precision on the paid fraction
scales with **dollar spread, not basis-point spread** — and 9 of 14 realistic
names sit at the penny tick, where a fill buys ~1/60th of what an 8-cent-spread
name's fill buys. Grace's 13-fill / 4-session plan works on MSFT-tier names
and is fiction on the names the fund holds; the PM's equal tiers are cut on the
wrong axis and cannot be equally sized. **Neither programme is on the critical
path**: cost = π × spread, the spread term is free from NBBO to ~1% today, and
the fill count is second-order. *Caveat the seat could not close at n=5:
additive-in-cents vs multiplicative residuals — the whole precision table rests
on the former.*

## Job 2 — the 38×, across the session: reproduces, survives, and does NOT support lowering the constant

SPY half-spread 0.1299 bps at 17:00Z → **38.5×** (reproduces Grace's 38.3×);
at the open 0.2611 → **19.2×**, worst session 15.3×. Most of it survives the
open. But **9 of 14 names are pinned at the $0.01 minimum tick all day** with
no time-of-day curve, and in the first five seconds of the open `5.00` is at
or below the quoted half-spread on **6 of 14 names** (DBC, DBA, F, SNAP, SOUN,
RIG). So the constant is not too high — it is one number where the truth spans
74×. **Do not lower it; replace it with a per-name, time-of-day-aware
quantity** — a loosening for 5 names and a tightening for 6+, one versioned
package, adversary blind then the CEO.

## Job 3 — the premia inequality: correct algebra, NOT a sufficient test

**(a) The algebra is right and rf cancels** under all three conventions
(arithmetic, GISW-geometric, continuous), each strictly increasing in r;
demonstrated numerically (excess-Sharpe ordering invariant across rf = 0/4/5%).
The financing clause is inert at k=1. "Always fully invested" is load-bearing —
it is what makes rf cancel in the *denominator*.

**(b) A zero-skill counterexample exists, on the gate-reachable window.**
Reproducing the gate's own benchmark exactly (buy-and-hold equal weight, no
rebalance, no costs), a **monthly-rebalanced equal-weight** book of 10
mega-caps over 2024-02-26..2026-08-19 gives ann 26.10% / vol 16.41% against the
benchmark's 24.82% / 17.36% — all three conditions, zero skill. Rolling
independent windows: **4 of 22 = 18.2%** (CP95 5.2–40.3%). Two of the three
conditions are nearly free on our data (vol ≤ benchmark held 91/91 in two of
three universes; benchmark-excess > 0 held 92.8%). The sign flips with the
window — buy-and-hold beats the rebalancer 1893% vs 934% over 2016-2026 — which
is the definition of one draw, and *why the gate has four folds*. Costs do not
rescue it (1.7–6.2 bps/yr turnover). **The crux, answered:** a low-vol tilt IS
a legitimate premia claim *with* a named counterparty and repeatability — the
conjunction requires neither, and the cleanest counterexample isn't even the
tilt, it's monthly rebalancing to equal weight.

**(c) What sufficiency does not cover that v5 would:** walk-forward folds
(18.2% zero-skill pass on one window), PSR, cost robustness, capacity, the
actual GISW premia statistic (σ-ordering + mean-ordering does not imply a
distributional-statistic ordering), and an rf series — H1 unchanged, and the
inequality's own condition (c) needs the rf series that does not exist in the
gate path.

## Two live defects confirmed (both already staged)

- **D1** — `/fund/tca` defaults `limit=500` into `store.stream`, which is
  `ORDER BY seq ASC`: it serves the **oldest 500 of 966 events**, reporting
  5.56 bps where `?limit=5000` reports 4.95. Worsens with every append; at
  5,001 events it can never see the present. Staged as R24.
- **D2** — order `17d64dcd` was submitted to venue `paper` (seq 593) but its
  `OrderFilled` says `alpaca` (seq 594), because `pipeline.py:318` writes the
  *proposed* venue and `tca.py:212` prefers the fill leg — intent over
  execution — admitting a structural zero into the informative sample (moves
  the mean 5.56 → 4.95, toward "cheaper than modelled"). Fix: swap the
  precedence + a divergence flag. Staged as R23.

## Record gap (builder queue)

0 of 40 verdicts store `benchmark_basis`/`kind`/`symbol`/`legs` — leanrunner
computes all four (`:1297-1302`) and the gate discards them, so **no verdict's
benchmark is auditable**. Third write-only instance.

---

# CHAIR VERIFICATION

Line-exact before recording: `grep volatility|annual_std|ann_vol app/fund/gate.py`
→ **0 hits** (condition (b) is unmeasurable belt-wide today); `leanrunner.py:1297-1302`
computes `benchmark_symbol`/`kind`/`basis`/`legs`, all discarded by the gate;
`scratchpad/val3/` holds the four scripts and their captures.

**The two decisions this settles for the CEO**: R27-vs-G2 → *neither*, the
answer is per-name dollar-spread cost (free), and the fill programme's value is
its spread data not its fills. The mechanism's Entry-20 premia-*bypass* → *do
not adopt*; correct algebra, insufficient test. Entry 20 the **candidate** is
untouched — the adversary is still attacking it blind. And a chair correction
Vishesh's triage earned: this dispatch ran without a desk-visible ticket (chair
dispatch, direct), which is exactly the invisibility his gate rule caught;
chair dispatches now get a desk record at dispatch time.
