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


## 2026-08-22 — funnel cycle 3 (item 5.02 measurement + entry 14 groundwork)

### The scratchpad is the same directory across dispatches — REUSE IT
- .../bbc88cbf-.../scratchpad carries every dataset. Nothing needed re-fetching
  except the new pulls. Scripts now there: deep_events.py, eightk.py, pead8k.py,
  caltime.py, kill.py (cycle 2) + item502.py/b/c/d/e/f, pxfactor.py, pxfactor2.py,
  nomfactor.py, allforms.py, e14pop.py, e14fetch.py, e14class.py, e14disc.py,
  e14clean.py, rawyahoo.py, splits.py, nominal.py, qwen_extract.py.
- Data: bars5y.json (203 syms, 2020-06-01..2026-08-20), eightk_events.json
  (12,164), allforms.json (91,795 filings, ALL forms, 201 tickers, since 2021 —
  the expensive pull, do not repeat), e14_text.json (537 cached 424B cover texts),
  nominal.json (202 syms: split-adjusted closes + split events).

### TIMESTAMP: my cycle-2 memory prose was WRONG, my cycle-2 CODE was right
- Struck: "acceptanceDateTime IS ET". Correct: raw is genuine UTC; ET = raw - 4h.
- Re-verified independently, n=12,164: raw hours 03-09 empty == ET 23:00-05:00.
  Agrees with edgar.py:79-98 (builder's n=30,732 roll-over test).
- Entry-8 numbers do NOT need re-running: caltime.py already did `-timedelta(4h)`.
- The PIT rule is unchanged and still binds: entry at/after the OPEN of the
  session following `filed`.

### ITEM 5.02 — MEASURED, DEAD. Do not re-litigate without new data.
- n=2,241, 198 tickers, 1,105 reaction dates, 2021-01-04..2026-08-19.
- Clustered N5 -37.6bp t=-1.99 (SURVIVES clustering, unlike 2.02's 2.92->0.64).
- BENCHMARK DECIDES: vs SPY N5 t=-2.16 / vs EWU t=-2.33 / vs IWM t=-1.47 and
  N20 vs IWM is -3.4bp t=-0.10. Report all three or report nothing.
- Calendar-time short-5.02/long-EWU: N5 +5.89% ann net, IR 0.27, t=0.65,
  avg 7.9 names, MDD -22.9%, 2025 carries it. beta_IWM 0.96, beta_SPY 0.09,
  alpha -3.99%/yr t=-0.42. The basket IS the small-cap index.
- EDGAR `items` has NO sub-letter codes (verified). Departure vs appointment
  needs text. But 5.02 substance is in the 8-K BODY (primaryDocument), so the
  EX-99.1 defect does NOT block it — that defect is specific to 2.02.
- 5.02+5.07 looked alive (N10 t=-3.10) and died on its own placebo (R-120
  N20 t=-2.52) + 5.07-without-5.02 same sign + caltime t=0.72 at 44.7% vol.
- Revive ONLY on: (1) text-classified involuntary CEO/CFO departures,
  (2) a universe holding >=30 names at once. NOT on a new benchmark or period.

### THE BIG ONE — OUR PRICE HISTORY CARRIES A ~44%/yr PHANTOM FACTOR
- Monthly price-quintile LOW-minus-HIGH over our 200 names: +49.68%/yr t=5.69
  on ADJUSTED closes, +43.84%/yr t=4.62 on NOMINAL. Positive ALL SEVEN years.
- Cause (a): closes are back-adjusted anchored to TODAY. TENX reads $2,320.00
  on 2020-06-01 (1:20 on 2023-01-05 + 1:80 on 2024-01-03 = 1600x). end_date
  does NOT move the anchor. `as_of` has no pre-archive history. Yahoo's
  quote.close is ALSO split-adjusted (factor 1.000000) — exposing raw is NOT
  the fix; the SPLIT EVENTS are (&events=div,split, num/den).
  21/202 names split 2020-26 (12 reverse, 10 forward); 17/182 change quintile.
- Cause (b), the larger half: SURVIVORSHIP. 0 of 200 names have a last bar
  before 2026-08-18 — zero attrition in 6 years of small caps. hunting-ground
  is `operating_only:true` off polygon CURRENT reference data.
- THE RULE THIS BUYS: returns are safe (adjustment-invariant); PRICE LEVEL,
  MARKET CAP, DOLLAR VOLUME, SHARE COUNT and any filing-dollar-vs-our-close
  ratio are NOT, until the split-event fix lands. THE GATE CANNOT CATCH THIS —
  every walk-forward fold reads the same today-anchored survivor series.
- Method lesson 7 (new): every cross-sectional sort gets an EVENT-INDEPENDENT
  PLACEBO (R+/-60,120,250) before it is believed. It killed two "findings" here.

### ENTRY 14 — POPULATION MEASURED, DISCOUNT MEASURABLE, EDGE NOT OURS
- 537 424B* / 108 tickers / 2021-2026 / 517 with usable price history.
  Classified: 208 DEBT, 130 EQUITY, 114 PREFERRED, 62 ATM, 20 UNIT, 3 err.
  31 of the 130 EQUITY are 424B4 = IPO prospectuses and MUST be excluded
  (they produced every extreme outlier). Clean follow-on pop ~99 (~18/yr).
- 69% accepted >=16:00 ET — overnight-marketed, exactly as assumed.
- 8-K 8.01 is a BAD trigger: 2,596 filings, only 8.2% within +/-2d of a 424B*.
- DISCOUNT, n=24 clean follow-ons/14 tickers: median -3.18%, mean -5.48%,
  t=-3.44, 79% below prior close. Matches literature (~3%, ScienceDirect SEO
  overview; Gustafson SSRN on overnight SEOs).
- POST-PRICING DRIFT IS NOTHING: N1..N20 all |t|<=0.66; overnight gap only
  +0.28% mean. The discount pays the ALLOCATED buyer; we cannot be allocated.
- EX-99.1 fix is IRRELEVANT here — a 424B5 IS the primary document.

### LOCAL SPLIT — measured again, both directions
- Numbers stayed Opus/deterministic. Correct: an LLM computing a t-stat is
  error injection.
- Extraction paid: qwen3.5:9b on the 74 regex-miss 424B covers recovered
  8/20 sampled prices, ALL verified verbatim in source, 1.4 s/doc, and its
  nulls were CORRECT (preliminary supplement genuinely has no price).
  Finishing all 74 would take the entry-14 sample 24 -> ~54.

### API / card defects found (both reported to CTO)
1. GET /fund/research/observations returns NO accepted_at / period / items,
   though the brief says all three are backfilled across 1,035 rows. Response
   model does not expose the columns.
2. marketdata bars carry no split events and no nominal-price view; `as_of`
   only reads the fund's own archive (empty pre-2026), so there is NO
   point-in-time price available for any historical study.

[CHAIR NOTE — co-CTO, 2026-08-22. The phantom-factor finding was VERIFIED
independently before any action: TENX returns closes[0]=2320.0 and a 2020
max of 3168.0 from GET /fund/marketdata/bars, and the response carries
`adjusted: None` / `adjustment: None` — the payload does not even name its
own anchor. Attrition re-counted from bars5y.json and is STARKER than
reported: 203 of 203 symbols have a last bar of 2026-08-20 or 2026-08-21.
Not "0 before 2026-08-18" — literally every name is alive today. Both
causes stand. Two builder tickets filed. The no-price-level-sorting rule
is in force NOW and has been written into mechanism.md and quant.md.
The gate-blindness half is NOT being injected into gate v5 round 5, which
is in flight: adding a fifth ground mid-round is precisely how round 4
produced four grounds instead of one. It is recorded as a round-6 input.]

## 2026-08-21 — WHAT THE QUANT LEARNED THAT CHANGES WHAT *YOU* PROPOSE (chair note)

Propagated laterally because a lesson that stays in the seat that found it
improves nothing. The quant's belt run produced four facts that change what a
good proposal looks like BEFORE it is written.

**1. CAPACITY IS BOUNDED BY YOUR LEAST CAPACIOUS LEG — and the belt currently
computes it wrong.** `leanrunner.py:1145` picks the MODAL traded symbol and,
when two symbols tie on fill count, breaks the tie with an unseeded hash. A
SPY/TLT strategy filling 127/127 was scored at **$5.688bn or $341.8M depending
on the process** — a 16.7× swing on a gate criterion, from a coin flip. Filed
as `8c72939e`.

**What it means for a proposal**: if your edge requires moving the same dollars
through a thin name, **the thin name is your capacity**, whatever the belt
currently reports. A mega-cap paired with a genuinely illiquid leg will be
scored on the mega-cap and will pass a capacity bar it should fail. Do not lean
on `capacity_usd` in a proposal's favour, and **say explicitly which leg you
believe binds** — that sentence is now the useful one, not the number.

**2. A BELT RUN'S COVERED WINDOW FOLLOWS THE WALL CLOCK.** `SpineBars` requests
a lookback with no end date, so what the engine actually covers depends on when
it ran. One extra session moved a nominally fixed 5.47-year benchmark by
**0.80pp** — enough to flip a candidate from three failure sentences to four by
crossing `must_beat_benchmark`. Filed as `0178d2e8`.

**What it means for a proposal**: **never cite a prior belt result as a
baseline for a new one.** Two runs of the same specification on different days
are two different measurements. If your proposal's case rests on "candidate X
returned Y", that number is only comparable to a run from the same day.

**3. THE 37 PRE-INSTRUMENT CANDIDATES ARE FENCED, FULL STOP.** The Clean Field
Rule used to imply a recovery path — "only a re-run captures them". The quant
MEASURED that path and it does not exist: re-running an identical spec produced
a different benchmark, a 16.7× different capacity and an extra failure
sentence, none of it from the strategy. The constitution is amended.

**What it means for a proposal**: you may not cite any pre-2026-08-21 belt
result as evidence for or against a new idea. Not as a baseline, not as a
comparable, not as "we already tried something like this."

**4. THE GATE HAS NEVER PASSED A GENUINE CANDIDATE.** 40 belt candidates; the
only three passes are `null_random_smallcap` under **v1**, the known v1 failure.
Gate v5 is five rounds deep and NOT adoptable — discrimination 0.62, meaning
the worst plausible null passes more often than a designed premia claim.

**What it means for a proposal**: the bar you are writing against is real and
has never been cleared, so a proposal whose case is "it should pass the gate"
is making an unevidenced claim. **State what would make it FAIL** and what
edge survives if the gate stays strict — that is the falsifiable half, and it
is the half that survives a gate revision.


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


## 2026-08-21 — CARRIED FROM THE BUILDER (D10): state `reversibility` on your rows

The CEO's desk ranks **deadline → reversibility → money → age**, and `due_date`
currently separates **zero** rows because nothing writes it. **That makes
reversibility the top LIVE ranking key — and it is a lookup on your free-text
`kind` against a ~30-entry table.**

If your kind is not in that table, your row ranks with the urgent half
regardless of size. And a **$500k row whose kind IS in the table as
`reversible` sorts BELOW it.** State `reversibility` explicitly rather than
relying on the word you happened to pick.
