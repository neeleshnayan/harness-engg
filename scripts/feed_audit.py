"""Cross-check the backtest feed against an independent vendor.

Every verdict this fund has issued rests on one price series nobody has checked.
A quiet adjustment error is invisible in exactly the way that matters: a missed
split looks like a crash, and price-return where total-return is needed looks like
persistent underperformance in every dividend-paying name. Neither announces
itself; both would be read as alpha or its absence.

The universe contains a REIT (DEI) and several other high-payout names, so the
total-return question is not hypothetical. If the spine's series is price-return
and the benchmark comparison assumes otherwise, the equal-weight bar every
candidate is measured against is systematically understated — which would mean the
gate has been too GENEROUS about "beats the benchmark" all along.

Method: same symbol, same window, both sources, compared on the dates they share.
Reports median and worst absolute deviation in daily close, and separately the
END-TO-END return difference, which is where a dividend-treatment mismatch shows
up as a steady drift rather than a spike.

A disagreement here is not automatically the spine being wrong. Two vendors
legitimately differ on adjustment timing. What matters is the SIZE and the SHAPE:
noise around zero is vendor difference, a one-day step is a corporate action
handled on different dates, and a steady drift is a different return definition.
"""
import json
import os
import statistics
import sys

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("FUND_STORE", "postgres")

import requests  # noqa: E402

from app.fund import polygon as pg  # noqa: E402
from app.fund.polygon import RateLimited  # noqa: E402

B = "http://127.0.0.1:8090/api/v1/fund"
START, END = "2025-01-01", "2026-08-14"

UNIVERSE = ["ALKT", "CON", "ATRC", "SOBO", "ADMA", "CLOV", "BLZE", "ZIM",
            "GHM", "NBR", "GCT", "DEI", "PRVA", "KOPN", "AVPT", "LINC",
            "CRAI", "ANIP", "NTCT", "TRN"]
NAMES = [s.strip().upper() for s in sys.argv[1].split(",")] if len(sys.argv) > 1 \
    else UNIVERSE


def spine_bars(sym: str) -> dict:
    r = requests.get(f"{B}/marketdata/bars",
                     params={"symbol": sym, "lookback_days": 900,
                             "format": "csv"}, timeout=120)
    r.raise_for_status()
    out = {}
    for line in r.text.strip().splitlines():
        if not line.strip():
            continue
        try:
            d, c = line.split(",")
            out[d] = float(c)
        except ValueError:
            continue
    return out


