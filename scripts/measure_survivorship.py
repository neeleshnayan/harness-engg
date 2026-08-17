"""Measure what the vanished names would have done to a band-wide portfolio.

The research note asserted that survivorship bias flatters a hold-everything
rule, on the reasoning that missing names are dead names. That reasoning is only
half right and the half it gets wrong matters: **delisting is not failure**. A
company that is acquired delists too, usually at a premium, and a ticker that
reorganises delists without any economic event at all. So the sign of the bias is
an empirical question, and assuming it is negative would be exactly the kind of
plausible-sounding invention the harness exists to prevent.

Method, and its limits stated up front:

  * ADV is measured over the six months BEFORE the test window opens, so band
    membership is decided on information available then rather than on the
    survivor-only measurement we have today.
  * Return runs from the first bar in the window to the LAST bar the vendor
    serves. For an acquisition that last print is close to the deal price, which
    is the right answer. For a company that fell to nothing it is a near-total
    loss, also right. What it cannot see is what holders received AFTER the last
    print — cash from a merger, or nothing from a liquidation — so a name whose
    terminal value came entirely from a post-delisting distribution is
    understated here. That is a known bias in this measurement and it is why the
    output is labelled an estimate.
  * A name whose bars do not arrive is UNMEASURED and excluded from the mean,
    never counted as a total loss. Assuming −100% would manufacture the very
    number this script exists to measure.

Rate-limited at four vendor calls a minute, so this samples rather than
enumerates, and it is resumable: names already measured are skipped.
"""
import json
import os
import random
import sys
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("FUND_STORE", "postgres")

import psycopg  # noqa: E402

from app.fund import polygon as pg  # noqa: E402
from app.fund.polygon import RateLimited  # noqa: E402
from app.fund.pgstore import dsn  # noqa: E402

AS_OF = "2025-01-01"
WINDOW_END = "2026-08-14"
#: ADV measured on the six months before the window opens — the band decided on
#: what was knowable then, not on today's survivor-only measurement.
ADV_START, ADV_END = "2024-07-01", "2024-12-31"
#: The band the 20-name universe came from: $2M–$25M ADV.
ADV_LO, ADV_HI = 2_000_000.0, 25_000_000.0

SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 40
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_survivorship_sample (
    ticker        TEXT PRIMARY KEY,
    adv_usd       NUMERIC,
    first_close   NUMERIC,
    last_close    NUMERIC,
    return_pct    NUMERIC,
    bars_seen     INT,
    first_bar     DATE,
    last_bar      DATE,
    in_band       BOOLEAN,
    unmeasured    TEXT,
    measured_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def vanished_cs() -> list[str]:
    with psycopg.connect(dsn()) as c, c.cursor() as cur:
        cur.execute("""
            SELECT a.ticker FROM fund_universe_asof a
            LEFT JOIN fund_ticker_reference r ON r.ticker = a.ticker
            WHERE a.as_of = %s AND r.ticker IS NULL AND a.type = 'CS'
            ORDER BY a.ticker
        """, (AS_OF,))
        return [r[0] for r in cur.fetchall()]


def already_done() -> set[str]:
    with psycopg.connect(dsn()) as c, c.cursor() as cur:
        cur.execute(SCHEMA)
        c.commit()
        cur.execute("SELECT ticker FROM fund_survivorship_sample")
        return {r[0] for r in cur.fetchall()}


def save(row: dict) -> None:
    with psycopg.connect(dsn()) as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO fund_survivorship_sample
              (ticker, adv_usd, first_close, last_close, return_pct, bars_seen,
               first_bar, last_bar, in_band, unmeasured)
            VALUES (%(ticker)s,%(adv_usd)s,%(first_close)s,%(last_close)s,
                    %(return_pct)s,%(bars_seen)s,%(first_bar)s,%(last_bar)s,
                    %(in_band)s,%(unmeasured)s)
            ON CONFLICT (ticker) DO UPDATE SET
              adv_usd=EXCLUDED.adv_usd, first_close=EXCLUDED.first_close,
              last_close=EXCLUDED.last_close, return_pct=EXCLUDED.return_pct,
              bars_seen=EXCLUDED.bars_seen, first_bar=EXCLUDED.first_bar,
              last_bar=EXCLUDED.last_bar, in_band=EXCLUDED.in_band,
              unmeasured=EXCLUDED.unmeasured, measured_at=now()
        """, row)
        c.commit()


def blank(ticker: str, why: Optional[str]) -> dict:
    """A row with no measurement. ``why`` may be None for a name that was
    measured successfully and simply fell outside the band — that is a result,
    not a failure, and conflating the two would inflate the unmeasured count."""
    return {"ticker": ticker, "adv_usd": None, "first_close": None,
            "last_close": None, "return_pct": None, "bars_seen": None,
            "first_bar": None, "last_bar": None, "in_band": None,
            "unmeasured": why[:200] if why else None}


def main() -> None:
    from statistics import median

    pool = vanished_cs()
    done = already_done()
    todo = [t for t in pool if t not in done]
    random.Random(SEED).shuffle(todo)
    todo = todo[:SAMPLE]
    print(f"{len(pool)} vanished CS names; {len(done)} already measured; "
          f"measuring {len(todo)} this run (seed {SEED})", flush=True)

    for i, sym in enumerate(todo, 1):
        # ADV window first: band membership must be decided on pre-window data.
        try:
            adv_bars = pg.daily_bars(sym, ADV_START, ADV_END)
        except RateLimited as e:
            # Deliberately NOT saved. A row here would say "this company has no
            # history" when what happened is that we asked too fast, and the
            # sample would carry our impatience as a fact about the market.
            # Leaving it unrecorded means the next run picks it up again.
            print(f"[{i}/{len(todo)}] {sym}: SKIPPED (rate limited, not recorded)",
                  flush=True)
            continue
        except Exception as e:  # noqa: BLE001
            save(blank(sym, f"no ADV bars: {e}"))
            print(f"[{i}/{len(todo)}] {sym}: unmeasured ({str(e)[:60]})", flush=True)
            continue
        dollar = [c * v for c, v in zip(adv_bars.get("closes") or [],
                                        adv_bars.get("volumes") or []) if c and v]
        if not dollar:
            save(blank(sym, "no dollar volume in the ADV window"))
            print(f"[{i}/{len(todo)}] {sym}: unmeasured (no ADV)", flush=True)
            continue
        adv = median(dollar)
        in_band = ADV_LO <= adv <= ADV_HI

        # Only spend a second call on names that would have been in OUR band.
        # The market-wide delisting rate is not the question; what biases our
        # results is specifically names that would have passed our screen.
        if not in_band:
            row = blank(sym, None)
            row.update({"adv_usd": adv, "in_band": False,
                        "bars_seen": len(adv_bars.get("closes") or [])})
            save(row)
            print(f"[{i}/{len(todo)}] {sym}: ADV ${adv/1e6:,.1f}m — outside band",
                  flush=True)
            continue

        try:
            b = pg.daily_bars(sym, AS_OF, WINDOW_END)
        except RateLimited:
            print(f"[{i}/{len(todo)}] {sym}: in band but rate limited — "
                  f"not recorded, will retry", flush=True)
            continue
        except Exception as e:  # noqa: BLE001
            row = blank(sym, f"in band but no window bars: {e}")
            row["adv_usd"] = adv
            row["in_band"] = True
            save(row)
            print(f"[{i}/{len(todo)}] {sym}: in band, window unmeasured", flush=True)
            continue
        closes = b.get("closes") or []
        dates = b.get("dates") or []
        if len(closes) < 2 or not closes[0]:
            row = blank(sym, "fewer than 2 window bars")
            row["adv_usd"] = adv
            row["in_band"] = True
            save(row)
            print(f"[{i}/{len(todo)}] {sym}: in band, too few bars", flush=True)
            continue
        ret = (closes[-1] / closes[0] - 1.0) * 100.0
        save({"ticker": sym, "adv_usd": adv, "first_close": closes[0],
              "last_close": closes[-1], "return_pct": ret,
              "bars_seen": len(closes), "first_bar": dates[0],
              "last_bar": dates[-1], "in_band": True, "unmeasured": None})
        print(f"[{i}/{len(todo)}] {sym}: ADV ${adv/1e6:,.1f}m IN BAND, "
              f"{ret:+.1f}% to last print {dates[-1]}", flush=True)

    report()


def report() -> None:
    from statistics import mean, median
    with psycopg.connect(dsn()) as c, c.cursor() as cur:
        cur.execute("SELECT count(*), count(*) FILTER (WHERE in_band), "
                    "count(*) FILTER (WHERE unmeasured IS NOT NULL) "
                    "FROM fund_survivorship_sample")
        total, in_band, unmeasured = cur.fetchone()
        cur.execute("SELECT ticker, adv_usd, return_pct, last_bar "
                    "FROM fund_survivorship_sample "
                    "WHERE in_band AND return_pct IS NOT NULL "
                    "ORDER BY return_pct")
        rows = cur.fetchall()
    print("\n" + "=" * 62, flush=True)
    print(f"sampled {total} vanished CS names: {in_band} in band, "
          f"{unmeasured} unmeasured", flush=True)
    if not rows:
        print("no band-eligible name has a measured return yet", flush=True)
        return
    rets = [float(r[2]) for r in rows]
    print(f"\nband-eligible vanished names with a measured return: {len(rets)}",
          flush=True)
    for t, adv, ret, last in rows:
        print(f"  {t:8s} ADV ${float(adv)/1e6:6.1f}m  {float(ret):+8.1f}%  "
              f"last print {last}", flush=True)
    print(f"\nmean {mean(rets):+.1f}%   median {median(rets):+.1f}%", flush=True)
    print(f"losers (< -50%): {sum(1 for r in rets if r < -50)}   "
          f"winners (> +20%): {sum(1 for r in rets if r > 20)}", flush=True)
    print("\nSIGN OF THE BIAS: a NEGATIVE mean means excluding these names "
          "flattered our backtests; a POSITIVE mean means it understated them.",
          flush=True)


if __name__ == "__main__":
    main()
