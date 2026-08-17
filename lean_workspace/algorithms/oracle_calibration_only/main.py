from AlgorithmImports import *

# ============================================================================
#  CALIBRATION INSTRUMENT — NOT A STRATEGY. NEVER DEPLOY THIS.
#
#  This algorithm CHEATS ON PURPOSE. It reads future prices and ranks names by
#  returns that have not happened yet, with a tunable probability `foresight`.
#  It exists for exactly one question: what size of REAL edge would clear the
#  gate's bar on the history we actually have?
#
#  The gate has failed every candidate it ever judged. The null audit can show
#  the bar is not trivially leaky, but it cannot show the bar is CLEARABLE — a
#  floor no genuine edge could pass would also reject every null, and the two
#  cases are indistinguishable from failures alone. This instrument distinguishes
#  them: dial in a known edge, see what the gate says, and read off the minimum
#  detectable effect.
#
#  foresight = 0.0  ->  identical to the null (pure noise)
#  foresight = 1.0  ->  perfect foreknowledge (the ceiling of what is detectable)
#
#  Any result from this belongs in a calibration note and NOWHERE near an
#  allocation. It is named `oracle_calibration_only` so that a glance at a job
#  list is enough to know it is not a candidate.
# ============================================================================

import random as _pyrandom
import json as _json
import urllib.request as _urlreq

SPINE = "http://host.docker.internal:8090/api/v1/fund"

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
    """A strategy with a KNOWN edge, for measuring the gate's sensitivity."""

    def initialize(self):
        self.set_start_date(*(_date(self.get_parameter("start")) or (2025, 1, 1)))
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(2000)

        self.top_n = int(self.get_parameter("top_n") or 5)
        self.hold_days = int(self.get_parameter("hold_days") or 63)
        # The dial. How often the ranking uses the future instead of a coin.
        self.foresight = float(self.get_parameter("foresight") or 0.5)
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
        self.set_warm_up(5, Resolution.DAILY)
        self.since_rebalance = 10_000

        # The cheat, loaded once: the whole close series per name, keyed by date.
        # Fetched over the same endpoint the data feed uses, so the "future" here
        # is the identical series the backtest walks — no second source to
        # disagree with, which keeps this measuring the gate rather than a
        # vendor difference.
        self.future = {}
        for t in UNIVERSE:
            try:
                url = (f"{SPINE}/marketdata/bars?symbol={t}"
                       f"&lookback_days=900&format=csv")
                with _urlreq.urlopen(url, timeout=60) as r:
                    rows = [ln.split(",") for ln in
                            r.read().decode().strip().splitlines() if ln.strip()]
                self.future[t] = {d: float(c) for d, c in rows}
            except Exception as e:
                # A name whose series will not load simply gets no foresight —
                # it falls back to the coin. Silently substituting zero would
                # make the dial mean something different from what it says.
                self.log(f"ORACLE: no future series for {t}: {e}")
                self.future[t] = {}
        self.log(f"ORACLE CALIBRATION INSTRUMENT — foresight={self.foresight}. "
                 f"This algorithm reads future prices on purpose and must never "
                 f"be deployed.")

    def _forward_return(self, ticker, today):
        """Realised return over the next hold period. This is the cheat."""
        series = self.future.get(ticker) or {}
        if not series:
            return None
        dates = sorted(d for d in series if d >= today)
        if len(dates) < 2:
            return None
        here = series[dates[0]]
        ahead = series[dates[min(self.hold_days, len(dates) - 1)]]
        if not here:
            return None
        return ahead / here - 1.0

    def on_data(self, data: Slice):
        live = [s for s in self.syms if s in data and data[s] is not None]
        if len(live) < self.top_n + 1:
            return
        self.since_rebalance += 1
        if self.since_rebalance < self.hold_days:
            return
        self.since_rebalance = 0

        today = self.time.strftime("%Y-%m-%d")
        # Per-name coin flip rather than one flip for the whole basket: a single
        # flip would make the strategy alternate between perfect and blind, which
        # is a different (and much lumpier) experiment than a partial edge.
        scored = []
        for s in live:
            if self.rng.random() < self.foresight:
                fwd = self._forward_return(s.value, today)
                score = fwd if fwd is not None else self.rng.random() - 0.5
            else:
                score = self.rng.random() - 0.5
            scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        winners = [s for _, s in scored[:self.top_n]]

        for s in self.syms:
            if self.portfolio[s].invested and s not in winners:
                self.liquidate(s)
        weight = 0.95 / len(winners)
        for s in winners:
            self.set_holdings(s, weight)
