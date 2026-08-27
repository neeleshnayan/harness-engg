"""Record perpetual-futures OPEN INTEREST before Binance throws it away.

WHY THIS EXISTS, and why it is urgent rather than merely useful:
``fapi/futures/data/openInterestHist`` serves a **30-day rolling window**
(MEASURED 2026-08-27: ``period=1d&limit=500`` returns 31 rows, 2026-07-28 to
2026-08-27, and ``startTime`` 60 days back is refused with
``{"code":-1130,"msg":"parameter 'startTime' is invalid."}``; the docs say
"Only the data of the latest 1 month is available"). **Every day nobody polls
it destroys a day of history that no amount of money buys back later.** It is
the sole unblock for the funding-crowding family of ideas, and it is free and
keyless (IP weight 0, 1000 requests / 5 minutes).

WHAT THIS IS NOT. This is RESEARCH data, not a fund fact. It never touches the
event log, the NAV fold, or any decision path. It writes JSONL under
``docs/research/data/oi/`` — the same shape as the NBBO capture beside it —
because a research collector that can reach the fund's ledger is a research
collector that can corrupt it.

FOUR THINGS THIS FILE KNOWS THAT THE DOCS DO NOT, each measured against the
live API on 2026-08-27:

1. **``period`` is a SAMPLING GRID, not an aggregation.** ``sumOpenInterest``
   is an instantaneous level, and the 1h and 5m series carry IDENTICAL values at
   identical timestamps (8 of 8 overlapping points; the 1d row at 00:00 equals
   both). That is why the store's key is ``(symbol, timestamp)`` with the period
   recorded only as provenance: two periods observing the same instant are the
   same observation, not two.
2. **A row appears to be SETTLED the moment it is published**, because it is a
   snapshot rather than a bucket. Three measurements, with their domains:
   re-polling the same 5m window 16 minutes later reproduced **97 of 97**
   overlapping rows byte-identical; a 5-minute watch compared **28 distinct
   points across 30 polls** with **0 mutations**; and ``--selftest`` (3 polls,
   24 points) reproduces the check on demand. **The honest limit of that
   evidence**: the youngest row any of those probes saw was already 73.7s old,
   so nothing here proves the first seconds of a row's life. That is why
   ``--settle-margin`` exists and defaults to **0** — the default is the
   measurement, and the knob is the doubt. This is the only source of ours that
   has ever escaped the settled-bar trap, so the escape is re-checkable rather
   than baked in.
3. **An UNKNOWN SYMBOL RETURNS ``[]`` AT HTTP 200.** A typo and a genuine
   outage are the same bytes. So symbols are validated against
   ``fapi/v1/exchangeInfo`` and an empty response for a VALID symbol is recorded
   as SERVED NOTHING — a refusal — never as "already up to date".
4. **The default text encoding on this host is cp1252 and it crashes on the
   API's own bytes.** Every read and write here states ``encoding="utf-8"``.

RAW IN, SCREENS AT READ TIME. Nothing is filtered on the way in — not the
>20x single-day jump screen, not an outlier rule. A collector that drops what
looks wrong destroys the evidence that it was wrong. The screens belong to
whoever reads the series.

    python scripts/data/oi_recorder.py                     # record, default symbols
    python scripts/data/oi_recorder.py --symbols BTCUSDT
    python scripts/data/oi_recorder.py --verify            # coverage, first/last/gaps
    python scripts/data/oi_recorder.py --dry-run           # fetch and report, write nothing
    python scripts/data/oi_recorder.py --selftest          # re-prove the settled-row claim
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

BASE = "https://fapi.binance.com"
OI_PATH = "/futures/data/openInterestHist"
EXCHANGE_INFO_PATH = "/fapi/v1/exchangeInfo"

#: The three the funding-crowding family needs first. Deliberately short: this
#: runs unattended and an unwatched job that quietly grows its own workload is
#: how a free endpoint becomes a rate-limit incident.
DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")

#: Hourly. MEASURED trade-off, not a preference: at ``limit=500`` the 1h grid
#: reaches back 20.8 days, so a single run repairs up to twenty missed days,
#: against 1.7 days for the 5m grid. The 1d grid reaches 30 but carries one
#: point a day. Twenty days of self-repair at twenty-four points a day is the
#: best cell in that table for a job that will sometimes not run.
DEFAULT_PERIOD = "1h"
#: The documented maximum (Binance: "max: 500"). Verified: 600 is accepted and
#: returns the same window, so the limit is not what bounds us — the 30-day
#: retention is.
MAX_LIMIT = 500

PERIOD_SECONDS = {
    "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200,
    "4h": 14400, "6h": 21600, "12h": 43200, "1d": 86400,
}

#: The fields the API serves. Recorded verbatim; nothing here is derived, so a
#: later correction to our own reading never has to be untangled from the data.
API_FIELDS = ("symbol", "sumOpenInterest", "sumOpenInterestValue",
              "CMCCirculatingSupply", "timestamp")

RECORDER_VERSION = "v1"

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
DEFAULT_STORE = os.path.join(REPO_ROOT, "docs", "research", "data", "oi")


# ----------------------------------------------------------------- transport

def _get(path: str, params: dict[str, Any], timeout: float = 20.0) -> Any:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}{path}?{query}" if query else f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "krypton-oi/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def tradable_symbols() -> Optional[set[str]]:
    """Every symbol the venue admits, or None meaning WE COULD NOT ASK.

    None is a third state and every caller keeps it distinct from an empty set.
    "The venue says this symbol does not exist" and "we could not reach the
    venue" lead to opposite actions, and an empty-array response cannot tell
    them apart on its own.
    """
    try:
        body = _get(EXCHANGE_INFO_PATH, {})
        rows = body.get("symbols") or []
    except Exception:  # noqa: BLE001
        return None
    return {r["symbol"] for r in rows if r.get("symbol")}


def fetch(symbol: str, period: str, limit: int) -> list[dict[str, Any]]:
    """Raw rows, oldest first. Raises on any transport or API-level failure."""
    body = _get(OI_PATH, {"symbol": symbol, "period": period,
                          "limit": min(int(limit), MAX_LIMIT)})
    if isinstance(body, dict):
        # The API reports its own errors as a 200 with a code/msg object.
        raise RuntimeError(f"binance refused: {body}")
    return list(body)


# --------------------------------------------------------------- pure fold

def normalise(row: dict[str, Any], period: str,
              observed_at: str) -> Optional[dict[str, Any]]:
    """One API row -> one stored row, or None if it is not usable.

    ``observed_at`` is when WE saw it, which is not when it happened; both are
    stored, because a series whose rows cannot say when they were collected
    cannot later answer "was this backfilled or watched live".
    """
    try:
        ts = int(row["timestamp"])
    except (KeyError, TypeError, ValueError):
        return None
    out = {"timestamp": ts,
           "at": datetime.fromtimestamp(ts / 1000.0, timezone.utc).isoformat()}
    for field in API_FIELDS:
        if field == "timestamp":
            continue
        if field in row:
            out[field] = row[field]
    out["period"] = period
    out["observed_at"] = observed_at
    out["recorder"] = RECORDER_VERSION
    return out


#: Fields whose disagreement between two observations of the same instant is a
#: CONFLICT. ``period`` and ``observed_at`` differ legitimately — the same
#: instant seen through a different grid, or seen again later.
VALUE_FIELDS = ("sumOpenInterest", "sumOpenInterestValue",
                "CMCCirculatingSupply")


def merge(existing: Iterable[dict[str, Any]],
          incoming: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold new rows into old ones. Idempotent per ``timestamp``.

    Returns ``new`` (to append), ``duplicates`` (already held, identical) and
    ``conflicts`` (already held, DIFFERENT value). A conflict is never merged
    and never silently dropped: the store keeps the first observation and the
    disagreement is reported and written to a sidecar, because a source that
    restates a settled number is a fact about the source that a research series
    must not quietly absorb.
    """
    held: dict[int, dict[str, Any]] = {}
    for row in existing:
        ts = row.get("timestamp")
        if isinstance(ts, int):
            held[ts] = row
    new: list[dict[str, Any]] = []
    duplicates = 0
    conflicts: list[dict[str, Any]] = []
    for row in incoming:
        ts = row.get("timestamp")
        if not isinstance(ts, int):
            continue
        prior = held.get(ts)
        if prior is None:
            # ``held`` is updated here, so a SECOND row for this instant inside
            # the same response falls through to the comparison below and is
            # counted as a duplicate (or a conflict) rather than appended
            # twice. This used to carry a separate ``seen_this_run`` set as
            # well; mutation proved it could never change an outcome, so it is
            # gone. One structure deciding one thing.
            new.append(row)
            held[ts] = row
            continue
        if all(prior.get(f) == row.get(f) for f in VALUE_FIELDS):
            duplicates += 1
        else:
            conflicts.append({
                "timestamp": ts, "at": row.get("at"),
                "held": {f: prior.get(f) for f in VALUE_FIELDS},
                "served": {f: row.get(f) for f in VALUE_FIELDS},
                "held_observed_at": prior.get("observed_at"),
                "served_observed_at": row.get("observed_at"),
            })
    return {"new": new, "duplicates": duplicates, "conflicts": conflicts}


