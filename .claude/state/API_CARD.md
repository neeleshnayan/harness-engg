# The API card — the spine's read surface, for every seat

**CTO-maintained. Purpose: stop each seat re-learning the spine by trial.
"Read the API before consuming it" still binds — if this card and the API
disagree, the API wins; one real call to check the shape, then write, and
report the card's defect in your STATE so the CTO fixes it here.**

Base URL: `http://127.0.0.1:8090/api/v1`

## Market and research data

- `GET /fund/marketdata/bars?symbol=X&lookback_days=N` — the param is
  `lookback_days`, NOT `days`, and the ENDPOINT caps it at 2000 (le=2000,
  fund.py:2582 — **`lookback_days=3650` returns HTTP 422**; the card's
  earlier "3650 works" line was WRONG, caught by the mechanism 2026-08-21).
  Depth params are **`start_date` / `end_date`** (NOT `start`/`end`).
  Verified depth: `start_date=2015-08-01&end_date=2026-08-21` returns
  **2,779 true daily sessions from 2015-08-03** on 30/30 symbols tried —
  ELEVEN years. Adjusted for splits/dividends. Also takes `as_of` (the
  point-in-time archive view).
- Treasury data (mechanism, 2026-08-21): `treasurydirect.gov
  TA_WS/securities/auctioned` IGNORES startDate/endDate/pagesize — serves
  only a rolling ~18-month window whatever you ask. Use
  `api.fiscaldata.treasury.gov` for auction history.
- `app.fund.walkforward.window_for_strategy` signature: `(end, hold_days,
  min_folds, train_days=252, floor=None)` — `hold_days` alone raises.
- `GET /fund/research/observations?ticker=&category=&limit=` — the filings
  corpus: 1,035 observations, 201 tickers, 249 filings (refreshed
  2026-08-21), each with the verbatim quote it was verified against.
  **`limit` defaults to 50, max 500** — a naive fetch silently returns 50
  of 1,035 rows; page by `category` (largest is liquidity at 379).
  `POST /fund/research/read` extends it — **`per_ticker` defaults to 2**
  (why the corpus was one filing deep per name); `forms:["10-Q"],
  per_ticker:6` reaches back ~2 years at a measured 12.3 s/filing.
