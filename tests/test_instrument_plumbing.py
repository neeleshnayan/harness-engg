"""Part B: the fund's instruments say what they measured and what they did not.

Four defects, each measured before it was fixed:

  B1 — `/fund/tca`'s execution/total blocks averaged paper-venue zeros into
       Monitor's EXECUTION QUALITY panel. The paper connector fills at the same
       quote the pipeline records as arrival (`paper.py:116` / `pipeline.py:215`),
       so every paper fill contributes exactly 0.00bps of slippage BY
       CONSTRUCTION — the more the fund trades on paper the cheaper it appears
       to trade (validator 8b863152; CDO D3, CTO-confirmed).
  B2 — 47 of 47 open recommendations carried no dollar figure, so the CEO desk's
       "rank by money" ranked by arrival order (builder dispatch 3).
  B3 — `/fund/judgement` returned `due_for_review: []` while a 7.75% drawdown
       sat in plain sight: sixteen of seventeen review triggers were free text
       nothing evaluated (validator 8b863152).
  B4 — the COO triage rule (>20 open items) had no counter anywhere.
"""

import pytest

from app.fund import desk as desk_mod
from app.fund import judgement as judgement_mod
from app.fund.connectors.base import Order, Side
from app.fund.deskstore import _money_at_stake
from app.fund.events import EventType
from app.fund.judgement import TriggerSpec
from app.fund.tca import TransactionCosts, summarise


# --- B1: venue on the fill, and informative-fills-only stats ----------------

class TestVenueOnFills:
    def test_the_fill_event_records_its_own_venue(self, wire):
        """The venue was only ever on OrderSubmitted, so anything folding fills
        alone had to join two events to ask 'could this fill measure cost?'."""
        r = wire.ledger.request_subscription(lp_id="lp", usd_amount=50_000.0, actor="m")
        wire.ledger.confirm_subscription(r["subscription_id"], actor="m")
        res = wire.pipe_open.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1), actor="op")
        wire.pipe_open.approve_order(res["order_id"], "op")
        fills = [e for e in wire.store.stream(0, 100_000)
                 if e["type"] == EventType.ORDER_FILLED.value]
        assert fills and fills[-1]["payload"]["venue"] == "paper"

    def test_tca_reads_the_venue_off_the_fill(self, wire):
        r = wire.ledger.request_subscription(lp_id="lp", usd_amount=50_000.0, actor="m")
        wire.ledger.confirm_subscription(r["subscription_id"], actor="m")
        res = wire.pipe_open.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1), actor="op")
        wire.pipe_open.approve_order(res["order_id"], "op")
        rows = TransactionCosts(wire.store).costs()
        assert rows and rows[0].venue == "paper"


class _Row:
    """A minimal OrderCost stand-in for the summarise() arithmetic."""

    def __init__(self, venue, execution_bps, total_bps=None, symbol="SPY"):
        self.venue = venue
        self.execution_bps = execution_bps
        self.total_bps = total_bps
        self.delay_bps = None
        self.approval_latency_s = None
        self.total_usd = None
        self.symbol = symbol
        self.strategy_id = None


class TestInformativeStats:
    def test_paper_zeros_are_excluded_from_the_informative_block(self):
        """Ten paper fills at 0.00bps and one real fill at 8bps must not report
        0.7bps. That average is the defect, and it gets cheaper every time the
        fund places a paper order."""
        rows = [_Row("paper", 0.0) for _ in range(10)] + [_Row("alpaca", 8.0, 12.0)]
        s = summarise(rows)
        assert s["informative"]["orders"] == 1
        assert s["informative"]["execution_bps"]["mean"] == 8.0
        assert s["informative"]["venues_counted"] == ["alpaca"]
        assert s["informative"]["venues_excluded"] == ["paper"]
        assert s["informative"]["excluded_orders"] == 10
        # And the all-venue block still exists, still averaging everything —
        # unchanged for its existing consumers, and now named as such.
        assert s["execution_bps"]["mean"] == pytest.approx(0.73, abs=0.01)

    def test_a_paper_only_book_reports_unmeasurable_not_zero(self):
        s = summarise([_Row("paper", 0.0) for _ in range(10)])
        assert s["informative"]["measurable"] is False
        assert s["informative"]["execution_bps"]["n"] == 0
        assert s["informative"]["execution_bps"]["mean"] is None
        assert "identically zero" in s["informative"]["reason"]

    def test_an_unrecorded_venue_is_not_assumed_to_be_paper(self):
        """A fill whose venue nobody recorded is counted as informative, because
        assuming 'paper' would silently drop real fills from the measurement."""
        s = summarise([_Row(None, 5.0)])
        assert s["informative"]["orders"] == 1
        assert s["informative"]["venues_counted"] == []

    def test_by_symbol_and_by_venue_cuts_exist(self, wire):
        r = wire.ledger.request_subscription(lp_id="lp", usd_amount=50_000.0, actor="m")
        wire.ledger.confirm_subscription(r["subscription_id"], actor="m")
        for sym in ("AAPL", "MSFT"):
            res = wire.pipe_open.propose_order(
                Order(venue="paper", symbol=sym, side=Side.BUY, qty=1), actor="op")
            wire.pipe_open.approve_order(res["order_id"], "op")
        tca = TransactionCosts(wire.store)
        assert set(tca.by_symbol()) == {"AAPL", "MSFT"}
        assert set(tca.by_venue()) == {"paper"}


