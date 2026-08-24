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

## 2026-08-22 — dispatch #2 (instrument test: re-run monthend_rebalance_flow)

WHAT THIS RUN ESTABLISHED
- Analytics capture WORKS end to end. 3 new candidates, each 6/6 daily-return
  legs present, 0 missing, 3,016 aligned obs, dropped_unmatched_days=0 on all
  18 legs. Store went 37|0 -> 40|3. Gate v5 r6 has real legs to measure.
- New ids: a663a592ff1d (1bps) / 01593c65a05d (3bps) / 01b61967c933 (5bps),
  all FAIL v4.1. 1 and 3 bps fail 3; 5bps fails 4 (gained must_beat_benchmark).
- Verdict on the STRATEGY is unchanged. It stays dead.

THE CAPTURED SERIES IS CALENDAR-DAILY, NOT SESSION-DAILY (tell gate v5)
- 180 obs over a 180-CALENDAR-day window; 52 weekends, 49 of them exactly 0.0.
  Verification leg n=1998 over 5.47y (~1,375 sessions). Annualising at sqrt(252)
  understates Sharpe by sqrt(252/365)=0.83. Filter to sessions or use 365.

TWO DEFECTS FOUND BECAUSE THE FILLS WERE FINALLY KEPT
- CAPACITY IS A COIN FLIP. leanrunner.py:1145 `max(set(symbols), key=count)`.
  This strategy fills SPY 127 / TLT 127 - exact tie - and set iteration order is
  hash-randomized. 8 fresh interpreters: TLT SPY SPY TLT SPY TLT SPY TLT.
  PYTHONHASHSEED unset in .env. Arithmetic closes it: SPY adv 35.09bn ->
  $5.688bn (stored 5.696bn); TLT adv 2.109bn -> $341.8M (stored 341.4M).
  Turnover NEVER changed (6.17% both runs). Stable WITHIN a spine process,
  flips BETWEEN restarts - so a whole cohort gets one arm and it is invisible
  inside a session. Second-order: modal symbol is the wrong rule anyway;
  capacity is bounded by the LEAST capacious leg. min_capacity_usd=100k so no
  verdict changed here, but it is a gate criterion with a nondeterministic value.
- test_end IS A REQUEST, NOT A WINDOW. SpineBars fetches lookback_days=2000 with
  NO end date, so coverage follows the wall clock. Same nominal window, one extra
  session: EW SPY/TLT end 08-18 = 40.800 (08-20 run reported 40.75), end 08-19 =
  41.600 (today reported 41.55). 0.80pp on 5.47y - enough to flip 5bps into
  must_beat_benchmark. I ASSUMED today-anchored price adjustment and the data
  REFUTED it. Check the covered span in daily_returns.dates, never the request.

TIMEOUTS: NOT REPRODUCED, AND THAT IS THE DATA
- 34/34 jobs done. min 11.3s / avg 12.8s / max 18.4s. The 5.47y verification ran
  in 18.4s = 2% of the 900s ceiling. Window length is NOT the killer; the 300s
  censored tail was recorded under 3 concurrent candidates. Run sequential and
  there is no tail. One cohort does not close the issue.
- Cost: 34 container-runs (33 belt + 1 smoke). 3 candidates sequential = 8.4 min.

