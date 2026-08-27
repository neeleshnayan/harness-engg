"use client";

import React from "react";
import { KT } from "../theme";
import type { SeatLamps } from "./seatActivity.ts";

/**
 * WHAT THIS SEAT IS RUNNING — every job, not the newest one.
 *
 * The CEO on the floor, 2026-08-27, verbatim: *"1 builder working but 2 in
 * reality"*. The room drew one lamp per seat because the record served one
 * job per seat. Both halves ship together; this is the half a person sees.
 *
 * DOES THIS FORM SERVE THIS CONTENT BETTER THAN A GENERIC LIST WOULD? The
 * content is a small set of concurrent things, each with a state, an age and a
 * sentence — and the question a reader has is *how many, and for how long*. So
 * the state is a dot (comparable down a column at a glance), the age is
 * right-aligned `tabular-nums` (comparable as digits), and the sentence takes
 * the remaining width. A generic list would put the sentence first and make
 * the two comparable facts un-scannable, which is what the old room did.
 *
 * THE BASIS LINE IS NOT DECORATION. A record that predates the fold reports
 * only the newest job, and this component says so rather than showing one row
 * and letting it read as the whole truth.
 */
export function OpenJobs({ lamps, compact = false }: {
  lamps: SeatLamps;
  /** Drops the heading — for the floor's detail card, which has one already. */
  compact?: boolean;
}) {
  const { lamps: jobs, note, basis, countIsFloor, understates } = lamps;

  return (
    <div className="mt-2.5 flex flex-col gap-2">
      {!compact && (
        <div className="flex items-baseline gap-2">
          <span className={KT.label}>Running now</span>
          <span className={`font-mono text-[10px] tabular-nums ${KT.muted}`}>
            {jobs.length === 0 ? "none" : `${jobs.length}${countIsFloor ? "+" : ""}`}
          </span>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {jobs.map((j, i) => (
            <div key={j.taskId ?? i} className="flex items-baseline gap-2.5">
              <span
                className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                  j.state === "working"
                    ? "bg-[var(--kt-warn)]"
                    : "bg-[var(--kt-accent)]"}`}
                aria-hidden
              />
              <span className="min-w-0 flex-1 text-[12px] leading-snug text-[var(--kt-text)]">
                {j.task ?? (
                  <span className={KT.muted}>
                    This job was started with no description on the record.
                  </span>
                )}
                {j.state === "awaiting_review" && (
                  <span className={`ml-1.5 font-mono text-[9px] uppercase tracking-[0.12em] ${KT.accent}`}>
                    back — needs review
                  </span>
                )}
                {j.state === "working" && !j.reviewDetectable && (
                  <span className={`ml-1.5 text-[10px] ${KT.muted}`}>
                    (we cannot tell whether it has come back)
                  </span>
                )}
              </span>
              <span className={`shrink-0 font-mono text-[10px] tabular-nums ${KT.muted}`}>
                {j.since ? ago(j.since) : "no start time"}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* The sentence is ALWAYS rendered, including when there are jobs: it is
          where "this record only reports the newest one" lives, and that
          caveat matters most exactly when rows are on screen to be believed. */}
      <p className={`text-[11px] leading-snug ${
        basis === "unreadable" || countIsFloor || understates
          ? KT.sev.warn : KT.muted}`}>
        {note}
      </p>
    </div>
  );
}

/** How long ago, the way a person says it. An unreadable stamp says so. */
function ago(at: string): string {
  const t = Date.parse(at);
  if (Number.isNaN(t)) return "start time unreadable";
  const m = (Date.now() - t) / 60_000;
  if (m < 0) return "starts in the future";
  if (m < 60) return `${Math.round(m)}m`;
  if (m < 1440) return `${(m / 60).toFixed(1)}h`;
  return `${(m / 1440).toFixed(1)}d`;
}
