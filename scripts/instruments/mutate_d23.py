"""Byte-level mutation harness for D23. CRLF-aware; restores exact bytes.

Each mutant is one plausible defect in the new branch logic. A mutant that no
NAMED test kills is a test gap, and it is reported as SURVIVED. A mutant proved
to be a no-op is RETIRED with the proof, never counted as killed.
"""
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/d23"
PY = r"C:/Users/user/Documents/Krypton Fund/ClarkHarness/venv/Scripts/python.exe"
TESTS = ["tests/test_premia_gate.py", "tests/test_premia_inputs.py",
         "tests/test_gate.py", "tests/test_leanrunner.py",
         "tests/test_daily_returns.py", "tests/test_doctrine.py",
         "tests/test_fold_scaling.py"]

G = "app/fund/gate.py"
L = "app/fund/leanrunner.py"
S = "app/fund/statistics.py"
F = "app/fund/factory.py"

MUTANTS = [
    # --- the premia inequality itself
    ("M01 stress check dropped", G,
     "    out[\"rf_sensitive\"] = bool(adv0 > margin and not adv1 > margin)",
     "    out[\"rf_sensitive\"] = False"),
    ("M02 rf=0 comparison inverted to >=", G,
     "    if not adv0 > margin:", "    if not adv0 >= margin:"),
    ("M03 drawdown comparison flipped", G,
     "    dd_ok = float(s[\"max_drawdown_pct\"]) <= float(b[\"max_drawdown_pct\"])",
     "    dd_ok = float(s[\"max_drawdown_pct\"]) >= float(b[\"max_drawdown_pct\"])"),
    ("M04 drawdown leg not enforced", G,
     "    if pc.get(\"premia_require_drawdown_not_worse\") and not dd_ok:",
     "    if False and not dd_ok:"),
    ("M05 coverage majority becomes non-strict", G,
     "    coverage_ok = common * 2 > total if total else False",
     "    coverage_ok = common * 2 >= total if total else False"),
    ("M06 coverage leg not enforced", G,
     "    if pc.get(\"premia_require_majority_window_coverage\") and not coverage_ok:",
     "    if False and not coverage_ok:"),
    ("M07 stress rate read as zero", G,
     "    rf_stress = float(pc[\"premia_rf_stress_pct\"])",
     "    rf_stress = 0.0"),
    ("M08 margin ignored (hardcoded 0)", G,
     "    margin = float(pc[\"premia_min_sharpe_advantage\"])",
     "    margin = 0.0"),
    ("M09 absent premia inputs pass instead of fail", G,
     "        return out, [\n            f\"the premia comparison could not be measured: {reason} — a premia \"",
     "        return out, [] and [\n            f\"the premia comparison could not be measured: {reason} — a premia \""),
    ("M10 premia branch never taken", G,
     "    if is_premia:\n        premia, premia_failures = _premia_leg(result, pc)",
     "    if False:\n        premia, premia_failures = _premia_leg(result, pc)"),
    ("M11 unknown claim type silently accepted", G,
     "    known = declared in CLAIM_TYPES", "    known = True"),
    ("M12 premia version stamp reverts to v4.3", G,
     "        \"gate_version\": GATE_VERSION_PREMIA if is_premia else GATE_VERSION,",
     "        \"gate_version\": GATE_VERSION,"),
    ("M13 must_beat_benchmark also applied to premia", G,
     "    elif c[\"must_beat_benchmark\"]:", "    if c[\"must_beat_benchmark\"]:"),
    ("M14 rf breakeven sign flipped", G,
     "    c = (float(mu_s) * float(sd_b) - float(mu_b) * float(sd_s)) / (\n        float(sd_b) - float(sd_s))",
     "    c = (float(mu_b) * float(sd_s) - float(mu_s) * float(sd_b)) / (\n        float(sd_b) - float(sd_s))"),
    # --- the belt legs
    ("M15 premia leg reads the DISCARDED engine series", L,
     "    if source == \"recomputed_basket\":\n        bmap = _returns_from_curve(result.get(\"benchmark_curve\"),\n                                   result.get(\"benchmark_dates\"))",
     "    if source == \"recomputed_basket\":\n        _b = list(daily.get(\"benchmark\") or [])\n        bmap = dict(zip(s_dates, _b)) if len(_b) == len(s_dates) else {}"),
    ("M16 legs measured over their own windows, not the shared one", L,
     "    strat = _stats.leg_moments([smap[d] for d in common], common)",
     "    strat = _stats.leg_moments([smap[d] for d in s_dates], s_dates)"),
    ("M17 disagreement never reported", L,
     "            \"agrees_with_headline\": (\n                None if headline is None\n                else abs(engine_total - float(headline)) <= 0.05),",
     "            \"agrees_with_headline\": True,"),
    ("M18 recomputed-basket marker never set", L,
     "        result[\"benchmark_series_source\"] = \"recomputed_basket\"",
     "        pass"),
    ("M19 curve chain does not break on a bad level", L,
     "        ok = isinstance(level, (int, float)) and math.isfinite(level) and level > 0",
     "        ok = isinstance(level, (int, float))"),
    ("M20 psr capture drops the sample length", L,
     "        \"n\": len(series),", "        \"n\": None,"),
    ("M21 psr vol reproduction always agrees", L,
     "        \"reproduces\": (None if published is None or recomputed is None\n                       else abs(published - recomputed) < 5e-4),",
     "        \"reproduces\": True,"),
    ("M22 psr capture annualises the reproduction at 365", L,
     "    recomputed = sd * math.sqrt(252.0) if sd else None",
     "    recomputed = sd * math.sqrt(365.0) if sd else None"),
    # --- the clock and the moments
    ("M23 annualisation falls back to 252", S,
     "    return {\"usable\": True,\n            \"obs_per_year\": (n - 1) / (span_days / 365.25),",
     "    return {\"usable\": True,\n            \"obs_per_year\": 252.0,"),
    ("M24 unreadable clock reports 252 instead of absent", S,
     "        return {\"usable\": False, \"obs_per_year\": None,\n                \"reason\": f\"the series spans {span_days} day(s), so no annual \"",
     "        return {\"usable\": True, \"obs_per_year\": 252.0,\n                \"reason\": f\"the series spans {span_days} day(s), so no annual \""),
    ("M25 constant-series floor removed", S,
     "    if sd <= max(1e-12, abs(mu) * 1e-9):\n        sd = 0.0", "    pass"),
    ("M26 rf converted by dividing instead of compounding", S,
     "    rf_per_obs = (1.0 + float(rf_pct) / 100.0) ** (1.0 / float(k)) - 1.0",
     "    rf_per_obs = float(rf_pct) / 100.0 / float(k)"),
    ("M27 sharpe ignores the risk-free rate entirely", S,
     "    return (mu - rf_per_obs) / sd * math.sqrt(float(k))",
     "    return mu / sd * math.sqrt(float(k))"),
    ("M28 drawdown returns the last fall, not the worst", S,
     "        if peak > 0:\n            worst = max(worst, 1.0 - level / peak)",
     "        if peak > 0:\n            worst = 1.0 - level / peak"),
    ("M29 sharpe returns a number for an unmeasurable leg", S,
     "    if not moments or not moments.get(\"measurable\"):\n        return None",
     "    if not moments:\n        return None"),
    # --- the belt refusal
    ("M30 belt accepts any claim type", F,
     "    if declared in CLAIM_TYPES:\n        return {\"known\": True, \"claim_type\": declared, \"reason\": None}",
     "    if True:\n        return {\"known\": True, \"claim_type\": declared, \"reason\": None}"),
    ("M31 malformed-payload guard removed (_premia_leg)", G,
     "    if absent:", "    if False:"),
    ("M32 malformed-payload guard removed (volatility_check)", G,
     "    if not readable:",
     "    if not (isinstance(p, dict) and p.get(\"measurable\")):"),
    ("M33 engine vol scaled blind by 100", L,
     "    return value if \"%\" in text else value * 100.0",
     "    return value * 100.0"),
]