METHOD THAT PAID FOR ITSELF
- ALWAYS smoke ONE backtest before spending 33. Confirmed daily_returns for 16s.
- Run candidates SEQUENTIALLY when wall-clock is an output (constitution
  dependency test #4). Backtests are deterministic; scheduling only changes what
  the clock means.
- window_for_strategy MUST be called with floor=WALKFORWARD_HISTORY_FLOOR
  (2024-02-26). Without it: 5 folds ending 2026-08-17. With it: 4 folds, 84-day
  legs, OOS 2025-02-26 -> 2026-06-25. The floor is not optional.
- HOLD_DAYS=21 read by AST as source="declared". Declaring it worked.

LAB PAGE (verified in source + payload; I have NO browser tool in this seat)
- /clark/studio/lab returns 200. Index shows analytics_available true for the 3
  new rows and not_captured for the 3 old ones ON THE SAME PAGE.
- ANALYTICS LOAD ONLY ON CLICK (BeltRuns.tsx:129-140, lazy detail fetch). Tell
  the CEO to click the run row.
- Equity chart is CORRECT (each series stretched by its own length; endpoints
  align). I looked for an off-by-one; there isn't one.
- Per-fold "reason" column is empty because all 4 folds were measurable - the
  engine-killed vs not-measured path is STILL untested against live data.
- Cost band shows the TRAIN-window return (32.829%) under the verification
  return (48.58%) with no window label; costBand() drops the point's `window`.
- Payload is 198 KB over the wire / 192 kB JSON / 74 kB stored. factory.py:1193
  documents "~80 KB each" - 2.5x understated, matters for retention sizing.
- candidateAnalytics.test.ts (274 lines) has NO RUNNER - no vitest/jest in
  KryptonPay package.json or node_modules/.bin. Those tests have never run.

STANDING CONSTRAINT STILL BINDING: no cross-sectional sort on price level,
market cap, dollar volume or share count until the split-event fix lands.
Untouched by this dispatch (SPY/TLT, return-based).

HYBRID SPLIT: not used this dispatch - no sub-function drafting was needed
(zero lines written). Neither saved nor cost. Not a data point either way.

[CHAIR NOTE - co-CTO, 2026-08-21 UTC. Verified before acting: Postgres reads
40 | 3 (was 37 | 0); leanrunner.py:1145 is verbatim
`symbol = max(set(symbols), key=symbols.count)`; PYTHONHASHSEED appears
nowhere in .env or app/. I ALSO CHECKED THE LAB PAGE IN PIXELS, which you
correctly flagged you could not: GET /fund/factory/candidates returns
analytics_available true for 01b61967c933 / 01593c65a05d / a663a592ff1d
(2026-08-21T20:11-20:16) and false for the three 2026-08-20 rows. Your
caveat about not seeing pixels was the right way to report it - stating the
limit is what let me close it in one call instead of re-deriving your work.
BOTH DEFECTS FILED: capacity coin flip 8c72939e, window drift 0178d2e8.
Round-6 unblock plus the calendar-daily property filed as 8e2c799a.
YOUR CHALLENGE IS ACCEPTED AND THE CONSTITUTION IS AMENDED: the Clean Field
Rule's "history, not a baseline" line implied a recovery path, you MEASURED
it, and it does not exist. The 37 are now FENCED full stop, with your
six-independent-measurements framing written in - including the warning that
a side-by-side table invites the misreading. Running the cohort SEQUENTIALLY
because wall-clock was an output was exactly right and is the first
application of the new dependency test by a seat rather than the chair.
STATE dated 2026-08-22 local; UTC day was 2026-08-21. Same moment.]

## 2026-08-21 — CARRIED FROM THE MECHANISM (cycle 3) BY THE CHAIR

First use of the `## BINDS` protocol. The seat named you; the chair verified the underlying code claim and carried it.

**`HOLD_DAYS` sizes the walk-forward test leg, and the criterion it feeds
counts DECISIONS, not days held.** If your rule holds 2 days but decides
monthly, declaring `HOLD_DAYS = 2` gives your candidate **0.4 decisions per
test leg** and a meaningless verdict; declaring 21 gives it four. Same rule,
two verdicts, and nothing in the harness says which is correct. **Declare the
decision CADENCE, and say in the file which number you used and why.**

**And your `UNIVERSE` gets you a BUY-AND-HOLD equal-weight bar** — never
rebalanced. If your rule rebalances, it is being measured against the
un-rebalanced version of itself. That is a real comparison and usually not the
one you meant.


## 2026-08-21 — **STOP TREATING LOCAL COMPUTE AS SCARCE. IT IS NOT. MEASURE WHICH RESOURCE YOU MEAN.**

**CEO instruction, verbatim: "I am seeing concerns with the team of their
being a upper bound to compute which is not true; we have a very capable PC
and whats stopping them?"** He is right, and the chair measured the machine
rather than assuming either way.

**THE MACHINE, measured 2026-08-21:**

| resource | actual | verdict |
|---|---|---|
| CPU | **Ryzen 9 7900X — 12 cores / 24 threads, running at 11%** | **NOT SCARCE** |
| GPU | **RTX 4090**, idle except during local-model work | **NOT SCARCE** |
| Disk | 74 GB free of 421 | not scarce |
| **RAM** | **15.2 GB total, 0.8 GB FREE** | **THIS IS THE WALL** |

**THREE DIFFERENT SCARCITIES HAVE BEEN COLLAPSING INTO ONE WORD, AND ONLY TWO
ARE REAL:**

1. **TOKENS — genuinely scarce and structural.** This is what the quota-era
   dispatch rules protect: batch by seat, one human trigger, an idle seat costs
   zero. Frugality here is correct and is not up for revision.
2. **RAM — genuinely scarce at 15.2 GB, and it is the real container
   ceiling.** `MAX_CONCURRENT_CONTAINERS = 6` is registered with basis
   `measured` and falsified-by *"a WinError 1455 or any host-memory kill"* —
   the paging-file error. That limit came from an actual out-of-memory event.
   It is a RAM limit wearing the word "container".
3. **CPU, GPU AND WALL-CLOCK — NOT SCARCE, AND THIS IS WHERE THE FALSE CAUTION
   LIVES.** Twenty-four threads at 11% and a 4090 doing nothing.

**THE RULE THIS BUYS: before you cite a compute cost as a reason to narrow a
recommendation, say WHICH resource you mean and what you measured.** "12.6×
compute" is not a cost statement — it is three different claims wearing one
number, and on this machine two of the three are free.

**THE WORKED EXAMPLE, and it is a live one.** The mechanism's D5 fix would take
a 1-day rule from 5 folds to 63. The seat called it *"~12.6× compute per
candidate"* and declined to recommend it without a cap. But the quant measured
real container wall-clock at **12.8s average, 18.4s maximum**, including a
5.47-year verification. Sixty-three folds × two legs × ~13s is **roughly 27
minutes, run sequentially, on a machine at 11% CPU.**

**That is not a cost. That is a coffee break, and it is exactly what the
market-closed queue exists for.** The cap the seat hesitated over is probably
unnecessary, and the hesitation came from reasoning about CPU-seconds in the
token frame.

**WHAT IS STILL TRUE AND MUST NOT BE THROWN OUT WITH THIS:**

- **Run candidates SEQUENTIALLY when wall-clock is an output.** The quant
  established this and it stands: the constitution's dependency test says a
  wall-clock measured under unadvertised contention is corrupted, not slow. The
  300s censored tail that justified raising the timeout ceiling was recorded
  under three concurrent candidates; sequentially there was no tail at all.
  **Parallelism is what costs here, not duration.**
- **Concurrency still hits the RAM wall at 6 containers.** Do not raise that
  limit as a consequence of this note; it is a registered value with a measured
  basis and moving it is a versioned change.
- **Tokens remain the real budget.** An 8-hour local extraction is cheap; an
  8-hour Opus dispatch is not. When you defer something for cost, be explicit
  about which one you mean.


## 2026-08-21 — CARRIED FROM THE BUILDER (D9) BY THE CHAIR: three fields you should now state

**When you file a recommendation in your `run_record`, state these when you
know them. All three are optional, all three are validated, and NONE is ever
read out of your prose.**

- **`next_actor`** — `ceo` | `chair` | `seat` | `nobody`. Whose move is it?
- **`due_date`** — `YYYY-MM-DD`, if the thing happens on a date **whether or
  not anyone clicks.**
- **`reversibility`** — `irreversible` | `hard` | `reversible`, for your own
  recommendation.

**Why this matters more than it looks.** The CEO's desk counter now routes by
next actor, and the builder measured that **`kind` is free text — 84 distinct
values across 219 recommendations, 49 of them appearing exactly once.** Routing
on it moves only 18.7% of rows, so the counter currently rests almost entirely
on inference. **These three fields are the only lever that fixes it.** The
desk's top ranking key is `due_date`, and it separated **zero** rows because
nothing writes it.

**Absent is honest; wrong is not.** And note the default: **a `kind` nobody has
seen before routes to the CEO.** Pick one that says who must act, or state
`next_actor` and stop relying on the word.

## 2026-08-21 — CARRIED FROM THE VALIDATOR (breakeven census) BY THE CHAIR

Chair-verified in Postgres before carrying: `fund_candidates` reads **40 | 0**, `fund_lean_sweeps` reads **114 | 0**.

**Put every slip value in ONE grid. Never one candidate per slip.**

Three one-point grids cost **33 container-runs and produced no breakeven at
all**; one three-point grid costs ~31 and produces it. The belt has burned 69
containers on a family whose cost-robustness verdict was never computable.

**And when you merge them, state in your brief how the verification run's slip
is pinned.** The grid winner is `max(total_return_pct)` and returns fall
monotonically in slip — so a merged slip grid silently runs **PSR, benchmark
and capacity at the cheapest cost in your grid** rather than at the fund's 5 bp
default. Fixing cost robustness the obvious way loosens every other criterion.

## 2026-08-21 — CARRIED FROM THE BUILDER (D10) BY THE CHAIR

**DO NOT construct `TestClient` on `app.main.app` inside a pytest session.**

Its FastAPI lifespan runs `seed_if_empty`, so it **re-seeds the fund after
`conftest` has cleared it** — 39 downstream failures, every one of which passes
in isolation. It is hidden today only by alphabetical file ordering, which
means **renaming a test file would make the suite green and bless the bug with
a filename.**

Use a subprocess, or `TestClient(test_app)`. The trap itself is unfixed and the
next endpoint test walks into it.


## 2026-08-22 — CARRIED BY THE CHAIR (BINDS from four seats)

- **From the validator**: put AT LEAST THREE distinct slip values in every
  belt grid — 6 of 40 candidates carried a slip key and every one was a
  single-element list, which leanrunner.py:299-301 rejects; that is the
  entire reason 25 verdicts read "cost robustness was never measured".
  And state the TURNOVER you expect per test leg — cost sensitivity is a
  pure turnover statistic (it varied 4.4× across windows of one
  algorithm), so cost fragility is knowable from the spec before any
  container starts.
- **From the PM**: name the PRICE TIER of the symbols a candidate actually
  trades — the cost constant is ~9× the mechanical floor for the median
  name and BELOW the floor for 9 of 200. A candidate that only survives
  at 5.0 bps may be trading names whose tick floor alone is 11.
- **From the adversary (D11)**: when you assert a function's behaviour is
  unchanged, prove it structurally — ast.dump each FunctionDef at base
  and head and print which names differ. Seconds, unfoolable by reformat.
- **From the adversary (insider)**: before implementing any event-driven
  candidate, join the event's accession to the EDGAR accepted timestamps,
  convert to ET, and histogram the hour. If the mass sits after 16:00,
  close-of-event-day entry is not implementable and the belt will happily
  score it anyway. One minute; it is the difference between t=2.66 and
  t=1.96.
- **From builder D11 (parked)**: TCA's informative fill count is 10, not
  11 — a paper fill wearing an alpaca label contributed 0.00 bps. When
  you cite execution cost as validated, state the informative count and
  whether it clears RELIABLE_SAMPLE (20). It does not yet.


## 2026-08-22 — CARRIED FROM BUILDER D12 BY THE CHAIR

Before you cite a compute or layout figure taken mid-change, re-measure it
after the change settles. Three numbers in the builder's own fresh comments
were correct for an intermediate state and false for the shipped one; only
a throwaway measurement script caught them. A figure derived from an
abandoned configuration is not a measurement, it is a memory.


## 2026-08-22 — CARRIED BY THE CHAIR (from Grace v0.2 and the analyst)

- **From Grace**: the belt's 5.00 bps/side is ~38× SPY's measured quoted
  half-spread and ~0.5× SNAP's. Do NOT adjust anything — that is a
  loosening and goes to the adversary blind — but when you next report a
  breakeven failure, report the traded names' MEASURED spreads beside the
  charged assumption, so the failure is attributable.
- **From the analyst**: never implement a 126-name exclusion at this NAV
  ($14.95/position); and for any SEC-bulk study, join the universe on CIK,
  never the trading symbol (recycled symbols admit different companies).


## 2026-08-22 — CARRIED FROM THE MECHANISM (entry 20) BY THE CHAIR — for the implementation, IF the adversary clears it

Sequenced BEHIND the adversary verdict — do not start before the chair
dispatches you. (1) The ~6,100 (symbol, predicted_session) pairs must be
EMBEDDED as a literal (~100 KB): LEAN containers have no network; source
panel at session scratchpad m5/edgar_filings.json, rebuildable in ~2 min.
(2) DECLARE hold=21 and write the D7 reason in the header (conservative:
same 5 folds as hold=5, 20-month OOS union vs 4.6). (3) Report the
ACTIVE-return breakeven separately — the gate's breakeven_bps reads ~70 for
any fully-invested equity book and is decoration here (D6); honest figure
~18–19 bps/side. (4) Report the strategy/benchmark VOLATILITY RATIO — both
curves are stored, neither vol computed. (5) The benchmark leg makes 175
sequential fetch_daily_bars calls — the most likely non-strategy failure;
check it first if a run dies.


## 2026-08-22 — CARRIED FROM BUILDER D13 BY THE CHAIR

When you record any run: pass dispatched_at and status on
POST /fund/desk/runs. A belt run that dies mid-container currently leaves
no row, so the firm's picture of what your containers cost is biased by
exactly the amount of work that failed. The chair records for you at
resolve — state both facts in your report so they land accurately.


## 2026-08-22 — CARRIED FROM THE VALIDATOR BY THE CHAIR

Two belt facts: (1) leanrunner._add_benchmark builds a BUY-AND-HOLD,
no-rebalance, cost-free EW bar — a candidate that merely rebalances is
compared to a benchmark that does not, and that gap alone can carry a
verdict; name it in every result. (2) The bar's IDENTITY is computed
(benchmark_basis/kind/symbol/legs at leanrunner :1297-1302) and DISCARDED by
the gate — record the basis in your own dispatch output until the gate stores
it, or a must_beat_benchmark failure is unauditable.


## 2026-08-22 — CARRIED FROM THE ADVERSARY (Entry 20) BY THE CHAIR — for the implementation

Entry 20 comes to you as an ALPHA candidate (its premia label was killed by
its own pre-commitment). Sequenced behind the v2 builder. Three things: (1)
**hold the residual sleeve EQUAL-WEIGHT REBALANCED, not drifted buy-and-hold**
— same tilt, same signal, measured ret/vol 1.071 vs 0.933 and vol 20.25% vs
22.74%; drifted buy-and-hold credits the candidate a rebalancing bonus it
does not produce. (2) **Do NOT read daily_returns.benchmark as the gate's
bar** — for multi-name strategies it is the ENGINE benchmark (set_benchmark),
discarded at leanrunner :1218 and replaced at :1291, never recomputed
(corr 1.0000 with SPY on a candidate whose bar is EW(SPY,TLT)); it is also on
a calendar-day clock with ~31% zeros. Compute both vol legs yourself from
benchmark_curve and a full-length equity series and say which clock. (3) The
panel embeds as a literal (~100KB); hold=21; report the ACTIVE-return
breakeven, which dies at ~12 bps against a zero-skill rebalance.


## 2026-08-22 — CARRIED FROM THE READINESS MATRIX (PM) BY THE CHAIR

Entry 20 needs TWO additions before any real stage, not one: the reduced-breadth restructure (PDT+granularity) AND a LOSS-STOP exit whose SET event predates the ENTRY event. Its native ip+3 TIME exit does NOT satisfy the readiness EXIT cell. Commit the loss stop before entry or it cannot leave S0 (sim).


## 2026-08-22 — CARRIED FROM GRACE (run-cfo-3) BY THE CHAIR

The candidate + pre-committed exit for the first Tier-0 measurement is on the
critical path to the first real dollar (~2026-08-28 target, binding on the
CEO's account KYC). Keep the deploy CEO-CLICKABLE - no dependency on the
auto-entry-envelope; it does not need to pass the gate (Tier-0's purpose is real
fills, not a P&L verdict). Commit the loss-stop exit before entry.


## 2026-08-22 — CARRIED FROM BUILDER D14 BY THE CHAIR

An exit rule is a commitment BY a strategy ABOUT a symbol. If the strategy
that holds the position is not the strategy on the rule, the position is
uncovered and its closing SELL cannot be auto-approved. Name the owning
strategy on every exit rule you propose - directly relevant to Entry 20's
loss-stop, which must be owned by the strategy that holds the slot and predate
the entry event.


## 2026-08-22 — STATE from run-quant-entry20 (Entry 20 belt run), appended by the chair

**2026-08-22 — dispatch #3 (Entry 20, announcement_premium) — FIRST REAL GATE PASS**

**THE RESULT.** Candidate `144387901688`, gate **v4.1**, **PASSED**, `failures == []`, verbatim: *"clears every criterion — worth a human look, which is a different claim from 'deploy it'"*. 6,997 orders, PSR 80.37, return 118.614% vs benchmark 84.78%, capacity $19.91M, holdout retention 1.3301 (annualised), 4/4 folds measurable, 3 retained (fold 3 = 0.3767), median retention 1.4883. Winner `slip=0.0001` in all five sweeps. 22 container runs, 96.4 min. I wrote zero lines — nothing blocked execution.

**THE PASS IS WEAKER THAN THE HEADLINE. Four numbers to carry:**
1. **Active IR 0.384, t = 0.60 over 611 sessions.** The alpha claim is not distinguishable from zero. PSR 80.37 was computed on the TOTAL book (Sharpe 2.311, t=3.60) at **beta 0.541** to its own benchmark. v4.1 passes alpha claims on a beta statistic — the same blindness that killed Entry 11, seen from the passing side.
2. **Like-for-like excess is +21.98 pp, not +33.83.** Benchmark curve ended 2026-08-04, strategy 2026-08-21 (equity at 08-03 = $20.68M vs $21.86M final → 106.762% not 118.614%).
3. **Active breakeven 13.9 bps/side** (measured: 1bp → +21.98pp active, 20bps → −10.52pp, slope −1.710). **Total breakeven 64.6 bps** — the gate's own machinery would have been 4.6× too generous.
4. **Vol ratio 0.656**, not the 1.0011 the proposal pre-committed on. Two clocks agree (session 0.6560 / calendar 0.6576); LEAN's `Annual Variance 0.014` → 11.83% corroborates independently. Strategy Sharpe 2.311 vs benchmark 1.289. **This is premia-shaped, and it passed the harder gate anyway.**

**THREE INSTRUMENT DEFECTS, ALL PASS-FAVOURABLE:**
- **`gate.py:405-412` — the breakeven floor is unreachable.** If the sweep says "still profitable at every cost tested", the gate writes the STRING `"beyond the tested range"` into `checks["breakeven_bps"]` and appends no failure. `min_breakeven_bps: 10.0` is never evaluated. A 1/3/5 bps grid only proves >5. **Always measure the active breakeven yourself with one extra container at a bracketing slip — it cost me 9 minutes and produced the number the gate refused to.**
- **`_add_benchmark` truncates to `min(len)` across legs, then labels with `ref_dates[:n]` (the LONGEST leg's dates).** At run time one of 170 legs had 612 bars; I re-fetched 40 min later and **all 170 returned 624 ending 2026-08-20**. Transient, non-reproducible, worth 11.85 pp here. **Caveat #1 (test_end is a request) bites the BENCHMARK leg, not just the strategy leg. Always diff `benchmark_dates[-1]` against `equity_dates[-1]` and recompute the excess on the common window.**
- **Capacity tie-break: three-way tie at 54 fills (FCEL/PEG/PRU).** Priced all arms: $19.93M / $20.52M / $19.16M — **7% spread, verdict-irrelevant here.** Report the magnitude, don't dramatise it; Entry 11's 16.7× was the exception.

**A HYPOTHESIS I CHECKED AND KILLED — do not re-derive it.** Capacity is NOT computed from the 1,000-order truncated list. `trim_result` runs at `runanalytics.capture` (`factory.py:186`), *after* `_add_capacity` (`leanrunner.py:1101`). Modal over first 1,000 is a 9-way tie at 9 (KTOS/MOS/NI/AEHR/AGX); modal over all 6,997 is FCEL at 54 — and FCEL is what was stored. No defect.

**ENGINE FACTS.**
- **A 170-name candidate costs 460–515s per container, not 13s.** Dominated by **170 sequential `SpineBars` fetches (~2.4s each ≈ 408s)**, near-independent of window length. `JOB_TIMEOUT_S = 900` → 1.75× headroom. Budget ~20 min per walk-forward fold, ~96 min per candidate.
- **THE SPINE'S BELT THREAD SURVIVES THE AGENT'S DEATH.** A cut dispatch does not orphan the candidate. Poll `state` before re-running anything. **The spine is on port 8090** — 8000 is nothing, and reading 8000 as "spine down" cost me a wrong first conclusion.
- Job polling is `GET /fund/lean/backtests/{job_id}`; there is no `/fund/lean/jobs`. `GET /fund/factory/candidates/{id}` carries `analytics.verification.result` (equity_curve, benchmark_curve, daily_returns, capacity, statistics); the LIST endpoint does not.
- `daily_returns` is **calendar**-daily (907 obs, 18.7% exact zeros); `benchmark_curve` is **session** (612); `equity_curve` is **LEAN-downsampled** (400). Three clocks in one payload — align on `benchmark_dates` and check `dropped_unmatched_days` before computing any vol.
- 238 buying-power rejections / 8,662 `set_holdings` calls (2.7%) despite reductions-first and a 0.98 book buffer.
- Turnover **10.41%/day ≈ 56×/yr**; $1.391bn traded on $10M; **$139,134 per bp/side = 1.391 pp of start equity per bp**. Median fill $251,124 = a full k=40 tilt slot, so the book is tilt-dominated, not EW-residual-dominated.
- Median traded price $88.09; p5 $7.87; 6.7% of fills under $10. **No phantom price factor in this basket** — the $9,774 max is NVR, genuinely ~$9k. Return-based signal, so the standing price-level constraint was never engaged.

**METHOD THAT PAID.** Checkpointing every phase to disk as it landed meant the second interruption would have cost nothing. Running `window_for_strategy` instead of asserting geometry. Pricing all three arms of a tie rather than calling it "unstable". Checking the truncation hypothesis before reporting it — it was false.

**HYBRID SPLIT:** not used. Zero lines written. Not a data point either way.

**FITNESS.** Implementations reaching an honest gate verdict without dying on an instrument defect: **1/1 this dispatch** (the belt completed end to end, no timeouts, no failed jobs). Instrument defects surfaced by running: **3** (breakeven floor unreachable, benchmark window truncation, capacity tie priced) plus **1 hypothesis correctly killed**.


## 2026-08-22 — CARRIED FROM BUILDER D15 BY THE CHAIR

The benchmark leg was fetched from a DIFFERENT VENDOR than your strategies
trade: marketdata.py routes any start+end call to Yahoo while your containers
get Alpaca, and Yahoo lags one session — so every excess you have ever quoted
was computed against a bar ending one session before your own curve
(systematic, not the transient truncation you found). MERGED FIX: snapshotted
candidates now pin one vendor; read `benchmark_truncated` and
`benchmark_feed_mixed` on every result — if either is present, the bar is not
the window you think. And keep checking benchmark_dates[-1] vs
equity_dates[-1] regardless.


## 2026-08-23 — CARRIED FROM THE EXEC PAIR BY THE CHAIR

1. (Grace) Before the Entry 20 v5 re-judge: the benchmark population is survivor-only (universe.py:115 screens ACTIVE-now) with a MEASURED bias of −6.90pp ± 2.40/20mo in the KILL direction (SURVIVORSHIP_2026-08-17.md). A wiring ticket is filed and hard-sequenced before the re-judge; if you run before it lands, **say the bias in the verdict** — an honest verdict that omits a measured known bias becomes contaminated history.
2. (Vishesh) Treat every pre-cf0368d benchmark comparison as contaminated (vendor split + one-session lag), Entry 20's included. Cite the v5 re-judge, never the v4.1 pass.
3. (Grace) Entry 20's restructure does NOT need to survive PDT (retired 2026-06-04; ip+3 generates zero day trades). Granularity alone binds.
4. State next_actor, due_date, reversibility on every recommendation you file.


## 2026-08-23 — CARRIED FROM BUILDER D16 BY THE CHAIR

Your Entry 20 challenge is built (gate v4.2, with the adversary blind before merge), and it changes how you submit: the belt now REFUSES at submission any candidate whose slip grid tops out below the gate's cost floor — **declare a grid point at or above 10 bps or the submission 400s**; it costs one container instead of 96 minutes. Your total-vs-active point is NOT closed: the gate labels the scale (`breakeven_basis: total_return`) and still cannot compute active — **never read `breakeven_bps` as an alpha candidate's fragility number.** And carry this into every report: **sweep grid points run on the HOLDOUT'S TRAIN WINDOW while the verification run covers the full window** — a sweep return and a headline return are not comparable and never were.


## 2026-08-23 — CARRIED FROM THE PM (run-pm-0908) BY THE CHAIR

Before you report any belt number for a candidate the fund might deploy, **state the book size the run used and whether `honours_fractional()` returned True.** `announcement_premium` reads no fractional parameter, so every number so far is whole-share at $10M — harmless there, the whole result at $250. "Measured at $10M" and "deployable at $250" are two different measurements; never let one stand in for the other. R47 (fractional re-run at nav=250/500) is ticketed for you, sequenced behind the benchmark-population fix.


## 2026-08-23 — CARRIED FROM THE ADVERSARY (batch 2) BY THE CHAIR

Your active-breakeven method is now load-bearing in the gate's own version note (v4.2 records breakeven_basis and cites 64.6 total vs 13.9 active). Keep issuing the active number as a pre-run prediction — it remains the only check on a criterion that judges an alpha claim on a scale 4.6x too generous. And when v4.2 merges: Entry 20's re-run needs a slip grid point at/above 0.0010 or the submission 400s.


## 2026-08-23 — CARRIED FROM PM R39 BY THE CHAIR

The /executions round-trip statistics (win_rate 0.3636, expectancy 1.0645, n=11) become UNCOMPARABLE after Monday — six sets of shares get realised twice (phantom fill then real). Never quote them without the fence; never put pre- and post-2026-08-24 round trips in one table.


## 2026-08-23 — CARRIED FROM BUILDER D17 BY THE CHAIR

No short-selling strategy reaches the belt on the assumption that exits work. The sign inversion is fixed, but a short's **unbounded downside, borrow cost, and buy-in risk remain unmodelled everywhere** — and the drawdown machinery assumes bounded downside. Any artifact with a short leg names those three as open risks; `exit_sign_fixed` is not coverage of them.


## 2026-08-22 (late) — CARRIED FROM BUILDER D18 BY THE CHAIR

When you propose anything that adds an EVENT TYPE to an existing aggregate, state which folds gate on that aggregate and whether your event is a LIFECYCLE step or a FINDING/annotation. One line from you; the harness now fails a test on an unclassified type, so an unanswered proposal fails CI rather than shipping a defect.


## 2026-08-22 (~22:20Z) — CARRIED FROM THE ADVERSARY (D18 re-review) BY THE CHAIR

`snapshots.py` has NO code-version key: if a measurement you take is served from a snapshotted fold, a projection-logic change between two runs means the runs are NOT comparable for reasons unrelated to the strategy. Same family as the unseeded-hash capacity: name the mechanism; never present the pair as before/after.


## 2026-08-22 (~23:15Z) — CARRIED FROM ED (batch #1) BY THE CHAIR

WHEN ENTRY 21 SURVIVES THE ADVERSARY and you implement: **w_hi = 0.600 is part of the SPEC, not a tunable — assert it, never sweep it.** Sweep only the instrument (EDV primary vs TLT fallback — one candidate, declared grid) and the cost grid {1,3,5,10,15,20,25}. Put an assertion in the algorithm that at most one weight-state transition occurs per session — the no-collision property is structural in the rule and must be structural in the code. Exit ownership per D14: the rule's own strategy_id holds what it sells.


## 2026-08-22 (~23:50Z) — CARRIED FROM THE ADVERSARY (Entry 21 review) BY THE CHAIR

Entry 21 is KILLED pre-belt — do not implement. FOR THE RECORD if it is ever resurrected: the adversary's pre-run prediction is active +3-4%/yr, BE 8-10 bps/side on the belt window, FAIL. And a standing rule from this review: **a candidate whose active return is a duration-timing overlay gets its breakeven read off total_return_pct (leanrunner.py:295) — inflated ~1.35× here. State BOTH numbers in every report so the gate's figure is never the only one on the record.**


## 2026-08-23 (~00:50Z) — CARRIED FROM THE VALIDATOR (census batch) BY THE CHAIR

State your grid's MAXIMUM TESTED SLIP in every submission and make it exceed min_breakeven_bps — the widest slip tested is now the number the gate compares to the floor, and factory.check_cost_grid refuses before a container starts. Entry 20 spent 96.4 minutes and 22 containers to reach a sentence that costs nothing at submission time.

## 2026-08-23 - CARRIED FROM BUILDER D19 BY THE CHAIR

Your bar URL is now a GATE INPUT, not a data detail. factory.effective_history_floor reads lookback_days out of your algorithm's source and uses it to decide how far back the walk-forward may reach: 700 gets the old 2024-02-26 window, 2000 gets 2021-02-11, and declaring nothing (or two different values) gets the SHALLOWEST treatment - unknown is never unlimited. Declare ONE unambiguous lookback_days in every algorithm you write. When you take the SpineBars start_date/end_date ticket: measure folds_before_data_path_reach before and after on the same candidate - it is 2 of 4 today for a 700-day algorithm, and that number is the ticket's whole return. (Pending adversary clearance of D19.)

## 2026-08-23 - CARRIED FROM THE ADVERSARY (D19 review) BY THE CHAIR

Under any merged form of D19, the lookback_days line in your bar URL decides your candidate's fold geometry (700 -> 4 folds need 4; 2000 -> 6 folds need 5 on the deep floor - a measured 1.7pp difference in how easily noise clears the walk-forward leg). State the lookback_days you chose AND WHY in every implementation memo. And a declared lookback the container fetches from the wall clock does NOT cover a backdated holdout - the bar URL carries no end_date today.

## 2026-08-23 - CARRIED FROM ED (batch #2) BY THE CHAIR

If P1 (Entry 11 month-turn reversal) or P2 (month-end duration extension, last-3 TLT/BIL) survive the adversary, implement from the FROZEN SPECS in docs/mechanism/ED_BATCH2_2026-08-23.md verbatim - do NOT consult cycle-1's Entry 11 numbers, they do not reproduce under the frozen spec (+80.7 claimed vs +39.56 recomputed, same window). Declare HOLD_DAYS=21 on both. P2's gate breakeven will be BIL-carry-inflated (D6) - record the active-basis number (16-17 bps/side) beside it.

## 2026-08-23 - CARRIED FROM THE ADVERSARY (Ed batch #2 review) BY THE CHAIR

P1/P2 are killed; no containers. Standing rule if any conditional rule ever reaches you: the belt run needs a SECOND ARM - the same algorithm with the observable frozen to a constant; their DIFFERENCE is what the gate should judge. And for a rule holding one asset over a k-session window, breakeven bps/side = mean bps/mo / 2, invariant to k - window choice must be justified on mechanism, never breakeven.

## 2026-08-23 - CARRIED FROM BUILDER D21 (the knowledge graph) BY THE CHAIR

fund_lean_jobs carries no candidate id and fund_candidate_sources has 0 rows - nothing links a container to the candidate that spent it, so cost-per-kill is time-window inference (exact for 16/41). When you submit a belt run, record the candidate id somewhere structured; the graph then prices kills exactly.

## 2026-08-23 - CARRIED FROM BUILDER D20 BY THE CHAIR

Your SpineBars change is the ONLY thing between the fleet and a deeper gate: 14 of 16 algorithms are pinned at the 2024-02-26 window purely because their bar URLs declare lookback_days=700 and carry no dates; the two that declare 2000 now get twelve folds and nearly DOUBLE the gate's power at no measured false-alarm cost (22.18% -> 39.91%). Teach the bar URLs start_date/end_date (format=csv already honours them) and every algorithm inherits it - this also retires the ratchet. Always: state declared lookback_days in any algorithm, and declare HOLD_DAYS explicitly - 15 of 16 have their hold ASSUMED at 21 and the fold geometry is sized from it.

## 2026-08-23 - CARRIED FROM THE VALIDATOR + ADVERSARY (parity/D20) BY THE CHAIR

HOLD_DAYS is now a GATE-GEOMETRY parameter: declare it explicitly (15 of 16 algorithms have it ASSUMED at 21) and state it + declared lookback_days in every belt report. At the live floor, hold 3 plans 5 folds and hold 4 plans 4 - one day moves a real edge's pass rate 37.2% -> 22.9%. Holds {4,9,14,19,20} + lookback>=910 land on a measurably looser bar (+1.1..+2.6pp) - never choose the hold to suit the bar; choose honestly and FLAG the combination (the adversary's watch-trigger will re-measure your cell). Run window_for_strategy(end, HOLD_DAYS, 4, effective_floor) before writing and report the fold count.

## 2026-08-23 - CARRIED FROM DOC (shelf v2) BY THE CHAIR

Before implementing ANY strategy reading an SEC form published on a review cycle (UPLOAD, CORRESP): use the DISSEMINATION date from the daily index, never filingDate - they differ by a median 57 days and agree 0.13% of the time; a filingDate backtest trades two months before the information exists and the belt cannot see it. Lookup: data/research/sec_correspondence_dissemination_2020_2026.csv.

## 2026-08-23 - CARRIED FROM ED (batch #3) BY THE CHAIR

The bars API end_date is EXCLUSIVE (verified by two independent workers; card corrected) - an off-by-one there silently shifts every window. And at lookback 2000 + deep floor the gate hands 12 folds at ANY hold - retained-share 0.5 now means 6-of-12, not 2-of-4; plan fold budgets accordingly.

## 2026-08-23 - CARRIED FROM DOC (the 8-K panel) BY THE CHAIR

fetch_daily_bars' `end` is EXCLUSIVE (the internal twin of the API endpoint finding, verified independently): a hold window ending on a named session LOSES ITS EXIT BAR unless you pass the day after; contiguous chunked pulls silently drop a session at every boundary - overlap chunks and check year session counts against known NYSE closures (2001=248, 2012=250, 2008=253).

## 2026-08-23 - CARRIED FROM ED (the universe slate) BY THE CHAIR

If the Liberty pair ever reaches you: the harvestable form is a LONG-ONLY rotation between FWONA and FWONK - never a pair trade (no shorting infrastructure), and the two legs are ONE position with a scheduling rule against same-session opposite-side fills.

## 2026-08-23 - CARRIED FROM THE VALIDATOR (joint power) BY THE CHAIR

When your Entry 20 run returns, your NEXT dispatch is the gate's first POSITIVE CONTROL + THE PSR IDENTIFICATION: run the four META archetypes (specs in run-validator-jointpower - BH, VOLSCALE, DDLIMIT, DIPBUY) with lookback_days=2000 AND HOLD_DAYS declared, and CAPTURE LEAN'S RAW STATISTICS BLOCK VERBATIM (observation count, benchmark series, benchmark Sharpe beside the reported PSR) - one run resolves whether the gate's TPR at Sharpe 1.0 is 25% or 1.6%. Score the pre-registered prediction ledger, especially DDLIMIT (predicted: passes everything except the one-shot holdout). Without lookback=2000 the consistency test will not run at all - the submission-format lottery, measured.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d24) BY THE CHAIR

Before starting a container batch or a bulk extraction, READ FREE HOST RAM and check for `ClarkHarness/.suite_running` (builder suites) and `ClarkHarness/.belt_running` (belt). The host sat at 0.49 GB free of 15.16 on 2026-08-23 with three builders live; the 2026-08-22 collapse happened at 1.28 GB. A wall-clock measurement taken in that band is corrupted, and a job that dies with the host loses everything it has not committed — bundle/commit as you go.

## 2026-08-23 — RUN-RECORD PROTOCOL v1 (chair, from run-builder-d24; the seat-protocol companion to desk routing v1)

Every recommendation in your output MUST carry all four routing fields, stated, never left to inference: `next_actor` (who moves next: ceo / chair / a named seat), `due_date` (ISO date or null), `reversibility` (reversible / hard-to-reverse / irreversible), `money_at_stake` (number or null). And your run's meta names `serves_requests`: the desk request ids your run answers (empty list if none — say so). `null` is legal and honest; SILENCE is what gets refused once enforcement flips: measured on live traffic, 16 of 21 of one day's runs across eight seats would have been refused-not-recorded. Until the flip, the desk returns `routing_advisory` on each filing — treat any advisory naming your seat as a defect in your own output.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d23) BY THE CHAIR

(1) Entry 20 is ONE GRID POINT from a certified premia claim. When the chair fires your next dispatch (sequenced after your censor re-judge lands and after the D23 gate merge): re-run `announcement_premium` with a cost grid whose widest slip is AT OR BEYOND 10 bps and submit it as `claim_type="premia"` (`POST /fund/factory/candidates` takes the field; `CandidateFactory.submit(..., claim_type=)` refuses an unknown word before the containers). Every other criterion is already clear on the stored evidence.
(2) LEAN's own `Annual Standard Deviation` is a CALENDAR-clock number annualised at sqrt(252) and is ~17% too low (measured 1.2033–1.2047 on 4/4) — never quote it as the strategy's volatility without saying which clock.
(3) The payload carries TWO benchmarks: `daily_returns["benchmark"]` is the series `_add_benchmark` DISCARDS for multi-name strategies; `benchmark_return_pct` is the recomputed basket and is the bar the gate reads. Never compute a statistic from the discarded leg.

## 2026-08-23 — STATE after dispatch #4 (Entry 20 re-judge under gate v4.3), appended verbatim by the chair — FENCED VERDICT, INSTRUMENT-CAUSED

**THE RESULT.** Candidate `997187b267d3`, gate **v4.3**, **passed: false**, verdict `"fails 1 of the bar"`, ONE failure verbatim: *"cost robustness was tested only to 3 bps and the floor is 10 — widen the grid past the floor"*. I submitted a grid topping at 10 bps; the 5 and 10 bps containers hung and were killed at 900 s, so `tested_range` collapsed to [1, 3] bps. Everything else passed: PSR 80.37, return 118.614 vs benchmark 84.82, capacity $19,913,113.08, holdout retention 1.3301 (annualised), orders 6997, **9 measurable folds of 12 planned against 9 required — zero margin**, 8 retained, share 0.889, median retention 0.9419. 66 containers, 180.1 min. **ZERO lines written** (md5 `493eb3afaee2cc594bd5f032c69fa049`, unchanged from the v4.1 run); the only change was one grid point.

**THE 900 s CENSORING IS THE HEADLINE AND IT IS NOT NEW.** 14 of 66 containers finished at 900.3–900.7 s, all `failed`; the other 52 finished in 21.3–82.5 s. **Nothing between 82.5 and 900.3 s.** Postgres says the v4.1 run was 21 done (452.6–559.2 s) + **1 failed at 900.42 s** — so **my 2026-08-22 STATE claim of "no timeouts, no failed jobs" was WRONG**; the rate went 4.5% → 21.2%. Signature: the container stalls after `Launching analysis` and BEFORE `AddPendingInternalDataFeeds`, at CPU 2%, RAM flat, **zero open sockets**. Killed three hypotheses: concurrency, the spine (33 ms while two hung), external bulk load (four timeouts predate it). Root cause unknown, outside my scope. **The discriminating experiment is `FUND_BAR_SNAPSHOT=0` + `scripts/belt/verify_bar_snapshot_e2e.py` — a chair action.**

**ALWAYS AUDIT THE REALISED GRID, NEVER THE DECLARED ONE.** Declared 4 × 13 = 52; **realised 39, mean 3.00 per sweep, range 2–4.** Winner is `max(total_return_pct)`, monotone decreasing in slip in 39/39 — a censored point can only move a winner if CHEAPER than every survivor: folds 2, 10, 12. Fold 2 unmeasurable either way. Fold 12 margin 0.40. **Fold 10 retention 0.5361 against the 0.5 floor — margin 0.036, inside the perturbation; the counterfactual (~0.55) is an extrapolation.** Label: **SELECTED-FROM-CENSORED-GRID, fenced.** The v4.1 pass was also censored (job `b18363d63b06`) and clean only by luck.

**THE DEEPENED FLOOR BUYS FOLDS THE ALGORITHM CANNOT TRADE IN.** The ratchet grants depth on `lookback_days` alone; it never checks declared warm-up against the reach. Data starts 2021-02-26, the 253-session liveness filter is satisfied only from **2022-02-25**, and **folds 1 and 2 begin with 0 of 170 names live** (167/174 orders in a year vs 4,289; both trains negative, both unmeasurable) — yet they counted in the DENOMINATOR (12 planned → 9 required), and `folds_before_data_path_reach` reported **0**. Absence-as-zero in the field built to report it. `lookback_days=2000` is the endpoint's hard maximum, so the data path cannot be deepened from my side.

**DECLARED CLOCK, AND IT COST ME A FOLD HONESTLY.** HOLD_DAYS=21 declared; holds 3 and 5 also plan 12 folds but require only **8** — declaring the rule's true ~5-session hold would have LOOSENED the bar by the one fold it cleared by. Keeping 21 was faithful and strictly harder. Say this every time.

**BENCHMARK STILL NOT LIKE-FOR-LIKE.** `benchmark_truncated` (612 vs 625 bars, EQR), `benchmark_feed_mixed: ["alpaca","yahoo"]` despite 170/170 pinned — Alpaca's AVB/EQR legs end early, barcache correctly declines partial windows, fallback routes to Yahoo, basket truncates to 2026-08-04. **Like-for-like excess +21.945 pp, not the headline +33.797** (reproduces v4.1 to 0.04 pp).

**NUMBERS THAT REPRODUCED EXACTLY.** Vol ratio **0.656** (14.043% vs 21.407%, 611 sessions; LEAN Annual Variance 0.014, Beta 0.102). Active IR **0.3836**, TE 12.652%, **t = 0.597** — still indistinguishable from zero. Capacity identical to the cent (FCEL). Active breakeven **13.83 bps/side** (slope −1.7103 pp/bp; no new container spent). Gate's `breakeven_basis: "total_return"` at 64.6 bps is **4.7× too generous** — never quote it for this candidate. Benchmark population: `survivor_only`, names 170, **names_judged 0**; Grace's −6.90pp ± 2.40/20mo KILL-direction bias stated in the verdict.

**ENGINE FACTS.** Bar snapshot: 170 legs in **26.9 s**, median useful container **33.4 s** vs 452–559 s — a 14× speedup, and the one data-path change correlated with the hang-rate rise. The snapshot is process-GLOBAL (`barcache._ACTIVE`) so a belt run's snapshot report is not purely its own. `lean_workspace/snapshots/{candidate_id}.json` is the only structured candidate↔data link; **jobs still carry no candidate id** — my 66 were inferred by time window.

**METHOD THAT PAID.** `check_cost_grid` / `window_for_strategy` / `effective_history_floor` locally before submitting — three facts for zero containers. Live-name count per fold computed from the snapshot BEFORE reading the verdict. Own external-load hypothesis tested against timestamps and REFUTED. Postgres queried for v4.1 durations rather than trusting my own STATE — which is how I found my own error.

**RECORD CORRECTION (2026-08-22 STATE): the v4.1 Entry-20 run was NOT clean** — 21 done + 1 failed at 900.42 s. Corrected here by append, never by edit.

**FITNESS.** Honest-verdict-without-instrument-death: 0.5 of 1 (full verdict, every new v4.3 field populated; but fenced). Instrument defects surfaced by running: 4, plus one correction to my own prior STATE, plus three hypotheses correctly killed. Hybrid split: not used, zero lines written, not a data point either way.

## 2026-08-23 — CARRIED FROM ADVERSARY (run-adversary-d23-d24) BY THE CHAIR

`claim_type` is submitter-declared and any premia bar is materially easier for anything holding cash or T-bills. **Before declaring `premia`, compute your strategy's Sharpe advantage over its bar on EXCESS returns using the REALISED cash series (BIL from the fund's own feed) over your own window, and state that number in the filing.** If it is within ±0.05 of zero you have a beta/carry re-mix, not a premium — and say so yourself before the gate has to.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d28) BY THE CHAIR — standing rule, adopted

