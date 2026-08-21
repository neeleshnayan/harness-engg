# Mechanism funnel cycle 3 — the bottleneck moved, and it is now numbered

**Filed by the co-CTO chair from the mechanism's dispatch, 2026-08-21 (UTC),
on the CEO's instruction to "run mechanism with what we have learnt today."**

**VERDICT: 0 candidates to the belt. 1 full spec DEFERRED behind two named
v4.1 unblocks. 1 mechanism family RETIRED, 2 pre-killed. Menu 15 → 19.
Three gate defects measured. ZERO containers spent.**

## Chair verification before filing

- **D6 CONFIRMED.** `leanrunner.py:271-290` — `breakeven_cost` skips any point
  where `p.get("total_return_pct") is None` and interpolates the zero crossing
  on that field. It measures cost robustness on **total return, not on edge.**
- **D5 CONFIRMED.** `factory.py:220` — `need = int(CRITERIA.get(
  "min_walkforward_folds") or 2)`. One global constant sets both the
  statistical requirement and the amount of market history a verdict rests on.
- Both are live in **v4.1**, in force today. Neither is a gate-v5 design
  question.

---

## 1. The finding that reframes the seat

> Across three cycles, eight mechanism verdicts: **four died on their own
> merits — that is the seat working — and four died on the instrument.**
> Today, **both** ideas that survived contact with the world died on the
> instrument.

**The kill rate attributable to the measuring device is 50% and rising.** The
chair's read: this is the strongest available evidence that "no candidate this
week" has stopped being an idea-supply problem, and the firm should stop
treating it as one.

### D5 — the out-of-sample window collapses 12× for fast rules

The entire OOS union is `(need + 1) × 4 × hold` trading days. Measured by
*running* `window_for_strategy`, not asserting:

| hold | today | with `need = max(4, ceil(252/test_days))` |
|---|---|---|
| **1** | 5 folds, **20 trading days** | 63 folds, **252 days** |
| 2 | 5 folds, 40 days | 32 folds, 256 days |
| 3 | 5 folds, 60 days | 21 folds, 252 days |
| 5 | 5 folds, 100 days | 13 folds, 260 days |
| 10 | 5 folds, 200 days | 7 folds, 280 days |
| 21 | 4 folds, 336 days | **unchanged** |

**A 1-day rule is certified on twenty trading days of a single regime, and
stamped with the same gate version as a 21-day rule certified on sixteen
months.**

Why this binds *this seat* specifically: the counterparty classes it is
allowed to accept — forced sellers, mandate-bound rebalancers,
prospectus-driven traders — mostly resolve in 1–10 days, because that is how
long the forced trader takes to finish. Slow premia are structurally IR
0.2–0.6. **The gate gives good calendar coverage only to the horizon band
where the effects are smallest.** That is why three cycles keep converging on
21-day rules and keep dying on effect size.

Strictly **TIGHTENING**. Does not touch `test_days`, so
`min_decisions_per_test_leg` is unaffected. **Honest cost, stated by the seat
rather than hidden: fold count IS container count — `hold=1` goes 5 → 63 runs,
~12.6× compute per candidate.** A cap trades span for cost; the seat declined
to pick the number, correctly.

### D6 — `breakeven_bps` is inflated by risk-free carry, in a live v4.1 criterion

Measured on the seat's own candidate, 11 years, TLT leg:

| slip bps/side | strategy | BIL alone |
|---|---|---|
| 0 | +3.55%/yr | +2.05%/yr |
| 5 | +2.32%/yr | +2.05%/yr |
| **10 — the gate's floor** | **+1.09%/yr** | **+2.05%/yr** |
| 15 | −0.11%/yr | +2.05%/yr |

Total return crosses zero at **14.55 bps/side** → comfortable pass against a
10.0 floor. **The edge crosses zero at 7.3 bps/side.**

> **At the gate's own robustness floor, the strategy earns half what doing
> nothing earns — and the gate calls it robust.**

