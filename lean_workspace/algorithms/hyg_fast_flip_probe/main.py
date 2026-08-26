# region imports
from AlgorithmImports import *
from collections import deque
from datetime import datetime, timedelta
import json
import os
import urllib.request
# endregion

# =====================================================================
# HYG FAST FLIP PROBE - A MACHINERY INSTRUMENT, NOT A CANDIDATE.
#
# Its purpose is to make the LIVE PATH VISIBLE within days: a LEAN algorithm
# that produces a BUY and a SELL on the fund's own daily feed often enough
# that a human can watch the chain - engine -> proposal -> approval queue ->
# UI - inside one week. ITS EDGE IS IRRELEVANT AND ITS GATE VERDICT IS
# IRRELEVANT. Nobody will ever deploy it for return, and it must never be
# tuned toward a better verdict: a machinery instrument tuned to look like a
# strategy stops being either. Requested by the chair on the CEO's
# instruction (2026-08-26), verbatim: "no point in testing with a silent
# algo."
#
# It is the SECOND algorithm targeting HYG. The other,
# `hyg_credit_sma_cross` (10/50), is a slow rule that would emit nothing for
# 2-3 months; THIS FILE is the one intended for the live session. Only one
# live session can run at a time (`leanrunner.start_live` refuses a second,
# leanrunner.py:640-645), so the two cannot collide.
#
# THE RULE, ENTIRE: hold HYG at 99% of NAV while its 2-session mean close is
# above its 4-session mean close, and stand in cash otherwise.
#
# ---------------------------------------------------------------------
# DESIGN DECISION 0 - THE ONE THIS FILE EXISTS TO FIX: ACT ON THE CONDITION,
# NEVER ON THE CROSSING.
#
# Measured on the sibling algorithm (2026-08-26): a fresh live session seeds
# its state on the first bar it receives WITHOUT ordering, because a crossing
# needs a previous state to cross from. So the first transition is consumed
# silently, and if that transition is DOWNWARD it is suppressed again (a sell
# of nothing is not a signal) - two crossings before anything is emitted. On
# a 10/50 rule that is a two-to-three MONTH silence.
#
# Here the state is a FUNCTION OF THE CONDITION AND THE BOOK, evaluated on
# every bar, with no memory required:
#
#     fast > slow AND flat      -> BUY   (the fix: no prior state needed)
#     fast <= slow AND holding  -> SELL
#     otherwise                 -> nothing
#
# The first bar is therefore ACTIONABLE. What makes that true and not merely
# hopeful is DESIGN DECISION 1: the means are primed from history before the
# first bar arrives, so `fast` and `slow` both exist on bar one.
#
# SESSIONS TO FIRST SIGNAL - measured, not asserted. Replaying the rule from
# every one of the 1,317 admissible historical start sessions in the fund's
# own HYG series (2021-03-01 -> 2026-08-26, 1,380 bars):
#     first signal on session 1: 55.7%  |  within 2: 69.7%  |  within 5: 92.9%
#     median 1 session, p90 5 sessions, WORST CASE OBSERVED 14 sessions.
# The asymmetry is structural and is not a defect: a session that starts
# while the condition is already IN buys immediately; a session that starts
# while it is OUT holds nothing, and there is nothing to sell, so it waits
# for the condition to turn. The only way to remove the wait entirely would
# be an unconditional first order, which would not be a signal.
#
# AS OF THE LAST BAR IN THE FEED (2026-08-26: mean2 79.885000 > mean4
# 79.770000) THE CONDITION IS **IN**. A session started against this data
# should BUY on its first bar. That is a falsifiable prediction, and the
# condition can flip before the session starts.
#
# ---------------------------------------------------------------------
# DESIGN DECISION 1 - PLAIN ARITHMETIC AND AN EXPLICIT PRIME; NO ENGINE
# INDICATORS AND NO `set_warm_up`.
#
# The means are `collections.deque` rolling windows computed in this file,
# PRIMED in `initialize` by fetching the same CSV the data feed reads and
# pushing the closes that fall strictly BEFORE the first bar the engine will
# deliver. Three reasons, each of which cost this seat something:
#
#   (a) `set_warm_up(N, Resolution.DAILY)` warms N CALENDAR days, not N bars
#       (measured 2026-08-22), and whether LEAN warms a custom REMOTE_FILE
#       subscription in LIVE-PAPER is an engine behaviour this seat has NOT
#       verified. The headline number of this dispatch is time-to-first-
#       signal; resting it on an unverified engine behaviour would make the
#       headline an assumption. Priming in Python removes the dependency.
#   (b) A previous whole-algorithm draft died on nonexistent engine methods.
#       A 2-bar and a 4-bar mean are arithmetic; there is no engine API here
#       to be wrong about.
#   (c) BACKTEST AND LIVE THEN RUN IDENTICAL CODE PATHS for the signal, which
#       is the entire point of a machinery instrument.
#
# The cutoff is the ONLY mode-dependent line in the file and it is declared:
# in a backtest, bars strictly before `start`; in live, bars strictly before
# TODAY (UTC) - which also excludes the feed's last, unsettled bar (see
# LIVE-VS-BACKTEST). If the prime fails (no network, bad payload) the
# algorithm does NOT die: it logs the failure loudly and the means fill from
# the streamed bars instead, costing up to SLOW sessions of silence. An
# absent prime is reported, never assumed to be zero history.
#
# ---------------------------------------------------------------------
# DESIGN DECISION 2 - FAST=2 / SLOW=4, CHOSEN ON A DECLARED FREQUENCY
# CONSTRAINT AND THEN DELIBERATELY ON THE WORST RETURN.
#
# The constraints were written before any equity number was read, and they
# are about VISIBILITY and about the CEO's approval queue, never about money:
#   1. median gap between actions <= 5 sessions   (roughly weekly)
#   2. p90 gap <= 10 sessions                     (nine in ten waits < 2 wks)
#   3. max gap <= 20 sessions                     (never silent for a month)
#   4. >= 20 buys AND >= 20 sells                 (both directions, gate floor)
#   5. p90 wait-to-first-signal <= 6 sessions     (a fresh session speaks fast)
# Constraint 3 has a ceiling written into it from the other side: a rule
# firing EVERY session is not better, because every live signal becomes an
# item in the CEO's approval queue.
#
# Ten of the forty (fast, slow) pairs scanned over fast in 1..5, slow in
# 3..15 clear all five: 1/3, 1/4, 1/5, 1/6, 2/3, 2/4, 2/5, 3/5, 4/5, 5/6.
# **2/4 was taken because it is the WORST PERFORMER of the ten** - replica
# equity x0.9622 over the window against HYG buy-and-hold x1.2317. Picking
# the worst admissible rule is the cheapest available proof that the choice
# was not return-motivated, and it is the same tie-break the sibling used.
#
# MEASURED FREQUENCY of 2/4 on the fund's own HYG closes (1,380 bars,
# 2021-03-01 -> 2026-08-26): **385 actions - 193 buys and 192 sells - one
# action per 3.57 sessions** over the acting span; gaps median 3.0, mean
# 3.57, p90 6, max 16 sessions. The six most recent actions the rule would
# have taken: sell 2026-08-11, buy 08-12, sell 08-17, buy 08-20, sell 08-21,
# buy 08-24.
#
# ---------------------------------------------------------------------
# DESIGN DECISION 3 - THE FEED IS A DIVIDEND-ADJUSTED TOTAL-RETURN SERIES.
# HYG distributes ~6%/yr and the fund's own closes run 64.83 (2021-03-01) ->
# 79.85 (2026-08-26) while HYG's quoted price fell over the same span. A
# price-vs-mean rule read on a total-return series is structurally biased
# LONG. NOT corrected, deliberately: the fund marks its book on this feed, so
# this IS the fund's series and a signal computed on another one would be a
# divergence argument waiting to happen. Irrelevant to a machinery
# instrument; recorded because a silent interpretation is how meaning drifts.
#
# DESIGN DECISION 4 - HOLD_DAYS = 4, MEASURED. HOLD_DAYS is the DECISION
# CADENCE the walk-forward test leg is sized from, not the days a position is
# held. The realised interval between actions in the replica is a median of 3
# and a mean of 3.57 sessions (n=384 gaps); 4 is the honest declaration and
# it rounds AGAINST the strategy (a longer test leg, fewer folds). NOT
# TESTABLE is not the risk here - the opposite is - and either way THIS FILE
# IS NOT GOING TO THE GATE.
#
# DESIGN DECISION 5 - `self.set_benchmark(self.sym)` IS MANDATORY AND IS
# PRESENT. `leanrunner.start_live` (leanrunner.py:634-639) REFUSES to start
# an algorithm whose source lacks the string `set_benchmark`, because LEAN
# otherwise adds a SPY MINUTE subscription of its own and live-paper's stub
# data queue cannot serve it - the session dies with "LiveDataQueue has not
# implemented live data" before one bar of the fund's own data arrives. The
# benchmark is this algorithm's OWN custom SpineBars symbol, the only series
# the container can actually receive. SYMBOLS SUBSCRIBED: exactly one, HYG,
# plus the internal benchmark feed LEAN derives from that same symbol.
#
# DESIGN DECISION 6 - TARGET_WEIGHT = 0.99, not 1.00: a 1% cash buffer so the
# entry market order cannot be rejected for buying power. A uniform drag
# against a fully-invested bar, i.e. PASS-UNFAVOURABLE; it can never flatter.
#
# DESIGN DECISION 7 - NOTIONAL = 1_000_000 is the answer about the RULE, not
# about the DEPLOYMENT. LEAN fills whole shares by default and HYG prints
# ~$80, so a $2,000 book is 24 shares. The `fractional` switch IS honoured
# (`leanrunner.honours_fractional` reads the block in `initialize`
# statically) and is OFF unless passed. In LIVE mode none of this applies:
# `set_cash` is overridden by the paper brokerage and the proposed size comes
# from SIGNAL_QTY.
#
# DESIGN DECISION 8 - THE LIVE PATH IS FOUR-WAY GUARDED, and guard (d) is
# kept from the sibling because a smoke container caught it there:
#   (a) no SIGNAL_TOKEN / STRATEGY_ID in a belt container, so `_send` no-ops
#       and logs that it did - a backtest is structurally silent;
#   (b) an action older than MAX_SIGNAL_AGE_DAYS is logged as replayed and
#       not sent (a backtest REPLAYS history; every 2021 action would
#       otherwise land in today's approval queue);
#   (c) one signal per calendar date, because the feed's LAST BAR IS LIVE AND
#       MOVING and a re-polled source could re-fire the same session;
#   (d) **NEVER SIGNAL A SELL OF STOCK THE ENGINE DOES NOT HOLD.** With the
#       condition design this can no longer arise from the first-bar case,
#       which is exactly why it stays: it is now a structural invariant with
#       no reachable path, and an invariant with no path is the cheapest kind
#       to keep. It is enforced at the branch, not after it.
# Every order below exists INSIDE a backtest. The live path does not place
# orders either: it POSTs a PROPOSAL to the spine's token-gated intake
# (`/fund/signals/external`), where it queues behind the risk and compliance
# gates for the CEO's click. This file has no venue credentials and no route
# to one.
#
# ---------------------------------------------------------------------
# LIVE-VS-BACKTEST - what will NOT behave the same:
#
#   * THE LAST BAR OF THE FEED IS AN UNSETTLED, MOVING QUOTE (measured
#     2026-08-26 on the sibling: three fetches minutes apart returned close
#     79.861379, then 79.86, then 79.84, while every prior bar was stable to
#     the cent). A 2/4 mean rule is MORE exposed to this than the sibling's
#     10/50, and the gap is MEASURED, not asserted. Today's close carries
#     half the fast mean and a quarter of the slow one, so
#     d(fast-slow)/d(close) = 0.2500 here against 0.0800 for 10/50; the close
#     move needed to flip the condition has a median of $0.340 here against
#     $6.392 there, and on **4.58% of the 1,376 sessions measured a 3-cent
#     intraday wobble is enough to flip the condition, against 0.60% for
#     10/50** - roughly 7.6x the exposure. A condition can therefore appear
#     and disappear inside a session. Guard (c) stops a double-fire; it
#     CANNOT stop a signal that would not have fired off the settled close.
#     THE RECOMMENDATION FOLLOWS AND IT IS STRONGER HERE THAN THERE: start
#     the live session AFTER the US close (>= 16:15 ET), not before. (For
#     reference, on the 2026-08-26 close the margin was 0.115, needing a
#     $0.46 move to flip - a comfortable session, not a typical one.)
#   * `set_start_date` / `set_end_date` / `get_parameter` are inert in
#     live-paper: LEAN ignores the dates and the belt's parameters are not
#     passed, so NOTIONAL, TARGET_WEIGHT, FAST, SLOW and the default 5 bps
#     slippage take their module defaults.
#   * `set_holdings` / `liquidate` in live mode move a paper LEAN book that
#     is NOT the fund's book. The fund's book moves only via `_send` -> the
#     approval queue -> the CEO's click. The two can and will diverge; the
#     LEAN book is this algorithm's own bookkeeping, never the NAV.
#   * On daily bars a live session is a ONCE-A-DAY event, not a ticking feed
#     (`leanrunner.start_live` docstring). Nothing here polls or loops.
# =====================================================================

