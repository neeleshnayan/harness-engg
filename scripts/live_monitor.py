"""Continuous read-only watch over the live session.

Runs while the market is open and answers, on a fixed cadence, the only three
questions that matter during a live test:

  1. Is the platform up and are its endpoints healthy? (latency, error rate)
  2. Does our ledger agree with Alpaca? (positions, cash, open orders)
  3. Is NAV — which is folded from the event log, never copied from the broker —
     tracking broker equity, and if not, by how much?

It places nothing, cancels nothing and writes no fund events. Output goes to
stdout and to a JSONL file so the session can be reviewed afterwards.

Divergence is reported, never repaired. Repair is `scripts/reconcile_broker.py`,
which is a separate, deliberate, dry-run-first act.

    python scripts/live_monitor.py --interval 120 --out logs/live_session.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "http://127.0.0.1:8090/api/v1/fund"

#: Endpoints polled every tick, with the budget above which we call them slow.
#: These are the ones a human actually waits on.
WATCHED = [
    ("/book", 1.0),
    ("/nav", 3.0),
    ("/risk/monitor", 5.0),
    ("/orders/history?limit=50", 3.0),
    ("/rebalance/pending", 3.0),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(path: str, timeout: float = 30.0):
    t0 = time.monotonic()
    req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
        return {"ok": True, "status": r.status, "ms": (time.monotonic() - t0) * 1000, "body": body}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "ms": (time.monotonic() - t0) * 1000,
                "error": e.read().decode()[:200]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": None, "ms": (time.monotonic() - t0) * 1000,
                "error": f"{type(e).__name__}: {e}"}


def broker_snapshot():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
        if not (key and secret):
            return {"ok": False, "error": "no credentials"}
        c = TradingClient(key, secret, paper=True)
        acct, clock = c.get_account(), c.get_clock()
        orders = c.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100))
        open_o = [o for o in orders
                  if o.status.value in ("new", "accepted", "partially_filled",
                                        "pending_new", "held")]
        return {
            "ok": True,
            "market_open": bool(clock.is_open),
            "equity": float(acct.equity),
            "cash": float(acct.cash),
            "positions": {p.symbol.upper(): float(p.qty) for p in c.get_all_positions()},
            "open_orders": [
                {"symbol": o.symbol, "side": o.side.value, "qty": str(o.qty),
                 "status": o.status.value, "filled": str(o.filled_qty)}
                for o in open_o
            ],
            "filled_today": sum(
                1 for o in orders
                if o.status.value == "filled"
                and str(o.submitted_at)[:10] == datetime.now().strftime("%Y-%m-%d")
            ),
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def tick() -> dict:
    rec: dict = {"ts": now(), "endpoints": {}, "issues": []}

    for path, budget in WATCHED:
        r = get(path)
        rec["endpoints"][path] = {"ok": r["ok"], "status": r["status"], "ms": round(r["ms"], 1)}
        if not r["ok"]:
            rec["issues"].append(f"{path} FAILED ({r.get('status')}) {r.get('error','')[:120]}")
        elif r["ms"] > budget * 1000:
            rec["issues"].append(f"{path} slow: {r['ms']/1000:.1f}s (budget {budget:.0f}s)")

    book = get("/book")
    nav = get("/nav")
    risk = get("/risk/monitor")
    orders = get("/orders/history?limit=50")

    if book["ok"]:
        b = book["body"]
        rec["venue"] = b.get("venue")
        rec["orders_are_real"] = b.get("orders_are_real")
        rec["env"] = b.get("env")

    ours: dict[str, float] = {}
    if nav["ok"]:
        live = nav["body"].get("live") or {}
        rec["nav_usd"] = live.get("total_nav_usd")
        rec["cash_usd"] = (live.get("breakdown") or {}).get("cash")
        ours = {p["symbol"].upper(): float(p["qty"]) for p in (live.get("positions") or [])}
        rec["n_positions"] = len(ours)

    if risk["ok"]:
        m = risk["body"]
        rec["halted"] = m.get("halted")
        rec["gross_exposure_pct"] = m.get("gross_exposure_pct")
        rec["drawdown_pct"] = (m.get("drawdown") or {}).get("drawdown_pct")
        alarms = m.get("alarms") or []
        rec["alarms"] = [a.get("key") for a in alarms]
        for a in alarms:
            if a.get("severity") in ("warn", "critical"):
                rec["issues"].append(f"ALARM[{a['severity']}] {a.get('message','')[:140]}")
        if m.get("unpriced_symbols"):
            rec["issues"].append(f"UNPRICED: {', '.join(m['unpriced_symbols'])}")
        if m.get("stale_marks"):
            rec["issues"].append(f"STALE MARKS: {m['stale_marks']}")

    if orders["ok"]:
        rows = orders["body"].get("orders") or []
        in_flight = [o for o in rows if o.get("status") in
                     ("pending", "approved", "working", "partial")]
        rec["orders_total"] = len(rows)
        rec["orders_in_flight"] = len(in_flight)
        for o in in_flight:
            rec["issues"].append(
                f"IN FLIGHT {o.get('side')} {o.get('qty')} {o.get('symbol')} "
                f"status={o.get('status')} filled={o.get('filled_qty')}"
            )

    b = broker_snapshot()
    rec["broker"] = {k: v for k, v in b.items() if k != "positions"}
    if b.get("ok"):
        rec["market_open"] = b["market_open"]
        theirs = b["positions"]
        # Position-level alignment — the question the whole session is testing.
        diffs = []
        for sym in sorted(set(ours) | set(theirs)):
            a, t = ours.get(sym, 0.0), theirs.get(sym, 0.0)
            if abs(a - t) > 1e-6:
                diffs.append({"symbol": sym, "ledger": a, "broker": t, "delta": round(a - t, 6)})
        rec["position_diffs"] = diffs
        if diffs:
            rec["issues"].append(
                "LEDGER/BROKER POSITION MISMATCH: "
                + ", ".join(f"{d['symbol']} ours={d['ledger']} theirs={d['broker']}" for d in diffs)
            )
        if rec.get("nav_usd") is not None:
            drift = float(rec["nav_usd"]) - b["equity"]
            rec["nav_vs_equity_drift"] = round(drift, 2)
            # $1 of drift on a $2k book is 5bp — worth a look, not an alarm.
            if abs(drift) > 1.0:
                rec["issues"].append(
                    f"NAV ${rec['nav_usd']:,.2f} vs broker equity ${b['equity']:,.2f} "
                    f"(drift ${drift:,.2f}). NAV is NEVER overwritten from the broker — "
                    "investigate with reconcile_broker.py, dry run first."
                )
        if b["open_orders"]:
            rec["issues"].append(
                f"{len(b['open_orders'])} OPEN ORDER(S) AT VENUE: "
                + ", ".join(f"{o['side']} {o['qty']} {o['symbol']} ({o['status']})"
                            for o in b["open_orders"])
            )
    return rec


def render(rec: dict) -> str:
    head = (f"[{rec['ts']}] "
            f"{'OPEN' if rec.get('market_open') else 'closed'} · "
            f"venue={rec.get('venue')} real={rec.get('orders_are_real')} · "
            f"NAV ${rec.get('nav_usd') or 0:,.2f} vs equity ${(rec.get('broker') or {}).get('equity') or 0:,.2f} "
            f"(drift ${rec.get('nav_vs_equity_drift', 0):,.2f}) · "
            f"{rec.get('n_positions', 0)} pos · "
            f"halted={rec.get('halted')}")
    lat = "  ".join(f"{p.split('?')[0]}={v['ms']:.0f}ms{'' if v['ok'] else '!'}"
                    for p, v in (rec.get("endpoints") or {}).items())
    lines = [head, f"    {lat}"]
    for i in rec.get("issues", []):
        lines.append(f"    ! {i}")
    if not rec.get("issues"):
        lines.append("    aligned, no issues")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=120, help="seconds between ticks")
    ap.add_argument("--minutes", type=int, default=0, help="stop after N minutes (0 = forever)")
    ap.add_argument("--out", default="logs/live_session.jsonl")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    deadline = time.monotonic() + args.minutes * 60 if args.minutes else None
    print(f"live monitor: every {args.interval}s -> {args.out}  (read-only)", flush=True)

    while True:
        rec = tick()
        print(render(rec), flush=True)
        with open(args.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        if deadline and time.monotonic() >= deadline:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