**Any one-off measurement script whose output becomes a headline number must first run against a case where it MUST return zero, and its exclusion rule is stated beside its output.** Basis: a D28 occlusion probe over-counted 30× (1,923 vs 65) and passed its own author's review because the number was large and pointed the expected way; the wrong figure reached four comment blocks and a commit message before a second instrument caught it. The null test costs one minute.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d27) BY THE CHAIR

`family_ledger` no longer reports `tested`; it reports **`recorded`** (proposals the graph knows) and **`judged`** (proposals with ≥1 live, non-voided verdict), and a family whose every outcome is fenced reads **RECORDED_UNJUDGED**. **Use `judged` as the denominator for any family-wise correction** — `recorded` counts things nobody has run.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d29) BY THE CHAIR

Once D29 merges, a premia candidate is judged on returns NET OF THE REALISED BIL SERIES over its own window, and the cash leg is fetched LIVE (not pinned to the candidate's snapshot). So a re-run of the same specification on a different day judges against a different cash rate. **State `rf.realised_annual_pct` beside any premia verdict you report, and never compare two premia verdicts struck on different windows as though the bar were the same.**

## 2026-08-23 — CEO DECISION, carried by the chair: ENTRY 20 IS A PREMIA CLAIM

Verbatim: 'Yes as premia makes sense' (CEO, 2026-08-23, on the chair's fork: alpha reads t=0.597 indistinguishable from zero; premia clears the whole v5r1-measured bar). The re-submission after the D23+D29 merge goes in as claim_type=premia, judged by the v5r2 realised-rf bar. Recorded falsifier (decisions-are-provisional rule 4): if the reconciled vol-ratio computation Ed names as authoritative reads >= 1.0 on the belt's own bar (0.656 today), the label reopens. Ed's falsifier-computation reconciliation continues as hygiene, not as a blocker.

## 2026-08-23 — CARRIED FROM ED (run-ed-batch4) BY THE CHAIR

The feed's closes are **DIVIDEND-ADJUSTED TOTAL-RETURN series, not prices** (chair-verified: KO 23.57 and T 9.52 on 2012-06-01; AT&T's actual price then was ~$34; only the last bar is a real price). Your return and benchmark arithmetic is unaffected (the bar is built the same way), but **state the basis whenever you report anything level-dependent, and never derive a market cap, price tier, or capital loss from a historical close.**

## 2026-08-23 — CARRIED FROM DOC (run-analyst-pituniverse) BY THE CHAIR

**Our own price feed cannot be asked "is this the company I meant."** 120 of 703 dead S&P tickers (17.1%) return a DIFFERENT, currently-listed company's prices at HTTP 200 (recycled tickers; marketdata.py never reads the vendor's instrument metadata — ticketed). Until the identity check lands: **any belt universe built from a pre-2015 constituent list is contaminated and the gate cannot catch it** — every fold reads the same wrong series. Also: BRK-B/BF-B are unreachable through the feed (dash validation).

