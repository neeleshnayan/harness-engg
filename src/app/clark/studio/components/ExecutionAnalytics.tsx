"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { spineError } from "@/lib/spine_error";
import { useChartColors } from "../chartColors";
import { KT } from "../theme";
import { ExecutionSummary, RoundTrip, StrategyExecutions, fundApiClient } from "@/lib/fund_api";
import { ExecutionChart } from "./ExecutionChart";

/**
 * What a live strategy actually did — every fill, and what each sale realized.
 *
 * The per-strategy P&L number answers "is it up". An operator watching a live
 * strategy needs the questions underneath it: when did it sell, was that right,
 * and is the result a distribution or one lucky trade? So this renders the
 * round-trips the spine folds out of the event log — never targets, never
 * intents, only fills that happened.
 *
 * Two deliberate refusals:
 *   * an open position is not a result, so a strategy that has only bought
 *     shows its fills and says there is nothing to summarise yet
 *   * a win rate needs a denominator, so nothing is drawn until there are
 *     closed round-trips — a 0% win rate from zero trades is not a fact
 */

const money = (n?: number | null, dp = 2) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const signed = (n?: number | null, dp = 2) =>
  n == null ? "—" : `${n >= 0 ? "+" : "−"}$${Math.abs(Number(n)).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 1) =>
  n == null ? "—" : `${(Number(n) * 100).toFixed(dp)}%`;
const pctSigned = (n?: number | null, dp = 2) =>
  n == null ? "—" : `${n >= 0 ? "+" : ""}${Number(n).toFixed(dp)}%`;
const when = (ts?: string | null) =>
  !ts ? "—" : ts.replace("T", " ").slice(0, 16);

type Side = "all" | "long" | "short";

export function ExecutionAnalytics({ strategyId, title }: {
  strategyId: string;
  title?: string;
}) {
  const c = useChartColors();
  const [data, setData] = useState<StrategyExecutions | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [side, setSide] = useState<Side>("all");
  const [loading, setLoading] = useState(true);
  const [sym, setSym] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fundApiClient.getExecutions(strategyId);
      setData(r as StrategyExecutions);
      setErr(null);
    } catch (e: unknown) {
      setErr(spineError(e));
      setData(null);          // unknown, not empty
    } finally {
      setLoading(false);
    }
  }, [strategyId]);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  // Symbols this strategy actually traded, most-traded first — taken from
  // fills, not from the strategy's declared universe, so the picker only ever
  // offers charts that have something on them.
  const symbols = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of data?.fills ?? []) {
      counts.set(f.symbol, (counts.get(f.symbol) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([s]) => s);
  }, [data]);

  useEffect(() => {
    setSym((cur) => (cur && symbols.includes(cur) ? cur : symbols[0] ?? null));
  }, [symbols]);

  // The side split is only offered when both sides exist — a toggle with an
  // always-empty option invites the reader to think data is missing.
  const hasShorts = (data?.round_trips ?? []).some((t) => t.side === "short");
  const summary: ExecutionSummary | undefined = useMemo(() => {
    if (!data) return undefined;
    if (side === "all" || !data.by_side) return data.summary;
    return data.by_side[side];
  }, [data, side]);

  const trips: RoundTrip[] = useMemo(() => {
    const all = data?.round_trips ?? [];
    return side === "all" ? all : all.filter((t) => t.side === side);
  }, [data, side]);

  const histogram = useMemo(() => {
    const d = summary?.distribution_pct;
    if (!d?.measurable || !d.bins) return null;
    return d.bins.map((b) => ({
      label: `${b.from_pct.toFixed(1)}`,
      mid: (b.from_pct + b.to_pct) / 2,
      count: b.count,
      sign: b.sign,
    }));
  }, [summary]);

  if (loading) {
    return (
      <div className={`mt-6 ${KT.panel} px-5 py-8 text-sm ${KT.muted}`}>
        Loading execution history…
      </div>
    );
  }

  if (err) {
    return (
      <div className={`mt-6 ${KT.panel} px-5 py-6 text-sm ${KT.down}`}>
        {err} — execution history unavailable. This is unknown, not empty.
      </div>
    );
  }

  const nFills = data?.n_fills ?? 0;
  const measurable = summary?.measurable === true;

  return (
    <div className={`mt-6 ${KT.panel}`}>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--kt-border)] px-5 py-3">
        <div>
          <span className={KT.label}>{title || "Execution history"}</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            Folded from the event log — fills only. A round-trip closes against the
            running average cost, so its entry is a quantity-weighted average.
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`font-mono text-[11px] ${KT.muted}`}>
            {nFills} fill{nFills === 1 ? "" : "s"} · {data?.n_round_trips ?? 0} closed
          </span>
          {hasShorts && (
            <div className="flex gap-1">
              {(["all", "long", "short"] as Side[]).map((s) => (
                <button key={s} onClick={() => setSide(s)}
                        className={`rounded px-2 py-0.5 text-[11px] capitalize ${
                          side === s
                            ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                            : `${KT.muted} hover:bg-[var(--kt-hover)]`}`}>
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Candles for the symbols this strategy actually touched, with its fills
          marked. Shown even when nothing has closed — seeing the entries on the
          chart is most of the value while a position is still open. */}
      {symbols.length > 0 && (
        <div className="border-b border-[var(--kt-border)] pb-2">
          <div className="flex flex-wrap items-center gap-2 px-5 pt-3">
            <span className={KT.label}>Price &amp; fills</span>
            <div className="flex gap-1">
              {symbols.map((s) => (
                <button key={s} onClick={() => setSym(s)}
                        className={`rounded px-2 py-0.5 text-[11px] ${
                          sym === s
                            ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                            : `${KT.muted} hover:bg-[var(--kt-hover)]`}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>
          {sym && <ExecutionChart symbol={sym} strategyId={strategyId} />}
        </div>
      )}

      {!measurable ? (
        <div className={`px-5 py-6 text-sm ${KT.muted}`}>
          {summary?.reason || data?.reason || "Nothing to summarise yet."}
          {nFills > 0 && (
            <span className="block mt-1">
              {nFills} fill{nFills === 1 ? "" : "s"} recorded and the position is still
              open — an open position is a mark, not a result.
            </span>
          )}
        </div>
      ) : (
        <>
          {/* Headline: realized only. Marks are not money. */}
          <div className="grid grid-cols-2 gap-4 px-5 py-4 lg:grid-cols-5">
            <Stat label="Realized" value={signed(summary?.total_realized_usd)}
                  tone={(summary?.total_realized_usd ?? 0) >= 0 ? "up" : "down"}
                  sub="closed trades only" />
            <Stat label="Win rate" value={pct(summary?.win_rate)}
                  sub={`${summary?.winners ?? 0}W / ${summary?.losers ?? 0}L / ${summary?.breakevens ?? 0} scratch`} />
            <Stat label="Payoff" value={summary?.payoff_ratio == null ? "—" : `${summary.payoff_ratio.toFixed(2)}×`}
                  sub="avg win ÷ avg loss" />
            <Stat label="Profit factor" value={summary?.profit_factor == null ? "—" : summary.profit_factor.toFixed(2)}
                  tone={(summary?.profit_factor ?? 0) >= 1 ? "up" : "down"}
                  sub="gross win ÷ gross loss" />
            <Stat label="Expectancy" value={signed(summary?.expectancy_usd, 2)}
                  tone={(summary?.expectancy_usd ?? 0) >= 0 ? "up" : "down"}
                  sub="per round-trip" />
          </div>

          {/* The two numbers that decide whether the edge is real or one trade. */}
          <div className="grid grid-cols-2 gap-4 border-t border-[var(--kt-border)] px-5 py-3 lg:grid-cols-4">
            <Stat small label="Longest loss streak"
                  value={summary?.streaks?.longest_loss_streak ?? "—"}
                  sub="what you must sit through" />
            <Stat small label="Best trade share of gross profit"
                  value={summary?.top_trade_share_of_gross_profit == null ? "—"
                         : pct(summary.top_trade_share_of_gross_profit)}
                  sub="high means the edge is one trade" />
            <Stat small label="Avg hold — winners"
                  value={summary?.holding?.avg_days_winners == null ? "—"
                         : `${summary.holding.avg_days_winners.toFixed(1)}d`}
                  sub="vs losers" />
            <Stat small label="Avg hold — losers"
                  value={summary?.holding?.avg_days_losers == null ? "—"
                         : `${summary.holding.avg_days_losers.toFixed(1)}d`}
                  sub={
                    summary?.holding?.avg_days_losers != null &&
                    summary?.holding?.avg_days_winners != null &&
                    summary.holding.avg_days_losers > summary.holding.avg_days_winners
                      ? "losers held longer — exits are not cutting"
                      : "shorter than winners is healthy"
                  } />
          </div>

          {/* Returns distribution — the TradingView view, on our own fills. */}
          {histogram && (
            <div className="border-t border-[var(--kt-border)] px-2 py-4">
              <div className={`px-3 pb-2 ${KT.label}`}>Returns distribution</div>
              <div className="h-[180px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={histogram} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                    <XAxis dataKey="label" tick={{ fill: c.textMuted, fontSize: 10 }}
                           stroke={c.axis} tickLine={false}
                           tickFormatter={(v) => `${v}%`} />
                    <YAxis allowDecimals={false} tick={{ fill: c.textMuted, fontSize: 10 }}
                           stroke={c.axis} tickLine={false} width={32} />
                    <Tooltip
                      contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`,
                                      borderRadius: 8, fontSize: 12, color: c.text }}
                      formatter={(v: number) => [`${v} trade${v === 1 ? "" : "s"}`, "count"]}
                      labelFormatter={(l) => `from ${l}%`}
                    />
                    <ReferenceLine x={0} stroke={c.textMuted} strokeDasharray="3 3" />
                    <Bar dataKey="count">
                      {histogram.map((b, i) => (
                        <Cell key={i} fill={b.sign === "win" ? c.up : c.down} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className={`mt-1 px-3 text-[11px] ${KT.muted}`}>
                Trades within ±{summary?.breakeven_band_pct ?? 0.05}% are counted as
                scratches, not wins — otherwise commission-sized noise inflates the
                win rate.
              </p>
            </div>
          )}

          {/* The blotter an operator actually reads: when it sold, and what for. */}
          <div className="border-t border-[var(--kt-border)]">
            <div className={`px-5 pt-3 ${KT.label}`}>Closed round-trips</div>
            <div className="max-h-[320px] overflow-auto px-2 pb-4">
              <table className="w-full text-left text-[12px]">
                <thead className={`sticky top-0 bg-[var(--kt-surface)] ${KT.muted}`}>
                  <tr>
                    <th className="px-3 py-2 font-normal">Exited</th>
                    <th className="px-3 py-2 font-normal">Symbol</th>
                    <th className="px-3 py-2 font-normal">Side</th>
                    <th className="px-3 py-2 text-right font-normal">Qty</th>
                    <th className="px-3 py-2 text-right font-normal">Avg entry</th>
                    <th className="px-3 py-2 text-right font-normal">Exit</th>
                    <th className="px-3 py-2 text-right font-normal">P&amp;L</th>
                    <th className="px-3 py-2 text-right font-normal">%</th>
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {[...trips].reverse().map((t, i) => (
                    <tr key={i} className="border-t border-[var(--kt-border)]">
                      <td className={`px-3 py-1.5 ${KT.muted}`}>{when(t.exit_ts)}</td>
                      <td className="px-3 py-1.5">{t.symbol}</td>
                      <td className={`px-3 py-1.5 ${KT.muted}`}>{t.side}</td>
                      <td className="px-3 py-1.5 text-right">{t.qty}</td>
                      <td className="px-3 py-1.5 text-right">{money(t.avg_entry_price)}</td>
                      <td className="px-3 py-1.5 text-right">{money(t.exit_price)}</td>
                      <td className={`px-3 py-1.5 text-right ${
                        t.outcome === "win" ? KT.up : t.outcome === "loss" ? KT.down : KT.muted}`}>
                        {signed(t.pnl_usd)}
                      </td>
                      <td className={`px-3 py-1.5 text-right ${
                        t.outcome === "win" ? KT.up : t.outcome === "loss" ? KT.down : KT.muted}`}>
                        {pctSigned(t.pnl_pct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Fills are shown even when nothing has closed — they are what happened. */}
      {nFills > 0 && (
        <div className="border-t border-[var(--kt-border)]">
          <div className={`px-5 pt-3 ${KT.label}`}>Fills</div>
          <div className="max-h-[240px] overflow-auto px-2 pb-4">
            <table className="w-full text-left text-[12px]">
              <thead className={`sticky top-0 bg-[var(--kt-surface)] ${KT.muted}`}>
                <tr>
                  <th className="px-3 py-2 font-normal">Time</th>
                  <th className="px-3 py-2 font-normal">Side</th>
                  <th className="px-3 py-2 font-normal">Symbol</th>
                  <th className="px-3 py-2 text-right font-normal">Qty</th>
                  <th className="px-3 py-2 text-right font-normal">Price</th>
                  <th className="px-3 py-2 text-right font-normal">Notional</th>
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums">
                {[...(data?.fills ?? [])].reverse().map((f, i) => (
                  <tr key={i} className="border-t border-[var(--kt-border)]">
                    <td className={`px-3 py-1.5 ${KT.muted}`}>{when(f.ts)}</td>
                    <td className={`px-3 py-1.5 ${f.side === "buy" ? KT.up : KT.down}`}>{f.side}</td>
                    <td className="px-3 py-1.5">{f.symbol}</td>
                    <td className="px-3 py-1.5 text-right">{f.qty}</td>
                    <td className="px-3 py-1.5 text-right">{money(f.price)}</td>
                    <td className="px-3 py-1.5 text-right">{money(f.notional_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, sub, tone, small }: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: "up" | "down";
  small?: boolean;
}) {
  return (
    <div>
      <div className={KT.label}>{label}</div>
      <div className={`mt-1 ${small ? "font-mono text-sm tabular-nums" : KT.numberLg} ${
        tone === "up" ? KT.up : tone === "down" ? KT.down : ""}`}>
        {value}
      </div>
      {sub && <div className={`mt-1 text-[11px] ${KT.muted}`}>{sub}</div>}
    </div>
  );
}
