# THE ETH DOSSIER v1 — 2026-08-23 (run-analyst-ethdossier1)

**The second coverage pilot, and the first on a non-equity. Under the amended
routing this is an UNDERSTANDING instrument: risk parameters to Stan,
cross-sectional / counterparty leads to Ed, never a per-name candidate.**

**VERDICT IN ONE LINE: the flow map is real, measurable and free — and every
mechanical flow on it is currently paying LESS than a T-bill or moving LESS
than the bid-ask. The one thing worth carrying into the book is a RISK
parameter, not a trade: 60.4% of the daily variance of the only ETH
instrument we can actually hold sits in a gap our exit machinery cannot see.**

Every number below was computed by this seat from a named series over a named
window, or carries the URL it came from. Where a number could not be obtained
it is reported ABSENT.

---

## 0. CONTRARY FACTS FIRST (Darwin's rule — these govern everything after)

1. **The biggest number I found is an artifact and I am reporting it as one.**
   ETH's cumulative weekend-only return over 2017-11-09→2026-08-23 is
   **+632.7%** against a weekday-only **+4.7%** (n=918 / 2,291 UTC days,
   Yahoo `ETH-USD` closes). It looks like the whole asset is a weekend
   phenomenon. It is not. Section 5 kills it four separate ways, including on
   its own placebo ladder.
2. **The tape has already priced the regime.** Perpetual funding — the
   canonical "longs pay shorts" carry — has collapsed from **+37.54%/yr
   annualised in 2021 to +1.41%/yr in 2026 YTD** (95% CI +0.94% to +1.89%,
   n=705 eight-hour prints). Against FEDFUNDS at **3.63%** (FRED, Jul-2026)
   the crypto basis trade currently pays **less than cash**.
3. **ETH is not a diversifier in the current regime.** 250-day rolling
   correlation with QQQ on matched equity-session dates is **+0.49** as of
   2026-04, having ranged +0.02 (2019) to +0.53 (2022-10). Anyone holding ETH
   "for diversification" is holding levered QQQ with an 81%/yr residual.
4. **ETH has NO unlock calendar, and that is a finding, not a gap.** Absence
   confirmed below — the single most-cited crypto flow mechanism (vesting
   cliffs) does not exist for this asset at all.

---

## 1. THE FLOW MAP — five candidate flows, each priced before it is written

The discipline carried from the META dossier's post-mortem (Ed's counterparty
kill on the index-share-count flow): **name who pays, name why they keep
paying, and price the flow against the cost floor BEFORE calling it a flow.**
Four of the five fail that test. One survives as a risk parameter.

### 1.1 Perpetual funding — REAL, MEASURED, FREE, AND CURRENTLY NOT PAYING

**Who pays whom**: on a perpetual swap the crowded side pays the other every
8 hours. Positive funding = longs pay shorts. **Why they keep paying**: a perp
is levered spot exposure with no borrow, no expiry and no delivery; leveraged
longs are structurally willing to rent it. That is a genuine, durable reason a
counterparty keeps losing.

**Measured, full history, no account** —
`https://fapi.binance.com/fapi/v1/fundingRate?symbol=ETHUSDT` (paged, n=7,385
prints, 2019-11-27 → 2026-08-23; BTCUSDT n=7,619 pulled as the sibling
control):

| window | mean per 8h | annualised (x3x365) | share of prints > 0 |
|---|---|---|---|
| full sample 2019-11 to 2026-08 | +0.0127% | **+13.90%** | 86.3% |
| 2020 | +0.0250% | +27.41% | 97.4% |
| 2021 | +0.0343% | **+37.54%** | 95.9% |
| 2022 | +0.0007% | +0.79% | 65.8% |
| 2023 | +0.0075% | +8.26% | 90.9% |
| 2024 | +0.0118% | +12.96% | 95.8% |
| 2025 | +0.0045% | +4.93% | 83.8% |
| **2026 YTD (n=705)** | **+0.0013%** | **+1.41%** | 66.2% |
| last 90 days | +0.0031% | +3.41% | 81.9% |
| BTCUSDT full sample | +0.0106% | +11.61% | 85.7% |

Distribution (ETH, full sample): p1 -0.0164%, p5 -0.0052%, p95 +0.0560%,
p99 +0.1355%, max +0.3750%, min -0.3563%. **34.8% of all prints sit exactly
at +0.0100%** — Binance's interest-rate default, which is itself +10.95%/yr:
the *neutral* state of this market is not zero. Sum of all funding paid to
shorts across the sample = **+93.8% of notional**.

**PRICED**: the 2026 realised carry is **+1.41%/yr, 95% CI [+0.94%, +1.89%]**.
FEDFUNDS is **3.63%** and DGS10 **4.69%**
(`https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS`, `?id=DGS10`,
pulled 2026-08-23). A cash-and-carry (short perp / long spot) therefore earns
**~220bp LESS than T-bills** before any execution, custody, margin or
exchange-solvency cost. **Flow real; trade currently negative against the
risk-free rate.**

**Where the series lives, free and keyless** (all four verified reachable from
this host, 2026-08-23): Binance `fapi/v1/fundingRate`; Bybit
`https://api.bybit.com/v5/market/funding/history?category=linear&symbol=ETHUSDT`;
OKX `https://www.okx.com/api/v5/public/funding-rate-history?instId=ETH-USDT-SWAP`;
Deribit
`https://www.deribit.com/api/v2/public/get_funding_rate_history?instrument_name=ETH-PERPETUAL`
(hourly `interest_8h`/`interest_1h` — the richest of the four). All three USDT
venues printed the identical +0.0100% default on the most recent stamp, so a
"three-venue cross-check" on funding is **not three independent observations**.

