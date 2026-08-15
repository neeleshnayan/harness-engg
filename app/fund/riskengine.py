"""The composed risk view — one call, every layer, one honest verdict.

Assembles the measurement modules into the picture a risk manager actually
needs, and turns the parts that breach a limit into alarms of the same shape the
existing monitor already emits, so nothing downstream has to learn a new format.

Layers, in the order they answer questions:

  1. ``correlation``  — is this book actually diversified, or one bet in disguise
  2. ``risk_contribution`` — which position drives the risk (not the capital)
  3. ``tail``         — Expected Shortfall on the real return distribution
  4. ``vol_regime``   — is recent volatility above what the long window admits
  5. ``regime``       — is the *market* becoming fragile (turbulence, absorption)
  6. ``reverse_stress`` — what move would breach our halt
  7. ``historical``   — what real crises would have done to today's book

Every layer degrades independently: if market data for the regime read is
unavailable, that block reports ``measurable: false`` with a reason and the rest
of the view still renders. A risk screen that goes blank because one feed is
down is worse than useless, and a risk screen that shows zeros because one feed
is down is dangerous.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)

from app.fund import riskmetrics
from app.fund.correlation import CorrelationAnalytics, DEFAULT_LOOKBACK_DAYS, aligned_returns
from app.fund.factors import FactorModel, eigen_factor_map
from app.fund.regime import RegimeAnalytics
from app.fund.risk import RiskLimits
from app.fund.riskmonitor import Alarm
from app.fund.stress import StressTester


#: A full view fetches a year of history per holding and replays five dated
#: crisis windows across every symbol — dozens of market-data calls. Recomputing
#: that on every page load is wasteful and rude to the data source, and the
#: inputs are daily bars that do not change intraday.
VIEW_TTL_SECONDS = 1800.0


class AdvancedRiskEngine:
    def __init__(self, nav_service, pricer: Callable[[str], float],
                 attribution: Any | None = None, strategies: Any | None = None):
        self._nav = nav_service
        self._price = pricer
        self._attr = attribution
        self._strategies = strategies
        self._corr = CorrelationAnalytics(nav_service)
        self._regime = RegimeAnalytics()
        self._stress = StressTester(nav_service)
        self._factors = FactorModel()
        self._view_cache: dict[tuple, tuple[float, str, dict[str, Any]]] = {}

    # --- caching ------------------------------------------------------------
    def _fingerprint(self) -> str:
        """What the book *is*, so a cached view cannot outlive its subject.

        A pure time-to-live would keep serving the pre-trade risk picture for
        half an hour after a rebalance fills — precisely when someone is most
        likely to open the page and precisely when being wrong matters most.
        Keying on the positions too means a fill invalidates the cache
        immediately, while an idle refresh still costs nothing.
        """
        try:
            snap = self._nav.compute()
            parts = sorted(
                f"{str(p['symbol']).upper()}:{float(p['usd_value']):.2f}"
                for p in snap.positions
            )
            return f"{float(snap.total_nav_usd):.2f}|" + ",".join(parts)
        except Exception:  # noqa: BLE001 — an unreadable book must miss, not crash
            return f"unreadable:{time.monotonic()}"

    def invalidate(self) -> None:
        self._view_cache.clear()

    # --- the whole picture --------------------------------------------------
    def view(self, lookback_days: int = DEFAULT_LOOKBACK_DAYS,
             limits: RiskLimits | None = None,
             peak_nav: float | None = None,
             include_regime: bool = True,
             include_historical: bool = True,
             force: bool = False) -> dict[str, Any]:
        lim = limits or RiskLimits()

        key = (int(lookback_days), bool(include_regime), bool(include_historical))
        fp = self._fingerprint()
        hit = self._view_cache.get(key)
        if not force and hit is not None:
            ts, cached_fp, cached = hit
            age = time.monotonic() - ts
            if cached_fp == fp and age < VIEW_TTL_SECONDS:
                # Never present cached numbers as live — the UI states the age.
                return {**cached, "cached": True, "cache_age_seconds": round(age, 1)}

        attr_rows, names = self._attribution()
        corr = self._corr.analyse(lookback_days=lookback_days,
                                  attribution_rows=attr_rows,
                                  strategy_names=names,
                                  pricer=self._price)

        out: dict[str, Any] = {"correlation": _strip_private(corr)}
        nav_usd = corr.get("nav_usd") or float(self._nav.compute().total_nav_usd)

        if corr.get("measurable"):
            rets = corr.get("_returns") or {}
            symbols = corr["symbols"]
            weights = np.array([corr["weights"][s] / 100.0 for s in symbols], dtype=float)
            mat = np.array([rets[s] for s in symbols], dtype=float).T

            out["risk_contribution"] = riskmetrics.risk_contributions(
                symbols, weights, riskmetrics.ewma_covariance(mat)
            )
            out["vol_regime"] = riskmetrics.vol_regime(mat, weights)
            out["tail"] = riskmetrics.historical_tail(
                corr.get("portfolio_returns") or [], nav_usd=nav_usd
            )
            out["portfolio_turbulence"] = self._regime.portfolio_turbulence(rets, symbols)
            out["loss_surface"] = riskmetrics.loss_surface(
                symbols, weights, mat, corr.get("portfolio_returns") or [], nav_usd
            )
            out["factor_map"] = eigen_factor_map(
                symbols, rets, {s: corr["weights"][s] for s in symbols}
            )
            try:
                out["factor_model"] = self._factors.analyse(
                    corr.get("portfolio_returns") or [], corr.get("_dates") or []
                )
            except Exception as e:  # noqa: BLE001 — a data gap must not blank the page
                out["factor_model"] = {"measurable": False,
                                       "reason": f"factor data unavailable ({type(e).__name__})"}
        else:
            for k in ("risk_contribution", "vol_regime", "tail", "portfolio_turbulence",
                      "loss_surface", "factor_map", "factor_model"):
                out[k] = {"measurable": False,
                          "reason": corr.get("reason", "no measurable book")}

        if include_regime:
            try:
                out["regime"] = self._regime.market()
            except Exception as e:  # noqa: BLE001 — a data outage must not blank the page
                out["regime"] = {"measurable": False,
                                 "reason": f"market regime data unavailable ({type(e).__name__})"}
        if include_historical:
            try:
                out["historical"] = self._stress.replay()
            except Exception as e:  # noqa: BLE001
                out["historical"] = {"measurable": False,
                                     "reason": f"historical replay unavailable ({type(e).__name__})"}

        try:
            out["reverse_stress"] = self._stress.reverse(
                drawdown_limit_pct=lim.max_drawdown_pct,
                peak_nav=float(peak_nav or nav_usd),
                daily_loss_limit_pct=lim.max_daily_loss_pct,
            )
        except Exception as e:  # noqa: BLE001
            out["reverse_stress"] = {"measurable": False,
                                     "reason": f"reverse stress unavailable ({type(e).__name__})"}

        out["nav_usd"] = round(float(nav_usd), 2)
        out["limits"] = lim.to_dict()
        out["alarms"] = [a.to_dict() for a in self.structural_alarms(out, lim)]
        out["headlines"] = self._headlines(out)
        out["computed_at"] = datetime.now(timezone.utc).isoformat()
        out["ttl_seconds"] = VIEW_TTL_SECONDS
        out["cached"] = False
        out["cache_age_seconds"] = 0.0
        self._view_cache[key] = (time.monotonic(), fp, out)

        # One compact point per fresh compute, so the page can show risk
        # DRIFTING instead of only where it stands. Deduped inside the sink;
        # failure costs a chart point, never the compute.
        if corr.get("measurable"):
            try:
                from app.fund.riskhistory import RiskHistory

                es = (out.get("tail", {}).get("levels") or {}).get("0.975") or {}
                rs = out.get("reverse_stress") or {}
                RiskHistory().append({
                    "nav_usd": out["nav_usd"],
                    "portfolio_vol_pct": corr.get("portfolio_vol_pct"),
                    "stressed_vol_pct": corr.get("stressed_vol_pct"),
                    "effective_bets": corr.get("effective_bets"),
                    "es975_pct": es.get("expected_shortfall_pct"),
                    "es975_usd": es.get("expected_shortfall_usd"),
                    "move_to_halt_pct": rs.get("uniform_move_to_halt_pct"),
                }, fingerprint=fp)
            except Exception as e:  # noqa: BLE001
                logger.warning("risk history point not stored: %s", e)
        return out

    # --- what-if ------------------------------------------------------------
    def what_if(self, strategy_targets_pct: dict[str, float],
                lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict[str, Any]:
        """Risk mechanics of a PROPOSED allocation, next to the current one.

        The operator moves strategy targets; this answers what that does to the
        things a weight slider cannot show — effective bets, book volatility,
        Expected Shortfall and the distance to the halt.

        Symbol weights are derived by scaling each strategy's *current* internal
        composition to its new target. That is an assumption and it is stated:
        it presumes a rebalance changes strategy size, not strategy content. A
        strategy holding nothing yet has no composition to scale, so it cannot
        be sized here and is reported in ``unallocatable`` rather than being
        given an invented one.
        """
        attr_rows, names = self._attribution()

        # An empty book is a legitimate starting point, not an error: the FIRST
        # rebalance of a freshly funded fund has nothing to attribute, and
        # refusing to measure it would leave the operator flying blind on the
        # one decision that creates the portfolio. "Before" is simply nothing.
        comp: dict[str, dict[str, float]] = {}
        for row in (attr_rows or []):
            sid, vals = row.get("strategy_id"), {}
            for sym, qty in (row.get("positions") or {}).items():
                try:
                    q, px = float(qty), float(self._price(str(sym).upper()))
                except (TypeError, ValueError):
                    continue
                if abs(q) > 1e-9 and px > 0:
                    vals[str(sym).upper()] = q * px
            if sid and vals:
                comp[sid] = vals

        # Match RebalanceService.build(): a strategy that has never traded still
        # has a declared universe. Without this the mechanics panel reports "no
        # change" for a plan that visibly buys something, which is worse than
        # reporting nothing — it is a confident wrong answer.
        assumed: list[str] = []
        for sid, tgt in strategy_targets_pct.items():
            if not tgt or sid in comp:
                continue
            priced: dict[str, float] = {}
            for sym in self._declared_assets(sid):
                try:
                    px = float(self._price(sym))
                except (TypeError, ValueError):
                    continue
                if px > 0:
                    priced[sym] = 1.0        # equal weight, scaled to target below
            if priced:
                comp[sid] = priced
                assumed.append(sid)

        unallocatable = [sid for sid, tgt in strategy_targets_pct.items()
                         if tgt and sid not in comp]

        nav = float(self._nav.compute().total_nav_usd)
        proposed: dict[str, float] = {}
        for sid, target_pct in strategy_targets_pct.items():
            book = comp.get(sid)
            if not book:
                continue
            total = sum(book.values())
            if total <= 0:
                continue
            target_usd = nav * (float(target_pct) / 100.0)
            for sym, usd in book.items():
                proposed[sym] = proposed.get(sym, 0.0) + target_usd * (usd / total)

        if not proposed:
            return {"measurable": False,
                    "reason": "proposed allocation has no priced exposure to measure",
                    "unallocatable": unallocatable}

        # Return history must cover the UNION of what we hold and what we would
        # hold. Using only the current book's series silently drops every new
        # name from the comparison, so a plan that visibly buys something would
        # report "no change" — a confident wrong answer, which is worse than an
        # unmeasurable one. Both sides are then measured on the SAME aligned
        # window, or the before/after difference is an artefact of the window.
        current_usd: dict[str, float] = {}
        for p in self._nav.compute().positions:
            v = float(p["usd_value"])
            if abs(v) > 1e-9:
                current_usd[str(p["symbol"]).upper()] = v

        union = sorted(set(proposed) | set(current_usd))
        used, rets, _dates, excluded = aligned_returns(union, lookback_days=lookback_days)
        have = set(used)

        symbols = [s for s in sorted(proposed) if s in have]
        dropped = [s for s in proposed if s not in have]
        cur_syms = [s for s in sorted(current_usd) if s in have]
        if not symbols:
            return {"measurable": False,
                    "reason": "no price history for any proposed holding",
                    "unallocatable": unallocatable, "excluded": excluded}

        gross = sum(abs(proposed[s]) for s in symbols)
        # Fractions of NAV, so cash dilutes risk (see _shape).
        denom = nav if nav > 0 else gross
        w = np.array([proposed[s] / denom for s in symbols], dtype=float)
        mat = np.array([rets[s] for s in symbols], dtype=float).T
        after = _shape(symbols, w, mat, nav)

        if cur_syms:
            cur_w = np.array([current_usd[s] / denom for s in cur_syms], dtype=float)
            cur_mat = np.array([rets[s] for s in cur_syms], dtype=float).T
            before = _shape(cur_syms, cur_w, cur_mat, nav)
        else:
            # A book holding nothing has zero volatility and zero shortfall, and
            # those ARE the measurements — not unknowns. Effective bets is left
            # null because "how independent are no positions" has no answer.
            before = {
                "symbols": [], "weights_pct_of_nav": {},
                "gross_exposure_pct_of_nav": 0.0,
                "effective_bets": None,
                "portfolio_vol_pct": 0.0, "stressed_vol_pct": 0.0,
                "expected_shortfall_usd": 0.0, "expected_shortfall_pct": 0.0,
                "largest_risk_contributor": None, "contributions": [],
            }

        return {
            "measurable": True,
            "nav_usd": round(nav, 2),
            "before": before,
            "after": after,
            "deltas": {k: round(after[k] - before[k], 4)
                       for k in ("effective_bets", "portfolio_vol_pct",
                                 "stressed_vol_pct", "expected_shortfall_usd")
                       if before.get(k) is not None and after.get(k) is not None},
            "proposed_exposure_usd": {s: round(proposed[s], 2) for s in symbols},
            "proposed_cash_usd": round(nav - gross, 2),
            "proposed_cash_pct": round((nav - gross) / nav * 100.0, 2) if nav > 0 else None,
            "symbols_without_history": dropped,
            "unallocatable": unallocatable,
            "equal_weighted_strategies": assumed,
            "assumption": (
                "each strategy keeps its current internal composition and is only "
                "resized; measured over the same window as the live book"
                + (f"; {len(assumed)} strategy with no holdings yet is assumed "
                   "equal-weight across its declared universe" if assumed else "")
            ),
        }

    # --- candidate fit ------------------------------------------------------
    def candidate_fit(self, candidate_returns: list[float], candidate_dates: list[str],
                      allocation_pct: float = 10.0,
                      lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict[str, Any]:
        """Would adding this strategy make the FUND better?

        A backtest answers "is this good on its own", which is the wrong question
        and the one every strategy tester answers. A strategy with a lower
        standalone Sharpe but low correlation to what you already hold can
        improve the portfolio more than a better one that duplicates it. That is
        the whole argument for running more than one strategy, and nothing in
        the platform measured it until now.

        Returns the book with and without the candidate at ``allocation_pct``,
        plus its correlation to each strategy already deployed.
        """
        attr_rows, names = self._attribution()
        corr = self._corr.analyse(lookback_days=lookback_days,
                                  attribution_rows=attr_rows,
                                  strategy_names=names, pricer=self._price)
        if not corr.get("measurable"):
            return {"measurable": False,
                    "reason": f"cannot measure the current book: {corr.get('reason')}"}

        book_rets = corr.get("portfolio_returns") or []
        book_dates = corr.get("_dates") or []
        if len(book_rets) < 40 or len(book_dates) != len(book_rets):
            return {"measurable": False,
                    "reason": "the current book has too little aligned history to "
                              "compare a candidate against"}

        idx = {d: i for i, d in enumerate(book_dates)}
        pairs = [(i, idx[d]) for i, d in enumerate(candidate_dates or [])
                 if d in idx and i < len(candidate_returns)]
        if len(pairs) < 40:
            return {"measurable": False,
                    "reason": f"only {len(pairs)} dates overlap between the candidate "
                              "and the current book — they cannot be compared"}

        cand = np.array([float(candidate_returns[i]) for i, _ in pairs])
        book = np.array([float(book_rets[j]) for _, j in pairs])
        w = max(0.0, min(float(allocation_pct) / 100.0, 1.0))
        blended = (1.0 - w) * book + w * cand

        nav = float(corr.get("nav_usd") or 0.0)

        def shape(series: np.ndarray) -> dict[str, Any]:
            vol = float(series.std(ddof=1)) * (riskmetrics.TRADING_DAYS ** 0.5)
            tail = riskmetrics.historical_tail(series.tolist(), nav_usd=nav)
            es = None
            if tail.get("measurable"):
                lvl = tail["levels"].get(f"{riskmetrics.FRTB_ES_LEVEL:.3f}")
                es = lvl.get("expected_shortfall_usd") if lvl else None
            mean = float(series.mean())
            sd = float(series.std(ddof=1))
            return {
                "vol_pct": round(vol * 100.0, 2),
                "expected_shortfall_usd": es,
                "sharpe_annual": round((mean / sd) * (riskmetrics.TRADING_DAYS ** 0.5), 3)
                if sd > 0 else None,
            }

        before, after = shape(book), shape(blended)
        rho = float(np.corrcoef(cand, book)[0, 1]) if cand.std() > 0 and book.std() > 0 else 0.0

        # Correlation to each strategy already deployed — the specific question
        # "which of my existing strategies is this a duplicate of".
        per_strategy: list[dict[str, Any]] = []
        rets = corr.get("_returns") or {}
        for row in (attr_rows or []):
            sid = row.get("strategy_id")
            vals: dict[str, float] = {}
            for sym, qty in (row.get("positions") or {}).items():
                s = str(sym).upper()
                if s not in rets:
                    continue
                try:
                    q, px = float(qty), float(self._price(s))
                except (TypeError, ValueError):
                    continue
                if abs(q) > 1e-9 and px > 0:
                    vals[s] = q * px
            tot = sum(vals.values())
            if tot <= 0:
                continue
            wts = {s: v / tot for s, v in vals.items()}
            series = np.array([
                sum(wts[s] * rets[s][j] for s in wts) for _, j in pairs
            ])
            if series.std() <= 0:
                continue
            per_strategy.append({
                "strategy_id": sid,
                "name": names.get(sid, sid),
                "correlation": round(float(np.corrcoef(cand, series)[0, 1]), 4),
            })
        per_strategy.sort(key=lambda r: r["correlation"], reverse=True)

        sharpe_up = (after["sharpe_annual"] or 0) > (before["sharpe_annual"] or 0)
        vol_down = after["vol_pct"] < before["vol_pct"]
        # Raising Sharpe by ADDING risk is a different act from raising it by
        # diversifying, and conflating them is how a book quietly levers up while
        # every dashboard reports an improvement. Name which one this is.
        kind = ("diversifying" if sharpe_up and vol_down
                else "return-seeking" if sharpe_up
                else "risk-reducing" if vol_down
                else "neither")
        improves = sharpe_up or vol_down

        verdict: list[str] = [
            f"At {w:.0%} the book's volatility goes {before['vol_pct']:.1f}% → "
            f"{after['vol_pct']:.1f}% and its Sharpe "
            f"{before['sharpe_annual']} → {after['sharpe_annual']}."
        ]
        if kind == "return-seeking":
            verdict.append(
                "It raises risk-adjusted return by taking MORE risk, not by "
                "diversifying — the book gets more volatile. That can be the right "
                "trade, but it is a leverage decision, not a free improvement."
            )
        elif kind == "diversifying":
            verdict.append(
                "It raises Sharpe while LOWERING volatility — the rare case where "
                "the addition is genuinely diversifying rather than levering."
            )
        elif kind == "risk-reducing":
            verdict.append(
                "It lowers volatility at the cost of risk-adjusted return — a "
                "de-risking trade, not an alpha one."
            )
        else:
            verdict.append(
                "It raises volatility without raising risk-adjusted return. On this "
                "window it made the book strictly worse."
            )
        verdict.append(
            f"The candidate correlates {rho:+.2f} with the book as it stands"
            + (" — close to a duplicate of what you already own."
               if rho > 0.8 else
               " — genuinely different from what you already own."
               if rho < 0.3 else ".")
        )
        if per_strategy and per_strategy[0]["correlation"] > 0.8:
            verdict.append(
                f"It is {per_strategy[0]['correlation']:.2f} correlated with "
                f"'{per_strategy[0]['name']}' — adding both is close to sizing that "
                "one strategy twice."
            )
        verdict.append(
            "Measured on overlapping history at fixed weights; it assumes the "
            "candidate behaves in future as it did in this window, which is the "
            "assumption every backtest makes and none can justify."
        )

        return {
            "measurable": True,
            "n_obs": len(pairs),
            "allocation_pct": round(w * 100.0, 2),
            "correlation_to_book": round(rho, 4),
            "per_strategy": per_strategy,
            "before": before,
            "after": after,
            "improves_book": bool(improves),
            "effect": kind,
            "verdict": verdict,
        }

    def _declared_assets(self, sid: str) -> list[str]:
        """The universe a strategy scopes, whether or not it has traded it."""
        if self._strategies is None:
            return []
        try:
            for st in self._strategies.list():
                if st.get("strategy_id") == sid:
                    return [str(a).upper() for a in (st.get("assets") or [])]
        except Exception:  # noqa: BLE001
            pass
        return []

    # --- alarms -------------------------------------------------------------
    def structural_alarms(self, view: dict[str, Any], limits: RiskLimits) -> list[Alarm]:
        """Breaches of the structural limits — the ones a position list cannot see.

        Keys are namespaced so they dedup against the existing alarm ledger
        without colliding with concentration/drawdown keys.
        """
        alarms: list[Alarm] = []
        corr = view.get("correlation") or {}

        if corr.get("measurable"):
            eff = corr.get("effective_bets")
            if eff is not None and eff < limits.min_effective_bets:
                alarms.append(Alarm(
                    key="crowding", type="crowding", severity="warn",
                    message=(f"{corr['n_positions']} positions behave like only {eff:.1f} "
                             f"independent bets (floor {limits.min_effective_bets:.1f}) — "
                             "per-name limits will not contain a common shock"),
                    metric=float(eff), threshold=limits.min_effective_bets,
                ))
            avg = corr.get("avg_pairwise_correlation")
            if avg is not None and avg > limits.max_avg_correlation:
                alarms.append(Alarm(
                    key="correlation", type="correlation", severity="warn",
                    message=(f"average pairwise correlation {avg:.2f} exceeds "
                             f"{limits.max_avg_correlation:.2f} — the book moves as one"),
                    metric=float(avg), threshold=limits.max_avg_correlation,
                ))
            overlap = (corr.get("strategy_overlap") or {})
            for pair in (overlap.get("pairs") or []):
                rc = pair.get("return_correlation")
                if rc is not None and rc > limits.max_strategy_correlation:
                    alarms.append(Alarm(
                        key=f"strategy_overlap:{pair['a']}:{pair['b']}",
                        type="strategy_overlap", severity="warn",
                        message=(f"'{pair['a_name']}' and '{pair['b_name']}' have return "
                                 f"correlation {rc:.2f} — they are one strategy held twice, "
                                 "so their separate allocations are not separate risk"),
                        metric=float(rc), threshold=limits.max_strategy_correlation,
                        strategy_id=pair["a"],
                    ))

        rc_block = view.get("risk_contribution") or {}
        if rc_block.get("measurable"):
            top = rc_block.get("largest_risk_contributor") or {}
            share = (top.get("risk_share_pct") or 0.0) / 100.0
            if share > limits.max_risk_concentration_pct:
                alarms.append(Alarm(
                    key=f"risk_concentration:{top.get('symbol')}",
                    type="risk_concentration", severity="warn",
                    message=(f"{top.get('symbol')} is {top.get('capital_weight_pct'):.0f}% of "
                             f"capital but {top.get('risk_share_pct'):.0f}% of book risk "
                             f"(limit {limits.max_risk_concentration_pct:.0%})"),
                    metric=float(share), threshold=limits.max_risk_concentration_pct,
                    symbol=top.get("symbol"),
                ))

        tail = view.get("tail") or {}
        if tail.get("measurable"):
            lvl = tail["levels"].get(f"{riskmetrics.FRTB_ES_LEVEL:.3f}")
            if lvl:
                es = lvl["expected_shortfall_pct"] / 100.0
                if es > limits.max_expected_shortfall_pct:
                    alarms.append(Alarm(
                        key="expected_shortfall", type="expected_shortfall", severity="warn",
                        message=(f"97.5% one-day Expected Shortfall is {es:.2%} of NAV "
                                 f"(limit {limits.max_expected_shortfall_pct:.2%})"
                                 + (f" — about ${abs(lvl.get('expected_shortfall_usd', 0)):,.0f}"
                                    if lvl.get("expected_shortfall_usd") else "")),
                        metric=float(es), threshold=limits.max_expected_shortfall_pct,
                    ))

        # Survivability. Every other alarm asks "are we inside our limits today";
        # this one asks "would a crisis we have actually lived through take us
        # past the kill switch". A book can sit comfortably inside every limit
        # and still be unable to survive a repeat of 2022 — and nothing else
        # here would say so.
        hist = view.get("historical") or {}
        if hist.get("measurable") and hist.get("worst_scenario"):
            w = hist["worst_scenario"]
            loss = -(w.get("nav_change_pct") or 0.0) / 100.0
            if loss > limits.max_drawdown_pct:
                alarms.append(Alarm(
                    key=f"historical_survivability:{w['key']}",
                    type="historical_survivability",
                    severity="critical" if loss > limits.max_drawdown_pct * 2 else "warn",
                    message=(f"a repeat of {w['label']} would cost this book "
                             f"{loss:.1%} of NAV (${abs(w['pnl_usd']):,.0f}) against a "
                             f"{limits.max_drawdown_pct:.0%} drawdown halt — the fund would "
                             "be halted and the loss taken, not avoided"),
                    metric=float(loss), threshold=limits.max_drawdown_pct,
                ))

        regime = view.get("regime") or {}
        if regime.get("measurable"):
            ab, turb = regime.get("absorption") or {}, regime.get("turbulence") or {}
            if ab.get("measurable") and ab.get("flagged"):
                alarms.append(Alarm(
                    key="market_fragility", type="market_fragility", severity="warn",
                    message=(f"market absorption ratio has risen "
                             f"{ab['standardised_shift']:+.2f} sigma — sectors are unusually "
                             "tightly coupled, which historically precedes drawdowns "
                             "(necessary, not sufficient)"),
                    metric=float(ab["standardised_shift"]), threshold=ab.get("threshold", 1.0),
                ))
            if turb.get("measurable") and turb.get("elevated"):
                alarms.append(Alarm(
                    key="market_turbulence", type="market_turbulence", severity="info",
                    message=(f"market turbulence at the {turb['percentile']:.0f}th percentile — "
                             "returns to risk-taking are historically poor while elevated"),
                    metric=float(turb["percentile"]), threshold=80.0,
                ))
        return alarms

    # --- helpers ------------------------------------------------------------
    def _attribution(self) -> tuple[list[dict] | None, dict[str, str]]:
        if self._attr is None:
            return None, {}
        try:
            rows = self._attr.with_values(self._price)
        except Exception:  # noqa: BLE001
            return None, {}
        names: dict[str, str] = {}
        if self._strategies is not None:
            try:
                for s in self._strategies.list():
                    names[s["strategy_id"]] = s.get("name", s["strategy_id"])
            except Exception:  # noqa: BLE001
                pass
        names.setdefault("discretionary", "Discretionary")
        return rows, names

    @staticmethod
    def _headlines(view: dict[str, Any]) -> list[str]:
        """Three or four sentences an operator can read in ten seconds."""
        out: list[str] = []
        corr = view.get("correlation") or {}
        if corr.get("measurable"):
            out.append(
                f"{corr['n_positions']} positions = {corr['effective_bets']:.1f} effective bets; "
                f"book vol {corr['portfolio_vol_pct']:.1f}%, "
                f"{corr['stressed_vol_pct']:.1f}% if correlations go to 1."
            )
        rc = view.get("risk_contribution") or {}
        if rc.get("measurable") and rc.get("largest_risk_contributor"):
            t = rc["largest_risk_contributor"]
            out.append(
                f"{t['symbol']} carries {t['risk_share_pct']:.0f}% of book risk on "
                f"{t['capital_weight_pct']:.0f}% of capital."
            )
        tail = view.get("tail") or {}
        if tail.get("measurable"):
            out.append(tail["headline"] + ".")
        rev = view.get("reverse_stress") or {}
        if rev.get("measurable") and rev.get("headline"):
            out.append(rev["headline"].capitalize() + ".")
        hist = view.get("historical") or {}
        if hist.get("measurable") and hist.get("worst_scenario"):
            w = hist["worst_scenario"]
            out.append(
                f"Worst replayed crisis for this exact book: {w['label']} "
                f"({w['nav_change_pct']:+.1f}% NAV, ${w['pnl_usd']:,.0f})."
            )
        return out


def _shape(symbols: list[str], weights, mat, nav_usd: float) -> dict[str, Any]:
    """The numbers that describe a book's risk, for before/after comparison.

    ``weights`` MUST be fractions of NAV, not of gross exposure. Normalising to
    gross would make a de-risked book — half in cash — report exactly the same
    volatility and Expected Shortfall as a fully invested one, because it would
    be measuring the shape of the deployed sleeve rather than the risk of the
    fund. Cash has to be able to dilute risk or the whole rebalance lens lies.

    Effective bets is deliberately unaffected by this: it is a shape property
    (a ratio of two volatilities), so holding more cash does not make the
    remaining positions any more independent of each other. That is correct,
    and worth not "fixing".

    Same estimator on both sides, or the comparison is meaningless.
    """
    cov = riskmetrics.sample_covariance(mat)
    vol = riskmetrics.portfolio_vol(weights, cov)
    sd = mat.std(axis=0, ddof=1)
    stressed = float((weights * sd).sum()) * (riskmetrics.TRADING_DAYS ** 0.5)
    dr = (stressed / vol) if vol > 1e-12 else 1.0

    port = (mat @ weights).tolist()
    tail = riskmetrics.historical_tail(port, nav_usd=nav_usd)
    es_usd = es_pct = None
    if tail.get("measurable"):
        lvl = tail["levels"].get(f"{riskmetrics.FRTB_ES_LEVEL:.3f}")
        if lvl:
            es_usd, es_pct = lvl.get("expected_shortfall_usd"), lvl.get("expected_shortfall_pct")

    contrib = riskmetrics.risk_contributions(symbols, weights, cov)
    return {
        "symbols": symbols,
        "weights_pct_of_nav": {s: round(float(weights[i]) * 100.0, 2)
                               for i, s in enumerate(symbols)},
        "gross_exposure_pct_of_nav": round(float(abs(weights).sum()) * 100.0, 2),
        "effective_bets": round(dr ** 2, 2),
        "portfolio_vol_pct": round(vol * 100.0, 2),
        "stressed_vol_pct": round(stressed * 100.0, 2),
        "expected_shortfall_usd": es_usd,
        "expected_shortfall_pct": es_pct,
        "largest_risk_contributor": contrib.get("largest_risk_contributor"),
        "contributions": contrib.get("contributions"),
    }


def _strip_private(d: dict[str, Any]) -> dict[str, Any]:
    """Drop the raw return series before serialising — it is an internal handoff
    between layers, not part of the API surface, and it is large."""
    return {k: v for k, v in d.items() if not k.startswith("_")}
