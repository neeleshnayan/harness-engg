"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";
import { fundApiClient, RiskMonitorResponse } from "@/lib/fund_api";
import { KT } from "../theme";

/**
 * Always-on risk strip, rendered under the header on every Studio page.
 *
 * Capital preservation is the fund's first priority, and a breach you have to
 * navigate to is a breach you find late — so halt state, drawdown-vs-limit and
 * active limit breaches follow the user everywhere. Never dismissible.
 *
 * Reads GET /fund/risk/monitor, which is a pure read (it writes no events).
 * Shows an honest "unreachable" state rather than implying all-clear when the
 * spine is down — silence must never look like safety.
 */
/**
 * The strip's own sentence for an unreachable monitor.
 *
 * Exported so the floor can say EXACTLY what the strip says on a dead spine
 * (CDO spec, Deliverable B) instead of carrying a second, softer copy. Two
 * renderings of one sentence is two things to drift, and the softer one always
 * wins the argument with a reader who wants reassurance.
 */
export const RISK_UNREACHABLE = {
  head: "Risk monitor unreachable",
  tail: "cannot confirm limits are being enforced",
} as const;

export const RISK_UNREACHABLE_SENTENCE =
  `${RISK_UNREACHABLE.head} — ${RISK_UNREACHABLE.tail}.`;

export function RiskBar({ pollMs = 30000 }: { pollMs?: number }) {
  const [m, setM] = useState<RiskMonitorResponse | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fundApiClient.getRiskMonitor();
        if (alive) { setM(r); setErr(false); }
      } catch {
        if (alive) setErr(true);
      }
    };
    load();
    const t = setInterval(load, pollMs);
    return () => { alive = false; clearInterval(t); };
  }, [pollMs]);

  if (err) {
    return (
      <Bar tone="warn">
        <AlertTriangle size={13} />
        <span className="font-medium">{RISK_UNREACHABLE.head}</span>
        <span className={KT.muted}>— {RISK_UNREACHABLE.tail}</span>
      </Bar>
    );
  }

  if (!m) {
    return (
      <Bar tone="idle">
        <span className={KT.muted}>Loading risk state…</span>
      </Bar>
    );
  }

  const alarms = m.alarms ?? [];
  const critical = alarms.filter((a) => a.severity === "critical").length;
  const dd = m.drawdown;
  const tone: Tone = m.halted || critical > 0 ? "critical" : alarms.length > 0 ? "warn" : "ok";

  return (
    <Bar tone={tone}>
      {m.halted ? (
        <>
          <ShieldAlert size={13} />
          <span className="font-semibold uppercase tracking-wide">Trading halted</span>
          <span className={KT.muted}>— buys blocked, sells allowed; resume is manual</span>
        </>
      ) : (
        <>
          {tone === "ok" ? <ShieldCheck size={13} /> : <AlertTriangle size={13} />}
          <span className="font-medium">
            {alarms.length === 0 ? "Within limits" : `${alarms.length} active limit breach${alarms.length > 1 ? "es" : ""}`}
          </span>
        </>
      )}

      {dd && (
        <span className={`ml-1 ${KT.muted}`}>
          drawdown{" "}
          <span className="font-mono tabular-nums text-[var(--kt-text)]">
            {dd.drawdown_pct?.toFixed(2)}%
          </span>{" "}
          of {dd.limit_pct?.toFixed(0)}% limit
        </span>
      )}

      {alarms.length > 0 && (
        <span className="truncate">· {alarms[0].message ?? alarms[0].type}</span>
      )}

      <Link href="/clark/studio/monitor" className="ml-auto shrink-0 underline underline-offset-2">
        {m.halted || alarms.length ? "Review" : "Monitor"}
      </Link>
    </Bar>
  );
}

type Tone = "ok" | "warn" | "critical" | "idle";

const TONE: Record<Tone, string> = {
  ok: "border-[var(--kt-border)] text-[var(--kt-text-dim)]",
  idle: "border-[var(--kt-border)] text-[var(--kt-text-muted)]",
  warn: "border-[var(--kt-warn)]/40 bg-[var(--kt-warn)]/10 text-[var(--kt-warn)]",
  critical: "border-[var(--kt-down)]/50 bg-[var(--kt-down)]/10 text-[var(--kt-down)]",
};

function Bar({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <div className={`border-b ${TONE[tone]}`}>
      <div className="mx-auto flex max-w-[1600px] items-center gap-2 px-6 py-1.5 text-[11px]">
        {children}
      </div>
    </div>
  );
}
