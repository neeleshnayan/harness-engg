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
    # a YYYY-MM-DD parameter as (y, m, d), or None when unset
    if not raw:
        return None
    return tuple(int(p) for p in str(raw).split("-"))


class MyAlgorithm(QCAlgorithm):
    def initialize(self):
        # three ints, never a date string; the window is settable so the Lab
        # can test the chosen settings on data they were not chosen on
        self.set_start_date(*(_date(self.get_parameter("start")) or (2025, 1, 1)))
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(2000)
        fast = int(self.get_parameter("fast") or 20)   # sweepable, with a default
        slow = int(self.get_parameter("slow") or 60)
        sec = self.add_data(SpineBars, "APLE", Resolution.DAILY)
        self.sym = sec.symbol
        self.set_benchmark(self.sym)
        # costs default ON: no commission on US equities, but the spread is
        # real, and a strategy that only works for free is not a strategy
        sec.set_fee_model(ConstantFeeModel(float(self.get_parameter("fee") or 0)))
        sec.set_slippage_model(
            ConstantSlippageModel(float(self.get_parameter("slip") or 0.0005)))
        # Indicator helpers are named for the indicator and take the symbol
        # FIRST: self.sma(sym, n), self.rsi(sym, n), self.ema(sym, n),
        # self.macd(sym, f, s, sig), self.atr(sym, n). There is no
        # self.indicator(...) and no self.add_rsi(...).
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