SPINE = "http://host.docker.internal:8090/api/v1/fund"

#: Read STATICALLY by the harness (`leanrunner._declared_universe`) to build
#: the equal-weight, never-rebalanced, cost-free buy-and-hold bar. One name,
#: so the bar is HYG itself.
UNIVERSE = ["HYG"]

#: Gate fields. HOLD_DAYS is read by AST (`walkforward.declared_hold_days`).
#: CLAIM_TYPE and BENCHMARK are declared for the reader and the coming gate-v5
#: fields; neither is read by any harness code today (grep-verified).
HOLD_DAYS = 4
CLAIM_TYPE = "alpha"
BENCHMARK = "HYG"

#: The rule. See DESIGN DECISION 2 - chosen on frequency, tie-broken on the
#: WORST return among the admissible set. Not tunable toward a verdict.
FAST = 2
SLOW = 4

TARGET_WEIGHT = 0.99
NOTIONAL = 1_000_000

#: An action older than this is replayed history, not a signal.
MAX_SIGNAL_AGE_DAYS = 3

#: Declared ONCE, in ONE string (the bar URL below), because
#: `factory.effective_history_floor` reads it statically to set this
#: candidate's data-path floor. Two different values, or none, gets the
#: SHALLOWEST treatment - unknown is never unlimited.

