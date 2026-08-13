"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle, ArrowRight, ShieldAlert, ShieldCheck,
} from "lucide-react";
import { spineError } from "@/lib/spine_error";
import { StudioHeader } from "./components/StudioHeader";
import { ApprovalQueue } from "./components/ApprovalQueue";
import { OrderFlow } from "./components/OrderFlow";
import { SignalsPanel } from "./components/SignalsPanel";
import { MonitorGraphs } from "./components/MonitorGraphs";
import { HaltControl } from "./components/HaltControl";
import { LimitsEditor } from "./components/LimitsEditor";
import { SystemStatus } from "./components/SystemStatus";
import { SimulationModal } from "./components/SimulationModal";
import { KT } from "./theme";
import { OrderHistoryRow, RiskMonitorResponse, fundApiClient } from "@/lib/fund_api";

/**
 * MONITOR — the landing page, and the answer to "I have five minutes".
 *
 * The Studio used to open on Decide, which showed only the approval queue. That
 * made the rarest event in the fund the first thing you saw, and pushed
 * everything an operator actually checks — is it halted, did it fill, is it
 * within limits, is our book the broker's book — one click away.
 *
 * So this page is ordered by what a short check must not miss, hardest question
 * first:
 *
 *   1. Is anything BROKEN?          halt state, breaches, ledger-vs-broker drift
 *   2. Is anything waiting on ME?   the approval queue
 *   3. What is the fund worth?      NAV, exposure, cash, drawdown against limit
 *   4. Did what I approved happen?  working orders
 *   5. What do the strategies want? signals, before anyone proposes them
 *
 * Deeper work has its own surfaces and is deliberately NOT here: sizing and
 * attribution on Allocate, structural risk on Risk, research and theses on Lab.
 *
 * Every figure is spine-sourced. Anything unknown renders "—", never a zero, and
 * an unreadable spine says so rather than showing an all-clear.
 */

const money = (n?: number | null, dp = 2) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 2) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

