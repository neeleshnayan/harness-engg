"""The hunting ground: names a large fund structurally cannot trade.

Every strategy this fund has run so far was on SPY, GLD or a mega-cap — names
with capacity measured in tens of billions, where our size buys us precisely
nothing and we compete against people with colocated hardware and hundreds of
PhDs. That is the one water where being small is only a disadvantage.

This builds the other water. Screen what our own venue will let us trade,
measure how much money each name can absorb, and keep the band where two
things are true at once: big enough that the strategy is worth running, small
enough that a multi-billion fund cannot be in it. That band is not a
consolation prize for being small — it is the only structural edge a fund this
size has, and it has to be searched deliberately because nothing drifts into
it on its own.

Two filters are non-negotiable and both are about US, not about the market:

  * TRADABLE at our venue. A name we cannot buy is not an opportunity, it is
    a distraction, and a universe built from an index would be full of them.
  * FRACTIONABLE. With a $2k book a position is roughly $170, so a $500 share
    price is uninvestable without fractional shares. Half the tradable
    universe fails this, and a screen that ignored it would keep proposing
    names we cannot actually hold.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_universe (
    symbol        TEXT PRIMARY KEY,
    exchange      TEXT,
    fractionable  BOOLEAN     NOT NULL DEFAULT TRUE,
    adv_usd       NUMERIC,
    median_close  NUMERIC,
    bars_seen     INT         NOT NULL DEFAULT 0,
    refreshed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fund_universe_adv_idx ON fund_universe (adv_usd DESC);
"""

#: Batch size for the venue's multi-symbol bar endpoint. 500 symbols returns in
#: about five seconds, so the whole fractionable universe costs ~90s.
BATCH = 500

#: Days of history used to measure typical volume. Long enough that a quiet
#: week does not dominate, short enough to describe the name as it trades now.
LOOKBACK_DAYS = 90

#: Bars required before a name gets an ADV at all. A recent listing with nine
#: sessions has no typical volume yet, and pretending otherwise puts a name in
#: the hunting ground on the strength of its IPO week.
MIN_BARS = 30

#: Past this the screen is reported as stale. A trading week is the sensible
#: horizon: a name's typical volume rarely moves band-to-band inside one, but a
#: delisting or a liquidity collapse over a week absolutely can.
STALE_AFTER_HOURS = float(os.getenv("UNIVERSE_STALE_HOURS", "168"))

#: How often the scheduler re-measures. Daily, because the refresh is 50
#: seconds of work and the alternative is remembering to do it.
REFRESH_EVERY_HOURS = float(os.getenv("UNIVERSE_REFRESH_HOURS", "24"))


def needs_refresh(age_hours: Optional[float]) -> bool:
    """Never measured, or older than the refresh interval."""
    return age_hours is None or age_hours >= REFRESH_EVERY_HOURS


