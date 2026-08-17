"""The map. Not a ranking — a ranking hides what it flattened.

A ranked list collapses many dimensions into one order, and once collapsed you
cannot see what was lost. A map preserves structure, and that single property
does the work: on a map ABSENCE IS VISIBLE. An empty region is obvious, where a
missing list entry is simply not there and nobody thinks to ask about it.

So this returns terrain rather than a recommendation. Every category is
present even when it holds nothing, because "we have read zero margin
observations this quarter" is the most useful sentence this module can produce
and a list would never say it.

Two things it must always declare, because the operator is assumed lazy and
will trust the default view rather than audit it:

  EXTENT — what has been read, and against what it could have read. Right now
  that ratio is the largest hole on the map by an enormous margin, and no
  amount of arranging the observations we have would reveal it.

  PROJECTION — how the map distorts. Mercator does not omit Greenland; it
  inflates it, systematically, while looking complete. Our capacity filter is a
  projection we CHOSE and should keep. The extraction model's preference for
  quoting balance-sheet facts over margin commentary is one nobody chose. Only
  the second is a defect, and the legend has to say both so they can be told
  apart.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Every category the map draws, present or empty. Taken from the extractor so
#: the two cannot drift — a category the model can emit but the map cannot show
#: would be an invisible region.
from app.fund.observations import CATEGORIES  # noqa: E402

#: A region holding this share or more of everything is called out. Not to
#: correct it — the market may genuinely have one story this quarter — but so a
#: concentration is never mistaken for a complete picture.
DOMINANCE_WARN = 0.5


def build(observations: Any, universe: Any = None,
          hunting_ground_size: Optional[int] = None,
          adv_band: Optional[tuple[float, float]] = None) -> dict[str, Any]:
    """The terrain: what has been read, what it said, and where nothing is.

    ``adv_band`` makes the extent measure the ground the fund CLAIMS to fish in
    rather than the whole market. Without it the headline was 84 of 5,196 names —
    a denominator of every listed company, which reading a thousand mega-caps
    would move and which reading forty band names would barely touch. The band
    figure has the opposite property, which is why it belongs on the face of the
    map.
    """
    coverage = (observations.coverage(adv_lo=adv_band[0], adv_hi=adv_band[1])
                if adv_band else observations.coverage())
    rows = observations.recent(limit=2000)

    by_cat: dict[str, dict[str, Any]] = {
        c: {"category": c, "count": 0, "tickers": set(), "latest": None}
        for c in CATEGORIES
    }
    by_ticker: dict[str, dict[str, Any]] = {}
    for o in rows:
        c = o.get("category") or "other"
        cell = by_cat.setdefault(
            c, {"category": c, "count": 0, "tickers": set(), "latest": None})
        cell["count"] += 1
        cell["tickers"].add(o["ticker"])
        if cell["latest"] is None or o["filed"] > cell["latest"]:
            cell["latest"] = o["filed"]

        t = by_ticker.setdefault(
            o["ticker"], {"ticker": o["ticker"], "count": 0, "categories": set()})
        t["count"] += 1
        t["categories"].add(c)

    total = sum(c["count"] for c in by_cat.values())
    regions = [
        {
            "category": c["category"],
            "count": c["count"],
            "tickers": sorted(c["tickers"]),
            "latest": c["latest"],
            "share": round(c["count"] / total, 3) if total else 0.0,
            # The point of the map. An empty region is a finding, not a gap in
            # the data structure, and it is labelled as one.
            "empty": c["count"] == 0,
        }
        for c in by_cat.values()
    ]
    regions.sort(key=lambda r: (-r["count"], r["category"]))

    return {
        "extent": _extent(coverage, universe, hunting_ground_size),
        "projection": _projection(regions, total),
        "regions": regions,
        "tickers": sorted(
            ({"ticker": t["ticker"], "count": t["count"],
              "categories": sorted(t["categories"])} for t in by_ticker.values()),
            key=lambda t: -t["count"]),
        "totals": {"observations": total, "regions": len(regions),
                   "empty_regions": sum(1 for r in regions if r["empty"])},
    }


def _extent(coverage: dict[str, Any], universe: Any,
            hunting_ground_size: Optional[int]) -> dict[str, Any]:
    """What has been read, against what could have been.

    Deliberately the first thing on the map. Arranging eleven observations
    beautifully would say nothing about the five thousand names nobody has
    opened, and that is by far the largest empty region here.
    """
    read_tickers = int(coverage.get("tickers") or 0)
    candidates = hunting_ground_size
    if candidates is None and universe is not None:
        try:
            candidates = int(universe.stats().get("symbols") or 0)
        except Exception:  # noqa: BLE001
            candidates = None

    pct = (round(read_tickers / candidates * 100, 3)
           if candidates else None)
    # Band coverage LEADS when it is available. Whole-market coverage answers
    # "how much of the market have we read", which is not the fund's question:
    # the thesis says the edge lives in one ADV band, so the number that measures
    # progress is coverage OF THAT BAND. Both are reported, because the gap
    # between them is itself the finding — 84 names read of which one was in the
    # tested universe is breadth aimed at the wrong population.
    band = coverage.get("band") or {"measured": False}
    return {
        "filings_read": int(coverage.get("filings_read") or 0),
        "observations": int(coverage.get("observations") or 0),
        "tickers_read": read_tickers,
        "tickers_available": candidates,
        "coverage_pct": pct,
        "band": band,
        "headline": ("band" if band.get("measured") else "market"),
        "last_read_at": coverage.get("last_extracted_at"),
        "note": _extent_note(read_tickers, candidates, pct, band),
    }


def _extent_note(read_tickers: int, candidates: Optional[int],
                 pct: Optional[float], band: dict[str, Any]) -> str:
    """One sentence, leading with whichever denominator is the fund's own."""
    if band.get("measured") and band.get("names_in_band"):
        return (f"{band['names_read']} of {band['names_in_band']:,} names in the "
                f"capacity band read ({band.get('coverage_pct')}%) — this is the "
                f"ground the thesis claims. {read_tickers} names have been read "
                f"in total, so the difference is reading that does not bear on it")
    if candidates and read_tickers < candidates * 0.5:
        return (f"read {read_tickers} of {candidates:,} names ({pct}%) — the rest "
                f"of the map is unexplored, and nothing about the observations we "
                f"do have tells us what is out there")
    return f"read {read_tickers} names"


