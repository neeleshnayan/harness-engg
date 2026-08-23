"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, ShieldCheck } from "lucide-react";
import type { DeskBriefingsShelf, DeskSupersessionEdge } from "@/lib/fund_api";
import { KT } from "../theme";
import { badgeView, supersessionChip } from "./deskEngine";

/**
 * The desk engine's three small views: the briefings shelf, the lineage chip,
 * and the disclosure that stops a page becoming a scroll.
 *
 * Every sentence here comes from the spine's fold or from a pure helper in
 * `deskEngine.ts`. Nothing in this file composes a claim of its own.
 */

/* `GreetingHeader` was DELETED here (D31, cleanup ticket dce47670).
 *
 * NOT ONE OF ITS SENTENCES WAS LOST, and that is the condition on this
 * deletion. The redesigned desk header is the answer, not a dashboard: the
 * greeting card's own `changed` line is now the header's greeting, its
 * `needs_you` figure is the header's hero number (which the card had to be
 * handed as a prop to stop it disagreeing), and `on_fire`, the three-valued
 * halt, the hygiene sentence and the readability warnings are in the Context
 * panel under the lanes — all still read verbatim from `view.greeting` and
 * `view.readable`, never composed by the page. What went is the CARD, its
 * `needsYou` prop, and one of the two places a reader had to look for the
 * same four facts.
 */

/* --------------------------------------------------------------- shelf --- */

export function BriefingsShelf({ shelf }: { shelf: DeskBriefingsShelf | null }) {
  if (!shelf) {
    return (
      <p className={`text-sm ${KT.sev.warn}`}>
        The briefings shelf could not be read. That is an outage, not an empty
        shelf.
      </p>
    );
  }
  if (shelf.memos.length === 0) {
    return <p className={`text-sm ${KT.muted}`}>{shelf.note}</p>;
  }
  return (
    <div className={`${KT.panel} divide-y divide-[var(--kt-border)]`}>
      {shelf.memos.map((m) => {
        const badge = badgeView(m);
        return (
          <div key={m.path} className="px-4 py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <p className="text-sm font-medium text-[var(--kt-text-strong)]">
                {m.title || m.path}
              </p>
              <span className={`flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] ${
                badge.tone === "verified" ? KT.accent
                  : badge.tone === "unknown" ? KT.sev.warn : KT.muted}`}>
                {badge.tone === "verified" && <ShieldCheck size={11} />}
                {badge.text}
              </span>
            </div>
            <p className={`mt-0.5 font-mono text-[10px] ${KT.muted}`}>
              {m.who} · {m.label} · {m.date ?? "undated"} · {m.path}
            </p>
            {/* A CORRECTION IS A CHIP, NEVER AN EDIT. Findings-doc rules apply
                to the shelf: a silently corrected memo is a memo whose reader
                cannot tell what it said when the decision was made. */}
            {m.corrections.map((c, i) => (
              <p key={i} className={`mt-1 text-[11px] ${KT.sev.warn}`}>
                correction ({c.actor}): {c.note}
              </p>
            ))}
          </div>
        );
      })}
      <p className={`px-4 py-2 text-[11px] italic ${KT.muted}`}>{shelf.note}</p>
    </div>
  );
}

/* --------------------------------------------------------- the lineage --- */

export function SupersessionNotice({ edge }: { edge: DeskSupersessionEdge | null }) {
  const chip = supersessionChip(edge);
  if (!chip) return null;
  return (
    <div className={`${KT.inset} mt-2 p-3`}>
      <p className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.sev.warn}`}>
        {chip.label}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-[var(--kt-text)]">{chip.detail}</p>
      {chip.superseder && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>
          superseded by <span className="font-mono">{chip.superseder}</span>
        </p>
      )}
      {chip.diesAt && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>
          premise dies at: {chip.diesAt}
        </p>
      )}
      {chip.revivesIf && (
        <p className={`mt-1 text-[11px] ${KT.muted}`}>
          revives if: {chip.revivesIf}
        </p>
      )}
      <p className={`mt-1.5 text-[11px] italic ${KT.muted}`}>
        The approve control is disabled AND the server refuses it — a disabled
        button is a hint, and this must be impossible, not awkward.
      </p>
    </div>
  );
}

/* `HygieneLine` was DELETED here (D31, cleanup ticket dce47670): a component
   with no caller since it was written, composing a client-side hygiene
   sentence that the spine now serves verbatim on `greeting.hygiene`. Its
   helper `deskEngine.hygieneLine()` went with it. */

/* ------------------------------------------------------------- a fold ---- */

/**
 * NAMED DISCLOSURE — what is behind it and how many, before it is opened.
 *
 * The distinction that makes this honest rather than a hiding place: a section
 * labelled "more" would be concealment with a chevron. The count renders shut
 * or open, so nothing leaves the page by being folded.
 */
export function Fold({ title, n, lede, defaultOpen = false, children }: {
  title: string;
  n: number | null;
  lede?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="mb-4">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`flex w-full items-center gap-2 rounded-lg px-1 py-2 text-left transition-colors hover:bg-[var(--kt-hover)]`}
      >
        {open ? <ChevronDown size={13} className={KT.muted} />
              : <ChevronRight size={13} className={KT.muted} />}
        <span className={KT.label}>{title}</span>
        <span className={`font-mono tabular-nums text-xs ${
          n === null ? KT.sev.warn : KT.muted}`}>
          {/* UNREADABLE IS A WORD. A dash here would read as zero. */}
          {n === null ? "unreadable" : n}
        </span>
      </button>
      {lede && !open && (
        <p className={`ml-6 text-[11px] leading-relaxed ${KT.muted}`}>{lede}</p>
      )}
      {open && <div className="mt-2">{children}</div>}
    </section>
  );
}