## 2026-08-23 — CARRIED FROM ADVERSARY (run-adversary-d29) BY THE CHAIR

When you implement or re-run any candidate declared **premia**, state its **maximum gross exposure** in the submission and the report. The gate has no gross field yet (D32 is adding capture + a fail-closed refusal above 1.0): until it merges, your stated number is the only thing between a levered cash book and a free (1−1/G)·rf/sd Sharpe gift (+0.15 at 1.25×, +3.2 at 3×, measured). Never read a premia `sharpe_advantage` as skill without the gross beside it. (Entry 20 is unaffected: gross ≤0.95.)

## 2026-08-24 — CARRIED FROM BUILDER (run-builder-d32) BY THE CHAIR

Post-merge, the gate reads `result["exposure"]` (the engine's Exposure chart) — a field the belt only started writing with D32. **Every stored candidate refuses the premia bar until freshly re-run** (0/55 carry it; the raw results were pruned, nothing back-fills). That is the fix, not a defect. Corollaries: a book whose max per-timestamp gross exceeds 1.0 is REFUSED, not scored — say so before burning containers on a levered/vol-scaled premia idea; and `exposure.measurable: False` on a fresh run means check the statistics block (the only two chartless runs on disk have zero statistics). Entry 20's fresh premia run post-merge captures exposure by design.

## 2026-08-24 — CARRIED FROM ADVERSARY (run-adversary-d32) BY THE CHAIR

On any premia belt run: confirm `result["exposure"]["measurable"] is True` before reporting anything; a stored result CANNOT be re-judged into a premia verdict (all 55 refuse) — re-run is the only path. Above 1.0x gross is REFUSED outright, not scored.

## 2026-08-24 — CARRIED FROM DOC (run-analyst-ethdossier1) BY THE CHAIR

Any ETH/crypto candidate runs on the belt today with no new code (endpoint serves ETH-USD incl. weekend bars; LEAN custom data defaults always-open) — BUT `leanrunner.py:1651` annualises at √252, understating a 365-day series' vol by 1.2039× (84.6% reports as ~70.3%), and every Sharpe/PSR/vol-cap criterion inherits it. Declare the benchmark explicitly. And the symbol law: **`ETH-USD`, never bare `ETH`** (which is a $23 ETF, 107× away).

## 2026-08-24 — STATE from run-quant-metacontrols (dispatch #5, THE POSITIVE CONTROLS), appended verbatim by the chair — 4 honest verdicts, 117 containers, zero timeouts

**WHAT EXISTS NOW.** meta_ctrl_{buyhold,volscale,earnwindow,pead} in the sandbox; candidates 0427da00eb66 (v4.3 fails 5) / 331b61ee31b1 (v5r3-premia fails 2) / ca0fba4598e7 (fails 4) / c1bf12c33306 (fails 4). All UNIVERSE=["META"], floor 2021-03-02, whole-share $1M, run ONCE, never tuned.

**PSR IS IDENTIFIED. IT IS NOT A LUCK FILTER.** Four positive-mean controls scored 2.128/1.398/0.051/0.315% — impossible against target 0 at any n. Implied target **0.07548 ± 0.00414/obs (cv 5.5%)** across Sharpe −0.18..+0.29, vol 15..36%, kurtosis 24..196. NOT the benchmark Sharpe (fifth construction rejected, cleanest design possible). **To clear PSR 65 at n=1936: per-obs 0.08424 = LEAN Sharpe 1.337.** Our own statistics module at target 0: 85.0/90.4/50.2/78.3 on the same series — 40× disagreement between two things called PSR. → CEO ruling on the desk.

**THE PREMIA BAR'S KILL-DIRECTION BIAS, measured**: LEAN pays 0% on cash; the bar subtracts realised BIL from both legs → a cash-heavy book is charged carry it never earned: **+0.093..+0.100 Sharpe understatement** on volscale (cash weight 0.543 replica / 0.583 engine-Beta), 12× its +0.00756 advantage. `rf_breakeven_pct` 3.6431 vs realised 3.365 — 0.28pp flips it. Never read a small premia advantage without this beside it. Fix = LOOSENING → adversary blind (D36).

**FILL TIMING SETTLED, MEASURED**: a decision on bar d fills at **close(d)** (smoke: 320.19×1.0005). Use `data[sym].time.date()`, never `self.time`. One 16s smoke container closed the biggest implementation risk in three files.

**SINGLE-NAME CANDIDATES: 10–18s/container (vs 452–560 for 170 names) AND a structurally clean bar** — `benchmark_series_source: engine_single_name` (no vendor split, no truncation, no survivorship, no capacity tie). The 900s ceiling is a FETCH-COUNT problem, not window length. Prefer single-name framing when the idea allows.

**KNIFE-EDGES**: earnwindow's holdout train 5.017% vs the 5.000 floor — 1.7bps chose the verdict's SHAPE (number vs absence); volscale 9-of-12 measurable vs 9 required, zero margin, and its fold 9 retention 10.04 off a +6.448% train leg — the exploding denominator 1.4pp above the floor built to stop it. **MIN_TRAIN_RETURN_PCT makes fold measurability a function of the ASSET'S direction for long-only single-name rules** (2 of 4 folds dead on all three 63-hold controls purely because META fell those years).

**HOLD_DAYS IS THE DECISION CADENCE, not days held** — the event pair holds 5/20 sessions but decides quarterly → 63 buys 4×252-day legs with exactly 4 decisions each; declaring the literal hold plans 12 starving folds. No harness code reads BENCHMARK or CLAIM_TYPE constants yet (grep-verified) — only HOLD_DAYS and UNIVERSE; UNIVERSE is the only benchmark control, and declaring one you don't trade is benchmark shopping, refused.

**CENSUS**: 117/117 done, 0 ceiling, 17.5 min; points_declared==realised every sweep; `fund_lean_jobs.algorithm` is an EXACT candidate link when one algorithm runs once — use it over time-window inference. **BELT-LOCK EXCEPTION CONFIRMED BY THE CHAIR**: writing ClarkHarness/.belt_running is permitted when the dispatch brief instructs it — a coordination flag is a coordination surface, not code; the write-scope boundary otherwise stands.

**BELT ETIQUETTE**: background tasks are EVICTED when new ones start — run ONE self-contained background process (wait → lock → every step → release, checkpointed), never two cooperating pollers.

**OBSERVED**: a9db39fdfab5 orphaned at exactly its 3h ceiling while SLOT-STARVED by my own 117 containers (chair diagnosed: runner alive, resumed when slots freed) — a candidate leaving `running` is NOT a free belt; check state=='done'. 9b767717ff08 stands done/passed-true.

**FITNESS**: 4/4 honest verdicts without instrument death; 4 instrument findings (PSR identified + sentence shown false; cash-carry bias quantified; direction-dependent measurability; the unreachable breakeven floor ×4 more); pre-registration scored 4/4 fold geometry, 3/4 returns ≤0.35pp, three misses named and owned.

### EVOLVE — two accepted: **WRITE THE OFFLINE REPLICA AND PRE-REGISTERED PREDICTION BEFORE SUBMITTING, and spend ONE smoke container on fill timing before a hundred on a verdict** (basis: 4/4 fold geometry predicted for zero containers; the 0.84pp miss came from modelling a static purchase as a rebalanced weight path; one 16s smoke settled close(d) fills). **RUN THE BELT FROM ONE SELF-CONTAINED BACKGROUND PROCESS** (basis: two cooperating pollers = two things that die and one that double-submits; both were evicted mid-wait).


---

## BIND from cfo (run-cfo-8, carried by the chair 2026-08-24) — a documented LEAN capability, UNVERIFIED against our stack

`lean research` / QuantBook runs locally against the same data providers as `lean backtest`, and `lean.json` supports a LocalObjectStore ("object-store", "object-store-root") persisting artifacts BETWEEN research and backtest runs — the documented pattern is train-in-research, save, load-in-backtest. Against your own census (86.4% of container-seconds is deadline, 3.1% useful slot utilisation, the hang cost 210 container-minutes of a 180-minute run): a hypothesis-evaluation path that spawns no graded container per fold, and a vendor-maintained home for the caching that took your median container 452s -> 33.4s. NOTHING verified against our docker image, SpineBars, or the container harness. It is NOT a gate and produces NO verdict. And the bar-snapshot data-path change is the one change correlated with the hang rate rising 4.5% -> 21.2% — caching here is not consequence-free. The coursework rule binds: docs first, probe second, surviving fact to PLATFORM_FACTS.md.
URLs: https://www.quantconnect.com/docs/v2/research-environment/key-concepts/research-engine ; https://www.quantconnect.com/docs/v2/research-environment/object-store


---

## BIND from adversary (run-adversary-batch4, carried by the chair 2026-08-24)

The +/-0.05 noise band you measured on sharpe_advantage is now the DECIDING quantity, not a caveat: under a credited-cash belt, a zero-skill cash mix scores |adv| ~ 0.01, five times inside your band. Any premia number you report must carry the cash weight and state whether the run's cash earned interest, because the two arms differ by more than the margin.


---

## BIND from builder (run-builder-d36, carried by the chair 2026-08-24)

A premia claim whose return series is an exact linear function of its benchmark is now UNJUDGEABLE, not merely failing: the advantage has no sampling variation and the gate refuses it. If you implement a cash/beta or pure-overlay shape, it needs genuine tracking error to be a claim at all. And no stored result can make a premia claim until it is re-belted: the payload needs schema 4 (the invested-weight series only the new parser writes).


---

## BIND from adversary (run-adversary-d36-prodgate2, carried by the chair 2026-08-24)

Your +/-0.05 advantage noise band is now load-bearing in shipped code: it is the stated rule that chose premia_min_luck_pct = 65.0. If you ever re-cut the band, say so loudly - a criterion depends on it. And a belt result with no undownsampled daily_returns block now fails the alpha gate outright on the luck leg (426 of 765 stored results do) - confirm the block is present before you count a run as judgeable.


---

## BIND from builder (run-builder-d37, carried by the chair 2026-08-24)

When you re-run the belt after D37 merges, a premia verdict's top-level `criteria` now carries the premia keys too - read the bar that judged a candidate from verdict[criteria] alone. And expect 656 changed failure SENTENCES with ZERO changed verdicts on any re-judge of stored results: if you see a verdict flip, that is a finding, not noise. Also queued to your next batch: the engine-target pin experiment (one LEAN container over a synthetic series of known Sharpe, reading the engine PSR target directly).


---

## BIND from adversary (run-adversary-d37-prodgate3, carried by the chair 2026-08-24)

The alpha gate's luck leg is NOT "P(Sharpe > 0)". It is P(the strategy's true EXCESS Sharpe exceeds an annualised 1.0) >= 65%, computed on 252 observations per year with a daily rf already subtracted by the engine. Price a candidate against a 1.0 annualised excess-Sharpe hurdle at 65% confidence before you spend a container on it - that leg refuses 656 of 765 stored results and is the second-largest kill cause in the fund's history. (Chair: the engine-target pin experiment queued to your batch earlier tonight is RETIRED - the target is published; nothing to run.)


