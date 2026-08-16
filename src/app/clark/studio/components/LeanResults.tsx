"use client";

import React from "react";
import { KT } from "../theme";
import { Stat } from "./Stat";
import { CandidateVerdict } from "./CandidateVerdict";
import { EquityChart } from "../lab/EquityChart";

/**
 * What a LEAN run means — one engine, one set of analytics.
 *
 * The Lab used to run two backtesters: a fast in-process one with rich
 * analytics, and LEAN with a single line of numbers. Two engines answering the
 * same question in two visual languages is worse than either alone, because
 * the reader has to hold "which tester produced this" in their head before
 * they can read a Sharpe. There is one engine now, and the analytics that were
 * only ever available upstairs live here.
 *
 * The order of the page is the order of the questions: what happened, did it
 * beat simply owning the thing, what did it actually do, and is it worth
 * owning. The last one is the only one that decides anything.
 */

export interface LeanRunResult {
  total_return_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  total_trades?: number | null;
  equity_curve?: number[];
  equity_dates?: string[];
  benchmark_curve?: number[];
  benchmark_return_pct?: number | null;
  benchmark_symbol?: string | null;
  benchmark_source?: string | null;
  orders?: LeanOrder[];
  statistics?: Record<string, string>;
}

export interface LeanOrder {
  time?: string | null;
  symbol?: string | null;
  side?: string | null;
  qty?: number | null;
  price?: number | null;
  value?: number | null;
}

const pctf = (n?: number | null) => (n == null ? "—" : `${n.toFixed(1)}%`);
const numf = (n?: number | null) => (n == null ? "—" : n.toFixed(2));

export function LeanResults({
  result,
  algorithm,
  wallSeconds,
}: {
  result: LeanRunResult;
  algorithm: string;
  wallSeconds?: number;
}) {
  const r = result;
  const orders = r.orders ?? [];
  const curve = r.equity_curve ?? [];
  const bench = r.benchmark_curve ?? [];
  const dates = r.equity_dates ?? [];
  const stats = r.statistics ?? {};

  const beat =
    r.total_return_pct != null && r.benchmark_return_pct != null
      ? r.total_return_pct > r.benchmark_return_pct
      : null;

  // The symbol the strategy actually traded — what buy & hold is measured on.
  const symbol =
    r.benchmark_symbol ??
    (orders.length ? String(orders[0].symbol ?? "") : "");

  return (
    <div className="space-y-4 px-5 py-4">
      {/* --- what happened, and against the only benchmark that matters --- */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat
          label="Total return"
          value={pctf(r.total_return_pct)}
          sub={
            r.benchmark_return_pct != null
              ? `buy & hold ${pctf(r.benchmark_return_pct)}`
              : "no benchmark available"
          }
          tone={(r.total_return_pct ?? 0) >= 0 ? KT.up : KT.down}
        />
        <Stat label="Sharpe" value={numf(r.sharpe)} sub="LEAN statistic" />
        <Stat
          label="Max drawdown"
          value={pctf(r.max_drawdown_pct)}
          sub="peak to trough"
          tone={KT.down}
        />
        <Stat
          label="Orders"
          value={r.total_trades != null ? String(r.total_trades) : String(orders.length || "—")}
          sub={orders.length ? "filled by the engine" : "it never traded"}
        />
      </div>

      {beat === false && (
        <div className={`text-[11px] ${KT.down}`}>
          Trails buy &amp; hold by{" "}
          {Math.abs((r.benchmark_return_pct ?? 0) - (r.total_return_pct ?? 0)).toFixed(2)}% —
          simply owning {symbol || "the underlying"} did better.
        </div>
      )}

      {/* --- the curve --- */}
      {curve.length >= 2 ? (
        <div className={KT.panel}>
          <div className="flex items-baseline gap-3 border-b border-[var(--kt-border)] px-5 py-3">
            <span className={KT.label}>Equity</span>
            {r.benchmark_symbol && (
              <span className={`text-[10px] ${KT.muted}`}>
                vs buy &amp; hold {r.benchmark_symbol}
                {r.benchmark_source ? ` · ${r.benchmark_source}` : ""}
              </span>
            )}
          </div>
          <div className="px-3 py-3">
            <EquityChart
              equity={curve}
              benchmark={bench.length >= 2 ? bench : undefined}
              dates={dates.length ? dates : null}
            />
          </div>
        </div>
      ) : (
        <p className={`text-[11px] ${KT.muted}`}>
          No equity curve — the algorithm never took a position, so there is
          nothing to plot. That is a result, not a failure.
        </p>
      )}

      {/* --- is it worth owning: alpha vs beta, and the fit with the book --- */}
      {curve.length >= 2 && dates.length >= 2 && (
        <CandidateVerdict
          equityCurve={curve}
          dates={dates}
          symbol={symbol || "—"}
          template={algorithm}
          params={{}}
        />
      )}

      {/* --- what it actually did --- */}
      <div className={KT.panel}>
        <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>
          Orders ({orders.length})
        </div>
        {orders.length === 0 ? (
          <div className={`px-5 py-8 text-sm ${KT.muted}`}>
            No fills — the algorithm never entered a position over this window.
          </div>
        ) : (
          <div className="max-h-[320px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[var(--kt-surface)]">
                <tr className={`border-b border-[var(--kt-border)] ${KT.label}`}>
                  <th className="px-5 py-2 text-left font-normal">#</th>
                  <th className="px-5 py-2 text-left font-normal">Side</th>
                  <th className="px-5 py-2 text-left font-normal">Symbol</th>
                  <th className="px-5 py-2 text-left font-normal">Filled</th>
                  <th className="px-5 py-2 text-right font-normal">Qty</th>
                  <th className="px-5 py-2 text-right font-normal">Price</th>
                  <th className="px-5 py-2 text-right font-normal">Value</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o, i) => (
                  <tr key={i} className="border-b border-[var(--kt-border)] last:border-0">
                    <td className={`px-5 py-2 ${KT.muted}`}>{i + 1}</td>
                    <td className={`px-5 py-2 uppercase ${o.side === "sell" ? KT.down : KT.up}`}>
                      {o.side ?? "—"}
                    </td>
                    <td className="px-5 py-2">{o.symbol ?? "—"}</td>
                    <td className={`px-5 py-2 ${KT.muted}`}>
                      {o.time ? String(o.time).slice(0, 10) : "—"}
                    </td>
                    <td className={`px-5 py-2 text-right ${KT.number}`}>{o.qty ?? "—"}</td>
                    <td className={`px-5 py-2 text-right ${KT.number}`}>{o.price ?? "—"}</td>
                    <td className={`px-5 py-2 text-right ${KT.number}`}>{o.value ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {Object.keys(stats).length > 0 && (
        <details>
          <summary className={`cursor-pointer text-[11px] ${KT.muted}`}>
            All {Object.keys(stats).length} LEAN statistics
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 sm:grid-cols-3">
            {Object.entries(stats).map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className={KT.muted}>{k}</span>
                <span className="font-mono tabular-nums">{String(v)}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      <p className={`text-[10px] ${KT.muted}`}>
        LEAN engine statistics, verbatim{wallSeconds != null ? ` · ${wallSeconds}s wall` : ""}.
        Buy &amp; hold is computed on the fund&apos;s own closes — the same feed the
        algorithm traded. Nothing here is registered or persisted to the fund;
        promotion to a strategy is a separate, deliberate step.
      </p>
    </div>
  );
}