### 1.2 Spot-ETF creations/redemptions — REAL FLOW, TOO SMALL TO MOVE ANYTHING

**Source, free and machine-parseable** (403s under the default fetch UA;
returns 185KB/557KB of HTML under a browser UA — measured):
`https://farside.co.uk/eth/` and
`https://farside.co.uk/ethereum-etf-flow-all-data/`. Parsed: **533 daily rows,
2024-07-23 → 2026-08-21, 10 products**.

- **Cumulative net flow since launch: +$12,154m.** ETHA +$12,170m;
  ETHE **-$5,350m** (the converted 2.50%-fee trust, still bleeding);
  FETH +$2,190m; ETH (Grayscale mini) +$1,853m.
- **Average daily net flow +$23.2m**; max single day +$1,018.8m; min -$465.1m.
  Median |net flow| $47.8m, mean $84.6m, p95 $307.8m.
- Fee table off the same page: ETHA 0.25%, ETHB 0.25%, FETH 0.25%, ETHW 0.20%,
  TETH 0.21%, ETHV 0.20%, QETH 0.25%, EZET 0.19%, **ETHE 2.50%**, ETH 0.15%.
  **Staking fees now exist** — ETHB 10%, TETH 25%, ETHE 23%, ETH 6% — i.e. the
  wrappers stake, which links section 1.3 to section 1.2 for the first time.
- Our own feed's 60-day median dollar ADV: **ETHA $406.7m/day**, ETH (Grayscale
  mini) $38.6m, ETHE $28.5m (computed from `fetch_daily_bars` closes x volumes,
  last 60 bars to 2026-08-21).
- ETH spot 24h volume **$15,814.6m**; market cap $297.68bn; circulating supply
  120,681,537 ETH, **no max supply**
  (`https://api.coingecko.com/api/v3/coins/ethereum`, 2026-08-23T21:47Z).

**PRICED**: the median day's net ETF flow is **0.302% of ETH spot volume**; the
*average* is 0.147%. Ed's floor from the equity side — index share-count
updates move **0.15 bps per 2% share change** with ~87% overnight reversal —
applies with room to spare. **Who pays?** An AP delivers cash, the issuer buys
spot from a market maker compensated by the creation spread and under no
obligation to transact at a bad price. **There is no mandated loser.** By the
rule Ed wrote into my memory, this is a story, not a flow.

**And I tested it rather than asserting it.** Regression of ETH daily return
(UTC `ETH-USD` closes) on same-day net flow, coefficient in bps of ETH per
$100m of flow, n=533:

| alignment | beta (bps per $100m) | t | R2 |
|---|---|---|---|
| k = -20 | +18.7 | +1.68 | 0.005 |
| k = -5 | +27.6 | +2.53 | 0.012 |
| k = -2 | +41.8 | +3.93 | 0.028 |
| **k = -1 (BEFORE the flow)** | **+70.7** | **+6.14** | **0.066** |
| k = 0 (same day, not tradeable) | +64.0 | +5.38 | 0.052 |
| **k = +1 (the tradeable one)** | +28.6 | +2.53 | 0.012 |
| k = +2 | -1.1 | -0.10 | 0.000 |
| k = +5 / +10 / +20 | +7.1 / +3.2 / +3.1 | <= +0.65 | ~0 |

**MDE stated before the test (clause 5)**: ETH daily sd over the flow window =
4.02%; mean-effect MDE at |t|=2 with n=533 is **0.348%/day**; a tercile
long-short with 177 days per leg needs **0.854%/day**. The realised
high-minus-low tercile is **+0.620%/day, t=+1.55** — *below its own pre-stated
MDE*, i.e. structurally underpowered, not merely unproven.

**THE KILL**: the backward placebo at k=-1 is **larger** than the forward
coefficient at k=+1 (+70.7 vs +28.6). **Flow chases price; price does not chase
flow.** And even taking +28.6 bps/$100m at face value, a median $47.8m day
predicts **+13.7 bps** against an Alpaca crypto round trip of **30-50 bps**
(section 3.3). Dead on costs by 2-4x, before the placebo.

*Alignment note (point-in-time)*: Farside's date D is the US session whose 4pm
ET NAV struck the creation. Yahoo's `ETH-USD` bar for D closes at D+1 00:00 UTC
= D 20:00 EDT, four hours after that strike — so "same day" already contains
the flow window and is not tradeable. k=+1 is the first clean bar.

### 1.3 Staking entry/exit queues — A SUPPLY LOCK, NOT A TRANSFER

`https://www.validatorqueue.com/` (data attributed on-page to beaconcha.in; the
beaconcha.in API itself now **401s without a key** — measured; its
`/api/v1/validators/queue` also returned 522 on first attempt):

- **Entry queue 2,206,906 ETH — wait 38 days 8 hours.** Churn 256/epoch.
- **Exit queue 192 ETH — wait 5 minutes.** Sweep delay 7.8 days.
- Active validators 902,197; **staked ETH 42.3M = 34.68% of supply**;
  **APR 2.67%**.

