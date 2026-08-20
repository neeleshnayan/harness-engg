"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useChartColors } from "../chartColors";
import { isFlat, navDomain } from "../navDomain";
import { KT } from "../theme";
import { money, pct } from "../format";
import {
  AdvancedRiskView, IntradayNavSeries, NavSnapshot, RiskLimitsConfig,
  RiskMonitorResponse, fundApiClient,
} from "@/lib/fund_api";

/**
 * Three pictures, each answering a question a number cannot.
 *
 *   1. Session P&L    — is it winning right now, and how did it get there?
 *   2. Limit headroom — how close is the fund to a wall it must not hit?
 *   3. Book shape     — what is it actually holding, and what does a bad day cost?
 *
 * Deliberately not a dashboard of everything measurable. Headroom is the one
 * that earns its place: the fund publishes a dozen limits and a breach list, but
 * a breach list only ever says "fine" or "not fine" — it cannot show a limit
 * being approached, which is the only moment you can still act cheaply.
 *
 * Every bar is measured against a limit the spine actually holds. Nothing here
 * invents a threshold.
 */

// Formatters moved to ../format.ts (2026-08-20). This file's retired `money`
// defaulted to 0 decimals, but BOTH of its call sites already passed 2
// explicitly — so the default was dead and the shared default of 2 changes
// nothing here. `pct` matched the house default of 1 already.

/** Bar width against a shared scale. Floors at a visible sliver so a genuinely
 *  tiny share still reads as "present but small" rather than as absent. */
const barW = (v: number, scale: number) =>
  `${Math.min(100, Math.max(1.5, (v / (scale || 1)) * 100))}%`;

type Gauge = {
  label: string;
  used: number;        // current value, in the same unit as `limit`
  limit: number;
  kind: "ceiling" | "floor";
  detail: string;
};

