"""The map — where absence is visible.

Every test here is about a property a RANKED LIST could not have. A list shows
what exists in some order; the whole reason for a map is that it also shows
what is missing, how much ground is unwalked, and how the view distorts.
"""

import pytest

from app.fund.observations import CATEGORIES
from app.fund.researchmap import build


class FakeObs:
    def __init__(self, rows, tickers=None, filings=None):
        self._rows = rows
        self._tickers = tickers if tickers is not None else len({r["ticker"] for r in rows})
        self._filings = filings if filings is not None else len(rows)

    def coverage(self):
        return {"observations": len(self._rows), "tickers": self._tickers,
                "filings_read": self._filings, "last_extracted_at": None}

    def recent(self, limit=2000, **kw):
        return self._rows[:limit]


def _o(ticker, category, filed="2026-06-30"):
    return {"ticker": ticker, "category": category, "filed": filed,
            "form": "10-Q", "url": "u", "observation": "x", "quote": "q",
            "read_partial_filing": False, "extracted_at": "2026-08-17T00:00:00+00:00"}


def test_every_category_appears_even_when_empty():
    """THE property. A list would simply not mention margin; the map has to
    show an empty region there, because that is the finding."""
    m = build(FakeObs([_o("A", "liquidity")]))
    shown = {r["category"] for r in m["regions"]}
    assert shown == set(CATEGORIES)
    empty = {r["category"] for r in m["regions"] if r["empty"]}
    assert "margin" in empty and "guidance" in empty


def test_empty_regions_are_counted_and_named_in_the_warnings():
    m = build(FakeObs([_o("A", "liquidity")]))
    assert m["totals"]["empty_regions"] == len(CATEGORIES) - 1
    assert any("nothing at all in" in w for w in m["projection"]["warnings"])
    assert any("margin" in w for w in m["projection"]["warnings"])


def test_a_dominant_region_is_flagged_without_being_corrected():
    """The concentration may be the market having one story. The map says it
    cannot tell, rather than quietly rebalancing."""
    rows = [_o("A", "liquidity") for _ in range(7)] + [_o("B", "segment")]
    m = build(FakeObs(rows))
    w = " ".join(m["projection"]["warnings"])
    assert "liquidity" in w
    assert "cannot yet tell" in w or "nothing here can yet tell" in w


def test_a_balanced_map_raises_no_dominance_warning():
    rows = [_o("A", c) for c in ("liquidity", "margin", "guidance", "segment")]
    m = build(FakeObs(rows))
    assert not any("of observations are" in w for w in m["projection"]["warnings"])


def test_chosen_and_unchosen_projections_are_distinguished():
    """The capacity filter is a tunnel we picked; the extractor's preference
    for balance-sheet quotes is not. Only the second is a defect."""
    m = build(FakeObs([_o("A", "liquidity")]))
    filters = {f["filter"]: f["chosen"] for f in m["projection"]["filters"]}
    assert filters["capacity"] is True
    assert filters["extraction bias"] is False


def test_extent_uses_the_true_universe_size_not_a_page_of_it():
    """The bug this pins: using the length of a limited page reported '3 of
    2,000' for a band holding 5,196 — flattering coverage on the one view
    built to be honest."""
    m = build(FakeObs([_o("A", "liquidity")], tickers=3),
              hunting_ground_size=5196)
    assert m["extent"]["tickers_available"] == 5196
    assert m["extent"]["coverage_pct"] == pytest.approx(0.058, abs=0.001)
    assert "unexplored" in m["extent"]["note"]


def test_unexplored_ground_is_stated_before_anything_else():
    """Arranging eleven observations beautifully says nothing about five
    thousand unopened names, and that is the largest hole on the map."""
    m = build(FakeObs([_o("A", "liquidity")], tickers=3), hunting_ground_size=5196)
    assert list(m.keys())[0] == "extent"


def test_a_map_with_no_observations_is_still_a_map():
    """An empty corpus must render as terrain nobody has walked, not as an
    error or an empty page."""
    m = build(FakeObs([]))
    assert len(m["regions"]) == len(CATEGORIES)
    assert all(r["empty"] for r in m["regions"])
    assert m["totals"]["observations"] == 0


def test_regions_carry_the_tickers_behind_them():
    """One-click traversal needs the map to say what is underneath a region,
    or the operator lands on a number with no way in."""
    m = build(FakeObs([_o("A", "liquidity"), _o("B", "liquidity")]))
    liq = next(r for r in m["regions"] if r["category"] == "liquidity")
    assert liq["tickers"] == ["A", "B"]


def test_an_unknown_category_still_gets_a_region():
    """A category the extractor can emit but the map cannot draw would be an
    invisible region — the one thing this design must never have."""
    m = build(FakeObs([_o("A", "brand_new_thing")]))
    assert any(r["category"] == "brand_new_thing" for r in m["regions"])
