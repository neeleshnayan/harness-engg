# region imports
from AlgorithmImports import *
# endregion

"""THE FRACTIONAL-FILL FALSIFIER. Not a strategy and never a candidate.

It exists to answer one question with the ENGINE rather than with a guess: does
overriding a security's lot size actually produce fractional fills here? It buys
a 49% target in each of SPY and TLT at a $2,000 book and logs what filled.

MEASURED 2026-08-21, two runs, identical window (2026-02-24..2026-03-20):

    fractional:0    SPY 1.0000    TLT 11.0000     <- the engine's default
    fractional:1    SPY 1.4298    TLT 11.1207

SPY printed at $685, so 49% of a $2,000 book is $980 = 1.43 shares. Whole-share
rounding holds ONE — 34% of the book against a 49% target, a 15 percentage-point
error, an order of magnitude larger than the 1-2%/yr effects the belt tests for.
That is the constraint that forced entry 11 to be run at a $100k notional
(run-quant-entry11).

KEEP THIS FILE. The switch in `leanrunner.FRACTIONAL_PARAM` is a claim about
engine behaviour, and this is the only thing that can falsify it — re-run both
arms after any LEAN image bump. A control whose proof was deleted is a control
nobody can check.

    ./venv/Scripts/python.exe -c "from app.fund.leanrunner import LeanRunner; \\
        r=LeanRunner(); print(r.submit_backtest('frac_probe', fractional=True))"
"""

SPINE = "http://host.docker.internal:8090/api/v1/fund"
UNIVERSE = ["SPY", "TLT"]


class SpineBars(PythonData):
    def get_source(self, config, date, is_live):
        url = (f"{SPINE}/marketdata/bars?symbol={config.symbol.value}"
               f"&lookback_days=2000&format=csv")
        return SubscriptionDataSource(url, SubscriptionTransportMedium.REMOTE_FILE)

    def reader(self, config, line, date, is_live):
        try:
            ds, close = line.strip().split(",")
            bar = SpineBars()
            bar.symbol = config.symbol
            bar.time = datetime.strptime(ds, "%Y-%m-%d")
            bar.value = float(close)
            bar["close"] = float(close)
            return bar
        except (ValueError, AttributeError):
            return None


class FracProbe(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2026, 2, 24)
        self.set_end_date(2026, 3, 20)
        self.set_cash(2000)
        self.frac = str(self.get_parameter("fractional") or "0") == "1"
        self.syms = []
        for t in UNIVERSE:
            sec = self.add_data(SpineBars, t, Resolution.DAILY)
            sec.set_fee_model(ConstantFeeModel(0))
            sec.set_slippage_model(ConstantSlippageModel(0.0003))
            if self.frac:
                # THE THING UNDER TEST. Reported, not assumed: whatever this
                # does or fails to do gets logged below.
                try:
                    old = sec.symbol_properties
                    sec.symbol_properties = SymbolProperties(
                        old.description, old.quote_currency,
                        old.contract_multiplier, old.minimum_price_variation,
                        0.0001, old.market_ticker)
                    self.log(f"PROBE lotsize-set {t} -> "
                             f"{sec.symbol_properties.lot_size}")
                except Exception as e:
                    self.log(f"PROBE lotsize-FAILED {t} {type(e).__name__}: {e}")
            self.syms.append(sec.symbol)
        self.done = False
        self.set_warm_up(5, Resolution.DAILY)

    def on_data(self, data):
        if self.is_warming_up or self.done:
            return
        if not all(s in data for s in self.syms):
            return
        for s in self.syms:
            sp = self.securities[s].symbol_properties
            self.log(f"PROBE lotsize-seen {s.value} = {sp.lot_size} "
                     f"frac={self.frac}")
            self.set_holdings(s, 0.49)
        self.done = True

    def on_order_event(self, ev):
        if ev.status == OrderStatus.FILLED:
            self.log(f"PROBE fill {ev.symbol.value} qty={ev.fill_quantity} "
                     f"price={ev.fill_price}")

    def on_end_of_algorithm(self):
        for s in self.syms:
            h = self.portfolio[s]
            self.log(f"PROBE final {s.value} qty={h.quantity} "
                     f"value={h.holdings_value}")
        self.log(f"PROBE cash={self.portfolio.cash} "
                 f"total={self.portfolio.total_portfolio_value}")
