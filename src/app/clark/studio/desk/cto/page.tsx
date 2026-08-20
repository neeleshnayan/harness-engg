"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { fundApiClient, DeskView, SpineEvent } from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import { SeatFace } from "../SeatFace";
import { estimateCostUsd, fmtAt, fmtUsd, isSeat } from "../seatLib";

/**
 * The CTO's desk — what waits on Fable's hands, and what the bench costs.
 *
 * Lean v1 (docs/briefs/EXEC_DESKS_2026-08-20.md; the builder upgrades it).
 * Everything here is CTO WORK, not CEO decisions: the dispatch queue (with
 * CEO-approved asks leading), unresolved dispatches, the accepted-but-unbuilt
 * backlog, and the week's dispatch economics.
 */
export default function CtoDeskPage() {
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [events, setEvents] = useState<SpineEvent[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [d, ev] = await Promise.allSettled([
      fundApiClient.getDesk(),
      fundApiClient.getEvents(1000, 0),
    ]);
    if (d.status === "fulfilled") { setDesk(d.value); setErr(null); }
    else setErr(d.reason instanceof Error ? d.reason.message : "unreachable");
    setEvents(ev.status === "fulfilled" ? (ev.value.events || []) : null);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const queue = (desk?.requests ?? []).filter((r) => r.status !== "resolved")
    // CEO-approved asks lead: they are cleared for trigger.
    .sort((a, b) => (a.status === "approved" ? -1 : 0) - (b.status === "approved" ? -1 : 0));

  const unresolvedDispatches = useMemo(() => {
    if (!events) return null;
    const resolved = new Set(
      events.filter((e) => e.type === "DeskRequestResolved")
            .map((e) => (e.payload as { request_id?: string })?.request_id));
    return events.filter((e) => e.type === "DeskDispatched")
      .map((e) => e.payload as { task_id?: string; seat?: string; task?: string; at?: string })
      .filter((p) => p.task_id && !resolved.has(p.task_id));
  }, [events]);

  const backlog = useMemo(() => (desk?.runs ?? []).flatMap((run) =>
    (run.recommendations ?? [])
      .filter((r) => r.status === "accepted"
                     && ["fix", "harness", "envelope_v2", "infra", "code_fix",
                         "measurement", "dispatch"].includes(r.kind ?? ""))
      .map((r) => ({ ...r, run_id: run.run_id }))), [desk]);

  const weekCost = useMemo(() => {
    const cutoff = Date.now() - 7 * 86400_000;
    let usd = 0, tokens = 0, priced = 0, runs = 0;
    for (const run of desk?.runs ?? []) {
      const at = run.resolved_at ? Date.parse(run.resolved_at) : NaN;
      if (Number.isNaN(at) || at < cutoff) continue;
      runs += 1;
      if (run.tokens != null) tokens += run.tokens;
      const c = estimateCostUsd(run.model, run.tokens);
      if (c != null) { usd += c; priced += 1; }
    }
    return { usd, tokens, priced, runs };
  }, [desk]);

  return (
    <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
      <StudioHeader subtitle="The CTO's desk — the build and dispatch queue, and what the bench costs" />
      <div className={KT.container}>
        <header className="mb-7 flex items-center gap-4">
          <SeatFace actor="cto" size={64} />
          <div>
            <p className={KT.label}>Krypton Fund · the console</p>
            <h1 className="text-2xl font-medium tracking-tight">Fable · CTO</h1>
            <p className={`mt-0.5 text-xs ${KT.muted}`}>
              bench, last 7 days: {weekCost.runs} runs ·{" "}
              <span className="font-mono tabular-nums">
                {weekCost.tokens ? `${Math.round(weekCost.tokens / 1000)}k tokens` : "no tokens recorded"}
              </span>{" "}
              · {fmtUsd(weekCost.priced ? weekCost.usd : null)} est.
              ({weekCost.priced} of {weekCost.runs} runs priced)
              {" "}· <Link href="/clark/studio/desk" className={`${KT.accent} hover:underline`}>back to the floor</Link>
            </p>
          </div>
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">The desk could not be read — the queue is unknown, not empty. {err}</p>
          </div>
        )}

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>The dispatch queue ({queue.length})</p>
          {desk && queue.length === 0 && (
            <p className={`text-sm ${KT.muted}`}>Empty — every filed ask has been triggered and resolved.</p>
          )}
          <div className="space-y-1.5">
            {queue.map((r) => (
              <div key={r.request_id}
                   className={`${KT.card} flex flex-wrap items-center gap-x-3 gap-y-1 p-3 text-sm`}>
                <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px]">
                  <SeatFace actor={(r.actor || "").trim()} size={18} decorative />
                  asks
                  <SeatFace actor={r.serves} size={18} decorative />
                  {isSeat(r.serves)
                    ? <Link href={`/clark/studio/desk/${r.serves}`} className={`${KT.accent} hover:underline`}>{r.serves}</Link>
                    : r.serves}
                </span>
                <span className="min-w-0 flex-1 text-[13px]">{r.subject}</span>
                {r.at && <span className={`font-mono text-[10px] ${KT.muted}`}>{fmtAt(r.at)}</span>}
                {r.status === "approved" ? (
                  <span className="shrink-0 rounded-full border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-accent)]">
                    CEO-approved — trigger it
                  </span>
                ) : (
                  <span className={`shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
                    awaiting CEO approval
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>Dispatched, not yet resolved</p>
          {unresolvedDispatches === null ? (
            <p className={`text-sm ${KT.sev.warn}`}>Event log unreadable — in-flight work is unknown, not none.</p>
          ) : unresolvedDispatches.length === 0 ? (
            <p className={`text-sm ${KT.muted}`}>Nothing in flight — every dispatch has been resolved.</p>
          ) : (
            <div className="space-y-1.5">
              {unresolvedDispatches.map((p) => (
                <div key={p.task_id} className={`${KT.card} flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm`}>
                  <span className="font-mono text-[11px] text-[var(--kt-accent)]">{p.seat}</span>
                  <span className="min-w-0 flex-1 truncate text-[13px]">{p.task}</span>
                  {p.at && <span className={`font-mono text-[10px] ${KT.muted}`}>{fmtAt(p.at)}</span>}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="mb-8">
          <p className={`${KT.label} mb-2`}>
            Accepted, not yet built ({backlog.length})
          </p>
          <p className={`mb-2 text-xs ${KT.muted}`}>
            CEO-accepted recommendations of buildable kinds — the CTO&apos;s backlog,
            straight from the flight recorder.
          </p>
          {desk && backlog.length === 0 && (
            <p className={`text-sm ${KT.muted}`}>Empty — everything accepted has been implemented.</p>
          )}
          <div className="space-y-1.5">
            {backlog.map((r) => (
              <div key={`${r.run_id}-${r.rec_id}`} className={`${KT.card} flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm`}>
                <span className="flex shrink-0 items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--kt-agent)]">
                  <SeatFace actor={r.seat} size={14} decorative /> {r.seat} · rec {r.rec_id}
                </span>
                <span className="min-w-0 flex-1 text-[13px] leading-snug">{r.text}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
