"""ADV probe B-6 (the BEFORE-ARM): which of the three mode.py mutants does the
SUITE kill, given the CLASSIFIER killed none? Runs the shipped tests in the clone."""
import os, subprocess, sys
CLONE = sys.argv[1]
PY_ = r"C:/Users/user/Documents/Krypton Fund/ClarkHarness/venv/Scripts/python.exe"
def reset():
    subprocess.run(["git","checkout","--","."], cwd=CLONE, capture_output=True)
def edit(rel, old, new):
    p = os.path.join(CLONE, rel); s = open(p, encoding="utf-8").read()
    assert old in s, rel
    open(p,"w",encoding="utf-8",newline="").write(s.replace(old,new,1))
def run(mods):
    p = subprocess.run([PY_,"-m","pytest",*mods,"-q","-p","no:cacheprovider"],
                       cwd=CLONE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = [l for l in p.stdout.strip().splitlines() if l.strip()][-1]
    return p.returncode, tail
MODS = ["tests/test_fund_mode.py"]
cases = [
 ("M1 PROD_UNLOCKED False->True",
  ("app/fund/mode.py","PROD_UNLOCKED = False","PROD_UNLOCKED = True")),
 ("M2 env bypass inside _refuse_prod_unless_reachable",
  ("app/fund/mode.py",
   '    if spec.mode is not FundMode.ALPACA_PROD:\n        return\n    report = prod_gate_report(store)',
   '    if spec.mode is not FundMode.ALPACA_PROD:\n        return\n'
   '    if os.environ.get("FUND_SKIP_GATE"):\n        return\n'
   '    report = prod_gate_report(store)')),
 ("M3 unevaluable precondition renders 'met'",
  ("app/fund/mode.py",
   '        if self.evaluator is None:\n            return {"key": self.key, "text": self.text, "status": "unchecked",',
   '        if self.evaluator is None:\n            return {"key": self.key, "text": self.text, "status": "met",')),
]
reset(); rc, tail = run(MODS)
print(f"BASE (no mutant):  rc={rc}  {tail}")
for label,(rel,old,new) in cases:
    reset(); edit(rel,old,new); rc, tail = run(MODS)
    print(f"{label:<52} rc={rc}  {tail}   -> "
          f"{'suite KILLS it' if rc else '*** SUITE GREEN — merges as an ordinary diff ***'}")
reset()
