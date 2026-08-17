from AlgorithmImports import *

SPINE = "http://host.docker.internal:8090/api/v1/fund"

#: Chosen by RULE, not by eye: the 20 highest-ADV operating companies inside
#: the $2M-$25M ADV capacity band, SIC-filtered to drop funds and trusts, each
#: with >=400 daily bars. Reproduce with scripts/build_xs_universe.py.
#:
#: The rule matters more than the names. I can see how these traded, so picking
#: eight favourites by hand would be look-ahead bias committed by the analyst
#: instead of the code — and it would not show up in any holdout, because the
#: holdout only tests the rule, never the person who chose its inputs.
#:
#: KNOWN BIAS, stated because it cannot be fixed with today's data: the band is
#: measured TODAY, so every name here survived to today. Anything delisted over
#: the test window is absent, which flatters the result by an unmeasured amount.
UNIVERSE = ["ALKT", "CON", "ATRC", "SOBO", "ADMA", "CLOV", "BLZE", "ZIM",
            "GHM", "NBR", "GCT", "DEI", "PRVA", "KOPN", "AVPT", "LINC",
            "CRAI", "ANIP", "NTCT", "TRN"]


class SpineBars(PythonData):
    """Daily bars from the fund's own market-data layer."""

    def get_source(self, config, date, is_live):
        url = (f"{SPINE}/marketdata/bars?symbol={config.symbol.value}"
               f"&lookback_days=700&format=csv")
        return SubscriptionDataSource(url, SubscriptionTransportMedium.REMOTE_FILE)

    def reader(self, config, line, date, is_live):
        try:
            ds, close = line.strip().split(",")
            bar = SpineBars()
            bar.symbol = config.symbol
            bar.time = datetime.strptime(ds, "%Y-%m-%d")
            bar.value = float(close)
            return bar
        except (ValueError, AttributeError):
            return None


def _date(raw):
    if not raw:
        return None
    return tuple(int(p) for p in str(raw).split("-"))


class MyAlgorithm(QCAlgorithm):
    """Cross-sectional momentum on small-caps a large fund cannot trade.

    WHY THIS SHAPE. Every candidate this fund has tested was a long-only TIMING
    rule on a single name, and every one failed the same criterion: an expensive
    way to hold the underlying. That is structural, not bad luck — a rule that
    sits in cash part of the time cannot beat holding an asset that drifts up,
    so the gate correctly rejects the entire family.

    Selection is a different shape. Holding the strongest few of a basket can
    beat holding the whole basket, because the comparison is no longer
    "in the market versus out of it" but "these names versus those names". It is
    also the shape that fits a small fund: the edge comes from looking at names
    nobody large can act on, which is exactly what the hunting ground is.

    Always fully invested across TOP_N, so this is not a market-timing bet in
    disguise. If the ranking has no skill, the result should land on the
    equal-weight basket rather than beating it by holding cash through a
    drawdown.
    """

    def initialize(self):
        self.set_start_date(*(_date(self.get_parameter("start")) or (2025, 1, 1)))
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(2000)

        self.lookback = int(self.get_parameter("lookback") or 120)
        self.top_n = int(self.get_parameter("top_n") or 3)
        self.hold_days = int(self.get_parameter("hold_days") or 21)

        slip = float(self.get_parameter("slip") or 0.0005)
        fee = float(self.get_parameter("fee") or 0)

        self.syms = []
        for t in UNIVERSE:
            sec = self.add_data(SpineBars, t, Resolution.DAILY)
            sec.set_fee_model(ConstantFeeModel(fee))
            sec.set_slippage_model(ConstantSlippageModel(slip))
            self.syms.append(sec.symbol)
        # Benchmark to a constituent so LEAN does not reach for SPY minute bars,
        # which live-paper's stub queue cannot serve. The REAL comparison is the
        # equal-weight basket the harness computes.
        self.set_benchmark(self.syms[0])

        # Rolling closes per name, kept by hand: momentum needs a price from N
        # sessions ago, and an indicator would only give the average.
        self.history = {s: RollingWindow[float](self.lookback + 1) for s in self.syms}
        self.since_rebalance = 10_000       # rebalance on the first ready bar

        # Warm-up is load-bearing, not a nicety. Without it the algorithm starts
        # every run with an empty window and has to spend `lookback` sessions
        # filling it before it may trade — so a held-out test shorter than the
        # lookback places NO orders and scores a flat 0%, which is
        # indistinguishable from a strategy that lost its edge. Reserving the
        # bars ahead of the start date means the out-of-sample window measures
        # the strategy rather than the length of the window.
        self.set_warm_up(self.lookback + 5, Resolution.DAILY)

    def on_data(self, data: Slice):
        ready = 0
        for s in self.syms:
            if s in data and data[s] is not None:
                self.history[s].add(data[s].value)
            if self.history[s].is_ready:
                ready += 1
        # Need enough names with full history to have a choice worth making.
        if ready < self.top_n + 1:
            return

        self.since_rebalance += 1
        if self.since_rebalance < self.hold_days:
            return
        self.since_rebalance = 0

        scored = []
        for s in self.syms:
            w = self.history[s]
            if not w.is_ready:
                continue
            now, then = w[0], w[self.lookback]
            if then and then > 0:
                scored.append((now / then - 1.0, s))
        if len(scored) < self.top_n + 1:
            return

        scored.sort(reverse=True)
        winners = [s for _, s in scored[:self.top_n]]

        for s in self.syms:
            if self.portfolio[s].invested and s not in winners:
                self.liquidate(s)
        # Fully invested across the winners, so a flat ranking lands on the
        # basket rather than beating it by sitting in cash.
        weight = 0.95 / len(winners)
        for s in winners:
            self.set_holdings(s, weight)
