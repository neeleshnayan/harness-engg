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


def _date(raw):
    """A YYYY-MM-DD parameter as (y, m, d), or None when unset."""
    if not raw:
        return None
    return tuple(int(p) for p in str(raw).split("-"))


class MyAlgorithm(QCAlgorithm):
    """SMA crossover: sweepable periods, settable window, costs ON by default."""

    def initialize(self):
        self.set_start_date(*(_date(self.get_parameter("start")) or (2025, 1, 1)))
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(2000)
        fast = int(self.get_parameter("fast") or 20)
        slow = int(self.get_parameter("slow") or 60)

        sec = self.add_data(SpineBars, "SPY", Resolution.DAILY)
        self.sym = sec.symbol
        self.set_benchmark(self.sym)
        # Costs default ON at 5bps. Alpaca charges no commission on US
        # equities, so the fee is genuinely 0 — the cost that bites is the
        # spread. Both are parameters so a sweep can find the cost at which
        # this edge stops paying.
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
