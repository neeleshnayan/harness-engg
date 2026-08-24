"""Pull stored belt results ONCE into a local json so probes never re-hit PG.

The regeneration half of the d41 clock census (promoted 2026-08-24 at the
adversary's D41 requirement: a register citation and an instrument's default
data path are the same kind of promise — both must outlive a session).

Usage:  python scripts/instruments/d41/pull_jobs.py [out.json]
Default out path is the shelved register-draft dump this repo commits:
docs/drafts/data/d38_jobs_2026-08-24.json — pass a new path to re-measure a
grown belt without overwriting the frozen citation data.

The one query, stated so the dump is reproducible without reading this code:
    SELECT job_id, result FROM fund_lean_jobs WHERE result IS NOT NULL
then per row: series = result.daily_returns.strategy (when present),
dates = result.daily_returns.dates, psr_pct = result.robustness.psr_pct,
psr_inputs = result.robustness.psr_inputs.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
for line in open(".env", encoding="utf-8", errors="replace"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
from app.fund import pgstore  # noqa: E402
import psycopg  # noqa: E402

OUT = (sys.argv[1] if len(sys.argv) > 1 else
       os.path.join(ROOT, "docs", "drafts", "data", "d38_jobs_2026-08-24.json"))

out = []
with psycopg.connect(pgstore.dsn()) as conn, conn.cursor() as cur:
    cur.execute("SELECT job_id, result FROM fund_lean_jobs WHERE result IS NOT NULL")
    for jid, res in cur.fetchall():
        if not isinstance(res, dict):
            continue
        d = res.get("daily_returns") or {}
        out.append({
            "job_id": jid,
            "psr_pct": (res.get("robustness") or {}).get("psr_pct"),
            "stats": {k: res.get("statistics", {}).get(k) for k in
                      ("Sharpe Ratio", "Annual Standard Deviation",
                       "Probabilistic Sharpe Ratio", "Compounding Annual Return",
                       "Net Profit")},
            "present": d.get("present"),
            "series": d.get("strategy") if d.get("present") else None,
            "dates": d.get("dates") if d.get("present") else None,
            "psr_inputs": (res.get("robustness") or {}).get("psr_inputs"),
        })
print("rows", len(out))
json.dump(out, open(OUT, "w"))
print("wrote", OUT)
