"""Point the filings reader at the hunting ground. Task #28.

The gap this closes is embarrassing when written down: the fund has read 376
filings from 84 tickers, and **not one of them was chosen because it was in the
capacity band**. Band coverage was 0 of 874. Meanwhile every research candidate
ever tested — all five ideas — was a parameter sweep over textbook signals on
liquid names: moving averages, momentum on large-cap tech, mean reversion on
cyclicals. Those are the most heavily mined ideas in finance and the realistic
prior that a parameter sweep over them holds undiscovered edge is about zero.

So the belt got faster all week while pointed at an empty field. This aims it
somewhere the prior is at least not obviously zero.

WHICH NAMES, AND WHY NOT THE SMALL ONES ONLY

The first version of this read the SMALLEST names in the band, arguing that a
large fund could not build a position in them. That argument is rejected: whether
somebody else could hold a name says nothing about whether WE make money on it. If
NVDA is the right asset it is the right asset. At $2k essentially the entire liquid
market is tradeable by us, so there is no case for narrowing the universe on
exclusivity.

What survives is a hypothesis, not a mandate: a less-covered name is more likely to
carry something unpriced in its filings. That is worth TESTING — and it cannot be
tested by only ever reading one end of the range. So the default samples evenly
across ADV, from about $9M to $250M, and `--spread smallest|largest` exists so the
hypothesis can be run as an experiment rather than assumed as a policy.

WHAT THIS DOES NOT DO, said plainly

It produces OBSERVATIONS, not strategies and not trade ideas. An observation is a
checkable statement carrying a verbatim quote matched against the filing before
storage. Turning one into a position is a separate step a person takes in the open,
and turning many into a testable rule is a separate step after that.

Nothing here improves the odds that the gate can SEE a modest edge — measured power
is 22.8% at Sharpe 1.0 on our history. This changes where we look, not how well we
can look.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import requests

sys.path.insert(0, ".")

B = "http://127.0.0.1:8090/api/v1/fund"


def _select(rows: list[dict], n: int, how: str) -> list[dict]:
    """Which names to read, and the reasoning is the point.

    An earlier version took the SMALLEST names, on the argument that a large fund
    could not build a position in them. That argument was rejected, correctly: it
    is a fact about other people's constraints, not about whether we make money.
    If NVDA is the right asset then it is the right asset, and at $2k essentially
    the whole liquid market is tradeable by us — so the universe should not be
    narrowed for exclusivity at all.

    What survives is much weaker and is a HYPOTHESIS rather than a mandate: a
    less-covered name is more likely to have something unpriced in its filings.
    That is testable later — do observations from thinner names predict better? —
    and it cannot be tested at all if we only ever read one end of the range.

    So the default samples EVENLY across ADV, from ~$9M to ~$250M. `smallest` and
    `largest` stay available precisely so the hypothesis can be run as an
    experiment instead of assumed as a policy.
    """
    rows = [r for r in rows if r.get("adv_usd")]
    if n >= len(rows) or how == "smallest":
        return rows[:n]
    if how == "largest":
        return rows[-n:]
    step = len(rows) / float(n)
    return [rows[int(i * step)] for i in range(n)]


def hunting_ground(limit: int, turnover_pct: float) -> list[dict]:
    r = requests.get(f"{B}/universe/hunting-ground",
                     params={"limit": limit, "turnover_pct": turnover_pct},
                     timeout=900)
    r.raise_for_status()
    return (r.json() or {}).get("names") or []


def coverage() -> dict:
    r = requests.get(f"{B}/research/observations", params={"limit": 1}, timeout=300)
    return (r.json() or {}).get("coverage") or {} if r.status_code == 200 else {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--names", type=int, default=120,
                    help="how many band names to read; see --spread for which")
    ap.add_argument("--per-ticker", type=int, default=2,
                    help="filings per name; the sweep skips ones already read")
    ap.add_argument("--turnover-pct", type=float, default=5.0)
    ap.add_argument("--batch", type=int, default=20,
                    help="names per request, so a failure costs one batch")
    ap.add_argument("--forms", default="10-Q,8-K")
    ap.add_argument("--spread", default="stratified",
                    choices=("stratified", "smallest", "largest"),
                    help="how to pick names across the ADV range")
    a = ap.parse_args()

    before = coverage()
    print("coverage BEFORE:", json.dumps(
        {k: v for k, v in before.items() if isinstance(v, (int, float))}))

    rows = [r for r in hunting_ground(2000, a.turnover_pct) if r.get("cik")]
    if not rows:
        print("the hunting ground returned nothing with a CIK — cannot read filings")
        return 1
    rows.sort(key=lambda r: r.get("adv_usd") or 0.0)
    picked = _select(rows, a.names, a.spread)
    lo = (picked[0].get("adv_usd") or 0) / 1e6
    hi = (picked[-1].get("adv_usd") or 0) / 1e6
    print(f"\n{len(picked)} band names, smallest ADV first: "
          f"${lo:.1f}M to ${hi:.1f}M")
    print(f"  {', '.join(r['symbol'] for r in picked[:12])}"
          f"{' ...' if len(picked) > 12 else ''}\n")

    forms = [f.strip() for f in a.forms.split(",") if f.strip()]
    # The endpoint's ACTUAL keys. The first version of this script read
    # read/stored/skipped/failed, none of which exist, so a run that stored 31
    # observations across 8 new tickers reported zeros and printed "NOTHING WAS
    # STORED". Third bug of this exact class in a day: reporting that reads a key
    # nothing returns is indistinguishable from the thing genuinely not happening.
    totals = {"filings_read": 0, "already_read": 0,
              "tickers_failed": 0, "observations_stored": 0}
    t0 = time.monotonic()
    for i in range(0, len(picked), a.batch):
        chunk = [r["symbol"] for r in picked[i:i + a.batch]]
        try:
            resp = requests.post(
                f"{B}/research/read",
                json={"tickers": chunk, "forms": forms,
                      "per_ticker": a.per_ticker},
                timeout=1800)
            resp.raise_for_status()
            got = resp.json()
        except Exception as e:  # noqa: BLE001
            # One batch failing must never stop the sweep, for the same reason
            # one awkward filing must not: a run that aborts on the first
            # bankruptcy reads the alphabet up to B.
            print(f"  batch {i // a.batch + 1}: FAILED "
                  f"({type(e).__name__}: {str(e)[:90]}) — stepping over it")
            continue
        for k in totals:
            totals[k] += int(got.get(k) or 0)
        print(f"  batch {i // a.batch + 1:>2} ({len(chunk)} names): "
              f"read {got.get('filings_read')}, "
              f"stored {got.get('observations_stored')}, "
              f"already {got.get('already_read')}, "
              f"failed {got.get('tickers_failed')}")

    dt = time.monotonic() - t0
    print(f"\ntotals after {dt / 60:.1f} min: {json.dumps(totals)}")

    after = coverage()
    print("coverage AFTER :", json.dumps(
        {k: v for k, v in after.items() if isinstance(v, (int, float))}))

    # Band coverage needs the band bounds supplied to the coverage endpoint, which
    # this script does not do — so it reports the OVERALL movement it can actually
    # measure rather than printing "None -> None" and calling it a result.
    band_before = before.get("observations")
    band_after = after.get("observations")
    print()
    if totals["observations_stored"] == 0:
        print("NOTHING WAS STORED. That is a finding, not a quiet no-op: either")
        print("  every filing was already read, or extraction produced nothing")
        print("  that survived verification. Check `failed` above before")
        print("  concluding the band has nothing to say.")
    else:
        print(f"{totals['observations_stored']} observation(s) stored. Total")
        print(f"  observations went {band_before} -> {band_after}.")
    print()
    print("These are OBSERVATIONS, not trade ideas and not strategies. Each is a")
    print("checkable statement carrying the verbatim quote it was matched against.")
    print("Turning one into a position is a separate step a person takes, in the")
    print("open — and turning many into a testable rule is another step after that.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
