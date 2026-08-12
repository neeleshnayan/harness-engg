"use client";

import React, { useState } from "react";
import { KT } from "../theme";
import { SpineEvent } from "@/lib/fund_api";
import { Activity, ShieldAlert, CheckCircle2, ChevronRight, ChevronDown, UserCheck, Bot } from "lucide-react";

interface AuditLogFeedProps {
  events: SpineEvent[];
  onRefresh?: () => void;
}

const EVENT_TYPE_BADGES: Record<string, { label: string; color: string }> = {
  OrderProposed: { label: "Order Proposed", color: "bg-sky-500/15 text-sky-300 border-sky-500/30" },
  OrderApproved: { label: "Order Approved", color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  OrderFilled: { label: "Order Filled", color: "bg-teal-500/15 text-teal-300 border-teal-500/30" },
  OrderDeclined: { label: "Order Declined", color: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
  NavStruck: { label: "NAV Struck", color: "bg-purple-500/15 text-purple-300 border-purple-500/30" },
  CashConfirmed: { label: "Deposit Confirmed", color: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  ThesisCreated: { label: "Thesis Created", color: "bg-blue-500/15 text-blue-300 border-blue-500/30" },
  MemoCreated: { label: "Memo Created", color: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30" },
};

export function AuditLogFeed({ events }: AuditLogFeedProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className={`${KT.panel} p-4 space-y-3`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-teal-400" />
          <h3 className="text-sm font-semibold text-zinc-100">Spine Audit Stream</h3>
          <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-mono text-zinc-400">
            {events.length} immutable events
          </span>
        </div>
      </div>

      <div className="divide-y divide-zinc-800/60 max-h-[380px] overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-500">No events logged yet.</div>
        ) : (
          events.map((e) => {
            const badge = EVENT_TYPE_BADGES[e.type] || {
              label: e.type,
              color: "bg-zinc-800 text-zinc-300 border-zinc-700",
            };
            const isExpanded = expandedId === e.event_id;
            const isAgent = e.actor?.toLowerCase().includes("clark") || e.actor?.toLowerCase().includes("agent");

            return (
              <div key={e.event_id} className="py-2.5 space-y-2">
                <div
                  className="flex items-center justify-between gap-3 text-xs cursor-pointer hover:bg-zinc-900/40 p-1.5 rounded-md transition-colors"
                  onClick={() => toggleExpand(e.event_id)}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-zinc-500 text-[11px] font-mono tabular-nums">#{e.seq}</span>
                    <span className={`rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${badge.color}`}>
                      {badge.label}
                    </span>
                    <span className="truncate text-zinc-300 font-medium">{e.aggregate_id}</span>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 text-zinc-500 text-[11px]">
                    <span className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded text-zinc-400">
                      {isAgent ? <Bot size={11} className="text-teal-400" /> : <UserCheck size={11} className="text-amber-400" />}
                      {e.actor}
                    </span>
                    <span className="tabular-nums">
                      {e.ts ? new Date(e.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "—"}
                    </span>
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-2 rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-[11px] font-mono text-zinc-300 space-y-1">
                    <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Payload JSON</div>
                    <pre className="overflow-x-auto max-h-48 text-teal-300/90 bg-zinc-900/60 p-2 rounded border border-zinc-800/80">
                      {JSON.stringify(e.payload, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
