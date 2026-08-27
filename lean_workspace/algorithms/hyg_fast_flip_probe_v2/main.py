# region imports
from AlgorithmImports import *
from collections import deque
from datetime import datetime, timedelta
import json
import os
import urllib.request
# endregion

# =====================================================================
# HYG FAST FLIP PROBE v2 - A MACHINERY INSTRUMENT, NOT A CANDIDATE.
#
# Purpose, written per the experimental-deployment rule: produce 2-5 BUY/SELL
# PROPOSALS PER WEEK on HYG so that the chain - engine -> /fund/signals/external
# -> approval queue -> the CEO's click -> alpaca paper order -> fill ->
# riskofficer audit - gets real events to chew on. EVERY SIGNAL IS A TEST OF THE
# MACHINERY. P&L is explicitly not the objective, the notional is sized so that
# it cannot become one, and this file must never be tuned toward a better
# verdict: a machinery instrument tuned to look like a strategy stops being
# either.
#
# Requested by the chair on the CEO's instruction (2026-08-27), verbatim:
# "maybe we needed a more agressive startegy on HYG since the point is testing
# and finding bugs and fixing them."
#
# It supersedes `hyg_fast_flip_probe` (v1, FAST=2/SLOW=4) for the live session.
# v1 is NOT deleted and NOT edited - it is the control arm, and the two differ
# in exactly two places (the rule, and the bar-delivery clock below), so any
# behavioural difference is attributable.
#
# ---------------------------------------------------------------------
# FINDING 0 - WHY v1 EMITTED NOTHING ON 2026-08-27, AND IT WAS NOT THE RULE.
#
# Measured: session 052650b749da started 2026-08-27T15:58:09Z (11:58 ET) and
# logged `primed 1379 bars ... ready_on_first_bar=True` and then NOTHING for
# 2h23m - no SIGNAL, no `state ->`, no `no condition yet`. `on_data` was never
# called. The condition was IN as of the 2026-08-26 close, so a delivered bar
# would have bought immediately. NO BAR WAS DELIVERED.
#
# The mechanism, read from LEAN's own source rather than guessed:
#
#   * `BaseData.EndTime` is `get => Time; set => Time = value;`
#     (Common/Data/BaseData.cs:96-100). `PythonData` does NOT override it, so a
#     custom bar has NO PERIOD: EndTime == Time. A bar whose `time` is
#     2026-08-27 00:00 therefore ENDS at 2026-08-27 00:00.
#     CORROBORATED IN OUR OWN CONTAINER: v1's smoke `c43e580e7997` shows its
#     first order at `2021-05-03T04:00:00Z` (= 2021-05-03 00:00 ET) filled at
#     65.342655 = the 2021-05-03 close (65.31) x 1.0005 slippage. Same date for
#     bar and slice - EndTime == Time, confirmed on our stack, not just in the
#     upstream file.
#   * `LiveCustomDataSubscriptionEnumeratorFactory.CreateEnumerator` seeds
#     `frontier = request.StartTimeLocal` (:82) and only emits data with
#     `EndTime > frontier` (:152, :186). A session started at 11:58 local
#     therefore DISCARDS every row in the file, including the current day's.
#   * It re-reads the remote file every `min(increment, minimumIntervalCheck)`
#     = 30 MINUTES (:92-96, :62 default `TimeSpan.FromMinutes(30)`).
#   * `FastForwardEnumerator` is given `Time.MaxTimeSpan` as its maximum data
#     age (:130), so age alone never drops a row. Only the frontier does.
#
# CONSEQUENCE UNDER v1'S READER: the first row that can ever clear the frontier
# is the one dated the day AFTER the session starts - and our feed publishes
# that row DURING that session (verified: at 2026-08-27T18:21Z, mid-session, the
# CSV already carried `2026-08-27,79.855`). So v1 would first speak at the first
# 30-minute refresh after the market opens, reading a RUNNING, UNSETTLED
# intraday print as if it were a close. v1's own header measured that hazard at
# 4.58% of sessions flippable by a 3-cent wobble. The recommendation it drew
# from that - "start the session after the close" - DOES NOT WORK, because the
# emission happens the next morning regardless of when the session starts.
#
# ---------------------------------------------------------------------
# DESIGN DECISION 0 - THE FIX: GIVE THE BAR AN EXPLICIT END, AND NEVER SERVE
# THE RUNNING ROW.
#
# Two lines in `SpineBars.reader`, and together they make the live contract
# statable:
#
#   (a) `bar.time = <bar date> + 1 day`. Since EndTime == Time for PythonData,
#       this is the only way to give a daily custom bar an end that lies after
#       the moment the feed publishes it. The row for session D now ENDS at
#       D+1 00:00 local.
#   (b) rows dated >= TODAY (UTC) are dropped. The feed's last row is a live,
#       moving quote; it is not a close and must not be read as one.
#
# THE RESULTING LIVE CONTRACT, which is the thing a machinery test needs to be
# able to state: **exactly one bar per calendar day, delivered within 30 minutes
# of 00:00 America/New_York, carrying the PREVIOUS session's SETTLED close.**
# The algorithm therefore proposes just after midnight ET and the CEO's click
# lands during the following session.
#
# WHAT THIS BUYS AND WHAT IT COSTS, stated because an implementation is an
# interpretation. It buys backtest/live parity at the data layer - both modes
# now compute the signal from settled closes, which is the whole point of a
# machinery instrument. It costs a day of latency versus a fill at the signal
# bar's close, and that latency is REAL and is not modelled: the backtest fills
# at bar D's close, the live book fills whenever the CEO clicks during D+1.
# Measuring that gap is part of what this probe is for; it is not a defect the
# algorithm can fix.
#
# VERIFICATION STATUS, split honestly. The BACKTEST half is verifiable in a
# container and is verified: every order timestamp is the bar date + 1 day at
# the bar date's close price. The LIVE half is a PREDICTION derived from the
# LEAN source cited above and has NOT been observed by this seat. The
# falsifiable form: the first line of the live log matching `BAR ` should
# appear within 30 minutes after 00:00 ET and should name the PREVIOUS
# session's date and its settled close.
#
# ---------------------------------------------------------------------
# DESIGN DECISION 1 - EVERY BAR IS LOGGED, WHETHER OR NOT IT ACTS.
#
# `GET /fund/engine` says of itself: "last_bar_seen: null ... UNKNOWN - the
# session record carries no bar clock ... a quiet engine and a dead one look
# identical." v1 logged only on an action or a state change, so a healthy v1 and
# a dead v1 produced the same log. v2 emits one `BAR <date> close=... mean=...
# cond=... held=... action=...` line per delivered bar. Half that blind spot
# closes from inside the algorithm, at zero cost, and `docker logs | grep '^.*BAR '`
# now answers "is it alive" without inference.
#
# ---------------------------------------------------------------------
# DESIGN DECISION 2 - THE RULE, AND WHY THIS ONE.
#
# THE RULE, ENTIRE: at the close of a session whose close is BELOW its own
# 3-session mean, hold HYG; sell it back at the very next delivered bar. Flat or
# long, never short, at most one action per bar.
#
# The constraints were declared as FREQUENCY and SAFETY constraints, never
# return constraints, and were applied to the trailing 252 sessions
# (2025-08-26 -> 2026-08-26) of the fund's own HYG closes:
#   1. 2.5 <= actions/week <= 4.0  (inside the brief's 2-5 band with margin on
#      BOTH sides, because a rule at the edge falls out of band when the year
#      is not representative)
#   2. max gap between actions <= 10 sessions (never silent for two weeks)
#   3. >= 20 buys AND >= 20 sells in the trailing year
#   4. long-only, flat-or-long, <= 1 action per bar
#   5. **BOUNDED HOLD, STRICTLY SHORTER THAN THE COMMITTED BACKSTOP TIME EXIT.**
#      This one eliminated a whole family. A condition rule ("hold while fast >
#      slow") has an UNBOUNDED hold, so a committed 5-session time exit would
#      fire routinely, sell the position out from under an engine that still
#      believes it is long, and leave the probe stuck flat-but-thinks-held -
#      silent for the wrong reason. A fixed 1-session hold means the committed
#      exit rule fires ONLY when the machinery has failed, which is exactly what
#      a backstop is for.
#
# Ten shapes were scanned against those constraints (SMA-condition pairs 1/2,
# 1/3, 2/3; dip-buy variants on down-close, down-or-flat, below-mean3,
# below-mean5; holds of 1 and 2 sessions). Six cleared them.
# TIE-BREAK, inherited from v1 and kept for the same reason: **take the WORST
# full-window replica return among the admissible set.** Picking the worst
# admissible rule is the cheapest available proof that the choice was not
# return-motivated.
#
#   admissible (trailing-year actions/week, full-window replica equity):
#     down-or-flat, hold 1   3.21   x1.0815
#     down close,   hold 1   3.06   x1.0707
#     BELOW MEAN3,  HOLD 1   2.82   x1.0384   <- CHOSEN (worst return)
#     down-or-flat, hold 2   2.58   x1.1648
#     down close,   hold 2   2.50   x1.1621
#     (SMA 1/2 condition     2.66   x1.0337 - lower return, but REJECTED by
#      constraint 5: unbounded hold)
#   HYG buy-and-hold over the same full window: x1.2345. The chosen rule
#   UNDERPERFORMS BUY-AND-HOLD BY 20 POINTS over 5.5 years. That is intended and
#   is the point: nobody can mistake this for a strategy.
#
# MEASURED FREQUENCY of the chosen rule on the fund's own HYG closes:
#   TRAILING YEAR (252 sessions, 2025-08-26 -> 2026-08-26): **142 actions - 71
#   buys and 71 sells - 2.82 per week**; gaps median 1.0, p90 4, max 8 sessions;
#   mean interval 1.738 sessions.
#   FULL WINDOW (1,378 settled bars, 2021-03-02 -> 2026-08-26): 782 actions,
#   mean interval 1.758 sessions.
#   The eight most recent actions the rule would have taken: 2026-08-06,
#   08-07, 08-10, 08-11, 08-17, 08-18, 08-20, 08-21 (alternating buy/sell).
#
# ---------------------------------------------------------------------
# DESIGN DECISION 3 - HOLD_DAYS = 2, MEASURED. HOLD_DAYS is the DECISION
# CADENCE the walk-forward test leg is sized from, not the days a position is
# held (carried from the mechanism, cycle 3). The realised interval between
# actions is a mean of 1.758 sessions full-window and 1.738 in the trailing
# year; 2 is the honest declaration and it rounds AGAINST the strategy (longer
# test legs). Fold geometry it would buy IF this were ever submitted as a
# candidate - RUN, not asserted (`window_for_strategy(end='2026-08-26',
# hold_days=2, min_folds=4, floor='2021-05-03')`): **12 folds, 11-calendar-day
# test legs, first test leg 2026-04-16 -> 2026-04-27.** IT IS NOT BEING
# SUBMITTED AS A CANDIDATE AND CARRIES NO GATE VERDICT.
#
# DESIGN DECISION 4 - THE FEED IS A DIVIDEND-ADJUSTED TOTAL-RETURN SERIES
# (carried verbatim from v1). HYG distributes ~6%/yr and the fund's own closes
# run 64.72 (2021-03-02) -> 79.90 (2026-08-26) while HYG's quoted price fell
# over the same span. NOT corrected, deliberately: the fund marks its book on
# this feed, so this IS the fund's series and a signal computed on another one
# would be a divergence argument waiting to happen. Recorded because a silent
# interpretation is how meaning drifts.
#
# DESIGN DECISION 5 - `self.set_benchmark(self.sym)` IS MANDATORY AND IS
# PRESENT. `leanrunner.start_live` REFUSES to start an algorithm whose source
# lacks the string `set_benchmark`, because LEAN otherwise adds a SPY MINUTE
# subscription of its own and live-paper's stub data queue cannot serve it - the
# session dies with "LiveDataQueue has not implemented live data" before one bar
# of the fund's own data arrives. SYMBOLS SUBSCRIBED: exactly one, HYG.
#
# DESIGN DECISION 6 - TWO BOOKS, TWO SIZES, AND THEY ARE NOT THE SAME NUMBER.
# (Carried from builder run-builder-kp9: SAY WHICH BOOK.)
#   * THE ENGINE'S BOOK - `self.portfolio`, a LEAN paper book that in live mode
#     fills the algorithm's own orders internally whatever the fund decides. It
#     is sized by NOTIONAL (default 1,000,000) so the backtest answers a
#     question about the RULE and is comparable to v1's smoke. IT IS NOT THE
#     FUND'S NAV and it never was.
#   * THE FUND'S BOOK - moved only by a proposal the CEO approves. Its size is
#     capped IN THIS FILE at MAX_SIGNAL_USD = $50.00 (~2.5% of a $2,000 NAV):
#     `qty = min(requested, MAX_SIGNAL_USD / price)`. The SIGNAL_QTY the chair
#     passes to `start_live` is treated as a REQUEST that can only be reduced,
#     never as an amplifier, so a launch-flag typo cannot enlarge the blast
#     radius. At an HYG close near $79.9 the cap is 0.6258 shares; pass
#     `qty=0.6` for a ~$48 position, or leave the default 0.1 for a ~$8 one.
#   These two books WILL diverge the first time a proposal is declined. The
#   divergence is readable at `GET /fund/engine` -> `reconcile.verdict`, and it
#   is only attributable because one strategy owns this algorithm and the fund
#   trades HYG nowhere else. Keep it that way.
#
# DESIGN DECISION 7 - THE SELL PROPOSES THE QUANTITY THE BUY PROPOSED. The
# algorithm cannot see the fund's book, only the engine's, so it closes what it
# ASKED FOR (`self.open_signal_qty`), never a quantity it has inferred. If the
# buy was declined and the sell approved, the fund's own pre-trade gate is what
# refuses to open a short - and that refusal is an informative test of the
# machinery, not a failure of it. EXPECT IT and read it as such.
#
# DESIGN DECISION 8 - THE LIVE PATH IS GUARDED SIX WAYS. (a)-(d) are v1's,
# unchanged; (e) and (f) are new:
#   (a) no SIGNAL_TOKEN / STRATEGY_ID in a belt container, so `_send` no-ops and
#       logs that it did - a backtest is structurally silent;
#   (b) an action older than MAX_SIGNAL_AGE_DAYS is logged as replayed and not
#       sent (a backtest REPLAYS history; every 2021 action would otherwise land
#       in today's approval queue);
#   (c) one signal per bar date;
#   (d) NEVER SIGNAL A SELL THE ENGINE DOES NOT HOLD - enforced at the branch;
#   (e) NEVER SIGNAL A BUY WHEN THE ENGINE IS ALREADY LONG - structural in the
#       same branch, so the position can never be doubled;
#   (f) THE STRATEGY CANNOT CROSS ZERO. It is flat or long; there is exactly one
#       `set_holdings` (positive weight) and one `liquidate`, and an assertion
#       logs loudly if the engine's quantity ever goes negative. This matters
#       beyond tidiness: the fund's exit machinery can only SELL
#       (exitrule.py:326), so a strategy that can go short has NO WORKING EXIT.
#       This one cannot go short, so the committed exit rule below is a complete
#       backstop.
# Every order in this file exists INSIDE a backtest. The live path places no
# order: it POSTs a PROPOSAL to the spine's token-gated intake, where it queues
# behind the risk and compliance gates for the CEO's click. This file has no
# venue credentials and no route to one.
#
# ---------------------------------------------------------------------
# EXIT RULES TO BE COMMITTED BEFORE ENTRY (experimental-deployment rule).
# The algorithm's OWN exit is the 1-session sell above and is the routine path.
# The two rules below are BACKSTOPS the chair commits through the ordinary path,
# owned by THIS algorithm's strategy id (builder D14: the strategy on the rule
# must be the strategy that holds the position), SET before any entry event:
#   * TIME EXIT at 5 sessions from entry. The rule's own hold is 1 session, so
#     this can only fire when the routine sell did not execute - a declined
#     proposal, a dead session, a stuck queue. Measured: it would fire on 0 of
#     782 historical actions in normal operation.
#   * STOP at -2.0% from the entry price. Measured on 1,378 sessions: a
#     single-session move of -2.0% or worse occurred 2 times (0.15%), and the
#     worst 5-session drawdown from any entry breached -2.0% on 3.49% of
#     entries. It is a tail backstop, not a routine exit. (-1.0% would fire on
#     13.83% of 5-session windows and would become the primary exit; -3.0%
#     breached a single session once in 5.5 years.)
#
# ---------------------------------------------------------------------
# LIVE-VS-BACKTEST - what will NOT behave the same:
#   * FILL TIMING. The backtest fills at the signal bar's close. Live, the
#     proposal is raised just after 00:00 ET and the fill happens whenever the
#     CEO clicks during the next session. One session of price drift, unmodelled.
#   * WEEKENDS. Friday's row ends Saturday 00:00, so a Friday signal is proposed
#     on a Saturday and sits in the queue until Monday.
#   * `set_start_date` / `set_end_date` / `get_parameter` are inert in
#     live-paper: LEAN ignores the dates and the belt's parameters are not
#     passed, so NOTIONAL, TARGET_WEIGHT, LOOKBACK, HOLD_BARS and the default
#     5 bps slippage take their module defaults.
#   * `set_holdings` / `liquidate` in live mode move the ENGINE's paper book,
#     which is not the fund's book (DESIGN DECISION 6).
#   * On daily bars a live session is a once-a-day event, not a ticking feed.
#     Nothing here polls or loops.
# =====================================================================

