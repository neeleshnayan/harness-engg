# THE GOLD DOSSIER v1 — 2026-08-24 (run-analyst-golddossier1)

**Author:** Dr. Mike Darwin (analyst). **Requested by:** the CEO ("Can we try
out Gold as an asset?"), third analytical-muscle pick after META and ETH.
**Filed verbatim by the chair at resolve 2026-08-24. Chair spot-checks
against the cached raw data before filing: the expense decay (−0.3964%/yr)
and the 2021+ premium statistics (n=1413, mean −0.0074%, mean|abs| 0.0235%)
reproduce to four decimals. Full reproduction scripts in the session
scratchpad `gold/`; run record `run-analyst-golddossier1`.**

```
TL;DR
Gold is cheap to own, deeply liquid, and genuinely different from what we already hold — but I found no tradeable edge in it: all four flow stories (central banks, ETF creations, the futures roll, COT positioning) are either backward-looking or statistically dead on 21 years of data.
The one thing worth acting on is a risk parameter, not a trade: 58% of gold's daily risk happens overnight while our venue is shut, so a stop-loss can only reach 42% of it — and gold does NOT protect the book on equity crash days (it averaged -0.26% on the S&P's twenty worst sessions).
Gold's entire 11-year advantage over stocks comes from the last 4.6 years, and my own macro model says 90 percentage points of that move is unexplained by rates or the dollar — that is either a new regime or the thing that unwinds.
Context the CEO should have before anything: gold set an all-time high on 29 Jan 2026, fell 10.3% the next day (its worst session in 22 years), bottomed 26.4% down in July, and is still 14.6% below the high.
Nothing here needs a human decision. This feeds Stan's risk parameters and Ed's menu. No trade is proposed.
```

**Grading key:** TRUE-AND-TRADEABLE · TRUE-AND-NOT-TRADEABLE · FALSE · CANNOT TELL.
**Fence:** the 2026-08-17 GLD phantom-fill cohort is contaminated and is cited in this dossier for ONE fact only — that GLD fills fractionally through our connector. No P&L, no cost, no comparison from that cohort appears anywhere below.
**Host discipline:** all work serial, zero containers, zero bulk extraction; free RAM 1.08–1.20 GB of 15.16 throughout.

---

## 0. CONTRARY FACTS FIRST (Darwin's rule)

**C1. Gold's entire recent superiority is one 4.6-year window, and my own model cannot explain it.** Measured on our feed (2015-08-03 → 2026-08-21, adjusted closes, excess of daily Fed Funds):

| | 2015-08-03 → 2021-12-31 (6.41y) | 2022-01-03 → 2026-08-21 (4.61y) |
|---|---|---|
| GLD CAGR / vol / Sharpe(excess) | 8.04% / 13.89% / **0.560** | 22.14% / 19.08% / **0.937** |
| SPY | 15.75% / 18.10% / **0.849** | 12.25% / 17.47% / 0.522 |
| DBC | 5.18% / 17.05% / 0.328 | 12.51% / 19.29% / 0.502 |
| TLT | 5.14% / 13.82% / 0.365 | −8.25% / 15.76% / −0.720 |

Before 2022 gold lost to equities on risk-adjusted excess return. Anyone quoting the full 11-year Sharpe (GLD 0.729 vs SPY 0.717) is quoting a window that contains the melt-up.

**C2. Gold is NOT an equity-crash hedge on our data.** On SPY's 20 worst sessions in 11 years (SPY mean −5.20%), **GLD averaged −0.26% and was up on only 9 of 20**. TLT averaged +0.63%. Gold diversifies by LOW correlation (+0.073), not by negative correlation — and the rolling 250-day corr(GLD, SPY) has drifted from **−0.295 (2016) to +0.146 (2026)**.

**C3. Central banks are price-SENSITIVE, and the World Gold Council says so in its own words.** WGC, Gold Demand Trends Q2 2026, published 30 July 2026, verbatim: *"The wider geopolitical backdrop, as well as softer gold prices, are likely to have provided some support for the increased Q2 buying."* They bought MORE because it got cheaper. That is a dip-buyer, not a price-taker.

**C4. Central-bank buying did not stop a 26% drawdown.** Central banks bought a record 289t in Q2 2026 — the same quarter that contained gold's trough. GLD peaked at $495.90 on **2026-01-29**, fell **−10.27% the next session** (its worst day in 22 years), and bottomed at $364.96 on **2026-07-16, −26.40%** from the high. It is **−14.63%** below the high as of 2026-08-21.

**C5. Gold ETF holdings are still below their 2012 peak.** GLD held 1,353.3 tonnes at end-2012 and holds **1,047.2 tonnes today**, with gold roughly 3.4× higher. Whatever has driven this bull market, it is not Western ETF investors piling in.

**C6. The one number that ends most gold arguments: real rates explain 4.1% of gold's daily variance.** Not 40%. Four.

---

## 1. THE INSTRUMENT MAP

### 1.1 Identity check before history (clause 4), and it holds

| | our feed's first bar | issuer inception (primary) | NAV/share (issuer, 2026-08-21) | our last close |
|---|---|---|---|---|
| GLD | 2004-11-18 | "Nov 18 2004" (SSGA) | $420.28 | $423.36 |
| GLDM | 2018-06-26 | "Jun 25 2018" (SSGA) | $90.64 | $91.32 |

Sources: SSGA GLD and GLDM product pages. Independent cross-check: the trust's own historical archive gives Total Net Asset Value **$154,240,992,702.79** on 2026-08-21; SSGA's page states **"$154,240.99 M"**. Exact agreement across two independent surfaces. The archive's first row (2004-11-18) has oz/share exactly 0.10000000 and NAV/share $44.20, implying spot **$442.00/oz** — the correct gold price at GLD's launch.

### 1.2 Liquidity and cost — measured, not quoted

Median daily dollar volume from our own feed (close × volume):

| ETF | $ADV, last 252 sessions | $ADV, last 60 | our feed n | first bar |
|---|---|---|---|---|
| **GLD** | **$4,173,840,537** | $2,902,794,094 | 2,780 | 2015-08-03 |
| **IAU** | $660,234,863 | $416,595,829 | 2,780 | 2015-08-03 |
| **GLDM** | $445,154,738 | $309,702,239 | 2,050 | 2018-06-26 |
| SGOL | $170,791,164 | $83,543,683 | 2,780 | 2015-08-03 |
| IAUM | $118,516,860 | $79,014,281 | 1,291 | 2021-07-01 |
| AAAU | $78,638,755 | $53,069,322 | 2,015 | 2018-08-15 |
| OUNZ | $34,400,863 | $23,623,149 | 2,780 | 2015-08-03 |
| BAR | $19,958,025 | $7,430,595 | 2,254 | 2017-09-01 |
| *(for scale)* DBC | $17,516,985 | $23,458,257 | | |
| *(for scale)* DBA | $9,934,136 | $21,733,008 | | |

**The thinnest gold ETF here trades more per day than either commodity ETF we already own.** Capacity is not a constraint at any conceivable size.

**Expense ratios, MEASURED from realised return differentials:**

| ETF | published ER | measured vs GLD, 2018-06-26+ (8.13y) | measured vs GLD, 2021-07-01+ (5.12y) | implied |
|---|---|---|---|---|
| GLD | **0.40%** (SSGA verbatim) | baseline | baseline | — |
| IAU | 0.25% (secondary) | +18.3 bps/yr | +18.1 bps/yr | ~0.22% |
| GLDM | **0.10%** (SSGA verbatim) | +31.0 bps/yr | +35.0 bps/yr | ~0.07% |
| SGOL | not verified | +25.5 bps/yr | +27.0 bps/yr | ~0.14% |
| BAR | not verified | +26.0 bps/yr | +26.3 bps/yr | ~0.14% |
| AAAU | not verified | — | +26.4 bps/yr | ~0.14% |
| OUNZ | not verified | +13.4 bps/yr | +16.8 bps/yr | ~0.24% |
| IAUM | not verified | — | +39.3 bps/yr | ~0.02% |

**And a third, cleaner measurement of GLD's fee that uses no price at all.** The trust publishes ounces of gold per share daily. It has decayed from **0.10000000 (2004-11-18) to 0.09172109 (2026-08-21)** — 21.75 years — a compound **−0.3964%/yr**, stable across sub-windows (last 10y: −0.3959%/yr; last 5y: −0.3934%/yr). The prospectus fee is 0.40%. **The fund's own physical accounting confirms the fee to within 4 basis points.** *(Chair spot-check at resolve: reproduces exactly from the cached archive.)*

**Grade: TRUE-AND-TRADEABLE.** GLDM is the cheapest deployable gold wrapper by ~31 bps/yr against GLD, verified two ways.

### 1.3 What our venue can actually trade — verified, with the gap named

- `alpaca.py:156-161` prices via `StockLatestTradeRequest` — US equities only. Gold ETFs are US-listed equities; the ETH deployability problem does **not** apply.
- `universe.py:118-120` filters on `a.tradable and a.fractionable`.
- **GLD is proven tradeable and fractionable at our venue by our own record** (a filled fractional order, qty 0.424471 — cited from the fenced cohort for this single fact only).
- **IAU, GLDM, SGOL tradability at our venue is UNVERIFIED** — needs a live `get_all_assets` call with credentials, a chair action. Absence reported, not assumed. If GLDM is not fractionable, the 31 bps/yr saving is unreachable and GLD is the deployable default.
- Gold ETFs are absent from the hunting ground (a fact about its construction, not about tradability).

### 1.4 Futures (GC) vs ETF — the basis, and the session trap

**The ETH-class alignment defect was checked for and NOT found.** GLD daily return vs COMEX front-month (`GC=F`) at lags −2…+2: k=0 corr **+0.9040** (beta +0.8794), all other lags ≤ |0.08|. n=2,776. Metadata confirms identity (FUTURE, COMEX, firstTradeDate 2000-08-30).

**But the beta is 0.88, not 1.00, and the reason is the most important structural fact in this dossier.** Decomposing GLD's day against the same futures day: overnight gap corr **+0.798** (beta 0.590); intraday corr +0.491 (beta 0.291). **Two-thirds of GLD's response to the gold market arrives before our venue opens.** The London fix that sets the ETF's NAV is struck at 10:30 a.m. NYT; gold's price is made in London and Asia while the NYSE is shut.

**The basis itself is nothing.** Using the LBMA fix recovered from the trust's own data (NAV/share ÷ oz-per-share — the LBMA column was removed at ICE's request but is recoverable by division), COMEX close vs same-date fix, n=5,461: mean **+0.014%**, p5 −0.880%, p95 +0.921% (two different clocks — most of the dispersion is 6.5 hours of drift). Largest dislocations: 2026-01-30 (−5.38%), 2008-10-10 (−5.01%), 2008-09-17 (+4.13%), 2006-06-13 (−4.09%), 2008-12-26 (+4.02%), 2020-04-13 (+3.82%) — genuine liquidity events only.

