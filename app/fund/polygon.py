"""Polygon.io — good data behind a very small tap.

Worth having for two things the free sources cannot do:

  * **Adjusted daily OHLCV with a volume-weighted price per bar.** Yahoo gives
    closes; ``vw`` is the average price actually paid across the session, which
    is a far better fill assumption than a close and feeds TCA directly.
  * **Delisted tickers.** ``active=false`` returns names with a ``delisted_utc``
    stamp, going back decades. Every universe this fund measures is measured
    TODAY, so it silently contains only survivors — and no amount of care with
    the surviving names fixes that. This endpoint is the only way we can price
    the bias instead of merely disclosing it.

THE CONSTRAINT IS THE DESIGN. The free tier allows **five requests per minute**,
which is not a detail to handle later — it decides what this source can be used
for. Twenty names is four minutes; the 2,363-name capacity band is eight hours.
So Polygon is never the bulk bars provider: it is a source you spend
deliberately on a few names and then cache, and the throttle here blocks rather
than fails so a caller cannot accidentally turn a research script into a
rate-limit storm.

The budget is SHARED, and learning that cost real data. An in-process throttle
resets every time a process starts, so a fresh script fires its whole allowance
into a minute the vendor is still counting from the last one — and the 429s that
came back were being recorded as "this name has no data", which is a rate limit
wearing the costume of a missing company. Two consequences, both handled here:
the window lives in Postgres so every process on this machine draws from one
budget, and a 429 is retried rather than surfaced, because impatience must never
enter a dataset as absence.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Polygon.io rebranded to Massive on 2025-10-30. api.massive.com is the
#: canonical host now; api.polygon.io still answers the same key and is kept as
#: a fallback because the vendor runs both in parallel during migration, and a
#: single-host client would turn their cutover into our outage.
BASE = os.getenv("POLYGON_API_BASE", "https://api.massive.com")
FALLBACK_BASE = "https://api.polygon.io"

#: Free-tier ceiling, measured rather than assumed: the fifth call inside a
#: minute returns 429. One is held back as headroom because the window is the
#: vendor's and not perfectly aligned with ours.
CALLS_PER_MINUTE = int(os.getenv("POLYGON_CALLS_PER_MINUTE", "4"))
WINDOW_S = 60.0

#: How far back the free tier actually serves, measured: asking for 2024-03-01
#: returned 2024-08-19. Recorded so callers stop asking for what cannot arrive.
FREE_TIER_HISTORY_DAYS = 730


class PolygonError(Exception):
    pass


#: Retries on a 429 before giving up. The vendor's minute window and ours are
#: never perfectly aligned, so an occasional collision is expected and waiting it
#: out is correct; what is not acceptable is recording the collision as data.
RATE_LIMIT_RETRIES = int(os.getenv("POLYGON_RATE_LIMIT_RETRIES", "4"))

_LIMIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_rate_limit (
    bucket   TEXT PRIMARY KEY,
    calls_at DOUBLE PRECISION[] NOT NULL DEFAULT '{}'
);
"""


class RateLimited(PolygonError):
    """The vendor refused for rate reasons.

    A distinct type on purpose: a caller building a dataset must be able to tell
    "the vendor was busy" from "this name has no history", and one exception for
    both forces it to guess — which is how a rate limit ends up recorded as a
    missing company.
    """