def coverage(rows: list[dict[str, Any]], period: str) -> dict[str, Any]:
    """First, last, count and every hole in the sampling grid.

    A gap is REPORTED, never inferred away. The expected step is the period, so
    any interval longer than one step is a run of missing points and is listed
    with how many are missing.

    ``complete`` IS THREE-VALUED AND ``pairs_compared`` IS WHY. Completeness is
    a statement about the intervals BETWEEN points, so a series of one point has
    made no comparison at all and a series of none has made no comparison at
    all — and "no gaps found over zero comparisons" is the shape of every
    vacuous pass this firm has shipped. Both cases return ``complete: None``
    with the domain beside it, never ``True``.
    """
    stamps = sorted({r["timestamp"] for r in rows
                     if isinstance(r.get("timestamp"), int)})
    step_ms = PERIOD_SECONDS.get(period, 0) * 1000
    pairs = max(0, len(stamps) - 1)
    if not stamps or pairs == 0:
        return {"rows": len(rows), "points": len(stamps),
                "first": (datetime.fromtimestamp(stamps[0] / 1000, timezone.utc)
                          .isoformat() if stamps else None),
                "last": (datetime.fromtimestamp(stamps[-1] / 1000, timezone.utc)
                         .isoformat() if stamps else None),
                "period": period, "expected_step_seconds": step_ms // 1000,
                "gaps": [], "missing_points": None, "complete": None,
                "pairs_compared": pairs,
                "note": (f"{len(stamps)} point(s) stored, so {pairs} interval(s) "
                         f"were compared - nothing here can be complete or "
                         f"incomplete")}
    gaps = []
    missing = 0
    if step_ms:
        for a, b in zip(stamps, stamps[1:]):
            if b - a > step_ms:
                n = (b - a) // step_ms - 1
                missing += int(n)
                gaps.append({
                    "after": datetime.fromtimestamp(a / 1000, timezone.utc).isoformat(),
                    "before": datetime.fromtimestamp(b / 1000, timezone.utc).isoformat(),
                    "missing_points": int(n),
                    "hours": round((b - a) / 3_600_000.0, 3),
                })
    return {
        "rows": len(rows),
        "points": len(stamps),
        "first": datetime.fromtimestamp(stamps[0] / 1000, timezone.utc).isoformat(),
        "last": datetime.fromtimestamp(stamps[-1] / 1000, timezone.utc).isoformat(),
        "period": period,
        "expected_step_seconds": step_ms // 1000 if step_ms else None,
        "gaps": gaps,
        "missing_points": missing if step_ms else None,
        "complete": (not gaps) if step_ms else None,
        "pairs_compared": pairs,
        "note": (f"no gaps across {pairs} interval(s) in the sampling grid"
                 if step_ms and not gaps else
                 f"{len(gaps)} gap(s), {missing} point(s) missing across "
                 f"{pairs} interval(s)" if step_ms
                 else f"period {period!r} has no declared step, so gaps cannot "
                      f"be counted"),
    }


