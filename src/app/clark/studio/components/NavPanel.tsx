"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { spineError } from "@/lib/spine_error";
import { useChartColors } from "../chartColors";
import { isFlat, navDomain } from "../navDomain";
import { KT } from "../theme";
import { money, signedMoney, signedPct } from "../format";
import { fundApiClient, IntradayNavSeries, NavResponse, StrategyView } from "@/lib/fund_api";

/**
 * NAV and P&L — what the fund is actually worth, and whether it is winning.
 *
 * The headline is **NAV per unit**, not NAV. NAV rises when someone subscribes
 * and falls when someone redeems, neither of which is performance; NAV per unit
 * moves only on P&L, which is why it is the number a fund reports. NAV in
 * dollars is shown beside it because that is what the operator has to size
 * against.
 *
 * Realized and unrealized are split rather than summed. A book that looks
 * profitable entirely on unrealized marks has not proven anything yet, and the
 * distinction is exactly what an operator needs before deciding to take a gain.
 *
 * With too few NAV marks to draw an honest curve, this says so rather than
 * drawing a two-point line and calling it a track record.
 */

// money / signedMoney / signedPct moved to ../format.ts (2026-08-20). The three
// bodies were byte-identical to the copies in ExecutionAnalytics; same
// defaults, so nothing here renders differently.
const signed = signedMoney;
const pctSigned = signedPct;

//: Two points is a line, not a curve. Below this we state the fact instead.
const MIN_POINTS_FOR_CURVE = 3;

//: Intraday windows. The session view an operator actually wants during a live
//: test, plus a longer one for the whole day.
const WINDOWS = [
  { label: "30m", minutes: 30 },
  { label: "2h", minutes: 120 },
  { label: "6h", minutes: 360 },
  { label: "1d", minutes: 1440 },
];

