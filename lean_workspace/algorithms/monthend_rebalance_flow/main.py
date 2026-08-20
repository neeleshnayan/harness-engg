# region imports
from AlgorithmImports import *
from datetime import date, timedelta
# endregion

SPINE = "http://host.docker.internal:8090/api/v1/fund"

#: The names this rule may hold, read STATICALLY by the harness (leanrunner
#: _universe_of) to build the equal-weight benchmark. Two names => the bar is the
#: equal-weight SPY/TLT basket, which is exactly this strategy's own baseline.
#: That is the honest bar for an ALPHA claim: the question is whether the
#: month-end rotation adds anything to simply holding 50/50.
UNIVERSE = ["SPY", "TLT"]

#: The strategy's own clock, DECLARED so the walk-forward test leg is sized from
#: it rather than from an assumed 21 (walkforward.declared_hold_days reads this
#: by AST). One decision per calendar month => 21 sessions.
HOLD_DAYS = 21

#: Gate v5 fields, declared ahead of the gate that will read them.
CLAIM_TYPE = "alpha"
BENCHMARK = "SPY/TLT"

#: Sessions between the signal measurement and the trade. FIXED by the flow's
#: timing (the mandate-driven order is placed into the month's last session), NOT
#: a free parameter and deliberately not swept.
SIGNAL_LEAD_SESSIONS = 5

#: Sessions the rotation is held before returning to the 50/50 baseline.
UNWIND_SESSIONS = 3

#: Fraction of the book deployed. "Full book, no leverage" in practice: the 2%
#: buffer stops a set_holdings(1.0) from being rejected for buying power once
#: slippage and fees are charged. Weights below are fractions of this.
BOOK = 0.98

#: Sessions of history the signal needs: the previous month's last close (up to
#: ~23 sessions back) plus the 5-session lead. Warm-up is sized from this.
LOOKBACK_SESSIONS = 30

#: Used only when the harness passes no explicit window. The full depth the
#: fund's own feed serves for these two names (measured 2026-08-20: alpaca,
#: 1380 joint sessions from 2021-02-23).
DEFAULT_START = (2021, 3, 1)

#: THE ONE DEVIATION FROM THE WORKSPACE DEFAULT, DECLARED BECAUSE IT IS
#: PASS-FAVOURABLE. Every other algorithm here runs set_cash(2000), the fund's
#: real NAV. LEAN fills whole shares only, and at $2,000 a single SPY share is
#: ~30% of the book — so a "50/50" target is actually held as ~29/45 and the
#: rounding error is an order of magnitude larger than the 1-2%/yr effect under
#: test. MEASURED, same rule, same window (2025-01-01..2025-06-30, 3bps):
#: $2,000 whole-share book returned +2.01% against a 3.69% benchmark, while the
#: same rule with fractional shares returned +5.48% against 4.44%. The lot size,
#: not the flow, decided that verdict. So the belt runs this at a notional where
#: granularity is negligible and the DEPLOYMENT constraint at $2k is reported
#: separately rather than smuggled into the verdict. Override with `nav`.
NOTIONAL = 100_000


class SpineBars(PythonData):
    """Daily closes from the fund's own market-data layer.

    Same feed the book is marked on. CSV because LEAN's remote-file reader
    iterates LINES as data points — a JSON blob reads as exactly one bar.
    """

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


def _date(raw):
    if not raw:
        return None
    return tuple(int(p) for p in str(raw).split("-"))


def _last_weekday_of_month(d):
    """The month's last weekday, from the calendar alone.

    NO LOOK-AHEAD by construction: this is a property of the date, published
    years in advance, and it is the same schedule the counterparty (a fixed-
    target mandate) trades on. Holidays are NOT modelled — when the last weekday
    is a market holiday no bar arrives for it and the month is simply skipped
    rather than guessed at. Measured against the fund's own feed: that costs one
    month-end in 2024-03 (Good Friday) and one in 2021-05 (Memorial Day) across
    1380 joint sessions.
    """
    nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
    x = nxt - timedelta(days=1)
    while x.weekday() >= 5:
        x -= timedelta(days=1)
    return x


