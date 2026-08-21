# analyst — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at hiring
- First dispatch: survey the 863-obs corpus, build the best-evidenced thesis.
- Corpus shape: categories liquidity(163), segment, margin, litigation, dilution,
  guidance, insider, customer_concentration; all obs 2026-05..2026-08; ~2 filings
  per name read so far — thin on any single name until you POST /research/read
  for more.

## 2026-08-20 — first thesis delivered (docs/research/THESIS_SRPT_2026-08-20.md)
- SRPT long, ~\$19.40 -> \$30+ / 12mo, on trough stabilization + three dated
  regulatory options. Densest single-direction cluster in the corpus (5 obs,
  5 categories). Under blind adversarial review — do not treat as more than a
  draft until the verdict.
- Largest open hole flagged in-memo: PMO revenue split by product (risk at the
  2027-02-28 PDUFA bounded [0, \$920M/yr] but unmeasured). EXONDYS confirmatory
  status unverified. Follow-up read of 2025 10-K yielded no new stored obs —
  extractor may cap; raise with CTO if it recurs.
- Runners-up parked with reasons: KD, FWRD, GSAT.

## 2026-08-20 — SRPT thesis KILLED (docs/reviews/ADVERSARY_SRPT_2026-08-20.md)
- What held: the SAID layer verified flawlessly, incl. the Arrowhead adjustment.
- What died, learn from each: (1) never read a tape move as thesis confirmation
  without a beta decomposition — the "re-rate" was the sector; (2) when citing a
  transcript, read the NEXT sentence — the collab raise was zero-margin
  pass-through; (3) run your own invalidation thresholds through the company's
  guidance BEFORE filing — the thesis was dead at guide midpoint by its own rule;
  (4) check the 8-K stream for governance changes (CEO changed 9 days pre-10-Q);
  (5) verify externals at their primary source (Cohort 8 data slipped to Q1-27 on
  the very call cited); (6) always price the worst measured day at the position
  cap vs NAV.
- Revival conditions are in the verdict; sharpest single settler: Q3 ELEVIDYS
  print (~Nov 2026) vs the $75M threshold.

## 2026-08-21 — funnel cycle 2 opening dispatch (corpus audit + PIT + entry 8)

### Corpus facts (supersede the 2026-08-20 seed entry)
- The seed entry's "~2 filings per name" was WRONG: it was 1.01 (204 filings /
  201 tickers). After my refresh: 1,035 obs / 201 tickers / 249 filings
  (216 10-Q, 33 8-K), filed range 2024-10-23 -> 2026-08-20.
- `GET /fund/research/observations` takes `limit` (default 50, le=500,
  fund.py:1758). Page by `category` to get the whole corpus; largest is
  liquidity (379). The API card omits this — reported to CTO.
- `POST /fund/research/read` per_ticker defaults to 2. `forms:["10-Q"],
  per_ticker:6` reaches back ~2 years (verified EPRT -> 2024-10-23).
  Measured cost 12.3 s/filing. Full-universe 2y deepening = ~3.4h. NOT spent.
- Corpus ∩ hunting ground = 9 / 201. The reading is not going where the fund
  fishes (the exact failure observations.py:366-383 was written to name).
  Caveat: hunting ground is a 200-name snapshot, possibly top-N.

### Point-in-time — the rule to carry into EVERY future study
- `filed` IS EDGAR's filingDate, not the period. 204/204 filings and 40/40
  sampled obs match exactly. Period sits a median 36d BEFORE filing — so
  period-dating would have been worth 36 days of lookahead. It is not present.
- EDGAR `acceptanceDateTime` has a "Z" suffix but is **ET = UTC-4**. VERIFIED
  against 4 index pages (ALKT/AADX/ACGL/AESI, all exact). Never assume this.
- 62.3% of corpus filings accepted post-close; 55.9% (114/204) accepted
  >=16:00 ET on the SAME date stored as `filed`. SRPT's 10-Q: 16:01:46 ET,
  106 SECONDS after the close a backtest would have used.
- **THE RULE: entry at or after the OPEN of the first session following
  `filed`. Safe 204/204. Close-of-`filed` is corrupted for 55.9%.
  Open-of-`filed` is safe for only 19.6%.**
