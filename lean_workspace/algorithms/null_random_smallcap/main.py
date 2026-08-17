from AlgorithmImports import *

# Explicit: `Random` unqualified can resolve to System.Random from the .NET
# namespace AlgorithmImports pulls in, which has no `sample` and would fail at
# the first rebalance rather than at import.
import random as _pyrandom

SPINE = "http://host.docker.internal:8090/api/v1/fund"

#: Identical universe to xs_momentum_smallcap. It has to be identical: the point
#: is to isolate the SIGNAL as the only difference between this and the real
#: candidate. A different universe would leave two variables changed and make
#: any comparison meaningless.
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
    """A strategy with NO information in it, for calibrating the gate.

    The gate has failed every candidate it has ever judged. That is consistent
    with a high standard, and equally consistent with a bar nothing could clear
    on two years of daily data — and we have never been able to tell those apart.
    This tells them apart from one side.

    The rule here is pure noise: pick `top_n` names at random on the rebalance
    clock and hold them. Same universe, same costs, same clock, same slippage as
    the real candidate — everything identical except that the selection carries
    no information whatsoever.

    Such a strategy has no edge by construction, so it MUST fail. Every seed that
    passes is a leak in the harness rather than a discovery: look-ahead in the
    data, a cost model that does not bite, or survivorship in the universe doing
    the work. Run enough seeds and the pass rate IS the gate's false-positive
    rate, measured instead of assumed.

    Note what this cannot do: it cannot show the gate is not too STRICT. That is
    the injected-edge audit's job, and the two together bound the gate from both
    sides.
    """

    def initialize(self):
        self.set_start_date(*(_date(self.get_parameter("start")) or (2025, 1, 1)))
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(2000)

        self.top_n = int(self.get_parameter("top_n") or 5)
        self.hold_days = int(self.get_parameter("hold_days") or 63)
        # Seeded so a given seed is reproducible and a batch of seeds spans the
        # distribution of luck. An unseeded null audit could not be re-run, and
        # an unreproducible calibration is not a calibration.
        self.rng = _pyrandom.Random(int(self.get_parameter("seed") or 1))

        slip = float(self.get_parameter("slip") or 0.0005)
        fee = float(self.get_parameter("fee") or 0)

        self.syms = []
        for t in UNIVERSE:
            sec = self.add_data(SpineBars, t, Resolution.DAILY)
            sec.set_fee_model(ConstantFeeModel(fee))
            sec.set_slippage_model(ConstantSlippageModel(slip))
            self.syms.append(sec.symbol)
        self.set_benchmark(self.syms[0])

        # Warm-up is short but not zero: the names still have to have printed
        # before they can be bought, and matching the real candidate's habit
        # keeps the two comparable.
        self.set_warm_up(5, Resolution.DAILY)
        self.since_rebalance = 10_000

    def on_data(self, data: Slice):
        live = [s for s in self.syms if s in data and data[s] is not None]
        if len(live) < self.top_n + 1:
            return
        self.since_rebalance += 1
        if self.since_rebalance < self.hold_days:
            return
        self.since_rebalance = 0

        winners = self.rng.sample(live, self.top_n)
        for s in self.syms:
            if self.portfolio[s].invested and s not in winners:
                self.liquidate(s)
        # Fully invested, exactly like the real candidate — so any difference in
        # result comes from the signal and not from one of them sitting in cash.
        weight = 0.95 / len(winners)
        for s in winners:
            self.set_holdings(s, weight)
