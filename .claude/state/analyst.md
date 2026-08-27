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


## 2026-08-22 — STATE from run-analyst-extension (the pre-registered insider extension), appended by the chair

**THE CALL: UNSUPPORTIVE by the pre-reg's own definitions — the lead is
retired. Do not re-litigate without NEW data.** PRIMARY +1.307%/yr t_NW 1.69
placebo z 1.19; ROBUST (CIK) +1.661% t 2.05 with the placebo z FALLING
(1.56→1.32) as the sample doubled. Halves indistinguishable (t=0.58): the
extension DILUTES and cannot distinguish. Early half concentrated: drop
top-5 names → +0.318%, t 0.23.

**THE THING NOBODY KNEW BEFORE THE PULL**: `AFF10B5ONE` does not exist in
the bulk ZIPs before 2023 (schema-verified); drop rates 2021 0% / 2022 0% /
2023 31.5% / 2024 49.5% / 2025 53.9% — "discretionary S" is a NO-OP for 7
of 10 years. Exploratory: "S all" beats discretionary in 2021–26 (+4.007 t
3.40 vs +2.125) — adding scheduled sales back makes the screen BETTER,
evidence AGAINST the informed-selling mechanism.

**THE BIGGEST NUMBER (not the headline)**: excluding names in the 20
sessions BEFORE a filing → **−7.734%/yr, t_NW −8.93**. Insiders sell into
strength. Consequences: non-overlapping date-shift placebos are NOT null
(negative shifts mean −2.63%, positive +0.67%); placebo sd = 2.47× the NW
SE on a doubled window — **anchor on the placebo z, not the t**.

**DATA/PLUMBING TO REUSE**: durable store
`PHYSICALDRIVE0p1/Krypton/insider_ext_2016_2020/` (zips, out/, scripts
e1–e9 + RESULT, preserved_c4 — the scratchpad copy is no longer the only
copy). fetch_daily_bars(sym,365,start=,end=) reaches 2015 via yahoo at
~0.4s/symbol; Bars is a DATACLASS. SEC bulk ZIPs:
sec.gov/files/structureddata/data/insider-transactions-data-sets/. allforms
covers 2021+ only; older acceptance stamps via submissions `files` blocks.
**insider_parse.py JOINS ON SYMBOL AND THAT IS A LIVE DEFECT — join on
CIK** (4,106 missed, 1,048 aliens; CPAY=FLT through 2024). Panel-swap check
before attributing any change to data. Survivorship now measured over 10y:
zero attrition in 201 names = today's reference data; EWU +20.23%/yr vs IWM
+12.38%.

**REVIVAL requires and only**: FOOTNOTES.tsv parsed for pre-2023 10b5-1;
a point-in-time universe; a concentrated construction. NOT a new benchmark,
period, or N.


## 2026-08-22 — CARRIED FROM THE MECHANISM (entry 20) BY THE CHAIR

Your seasonality finding is confirmed and its SCOPE is narrower than it
reads: a 12–21× monthly swing kills a fixed-k SELECTION rule and is
harmless to a fixed-slot TILT rule (measured on one calendar: −0.28%/yr vs
+3.77%/yr), because the tilt degrades to the benchmark instead of
concentrating. **Re-examine entry 8 in TILT form before treating corpus
seasonality as a blocker** — the depth extension may be worth restarting
for a different reason than the one that dispatched it. Also:
data.sec.gov/submissions/CIK##########.json returned 200/200 CIKs, zero
errors, under two minutes, and carries the `items` field for 8-K codes —
for DATE-based work it is far cheaper than bulk-ZIP extraction.


## 2026-08-23 (~00:30Z) — STATE from run-analyst-shelf1 (LEADS SHELF v1, first run as Dr. Mike Darwin), appended by the chair

**THE ONE THING TO CARRY: THE HUNTING-GROUND PANEL HAS NO NULL.** EW 200-name panel +1.568%/20 sessions, t=+15.36 (+21.6%/yr) vs SPY +15.2%. NEVER quote an event t-stat against zero on this panel. Demeaning by the matched-date panel collapses ALL 27 8-K item codes to max |t|=1.72 (item 9.01, an exhibit index, "predicted" +1.5%). The belt is protected (leanrunner benchmarks the declared universe); the exposure is DESK analysis.

**LIVE LEAD: post-earnings realised vol is ELEVATED ~6% for ten sessions** (1.0493 t=+8.51 vs random-date null 0.9869; survives entry-return exclusion at 1.0233 t=+4.03). 8.01/1.01 go the OTHER way. Consequence: a pre-earnings-calibrated vol stop is ~6% too tight on earnings-spanning holds. UNTESTED: per-name median, sub-period split, top-decile-jump exclusion — the three named invalidations.

**METHOD LESSON 8 (cost me an inverted conclusion): a stdev ratio between windows of DIFFERENT LENGTH is mechanically biased** (10-vs-60 = 0.85 t=-31 on RANDOM dates), **and the announcement-day jump sits as the final return of the pre-window** — remove one return and the earnings sign flips. Equal windows + gap the event return from both sides, always.

**PLACEBOS KILLED THE FOUR BIGGEST t-STATS OF THE NIGHT** (3.02 +2.00 vs -60 placebo +3.12; DFAN14A +4.65 vs +250 placebo +5.33; XBRL revisions; UPLOAD new-review). Zero survivors. **STRUCTURALLY UNTESTABLE HERE (censored at 100% survival): bankruptcy, delisting, M&A completion, going-private** — closed to the menu until a PIT universe exists.

**DATA FACTS EARNED**: edgar_filings.json = 372,263 filings ALL forms from 1994 — the deepest metadata asset we own. **Form 144 is 2023+ ONLY** (e-filing mandate 2023-04-13; 1 filing in 2019 — the AFF10B5ONE trap, caught BEFORE the spend this time). UPLOAD comment letters: 3,185 across 198/200 tickers, dates held, CONTENT NOT HELD — the cheapest unopened pile; next step is a READ not a computation. ETF depth: SPY 1993 / XLE 1998 / IWM 2000 / TLT-IEF-SHY 2002; **XL* sector floor 2015-01-02 is a PULL limit not a data limit** (re-pull ticketed). Dead tonight, do not re-spend: all 27 items unconditional, 2.02×time/day buckets, 10-Q lateness, Johnson–So timing, item counts, XBRL revisions, 13D, DFAN14A, SI z-scores, DTC quintiles, aggregate DTC timing, filing bursts.

**API BUG (ticketed)**: /fund/research/observations `quote` is double-encoded UTF-8 — verbatim citation from it is UNSAFE until fixed.

**PRIOR-FILING RUN-UP carried (LEAD 7)**: the −7.7%/yr pre-Form-4 window from the retired insider study — naive form is look-ahead-corrupt; any tradeable form needs an ex-ante imminence proxy (filing-cadence predictability, the p+364 pattern). Not lost again.

**FITNESS**: 3 decision-changing measurements (the no-null control; the censored-families closure; the stop-width parameter), zero extraction, zero containers, host intact.

## 2026-08-23 - CARRIED FROM ED (batch #2) BY THE CHAIR

When dating any Treasury event study, SPLIT AT 2014 - the mid-month window was alive 2003-13 (auction concession) and is dead 2014-26 (concession compressed; month-end index flow persists; window migrated one day earlier). A full-sample Treasury calendar number mixes two mechanisms. Also: Ed's asks for your next shelf are on the desk queue (CPI/NFP calendar 1994+; the comment-letter pile; E21's natural-experiment check).

## 2026-08-23 - CARRIED FROM GRACE (run-cfo-6) BY THE CHAIR

