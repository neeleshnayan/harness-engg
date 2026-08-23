# A survivorship-bias-free S&P 500 study universe for $0: what is actually buildable

**Dr. Mike Darwin (Doc), analyst · 2026-08-23 · approved experiment under
Experiment Delegation v1 · run `run-analyst-pituniverse` · filed verbatim by
the chair, who verified the two line-cited code claims at resolve
(marketdata.py 208–296 contains zero `meta` reads; :378 strips only ".").**

## TL;DR

1. Point-in-time S&P 500 membership is genuinely free and good: 30.5 years,
   703 names that left the index, five spot-checks against deal press
   releases all matched.
2. Free PRICES for the companies that died are not merely thin — they are
   absent or actively wrong. Of 703 leavers our own feed serves a correct
   dead-company series for **6** (0.9%), and all six died in 2018.
3. Worse: for **120 of them (17.1%) the ticker was reused and our feed
   returns the NEW company's prices with no error at all** — `EMC` is a
   Global X ETF, `APC` is ARKO Petroleum first traded 2026-02-12, `SBNY`
   returns the right name with history starting AFTER the bank failed.
   `marketdata.py:208-296` never inspects `result["meta"]` and stamps the
   requested symbol onto whatever comes back. Also `marketdata.py:378`
   rejects dashes: BRK-B and BF-B — two current S&P 500 members — are
   unreachable through our own feed.
4. A usable free-adjacent universe exists only from ~2015, and only via a
   Tiingo key: their keyless ticker list represents recycling structurally
   (two rows per reused ticker; APC's old row ends exactly on the Oxy close
   date), leaver coverage 82.3% post-2015 vs 12.1% pre-2005 — but the free
   tier is 500 symbols/month against our 1,206-ticker universe and licensed
   "Internal Use Only" (the licence question is the CEO's). The 5-URL probe
   is spec'd; probe 1 (`apc/prices?startDate=2019-07-01`) is the decider
   and no bulk pull runs before it returns.
5. **QuantConnect's free cloud is the strongest $0 answer**: survivorship-
   free US equity from Jan 1998, ~27,500 names, delistings/mergers/ticker
   changes — compute in, nothing exports (10 KB logs/backtest), no live
   trading. A place to RUN the survivorship question, not to GET data.
6. **Prices verified from vendor pages: Norgate Platinum is $630 PER YEAR
   recurring** (Silver 270 / Gold 360 / Platinum 630 / Diamond 787.50 —
   three years ≈ the entire $1,885 NAV). Tiingo Power $360/yr. QC
   on-premise $600/yr in LEAN format — whether it includes daily OHLCV is
   NOT stated on their page and remains unverified.

## Membership (verified)

`fja05680/sp500` "S&P 500 Historical Components & Changes (Updated).csv":
2,718 rows, 1996-01-02 → 2026-06-30 (54 days stale), 1,206 distinct
tickers, 503 current members, **703 leavers**, 756 drop transitions on 604
dates, 772 adds on 611 dates. Provenance: the 1996–2019 base is Andreas
Clenow's *Trading Evolved* file, NOT Wikipedia; only post-2019 updates are
Wikipedia-assisted — and dating precision collapses there (median row gap
2d → 15.5d; drops dated within 4 days fall 69.7% → 14.9%; the gap is an
upper bound on error and you cannot tell exact from grid without the S&P
DJI press-release archive, which is free, dated, and one dispatch away).
Spot-checks 5/5 exact vs press releases (TWTR/MON, EMC, TWX, CELG, APC,
DTV). **`hanshof/sp500_constituents` is DEFECTIVE — do not use**: its
script appends today's Wikipedia table each run (120 Saturday + 118 Sunday
rows), and 81 fja tickers are absent from it, 60 of them leavers — EMC on
0 of its rows vs 2,302 of fja's. A survivorship dataset that dropped the
leavers.

## Delisted prices (the hard negative, measured on all 703 leavers)

Yahoo (our feed), classification on the last NON-NULL close: **428 ABSENT
(60.9%) · 120 RECYCLED-alien-series-at-HTTP-200 (17.1%) · 144 still
trading (20.5%) · 5 ambiguous · 6 USABLE (0.9%, all died 2018)**. Stooq is
gated behind a JS proof-of-work challenge served with HTTP 200 and a
796-byte body (a naive puller saves the challenge as data); the analyst
declined to circumvent an access control. Doc's own first pass misread
Yahoo's null-padded YHD calendars as live series (AET) and was corrected —
classify on the last non-null observation, never the last timestamp.

## Panel completeness (the survivorship glow drawn as a picture)

Fraction of that day's real members with a usable price path, free (Yahoo):
**42.0% (1996) → 59.4% (2005) → 77.9% (2015) → 94.4% (2022) → 100.0%
(2026)** — a monotone ramp to exactly 100% at today, by construction. With
a Tiingo key (upper bound, list-evidence only): 52.9% → 76.1% → 94.4% →
98.0% → 100%.

## Family verdicts (MDE stated before any test; residual daily sd measured
at 1.61%, median of 44 sampled current members, beta 1.02)

- **Merger arb**: ~479 true events; 6 free; 125 with Tiingo of which 110
  post-2015 = ONE regime, no sub-period split possible → **stays fenced**.
- **Distress**: n=28 Q-suffix bankruptcies in 30.5 years (~0.92/yr) →
  **fenced structurally**; no vendor changes n.
- **Delisting/index deletion**: 236 of 756 events covered free (n=196
  names, MDE 2.06% at N=20) → **partially open**, conditional on sourcing
  deletion REASONS point-in-time from the S&P DJI press-release archive
  (free) — without reasons, "still trading today" is a look-ahead.
- **Going-private**: unclassifiable in this data — but **SC 13E-3 is the
  SEC's going-private form and the fund already holds 372,263 EDGAR filing
  records**: an untried, free, dated primary-source classifier. A lead.
- **Index additions (Ed's Fast-Track ask)**: only 66.1% of 772 add events
  are on tickers alive today; censoring is era-shaped (46.9% / 66.5% /
  83.5%) and one-directional. **Pre-2015 inclusion studies are not usable
  free.**

## Standing scope constraint (adopted by the chair at resolve)

No cross-sectional claim covering 1996–2014 may be filed off free data by
any seat (free completeness 42–78% in those years, non-random). Where a
study must cover those years, it runs in the QC free cloud or it is not
run.

## The recommendation

**Do not buy data this month.** (1) $0: run the survivorship question in
QuantConnect's free cloud over 1998–2026 — it prices the paid options
before we pay. (2) $0: the Tiingo 5-URL probe the moment the CEO creates a
key, and the SC 13E-3 classifier from EDGAR metadata already held. (3)
Only then decide $360 vs $630/yr — against a named study, not a coverage
table. Every Norgate coverage claim in circulation is vendor marketing
until someone at this firm has seen their data.

Sources: fja05680/sp500 and hanshof/sp500_constituents (GitHub), S&P DJI
press releases, dell.com, businesswire.com, news.bms.com, sec.gov,
prnewswire.com, tiingo.com/pricing and supported_tickers.zip,
quantconnect.com data + tier docs, norgatedata.com/stockmarketpackages.php
— URLs in the run record. Cached artifacts: `scratchpad/pit/`.
