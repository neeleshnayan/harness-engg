"""Evidence (a): the cache and the direct fetch must produce IDENTICAL BYTES.

Run before trusting a bar snapshot on the belt. For one real candidate's whole
leg set this fetches every leg BOTH ways — from the pinned snapshot and straight
from the vendor — and byte-compares the CSV the LEAN container would actually
read (``date,close`` per line, which is what fund.py streams for format=csv).

Why bytes and not "close enough": this cache sits in the measurement instrument.
A tolerance here would mean the belt's verdicts depend on which path a container
happened to take, and the whole point of a candidate-scoped snapshot is that
they cannot. If this script reports a single mismatch, the cache is wrong.

    python scripts/belt/verify_bar_snapshot.py monthend_rebalance_flow
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.fund import barcache                                       # noqa: E402
from app.fund.leanrunner import (_declared_lookback_days,           # noqa: E402
                                 _declared_universe)
from app.fund.marketdata import fetch_daily_bars                    # noqa: E402


def _csv(dates, closes) -> str:
    """Exactly what fund.py:get_bars streams for format=csv."""
    return "\n".join(f"{d},{c}" for d, c in zip(dates, closes))


def main(algorithm: str) -> int:
    root = Path(__file__).resolve().parents[2]
    # An algorithm NAME resolves inside this workspace; an explicit PATH lets the
    # check run against a candidate that is not committed here (Entry 20's
    # 170-name algorithm is untracked in the live tree), without copying someone
    # else's file into this repo to verify it.
    src = (Path(algorithm) if algorithm.endswith(".py")
           else root / "lean_workspace" / "algorithms" / algorithm / "main.py")
    code = src.read_text(encoding="utf-8")
    universe = _declared_universe(code)
    lookback = _declared_lookback_days(code)
    print(f"algorithm : {algorithm}")
    print(f"universe  : {universe}")
    print(f"lookback  : {lookback}")
    if not universe or lookback is None:
        print("REFUSED: this algorithm would not be snapshotted at all "
              "(no single UNIVERSE / lookback_days), so there is nothing to verify.")
        return 2

    snap = barcache.prefetch(universe, candidate="verify", lookback_days=lookback)
    print(f"prefetch  : {len(snap.legs)} legs in {snap.prefetch_seconds}s "
          f"({len(snap.unavailable)} unavailable)")
    if snap.unavailable:
        print(f"UNAVAILABLE: {snap.unavailable}")

    # The direct side is fetched in parallel purely so a 170-leg check finishes
    # in a minute instead of six. Byte equality does not depend on timing, and
    # each leg is still one independent vendor call, exactly as a container makes.
    from concurrent.futures import ThreadPoolExecutor

    def _direct(sym):
        try:
            return sym, fetch_daily_bars(sym, lookback_days=lookback), None
        except Exception as e:                                      # noqa: BLE001
            return sym, None, f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        direct_by_sym = {s: (b, e) for s, b, e in pool.map(_direct, universe)}

    compared = 0
    mismatches = []
    with barcache.activate(snap):
        for sym in universe:
            pinned = barcache.serve(sym, lookback_days=lookback)
            if pinned is None:
                mismatches.append((sym, "snapshot MISS — no pinned leg to compare"))
                continue
            direct, err = direct_by_sym.get(sym, (None, "not fetched"))
            if direct is None:
                mismatches.append((sym, f"direct fetch failed: {err}"))
                continue
            a = _csv(pinned.dates, pinned.closes)
            b = _csv(direct.dates or [], direct.closes or [])
            compared += 1
            if a != b:
                # Report the FIRST differing line verbatim, not a summary.
                la, lb = a.splitlines(), b.splitlines()
                where = next((i for i in range(min(len(la), len(lb)))
                              if la[i] != lb[i]), min(len(la), len(lb)))
                mismatches.append((
                    sym,
                    f"cache {len(la)} lines / direct {len(lb)} lines; "
                    f"first difference at line {where}: "
                    f"cache={la[where] if where < len(la) else '<none>'!r} "
                    f"direct={lb[where] if where < len(lb) else '<none>'!r}"))
            elif compared <= 5 or len(universe) <= 20:
                print(f"  {sym:<6} IDENTICAL  {len(a):>8} bytes  "
                      f"{len(pinned.dates):>5} bars  {pinned.first}..{pinned.last}  "
                      f"src={pinned.source}")
            elif compared == 6:
                print(f"  ... ({len(universe) - 5} more legs, "
                      f"printed only on mismatch)")

    print(f"\ncompared  : {compared} legs")
    print(f"mismatches: {len(mismatches)}")
    for sym, why in mismatches:
        print(f"  MISMATCH {sym}: {why}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1
                          else "monthend_rebalance_flow"))
