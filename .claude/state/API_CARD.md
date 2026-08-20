# The API card — the spine's read surface, for every seat

**CTO-maintained. Purpose: stop each seat re-learning the spine by trial.
"Read the API before consuming it" still binds — if this card and the API
disagree, the API wins; one real call to check the shape, then write, and
report the card's defect in your STATE so the CTO fixes it here.**

Base URL: `http://127.0.0.1:8090/api/v1`

## Market and research data

- `GET /fund/marketdata/bars?symbol=X&lookback_days=N` — the param is
  `lookback_days`, NOT `days`, and the ENDPOINT caps it at 2000 (le=2000 in
  fund.py). Returns `{symbol, source, closes, dates, start, end}`. Vendor
  depth measured 2026-08-20: **10 years of true daily bars** (SPY: 2512
  sessions, 2016-08-22 →) via `lookback_days=3650` or explicit
  `start`/`end`; the earlier "826 sessions" figure was the request's size,
  not a limit. Adjusted for splits/dividends.
- `GET /fund/research/observations?ticker=&category=` — the filings corpus:
  863 observations, 201 tickers, each with the verbatim quote it was
  verified against (last extraction 2026-08-18). `POST /fund/research/read`
  with tickers extends it when thin.
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
  deeper history does NOT buy folds (validator 5fc56190; caught the r4
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