# --- B2: money_at_stake -----------------------------------------------------

class TestMoneyAtStake:
    def test_a_stated_figure_is_carried(self):
        assert _money_at_stake({"text": "t", "money_at_stake": 376.84}) == 376.84
        assert _money_at_stake({"text": "t", "money_at_stake": "376.84"}) == 376.84

    def test_an_absent_figure_is_none_never_zero(self):
        """The whole point. A recommendation with no stated stake must rank
        absent-last, and it can only do that if it is None."""
        assert _money_at_stake({"text": "t"}) is None
        assert _money_at_stake({"text": "t", "money_at_stake": None}) is None
        assert _money_at_stake("a bare string recommendation") is None

    def test_junk_is_none_not_a_number(self):
        for junk in ("about $400", True, float("nan"), float("inf"), {}, []):
            assert _money_at_stake({"money_at_stake": junk}) is None

    def test_zero_is_kept_because_zero_is_a_statement(self):
        """A seat that says 'this moves no money' has said something. That is
        different from saying nothing, and the desk must be able to tell."""
        assert _money_at_stake({"money_at_stake": 0}) == 0.0


# --- B3: machine-checkable review triggers ---------------------------------

class TestTriggerSpec:
    def test_a_fired_trigger_makes_the_entry_due(self):
        """The measured defect: a 7.75% drawdown against R6's registered
        'first drawdown episode over 3% from peak', and due_for_review: []."""
        j = judgement_mod.Judgement(
            "example", where="x", basis="judged", why="y", falsified_by="z",
            review_trigger="first drawdown over 3%", review_by="2099-01-01",
            trigger_spec=TriggerSpec("risk_monitor.drawdown_pct", ">", 3.0))
        assert j.due("2026-08-20", {"risk_monitor.drawdown_pct": 7.75}) is True
        assert j.due("2026-08-20", {"risk_monitor.drawdown_pct": 1.0}) is False

    def test_an_unreadable_metric_is_unchecked_not_unfired(self):
        j = judgement_mod.Judgement(
            "example", where="x", basis="judged", why="y", falsified_by="z",
            review_trigger="t", review_by="2099-01-01",
            trigger_spec=TriggerSpec("risk_monitor.drawdown_pct", ">", 3.0))
        got = j.to_dict("2026-08-20", {})          # namespace present, key absent
        assert got["trigger_spec"][0]["readable"] is False
        assert got["trigger_spec"][0]["fired"] is None
        assert got["unchecked_triggers"] == 1
        assert got["trigger_fired"] is False
        assert "NOT been checked" in got["trigger_spec"][0]["note"]

    def test_a_non_numeric_metric_is_unchecked(self):
        spec = TriggerSpec("m", ">", 1.0)
        got = spec.evaluate({"m": "seven point seven five"})
        assert got["readable"] is False and got["fired"] is None

    def test_the_date_backstop_still_works_without_any_spec(self):
        j = judgement_mod.Judgement(
            "example", where="x", basis="judged", why="y", falsified_by="z",
            review_trigger="prose only", review_by="2020-01-01")
        assert j.due("2026-08-20") is True
        assert j.to_dict("2026-08-20")["trigger_spec"] == []

    def test_a_bad_comparator_is_refused_at_construction(self):
        with pytest.raises(ValueError):
            TriggerSpec("m", "~=", 1.0)

    def test_the_live_register_carries_at_least_one_machine_checkable_trigger(self):
        specs = [j for j in judgement_mod.registry() if j.trigger_spec]
        assert specs, "the register migrated no trigger to a checkable form"
        assert any(j.key == "min_effective_bets" for j in specs)

    def test_a_fired_trigger_reaches_due_for_review_and_says_why(self):
        """End to end through review(): the report the endpoint returns."""
        judgement_mod.use_metrics(lambda: {"risk_monitor.drawdown_pct": 7.75,
                                           "risk_monitor.drawdown_utilization_pct": 77.5})
        try:
            report = judgement_mod.review("2026-08-20")
        finally:
            judgement_mod.use_metrics(None)
        keys = [e["key"] for e in report["due_for_review"]]
        assert "min_effective_bets" in keys, \
            "a fired drawdown trigger did not surface in due_for_review"
        assert "min_effective_bets" in [e["key"] for e in report["triggered"]]
        entry = next(e for e in report["entries"] if e["key"] == "min_effective_bets")
        assert "7.75" in entry["due_reason"]

    def test_with_no_metric_source_triggers_are_unchecked_not_passing(self):
        judgement_mod.use_metrics(None)
        report = judgement_mod.review("2026-08-20")
        assert report["triggers_unchecked"], \
            "with no metric source every spec must report UNCHECKED"
        assert report["triggered"] == []


