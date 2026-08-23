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
