# Mechanism dispatch — funnel cycle 1, menu entries 5, 6, 11

**Author: mechanism agent (second dispatch, 2f0959d6), 2026-08-20. Filed
verbatim by the CTO at resolve; CTO verification note at the bottom.
Headline: 0 proposals to the container, 1 implementation-ready spec DEFERRED
with named unblock conditions, 2 entries refused with arithmetic, and 3
defects found in the fund's own instruments. Zero container cost.
Measurement scripts in the session scratchpad (rev.py, rev2.py, mend.py,
mend2.py), all driven off GET /fund/marketdata/bars.**

## Entry 5 — cross-sectional momentum in the capacity band: NOT PROPOSABLE

All 20 names from RESEARCH_XS_MOMENTUM_2026-08-17.md:51, pulled off the
fund's own feed (467 common sessions, 2024-10-08 → 2026-08-19 — the common
window is bounded by the newest names; stated as the estimate's sample):
median annualised vol **48.2%** (min 28.0, max 101.8), mean pairwise
correlation **0.182**, 20-name equal-weight basket vol 22.8%/yr. The gate
benchmarks a declared-UNIVERSE strategy against that basket
(leanrunner.py:1141-1144), so the deciding statistic is ACTIVE vol:

| selection | tracking vol vs the 20-name basket | alpha required for IR 1.0 |
|---|---|---|
| top-3 | 23.2%/yr | 23.2%/yr |
| top-5 (the tested rule) | 16.9%/yr | **16.9%/yr** |
| top-8 | 11.9%/yr | 11.9%/yr |
| top-10 | 9.7%/yr | 9.7%/yr |

Documented diversified equity style premia run single-digit percent per year
on hundreds of names (QMJ 1964–2023: 4.7%/yr, Sharpe 0.47, and that is a
long/short factor we cannot build). **The required effect is ~4× the largest
documented one.** The counterparty story (slow-diffusing information) is a
claim about a diversified factor; in a 5-of-20 book the factor is buried 5:1
under idiosyncratic small-cap risk, and diversifiable risk earns nothing by
construction — which is why the write-up's own out-of-sample was +7.1% vs the
basket's +37.0%, and its 24-cell grid ran best +21.7% / median +3.6% / worst
−38.4%: ±20-40pp is what 16.9%/yr of tracking noise looks like when ranked.

