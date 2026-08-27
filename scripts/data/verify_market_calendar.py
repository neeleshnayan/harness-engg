"""Check `navgap`'s sourced closure table against the fund's OWN daily bars.

The table in ``app/fund/navgap.py`` is transcribed from the venue
(https://www.nyse.com/markets/hours-calendars). A transcription is a claim, and
a wrong one is silent in the worst direction: a trading day mistyped as a
holiday turns a hole in the NAV record into a legitimate closure and the
instrument stops reporting the exact thing it was built for.

So the table is verified against a second, independent source the fund already
owns: its own daily bar series. A US-listed ETF has a bar on every trading day
and none on any other. The two must agree in BOTH directions:

  * every weekday with no bar must be in HOLIDAYS  (else the table is missing a
    closure and a real holiday would read as a hole)
  * every weekday with a bar must NOT be in HOLIDAYS  (else the table invents a
    closure and a real hole would read as a holiday)

Prints the DOMAIN — how many weekdays were compared — because a zero-mismatch
result over zero comparisons is not a result. Exit 0 on agreement, 1 on any
disagreement, 2 when the bar series could not be read (which is neither).

    python scripts/data/verify_market_calendar.py
    python scripts/data/verify_market_calendar.py --symbol IWM --spine http://127.0.0.1:8090
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from app.fund import navgap  # noqa: E402

DEFAULT_SPINE = os.getenv("SPINE_URL", "http://127.0.0.1:8090")


def bar_dates(spine: str, symbol: str, lookback_days: int) -> set[str]:
    url = (f"{spine}/api/v1/fund/marketdata/bars?symbol={symbol}"
           f"&lookback_days={lookback_days}&format=csv")
    with urllib.request.urlopen(url, timeout=120) as r:
        body = r.read().decode("utf-8")
    out = set()
    for row in csv.reader(io.StringIO(body)):
        if row and row[0].strip():
            out.add(row[0].strip())
    return out


def compare(dates: set[str], first: date, last: date) -> dict:
    missing, invented, compared = [], [], 0
    day = first
    while day <= last:
        if day.weekday() < 5 and navgap.calendar_covers(day):
            compared += 1
            iso = day.isoformat()
            has_bar = iso in dates
            shut = navgap.session_bounds(day) is None
            if not has_bar and not shut:
                missing.append(iso)
            if has_bar and shut:
                invented.append(iso)
        day += timedelta(days=1)
    return {"compared": compared, "missing_from_table": missing,
            "invented_by_table": invented}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--spine", default=DEFAULT_SPINE)
    ap.add_argument("--lookback-days", type=int, default=400)
    args = ap.parse_args()

    try:
        dates = bar_dates(args.spine, args.symbol, args.lookback_days)
    except Exception as e:  # noqa: BLE001
        print(f"UNREADABLE: could not read {args.symbol} bars from "
              f"{args.spine} ({type(e).__name__}: {e}). This is not a pass.")
        return 2
    if not dates:
        print(f"UNREADABLE: {args.symbol} returned zero bars - nothing to "
              f"compare against, which is not agreement.")
        return 2

    # Only the overlap of (what the bars cover) and (what the table covers).
    first = max(date.fromisoformat(min(dates)), navgap.CALENDAR_FIRST_DAY)
    last = min(date.fromisoformat(max(dates)), navgap.CALENDAR_LAST_DAY)
    if last < first:
        print("UNREADABLE: the bar series and the calendar table do not "
              "overlap, so nothing was compared.")
        return 2

    res = compare(dates, first, last)
    print(f"source      : {navgap.CALENDAR_SOURCE} (sourced "
          f"{navgap.CALENDAR_SOURCED_ON})")
    print(f"cross-check : {args.symbol} daily bars, {first} to {last}")
    print(f"DOMAIN      : {res['compared']} weekdays compared")
    print(f"missing from table (weekday, no bar, not a holiday): "
          f"{res['missing_from_table'] or 'NONE'}")
    print(f"invented by table (weekday, has a bar, called a holiday): "
          f"{res['invented_by_table'] or 'NONE'}")
    bad = res["missing_from_table"] or res["invented_by_table"]
    print("VERDICT     :", "DISAGREE" if bad else "agree")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
