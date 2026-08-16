"""Is the SYSTEM well? — the question the fund could not previously ask.

The harness has excellent checks on whether a NUMBER is honest and almost none
on whether the machinery producing it is healthy. Every operational failure
this month was found by tripping over it:

  * NAV took sixty seconds because a cache still pointed at a database the
    ledger had left. Found because an unrelated evaluation hung.
  * An allocation returned 500 and the event never reached the log, so a
    strategy silently kept its old weight. Found because someone read the
    response.
  * Firestore's daily quota ran out mid-afternoon and the scheduler stopped
    striking NAV. Found in a log tail, hours later.

Note what those have in common: the service was UP throughout. A liveness ping
would have returned 200 through every one of them. So these checks do the real
work and time it — a dependency is healthy when it can actually serve the
operation the fund needs, within the time the fund needs it.

Budgets are stated per check and deliberately generous. The point is not to
alarm on a slow second; it is that sixty seconds must be impossible to miss.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: What "too slow to be useful" means, per check. These are not SLAs, they are
#: the line past which something is wrong rather than busy. NAV's number is the
#: one that matters: Clark's tools time out at 20s, so a NAV slower than that
#: makes the fund unreachable to its own assistant while looking healthy.
BUDGETS_MS: dict[str, float] = {
    "event_store": 1_000.0,
    "chain": 5_000.0,
    "nav": 10_000.0,
    "market_data": 5_000.0,
    "venue": 5_000.0,
    "lean_engine": 10_000.0,
}


def _timed(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run a check, time it, and judge it against its budget.

    An exception is a failed check, never a failed request: a health endpoint
    that 500s tells the operator nothing except that the health endpoint is
    broken.
    """
    t0 = time.monotonic()
    try:
        out = fn() or {}
        ok = out.pop("ok", True)
        detail = out
        err = None
    except Exception as e:  # noqa: BLE001
        ok, detail, err = False, {}, f"{type(e).__name__}: {e}"[:300]
    ms = round((time.monotonic() - t0) * 1000, 1)
    budget = BUDGETS_MS.get(name)
    over = budget is not None and ms > budget
    return {
        "check": name,
        "ok": bool(ok) and not over,
        "latency_ms": ms,
        "budget_ms": budget,
        "over_budget": over,
        "error": err,
        **detail,
        **({"note": f"took {ms:.0f}ms against a {budget:.0f}ms budget — the "
                    f"dependency answers, but too slowly to be useful"}
           if over else {}),
    }


# --- the checks ------------------------------------------------------------
# Each one performs the real operation. A ping would have passed through every
# outage this month.

def check_event_store() -> dict[str, Any]:
    """Can we read the log at all, and how many events are in it?"""
    from app.fund.events import EventStore, store_backend
    store = EventStore()
    rows = store.stream(since_seq=0, limit=1)
    return {"backend": store_backend(),
            "reachable": True,
            "has_events": bool(rows)}


def check_chain() -> dict[str, Any]:
    """Does the tamper evidence still hold? A break is not a slow day."""
    from app.fund.events import EventStore
    v = EventStore().verify_chain()
    return {"ok": bool(v.get("ok")),
            "checked": v.get("checked"), "chained": v.get("chained"),
            "first_break": v.get("first_break")}


def check_nav(nav_service: Any = None) -> dict[str, Any]:
    """FOLD the book, do not read a cached number.

    This is the check that would have caught the sixty-second NAV, and it only
    works because it does the expensive thing rather than asking whether the
    expensive thing is available.
    """
    if nav_service is None:
        return {"ok": False, "skipped": "no nav service wired"}
    snap = nav_service.compute()
    return {"ok": snap.total_nav_usd is not None,
            "nav_usd": float(snap.total_nav_usd),
            "positions": len(snap.positions or [])}


def check_market_data(symbol: str = "SPY") -> dict[str, Any]:
    """Can we price anything? A stale mark is worse than a missing one."""
    from app.fund.quotes import quote
    q = quote(symbol)
    return {"ok": bool(q.get("ok")) and q.get("price") is not None,
            "symbol": symbol, "price": q.get("price"),
            "stale": q.get("stale")}


def check_venue(connector: Any = None) -> dict[str, Any]:
    """Is the broker reachable, and does it agree it is configured?"""
    if connector is None:
        return {"ok": False, "skipped": "no connector wired"}
    info = connector.account_info() if hasattr(connector, "account_info") else {}
    return {"ok": bool(info.get("configured", True)),
            "venue": type(connector).__name__,
            "configured": info.get("configured")}


def check_lean_engine(runner: Any = None) -> dict[str, Any]:
    """Is the engine's Docker actually there?

    Listing algorithms touches the filesystem only, so this reports whether the
    workspace is intact. Docker itself is checked by asking it for its version
    rather than by running a backtest, because a health check that costs ten
    seconds of engine time is one nobody will call.
    """
    import subprocess
    out = {"algorithms": None, "docker": None}
    if runner is not None:
        try:
            out["algorithms"] = len(runner.list_algorithms())
        except Exception as e:  # noqa: BLE001
            out["algorithms_error"] = str(e)[:200]
    try:
        p = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                           capture_output=True, text=True, timeout=15)
        out["docker"] = (p.stdout or "").strip() or None
        out["ok"] = p.returncode == 0
    except Exception as e:  # noqa: BLE001
        out["ok"] = False
        out["docker_error"] = f"{type(e).__name__}: {e}"[:200]
    return out


def report(nav_service: Any = None, connector: Any = None,
           runner: Any = None) -> dict[str, Any]:
    """Every check, with latencies, and one verdict.

    Degraded is a distinct state from down, deliberately. A fund whose venue is
    unreachable can still value its book and answer questions; one whose event
    store is gone cannot do anything at all, and collapsing both into "unhealthy"
    would mean an operator learns nothing from the word.
    """
    checks = [
        _timed("event_store", check_event_store),
        _timed("chain", check_chain),
        _timed("nav", lambda: check_nav(nav_service)),
        _timed("market_data", lambda: check_market_data()),
        _timed("venue", lambda: check_venue(connector)),
        _timed("lean_engine", lambda: check_lean_engine(runner)),
    ]
    critical = {"event_store", "chain", "nav"}
    failed = [c["check"] for c in checks if not c["ok"]]
    critical_failed = [c for c in failed if c in critical]
    slow = [c["check"] for c in checks if c.get("over_budget")]

    status = ("down" if critical_failed else
              "degraded" if failed else "ok")
    return {
        "status": status,
        "failed": failed,
        "slow": slow,
        "summary": (
            f"critical checks failing: {', '.join(critical_failed)}"
            if critical_failed else
            f"degraded — {', '.join(failed)} unavailable, the book is still "
            f"valuable and readable" if failed else
            f"all checks within budget"),
        "checks": checks,
    }
