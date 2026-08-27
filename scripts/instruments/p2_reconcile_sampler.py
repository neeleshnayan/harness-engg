"""Sample GET /fund/venue/reconcile repeatedly. Read-only (drift() writes no events)."""
import json, sys, time, urllib.request
URL = "http://127.0.0.1:8090/api/v1/fund/venue/reconcile"
N = int(sys.argv[1]); GAP = float(sys.argv[2])
out = []
for i in range(N):
    t0 = time.time()
    try:
        with urllib.request.urlopen(URL, timeout=40) as r:
            d = json.load(r)
        out.append({"i": i, "wall": time.strftime("%H:%M:%SZ", time.gmtime()),
                    "as_of": d.get("as_of"), "book_nav": d.get("book_nav"),
                    "broker_equity": d.get("broker_equity"),
                    "delta_usd": d.get("delta_usd"), "delta_pct": d.get("delta_pct"),
                    "oos": d.get("symbols_out_of_sync"),
                    "n_sym": len(d.get("per_symbol") or [])})
    except Exception as e:
        out.append({"i": i, "wall": time.strftime("%H:%M:%SZ", time.gmtime()), "error": repr(e)})
    print(json.dumps(out[-1]), flush=True)
    time.sleep(max(0.0, GAP - (time.time() - t0)))
json.dump(out, open(sys.argv[3], "w"), indent=1)
