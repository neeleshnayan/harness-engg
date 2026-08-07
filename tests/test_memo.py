"""Memo aggregate — drafted against a thesis, links back, finalizes."""

import pytest

from app.fund.memo import MemoError, MemoService
from app.fund.thesis import ThesisService


def test_memo_requires_thesis_and_title(wire):
    svc = MemoService(store=wire.store)
    with pytest.raises(MemoError):
        svc.create({"title": "no thesis"}, actor="clark")
    with pytest.raises(MemoError):
        svc.create({"thesis_id": "t1"}, actor="clark")  # no title


def test_memo_links_back_to_thesis(wire):
    theses = ThesisService(store=wire.store)
    t = theses.create({"title": "Long AAPL"}, actor="rushi")["thesis_id"]
    memos = MemoService(store=wire.store)
    m = memos.create({
        "thesis_id": t, "title": "AAPL into the print",
        "recommendation": "Buy 2% NAV", "conviction": "high",
        "sections": {"Valuation": "20x fwd", "Risks": "guidance cut"},
    }, actor="clark")
    assert m["status"] == "draft" and m["author"] == "clark"
    # the thesis now references the memo without a second write
    assert m["memo_id"] in theses.get(t)["memo_ids"]
    # scoped listing
    assert [x["memo_id"] for x in memos.list(thesis_id=t)] == [m["memo_id"]]


def test_memo_finalize(wire):
    theses = ThesisService(store=wire.store)
    t = theses.create({"title": "T"}, actor="r")["thesis_id"]
    memos = MemoService(store=wire.store)
    m = memos.create({"thesis_id": t, "title": "M"}, actor="clark")["memo_id"]
    assert memos.finalize(m, actor="rushi")["status"] == "final"
