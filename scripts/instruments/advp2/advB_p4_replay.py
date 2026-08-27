"""ADV probe B-4: FALSE-URGENCY. Replay the last N real commits through the
SHIPPED classifier and count how often it would have demanded an adversary pass."""
import os, subprocess, sys
REPO = r"C:/Users/user/Documents/Krypton Fund/ClarkHarness"
CLONE = sys.argv[1]; N = int(sys.argv[2])
sys.path.insert(0, os.path.join(REPO, "scripts"))
from merge_builder import (classify_paths, scan_diff, changed_lines,
                           scan_control_flow, refusal_predicates)
def git(*a, cwd=CLONE):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout
shas = [s for s in git("log", "--format=%H", f"-{N}").split() if s]
rows = []
for sha in shas:
    names = [p for p in git("diff", "--name-only", f"{sha}~1", sha).splitlines() if p.strip()]
    if not names: continue
    diff = git("diff", "--unified=0", f"{sha}~1", sha)
    b = classify_paths(names); s = scan_diff(diff)
    def _read(rel, _sha=sha):
        out = subprocess.run(["git", "show", f"{_sha}:{rel}"], cwd=CLONE,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
        return out.stdout if out.returncode == 0 else None
    c = scan_control_flow(changed_lines(diff), _read)
    blocked = bool(b["forbidden"] or b["sensitive"] or s["regions"] or
                   s["removals"] or c["hits"] or c["unreadable"])
    rows.append((sha[:8], len(names), len(b["sensitive"]), len(s["regions"]),
                 len(s["removals"]), len(c["hits"]), len(c["unreadable"]), blocked,
                 git("log","-1","--format=%s",sha).strip()[:52]))
print(f"{'sha':<9}{'files':>6}{'sens':>5}{'reg':>5}{'rem':>5}{'cf':>5}{'unrd':>5}  {'blocked':<8} subject")
for r in rows:
    print(f"{r[0]:<9}{r[1]:>6}{r[2]:>5}{r[3]:>5}{r[4]:>5}{r[5]:>5}{r[6]:>5}  "
          f"{'BLOCK' if r[7] else '.':<8} {r[8]}")
nb = sum(1 for r in rows if r[7])
print(f"\n{nb} of {len(rows)} real commits ({nb/len(rows)*100:.0f}%) would demand an adversary pass")
