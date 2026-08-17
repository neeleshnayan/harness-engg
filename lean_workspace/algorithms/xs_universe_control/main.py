from AlgorithmImports import *

SPINE = "http://host.docker.internal:8090/api/v1/fund"

#: Identical list to xs_momentum_smallcap. Kept as a literal rather than
#: imported: the control must not be able to drift out of step with the thing it
#: controls for, and a shared import would let one change silently.
UNIVERSE = ["ALKT", "CON", "ATRC", "SOBO", "ADMA", "CLOV", "BLZE", "ZIM",
            "GHM", "NBR", "GCT", "DEI", "PRVA", "KOPN", "AVPT", "LINC",
            "CRAI", "ANIP", "NTCT", "TRN"]


class SpineBars(PythonData):
    def get_source(self, config, date, is_live):
        url = (f"{SPINE}/marketdata/bars?symbol={config.symbol.value}"
               f"&lookback_days=900&format=csv")
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
    """The bar the selection rule has to clear: hold all 20, equally, forever.

    This exists because a benchmark built from the symbols a strategy TRADED is
    the wrong question. A momentum rule only ever buys the names it liked, so
    measuring it against those names asks "did you time your favourites well"
    when the decision under test was "were these the right names to pick at
    all". The honest counterfactual is the whole universe held without opinion —
    what an investor with the same hunting ground and no view would have got.

    Same costs, same feed, same window as the strategy. The only difference is
    the absence of a decision, which is exactly the variable being priced.
    """

    def initialize(self):
        self.set_start_date(*(_date(self.get_parameter("start")) or (2024, 3, 1)))
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(2000)

        slip = float(self.get_parameter("slip") or 0.0005)
        fee = float(self.get_parameter("fee") or 0)

        self.syms = []
        for t in UNIVERSE:
            sec = self.add_data(SpineBars, t, Resolution.DAILY)
            sec.set_fee_model(ConstantFeeModel(fee))
            sec.set_slippage_model(ConstantSlippageModel(slip))
            self.syms.append(sec.symbol)
        self.set_benchmark(self.syms[0])
        self.bought = False

    def on_data(self, data: Slice):
        if self.bought:
            return
        # Buy once every name has printed, so the basket starts equal rather
        # than weighted by whoever happened to have data first.
        live = [s for s in self.syms if s in data and data[s] is not None]
        if len(live) < len(self.syms):
            return
        weight = 0.95 / len(self.syms)
        for s in self.syms:
            self.set_holdings(s, weight)
        self.bought = True