- ⛔ **REFUTED 2026-08-21 — DO NOT ACT ON THE STRUCK LINE BELOW.** The
  raw `acceptanceDateTime` is **genuine UTC; apply NO shift on the way
  in.** To DISPLAY Eastern time, subtract 4h (EDT) — EDGAR's own filing
  index pages render ET, which is why an index page reads 4h behind the
  JSON. Measured three ways: builder D7 (n=2,400 hour histogram +
  n=30,732 next-business-day roll-over), co-CTO independently (n=4,895,
  six issuers — raw hours 06–09 UTC are empty, which is 02:00–05:00 ET
  when EDGAR is shut), and at the data layer (SRPT stores 20:01:46+00 =
  16:01:46 ET, the analyst's own cited figure). `fund_observations
  .accepted_at` stores UTC unshifted and a named test guards it.
  Quarantined by the co-CTO on the COO's recorded dissent; the full
  correction is parked for Fable in CTO_REVIEW_QUEUE.md.
- ~~EDGAR gotchas (analyst, 2026-08-21): `acceptanceDateTime` carries a
  "Z" suffix but is **ET = the stamp minus 4 hours** (verified on four
  index pages).~~ **← REFUTED, see above.** Still true and unaffected:
  55.9% of corpus filings were accepted post-close on their own
  `filed` date — **any backtest consuming the corpus must enter at or
  after the OPEN of the session following `filed`**, never the close.
  `fetch_daily_bars("BTC")` returns CoinGecko bitcoin (7-day calendar),
  not the SEC filer Grayscale Bitcoin Mini Trust — run a bar-count
  integrity check against SPY in any study touching crypto-named tickers.
- `GET /fund/universe/hunting-ground` — liquidity, capacity, CIKs. Never
  filter on "too small for big funds": at $2k NAV that is other people's
  constraint, not ours.

## Fund state (read-only for every seat)

- `GET /fund/doctrine`, `/fund/judgement`, `/fund/mechanics`,
  `/fund/liveness` — live doctrine, registered thresholds with provenance,
  mechanics, heartbeats.
- `GET /fund/orders/pending` and `GET /fund/orders/history?limit=N` —
  lifecycle rows. **Fills carry `filled_qty`, not `qty`** (reading the wrong
  key is how autopolicy v2 failed closed on everything).
- `GET /fund/executions?strategy_id=&limit=` — fills matched to round-trips
  with realised P&L.
- `GET /fund/events` — the event log (append is CTO/spine only; no seat
  POSTs anywhere except its own run output through the CTO).

## Local compute

- Python: `./venv/Scripts/python.exe` from the ClarkHarness directory, with
  `sys.path.insert(0, '.')` (or `PYTHONPATH=.`) for `app.*` imports. Add
  `-X utf8` when printing non-ASCII on Windows. PowerShell mangles `*` and
  newlines in inline `-c` strings — write a script file instead.
- Fold planning: `app.fund.walkforward.window_for_strategy` — RUN it, never
  assert fold counts. Fold count and regime coverage INVERT for fast rules
  (mechanism defect D1, confirmed with closed forms 2026-08-20:
  span_oos = K·floor(4·hold·365/252) days; hold-1 gets 5 folds over 25
  calendar days). AND: **fold count is INVARIANT to available history** —
  reach-back is fixed at train + test·(K+1); the floor only clips, so
  deeper history does NOT buy folds — UNLESS min_folds is raised: K is a
  caller-settable input to window_for_strategy, so the invariant holds per
  chosen K, not absolutely (caveat added 2026-08-28, closing the residual
  the second closure sweep caught on run-mechanism-cycle3#8) (validator 5fc56190; caught the r4
  audit modeling a packed generator the belt doesn't have). Also: fold
  count is non-monotone in hold (drops 5→4 at holds 4/9/14/19, cal()
  rounding); `holdout_result.test.window` is engine-actual and is NOT
  copied into the fold row — requested dates are the only per-fold record
  downstream, gate them on `dates_honoured`.
- Fold measurability: `app.fund.walkforward.retention()` returns
  `measurable: False` with a named reason (no trades, missing figure,
  non-positive or sub-floor train leg) — an unmeasurable fold is never a
  zero and never a free pass.

## Known gotchas (each one cost a real dispatch)

1. `lookback_days`, not `days` (mechanism, cycle 1).
2. `filled_qty`, not `qty`, on fill payloads (autopolicy v2 post-mortem).
3. An absent number is reported absent — absence is never zero (constitution).
4. Costs: `app/fund/costassumption.py` applies ONE global 5bps/side
   slippage constant (defect D2 — confirmed). CORRECTED 2026-08-20
   (validator audit): the "ten fills" behind it are five ETF, three
   mega-cap, two small/mid — NOT "ten small-cap fills" — measured
   decision→fill (includes ~9 min mean approval latency), and dropping two
   partial-fill outliers moves 5.95 → 3.34 bps. The "3–5× ETF overcharge"
   figure has no measurement behind it. Say so when cost arithmetic
   decides your conclusion.
6. **The PAPER venue cannot measure cost, ever**: `paper.py:116` fills at
   its own quote — the same call `pipeline.py:215` records as
   arrival_price, so execution slippage is identically zero at any sample
   size. Only alpaca-venue fills carry information (8 exist, ≤2 per
   instrument). Never treat `/fund/tca`'s realised-vs-assumed verdict as a
   cost measurement until its leg comparison is fixed.
5. Deep history: asking `fetch_daily_bars` for MORE than 10 years without
   explicit `start`/`end` maps to Yahoo `range=max`, which silently returns
   MONTHLY bars from a function named fetch_DAILY_bars (SPY: 404 bars,
   1993→2026, measured 2026-08-20). At ≤10y (`range=10y` or start/end) the
   series is true daily. Check bar spacing before trusting depth.

- **CORRECTION 2026-08-23 (Ed batch #3, two-worker verification): `GET /fund/marketdata/bars` `end_date` is EXCLUSIVE** - request 2026-08-21 to receive bars through 2026-08-20. Any prior note implying inclusive is wrong. Also: BIL's last bar lags one session; statsmodels is absent from the venv.
- **ADDENDUM (Doc, 8-K panel run): the INTERNAL `fetch_daily_bars` `end` is also EXCLUSIVE** (verified: end=2010-12-31 returns last bar 2010-12-30). Chunked pulls must overlap windows; verify year session counts against known NYSE closures (2001=248, 2012=250, 2008=253).
- **POST /fund/desk/requests/{FULL_id}/resolve** takes {resolution: str, actor: str} - closes an open request with a recorded disposition (used for superseded/answered asks; distinct from the guarded approve path).



## FRED (corrected 2026-08-24, measured at run-analyst-golddossier1)

- The keyless fredgraph.csv warning is PER-SERIES, not blanket: market-price
  series (DFII10, VIXCLS) are NEVER revised (0/10,381 obs changed vs
  2022/2024 vintages); revised aggregates (DTWEXBGS 36-44% changed, CPI,
  payrolls) need the keyed API with realtime_start/realtime_end. Check any
  new series once with one vintage call before trusting the keyless feed.
- Release-lag trap on never-revised series: day D's DFII10 is not visible
  on day D (H.15 lands after the close) - same-day rules take look-ahead.
- SPDR GLD archive (standing free asset): api.spdrgoldshares.com/api/v1/
  historical-archive?product=gld&exchange=NYSE&lang=en - XLSX, browser UA,
  5,472 rows 2004+; oz/share, tonnes, NAV@10:30, premium@16:15. Traps: the
  advertised .csv 301s to a PDF; 204 rows read "US Holiday"; openpyxl not
  in venv. Recovers the LBMA fix as NAV/oz (no free FRED gold price exists
  - GOLDAMGBD228NLBM is a 404).


## Crypto-adjacent feed facts (corrected 2026-08-27, run-ed-batch7, chair-verified live)

- **`GET /fund/marketdata/bars?symbol=ETH` returns the GRAYSCALE ETHEREUM
  MINI TRUST ETF (~$23.59, source alpaca), NOT ethereum.** The card's older
  BTC/CoinGecko warning described the internal `fetch_daily_bars` only —
  the ENDPOINT and the function resolve symbols differently. Any crypto
  study must state which surface it read and verify the instrument's
  identity (price sanity vs the coin), not just the symbol.
- **A <=6-char ticker colliding with ANY Yahoo listing returns HTTP 200
  with the WRONG instrument's real bars** (GETH -> an OTC penny stock at
  $0.0001), and a genuine no-such-symbol 422s with an outage-shaped
  message. Fix queued (B1). Until then: sanity-check price level and
  source field on every unfamiliar symbol.