SPINE = "http://host.docker.internal:8090/api/v1/fund"

#: Read STATICALLY by the harness (`leanrunner._declared_universe`) to build the
#: equal-weight, never-rebalanced, cost-free buy-and-hold bar. One name, so the
#: bar is HYG itself.
UNIVERSE = ["HYG"]

#: Gate fields. HOLD_DAYS is read by AST (`walkforward.declared_hold_days`).
#: CLAIM_TYPE and BENCHMARK are declared for the reader and for gate v5; neither
#: is read by any harness code today. THIS FILE IS NOT A CANDIDATE and is not
#: being submitted to the gate - the declarations exist so that nothing
#: downstream has to ASSUME them (an assumed hold fabricates the test's shape).
HOLD_DAYS = 2
CLAIM_TYPE = "alpha"
BENCHMARK = "HYG"

#: THE RULE. See DESIGN DECISION 2 - chosen on a declared frequency/safety
#: constraint set and tie-broken on the WORST return among the admissible.
#: Not tunable toward a verdict.
LOOKBACK = 3          # sessions in the mean the close is compared against
HOLD_BARS = 1         # sessions held before the unconditional exit

TARGET_WEIGHT = 0.99  # 1% cash buffer: the entry cannot be rejected for
                      # buying power. Uniform drag, i.e. PASS-UNFAVOURABLE.
