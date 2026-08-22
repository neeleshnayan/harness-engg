# Proposal — Entry 20: the scheduled-announcement liquidity premium

**Seat: mechanism · cycle 5 · filed verbatim by the CTO chair 2026-08-22 ·
zero containers · all numbers RUN, scripts at session scratchpad `m5/`.
Chair-verified before filing: `leanrunner.py` stores both curves and computes
no volatility for either ("volatility" appears once in the file, in a comment
at :1559); `edgar_filings.json` and the analysis scripts exist on disk.**

## 1. The mechanism

A scheduled earnings release is a known-date, unknown-magnitude jump.
Somebody must hold inventory across it; dealers do not want to, and because
the date is public months ahead they can charge for the service in advance.
In the days around a scheduled announcement the price of immediacy rises, and
whoever is willing to BE the inventory collects the fee — earned across the
event and largely handed back after, the signature of a payment for a service
on a date, not a holding-period premium. (So & Wang, JFE 2014: a six-fold
increase in short-horizon return reversals during announcements, attributed
to exactly this.)

**The prediction this story makes and the alternatives do not, RUN**: the
payment must scale with inventory risk. By the name's trailing 60d vol
quintile, abnormal return in [−1,+3]: −0.084% / −0.155% / +0.015% /
**+0.557% (t 2.22)** / **+1.247% (t 3.41)** — and the **vol-NORMALISED**
payment also rises (−0.0035 → +0.0187, t +3.37). A beta or lottery story
predicts a flat risk-adjusted profile; it rises. (The market-vol time-series
axis is humped, not monotone — reported as unconfirmed.)

## 2. The counterparty

**Primary payer: the liquidity supplier who will not hold inventory across a
scheduled jump**, plus the institution that must transact around the print
anyway. Both permanent; ~700 chargeable events/yr in our universe alone.
**Secondary (Savor-Wilson 2016, systematic-risk premium) declared NOT
supported by our data**: on 6,882 events at ACTUAL dates, [−21,−1] −0.062%
(t −0.41), [−5,−1] −0.014%, **[−1,+1] +0.348% (t +3.53)**, [+2,+21] −0.214%
(t −1.65). Everything is in three days and ~60% reverses within the month —
which kills the holding-period reading and tells the implementation when to
leave.

## 3. Claim type — PREMIA

Compensation for bearing a risk somebody pays to shed, documented across
three literatures, capacity enormous relative to us. Measured: strategy vol
**22.74%/yr vs benchmark 23.63%** (ratio 0.962, beta 0.931), strategy
+21.22%/yr vs the belt's actual EW buy-and-hold bar +18.01%, return-to-vol
0.961 vs 0.820, maxDD −40.65% vs −40.25%. **Pre-committed: if the belt
reports a vol ratio above 1.0 on its own window, the premia sufficiency
argument breaks and this re-declares as alpha before any verdict is read.**

## 4. The rule

**Universe (declared, module-level)**: the **175** hunting-ground symbols
that are domestic SEC filers with ≥1 8-K Item 2.02 since 2015 (the 25
excluded are foreign private issuers filing 6-K, verified by name).

**Signal — a calendar, touching no price**: for each name, every past 8-K
Item 2.02 date `p` projects to `q = p + 364d`; dedupe within 45d; map to the
first session ≥ q = the predicted announcement session `ip`. Inputs are >1
year old when used, so **point-in-time hazard is exactly zero**. Verified:
n=6,105 predictions, median error 0 trading days, |e|≤2 for 70.0%, ≤5 for
92.0%; 88.4% of windows contain a real 2.02 within [−3,+5].

**Window**: in-window = sessions ip−1 … ip+3; enter at close of ip−2, exit at
close of ip+3.

**Sizing — k declared**: **k = 40 slots**, each in-window name at 1/k = 2.5%
NAV; if >40 in window (6.5% of days) keep the 40 nearest ip. **Unfilled
slots hold the equal-weight universe** — always 100% long, unlevered, never
cash. k is a demonstrated tracking-error dial: IR 0.76/0.81/0.80/0.76/0.77
at k=20/30/40/60/80 while TE runs 8.82→2.38%/yr.

**Cost**: 5.56 bps/side measured. One-way turnover 2,584%/yr.

**Deliberately NOT added**: the vol-quintile screen that would ~double the
effect — a factor-proxy sort measured to destroy ~70% of breadth, and adding
it after seeing the table is forbidden tuning. Recorded as a mechanism
property for a later, separately pre-registered cycle.

## 5. Testability

Fold geometry RUN via `window_for_strategy`: **declare hold=21** (defect D7
live; conservative on both axes — same 5 folds as hold=5 but a 20-month OOS
union, 2024-12-22..2026-08-19, against 4.6 months). Ten-year full feed:
excess +3.20%/yr, TE 5.95%, **IR +0.54**; belt OOS union **+11.50%/yr, IR
1.53 — 3.6× the ten-year figure; the belt window flatters this and the
verdict must be read against the ten-year number.** Honest criterion map:
`must_beat_benchmark` is the only criterion that genuinely tests this;
`min_breakeven_bps` will pass for the WRONG reason (D6: interpolates on
total return → reads ~70 bps/side for any fully-invested equity book; the
honest ACTIVE-return breakeven is ~18–19 bps/side — IR +0.22 at 15 bps,
−0.38 at 25); walk-forward retention is benchmark-blind on a ~75%-index book
and carries no information here. Event-level evidence: n=5,779, +0.313%/event,
t +2.96; the belt run is a consistency check on an argument carried by the
event panel.

