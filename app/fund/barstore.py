"""The bar archive — what we KNEW, not what the vendor says today.

Every backtest in this system asks a data vendor for history and gets today's
view of it. That view is not what was knowable at the time: closes come back
adjusted for splits and dividends that had not happened yet, delisted names
have quietly vanished, and a vendor that corrects a bad print rewrites the past
without telling anyone. A backtest run against that is not a simulation of a
decision — it is a decision made with the answer in hand.

So the first observation of every bar is archived and never overwritten. Later
disagreements are recorded as RESTATEMENTS rather than applied, which turns a
silent rewrite into a fact with a timestamp. Two properties follow:

  * ``as_of`` reads return only bars dated on or before that date, and only
    observations first seen on or before it — so a backtest can be handed the
    history a decision-maker actually had.
  * A restatement log accumulates, and it is worth reading. A vendor quietly
    changing 2025 closes is the single most common reason a backtest stops
    reproducing, and without this it is invisible.

This does NOT retroactively fix history already gathered without it. Bars first
seen today are point-in-time from today forward, and the archive says so rather
than implying a provenance it does not have.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_bars (
    symbol        TEXT        NOT NULL,
    bar_date      DATE        NOT NULL,
    close         NUMERIC     NOT NULL,
    source        TEXT        NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, bar_date)
);

CREATE INDEX IF NOT EXISTS fund_bars_seen_idx ON fund_bars (symbol, first_seen_at);

-- A vendor changing a close it already served. Recorded, never applied: the
-- archived value stays the one we acted on.
CREATE TABLE IF NOT EXISTS fund_bar_restatements (
    id         BIGSERIAL   PRIMARY KEY,
    symbol     TEXT        NOT NULL,
    bar_date   DATE        NOT NULL,
    old_close  NUMERIC     NOT NULL,
    new_close  NUMERIC     NOT NULL,
    source     TEXT        NOT NULL,
    seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fund_bar_restatements_sym_idx
    ON fund_bar_restatements (symbol, seen_at DESC);
"""

#: Closes agreeing to within this are the same number wearing different
#: rounding. Wider than this from the same source is a real restatement.
RESTATEMENT_EPS = Decimal("0.0001")


