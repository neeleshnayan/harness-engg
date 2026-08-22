"""Candidate-scoped bar snapshots — one fetch per leg, one instant, for a whole candidate.

WHY THIS EXISTS, MEASURED (quant run-quant-entry20, 2026-08-22; re-measured by
the builder against the live spine 2026-08-22):

    GET /fund/marketdata/bars?symbol=SPY&lookback_days=2000&format=csv
        -> 200, 24,702 bytes, 1.94s / 1.98s / 1.91s on three consecutive calls

Two seconds for twenty-four kilobytes, and the second identical call is no
faster than the first: the cost is the vendor round trip on the server side,
not the network and not the container. A 170-name candidate runs 22 containers
(5 sweeps x [3 slip points + 1 holdout leg] + verification + probes) and EVERY
container re-fetches EVERY leg, so ~85% of the belt's wall clock is spent
re-downloading bytes the harness already had.

WHAT THIS MODULE DOES, AND WHY IT IS A SNAPSHOT RATHER THAN A CACHE:

A cache would make the belt faster. A SNAPSHOT also makes it CORRECT, and that
is the larger prize. Two live defects come from the belt fetching per container:

  * WALL-CLOCK DRIFT (ticket 0178d2e8). ``lookback_days=N`` with no end date
    means "N days back from whenever you happen to ask". Containers of one
    candidate ask at different minutes, so they can cover different windows, and
    a re-run of an identical specification moved the benchmark 0.80pp for no
    reason connected to the strategy.
  * TRANSIENT LEG TRUNCATION (leanrunner.py:1289). The benchmark truncates every
    leg to the SHORTEST one. A single leg that transiently returns a short
    series silently shortens the window the benchmark return is computed over —
    which cost 11.85pp on Entry 20.

Both are the same disease: the belt asks the world the same question many times
and quietly accepts different answers. So this module asks ONCE, at one instant,
and every consumer of that candidate is served from the same pinned bytes.

THE DESIGN RULE THAT MAKES THAT TRUE: one pinned SERIES per symbol, and every
differently-shaped request is answered by SLICING it. The container asks for a
trailing ``lookback_days`` window; the benchmark asks for an explicit
``start``/``end`` window; both are served from the same leg. That is what lets
the harness say the strategy and its benchmark ran on identical closes rather
than merely hoping so.

FAIL OPEN AND LOUD. A request this snapshot cannot satisfy is a MISS: the caller
falls through to the ordinary live fetch, the miss is logged naming the leg, AND
it is recorded on the snapshot so it can be reported with the candidate. A
silent difference in data path between two containers of one candidate is the
thing this module exists to prevent, so a miss is never allowed to be quiet.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: it does not wrap
``marketdata.fetch_daily_bars``. Nothing is served from a snapshot unless the
call site explicitly asks. That boundary is load-bearing — the fund's marks,
NAV, risk engine, stress and correlation all call ``fetch_daily_bars``
IN-PROCESS, and none of them may ever be handed a pinned bar. The consult sites
are exactly three and all three are belt-side: the HTTP bars endpoint (which
only LEAN containers and offline scripts use), the benchmark leg, and the
capacity estimate. ``tests/test_barcache.py`` pins that list.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: Parallel fetch width for a prefetch. MEASURED on this host 2026-08-22 against
#: the live spine — 10 symbols, wall clock for the whole prefetch, two reps in
#: descending order to keep warm-up from flattering the wide settings:
#:
#:     workers=1  -> 20.0s, 19.5s        workers=8  -> 4.3s, 4.2s
#:     workers=4  ->  6.2s,  7.2s        workers=16 -> 4.9s, 2.7s
#:
#: 16 has the better median and visibly worse variance; 8 is flat. The honest
#: reading is that the knee is at 8 and everything past it is bounded by the
#: vendor rather than by this host — 24 threads at 11% CPU are not what is
#: costing here, so widening further buys ~1.5s on a prefetch that happens ONCE
#: per candidate against a ~96-minute belt. That is immaterial, and it is bought
#: by doubling concurrent load on a free-tier API the fund ALSO marks its book
#: against. So: 8, for stability and for being a polite client, with the faster
#: setting recorded above rather than hidden — if a future candidate's universe
#: is large enough that prefetch wall clock starts mattering, the number to try
#: is 16 and the measurement is already here.
DEFAULT_WORKERS = 8

#: How long a snapshot may serve after it was taken. A snapshot is meant to live
#: exactly as long as one candidate; this bound exists for the case where an
#: activation LEAKS (an exception path that skips deactivation, a thread that
#: outlives its factory). Past it every request misses and falls through to a
#: live fetch — the safe direction, because stale bars that keep being served
#: are indistinguishable from fresh ones to the caller.
MAX_AGE_S = 6 * 3600.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SnapshotLeg:
    """One symbol's pinned series, fetched once."""

    symbol: str
    dates: list[str]
    closes: list[float]
    source: str
    #: The request shape this leg was fetched with, kept so a later request can
    #: be checked against what was actually asked for rather than assumed.
    lookback_days: Optional[int] = None
    start: Optional[str] = None
    end: Optional[str] = None
    volumes: Optional[list[float]] = None

    @property
    def first(self) -> Optional[str]:
        return self.dates[0] if self.dates else None

    @property
    def last(self) -> Optional[str]:
        return self.dates[-1] if self.dates else None