def main() -> None:
    rows, skipped = [], []
    for i, sym in enumerate(NAMES, 1):
        try:
            spine = spine_bars(sym)
        except Exception as e:  # noqa: BLE001
            skipped.append((sym, f"spine: {e}"[:90]))
            print(f"[{i}/{len(NAMES)}] {sym}: spine unavailable", flush=True)
            continue
        try:
            p = pg.daily_bars(sym, START, END)
        except RateLimited:
            # Not a finding about the symbol. Left unrecorded so a re-run picks
            # it up, rather than entering the audit as a disagreement of zero.
            skipped.append((sym, "rate limited - not recorded"))
            print(f"[{i}/{len(NAMES)}] {sym}: rate limited, skipped", flush=True)
            continue
        except Exception as e:  # noqa: BLE001
            skipped.append((sym, f"vendor: {e}"[:90]))
            print(f"[{i}/{len(NAMES)}] {sym}: vendor unavailable", flush=True)
            continue

        vendor = dict(zip(p.get("dates") or [], p.get("closes") or []))
        shared = sorted(set(spine) & set(vendor))
        if len(shared) < 30:
            skipped.append((sym, f"only {len(shared)} shared dates"))
            print(f"[{i}/{len(NAMES)}] {sym}: too few shared dates", flush=True)
            continue

        devs = [abs(spine[d] - vendor[d]) / vendor[d] * 100.0
                for d in shared if vendor[d]]
        spine_ret = (spine[shared[-1]] / spine[shared[0]] - 1) * 100.0
        vendor_ret = (vendor[shared[-1]] / vendor[shared[0]] - 1) * 100.0
        rows.append({
            "ticker": sym, "shared_days": len(shared),
            "median_abs_dev_pct": round(statistics.median(devs), 4),
            "worst_abs_dev_pct": round(max(devs), 4),
            "spine_return_pct": round(spine_ret, 2),
            "vendor_return_pct": round(vendor_ret, 2),
            "return_gap_pct_pts": round(spine_ret - vendor_ret, 2),
        })
        print(f"[{i}/{len(NAMES)}] {sym}: {len(shared)}d  median dev "
              f"{rows[-1]['median_abs_dev_pct']:.3f}%  worst "
              f"{rows[-1]['worst_abs_dev_pct']:.2f}%  return gap "
              f"{rows[-1]['return_gap_pct_pts']:+.2f}pp", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("FEED AUDIT - spine bars vs an independent vendor", flush=True)
    print("=" * 70, flush=True)
    if not rows:
        print("  nothing was comparable - no evidence either way, which is not "
              "the same as agreement", flush=True)
        if skipped:
            for s, why in skipped:
                print(f"    {s}: {why}", flush=True)
        return

    meds = [r["median_abs_dev_pct"] for r in rows]
    gaps = [r["return_gap_pct_pts"] for r in rows]
    print(f"  compared {len(rows)} names, skipped {len(skipped)}", flush=True)
    print(f"  median daily deviation, across names: "
          f"{statistics.median(meds):.4f}%", flush=True)
    print(f"  worst single-day deviation seen: "
          f"{max(r['worst_abs_dev_pct'] for r in rows):.2f}%", flush=True)
    print(f"  end-to-end return gap: median {statistics.median(gaps):+.2f}pp, "
          f"range {min(gaps):+.2f} to {max(gaps):+.2f}", flush=True)

    # The shape is the diagnosis, not the size alone.
    drifters = [r for r in rows if abs(r["return_gap_pct_pts"]) > 2.0]
    steppers = [r for r in rows if r["worst_abs_dev_pct"] > 5.0]
    print(flush=True)
    if not drifters and not steppers:
        print("  VERDICT: the two sources agree within vendor noise. The feed is",
              flush=True)
        print("  not silently wrong about splits or dividends on these names.",
              flush=True)
    else:
        if steppers:
            print(f"  {len(steppers)} name(s) show a large single-day step - the",
                  flush=True)
            print("  signature of a corporate action applied on different dates:",
                  flush=True)
            for r in steppers:
                print(f"    {r['ticker']}: worst day "
                      f"{r['worst_abs_dev_pct']:.1f}%", flush=True)
        if drifters:
            print(f"  {len(drifters)} name(s) show a steady end-to-end drift - the",
                  flush=True)
            print("  signature of a different RETURN DEFINITION (price vs total):",
                  flush=True)
            for r in drifters:
                print(f"    {r['ticker']}: spine {r['spine_return_pct']:+.1f}% vs "
                      f"vendor {r['vendor_return_pct']:+.1f}% "
                      f"({r['return_gap_pct_pts']:+.1f}pp)", flush=True)
            print(flush=True)
            print("  If the drift is one-directional across dividend payers, the",
                  flush=True)
            print("  equal-weight benchmark is understated and the gate has been",
                  flush=True)
            print("  too GENEROUS about 'beats the benchmark'.", flush=True)

    if skipped:
        print(f"\n  skipped ({len(skipped)}) - absent, not agreeing:", flush=True)
        for s, why in skipped:
            print(f"    {s}: {why}", flush=True)

    with open("docs/feed_audit_results.json", "w") as fh:
        json.dump({"window": [START, END], "compared": rows,
                   "skipped": [{"ticker": s, "why": w} for s, w in skipped]},
                  fh, indent=1)
    print("\n  written to docs/feed_audit_results.json", flush=True)


if __name__ == "__main__":
    main()