**Arithmetic** (mine, from the page's own numbers): 2,206,906 / 38.33 days =
**57,580 ETH/day**, matching 256 ETH/epoch x 225 epochs/day = 57,600 — so the
churn is ETH-denominated and the queue is rate-limited at **~$142m/day** at
$2,467. That is **0.90% of spot daily volume**.

**Who pays?** Nobody. A queue is a *lock*, not a transfer: no counterparty is
compelled to trade at a worse price because ETH is waiting to be staked. **"Long
entry queue = bullish" is a story.** Priced: 2.2M ETH = 1.83% of supply = **0.34
days of spot volume**, spread over 38 days.

**The genuinely useful half is the EXIT side, and it is a RISK parameter**:
42.3M staked ETH cannot leave faster than 57,600 ETH/day, so a **full unwind is
rate-limited to ~734 days**. Staked ETH is therefore *not* liquid collateral and
cannot produce an instantaneous supply shock; equally, an ETF that stakes
(ETHB/TETH/ETHE/ETH per section 1.2) holds an asset whose redemption path is
queue-dependent. **Route to Stan.**

### 1.4 Token unlocks — THE ABSENCE IS THE FINDING

**ETH has no unlock calendar.** Confirmed against
`https://defillama.com/unlocks/ethereum` and
`https://tokenomist.ai/ethereum/unlock-events`: all historical allocations (ICO,
foundation, early contributors) are fully released; no vesting cliffs are
scheduled for 2026 or beyond; and there is no maximum supply — CoinGecko returns
`max_supply: None` with `total_supply == circulating == 120,681,537` (verified
directly, section 1.2).

**What this means for the cross-section, and it is Ed's, not mine**: the
unlock-cliff mechanism — a dated, pre-announced, price-insensitive supply
increase with a *forced* seller — is one of the few crypto flows with a
genuinely mandated loser. **ETH does not have it. Assets with live vesting
schedules do.** That is a cross-sectional lead, and it points away from where a
single-name coverage model would have looked.

The ETH analogue of an unlock is *net issuance* = staking rewards minus EIP-1559
burn. **REPORTED ABSENT**: no verified net-issuance series from a free keyless
source was obtained in this dispatch — `api.ultrasound.money` failed DNS
resolution from this host (`getaddrinfo failed`), and CoinGecko's supply endpoint
gives a point value, not a history. Do not fill this with an estimate.

### 1.5 Liquidation cascades — MEASURABLE ONLY AS A PROXY, FREE

- **Coinglass, the standard liquidation series, is key-gated**:
  `https://open-api.coinglass.com/public/v2/liquidation_info?symbol=ETH` ->
  `{"code":"30001","msg":"API key missing."}`.
- **Free proxies that DO work, no account** (all verified 2026-08-23): Binance
  open-interest history
  `https://fapi.binance.com/futures/data/openInterestHist?symbol=ETHUSDT&period=1d`
  (**30-day limit** — sumOpenInterest 2,320,370 ETH / $5.398bn on 2026-08-21;
  2,422,087 ETH / $6.094bn on 2026-08-22); live OI `fapi/v1/openInterest`
  (2,377,686 ETH); positioning `futures/data/topLongShortAccountRatio`
  (2026-08-22: 59.55% long / 40.45% short, ratio 1.4722); Deribit option book
  with `mark_iv` (ETH-28AUG26-2020-P at 91.2 IV, underlying 2472.33).
- **Scale**: perp OI $5.4-6.1bn against a $297.7bn market cap and $15.8bn daily
  spot volume — perp OI is **~2.0% of market cap** and **~0.38 days of volume**.

**HONEST LIMIT**: liquidation *history* is not freely available; only the 30-day
OI window is. Any liquidation-cascade study is therefore a **forward collection
problem** (start recording OI daily now) or a paid-data problem. Stated, not
papered over.

### 1.6 One flow nobody asked about, and it is the biggest

`https://api.coingecko.com/api/v3/companies/public_treasury/ethereum`:
**public-company treasuries hold 7,829,420 ETH = $19.33bn = 6.49% of ETH market
cap**, of which **BitMine Immersion alone holds 5,815,164 ETH**. That is 3.4x
the total ETF flow of section 1.2, sitting in equity-listed vehicles.

**Route to Ed as a cross-sectional lead**: these are US-listed issuers with SEC
filings, a NAV and a share count — the *equity* side of a crypto flow, which is
the side our filing machinery can already read. A digital-asset treasury company
trading at a premium/discount to NAV with an at-the-market issuance programme is
the shape that has a real loser (the ATM buyer funding accretive issuance).
Not measured here; named and handed over.

---

## 2. RISK PARAMETERS FOR STAN

All from `fetch_daily_bars` (Yahoo `ETH-USD`, UTC daily closes,
2017-11-09 to 2026-08-23, n=3,209 returns) unless stated.

### 2.1 The headline number, and it is the reason this section exists

**ETHA (iShares Ethereum Trust — the only ETH instrument our venue can hold):
60.4% of daily return variance is in the OVERNIGHT/WEEKEND GAP.**

| instrument (2024-07 to 2026-08) | gap sd | gap share of variance | intraday sd | close-close sd | worst gap |
|---|---|---|---|---|---|
| **ETHA** | **3.49%** | **60.4%** | 2.77% | 4.49% | **-27.28%** |
| SPY | 0.66% | 39.8% | 0.89% | 1.05% | -3.99% |
| QQQ | 0.90% | 41.0% | 1.14% | 1.40% | -5.36% |

ETHA gap percentiles: p5 -4.52%, p1 -7.36%. **Monday gaps (n=100): sd 5.58%,
worst -27.28%.** The five worst gaps are **2024-08-05 (-27.28%), 2025-02-03
(-22.77%), 2025-04-07 (-17.01%), 2026-02-02 (-13.24%), 2025-02-25 (-8.65%)** —
four of five are Mondays, and in each case spot ETH had already moved over the
weekend (ETH-USD Fri->Mon: -19.05%, -12.54%, -14.33% respectively).

**The mechanism, named**: crypto is the only asset class that prices weekend
macro news, and the ETF wrapper delivers that repricing as a single ungoverned
open gap. **Consequence for exit rules**: our exit machinery marks and fires on
daily bars and live session marks. On a crypto-proxy position it is structurally
unable to act on the majority of the risk. **Size off the GAP distribution (p1 =
-7.36%, realised worst -27.28%), not off close-to-close vol.** A stop set from
close-to-close sd is not a tighter stop — it is a stop that does not exist for
60.4% of the variance.

Bootstrap (2,000 resamples of 85 days) puts the gap-variance share at **median
59.8%, 5th pct 44.3%, 95th pct 75.1%** — the number is stable, not a
small-sample fluke.

### 2.2 Realised volatility — pick your calendar, and say which

**A crypto series has 365 observations per year, an equity series 252.**
Annualise at sqrt(365) for ETH and sqrt(252) for equities, or the comparison is
wrong by **sqrt(365/252) = 1.2039**.

| series | n | daily sd | annualised | skew | excess kurtosis | worst day |
|---|---|---|---|---|---|---|
| ETH-USD (own calendar, sqrt365) | 3,209 | 4.43% | **84.6%** | -0.08 | 6.27 | -42.35% |
| ETH on matched equity dates (sqrt252) | 2,205 | 4.76% | **75.6%** | -0.13 | 5.86 | -42.35% |
| BTC-USD (sqrt365) | 4,252 | 3.47% | 66.3% | -0.11 | 8.10 | -37.17% |
| SPY (sqrt252) | 2,925 | 1.11% | 17.6% | -0.31 | 14.03 | -10.94% |
| QQQ (sqrt252) | 2,925 | 1.38% | 21.9% | -0.19 | 7.28 | -11.98% |
| IWM (sqrt252) | 2,925 | 1.41% | 22.4% | -0.48 | 7.63 | -13.27% |

Note the asymmetry: ETH's *weekday* sd is 4.74% and its *weekend* sd 3.54%
(ratio 0.746) — which is why the matched-date sd (4.76%) is **higher** than the
all-days sd (4.43%). **A study that samples ETH only on equity sessions is
sampling its high-volatility days.**

Trailing realised vol (sqrt365): 20d **81.8%**, 60d 59.9%, 125d 55.1%, 250d
63.9%, 750d 70.9%. By year: 2018 106.9% / 2019 78.5% / 2020 94.2% / 2021 106.8%
/ 2022 86.3% / **2023 46.6% (the floor)** / 2024 65.0% / 2025 75.1% / 2026 YTD
65.2%. **The eight-year range is 46.6%-106.9%; there is no "normal" ETH vol,
there is a regime.**

### 2.3 Tail behaviour vs equities

ETH: p1 -12.63%, p5 -6.68%, ES@1% **-16.35%**, ES@5% -10.17%, worst -42.35%,
best +26.46%. SPY: p1 -3.17%, ES@1% -4.63%, worst -10.94%.

**Excess kurtosis is LOWER for ETH (6.27) than for SPY (14.03).** ETH is not
fat-tailed relative to its own vol — it is four times as volatile with an almost
symmetric distribution (skew -0.08 vs SPY -0.31). **This is the useful
correction to intuition**: the danger in ETH is scale, not surprise. A
Gaussian-ish 4.4%/day asset does not need a jump model; it needs a position size
four times smaller.

### 2.4 Correlation regime and the factor verdict

Matched equity-session dates (n=2,205):

| vs | corr | beta |
|---|---|---|
| SPY | +0.328 | +1.31 |
| QQQ | +0.335 | +1.07 |
| IWM | +0.327 | +1.02 |
| GLD | +0.123 | +0.55 |
| TLT | **-0.008** | -0.04 |
| HYG | +0.241 | +2.13 |
| UUP | -0.114 | -1.24 |
| **BTC-USD** | **+0.782** | +1.01 |

Rolling 250-day correlation vs QQQ, 6-month steps: 2018-11 **+0.15** / 2019-11
**+0.07** / 2020-11 +0.45 / 2021-11 +0.24 / 2022-10 **+0.53** / 2024-04 **+0.14**
/ 2025-04 +0.48 / 2026-04 **+0.49**.

Beta ladder vs QQQ: full-sample **1.12**, 3y **1.28**, 2y **1.43**, 1y **1.51**,
6m **0.94**. **REFUSE any proposal that prices ETH off a specific equity beta** —
the same lesson the META dossier learned on rate and dollar betas, now confirmed
on a second asset. R2 is 0.10-0.21 in every window; **residual vol is 54-81%/yr
at every horizon** (3.72-3.83%/day on the 1-3y windows). Eighty to ninety percent
of ETH's variance is idiosyncratic to any equity factor we can build.

The one stable relationship is **ETH<->BTC at +0.78**. Any ETH position is ~78% a
crypto-beta position; ETH-vs-BTC is the only pair in which ETH is a distinct
asset.

**MDE constants for this asset (reuse these, do not re-derive)**: residual sd vs
QQQ = **3.7-3.8%/day** on 1-3y windows. MDE at |t|=2 for a 20-day cumulative
event window: **n=20 events -> 7.5%; n=40 -> 5.3%; n=100 -> 3.3%.** Compare the
equity panel constant already in my memory (residual sd vs SPY = 1.61%; n=100 ->
2.88%). **ETH needs ~1.2-2.3x the effect size for the same event count.**

### 2.5 Drawdown geometry — the parameter that ends the conversation

| series | max DD | peak -> trough | longest underwater run | % of bars >20% below peak |
|---|---|---|---|---|
| **ETH-USD** | **-94.0%** | 2018-01-13 -> 2018-12-14 | **1,382 bars (3.8y)** | **88%** |
| BTC-USD | -83.4% | 2017-12-16 -> 2018-12-15 | 1,079 bars | 63% |
| SPY | -33.7% | 2020-02-19 -> 2020-03-23 | 488 bars | 2% |
| QQQ | -35.1% | 2021-12-27 -> 2022-11-03 | 493 bars | 9% |

**ETH has spent 88% of its listed life more than 20% below a prior peak.** For a
fund whose drawdown reference is a governed, re-baselined number, that is not a
footnote — a buy-and-hold ETH sleeve is a position that is *usually* in a large
drawdown by construction.

### 2.6 Session structure — what "close" means, precisely

- **ETH-USD daily bars are stamped 00:00:00 UTC (bar START) and their close is
  at 24:00 UTC**; SPY bars are stamped 13:30 UTC (09:30 ET) and close at 20:00
  UTC (16:00 ET, EDT). Verified on raw Yahoo timestamps, 2026-08-23.
- **Therefore ETH's date-D close is FOUR HOURS LATER than SPY's date-D close**
  (five in EST). A signal that reads ETH's date-D close and trades an equity at
  that day's close is **look-ahead by four hours**. The reverse (equity close ->
  crypto trade) is executable.