- 1,035/1,035 obs carry no period and no acceptance timestamp. Both fields
  are returned free by EDGAR on 201/201 tickers; edgar.py:138-139 zips only
  form/filingDate/accessionNumber/primaryDocument and drops them, plus 8-K
  `items` (present on 12,164/12,164).

### Confirmed defects (both filed as recommendations)
1. 8-K reader reads the COVER PAGE. Filing.url uses primaryDocument
   (edgar.py:86-89); substance is EX-99.1. Measured: 8-K 0.52 obs/filing,
   **83% zero-yield (120/144)** vs 10-Q 4.09 and 0%. AEHR 8-K = 3,648 chars
   of letterhead. Item 2.02 earnings content is currently UNREACHABLE.
2. fetch_daily_bars("BTC") returns CoinGecko bitcoin on a 7-day calendar.
   Filer is Grayscale Bitcoin Mini Trust ETF (CIK 2015034), 6 obs in corpus.
   Wrong instrument + wrong calendar. Caught by a bar-count integrity check —
   KEEP THAT CHECK in every study.

### Entry 8 — MEASURED AND REJECTED, do not re-litigate without new data
- Built 16,466 dated events (4,302 10-Q/10-K + 12,164 8-K), 201 tickers,
  2021-2026, acceptance timestamps + item codes, for ~400 SEC metadata calls
  (~3 min). **The price side of drift needs ZERO filing reads.** Corpus
  content conditions only 1.5% of them. Scripts in scratchpad: deep_events.py,
  eightk.py, pead8k.py, caltime.py, kill.py.
- 10-Q/10-K drift: dead unconditionally (|t|<=1.05, n=4,287) and dead
  conditioned on AR (naive t 2.12 -> clustered -0.24).
- **The 10-Q is NOT the earnings event.** 8-K item 2.02 is. Test the right one.
- 8-K 2.02 (n=4,413): naive L-S N=20 +205bp t=2.92; clustered t=0.64; all six
  years positive (sign test p~0.031). Calendar-time PIT portfolio: L-S hold-20
  +41.74% ann, IR 0.98, **t=2.22** — then KILLED: ex-2021 t=0.85;
  2024-onward -6.93% t=-0.27; beta_SPY 1.27, alpha t -0.55 since 2024;
  excess-series max DD -50.5%; avg 13.1 names = ~$38/position at sleeve size.
- Independently reproduces Subrahmanyam's replication (t=2.18 all stocks ->
  1.43 ex-microcap). anderson-review.ucla.edu.
- LEFT ON THE TABLE, unmeasured, not proposed: item 5.02 officer departures
  (unconditional N=5 -32bp **t=-1.98**, the only unconditional signal found
  anywhere, and the SRPT governance lesson made systematic); item 3.02
  dilution (-591bp N=60 but <20 clusters); content-conditioned drift once
  EX-99.1 is fixed.

### Method lessons to reuse (earned this dispatch)
1. **Naive cross-sectional t-stats on event studies LIE.** Always cluster by
   event date. Saw 2.92 -> 0.64 and -2.23 -> +0.20 in one run.
2. **Calendar-time portfolio, not event t-stat**, whenever the question is
   "is this tradeable" — it handles overlap and maps 1:1 to a strategy.
3. **Sub-period split before reporting any t>2.** 2021 carried everything.
4. SRPT lesson held again: beta decomposition turned +25% excess into
   alpha t=1.31 (beta 1.27). Never report excess-vs-SPY alone.
5. Hand-verify one event end to end against printed prices before trusting
   any pipeline's aggregate.
6. Local split: extraction = local qwen (paid off, 155 filings, 58 bad quotes
   caught). Numerical scans = Opus/deterministic; an LLM computing a t-stat
   is error injection, not savings. Don't force the split where "checkable
   output" isn't actually met.

- [CTO note at resolve, 2026-08-21]: edgar.py discard claims and the corpus
  refresh verified line-exact before filing. Entry 8 recorded as MEASURED
  NO-GO (docs/research/ANALYST_CYCLE2_2026-08-21.md); the 5.02 ask filed as
  909c316c; the three harness defects queued for builder D7; API card
  corrected same hour. This dispatch is the seat earning its chair: leg 1
  (a t=2.92 mirage killed before it cost a cycle) in direct service of
  leg 2 (the dataset that makes the next three studies nearly free).
