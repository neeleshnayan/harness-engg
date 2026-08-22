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
