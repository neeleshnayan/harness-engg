"""Risk history: the drift chart's data must accrue without becoming noise."""

from app.fund.riskhistory import RiskHistory


def _sink(wire):
    # The wire fixture installed the fake firestore; RiskHistory picks it up
    # through the app's own db() factory.
    return RiskHistory()


def test_append_and_read_back_in_chart_order(wire):
    h = _sink(wire)
    assert h.append({"portfolio_vol_pct": 20.0, "effective_bets": 3.0}, fingerprint="book-a")
    pts = h.recent()
    assert len(pts) == 1
    assert pts[0]["portfolio_vol_pct"] == 20.0
    assert pts[0]["fingerprint"] == "book-a"
    assert "ts" in pts[0]


def test_same_book_within_gap_is_deduped(wire):
    """A nervous operator clicking Recompute must not turn the series into
    noise: same fingerprint within the gap refines the picture, it does not
    add information."""
    h = _sink(wire)
    assert h.append({"portfolio_vol_pct": 20.0}, fingerprint="book-a") is True
    assert h.append({"portfolio_vol_pct": 20.1}, fingerprint="book-a") is False
    assert len(h.recent()) == 1


def test_changed_book_appends_immediately(wire):
    """A fill changes the book; the next point must land at once — drift after
    a trade is exactly what the chart exists to show."""
    h = _sink(wire)
    assert h.append({"portfolio_vol_pct": 20.0}, fingerprint="book-a") is True
    assert h.append({"portfolio_vol_pct": 24.0}, fingerprint="book-b") is True
    pts = h.recent()
    # Both points present; intra-microsecond order is not meaningful (the two
    # appends can share a timestamp on a coarse clock).
    assert sorted(p["fingerprint"] for p in pts) == ["book-a", "book-b"]
