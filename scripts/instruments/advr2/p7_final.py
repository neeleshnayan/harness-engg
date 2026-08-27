"""P7: (a) the pending_approved absence/shape table; (b) MAX_PENDING_AGE and
MAX_PLAUSIBLE_NAV boundary direction; (c) a randomised property test that the
four-corner shortcut equals the TRUE 2^n worst case, computed independently."""
import sys, importlib.util, random, itertools
sys.path.insert(0, sys.argv[2]); from base import base, run
spec = importlib.util.spec_from_file_location("v5", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def R(o,c,b): return run(m,o,c,b)
o,c,b = base(); assert R(o,c,b)["approve"], "PRECOND"
print("PRECOND base approves\n(a) pending_approved shape table")
ROW = {"order_id":"o1","strategy_id":"s1","symbol":"HYG","side":"buy",
       "qty":0.1,"mark_usd":80.0,"age_minutes":1.0}
def shape(tag, val, drop=False):
    o,c,bb = base()
    if drop: c.pop("pending_approved")
    else: c["pending_approved"] = val
    r = R(o,c,bb)
    f = [x for x in r["checks"] if x["check"] in
         ("in_flight_ledger_readable","in_flight_orders_fresh")]
    print(f"   {tag:<50} approve={r['approve']!s:<5} readable={f[0]['ok']!s:<5} fresh={f[1]['ok']}")
shape("KEY ABSENT ENTIRELY", None, drop=True)
shape("None (unreadable)", None)
shape("[] (measured zero)", [])
shape("() empty tuple", ())
shape("{} empty dict", {})
shape("'' empty string", "")
shape("'[]' a JSON string", "[]")
shape("0 / int", 0)
shape("[None]", [None])
shape("[{}] empty row", [{}])
shape("[row] good", [dict(ROW)])
shape("[row, 'junk']", [dict(ROW), "junk"])
shape("row missing symbol", [{**ROW,"symbol":None}])
shape("row missing side", [{**ROW,"side":None}])
shape("row side='SELL '", [{**ROW,"side":"SELL "}])
shape("row qty=0", [{**ROW,"qty":0}])
shape("row qty=-1", [{**ROW,"qty":-1}])
shape("row qty=True", [{**ROW,"qty":True}])
shape("row qty='0.1' string", [{**ROW,"qty":"0.1"}])
shape("row qty=1e308", [{**ROW,"qty":1e308}])
shape("row mark=0", [{**ROW,"mark_usd":0}])
shape("row mark=1e308", [{**ROW,"mark_usd":1e308}])
shape("row age=None", [{**ROW,"age_minutes":None}])
shape("row age=-1", [{**ROW,"age_minutes":-1}])
shape("row age=29.9", [{**ROW,"age_minutes":29.9}])
shape("row age=30.0 (boundary)", [{**ROW,"age_minutes":30.0}])
shape("row age=30.001", [{**ROW,"age_minutes":30.001}])
shape("row symbol='hyg ' (case/space)", [{**ROW,"symbol":"hyg "}])
shape("row symbol='HYG.' (near-miss)", [{**ROW,"symbol":"HYG."}])
shape("50 duplicate rows of the SAME order", [dict(ROW) for _ in range(50)])
shape("row with an unknown extra key", [{**ROW,"venue":"alpaca"}])

print("\n(b) constant boundaries")
for nav in (1e12, 1e12+1, 1e12*1.0000001):
    o,c,bb = base(); c["nav_usd"]=nav
    print(f"   nav_usd={nav!r:<22} approve={R(o,c,bb)['approve']}")

print("\n(c) property test: module's 4-corner bound vs the TRUE 2^n worst case")
rnd = random.Random(20260827); bad_abs = bad_short = n = 0
for _ in range(4000):
    k = rnd.randint(0,4)
    rows=[]
    for i in range(k):
        rows.append({"order_id":f"o{i}","strategy_id":"s1","symbol":"HYG",
                     "side":rnd.choice(["buy","sell"]),
                     "qty":round(rnd.uniform(0.01,5),4),"mark_usd":80.0,
                     "age_minutes":1.0})
    book = round(rnd.uniform(-5,5),4)
    delta = round(rnd.uniform(0.01,5),4) * rnd.choice([1,-1])
    fl = m.in_flight(rows,"HYG","s1")
    mod_abs   = m.worst_abs_position(book, fl["symbol_buy_qty"], fl["symbol_sell_qty"], delta)
    mod_short = m.worst_short_position(book, fl["symbol_sell_qty"], delta)
    signed=[ (r["qty"] if r["side"]=="buy" else -r["qty"]) for r in rows]
    true_positions=[book+delta+sum(s) for L in range(len(signed)+1)
                    for s in itertools.combinations(signed,L)]
    t_abs = max(true_positions, key=abs); t_short = min(true_positions)
    n+=1
    if abs(abs(mod_abs)-abs(t_abs))>1e-9: bad_abs+=1
    if abs(mod_short-t_short)>1e-9: bad_short+=1
print(f"   {n} random books x in-flight sets: concentration-corner mismatches "
      f"{bad_abs}, worst-short mismatches {bad_short}")
