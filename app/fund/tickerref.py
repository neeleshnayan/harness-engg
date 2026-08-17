"""What each ticker actually IS — the difference between a map and a list.

The hunting ground was measured purely from price and volume, which is enough to
say a name is small and illiquid but says nothing about what it is. So the
flagship view claimed to show "businesses a multi-billion fund cannot build a
position in" and cheerfully listed URTY and NVDU — leveraged ETFs, which are not
businesses at all, and whose whole existence is unlimited creation of new units.
A sharp reader spots that immediately, and rightly stops trusting the rest.

Reference data fixes it at the source: type, name, exchange and CIK per ticker,
pulled in bulk (1,000 rows a call) rather than per name, so the entire US
common-stock universe costs a handful of requests against a five-per-minute
budget.

Kept as its own table rather than folded into ``fund_universe`` because the two
change on different clocks and for different reasons: prices and volumes are
re-measured constantly, while what a company IS changes when it lists, delists or
reorganises. Joining them at read time keeps either refresh independent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_ticker_reference (
    ticker       TEXT PRIMARY KEY,
    name         TEXT,
    type         TEXT,
    exchange     TEXT,
    cik          TEXT,
    active       BOOLEAN     NOT NULL DEFAULT true,
    delisted_utc TIMESTAMPTZ,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fund_ticker_reference_type_idx
    ON fund_ticker_reference (type);
"""

#: Types that are operating companies — a share of a business whose float is
#: finite, which is the entire basis of the capacity argument. Everything else
#: (ETF, ETN, WARRANT, UNIT, RIGHT, FUND) either issues units on demand or is a
#: derivative claim, and neither can be "closed to a big fund" in the sense that
#: matters. ADRC is included: a foreign operating business is still a business.
OPERATING_TYPES = ("CS", "ADRC")


class TickerReference:
    """Ticker identity, kept alongside the measured universe."""

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

    # --- refresh -----------------------------------------------------------

    def refresh(self, types: tuple[str, ...] = OPERATING_TYPES,
                max_pages: int = 40) -> dict[str, Any]:
        """Pull ticker identity in bulk and upsert it.

        ``max_pages`` is a stop, not a target: without one, a vendor that keeps
        returning cursors would spend the whole rate budget silently. If the
        cap is hit, that is REPORTED rather than passed off as a complete
        refresh — a partially-loaded reference table that claims to be whole
        would quietly re-admit the ETFs this exists to exclude.
        """
        from app.fund import polygon as pg

        if not pg.available():
            return {"refreshed": 0,
                    "note": "POLYGON_API_KEY not set — reference data unavailable"}

        rows: list[tuple] = []
        pages = 0
        truncated: list[str] = []
        for t in types:
            cursor = None
            for _ in range(max_pages):
                body = pg._get("/v3/reference/tickers",
                               {"market": "stocks", "type": t, "active": "true",
                                "limit": 1000, "sort": "ticker", "cursor": cursor})
                pages += 1
                got = body.get("results") or []
                for r in got:
                    rows.append((r.get("ticker"), r.get("name"), r.get("type"),
                                 r.get("primary_exchange"), r.get("cik"), True, None))
                nxt = body.get("next_url") or ""
                if not nxt or not got:
                    break
                import urllib.parse
                cursor = urllib.parse.parse_qs(
                    urllib.parse.urlparse(nxt).query).get("cursor", [None])[0]
                if not cursor:
                    break
            else:
                truncated.append(t)

        rows = [r for r in rows if r[0]]
        if not rows:
            return {"refreshed": 0, "note": "vendor returned no tickers"}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO fund_ticker_reference
                        (ticker, name, type, exchange, cik, active, delisted_utc)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ticker) DO UPDATE SET
                        name = EXCLUDED.name, type = EXCLUDED.type,
                        exchange = EXCLUDED.exchange, cik = EXCLUDED.cik,
                        active = EXCLUDED.active,
                        delisted_utc = EXCLUDED.delisted_utc,
                        refreshed_at = now()
                    """, rows)
            conn.commit()
        out = {"refreshed": len(rows), "pages": pages, "types": list(types)}
        if truncated:
            out["incomplete"] = (
                f"hit the {max_pages}-page cap on {', '.join(truncated)} — the "
                f"reference table is PARTIAL, so names missing from it are "
                f"unclassified rather than confirmed non-operating")
        return out

    # --- reads -------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT type, count(*) FROM fund_ticker_reference "
                            "GROUP BY type ORDER BY count(*) DESC")
                by_type = {t: int(n) for t, n in cur.fetchall()}
                cur.execute("SELECT max(refreshed_at) FROM fund_ticker_reference")
                refreshed = cur.fetchone()[0]
        return {"by_type": by_type, "total": sum(by_type.values()),
                "refreshed_at": refreshed.isoformat() if refreshed else None,
                "operating_types": list(OPERATING_TYPES)}