NOTIONAL = 1_000_000  # THE ENGINE'S book (see DESIGN DECISION 6), not the NAV.

#: THE FUND'S book. A hard dollar cap on any proposal this algorithm raises.
#: Structural, not a launch flag: SIGNAL_QTY can only reduce it.
MAX_SIGNAL_USD = 50.0

#: An action older than this is replayed history, not a signal.
MAX_SIGNAL_AGE_DAYS = 3

#: Bars are delivered one calendar day after the session they describe, because
#: PythonData has no period and a bar that ends at its own midnight can never
#: clear a live session's frontier. See FINDING 0 / DESIGN DECISION 0.
BAR_END_OFFSET_DAYS = 1

#: `lookback_days=2000` is spelled as a LITERAL inside the two URL strings below
#: and nowhere else, because `factory.effective_history_floor` reads it
#: statically and anything computed or spelled two ways reads as UNKNOWN - and
#: unknown is never treated as unlimited.

#: Default verification window: two months after the feed's earliest bar at
#: lookback 2000 (2021-03-02, measured 2026-08-27), so the mean has room.
DEFAULT_START = (2021, 5, 3)


def _date(raw):
    if not raw:
        return None
    return tuple(int(p) for p in str(raw).split("-"))


class SpineBars(PythonData):
    """Daily closes from the fund's own market-data layer - the same feed the
    book is marked on. CSV because LEAN's remote-file reader iterates LINES, so
    a JSON blob would read as exactly one bar.

    TWO DELIBERATE DEPARTURES from the v1 reader, both in `reader` and both
    explained in FINDING 0 / DESIGN DECISION 0: the running row is dropped, and
    every bar is stamped one day after the session it describes so that it has
    an end a live frontier can clear.
    """

    def get_source(self, config, dt_, is_live):
        url = (f"{SPINE}/marketdata/bars?symbol={config.symbol.value}"
               f"&lookback_days=2000&format=csv")
        return SubscriptionDataSource(url, SubscriptionTransportMedium.REMOTE_FILE)

    def reader(self, config, line, dt_, is_live):
        try:
            ds, close = line.strip().split(",")
            session = datetime.strptime(ds, "%Y-%m-%d")
            # The feed's last row is a LIVE, MOVING quote - measured on the
            # sibling: three fetches minutes apart returned 79.861379, 79.86,
            # 79.84 while every prior bar was stable to the cent. It is not a
            # close and is never read as one.
            if session.date() >= datetime.utcnow().date():
                return None
            bar = SpineBars()
            bar.symbol = config.symbol
            # EndTime == Time for PythonData (BaseData.cs:96-100), so this IS
            # the bar's end. Stamping it one day on is the only way a daily
            # custom bar can end after the moment its row is published.
            bar.time = session + timedelta(days=BAR_END_OFFSET_DAYS)
            bar.value = float(close)
            bar["close"] = float(close)
            return bar
        except (ValueError, AttributeError):
            return None


