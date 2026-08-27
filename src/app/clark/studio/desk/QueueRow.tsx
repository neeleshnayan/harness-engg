"use client";

import React, { useState } from "react";
import { KT } from "../theme";
import { SeatFace } from "./SeatFace";
import type { Band, ConsoleRow } from "./consoleQueue.ts";

/**
 * QUEUES ARE ROWS, NEVER ESSAYS — the Main board's idiom, built once.
 *
 * The CEO approved the Studio Work Surfaces canvas with *"Cool lets get this"*.
 * Its instruction for a queue: **band · seat · verb-and-object · money · age,
 * one tap to open, an honest tail.** The console it replaces stacked cards, each
 * a paragraph tall and none of them ranked, so the oldest item on the desk (142
 * hours, measured on the live record 2026-08-27) looked exactly like the newest.
 *
 * DOES THIS FORM SERVE THIS CONTENT BETTER THAN A GENERIC LIST WOULD? A queue's
 * whole job is COMPARISON — the reader is not reading items, they are choosing
 * between them. A row puts the four comparable fields in four fixed columns, so
 * the eye scans down one column instead of re-finding a fact inside each card.
 * A card grid makes every comparison a search. That is the answer, and it is
 * why the prose lives behind the caret rather than on the surface.
 *
 * NO EMOJI, NO GRADIENT, NO LEFT-ACCENT-BAR. The caret is a stroke SVG on a
 * 16px grid; the band chip is the only tonal element and it earns it by being
 * the CEO's own ranking made visible.
 */

/* ---------------------------------------------------------------- chips --- */

const BAND_TONE: Record<Band, string> = {
  // Warn is the loudest token in the house and this is the one row-level fact
  // that has earned it: the filer said this is holding something up.
  blocker: "border-[var(--kt-warn)]/40 bg-[var(--kt-warn)]/10 text-[var(--kt-warn)]",
  // Dated is a fact, not an alarm — bordered, untinted.
  time_sensitive: "border-[var(--kt-border-strong)] text-[var(--kt-text-dim)]",
  rest: "",
  unbanded: "",
};

/**
 * The band, as a chip. Renders NOTHING when the record made no claim.
 *
 * An empty pill for "nobody said" would read as a fourth priority level, and a
 * chip saying "normal" would be the renderer inventing a judgement the filer
 * declined to make.
 */
export function BandChip({ row }: { row: Pick<ConsoleRow, "band" | "bandLabel" | "bandNote"> }) {
  if (!row.bandLabel) return null;
  return (
    <span
      title={row.bandNote ?? undefined}
      className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] ${BAND_TONE[row.band]}`}
    >
      {row.bandLabel}
    </span>
  );
}

function Caret({ open }: { open: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden
         className={`shrink-0 transition-transform ${open ? "rotate-90" : ""}`}>
      <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.25"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ------------------------------------------------------------- the money -- */

/** Zero is quiet: a stated $0 renders as a dash in the muted tone rather than
 *  as a figure competing with real ones. Absent renders as nothing at all —
 *  124 of the 200 priced rows on the live desk are 0.0, and a column of $0
 *  would be the loudest thing on the page while saying nothing. */
function Money({ usd }: { usd: number | null }) {
  if (usd == null) return <span className="w-16" />;
  if (usd === 0) {
    return (
      <span className={`w-16 shrink-0 text-right font-mono text-[11px] tabular-nums ${KT.muted}`}
            title="The seat filed this as nothing at stake.">
        —
      </span>
    );
  }
  return (
    <span className="w-16 shrink-0 text-right font-mono text-[11px] tabular-nums text-[var(--kt-accent)]">
      {usd >= 1000 ? `$${Math.round(usd).toLocaleString("en-US")}` : `$${usd.toFixed(usd % 1 === 0 ? 0 : 2)}`}
    </span>
  );
}

/* --------------------------------------------------------------- the row -- */

export function QueueRow({ row, last = false }: { row: ConsoleRow; last?: boolean }) {
  const [open, setOpen] = useState(false);
  const hasFold = Boolean(row.detail || row.approvedBy || row.bandNote);
  return (
    <div className={last ? "" : "border-b border-[var(--kt-border)]/60"}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        disabled={!hasFold}
        className={`flex w-full items-center gap-3.5 px-5 py-3 text-left transition-colors ${hasFold ? "hover:bg-[var(--kt-hover)]" : "cursor-default"}`}
      >
        {/* THE DATE COLUMN. Fixed width so the eye scans one column; a dash in
            the muted tone where there is none, because an undated row is a
            fact and a blank cell is an oversight. */}
        <span className={`w-[68px] shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] tabular-nums ${row.dueDate ? "text-[var(--kt-warn)]" : KT.muted}`}>
          {row.dueDate ? row.dueDate.slice(5).replace("-", " ") : "—"}
        </span>
        <BandChip row={row} />
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-[10px]">
          <SeatFace actor={row.seat ?? undefined} size={16} decorative />
          <span className={KT.muted}>{row.seat ?? "unassigned"}</span>
        </span>
        <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--kt-text-strong)]">
          {row.verbObject}
        </span>
        <Money usd={row.money} />
        <span className={`w-11 shrink-0 text-right font-mono text-[10px] tabular-nums ${KT.muted}`}>
          {row.ageLabel ?? "—"}
        </span>
        <span className={hasFold ? KT.muted : "text-transparent"}><Caret open={open} /></span>
      </button>
      {open && hasFold && (
        <div className="flex flex-col gap-2.5 px-5 pb-4 pl-[92px]">
          {row.detail && (
            <p className={`max-w-3xl whitespace-pre-wrap text-[12.5px] leading-relaxed ${KT.body}`}>
              {row.detail}
            </p>
          )}
          {row.bandNote && (
            <p className={`text-[11px] ${KT.muted}`}>{row.bandNote}</p>
          )}
          <p className={`flex flex-wrap gap-x-3 font-mono text-[10px] ${KT.muted}`}>
            {row.approvedBy && (
              <span className={KT.accent}>
                approved by {row.approvedBy}{row.approvedAt ? ` · ${row.approvedAt.slice(0, 16).replace("T", " ")}Z` : ""}
              </span>
            )}
            {row.seatFiled && <span>filed by a seat — an ask, never a trigger</span>}
            <span>{row.origin === "request" ? "desk ask" : "recommendation"}</span>
            <span>{row.id.slice(0, 20)}</span>
          </p>
        </div>
      )}
    </div>
  );
}