class MonthEndRebalanceFlow(QCAlgorithm):
    """Entry 11 — month-end rebalancing flow (SPY/TLT), implemented verbatim.

    The mechanism: ~$20tn of US pension/TDF assets run fixed-target calendar
    rebalancing, so when equities outrun bonds inside a month those mandates are
    REQUIRED to sell the winner into the month's last session. The rule takes the
    other side: at the close of T (the month's last session) it goes 100% into
    whichever leg the mandates must be selling, then back to 50/50 three sessions
    later once the flow has passed.

    The rule, exactly as specified and with nothing added:
      * baseline 50/50 SPY/TLT, always invested, never in cash
      * signal = sign of (SPY month-to-date - TLT month-to-date) measured at the
        CLOSE OF T-5, month-to-date from the previous month's last close
      * at the close of T: 100/0 if the signal is positive, 0/100 if not
      * at the close of T+3: back to 50/50
      * full book, no leverage, no shorting, one decision per month

    Every order below exists INSIDE a backtest. This file never contacts the
    fund's order path; the only network call it makes is reading its own bars.
    """

    def initialize(self):
        self.set_start_date(*(_date(self.get_parameter("start")) or DEFAULT_START))
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(int(float(self.get_parameter("nav") or NOTIONAL)))

        # The harness supplies the cost assumption; the literals are only a
        # fallback for running this file outside it.
        slip = float(self.get_parameter("slip") or 0.0005)
        fee = float(self.get_parameter("fee") or 0)

        self.syms = []
        for t in UNIVERSE:
            sec = self.add_data(SpineBars, t, Resolution.DAILY)
            sec.set_fee_model(ConstantFeeModel(fee))
            sec.set_slippage_model(ConstantSlippageModel(slip))
            self.syms.append(sec.symbol)
        self.spy, self.tlt = self.syms[0], self.syms[1]
        self.set_benchmark(self.spy)

        # Enough bars to see the previous month's last close and the 5-session
        # lead before the first month-end the run could act on.
        self.set_warm_up(LOOKBACK_SESSIONS + SIGNAL_LEAD_SESSIONS, Resolution.DAILY)

        #: Joint history: one entry per session in which BOTH names printed, so
        #: index arithmetic ("five sessions back") means the same thing for both.
        self.hist = []          # list of (date, spy_close, tlt_close)
        self.invested = False
        self.since_trigger = None
        self.fired = 0
        self.skipped = 0

    # --- helpers ---------------------------------------------------------

    def _weights(self):
        eq = self.portfolio.total_portfolio_value
        if not eq:
            return {s: 0.0 for s in self.syms}
        return {s: self.portfolio[s].holdings_value / eq for s in self.syms}

    def _rebalance(self, targets):
        """Move to target weights, REDUCTIONS FIRST.

        Ordering is load-bearing: going 50/50 -> 100/0 buys with cash the other
        leg has not been sold for yet, and the buy is rejected for buying power.
        """
        now = self._weights()
        for s in sorted(self.syms, key=lambda x: targets[x] - now[x]):
            self.set_holdings(s, targets[s])

    def _signal(self, i):
        """SPY-minus-TLT month-to-date at the close of T-5, or None.

        Reads history[:i-5+1] only — the decision date's close is the newest
        price it can see, so the trade at T uses nothing that happened after
        T-5. The previous month's last close is found by walking BACK from T-5.
        """
        j = i - SIGNAL_LEAD_SESSIONS
        if j < 1:
            return None
        month = (self.hist[i][0].year, self.hist[i][0].month)
        k = j
        while k >= 0 and (self.hist[k][0].year, self.hist[k][0].month) == month:
            k -= 1
        if k < 0:
            return None
        base_d, base_s, base_t = self.hist[k]
        _, spy_j, tlt_j = self.hist[j]
        if not base_s or not base_t:
            return None
        return (spy_j / base_s - 1.0) - (tlt_j / base_t - 1.0)

    # --- the rule --------------------------------------------------------

    def on_data(self, data: Slice):
        if any(s not in data or data[s] is None for s in self.syms):
            return
        # The BAR's own stamp, not self.time: LEAN advances algorithm time to a
        # daily bar's END (the following midnight), which would shift every
        # month-end test by one session.
        d = data[self.spy].time.date()
        row = (d, float(data[self.spy].value), float(data[self.tlt].value))
        if self.hist and self.hist[-1][0] == d:
            self.hist[-1] = row
        else:
            self.hist.append(row)
        if self.is_warming_up:
            return

        base = {self.spy: BOOK / 2.0, self.tlt: BOOK / 2.0}
        if not self.invested:
            self._rebalance(base)
            self.invested = True

        i = len(self.hist) - 1
        if d == _last_weekday_of_month(d):
            sig = self._signal(i)
            if sig is None:
                self.skipped += 1
                self.debug(f"{d}: month-end reached without enough history for "
                           f"the T-5 signal — no rotation, staying 50/50")
                return
            if sig > 0:
                targets = {self.spy: BOOK, self.tlt: 0.0}
            else:
                targets = {self.spy: 0.0, self.tlt: BOOK}
            self._rebalance(targets)
            self.fired += 1
            self.since_trigger = 0
            self.debug(f"{d}: month-end T, T-5 SPY-TLT MTD {sig:+.4f} -> "
                       f"{'100% SPY' if sig > 0 else '100% TLT'}")
            return

        if self.since_trigger is not None:
            self.since_trigger += 1
            if self.since_trigger >= UNWIND_SESSIONS:
                self._rebalance(base)
                self.since_trigger = None
                self.debug(f"{d}: T+{UNWIND_SESSIONS} — back to 50/50")

    def on_end_of_algorithm(self):
        self.debug(f"month-ends traded: {self.fired}; month-ends skipped for "
                   f"want of history: {self.skipped}")
