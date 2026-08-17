"""Who was listed on a date, and what it costs us that we only know today.

Every universe this fund measures is measured NOW. That single fact biases every
backtest run over it, and not by a small or knowable amount: the band contains
only companies that made it to today, so a rule that holds everything is
flattered by the absence of everything that died. A selective rule is flattered
too, but less — it at least had the chance to avoid the failures — so the bias
lands hardest on exactly the comparison the gate leans on when it says "an
expensive way to hold the underlying".

Disclosing that in a docstring was the honest thing to do while it was all we
could do. It is no longer all we can do. The vendor's reference endpoint takes a
``date``, answering "which tickers were listed then" directly, and separately
lists delisted names with the date they stopped. Between them the bias stops
being a caveat and becomes a measured haircut.

Two rules hold throughout, both instances of the house pattern that absence is
never zero:

  * A snapshot nobody took is NOT an empty market. ``membership()`` returns None
    for a date it has never seen, never an empty set, because an empty set would
    silently exclude every name from an as-of screen and look like a finding.
  * A delisted name whose history cannot be fetched is UNMEASURED, not a total
    loss. Assuming −100% would manufacture the very number this module exists to
    measure honestly, and in the direction that flatters our conclusion.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from statistics import median
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
-- Who was listed on a given date, per the vendor's own as-of answer.
CREATE TABLE IF NOT EXISTS fund_universe_asof (
    as_of        DATE        NOT NULL,
    ticker       TEXT        NOT NULL,
    name         TEXT,
    type         TEXT,
    captured_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (as_of, ticker)
);

CREATE INDEX IF NOT EXISTS fund_universe_asof_date_idx
    ON fund_universe_asof (as_of);

-- Names that stopped trading, with the date they stopped. Separate from the
-- as-of snapshots because it answers a different question: not "who was here"
-- but "who left", which is the half a today-measured universe cannot see.
CREATE TABLE IF NOT EXISTS fund_delisted (
    ticker       TEXT PRIMARY KEY,
    name         TEXT,
    type         TEXT,
    exchange     TEXT,
    delisted_utc TIMESTAMPTZ,
    -- Measured from the vendor's own bars when we go looking, so a name can be
    -- band-tested rather than assumed. NULL means not yet measured, which is
    -- deliberately distinct from measured-and-small.
    adv_usd      NUMERIC,
    median_close NUMERIC,
    bars_seen    INT,
    first_bar    DATE,
    last_bar     DATE,
    measured_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS fund_delisted_when_idx
    ON fund_delisted (delisted_utc);
"""