def settled(rows: list[dict[str, Any]], *, now_ms: int,
            margin_seconds: float) -> tuple[list[dict[str, Any]], int]:
    """Drop rows younger than ``margin_seconds``. Returns (kept, dropped).

    MEASURED: these rows do not need it — an open-interest row is a snapshot of
    a level at an instant, not a bucket that fills, and re-polling reproduces it
    exactly. The knob exists anyway because the settled-bar trap has cost this
    firm real money elsewhere, and a claim that a source escaped it should be
    re-checkable rather than baked in. Default 0 = keep everything, which is the
    measurement, not an oversight.
    """
    if margin_seconds <= 0:
        return list(rows), 0
    cutoff = now_ms - int(margin_seconds * 1000)
    kept = [r for r in rows if r.get("timestamp", 0) <= cutoff]
    return kept, len(rows) - len(kept)


# ------------------------------------------------------------------ storage

def store_path(root: str, symbol: str) -> str:
    return os.path.join(root, f"{symbol}.jsonl")


def conflict_path(root: str, symbol: str) -> str:
    return os.path.join(root, f"{symbol}.conflicts.jsonl")


def read_jsonl(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # A corrupt line is NOT skipped silently: it is surfaced as a
                # marker so the caller's own count of held points is honest
                # about what it could not read.
                out.append({"_unreadable": line[:120]})
    return out


def append_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


# -------------------------------------------------------------------- record

def record_symbol(symbol: str, *, root: str, period: str, limit: int,
                  margin_seconds: float, known: Optional[set[str]],
                  dry_run: bool) -> dict[str, Any]:
    observed_at = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {"symbol": symbol, "period": period,
                              "observed_at": observed_at}
    if known is not None and symbol not in known:
        result["state"] = "unknown_symbol"
        result["note"] = (f"{symbol} is not in the venue's tradable set; the "
                          f"endpoint would answer [] and that is a typo, not "
                          f"an outage")
        return result
    try:
        raw = fetch(symbol, period, limit)
    except Exception as e:  # noqa: BLE001
        result["state"] = "unreadable"
        result["note"] = f"{type(e).__name__}: {e}"
        return result

    if not raw:
        # Distinguishing this from "nothing new" is the whole point of asking
        # exchangeInfo first.
        result["state"] = ("served_nothing" if known is not None
                           else "served_nothing_symbol_unverified")
        result["note"] = (f"the endpoint served zero rows for {symbol}. "
                          f"An unknown symbol answers identically, and the "
                          f"symbol list was "
                          + ("checked" if known is not None else "UNREADABLE")
                          + " this run")
        return result

    normalised = [n for n in (normalise(r, period, observed_at) for r in raw)
                  if n is not None]
    result["served"] = len(raw)
    result["unusable"] = len(raw) - len(normalised)
    kept, dropped = settled(
        normalised, now_ms=int(time.time() * 1000),
        margin_seconds=margin_seconds)
    result["withheld_unsettled"] = dropped

    path = store_path(root, symbol)
    existing = read_jsonl(path)
    result["held_before"] = sum(1 for r in existing if "_unreadable" not in r)
    result["unreadable_lines"] = sum(1 for r in existing if "_unreadable" in r)
    folded = merge(existing, kept)
    result["appended"] = len(folded["new"])
    result["duplicates"] = folded["duplicates"]
    result["conflicts"] = len(folded["conflicts"])
    result["state"] = "recorded"
    if not dry_run:
        if folded["new"]:
            append_jsonl(path, folded["new"])
        if folded["conflicts"]:
            append_jsonl(conflict_path(root, symbol), [
                {**c, "detected_at": observed_at} for c in folded["conflicts"]])
    else:
        result["state"] = "dry_run"
    if folded["conflicts"]:
        result["note"] = (f"{len(folded['conflicts'])} point(s) came back with "
                          f"a DIFFERENT value than the one already stored; the "
                          f"stored value is kept and the disagreement is in "
                          f"{os.path.basename(conflict_path(root, symbol))}")
    return result


# -------------------------------------------------------------------- verify

def verify_symbol(symbol: str, *, root: str, period: str) -> dict[str, Any]:
    path = store_path(root, symbol)
    if not os.path.exists(path):
        return {"symbol": symbol, "state": "absent",
                "note": f"no store at {path} - nothing has ever been recorded"}
    rows = read_jsonl(path)
    unreadable = sum(1 for r in rows if "_unreadable" in r)
    good = [r for r in rows if "_unreadable" not in r]
    out = {"symbol": symbol, "state": "present",
           "unreadable_lines": unreadable,
           **coverage(good, period)}
    conflicts = read_jsonl(conflict_path(root, symbol))
    out["conflicts_recorded"] = len(conflicts)
    return out


# ------------------------------------------------------------------ selftest

def selftest(symbol: str = "BTCUSDT", period: str = "5m",
             waits: int = 3, gap_seconds: float = 20.0) -> dict[str, Any]:
    """Re-prove the settled-row claim against the live API.

    Polls the same window ``waits`` times and reports how many rows CHANGED,
    with the domain — how many were compared. A zero over zero comparisons is
    not evidence, so both numbers are printed.
    """
    seen: dict[int, tuple] = {}
    mutated = 0
    polls = 0
    for i in range(max(2, waits)):
        if i:
            time.sleep(gap_seconds)
        try:
            rows = fetch(symbol, period, 24)
        except Exception as e:  # noqa: BLE001
            return {"state": "unreadable", "note": f"{type(e).__name__}: {e}"}
        polls += 1
        for r in rows:
            key = int(r["timestamp"])
            value = tuple(r.get(f) for f in VALUE_FIELDS)
            if key in seen and seen[key] != value:
                mutated += 1
            seen[key] = value
    return {"state": "ran", "polls": polls, "points_compared": len(seen),
            "mutated": mutated,
            "note": (f"{mutated} of {len(seen)} points changed across {polls} "
                     f"polls of {symbol} {period}"
                     + (" - the settled-row claim HOLDS" if not mutated
                        else " - the settled-row claim is FALSIFIED; set "
                             "--settle-margin"))}


# ---------------------------------------------------------------------- main

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    ap.add_argument("--period", default=DEFAULT_PERIOD,
                    choices=sorted(PERIOD_SECONDS))
    ap.add_argument("--limit", type=int, default=MAX_LIMIT)
    ap.add_argument("--root", default=DEFAULT_STORE)
    ap.add_argument("--settle-margin", type=float, default=0.0,
                    help="drop rows younger than this many seconds (measured "
                         "unnecessary for this endpoint; kept re-checkable)")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args(argv)

    if args.selftest:
        out = selftest()
        print(json.dumps(out, indent=2) if args.json else out["note"])
        return 0 if out.get("state") == "ran" and not out.get("mutated") else 1

    if args.verify:
        results = [verify_symbol(s, root=args.root, period=args.period)
                   for s in args.symbols]
        if args.json:
            print(json.dumps({"verify": results}, indent=2))
        else:
            for r in results:
                print(f"{r['symbol']:10s} {r['state']}")
                if r["state"] != "present":
                    print(f"           {r['note']}")
                    continue
                print(f"           points {r['points']}  "
                      f"{r['first']} -> {r['last']}")
                print(f"           {r['note']}"
                      + (f"  (unreadable lines: {r['unreadable_lines']})"
                         if r["unreadable_lines"] else ""))
                for g in r["gaps"][:20]:
                    print(f"             GAP {g['after']} -> {g['before']}  "
                          f"{g['missing_points']} missing ({g['hours']}h)")
                if len(r["gaps"]) > 20:
                    print(f"             ... {len(r['gaps']) - 20} more gaps")
                if r["conflicts_recorded"]:
                    print(f"           CONFLICTS recorded: "
                          f"{r['conflicts_recorded']}")
        # A gap is a finding, not an error: exit 0 so a scheduled --verify does
        # not read as a crashed job. The report is the output.
        return 0

    known = tradable_symbols()
    results = [record_symbol(s, root=args.root, period=args.period,
                             limit=args.limit,
                             margin_seconds=args.settle_margin,
                             known=known, dry_run=args.dry_run)
               for s in args.symbols]
    payload = {"recorder": RECORDER_VERSION,
               "symbol_list_readable": known is not None,
               "results": results}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if known is None:
            print("NOTE: the venue's symbol list was UNREADABLE this run, so "
                  "an empty response cannot be told from a bad symbol")
        for r in results:
            line = f"{r['symbol']:10s} {r['state']}"
            if r["state"] in ("recorded", "dry_run"):
                line += (f"  served {r['served']}  appended {r['appended']}  "
                         f"dup {r['duplicates']}  conflicts {r['conflicts']}")
                if r.get("withheld_unsettled"):
                    line += f"  withheld {r['withheld_unsettled']}"
            print(line)
            if r.get("note"):
                print(f"           {r['note']}")
    bad = [r for r in results
           if r["state"] not in ("recorded", "dry_run")
           or r.get("conflicts")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