def run():
    p = subprocess.run([PY, "-m", "pytest", "-q", "-x", "--no-header",
                        "-p", "no:randomly"] + TESTS,
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": ROOT,
                            "PYTHONIOENCODING": "utf-8"})
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    rc, out = run()
    if rc != 0:
        print("BASELINE IS RED — stopping\n", out[-2000:])
        return 1
    print("baseline green:", out.strip().splitlines()[-1])
    killed, survived, notapplied = [], [], []
    for name, rel, old, new in MUTANTS:
        path = os.path.join(ROOT, rel)
        raw = io.open(path, "rb").read()
        nl = b"\r\n" if b"\r\n" in raw else b"\n"
        o = old.replace("\n", nl.decode()).encode("utf-8")
        n = new.replace("\n", nl.decode()).encode("utf-8")
        if raw.count(o) != 1:
            notapplied.append((name, f"pattern occurs {raw.count(o)} times"))
            print(f"NOT-APPLIED {name}")
            continue
        io.open(path, "wb").write(raw.replace(o, n))
        try:
            mrc, mout = run()
        finally:
            io.open(path, "wb").write(raw)
        if mrc != 0:
            first = [l for l in mout.splitlines() if l.startswith("FAILED")]
            killed.append((name, first[0] if first else mout.strip()[-200:]))
            print(f"killed   {name}  <- {killed[-1][1][:110]}")
        else:
            survived.append(name)
            print(f"SURVIVED {name}")
    print("\n=== %d killed, %d SURVIVED, %d not-applied ==="
          % (len(killed), len(survived), len(notapplied)))
    for n_, why in notapplied:
        print("  not-applied:", n_, "-", why)
    for n_ in survived:
        print("  SURVIVED:", n_)
    # The tree must be byte-identical to how we found it.
    st = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                        capture_output=True, text=True)
    print("git status after restore:", repr(st.stdout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
