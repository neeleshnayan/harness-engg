from AlgorithmImports import *

SPINE = "http://host.docker.internal:8090/api/v1/fund"


class SpineBars(PythonData):
    """Daily bars from the fund's own market-data layer."""

    def get_source(self, config, date, is_live):
        url = f"{SPINE}/marketdata/bars?symbol={config.symbol.value}&lookback_days=700&format=csv"
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


def _date(raw, fallback):
    """A YYYY-MM-DD parameter, or the default. Lets the Lab hand the algorithm
    a training window and then a held-out one it was not chosen on."""
    if raw:
        y, m, d = (int(p) for p in str(raw).split("-"))
        return y, m, d
    return fallback


class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(*_date(self.get_parameter("start"), (2025, 1, 1)))
        end = self.get_parameter("end")
        if end:
            self.set_end_date(*_date(end, None))
        self.set_cash(2000)
        # Read tunables as parameters so the Lab can sweep them. get_parameter
        # returns None when unset, hence the defaults — a plain Run still works.
        fast = int(self.get_parameter("fast") or 20)
        slow = int(self.get_parameter("slow") or 60)

        sec = self.add_data(SpineBars, "SPY", Resolution.DAILY)
        self.sym = sec.symbol
        self.set_benchmark(self.sym)
        # Costs are ON by default, and the default is not zero. Alpaca charges
        # no commission on US equities, so the fee really is 0 — the cost that
        # bites is the SPREAD: you buy at the ask and sell at the bid. 5bps is
        # a conservative half-spread for liquid names at this size.
        #
        # Both are parameters so the sweep can answer the question that
        # actually matters: not "what does trading cost" but "at what cost does
        # this edge disappear". Sweep slip and watch where the return crosses
        # zero.
        sec.set_fee_model(ConstantFeeModel(float(self.get_parameter("fee") or 0)))
        sec.set_slippage_model(
            ConstantSlippageModel(float(self.get_parameter("slip") or 0.0005)))

        self.fast = self.sma(self.sym, fast)
        self.slow = self.sma(self.sym, slow)

    def on_data(self, data: Slice):
        if self.sym not in data or not self.slow.is_ready:
            return
        if self.fast.current.value > self.slow.current.value:
            if not self.portfolio[self.sym].invested:
                self.set_holdings(self.sym, 0.95)
        elif self.portfolio[self.sym].invested:
            self.liquidate(self.sym)
