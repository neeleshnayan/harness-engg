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