---

## BIND from analyst (run-analyst-golddossier1, carried by the chair 2026-08-24)

If a gold candidate reaches you: (1) a Sharpe improvement below ~0.6 is UNDETECTABLE on every gold sample that exists (SE(Sharpe)=0.357 on 11y, 0.221 on 23y) - report gold vol-targeting results as TAIL claims (worst-20-day drawdown), never Sharpe claims, and say so in the failure sentences; (2) gold's benchmark default is bad: SPY removes 0.3% of gold's variance (residual sd 1.022% vs raw 1.025%) - benchmark against gold itself or GC=F, and say which.


---

## BIND from pm (run-pm-goldsizing, carried by the chair 2026-08-24)

When a vol-targeted commodity or gold archetype reaches the belt: the Sharpe leg is pre-registered at <= 0 (Harvey: negligible for commodities) and SE(Sharpe) ~ 0.357 on an 11-year gold sample means any Sharpe difference below ~0.6 is undetectable on any constructible gold sample. Report the TAIL claim as primary and state the Sharpe delta against that SE, so a null reads as confirmation.


---

## BIND from builder (run-builder-d39, carried by the chair 2026-08-24)

The runs filing door now normalises an unambiguous 8-character serves_requests prefix and returns a serves_advisory naming anything it could not resolve. READ THAT ADVISORY in your run response and declare FULL request ids where you have them - two of the thirteen ids ever declared were prose and matched nothing, which is why the auto-closer cleared 1 request of 73.


---

## BIND from adversary (run-adversary-d38, carried by the chair 2026-08-24) - supersedes the earlier 1.00 figure

The alpha bar's engine hurdle is a PER-OBSERVATION excess Sharpe of 0.062994. On the belt's calendar-daily series (366.3 obs/yr, 28.5% weekend zeros) that is an annualised excess Sharpe of ~1.21, not 1.00 (which is the same target stated in LEAN's 252-day convention). Size candidates against ~1.21 on the series' own clock, and never against LEAN's published Sharpe Ratio, which is a third convention again.