@dataclass
class BarSnapshot:
    """Every leg a candidate needs, pinned at one instant.

    ``taken_at`` is the whole point: it replaces the wall clock as the reference
    for a trailing ``lookback_days`` window, which is what makes two containers
    of the same candidate cover the same window by construction rather than by
    luck.
    """

    candidate: str
    taken_at: datetime = field(default_factory=_now)
    legs: dict[str, SnapshotLeg] = field(default_factory=dict)
    #: Every request this snapshot could not satisfy, in order. Reported with
    #: the candidate — a miss means one container read a different data path
    #: from its siblings, and that must be visible, not merely logged.
    misses: list[dict[str, Any]] = field(default_factory=list)
    hits: int = 0
    #: Wall seconds the prefetch itself took, for the before/after record.
    prefetch_seconds: Optional[float] = None
    #: Legs that were ASKED for and could not be fetched at all. Distinct from a
    #: miss: absent, not merely unmatched. Absence is never zero.
    unavailable: dict[str, str] = field(default_factory=dict)

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False,
                                  compare=False)

    # --- serving -----------------------------------------------------------

    def age_s(self) -> float:
        return (_now() - self.taken_at).total_seconds()

    def expired(self, max_age_s: float = MAX_AGE_S) -> bool:
        return self.age_s() > max_age_s

    def serve(self, symbol: str, lookback_days: Optional[int] = None,
              start: Optional[str] = None,
              end: Optional[str] = None) -> Optional[SnapshotLeg]:
        """The pinned series for this request, or None if it cannot be served.

        A request is served only when the pinned leg DEMONSTRABLY COVERS it.
        Serving a request the leg only partly covers would hand the caller a
        truncated series that looks complete — which is precisely the Entry 20
        defect (leanrunner.py:1289) arrived at from the other side. So a partial
        overlap is a MISS and the caller falls through to a live fetch.
        """
        sym = (symbol or "").strip().upper()
        leg = self.legs.get(sym)
        if leg is None or not leg.dates:
            self._miss(sym, lookback_days, start, end, "no pinned leg for this symbol")
            return None
        if self.expired():
            self._miss(sym, lookback_days, start, end,
                       f"snapshot is {self.age_s():.0f}s old, past the {MAX_AGE_S:.0f}s bound")
            return None

        if start is None and end is None:
            # THE CONTAINER'S REQUEST, and the one that must be byte-identical.
            #
            # A trailing-lookback request is served ONLY when it is the exact
            # question this leg was fetched with — in which case the leg IS the
            # answer and is returned whole. It is deliberately NOT re-sliced to
            # "N days before taken_at": vendors do not interpret a lookback as a
            # calendar cut, and doing that arithmetic here made a pinned SPY leg
            # return 1,377 bars from 2021-03-01 where the direct fetch returns
            # 2,000 from 2018-09-06. That is a truncation invented by the cache,
            # which is the Entry 20 defect wearing this module's clothes, so the
            # arithmetic is gone rather than corrected.
            #
            # A DIFFERENT lookback is a miss, not an approximation. The caller
            # falls through to a live fetch and gets exactly what it asked for.
            if leg.lookback_days is None or int(lookback_days or 0) != int(leg.lookback_days):
                self._miss(sym, lookback_days, start, end,
                           f"asked for lookback_days={lookback_days}, leg pinned "
                           f"at {leg.lookback_days} — served live rather than "
                           f"approximated")
                return None
            with self._lock:
                self.hits += 1
            return SnapshotLeg(
                symbol=leg.symbol, dates=list(leg.dates), closes=list(leg.closes),
                source=leg.source, lookback_days=leg.lookback_days,
                volumes=(list(leg.volumes) if leg.volumes else None),
            )

        # An explicit window (the benchmark leg). Served by slicing the pinned
        # series, which is what makes the strategy and its bar provably the same
        # closes rather than two vendor calls that agree by assumption.
        lo, hi = start, end

        dates, closes = leg.dates, leg.closes
        if lo is not None and lo > (leg.first or ""):
            # Fine: the window starts inside the pinned leg.
            pass
        elif lo is not None and lo < (leg.first or ""):
            # The caller wants history from before this leg begins. The leg may
            # still be complete (the vendor may simply not go back that far),
            # but this snapshot cannot PROVE that, and a snapshot that guesses
            # is worse than one that declines. Fall through to a live fetch.
            self._miss(sym, lookback_days, start, end,
                       f"window starts {lo}, pinned leg starts {leg.first}")
            return None
        if hi is not None and hi > (leg.last or ""):
            self._miss(sym, lookback_days, start, end,
                       f"window ends {hi}, pinned leg ends {leg.last}")
            return None

        i0 = 0 if lo is None else _bisect_left(dates, lo)
        i1 = len(dates) if hi is None else _bisect_right(dates, hi)
        if i1 <= i0:
            self._miss(sym, lookback_days, start, end, "window selects no bars")
            return None
        with self._lock:
            self.hits += 1
        return SnapshotLeg(
            symbol=leg.symbol, dates=dates[i0:i1], closes=closes[i0:i1],
            source=leg.source, lookback_days=lookback_days, start=start, end=end,
            volumes=(leg.volumes[i0:i1] if leg.volumes else None),
        )

    def _miss(self, symbol: str, lookback_days, start, end, why: str) -> None:
        rec = {"symbol": symbol, "lookback_days": lookback_days,
               "start": start, "end": end, "why": why,
               "at": _now().isoformat()}
        with self._lock:
            self.misses.append(rec)
        # Loud by requirement: a miss means this container read a different data
        # path from its siblings, and the leg is named so it can be chased.
        logger.warning(
            "bar snapshot MISS for candidate %s leg %s (%s) — falling back to a "
            "live fetch; this container's bars may differ from its siblings'",
            self.candidate, symbol, why)

    # --- reporting ---------------------------------------------------------

    def report(self) -> dict[str, Any]:
        """What the candidate should carry about its own data path."""
        return {
            "candidate": self.candidate,
            "taken_at": self.taken_at.isoformat(),
            "legs": sorted(self.legs),
            "leg_count": len(self.legs),
            "hits": self.hits,
            "miss_count": len(self.misses),
            "misses": list(self.misses),
            "unavailable": dict(self.unavailable),
            "prefetch_seconds": self.prefetch_seconds,
            # Stated as a sentence because the interesting case is the one a
            # reader would otherwise have to infer from two zeroes.
            "uniform_data_path": (not self.misses) and (not self.unavailable),
        }

    # --- checkpointing -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "taken_at": self.taken_at.isoformat(),
            "prefetch_seconds": self.prefetch_seconds,
            "unavailable": dict(self.unavailable),
            "legs": {s: {"symbol": l.symbol, "dates": l.dates, "closes": l.closes,
                         "source": l.source, "lookback_days": l.lookback_days,
                         "start": l.start, "end": l.end, "volumes": l.volumes}
                     for s, l in self.legs.items()},
        }

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "BarSnapshot":
        snap = cls(candidate=doc.get("candidate") or "unknown")
        raw = doc.get("taken_at")
        if raw:
            snap.taken_at = datetime.fromisoformat(raw)
        snap.prefetch_seconds = doc.get("prefetch_seconds")
        snap.unavailable = dict(doc.get("unavailable") or {})
        for sym, l in (doc.get("legs") or {}).items():
            snap.legs[sym] = SnapshotLeg(
                symbol=l.get("symbol") or sym, dates=list(l.get("dates") or []),
                closes=list(l.get("closes") or []), source=l.get("source") or "unknown",
                lookback_days=l.get("lookback_days"), start=l.get("start"),
                end=l.get("end"), volumes=l.get("volumes"))
        return snap

    def save(self, path: Path) -> Path:
        """Checkpoint to disk. A dispatch that dies keeps what it already paid for."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict()), encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path) -> "BarSnapshot":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _bisect_left(dates: list[str], value: str) -> int:
    import bisect
    return bisect.bisect_left(dates, value)


def _bisect_right(dates: list[str], value: str) -> int:
    import bisect
    return bisect.bisect_right(dates, value)


# --- prefetch ---------------------------------------------------------------


def prefetch(symbols: list[str], candidate: str = "adhoc",
             lookback_days: int = 2000,
             workers: int = DEFAULT_WORKERS,
             fetcher: Optional[Callable[..., Any]] = None) -> BarSnapshot:
    """Fetch every leg ONCE, in parallel, and pin them at one instant.

    ``fetcher`` is injectable for tests only; production passes nothing and gets
    ``marketdata.fetch_daily_bars``.

    A leg that cannot be fetched is recorded in ``unavailable`` rather than
    omitted silently — a candidate whose universe partly failed to load must be
    able to say so, because the alternative is a benchmark quietly built from
    the names that happened to work.
    """
    if fetcher is None:
        from app.fund.marketdata import fetch_daily_bars as fetcher  # noqa: N806

    wanted = sorted({(s or "").strip().upper() for s in symbols if (s or "").strip()})
    snap = BarSnapshot(candidate=candidate)
    if not wanted:
        snap.prefetch_seconds = 0.0
        return snap

    t0 = time.monotonic()

    def _one(sym: str):
        try:
            return sym, fetcher(sym, lookback_days=lookback_days), None
        except Exception as e:  # noqa: BLE001
            return sym, None, f"{type(e).__name__}: {e}"[:200]

    width = max(1, min(int(workers), len(wanted)))
    with ThreadPoolExecutor(max_workers=width) as pool:
        for sym, bars, err in pool.map(_one, wanted):
            if err is not None or bars is None:
                snap.unavailable[sym] = err or "fetch returned nothing"
                logger.warning("snapshot leg unavailable for %s: %s", sym, err)
                continue
            dates = list(getattr(bars, "dates", None) or [])
            closes = list(getattr(bars, "closes", None) or [])
            if not dates or len(dates) != len(closes):
                # A leg whose dates and closes disagree is not a series. Refusing
                # it is the honest move: every consumer below zips them.
                snap.unavailable[sym] = (
                    f"{len(dates)} dates against {len(closes)} closes — not a series")
                logger.warning("snapshot leg malformed for %s: %s", sym,
                               snap.unavailable[sym])
                continue
            snap.legs[sym] = SnapshotLeg(
                symbol=getattr(bars, "symbol", sym) or sym,
                dates=dates, closes=closes,
                source=getattr(bars, "source", None) or "unknown",
                lookback_days=lookback_days,
                volumes=(list(getattr(bars, "volumes", None) or []) or None),
            )
    snap.prefetch_seconds = round(time.monotonic() - t0, 2)
    logger.info("bar snapshot for candidate %s: %d legs in %.1fs (%d unavailable)",
                candidate, len(snap.legs), snap.prefetch_seconds,
                len(snap.unavailable))
    return snap


# --- activation -------------------------------------------------------------
#
# PROCESS-GLOBAL AND DELIBERATELY SO. A candidate's work is spread across
# threads that the factory does not own: the sweep's worker pool, the engine
# slot threads in leanrunner, and FastAPI's threadpool serving the container's
# HTTP fetch. A thread-local would be invisible to every one of them, which
# would make this module a cache that never hits.
#
# The safety does NOT come from the scope being narrow. It comes from the
# consult sites being few and named: nothing reads a snapshot unless it asked.

_ACTIVE: Optional[BarSnapshot] = None
_ACTIVE_LOCK = threading.Lock()


def active() -> Optional[BarSnapshot]:
    return _ACTIVE


class activate:
    """Make ``snap`` the active snapshot for the duration of a block.

    Re-entrant only in the sense that it restores whatever was active before,
    so a nested candidate cannot silently un-pin its parent.
    """

    def __init__(self, snap: Optional[BarSnapshot]):
        self._snap = snap
        self._prev: Optional[BarSnapshot] = None

    def __enter__(self) -> Optional[BarSnapshot]:
        global _ACTIVE
        with _ACTIVE_LOCK:
            self._prev = _ACTIVE
            _ACTIVE = self._snap
        return self._snap

    def __exit__(self, *exc) -> None:
        global _ACTIVE
        with _ACTIVE_LOCK:
            _ACTIVE = self._prev
        return None


def serve(symbol: str, lookback_days: Optional[int] = None,
          start: Optional[str] = None,
          end: Optional[str] = None) -> Optional[SnapshotLeg]:
    """The one function belt-side call sites use.

    Returns None whenever there is no active snapshot, which is the ordinary
    case for every non-belt caller — so a call site that consults this is a
    no-op outside a candidate rather than a behaviour change.
    """
    snap = _ACTIVE
    if snap is None:
        return None
    return snap.serve(symbol, lookback_days=lookback_days, start=start, end=end)
