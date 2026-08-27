"""ADV probe B-3: how wide is the AST leg's blind spot?
For every app/**.py file: does the SHIPPED refusal_predicates() see any refusal
region, and does the file contain a conditional raise of some OTHER class
(i.e. a refusal the leg cannot see)? Also: is the file covered by the path legs?"""
import ast, os, sys, fnmatch
REPO = r"C:/Users/user/Documents/Krypton Fund/ClarkHarness"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from merge_builder import (refusal_predicates, SENSITIVE_PATHS, SENSITIVE_GLOBS,
                           REFUSAL_EXCEPTIONS)

def cond_raise_classes(src):
    out = set()
    try: tree = ast.parse(src)
    except Exception: return out
    for br in ast.walk(tree):
        if not isinstance(br, ast.If): continue
        for stmt in list(br.body) + list(br.orelse):
            for n in ast.walk(stmt):
                if isinstance(n, ast.Raise):
                    e = getattr(n, "exc", None)
                    e = e.func if isinstance(e, ast.Call) else e
                    if isinstance(e, ast.Name): out.add(e.id)
                    elif isinstance(e, ast.Attribute): out.add(e.attr)
    return out

def path_covered(p):
    return p in SENSITIVE_PATHS or any(fnmatch.fnmatch(p, g) for g in SENSITIVE_GLOBS)

blind = []
seen_ast = 0; total = 0
for root, dirs, files in os.walk(os.path.join(REPO, "app")):
    dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
    for f in files:
        if not f.endswith(".py"): continue
        full = os.path.join(root, f)
        rel = os.path.relpath(full, REPO).replace("\\", "/")
        src = open(full, encoding="utf-8").read()
        total += 1
        info = refusal_predicates(src)
        has_region = bool(info["regions"])
        if has_region: seen_ast += 1
        others = cond_raise_classes(src) - set(REFUSAL_EXCEPTIONS)
        if (not has_region) and others and not path_covered(rel):
            blind.append((rel, sorted(others)[:4], len(src.splitlines())))
print(f"app/**.py files: {total}; files the AST leg sees a refusal region in: {seen_ast}")
print(f"\nFILES WITH A CONDITIONAL RAISE THE AST LEG CANNOT SEE *AND* NO PATH COVER: {len(blind)}")
for rel, cls, n in sorted(blind, key=lambda r: -r[2])[:22]:
    print(f"  {rel:<48} {n:>5} lines   raises {', '.join(cls)}")
