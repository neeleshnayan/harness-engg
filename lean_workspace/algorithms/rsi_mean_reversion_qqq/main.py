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
        low_rsi = int(self.get_parameter("low") or 30)
        high_rsi = int(self.get_parameter("high") or 70)
        rsi_period = int(self.get_parameter("period") or 14)
        self.sym = self.add_data(SpineBars, "QQQ", Resolution.DAILY).symbol
        self.rsi = self.indicator(RSI, self.sym, rsi_period)

    def on_data(self, data: Slice):
        if self.sym not in data or not self.rsi.is_ready:
            return
        rsi_val = self.rsi.current.value
        if rsi_val < int(self.get_parameter("low") or 30):
            if not self.portfolio[self.sym].invested:
                self.set_holdings(self.sym, 0.95)
        elif rsi_val > int(self.get_parameter("high") or 70):
            if self.portfolio[self.sym].invested:
                self.liquidate(self.sym)