**Grade: TRUE-AND-NOT-TRADEABLE.** No ETF-vs-futures edge for us; `GC=F` is the research proxy (2000+), a physical ETF is the deployable instrument, and our venue could not trade GC anyway.

### 1.5 The premium/discount, and a mistake made and caught

First pass computed GLD's close ($423.36) against SSGA's NAV ($420.28) → **+0.73% premium**. **Artifact.** GLD's NAV is struck at the 10:30 a.m. fix; the close is 16:00 ET. The trust's own like-clock comparison (mid at 16:15 vs indicative at 16:15) reads **0.0057%** the same day.

| GLD premium/discount @16:15 ET | n | mean | median | p5 | p95 | mean abs |
|---|---|---|---|---|---|---|
| full history | 5,469 | +0.0030% | — | — | — | — |
| 2021-01-01 onward | 1,413 | **−0.0074%** | −0.0052% | −0.0578% | +0.0380% | **0.0235%** |

**GLD trades within about two basis points of fair value.** *(Chair spot-check at resolve: the 2021+ row reproduces exactly.)*

**Method lesson 13: never compute an ETF premium against a NAV struck on a different clock.** The magnitude here was **128× the real number**.

**Not measured: the bid/ask spread width.** The archive gives the mid, not the width; our bars carry no quotes. Absent, reported absent.

