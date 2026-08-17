"""Coverage must be measured against the ground the thesis claims.

The finding that prompted this: 84 names read, of which exactly ONE was in the
tested universe. Whole-market coverage reported that as progress, because its
denominator was every listed company — a number reading a thousand mega-caps
would move and reading forty band names would barely touch. The band figure has
the opposite property, so it leads.
"""

from app.fund.researchmap import _extent, _extent_note


def test_band_coverage_leads_the_headline_when_measured():
    band = {"measured": True, "names_in_band": 200, "names_read": 12,
            "coverage_pct": 6.0, "note": "..."}
    out = _extent({"tickers": 84, "filings_read": 84, "observations": 376,
                   "band": band}, universe=None, hunting_ground_size=5196)
    assert out["headline"] == "band"
    assert "12 of 200 names in the capacity band" in out["note"]
    # The market number is still reported — the GAP between them is the finding.
    assert out["tickers_read"] == 84
    assert out["tickers_available"] == 5196


def test_without_band_bounds_the_market_number_leads_rather_than_a_guess():
    """A coverage ratio against an assumed band would be a number about nothing,
    so the band figure is absent rather than invented."""
    out = _extent({"tickers": 84, "filings_read": 84, "observations": 376,
                   "band": {"measured": False}}, universe=None,
                  hunting_ground_size=5196)
    assert out["headline"] == "market"
    assert out["band"]["measured"] is False
    assert "5,196" in out["note"]


def test_reading_the_wrong_population_is_said_out_loud():
    """Breadth aimed off-thesis must not read as coverage of the thesis."""
    note = _extent_note(84, 5196, 1.617,
                        {"measured": True, "names_in_band": 200,
                         "names_read": 0, "coverage_pct": 0.0})
    assert "0 of 200" in note
    assert "does not bear on it" in note


def test_a_band_with_no_measured_names_has_no_denominator():
    """An empty band is a stale universe, not full coverage — and 0/0 must never
    render as 100%."""
    from app.fund.observations import _band_note
    note = _band_note(read=0, total=0, read_anywhere=84)
    assert "no denominator" in note
