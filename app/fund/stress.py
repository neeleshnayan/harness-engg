"""Stress testing: what actually happened, and what would actually break us.

Two kinds of test, and the second is the one people skip.

**Historical replay.** Take a real crisis window and apply the *actual* daily
returns of the names we hold today to today's weights. No betas, no proxies, no
assumed sensitivities — if we held these names through March 2020, this is the
arithmetic of what would have happened. Where a name did not exist yet, it is
excluded and reported, never back-filled with a guess.

**Reverse stress.** Conventional stress testing asks "what if the market falls
20%?" and produces a number nobody acts on. Reverse stress testing inverts it:
*what move would it take to breach our halt?* That yields a threshold the
operator can hold in their head and check against the tape. Regulators have been
pushing this direction for a decade for the same reason — the useful question is
what breaks you, not what a round number does to you.

Everything is computed at current weights over live positions.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from app.fund.marketdata import BarsError, fetch_daily_bars

#: Real, dated crisis windows. Replayed with real returns — these are date
#: ranges, not scenarios anyone invented.
HISTORICAL_SCENARIOS: tuple[dict[str, str], ...] = (
    {"key": "covid_2020", "label": "COVID crash",
     "start": "2020-02-19", "end": "2020-03-23",
     "note": "fastest 30%+ drawdown in S&P history"},
    {"key": "q4_2018", "label": "Q4 2018 selloff",
     "start": "2018-10-01", "end": "2018-12-24",
     "note": "rate-hike and growth scare"},
    {"key": "bear_2022", "label": "2022 rate shock",
     "start": "2022-01-03", "end": "2022-10-12",
     "note": "inflation and a repricing of duration; a slow grind, not a crash"},
    {"key": "svb_2023", "label": "SVB / regional banks",
     "start": "2023-03-08", "end": "2023-03-15",
     "note": "sudden idiosyncratic financial-sector shock"},
    {"key": "yen_carry_2024", "label": "Aug 2024 carry unwind",
     "start": "2024-07-31", "end": "2024-08-05",
     "note": "three-day global de-risking on a funding-currency move"},
)


class StressTester:
    def __init__(self, nav_service, fetcher: Callable[..., Any] = fetch_daily_bars):
        self._nav = nav_service
        self._fetch = fetcher

    # --- current book ------------------------------------------------------
    def _book(self) -> tuple[float, dict[str, float]]:
        snap = self._nav.compute()
        nav = float(snap.total_nav_usd)
        held = {}
        for p in snap.positions:
            v = float(p["usd_value"])
            if abs(v) > 1e-9:
                held[str(p["symbol"]).upper()] = v
        return nav, held

    # --- historical replay -------------------------------------------------
    def replay(self, scenarios: Sequence[dict] = HISTORICAL_SCENARIOS) -> dict[str, Any]:
        nav, held = self._book()
        if not held:
            return {"measurable": False, "reason": "no open positions"}

        out: list[dict[str, Any]] = []
        for sc in scenarios:
            per_symbol: list[dict[str, Any]] = []
            missing: list[str] = []
            total_pnl = 0.0
            covered_usd = 0.0
            for sym, usd in held.items():
                try:
                    bars = self._fetch(sym, lookback_days=0, start=sc["start"], end=sc["end"])
                except (BarsError, Exception):  # noqa: BLE001 — absence is a finding
                    missing.append(sym)
                    continue
                closes = getattr(bars, "closes", None) or []
                if len(closes) < 2 or not closes[0]:
                    missing.append(sym)
                    continue
                ret = closes[-1] / closes[0] - 1.0
                pnl = usd * ret
                total_pnl += pnl
                covered_usd += usd
                per_symbol.append({
                    "symbol": sym, "return_pct": round(ret * 100.0, 2),
                    "pnl_usd": round(pnl, 2), "n_bars": len(closes),
                })

            if not per_symbol:
                out.append({**sc, "measurable": False,
                            "reason": "none of the current holdings have price history "
                                      "covering this window",
                            "missing": missing})
                continue

            per_symbol.sort(key=lambda r: r["pnl_usd"])
            coverage = (covered_usd / sum(held.values()) * 100.0) if held else 0.0
            out.append({
                **sc,
                "measurable": True,
                "pnl_usd": round(total_pnl, 2),
                "nav_change_pct": round((total_pnl / nav * 100.0) if nav > 0 else 0.0, 2),
                "nav_after": round(nav + total_pnl, 2),
                "worst_name": per_symbol[0],
                "per_symbol": per_symbol,
                "missing": missing,
                "coverage_pct": round(coverage, 1),
                "caveat": (
                    f"assumes today's weights held unchanged through the window and "
                    f"covers {coverage:.0f}% of gross exposure"
                    + (f"; no history for {', '.join(missing)}" if missing else "")
                ),
            })

        measurable = [s for s in out if s.get("measurable")]
        worst = min(measurable, key=lambda s: s["pnl_usd"]) if measurable else None
        return {
            "measurable": bool(measurable),
            "nav_usd": round(nav, 2),
            "scenarios": out,
            "worst_scenario": worst,
            "note": "real returns from real dates applied to the current book — no "
                    "assumed betas or proxied sensitivities",
        }

    # --- reverse stress ----------------------------------------------------
    def reverse(self, drawdown_limit_pct: float, peak_nav: float,
                daily_loss_limit_pct: float | None = None) -> dict[str, Any]:
        """What move breaches the halt?

        Solves for the uniform percentage move across the book that would drive
        NAV to the drawdown kill-switch, and the equivalent single-name move for
        each position. Cash does not fall, so a book that is 40% cash needs a
        much larger equity move to breach — which is exactly the intuition a
        cash-floor limit is supposed to buy, made explicit.
        """
        nav, held = self._book()
        gross = sum(held.values())
        if gross <= 0:
            return {"measurable": False, "reason": "no market exposure — nothing to shock"}

        peak = max(float(peak_nav), nav)
        halt_nav = peak * (1.0 - drawdown_limit_pct)
        loss_needed = nav - halt_nav

        result: dict[str, Any] = {
            "measurable": True,
            "nav_usd": round(nav, 2),
            "peak_nav_usd": round(peak, 2),
            "halt_nav_usd": round(halt_nav, 2),
            "gross_exposure_usd": round(gross, 2),
            "drawdown_limit_pct": round(drawdown_limit_pct * 100.0, 2),
        }

        if loss_needed <= 0:
            result["already_breached"] = True
            result["headline"] = "the drawdown limit is already breached"
            return result

        result["already_breached"] = False
        result["loss_to_halt_usd"] = round(loss_needed, 2)
        uniform = loss_needed / gross
        result["uniform_move_to_halt_pct"] = round(-uniform * 100.0, 2)
        result["headline"] = (
            f"a {uniform * 100.0:.1f}% fall across every holding takes the fund to its "
            f"{drawdown_limit_pct:.0%} drawdown halt (${loss_needed:,.0f} of loss)"
        )

        per_name = []
        for sym, usd in sorted(held.items(), key=lambda kv: -kv[1]):
            move = loss_needed / usd if usd > 0 else None
            per_name.append({
                "symbol": sym,
                "exposure_usd": round(usd, 2),
                "move_to_halt_pct": round(-move * 100.0, 2) if move is not None else None,
                "possible": bool(move is not None and move <= 1.0),
            })
        result["single_name"] = per_name
        result["single_name_note"] = (
            "the move that name alone would have to make, with everything else "
            "unchanged; 'possible: false' means it could go to zero without "
            "breaching the limit by itself"
        )

        if daily_loss_limit_pct:
            d_loss = nav * daily_loss_limit_pct
            result["daily_loss_limit_pct"] = round(daily_loss_limit_pct * 100.0, 2)
            result["uniform_move_to_daily_halt_pct"] = round(-(d_loss / gross) * 100.0, 2)
            result["daily_headline"] = (
                f"a {(d_loss / gross) * 100.0:.1f}% fall in one session trips the daily-loss halt"
            )
        return result
