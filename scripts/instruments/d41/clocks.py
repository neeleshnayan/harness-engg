"""D41 measurement: what clock the belt's stored series actually runs on, and
what the engine's per-observation target is worth ON THAT CLOCK.

Reads the adversary's already-pulled jobs.json (no PG hit). Prints the
population summary the D41 comments and the register draft cite, plus a NULL
TEST: a synthetic series with exactly 252 observations per year must put the
hurdle at exactly 1.00, because that is the engine's own convention and the
whole claim is that the two only differ through the clock.

PROMOTED TO THE SHELF (D41) because the register draft for `min_psr_pct` cites
this table as the evidence for its `why`, and a register entry whose evidence
lives in a session scratchpad is a citation that stops resolving the moment the
session ends. The jobs dump is a positional argument rather than a constant for
the same reason: repoint it, do not edit it.

Reproduce:
  ./venv/Scripts/python.exe scripts/instruments/d41/clocks.py <tree> [jobs.json]

<tree> is a ClarkHarness checkout (its `app.fund.statistics` is what gets
measured). [jobs.json] is a read-only dump of stored belt results — a JSON list
of rows with `present`, `series` and `dates` — produced by one SELECT over
`fund_lean_jobs`. It defaults to the D38 pull if that path still exists, and
REFUSES rather than reporting an empty population if it does not: a band
printed over zero rows is the failure this instrument's null test exists to
make impossible.
"""
import json
import math
import os
import statistics as pystat
import sys
from datetime import date, timedelta

ROOT = sys.argv[1]
sys.path.insert(0, ROOT)
from app.fund import statistics as st  # noqa: E402

#: The D38 pull. Kept as the default so the figures in the register draft
#: reproduce verbatim; pass a fresh dump as argv[2] to re-measure a grown belt.
JOBS = (sys.argv[2] if len(sys.argv) > 2 else
        r"C:\Users\user\AppData\Local\Temp\claude"
        r"\C--Users-user-Documents-Krypton-Fund"
        r"\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\advd38\jobs.json")

if not os.path.exists(JOBS):
    raise SystemExit(
        f"the jobs dump is not at {JOBS}. Pass one as the second argument — "
        f"this instrument REFUSES rather than printing bands over zero rows, "
        f"because an empty population and a uniform one look identical in a "
        f"min/median/max table.")

rows = json.load(open(JOBS, encoding="utf-8"))
print("stored results:", len(rows))

per_obs = st.lean_psr_target()["per_obs"]
print(f"engine per-observation target 1/sqrt(252) = {per_obs:.6f}")
print(f"engine convention annualised at 252        = "
      f"{per_obs * math.sqrt(252):.6f}")

clocks, hurdles, demands, alt_clocks = [], [], [], []
usable = 0
for r in rows:
    if not r.get("present") or not r.get("series") or not r.get("dates"):
        continue
    series = [x for x in r["series"] if isinstance(x, (int, float))]
    if len(series) < 2:
        continue
    clock = st.observations_per_year([str(d)[:10] for d in r["dates"]],
                                     len(series))
    if not clock.get("usable"):
        continue
    usable += 1
    k = float(clock["obs_per_year"])
    clocks.append(k)
    # The n-instead-of-(n-1) convention, on the same rows.
    alt_clocks.append(len(series) / (float(clock["span_days"]) / 365.25))
    hurdles.append(per_obs * math.sqrt(k))
    bar = st.sharpe_bar_for_psr(65.0, series, per_obs)
    if bar.get("measurable"):
        demands.append(float(bar["sharpe_per_obs"]) * math.sqrt(k))


def band(name, xs, unit=""):
    if not xs:
        print(f"{name}: ABSENT (n=0)")
        return
    xs = sorted(xs)
    print(f"{name}: n={len(xs)} min={xs[0]:.4f} median={pystat.median(xs):.4f} "
          f"max={xs[-1]:.4f}{unit}")


print(f"series usable for a clock: {usable}")
band("  obs_per_year", clocks)
# THE OTHER CONVENTION, measured rather than argued. `observations_per_year`
# divides by the INTERVAL count (n-1); dividing by the observation count (n)
# overstates the rate by 1/(n-1). That difference is the whole distance between
# the 365.25 this fund measures and the "366.3" that has been quoted for the
# same population, and it is worth printing side by side so nobody has to
# reconstruct which convention produced which figure.
band("  obs_per_year IF divided by n instead of n-1", alt_clocks)
band("  hurdle on the series' own clock (annualised excess Sharpe)", hurdles)
band("  what 65% demands on the series' own clock", demands)

# --- THE NULL TEST -------------------------------------------------------
# A series observed exactly 252 times a year must put the hurdle at exactly
# 1.00 — that is the engine's own convention, and if this arm does not return
# 1.00 the instrument above is measuring something other than the clock.
d0 = date(2016, 1, 3)
dates, i, held = [], 0, 0
while held < 252 * 4:
    d = d0 + timedelta(days=i)
    i += 1
    if d.weekday() < 5:                      # ~260/yr, not 252 — see below
        dates.append(d.isoformat())
        held += 1
weekday = st.observations_per_year(dates, len(dates))
print(f"NULL(business-day series): obs_per_year={weekday['obs_per_year']:.4f} "
      f"hurdle={per_obs * math.sqrt(float(weekday['obs_per_year'])):.6f}")
print("NULL(exact 252 clock)      : hurdle="
      f"{per_obs * math.sqrt(252.0):.6f}  (must read 1.000000)")
