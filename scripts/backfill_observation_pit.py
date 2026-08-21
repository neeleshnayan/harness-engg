"""Backfill `accepted_at` / `period` / `items` onto observations already stored.

The columns landed 2026-08-21; the corpus predates them. Every existing
observation carries a DATE and nothing finer, and 55.9% of the corpus shares a
filing date with another observation on the same name — so a backtest reading
them in id order is reading the future inside a day.

The accession is already stored on every row, and EDGAR's submissions feed is
keyed by CIK with the accession in it, so the mapping is recoverable exactly.
Nothing is inferred: a row whose accession does not appear in the issuer's
recent-filings window is LEFT ALONE and counted, never guessed at from `filed`.

NO TIMEZONE SHIFT is applied. See `Filing.accepted_at` — the dispatch brief's
claim that acceptanceDateTime is ET was tested against 30,732 live filings and
refuted; the Z is truthful.

Run:
    ./venv/Scripts/python.exe -X utf8 scripts/backfill_observation_pit.py --dry-run
    ./venv/Scripts/python.exe -X utf8 scripts/backfill_observation_pit.py --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true",
                    help="write. Without it, nothing is changed.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-tickers", type=int, default=0,
                    help="stop after N tickers (EDGAR is rate limited)")
    a = ap.parse_args(argv)
    if not a.apply and not a.dry_run:
        print("choose --dry-run or --apply", file=sys.stderr)
        return 2

    import psycopg
    from app.fund.edgar import SUBMISSIONS_URL, _col, _throttled_get, _utc, cik_for
    from app.fund.pgstore import dsn
    import json

    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            # PRECONDITION, checked rather than assumed. The columns are created
            # by `Observations`' schema migration, which runs when the spine
            # starts with this build — so on a database the spine has not yet
            # restarted against, they are simply absent. Say that plainly
            # instead of dying on a psycopg UndefinedColumn six frames down.
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                " WHERE table_name = 'fund_observations' "
                "   AND column_name IN ('accepted_at','period','items')")
            have = {r[0] for r in cur.fetchall()}
            missing = {"accepted_at", "period", "items"} - have
            if missing:
                print(f"REFUSED: fund_observations is missing {sorted(missing)}.",
                      file=sys.stderr)
                print("  These columns are created by the Observations schema "
                      "migration, which runs when the spine starts with this "
                      "build. Restart the spine, then re-run.", file=sys.stderr)
                return 1
            cur.execute(
                "SELECT ticker, accession, count(*) FROM fund_observations "
                " WHERE accepted_at IS NULL GROUP BY ticker, accession "
                " ORDER BY ticker")
            todo = cur.fetchall()
    by_ticker: dict[str, list[str]] = defaultdict(list)
    for ticker, accession, _n in todo:
        by_ticker[ticker].append(accession)
    total_rows = sum(n for _t, _a, n in todo)
    print(f"{len(todo)} (ticker, accession) pairs across {len(by_ticker)} tickers, "
          f"{total_rows} observation rows with no accepted_at")

    tickers = sorted(by_ticker)
    if a.limit_tickers:
        tickers = tickers[:a.limit_tickers]

    resolved: dict[str, tuple] = {}
    unresolved: list[tuple[str, str]] = []
    for i, tk in enumerate(tickers, 1):
        cik = cik_for(tk)
        if not cik:
            unresolved += [(tk, acc) for acc in by_ticker[tk]]
            continue
        try:
            doc = json.loads(_throttled_get(SUBMISSIONS_URL.format(cik=cik)).decode())
        except Exception as e:  # noqa: BLE001
            print(f"  {tk}: submissions unavailable ({type(e).__name__}) — skipped")
            unresolved += [(tk, acc) for acc in by_ticker[tk]]
            continue
        rec = (doc.get("filings") or {}).get("recent") or {}
        n = len(rec.get("accessionNumber") or [])
        accs = _col(rec, "accessionNumber", n)
        acc_dt = _col(rec, "acceptanceDateTime", n)
        periods = _col(rec, "reportDate", n)
        items = _col(rec, "items", n)
        index = {accs[j]: (_utc(acc_dt[j]), periods[j] or None, items[j] or None)
                 for j in range(n)}
        for acc in by_ticker[tk]:
            hit = index.get(acc)
            if hit and hit[0]:
                resolved[acc] = hit
            else:
                unresolved.append((tk, acc))
        if i % 25 == 0:
            print(f"  ... {i}/{len(tickers)} tickers, {len(resolved)} accessions resolved")

    print(f"\nresolved {len(resolved)} accessions; "
          f"{len(unresolved)} could NOT be resolved")
    if unresolved[:5]:
        print("  unresolved sample (left untouched, never guessed):",
              unresolved[:5])

    if not a.apply:
        print("\n[dry run] nothing written")
        return 0

    updated = 0
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            for acc, (accepted, period, items_) in resolved.items():
                cur.execute(
                    "UPDATE fund_observations SET accepted_at = %s, "
                    "       period = COALESCE(period, %s), "
                    "       items = COALESCE(items, %s) "
                    " WHERE accession = %s AND accepted_at IS NULL",
                    (accepted, period, items_, acc))
                updated += cur.rowcount
        conn.commit()
    print(f"updated {updated} observation rows")
    print(f"LEFT ALONE: {len(unresolved)} accession(s) outside EDGAR's recent "
          f"window — absent stays absent rather than being filled from `filed`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
