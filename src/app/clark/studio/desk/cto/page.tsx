"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { fundApiClient, DeskView } from "@/lib/fund_api";
import { KT } from "../../theme";
import { StudioHeader } from "../../components/StudioHeader";
import { SeatFace } from "../SeatFace";
import { estimateCostUsd, fmtUsd, SEATS } from "../seatLib";
import { CooTriageChip } from "../components";
import { consoleQueue } from "../consoleQueue.ts";
import { QueueRow } from "../QueueRow";
import { benchFlight, seatLamps } from "../seatActivity.ts";
import { fmtTokensShort } from "../briefing.ts";

/**
 * THE CONSOLE — what is on the chair's hands, ranked, as rows.
 *
 * Rebuilt 2026-08-27 against the CEO-approved Main board (*"Cool lets get
 * this"*) and his ranking decision the same day (*"can we add ordering to my
 * desk say high-priority to low; time-sensitive or not; blocker or not?"*).
 *
 * WHAT CHANGED AND WHY, because the old page was not wrong so much as unusable:
 * it rendered three separate stacks of cards — queued asks, unresolved
 * dispatches, accepted-not-built — each card a paragraph tall, none of them
 * ranked against each other. The chair's real question is *what do I fire
 * next*, and answering it meant reading three lists and doing the merge by eye.
 * Measured on the live record the day this was written: 55 approved asks
 * awaiting a trigger, the oldest 142 hours old, indistinguishable on screen
 * from the newest.
 *
 * So: ONE ranked list over both populations, the band from the record on every
 * row, prose one tap down, and an honest tail that says what it is hiding and
 * why. The in-flight lamps move to the top as three numbers, because "is a slot
 * free" is the other question this page exists to answer — and it now answers
 * it with EVERY open dispatch rather than one per seat.
 */