---

## 2. THE DRIVER MEASUREMENT — gold vs real rates

### 2.1 Pre-registered form

Beta of gold's daily log return on Δ DFII10 is negative and stable; the claimed 2022–2024 decoupling to be verified, not assumed.

### 2.2 The daily relationship — real, robust, and small

| series | window | beta (% per +1pp real yield) | t_NW | corr | R² | n |
|---|---|---|---|---|---|---|
| GC=F | 2003-01-03 → 2026-08-20 | **−4.535%** | **−9.99** | −0.203 | **4.1%** | 5,892 |
| GLD | 2004-11-19 → 2026-08-20 | **−5.612%** | **−12.75** | −0.250 | **6.2%** | 5,432 |

**The sign is negative in all 24 calendar years** (sign-test p ≈ 6×10⁻⁸). **The magnitude is the story: R² = 4.1%.** Real-rate news explains one twenty-fifth of gold's daily variance.

### 2.3 The dollar dominates, and inflation expectations do nothing

| model | R² | d_real (%/pp) | d_lnUSD | d_BE (%/pp) |
|---|---|---|---|---|
| Δreal only | 4.10% | −4.535 (t −15.87) | — | — |
| + Δ dollar | **17.60%** | −2.506 (t −9.19) | **−90.63 (t −31.06)** | — |
| + Δ breakeven | 17.60% | −2.514 (t −9.12) | −90.67 (t −31.02) | **−0.091 (t −0.22)** |