Separately sufficient, the constitutional objection: the universe rule
(top-ADV names inside the $2M–$25M band, universe.py:10-12 — "small enough
that a multi-billion fund cannot be in it") is exactly the narrowing the
mechanism charter forbids as a source of edge — and it is what raises median
name vol from ~20% to 48.2%, creating the impossible arithmetic.

**Disposition: RETIRE from the menu** (executed). Revivable only with a
NON-PRICE signal (menu entry 8, the filings corpus) — only a different signal
changes the arithmetic, which is about signal strength.

## Entry 6 — short-horizon index mean reversion: NOT PROPOSABLE

The only version with a real named counterparty is daily-reset
leveraged/inverse ETF rebalancing (mandate-bound, price-insensitive,
into-the-close, computable size). It makes a SYMMETRIC prediction: the
rebalance amplifies the close in the day's direction, so a big UP day must be
followed by negative excess exactly as a big DOWN day by positive. The
signature test, run on our feed BEFORE writing a proposal (SPY, 826 sessions
2023-05-05 → 2026-08-19; Welch t vs all other days):

| forward | after ≤ −1.5% (n=36) | after ≥ +1.5% (n=34) |
|---|---|---|
| 1d | +0.356%, t=+0.93 | +0.022%, t=+0.12 |
| 3d | +0.890%, t=+1.74 | **+0.286%, t=+0.87 (WRONG SIGN)** |
| 5d | +1.091%, t=+1.91 | +0.174%, t=+0.39 |

**Both tails positive — the mechanism's own signature fails.** What remains
is a volatility effect in a rising market. Prior art agrees: the 2024 QFE
survey of the LETF-impact literature finds the papers methodologically flawed
and the economic associations insignificant.

Three further independently-sufficient kills: (1) the only always-invested
expression on our infrastructure is conditional leverage into UPRO — higher
average beta, which benchmark-blind v4.1 would pass for the wrong reason and
v5's beta adjustment is killed three times over; (2) the trigger fires on
5.5% of sessions, so 42% of 12-day test legs contain ZERO events (folds the
belt already conflates with lost edge — 20.8% real-belt unmeasurable rate);
(3) the whole effect is in the recent half (H1 +0.380% t=1.09 / H2 +1.060%
t=1.90) — the recency walk-forward exists to discount.

**Disposition: DECLINED-WITH-CONDITIONS** (in the revival register).

## Entry 11 — month-end rebalancing flow: SPEC FILED, DEFER

**Mechanism**: ~$20 trillion of US pension/TDF assets run fixed-target
calendar rebalancing; when equities outperform, mandates force selling the
winner into month-end — measured at **17bp next-day equity impact**, robust
to momentum/reversal/macro controls, reverting because it carries no
information (Harvey/Mazzoleni/Melone, NBER w33554; Etula et al., RFS 2020).
**Counterparty, named**: policy-weight mandates that are REQUIRED to trade on
a published schedule — the payer, date, direction and dollar size (~$16bn/yr
transferred) are all public, with the authors stating front-running is
profitable. **Claim type: ALPHA** (a mispricing to be beaten after costs, not
a risk premium) — stated with the honest prior that a published mispricing is
being competed for.

**The rule** (one free parameter, fixed by the flow's timing, no sweep):
`UNIVERSE = ["SPY", "TLT"]` (equal-weight basket benchmark — the honest bar
v4.1 can already apply); baseline 50/50, always invested, never cash; signal
= sign of month-to-date SPY−TLT measured at close of T−5 (T = month's last
session); trade at close of T to 100/0 (s>0) or 0/100 (s≤0); back to 50/50 at
close of T+3; full book, no leverage; `HOLD_DAYS = 21` (the strategy's own
clock). Fold arithmetic RUN, not asserted: exactly 4 folds, 84-session test
legs spanning 2025-02-26 → 2026-06-25, ~4 month-ends per leg.

**Pre-registered falsification tests, run before writing** (38 months,
2023-06 → 2026-07, our feed) — two lean against the proposal and are
reported anyway:
- F1 sign structure: pressure −0.262 (t=−1.63), reversal +0.223 (t=+1.37) —
  right signs, not significant.
- **F2 mid-month placebo: −0.071%, t=−0.34** vs the month-turn rule's
  +0.807%, t=+1.85 — PASSES cleanly; the strongest evidence this is a flow,
  not a seasonal.
- **F3 magnitude scaling: FAILS on the mean** (small-divergence months
  +1.18% vs large +0.43%; win rates go the right way; n=19 per bucket —
  uninformative rather than damning, and the kill test on a deeper sample).
- F4 split-sample: H1 +1.280% t=1.73 / **H2 +0.335% t=0.74, win 47%** — the
  post-publication half is a coin flip, the shape of an effect being competed
  away.
- F5 outliers: mean holds ex-extremes (+0.658%, t=1.91). PASSES.
- F6 cross-pair control (SPY/IWM): +0.343% vs +0.807% — directionally right,
  not clean.

**Why DEFER, both measurable**: (P1) the fund's single global
`DEFAULT_SLIPPAGE_BPS = 5.0` was validated on ten SMALL-CAP fills; this rule
turns 24× book/yr, so the model charges 1.20%/yr against 1.0–1.8%/yr gross —
the cost MODEL, not the market, kills it. A per-instrument realised-cost
measurement (SPY/TLT half-spread ≈ 1bp) is the unblock — a measurement, not
a threshold move. Pre-registered cost-efficiency variant (UPRO/TMF express,
~0.40%/yr modelled cost, its own falsifiers) recorded so it is not invented
after a bad result. (P2) ~30 month-end observations cannot resolve a 17bp
effect at 22.8% gate power — the history backfill (correctly blocked behind
gate v5) turns 4 folds into ~27. **Confirming measurement: the live fetch
path served 826 sessions back to 2023-05-04 for every symbol asked — the
request, not the vendor, was the binding limit.**

## Three instrument defects (verified by the CTO, below)

- **D1 — fold count vs regime coverage invert for fast rules**: hold-3's
  "5 independent folds" all sit inside ONE QUARTER (2026-05-26 → 08-19);
  hold-21's 4 folds span 16 months (`window_for` reaches back only
  train + test·(K+1) days). A fold count is being read as evidence strength
  when what varies is regime coverage. Stated in no doc until now.
- **D2 — one global cost constant, calibrated on the wrong instruments**:
  5bps/side for everything, validated on ten band fills; mega-liquid ETFs
  overcharged 3–5×; binding on entry 11.
- **D3 — the menu's "Testable today?" conflated folds-exist with
  effect-resolvable** (fixed in the menu the same day).

## What could NOT be checked — absence, not zero

Actual rebalancing-flow data (the signal is a proxy; sell-side month-end
estimates are on no feed we have); whether entry 6's down-day effect is a
vol-risk premium (needs VIX — no ingestion path, established previously);
realised SPY/TLT spread at our venue (zero fills in either name); the true
vendor history limit (826 sessions confirmed because that was the request);
any execution behaviour (no orders, no backtests, no thresholds touched).
The 20-name vol/correlation estimates carry their 467-session sample.

**Sources**: NBER w33554 (Harvey/Mazzoleni/Melone); CFA Institute summary;
Etula/Rinne/Suominen/Vaittinen RFS 33(1) 2020; AIMS QFE 2024 LETF survey;
practitioner month-end flow coverage (GS/JPM estimates); Alpha Architect QMJ
magnitude anchor. URLs in the run record.

---

## CTO verification note (2026-08-20, at resolve)

Spot-checked before acting: **D1 reproduced exactly** by running
`window_for_strategy` myself (hold 3 → 5 folds, test span 2026-05-26→08-19;
hold 21 → 4 folds, 2025-02-26→2026-06-25); **D2 confirmed** at
costassumption.py:33. The two refusals rest on measurements whose scripts are
in the session scratchpad and whose key numbers were sanity-consistent with
the feed; the entry-11 spec's fold table matched my independent run. Menu
statuses updated (5 RETIRED, 6 DECLINED-WITH-CONDITIONS, 11
SPEC-FILED/DEFERRED), the Testable column split per D3, revival register
extended, the seat's validator request filed as the amendment's first
seat-filed ask, and the D2 cost measurement queued. Recorded as
run-mechanism-cycle1 (trace 2f0959d6).