**Seasonality present and the construction is immune**: slots filled swing
12.0× by month (Feb 24, Dec 2; zero slots 7.7% of days) — fatal for a
fixed-k SELECTION rule (measured: "hold 40 soonest announcers, else flat" =
−0.28%/yr, IR −0.06), harmless for the fixed-slot TILT (+3.77%/yr vs the
daily-rebalanced bar, IR +0.80, t +2.54), because active weight is n_t/k and
a thin calendar becomes a small tilt, not a concentrated bet.

## 6. Falsification

1. **The payment stops scaling with inventory risk** — vol-normalised
   abnormal return flat/decreasing across name-vol quintiles kills the
   liquidity story.
2. **The pre-window starts earning** ([−5,−1] currently −0.014%, t −0.24) —
   leakage or selection artifact.
3. **The post-window reversal disappears** — it is a holding-period premium
   after all; a different strategy, re-derived not re-parameterised.
4. **A placebo earns what the real date earns.** Currently: calendar shifts
   −60/−30/+30/+60/+90/+120/+182d all between −4.15% and −0.04%/yr; 8
   name-shuffle placebos (calendar distribution preserved) mean IR −0.43,
   max +0.51, vs base +0.80.
5. **Post-publication decay** — currently the second half is STRONGER
   (2016-21 IR +0.61; 2021-26 IR +0.95); a rolling 3y IR through zero says
   the arbitrage closed.

**The honest weakness, in the falsification section not buried**: median
event −0.113%, win rate 49.1%, skew +1.20; 5% two-sided trimming takes the
mean to +0.061% (t 0.94); top-5 of 169 names supply 43.2% of P&L — the
**98th percentile** of a 400-draw reshuffle null whose median is 35.5%, so
mostly what skew looks like — and the concentration does NOT persist by name
(H1 top-quartile contributors earn +0.430% in H2 vs +0.378% for H1
bottom-quartile): no ex-ante name story either way. Positive skew makes IR
UNDERSTATE this strategy; a t on a +1.20-skew mean overstates significance —
the deliberately-unfair pessimistic bound (drop top-10 contributors ex post)
is +0.085% (t 0.86). **Two more disclosures**: the window [−1,+3] is the
argmax of eight tested (neighbours +0.305 to +0.383, so not knife-edge, but
selected); and the second-half per-event mean attenuates to +0.164% (t≈1.1)
even as the second-half portfolio IR improves — both true, the tension named.

## 7. Prior art

Well known — and for a premia claim that is the correct profile, not a
warning: Frazzini & Lamont 2007 (>60 bps/month); Barber et al. 2013
(global); Savor & Wilson 2016 (9.9%/yr, two decades); So & Wang 2014 (the
counterparty). Magnitude sanity: this measurement annualises to ~12–16%/yr
while held against the published 9.9% — same order, modestly larger; treat
the published figure as the prior. **Materially different from the menu**:
entry 8 conditions on filing CONTENT after it appears (payer: slow
attention); entry 20 conditions on the DATE of a filing that has not
happened yet, predicted from the name's own calendar a year earlier (payer:
a dealer's inventory constraint). Entry 5 stays retired; nothing here leans
on the ADV band.

## 8. The leg that binds — and it is not capacity

Min ADV $167.7M, min capacity_usd $33.5M against $1,885 NAV: four orders of
magnitude of headroom. **The binding leg is order granularity and approval
throughput**: ~1,034 one-way orders/yr (~4.1/session) at $50 each at $2k NAV
($12.50 on the $500 sleeve), essentially all outside autopolicy v3 and
therefore on the CEO's click. As a BELT CANDIDATE it is fully testable today
for one container; as a LIVE POSITION it is the first product of this firm
whose constraint is the size of the fund, not the quality of the idea.

## 9. Implementation notes for the quant

(1) The ~6,100 (symbol, predicted_session) pairs must be EMBEDDED as a
literal (~100 KB) — LEAN containers have no network; the panel exists at
`scratchpad/m5/edgar_filings.json`. (2) The benchmark leg makes 175
sequential `fetch_daily_bars` calls — the most likely non-strategy failure
point. (3) Report the ACTIVE-return breakeven and the strategy/benchmark
volatility ratio — both curves are stored; neither number is computed. (4)
Declare hold=21 with the D7 reason recorded.

## CHALLENGE — the premia lane does not need gate v5 for the adopted shape

**Direction: TIGHTENS** (adds a required reported number, removes no
control) — **and an adversary pass is requested anyway**, because any route
by which a premia claim gets judged outside v5 is the shape a loosening
would arrive in.

For a candidate that is long-only, unlevered, always fully invested, and
holds only members of its declared universe:

> `must_beat_benchmark` passes AND `vol(strategy) ≤ vol(benchmark)` AND the
> benchmark's own excess return is positive
> ⟹ the strategy's excess-return risk-adjusted performance strictly exceeds
> the benchmark's.

Arithmetic, not an estimator: if σ_s ≤ σ_b and (r_s−rf) > (r_b−rf) > 0 then
(r_s−rf)/σ_s > (r_b−rf)/σ_b. No calibration, no null battery, no rf-leak
(rf cancels in the inequality's direction), and the round-4 financing hole
cannot arise because the shape forbids leverage. **Demonstrated
consequence**: this candidate satisfies it on measurement and would
otherwise be shelved as unjudgeable-as-premia or re-dressed as alpha. Cost:
a standard deviation of two already-stored curves. **Not claimed**:
necessity; anything about levered or hedged claims; that v5 is unnecessary —
only that it is not-blocking for the one shape the CEO adopted as default.
**What would change the seat's mind**: a zero-skill null satisfying all
three conditions on this history — the seat could not construct one and has
not proven it impossible.
