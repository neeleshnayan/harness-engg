# PLATFORM FACTS — the course before the exam

**Created 2026-08-24 on the CEO's insight, verbatim: "we are discovering
things that could be easily sourced from the web... build what doesnt exist
and tune what we brought in — the linkedin courses analogy for employees but
for our ai team."**

This file is the COMMODITY-KNOWLEDGE layer: verified facts about
third-party platforms that this firm PAID discovery price for before anyone
checked the documentation. Every entry carries its source and its
verification (docs lie too — a fact enters only after a probe confirmed
it). Rules: append-only; a fact later falsified gets a dated CORRECTION
line, never an edit; anything about OUR OWN code, feed, or fills does NOT
belong here — that is discovery, and the seat memories are its record.

**The coursework rule (in builder.md and quant.md seat files): DOCS FIRST,
PROBE SECOND, for platform behavior — the doc supplies the hypothesis, the
probe verifies it, and the surviving fact lands here so the next seat reads
the course instead of re-taking the exam.**

## LEAN / QuantConnect

- **No margin interest by default**: `NullMarginInterestRateModel` is the
  `DefaultBrokerageModel` default — a backtest lends for free (QC docs,
  reality-modeling/margin-interest-rate). Verified: adversary D29 probeD
  (the gift measured at (1−1/G)·rf/sd). *Scar we paid: a full kill round.*
- **`Annual Standard Deviation` is calendar-clock × √252** — the equity
  series carries one point per calendar day; trading-day truth is ~1.204×
  higher. Verified: D23, 4/4 stored runs.
- **The Exposure chart** (`Base - Long Ratio`/`Base - Short Ratio`,
  `[unix_ts, ratio]`, short as magnitude, sampled daily at 00:00 ET) is
  published on every run with statistics. Verified: D32 census 108/108.
- **LEAN custom data defaults to always-open calendars** — 7-day bars are
  consumed without complaint. Verified: ETH weekend bars, Doc's dossier.
- **`Sharpe Ratio` embeds an internal risk-free rate** (implied 3.04–3.80%/yr
  on our stored runs) — never assume rf=0. Verified: D23 inversion.

## Alpaca

- **SIP (consolidated) data is 15-minute delayed on the free tier**; recent
  queries are refused with an explicit error; IEX feed is real-time.
  Verified: D35 probe (refused at 14min, served at 16).
- **`avg_price` on fill events is a CUMULATIVE running average**, on
  partials AND the terminal fill (a restatement, not a print). Verified:
  D35, order 5d495c88.
- **`StockQuotesRequest` normalises datetimes to NAIVE.** Verified: D35.
- **Alpaca supports crypto (ETH/USD) paper trading at 15–25 bps** — our
  connector's equity-only filters are OUR limitation, not theirs.
  Verified: Doc's dossier vs alpaca.py:156.
- **A one-sided quote arrives as price 0.0 × size 0** — a mid computed
  over a zero side is a fabricated price. Verified: D35 live (DBA).

## CoinGecko / crypto data

- **Daily points are stamped at D 00:00 UTC but carry D−1's close**; the
  live tail point overwrites the same key. Verified: Doc n=349 (169.9 bps
  same-date vs 4.4 shifted). *Scar we paid: a wrong-sign daily return.*
- **`/range` beyond ~365d and `days=400` now return HTTP 401** (free tier
  shrank). Verified: Doc, 2026-08-23.
- **Perp funding on the three USDT venues prints an identical +0.01%
  default** — three venues ≠ three independent observations. Verified: Doc.
- **Farside flows 403 the default user agent** — browser UA required.

## FRED / macro

- **The keyless `fredgraph.csv` endpoint SILENTLY IGNORES
  `vintage_date`/`revision_date`** — it always serves the fully revised
  series; point-in-time requires the (free) API key's
  `realtime_start`/`realtime_end`. Verified: Doc, identical pulls.
- **Postgres `rtrim(text)` trims SPACES only, not newlines** (PG docs).
  Verified: the compactor's first dry-run refusing everything.

## Python / tooling / OS

- **pydantic v2 lax `Optional[int]` coerces JSON `true`→1 and `"1"`→1**;
  `StrictInt` refuses both (pydantic docs, strict mode). Verified: D24.
- **fastapi keeps `Query` bounds in annotated-types metadata, not `.le`** —
  reading `.le` returns None; an assert against it is vacuous. Verified: D35.
- **Windows filesystems are case-insensitive: creating `Foo.tsx` OVERWRITES
  `foo.tsx`**, signaled only by ` M` vs `??` in git status. Verified: D31,
  a 453-line file clobbered and recovered.
- **A default argument is a copy taken at import** — `def f(x=CONST)`
  cannot be moved by a test patching CONST. Verified: D16/D21/D24.
