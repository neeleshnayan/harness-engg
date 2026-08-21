# quant — seat memory

## PLACEMENT (versioned 2026-08-21, CEO acceptance — read before drafting)

You MAY delegate SUB-FUNCTION drafting to local `qwen3.8:latest` (Ollama,
127.0.0.1:11434, ~102 tok/s, free): always against a FIXED data structure
stated in the prompt, always judged by hidden deterministic tests the
model never sees, temperature 0.2, `think: false`. Benchmark basis: 4/4
hidden-test pass including the calendar-month-end regression probe that
killed the whole-algorithm hybrid (which stays REVERTED — whole
algorithms are yours on Opus). A failed local draft is REWRITTEN by you,
never debugged at length. Report in your STATE whether the split saved
or cost on each dispatch — two consecutive dispatches where it costs
reverts it, same as last time.

## 2026-08-21 — dispatch #1 (Entry 11, month-end rebalancing flow) — FIRST HOT RUN

[Seat's own STATE, appended verbatim by the CTO at resolve; full report at
docs/research/QUANT_ENTRY11_2026-08-21.md.]

WHAT EXISTS NOW
- lean_workspace/algorithms/monthend_rebalance_flow/main.py — Entry 11 verbatim.
  Declares HOLD_DAYS=21, CLAIM_TYPE="alpha", BENCHMARK="SPY/TLT", UNIVERSE=["SPY","TLT"].
  Params: start, end, slip, fee, nav. (Committed by the CTO at resolve.)
- Three candidates, all FAIL v4.1, 3 failures each:
  9ba5e4b3154d (1bps) / da1a5a6f4275 (3bps) / 279ffc5d8538 (5bps).
  Returns 49.795 / 46.05 / 42.456 vs benchmark 40.75 (equal-weight SPY/TLT basket),
  254 orders, capacity $341M, holdout retention 1.20/1.21/1.22 (all pass).
  Killers: PSR (0.95/0.746/0.584 vs 65 floor), breakeven-never-measured,
  walk-forward 2-of-4 folds retained.

STARTUP FACTS FOR THE NEXT DISPATCH (each cost me a step)
- Spine bars via lookback_days=2000 give SPY/TLT 1380 joint DAILY sessions from
  2021-02-23, source alpaca. Use 2000 in the SpineBars URL — it also feeds warm-up
  before an early fold's train_start.
- factory.WALKFORWARD_HISTORY_FLOOR is still 2024-02-26 and clips fold train legs.
- Fold geometry for HOLD_DAYS=21 is 4 folds / 84-day legs / 2025-02-26→2026-06-25,
  INVARIANT to test_end. Each leg = 4 month-end decisions = 18 orders for this rule.
- A candidate costs 11 container runs (1 sweep pt + 1 sweep holdout + 1 verification
  + 4 folds x 2). Three in parallel = 33 runs, ~8 min wall — AND 2 of 37 runs hit
  LEAN_JOB_TIMEOUT=300s and died. Do not run 3 candidates concurrently until that
  timeout moves; a killed fold becomes "only N folds could be measured".
- Per-fold rows are NOT in the candidate API. Reconstruct from GET /fund/lean/sweeps
  (holdout/holdout_result/train/test/dates_honoured, keyed by grid value).
- ALWAYS smoke a single backtest (POST /fund/lean/backtests) before submitting a
  candidate: it caught the notional/lot-size problem and confirmed trade DATES.
  Verify timing from result["orders"], never from the log tail.
- LEAN advances algorithm time to a daily bar's END. Use data[sym].time, not
  self.time, or every calendar test is off by one session.
- set_holdings must be called reductions-first or the buy is rejected for buying power.
- prescreen cannot express anything but xs_momentum / xs_meanrev; for other shapes
  write a throwaway offline replica — mine predicted every LEAN fold leg within ~1pp.

TRAPS THE GATE SETS FOR CERTAIN STRATEGY SHAPES (report these, do not fight them)
- A one-point grid ALWAYS fails "cost robustness was never measured". Unavoidable
  when the spec forbids a sweep.
- An overlay on a fully-invested basket can never clear PSR 65: PSR is computed on
  the TOTAL book's Sharpe, which is the basket's. For alpha claims this is a beta
  filter, not an alpha test.
- breakeven_cost finds where TOTAL return hits zero, not where the EXCESS dies.
  For Entry 11: 28.1 bps vs 5.92 bps. Compute the excess breakeven yourself.

STANDING JUDGEMENT CALLS I MADE (inherit or overturn deliberately)
- NOTIONAL=100_000, not the workspace's 2000. At $2k, whole-share fills on a $600
  SPY make a "50/50" book actually ~29/45 and the rounding swamps a 1-2%/yr effect:
  measured 36.024% (nav=2000) vs 46.05% (nav=100000) on the same window. It is
  PASS-FAVOURABLE and must be declared every time. The $2k number is the DEPLOYMENT
  answer; the $100k number is the answer about the IDEA.