#: Default verification window: two months after the feed's earliest bar at
#: lookback 2000 (2021-03-01, measured 2026-08-26), so the means have room.
DEFAULT_START = (2021, 5, 3)


def _date(raw):
    if not raw:
        return None
    return tuple(int(p) for p in str(raw).split("-"))


class SpineBars(PythonData):
    """Daily closes from the fund's own market-data layer - the same feed the
    book is marked on. CSV because LEAN's remote-file reader iterates LINES,
    so a JSON blob would read as exactly one bar."""

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


class HygFastFlipProbe(QCAlgorithm):

    # --- lifecycle ------------------------------------------------------

    def initialize(self):
        start = _date(self.get_parameter("start")) or DEFAULT_START
        self.set_start_date(*start)
        end = _date(self.get_parameter("end"))
        if end:
            self.set_end_date(*end)
        self.set_cash(int(float(self.get_parameter("nav") or NOTIONAL)))

        self.w = float(self.get_parameter("weight") or TARGET_WEIGHT)
        self.fast_n = int(self.get_parameter("fast") or FAST)
        self.slow_n = int(self.get_parameter("slow") or SLOW)
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
        # `honours_fractional()` reads this block statically and must find
        # both tokens.
        if str(self.get_parameter("fractional") or "0") == "1":
            old = sec.symbol_properties
            sec.symbol_properties = SymbolProperties(
                old.description, old.quote_currency, old.contract_multiplier,
                old.minimum_price_variation, 0.0001, old.market_ticker)

        # MANDATORY - see DESIGN DECISION 5. Without this string in the
        # source, `start_live` refuses to start the session at all.
        self.set_benchmark(self.sym)

        # No `set_warm_up`: the means are primed explicitly below, and a
        # warm-up on top would double-count the primed bars. See DECISION 1.
        self.closes = deque(maxlen=max(self.fast_n, self.slow_n))
        self.state = None          # "in" | "out" - derived from the CONDITION
        self.sessions = 0
        self.actions = 0
        self.buys = 0
        self.sells = 0
        self.last_signal_date = None
        self.first_session = None
        self.last_session = None

        self.live = bool(getattr(self, "live_mode", False))
        cutoff = (datetime.utcnow().date() if self.live
                  else datetime(*start).date())
        self.primed = self._prime(cutoff)

        # Wired at run time via container env by `leanrunner._run_live`. Empty
        # in every belt container, so a backtest is structurally silent.
        # Secrets do not belong in a config.json that ends up committed.
        self.token = os.environ.get("SIGNAL_TOKEN", "") or (self.get_parameter("signal-token") or "")
        self.strategy_id = os.environ.get("STRATEGY_ID", "") or (self.get_parameter("strategy-id") or "")
        self.qty = float(os.environ.get("SIGNAL_QTY", "") or self.get_parameter("qty") or 0.1)

        self.log(f"hyg_fast_flip_probe init: live={self.live} "
                 f"fast={self.fast_n} slow={self.slow_n} weight={self.w} "
                 f"cutoff={cutoff} primed={self.primed} "
                 f"ready_on_first_bar={len(self.closes) >= self.slow_n}")

    # --- the prime ------------------------------------------------------

    def _prime(self, cutoff):
        """Fill the rolling window from bars strictly BEFORE the first bar the
        engine will deliver, so the condition exists on bar one.

        Best effort and loudly reported. A failure costs up to `slow` sessions
        of silence; it never kills the run, and an absent prime is reported
        rather than assumed away.
        """
        url = (f"{SPINE}/marketdata/bars?symbol={UNIVERSE[0]}"
               f"&lookback_days=2000&format=csv")
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                text = r.read().decode()
        except Exception as e:  # noqa: BLE001
            self.log(f"PRIME FAILED ({type(e).__name__}: {e}) - the means will "
                     f"fill from streamed bars instead, costing up to "
                     f"{self.slow_n} sessions of silence")
            return 0
        kept = 0
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
            kept += 1
        self.log(f"primed {kept} bars before {cutoff}; window holds "
                 f"{len(self.closes)} of {self.closes.maxlen}")
        return kept

    # --- the rule -------------------------------------------------------

    def _means(self):
        if len(self.closes) < self.slow_n:
            return None, None
        vals = list(self.closes)
        return (sum(vals[-self.fast_n:]) / self.fast_n,
                sum(vals[-self.slow_n:]) / self.slow_n)

    def on_data(self, data):
        if self.sym not in data or data[self.sym] is None:
            return

        # The bar's OWN date, never self.time: LEAN advances algorithm time to
        # a daily bar's END, so self.time is one session ahead of the bar it
        # is describing (measured, Entry 11).
        bar_date = data[self.sym].time.date()
        price = float(data[self.sym].value)
        self.closes.append(price)
        self.sessions += 1
        if self.first_session is None:
            self.first_session = str(bar_date)
        self.last_session = str(bar_date)

        fast, slow = self._means()
        if fast is None:
            self.log(f"{bar_date}: only {len(self.closes)}/{self.slow_n} bars "
                     f"- no condition yet")
            return

        want = "in" if fast > slow else "out"
        held = self.portfolio[self.sym].quantity != 0

        # THE FIX (DESIGN DECISION 0): the action follows from the CONDITION
        # and the BOOK, not from a transition. No prior state is required, so
        # the first bar is actionable.
        if want == "in" and not held:
            side = "buy"
        elif want == "out" and held:
            side = "sell"
        else:
            # GUARD (d) lives in this branch: `want == "out" and not held`
            # falls through to nothing - a sell of stock the engine does not
            # hold is never ordered and never signalled.
            if want != self.state:
                self.log(f"state -> {want} on {bar_date} with "
                         f"{'a position' if held else 'nothing'} held "
                         f"- no order, no signal")
            self.state = want
            return

        self.state = want
        self.actions += 1
        if side == "buy":
            self.buys += 1
        else:
            self.sells += 1

        reason = (
            f"HYG {self.fast_n}-session mean {fast:.4f} is "
            f"{'above' if want == 'in' else 'below'} its {self.slow_n}-session "
            f"mean {slow:.4f} on the {bar_date} close ({price:.4f}); rule says "
            f"{'hold credit' if want == 'in' else 'stand in cash'}")

        # THE ORDER. Inside a backtest this fills; in live mode it moves the
        # engine's own paper book, which is not the fund's book. The fund's
        # book moves only via `_send` -> approval queue -> the CEO's click.
        if side == "buy":
            self.set_holdings(self.sym, self.w)
        else:
            self.liquidate(self.sym)

        self.log(f"SIGNAL {side} {self.qty} HYG - {reason}")
        self._maybe_send(side, reason, bar_date)

    # --- the proposal path ----------------------------------------------

    def _maybe_send(self, side, reason, bar_date):
        # Guard (c): one signal per calendar date. The feed's last bar is a
        # LIVE, MOVING quote, so a re-polled source can present the same
        # session twice with different values.
        if self.last_signal_date == bar_date:
            self.log(f"already signalled on {bar_date} - suppressed")
            return
        # Guard (b): a backtest REPLAYS history and every old action would
        # otherwise land in today's approval queue as a live proposal.
        age_days = (datetime.utcnow().date() - bar_date).days
        if age_days > MAX_SIGNAL_AGE_DAYS:
            self.log(f"historical action ({age_days}d old) - replayed, not sent")
            return
        self.last_signal_date = bar_date
        self._send(side, reason)

    def _send(self, side, reason):
        # Guard (a): unset in every belt container, so a backtest cannot speak
        # even if the recency guard were wrong.
        if not (self.token and self.strategy_id):
            self.log("signal NOT sent: SIGNAL_TOKEN/STRATEGY_ID unset")
            return
        body = json.dumps({
            "token": self.token, "source": "lean",
            "algo_id": "hyg_fast_flip_probe",
            "symbol": "HYG", "side": side, "qty": self.qty,
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
        self.log(f"hyg_fast_flip_probe: sessions={self.sessions} "
                 f"actions={self.actions} buys={self.buys} sells={self.sells} "
                 f"fast={self.fast_n} slow={self.slow_n} weight={self.w} "
                 f"primed={self.primed} first={self.first_session} "
                 f"last={self.last_session} final_state={self.state}")
