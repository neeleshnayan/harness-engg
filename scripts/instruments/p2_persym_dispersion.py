"""Paired per-symbol mark dispersion: fund mark (IEX latest trade, the pricer
NavService actually uses) vs the broker's own position current_price, same instant.
READ-ONLY."""
import json, os, sys, time
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), ".env"))
from app.fund.mode import resolve, activate
from app.fund.venue import build_connector
spec = activate(resolve()); c = build_connector(spec)
N = int(sys.argv[1]); GAP = float(sys.argv[2]); OUT = sys.argv[3]
rows = []
for i in range(N):
    t0 = time.time()
    try:
        pos = c._trading().get_all_positions()
        acct = c._trading().get_account()
        rec = {"i": i, "t": time.strftime("%H:%M:%SZ", time.gmtime()),
               "equity": float(acct.equity), "cash": float(acct.cash), "sym": {}}
        for p in pos:
            s = p.symbol
            try:
                fund_mark = c._fetch_price(s)   # bypasses the 5s TTL cache on purpose
            except Exception as e:
                fund_mark = None
            rec["sym"][s] = {"qty": float(p.qty), "broker_px": float(p.current_price),
                             "fund_px": fund_mark,
                             "rel_bps": (None if fund_mark in (None, 0) else
                                         round((float(p.current_price)/fund_mark - 1.0)*1e4, 2))}
        rows.append(rec)
    except Exception as e:
        rows.append({"i": i, "error": repr(e)})
    print(json.dumps(rows[-1]), flush=True)
    time.sleep(max(0.0, GAP - (time.time()-t0)))
json.dump(rows, open(OUT, "w"), indent=1)