export function MonitorGraphs({ m }: { m: RiskMonitorResponse | null }) {
  const c = useChartColors();
  const [limits, setLimits] = useState<RiskLimitsConfig | null>(null);
  const [intraday, setIntraday] = useState<IntradayNavSeries | null>(null);
  const [struck, setStruck] = useState<NavSnapshot[]>([]);
  const [adv, setAdv] = useState<AdvancedRiskView | null>(null);

  const load = useCallback(async () => {
    const [l, i, h] = await Promise.all([
      fundApiClient.getRiskLimits().catch(() => null),
      fundApiClient.getIntradayNav(360).catch(() => null),
      // Struck NAVs from the ledger — the fallback picture for when the
      // market is shut and the in-memory intraday trace is a flat line.
      fundApiClient.getNavHistory(30).catch(() => null),
    ]);
    setLimits(l);
    setIntraday(i);
    setStruck(h?.history ?? []);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  // Structural risk on its own, slower clock. It reads a year of market history
  // and is cached server-side for 30 minutes, so putting it on the 60s loop
  // would be all cost and no freshness. Fetched separately for a second reason:
  // it takes seconds on a cold cache, and the two fast panels should not wait
  // behind it. Failure leaves `adv` null and the panel falls back to capital
  // weights — a blank panel would be worse than a partial one.
  useEffect(() => {
    let alive = true;
    const pull = () => {
      fundApiClient
        .getRiskAdvanced({ includeRegime: false, includeHistorical: false })
        .then((r) => { if (alive) setAdv(r); })
        .catch(() => { /* falls back to capital weights */ });
    };
    pull();
    const t = setInterval(pull, 300000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  // --- 1. session P&L ------------------------------------------------------
  const trace = useMemo(() => {
    const s = intraday?.samples ?? [];
    return s.map((p) => ({ ts: p.ts.slice(11, 16), nav: p.total_nav_usd }));
  }, [intraday]);

  // The market is shut two days out of seven, and a flat line with an apology
  // was this panel's face for all of them. When the intraday trace has nothing
  // to say, fall back to the struck NAVs from the ledger — a coarser picture,
  // but a real one, and clearly labelled as the different thing it is.
  const daily = useMemo(
    () => struck
      .filter((h) => h.ts && h.total_nav_usd != null)
      .map((h) => ({ ts: String(h.ts).slice(5, 10), nav: h.total_nav_usd })),
    [struck],
  );
  const intradayLive = trace.length >= 3 && !isFlat(trace.map((t) => t.nav));
  const useDaily = !intradayLive && daily.length >= 2;
  const shown = useDaily ? daily : trace;

  const change = useDaily
    ? (daily.length >= 2 ? daily[daily.length - 1].nav - daily[daily.length - 2].nav : null)
    : (intraday?.change_usd ?? null);
  const up = (change ?? 0) >= 0;

  // --- 2. limit headroom ---------------------------------------------------
  // Only limits with a measured current value. A gauge whose "used" side we
  // cannot observe would be a picture of an assumption.
  const gauges: Gauge[] = useMemo(() => {
    if (!m || !limits) return [];
    const g: Gauge[] = [];
    const biggest = (m.positions ?? []).reduce(
      (w, p) => (p.weight_pct > (w?.weight_pct ?? -1) ? p : w),
      null as null | { symbol: string; weight_pct: number },
    );

    if (m.drawdown?.limit_pct) {
      g.push({
        label: "Drawdown", used: m.drawdown.drawdown_pct ?? 0, limit: m.drawdown.limit_pct,
        kind: "ceiling", detail: `halt at ${pct(m.drawdown.limit_pct, 0)}`,
      });
    }
    if (biggest && limits.max_position_pct) {
      g.push({
        label: `Largest position (${biggest.symbol})`, used: biggest.weight_pct,
        limit: limits.max_position_pct * 100, kind: "ceiling",
        detail: `cap ${pct(limits.max_position_pct * 100, 0)}`,
      });
    }
    if (limits.min_cash_pct != null) {
      g.push({
        label: "Cash", used: m.cash_pct ?? 0, limit: limits.min_cash_pct * 100,
        kind: "floor", detail: `floor ${pct(limits.min_cash_pct * 100, 0)}`,
      });
    }
    return g;
  }, [m, limits]);

  // --- 3. book shape -------------------------------------------------------
  //
  // This panel used to plot capital weight and a "-20% costs $X" figure, where
  // the shock was `value * -0.20` per position — the same haircut on every
  // name, so the total was just 20% of gross exposure restated. Both told you
  // how *big* the book is. Neither told you what it is exposed to.
  //
  // The measured version is more interesting and, in this book, alarming: every
  // holding is roughly 8% of NAV, so seven near-identical capital bars read as
  // "evenly spread, nothing to see" — while INTC, on 14% of invested capital,
  // carries 35% of the book's risk. The engine already computes that. Drawing
  // capital and risk on the same row is what makes the divergence visible.
  const book = useMemo(() => {
    const rows = [...(m?.positions ?? [])];
    const byRisk = new Map(
      (adv?.risk_contribution?.contributions ?? []).map((c) => [c.symbol, c]),
    );
    const vols = adv?.correlation?.annualised_vol_pct ?? {};
    const merged = rows.map((p) => {
      const rc = byRisk.get(p.symbol);
      return {
        symbol: p.symbol,
        // % of NAV. Cash is in that denominator, so this is the number the
        // concentration cap is written against and the only one it can be
        // checked against.
        navWeight: p.weight_pct,
        // % of *invested* capital — cash excluded. Risk shares are computed on
        // this basis, so the two bars must share it or they are not
        // comparable: INTC reads 8.1% of NAV and 14.0% of capital, and drawing
        // 8.1% against a 35.3% risk share silently overstates the gap.
        capitalShare: rc?.capital_weight_pct ?? null,
        value: p.value_usd,
        pnl: p.unrealized_pnl_pct,
        riskShare: rc?.risk_share_pct ?? null,
        vol: vols[p.symbol] ?? null,
      };
    });
    // Sorted by whichever dimension we can actually see. Once risk shares are
    // in, ordering by risk puts the name that matters at the top; before then,
    // capital is all there is.
    const haveRisk = merged.some((r) => r.riskShare != null);
    merged.sort((a, b) =>
      haveRisk
        ? (b.riskShare ?? -Infinity) - (a.riskShare ?? -Infinity)
        : b.navWeight - a.navWeight,
    );
    return merged;
  }, [m, adv]);

  const capPct = limits?.max_position_pct ? limits.max_position_pct * 100 : null;
  const haveRisk = book.some((r) => r.riskShare != null);
  const effBets = adv?.correlation?.measurable ? adv.correlation.effective_bets : null;
  const topRisk = adv?.risk_contribution?.largest_risk_contributor ?? null;
  /** Longest bar in the panel, shared by every row and both series. */
  const scale = useMemo(
    () => Math.max(
      1,
      ...book.map((b) =>
        Math.max(b.capitalShare ?? b.navWeight, Math.abs(b.riskShare ?? 0))),
    ),
    [book],
  );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* 1 — session P&L, or NAV by day when the session has nothing to show */}
      <div className={KT.panel}>
        <div className="flex items-baseline justify-between border-b border-[var(--kt-border)] px-4 py-2.5">
          <span className={KT.label}>{useDaily ? "NAV by day" : "Session P&L"}</span>
          {change != null && (
            <span className={`font-mono text-[12px] tabular-nums ${up ? KT.up : KT.down}`}>
              {up ? "+" : "−"}{money(Math.abs(change), 2)}
              {useDaily && <span className={KT.muted}> last strike</span>}
            </span>
          )}
        </div>
        {shown.length < (useDaily ? 2 : 3) ? (
          <div className={`px-4 py-10 text-center text-[12px] ${KT.muted}`}>
            {trace.length === 0
              ? "No intraday samples yet — the spine samples once a minute."
              : `Only ${trace.length} samples so far; two points is a line, not a trace.`}
          </div>
        ) : (
          <div className="h-[132px] w-full px-1 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={shown} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="monNav" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={up ? c.up : c.down} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={up ? c.up : c.down} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="ts" tick={{ fill: c.textMuted, fontSize: 9 }}
                       stroke={c.axis} tickLine={false} minTickGap={40} />
                <YAxis domain={navDomain(shown.map((t) => t.nav))} hide />
                <Tooltip
                  contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`,
                                  borderRadius: 8, fontSize: 11, color: c.text }}
                  formatter={(v: number) => [money(v, 2), "NAV"]} />
                {shown[0] && (
                  <ReferenceLine y={shown[0].nav} stroke={c.textMuted} strokeDasharray="3 3" />
                )}
                <Area type="monotone" dataKey="nav" stroke={up ? c.up : c.down}
                      strokeWidth={1.75} fill="url(#monNav)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
        <p className={`px-4 pb-2 text-[10px] ${KT.muted}`}>
          {useDaily
            ? "Struck NAVs from the ledger — the intraday trace is flat (closed market), so this shows the record instead."
            : <>
                {isFlat(trace.map((t) => t.nav)) && "Flat — marks are static, which is a closed market. "}
                In-memory samples, lost on restart — telemetry, not the NAV record.
              </>}
        </p>
      </div>

      {/* 2 — limit headroom */}
      <div className={KT.panel}>
        <div className="border-b border-[var(--kt-border)] px-4 py-2.5">
          <span className={KT.label}>Limit headroom</span>
        </div>
        {gauges.length === 0 ? (
          <div className={`px-4 py-10 text-center text-[12px] ${KT.muted}`}>
            Limits unreadable — headroom unknown.
          </div>
        ) : (
          <div className="space-y-3 px-4 py-3">
            {gauges.map((g) => {
              // A ceiling is breached above the limit; a floor, below it.
              const ratio = g.kind === "ceiling"
                ? (g.limit ? g.used / g.limit : 0)
                : (g.used ? g.limit / g.used : 2);
              const breached = g.kind === "ceiling" ? g.used > g.limit : g.used < g.limit;
              const near = !breached && ratio > 0.75;
              const fill = breached ? c.down : near ? c.warn : c.up;
              return (
                <div key={g.label}>
                  <div className="flex items-baseline justify-between text-[11px]">
                    <span className={breached ? KT.down : ""}>{g.label}</span>
                    <span className={`font-mono tabular-nums ${breached ? KT.down : KT.muted}`}>
                      {pct(g.used)} <span className={KT.muted}>/ {g.detail}</span>
                    </span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded bg-[var(--kt-hover)]">
                    <div className="h-full rounded transition-all"
                         style={{ width: `${Math.min(100, Math.max(2, ratio * 100))}%`,
                                  background: fill }} />
                  </div>
                </div>
              );
            })}
            <p className={`pt-1 text-[10px] ${KT.muted}`}>
              A breach list only says fine or not fine. This shows a limit being
              approached — the last point where acting is still cheap.
            </p>
          </div>
        )}
      </div>

      {/* 3 — book shape */}
      <div className={KT.panel}>
        <div className="flex items-baseline justify-between border-b border-[var(--kt-border)] px-4 py-2.5">
          <span className={KT.label}>Book shape</span>
          {effBets != null && (
            <span className={`font-mono text-[11px] tabular-nums ${KT.muted}`}>
              {book.length} names · {effBets.toFixed(1)} bets
            </span>
          )}
        </div>

        {/* C6 (found 2026-08-20 by running Monitor against a dead spine, while
            fixing C2; same defect class, different panel). `book` is derived
            from `m?.positions ?? []`, so an unreadable risk monitor produced an
            empty array and this panel reported "No positions held" — a
            statement about the fund's book made without reading it. The fund
            held 43% of NAV at the time. Unknown says unknown. */}
        {m === null ? (
          <div className={`px-4 py-10 text-center text-[12px] ${KT.sev.warn}`}>
            Positions unreadable — the book&apos;s shape is unknown, not flat.
          </div>
        ) : book.length === 0 ? (
          <div className={`px-4 py-10 text-center text-[12px] ${KT.muted}`}>
            No positions held.
          </div>
        ) : (
          <div className="px-4 py-3">
            {/* CDO D8: the denominator lives beside the numbers, not only in
                the footnote below them. Every percentage on this panel is a
                share of INVESTED CAPITAL (cash excluded) — a reader who takes
                them for shares of NAV under-reads every one of them, and the
                footnote that said so was three screens of bars away. */}
            <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className={`flex items-center gap-1.5 text-[10px] ${KT.muted}`}>
                <span className="h-2 w-2 rounded-sm" style={{ background: c.accent }} />
                capital — of invested capital
              </span>
              {haveRisk && (
                <span className={`flex items-center gap-1.5 text-[10px] ${KT.muted}`}>
                  <span className="h-2 w-2 rounded-sm" style={{ background: c.warn }} />
                  risk — of portfolio risk
                </span>
              )}
            </div>

            <div className="space-y-2.5">
              {book.map((r) => {
                // One scale across both bars and every row, so lengths mean
                // something. Rescaling per row would flatten exactly the
                // divergence this panel exists to show.
                const cap = r.capitalShare ?? r.navWeight;
                const overCap = capPct != null && r.navWeight > capPct;
                // Negative is real, not an error: a holding that moves against
                // the rest of the book lowers total risk. Drawn on its own side
                // rather than as a 1px stub pretending to be small-positive.
                const diversifier = r.riskShare != null && r.riskShare < 0;
                const skew = r.riskShare != null && cap > 0 ? r.riskShare / cap : null;
                const loud = skew != null && skew >= 1.5;
                return (
                  <div key={r.symbol}>
                    <div className="flex items-baseline justify-between gap-2 text-[11px]">
                      <span className="flex items-baseline gap-1.5 truncate">
                        <span className={overCap ? KT.down : ""}>{r.symbol}</span>
                        {r.vol != null && (
                          <span className={`font-mono text-[10px] tabular-nums ${KT.muted}`}>
                            vol {pct(r.vol, 0)}
                          </span>
                        )}
                      </span>
                      <span
                        className="flex-shrink-0 font-mono tabular-nums"
                        title={`${pct(cap)} of invested capital${
                          r.riskShare != null ? ` → ${pct(r.riskShare)} of portfolio risk` : ""
                        }`}
                      >
                        <span className={overCap ? KT.down : KT.muted}>{pct(cap)}</span>
                        {r.riskShare != null && (
                          <>
                            <span className={KT.muted}> → </span>
                            <span className={diversifier ? KT.up : loud ? KT.sev.warn : KT.muted}>
                              {pct(r.riskShare)}
                            </span>
                          </>
                        )}
                      </span>
                    </div>
                    <div className="mt-1 space-y-[3px]">
                      <div className={KT.barTrack}>
                        <div className="h-full rounded-full"
                             style={{ width: barW(cap, scale),
                                      background: overCap ? c.down : c.accent }} />
                      </div>
                      {r.riskShare != null && (
                        <div className={KT.barTrack}>
                          <div className="h-full rounded-full"
                               style={{ width: barW(Math.abs(r.riskShare), scale),
                                        background: diversifier ? c.up : c.warn }} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <p className={`mt-3 text-[10px] leading-relaxed ${KT.muted}`}>
              {haveRisk && topRisk ? (
                <>
                  {topRisk.symbol} is {pct(topRisk.capital_weight_pct)} of invested capital
                  and {pct(topRisk.risk_share_pct)} of its risk. Equal capital weights are
                  not equal risk weights — volatility and correlation decide that. Shares
                  are of invested capital, so cash is excluded; the {capPct != null ? `${pct(capPct, 0)} ` : ""}
                  concentration cap is measured against NAV instead.
                </>
              ) : (
                <>Capital weight only — the risk decomposition reads a year of market
                history and is still loading.</>
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