class _Throttle:
    """Blocks until a call is allowed, against a budget shared by every process.

    In-memory was simpler and was what we had. It is also wrong here: the limit
    belongs to the API KEY, not to a process, so two scripts each politely
    obeying four-a-minute together ask for eight and both are refused. The window
    lives in Postgres, serialised with FOR UPDATE, so the budget is counted where
    it actually applies.

    Falls back to in-memory when there is no database. A research script on a
    laptop without Postgres should still be throttled, just less precisely — an
    unavailable database must never mean an unthrottled client.
    """

    def __init__(self, calls: int = CALLS_PER_MINUTE, window_s: float = WINDOW_S):
        self._calls = max(1, calls)
        self._window = window_s
        self._times: list[float] = []
        self._lock = threading.Lock()
        self._pg_ready = False
        self._pg_broken = False

    def _ensure_pg(self) -> bool:
        if self._pg_broken:
            return False
        if self._pg_ready:
            return True
        try:
            import psycopg
            from app.fund.pgstore import dsn
            with psycopg.connect(dsn()) as conn:
                with conn.cursor() as cur:
                    cur.execute(_LIMIT_SCHEMA)
                    cur.execute("INSERT INTO fund_rate_limit (bucket) "
                                "VALUES ('polygon') ON CONFLICT DO NOTHING")
                conn.commit()
            self._pg_ready = True
            return True
        except Exception as e:  # noqa: BLE001
            logger.info("polygon throttle falling back to in-process: %s", e)
            self._pg_broken = True
            return False

    def _claim_pg(self):
        """Take a slot, or return the seconds to wait. None means claimed."""
        import psycopg
        from app.fund.pgstore import dsn
        # Wall clock, not monotonic: monotonic epochs differ per process, so a
        # shared window has to be measured on a clock everyone agrees about.
        now = time.time()
        with psycopg.connect(dsn()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT calls_at FROM fund_rate_limit "
                            "WHERE bucket = 'polygon' FOR UPDATE")
                row = cur.fetchone()
                recent = [t for t in (row[0] if row and row[0] else [])
                          if now - t < self._window]
                if len(recent) < self._calls:
                    recent.append(now)
                    cur.execute("UPDATE fund_rate_limit SET calls_at = %s "
                                "WHERE bucket = 'polygon'", (recent,))
                    conn.commit()
                    return None
                wait = self._window - (now - min(recent)) + 0.05
            conn.rollback()
        return max(0.05, wait)

    def wait(self) -> float:
        waited = 0.0
        if self._ensure_pg():
            while True:
                try:
                    sleep_for = self._claim_pg()
                except Exception as e:  # noqa: BLE001
                    logger.info("shared throttle unavailable mid-run (%s) — "
                                "continuing in-process", e)
                    self._pg_broken = True
                    break
                if sleep_for is None:
                    return waited
                time.sleep(sleep_for)
                waited += sleep_for
        while True:
            with self._lock:
                now = time.monotonic()
                self._times = [t for t in self._times if now - t < self._window]
                if len(self._times) < self._calls:
                    self._times.append(now)
                    return waited
                sleep_for = self._window - (now - self._times[0]) + 0.05
            time.sleep(max(0.05, sleep_for))
            waited += max(0.05, sleep_for)


_THROTTLE = _Throttle()


def api_key() -> Optional[str]:
    return os.getenv("POLYGON_API_KEY") or None


def available() -> bool:
    return bool(api_key())


