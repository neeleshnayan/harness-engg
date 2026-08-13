"""Correlation, crowding and true diversification.

The most expensive lie a small fund tells itself is "I hold four names across
three strategies, so I am diversified". If those four names move together, that
is one bet wearing four hats — and the number of *positions* says nothing about
the number of *bets*.

This module measures it instead of assuming it. Everything comes from realised
daily returns of the symbols actually held, fetched from the same market data
source the rest of the spine uses. Nothing is hardcoded and nothing is proxied:
if a symbol has no usable history it is reported as excluded, and the metrics
say how much of the book they could not see.

Two properties get computed that a position list cannot show you:

  * **Effective bets** — how many genuinely independent positions the book holds.
    A four-name book of perfectly correlated names has one effective bet.
  * **Stress correlation** — what the book's volatility becomes if correlations
    go to 1, which is what they do in a crisis (the "phase-locking" that
    Chan/Getmansky/Haas/Lo document: diversification fails exactly when it is
    needed). The gap between normal and stressed vol is the diversification
    benefit you are counting on and would lose.

Read-only. This is a lens on the truth, never truth itself.
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Sequence

from app.fund.marketdata import BarsError, fetch_daily_bars

#: Below this many aligned observations, correlation estimates are noise.
MIN_OBS = 40

#: Default estimation window. Long enough to be stable, short enough that the
#: current regime dominates — a 5-year window would average away the thing we
#: are trying to see.
DEFAULT_LOOKBACK_DAYS = 250

TRADING_DAYS = 252


def _returns_from_closes(closes: Sequence[float]) -> list[float]:
    out: list[float] = []
    for prev, cur in zip(closes, closes[1:]):
        if prev and prev > 0:
            out.append(cur / prev - 1.0)
        else:
            out.append(0.0)
    return out


#: Daily bars change once a day, but several risk layers want the same series
#: within one request. Without this, one risk page load refetches every symbol
#: three or four times — which on a metered feed is both slow and expensive.
_BARS_TTL_SECONDS = 900.0
_bars_cache: dict[tuple, tuple[float, Any]] = {}


def clear_bars_cache() -> None:
    _bars_cache.clear()


def aligned_returns(
    symbols: Sequence[str],
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    fetcher: Callable[..., Any] = fetch_daily_bars,
) -> tuple[list[str], dict[str, list[float]], list[str], dict[str, str]]:
    """Daily returns for ``symbols`` on a COMMON set of dates.

    Correlation across series with different date coverage is meaningless, so
    we intersect the dates first and report what got dropped.

    Returns ``(symbols_used, returns_by_symbol, dates_used, excluded_reasons)``.
    """
    key = (tuple(sorted({(s or "").upper() for s in symbols if s})), int(lookback_days),
           getattr(fetcher, "__name__", repr(fetcher)))
    hit = _bars_cache.get(key)
    if hit is not None and (time.monotonic() - hit[0]) < _BARS_TTL_SECONDS:
        return hit[1]

    closes_by_date: dict[str, dict[str, float]] = {}
    excluded: dict[str, str] = {}

    for sym in symbols:
        s = (sym or "").upper()
        if not s:
            continue
        try:
            bars = fetcher(s, lookback_days=lookback_days)
        except (BarsError, Exception) as e:  # noqa: BLE001 — a data gap is a finding
            excluded[s] = f"no price history ({type(e).__name__})"
            continue
        if not bars or not bars.closes or not bars.dates:
            excluded[s] = "no price history returned"
            continue
        closes_by_date[s] = {d: c for d, c in zip(bars.dates, bars.closes)}

    if not closes_by_date:
        result = ([], {}, [], excluded)
        _bars_cache[key] = (time.monotonic(), result)
        return result

    common: set[str] | None = None
    for sym, series in closes_by_date.items():
        ds = set(series.keys())
        common = ds if common is None else (common & ds)
    dates = sorted(common or set())

    if len(dates) < MIN_OBS + 1:
        for s in list(closes_by_date):
            excluded.setdefault(
                s, f"only {len(dates)} overlapping trading days (need {MIN_OBS + 1})"
            )
        result = ([], {}, dates, excluded)
        _bars_cache[key] = (time.monotonic(), result)
        return result

    used = sorted(closes_by_date.keys())
    rets = {s: _returns_from_closes([closes_by_date[s][d] for d in dates]) for s in used}
    result = (used, rets, dates[1:], excluded)
    _bars_cache[key] = (time.monotonic(), result)
    return result


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def _corr(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a, b = a[:n], b[:n]
    ma, mb = _mean(a), _mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da <= 0 or db <= 0:
        return 0.0
    return max(-1.0, min(1.0, num / (da * db)))


def portfolio_returns(weights: dict[str, float], rets: dict[str, list[float]]) -> list[float]:
    """The book's own daily return series, at CURRENT weights.

    This is a counterfactual — it asks what today's portfolio *would have done*
    over the window, not what it did earn. That is the right question for
    forward-looking risk and the wrong one for performance; never present it
    as a track record.
    """
    syms = [s for s in weights if s in rets and rets[s]]
    if not syms:
        return []
    n = min(len(rets[s]) for s in syms)
    return [sum(weights[s] * rets[s][t] for s in syms) for t in range(n)]


class CorrelationAnalytics:
    """Crowding and diversification over the live book."""

    def __init__(self, nav_service, fetcher: Callable[..., Any] = fetch_daily_bars):
        self._nav = nav_service
        self._fetch = fetcher

    # --- core ---------------------------------------------------------------
    def analyse(self, lookback_days: int = DEFAULT_LOOKBACK_DAYS,
                attribution_rows: list[dict] | None = None,
                strategy_names: dict[str, str] | None = None,
                pricer: Callable[[str], float] | None = None) -> dict[str, Any]:
        snap = self._nav.compute()
        nav_usd = float(snap.total_nav_usd)

        held: dict[str, float] = {}
        for p in snap.positions:
            v = float(p["usd_value"])
            if abs(v) > 1e-9:
                held[str(p["symbol"]).upper()] = v
        gross = sum(abs(v) for v in held.values())

        if not held:
            return {
                "measurable": False,
                "reason": "no open positions to correlate",
                "nav_usd": round(nav_usd, 2),
            }

        used, rets, dates, excluded = aligned_returns(
            list(held.keys()), lookback_days=lookback_days, fetcher=self._fetch
        )
        if not used:
            return {
                "measurable": False,
                "reason": "not enough overlapping price history to measure correlation",
                "excluded": excluded,
                "nav_usd": round(nav_usd, 2),
                "positions_covered_pct": 0.0,
            }

        covered = sum(abs(held[s]) for s in used)
        coverage_pct = (covered / gross * 100.0) if gross > 0 else 0.0

        # Weights are shares of the COVERED gross exposure, so they sum to 1 and
        # the vol maths is well-posed even when a symbol had to be excluded.
        weights = {s: held[s] / covered for s in used} if covered > 0 else {}

        n_obs = min(len(rets[s]) for s in used)
        vols = {s: _std(rets[s][:n_obs]) * math.sqrt(TRADING_DAYS) for s in used}

        matrix: list[list[float]] = []
        pairs: list[dict[str, Any]] = []
        for i, a in enumerate(used):
            row: list[float] = []
            for j, b in enumerate(used):
                c = 1.0 if i == j else _corr(rets[a][:n_obs], rets[b][:n_obs])
                row.append(round(c, 4))
                if j > i:
                    pairs.append({"a": a, "b": b, "correlation": round(c, 4)})
            matrix.append(row)

        # Portfolio vol from the covariance matrix: sqrt(w' S w).
        var = 0.0
        for i, a in enumerate(used):
            for j, b in enumerate(used):
                var += weights[a] * weights[b] * vols[a] * vols[b] * matrix[i][j]
        port_vol = math.sqrt(max(var, 0.0))

        # If every pair moved together, correlation terms all become 1 and the
        # portfolio vol collapses to the weighted average of the parts.
        stressed_vol = sum(weights[s] * vols[s] for s in used)

        diversification_ratio = (stressed_vol / port_vol) if port_vol > 1e-12 else 1.0
        effective_bets = diversification_ratio ** 2
        naive_bets = 1.0 / sum(w * w for w in weights.values()) if weights else 0.0

        avg_pair = _mean([p["correlation"] for p in pairs]) if pairs else 0.0
        max_pair = max(pairs, key=lambda p: p["correlation"]) if pairs else None

        port_rets = portfolio_returns(weights, {s: rets[s][:n_obs] for s in used})

        result: dict[str, Any] = {
            "measurable": True,
            "nav_usd": round(nav_usd, 2),
            "lookback_days": lookback_days,
            "n_obs": n_obs,
            "window_start": dates[0] if dates else None,
            "window_end": dates[-1] if dates else None,
            "symbols": used,
            "excluded": excluded,
            "positions_covered_pct": round(coverage_pct, 2),
            "weights": {s: round(weights[s] * 100.0, 2) for s in used},
            "annualised_vol_pct": {s: round(vols[s] * 100.0, 2) for s in used},
            "matrix": matrix,
            "pairs": sorted(pairs, key=lambda p: p["correlation"], reverse=True),
            "avg_pairwise_correlation": round(avg_pair, 4),
            "max_pair": max_pair,
            "portfolio_vol_pct": round(port_vol * 100.0, 2),
            "stressed_vol_pct": round(stressed_vol * 100.0, 2),
            "diversification_ratio": round(diversification_ratio, 3),
            "effective_bets": round(effective_bets, 2),
            "naive_bets": round(naive_bets, 2),
            "n_positions": len(used),
            "portfolio_returns": port_rets,
            "_returns": {s: rets[s][:n_obs] for s in used},
            "_dates": list(dates[:n_obs]),
        }
        result["interpretation"] = self._interpret(result)
        if attribution_rows is not None:
            result["strategy_overlap"] = self.strategy_overlap(
                attribution_rows, rets, n_obs, strategy_names or {}, pricer=pricer
            )
        return result

    # --- strategy overlap ---------------------------------------------------
    def strategy_overlap(self, attribution_rows: list[dict],
                         rets: dict[str, list[float]], n_obs: int,
                         names: dict[str, str],
                         pricer: Callable[[str], float] | None = None) -> dict[str, Any]:
        """Are the strategies actually different bets?

        Two measures, because they answer different questions:

          * ``shared_exposure_pct`` — how much of the two strategies' weight sits
            in the same names. Structural, easy to game by picking different
            tickers in the same sector.
          * ``return_correlation`` — the correlation of the two strategies'
            implied daily return series at current weights. This is the one that
            matters: two strategies holding *different* names that move together
            are still one bet, and only this number catches that.
        """
        # Attribution carries SHARE COUNTS. 100 shares of a $13 stock and 100 of
        # a $100 stock are not the same bet, so weights must be built from USD
        # value; without a pricer we cannot do that and say so rather than
        # silently treating share counts as weights.
        if pricer is None:
            return {"measurable": False,
                    "reason": "no pricer supplied; cannot convert share counts to USD weights"}

        vectors: dict[str, dict[str, float]] = {}
        for row in attribution_rows or []:
            sid = row.get("strategy_id")
            positions = row.get("positions") or {}
            if not sid:
                continue
            vals: dict[str, float] = {}
            for sym, qty in positions.items():
                s = str(sym).upper()
                if s not in rets:
                    continue
                try:
                    q = float(qty)
                    px = float(pricer(s))
                except (TypeError, ValueError):
                    continue
                if abs(q) > 1e-9 and px > 0:
                    vals[s] = q * px
            if vals:
                vectors[sid] = vals

        if len(vectors) < 2:
            return {
                "measurable": False,
                "reason": f"{len(vectors)} strategy with priced positions — "
                          "overlap needs at least two",
            }

        # Normalise each strategy to weights of its own exposure. We use share
        # counts scaled by the last price implied in the return series only if a
        # value is supplied; otherwise raw share weight is a poor proxy, so we
        # require the caller's attribution to carry per-symbol USD value.
        weights: dict[str, dict[str, float]] = {}
        for sid, vals in vectors.items():
            tot = sum(abs(v) for v in vals.values())
            if tot > 0:
                weights[sid] = {s: v / tot for s, v in vals.items()}

        series: dict[str, list[float]] = {
            sid: portfolio_returns(w, {s: rets[s][:n_obs] for s in w if s in rets})
            for sid, w in weights.items()
        }

        out: list[dict[str, Any]] = []
        sids = sorted(weights.keys())
        for i, a in enumerate(sids):
            for b in sids[i + 1:]:
                shared = sum(
                    min(weights[a].get(s, 0.0), weights[b].get(s, 0.0))
                    for s in set(weights[a]) | set(weights[b])
                )
                rc = _corr(series.get(a, []), series.get(b, [])) if series.get(a) and series.get(b) else None
                out.append({
                    "a": a,
                    "a_name": names.get(a, a),
                    "b": b,
                    "b_name": names.get(b, b),
                    "shared_exposure_pct": round(shared * 100.0, 2),
                    "shared_symbols": sorted(set(weights[a]) & set(weights[b])),
                    "return_correlation": round(rc, 4) if rc is not None else None,
                })

        out.sort(key=lambda r: (r["return_correlation"] if r["return_correlation"] is not None else -2),
                 reverse=True)
        worst = out[0] if out else None
        return {
            "measurable": True,
            "pairs": out,
            "worst_pair": worst,
            "note": "return correlation is the binding measure — different tickers "
                    "that move together are still one bet",
        }

    # --- narrative ----------------------------------------------------------
    @staticmethod
    def _interpret(r: dict[str, Any]) -> list[str]:
        """Plain sentences for the operator. Each one states what the number
        means and what it does NOT mean."""
        lines: list[str] = []
        eff, n = r["effective_bets"], r["n_positions"]
        lines.append(
            f"{n} positions behave like {eff:.1f} independent bets "
            f"(average pairwise correlation {r['avg_pairwise_correlation']:.2f})."
        )
        if eff < 2.0 and n >= 2:
            lines.append(
                "That is effectively a single directional bet. Position limits will "
                "not protect the book — every name can fall together."
            )
        gap = r["stressed_vol_pct"] - r["portfolio_vol_pct"]
        lines.append(
            f"Book volatility is {r['portfolio_vol_pct']:.1f}% annualised. If correlations "
            f"go to 1 — which is what they do in a sell-off — it becomes "
            f"{r['stressed_vol_pct']:.1f}%. The {gap:.1f} point difference is the "
            "diversification benefit being assumed, and it is the first thing a crisis removes."
        )
        if r["max_pair"] and r["max_pair"]["correlation"] > 0.7:
            mp = r["max_pair"]
            lines.append(
                f"{mp['a']} and {mp['b']} correlate {mp['correlation']:.2f} — "
                "holding both is close to holding twice as much of one."
            )
        if r["positions_covered_pct"] < 99.0:
            lines.append(
                f"Only {r['positions_covered_pct']:.0f}% of gross exposure could be measured; "
                f"excluded: {', '.join(r['excluded'].keys()) or 'none'}. "
                "The figures above describe the measured part only."
            )
        lines.append(
            f"Measured over {r['n_obs']} trading days ending {r['window_end']}. "
            "Correlation is backward-looking; a regime change invalidates it without warning."
        )
        return lines