This is the **same risk-free leak** the CEO's excess-return amendment was
written for, found in a third criterion nobody had checked. Inflation ~2× here
and it scales with the cash fraction.

### D7 — `HOLD_DAYS` conflates holding period with decision cadence

The criterion says a test leg must contain roughly this many of the strategy's
**decisions**. For a calendar rule those are different numbers: the seat's own
candidate *holds* 2 days and *decides* every 21. Declared as `2` it gets 0.4
decisions per leg; as `21`, four month-ends per leg. **Same rule, two
verdicts, and nothing says which is correct.** The quant is writing these
constants now.

---

## 2. Entry 16 — month-end Treasury index extension. SPEC-FILED, DEFERRED.

**The mechanism.** Bloomberg's Aggregate and Treasury indices rebalance on the
last business day of each month; new issues enter, sub-one-year bonds leave,
and index duration mechanically extends. Every tracking fund must buy that
duration on that date.

**The counterparty, named.** Passive fixed-income index funds under tracking
mandates. The New York Fed measures the footprint: trading in benchmark
Treasury notes and bonds is **~46% higher on the last trading day of the
month**, attributed to turn-of-month rebalancing by index-tracking funds. They
keep paying because the alternative is tracking error against a benchmark
their prospectus names.

**Claim type: premia.** Compensation for supplying duration to a forced buyer
on a known date — not a mispricing. Everyone on a rates desk knows the date.

**Measured** (2015-08-01..2026-08-21, n=2,779 sessions, 133 month-ends):

| instrument | last-2-session mean | t | mid-month placebo | next-3-day |
|---|---|---|---|---|
| SHY | +0.0448% | **+4.41** | — | +0.0193% (t 1.21) |
| AGG | +0.0909% | **+3.06** | — | +0.0512% (t 1.00) |
| IEF | +0.1155% | **+2.68** | −0.0181% (t −0.37) | +0.0280% (t 0.40) |
| TLT | +0.1458% | +1.66 | −0.0700% (t −0.65) | +0.0250% (t 0.16) |

**Three independent confirmations, not one t-stat**: the effect is **ordered by
duration** — the mechanism's own signature, since the flow is a demand for
duration; the **mid-month placebo is clean** in both tails; and there is **no
3-day giveback**, so it is a repeated premium rather than transient impact that
reverses.

**Why it is DEFERRED rather than proposed — and this is the cycle's whole
point.** Pre-flighted against the exact fold legs `window_for_strategy`
returns and the exact bar the belt builds:

| window | strategy | EW bar | excess |
|---|---|---|---|
| **OOS union, annualised** | +2.10%/yr | +1.98%/yr | **+0.12%/yr** |
| **11 years, annualised** | +2.32%/yr | +0.69%/yr | **+1.63%/yr** |

**The edge is real at +1.63%/yr over eleven years, and the belt's sixteen-month
window contains +0.12%/yr of it.** Retention is a bare 3-of-4 on 0.4–0.6%
magnitudes against one −1.55% fold — and D6 would hand it a pass for the wrong
reason.

> *"A belt run today buys a coin flip stamped with a gate version. I will not
> spend a container on that."*

**Falsification stated at mechanism level, not P&L level**: if SHY's month-end
premium ever equals or exceeds TLT's, the flow is not a duration demand and the
story is false regardless of returns. Second falsifier: if the effect migrates
off the final two sessions, the calendar anchor is gone.

**Prior art: well known, and it should be** — a standing rates-desk trade. That
is the correct profile for a premia claim: documented, capacity-rich
compensation, not a secret.

---

## 3. Three families killed on their own signature tests — zero containers

**(a) Levered-ETF rebalance flow → entry 6 RETIRED.** The mechanism predicts
reversal *ordered* by flow-to-liquidity and *symmetric* in sign. Across 12
complexes and 11 years the **ordering inverts**: the clean signature appears
only in SPY/QQQ — where levered flow relative to liquidity is *smallest* — and
is absent or wrong-signed in XBI, GDX, FXI, XLE, where it is largest. Second
failure of its own discriminating test on different data.