class AsOfUniverse:
    """Point-in-time listing membership, and the cost of not having had it."""

    def __init__(self, dsn_str: Optional[str] = None):
        from app.fund.pgstore import dsn
        self._dsn = dsn_str or dsn()
        self._ensure_schema()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    # --- capturing ----------------------------------------------------------

    def snapshot(self, as_of: str, types: tuple[str, ...] = ("CS", "ADRC"),
                 max_pages: int = 40) -> dict[str, Any]:
        """Capture who was listed on ``as_of``, in bulk.

        A page cap is a stop, not a target: without one a vendor that keeps
        handing back cursors would spend the whole rate budget silently. Hitting
        it is REPORTED, because a partial snapshot that claims to be whole would
        make an as-of screen quietly exclude real names.
        """
        from app.fund import polygon as pg
        import urllib.parse

        if not pg.available():
            return {"as_of": as_of, "captured": 0,
                    "note": "POLYGON_API_KEY not set — cannot capture as-of membership"}

        rows: list[tuple] = []
        pages = 0
        truncated: list[str] = []
        for t in types:
            cursor = None
            for _ in range(max_pages):
                body = pg._get("/v3/reference/tickers",
                               {"market": "stocks", "type": t, "active": "true",
                                "date": as_of, "limit": 1000, "sort": "ticker",
                                "cursor": cursor})
                pages += 1
                got = body.get("results") or []
                for r in got:
                    if r.get("ticker"):
                        rows.append((as_of, r["ticker"], r.get("name"), r.get("type")))
                nxt = body.get("next_url") or ""
                if not nxt or not got:
                    break
                cursor = urllib.parse.parse_qs(
                    urllib.parse.urlparse(nxt).query).get("cursor", [None])[0]
                if not cursor:
                    break
            else:
                truncated.append(t)

        if not rows:
            return {"as_of": as_of, "captured": 0,
                    "note": "vendor returned no tickers for this date"}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO fund_universe_asof (as_of, ticker, name, type) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT (as_of, ticker) DO UPDATE "
                    "SET name = EXCLUDED.name, type = EXCLUDED.type, "
                    "    captured_at = now()", rows)
            conn.commit()
        out = {"as_of": as_of, "captured": len(rows), "pages": pages}
        if truncated:
            out["incomplete"] = (
                f"hit the {max_pages}-page cap on {', '.join(truncated)} — this "
                f"snapshot is PARTIAL, so names missing from it are unknown "
                f"rather than confirmed unlisted")
        return out

    def capture_delisted(self, since: str, max_pages: int = 40) -> dict[str, Any]:
        """Names that stopped trading on or after ``since``.

        These are the names a today-measured universe cannot see, and therefore
        the entire content of the survivorship bias over that window.
        """
        from app.fund import polygon as pg
        import urllib.parse

        if not pg.available():
            return {"captured": 0, "note": "POLYGON_API_KEY not set"}

        rows: list[tuple] = []
        pages = 0
        cursor = None
        hit_cap = True
        for _ in range(max_pages):
            body = pg._get("/v3/reference/tickers",
                           {"market": "stocks", "active": "false",
                            "delisted_utc.gte": since, "limit": 1000,
                            "sort": "ticker", "cursor": cursor})
            pages += 1
            got = body.get("results") or []
            for r in got:
                if r.get("ticker"):
                    rows.append((r["ticker"], r.get("name"), r.get("type"),
                                 r.get("primary_exchange"), r.get("delisted_utc")))
            nxt = body.get("next_url") or ""
            if not nxt or not got:
                hit_cap = False
                break
            cursor = urllib.parse.parse_qs(
                urllib.parse.urlparse(nxt).query).get("cursor", [None])[0]
            if not cursor:
                hit_cap = False
                break

        if rows:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO fund_delisted "
                        "(ticker, name, type, exchange, delisted_utc) "
                        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (ticker) DO UPDATE "
                        "SET name = EXCLUDED.name, type = EXCLUDED.type, "
                        "    exchange = EXCLUDED.exchange, "
                        "    delisted_utc = EXCLUDED.delisted_utc", rows)
                conn.commit()
        out = {"captured": len(rows), "pages": pages, "since": since}
        if hit_cap:
            out["incomplete"] = (
                f"hit the {max_pages}-page cap — more delisted names exist than "
                f"were captured, so any haircut computed from this is a LOWER "
                f"bound on the bias")
        return out

    # --- reads --------------------------------------------------------------

    def membership(self, as_of: str) -> Optional[set[str]]:
        """Tickers listed on that date, or None if never captured.

        None rather than an empty set, deliberately. An as-of screen that
        intersects with an empty set returns nothing and looks like a market with
        no companies in it — a silent, total failure dressed as a result.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ticker FROM fund_universe_asof WHERE as_of = %s",
                            (as_of,))
                rows = [r[0] for r in cur.fetchall()]
        return set(rows) if rows else None

    def snapshots(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT as_of, count(*), max(captured_at) "
                            "FROM fund_universe_asof GROUP BY as_of ORDER BY as_of")
                rows = cur.fetchall()
        return [{"as_of": r[0].isoformat(), "tickers": int(r[1]),
                 "captured_at": r[2].isoformat()} for r in rows]

    def vanished_since(self, as_of: str) -> list[dict[str, Any]]:
        """Listed then, absent from today's reference now.

        The measurable content of the survivorship bias: every one of these is a
        name any screen built today cannot propose, and every backtest over a
        today-measured universe silently excluded.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.ticker, a.name, a.type, d.delisted_utc, d.adv_usd,
                           d.median_close, d.bars_seen
                    FROM fund_universe_asof a
                    LEFT JOIN fund_ticker_reference r ON r.ticker = a.ticker
                    LEFT JOIN fund_delisted d ON d.ticker = a.ticker
                    WHERE a.as_of = %s AND r.ticker IS NULL
                    ORDER BY a.ticker
                """, (as_of,))
                rows = cur.fetchall()
        return [{"ticker": r[0], "name": r[1], "type": r[2],
                 "delisted_utc": r[3].isoformat() if r[3] else None,
                 "adv_usd": float(r[4]) if r[4] is not None else None,
                 "median_close": float(r[5]) if r[5] is not None else None,
                 "bars_seen": r[6]} for r in rows]

    # --- measuring the vanished --------------------------------------------

    def measure(self, tickers: list[str], start: str, end: str) -> dict[str, Any]:
        """Fetch bars for delisted names so they can be band-tested.

        Expensive by construction — four vendor calls a minute — so callers pass
        a deliberate shortlist rather than a whole market. Names whose bars do
        not arrive are recorded as UNMEASURED and counted separately: treating a
        fetch failure as a dead company would invent the loss this is trying to
        measure.
        """
        from app.fund import polygon as pg
        from app.fund.polygon import PolygonError

        measured, unmeasured = 0, []
        for sym in tickers:
            try:
                b = pg.daily_bars(sym, start, end)
            except PolygonError as e:
                logger.info("no bars for delisted %s: %s", sym, e)
                unmeasured.append({"ticker": sym, "reason": str(e)[:120]})
                continue
            closes = b.get("closes") or []
            vols = b.get("volumes") or []
            dates = b.get("dates") or []
            if len(closes) < 2:
                unmeasured.append({"ticker": sym, "reason": "fewer than 2 bars served"})
                continue
            dollar = [c * v for c, v in zip(closes, vols) if c and v]
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO fund_delisted
                            (ticker, adv_usd, median_close, bars_seen, first_bar,
                             last_bar, measured_at)
                        VALUES (%s,%s,%s,%s,%s,%s, now())
                        ON CONFLICT (ticker) DO UPDATE SET
                            adv_usd = EXCLUDED.adv_usd,
                            median_close = EXCLUDED.median_close,
                            bars_seen = EXCLUDED.bars_seen,
                            first_bar = EXCLUDED.first_bar,
                            last_bar = EXCLUDED.last_bar,
                            measured_at = now()
                    """, (sym, median(dollar) if dollar else None,
                          median(closes), len(closes), dates[0], dates[-1]))
                conn.commit()
            measured += 1
        return {"measured": measured, "unmeasured": unmeasured,
                "unmeasured_count": len(unmeasured),
                "note": ("names that did not return bars are unmeasured, not "
                         "assumed worthless — the haircut counts them separately"
                         if unmeasured else "every name returned bars")}

    def band_eligible_vanished(self, as_of: str, adv_lo: float,
                               adv_hi: float) -> dict[str, Any]:
        """Of the vanished, which would have been in OUR band.

        The number that matters. A market-wide delisting count says little about
        a fund that only ever fishes in one ADV band; what biases *our* results
        is specifically the names that would have passed *our* screen and then
        died.
        """
        rows = self.vanished_since(as_of)
        eligible, outside, unmeasured = [], [], []
        for r in rows:
            if r["adv_usd"] is None:
                unmeasured.append(r)
            elif adv_lo <= r["adv_usd"] <= adv_hi:
                eligible.append(r)
            else:
                outside.append(r)
        return {
            "as_of": as_of,
            "adv_band_usd": [adv_lo, adv_hi],
            "vanished_total": len(rows),
            "band_eligible": eligible,
            "band_eligible_count": len(eligible),
            "outside_band_count": len(outside),
            "unmeasured_count": len(unmeasured),
            "note": (f"{len(unmeasured)} vanished names have no measured ADV, so "
                     f"band eligibility is unknown for them — the eligible count "
                     f"is a LOWER bound"
                     if unmeasured else
                     "every vanished name has a measured ADV"),
        }
