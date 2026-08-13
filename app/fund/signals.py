"""The signal→order loop: what turns a registered strategy into a live trade.

Until this existed the fund had strategies with allocations and universes but no
mechanism that ever *ran* them — every fill in the book arrived from somewhere
else. This is the missing link, and because it is the piece that spends real
money it is built to propose, never to execute.

The contract, deliberately narrow:

  * **Proposes only.** Every intended trade goes through
    :meth:`OrderPipeline.propose_order`, which runs the venue check and the risk
    gate and leaves the order *pending human approval*. This module holds no
    approval path at all, so no code change here can make the fund trade by
    itself — enabling autonomy has to be a separate, deliberate decision made
    somewhere else.
  * **Refuses rather than guesses.** A symbol whose bars will not load, a
    template without enough history to fill its lookback, a strategy with no
    allocation — each is skipped with a stated reason. None of them produce a
    "flat" signal, because "I don't know" and "be flat" are different
    instructions and only one of them is a decision.
  * **Idempotent per cycle.** A signal that is still true on the next tick must
    not stack a second order on top of the first. Anything already pending for
    the same strategy and symbol suppresses a new proposal.

Sizing follows from the target the operator already set: a strategy allocated
25% of NAV over two symbols targets 12.5% in each when its signal is long, and
zero when it is flat. The delta against what is actually held is the trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.fund.backtest import signals_for
from app.fund.connectors.base import Order, Side
from app.fund.marketdata import DAILY, BarsError, fetch_bars

#: Below this the trade is not worth its own spread — the same floor the
#: rebalancer uses, so the two do not disagree about what "too small" means.
MIN_TRADE_USD = 5.0

#: The strategy states that mean "this is carrying capital and should trade".
#: Read from the registry rather than assumed: the book uses "deployed", and a
#: runner filtering on a state that never occurs does nothing at all — silently.
LIVE_STATES = ("deployed", "live")

#: A template must have enough bars to fill its longest lookback plus a margin,
#: or its first signals are computed from a partial window and mean nothing.
WARMUP_MARGIN_BARS = 10


@dataclass
class SignalDecision:
    """What one strategy/symbol pair wants, and why."""
    strategy_id: str
    strategy_name: str
    symbol: str
    signal: float | None            # -1 / 0 / +1, or None when unmeasurable
    target_usd: float | None
    current_usd: float | None
    delta_usd: float | None
    action: str                     # buy | sell | hold | skip
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "signal": self.signal,
            "target_usd": None if self.target_usd is None else round(self.target_usd, 2),
            "current_usd": None if self.current_usd is None else round(self.current_usd, 2),
            "delta_usd": None if self.delta_usd is None else round(self.delta_usd, 2),
            "action": self.action,
            "reason": self.reason,
        }


class SignalRunner:
    """Evaluates live strategies and proposes the orders their signals imply."""

    def __init__(self, strategies, nav, pipeline, pricer: Callable[[str], float],
                 pending_lookup: Callable[[], list[dict]],
                 bars_fetcher=fetch_bars, lookback_days: int = 400,
                 market_open: Callable[[], bool | None] | None = None):
        self._strategies = strategies
        self._nav = nav
        self._pipeline = pipeline
        self._pricer = pricer
        self._pending = pending_lookup
        self._fetch = bars_fetcher
        self._lookback_days = lookback_days
        self._market_open = market_open

    # ------------------------------------------------------------- evaluate
    def evaluate(self) -> list[SignalDecision]:
        """What every live strategy currently wants. Proposes nothing."""
        snap = self._nav.compute()
        total_nav = float(snap.total_nav_usd)
        held = {str(p["symbol"]).upper(): float(p["usd_value"]) for p in snap.positions}

        out: list[SignalDecision] = []
        for s in self._strategies.list():
            # "deployed" is the state a funded strategy actually carries.
            if s.get("state") not in LIVE_STATES:
                continue
            sid, name = s["strategy_id"], s.get("name", s["strategy_id"])
            alloc = s.get("allocation_pct")
            symbols = [x.upper() for x in (s.get("assets") or [])]
            defn = s.get("definition") or {}
            # Definitions in this book store the template under "type";
            # accept the other spellings rather than silently skipping.
            template = defn.get("type") or defn.get("strategy") or defn.get("template")

            if not alloc:
                out.append(self._skip(sid, name, "—", "no allocation set — nothing to size against"))
                continue
            if not symbols:
                out.append(self._skip(sid, name, "—", "no symbols scoped to this strategy"))
                continue
            if not template:
                out.append(self._skip(
                    sid, name, "—",
                    "definition names no signal template, so there is nothing to evaluate",
                ))
                continue

            # Equal weight within the strategy. Not a claim that equal weight is
            # optimal — it is the only split the operator has actually specified.
            per_symbol_target_usd = (float(alloc) / 100.0) * total_nav / len(symbols)

            for sym in symbols:
                out.append(self._evaluate_one(
                    sid, name, sym, template, defn, per_symbol_target_usd, held.get(sym, 0.0),
                ))
        return out

    def _evaluate_one(self, sid, name, sym, template, defn,
                      target_full_usd: float, current_usd: float) -> SignalDecision:
        # A strategy may declare its own bar size. Daily is the default because
        # it is what a slow trend template is designed for; an intraday strategy
        # has to say so, since the data behind it is thinner and IEX-only.
        timeframe = str(defn.get("timeframe") or DAILY)
        try:
            bars = self._fetch(sym, lookback_days=self._lookback_days,
                               timeframe=timeframe)
        except BarsError as e:
            return self._skip(sid, name, sym, f"bars unavailable ({e})")
        except TypeError:
            # A fetcher that predates timeframes still serves daily bars.
            if timeframe != DAILY:
                return self._skip(sid, name, sym,
                                  f"this data source cannot serve {timeframe} bars")
            try:
                bars = self._fetch(sym, lookback_days=self._lookback_days)
            except BarsError as e:
                return self._skip(sid, name, sym, f"bars unavailable ({e})")
            except Exception as e:  # noqa: BLE001
                return self._skip(sid, name, sym, f"bars failed ({type(e).__name__}: {e})")
        except Exception as e:  # noqa: BLE001
            return self._skip(sid, name, sym, f"bars failed ({type(e).__name__}: {e})")

        prices = bars.closes
        need = self._warmup_bars(template, defn)
        if len(prices) < need:
            return self._skip(
                sid, name, sym,
                f"{len(prices)} bars, template needs {need} to warm up — "
                "an unwarmed signal is not a signal",
            )

        try:
            sigs = signals_for(template, prices, **self._params(template, defn))
        except Exception as e:  # noqa: BLE001
            return self._skip(sid, name, sym, f"signal evaluation failed ({e})")
        if not sigs:
            return self._skip(sid, name, sym, "template produced no signals")

        signal = float(sigs[-1])
        target_usd = target_full_usd * signal
        delta = target_usd - current_usd

        if abs(delta) < MIN_TRADE_USD:
            return SignalDecision(
                sid, name, sym, signal, target_usd, current_usd, delta, "hold",
                f"already within ${MIN_TRADE_USD:.0f} of target",
            )
        # A short is a different instrument with different borrow and margin
        # rules; the fund is long-only until that is deliberately enabled.
        if target_usd < 0:
            return SignalDecision(
                sid, name, sym, signal, target_usd, current_usd, delta, "skip",
                "template wants a SHORT and this fund is long-only — not proposed",
            )
        return SignalDecision(
            sid, name, sym, signal, target_usd, current_usd, delta,
            "buy" if delta > 0 else "sell",
            f"signal {signal:+.0f} targets ${target_usd:,.2f} against ${current_usd:,.2f} held",
        )

    # -------------------------------------------------------------- propose
    def run(self, actor: str = "signal-runner", dry_run: bool = True,
            venue: str = "alpaca") -> dict[str, Any]:
        """Evaluate, then propose the trades the signals imply.

        ``dry_run`` defaults to True: calling this with no arguments tells you
        what WOULD be proposed and touches nothing. Proposals still require a
        human approval afterwards — this method has no path to execution.
        """
        # Proposing into a closed market prices the trade off a stale mark and
        # queues it to fill on an opening auction nobody reviewed. A dry run is
        # always allowed — looking is free, and this is exactly when an operator
        # wants to see what tomorrow's open would do.
        open_now = self._market_open() if self._market_open else None
        if not dry_run and open_now is False:
            return {
                "dry_run": False, "evaluated": [d.to_dict() for d in self.evaluate()],
                "proposed": [], "suppressed": [], "rejected": [],
                "counts": {"evaluated": 0, "proposed": 0, "suppressed": 0, "rejected": 0},
                "market_open": False,
                "note": "market is CLOSED — nothing proposed. Re-run when it opens, "
                        "or use dry_run to see what the signals currently want.",
            }

        decisions = self.evaluate()
        pending_keys = self._pending_keys()

        proposed, suppressed, rejected = [], [], []
        for d in decisions:
            if d.action not in ("buy", "sell"):
                continue
            key = (d.strategy_id, d.symbol)
            if key in pending_keys:
                suppressed.append({**d.to_dict(),
                                   "reason": "an order for this strategy/symbol is already "
                                             "pending approval — not stacking another"})
                continue

            price = self._safe_price(d.symbol)
            if price is None:
                suppressed.append({**d.to_dict(),
                                   "reason": "no usable price — cannot size an order"})
                continue
            qty = round(abs(d.delta_usd or 0.0) / price, 6)
            if qty <= 0:
                suppressed.append({**d.to_dict(), "reason": "sizes to zero shares"})
                continue

            if dry_run:
                # Run the gate WITHOUT writing. RiskGate.check is pure, so a dry
                # run can tell the operator a trade would be refused instead of
                # offering a button whose only possible outcome is a rejection
                # — and an ORDER_REJECTED event in the log for a click that
                # never had a chance.
                would = self._would_breach(d.symbol, d.action, qty, price)
                row = {**d.to_dict(), "qty": qty, "price": price, "dry_run": True}
                if would:
                    rejected.append({**row, "status": "would_be_rejected",
                                     "breaches": would})
                else:
                    proposed.append(row)
                continue

            order = Order(venue=venue, symbol=d.symbol,
                          side=Side.BUY if d.action == "buy" else Side.SELL,
                          qty=qty, strategy_id=d.strategy_id)
            res = self._pipeline.propose_order(order, actor=actor)
            row = {**d.to_dict(), "qty": qty, "price": price, **res}
            # A gate rejection is a RESULT, not an error: it is the risk engine
            # doing its job, and it must be visible rather than swallowed.
            (rejected if res.get("status") == "rejected" else proposed).append(row)
            if res.get("status") != "rejected":
                pending_keys.add(key)

        return {
            "dry_run": dry_run,
            # None means the clock was unreachable, which is NOT the same as
            # closed — the caller sees the difference.
            "market_open": open_now,
            "evaluated": [d.to_dict() for d in decisions],
            "proposed": proposed,
            "suppressed": suppressed,
            "rejected": rejected,
            "counts": {
                "evaluated": len(decisions),
                "proposed": len(proposed),
                "suppressed": len(suppressed),
                "rejected": len(rejected),
            },
            "note": ("nothing was written — dry run" if dry_run else
                     "orders are PENDING APPROVAL; this runner cannot approve them"),
        }

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _skip(sid, name, sym, reason) -> SignalDecision:
        return SignalDecision(sid, name, sym, None, None, None, None, "skip", reason)

    @staticmethod
    def _params(template: str, defn: dict) -> dict[str, Any]:
        """Translate a strategy definition's parameters into the flat keyword
        names :func:`signals_for` expects.

        Definitions are written per template — the RSI strategy stores
        ``{"period": 14, "low": 30, "high": 70}``, MACD stores
        ``{"fast": 12, "slow": 26, "signal": 9}`` — while ``signals_for`` takes
        one flat namespace (``rsi_period``, ``macd_fast``, …). Passing the raw
        definition through would silently drop every configured value and run on
        defaults, and because several defaults happen to match the configured
        values, it would LOOK correct while ignoring the operator entirely.

        Anything unrecognised is dropped rather than forwarded: an unknown key
        reaching a signal function is a crash, and a crash here stops a strategy
        from trading.
        """
        alias: dict[str, dict[str, str]] = {
            "sma": {"fast": "fast", "slow": "slow"},
            "rsi": {"period": "rsi_period", "low": "rsi_low", "high": "rsi_high",
                    "rsi_period": "rsi_period", "rsi_low": "rsi_low", "rsi_high": "rsi_high"},
            "breakout": {"lookback": "breakout_lookback",
                         "breakout_lookback": "breakout_lookback"},
            "macd": {"fast": "macd_fast", "slow": "macd_slow", "signal": "macd_signal",
                     "macd_fast": "macd_fast", "macd_slow": "macd_slow",
                     "macd_signal": "macd_signal"},
            "bollinger": {"period": "boll_period", "k": "boll_k",
                          "boll_period": "boll_period", "boll_k": "boll_k"},
            "momentum": {"lookback": "momentum_lookback",
                         "momentum_lookback": "momentum_lookback"},
            "atr_trail": {"period": "atr_period", "mult": "atr_mult",
                          "atr_period": "atr_period", "atr_mult": "atr_mult"},
            "buy_hold": {},
        }
        # Note what is deliberately absent: `timeframe` selects the DATA, not
        # the indicator, so it is not in any alias table and can never reach
        # signals_for as a keyword.
        mapping = alias.get(template, {})
        return {mapping[k]: v for k, v in defn.items()
                if k in mapping and v is not None}

    @classmethod
    def _warmup_bars(cls, template: str, defn: dict) -> int:
        """Longest lookback the template reaches back through, plus margin.

        Computed from the TRANSLATED parameters. Reading the raw definition here
        would measure the wrong window — an RSI strategy storing ``period: 200``
        would be judged against a default of 30 and allowed to trade on a signal
        that never warmed up.
        """
        params = cls._params(template, defn)
        lookbacks = [v for k, v in params.items()
                     if k in ("fast", "slow", "rsi_period", "breakout_lookback",
                              "macd_fast", "macd_slow", "macd_signal",
                              "boll_period", "momentum_lookback", "atr_period")]
        longest = max([int(v) for v in lookbacks if v] or [30])
        return longest + WARMUP_MARGIN_BARS

    def _would_breach(self, symbol: str, action: str, qty: float,
                      price: float) -> list[str]:
        """What the risk gate would say, without writing anything.

        Returns an empty list when the gate cannot be consulted — an unknown
        verdict must not masquerade as a refusal, or a data blip would silently
        hide every proposable trade.
        """
        gate = getattr(self._pipeline, "risk_gate_for_preview", None)
        if gate is None:
            return []
        try:
            probe = Order(venue="preview", symbol=symbol,
                          side=Side.BUY if action == "buy" else Side.SELL, qty=qty)
            return list(gate().check(probe, price, self._nav.compute()).breaches or [])
        except Exception:  # noqa: BLE001
            return []

    def _safe_price(self, symbol: str) -> float | None:
        try:
            px = float(self._pricer(symbol))
        except Exception:  # noqa: BLE001 — an unpriced symbol is skipped, not guessed
            return None
        return px if px > 0 else None

    def _pending_keys(self) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        for o in self._pending() or []:
            if o.get("status") in ("pending", "approved", "working", "partial"):
                keys.add((o.get("strategy_id") or "", str(o.get("symbol") or "").upper()))
        return keys
