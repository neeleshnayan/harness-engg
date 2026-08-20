"use client";

import React from "react";
import { KT } from "../theme";
import { moneyCompact, pct } from "../format";
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
  robustness?: LeanRobustness | null;
  capacity?: LeanCapacity | null;
}

export interface LeanCapacity {
  symbol?: string;
  adv_usd?: number | null;
  capacity_usd?: number | null;
  participation?: number;
  thin_market?: boolean;
  below_big_fund_floor?: boolean;
  verdict?: string;
  assumption?: string;
  reason?: string;
}

export interface LeanRobustness {
  psr_pct?: number | null;
  total_orders?: number | null;
  win_rate_pct?: number | null;
  total_fees?: number | null;
  turnover_pct?: number | null;
  periods?: { from: string; to: string; return_pct: number }[];
  costs?: LeanCostDisclosure | null;
}

export interface LeanCostDisclosure {
  slippage_modelled?: boolean;
  fee_model_set?: boolean;
  commission_paid?: number | null;
  unpriced?: boolean;
  note?: string;
}

export interface LeanOrder {
  time?: string | null;
  symbol?: string | null;
  side?: string | null;
  qty?: number | null;
  price?: number | null;
  value?: number | null;
}

// `pctf` was `pct(n, 1)` under another name — retired to ../format.ts.
const numf = (n?: number | null) => (n == null ? "—" : n.toFixed(2));

/**
 * The question that comes BEFORE "is it worth owning".
 *
 * A backtest states its return with identical confidence whether it rests on
 * five trades or five hundred, which is how a lucky streak gets promoted to a
 * strategy. Everything here is measured by the engine, not asserted by us.
 */