1. **The dollar is gold's dominant daily driver** (confirmed on our own feed: corr(GLD, UUP) = −0.4375, beta −1.011).
2. **"Gold is an inflation hedge" is FALSE at daily frequency** — the breakeven coefficient adds 0.00pp of R². *(Scope: tests news, not decade-scale purchasing power.)*

### 2.4 The 2022–2024 decoupling — VERIFIED, and it is not what the phrase implies

**(a) RETURN correlation did NOT decouple** — 2022 −0.400, 2023 −0.493 (its most negative ever); only 35 of 5,643 rolling windows were ever positive (2009-10).
**(b) LEVEL correlation COLLAPSED on schedule** — 2020 −0.958 → 2022-25 −0.106/−0.164/−0.077/−0.059.

**Gold kept reacting to real-rate *news* exactly as always — more strongly than ever — while acquiring a large drift orthogonal to rates.** The footprint of a persistent price-taking buyer, not of "gold stopped caring about rates."

**Grade: TRUE-AND-NOT-TRADEABLE.** The level correlation tells you the regime after it has happened.

### 2.5 The size of the unexplained move — and the honest power statement

Fit 2003–2021 (n=4,736, R²=17.83%), apply out of sample 2022-01-03 → 2026-08-20 (n=1,156):

| | cumulative | annualised |
|---|---|---|
| **ACTUAL gold** | **+147.1%** | +21.80%/yr |
| model PREDICTED | +29.8% | +5.84%/yr |
| **RESIDUAL — unexplained** | **+90.5%** | **+15.08%/yr** |

By year: 2022 +5.02% · 2023 +2.92% · **2024 +26.85% · 2025 +37.77%** · 2026 +0.83%. **Placebo clean**: fit 2003–16, test 2017–21 → −0.78%/yr.

**THE MDE (clause 5).** Residual sd 1.110%/d, n=1,156 → |t|=2 needs 16.5%/yr; measured 15.08%/yr → **t = +1.71**. **The largest macro dislocation in modern gold history does not clear a two-sigma bar.** Confirming it needs ~5.5 years of daily data. **Any "gold has entered a new regime" claim is structurally unconfirmable inside the horizon that matters.** If the residual is permanent, current levels are the baseline; if it fully unwinds, gold falls **−47.5%** from here. Both tails live; no available test discriminates.

### 2.6 Point-in-time honesty — what the FRED key bought, measured

Vintage-vs-today comparisons with the new key:

| series | as-of vintage | observations | CHANGED | max abs delta |
|---|---|---|---|---|
| **DFII10** | 2022-06-30 | 4,878 | **0 (0.00%)** | **0.0000** |
| **DFII10** | 2024-12-31 | 5,503 | **0 (0.00%)** | **0.0000** |
| DTWEXBGS | 2022-06-30 | 4,134 | **1,833 (44.34%)** | 0.2060 |
| DTWEXBGS | 2024-12-31 | 4,761 | **1,723 (36.19%)** | 0.4167 |
| VIXCLS | 2024-12-31 | 5,557 | 0 (0.00%) | 0.0000 |