- The same-day ETH/SPY correlation of **+0.328** is contemporaneous overlap, not
  prediction: **corr(ETH_t+1, SPY_t) = -0.069** and **corr(ETH_t, SPY_t+1) =
  -0.016**. No lead-lag in either direction at daily frequency. The four-hour
  overlap is a *contamination* channel, not an *edge* channel.
- ETH trades 365 days a year, including every US market holiday. Our matched
  panel loses **1,004 of 3,209 ETH days (31.3%)** the moment it is aligned to an
  equity calendar.

---

## 3. WHAT OUR OWN MACHINERY CAN SEE — measured, with the gaps named

### 3.1 The feed: identity first (clause 4), and it holds

app/fund/marketdata.py was fixed for the BTC identity defect I reported on
2026-08-21, and the fix works. Verified against Yahoo instrument metadata
(chart.result[0].meta) — the field marketdata.py:208-296 still never reads, so I
read it directly:

| symbol asked | instrument returned | type | exchange | first trade |
|---|---|---|---|---|
| ETH (bare) | **Grayscale Ethereum Mini Trust ETF** | ETF | NYSEArca | 2024-07-23 |
| ETH-USD | **Ethereum USD** | CRYPTOCURRENCY | CCC | 2017-11-09 |
| ETHE | Grayscale Ethereum Staking ETF | ETF | NYSEArca | 2019-06-14 |
| ETHA | iShares Ethereum Trust ETF | ETF | NasdaqGM | 2024-07-23 |
| BTC (bare) | Grayscale Bitcoin Mini Trust ETF | ETF | NYSEArca | 2024-08-01 |

