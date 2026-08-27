"""ADV probe B-2: run the SHIPPED merge-gate classifier over REAL git diffs of
constructed mutations. Nothing is hand-written: each mutant is applied to a
throwaway CLONE, `git diff --unified=0` produces the diff the gate would read,
and the mutated tree is the 'merged tree' the control-flow scan reads."""
import os, re, subprocess, sys, shutil
REPO = r"C:/Users/user/Documents/Krypton Fund/ClarkHarness"
CLONE = sys.argv[1]
sys.path.insert(0, os.path.join(REPO, "scripts"))
from merge_builder import (classify_paths, scan_diff, changed_lines,
                           scan_control_flow)

def git(*a):
    p = subprocess.run(["git", *a], cwd=CLONE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.stdout

def reset():
    subprocess.run(["git", "checkout", "--", "."], cwd=CLONE,
                   capture_output=True)
    subprocess.run(["git", "clean", "-qfd"], cwd=CLONE, capture_output=True)

def edit(rel, old, new, count=1):
    p = os.path.join(CLONE, rel)
    s = open(p, encoding="utf-8").read()
    assert s.count(old) >= 1, f"anchor not found in {rel}: {old!r}"
    open(p, "w", encoding="utf-8", newline="").write(s.replace(old, new, count))

def write(rel, body):
    p = os.path.join(CLONE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="").write(body)

def verdict(label, want_flag, note):
    names = [l.strip() for l in git("diff", "--name-only").splitlines() if l.strip()]
    names += [l.strip() for l in git("ls-files", "--others",
                                     "--exclude-standard").splitlines() if l.strip()]
    diff = git("diff", "--unified=0")
    # untracked files: add to index (in the clone only) so they appear in the diff
    if git("ls-files", "--others", "--exclude-standard").strip():
        subprocess.run(["git", "add", "-A"], cwd=CLONE, capture_output=True)
        diff = git("diff", "--cached", "--unified=0")
    b = classify_paths(names)
    s = scan_diff(diff)
    def _read(rel):
        try:
            return open(os.path.join(CLONE, rel), encoding="utf-8").read()
        except Exception:
            return None
    c = scan_control_flow(changed_lines(diff), _read)
    total = (len(b["forbidden"]) + len(b["sensitive"]) + len(s["regions"])
             + len(s["removals"]) + len(c["hits"]) + len(c["unreadable"]))
    got = "FLAGGED" if total else "ordinary"
    exp = "FLAGGED" if want_flag else "ordinary"
    mark = "" if got == exp else ("   <<<< MISS" if want_flag else "   <<<< FALSE URGENCY")
    print(f"\n{label}\n  {note}")
    print(f"  files={names}")
    print(f"  path:forbidden={len(b['forbidden'])} sensitive={len(b['sensitive'])} | "
          f"scan_diff:regions={len(s['regions'])} constants={len(s['constants'])} "
          f"removals={len(s['removals'])} | control:hits={len(c['hits'])} "
          f"unreadable={len(c['unreadable'])}")
    print(f"  => {got}  (expected {exp}){mark}")
    for h in c["hits"][:2]: print(f"     hit: {h['path']}:{h['line']} {h['why'][:90]}")
    for r in s["regions"][:2]: print(f"     region: {r['path']} {r['line'][:80]}")
    for r in s["removals"][:2]: print(f"     removal: {r['path']} {r['line'][:80]}")
    reset()
    return got == exp

ok = []
# ---------- M1: flip the fund's master prod lock -------------------------
reset()
edit("app/fund/mode.py", "PROD_UNLOCKED = False", "PROD_UNLOCKED = True")
ok.append(verdict("M1  PROD_UNLOCKED False -> True", True,
    "the constitution's structural prod lock; mode.py:473 reads it as one of the two locks"))

# ---------- M2: an env bypass inside THE ONE GATE ------------------------
reset()
edit("app/fund/mode.py",
     '    if spec.mode is not FundMode.ALPACA_PROD:\n        return\n    report = prod_gate_report(store)',
     '    if spec.mode is not FundMode.ALPACA_PROD:\n        return\n'
     '    if os.environ.get("FUND_SKIP_GATE"):\n        return\n'
     '    report = prod_gate_report(store)')
ok.append(verdict("M2  env bypass added inside _refuse_prod_unless_reachable", True,
    "mode.py:477 docstring: 'THE ONE GATE. Every alpaca-prod refusal comes through here.'"))

# ---------- M3: a precondition silently satisfied ------------------------
reset()
edit("app/fund/mode.py",
     '        if self.evaluator is None:\n            return {"key": self.key, "text": self.text, "status": "unchecked",',
     '        if self.evaluator is None:\n            return {"key": self.key, "text": self.text, "status": "met",')
ok.append(verdict("M3  an unevaluable precondition renders 'met' instead of 'unchecked'", True,
    "mode.py:313-318: 'An unchecked precondition BLOCKS here'; this makes 4 of 5 pass"))

# ---------- M4: SHOULD flag — edit inside a refusal region in fund.py ----
reset()
_p = os.path.join(CLONE, "app/api/v1/fund.py")
_s = open(_p, encoding="utf-8").read()
_m = re.search(r"\n(    if not .+?:\n        raise HTTPException\()", _s)
edit("app/api/v1/fund.py", _m.group(1), _m.group(1).replace("if not ", "if False and not "))
ok.append(verdict("M4  CONTROL: a refusal condition in fund.py weakened", True,
    "the case the gate was built for"))

# ---------- M5: SHOULD flag — a refusal line removed --------------------
reset()
_s = open(_p, encoding="utf-8").read()
_m = re.search(r"\n(        raise HTTPException\(status_code=40\d,[^\n]*\n)", _s)
edit("app/api/v1/fund.py", _m.group(1), "")
ok.append(verdict("M5  CONTROL: a raise HTTPException line deleted", True,
    "the removed-side scan's own falsifier"))

# ---------- M6: helper predicate BODY changed in fund.py ----------------
reset()
write("app/api/v1/_advhelper.py", "x = 1\n")
ok.append(verdict("M6  CONTROL(innocent): a new trivial module", False,
    "the false-urgency direction: an ordinary file must stay ordinary"))

# ---------- M7: docs + tests only ---------------------------------------
reset()
edit("README.md", "#", "# ", 1)
ok.append(verdict("M7  CONTROL(innocent): a README edit", False, "must stay ordinary"))

print(f"\n\n{sum(ok)} of {len(ok)} cases matched expectation")
