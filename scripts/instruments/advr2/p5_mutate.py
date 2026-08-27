"""P5: MUTATION GRADING. Does the r2 suite PIN the two repairs and the four
residuals, or was it written around them? Each mutant reverts ONE r2 repair to
its r1 behaviour. A mutant that survives is a repair no test holds."""
import os, subprocess, sys, shutil
S = os.path.dirname(os.path.abspath(__file__)); R = sys.argv[1]
SRC = open(os.path.join(S, "v5r2.py"), encoding="utf-8").read()

MUT = {
 "M-A concentration ignores in-flight (r1 bound)": (
   'worst_book = worst_abs_position(book, flight["symbol_buy_qty"],\n'
   '                                    flight["symbol_sell_qty"], delta)',
   'worst_book = post_fill_position(book, delta)'),
 "M-B reduce-only netted, not worst-corner": (
   "return float(pre) + float(pending_sell_qty) + float(delta)",
   "return float(pre) + float(delta)"),
 "M-C unreadable in-flight ledger folds to ZERO": (
   '    if pending is None:\n        return {**absent, "reason": IN_FLIGHT_UNREADABLE}',
   '    if pending is None:\n        pending = []'),
 "M-D exit ordering back to STRING compare": (
   "        return datetime.fromisoformat(a) < datetime.fromisoformat(b)",
   "        return str(a) < str(b)"),
 "M-E mark move back to SIGNED": (
   "ok = abs(move) <= MAX_MARK_MOVE_VS_STRIKE_PCT",
   "ok = move <= MAX_MARK_MOVE_VS_STRIKE_PCT"),
 "M-F _number accepts booleans again": (
   "    if isinstance(value, bool):\n        return None",
   "    if isinstance(value, bool):\n        pass"),
 "M-G _number ignores its declared range": (
   "    if lo is not None and out < lo:\n        return None\n"
   "    if hi is not None and out > hi:\n        return None",
   "    if False:\n        return None"),
 "M-H evaluate guard removed (raises escape)": (
   "    except Exception as e:  # noqa: BLE001 — a verdict for every input, always",
   "    except () as e:  # noqa"),
 "M-I stale in-flight row no longer stale": (
   "            if r_age > MAX_PENDING_AGE_MINUTES:\n                stale += 1",
   "            if False:\n                stale += 1"),
 "M-J unreadable in-flight AGE reads as fresh": (
   "        if r_age is None:\n            stale += 1",
   "        if r_age is None:\n            pass"),
 "M-K NAV plausibility ceiling removed": (
   'nav = num("nav_usd", lo=POSITION_EPS, hi=MAX_PLAUSIBLE_NAV_USD)',
   'nav = num("nav_usd", lo=POSITION_EPS)'),
 "M-L strategy_matches_the_order removed": (
   'bool(row_sid) and bool(order_sid) and row_sid == order_sid,',
   'True,'),
 "M-M in-flight OTHER-symbol gross dropped from bounds": (
   "            other_gross += r_qty * r_mark",
   "            other_gross += 0.0"),
 "M-N empty asset scope reads as UNLIMITED": (
   '        check("symbol_in_scoped_assets", False,',
   '        check("symbol_in_scoped_assets", True,'),
 "M-O unmeasurable throttle reads as FULL gross": (
   "    if measurable is not True or mult is None or mandate is None:",
   "    if False:"),
 "M-P one bad in-flight row skipped, not fatal": (
   '        if not isinstance(row, dict):\n            return {**absent,',
   '        if not isinstance(row, dict):\n            continue\n        if False:\n            return {**absent,'),
}
os.makedirs(os.path.join(S, "mutwork"), exist_ok=True)
print(f"{'MUTANT':<48} {'RESULT':<10} failing tests")
for tag, (old, new) in MUT.items():
    if old not in SRC:
        print(f"{tag:<48} {'PATCH-MISS':<10} (anchor not found)"); continue
    p = os.path.join(S, "mutwork", "m.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(old, new, 1))
    env = dict(os.environ, V5_REPO=R, V5_MODULE=p)
    r = subprocess.run([os.path.join(R, "venv/Scripts/python.exe"), "-m", "pytest",
                        "-q", "-p", "no:cacheprovider", "--tb=no", "."],
                       cwd=os.path.join(S, "mut"), env=env,
                       capture_output=True, text=True)
    out = r.stdout
    fails = [l.split("::")[-1].split()[0] for l in out.splitlines()
             if l.startswith("FAILED")]
    fails = [f for f in fails if f != "test_the_draft_imports_nothing_from_the_fund"]
    verdict = "KILLED" if fails else "SURVIVED"
    print(f"{tag:<48} {verdict:<10} {len(fails)}: {', '.join(fails[:3])}")