_crypto_id (marketdata.py:145-161) routes a bare ETH to equities because it has
an EDGAR CIK, and an explicit ETH-USD to crypto. **The rule for every seat:
write ETH-USD, never ETH.** A bare ETH in a study is a $23 ETF, not a $2,467
asset — a ~107x error, exactly the shape of the BTC defect.

**Coverage limit, reported honestly**: Yahoo's ETH-USD starts **2017-11-09**.
Ethereum launched 2015-07-30. **Our feed cannot see ETH's first 27 months**,
including the 2017 run-up. Any "full history" claim on ETH from this feed is
false.

### 3.2 THE DEFECT I FOUND: our CoinGecko bars are labelled one day late

marketdata.py:186-189 keys each CoinGecko price by the UTC date of its timestamp:

    for ms, px in payload.get("prices", []):
        d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
        by_date[d] = float(px)  # last price seen for the date = daily close

CoinGecko's market_chart?interval=daily returns points stamped at **D
00:00:00 UTC**, whose value is the price *at that instant* — i.e. the **close of
D-1**. Yahoo stamps the bar at D 00:00 UTC and puts the close *of D* in it. The
two conventions are one day apart, and the code adopts CoinGecko's stamp as the
bar date.

**Measured, n=349 overlapping days (CoinGecko days=350 vs Yahoo range=2y):**

| pairing | median absolute difference | within 25 bps |
|---|---|---|
| cg[D] vs yahoo[D] (same date) | **169.9 bps** | 40 / 349 |
| **cg[D] vs yahoo[D-1] (shifted)** | **4.4 bps** | **322 / 349** |

Worked example, raw payloads 2026-08-23: CoinGecko 2026-08-20T00:00Z = 2253.56
matches Yahoo's **2026-08-19** close 2251.46; CoinGecko 2026-08-23T00:00Z =
2423.41 matches Yahoo's **2026-08-22** close 2424.25.

**Three consequences, in order of money:**

1. **The last bar is internally inconsistent.** CoinGecko also appends a live
   point (2026-08-23T21:47Z = 2466.06) which maps to the *same* date key, so
   by_date overwrites: the final bar is today's live price while every earlier
   bar is yesterday's close. The final *return* therefore spans ~2 days.
   Measured on 2026-08-23: our CoinGecko series implies **-2.12%** for the day;
   the true 08-22 to 08-23 move was **+1.72%**. **Wrong sign on the one bar a
   live signal reads.**
