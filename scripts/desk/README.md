# `scripts/desk/` — run these instead of writing a query

Four vetted scripts over the fund's own record. **Run them; do not re-author
them.** Each one replaces a fold a seat was doing by hand, and each carries the
Postgres quirks in its docstring so nobody re-learns them at the cost of a
dozen tool calls.

```
./venv/Scripts/python.exe -X utf8 scripts/desk/day_events.py [YYYY-MM-DD]
./venv/Scripts/python.exe -X utf8 scripts/desk/friction.py   [--all]
./venv/Scripts/python.exe -X utf8 scripts/desk/run_stats.py
./venv/Scripts/python.exe -X utf8 scripts/desk/nav_day.py    [YYYY-MM-DD]
```

Every script takes `--json` for the raw body. Exit 0 on success, 2 on a usage
error. **`| head` returns head's exit code, not the script's** — redirect to a
file and read `$?` if the code matters.

| script | answers | source |
|---|---|---|
| `day_events.py` | one UTC day: events by type, decisions by actor and status, NAV open/close/strikes, fills with notional and venue split, mismatches, desk-request lifecycle, per-seat runs | spine, Postgres fallback |
| `friction.py` | every desk request folded forward, aged since filing, oldest first, with `approved_undispatched` as a first-class state | spine, Postgres fallback |
| `run_stats.py` | lifetime per-seat runs, tokens, tool uses, wall-clock, outcomes — **uncapped, with a truncation proof** | spine, Postgres fallback |
| `nav_day.py` | every NAV strike on a day with its cash/positions split and the change from the previous strike | Postgres only |

## Why they exist

Measured, not asserted. The secretary's end-of-day brief cost **80 tool uses,
26 minutes and 271k tokens**, most of it re-deriving aggregates from 965 raw
events. The CFO built the firm's first spend meter from a payload capped at 25
runs when lifetime was 49+, and was silently truncated. The validator
re-derived three findings already on the desk. Three seats computed the same
things three ways, and a hand-rolled fold is a fold nobody reviewed.

## Two rules these scripts obey and you should too

**A ROLLUP IS NEVER THE BOOK.** NAV folds from the event log through
`NavService`. Everything here is a derived reading. If a script and the fold
disagree, the fold wins and the disagreement is the finding.

**ABSENCE IS PRINTED AS ABSENCE.** `ABSENT`, `UNKNOWN` and `UPPER BOUND` appear
in this output on purpose. If you quote a number, quote the qualifier with it:

- `tokens: ABSENT` — the seat's runs carry no token count. Not zero.
- `median_wall: UNKNOWN` — nobody passed `dispatched_at` at record time.
- `outcome unrecorded=N` — the run stated no outcome. **Not `delivered`.**
  While any row is unrecorded, the failure count is a FLOOR.
- `approved_undispatched … <-- UPPER BOUND` — 14 of 24 `DeskDispatched` events
  carry no `request_id`, so a dispatched request can look undispatched.

## The quirk list

The authoritative copy is the docstring of `_common.py`. In brief:

- Event types are **PascalCase** (`OrderFilled`); the column is `type`, not
  `event_type`; `ts` is **TEXT**.
- Bound a day with `ts >= %s AND ts < %s` and full ISO instants.
- **A `%` in a LIKE literal beside a `%s` placeholder raises** `only
  '%s','%b','%t' are allowed`. Write `LIKE 'Desk%%'` or use `= ANY(%s)`.
- The runs token column is `tokens`, not `tokens_used`.
- `OrderFilled.avg_price` is a **string on 22 of 29 rows and a number on 7**.
- **20 of 29 fills carry no `venue` key.** Do not bucket them as paper.
- **Never fold `DeskDispatched` into a request table** — it creates a phantom
  row with a `None` id.
- There is **no `psql`**. Use `psycopg` from the ClarkHarness venv. Postgres is
  `127.0.0.1:5433`, database `krypton_fund`, DSN already in
  `app.fund.pgstore.dsn()`.

## Source of truth, printed on every run

The banner says `source=spine` or `source=postgres`. The spine is preferred —
same arithmetic the UI sees, no credentials. Postgres is the fallback because
the spine has been observed **alive and listening while serving nothing**
(desk request `d1d5beef`, 2026-08-22), and a seat with a deadline needs a path
that does not depend on it. A number's provenance is part of the number.

Underneath, both paths call the **same** functions in `app/fund/metrics.py`.
The scripts carry no second implementation of any fold: two copies of an
aggregate drift, and the drift is invisible because both copies look plausible.
