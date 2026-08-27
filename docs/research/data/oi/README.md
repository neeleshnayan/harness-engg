# Open-interest series (perpetual futures)

Written by `scripts/data/oi_recorder.py`. **Research data, not a fund fact** —
nothing here feeds NAV, the event log, or any decision path.

## What is in here

One `<SYMBOL>.jsonl` per symbol, append-only, one observation per line, keyed by
`timestamp` (epoch ms, UTC). A `<SYMBOL>.conflicts.jsonl` appears only if the
source ever restates a value it had already served for an instant already
stored — the stored value is kept and the disagreement is recorded rather than
absorbed.

Each row carries the API's fields verbatim (`sumOpenInterest`,
`sumOpenInterestValue`, `CMCCirculatingSupply`), plus `at` (when it happened),
`observed_at` (when we saw it), `period` (which grid served it) and `recorder`
(the version that wrote it). **Nothing is filtered on the way in** — not the
>20x single-day jump screen, not any outlier rule. A collector that drops what
looks wrong destroys the evidence that it was wrong; screens run at read time.

## Why it is collected daily, and why that is urgent

`fapi/futures/data/openInterestHist` serves a **30-day rolling window**.
Measured 2026-08-27: `period=1d&limit=500` returns 31 rows (2026-07-28 to
2026-08-27), and a `startTime` 60 days back is refused with
`{"code":-1130,"msg":"parameter 'startTime' is invalid."}`. **A day nobody polls
is a day of history destroyed, permanently.** This is the sole unblock for the
funding-crowding family of ideas.

The recorder defaults to the `1h` grid at `limit=500`, which reaches back
**20.8 days per run** — so a single run repairs up to twenty missed days. That
margin is the design: a daily job that only works if it runs every day is a
daily job that will eventually lose data. If a run is ever more than ~20 days
late, use `--period 1d` first to recover the full 30-day window, then resume
hourly.

## Reading it

```
python scripts/data/oi_recorder.py --verify      # first/last/points/gaps per symbol
python scripts/data/oi_recorder.py --selftest    # re-prove the settled-row claim
```

`--verify` exits 0 even when it finds gaps: a gap is a finding, not a crashed
job, and a check that exits non-zero on a known hole trains its reader to
ignore it. An empty store reports `complete: null`, never `true` — a series
with nothing in it is not a complete one.

## Two facts about the source that are not in its documentation

Both measured against the live API on 2026-08-27, both in the recorder's
docstring with their domains:

1. **`period` is a sampling grid, not an aggregation.** `sumOpenInterest` is an
   instantaneous level, and the 1h and 5m series carry identical values at
   identical timestamps (8 of 8 overlapping points; the 1d row at 00:00 equals
   both). That is why the store's key is `(symbol, timestamp)` and the period
   is provenance only.
2. **An unknown symbol returns `[]` at HTTP 200** — the same bytes as an
   outage. The recorder validates symbols against `fapi/v1/exchangeInfo` first,
   so an empty response for a valid symbol records as a refusal, never as
   "already up to date".
