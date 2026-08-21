# Analyst — funnel cycle 2 opening dispatch (filed verbatim)

**2026-08-21, run-analyst-cycle2. Three batched tasks: corpus freshness
audit + refresh, point-in-time audit, entry-8 (post-filing drift) evidence
pack. CTO verification note at the end. The seat's full report follows
verbatim; its STATE and run_record are in the seat memory and flight
recorder respectively.**

---

```
TL;DR
The filings corpus is safe to backtest only if trades are dated to the morning AFTER a filing, never the same afternoon — 56% of filings landed after the closing bell, one just 106 seconds after it. I refreshed 51 stale names (corpus now 1,035 findings) and found two fixable flaws: we throw away the exact publication timestamp the SEC gives us free, and our 8-K reader reads the cover page instead of the earnings release, so 83% of those reads produced nothing.
On the trade idea itself — buying after strong earnings reactions — I built a 16,466-event, 5.6-year test and it does not work: what looks profitable overall comes entirely from 2021, and the last two and a half years are negative. No position here. Nothing needs a human decision; two engineering fixes are worth queuing.
```

## API card defects found

1. **`GET /fund/research/observations` takes `limit`, default 50, `le=500`** (fund.py:1758). A naive full-corpus fetch silently returns 50 of 1,035 rows. Page by `category` (largest 379 < 500).
2. `POST /fund/research/read` body is `{tickers, forms, since, per_ticker}` — `per_ticker` defaults to **2**, which is why the corpus was one filing deep per name.

## TASK 1 — Corpus freshness audit and refresh