1. **The real-rate centerpiece is point-in-time clean** — DFII10 is never revised. The keyless-feed warning is real for macro AGGREGATES and not for market-price series; that distinction was a guess before today and is a measurement now.
2. **The dollar index IS revised** (36–44% of observations) — the dollar leg of §2.3 carries revision contamination the real-rate leg does not. Stated, not papered over.
3. **The genuine PIT constraint is a RELEASE lag, not a revision**: the 2022-06-30 vintage of DFII10 lacks 2022-06-30 itself — **day D's real yield is not visible on day D.** Any same-day rule is taking a few hours of look-ahead.
4. Current lags (2026-08-24): DFII10 → 08-20 · DTWEXBGS → 08-14 · CPIAUCSL → 07-01 · FEDFUNDS → 07-01.

---

## 3. NAMED COUNTERPARTIES — four flow stories, each priced

### 3.1 Central banks — REAL, LARGE, PRICE-SENSITIVE, STRUCTURALLY UNMEASURABLE FOR US

WGC Q2 2026 (published 30 July, data to 24 July, revises): net purchases **289t**; H1 345t — *"the lowest for a first half since 2022."* Poland +51t (to 632t), China +33t, Uzbekistan +16t, Kazakhstan +15t. Secondary press reported the YoY jump as "74%"; the primary's figure is **62%** (289 ÷ 177.9 = +62.4%). **Use the primary.**

**Tradeable behind a 30-day lag? No — and the reason is POWER, computed before any test**: quarterly return sd ≈ 8.1%, ~100 usable quarters, tercile MDE **4.0%/quarter = 17%/yr**. No plausible flow signal delivers that. The test cannot mean anything, so it was not run. **The falsifier is already half-fired**: H1 2026 was the weakest since 2022 — the flow is not monotonic.

**Grade: TRUE-AND-NOT-TRADEABLE.**

### 3.2 ETF creations/redemptions — THE BEST DATASET IN THIS DOSSIER, AND A CLEAN KILL

**Source** (a trap on the way: the advertised `.csv` **301-redirects to a PDF** — check Content-Type, not extension): `api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en` (XLSX, browser UA required) — **5,472 usable rows, 2004-11-18 → 2026-08-21** (204 "US Holiday" string rows dropped): oz/share, NAV@10:30, indicative@16:15, mid@16:15, premium, volume, ounces, tonnes, total NAV.

**Publication lag from the sponsor's own page**: day D's holdings post after the 16:00 close → earliest tradeable action is D+1's open, which is exactly what the test uses. Flow structure: 47.6% of days zero change; median |flow| 0.30t; max 49.76t; tonnes 8.1 (2004) → 1,353.3 (2012) → **1,047.2 today**.

| horizon | n | **pre-stated MDE at \|t\|=2** | HIGH-minus-LOW flow tercile | t |
|---|---|---|---|---|
| next session | 5,219 | 0.079% | −0.038% | **−0.96** |
| 1 week | 5,215 | 0.173% | −0.118% | **−1.38** |
| 1 month | 5,199 | 0.344% | −0.232% | **−1.36** |
| **contemporaneous** (not tradeable) | 5,220 | — | **+0.404%** | **+10.19** |

**ETF flow follows the price. It does not lead it.** Replicates the ETH ETF-flow kill on a 21-year sample. Only a genuinely predictive creation signal (intraday AP orders, AP inventory — neither public) would change this.

**Grade: FALSE as a signal, TRUE-AND-TRADEABLE as an instrument-quality dataset.**

### 3.3 The futures roll — nobody pays it, and that is the finding

Gold is a pure carry market: contango ≈ financing. Net roll cost to a fully-collateralised long ≈ **zero in every rate regime** (2021: 0.01%/roll; 2023: 0.84% recovered on collateral; 2026: 0.61% recovered). **The true cost of the ETF wrapper is the fee PLUS ~3.6%/yr of forgone collateral income at today's funds rate** — nine times the expense ratio. That makes the ETF a *fully-funded* position (what an unlevered mandate wants), and makes any ETF-vs-futures return comparison that ignores it a funded-vs-levered comparison.

**Grade: TRUE-AND-NOT-TRADEABLE.**