export default function CtoDeskPage() {
  const [desk, setDesk] = useState<DeskView | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setDesk(await fundApiClient.getDesk()); setErr(null); }
    catch (e) { setDesk(null); setErr(e instanceof Error ? e.message : "unreachable"); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  /* The queue. `null` where the read FAILED and `[]` where it succeeded and
     held nothing — the fold reports the difference, and the note below prints
     it. Passing `[]` for an unread payload is the absence-as-zero this whole
     surface is written against. */
  const queue = useMemo(() => consoleQueue(
    desk ? desk.requests : null,
    desk ? (desk.open_recommendations as unknown as Record<string, unknown>[]) : null,
  ), [desk]);

  /* THE ROOM'S TRUTH, on the console too. Every open dispatch per seat, not
     one per seat — the CEO's own observation, 2026-08-27: "1 builder working
     but 2 in reality". */
  const lamps = useMemo(() => SEATS.map((s) =>
    seatLamps(s, desk?.roster?.find((r) => r.agent === s)?.activity ?? null)),
    [desk]);
  const flight = useMemo(() => benchFlight(lamps), [lamps]);
  const running = useMemo(
    () => lamps.filter((l) => l.lamps.length > 0), [lamps]);

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
      <StudioHeader subtitle="The console — what is on your hands, ranked" />
      <div className={KT.container}>

        {/* ============ HEADER: three numbers, one line of cost ============ */}
        <header className="mb-7 flex flex-wrap items-end gap-x-10 gap-y-4">
          <div className="flex items-center gap-3">
            <SeatFace actor="cto" size={44} decorative />
            <div className="flex flex-col gap-1">
              <span className={KT.label}>The console · Fable</span>
              <div className="flex items-baseline gap-2">
                <span className={KT.hero}>
                  {desk === null ? "—" : queue.total}
                </span>
                <span className="text-[13px] text-[var(--kt-text-dim)]">
                  cleared to trigger
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-1 pb-1">
            <div className="flex items-baseline gap-2">
              <span className={KT.numberLg}>
                {desk === null ? "—" : flight.working}
              </span>
              <span className="text-xs text-[var(--kt-text-dim)]">
                running now{flight.isFloor ? " (at least)" : ""}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-1 pb-1">
            <div className="flex items-baseline gap-2">
              <span className={`font-mono tabular-nums text-2xl font-light ${flight.awaiting > 0 ? "text-[var(--kt-warn)]" : "text-[var(--kt-text-strong)]"}`}>
                {desk === null ? "—" : flight.awaiting}
              </span>
              <span className="text-xs text-[var(--kt-text-dim)]">
                back, waiting on your review
              </span>
            </div>
          </div>

          <div className="ml-auto flex flex-col items-end gap-1 pb-1">
            {desk?.desk_load && <CooTriageChip load={desk.desk_load} />}
            <span className={`font-mono text-[11px] ${KT.muted}`}>
              {desk === null
                ? "what the bench cost this week is unknown, not nothing"
                : `bench, 7 days · ${weekCost.runs} runs · ${weekCost.tokens ? fmtTokensShort(weekCost.tokens) : "no token totals filed"} · ${fmtUsd(weekCost.priced ? weekCost.usd : null)} (${weekCost.priced} of ${weekCost.runs} priced)`}
            </span>
          </div>
        </header>

        {err && (
          <div className={`${KT.card} mb-6 flex items-start gap-2 border-[var(--kt-warn)]`}>
            <AlertTriangle size={15} className="mt-0.5 text-[var(--kt-warn)]" />
            <p className="text-sm">
              We could not reach the fund&apos;s record, so this page is showing
              nothing rather than a clear board. {err}
            </p>
          </div>
        )}

        {/* ============ THE QUEUE ============ */}
        <section className="mb-8">
          <div className="mb-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className={KT.label}>Cleared to trigger</span>
            <span className={`text-[11px] ${KT.muted}`}>{queue.note}</span>
          </div>

          <div className={`${KT.panel} overflow-hidden`}>
            {queue.rows.length === 0 ? (
              <p className={`px-5 py-4 text-sm ${desk === null ? KT.sev.warn : KT.muted}`}>
                {desk === null
                  ? "The queue is unknown, not empty."
                  : "Nothing is waiting on you."}
              </p>
            ) : (
              queue.rows.map((r, i) => (
                <QueueRow key={r.id} row={r} last={i === queue.rows.length - 1 && !queue.tailNote} />
              ))
            )}
            {queue.tailNote && (
              <div className="flex items-center justify-between border-t border-[var(--kt-border)] bg-[var(--kt-inset)] px-5 py-3">
                <span className={`text-xs ${KT.muted}`}>{queue.tailNote}</span>
                <span className={`font-mono text-[11px] ${KT.muted}`}>
                  all {queue.total} in the fund&apos;s record
                </span>
              </div>
            )}
          </div>
        </section>

        {/* ============ IN FLIGHT ============ */}
        <section className="mb-8">
          <div className="mb-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className={KT.label}>
              In flight · {desk === null ? "unknown" : flight.working + flight.awaiting}
            </span>
            <span className={`text-[11px] ${KT.muted}`}>{flight.note}</span>
          </div>
          {running.length === 0 ? (
            <p className={`text-sm ${desk === null ? KT.sev.warn : KT.muted}`}>
              {desk === null
                ? "What the bench is doing is unknown, not nothing."
                : "Nothing is running. A bench sitting idle costs the fund nothing."}
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {running.flatMap((seat) => seat.lamps.map((l, i) => (
                <Link key={`${seat.seat}-${l.taskId ?? i}`}
                      href={`/clark/studio/desk/${seat.seat}`}
                      className={`${KT.panel} ${KT.cardHover} flex flex-col gap-1.5 p-3.5`}>
                  <div className="flex items-center gap-2">
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${l.state === "working" ? "bg-[var(--kt-warn)]" : "bg-[var(--kt-accent)]"}`} />
                    <span className="text-[13px] font-semibold text-[var(--kt-text-strong)]">
                      {seat.seat}
                    </span>
                    <span className={`ml-auto font-mono text-[10px] tabular-nums ${KT.muted}`}>
                      {l.since ? sinceLabel(l.since) : "no start time on record"}
                    </span>
                  </div>
                  <span className="text-xs leading-snug text-[var(--kt-text-dim)]">
                    {l.task ?? "This job was started with no description on the record."}
                  </span>
                  {l.state === "awaiting_review" && (
                    <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${KT.accent}`}>
                      back — waiting on your review
                    </span>
                  )}
                  {!l.reviewDetectable && l.state === "working" && (
                    <span className={`text-[10px] ${KT.muted}`}>
                      We cannot tell whether this has come back yet.
                    </span>
                  )}
                </Link>
              )))}
            </div>
          )}
        </section>

        <p className={`text-xs ${KT.muted}`}>
          <Link href="/clark/studio/desk" className={`${KT.accent} hover:underline`}>
            back to the floor
          </Link>
          {" · "}The fund records what was asked and what came back. It does not
          run the agents, and nothing on this page starts one.
        </p>
      </div>
    </div>
  );
}

/** How long ago, said the way a person says it. Absent stays absent. */
function sinceLabel(at: string): string {
  const t = Date.parse(at);
  if (Number.isNaN(t)) return "start time unreadable";
  const m = (Date.now() - t) / 60_000;
  if (m < 0) return "start time is in the future";
  if (m < 60) return `${Math.round(m)}m`;
  if (m < 1440) return `${(m / 60).toFixed(1)}h`;
  return `${(m / 1440).toFixed(1)}d`;
}
