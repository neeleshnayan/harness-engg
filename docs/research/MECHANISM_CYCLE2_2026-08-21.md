# Mechanism — funnel cycle 2: entries 7 and 4 (filed verbatim)

**2026-08-21, run-mechanism-cycle2, serving CEO-approved asks 34a1ff35
(entry 7) and 9e558217 (entry 4). CTO verification note at the end. The
seat's STATE and run_record are in the seat memory and flight recorder.**

---

```
TL;DR
Both menu entries die on our own 11 years of data, and the reason is one piece of arithmetic worth more than either: with financing charged, cutting exposure can never improve risk-adjusted return — only correct timing can, and neither entry has any.
Entry 7 (defensive/low-vol): DECLINED. Every version loses on our data, and the purest version of the trade lost 17% a year over the last thirty months. Seating it as a sleeve leg would have cost roughly $22–$84 a year on a $1,885 fund.
Entry 4 (trend): RETIRED as a rule we run — it lost in 11 of 12 configurations. Buying it in a fund wrapper does not rescue it: the two wrappers we could actually have bought eleven years ago earned essentially nothing.
The menu grows by three new ideas with named payers (tax-deadline selling, share-offering placement discounts, Treasury auction flow) and loses two dead ones. Nothing needs a human decision today; one optional ask is filed for the PM.
```

Method: every mechanism's own signature test on the live feed before any
prose; zero containers spent; all figures excess of BIL per the
constitution's 2026-08-21 amendment; feed 2015-08-03 → 2026-08-20, 2,779
daily sessions/symbol. Scripts: scratchpad/mech2/ (fetch.py, lib.py,
e7.py, e4.py, e4b.py, wrappers.py, mf.py, mf2.py, roll.py, auction2.py).

## 0. DEFECT D4 — the finding that governs both verdicts

**Under the excess-return amendment, leverage is Sharpe-invariant:
Sharpe(L·r_ex) = Sharpe(r_ex) for constant L. Therefore a long-only
de-risking rule cannot be a premia claim** — it changes exposure, not
risk-adjusted return; any measured improvement must come from TIMING.
This kills in advance: long-only low-vol, long/flat trend, vol-targeting
without leverage, "de-risk into stress" overlays. Constructive corollary:
**a long-only premia claim must ADD an independent return stream, never
subtract exposure.** This is adversary-r4's gate-v5 kill read from the
proposer's side.

## 1. ENTRY 7 — defensive/low-vol: DECLINED-WITH-CONDITIONS

The mechanism is real (leverage-constrained reachers: Black 1972;
Frazzini & Pedersen JFE 2014; benchmark-tracking managers: Baker, Bradley
& Wurgler FAJ 2011) — and it does not matter, four ways:

1. **Prior art discounts it**: Novy-Marx & Velikov (JFE 143(1) 2022) —
   BAB's performance is substantially a microcap-weighting artifact
   ($1.05/dollar in bottom-1%-cap stocks).
2. **Our band's SML slopes UP**: across 9 SPDR sectors, corr(beta, excess
   Sharpe) = **+0.62** (BAB requires negative). XLK beta 1.26 SR +0.89;
   XLP beta 0.55 SR +0.44.
3. **Every holdable expression loses**: USMV/SPLV excess Sharpe 0.61/0.49
   vs SPY 0.72 (full 11y), 0.61/0.45 vs 0.93 (belt window) — and per D4
   leverage cannot fix it. The non-closet-SPY expression (within-universe
   low-vol rotation, 126d vol rank, monthly, K lowest sectors, active vol
   6.3–8.1%/yr) loses the paired block bootstrap in all four
   configurations (P(win) 25.9–41.9%); the HIGH-vol mirror beat both
   every time.
4. **The investable long-short form lost for eleven years**: BTAL excess
   −3.72%/yr full (SR −0.22), −7.89%/yr since 2020, **−16.87%/yr in the
   belt window**. This is the closer.