- Month-end = last WEEKDAY by calendar; holidays skip the month (2 in 1380 sessions).
- HYBRID: ollama is INSTALLED but NOT SERVING by default. Binary at
  C:\Users\user\AppData\Local\Programs\Ollama\ollama, qwen3.8:latest present.
  Start it by hand (`ollama serve`, backgrounded) and expect it to die with the
  dispatch — mine was killed at session end. Budget ~15s to start + ~40s to
  draft. Verify with: curl -s -m 5 http://127.0.0.1:11434/api/tags (rc=7 means
  not up). [Seat-issued correction, 2026-08-21: the original line claimed the
  server was left running; re-verified dead after session end.] qwen3.8
  drafted in 36.5s and the draft was discarded — last CALENDAR day month-end,
  nonexistent set_slippage/set_fee, a guaranteed zero-order failure in a bare
  except. Reviewing cost more than writing. Recommendation: point the local
  model at sub-functions, not whole algorithms.

- [CTO note at resolve, 2026-08-21]: candidates and file verified; algorithm
  committed; report filed verbatim-in-substance as
  docs/research/QUANT_ENTRY11_2026-08-21.md; recorded as run-quant-entry11.
  Your hybrid verdict REVERTED the split for whole algorithms in the
  constitution (measured, not asserted — exactly how the placement rule said
  it would be decided). Entry 11's register status is BELT-TESTED / NOT
  DEPLOYABLE with sharpened revival conditions; the experimental alpaca path
  (CEO-authorized) is its only route forward. Your three gate recommendations
  travel with round 4 to the adversary as field evidence. Your bottlenecks
  join the flow-test synthesis; the timeout/serialisation and folds-in-API
  items go to the next harness batch.


## 2026-08-22 — BINDING CONSTRAINT ON YOUR NEXT ARTIFACT (chair note, co-CTO)

**Our own price history carries a ~44%/yr phantom factor. Do not sort on
price level, market cap, dollar volume or share count until told otherwise.**

Measured by the analyst and VERIFIED independently by the chair before this
note was written:

- Monthly-rebalanced price-quintile LOW-minus-HIGH over the fund's 200-name
  universe returns **+49.68%/yr (t=5.69) on adjusted closes and +43.84%/yr
  (t=4.62) on nominal closes, positive in all seven years.** None of it is
  a market effect.
- **Cause (a) — the anchor is TODAY, not the bar's own date.** Closes are
  split-back-adjusted from the present. `GET /fund/marketdata/bars?symbol=TENX`
  returns `closes[0] = 2320.0` for 2020-06-01 and a 2020 high of 3168.0 for a
  sub-$2 biotech, because 1:20 (2023-01-05) and 1:80 (2024-01-03) reverse
  splits are projected backwards. Changing `end_date` does NOT move the
  anchor. The payload carries `adjusted: None` — it does not even name what
  it is anchored to. Yahoo's raw `quote.close` is ALSO adjusted, so exposing
  a raw field is not the fix; the SPLIT EVENTS are.
- **Cause (b), the larger half — survivorship.** Re-counted by the chair
  from the cached 5-year bar set: **203 of 203 symbols have a last bar of
  2026-08-20 or 2026-08-21.** Zero attrition across six years of small and
  mid caps — no bankruptcy, no delisting, no going-private, not one name.
  `GET /fund/universe/hunting-ground` is `operating_only: true` off Polygon's
  CURRENT reference data, so membership is conditioned on being alive today.

**What is safe and what is not:**

- **SAFE — anything built from RETURNS.** Momentum, reversal, event abnormal
  returns, volatility. Returns are adjustment-invariant; that is what
  adjustment is for.
- **NOT SAFE — any cross-sectional sort on price level, market cap, dollar
  volume or share count, and any comparison of a filing's nominal dollar
  figure to one of our closes.** A candidate built on one of these will
  present roughly +44%/yr with a good IR, positive in every walk-forward
  fold, and the gate will pass it — because every fold reads the same
  today-anchored, survivor-only series. **The gate is structurally blind to
  this class of defect.** It is not a filter you can lean on here.
- Long-horizon ABSOLUTE-return studies on this universe are inflated by
  survivorship regardless of what they sort on.

This lifts when the split-event fix lands (filed as a builder ticket:
`&events=div,split` gives numerator/denominator; `nominal(t) =
split_adjusted(t) x product of (num/den) for splits after t`, verified
working on 202/202 symbols). Survivorship does not lift — no point-in-time
universe membership exists in the fund, so that half is fenced, not fixed.

**And the method rule that found it, which now binds you too: every
cross-sectional conditioning claim carries an EVENT-INDEPENDENT PLACEBO
(the same names, dates shifted +/-60/120/250 sessions) before it is
believed.** It killed two |t|>3 "findings" in the dispatch that produced
this note — including one that looked like a clean tradeable short.
