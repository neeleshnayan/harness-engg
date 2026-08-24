"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { KT } from "../theme";
import { fmtAt } from "./seatLib";
import { laneEmptyNote, laneGlyph } from "./deskLanes";
import type { Lane, LaneRow } from "./deskLanes";
import type { LineageAnchor, LineageSources } from "./lineage";
import { lineageFor } from "./lineage";
import { LineageView } from "./LineageView";

/**
 * A LANE — a named queue, count first, collapsed unless it needs you.
 *
 * The CEO's standard for this page, verbatim: *"uncluttered and doesn't feel
 * generic ai slop + well arranged and maintained for lineage across our work
 * output"*. Four rules fall out of it and all four are structural:
 *
 *  1. **The number is read before the label is.** A lane header is a big light
 *     tabular numeral and a small uppercase mono label — the Studio's own
 *     type scale, which puts the figure first without spending any colour on
 *     it. Every count is on screen shut, so folding a lane hides no quantity.
 *  2. **A lane's number is the FUND'S number.** Where the page can render
 *     fewer rows than the fund counts, the header says `N · showing M` and the
 *     sentence under it says why. See `laneCount`.
 *  3. **One line per row, expand for the chain.** A row is a sentence and an
 *     actor; everything else — who asked, which run served it, in whose words
 *     it was decided, whether it was carried out — is one click away and is
 *     the SAME data, never a summary of it.
 *  4. **No decoration.** No gradient, no icon per row, no shadow, one accent
 *     hue. The only chevron on the page is the one that says a thing opens.
 */

export function LaneBlock({ lane, sources, children }: {
  lane: Lane;
  sources: LineageSources;
  /** Lane (a) renders the existing decision cards, which carry the approval
   *  controls. It passes them here rather than through `lane.rows` so that no
   *  control on the firm's decision channel is re-implemented by this file. */
  children?: React.ReactNode;
}) {
  const [open, setOpen] = useState(lane.openByDefault);
  const c = lane.count;
  return (
    <section className="border-t border-[var(--kt-border)] py-5 first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-baseline gap-3 text-left"
      >
        {open
          ? <ChevronDown size={14} className={`shrink-0 ${KT.muted}`} />
          : <ChevronRight size={14} className={`shrink-0 ${KT.muted}`} />}
        <span className={`${KT.numberLg} shrink-0 tabular-nums`}>
          {laneGlyph(c)}
        </span>
        <span className="min-w-0 flex-1">
          <span className={`${KT.label} block`}>{lane.label}</span>
          <span className={`mt-1 block max-w-3xl text-[12px] leading-relaxed ${KT.muted}`}>
            {lane.lede}
          </span>
        </span>
        {c.value !== null && c.shown !== c.value && (
          <span className={`shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            showing {c.shown}
          </span>
        )}
      </button>

      {c.note && (
        <p className={`ml-8 mt-2 max-w-3xl text-[11px] leading-relaxed ${
          c.source === "spine" && c.shown !== c.value ? KT.sev.warn : KT.muted}`}>
          {c.note}
        </p>
      )}
      {/* A WITHDRAWN ROW IS NEVER IN THIS LANE, and saying so is the difference
          between a filter and a disappearance. The row is reachable through
          the lineage of whatever replaced it. */}
      {lane.withdrawn > 0 && (
        <p className={`ml-8 mt-1 max-w-3xl text-[11px] leading-relaxed ${KT.muted}`}>
          {lane.withdrawn} row{lane.withdrawn === 1 ? " is" : "s are"} withdrawn
          by lineage and not listed here — the server refuses their approval, so
          a lane offering one would be offering a control that fails. They
          appear in lineage, labelled, with their replacement.
        </p>
      )}

      {open && (
        <div className="ml-8 mt-4">
          {children}
          {lane.rows.length > 0 && (
            <div className="space-y-1">
              {lane.rows.map((r) => (
                <LaneRowView key={r.key} row={r} sources={sources} />
              ))}
            </div>
          )}
          {/* THREE REASONS A LANE IS EMPTY, and only one of them is an empty
              queue — `laneEmptyNote`, in a file a test can run. */}
          {!children && lane.rows.length === 0 && (
            <p className={`text-[12px] ${KT.muted}`}>{laneEmptyNote(c)}</p>
          )}
        </div>
      )}
    </section>
  );
}

/** One row: a sentence, an actor, and the chain behind it on click. */
export function LaneRowView({ row, sources }: {
  row: LaneRow; sources: LineageSources;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-[var(--kt-border)] py-2 last:border-b-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="min-w-0 flex-1 text-[13px] leading-snug">{row.text}</p>
        {/* The one thing every collapsed lane must say per row: whose move it
            is. `null` renders as a finding, never as a blank. */}
        <span className={`shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] ${
          row.actor ? KT.muted : KT.sev.warn}`}
              title={row.actorWhy ?? undefined}>
          {row.actor ?? "no actor recorded"}
        </span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className={`shrink-0 font-mono text-[10px] ${KT.accent} hover:underline`}
        >
          {open ? "− lineage" : "+ lineage"}
        </button>
      </div>
      <p className={`mt-0.5 font-mono text-[10px] ${KT.muted}`}>
        {row.seat ?? "unattributed"}
        {row.at ? ` · ${fmtAt(row.at)}` : ""}
        {row.detail ? ` · ${row.detail}` : ""}
      </p>
      {open && <LineageInline anchor={row.anchor} sources={sources} />}
    </div>
  );
}

/**
 * The chain, folded on demand.
 *
 * FOLDED ON DEMAND AND NOT UP FRONT, deliberately: `lineageFor` walks the
 * whole 1000-event window per row, and doing that for 162 collapsed rows on
 * every 15-second poll would put a visible stall on the desk. Opening one row
 * is one walk.
 */
export function LineageInline({ anchor, sources }: {
  anchor: LineageAnchor; sources: LineageSources;
}) {
  const lineage = lineageFor(anchor, sources);
  return <LineageView lineage={lineage} />;
}