export default function MonitorHome() {
  const [m, setM] = useState<RiskMonitorResponse | null>(null);
  const [orders, setOrders] = useState<OrderHistoryRow[]>([]);
  const [drift, setDrift] = useState<Awaited<ReturnType<typeof fundApiClient.getVenueReconcile>> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [simOpen, setSimOpen] = useState(false);
  // One refresh signal shared by every panel. Each panel owns its own data, so
  // without this an action in one left the others showing the world as it was
  // before it — propose an order and the queue above still read "nothing
  // awaiting you" until its own timer came round.
  const [tick, setTick] = useState(0);
  const queueRef = React.useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const [risk, oh, dr] = await Promise.all([
        fundApiClient.getRiskMonitor(),
        fundApiClient.getOrderHistory(null, 50).catch(() => ({ orders: [] })),
        fundApiClient.getVenueReconcile().catch(() => null),
      ]);
      setM(risk);
      setOrders(oh.orders || []);
      setDrift(dr);
      setErr(null);
    } catch (e: unknown) {
      setM(null);              // unknown, never an implied all-clear
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

  /** Something changed the book — refresh this page AND every panel on it. */
  const bump = useCallback(() => { setTick((t) => t + 1); load(); }, [load]);

  /** After proposing from the signals panel at the bottom, take the operator to
   *  the queue so they SEE the order land. Previously the proposal appeared far
   *  above the fold and the click looked like it had done nothing. */
  const showQueue = useCallback(() => {
    bump();
    queueRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [bump]);

  const alarms = m?.alarms ?? [];
  const critical = alarms.filter((a: { severity?: string }) => a.severity === "critical");
  // `symbols_out_of_sync` is the reconciler's own count; anything above zero
  // means our positions and the broker's have diverged.
  const outOfSync = (drift?.symbols_out_of_sync ?? 0) > 0;

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Everything that needs you, in one screen"
        actions={
          <button className={`flex h-8 items-center ${KT.btnGhost}`} onClick={() => setSimOpen(true)}>
            <ShieldAlert size={14} className="mr-1.5" /> Stress test
          </button>
        }
      />

      <div id="top" className="mx-auto max-w-[1600px] px-6 py-6">
        {/* 1 — IS ANYTHING BROKEN? Loudest thing on the page, or absent. */}
        {err && (
          <div className={`mb-4 flex items-start gap-2 p-3 text-sm ${KT.inset} ${KT.down}`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Cannot read the spine</div>
              <div className={`mt-0.5 ${KT.muted}`}>{err}</div>
              <div className="mt-1 text-[11px]">
                This is not an all-clear. The fund&apos;s state is unknown from here.
              </div>
            </div>
          </div>
        )}

        {m?.halted && (
          <div className={`mb-4 flex items-center gap-2 p-3 text-sm ${KT.inset} ${KT.down}`}>
            <ShieldAlert size={15} />
            <span className="font-semibold">Trading halted</span>
            <span className={KT.muted}>— buys blocked, sells allowed; resume is manual</span>
            <a href="#killswitch" className={`ml-auto text-[11px] ${KT.accent} underline underline-offset-2`}>
              resume at the kill switch below
            </a>
          </div>
        )}

        {outOfSync && (
          <div className={`mb-4 flex items-start gap-2 p-3 text-sm ${KT.inset} ${KT.sev.warn}`}>
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Our book disagrees with the broker</div>
              <div className={`mt-0.5 text-[11px] ${KT.muted}`}>
                {drift?.symbols_out_of_sync} position(s) differ. NAV is never overwritten
                from the broker — investigate before trading on it.
              </div>
            </div>
          </div>
        )}

        {critical.length > 0 && (
          <div className={`mb-4 p-3 ${KT.inset} ${KT.down}`}>
            <div className="flex items-center gap-2 text-sm font-medium">
              <AlertTriangle size={15} /> {critical.length} critical breach{critical.length === 1 ? "" : "es"}
            </div>
            <ul className={`mt-1.5 space-y-0.5 text-[12px] ${KT.muted}`}>
              {critical.map((a: { key?: string; message?: string; type?: string }) => (
                <li key={a.key}>· {a.message ?? a.type}</li>
              ))}
            </ul>
          </div>
        )}

        {/* ── FLOW: everything moving through the fund, top to bottom in the
              order it actually moves. Approvals, then what each one became,
              then what the strategies want next. These were scattered down the
              page with metrics and breaches wedged between them, which broke
              the one story an operator is trying to follow. ── */}
        <div ref={queueRef} className="scroll-mt-24 space-y-4">
          {/* One frame, two halves: what is waiting on a decision, and what
              that decision became. They were stacked as separate panels, which
              read as two unrelated lists rather than the two ends of the same
              journey — an order leaves the left side and appears on the right. */}
          <div className={KT.panel}>
            <div className="flex items-center gap-2 border-b border-[var(--kt-border)] px-5 py-2">
              <span className={KT.label}>Order flow</span>
              <span className={`flex items-center gap-1.5 text-[11px] ${KT.muted}`}>
                your decision <ArrowRight size={11} /> the venue
              </span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2">
              <div className="border-b border-[var(--kt-border)] lg:border-b-0 lg:border-r">
                <ApprovalQueue onChanged={bump} refreshSignal={tick} embedded />
              </div>
              <div>
                <OrderFlow orders={orders} loading={loading} error={err} embedded />
              </div>
            </div>
          </div>

          <SignalsPanel onProposed={showQueue} bookChanged={tick} />
        </div>

        {/* ── STATE: what the fund is, right now. ── */}
        <div className="mt-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className={KT.card}>
            <div className={KT.label}>Live NAV</div>
            <div className={`mt-1 ${KT.numberLg}`}>{money(m?.nav_usd)}</div>
          </div>
          <div className={KT.card}>
            <div className={KT.label}>Gross exposure</div>
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

        <div className="mt-4">
          <MonitorGraphs m={m} />
        </div>

        {/* Breaches as a list — the graphs above show a limit being APPROACHED,
            this says which are actually crossed. */}
        <div className={`mt-4 ${KT.panel}`}>
          <div className="border-b border-[var(--kt-border)] px-5 py-3">
            <span className={KT.label}>Limit breaches</span>
          </div>
          {!m ? (
            <div className={`flex items-center gap-2 px-5 py-6 text-sm ${KT.sev.warn}`}>
              <AlertTriangle size={14} /> Cannot read limits — this is NOT an all-clear.
            </div>
          ) : alarms.length === 0 ? (
            <div className={`flex items-center gap-2 px-5 py-6 text-sm ${KT.muted}`}>
              <ShieldCheck size={14} className={KT.accent} /> Within every limit.
            </div>
          ) : (
            <ul className="divide-y divide-[var(--kt-border)]">
              {alarms.map((a: { key?: string; severity?: string; message?: string; type?: string; metric?: number; threshold?: number }) => (
                <li key={a.key} className="flex items-baseline gap-3 px-5 py-2.5 text-sm">
                  <AlertTriangle size={13} className={a.severity === "critical" ? KT.down : "text-[var(--kt-warn)]"} />
                  <span className="font-medium">{a.message ?? a.type}</span>
                  <span className={`ml-auto font-mono text-[11px] ${KT.muted}`}>
                    {a.metric?.toFixed?.(2)} vs {a.threshold?.toFixed?.(2)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-4">
          <LimitsEditor onChanged={bump} />
        </div>

        {/* ── LAST: the kill switch, out of reach of a routine scan. ── */}
        <div id="killswitch" className="mt-8 scroll-mt-24">
          <HaltControl halted={m ? m.halted : undefined} onChanged={bump} />
        </div>

        <div className="mt-8">
          <SystemStatus refreshSignal={tick} />
        </div>

        <div className={`mt-6 flex flex-wrap gap-2 text-[11px] ${KT.muted}`}>
          <span>Deeper work:</span>
          <Link href="/clark/studio/allocate" className={KT.accent}>sizing &amp; attribution</Link>
          <span>·</span>
          <Link href="/clark/studio/risk" className={KT.accent}>structural risk</Link>
          <span>·</span>
          <Link href="/clark/studio/lab" className={KT.accent}>research &amp; theses</Link>
        </div>
      </div>

      <SimulationModal open={simOpen} onOpenChange={setSimOpen} onSuccess={load} />
    </div>
  );
}