Census, not sample: all 201 tickers against EDGAR submissions JSON, 0 errors. Starting state measured: 863 observations, 201 tickers, **204 distinct filings** (1.01 filings/name — the seed memory's "~2" was wrong). 47/201 tickers (23.4%) had ≥1 unread filing; only 17 filings arrived after the 08-18 extraction — the other 51 existed then and went unread because `per_ticker=2`. **The corpus was never stale so much as shallow by construction.**

Refreshed 51 names (47 stale ∪ 7 single-observation): `{'tickers': 51, 'filings_read': 155, 'already_read': 49, 'tickers_failed': 0, 'observations_stored': 120}`. Corpus now **1,035 observations, 201 tickers, 249 filings**, last_extracted_at 2026-08-21T08:47:54Z.

NOT refreshed, deliberately: full-universe 2-year deepening (measured 12.3 s/filing → ~3.4 hours; Task 3 proved the price side of entry 8 needs no filing reads, so this is a CTO/CEO budget call).

**Confirmed defect: the 8-K reader reads the cover page.** `Filing.url` (edgar.py:86-89) uses EDGAR's `primaryDocument`; for an 8-K that is the cover page — the substance is exhibit EX-99.1, never targeted. Measured: 8-K 0.52 obs/filing with **83% zero-yield (120/144)** vs 10-Q 4.09 and 0%. AEHR's 2026-07-14 8-K gave the model 3,648 chars of letterhead (https://www.sec.gov/Archives/edgar/data/1040470/000165495426006655/aehr_8k.htm). **Item 2.02 earnings-release content is currently unreachable by this fund.**

**Second confirmed defect: symbol-namespace collision.** `fetch_daily_bars("BTC")` returns CoinGecko bitcoin spot (7-day calendar) while EDGAR resolves BTC to Grayscale Bitcoin Mini Trust ETF (CIK 2015034), which holds 6 observations in our corpus. Wrong instrument, wrong calendar; caught by a bar-count integrity check (more bars than SPY).

**Third measurement:** corpus ∩ hunting ground = **9 of 201** — the reading is not going where the fund fishes (caveat: the hunting ground is a 200-name snapshot, possibly top-N).

## TASK 2 — Point-in-time audit

Method: census leg (all 204 filings matched to EDGAR, 204/204) + sample leg (40 random observations, seed 20260821). Timezone verified against four filing index pages: **EDGAR's acceptanceDateTime carries a "Z" suffix but is ET = the stamp minus 4 hours** (ALKT/AADX/ACGL/AESI all exact; AESI also demonstrates the 17:30 ET filingDate roll).

**Finding 1 — dated by FILING, not by period: the right anchor.** Stored `filed` == EDGAR filingDate 204/204 and 40/40. Period sits median **36 days** before filing — the classic lookahead is NOT present and would have been worth 36 days.

**Finding 2 — real sub-daily lookahead, the majority of the corpus.** 62.3% of filings accepted post-close; **114/204 (55.9%) accepted ≥16:00 ET on the same date stored as `filed`**. A close-of-`filed` entry trades 1–88 minutes before the disclosure exists. Sharpest: **SRPT 10-Q, accepted 16:01:46 ET — 106 seconds after the close** ($15.93 → next session $16.78, +5.5% market-adjusted, booked from nothing).

**Finding 3 — the missing fields are free.** edgar.py:138-139 zips four columns and discards `acceptanceDateTime` (201/201), `reportDate` (201/201), and 8-K `items` (12,164/12,164). All 1,035 observations carry neither a period nor an acceptance timestamp.

**VERDICT: CONDITIONALLY POINT-IN-TIME-SAFE — enforced in code, not remembered.** SAFE: entry at/after the open of the first session following `filed` (204/204). UNSAFE: close-of-`filed` (corrupted for 55.9%) and open-of-`filed` (safe for only 19.6%). The corpus needs the dating fields before entry-8-class work can be fully honest.

## TASK 3 — Entry-8 evidence pack (post-filing drift)

**(a) Literature + counterparty.** Bernard & Thomas (1989), JAR 27:1-36: ~2%/60d drift, 41/48 quarters (ideas.repec.org/a/bla/joares/v27y1989ip1-36.html). The counterparty is **35 years of published arbitrage**: Martineau (2022) — gone from non-microcaps by 2006; Subrahmanyam's replication: **t=2.18 pooled → 1.43 ex-microcap** (anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/). My own measurement independently reproduces that collapse: **t=2.22 pooled → 0.85** under a different restriction.

**(b) What our corpus and feed can measure.** The price side needs ZERO filing reads: 4,302 10-Q/10-K events + 12,164 8-K events (100% item-coded, acceptance-timestamped), 201 tickers, 2021-2026, built from ~400 throttled SEC metadata calls (~3 min) vs ~56 hours of filing reads. 203/203 price series fetched, adjusted, daily-bar-spacing-verified. Corpus content conditions **1.5%** of measurable events. BTC excluded (collision above).

**(c) The measurement.** Entry = open of R+1 (never close-of-`filed`, per Task 2); excess vs SPY over identical sessions; hand-verified end to end on SRPT.

- **10-Q/10-K drift: dead.** Unconditional |t| ≤ 1.05 (n=4,287); AR-conditioned naive t up to 2.92-class collapses under date clustering (2.12 → −0.24; −2.23 → +0.20; 760 reaction dates for 4,287 events). Median sharply negative (−285.6 bps at N=60) while the mean is positive — a long basket fights a negative median.
- **The 10-Q is not the earnings event — 8-K item 2.02 is.** Re-run (n=4,413): naive L-S N=20 +205 bps t=2.92; clustered t=0.64; but all six years positive (sign test p≈0.031).
- **Deployable form, then its kill.** Calendar-time PIT portfolio, quintiles from trailing 365d, 5 bps/side: L-S hold-20 **+41.74%/yr, IR 0.98, t=2.22**. Killed twice: **ex-2021 t=0.85**; **2024-onward −6.93%/yr, t=−0.27**; beta to SPY 1.27 with CAPM alpha t −0.55 since 2024; excess max drawdown −50.5%; avg 13.1 names ≈ **$38/position** at sleeve size. Per-year Q5 net excess: 2021 +108.8%, 2022 +30.2%, 2023 +29.6%, 2024 −6.4%, 2025 −32.7%, 2026 +39.3% (partial). **The pooled result is 2021 plus a decaying tail.**

**Verdict on entry 8: NO THESIS — do not carry post-filing drift, as posed, to a mechanism proposal.** Fails clustering, fails the sub-period split, fails beta decomposition, and reproduces the published replication collapse. Well-powered (16,466 events, 5.6y): a real negative, not absent data.

**What survives as raw material:** the 16,466-event dataset (scratchpad: deep_events.py, eightk.py, pead8k.py, caltime.py, kill.py), and three untested lanes: **item 5.02 officer departures** (the only unconditional signal anywhere: N=5 −32 bps, t=−1.98, n=2,241 over 1,105 reaction dates — the SRPT governance lesson made systematic), item 3.02 dilution (−591 bps N=60 but <20 clusters — no claim), and content-conditioned drift once EX-99.1 is fixed.

**Not checked**: earnings-surprise data (no estimates — announcement return used as proxy, stated); sector residuals (no ticker→sector map exists — absent, not approximated); intraday; survivorship (cuts in FAVOUR of the rejected effect); costs (5 bps/side constant, D2 caveat — does not decide the conclusion); delisted names.

**Local-compute split, honest report:** extraction ran fully local (qwen3.5:9b, 155 filings, 120 verified observations, 58 unverifiable quotes caught and discarded by the string-match gate) — paid off. The numerical scans were deliberately NOT routed local: a language model computing a t-statistic is error injection, not savings; "checkable outputs only" was not met. Judgement stayed on Opus.

---

## CTO verification note (2026-08-21, at resolve)

Verified before filing: (1) edgar.py:137-139 zips exactly form/filingDate/
accessionNumber/primaryDocument and Filing.url builds from primaryDocument
— both discard claims line-exact; (2) the corpus refresh is real — the
liquidity category alone returns 379 rows against the card's undocumented
limit param, matching the seat's paging note; (3) the PIT entry rule and
the clustering/sub-period kill methodology are the SRPT and gate-audit
lessons applied unprompted. Consequences at resolve: entry 8 recorded as
MEASURED NO-GO (this doc is the record; the mechanism's cycle-2 brief
redirects to the CEO-approved entries 7 and 4 with the event dataset
handed over as raw material, never as a proposal); the analyst's 5.02 ask
filed to the desk queue; the three API-card corrections applied; the two
defect-fixes (EDGAR dating fields, EX-99.1 reader) and the BTC routing
defect queued for builder D7. The counterfactual in the seat's own words
is the north star's leg 1 working: the naive study returns t=2.92 and
would have consumed a full candidate cycle before dying at the gate.