# --- B4: the desk load counter ---------------------------------------------

class TestDeskLoad:
    def test_the_count_is_the_sum_of_the_three_named_components(self):
        load = desk_mod.desk_load([{}] * 18, [{}] * 3, [{}] * 2)
        assert load["total"] == 23
        assert load["components"] == {"open_recommendations": 18,
                                      "pending_orders": 3,
                                      "requests_awaiting_approval": 2}

    def test_the_chip_fires_at_or_above_the_threshold(self):
        """RENAMED AND RE-PINNED 2026-08-21 (CEO instruction, verbatim:
        "Lets run coo on >=50 items or we can trigger as needed").

        The old invariant was STRICTLY above (>20 fired at 21). The CEO's
        instruction says >=50, which fires AT 50, so the comparison moved
        from `>` to `>=` and this test's name moved with it. Recorded
        loudly rather than quietly because a test renamed to match the
        change it is supposed to catch is exactly how a gate gets loosened
        by its own suite — the difference here is one item on a governance
        dashboard light, it moves no risk limit, and the reason is in
        desk.py beside the constant.

        What this still pins, and why it is worth a test at all: the
        boundary is exact. One item below the threshold is quiet; the
        threshold itself fires."""
        assert desk_mod.desk_load(
            [{}] * (desk_mod.COO_TRIAGE_THRESHOLD - 1), [], []
        )["coo_triage_due"] is False
        assert desk_mod.desk_load(
            [{}] * desk_mod.COO_TRIAGE_THRESHOLD, [], []
        )["coo_triage_due"] is True

    def test_decided_recommendations_do_not_count_toward_the_ceo_load(self):
        """Measured on the counter's first live day: it read 73 against 10
        truly open — the upstream feed includes accepted+staged (the UI
        renders those as 'decided, awaiting execution'), and the trigger
        fired a COO triage at 3.65x the real load, whose own memo found the
        miscount (triage #2, 2026-08-20). A row with NO status still counts:
        dropping a malformed row would hide work."""
        rows = ([{"status": "open"}] * 4 + [{"status": "accepted"}] * 40
                + [{"status": "staged"}] * 20 + [{}] * 2)
        load = desk_mod.desk_load(rows, [], [])
        assert load["components"]["open_recommendations"] == 6
        assert load["coo_triage_due"] is False

    def test_an_uncountable_component_makes_the_total_incomplete(self):
        """A partial count that reads like a full one is how a desk over the
        trigger looks quiet."""
        load = desk_mod.desk_load([{}] * 19, None, [{}] * 2)
        assert load["total"] == 21
        assert load["complete"] is False
        assert load["unreadable"] == ["pending_orders"]
        assert "could not be counted" in load["note"]
        assert "at least this" in load["note"]

    def test_the_counter_dispatches_nothing(self):
        """The chip is a SIGNAL for the CTO, not a starter motor. Crossing the
        trigger must remain a fact somebody reads, never a call somebody's code
        makes — the ignition keys stay human by construction, not by intent.

        Checked against the parsed source, not a grep, so the word 'dispatch'
        in the explanatory note cannot make this pass or fail by accident.
        """
        import ast
        import inspect
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(desk_mod.desk_load)))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    called.add(f.id)
                elif isinstance(f, ast.Attribute):
                    called.add(f.attr)
        # Counting, filtering, formatting and sorting only. No append, no
        # post, no run. ("get" reads a row's status for the decided-rows
        # filter — a read, not an action.)
        assert called <= {"_count", "int", "len", "sum", "sorted", "join",
                          "values", "items", "isinstance", "get"}, called
