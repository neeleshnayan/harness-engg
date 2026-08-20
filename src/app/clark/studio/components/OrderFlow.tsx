"use client";

import React, { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { KT } from "../theme";
import { UNSETTLED } from "../orderCounts";
import { OrderHistoryRow } from "@/lib/fund_api";

/**
 * Orders, working and settled, in one place behind a toggle.
 *
 * These were two stacked panels showing the same rows in the same shape, split
 * only by status — which made the operator scan two tables to answer one
 * question ("what happened to my order?") and buried the settled half below the
 * fold. It is one table now; the toggle is the filter.
 *
 * Working leads by default because it is the live question. The counts sit on
 * the toggle itself, so the half you are NOT looking at still tells you whether
 * it is worth looking at.
 */

/** Left the human's hands, not yet terminal. This panel's "working" tab
 *  includes `pending` (the operator wants their own un-approved ticket in the
 *  same list), so it binds UNSETTLED — the set that MonitorVerdict's narrower
 *  `inFlightCount` deliberately does not use. Both live in ../orderCounts.ts so
 *  the difference is one file's decision rather than two files' accident. */
const IN_FLIGHT = UNSETTLED;
/** Terminal and bad — these must stay visible rather than blend into "settled". */
const BAD = new Set(["failed", "rejected", "declined"]);

const STATUS_TONE: Record<string, string> = {
  filled: KT.up,
  partial: "text-[var(--kt-warn)]",
  working: "text-[var(--kt-text-dim)]",
  approved: "text-[var(--kt-text-dim)]",
  pending: "text-[var(--kt-warn)]",
  failed: KT.down,
  rejected: KT.down,
  declined: KT.muted,
};

type Tab = "working" | "settled";

export function OrderFlow({ orders, loading, error, limit = 12, embedded = false,
                            marketOpen = null }: {
  /** null = the order history could not be read (defect C2). The `error` prop
   *  did not cover this: Monitor catches the order fetch on its own, so `error`
   *  stayed null while `orders` arrived as `[]` and this panel printed
   *  "Nothing in flight — every order has reached a terminal state." */
  orders: OrderHistoryRow[] | null;
  loading?: boolean;
  error?: string | null;
  limit?: number;
  /** Render without panel chrome — see ApprovalQueue. */
  embedded?: boolean;
  /** Venue session state, if the caller knows it — decides whether an old
   *  working order is news or just a shut market. null = unknown. */
  marketOpen?: boolean | null;
}) {
  const [tab, setTab] = useState<Tab>("working");

  const unreadable = orders === null;
  const { working, settled } = useMemo(() => ({
    working: (orders ?? []).filter((o) => IN_FLIGHT.has(o.status)),
    settled: (orders ?? []).filter((o) => !IN_FLIGHT.has(o.status)),
  }), [orders]);

  // Open on whichever half has something to say: an empty Working tab hiding a
  // rejection behind a toggle is exactly the failure this panel should avoid.
  const [touched, setTouched] = useState(false);
  const active: Tab = touched
    ? tab
    : (working.length === 0 && settled.some((o) => BAD.has(o.status)) ? "settled" : tab);

  const rows = (active === "working" ? working : settled).slice(0, limit);

  const pick = (t: Tab) => { setTouched(true); setTab(t); };

  return (
    <div className={embedded ? "flex h-full flex-col" : KT.panel}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <span className={KT.label}>Orders</span>
        <div className="flex gap-1">
          {([
            ["working", "Working", working.length],
            ["settled", "Settled", settled.length],
          ] as const).map(([key, label, count]) => (
            <button key={key} onClick={() => pick(key)}
                    className={`rounded px-2.5 py-0.5 text-[11px] ${
                      active === key
                        ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)]"
                        : `${KT.muted} hover:bg-[var(--kt-hover)]`}`}>
              {label}{" "}
              <span className="font-mono tabular-nums">{unreadable ? "—" : count}</span>
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className={`flex items-center gap-2 px-5 py-6 text-sm ${KT.muted}`}>
          <Loader2 size={14} className="animate-spin" /> Loading…
        </div>
      ) : error || unreadable ? (
        <div className={`px-5 py-6 text-sm ${KT.sev.warn}`}>
          Order history unreadable — cannot confirm whether anything is in flight.
          Orders may be working at the venue. Check the broker directly.
        </div>
      ) : rows.length === 0 ? (
        <div className={`px-5 py-6 text-sm ${KT.muted}`}>
          {active === "working"
            ? "Nothing in flight — every order has reached a terminal state."
            : "Nothing settled yet."}
        </div>
      ) : (
        <ul className="divide-y divide-[var(--kt-border)]">
          {rows.map((o) => (
            <li key={o.order_id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-5 py-2.5 text-sm">
              <span className="font-medium uppercase">{o.side}</span>
              <span className={KT.number}>{o.qty}</span>
              <span className="font-semibold">{o.symbol}</span>
              <span className={`text-[11px] uppercase tracking-wide ${STATUS_TONE[o.status] || KT.muted}`}>
                {o.status}
              </span>
              <span className={`text-[11px] ${KT.muted}`}>
                filled {o.filled_qty ?? 0} of {o.qty}
              </span>
              {/* Age turns a stale working order from a mystery into a verdict:
                  27h on a shut market is a non-event; 20 minutes unfilled on an
                  open one is the thing this list exists to surface. */}
              {IN_FLIGHT.has(o.status) && o.ts && (() => {
                const ageMs = Date.now() - new Date(o.ts).getTime();
                const stale = marketOpen === true && ageMs > 15 * 60_000;
                const age = ageMs < 3600_000
                  ? `${Math.max(1, Math.round(ageMs / 60_000))}m`
                  : `${Math.round(ageMs / 3600_000)}h`;
                return (
                  <span className={`text-[11px] ${stale ? "text-[var(--kt-warn)]" : KT.muted}`}>
                    {age} in flight
                    {marketOpen === false && " · market closed"}
                    {stale && " · unfilled on an open market"}
                  </span>
                );
              })()}
              <span className={`ml-auto font-mono text-[11px] ${KT.muted}`}>
                {String(o.ts ?? "").slice(0, 19).replace("T", " ")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
