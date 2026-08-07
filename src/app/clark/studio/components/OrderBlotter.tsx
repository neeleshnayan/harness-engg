"use client";

import React from "react";
import { History } from "lucide-react";
import { OrderHistoryRow, StrategyView } from "@/lib/fund_api";

const STATUS_STYLE: Record<string, string> = {
  filled: "bg-emerald-500/15 text-emerald-300",
  working: "bg-sky-500/15 text-sky-300",
  partial: "bg-sky-500/15 text-sky-300",
  pending: "bg-amber-500/15 text-amber-300",
  approved: "bg-amber-500/15 text-amber-300",
  failed: "bg-red-500/15 text-red-300",
  rejected: "bg-red-500/15 text-red-300",
  declined: "bg-zinc-500/15 text-zinc-400",
};

const fmtTs = (ts?: string | null) => {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
const money = (n?: number | null) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

/** The trade blotter — order history, filterable by strategy (parent rolls up children). */
export function OrderBlotter({
  orders,
  strategies,
  filter,
  onFilter,
}: {
  orders: OrderHistoryRow[];
  strategies: StrategyView[];
  filter: string | null;
  onFilter: (strategyId: string | null) => void;
}) {
  const nameOf = (id?: string | null) =>
    id ? strategies.find((s) => s.strategy_id === id)?.name || "—" : "discretionary";

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-4 py-2.5">
        <History size={14} className="text-teal-400" />
        <span className="text-sm font-semibold">Order history</span>
        <span className="text-[11px] text-zinc-500">{orders.length} orders</span>
        <select
          value={filter ?? ""}
          onChange={(e) => onFilter(e.target.value || null)}
          className="ml-auto rounded border border-zinc-700 bg-zinc-800/60 px-2 py-1 text-xs text-zinc-200 outline-none"
        >
          <option value="">All strategies</option>
          {strategies.map((s) => (
            <option key={s.strategy_id} value={s.strategy_id}>
              {s.is_container ? `${s.name} (+children)` : s.name}
            </option>
          ))}
        </select>
      </div>
      {orders.length === 0 ? (
        <div className="p-6 text-center text-sm text-zinc-500">No orders yet.</div>
      ) : (
        <div className="max-h-[280px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-zinc-900/95">
              <tr className="text-[10px] uppercase tracking-wide text-zinc-500">
                <th className="px-4 py-1.5 text-left font-medium">When</th>
                <th className="px-2 py-1.5 text-left font-medium">Side</th>
                <th className="px-2 py-1.5 text-left font-medium">Order</th>
                <th className="px-2 py-1.5 text-right font-medium">Fill</th>
                <th className="px-2 py-1.5 text-left font-medium">Strategy</th>
                <th className="px-4 py-1.5 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.order_id} className="border-t border-zinc-800/60 hover:bg-zinc-800/20">
                  <td className="px-4 py-1.5 font-mono text-[11px] text-zinc-500">{fmtTs(o.ts)}</td>
                  <td className="px-2 py-1.5">
                    <span className={`text-[10px] font-bold uppercase ${o.side === "buy" ? "text-emerald-400" : "text-red-400"}`}>
                      {o.side}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 font-mono text-xs">{o.qty} {o.symbol}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-[11px] text-zinc-400">
                    {o.filled_qty != null ? `${o.filled_qty} @ ${money(o.avg_price)}` : "—"}
                  </td>
                  <td className="px-2 py-1.5 truncate text-[11px] text-zinc-400">{nameOf(o.strategy_id)}</td>
                  <td className="px-4 py-1.5 text-right">
                    <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase ${STATUS_STYLE[o.status] || "bg-zinc-500/15 text-zinc-400"}`}>
                      {o.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