**Revival conditions (both required, each one command)**: C7a —
corr(beta, excess Sharpe) over ≥5y of our feed turns negative (today
+0.62); C7b — BTAL (or any anti-beta wrapper) trailing-3y excess turns
positive (today −7.89%/yr). Falsification of the decline: both flip AND a
within-universe rotation's bootstrap win rate exceeds ~70% over ≥5y.
**Money at stake avoided**: $21.96–$83.56/yr on the PM's 14% leg size
(1.2–4.4% of NAV/yr).

## 2. ENTRY 4 — trend as premia: RETIRED

The counterparty story is honest (fixed-weight policy portfolios are
mechanically contrarian; VaR-constrained holders delever after losses;
Hurst-Ooi-Pedersen JPM 2017 document a century of the premium) — and the
trade is not ours to put on:

1. **11 of 12 configurations lose** (2 universes × 2 weightings × 3
   lookbacks, monthly, 1-session lag, long/flat, benchmark = same-universe
   hold): the documented inverse-vol 252d construction is WORST (SR +0.18
   vs +0.50, P(win) 7.8%). Sub-periods: 2016-2019 P(win) 9.5%; belt
   window 15.8%.
2. **No convexity**: down-market beta 0.37 vs up-market 0.35 (120 months).
   The apparent crisis relief is 65% average exposure — D4 again.
3. **The wrapper re-expression fails ex-ante selection**: DBMF looks
   excellent (+6.99%/yr, SR 0.57, corr(SPY) +0.19) but the entire blend
   benefit is 2022 (+19.92%); ex-2022 the blends are coin flips (P(win)
   48.4%/43.8%). The wrappers actually selectable at window start (WTMF,
   FMF) earned SR +0.21/+0.05 and **WTMF LOST 7.80% in 2022** — the one
   year the mechanism exists to pay. VMOT delisted 2026-07-17; wrapper
   mortality is live. Same lesson as VRP/XYLD: the wrapper is not the
   mechanism.
4. **Unjudgeable by the current instrument, measured exactly**: at hold-21
   the belt gives 4 folds whose UNION of OOS legs (2025-04-22→2026-08-19,
   334 sessions) is SPY +47.91% with max DD −8.88% — zero bear markets in
   any fold. A crisis-convexity premium cannot be judged by a 48% rally.
   Unblock = the 10y backfill (gated on gate v5, killed 4×) + a premia
   criterion scoring diversification in the benchmark's bad states.

**Written reason for the register**: the long-only, no-leverage form is a
de-risking rule (D4); the documented form is unreachable; the wrapper
form fails ex-ante selection. The premium may well be real, and this fund
cannot hold it. Falsification of the retirement: an ex-ante-selectable
wrapper basket beating a matched-vol hold over a window with ≥2 equity
bears, passing a leak test vs the SG Trend Index. **Money at stake
avoided**: −$37.41 in a single bad year on a 15% leg, against zero
measured ex-ante compensation.

## 3. Pre-killed at zero cost

- **Merger arb (MNA)**: +0.95%/yr excess 11y, SR 0.15, daily skew −2.30;
  since 2020 −0.35%/yr. The fee eats the insurance premium; the payoff
  shape is the one gate v5 keeps being killed for mis-certifying.
- **Index reconstitution**: Greenwood & Sammon (JF 80(2) 2025) — S&P
  addition effect 7.4% (1990s) → 0.3% (last decade). The payer stopped
  paying.
- **Commodity roll-schedule spread**: DBC−GSG +1.16%/yr t=0.54 —
  confounded by wrapper sector weights; uninformative, not negative.

## 4. The menu after cycle 2 — two out, three in (12 → 15)

- **7** → DECLINED-WITH-CONDITIONS (C7a/C7b). **4** → RETIRED (reason in
  §2).
- **NEW 13 — Tax-deadline forced selling**: payers are Oct-31-FY mutual
  funds managing distributions and Dec-31 retail loss-harvesters —
  statutory, recurring. Expression: worst trailing-12m names in a declared
  universe, Nov 1–Dec 31, revert in January; always-invested,
  sign-varying, v4.1-honest. Claim: alpha. UNTESTED; blocked on history
  depth (2 Decembers in the archive). LIVE.