### 3.4 COT positioning — free, machine-readable, and dead

CFTC Socrata, code 088691, **1,930 reports 1986-01-15 → 2026-08-18** (Tuesdays 1,768). Release Fridays 15:30 ET; entry rule the following Monday (no look-ahead). Latest: OI 406,260 contracts (~$190.6bn), non-commercial net +222,189.

| horizon | n | **pre-stated MDE** | LOW-minus-HIGH tercile | t |
|---|---|---|---|---|
| 1 week | 1,234 | 0.35% | +0.012% | **+0.07** |
| 1 month | 1,230 | 0.69% | −0.185% | **−0.54** |
| 3 months | 1,221 | 1.13% | −1.494% | **−2.56** ← |

**The 3-month result is an overlap artifact, killed properly**: 13 disjoint non-overlapping phases give `−1.88 −2.35 −1.46 −0.89 −0.10 +0.27 +0.63 +0.17 +0.03 −0.19 −1.38 −1.09 −1.40` — **1 of 13 reaches |t|>2, signs disagree**, and the pooled t was inflated √12.6 ≈ 3.55× by overlap. What little signal exists is *momentum*, the opposite of the "fade the specs" story.

**Grade: FALSE.** Revivable only by the Disaggregated managed-money subseries (2006+) or a non-public intra-week proxy.

---

## 4. RISK PARAMETERS FOR STAN

*(Per the accepted routing: risk parameters and menu inputs; no position, no candidate.)*

### 4.1 THE HEADLINE PARAMETER: 58% of gold's daily risk is outside our reach

Variance decomposition, 2015-08-03 → 2026-08-21, n=2,779 (OHLC share one adjustment factor, `marketdata.py:266-273`, so the split is valid):

| instrument | ann vol | overnight gap sd/day | intraday sd/day | **gap share** |
|---|---|---|---|---|
| **GLD** | **16.27%** | **0.778%** | 0.625% | **57.6%** |
| IAU | 16.24% | 0.777% | 0.625% | 57.7% |
| GLDM | 17.21% | 0.824% | 0.654% | 57.7% |
| SLV | 31.60% | 1.537% | 1.197% | 59.6% |
| **SPY** | 17.84% | 0.729% | 0.847% | **42.1%** |
| TLT | 14.68% | 0.683% | 0.638% | 54.6% |
| DBC | 18.01% | 0.824% | 0.779% | 52.8% |
| DBA | 13.00% | 0.499% | 0.643% | 37.2% |
| GDX | 39.19% | 1.505% | 2.005% | **37.2%** |

Bootstrap 95% CI on GLD's gap share: **[53.4%, 62.0%]**. **A stop-loss on gold reaches at most 42% of its risk.** Gap distribution: mean +0.0557%, sd 0.778%, p1 −2.13%, p99 +2.07%, min **−5.98%** (2026-01-30). Monday-gap ratio only 1.067 — no weekend, unlike crypto. GDX inverts the profile (37% gap) because it IS a US equity — stop-reachable gold exposure exists only at 39% vol and −49.8% drawdowns.

### 4.2 Volatility regime — gold is at twice its normal volatility right now

2017 9.90% · 2019 11.66% · 2021 13.68% · 2023 13.39% · 2024 15.01% · 2025 **19.85%** (+63.68% return) · **2026 to 08-21: 32.14%** (+6.83%). **Any vol parameter inherited from a pre-2025 study is wrong by a factor of two today.**

### 4.3 Drawdown geometry

ATH close $495.90 (2026-01-29) → **−10.27% next session** (worst in 22y) → trough $364.96 (2026-07-16, **−26.40%**) → now −14.63%. Worst sessions ever: 2026-01-30 −10.27% · 2013-04-15 −8.78% · 2008-10-10 −7.52% · 2006-06-13 −6.85% · 2025-10-21 −6.43%. Max DD (11y feed): GLD −26.40% vs SPY −33.72% / DBC −41.71% / TLT −48.35% / GDX −49.79% / SLV −52.28%. The 2026-01-30 *cause* (Warsh nomination after a parabolic January) is secondary-sourced: **CANNOT TELL on causation; TRUE on the price action.**

### 4.4 Correlation to the existing book, and the DBC overlap measured honestly