def _projection(regions: list[dict[str, Any]], total: int) -> dict[str, Any]:
    """How this map distorts, stated rather than corrected.

    A quota that forced balance across categories would hide the very question
    worth asking: is this concentration the market having one story, or the
    extractor preferring one kind of sentence? We cannot yet tell those apart,
    and saying so is more useful than papering over it.
    """
    filters = [
        {"filter": "capacity", "chosen": True,
         "note": "only names a large fund cannot build a position in — a tunnel "
                 "we chose, and the reason the fund's size is an advantage here"},
        {"filter": "forms", "chosen": True,
         "note": "10-Q and 8-K only; no transcripts, no proxies, no S-1s"},
        {"filter": "section", "chosen": True,
         "note": "MD&A where the filing has one, so the financial statements "
                 "themselves are not read directly"},
        {"filter": "extraction bias", "chosen": False,
         "note": "the model quotes balance-sheet facts more readily than margin "
                 "or guidance commentary, because they are easier to cite "
                 "verbatim — this one nobody chose"},
    ]
    top = regions[0] if regions else None
    warnings = []
    if top and total and top["share"] >= DOMINANCE_WARN:
        warnings.append(
            f"{top['share']:.0%} of observations are '{top['category']}'. That "
            f"is either the market having one story right now or the extractor "
            f"preferring one kind of sentence, and nothing here can yet tell "
            f"those apart — read the cluster before trusting its size")
    empties = [r["category"] for r in regions if r["empty"]]
    if empties:
        warnings.append(
            f"nothing at all in: {', '.join(empties)} — visible here precisely "
            f"because a list would simply not have mentioned them")
    return {"filters": filters, "warnings": warnings}