class BarStore:
    """Append-first archive of daily closes, with as-of reads."""

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

    # --- writing ------------------------------------------------------------

    def archive(self, symbol: str, dates: list[str], closes: list[float],
                source: str) -> dict[str, Any]:
        """Record an observation. First value wins; disagreements are logged.

        Returns counts rather than raising on a restatement: a vendor revising
        history is a fact to surface, not an error to abort a fetch over.
        """
        symbol = (symbol or "").strip().upper()
        if not symbol or not dates:
            return {"inserted": 0, "restated": 0, "unchanged": 0}

        inserted = restated = unchanged = 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                for d, c in zip(dates, closes):
                    if c is None:
                        continue
                    cur.execute(
                        "SELECT close FROM fund_bars WHERE symbol = %s AND bar_date = %s",
                        (symbol, d))
                    row = cur.fetchone()
                    if row is None:
                        cur.execute(
                            "INSERT INTO fund_bars (symbol, bar_date, close, source) "
                            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                            (symbol, d, Decimal(str(c)), source))
                        inserted += 1
                        continue
                    old = Decimal(str(row[0]))
                    new = Decimal(str(c))
                    if abs(old - new) <= RESTATEMENT_EPS:
                        unchanged += 1
                        continue
                    # Logged, NOT applied. The archived close is the one the
                    # fund acted on, and overwriting it would erase the only
                    # evidence that the vendor changed its mind.
                    cur.execute(
                        "INSERT INTO fund_bar_restatements "
                        "(symbol, bar_date, old_close, new_close, source) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (symbol, d, old, new, source))
                    restated += 1
            conn.commit()

        if restated:
            logger.warning(
                "%s: %d archived close(s) disagree with %s's current view — "
                "recorded as restatements, archive unchanged", symbol, restated, source)
        return {"inserted": inserted, "restated": restated, "unchanged": unchanged}

    # --- reading ------------------------------------------------------------

    def as_of(self, symbol: str, as_of_date: str,
              start: Optional[str] = None) -> dict[str, Any]:
        """The series as it was known on ``as_of_date``.

        Two filters, and both are needed. ``bar_date <= as_of`` keeps out bars
        from the future, which is the obvious one. ``first_seen_at <= as_of``
        keeps out bars from the PAST that we only learned later — a
        backfilled month looks identical to contemporaneous data once it is in
        the table, and treating it as known-at-the-time is exactly the error
        this archive exists to prevent.
        """
        symbol = (symbol or "").strip().upper()
        params: list[Any] = [symbol, as_of_date, _end_of(as_of_date)]
        sql = ("SELECT bar_date, close, source FROM fund_bars "
               "WHERE symbol = %s AND bar_date <= %s AND first_seen_at <= %s")
        if start:
            sql += " AND bar_date >= %s"
            params.append(start)
        sql += " ORDER BY bar_date ASC"

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return {
            "symbol": symbol,
            "dates": [r[0].isoformat() for r in rows],
            "closes": [float(r[1]) for r in rows],
            "sources": sorted({r[2] for r in rows}),
            "as_of": as_of_date,
            "point_in_time": True,
        }

    def coverage(self, symbol: str) -> dict[str, Any]:
        """What the archive holds, and since when it has been trustworthy.

        ``first_seen_at`` on the earliest row is the honest answer to "from
        when is this point-in-time": bars archived in bulk today are a snapshot
        of today's view, however old the bars themselves are.
        """
        symbol = (symbol or "").strip().upper()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*), min(bar_date), max(bar_date), "
                    "       min(first_seen_at), max(first_seen_at) "
                    "FROM fund_bars WHERE symbol = %s", (symbol,))
                n, lo, hi, seen_lo, seen_hi = cur.fetchone()
                cur.execute(
                    "SELECT count(*) FROM fund_bar_restatements WHERE symbol = %s",
                    (symbol,))
                restatements = cur.fetchone()[0]
        return {
            "symbol": symbol, "bars": int(n or 0),
            "first_bar": lo.isoformat() if lo else None,
            "last_bar": hi.isoformat() if hi else None,
            "archived_from": seen_lo.isoformat() if seen_lo else None,
            "archived_to": seen_hi.isoformat() if seen_hi else None,
            "restatements": int(restatements or 0),
            "caveat": ("bars first seen in one bulk archive are a snapshot of "
                       "that day's vendor view, not contemporaneous records"),
        }

    def restatements(self, symbol: Optional[str] = None,
                     limit: int = 100) -> list[dict[str, Any]]:
        """Times a vendor changed a close it had already served."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                if symbol:
                    cur.execute(
                        "SELECT symbol, bar_date, old_close, new_close, source, seen_at "
                        "FROM fund_bar_restatements WHERE symbol = %s "
                        "ORDER BY seen_at DESC LIMIT %s",
                        ((symbol or "").strip().upper(), limit))
                else:
                    cur.execute(
                        "SELECT symbol, bar_date, old_close, new_close, source, seen_at "
                        "FROM fund_bar_restatements ORDER BY seen_at DESC LIMIT %s",
                        (limit,))
                rows = cur.fetchall()
        return [{
            "symbol": r[0], "bar_date": r[1].isoformat(),
            "old_close": float(r[2]), "new_close": float(r[3]),
            "drift_pct": round((float(r[3]) / float(r[2]) - 1) * 100, 4) if r[2] else None,
            "source": r[4], "seen_at": r[5].isoformat(),
        } for r in rows]


def _end_of(day: str) -> datetime:
    """A date as the last instant of that day, UTC.

    An observation made at 16:00 on the as-of date WAS available on that date;
    comparing a timestamp against midnight would discard the whole day.
    """
    y, m, d = (int(p) for p in str(day).split("-"))
    return datetime(y, m, d, 23, 59, 59, 999999, tzinfo=timezone.utc)
