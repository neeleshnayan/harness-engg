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


class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_cash(2000)
        self.sym = self.add_data(SpineBars, "SPY", Resolution.DAILY).symbol
        self.fast = self.sma(self.sym, 20)
        self.slow = self.sma(self.sym, 60)

    def on_data(self, data: Slice):
        if self.sym not in data or not self.slow.is_ready:
            return
        if self.fast.current.value > self.slow.current.value:
            if not self.portfolio[self.sym].invested:
                self.set_holdings(self.sym, 0.95)
        elif self.portfolio[self.sym].invested:
            self.liquidate(self.sym)