corr(GLD, ·), n=2,779: SPY **+0.073** · TLT +0.258 · DBC **+0.256** · DBA +0.122 · TIP +0.347 · **UUP −0.4375 (beta −1.011)** · GDX +0.774 · SLV +0.780.

**The brief's "DBC carries ~8–12% gold" premise could NOT be verified at a primary — reported ABSENT** (Invesco confirms gold is one of 14 components; weights unobtainable). **The overlap itself is measured and small**: DBC on GLD → R² **6.54%**. Adding gold beside DBC is not doubling an exposure.

**Crisis behaviour:**

| SPY's worst k sessions | SPY mean | **GLD mean** | TLT mean | DBC mean | GLD up-days |
|---|---|---|---|---|---|
| 20 | −5.20% | **−0.26%** | +0.63% | −2.59% | 9 / 20 |
| 50 | −3.91% | −0.08% | +0.62% | −1.70% | 25 / 50 |
| 100 | −3.08% | +0.09% | +0.49% | −1.14% | 47 / 100 |

**Gold is a coin flip on equity crash days. Treasuries are the thing that rises.**

### 4.5 Book impact, at the live NAV ($1,885.74, cash 51.4%)

| configuration | ann vol | delta |
|---|---|---|
| **current book** | **4.52%** | — |
| + GLD 5% NAV from cash | 4.84% | +0.32pp |
| + GLD 5% from DBC | **4.23%** | −0.29pp |
| + GLD 10% from cash | 5.27% | +0.74pp |
| + GLD 10% from DBC | **4.19%** | **−0.33pp** |
| + GLD 15% from cash | 5.78% | +1.26pp |

**The funding source matters more than the size.** Worst-case arithmetic at caps: 5% NAV → worst session −$9.69 (−0.51% NAV), worst gap −$5.64; 10% → −$19.37 / −$11.28; 15% → −$29.06 / −$16.92.

### 4.6 MDE constants for any future gold event work (reuse; do not re-derive)

Raw daily sd **1.025%**. Residual sd: vs SPY **1.022%** (SPY removes 0.3% of the variance — a useless benchmark), vs DBC 0.991%, vs GDX 0.649%, vs macro model 1.11–1.13%.

| n events | N=5d MDE | N=20d MDE |
|---|---|---|
| 10 | 1.45% | 2.90% |
| 50 | 0.65% | 1.30% |
| 250 | 0.29% | 0.58% |

**Most per-event gold hypotheses (FOMC/CPI/payrolls on one instrument) are structurally unmeasurable. Route to the cross-section or the bin.**

---

## 5. PRE-REGISTERED PRIOR: volatility targeting on gold

**Registered 2026-08-24, before any volscale-style gold candidate exists.** Harvey et al. 2018: vol targeting improves Sharpe only for risk assets; *"for bonds, currencies, and commodities the impact on the Sharpe ratio is negligible"*, while tail severity improves across all classes.

1. **Sharpe: no improvement expected** — gold shows the *opposite* of the equity leverage effect (its highest-vol years were its best: 2025 19.85% vol / +63.68%). A vol-targeted sleeve systematically underweights gold in its best years. Expect ≤ 0.
2. **Tail: genuine improvement expected** — gold's worst sessions cluster in high-vol regimes.
3. **THE BAR, computed first**: SE(Sharpe) ≈ 0.357 on 11y (0.221 on 23y) → **a Sharpe difference below ~0.6 is undetectable on every gold sample we can construct.** "Improved 0.73 → 0.91" is +0.18 against SE 0.36 — noise. The correct claim for such a candidate is the tail claim.

**Scoring**: P10 in the ledger.

---

## 6. DATA-SOURCE AUDIT

Embargo honoured: **no collector output consumed**; every series fetched at a primary or vendor source this dispatch. 12 sources, graded (full table in the run record): our Yahoo-sourced ETF bars (GOOD, adjustment verified), GC=F/DXY chart API (ADEQUATE — front-month splice, daily returns only), FRED keyless (DFII10/VIXCLS EXCELLENT-never-revised; DTWEXBGS CONTAMINATED), FRED vintage with key (GOOD; key never printed), **the SPDR archive (EXCELLENT — issuer primary, 5,472 rows)**, CFTC Socrata (GOOD), WGC Q2 (GOOD as text), SSGA pages (EXCELLENT), iShares (WEAK — 403s automated fetch; the measured differential is the stronger evidence), Invesco DBC weights (**ABSENT**), the fund's own endpoints (GOOD).

