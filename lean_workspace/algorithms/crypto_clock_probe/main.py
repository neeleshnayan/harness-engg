# region imports
from AlgorithmImports import *
from datetime import date, datetime, timedelta
# endregion

# =====================================================================
# CRYPTO ANNUALISATION PROBE — the smallest honest algorithm that answers one
# question, dispatched as the crypto half of the annualisation-clock finding.
#
# THE QUESTION, entire: on OUR stack, what does LEAN report as the
# annualisation basis for a CRYPTO-pair daily strategy — 252 or 365 — and does
# `set_brokerage_model` with a crypto brokerage move it?
#
# WHY IT NEEDS ASKING. `leanrunner.annualisation_clock` compares the engine's
# clock against the SERIES' clock and reports `engine_understates` when the
# engine's is shorter. The builder's B1 note says a crypto algorithm that never
# calls `set_brokerage_model` is scored on 252 and every sqrt-annualised
# statistic is understated by sqrt(365/252) = 1.2035. But this seat MEASURED
# the same flag firing on a pure US-equity-ETF strategy (dispatch #8,
# `hyg_fast_flip_probe_v2`: engine 252.0, series 365.25, factor 1.203912) —
# because LEAN emits one equity point per CALENDAR day, so the SERIES clock is
# 365.25 for an equity strategy too. The flag therefore cannot discriminate
# "crypto on an equity clock" from "equity on a calendar clock", and the state
# alone is not evidence about the asset class. This probe supplies the
# crypto-side data point the discrimination needs.
#
# THE RULE, entire: buy BTC/USD with the whole book on the first delivered bar
# and hold. There is nothing to overfit and no verdict is sought — this is an
# INSTRUMENT measurement, not a candidate. It is deliberately the shape whose
# returns nobody can misread as an edge.
#
# Every order below exists INSIDE a backtest. This file never contacts the
# fund's order path.
#
# ---------------------------------------------------------------------
# DESIGN DECISIONS
#
# 1. THE PAIR, NOT THE TICKER. `resolve_namespace("BTC")` returns
#    `basis: 'equity_filer'` — the BARE ticker is the Grayscale Bitcoin Mini
#    Trust ETF, and pricing it as bitcoin is a ~1000x error. `BTC-USD` is
#    pair form and resolves `{'crypto': True, 'basis': 'pair_form'}`. The feed
#    then serves `symbol: 'BTC/USD'`, `source: 'alpaca-crypto'`,
#    `instrument_type: 'CRYPTOCURRENCY'`, `exchange: 'alpaca'` — 2,005 bars
#    from 2021-03-02 (measured 2026-08-28). The VENUE is alpaca and it is
#    named, because a crypto ticker is not an identity.
#
# 2. `BTC-USD` RATHER THAN `BTC/USD` IN `add_data`. The custom-data source URL
#    interpolates `config.symbol.value` directly; a slash in a ticker becomes
#    a path separator in the URL. The endpoint accepts the dash form and
#    reports back the canonical `BTC/USD`, so the dash costs nothing and
#    removes an escaping failure mode.
#
# 3. THE BROKERAGE MODEL IS A PARAMETER, not a constant, so the two arms of
#    the question are one file. LEAN takes `Settings.TradingDaysPerYear` from
#    the BROKERAGE MODEL rather than from the security type. `brokerage=none`
#    is the control (expected 252); `brokerage=coinbase|binance|bitfinex` is
#    the treatment (expected 365 if the documented behaviour holds on our
#    stack). Note the honest risk, written before the run: the data here is a
#    CUSTOM type (`SecurityType.Base`), not a native crypto security, so a
#    crypto brokerage model may refuse to submit orders for it. If that
#    happens the clock question is still answered — `tradingDaysPerYear` is
#    read from the run's configuration, not from its fills — and the refusal
#    is itself the finding.
#
# 4. THE WINDOW ENDS ON THE LAST COMPLETED DAY. The feed's final row is the
#    running print for today. Crypto has no session boundary, so "today's
#    close" does not exist until UTC midnight; the end is pinned one day back
#    and the run is reproducible.
#
# 5. NO WARM-UP, NO INDICATOR, NO PARAMETER TO SWEEP. One decision, held.
# =====================================================================

SPINE = "http://host.docker.internal:8090/api/v1/fund"

#: Read statically by the harness. One name, so any benchmark bar built from
#: it is BTC/USD buy-and-hold — which is also what this strategy is.
UNIVERSE = ["BTC-USD"]

#: Declared so `hold_days_source` reads "declared" rather than "assumed".
#: INERT here: this probe is not submitted as a candidate and no walk-forward
#: is run on it. 21 is the decision cadence a hold-and-monitor rule would
#: carry; the rule below makes exactly one decision.
HOLD_DAYS = 21
CLAIM_TYPE = "premia"
BENCHMARK = "BTC-USD"

TARGET_WEIGHT = 0.99
NOTIONAL = 1_000_000