class Universe:
    """What we can trade, and how much of it the market can absorb."""

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

    # --- building -----------------------------------------------------------

    @staticmethod
    def tradable_assets() -> list[dict[str, Any]]:
        """Names our venue will actually let us buy, in sizes we can afford."""
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import AssetClass, AssetStatus
        from alpaca.trading.requests import GetAssetsRequest

        tc = TradingClient(os.getenv("ALPACA_API_KEY"),
                           os.getenv("ALPACA_SECRET_KEY"), paper=True)
        assets = tc.get_all_assets(GetAssetsRequest(
            status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY))
        return [
            {"symbol": a.symbol, "exchange": str(getattr(a, "exchange", "") or "")}
            for a in assets
            if a.tradable and getattr(a, "fractionable", False)
        ]

    def refresh(self, limit: Optional[int] = None,
                progress: bool = False) -> dict[str, Any]:
        """Measure typical dollar volume for every tradable name.

        Median dollar volume per name, not mean: one earnings session or index
        rebalance can be ten times a normal day, and a mean would let that
        single print promote a name into a band it does not belong in.
        """
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        assets = self.tradable_assets()
        if limit:
            assets = assets[:limit]
        by_symbol = {a["symbol"]: a for a in assets}
        symbols = list(by_symbol)

        dc = StockHistoricalDataClient(os.getenv("ALPACA_API_KEY"),
                                       os.getenv("ALPACA_SECRET_KEY"))
        end = datetime.now(timezone.utc) - timedelta(days=1)
        start = end - timedelta(days=LOOKBACK_DAYS)

        rows: list[tuple] = []
        thin = priced = 0
        for i in range(0, len(symbols), BATCH):
            chunk = symbols[i:i + BATCH]
            try:
                data = dc.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=chunk, timeframe=TimeFrame.Day,
                    start=start, end=end)).data
            except Exception as e:  # noqa: BLE001
                logger.warning("bars batch %d failed: %s", i // BATCH, e)
                continue
            for sym, bars in data.items():
                dollar = [float(b.close) * float(b.volume) for b in bars
                          if b.close and b.volume]
                closes = [float(b.close) for b in bars if b.close]
                if len(dollar) < MIN_BARS:
                    thin += 1
                    continue
                rows.append((sym, by_symbol.get(sym, {}).get("exchange"),
                             True, median(dollar), median(closes), len(dollar)))
                priced += 1
            if progress:
                logger.info("universe: %d/%d symbols measured", priced, len(symbols))

        self._upsert(rows)
        return {"tradable_fractionable": len(symbols), "measured": priced,
                "too_few_bars": thin, "lookback_days": LOOKBACK_DAYS}

    def _upsert(self, rows: list[tuple]) -> None:
        if not rows:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO fund_universe
                        (symbol, exchange, fractionable, adv_usd, median_close,
                         bars_seen, refreshed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (symbol) DO UPDATE SET
                        exchange = EXCLUDED.exchange,
                        adv_usd = EXCLUDED.adv_usd,
                        median_close = EXCLUDED.median_close,
                        bars_seen = EXCLUDED.bars_seen,
                        refreshed_at = now()
                    """,
                    rows)
            conn.commit()

    # --- searching ----------------------------------------------------------

    def hunting_ground(self, turnover_pct: float = 5.0,
                       participation: float = 0.01,
                       min_capacity: float = 100_000.0,
                       max_capacity: float = 50_000_000.0,
                       limit: int = 200) -> dict[str, Any]:
        """Names inside the band where our size is an advantage.

        Capacity is computed at a REFERENCE turnover rather than stored,
        because capacity is a property of a strategy-on-a-name, not of a
        ticker: the same symbol supports ten times the money at a tenth the
        turnover. Storing one number would quietly turn an assumption into a
        fact.

        The upper bound is the interesting one and it is deliberate. Names
        ABOVE it are not rejected for being bad — they are rejected for being
        available to everyone, which is a different and more useful reason.
        """
        t = turnover_pct / 100.0
        if t <= 0:
            raise ValueError("turnover must be positive")
        # capacity = participation * adv / turnover, inverted to bound adv.
        adv_lo = min_capacity * t / participation
        adv_hi = max_capacity * t / participation

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT symbol, exchange, adv_usd, median_close, bars_seen
                    FROM fund_universe
                    WHERE adv_usd BETWEEN %s AND %s
                    ORDER BY adv_usd DESC
                    LIMIT %s
                    """,
                    (adv_lo, adv_hi, limit))
                rows = cur.fetchall()

        from app.fund.capacity import closed_to_big_funds

        names = []
        for r in rows:
            adv = float(r[2])
            # NOT our participation. Ours keeps us impact-free; a large fund
            # building a position accepts impact to get in at all, and judging
            # their access by our caution reported every name as closed.
            big = closed_to_big_funds(adv)
            names.append({
                "symbol": r[0], "exchange": r[1],
                "adv_usd": adv, "median_close": float(r[3]),
                "bars_seen": r[4],
                "capacity_usd": round(participation * adv / t, 2),
                # The moat claim, kept SEPARATE from capacity. Capacity is a
                # property of a strategy at a turnover; this is whether a large
                # fund could build a position at all. At 5% turnover the
                # capacity band happily admits S&P names — JBHT reports $50m of
                # "capacity" and is perfectly available to a $5bn fund — so
                # reporting only capacity invites exactly the wrong conclusion.
                "closed_to_big_funds": big.get("closed"),
                "big_fund_days_to_build": big.get("days_to_build"),
            })
        closed = [n for n in names if n["closed_to_big_funds"]]
        return {
            # Staleness travels WITH the results, not in a separate stats call
            # nobody makes. Liquidity moves, listings appear and delistings
            # leave tickers in the screen that cannot be bought — and a stale
            # screen is worse than none precisely because it still looks
            # authoritative.
            **self.freshness(),
            "turnover_pct": turnover_pct, "participation": participation,
            "capacity_band_usd": [min_capacity, max_capacity],
            "adv_band_usd": [round(adv_lo, 2), round(adv_hi, 2)],
            "count": len(names),
            "closed_to_big_funds_count": len(closed),
            "caveat": ("capacity is a property of a strategy at this turnover; "
                       "closed_to_big_funds is a property of the NAME. Only the "
                       "second is the structural edge — at high turnover the "
                       "capacity band admits large caps a big fund can hold "
                       "comfortably"),
            "names": names,
        }

    def freshness(self) -> dict[str, Any]:
        """How old the measurements are, and whether to trust them.

        Returned alongside every screen. The failure mode this guards is the
        same one an unscheduled backup has: the thing still answers, still
        looks authoritative, and is quietly describing a market that has moved.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT max(refreshed_at), count(*) FROM fund_universe")
                refreshed, n = cur.fetchone()
        if not refreshed or not n:
            return {"refreshed_at": None, "age_hours": None, "stale": True,
                    "freshness_note": "the universe has never been measured — "
                                      "run a refresh before trusting a screen"}
        age_h = (datetime.now(timezone.utc) - refreshed).total_seconds() / 3600.0
        stale = age_h > STALE_AFTER_HOURS
        return {
            "refreshed_at": refreshed.isoformat(),
            "age_hours": round(age_h, 1),
            "stale": stale,
            "freshness_note": (
                f"volumes are {age_h:.0f} hours old, past the {STALE_AFTER_HOURS}h "
                f"limit — names may have drifted out of the band, and a delisted "
                f"ticker would still be listed here" if stale else
                f"measured {age_h:.1f} hours ago"),
        }

    def hunting_ground_count(self, turnover_pct: float = 5.0,
                             participation: float = 0.01,
                             min_capacity: float = 100_000.0,
                             max_capacity: float = 50_000_000.0) -> int:
        """How many names are in the band — the TRUE count, not a page of them.

        Separate from hunting_ground() on purpose. That method takes a limit
        because nobody wants five thousand rows, and using the length of a
        limited page as a denominator would report "3 of 2,000" when the real
        answer is "3 of 5,557" — understating the unexplored territory, which
        is precisely the dishonesty the map exists to prevent.
        """
        t = turnover_pct / 100.0
        if t <= 0:
            raise ValueError("turnover must be positive")
        adv_lo = min_capacity * t / participation
        adv_hi = max_capacity * t / participation
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM fund_universe WHERE adv_usd BETWEEN %s AND %s",
                    (adv_lo, adv_hi))
                return int(cur.fetchone()[0])

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*), min(adv_usd), max(adv_usd), "
                    "       percentile_cont(0.5) WITHIN GROUP (ORDER BY adv_usd), "
                    "       max(refreshed_at) FROM fund_universe")
                n, lo, hi, med, refreshed = cur.fetchone()
        return {
            "symbols": int(n or 0),
            "adv_min_usd": float(lo) if lo else None,
            "adv_median_usd": float(med) if med else None,
            "adv_max_usd": float(hi) if hi else None,
            "refreshed_at": refreshed.isoformat() if refreshed else None,
        }