**Traps recorded**: the SPDR `.csv` URL 301-redirects to a PDF (Content-Type, not extension); FRED's LBMA gold series are discontinued 404s and Yahoo `XAUUSD=X` 404s — **there is no free FRED gold price today; the recovered NAV÷oz series is the substitute and it is better**; iShares and SSRN 403 automated fetches; 204 archive rows read "US Holiday" in every column; openpyxl is not in the venv.

---

## 7. PREDICTION LEDGER — P1 to P10

| # | prediction | resolves | scores WRONG if |
|---|---|---|---|
| P1 | GLD oz/share on 2026-12-31 = **0.09159 ± 0.00008** | 2026-12-31 | outside band |
| P2 | median 16:15 premium 2026-09-01→12-31 within **±0.02%** | 2027-01-05 | outside |
| P3 | flow-tercile next-session spread \|t\| < 2 on Q4 data | 2027-01-05 | \|t\| ≥ 2 |
| P4 | COT 3-month: fewer than 3 of 13 disjoint phases reach \|t\| ≥ 2 through 2027-06-30 | 2027-07-05 | ≥ 3 do |
| P5 | 2026 full-year real-rate beta negative (24 of 24 years) | 2027-01-05 | positive |
| P6 | rolling 250d LEVEL corr stays above −0.60 through 2026-12-31 (decoupling persists) | 2027-01-05 | any print ≤ −0.60 |
| P7 | WGC Q3 central-bank net purchases in **[+100t, +400t]**, published by 2026-11-07 | 2026-11-07 | outside, or late |
| P8 | GLD median $ADV Sep–Dec > **$1.5bn** | 2027-01-05 | ≤ |
| P9 | GLDM beats GLD by **+25 to +40 bps** over 12mo to 2027-08-21 | 2027-08-23 | outside |
| P10 | any belt gold vol-target candidate: Sharpe delta **< +0.6** AND worst-20d drawdown improves **> 15%** | 2027-06-30 or void | either fails |

---

## 8. THE HONEST VERDICT

**As an INSTRUMENT: TRUE-AND-TRADEABLE, no reservations.** Fractionally fillable at our venue (proven by our own record), $4.17bn/day ADV, fee verified three independent ways (0.40% GLD / ~0.10% GLDM), ~2 bps from fair value, no basis to fight, no roll to pay, no unlock calendar, no counterparty. Cleaner, cheaper, more liquid than anything the fund currently holds.

**As an EDGE: nothing found, on 21 years of free primary data.** Four named counterparties, four honest kills, zero manufactured signals.

**What survives — risk parameters, not trades**: (1) 58% of daily variance is overnight [53.4%, 62.0%] — size off the gap distribution; (2) gold is not an equity-crash hedge (−0.26% on SPY's worst 20; corr drifted −0.295 → +0.146); (3) funding dominates sizing (10% from cash: book vol 4.52→5.27%; from DBC: 4.19%); (4) 2026 realised vol 32.14% — double the decade average — 14.6% below an ATH set seven months ago after a −26.4% drawdown.

**And the contrary fact not to lose: +90.5pp of the last 4.6 years is unexplained by rates, the dollar, or inflation expectations — at t = +1.71, unconfirmable either way for ~5.5 more years. Anyone sizing gold today is sizing an unconfirmed regime break, and the honest place to say so is in the sizing, not the thesis.**

**The money question, answered directly**: at $1,885 NAV, a 10% sleeve is $188.57; its worst historical session costs $19.37, its worst gap $11.28. Affordable — but **this dossier produces no alpha claim and therefore no candidate.** Gold here is a **beta allocation decision** — Stan's judgement on the parameters above, the CEO's click. *True, and tradeable only as an allocation.*

---

*Reproduction: scripts g1–g19 + cached data in the session scratchpad
`gold/`. Chair's resolve actions and the seat's STATE/BINDS are in
`run-analyst-golddossier1` and `.claude/state/analyst.md`. Per the
non-negotiables this document is never edited.*
