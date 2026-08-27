"""ADV probe B-5: the filter-at-point-of-use edges the brief names."""
import ast, os, sys, re
REPO = r"C:/Users/user/Documents/Krypton Fund/ClarkHarness"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from merge_builder import refusal_predicates, scan_control_flow, _UBIQUITOUS_NAMES
src = open(os.path.join(REPO, "app/api/v1/fund.py"), encoding="utf-8").read()
info = refusal_predicates(src)
lines = src.splitlines()
tot = len(lines)
covered = set()
for r in info["regions"]:
    covered |= set(range(r["first_line"], r["last_line"] + 1))
print(f"fund.py: {len(info['regions'])} refusal regions, {len(info['names'])} guarding "
      f"names after the filter, {len(covered)} of {tot} lines = {len(covered)/tot*100:.1f}%")
# which guarding names are FUNCTIONS defined in this same file (the helper case)?
tree = ast.parse(src)
defs = {n.name: (n.lineno, getattr(n, "end_lineno", n.lineno))
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
helpers = {n: defs[n] for n in sorted(info["names"]) if n in defs}
print(f"\nguarding names that are same-file FUNCTIONS ({len(helpers)}):")
for n, (a, b) in list(helpers.items())[:12]:
    inside = any(r["first_line"] <= a <= r["last_line"] for r in info["regions"])
    print(f"  {n:<34} def at {a:>5}-{b:<5} body inside a refusal region? {inside}")
# THE PROBE: change a helper's BODY (not its def line) and ask the shipped scan.
if helpers:
    name, (a, b) = next(iter((k, v) for k, v in helpers.items()
                             if not any(r["first_line"] <= v[0] <= r["last_line"]
                                        for r in info["regions"])), (None, (0, 0)))
    if name:
        body_line = a + 1
        while body_line <= b and (not lines[body_line-1].strip()
                                  or lines[body_line-1].strip().startswith(('"""', "#"))):
            body_line += 1
        res = scan_control_flow({"app/api/v1/fund.py": {body_line}}, lambda p: src)
        print(f"\nHELPER-BODY PROBE: change line {body_line} inside {name}() "
              f"(a predicate a refusal reads)\n  line text: {lines[body_line-1].strip()[:90]}")
        print(f"  scan_control_flow hits = {len(res['hits'])}  -> "
              f"{'SEEN' if res['hits'] else '*** INVISIBLE ***'}")
        res2 = scan_control_flow({"app/api/v1/fund.py": {a}}, lambda p: src)
        print(f"  (control) changing the `def {name}` line itself: hits = {len(res2['hits'])}")
# short-name regions: does a region gated ONLY on <=2-char names still count?
short = [r for r in info["regions"]
         if not {g for g in r["guards"] if g not in _UBIQUITOUS_NAMES and len(g) > 2}]
print(f"\nregions whose guards are ALL filtered out (short/ubiquitous): {len(short)} "
      f"-> these are the 22 the 38->60 repair recovered; they ARE regions: "
      f"{[r['function'] for r in short][:8]}")