**(b) The rebalancing / diversification return → PRE-KILLED.** The belt's bar
is buy-and-hold, so a rebalanced portfolio faces exactly the right
counterfactual — the cleanest premia shape v4.1 offers. It **loses on return in
6 of 7 universes** over 11 years (SPY/TLT −2.16%/yr, SOXX/TLT/GLD −5.85%/yr),
and Δ excess-Sharpe spans −0.14 to +0.07, negative in 5 of 7. *The rebalancer
is short momentum, and momentum won this decade — we would have been paying the
premium, not earning it.*

**(c) FX hedging cost → entry 18, MEASURED BUT NOT RESOLVABLE.** Payer genuinely
named (Japanese lifers and EU insurers hedging USD under JFSA/Solvency II).
DXJ−EWJ +6.36%/yr IR 0.59; HEFA−EFA +2.12% IR 0.31; HEDJ−VGK +0.44% IR 0.05.
All IR < 1.0 at 22.8% power, and the EUR leg shows nothing despite a comparable
rate differential — the cross-sectional discriminator fails.

---

## 4. Two facts recorded so no future cycle re-derives them

**The corpus lane is blocked on DEPTH, and it is now a number**: 249 filings
across 201 tickers = **1.2 per name.** A snapshot, not an event panel. An event
study at 10–21 days needs a few hundred events inside the OOS window; reaching
~3 years deep is ~8 hours of extraction.

**The survivorship fence extends further than stated**: it does **not** cancel
for any event family that predicts delisting. Going-concern, covenant breach,
distress and bankruptcy-adjacent studies on our universe are **structurally
unmeasurable, not merely noisy.** It largely does cancel for
benchmark-relative event studies uncorrelated with survival.

---

## 5. The seat's challenge — decouple the backfill from gate v5

**Direction: TIGHTENS. It asks for more history and more folds. No control is
loosened, no envelope widened, no check removed.**

**Challenged**: that the 10-year history backfill is sequenced *behind* gate v5,
on the recorded reason that fold count is invariant to history depth.

**What is new:**

1. **Fold count is invariant to depth only at a FIXED `min_folds` — and
   `min_folds` is a gate criterion nobody has turned.** It is not a property of
   the data; it is `CRITERIA["min_walkforward_folds"]` read at
   `factory.py:220`. At `hold=3`, `min_folds=21` yields 21 folds spanning 252
   days instead of 5 spanning 60. *The premise is true and incomplete: depth
   plus a derived `min_folds` buys regime coverage, which is the thing actually
   missing.*
2. **The feed already serves the history** — 2,779 sessions on every symbol
   tried. The backfill is belt plumbing, not data acquisition.
3. **Demonstrated consequence**: 4 of 8 verdicts died on the instrument, and
   today both survivors did.
4. **The money**: $917.06 of a $1,885.74 NAV sits under **no criterion since
   2026-08-19**, and gate v5's blocking hole (H1, no risk-free series in the
   gate path) is a *build*, not a design tweak. **The cheap fixes are in v4.1,
   not v5.**

**Proposed instead**: ship D5 and D6 against **v4.1** as versioned tightening
changes, and run the backfill in parallel rather than behind v5. *"D5 and D6
are the two things standing between entry 16 and a belt run; v5 is the third
and it is the only one that is genuinely hard."*

The seat explicitly notes it is **not acting against the standing sequencing**
and that the filing licenses no one else to.

---

## 6. Sequencing the seat asks for

1. **builder (Tier-3, park for Fable)** — D5 and D7. Arithmetic, fold table and
   container cost are all measured in this artifact; no re-derivation needed.
2. **validator** — D6 is retrospective too: **of the 40 belt candidates, how
   many passed `min_breakeven_bps` on a figure inflated by a cash leg?** One
   query plus one re-interpolation. That is leg 1 of the team metric, weighted
   by money.
3. **Entry 16 goes to the quant the day D6 lands** — not before.