function Robustness({ rb }: { rb: LeanRobustness }) {
  const psr = rb.psr_pct;
  const periods = rb.periods ?? [];
  const positive = periods.filter((p) => p.return_pct > 0).length;

  // Probabilistic Sharpe Ratio: the probability the TRUE Sharpe beats zero,
  // adjusted for skew, kurtosis and how much history there is. Below ~50% the
  // observed Sharpe is not distinguishable from luck.
  const verdict =
    psr == null ? null
      : psr >= 95 ? { text: "The Sharpe is very unlikely to be luck.", tone: KT.up }
      : psr >= 50 ? { text: "The Sharpe is more likely real than not, but not settled.", tone: "text-[var(--kt-warn)]" }
      : { text: "The Sharpe is NOT distinguishable from luck on this much history.", tone: KT.down };

  return (
    <div className={KT.panel}>
      <div className="border-b border-[var(--kt-border)] px-5 py-3">
        <span className={KT.label}>Can this be believed?</span>
        <div className={`mt-1 text-[11px] ${KT.muted}`}>
          Before asking whether a strategy is good, ask whether the result is a
          measurement or a coincidence.
        </div>
      </div>

      <div className="grid grid-cols-1 gap-x-8 gap-y-4 px-5 py-4 sm:grid-cols-3">
        <div>
          <div className={KT.label}>Confidence the edge is real</div>
          <div className={`mt-1 font-mono tabular-nums text-xl font-light ${verdict?.tone ?? ""}`}>
            {psr == null ? "—" : `${psr.toFixed(1)}%`}
          </div>
          <div className={`mt-1 text-[10px] ${KT.muted}`}>
            probabilistic Sharpe — LEAN&apos;s own statistic
          </div>
        </div>

        <div>
          <div className={KT.label}>Evidence</div>
          <div className="mt-1 font-mono tabular-nums text-xl font-light">
            {rb.total_orders ?? "—"}
          </div>
          <div className={`mt-1 text-[10px] ${KT.muted}`}>
            fills{rb.win_rate_pct != null ? ` · ${rb.win_rate_pct.toFixed(0)}% won` : ""}
          </div>
        </div>

        <div>
          <div className={KT.label}>Trading costs</div>
          <div className={`mt-1 font-mono tabular-nums text-xl font-light ${rb.costs?.unpriced ? "text-[var(--kt-warn)]" : ""}`}>
            {rb.costs?.unpriced ? "unpriced" : rb.costs?.slippage_modelled ? "modelled" : "—"}
          </div>
          <div className={`mt-1 text-[10px] ${KT.muted}`}>
            {rb.turnover_pct != null ? `${rb.turnover_pct.toFixed(1)}% turnover` : "spread + commission"}
          </div>
        </div>
      </div>

      {verdict && (
        <div className={`px-5 pb-3 text-[11px] ${verdict.tone}`}>{verdict.text}</div>
      )}

      {rb.costs?.unpriced && (
        <div className={`px-5 pb-3 text-[11px] text-[var(--kt-warn)]`}>
          This run was never priced — no slippage model, so every fill happened
          at the close. The live version will earn less than the curve above,
          and the more it trades the wider that gap gets. Add
          <code> sec.set_slippage_model(ConstantSlippageModel(0.0005))</code> and
          run it again.
        </div>
      )}
      {rb.costs?.slippage_modelled && (
        <p className={`px-5 pb-3 text-[10px] ${KT.muted}`}>
          Costs are modelled: fills cross the spread. Commission is
          ${(rb.costs.commission_paid ?? 0).toFixed(2)} because Alpaca charges
          none on US equities — that zero is correct, not missing. Sweep the
          <code> slip</code> parameter to find the cost at which this edge stops
          paying.
        </p>
      )}

      {periods.length > 0 && (
        <div className="border-t border-[var(--kt-border)] px-5 py-3">
          <div className={KT.label}>Did it work throughout?</div>
          <div className="mt-2 space-y-1">
            {periods.map((p, i) => (
              <div key={i} className="flex items-baseline gap-3 text-[11px]">
                <span className={KT.muted}>{p.from} → {p.to}</span>
                <span className={`ml-auto font-mono tabular-nums ${p.return_pct >= 0 ? KT.up : KT.down}`}>
                  {p.return_pct >= 0 ? "+" : ""}{p.return_pct.toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
          <p className={`mt-2 text-[10px] ${KT.muted}`}>
            {positive === periods.length
              ? "Positive in every stretch of the window."
              : positive <= 1
                ? "Nearly all of the result came from one stretch — that is a single event, not a repeatable edge."
                : "Mixed across the window; the result is not evenly earned."}
          </p>
        </div>
      )}
    </div>
  );
}

// This file's abbreviating `money` moved to ../format.ts as `moneyCompact`
// (2026-08-20) — renamed on the way out, because it was the ONE `money` in the
// Studio that was lossy, and a lossy formatter sharing a name with the one the
// book's dollars go through is an accident waiting for a copy-paste.

/**
 * How much money this could ever hold — and why a small answer is good news.
 *
 * The instinct on seeing a low number is that something is wrong. Here it is
 * usually the opposite: a strategy with $400k of capacity is invisible to a
 * multi-billion fund, and that is the only structural protection a fund this
 * size has. A capacity in the billions means the opposite — everyone can be
 * here, and something other than size has to be protecting the edge.
 */
function Capacity({ cap }: { cap: LeanCapacity }) {
  if (cap.capacity_usd == null) {
    return (
      <div className={`${KT.panel} px-5 py-3`}>
        <span className={KT.label}>Capacity</span>
        <p className={`mt-1 text-[11px] ${KT.muted}`}>{cap.reason ?? "not estimated"}</p>
      </div>
    );
  }
  const good = cap.below_big_fund_floor && !cap.thin_market;
  return (
    <div className={KT.panel}>
      <div className="border-b border-[var(--kt-border)] px-5 py-3">
        <span className={KT.label}>How much money could this hold?</span>
      </div>
      <div className="grid grid-cols-1 gap-4 px-5 py-4 sm:grid-cols-3">
        <div>
          <div className={KT.label}>Capacity</div>
          <div className={`mt-1 font-mono tabular-nums text-xl font-light ${good ? KT.up : ""}`}>
            {moneyCompact(cap.capacity_usd)}
          </div>
          <div className={`mt-1 text-[10px] ${KT.muted}`}>{cap.symbol}</div>
        </div>
        <div>
          <div className={KT.label}>Daily volume</div>
          <div className="mt-1 font-mono tabular-nums text-xl font-light">
            {moneyCompact(cap.adv_usd)}
          </div>
          <div className={`mt-1 text-[10px] ${KT.muted}`}>median dollar ADV</div>
        </div>
        <div>
          <div className={KT.label}>Our headroom</div>
          <div className="mt-1 font-mono tabular-nums text-xl font-light">
            {cap.capacity_usd ? `${((2026.86 / cap.capacity_usd) * 100).toFixed(4)}%` : "—"}
          </div>
          <div className={`mt-1 text-[10px] ${KT.muted}`}>of capacity used at current NAV</div>
        </div>
      </div>
      {cap.verdict && (
        <p className={`px-5 pb-3 text-[11px] ${good ? KT.up : KT.muted}`}>{cap.verdict}</p>
      )}
      {cap.assumption && (
        <p className={`px-5 pb-4 text-[10px] ${KT.muted}`}>{cap.assumption}</p>
      )}
    </div>
  );
}

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
          value={pct(r.total_return_pct)}
          sub={
            r.benchmark_return_pct != null
              ? `buy & hold ${pct(r.benchmark_return_pct)}`
              : "no benchmark available"
          }
          tone={(r.total_return_pct ?? 0) >= 0 ? KT.up : KT.down}
        />
        <Stat label="Sharpe" value={numf(r.sharpe)} sub="LEAN statistic" />
        <Stat
          label="Max drawdown"
          value={pct(r.max_drawdown_pct)}
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

      {/* --- can it be believed, before it is worth owning --- */}
      {r.robustness && <Robustness rb={r.robustness} />}

      {/* --- how much money it could ever hold --- */}
      {r.capacity && <Capacity cap={r.capacity} />}

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