export function NavPanel({ nav, strategies }: {
  nav: NavResponse | null;
  strategies: StrategyView[];
}) {
  const c = useChartColors();
  const [history, setHistory] = useState<{ ts?: string; total_nav_usd: number; nav_per_unit?: number }[] | null>(null);
  const [intraday, setIntraday] = useState<IntradayNavSeries | null>(null);
  const [minutes, setMinutes] = useState(120);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [h, i] = await Promise.all([
        fundApiClient.getNavHistory(180),
        fundApiClient.getIntradayNav(minutes).catch(() => null),
      ]);
      setHistory(h.history || []);
      setIntraday(i);
      setErr(null);
    } catch (e: unknown) {
      setErr(spineError(e));
      setHistory(null);        // unknown, not empty
    }
  }, [minutes]);

  // The trace is the point of this panel during a live session, so it refreshes
  // on the same cadence the spine samples at.
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const live = nav?.live;
  const navUsd = live?.total_nav_usd ?? null;
  const units = live?.units_outstanding ?? null;
  const npu = live?.nav_per_unit ?? null;

  // Realized vs unrealized, summed from per-strategy attribution.
  const { realized, unrealized, costBasis } = useMemo(() => {
    let r = 0, u = 0, cb = 0, any = false;
    for (const s of strategies) {
      if (s.realized_pnl_usd != null) { r += s.realized_pnl_usd; any = true; }
      if (s.unrealized_pnl_usd != null) { u += s.unrealized_pnl_usd; any = true; }
      if (s.cost_basis_usd != null) cb += s.cost_basis_usd;
    }
    return any ? { realized: r, unrealized: u, costBasis: cb }
               : { realized: null, unrealized: null, costBasis: null };
  }, [strategies]);

  // Return since inception, per unit. Falls back to nothing rather than guessing
  // a starting value we cannot observe.
  const inceptionNpu = useMemo(() => {
    const first = (history ?? []).find((h) => h.nav_per_unit != null);
    return first?.nav_per_unit ?? null;
  }, [history]);
  const returnPct = (npu != null && inceptionNpu)
    ? ((npu / inceptionNpu) - 1) * 100 : null;
  const totalPnl = (npu != null && inceptionNpu && units != null)
    ? (npu - inceptionNpu) * units : null;

  // Prefer the intraday trace — it is what "P&L over the last few hours" means.
  // Struck NAV is the fallback when the sampler has not run long enough.
  const points = useMemo(() => {
    const live = (intraday?.samples ?? []).map((p) => ({
      ts: p.ts.slice(11, 16),
      nav: p.total_nav_usd,
      npu: p.nav_per_unit,
    }));
    if (live.length >= MIN_POINTS_FOR_CURVE) return live;
    return (history ?? [])
      .filter((h) => h.total_nav_usd != null)
      .map((h) => ({
        ts: (h.ts || "").slice(5, 16).replace("T", " "),
        nav: h.total_nav_usd,
        npu: h.nav_per_unit ?? null,
      }));
  }, [intraday, history]);

  const usingIntraday = (intraday?.samples?.length ?? 0) >= MIN_POINTS_FOR_CURVE;
  const winChange = intraday?.change_usd ?? null;
  const winChangePct = intraday?.change_pct ?? null;

  const enoughToPlot = points.length >= MIN_POINTS_FOR_CURVE;
  // A flat line through the middle of a chart still invites the reader to find
  // a trend in it, so the caption names it.
  const flat = isFlat(points.map((p) => p.nav));
  const up = (returnPct ?? 0) >= 0;

  return (
    <div className={`mt-6 ${KT.panel}`}>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>Fund value &amp; P&amp;L</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            NAV per unit is the performance measure — NAV in dollars also moves on
            subscriptions and redemptions, which are not returns.
          </div>
        </div>
        <div className="flex items-center gap-3">
          {usingIntraday && winChange != null && (
            <span className={`font-mono text-sm tabular-nums ${winChange >= 0 ? KT.up : KT.down}`}>
              {signed(winChange)} ({pctSigned(winChangePct)}) this window
            </span>
          )}
          <div className="flex gap-1">
            {WINDOWS.map((w) => (
              <button key={w.minutes} onClick={() => setMinutes(w.minutes)}
                      className={`rounded px-2 py-0.5 text-[11px] ${
                        minutes === w.minutes
                          ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                          : `${KT.muted} hover:bg-[var(--kt-hover)]`}`}>
                {w.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {err && <div className={`px-5 py-3 text-sm ${KT.down}`}>{err}</div>}

      <div className="grid grid-cols-2 gap-4 px-5 py-4 lg:grid-cols-5">
        <div>
          <div className={KT.label}>NAV</div>
          <div className={`mt-1 ${KT.numberLg}`}>{money(navUsd)}</div>
        </div>
        <div>
          <div className={KT.label}>NAV / unit</div>
          <div className={`mt-1 ${KT.numberLg}`}>
            {npu == null ? "—" : `$${Number(npu).toFixed(6)}`}
          </div>
        </div>
        <div>
          <div className={KT.label}>Return since inception</div>
          <div className={`mt-1 ${KT.numberLg} ${returnPct == null ? KT.muted : up ? KT.up : KT.down}`}>
            {pctSigned(returnPct)}
          </div>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            {totalPnl == null
              ? "no inception mark yet"
              : `${signed(totalPnl)} across ${Number(units).toLocaleString(undefined, { maximumFractionDigits: 0 })} units`}
          </div>
        </div>
        <div>
          <div className={KT.label}>Unrealized</div>
          <div className={`mt-1 ${KT.numberLg} ${unrealized == null ? KT.muted : unrealized >= 0 ? KT.up : KT.down}`}>
            {signed(unrealized)}
          </div>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>marks, not money — not yet banked</div>
        </div>
        <div>
          <div className={KT.label}>Realized</div>
          <div className={`mt-1 ${KT.numberLg} ${realized == null ? KT.muted : realized >= 0 ? KT.up : KT.down}`}>
            {signed(realized)}
          </div>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            {costBasis ? `on ${money(costBasis, 0)} cost basis` : "closed positions only"}
          </div>
        </div>
      </div>

      <div className="px-2 pb-4">
        {history === null ? (
          <div className={`px-3 py-8 text-sm ${KT.sev.warn}`}>
            NAV history unavailable — cannot show the record.
          </div>
        ) : !enoughToPlot ? (
          <div className={`px-3 py-8 text-sm ${KT.muted}`}>
            {points.length === 0
              ? "No NAV samples yet. The spine samples every minute — give it a moment."
              : `Only ${points.length} point${points.length === 1 ? "" : "s"} so far — not enough to draw a
                 curve. Intraday samples accumulate once a minute; two points would be a
                 line, not a trace.`}
          </div>
        ) : (
          <div className="h-[220px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="navFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={up ? c.up : c.down} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={up ? c.up : c.down} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={c.grid} vertical={false} />
                <XAxis dataKey="ts" tick={{ fill: c.textMuted, fontSize: 10 }}
                       stroke={c.axis} tickLine={false} />
                <YAxis domain={navDomain(points.map((p) => p.nav))} tick={{ fill: c.textMuted, fontSize: 10 }}
                       stroke={c.axis} tickLine={false} width={64}
                       tickFormatter={(v) => `$${Number(v).toFixed(0)}`} />
                <Tooltip
                  contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`,
                                  borderRadius: 8, fontSize: 12, color: c.text }}
                  formatter={(v: number | string) => [money(Number(v)), "NAV"]}
                />
                {/* Where the fund started. Above it is profit; below it is not. */}
                {points[0]?.nav != null && (
                  <ReferenceLine y={points[0].nav} stroke={c.textMuted} strokeDasharray="3 3"
                                 label={{ value: "inception", position: "insideTopLeft",
                                          fill: c.textMuted, fontSize: 10 }} />
                )}
                <Area type="monotone" dataKey="nav" stroke={up ? c.up : c.down}
                      strokeWidth={2} fill="url(#navFill)" dot={points.length < 30} />
              </AreaChart>
            </ResponsiveContainer>
            <p className={`mt-1 px-3 text-[11px] ${KT.muted}`}>
              {flat && "Flat — every mark in this window is identical, which is what "
                + "a closed market looks like. "}
              {usingIntraday
                ? `Intraday samples, once a minute, in memory only — telemetry for watching
                   the session, not the NAV record. Lost on restart.`
                : "Struck NAV marks — the official record."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
