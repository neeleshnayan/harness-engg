"""Seed the in-memory mock book: fake transactions, real market prices.

Mock mode is for exercising the product when the real ledger is unavailable or
when you simply do not want to touch it. The fills are invented; the prices they
fill at are not — marks come from live market data, so NAV, exposure, drawdown
and reconciliation all move against reality.

Shape of the seeded book: $2,000 across THREE deployed strategies with distinct
universes, sized to leave roughly $100 in cash. That is deliberate — a fund this
small holding this much of its NAV in market exposure is exactly the situation
the structural risk limits exist to police, and three strategies over overlapping
large-cap US equities is exactly the "three strategies that are really one bet"
case the correlation engine is built to catch. The seed is meant to produce a
book with real risk findings in it, not a clean one.

Run against a spine started with USE_FAKE_FIRESTORE=1. Refuses otherwise: this
writes subscriptions and fills, and none of that belongs in the real book.
"""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1/fund"

CAPITAL = 2000.0
TARGET_CASH = 120.0          # a little above the $100 floor so the last order clears

# Risk limits sized for a $2k book that intends to run ~95% deployed.
LIMITS = {
    "min_cash_pct": 0.05,               # $100 floor, now enforced PRE-trade
    "max_position_pct": 0.20,           # $400 in any one name
    "max_order_notional_pct": 0.15,     # $300 in any one order
    "max_strategy_pct": 0.40,           # $800 in any one strategy
    "max_drawdown_pct": 0.10,           # halt at -10% from peak
    "max_daily_loss_pct": 0.04,
    "underwater_pct": 0.15,
    "min_effective_bets": 2.0,
    "max_avg_correlation": 0.75,
    "max_strategy_correlation": 0.90,
    "max_risk_concentration_pct": 0.50,
    "max_expected_shortfall_pct": 0.05,
}

