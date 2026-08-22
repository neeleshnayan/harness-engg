"""Prepare a book for live-flow testing against the real Alpaca venue.

Funds the book, sets the mandate, and registers the three strategies with their
universes and backtests — and then stops. It places **no orders**, deliberately:
order flow is the thing being tested, so it has to go through the real path
(Allocate → Rebalance → propose → risk gate → approve), not be manufactured by a
script.

Intended startup:

    ./scripts/run.sh        # FUND_MODE=alpaca-paper

One switch, both dimensions. The three-flag incantation this line used to carry
(USE_FAKE_FIRESTORE=1 FUND_REAL_BROKER=1 ...) described a state the fund can no
longer be in: a LOCAL ledger with REAL orders. That split was the point of the
old flags and it is exactly what the mode design forbids — a book whose events
and whose fills disagree about which fund they belong to is how the alpaca-paper
account and the fund's own ledger came to record two different funds.

Refuses to run if orders are NOT real — for a simulated venue the normal
mock_seed.py is the right tool.
"""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1/fund"

CAPITAL = 2000.0

LIMITS = {
    "min_cash_pct": 0.05,
    "max_position_pct": 0.20,
    "max_order_notional_pct": 0.15,
    "max_strategy_pct": 0.40,
    "max_drawdown_pct": 0.10,
    "max_daily_loss_pct": 0.04,
    "underwater_pct": 0.15,
    "min_effective_bets": 2.0,
    "max_avg_correlation": 0.75,
    "max_strategy_correlation": 0.90,
    "max_risk_concentration_pct": 0.50,
    "max_expected_shortfall_pct": 0.05,
}

STRATEGIES = [
    {"name": "Momentum — Large Cap Tech",
     "definition": {"type": "sma", "fast": 10, "slow": 30},
     "assets": ["AAPL", "MSFT", "NVDA"], "backtest": "AAPL", "target": 25.0},
    {"name": "Mean Reversion — Cyclicals",
     "definition": {"type": "rsi", "period": 14, "low": 30, "high": 70},
     "assets": ["F", "INTC", "SOFI"], "backtest": "INTC", "target": 25.0},
    {"name": "Trend — Sector & Commodity",
     "definition": {"type": "macd", "fast": 12, "slow": 26, "signal": 9},
     "assets": ["SPY", "XLE", "GLD"], "backtest": "SPY", "target": 25.0},
]


def call(method, path, body=None, timeout=240):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:300]}


def must(res, what):
    if isinstance(res, dict) and res.get("_error"):
        print(f"FAILED {what}: HTTP {res['_error']} {res.get('_body','')}")
        raise SystemExit(1)
    return res


def main() -> int:
    book = call("GET", "/book")
    if book.get("_error"):
        print("spine unreachable:", book)
        return 1
    if not book.get("orders_are_real"):
        print(f"REFUSING: this spine does not route orders to the real broker "
              f"(venue={book.get('venue')!r}). Start it with FUND_REAL_BROKER=1, "
              "or use mock_seed.py for a simulated venue.")
        return 1
    if book.get("is_production"):
        print("REFUSING: this is the PRODUCTION ledger. This script is for a local "
              "ledger paired with the paper venue.")
        return 1

    nav_now = (call("GET", "/nav").get("live") or {}).get("total_nav_usd") or 0
    if float(nav_now) > 0:
        print(f"REFUSING: book already has NAV ${float(nav_now):,.2f}. Restart the "
              "spine with a cleared .firestore_local_db.json first.")
        return 1

    print(f"local ledger: {book.get('project_id')} / {book.get('env')}  "
          f"→ venue {book.get('venue')} (REAL ORDERS)\n")

    must(call("POST", "/risk/limits", {"patch": LIMITS, "actor": "vishesh"}), "limits")
    print(f"  limits set — cash floor {LIMITS['min_cash_pct']:.0%}, "
          f"drawdown halt {LIMITS['max_drawdown_pct']:.0%}")

    sub = must(call("POST", "/lp/subscriptions",
                    {"lp_id": "rushi", "lp_name": "Rushi",
                     "usd_amount": CAPITAL, "actor": "operator"}), "subscribe")
    must(call("POST", f"/lp/subscriptions/{sub['subscription_id']}/confirm",
              {"actor": "operator"}), "confirm cash")
    print(f"  funded ${CAPITAL:,.0f} — matches the broker's $2,000 paper account\n")

    for spec in STRATEGIES:
        st = call("POST", "/strategies", {"name": spec["name"], "actor": "rushi",
                                          "definition": spec["definition"]})
        sid = st.get("strategy_id")
        if not sid:
            print("  could not create", spec["name"], st)
            return 1
        call("POST", f"/strategies/{sid}/assets",
             {"symbols": spec["assets"], "actor": "rushi"})
        bt = call("POST", f"/strategies/{sid}/backtest/by_symbol",
                  {"symbol": spec["backtest"], "lookback_days": 365})
        call("POST", f"/strategies/{sid}/state", {"state": "deployed", "actor": "rushi"})
        call("POST", f"/strategies/{sid}/allocation",
             {"target_pct": spec["target"], "actor": "rushi"})
        line = ""
        if "result" in bt:
            r = bt["result"]
            line = f"  backtest {spec['backtest']}: {r['total_return']*100:+.1f}% sharpe {r['sharpe']:.2f}"
        print(f"{spec['name']}  ({sid[:8]}) — {', '.join(spec['assets'])} @ {spec['target']}%")
        if line:
            print(line)

    call("POST", "/nav/strike", {"actor": "system"})
    nav = call("GET", "/nav").get("live", {})
    print(f"\n  NAV ${nav.get('total_nav_usd'):,.2f} · "
          f"cash ${(nav.get('breakdown') or {}).get('cash', 0):,.2f} · "
          f"{len(nav.get('positions') or [])} positions · 0 orders placed")
    print("\n  NEXT: open Allocate → Rebalance → Compose a plan. Targets are already")
    print("  set at 25/25/25, so move one and propose. Approving it places REAL")
    print("  orders on Alpaca, which is the flow being tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