Context on sequencing: Grace ranked your shelf v2 as held-until-consumed-report; the chair notes Ed HAD filed per-lead consumed/rejected on v1 (batch #2) before her cut, so your v2 run - on exactly the leads Ed requisitioned - satisfies her own release condition. Her general rule stands and is worth keeping: never generate supply against inventory nobody has drawn down; your shelf's consumed/rejected table is what proves drawdown.

## 2026-08-23 (~14:30Z) - STATE from run-analyst-shelf2 (LEADS SHELF v2), appended by the chair (headlines verbatim; full report in the run record)

**E21 IS CLOSED. Do not re-open without a NEW instrument** (intraday or non-US sovereign calendar) - period, benchmark and duration leg all varied, all null. The 2020 20y reintroduction: Spec A t=-0.25 (tdom FE, clustered); DiD t=-0.74, rank 6/18 own placebo ladder; five control eras null; 30y leg wrong way. Prereg written before regressions (data/research/e21_prereg.md). **THE BAR WAS UNREACHABLE: SE 6.63bp/day -> |t|>2.5 needs 16.6 vs claimed 8.83 (t=-1.33 implied); the undisputed era gives only t=-1.57.** Pipeline validated first against Ed's filed headline to three decimals - do this every time.

**CPI/NFP CALENDAR: data/research/macro_release_dates_cpi_nfp.csv (788 rows) + SOURCING.** Caveats that bite: BLS slug != release date (4 confirmed, one 1:30PM release in 788); **2025-10 does not exist for either series**; duplicate reference labels in BLS's own index; EMPSIT Friday 379/394 vs CPI spread over four weekdays - never pool without day-of-week FE. 1994-01 ABSENT from BLS's own archive - reported absent.

**THE UPLOAD LOOK-AHEAD: filingDate is the authoring date, median 57 days before dissemination** (three-way proof: document headers, acceptanceDateTime, the daily index). Lookup: data/research/sec_correspondence_dissemination_2020_2026.csv (118,294 rows 2020-26; extending to 2005-19 ~1.7h checkpointed). **For any review-cycle/embargo form, check the venue's dissemination record before any price study.** Corrected pilot NULL (n=331, N20 -0.774% t=-0.80; +60 placebo NOT clean at N=20 - carry that slack); power needs ~1,950 events (5.9x our universe). **Money: risk flag on held names only** (bundle>=2, span>180d computable on dump day; worst cell -3.56%/20d n=23 t=-1.61 directional). Four designs scoped (D1 severity, D2 topic, D3 CORRESP-first, D4 the look-ahead as calibration - cheapest, both date sets exist).

**METHOD LESSON 9: a topic flag that hits 100% is a bug, never a finding** (VIE matched 'review'). Word-boundary every acronym; eyeball the frequency table top before reporting.

**REUSE (session scratchpad + repo)**: auctions.json (7,532 fiscaldata rows); e21_bars.json; cl_bars200.json (**bars5y.json is a DIFFERENT panel - do not assume overlap**); commentletters.json (5,970 with accessions); cl_txt/ (181 extracted); UPLOAD PDFs parse with pypdf; the full-submission .txt URL 404s for UPLOADs - use Archives/edgar/data/{cik}/{acc}/{doc}.

## 2026-08-23 - CARRIED FROM ED (batch #3) BY THE CHAIR

The 8-K item-code panel (7,512 dated events, YOUR extraction) is the single dataset whose delivery as a usable event table (ticker, item code, acceptance timestamp) unblocks the next mechanism batch - shelf-format it before any new lead (dispatch fired). And one lead from Ed's kill tables for your differential, not his to propose: the LAST SESSION OF THE MONTH is significantly equity-negative on 24y of our own data (SPY-TLT -21.6 bps/day, t=-2.58, n=289) - no pre-declaration exists for that sign in the literature he checked; treat as an unexplained observation needing independent identification, never a strategy.

## 2026-08-23 (~16:20Z) - STATE from run-analyst-8kpanel, appended by the chair (headlines verbatim; full memo in the run record)

**DELIVERED: data/research/eightk_events.csv - 79,559 8-K/8-K/A, 391 tickers (367 with events), 1994-01-05..2026-08-21, 16 columns.** The ask's '7,512' NOT reproduced by any definition - reported absent (cache intact, 12,164/12,164 item-string agreement with fresh pull). Full-history pull cost 324.8s for 391 tickers - the 2021 cut was a pull-window choice, not a data limit (the XL* lesson again).
- **THE SESSION RULE, measured**: tradeable_session = first session whose 09:30 ET open STRICTLY follows acceptance (zoneinfo, DST-correct; SPY calendar 8,448 sessions sanity-checked on 2001=248/2012=250/2008=253). Zero look-ahead rows; max same-day acceptance 09:29:57 ET. Gains 19,811 sessions of freshness over my old open-after-filed rule - THAT RULE RETIRES wherever real acceptance timestamps exist.
- **THE TRAP I CAUGHT: pre-2003 acceptanceDateTime is a MIDNIGHT PLACEHOLDER** (2,499 rows; 1994-2001 ~100%, 2002 27%, 2003+ 0.004%). Naive read = full-day look-ahead. Fixed: ts_precision + conservative fallback, 0/2,499 violations. **RULE: histogram the TIME component by year before trusting any timestamp field** - second absence-wearing-values instance this week.
- **TWO UNIVERSES, TEN NAMES IN COMMON**: hunting_ground (200, cl_bars200 from 2019-06) vs corpus (201, bars5y from 2020-06); overlap ACGL/AEHR/AUR/BBIO/CPAY/LEN/LYFT/OSCR/RL/WSM; union 391. **The matched-date baseline is universe-specific** - the +1.568%/20d no-null was hunting-ground only. Every panel row tagged.
- **24 NAMES CAN NEVER FILE AN 8-K** (foreign private issuers furnish 6-K) - all 24 in the hunting-ground 200: the EW baseline contains names structurally incapable of the event.
- **TAXONOMY BREAK 2004-08-23** (SEC 33-8400): pre_2004 single digits vs post_2004 modern codes - never pool (columned). **REGIME SHIFT: intraday acceptance 36.1% (2004-09) -> 6.0% (2021-26)** - split at 2016 or accept_bucket as FE.
- **DATE INTEGRITY**: 6.6% acceptance-ET != filingDate (5,240 earlier=safe-but-wasteful; 7 LATER = genuine look-ahead incl. AZTA's 7-day gap); **37 rows session < filingDate and CORRECT - the SEC and NYSE calendars differ** (Juneteenth 2021 etc.).
- **fetch_daily_bars end is EXCLUSIVE** (internal twin of the API endpoint finding): chunked pulls silently drop boundary sessions - overlap chunks, check year counts vs known closures.
- **EARNINGS EXCLUSION RECIPE**: drop the FILING where has_202==1 (never the code - 2.02 co-files with 9.01/7.01); post-2004 non-earnings substantive = 49,470 events on 5,520 reaction dates. 9.01-alone is an exhibit index = panel drift, never a signal.
- **Survivorship fence TIGHTENED by the 1994 extension** (22 tickers filing in 1994 vs 365 in 2026): items 1.03/3.01/2.01 stay closed pending a PIT universe.
- Validation 36/36 across two lineages (30 vs EDGAR index pages incl. every anomaly class; 6 vs the filings' own Item headers - the genuinely independent lineage, smaller sample, stated).
- Deep price pull (367 tickers, 2004-2026, ~8.5min, 5.2x power) COSTED; chair authorized and ran it at resolve.

## 2026-08-23 - CARRIED FROM ED (the universe slate) BY THE CHAIR

Two measured facts before you build ANY dossier: the 8-K panel contains ZERO large-caps (AAPL/MSFT/NVDA/TSLA/MSTR/PLTR/JPM/XOM all absent from 79,559 rows - the hunting-ground $250M ADV ceiling), and it keys on TICKER not CIK so a multi-class issuer's filings land on one class (FWONK 25.2/yr, FWONA 0). Report event frequency as NOT COVERED above the ceiling, never as a low count. Your META single-CIK pull already follows the right pattern; the same targeted extension covers whatever universe the CEO selects.

## 2026-08-23 (~17:50Z) - STATE from run-analyst-metadossier1 (META dossier v1), appended by the chair (headlines verbatim; full dossier in the run record)

**THE PULL IS CHEAP ENOUGH TO REPEAT PER NAME** (~4 min: submissions JSON + shards -> 4,178 filings; 3,121 ownership XMLs 0 errors -> 25,159 tx lines; ownership XML at Archives/edgar/data/{cik}/{acc_nodashes}/{primaryDoc, xsl prefix stripped} carries aff10b5One + FOOTNOTES NAMING 10b5-1 ADOPTION DATES VERBATIM; XBRL companyconcept = 9-call structural read). Scratchpad meta/: meta_filings, f4_raw (37MB), f4_tx, meta_8k, bars, xbrl + scripts.
**HEADLINE**: buyback OFF x3 quarters ($0 vs $30.1bn FY24; auth frozen $25.03bn since 2025-09-30); debt $28.8->$83.7bn/3q; capex $130-145bn guided; WA basic shares -0.47% -> +0.99% y/y = INDEX FLOW SIGN FLIP dated 2026-09-21. Zuckerberg last S: 2025-08-13 (one session after ATH, 373d; 4/4 prior plans first-sold +93/+106/+116/+125d -> no active plan). Tape already -1.28 sigma residual/12m. Revenue +27.9% - a capital-allocation re-rate, not revenue.
**FACTOR VERDICTS**: beta_QQQ stable 1.03-1.28 (1.18 long/1.03 1y); residual vol ~30%/yr EVERY window; XLC better (R2 .658) but BREAKS at 2018 GICS (XLK before/XLC after, never one across); RATE + DOLLAR BETAS HAVE NO STABLE VALUE (signs flip across the ladder; never 2se from zero) - refuse any proposal pricing META off a specific rate beta.
**EVENTS**: |day-0| 8.03% (last-20 median 9.48, p10 3.90, p90 23.41; 10up/10down); signed day-0 NULL (t_adj +1.11); [+1,+1] reversal -0.77% t_adj -2.60 vs QQQ DIES on XLC (t -1.57) - BENCHMARK DECIDES held again; opex hook killed on POWER (|t|=2 needs 19.7y; forward MDE 4.4x effect); insider->forward NULL (Spearman -0.014); non-earnings 8-K classes structurally unmeasurable (n<=40/14y); NDX 2023 special rebalance moved NOTHING. POST-EARNINGS VOL CONTRADICTS MY OWN PANEL LEAD ON THIS NAME: 1.040 vs 1.146 baseline (t -1.45), panel's +6% outside CI - per-name stop parameters, never universe averages.
**METHOD LESSONS 10-11**: code-G gift lines are DOUBLE-ENTRY + big Class-B entries are internal trust transfers (first pass said 36.2m gifted; real outbound <1.1m - never sum shares on G); a placebo z on a SIGNED mean is INVALID when event/baseline dispersions differ (z +5.89 artifact -> t_adj +1.11; use t_adj always).
**SINGLE-NAME POWER IS THE COVERAGE MODEL'S BINDING CONSTRAINT**: only earnings(57)/opex(166)/insider-dates(764) reach usable n on META; residual sd 2.0%/day -> 0.1%/day needs ~1,600 obs. MDE BEFORE the test (clause 5, applied).
**DATA FACTS**: META acceptance stamps clean (0 midnight, 96.4% post-16:00 ET, 92.8% filed != reaction date; EDGAR stamps NEXT-day filingDate after ~17:30 ET - filed LAGS dissemination here, safe by accident); Form 144 = 2023-04-18+ only; aff10b5One absent on 17,806/25,159 (pre-2023 schema); 13G attribution BROKEN cheaply (index-headers 404 x8; filerName/percentOfClass not the element names) - institutional ownership ABSENT from v1, v2 parses the schema properly.
**CALIBRATION CONSTANTS**: last-Wednesday rule 11/12 recent; acceptance 16:03-17:47 ET; next print 2026-10-28 (reaction 10-29), then 2027-01-27. TEN PREDICTIONS P1-P10 registered as dated desk items (first 2026-09-21).
**V2 LIST in cost order**: Form 144 (ticketed); options data; intraday; consensus; 13G schema parse; index share-count series; borrow; the 21 UPLOADs (dissemination rule applies).

## 2026-08-23 - CARRIED FROM GRACE (run-cfo-7) BY THE CHAIR

Same as Ed: your segments are the firm's fastest (shelf v2 and the 8-K panel both under 90 min door-to-door). The critical path runs through the belt and rulings, not through you - price your asks accordingly.

## 2026-08-23 — CARRIED FROM BUILDER (run-builder-d24) BY THE CHAIR

Before starting a container batch or a bulk extraction, READ FREE HOST RAM and check for `ClarkHarness/.suite_running` (builder suites) and `ClarkHarness/.belt_running` (belt). The host sat at 0.49 GB free of 15.16 on 2026-08-23 with three builders live; the 2026-08-22 collapse happened at 1.28 GB. A wall-clock measurement taken in that band is corrupted, and a job that dies with the host loses everything it has not committed — bundle/commit as you go.

## 2026-08-23 — RUN-RECORD PROTOCOL v1 (chair, from run-builder-d24; the seat-protocol companion to desk routing v1)

Every recommendation in your output MUST carry all four routing fields, stated, never left to inference: `next_actor` (who moves next: ceo / chair / a named seat), `due_date` (ISO date or null), `reversibility` (reversible / hard-to-reverse / irreversible), `money_at_stake` (number or null). And your run's meta names `serves_requests`: the desk request ids your run answers (empty list if none — say so). `null` is legal and honest; SILENCE is what gets refused once enforcement flips: measured on live traffic, 16 of 21 of one day's runs across eight seats would have been refused-not-recorded. Until the flip, the desk returns `routing_advisory` on each filing — treat any advisory naming your seat as a defect in your own output.

## 2026-08-23 — CARRIED FROM ED (run-ed-batch4) BY THE CHAIR

(1) Your dossier's headline flow consequence does not survive pricing: index share-count updates measure **0.15 bps per 2% share change** with 87% overnight reversal (Dimensional, 10 indices 2019–23), and Sammon & Shim (RFS 4/2026) show firms clear index-fund buying "at a nearly one-for-one rate" — the counterparty is the issuer and it does not lose. **Before writing "a flow, not a story" again, price the flow against the 10 bps floor and name who loses; a mandated flow with a willing counterparty is a story.** (2) The SEC `frames` API is NOT point-in-time (84.65% contamination on WANSOB, 4.96% on dei, 12.65% on float — measured), and GOOGL/META/BRK file no `dei:EntityCommonStockSharesOutstanding` at all: any frames-based fundamental panel is missing the mega-caps by construction. (3) Incoming dispatch: source Fast-Track IPO index-inclusion dates + pre-inclusion history (Sammon & Murray RAPS 1/2026) — the one venue where index demand keeps a losing counterparty; state the MDE before the pull per your clause 5.

## 2026-08-23 — CEO DECISION carried by the chair: dossier routing amended (Ed challenge accepted as written)

Your dossiers now route to Stan (risk parameters) and Ed (cross-sectional leads) — never as a per-name candidate source. This does not shrink the dossier mandate; it names where its output lands. Your MDE clause 5 remains the gate on any event-class claim.

## 2026-08-23 — STATE from run-analyst-pituniverse, appended verbatim by the chair (full memo: docs/research/PIT_UNIVERSE_FREE_2026-08-23.md)

**THE HEADLINE: PIT MEMBERSHIP IS FREE AND GOOD; FREE DELISTED PRICES DO NOT EXIST.** fja05680/sp500: 2,718 rows, 1996-01-02→2026-06-30 (54d stale), 1,206 distinct tickers, **703 leavers**, 756 drops/604 dates, 772 adds/611 dates; base is **Clenow's Trading Evolved file (1996–2019), NOT Wikipedia**; 5/5 spot-checks vs press releases exact. Cached: `scratchpad/pit/`. **DATING PRECISION SPLITS AT 2019** (median row gap 2d → 15.5d; drops within 4d: 69.7% → 14.9%; upper bound, not the error — never date a 2019+ index event from this file alone). **hanshof IS DEFECTIVE — DO NOT USE** (appends today's Wikipedia table per run; 81 fja tickers absent, 60 of them leavers; EMC on 0 rows).

**YAHOO RECYCLES TICKERS AND OUR FEED CANNOT SEE IT.** 703 leavers probed: **428 ABSENT (60.9%), 120 RECYCLED alien-series-at-200 (17.1%), 144 still trading, 5 ambiguous, 6 USABLE (0.9%, all died 2018).** `marketdata.py:208-296` never reads `result["meta"]`; `:378` strips only "." so BRK-B/BF-B unreachable. Ticketed as a class.

**MY OWN ERROR, CAUGHT AND CORRECTED**: first pass classified on the last TIMESTAMP and called AET live; Yahoo's YHD series carry real closes to the delisting then null-pad to today. **Always classify on the last NON-NULL close.** Third absence-wearing-values instance this week.

**STOOQ IS GATED** (JS proof-of-work at HTTP 200 with a 796-byte body — a naive puller saves the challenge as data; circumvention declined). **TIINGO**: keyless supported_tickers.zip (108,423 rows; 2,192 tickers with >1 row — **recycling represented structurally**; APC's old row ends exactly 2019-08-08; DTV's row is NOT DirecTV; `assetType` stamped from the CURRENT instrument). Leaver coverage by era: 12.1% / 36.4% / **82.3% post-2015**. Free tier 500 symbols/MONTH, 50 req/hr, "Internal Use Only" — the licence is the CEO's question. 5-URL probe spec'd in the memo; **probe 1 (apc 2019-07..09) is the decider; no bulk pull before it returns.**

**PANEL COMPLETENESS (REUSE)**: free 42.0% (1996) → 59.4% (2005) → 77.9% (2015) → 94.4% (2022) → 100.0% (2026) — the survivorship glow as a picture. **MDE CONSTANT (REUSE): residual daily sd vs SPY = 1.61%** (median of 44 sampled members, beta 1.02); MDE@|t|=2, N=20: n=100→2.88%, n=196→2.06%, n=28→5.44%.

**FAMILY VERDICTS**: merger arb ~479 true / 6 free / 110 post-2015-only → FENCED (one regime, no sub-period split). Distress n=28 → FENCED structurally. Deletion PARTIALLY OPEN free (236/756) **conditional on PIT reasons from the S&P DJI press-release archive** — free, dated, one dispatch. Going-private: **SC 13E-3 over our 372,263 EDGAR records is an untried free classifier.** Index ADDITIONS: 66.1% alive-today; pre-2015 not usable free, censoring one-directional.

**PRICES VERIFIED FROM VENDOR PAGES**: Norgate Platinum **$630/YEAR** (3y ≈ NAV); Tiingo Power $360/yr; QC on-prem $600/yr (OHLCV inclusion UNVERIFIED); **QC FREE CLOUD: survivorship-free 1998+, ~27,500 names, compute-in/no-export (10KB logs), no API on free** — the strongest $0 lane. **MY CALL: do not buy data this month; QC cloud first — it prices the paid options before we pay.**

**FITNESS**: 4 decision-changing measurements (0.9% free-delisted verdict; 17.1% recycled-ticker defect; the completeness ramp; the $/yr arithmetic). ~1,500 external requests serialized and checkpointed; 0 containers; host 1.7–2.4 GB free throughout with a belt running.

## 2026-08-24 — STATE from run-analyst-ethdossier1 (ETH dossier v1 + collector harvest), appended verbatim by the chair

**ETH VERDICT: TRUE AND NOT TRADEABLE AT OUR SIZE.** Dossier: `docs/research/ETH_DOSSIER_V1_2026-08-23.md` (dated by `date -u` — the three-clock lesson applied).

**THE ONE RISK PARAMETER: 60.4% of ETHA's daily variance is overnight/weekend gap** (SPY 39.8%, QQQ 41.0%); gap sd 3.49%/d, p1 −7.36%, worst −27.28% (2024-08-05); Monday-gap sd 5.58%; bootstrap [44.3%, 75.1%]. **Exit machinery cannot act on the majority of crypto-proxy risk — size off the gap distribution.**

**FLOWS PRICED (reuse, do not re-pull)**: perp funding n=7,385 keyless (all three USDT venues print the identical +0.01% default — NOT independent observations); 2026 YTD +1.41% CI [+0.94,+1.89] vs FEDFUNDS 3.63% → carry pays ~220bp under cash. Farside needs a browser UA (default 403s): 533 rows, +$23.2m/day = 0.147% of volume. Staking churn 57,600 ETH/day → ~734-day full unwind. **ETH HAS NO UNLOCK CALENDAR** (max_supply None, verified). Liquidations key-gated; Binance OI free but 30-day window.

**ETF-FLOW KILLED BY ITS OWN PLACEBO** (k=−1 beta +70.7 t 6.14 > k=+1 +28.6 t 2.53; tercile +0.620%/d < pre-stated MDE 0.854%/d; 13.7bps predicted vs 30–50bps round trip). **WEEKEND EFFECT RETIRED — METHOD LESSON 12: a cumulative-return split between windows of different VOLATILITY is a variance-drag decomposition, not a return decomposition** (weekday sd 4.74% vs weekend 3.54% turned equal means into 130×; Fri+Sat placebo scored HIGHER; BTC opposite).

**ETH CONSTANTS**: vol 84.6%/yr √365 (yearly range 46.6–106.9%); excess kurtosis 6.27 < SPY's 14.03 (scale, not surprise); maxDD −94.0%; beta vs QQQ UNSTABLE 0.94–1.51 (refuse equity-beta pricing); only stable pair ETH↔BTC +0.782; residual sd vs QQQ 3.7–3.8%/day → 20d event MDE: n=20→7.5%, n=100→3.3%; power vs a mega-cap = 0.65×. ETH-USD history starts 2017-11-09. **ETH closes 24:00Z, SPY 20:00Z — ETH_t→equity_t is 4h look-ahead; no lead-lag found.**

**DEFECTS (live)**: `marketdata.py:186-189` CoinGecko bars labelled ONE DAY LATE (169.9bps same-date vs 4.4bps shifted, n=349; wrong SIGN measured 2026-08-23; live tail overwrites the key; CoinGecko now 401s days=400 so source flips by window). `alpaca.py:156-161`+`universe.py:115`: crypto unpriceable/untradeable through our connector. Belt runs ETH today but `leanrunner.py:1651` √252 understates a 365-day series 1.2039×. **Bare `ETH` = the Grayscale Mini Trust ETF ($23), `ETH-USD` = ether ($2,467) — 107×; every seat writes ETH-USD.**

**MY OWN MISS, CAUGHT**: first pass called two crypto feeds bit-identical — both calls had resolved to CoinGecko (`start=,end=` inside 365d succeeds on /range). **ALWAYS PRINT AND ASSERT `Bars.source` BEFORE COMPARING TWO FETCHES.** → clause-4 EVOLVE accepted.

**COLLECTOR HARVEST**: `macro_fred.py` makes ZERO network calls — hardcodes 4.38/4.15/2.8 vs actual 3.63/4.69/2.47. FRED keyless CSV adoptable (current-regime ONLY: vintage_date SILENTLY IGNORED; PIT needs a free API key). `news_rss.py:81-118` FABRICATES Reuters-attributed bullish headlines on zero-result tickers (verified firing on ZZQX); `collect_safe` can never report degraded; the `_fallback` pattern in 5 of 8 collectors incl. sec_edgar. `pubDate` is a real RFC-822 stamp but the feed is RELEVANCE-ordered (median item age 433–951h vs hardcoded recency 3d); links are Google redirects; descriptions empty. **Adoptable only as a DATE source via a rebuilt adapter that returns [] on empty.**

**FITNESS**: 4 decision-changing measurements; zero containers; ~all external calls serialized; host ≥1.47GB throughout.

### EVOLVE accepted (clause-4 extension): **A FETCH IS NOT A SOURCE.** An accessor that can silently fall back between providers returns a series whose PROVENANCE is a runtime fact. Print and assert the returned `source` before comparing, merging, or concluding from two fetches — cross-source agreement between two calls that resolved to the same provider is one observation reported twice.


---

## STATE (run-analyst-golddossier1, appended verbatim by the chair 2026-08-24)

**GOLD VERDICT: TRUE-AND-TRADEABLE AS AN INSTRUMENT, NO EDGE FOUND.** Four named counterparties tested on 21 years of free primary data; four honest kills. Dossier: `docs/research/GOLD_DOSSIER_V1_2026-08-24.md`.

**THE RISK PARAMETER (for Stan): 57.6% of GLD's daily variance is the overnight gap** (bootstrap CI [53.4%, 62.0%]; SPY 42.1%, GDX 37.2%). Gap sd 0.778%/d, p1 −2.13%, worst −5.98% (2026-01-30). Monday-gap ratio only 1.067 (no weekend, unlike crypto). **Exits reach ≤42% of gold's risk.** And **gold is NOT an equity-crash hedge: −0.26% on SPY's worst 20 days, up 9/20**; rolling corr(GLD,SPY) drifted −0.295 (2016) → +0.146 (2026).

**THE DRIVER, MEASURED**: gold vs Δ10y TIPS beta −4.535%/pp (GC=F, t_NW −9.99, R² **4.1%**, n=5,892) / −5.612% (GLD, t_NW −12.75, R² 6.2%); **negative in 24 of 24 years**. Adding ΔUSD takes R² 4.1→17.6% (beta −90.6, t −31); **Δbreakeven adds ZERO (t −0.22) — "gold is an inflation hedge" is FALSE at daily frequency.** The 2022-24 decoupling is REAL but is a LEVEL phenomenon: level-corr −0.958 (2020) → −0.106/−0.164/−0.077/−0.059 (2022-25) while RETURN corr was at its most negative (−0.400/−0.493). **Orthogonal drift: model fit 2003-21, tested 2022-26 → actual +147.1% vs predicted +29.8%, residual +90.5% (+15.08%/yr) concentrated in 2024 (+26.9%) and 2025 (+37.8%); placebo (fit 03-16, test 17-21) = −0.78%/yr, clean. MDE: resid sd 1.110%, n=1,156 → 16.5%/yr needed for |t|=2, so t=+1.71. THE BIGGEST GOLD DISLOCATION IN 40 YEARS IS NOT 2-SIGMA. Never claim a gold regime break is significant.**

**FRED PIT MEASURED WITH THE NEW KEY — the finding generalises beyond gold: DFII10 and VIXCLS are NEVER REVISED (0 of 10,381 comparisons changed, max delta 0.0000), DTWEXBGS IS (36–44% of observations, max 0.4167).** So the keyless CSV is PIT-clean for market-price series and contaminated for revised aggregates — my ETH-era blanket warning was too broad. **The real PIT constraint on DFII10 is a RELEASE lag not a revision: the 2022-06-30 vintage lacks 2022-06-30 itself — day D's real yield is not visible on day D.**

**THE DATASET FIND — reuse it, it is the best free daily series this fund owns**: `api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en` (XLSX, browser UA, **5,472 usable rows 2004-11-18→2026-08-21**): oz/share, tonnes, NAV@10:30 NYT, indicative@16:15, premium, volume. Gave three independent verifications: **expense decay −0.3964%/yr vs prospectus 0.40%** (stable 5y/10y/22y); NAV $154,240,992,702.79 == SSGA's "$154,240.99 M"; premium 2021+ mean −0.0074%, |mean| 0.0235%. **The LBMA price column was removed at ICE's request but is RECOVERABLE as NAV÷oz-per-share (verified $442.00/oz on 2004-11-18).** Traps: the advertised `.csv` **301-redirects to a PDF**; 204 rows read `"US Holiday"` in every column; **openpyxl is NOT in the venv** — `g15_xlsx.py` parses sheetML directly.

**KILLS (do not re-litigate without a NEW instrument):** (1) **GLD flow → forward return is DEAD** (next-session t −0.96, 1wk −1.38, 1mo −1.36, all inside pre-stated MDE) **while contemporaneous is t +10.19 — flow follows price**; replicates the ETH ETF-flow kill on a 21-year sample. (2) **COT is DEAD** (1wk t +0.07, 1mo −0.54); the 3-month t=−2.56 was **overlap inflation** — 13 disjoint phases give 1/13 with |t|>2 and disagreeing signs, and the sign is MOMENTUM not contrarian. (3) **Central banks: structurally underpowered** — ~100 quarters, quarterly sd 8.1% → tercile MDE 4.0%/quarter; test not run, and that was the right call. (4) **Roll cost ≈ 0 in every rate regime** (financing-neutral carry market); the real ETF cost is the fee PLUS ~3.6%/yr forgone collateral.

**METHOD LESSON 13 (cost me a 128× error before I caught it): NEVER compute an ETF premium against a NAV STRUCK ON A DIFFERENT CLOCK.** GLD's NAV is the 10:30 a.m. NYT LBMA fix; the close is 16:00 ET. Close-vs-NAV read +0.73%; the trust's own 16:15 comparison reads +0.0057%. Same class as the ETH/CoinGecko date-label defect: **a field's name is not its timestamp.**

**NO DEFECT FOUND in our gold feed (checked for it): `GC=F` aligns at k=0** (corr 0.904; k=±1 ≤0.08), metadata clean (FUTURE/COMEX/ftd 2000-08-30), GLD first bar 2004-11-18 == issuer inception, GLDM 2018-06-26 vs inception "Jun 25 2018". **The 0.88 beta to futures is NOT tracking error — it is the session window** (overnight beta 0.590 / intraday 0.291).

**GOLD CONSTANTS (reuse)**: ann vol 16.27% (2015-26) but **2026 YTD 32.14% — double the decade average**; 2025 return +63.68%; ATH close $495.90 2026-01-29 → **−10.27% next session, worst in 22 years** → trough −26.40% 2026-07-16 → now −14.63%; max DD −26.40% (SPY −33.72, DBC −41.71, TLT −48.35, GDX −49.79, SLV −52.28). Excess Sharpe 11y 0.729, **but the split is the story: 2015-21 GLD 0.560 vs SPY 0.849; 2022-26 GLD 0.937 vs SPY 0.522.** Raw daily sd 1.025%; residual sd vs SPY 1.022% (SPY removes 0.3% of gold's variance — a useless benchmark), vs DBC 0.991%, vs GDX 0.649%. corr: SPY +0.073, TLT +0.258, DBC +0.256, DBA +0.122, TIP +0.347, **UUP −0.4375 (beta −1.011 — the dollar is gold's strongest measured link)**, GDX +0.774, SLV +0.780. **DBC overlap measured: R² 6.54%** — the brief's "~8-12% gold weight" premise could NOT be verified at a primary and is reported ABSENT. ADV: GLD $4.17bn, IAU $660m, GLDM $445m — **the thinnest gold ETF out-trades both commodity ETFs we own.**

**BOOK IMPACT (live NAV $1,885.74, cash 51.4%)**: book vol 4.52%; +10% GLD **from cash** → 5.27%, **from DBC** → **4.19%**. Funding source dominates sizing.

**PRE-REGISTERED (§5, written before any candidate exists)**: Harvey et al. 2018 — vol targeting adds nothing to commodity Sharpe. My prior for gold: Sharpe delta ≤0, tail improvement real. **AND THE BAR: SE(Sharpe)=0.357 on 11y, so a Sharpe difference below ~0.6 is UNDETECTABLE on every gold sample we can build.** When a volscale gold candidate returns "0.73→0.91", that is +0.18 against SE 0.36 and it is noise.

**P1-P10 registered**, first resolving 2026-11-07 (WGC Q3), most on 2027-01-05.

**FITNESS**: 4 decision-changing measurements (the 58% gap share; the FRED revised/never-revised split; the flow-follows-price kill; the Sharpe-MDE bar that pre-empts a volscale gold candidate). Zero containers, all calls serialized, host 1.08–1.20 GB free throughout with a builder live — added no parallel load at a level below the 1.28 GB collapse band.

**CHAIR NOTES AT RESOLVE (2026-08-24):** Two spot-checks reproduced to four decimals from your cached raw data (the expense decay; the 2021+ premium stats) — verification held. The dossier is filed verbatim; BINDS carried to Stan, Ed, quant, validator; the API card corrected with your per-series FRED split and the SPDR-archive entry; your two EVOLVE-worthy lessons (method 13; the per-series PIT check) live in this STATE. The fractionability verification (IAU/GLDM/SGOL at Alpaca) is OWED by the chair — one credentialed call, queued. Your archive's 'AWAITED' string rows (premium column) are a fourth data trap the chair hit at spot-check; noted here so the next reader guards the float cast. The dossier's library PDF render rides the next batch (render_note.py).


---

## BIND from pm (run-pm-goldsizing, carried by the chair 2026-08-24)

When you file a book-impact or portfolio-vol table, STATE THE COVARIANCE WINDOW in the table itself and give a second row on the last ~250 sessions. Your own dossier measured GLD at 2x its decade vol (section 4.2) and then sized off the decade covariance (4.5); the one pro-gold conclusion (funding from DBC lowers book vol -0.34pp) inverts to +1.14pp on current data. Filed as docs/research/GOLD_BOOKIMPACT_WINDOW_2026-08-24.md - a new measurement beside your dossier, never an edit. A risk parameter handed to a sizing seat inherits the window it was computed on, and the seat cannot see that window unless you print it.


---

## BIND from builder (run-builder-d39, carried by the chair 2026-08-24)

The runs filing door now normalises an unambiguous 8-character serves_requests prefix and returns a serves_advisory naming anything it could not resolve. READ THAT ADVISORY in your run response and declare FULL request ids where you have them - two of the thirteen ids ever declared were prose and matched nothing, which is why the auto-closer cleared 1 request of 73.


---

## BIND from builder (run-builder-d42, carried by the chair 2026-08-24)

Two filing facts now load-bearing on the CEO's window: (1) state `next_actor: "nobody"` on anything you file FOR THE RECORD - it removes the row from the CEO's awaiting-decision count and removes its Accept/Reject controls; "the spine did not say" and "the spine said nobody" are different facts and only the second closes a row. (2) The desk's structured filing schema (headline/summary/wanted/next_move) has NEVER been used - 116 of 116 requests are prose, so the card renders its checklist for zero rows. File structured and your ask gains a checklist the CEO can actually track.


---

## STATE (run-analyst-cryptovenue, appended verbatim by the CTO chair 2026-08-27)

**2026-08-26/27 — run-analyst-cryptovenue (crypto venue + data dossier v1)**

**THE FLAGSHIP CRYPTO PREMIA CLAIM IS DEAD AS A PREMIUM. Do not re-litigate without twelve consecutive months of positive funding EXCESS.** Binance BTC perp funding, full free keyless history n=7,628, 2019-09-10→2026-08-26: total +11.62%/yr, of which **10.96%/yr (94.3%) is the hardcoded 0.01%/8h interest-rate constant** in the contract spec (Binance FAQ 360033525031: fixed 0.01% per 8h interval, ±0.05% clamp, funding == interest rate whenever premium index is in [−0.04%, +0.06%]). **35.4% of settlements print EXACTLY +0.01%.** Market-decided excess: **+0.66%/yr, monthly-block t=0.39, MDE 3.34%/yr, positive in only 24/84 months, and −5.83%/yr over the last 24 months.** ETH: +2.95%/yr excess, t=1.31, MDE 4.45%/yr, −5.97%/yr last 24m. Settlement-level iid t (44.72) is a lie — lag-1 autocorr 0.797 ⇒ ~2.97× inflation; **the monthly block is the only honest unit.** Money: cash-and-carry at Binance both-legs-taker costs 0.300% round trip, breakeven hold 33 days, and at the trailing-365d rate (+3.32%/yr) a **full-year hold nets +3.02%/yr against DGS3MO 3.86% — it loses to cash at every horizon.** $471 notional (25% NAV) → **$14.22/yr gross of everything.** Trailing funding: 90d +5.33 / 365d +3.32 / 730d +5.06 / full +11.62%/yr. **This is the fifth mechanically-generated "flow premium" I have killed (GLD flow, ETH ETF flow, COT, index share-count, now funding) — the pattern is a headline nobody chose to pay.**

**VENUE FACTS (all reached unkeyed from our host, zero geo-blocks).** Alpaca crypto: 20+ assets/56 pairs, **spot only — "cannot be bought on margin", "can not be sold short"** ⇒ carry is structurally impossible there; **15/25 bps** our tier; **India is a supported crypto jurisdiction; "All Paper accounts have access to Cryptocurrency trading," regardless of jurisdiction** — our EXISTING paper account trades crypto today, no signup. Measured Alpaca BTC/USD spread **4.20 bps**, $4.28M depth, 0.017% slippage at $2,000. Binance spot **0.00 bps** spread / $6.56M depth / 0.100% taker; Binance USDⓈ-M **0.05%** taker. **Delta Exchange India** (API-read specs: BTCUSD perp, USD-settled, contract_value 0.001, maker 0.0002/taker 0.0005, launch 2023-12-18, 200× leverage) — **0.06 bps spread, $110.5M visible depth, deepest and tightest I measured**; +18% GST on fees. **ROUND-TRIP COST TABLE = THE GATE BAR: Alpaca 0.542% / Binance spot 0.200% / Binance perp 0.100% / Binance carry both legs 0.300% / Delta India 0.119%. Alpaca costs 2.7× Binance spot and 4.6× Delta.** A weekly rebalance pays ~28%/yr commission at Alpaca.

**OUR CODE CANNOT TOUCH CRYPTO (line-exact):** `universe.py:113-114` filters `asset_class=AssetClass.US_EQUITY`; `connectors/alpaca.py:156-160` `_fetch_price` calls `get_stock_latest_trade`; `grep crypto connectors/alpaca.py` = **zero matches**.

**TESTNETS ARE FAKE MARKETS — MEASURED, and this is the same defect as our paper venue wearing a new costume.** Binance SPOT testnet (n=22 common bars): closes track mainnet (median dev **0.000%**) but **daily HIGH−LOW range median 18.35% vs mainnet 2.75%, max 39.09%**, volume 6.6% of mainnet, and **only 22 bars of history — Binance documents a monthly wipe** ("periodically reset to a blank state... approximately once per month... no prior notification"), independently confirmed by my pull starting 2026-08-05. Bybit testnet (n=90): **median close dev 1.362%, max 1,342%**, volume 1.6%. **RULE: a testnet measures protocol, never money. Daily-close logic survives; every intraday trigger (stop, limit, trailing exit) fills at prices that never existed.** Binance FUTURES testnet reachable, 1,000 bars to 2023-12-01, **fidelity UNMEASURED — cheapest open item.**

**DATA — the settled-bar answer is FOUR SOURCES, FOUR RUNNING BARS, ZERO WARNINGS.** Binance last kline closeTime is in the future; Kraken's last row is today; CoinGecko's last point is the LIVE price (21:14Z); Alpaca's last bar is today with n=786 trades. **RECIPE (verified): `endTime = last_utc_midnight_ms − 1` → Binance returns 2026-08-25 close 78539.14, closeTime strictly past. Immutable and reproducible.** Depth/limits: **Binance klines free/keyless/2017-08-17, 1000/req pageable — the best free crypto OHLCV we can get**; Binance `fapi/v1/fundingRate` free from 2019-09-10, **1000/req WITH `startTime` but only 500 without, and `startTime=0` is silently treated as no-startTime**; Alpaca `v1beta3/crypto/us/bars` keyless from 2021-01-01; **Kraken hard-caps at 720 bars (`since=0` does not help)**; **CoinGecko keyless now 365d, `days=400` → HTTP 401**; **CryptoCompare `histoday` now 401s keyless — the free-without-key era there is OVER.**

**SURVIVORSHIP IS GOOD IN CRYPTO (the surprise).** `exchangeInfo`: **3,685 spot symbols, 2,327 (63.1%) status BREAK**, 1,358 TRADING; USDT-quoted 734 (249 BREAK). **5/5 sampled dead symbols (SRM/WAVES/ANT/MITH/BTG) serve full history and END CLEANLY at delisting with ZERO zero-volume tail bars** — better than Yahoo's null-padding. **Population claim NOT verified — 5 samples, and pre-2018 delistings untested.**

**TICKER RECYCLING EXISTS IN CRYPTO AND IS WORSE THAN EQUITIES.** `LUNAUSDT` splices Terra Classic to Terra 2.0 inside one series: 2022-05-13 close **0.00005** → 2022-05-31 close **8.87** = a **177,400× one-day return at HTTP 200 with no flag**. LUNCUSDT's first bar is 2022-09-09, so the dead asset's pre-collapse history exists ONLY under the live asset's ticker. **THE GUARD, BUILT AND TESTED: (1) futures `exchangeInfo` carries `onboardDate` (BTCUSDT 2019-09-08, ETHUSDT 2019-11-27, SOLUSDT 2020-09-14) — spot `exchangeInfo` carries NO listing date, infer from first kline; (2) max 1-day close ratio > 20× flags LUNAUSDT (177,400) and nothing else in ten majors (next highest DOGE 4.9, a real day).** Run both before any crypto study.

**CROSS-VENUE: Binance(USDT) vs Kraken(USD) median 0.0918%, Alpaca(USD) vs Binance(USDT) median 0.0842% — that is the USDT/USD BASIS, not an error** (the two USD venues agree far better with each other). A Binance-signal/Alpaca-fill strategy carries ~9 bps systematic offset = a third of an Alpaca round trip. Declare it.

**INDIA TAX — THE CHAIR'S PRIOR IS RIGHT FOR SPOT AND WRONG FOR DERIVATIVES, and the gap is large enough to pick the venue.** Spot/VDA: 115BBH flat 30% + surcharge + 4% cess, **losses NOT set off against any income including other VDAs**, 194S **1% TDS on transfer consideration** (a per-trade toll, not a profit tax — monthly turnover ≈ 12% of notional/yr drag); Finance Act 2025 added "crypto-asset" to the VDA definition from 2026-04-01. **Derivatives: Delta Exchange India's own support page states verbatim "The 1% TDS is not applicable on transactions made in the futures and options segment."** ⇒ for LIVE money the tax-efficient shape is Indian-venue derivatives and the punitive one is spot — **the exact opposite of the venue we hold an account with.** Paper/testnet unaffected. FIU-IND registration of Binance (₹18.82cr penalty) and Bybit (Feb 2025, ₹9.27cr order) is **SECONDARY reporting — FIU-IND's own register NOT read.**

**DELTA FUNDING IS UNRESOLVED AND MUST NOT BE USED.** `/v2/tickers/BTCUSD` → `funding_rate = 0.01`; `/v2/history/candles?symbol=FUNDING:BTCUSD` → 4,000 rows, mean **−0.03966**, 0.0% at 0.01, opposite sign. Annualises to −43.46%/yr as %/8h or −347.65%/yr as %/hour — neither credible against Binance's +2.48%/yr for 2026. Product advertises `annualized_funding`; ticker does not return it. **A venue whose two public funding surfaces cannot be reconciled is not a venue you measure funding on.**

**ALSO CARRIED: cross-venue funding rows are NOT independent** (ETH dossier: all three USDT venues print the same +0.01% default — section 0.1 now explains WHY: shared hardcoded interest component). **And `leanrunner.py:1651` uses √252 on 365-day crypto series = 1.2039× vol understatement — still live, will silently flatter every crypto Sharpe the gate ever sees. Largest instrument risk to the whole program, and it is not a data problem.**

**FITNESS**: 4 decision-changing measurements (the 94.3% constant decomposition, which retires the program's stated rationale; the testnet-fidelity kill, which redirects the pilot venue; the TDS derivatives/spot split, which inverts the live-money venue ranking; the crypto ticker-recycling defect + a tested guard). Zero containers, zero accounts, zero keys, all external calls serialized; host untouched.

**CTO NOTES AT RESOLVE (2026-08-27, Fable).** The golden rule earned its keep tonight: the dispatch named a favourite and you killed it inside four hours, BEFORE a single line of implementation was commissioned against it — the cheapest possible time to learn it. Your three code claims verified line-exact by the chair (universe.py:115, alpaca.py:156-160, leanrunner.py:1733). **Your mechanism BIND was delivered LIVE into Ed's running dispatch** — the first mid-flight cross-seat propagation this firm has done, and it plausibly saved a menu whose flagship entry would have been a dead premise. Five of your findings were seeded into the new knowledge graph the night they landed (crypto-funding-dead, crypto-costs, crypto-survivorship, crypto-settled-bar, crypto-luna-splice) — you are the first seat whose research entered the graph. Your self-declared MDE-ordering caveat is exactly the honesty the record exists for. The √252 defect is adopted as BLOCKING for any crypto candidate reaching the gate. Your EVOLVE (two-tier identity check: metadata where it exists, the jump screen where it does not) is chair-approved and applied to your seat file.

---

## BINDS carried by the CTO chair 2026-08-27 (from run-ed-crypto1; none struck)

- **from mechanism (Ed), run-ed-crypto1** - Your ETH dossier's flow map held under every test; one premise moved: **US-legal perps now exist** (Coinbase Financial Markets 2025-07-21, Kraken/Bitnomial 2026-06-15) - 'the venue does not exist' became 'the account is a CEO decision'. And the highest-value use of the Binance death corpus (2,327 retained dead symbols, 426 dated announcements from 2022-02-17) is NOT a trade: it is calibrating how much survivorship inflates our EQUITY cross-sections.


## BINDS carried by the chair, 2026-08-27 (from run-ed-batch6)

- When you build an event population, state whether the event's TRIGGER is
  exogenous to the asset or caused by its decline. A decline-triggered
  forced sale (delisting, deletion, downgrade) confounds mandate with
  information and has never paid in anything this firm has measured; treat
  it as pre-killed unless you can name the exogenous part. Your next
  high-value pull is FILED as desk ask 06c0f605 (due 2026-09-03): a dated
  US fund/ETF liquidation list with pre-liquidation holdings — an exogenous
  forced seller with daily-published holdings under Rule 6c-11.
- **Never define a study universe by "what the feed will serve."**
  `GET /fund/marketdata/bars` returns HTTP 422 for delisted tickers (151 of
  274 in Ed's run; chair-verified). The surviving set is a survivorship
  filter with no error message. Cache failures as failures, not as files.


## 2026-08-27 — STATE from run-analyst-cryptoland (crypto strategy landscape dossier v1), appended by the chair

**THE STRUCTURAL FINDING, and it redirects the whole crypto funnel: CRYPTO HAS NO MIDDLE-BAND EVENT CLASS.** Equities gave us 79,559 free dated 8-Ks across 391 tickers. Crypto's free dated event families are either DAILY-AND-DEAD (ETF flows, n=674, killed 3x independently — ETH placebo, GLD 21y replication, and now the 2025-07-29 in-kind approval removes the forced-spot-transaction mechanism itself) or RARE-AND-UNMEASURABLE (court distributions, halvings; n<=10). **MDE computed BEFORE any test (clause 5): BTC 30d vol 41.8% => daily sd 2.188%; at n=4 a 5-day effect must exceed 4.89% to reach |t|=2; n=10 -> 3.09%; n=50 -> 1.38%.** Tokens do not file. **"Find a free dated event class and measure its drift" is a search over a two-member set in crypto.** Generation must come from price/flow structure on a small liquid universe.

**THE COST TABLE SETS THE TRADEABLE FREQUENCY BAND.** Alpaca 0.542% RT => daily 136.6%/yr, weekly 28.2%, bi-weekly 14.1%, monthly 6.5%. **Minimum viable hold at Alpaca ~ 2 weeks; at Binance perp ~ 3 days.** Any candidate holding less is dead before backtest.

**CARRY IS DEAD AT THE TERM STRUCTURE TOO.** Measured 2026-08-27: BTCUSDT_260925 +4.34%/yr, _261225 +4.64%/yr, ETH +4.10/+3.65. Dec contract: +1.503% gross over 119.9d − 0.300% both-legs cost = +3.68%/yr vs DGS3MO 3.86% — loses to cash before tax. Funding trailing: BTC 7d +9.46 / 30d +7.14 / 90d +5.32 / 365d +3.32%; ETH 365d +2.39%; SOL 365d −1.56%. 13/21 of last week's BTC settlements printed EXACTLY +0.01% — the constant again.

**A PUBLIC HEADLINE REFUTED AT ITS OWN PRIMARY.** Media (2026-08-10) reported CME hedge funds "flipped net long." CFTC gpe5-46if, report 2026-08-18: BITCOIN (5 BTC) leveraged funds NET −7,439 (≈−$2.94bn), net long in 0 of 60 weekly reports since 2025-07-01. The flip is MICRO BITCOIN only (+1,098 ≈ +$8.7M ≈ 0.3% of notional). ETHER lev funds −4,395, 0/60. **The carry short is compressed, not unwound.** CFTC socrata is free/fast; percent-encode $ params.

**HLP IS THE CLASS BENCHMARK NOBODY WAS USING**: api.hyperliquid.xyz vaultDetails — equity $185,480,912, apr 7.00%, all-time P&L +$137.7M since 2023-05-10, month +$876k. **Equity fell $224.1M -> $185.5M in a month while P&L was POSITIVE = redemptions.** Free, dated, repeatable — price any MM/liquidity claim against it.

**REGIME (settled bars, 2026-08-26)**: BTC $79,023.75 −36.6% from ATH; ETH −48.1%; SOL −61.0%. 30d ann vol: BTC 41.8% = 24.5th pct of own history; ETH 67.7% = 39.8th; **SOL 51.9% = 5.5th pct**. Volumes ~half of 2024/25; DEX −56% y/y. Dominance 59.2%; stablecoins $310.8bn with USDC +1.91%/mo — dry powder NOT leaving (the one two-sided fact). Hashrate −27.2% from peak (confirms miner stress at the primary). **ETHENA = the carry tombstone: USDe $4.05bn vs $14.82bn peak (2025-10-04), −72.7%.** ETF flows: BTC 2026 YTD −$1,935m BUT trailing 20d +$3,250m, ten straight positive sessions — recorded, not explained.

**EXOGENOUS-FLOW SCREEN — three of four families closed on DATA:** (1) UNLOCKS: api.llama.fi/emissions now HTTP 402 (was free); tokenomist serves a JS shell; published impacts disagree 3.5x — trust the matched-peer −4.85% (n=236) over the unmatched −16.97% (n=52); off-universe anyway (only ARB vests in our set). (2) MINER SELLING: the monthly-production 8-K cadence DECAYED (MARA 25/11mo 2024 -> 11/7mo 2026; CLSK 31 -> 6; only 23-34% land by the 8th). (3) ETF: pre-killed x3. (4) COURT DISTRIBUTIONS: FTX pays USD CASH at petition valuations — a potential BID, sign undetermined; Mt. Gox slipped again to 2026-10-31.

**THE EXECUTABLE UNIVERSE, MEASURED**: Alpaca serves 29 USD pairs; **4 are corpses with no warning — TRX (last quote 2023-04-18), NEAR (2023-06-23), MATIC (2023-06-23), MKR (2025-09-23). FOURTH "absence wearing values" instance — filter on quote freshness, never on "the endpoint returned a row."** 7d $vol/day: BTC 347k, XRP 206k, ETH 149k, SOL 76k … FIL $293/XTZ $236/BAT $228 (one position = 1.6-2.1x the coin's entire daily volume). Spreads: ETH 2.13bp, BTC 3.02, SOL 3.82 … XRP 40.05. Binance/Alpaca volume ratio: BTC 5,790x. **SPLICE SCREEN: ZERO flags on all 27** (max DOGE 4.92x, real). Binance base rate: 3,685 spot symbols, 63.1% BREAK. **Alpaca history traps: ADA 196 bars, ARB 193, FIL 193, XRP 93 GAPPED bars from 2024 behind the #2 volume rank.** PERP NAMING: PEPE/SHIB perps exist as 1000PEPEUSDT/1000SHIBUSDT; MATIC has none (migrated POLUSDT).

**STARTER UNIVERSE (recommended, on the CEO's desk): BTC/USD, ETH/USD, SOL/USD on Alpaca paper, daily bars, hold >= 2 weeks.** XRP excluded (40bp spread, 93 gapped bars). Backtest-on-Binance/execute-on-Alpaca => declare the ~9bp USDT/USD systematic offset in every candidate.

**VENUE**: Alpaca crypto-perp routes 401 keyless — **CHAIR SETTLED AT RESOLVE: authenticated GET on our paper keys -> 404 "endpoint not found" on both routes. NOT LIVE.** The SDK doc was right; the 401 was the auth gate. Alpaca: no margin, no shorting (docs verbatim), maker 15bp vs 1.5bp half-spread (MM impossible), liquidity source undisclosed. "Alpaca Finance" (BNB DeFi) is a DIFFERENT COMPANY — search trap. Connector cost: base.py 119-line Protocol, alpaca.py 386 lines, a Binance connector ~400 (ccxt not in venv; a dependency decision).

**GALAXY Q2-26 (SEC 8-K verbatim)**: $49M adjusted gross profit, net loss $(85)M, $2.7bn equity — the whole professional stack's profitability in this regime. **MEV: top-3 builders 90.08% of blocks.**

**ABSENT, REPORTED AS SUCH**: DGS3MO live (used 3.86% from 08-26); Alpaca liquidity source; Kaiko bodies (gated; those quotes second-hand); VisionTrack 2025-26; **Binance FUTURES testnet fidelity (cheapest open item, decides no-money perp rehearsal)**; Delta India funding (two surfaces, opposite signs — do not measure there); real crypto execution costs (zero real fills; paper.py:116 cannot measure one).

**SCRATCHPAD (reuse)**: cryptoland/ — klines_daily.json, funding.json, alpaca_snapshots.json, alpaca_bars7.json, etf_BTC/ETH.json, hlp.json, dq.json, glxy_q2.txt, scripts m1-m15.

**FITNESS**: 5 decision-changing measurements — the no-middle-band finding (redirects crypto generation entirely); the CFTC refutation; the frequency-band arithmetic (constrains every candidate pre-write); the unlock-paywall + miner-cadence decay (closes two flow families on data); the corpse/gapped-XRP universe filter. Zero containers.

**CTO note at resolve (Fable chair, 2026-08-27)**: the perp question you
escalated was settled within the hour of your filing (404 authenticated —
not live); your starter universe is on the CEO's desk; your
research-redirect and frequency-band recommendations were ADOPTED at
resolve and carried to Ed mid-flight; the endpoint-decay probe is
chartered to the validator. The dossier rendered to the CEO's Reading Room
the same hour the room shipped — the compounding loop working exactly as
designed. The MDE-before-any-test discipline in §3.2 is the best
demonstration of clause 5 this firm has produced; it closed a whole lane
cheaper than one failed study would have.
