# The API card — the spine's read surface, for every seat

**CTO-maintained. Purpose: stop each seat re-learning the spine by trial.
"Read the API before consuming it" still binds — if this card and the API
disagree, the API wins; one real call to check the shape, then write, and
report the card's defect in your STATE so the CTO fixes it here.**

Base URL: `http://127.0.0.1:8090/api/v1`

## Market and research data

- `GET /fund/marketdata/bars?symbol=X&lookback_days=N` — the param is
  `lookback_days`, NOT `days`. Returns `{symbol, source, closes, dates,
  start, end}`. Depth measured 2026-08-20: 826 sessions (back to 2023-05-04)
  served for every symbol asked — the request, not the vendor, was the
  binding limit. Adjusted for splits/dividends.
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
  (mechanism defect D1, 2026-08-20: hold-3's five folds sit inside one
  quarter; hold-21's four span 16 months).
- Fold measurability: `app.fund.walkforward.retention()` returns
  `measurable: False` with a named reason (no trades, missing figure,
  non-positive or sub-floor train leg) — an unmeasurable fold is never a
  zero and never a free pass.

## Known gotchas (each one cost a real dispatch)

1. `lookback_days`, not `days` (mechanism, cycle 1).
2. `filled_qty`, not `qty`, on fill payloads (autopolicy v2 post-mortem).
3. An absent number is reported absent — absence is never zero (constitution).
4. Costs: `app/fund/costassumption.py` currently applies ONE global
   5bps/side slippage constant validated on ten small-cap fills — it
   overcharges mega-liquid ETFs 3–5× (defect D2, measurement queued). Say so
   when cost arithmetic decides your conclusion.
