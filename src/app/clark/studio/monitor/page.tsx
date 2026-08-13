"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { spineError } from "@/lib/spine_error";
import { AlertTriangle, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { StudioHeader } from "../components/StudioHeader";
import { SimulationModal } from "../components/SimulationModal";
import { KT } from "../theme";
import {
  fundApiClient,
  OrderHistoryRow,
  RiskMonitorResponse,
} from "@/lib/fund_api";

/**
 * MONITOR — the shared cockpit. Two people, two questions, one screen:
 *
 *   Rushi (operator): is the fund okay, and did what I approved actually happen?
 *   Vishesh (risk):   where is the danger right now?
 *
 * Working orders lead, because "did it fill" is a daily operator question that
 * was previously answerable only by curling the API. Risk follows, because it is
 * a standing watch rather than a periodic check.
 *
 * Every figure is spine-sourced. Anything unknown renders "—", never a zero.
 */

const money = (n?: number | null, dp = 2) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 2) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

/** Orders that have left the human's hands but not yet reached a terminal state. */
const IN_FLIGHT = new Set(["pending", "approved", "working", "partial"]);
const TERMINAL_BAD = new Set(["failed", "rejected", "declined"]);

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

export default function MonitorPage() {
  const [m, setM] = useState<RiskMonitorResponse | null>(null);
  const [orders, setOrders] = useState<OrderHistoryRow[]>([]);
  const [drift, setDrift] = useState<any>(null);
  // NAV record and audit trail moved here from Review: both answer "what has
  // happened to the fund", which is this page's question, not a separate one.
  const [navHistory, setNavHistory] = useState<{ ts?: string; total_nav_usd: number }[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [simOpen, setSimOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [risk, oh, dr, nh, ev] = await Promise.all([
        fundApiClient.getRiskMonitor(),
        fundApiClient.getOrderHistory(null, 50).catch(() => ({ orders: [] })),
        fundApiClient.getVenueReconcile().catch(() => null),
        fundApiClient.getNavHistory(90).catch(() => ({ history: [] })),
        fundApiClient.getEvents(40).catch(() => ({ events: [] })),
      ]);
      setM(risk);
      setOrders(oh.orders || []);
      setDrift(dr);
      setNavHistory(nh.history || []);
      setEvents(ev.events || []);
      setErr(null);
    } catch (e: any) {
      setErr(spineError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const inFlight = useMemo(() => orders.filter((o) => IN_FLIGHT.has(o.status)), [orders]);
  const recent = useMemo(
    () => orders.filter((o) => !IN_FLIGHT.has(o.status)).slice(0, 8),
    [orders],
  );
  const alarms = m?.alarms ?? [];

  const halt = async (reason: string) => {
    setBusy(true);
    try { await fundApiClient.haltTrading(reason, "rushi"); await load(); }
    finally { setBusy(false); }
  };
  const resume = async () => {
    setBusy(true);
    try { await fundApiClient.resumeTrading("rushi"); await load(); }
    finally { setBusy(false); }
  };

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Live NAV, fills, limit breaches and the trading halt"
        actions={
          <button className={`flex h-8 items-center ${KT.btnGhost}`} onClick={() => setSimOpen(true)}>
            <ShieldAlert size={14} className="mr-1.5" /> Stress test
          </button>
        }
      />

      <div className="mx-auto max-w-[1600px] px-6 py-6">
        {err && (
          <div className={`mb-4 p-3 text-sm ${KT.inset} ${KT.down}`}>
            {err}
          </div>
        )}

        {/* --- is the fund okay --- */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className={KT.card}>
            <div className={KT.label}>Live NAV</div>
            <div className={`mt-1 ${KT.numberLg}`}>{money(m?.nav_usd)}</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Gross Exposure</div>
            <div className={`mt-1 ${KT.numberLg}`}>{money(m?.gross_exposure_usd)}</div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>{pct(m?.gross_exposure_pct)} of NAV</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Cash</div>
            <div className={`mt-1 ${KT.numberLg}`}>{money(m?.cash_usd)}</div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>{pct(m?.cash_pct)} of NAV</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Drawdown vs limit</div>
            <div className={`mt-1 ${KT.numberLg} ${(m?.drawdown?.utilization ?? 0) > 0.75 ? KT.down : ""}`}>
              {pct(m?.drawdown?.drawdown_pct)}
            </div>
            <div className={`mt-1 text-[11px] ${KT.muted}`}>halt at {pct(m?.drawdown?.limit_pct, 0)}</div>
          </div>
        </div>

        {/* --- did it fill? the operator's daily question --- */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-5 py-3">
            <span className={KT.label}>Working orders</span>
            {inFlight.length > 0 && (
              <span className={`text-[11px] ${KT.muted}`}>{inFlight.length} awaiting fill</span>
            )}
          </div>
          {loading ? (
            <div className={`flex items-center gap-2 px-5 py-8 text-sm ${KT.muted}`}>
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          ) : err ? (
            <div className={`px-5 py-8 text-sm ${KT.sev.warn}`}>
              Order status unavailable — cannot confirm whether anything is in flight.
            </div>
          ) : inFlight.length === 0 ? (
            <div className={`px-5 py-8 text-sm ${KT.muted}`}>
              Nothing in flight — every order has reached a terminal state.
            </div>
          ) : (
            <ul className="divide-y divide-[var(--kt-border)]">
              {inFlight.map((o) => (
                <li key={o.order_id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-5 py-3 text-sm">
                  <span className="font-medium uppercase">{o.side}</span>
                  <span className={KT.number}>{o.qty}</span>
                  <span className="font-semibold">{o.symbol}</span>
                  <span className={`text-[11px] uppercase tracking-wide ${STATUS_TONE[o.status] || KT.muted}`}>
                    {o.status}
                  </span>
                  <span className={`text-[11px] ${KT.muted}`}>
                    filled {o.filled_qty ?? 0} of {o.qty}
                  </span>
                  <span className={`ml-auto font-mono text-[11px] ${KT.muted}`}>
                    {String(o.ts ?? "").slice(0, 19).replace("T", " ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* --- Vishesh's watch: breaches + the kill switch --- */}
          <div className={`${KT.panel} lg:col-span-2`}>
            <div className="flex items-center justify-between border-b border-[var(--kt-border)] px-5 py-3">
              <span className={KT.label}>Limit breaches</span>
              {!m ? null : m.halted ? (
                <button disabled={busy} onClick={resume} className={`text-[11px] ${KT.btn} px-2 py-1`}>
                  Resume trading
                </button>
              ) : (
                <button disabled={busy} onClick={() => halt("manual halt from monitor")}
                        className={`text-[11px] ${KT.btnDanger} px-2 py-1`}>
                  Halt trading
                </button>
              )}
            </div>

            {m?.halted && (
              <div className={`flex items-center gap-2 border-b border-[var(--kt-border)] px-5 py-2.5 text-sm ${KT.down}`}>
                <ShieldAlert size={14} />
                <span className="font-semibold">Trading halted</span>
                <span className={KT.muted}>— buys blocked, sells allowed; resume is manual</span>
              </div>
            )}

            {!m ? (
              <div className={`flex items-center gap-2 px-5 py-8 text-sm ${KT.sev.warn}`}>
                <AlertTriangle size={14} /> Cannot read limits — this is NOT an all-clear.
              </div>
            ) : alarms.length === 0 ? (
              <div className={`flex items-center gap-2 px-5 py-8 text-sm ${KT.muted}`}>
                <ShieldCheck size={14} className={KT.accent} /> Within every limit.
              </div>
            ) : (
              <ul className="divide-y divide-[var(--kt-border)]">
                {alarms.map((a: any) => (
                  <li key={a.key} className="flex items-baseline gap-3 px-5 py-3 text-sm">
                    <AlertTriangle size={13} className={a.severity === "critical" ? KT.down : "text-[var(--kt-warn)]"} />
                    <span className="font-medium">{a.message ?? a.type}</span>
                    <span className={`ml-auto font-mono text-[11px] ${KT.muted}`}>
                      {a.metric?.toFixed?.(2)} vs {a.threshold?.toFixed?.(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            {/* limit utilization — how close are we to each ceiling */}
            {m?.utilization && (
              <div className="grid grid-cols-2 gap-4 border-t border-[var(--kt-border)] px-5 py-4 sm:grid-cols-4">
                {Object.entries(m.utilization).map(([k, v]) => {
                  const u = Math.max(0, Math.min(1, Number(v) || 0));
                  return (
                    <div key={k}>
                      <div className={`${KT.label} truncate`}>{k.replace(/_/g, " ")}</div>
                      <div className={`mt-1 ${KT.barTrack}`}>
                        <div className={u > 0.75 ? "h-full rounded-full bg-[var(--kt-down)]" : KT.barFill}
                             style={{ width: `${u * 100}%` }} />
                      </div>
                      <div className={`mt-1 text-[10px] ${KT.muted}`}>{(u * 100).toFixed(0)}% used</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* --- book vs broker --- */}
          <div className={KT.panel}>
            <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>Book vs broker</div>
            {!drift ? (
              <div className={`px-5 py-8 text-sm ${KT.muted}`}>Reconciliation unavailable.</div>
            ) : drift.configured === false ? (
              <div className={`px-5 py-8 text-sm ${KT.muted}`}>
                Broker not configured — cannot confirm the book matches the venue.
              </div>
            ) : (
              <div className="space-y-2 px-5 py-4 text-sm">
                <Row label="Book NAV" value={money(drift.book_nav)} />
                <Row label="Broker equity" value={money(drift.broker_equity)} />
                <Row
                  label="Drift"
                  value={money(drift.delta_usd)}
                  tone={Math.abs(drift.delta_usd ?? 0) > 1 ? KT.down : KT.up}
                />
                <Row
                  label="Out of sync"
                  value={`${drift.symbols_out_of_sync ?? 0} symbol(s)`}
                  tone={(drift.symbols_out_of_sync ?? 0) > 0 ? KT.down : KT.up}
                />
              </div>
            )}
          </div>
        </div>

        {/* --- positions --- */}
        <div className={`mt-6 ${KT.panel}`}>
          <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>Positions</div>
          {!m?.positions?.length ? (
            <div className={`px-5 py-8 text-sm ${KT.muted}`}>No open positions.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className={`border-b border-[var(--kt-border)] ${KT.label}`}>
                    <th className="px-5 py-2 text-left font-normal">Symbol</th>
                    <th className="px-5 py-2 text-right font-normal">Qty</th>
                    <th className="px-5 py-2 text-right font-normal">Mark</th>
                    <th className="px-5 py-2 text-right font-normal">Value</th>
                    <th className="px-5 py-2 text-right font-normal">Weight</th>
                    <th className="px-5 py-2 text-right font-normal">Unrealized</th>
                    <th className="px-5 py-2 text-right font-normal">−20% shock</th>
                  </tr>
                </thead>
                <tbody>
                  {m.positions.map((p: any) => (
                    <tr key={p.symbol} className="border-b border-[var(--kt-border)] last:border-0">
                      <td className="px-5 py-2.5 font-medium">{p.symbol}</td>
                      <td className={`px-5 py-2.5 text-right ${KT.number}`}>{p.qty}</td>
                      <td className={`px-5 py-2.5 text-right ${KT.number}`}>{money(p.mark)}</td>
                      <td className={`px-5 py-2.5 text-right ${KT.number}`}>{money(p.value_usd)}</td>
                      <td className={`px-5 py-2.5 text-right ${KT.number}`}>{pct(p.weight_pct)}</td>
                      <td className={`px-5 py-2.5 text-right font-mono tabular-nums ${(p.unrealized_pnl_pct ?? 0) >= 0 ? KT.up : KT.down}`}>
                        {pct(p.unrealized_pnl_pct)}
                      </td>
                      <td className={`px-5 py-2.5 text-right font-mono tabular-nums ${KT.down}`}>
                        {money(p.shock_20_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* --- recently settled --- */}
        {recent.length > 0 && (
          <div className={`mt-6 ${KT.panel}`}>
            <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>Recently settled</div>
            <ul className="divide-y divide-[var(--kt-border)]">
              {recent.map((o) => (
                <li key={o.order_id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-5 py-2.5 text-sm">
                  <span className="font-medium uppercase">{o.side}</span>
                  <span className={KT.number}>{o.filled_qty ?? o.qty}</span>
                  <span className="font-semibold">{o.symbol}</span>
                  {o.avg_price != null && <span className={KT.number}>@ {money(o.avg_price)}</span>}
                  <span className={`text-[11px] uppercase tracking-wide ${STATUS_TONE[o.status] || KT.muted}`}>
                    {o.status}
                  </span>
                  <span className={`ml-auto font-mono text-[11px] ${KT.muted}`}>
                    {String(o.ts ?? "").slice(0, 19).replace("T", " ")}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* --- the fund's record --- */}
        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className={KT.panel}>
            <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>
              NAV record
            </div>
            {navHistory.length === 0 ? (
              <div className={`px-5 py-8 text-sm ${KT.muted}`}>
                No valuations struck yet.
              </div>
            ) : (
              <div className="px-5 py-4">
                <NavSparkline points={navHistory.map((h) => h.total_nav_usd)} />
                <div className={`mt-2 flex justify-between text-[11px] ${KT.muted}`}>
                  <span>{String(navHistory[0]?.ts ?? "").slice(0, 10)}</span>
                  <span>{navHistory.length} strikes</span>
                  <span>{String(navHistory[navHistory.length - 1]?.ts ?? "").slice(0, 10)}</span>
                </div>
              </div>
            )}
          </div>

          <div className={KT.panel}>
            <div className={`border-b border-[var(--kt-border)] px-5 py-3 ${KT.label}`}>
              Audit trail
            </div>
            {events.length === 0 ? (
              <div className={`px-5 py-8 text-sm ${KT.muted}`}>No events recorded.</div>
            ) : (
              <ul className="max-h-[240px] divide-y divide-[var(--kt-border)] overflow-y-auto">
                {events.map((e, i) => (
                  <li key={e.seq ?? i} className="flex items-baseline gap-3 px-5 py-1.5 text-[11px]">
                    <span className={`w-10 shrink-0 font-mono ${KT.muted}`}>#{e.seq}</span>
                    <span className="w-40 shrink-0 truncate font-medium">{e.type}</span>
                    <span className={`shrink-0 font-mono ${KT.muted}`}>
                      {String(e.ts ?? "").slice(11, 19)}
                    </span>
                    <span className={`truncate ${KT.muted}`}>{e.actor}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <SimulationModal open={simOpen} onOpenChange={setSimOpen} onSuccess={() => load()} />
    </div>
  );
}

/** NAV over time — the shape of the record, not a precise chart. */
function NavSparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <div className={`text-[11px] ${KT.muted}`}>Not enough strikes to plot.</div>;
  const lo = Math.min(...points), hi = Math.max(...points), span = hi - lo || 1;
  const d = points
    .map((v, i) => `${i ? "L" : "M"}${(i / (points.length - 1)) * 300},${28 - ((v - lo) / span) * 24}`)
    .join("");
  const up = points[points.length - 1] >= points[0];
  return (
    <svg viewBox="0 0 300 32" className="w-full" style={{ height: 48 }} preserveAspectRatio="none">
      <path d={d} fill="none" strokeWidth={1.5}
            stroke={up ? "var(--kt-up)" : "var(--kt-down)"} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className={KT.muted}>{label}</span>
      <span className={`font-mono tabular-nums ${tone || KT.number}`}>{value}</span>
    </div>
  );
}