# Three strategies, deliberately different in style AND universe. Whether they
# turn out to be genuinely different *bets* is a measurement, not a claim — the
# correlation engine answers it after the fills land.
STRATEGIES = [
    {
        "name": "Momentum — Large Cap Tech",
        "definition": {"type": "sma", "fast": 10, "slow": 30},
        "assets": ["AAPL", "MSFT", "NVDA"],
        "backtest": "AAPL",
    },
    {
        "name": "Mean Reversion — Cyclicals",
        "definition": {"type": "rsi", "period": 14, "low": 30, "high": 70},
        "assets": ["F", "INTC", "SOFI"],
        "backtest": "INTC",
    },
    {
        "name": "Trend — Sector & Commodity",
        "definition": {"type": "macd", "fast": 12, "slow": 26, "signal": 9},
        "assets": ["SPY", "XLE", "GLD"],
        "backtest": "SPY",
    },
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
    """Seeding silently over a failed call is how a book ends up describing
    state it does not have. Stop instead."""
    if isinstance(res, dict) and res.get("_error"):
        print(f"FAILED {what}: HTTP {res['_error']} {res.get('_body','')}")
        raise SystemExit(1)
    return res


def quotes(symbols):
    res = call("GET", "/market/quotes?symbols=" + ",".join(symbols))
    out = {}
    for q in (res.get("quotes") or []):
        px = q.get("price")
        if px:
            out[q["symbol"].upper()] = float(px)
    return out


def main() -> int:
    book = call("GET", "/book")
    if book.get("orders_are_real"):
        print("REFUSING: this spine routes orders to the REAL broker "
              f"(venue={book.get('venue')!r}). The seeder invents fills and would "
              "place nine real orders. Start without FUND_REAL_BROKER to seed.")
        return 1
    if book.get("env") != "mock":
        print(f"REFUSING: spine is not in mock mode (env={book.get('env')!r}, "
              f"project={book.get('project_id')!r}).")
        print("Start it with USE_FAKE_FIRESTORE=1 first.")
        return 1

    nav_now = (call("GET", "/nav").get("live") or {}).get("total_nav_usd") or 0
    if float(nav_now) > 0:
        print(f"REFUSING: book already has NAV ${float(nav_now):,.2f}. This seeder is not "
              "idempotent — running it twice doubles the fund. Restart the spine with a "
              "cleared .firestore_local_db.json first.")
        return 1

    print(f"mock book: {book.get('project_id')} / {book.get('env')}\n")

    # 0. limits first, so every order below is gated by the real mandate
    must(call("POST", "/risk/limits", {"patch": LIMITS, "actor": "vishesh"}), "set limits")
    print(f"  limits set — cash floor {LIMITS['min_cash_pct']:.0%}, "
          f"drawdown halt {LIMITS['max_drawdown_pct']:.0%}, "
          f"max {LIMITS['max_position_pct']:.0%} per name")

    # 1. capital
    sub = must(call("POST", "/lp/subscriptions",
                    {"lp_id": "rushi", "lp_name": "Rushi",
                     "usd_amount": CAPITAL, "actor": "operator"}), "subscribe")
    sid = sub.get("subscription_id")
    if not sid:
        print(f"FAILED subscribe: no subscription_id in {sub}")
        return 1
    must(call("POST", f"/lp/subscriptions/{sid}/confirm", {"actor": "operator"}), "confirm cash")
    print(f"  funded ${CAPITAL:,.0f}  (subscription {str(sid)[:8]})\n")

    deployable = CAPITAL - TARGET_CASH
    per_strategy = deployable / len(STRATEGIES)
    target_pct = round(per_strategy / CAPITAL * 100.0, 1)

    filled = 0
    for spec in STRATEGIES:
        st = call("POST", "/strategies", {"name": spec["name"], "actor": "rushi",
                                          "definition": spec["definition"]})
        st_id = st.get("strategy_id")
        if not st_id:
            print(f"  could not create {spec['name']}: {st}")
            return 1
        call("POST", f"/strategies/{st_id}/assets",
             {"symbols": spec["assets"], "actor": "rushi"})

        bt = call("POST", f"/strategies/{st_id}/backtest/by_symbol",
                  {"symbol": spec["backtest"], "lookback_days": 365})
        line = ""
        if "result" in bt:
            r = bt["result"]
            line = (f"  backtest {spec['backtest']}: return {r['total_return']*100:.1f}% "
                    f"sharpe {r['sharpe']:.2f}")
        call("POST", f"/strategies/{st_id}/state", {"state": "deployed", "actor": "rushi"})
        call("POST", f"/strategies/{st_id}/allocation",
             {"target_pct": target_pct, "actor": "rushi"})
        print(f"{spec['name']}  ({st_id[:8]}) — {', '.join(spec['assets'])} @ {target_pct}%")
        if line:
            print(line)

        px = quotes(spec["assets"])
        per_name = per_strategy / len(spec["assets"])
        for sym in spec["assets"]:
            price = px.get(sym)
            if not price:
                print(f"    {sym:<5} skipped: no live quote")
                continue
            qty = round(per_name / price, 4)      # Alpaca allows fractional
            if qty <= 0:
                continue
            p = call("POST", "/orders/propose",
                     {"symbol": sym, "side": "buy", "qty": qty,
                      "strategy_id": st_id, "actor": "rushi"})
            if p.get("status") != "pending_approval":
                reason = p.get("breaches") or p.get("_body") or p.get("status")
                print(f"    {sym:<5} not proposed: {reason}")
                continue
            call("POST", f"/orders/{p['order_id']}/approve", {"approver": "rushi"})
            filled += 1
            print(f"    bought {qty:>9} {sym:<5} @ ${price:,.2f}  (${qty*price:,.2f})")
        print()

    call("POST", "/nav/strike", {"actor": "system"})

    nav = call("GET", "/nav").get("live", {})
    total = nav.get("total_nav_usd") or 0
    cash = (nav.get("breakdown") or {}).get("cash", 0)
    print(f"  NAV ${total:,.2f} · cash ${cash:,.2f} "
          f"({cash/total*100 if total else 0:.1f}%) · "
          f"{len(nav.get('positions') or [])} positions · {filled} fills")

    adv = call("GET", "/risk/advanced?include_historical=false", timeout=300)
    if adv.get("headlines"):
        print("\n  risk view:")
        for h in adv["headlines"]:
            print(f"    {h}")
    for a in (adv.get("alarms") or []):
        print(f"    [{a['severity'].upper()}] {a['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