#: First bar of the pair on our feed is 2021-03-02 (measured).
DEFAULT_START = (2021, 3, 2)
#: Last COMPLETED day. See DESIGN DECISION 4.
DEFAULT_END = (2026, 8, 26)


def _date(raw):
    if not raw:
        return None
    return tuple(int(p) for p in str(raw).split("-"))


class SpineBars(PythonData):
    """Daily closes from the fund's own market-data layer. CSV because LEAN's
    remote-file reader iterates LINES."""

    def get_source(self, config, dt_, is_live):
        url = (f"{SPINE}/marketdata/bars?symbol={config.symbol.value}"
               f"&lookback_days=2000&format=csv")
        return SubscriptionDataSource(url, SubscriptionTransportMedium.REMOTE_FILE)

    def reader(self, config, line, dt_, is_live):
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


class CryptoClockProbe(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*(_date(self.get_parameter("start")) or DEFAULT_START))
        self.set_end_date(*(_date(self.get_parameter("end")) or DEFAULT_END))
        self.set_cash(int(float(self.get_parameter("nav") or NOTIONAL)))

        # THE TREATMENT. Set BEFORE add_data so the security inherits the
        # brokerage's models, exactly as a real crypto algorithm would.
        self.brokerage_arm = str(self.get_parameter("brokerage") or "none").lower()
        self.brokerage_error = None
        if self.brokerage_arm != "none":
            names = {
                "coinbase": BrokerageName.COINBASE,
                "binance": BrokerageName.BINANCE,
                "bitfinex": BrokerageName.BITFINEX,
                "kraken": BrokerageName.KRAKEN,
            }
            try:
                self.set_brokerage_model(names[self.brokerage_arm],
                                         AccountType.CASH)
            except Exception as exc:                      # noqa: BLE001
                # An arm that cannot be set is reported, never silently skipped
                # — a probe that quietly runs the control while claiming the
                # treatment measures nothing.
                self.brokerage_error = f"{type(exc).__name__}: {exc}"

        self.w = float(self.get_parameter("weight") or TARGET_WEIGHT)
        slip = float(self.get_parameter("slip") or 0.0005)
        fee = float(self.get_parameter("fee") or 0)

        sec = self.add_data(SpineBars, UNIVERSE[0], Resolution.DAILY)
        sec.set_fee_model(ConstantFeeModel(fee))
        sec.set_slippage_model(ConstantSlippageModel(slip))
        # ARM 3, added after arms 1 and 2 measured the trade-off (jobs
        # 07cebef339f4 / c5ec1c1cb7ab): a crypto brokerage model buys the 365
        # clock and installs a CashBuyingPowerModel that refuses our feed —
        # "Unable to compute order quantity of BTC-USD.SpineBars. Reason: The
        # security type must be Cryptoor Forex. Returning null." (LEAN's own
        # words, missing space included). Our data is a custom PythonData type,
        # so its SecurityType is Base, not Crypto. Putting an unlevered margin
        # model back on the SECURITY leaves the algorithm-level clock alone and
        # asks whether the order can then be sized. `bpm=margin` selects it.
        if str(self.get_parameter("bpm") or "default").lower() == "margin":
            sec.set_buying_power_model(SecurityMarginModel(1.0))
        if str(self.get_parameter("fractional") or "0") == "1":
            old = sec.symbol_properties
            sec.symbol_properties = SymbolProperties(
                old.description, old.quote_currency, old.contract_multiplier,
                old.minimum_price_variation, 0.0001, old.market_ticker)
        self.sym = sec.symbol
        self.settings.minimum_order_margin_portfolio_percentage = 0

        self.set_benchmark(self.sym)

        self.bought = False
        self.bars = 0
        self.entry_bar = None
        self.rejects = 0

    def on_order_event(self, order_event):
        # A crypto brokerage model refusing a custom-data order is the outcome
        # DESIGN DECISION 3 warned about; count it rather than infer it.
        if str(order_event.status) in ("OrderStatus.INVALID", "Invalid"):
            self.rejects += 1

    def on_data(self, data):
        if self.sym not in data or data[self.sym] is None:
            return
        self.bars += 1
        if self.bought:
            return
        self.entry_bar = str(data[self.sym].time.date())
        self.set_holdings(self.sym, self.w)
        self.bought = True

    def on_end_of_algorithm(self):
        # Read defensively: the point of the probe is the clock, and an
        # attribute error here would destroy the run that was measuring it.
        try:
            tdy = self.settings.trading_days_per_year
        except Exception as exc:                          # noqa: BLE001
            tdy = f"UNREADABLE {type(exc).__name__}: {exc}"
        self.log(f"crypto_clock_probe: arm={self.brokerage_arm} "
                 f"brokerage_error={self.brokerage_error} bars={self.bars} "
                 f"entry_bar={self.entry_bar} invested={self.portfolio.invested} "
                 f"rejects={self.rejects} trading_days_per_year={tdy}")