def _read(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=45) as r:
        return json.loads(r.read())


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise PolygonError("POLYGON_API_KEY is not set")
    q = {k: v for k, v in params.items() if v is not None}
    q["apiKey"] = key
    query = urllib.parse.urlencode(q)
    waited = _THROTTLE.wait()
    if waited > 1:
        logger.info("polygon throttle held %.0fs before %s", waited, path)
    try:
        body = _read(f"{BASE}{path}?{query}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            # Wait it out rather than surface it. A 429 says nothing whatsoever
            # about the symbol, so letting it reach a caller that is building a
            # dataset invites the collision to be filed as "no history".
            body = None
            for attempt in range(1, RATE_LIMIT_RETRIES + 1):
                backoff = WINDOW_S / max(1, CALLS_PER_MINUTE) * attempt + 1.0
                logger.info("polygon 429 on %s — waiting %.0fs (attempt %d/%d)",
                            path, backoff, attempt, RATE_LIMIT_RETRIES)
                time.sleep(backoff)
                try:
                    _THROTTLE.wait()
                    body = _read(f"{BASE}{path}?{query}")
                    break
                except urllib.error.HTTPError as again:
                    if again.code != 429:
                        raise PolygonError(
                            f"polygon HTTP {again.code} on {path}") from again
                except Exception as again:  # noqa: BLE001
                    raise PolygonError(f"polygon unreachable: {again}") from again
            if body is None:
                raise RateLimited(
                    f"polygon still rate-limiting after {RATE_LIMIT_RETRIES} "
                    f"retries — a vendor budget problem, NOT a missing symbol; "
                    f"this must not be recorded as absent data") from e
        else:
            raise PolygonError(f"polygon HTTP {e.code} on {path}") from e
    except Exception as e:  # noqa: BLE001
        # Only a transport failure earns the fallback host. An HTTP error is a
        # real answer and retrying it elsewhere would spend a second call from a
        # five-per-minute budget to be told the same thing twice.
        try:
            body = _read(f"{FALLBACK_BASE}{path}?{query}")
            logger.info("polygon: %s unreachable (%s), served by %s",
                        BASE, e, FALLBACK_BASE)
        except Exception:  # noqa: BLE001
            raise PolygonError(f"polygon unreachable: {e}") from e
    if body.get("status") not in ("OK", "DELAYED", None):
        raise PolygonError(f"polygon status {body.get('status')}: "
                           f"{str(body.get('error'))[:200]}")
    return body


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def daily_bars(symbol: str, start: str, end: str,
               adjusted: bool = True) -> dict[str, Any]:
    """Adjusted daily OHLCV for an exact window.

    ``adjusted`` defaults True and should stay that way: an unadjusted series
    turns a split into a crash, so a backtest run on one measures the wrong
    thing entirely.

    Returns the window ACTUALLY served alongside the one requested. The free
    tier truncates silently at about two years, and a caller that assumes it got
    what it asked for will conclude a strategy had no history when in fact the
    data did.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        raise PolygonError("no symbol")
    body = _get(f"/v2/aggs/ticker/{sym}/range/1/day/{start}/{end}",
                {"adjusted": "true" if adjusted else "false",
                 "sort": "asc", "limit": 50_000})
    rows = body.get("results") or []
    out = {
        "symbol": sym,
        "source": "polygon",
        "adjusted": bool(body.get("adjusted", adjusted)),
        "adjustment": "splits_and_dividends" if adjusted else "none",
        "requested_window": [start, end],
        "dates": [_iso(r["t"]) for r in rows],
        "opens": [float(r["o"]) for r in rows],
        "highs": [float(r["h"]) for r in rows],
        "lows": [float(r["l"]) for r in rows],
        "closes": [float(r["c"]) for r in rows],
        "volumes": [float(r.get("v") or 0.0) for r in rows],
        #: Volume-weighted average price per bar — what trading the whole
        #: session would actually have paid, which is a better fill assumption
        #: than a close and is the number TCA wants to compare against.
        "vwaps": [float(r["vw"]) for r in rows if r.get("vw") is not None],
        "trades": [int(r.get("n") or 0) for r in rows],
    }
    out["served_window"] = ([out["dates"][0], out["dates"][-1]]
                            if out["dates"] else None)
    if out["dates"] and out["dates"][0] > start:
        out["truncated"] = (
            f"asked from {start}, served from {out['dates'][0]} — the free tier "
            f"holds roughly {FREE_TIER_HISTORY_DAYS} days, so anything earlier "
            f"is absent rather than empty")
    return out


def delisted(limit: int = 1000, cursor: Optional[str] = None,
             delisted_after: Optional[str] = None) -> dict[str, Any]:
    """Names that stopped trading — the only cure for survivorship bias.

    A universe measured today contains only the companies that made it. Backtests
    over such a universe are flattered by an amount nobody can state, and a
    hold-everything strategy is flattered MORE than a selective one, because
    selection at least had the chance to avoid the failures. This is how that
    stops being a caveat and becomes a number.
    """
    body = _get("/v3/reference/tickers",
                {"market": "stocks", "active": "false",
                 "limit": min(int(limit), 1000), "cursor": cursor,
                 "delisted_utc.gte": delisted_after, "sort": "ticker"})
    names = []
    for t in body.get("results") or []:
        names.append({
            "ticker": t.get("ticker"),
            "name": t.get("name"),
            "delisted_utc": t.get("delisted_utc"),
            "exchange": t.get("primary_exchange"),
            "type": t.get("type"),
        })
    nxt = body.get("next_url") or ""
    return {"names": names, "count": len(names),
            "next_cursor": (urllib.parse.parse_qs(
                urllib.parse.urlparse(nxt).query).get("cursor", [None])[0]
                if nxt else None)}