- **`git checkout <rev> -- <subtree>` restores from the INDEX/rev and
  silently destroys uncommitted working-tree edits in that subtree.**
  Verified: D28's lint-baseline incident.
- **Node resolves junctions to realpaths** — a junctioned node_modules
  package looks for its deps under the target tree. Junction era over;
  `npm ci` in worktrees. Verified: D31.
- **Google News RSS is relevance-ordered, not chronological**, links are
  redirect-wrapped, descriptions are empty anchors. Verified: Doc's harvest.

## SEC EDGAR (data.sec.gov)

- **`/api/xbrl/companyfacts/CIK##########.json` is free, keyless, and serves
  the full XBRL statement history with a `filed` date on every fact** (META:
  458 us-gaap concepts; Q2-2026 revenue fact carries filed=2026-07-30) — a
  point-in-time fundamentals primary source. Requires a User-Agent header
  with contact info. Verified: chair probe 2026-08-24. *Validation of
  filed-vs-dissemination lag owed (the 57-day UPLOAD back-dating lesson).*

## FMP (financialmodelingprep.com)

- **The FREE tier serves `/stable/earnings-calendar` with FORWARD dates and
  estimates** (NVDA 2026-08-26 with epsEstimated, lastUpdated same-day)
  while price endpoints remain 402 Premium. The forward-calendar hole under
  announcement_premium closes at zero cost, pending validation. Verified:
  chair probe 2026-08-24.

## FRED (with API key)

- **The keyed API honors `realtime_start`/`realtime_end` correctly**: DFII10
  queried at vintage 2022-06-01 served late-May-2022 values with correct
  vintage windows — the point-in-time capability the keyless fredgraph.csv
  silently lacks. Key lives in .env only. Verified: chair probe 2026-08-24.

- **THE CLOCK CHECK (standing, four measured strikes in one week)**: LEAN's
  statistics are stated in a 252-trading-day convention while its emitted
  daily series carries ~366 calendar points/yr (weekend zeros included).
  ANY figure crossing the engine boundary must state its clock; the factor
  sqrt(366.3/252) = 1.2039 re-entered four separate reviews (D36 draws,
  D37 decomposition, D38 annualisation, the chair's own ruling text).
  Per-observation quantities are the only safe currency. Verified:
  run-adversary-d38, 339-run census.


## LEAN — live custom-data emission (added 2026-08-28, quant dispatch #8)

- **`PythonData` bars have NO period: `EndTime == Time`.** `BaseData.EndTime`
  is `get => Time; set => Time = value;` (`Common/Data/BaseData.cs:96-100`)
  and `PythonData` does not override it, so a daily custom bar ends at its
  own midnight. Verified in our own container: v1 smoke `c43e580e7997`
  first order `2021-05-03T04:00:00Z` filled at the 2021-05-03 close x 1.0005
  — bar date == slice date.
- **A live session's frontier starts at the session's own start time and
  discards every earlier bar.** `LiveCustomDataSubscriptionEnumeratorFactory`
  seeds `frontier = request.StartTimeLocal` (`:82`) and emits only
  `EndTime > frontier` (`:152`, `:186`). Consequence: a session started
  intraday receives NO bar that day; the first row that can clear the
  frontier is dated the NEXT day — which a same-day-updating feed publishes
  DURING the session as a running, unsettled quote. "Start the session after
  the close" does NOT mitigate this; the emission is the next morning
  regardless of start time. Verified: v1 live session `052650b749da` primed
  1,379 bars, `ready_on_first_bar=True`, and `on_data` was called zero
  times in 2h23m.
- **The remote file is re-read every 30 minutes** (`min(increment,
  minimumIntervalCheck)`, default `TimeSpan.FromMinutes(30)` at `:62`,
  applied `:92-96`), and **age filtering is disabled** — the
  `FastForwardEnumerator` is handed `Time.MaxTimeSpan` (`:130`), so no row
  is ever dropped for being old.
- **The mitigation that works (v2 pattern, `hyg_fast_flip_probe_v2`)**: in
  the reader, DROP rows dated >= today-UTC (the running row is not a close)
  and STAMP `bar.time = session + 1 day` so the bar's end lies after its
  publication. Backtest half verified in-container (bar 2021-05-04 delivered
  at slice 2021-05-05, job `f44922f7e7b0`); live half is a PREDICTION —
  one bar per calendar day within 30 min of 00:00 ET carrying the previous
  session's settled close; falsifier: a first `BAR ` log line naming the
  current day at a running price. Declared cost: the +1 stamp drops the
  final session of a backtest whose end is "today".
- **LEAN takes `TradingDaysPerYear` from the BROKERAGE MODEL** (prior fact,
  cross-referenced): the emission facts above are about DELIVERY; the
  annualisation clock is a separate trap and both bit HYG probes in the
  same week.
