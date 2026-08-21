"""One-command session-start digest — the tokenomics ritual, scriptized.

Replaces the hand-rolled curl sequence every session (CTO, co-CTO, or any
seat briefed to run it) burns tokens re-deriving: monitor state, desk load,
pending approvals, exit-rule standing, recent events. Deterministic reads
only; writes nothing; the output is deliberately compact because its whole
purpose is to be cheap to put in a context window.

Run: ./venv/Scripts/python.exe -X utf8 scripts/desk_digest.py
"""
import json
import urllib.request

BASE = "http://127.0.0.1:8090/api/v1"


def get(path):
    try:
        return json.loads(urllib.request.urlopen(BASE + path, timeout=30).read())
    except Exception as e:  # noqa: BLE001
        return {"_unreachable": f"{type(e).__name__}: {e}"}


m = get("/fund/risk/monitor")
if "_unreachable" in m:
    print("SPINE UNREACHABLE:", m["_unreachable"])
    raise SystemExit(1)

print(f"NAV ${m['nav_usd']:,.2f} | gross {m['gross_exposure_pct']:.2f}% | "
      f"cash {m['cash_pct']:.2f}% | halted={m['halted']}"
      + (f" ({m.get('halt_reason')})" if m["halted"] else ""))
print("alarms:", m["alarms"] if m["alarms"] else "none")
dd = m.get("drawdown") or {}
print(f"drawdown {dd.get('drawdown_pct')}% of {dd.get('limit_pct')}% "
      f"(peak {dd.get('peak_nav')})")
print("positions:", ", ".join(
    f"{p['symbol']} {p['qty']:.4f} @ {p['mark']:.2f} ({p['weight_pct']:.1f}%)"
    for p in m.get("positions", [])) or "none")

desk = get("/fund/desk")
dl = desk.get("desk_load") or {}
print(f"\ndesk_load {dl.get('total')}/{dl.get('threshold')} "
      f"(coo_triage_due={dl.get('coo_triage_due')}) "
      f"components={dl.get('components')}")
for r in desk.get("requests", []):
    if r.get("status") == "open":
        print(f"  open ask {str(r.get('request_id'))[:8]} -> "
              f"{r.get('seat')}: {(r.get('task') or '')[:90]}")
for r in desk.get("open_recommendations", []) or []:
    print(f"  open rec [{r.get('seat')}] {(r.get('text') or '')[:90]}")

pend = get("/fund/orders/pending").get("pending", [])
print(f"\npending orders: {len(pend)}")
for p in pend:
    print(f"  {str(p.get('order_id'))[:8]} {p.get('symbol')} {p.get('side')} "
          f"{p.get('qty')}")

chk = get("/fund/exits/check")
for key in ("fired", "unevaluable"):
    rows = chk.get(key) or []
    if rows:
        print(f"exits {key}: " + "; ".join(
            f"{r.get('strategy_id')}/{r.get('symbol')} {r.get('kind')}"
            for r in rows))
if not (chk.get("fired") or chk.get("unevaluable")):
    print("exits: all holding, all evaluable")

evs = (get("/fund/events?limit=10") or {}).get("events", [])
print("\nlast events:", "; ".join(
    f"{e['seq']} {e['type']}"
    + (f" {e['payload'].get('symbol')}" if isinstance(e.get('payload'), dict)
       and e['payload'].get('symbol') else "")
    for e in evs[:8]))
