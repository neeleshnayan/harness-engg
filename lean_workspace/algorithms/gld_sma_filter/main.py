# region imports
from AlgorithmImports import *
import json
import urllib.request
# endregion

SPINE = "http://host.docker.internal:8090/api/v1/fund"


class SpineBars(PythonData):
    """Daily bars served by the fund spine's own market-data layer.

    Deliberate: LEAN judges the market on the SAME closes the fund marks its
    book with. A signal computed on one feed and a NAV marked on another is a
    divergence argument waiting to happen.

    CSV, one line per bar — LEAN's remote-file reader iterates LINES as data
    points, so a JSON blob reads as exactly one bar (the smoke test processed
    1 point of a 155-bar history before this switched to csv).
    """

    def get_source(self, config, date, is_live):
        url = (f"{SPINE}/marketdata/bars?symbol={config.symbol.value}"
               f"&lookback_days=700&format=csv")
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


class GldSmaFilter(QCAlgorithm):
    """Phase 1 sidecar: 100-day SMA filter on GLD, signal-only.

    In the market above its 100-day SMA, in cash below it — the exact strategy
    the operator asked Clark to backtest. This algorithm cannot trade: its
    entire output is a POST to the spine's token-gated signal intake, where the
    proposal waits in the approval queue behind the risk and compliance gates.
    The human click stays the only path to the venue.
    """

    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_cash(2000)
        self.gld = self.add_data(SpineBars, "GLD", Resolution.DAILY).symbol
        self.sma = self.sma(self.gld, 100)
        self.state = None  # "in" | "out" — signal fires only on CHANGE

        # Wired at run time via container env (see run_backtest.sh); empty =
        # signals are logged but not sent, so a half-configured run stays
        # harmless. Env beats LEAN parameters here: secrets do not belong in
        # a config.json that will end up committed.
        import os
        self.token = os.environ.get("SIGNAL_TOKEN", "") or (self.get_parameter("signal-token") or "")
        self.strategy_id = os.environ.get("STRATEGY_ID", "") or (self.get_parameter("strategy-id") or "")
        self.qty = float(os.environ.get("SIGNAL_QTY", "") or self.get_parameter("qty") or 0.1)

    def on_data(self, data: Slice):
        if self.gld not in data or not self.sma.is_ready:
            return
        price = data[self.gld].value
        want = "in" if price > self.sma.current.value else "out"
        if want == self.state:
            return
        prev, self.state = self.state, want
        if prev is None:
            return  # first observation is a state, not a signal

        side = "buy" if want == "in" else "sell"
        reason = (f"GLD {price:.2f} crossed {'above' if want == 'in' else 'below'} "
                  f"its 100-day SMA ({self.sma.current.value:.2f}); "
                  f"filter says {'hold gold' if want == 'in' else 'stand in cash'}")
        self.log(f"SIGNAL {side} {self.qty} GLD — {reason}")
        # Recency guard: a backtest REPLAYS history, and every 2025 crossing
        # would otherwise land in today's approval queue as a live proposal.
        # Only the live edge speaks; the replayed past is context, not signal.
        age_days = (datetime.utcnow() - self.time).days
        if age_days > 3:
            self.log(f"historical crossing ({age_days}d old) — replayed, not sent")
            return
        self._send(side, reason)

    def _send(self, side: str, reason: str):
        if not (self.token and self.strategy_id):
            self.log("signal NOT sent: signal-token/strategy-id parameters unset")
            return
        body = json.dumps({
            "token": self.token, "source": "lean", "algo_id": "gld_sma_filter",
            "symbol": "GLD", "side": side, "qty": self.qty,
            "strategy_id": self.strategy_id, "reason": reason,
        }).encode()
        try:
            req = urllib.request.Request(
                f"{SPINE}/signals/external", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                self.log(f"signal accepted: {r.read().decode()[:200]}")
        except Exception as e:
            # A rejected proposal is the system working; log and carry on.
            self.log(f"signal rejected/undeliverable: {e}")