- **NEW 14 — Secondary-offering placement discount**: payer is the
  issuer/selling shareholder buying execution certainty (plus the
  underwriter clearing a block). Signal: EDGAR 424B5 / 8-K item 8.01
  pricing filings — a NON-PRICE signal on in-house data with the
  analyst's acceptance-timestamp tooling already built. Claim: alpha.
  Prerequisite: measure the event count in our band first. LIVE — the
  seat's pick for cycle 3.
- **NEW 15 — Treasury auction cycle**: payers are primary dealers (bid
  obligation) and index bond funds (on-the-run buying). ADDED WITH ITS
  FIRST TEST NEGATIVE: on the 63 long-end coupon auctions the vendor
  serves (2025-03→2026-08), no post-auction reversal in either sample
  half (auction+1..+3 TLT −0.113%, t=−0.82). The tradable leg is the
  reversal and it is absent. Needs full-history data
  (api.fiscaldata.treasury.gov) before any dispatch. Recorded so the
  negative is not re-discovered.

Live and unblocked: 12 (dated catalysts), 14, 10 (data absent). Blocked
on backfill: 13, 4-post-backfill, 2, 3, 9.

## 5. Instrument defects found

- **C1 (API card, verified)**: `lookback_days` is le=2000 (fund.py:2582);
  3650 returns HTTP 422. Depth params are `start_date`/`end_date`. True
  depth: 2,779 daily sessions from 2015-08-03 = ELEVEN years, 30/30
  symbols.
- **C2 (external)**: treasurydirect.gov TA_WS ignores date/pagesize
  params — rolling ~18-month window only; use api.fiscaldata.treasury.gov.
- `window_for_strategy` signature: (end, hold_days, min_folds,
  train_days=252, floor=None).
- **D4** (§0): both entries were written on the premise that reducing
  exposure harvests a premium; with financing charged, it does not. Goes
  into the menu's ground rules.

## 6. Ask filed

mechanism requests pm (an ask, never a trigger): close R8 formally in the
sleeve design record with §2's measured answer, so the fifth-leg slot is
not held open on a premium the ex-ante wrapper set does not deliver.

**Sources**: Frazzini & Pedersen JFE 2014 · Novy-Marx & Velikov JFE
143(1) 2022 (mysimon.rochester.edu/novy-marx/research/BABAB.pdf) · Baker,
Bradley & Wurgler FAJ 2011 · Hurst, Ooi & Pedersen JPM 2017 · Greenwood &
Sammon JF 80(2) 2025 · Cederburg, O'Doherty, Wang & Yan JFE 138(1) 2020.

---

## CTO verification note (2026-08-21, at resolve)

Verified before filing: (1) fund.py:2582 — `lookback_days` le=2000 with
`start_date`/`end_date` as the depth params, line-exact: the mechanism
caught the CTO's OWN API card in error (the "3650 works" gotcha was
wrong), the fourth time the bench has corrected the chair's instruments;
card amended at resolve. (2) D4's arithmetic is exact — Sharpe invariance
to constant leverage on excess returns is an identity, and it is the
adversary's r4 ground 1 restated from the proposer's side, independently
derived. (3) The belt-geometry claim matches the validator's fold-count
invariance finding. Consequences at resolve: menu statuses applied via a
dated cycle-2 section on PREMIA_MENU (7 declined-with-conditions, 4
retired, 13/14/15 added, D4 into ground rules); both CEO-approved asks
(34a1ff35, 9e558217) resolved with this artifact; the PM ask filed; the
API card corrected. Cycle 3's aim, per the seat's own STATE: entry 14 —
the secondary-offering placement discount, a non-price signal on in-house
EDGAR data, jointly with the analyst. The north star's shape in this
artifact: two dead entries cost zero containers, three new payers entered
the menu, and the next dispatch has a target the instruments can actually
judge.