class HygFastFlipProbeV2(QCAlgorithm):

    # --- lifecycle ------------------------------------------------------

    def initialize(self):
        start = _date(self.get_parameter("start")) or DEFAULT_START
        self.set_start_date(*start)
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(int(float(self.get_parameter("nav") or NOTIONAL)))

        self.w = float(self.get_parameter("weight") or TARGET_WEIGHT)
        self.lookback = int(self.get_parameter("lookback") or LOOKBACK)
        self.hold_bars = int(self.get_parameter("hold") or HOLD_BARS)
        slip = float(self.get_parameter("slip") or 0.0005)
        fee = float(self.get_parameter("fee") or 0)

        sec = self.add_data(SpineBars, UNIVERSE[0], Resolution.DAILY)
        sec.set_fee_model(ConstantFeeModel(fee))
        sec.set_slippage_model(ConstantSlippageModel(slip))
        self.sym = sec.symbol

        # FRACTIONAL SHARES, opt-in. The engine fills whole shares by default
        # and Alpaca does not, so a small book tested whole-share is tested
        # under a constraint the fund does not have (leanrunner
        # FRACTIONAL_PARAM). OFF unless the parameter is passed;
        # `honours_fractional()` reads this block statically and must find both
        # tokens.
        if str(self.get_parameter("fractional") or "0") == "1":
            old = sec.symbol_properties
            sec.symbol_properties = SymbolProperties(
                old.description, old.quote_currency, old.contract_multiplier,
                old.minimum_price_variation, 0.0001, old.market_ticker)

        # MANDATORY - see DESIGN DECISION 5. Without this string in the source,
        # `start_live` refuses to start the session at all.
        self.set_benchmark(self.sym)

        # No `set_warm_up`: the mean is primed explicitly below, and a warm-up
        # on top would double-count the primed bars. `set_warm_up(N, DAILY)`
        # warms N CALENDAR days rather than N bars (measured 2026-08-22), and
        # whether LEAN warms a custom REMOTE_FILE subscription in live-paper is
        # UNVERIFIED by this seat - priming in Python removes the dependency
        # and makes backtest and live run identical signal code.
        self.closes = deque(maxlen=max(2, self.lookback))
        self.sessions = 0
        self.actions = 0
        self.buys = 0
        self.sells = 0
        self.bars_held = 0
        self.open_signal_qty = 0.0
        self.pending_buy_date = None   # set when a buy is ordered, cleared once
                                       # the engine's book confirms a position
        self.last_signal_date = None
        self.first_session = None
        self.last_session = None
        self.short_alarms = 0
        self.zero_fill_alarms = 0

        self.live = bool(getattr(self, "live_mode", False))
        # The first bar the engine can deliver. In a backtest that is the row
        # dated (start - BAR_END_OFFSET_DAYS), because rows are stamped forward;
        # in live it is the row dated today (delivered after midnight, once
        # "today" has advanced past it). Prime everything strictly before.
        cutoff = (datetime.utcnow().date() if self.live
                  else (datetime(*start) - timedelta(days=BAR_END_OFFSET_DAYS)).date())
        self.primed = self._prime(cutoff)

        # Wired at run time via container env by `leanrunner._run_live`. Empty
        # in every belt container, so a backtest is structurally silent. Secrets
        # do not belong in a config.json that ends up committed.
        self.token = os.environ.get("SIGNAL_TOKEN", "") or (self.get_parameter("signal-token") or "")
        self.strategy_id = os.environ.get("STRATEGY_ID", "") or (self.get_parameter("strategy-id") or "")
        self.qty_request = float(os.environ.get("SIGNAL_QTY", "") or self.get_parameter("qty") or 0.1)

        self.log(f"hyg_fast_flip_probe_v2 init: live={self.live} "
                 f"lookback={self.lookback} hold_bars={self.hold_bars} "
                 f"weight={self.w} bar_end_offset_days={BAR_END_OFFSET_DAYS} "
                 f"cutoff={cutoff} primed={self.primed} "
                 f"ready_on_first_bar={len(self.closes) >= self.lookback} "
                 f"max_signal_usd={MAX_SIGNAL_USD} qty_request={self.qty_request}")

    # --- the prime ------------------------------------------------------

    def _prime(self, cutoff):
        """Fill the rolling window from sessions strictly BEFORE the first bar
        the engine will deliver, so the condition exists on bar one.

        Best effort and loudly reported. A failure costs up to `lookback`
        sessions of silence; it never kills the run, and an absent prime is
        reported rather than assumed away.
        """
        url = (f"{SPINE}/marketdata/bars?symbol={UNIVERSE[0]}"
               f"&lookback_days=2000&format=csv")
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                text = r.read().decode()
        except Exception as e:  # noqa: BLE001
            self.log(f"PRIME FAILED ({type(e).__name__}: {e}) - the mean will "
                     f"fill from streamed bars instead, costing up to "
                     f"{self.lookback} sessions of silence")
            return 0
        kept = 0
        last = None
        for line in text.splitlines():
            parts = line.strip().split(",")
            if len(parts) != 2:
                continue
            try:
                d = datetime.strptime(parts[0], "%Y-%m-%d").date()
                c = float(parts[1])
            except ValueError:
                continue
            if d >= cutoff:
                break
            self.closes.append(c)
            last = d
            kept += 1
        self.log(f"primed {kept} sessions before {cutoff} (last primed {last}); "
                 f"window holds {len(self.closes)} of {self.closes.maxlen}")
        return kept

    # --- the rule -------------------------------------------------------

    def on_data(self, data):
        if self.sym not in data or data[self.sym] is None:
            return

        # The bar's OWN session date. `data[sym].time` is the STAMPED time,
        # which this file deliberately set one day forward, so the session the
        # bar describes is one day back. Both are logged, so an off-by-one is
        # visible rather than inferred.
        stamped = data[self.sym].time
        bar_date = (stamped - timedelta(days=BAR_END_OFFSET_DAYS)).date()
        price = float(data[self.sym].value)
        self.closes.append(price)
        self.sessions += 1
        if self.first_session is None:
            self.first_session = str(bar_date)
        self.last_session = str(bar_date)

        qty_held = self.portfolio[self.sym].quantity
        held = qty_held != 0

        # GUARD (f): flat or long, never short. There is no code path that can
        # produce a negative quantity; if one ever appears, say so loudly rather
        # than trade through it - the fund's exit machinery can only SELL and a
        # short position would have no exit at all.
        if qty_held < 0:
            self.short_alarms += 1
            self.log(f"ALARM {bar_date}: engine quantity {qty_held} is SHORT - "
                     f"this strategy has no cover path; liquidating")
            self.liquidate(self.sym)
            return

        # NO SILENT ZERO-ORDER PATH: a buy that produced no position is a failed
        # buy, not a held position, and it must never look like one.
        if self.pending_buy_date is not None:
            if held:
                self.pending_buy_date = None
            else:
                self.zero_fill_alarms += 1
                self.log(f"ALARM {bar_date}: the buy ordered on "
                         f"{self.pending_buy_date} produced NO POSITION "
                         f"(quantity 0) - the book is too small for one share, "
                         f"or the order was rejected. Treating as flat.")
                self.pending_buy_date = None
                self.bars_held = 0

        if len(self.closes) < self.lookback:
            self.log(f"BAR {bar_date} stamped={stamped:%Y-%m-%d} "
                     f"close={price:.4f} mean=NA cond=NA held={held} "
                     f"action=none reason=only_{len(self.closes)}"
                     f"_of_{self.lookback}_bars")
            return

        vals = list(self.closes)[-self.lookback:]
        mean = sum(vals) / self.lookback
        cond = price < mean          # the dip condition

        side = None
        if held:
            self.bars_held += 1
            if self.bars_held >= self.hold_bars:
                side = "sell"        # GUARD (d): only ever reached while held
        elif cond:
            side = "buy"             # GUARD (e): only ever reached while flat

        self.log(f"BAR {bar_date} stamped={stamped:%Y-%m-%d} close={price:.4f} "
                 f"mean{self.lookback}={mean:.4f} cond={'in' if cond else 'out'} "
                 f"held={held} qty={qty_held} bars_held={self.bars_held} "
                 f"action={side or 'none'}")

        if side is None:
            return

        self.actions += 1
        reason = (
            f"HYG closed {price:.4f} on {bar_date}, "
            f"{'below' if cond else 'at or above'} its {self.lookback}-session "
            f"mean {mean:.4f}; the probe "
            + (f"takes a {self.hold_bars}-session position"
               if side == "buy" else
               f"closes the position opened {self.bars_held} session(s) ago")
            + " (machinery instrument - no return claim)")

        # THE ORDER. Inside a backtest this fills; in live mode it moves the
        # ENGINE's own paper book, which is not the fund's book. The fund's book
        # moves only via `_send` -> approval queue -> the CEO's click.
        if side == "buy":
            self.buys += 1
            self.bars_held = 0
            self.pending_buy_date = str(bar_date)
            self.set_holdings(self.sym, self.w)
        else:
            self.sells += 1
            self.bars_held = 0
            self.liquidate(self.sym)

        self._maybe_send(side, reason, bar_date, price)

    # --- the proposal path ----------------------------------------------

    def _signal_qty(self, side, price):
        """The quantity to PROPOSE to the fund - never the engine's quantity.

        A BUY is capped in DOLLARS (MAX_SIGNAL_USD) and the launch flag can only
        reduce it. A SELL proposes exactly what the BUY proposed, because this
        algorithm cannot see the fund's book and must never infer it.
        """
        if side == "sell":
            return self.open_signal_qty
        cap = MAX_SIGNAL_USD / price if price > 0 else 0.0
        qty = min(float(self.qty_request), cap)
        return float(int(qty * 10_000) / 10_000)   # truncate, never round up

    def _maybe_send(self, side, reason, bar_date, price):
        # Guard (c): one signal per bar date.
        if self.last_signal_date == bar_date:
            self.log(f"already signalled on {bar_date} - suppressed")
            return
        # Guard (b): a backtest REPLAYS history and every old action would
        # otherwise land in today's approval queue as a live proposal.
        age_days = (datetime.utcnow().date() - bar_date).days
        if age_days > MAX_SIGNAL_AGE_DAYS:
            self.log(f"historical action ({age_days}d old) - replayed, not sent")
            return
        qty = self._signal_qty(side, price)
        if qty <= 0:
            self.log(f"signal NOT sent: computed qty {qty} is not positive "
                     f"(side={side} price={price:.4f} request={self.qty_request})")
            return
        self.last_signal_date = bar_date
        if side == "buy":
            self.open_signal_qty = qty
        else:
            self.open_signal_qty = 0.0
        self.log(f"SIGNAL {side} {qty} HYG (~${qty * price:.2f}) - {reason}")
        self._send(side, qty, reason)

    def _send(self, side, qty, reason):
        # Guard (a): unset in every belt container, so a backtest cannot speak
        # even if the recency guard were wrong.
        if not (self.token and self.strategy_id):
            self.log("signal NOT sent: SIGNAL_TOKEN/STRATEGY_ID unset")
            return
        body = json.dumps({
            "token": self.token, "source": "lean",
            "algo_id": "hyg_fast_flip_probe_v2",
            "symbol": "HYG", "side": side, "qty": qty,
            "strategy_id": self.strategy_id, "reason": reason,
        }).encode()
        try:
            req = urllib.request.Request(
                f"{SPINE}/signals/external", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                self.log(f"signal accepted: {r.read().decode()[:200]}")
        except Exception as e:  # noqa: BLE001
            # A rejected proposal is the system working. Log and carry on - a
            # raise here would kill a live session over a queue decision.
            self.log(f"signal rejected/undeliverable: {e}")

    def on_end_of_algorithm(self):
        self.log(f"hyg_fast_flip_probe_v2: sessions={self.sessions} "
                 f"actions={self.actions} buys={self.buys} sells={self.sells} "
                 f"lookback={self.lookback} hold_bars={self.hold_bars} "
                 f"weight={self.w} primed={self.primed} "
                 f"first={self.first_session} last={self.last_session} "
                 f"short_alarms={self.short_alarms} "
                 f"zero_fill_alarms={self.zero_fill_alarms}")
