"""Every NAV strike on one UTC day — the detail view behind the day rollup.

    ./venv/Scripts/python.exe -X utf8 scripts/desk/nav_day.py 2026-08-21
    ./venv/Scripts/python.exe -X utf8 scripts/desk/nav_day.py            # today
    ... nav_day.py 2026-08-21 --json

``day_events.py`` answers "how many strikes, and open to close". This answers
"show me each one", which is the question actually asked when a mark looks
wrong: it prints every ``NavStruck`` in sequence with its cash/positions split
and the change from the previous strike.

**THIS IS A DERIVED READING OF THE LOG AND IS NOT THE BOOK.** NAV folds from
the event log through ``NavService``; these are the strikes that were
RECORDED. If the two ever disagree, the fold wins and the disagreement is the
finding.

POSTGRES-ONLY, deliberately: there is no aggregate endpoint for per-strike
detail and inventing one would put 60 KB of positions into a payload that is
read on every desk load. See ``scripts/desk/_common.py`` for the quirks.

A day with no strike prints the sentence, not a zero.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import _common as C


def render(body: dict) -> str:
    rows = body["strikes"]
    if not rows:
        return body["note"]
    out = [f"{'SEQ':>6}  {'TIME (UTC)':<16}{'NAV':>14}{'CHANGE':>12}"
           f"{'CASH':>12}{'POSITIONS':>12}{'LEGS':>6}"]
    prev = None
    for r in rows:
        nav = r["total_nav_usd"]
        # UNREADABLE, never 0 — a strike that happened and could not be parsed
        # is listed, because dropping it would hide it.
        chg = "—" if (prev is None or nav is None) else f"{nav - prev:+,.2f}"
        out.append(f"{str(r['seq'] or '-'):>6}  {(r['ts'] or 'ABSENT')[11:19]:<16}"
                   f"{C.money(nav):>14}{chg:>12}"
                   f"{C.money(r['cash_usd']):>12}"
                   f"{C.money(r['positions_usd']):>12}"
                   f"{('ABSENT' if r['position_count'] is None else r['position_count']):>6}")
        if nav is not None:
            prev = nav
    firsts = [r["total_nav_usd"] for r in rows if r["total_nav_usd"] is not None]
    if len(firsts) >= 2:
        out.append("")
        out.append(f"open {C.money(firsts[0])} -> close {C.money(firsts[-1])}"
                   f"   ({firsts[-1] - firsts[0]:+,.2f} over "
                   f"{len(rows)} strike(s))")
    unreadable = sum(1 for r in rows if r["total_nav_usd"] is None)
    if unreadable:
        out.append(f"{unreadable} strike(s) carried NO readable total — listed "
                   f"above, never dropped and never counted as zero")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv
    if len(args) > 1:
        C.usage("usage: nav_day.py [YYYY-MM-DD] [--json]")
    day = args[0] if args else datetime.now(timezone.utc).date().isoformat()

    # C.stores() puts the repo root on sys.path, so the import follows it.
    store, _ = C.stores()
    from app.fund import metrics
    try:
        body = metrics.nav_strikes(day, store)
    except ValueError as e:
        C.usage(str(e))
    if as_json:
        print(json.dumps(body, indent=1, default=str))
        return 0
    print(C.banner("postgres", f"NAV strikes {body['day']}"))
    print(render(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