2. **Which source you get depends on the window.** fetch_daily_bars (:368-376)
   tries CoinGecko first and falls back to Yahoo on BarsError. CoinGecko's free
   tier now returns **HTTP 401 for days=400** and for any /range request outside
   ~365 days (measured). So <=365-day windows go to CoinGecko (shifted);
   >365-day windows go to Yahoo (correct). **The belt asks for
   lookback_days=2000; the endpoint default is 180.** A strategy fitted on belt
   history and marked on endpoint marks is mixing two conventions one day apart.
3. **My own near-miss, recorded so the next seat does not repeat it.** My first
   comparison concluded the two feeds were *bit-identical on 299/299 days*. They
   were not: fetch_daily_bars(..., start=, end=) inside 365 days succeeds on
   CoinGecko's /range, so I had compared CoinGecko to CoinGecko. **Always print
   and assert Bars.source before comparing two fetches.** (Third "absence wearing
   values" catch this week, and the first where the absence was mine.)

**Ticket-shaped**: subtract one day from CoinGecko's date key, and drop or
explicitly stamp the partial final point. This is control-adjacent code (marks
feed NAV), so it is the chair's and the builder's, not mine.

### 3.3 Execution — we cannot trade ETH today, and the reason is one line

- **Alpaca supports the asset**: 20+ coins / 56 pairs including **ETH/USD**,
  24/7, minimum order 0.0001, paper available
  (https://docs.alpaca.markets/docs/crypto-trading). **Fees 15-25 bps
  maker/taker at the $0-100k 30-day-volume tier** — our tier. **Round trip
  30-50 bps.**
- **Our connector cannot price it.** app/fund/connectors/alpaca.py:156-161:

        def _fetch_price(self, symbol: str) -> float:
            from alpaca.data.requests import StockLatestTradeRequest
            res = self._data_client().get_stock_latest_trade(
                StockLatestTradeRequest(symbol_or_symbols=symbol))
            return float(res[symbol].price)

  An equity-only request type. A crypto symbol has no path to a mark.
- **Our universe cannot see it.** app/fund/universe.py:115 requests
  asset_class=AssetClass.US_EQUITY. The hunting ground is equity-only by
  construction — which is *also* why the ETFs (ETHA/ETHE/ETH) are the only
  reachable exposure, and they carry section 2.1's gap.
- **Order construction is asset-class-blind** (alpaca.py:378-386:
  TimeInForce.DAY on every order). DAY does not mean on a 24/7 venue what it
  means in an equity session.

**So the honest statement: ETH exposure at Krypton today = ETHA/ETH/ETHE equity
ETFs, in the 09:30-16:00 window, with 60.4% of the risk outside it.**

### 3.4 The belt — it can run ETH, and the gate will misreport it

- The belt's data path is a custom PythonData class (SpineBars) hitting
  GET /fund/marketdata/bars?symbol=...&format=csv
  (lean_workspace/algorithms/*/main.py). **The endpoint accepts ETH-USD**
  (app/api/v1/fund.py:4077, max_length=12) — verified live: returned 10
  CoinGecko bars including **2026-08-22 and 2026-08-23, both weekend days**.
- **LEAN's default exchange hours for custom data are ALWAYS OPEN**
  (https://www.quantconnect.com/docs/v2/writing-algorithms/importing-data/streaming-data/custom-securities/key-concepts),
  so a 7-day bar stream would be *consumed*, not silently dropped. **Crypto
  backtesting is available today with no new code.**
- **But the measurement would be wrong in a known direction.**
  leanrunner.py:1651 recomputes sd * math.sqrt(252.0) and gate.py:1000 carries
  the same note: the engine annualises a calendar-day series at sqrt(252). On a
  genuine 365-day series that **understates annualised vol by 1.2039x** — an ETH
  strategy at a true 84.6% vol would be reported at ~70.3%, and every Sharpe /
  PSR / vol-cap criterion downstream inherits it. The comment at
  leanrunner.py:1662 already says this; nothing acts on it.
- **Benchmark**: _declared_universe (leanrunner.py:2722) benchmarks against the
  declared universe. An ETH strategy benchmarked against a 252-bar SPY series is
  compared over a different number of observations. **Name the benchmark
  explicitly in any ETH candidate, or the belt picks one on a different
  calendar.**

### 3.5 What we could NOT see — the absence list

- **Liquidation history**: key-gated (Coinglass). Only 30 days of OI free.
- **Net ETH issuance / burn history**: ultrasound.money unreachable from this
  host (DNS). No free substitute found in this dispatch.
- **Options surface history**: Deribit's live book is free; historical IV was not
  pulled and is not known to be free.
- **Intraday crypto bars**: INTRADAY_TIMEFRAMES exists in marketdata.py but was
  not probed for crypto. Untested.
- **ETF per-share ETH holdings**: issuer pages 403 from here (iShares,
  Grayscale); Farside's fee/flow table was the substitute. The trusts file with
  the SEC, so this is reachable through EDGAR — **not attempted, named as v2
  work**.
- **beaconcha.in API**: now key-gated. The queue numbers above come from
  validatorqueue.com's rendering of it — **one hop from primary**, and labelled
  as such.

---

## 4. TEN DATED, FALSIFIABLE PREDICTIONS

Each carries its series, window, clock and statistic (card item 15) and its MDE
(clause 5). The META scoring said my **instrument** predictions beat my
**statistic** predictions, so four of these ten are instrument predictions and
none is a price forecast.

**P1 — 2026-09-30.** Binance ETHUSDT perp funding over 2026-01-01..2026-09-30
annualises **below 3.0%**.
*Computation*: fapi/v1/fundingRate?symbol=ETHUSDT; clock fundingTime UTC;
statistic mean(rate) x 3 x 365.
*MDE*: sd of 8h prints 0.00575%; at n~2,000 the SE of the annualised mean is
**0.28%/yr** — decisively powered. Current YTD +1.41%, CI [+0.94, +1.89].

**P2 — 2026-12-31.** ETH realised vol over 2026-09-01..2026-12-31 lands in
**[45%, 100%]**.
*Computation*: Yahoo ETH-USD UTC closes, close-to-close, sd x sqrt(365).
*MDE*: 8-year annual range 46.6-106.9%; at n~122 days the sd of the vol
estimate is about vol/sqrt(2n) ~ 4pp, so the band is ~7 sigma wide — this is a
regime claim, and a break of it is a regime change worth a dispatch.

**P3 — 2026-12-31.** ETHA overnight-gap share of daily variance over
2026-09-01..2026-12-31 lands in **[44%, 75%]**.
*Computation*: fetch_daily_bars("ETHA") opens/closes; var(open/prevclose-1) /
var(close/prevclose-1).
*MDE*: bootstrap (2,000 draws of 85 days) gives median 59.8%, 5th 44.3%, 95th
75.1% — **the band is the MDE**, stated before the window opens.

**P4 — 2026-11-30.** Farside cumulative US spot ETH-ETF Total lands in
**[$10.0bn, $15.0bn]**.
*Computation*: farside.co.uk/ethereum-etf-flow-all-data/, browser UA, final
summary row.
*MDE*: now $12.154bn; average +$23.2m/day x ~70 sessions = +$1.6bn central
case; the band is roughly +/-3 sd of the daily flow distribution over 70 days.

**P5 — 2026-12-31.** The ETH validator **entry** queue still exceeds the **exit**
queue in ETH terms.
*Computation*: validatorqueue.com header figures, read on the date.
*MDE*: binary. Now 2,206,906 vs 192 ETH — an 11,500x ratio; falsified only by a
genuine regime change, which is exactly what would make it worth knowing.

**P6 — 2026-12-31.** **No scheduled ETH token unlock** is listed on DefiLlama or
Tokenomist.
*Computation*: the two unlock pages, read on the date.
*MDE*: binary. This makes the absence claim of section 1.4 falsifiable rather
than rhetorical.

**P7 — 2026-10-31.** Re-running section 1.2's regression through 2026-10-31,
the **k=-1 coefficient still exceeds k=+1**, and **k=+2 stays |t|<2**.
*Computation*: Farside daily Total x Yahoo ETH-USD returns; OLS, bps per $100m,
placebo ladder k in {-20..+20}.
*MDE*: n grows 533 -> ~580; mean-effect MDE at |t|=2 is ~0.33%/day. The
falsifiable content is the **ordering**, not the level.

**P8 — 2026-12-31.** 250-day rolling corr(ETH-USD, QQQ) on matched equity
sessions stays in **[0.20, 0.60]**.
*Computation*: matched-date daily returns, Pearson, trailing 250 observations.
*MDE*: 8-year realised range 0.02-0.53; last three semi-annual readings
0.48/0.45/0.49; SE(corr) at n=250 is ~0.055.

**P9 — 2026-12-31 (INSTRUMENT).** Our CoinGecko-served bars are **still labelled
one day late** unless a builder ticket lands.
*Computation*: compare _from_coingecko("ETH-USD",350) to
_from_yahoo("ETH-USD",400) at D and at D-1; median absolute difference.
*MDE*: binary against today's 169.9 bps (same date) vs 4.4 bps (shifted).

**P10 — 2026-12-31 (INSTRUMENT).** **ETH/USD remains untradeable through our
connector** unless a builder ticket lands.
*Computation*: alpaca.py::_fetch_price still constructs StockLatestTradeRequest;
universe.py still filters AssetClass.US_EQUITY.
*MDE*: binary on the code.

**Deliberately NOT predicted**: the ETH price, in any form. Nothing in this
dossier supports a directional view, and inventing one to fill a table is how a
coverage model becomes a tout sheet.

---

## 5. THE WEEKEND EFFECT — killed four ways, and why I am reporting the corpse

The headline in section 0.1 (+632.7% weekend vs +4.7% weekday) is the single
most seductive number this dispatch produced. Here is what killed it.

**MDE stated first**: weekend-day sd = 3.54%; at n=918 the MDE at |t|=2 is
**0.233%/day**; Bonferroni over 7 weekdays needs |t| > 2.69.

1. **It does not clear its own multiple-testing bar.** Full-sample Sat+Sun mean
   +0.279%/day, **t = +2.39** — below 2.69.
2. **It is a dead regime.** 2017-19 t=+1.54; 2020-21 t=+2.07; **2022-23
   t=-0.09**; 2024-26 t=+0.73; **2026 YTD -0.179%/day, t=-0.59**. No single year
   reaches |t|=2 (2021's +1.98 is the maximum). In the ETF era (2024-01 onward)
   the only |t|>2 day-of-week is **Wednesday** (+0.712%, t=+2.05), which is what
   a 7-way search finds by construction.
3. **The placebo ladder beats the finding.** Shifting the two-day window around
   the week: Fri+Sat scores **t=+2.58**, *higher* than the true Sat+Sun
   **t=+2.39**. A window that is not the weekend outperforms the weekend.
   (Method lesson 7, third kill.)
4. **It does not replicate on the sibling.** BTC-USD weekend mean +0.129%
   (t=+1.68) vs weekday +0.215% (**t=+3.16**); BTC's cumulative weekday return is
   **+7,864%** against +210% on weekends — the exact opposite split. SOL-USD
   weekend t=+2.75 is in ETH's direction, so the pattern is not universal in
   either direction.

Robustness for completeness (it survives trimming, which is why only the
placebo and the sub-periods kill it): dropping the 1/3/5/10 most extreme
weekend days each tail moves the mean +0.279% -> +0.269/+0.273/+0.276/+0.275%
and the t *rises* to +2.81. Median weekend day +0.169% vs weekday -0.015%;
share positive 54.7% vs 49.7%.

**And the +632.7% headline is arithmetic, not alpha.** Weekend arithmetic mean
+0.279%/day against variance drag 0.5*sigma^2 = 0.063% gives geometric
+0.216%/day. Weekday arithmetic mean +0.116%/day against drag 0.112% gives
geometric ~0. **The cumulative split is a volatility-drag decomposition, not a
return decomposition.** Two sub-samples with similar arithmetic means will show
wildly different cumulative products if their variances differ (weekday sd
4.74% vs weekend 3.54%). **Any future "X% of the return happens in window W"
claim from any seat must be checked this way before it is written.**

**Retired. Do not re-litigate without an intraday series or a non-US venue
calendar.**

---

## 6. THE HONEST VERDICT

**Which claim classes reach usable n, and at what horizon:**

| class | observations/yr | usable? |
|---|---|---|
| **Perp funding** | 1,095 prints | **YES, decisively** — MDE 0.38%/yr on a one-year mean. The best-powered series this fund has touched. |
| **ETF flow days** | ~252 | **MARGINAL** — 533 days give MDE 0.348%/day; the tercile test needed 0.854%/day and delivered 0.620%. Two more years to power it, by which time the regime will have moved. |
| **Daily returns** | 365 | **WORSE than an equity name despite more days.** Power scales as sqrt(n)/sigma: a mega-cap at 252 obs and 2.0% residual scores 7.94; ETH at 365 obs and 3.7% residual scores **5.16 — 0.65x**. Volatility scales faster than the calendar. |
| **Gap / vol parameters** | 252 ETF sessions | **YES** — the bootstrap band on the variance share is tight enough to size a position from. |
| **Liquidation events** | unknown | **NOT MEASURABLE** free. Forward collection or paid data. |
| **Unlocks** | **zero** | Structurally absent. |

**What data must exist first, in cost order**: (1) fix the CoinGecko date label
— free, one line, and it corrupts marks today; (2) start recording Binance OI
daily — free, and the 30-day window means the history is being lost right now;
(3) EDGAR pull of the ETH trusts' own filings for per-share ETH holdings — free,
our existing machinery; (4) a net-issuance series — source unknown; (5) intraday
crypto bars — unknown cost; (6) Coinglass liquidations — paid.

**Does the analytical muscle transfer?** Partly, and the part that transfers is
not the part I expected.

- **The STATISTICS do not transfer; they get worse.** Crypto's 24/7 calendar is
  not free power: 45% more observations against 85% more residual vol is a net
  loss of ~35% of the annual power for return-based claims. Every MDE written
  for equities must be recomputed, never scaled.
- **The FLOW / COUNTERPARTY discipline transfers perfectly, and crypto is a
  better classroom.** Equities hide their flows inside index rebalances, order
  routing and dealer books. Crypto publishes its mandated flows in public APIs
  with no key: who pays whom, every eight hours, with the full history. **This
  dispatch priced five flows against a cost floor and killed four of them in an
  afternoon** — the same exercise on an equity flow would have needed data we
  cannot buy. If the fund wants to practise Ed's counterparty test, this is the
  cheapest gym it will ever have.
- **The CLOCK discipline transfers and gets sharper.** Equities gave me filed vs
  accepted vs the venue's dissemination record. Crypto gives me a bar-stamping
  convention that differs *between two feeds for the same asset* and a four-hour
  asymmetry between two assets' "closes". Same disease, louder symptoms.

**THE MONEY QUESTION, plainly.** ETH is **not tradeable as an edge at our size,
and holdable only through a wrapper we cannot risk-manage properly.** The perp
carry — the one flow with a real, durable, paying counterparty — pays ~220bp
less than T-bills in 2026 and needs a venue we do not have. The ETF flow is
0.15-0.30% of volume, chases price rather than leading it, and predicts 13.7 bps
against a 30-50 bps round trip. The staking queue is a lock, not a transfer.
Unlocks do not exist. **TRUE AND NOT TRADEABLE AT OUR SIZE.**

**What this dossier is worth is the risk parameter and the two defects**: the
60.4% ungoverned gap (which changes how any crypto-proxy position must be sized,
and which our exit machinery cannot protect), the one-day CoinGecko date shift
(which is corrupting marks today), and the equity-only execution path (which
makes the answer to "can we trade ETH" a one-line *no*). Those three are worth
more than any view on the price, and they are the only things here I would
defend to an adversary.

---

## APPENDIX — reproduction

Session scratchpad (.../bbc88cbf-.../scratchpad/): eth_probe1.py, eth_probe2.py,
eth_pull.py -> eth_bars.json (13 series, 2015 to 2026-08-23), eth_ts.py,
eth_stats.py, eth_weekend.py, cg_vs_yahoo.py, funding_probe.py, funding_pull.py
-> eth_funding_binance.json (7,385) / btc_funding_binance.json (7,619),
funding_stats.py, queue_probe.py, vq.py, liq_probe.py, farside.py /
farside_all.py -> farside_eth_all.json (533 rows), etfflow_test.py, gap_test.py,
final_stats.py, fred_probe.py, fred2.py, rss_probe.py.

Host discipline: free RAM 1.47 GB of 15.16 at start with ClarkHarness/.belt_running
present — no containers, no bulk extraction, every external call serialized.
