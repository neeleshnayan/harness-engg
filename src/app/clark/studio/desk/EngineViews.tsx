"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, Flame, ShieldCheck, TriangleAlert } from "lucide-react";
import type {
  CeoDeskView, DeskBriefingsShelf, DeskHygieneReport, DeskSupersessionEdge,
} from "@/lib/fund_api";
import { KT } from "../theme";
import { badgeView, hygieneLine, supersessionChip } from "./deskEngine";

/**
 * The desk engine's four small views: the greeting, the shelf, the lineage
 * chip, and the disclosure that stops a page becoming a scroll.
 *
 * Every sentence here comes from the spine's fold or from a pure helper in
 * `deskEngine.ts`. Nothing on this page composes a claim of its own — the
 * greeting in particular is GENERATED, because a hand-written "all quiet"
 * would be the one line on the desk that nobody could falsify.
 */

/* ------------------------------------------------------------ greeting --- */

export function GreetingHeader({ view, needsYou }: {
  view: CeoDeskView | null;
  /** THE PAGE'S OWN COUNT, when the page has one.
   *
   *  Caught by looking at the rendered page: the greeting rendered the
   *  spine's figure four lines above a header rendering the page's, and the
   *  CEO's desk carried THREE numbers claiming to answer one question. It has
   *  shipped that defect twice already (11 vs 6, then 1 vs 0), and adding a
   *  third instance inside the instrument built to end it would be the worst
   *  possible place for it.
   *
   *  So a page that computes its own total passes it here and the greeting
   *  agrees with the header by construction. The page-vs-spine divergence is
   *  a real thing and it already has its own warning banner — one warning,
   *  not two numbers. Omit the prop and the spine's sentence is used verbatim,
   *  which is right for any surface with no count of its own. */
  needsYou?: number | null;
}) {
  if (!view) return null;
  const g = view.greeting;
  const halted = view.on_fire.risk_halted;
  const needs = typeof needsYou === "number"
    ? (needsYou ? `${needsYou} item(s) need you.`
                : "Nothing is waiting on you right now.")
    : g.needs_you;
  return (
    <div className={`${KT.card} mb-6`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className={KT.label}>Good to see you</p>
        <p className={`font-mono text-[10px] ${KT.muted}`}>
          {g.since ? `since your last visit ${g.since}` : "no previous visit supplied"}
        </p>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-[var(--kt-text)]">{g.changed}</p>
      <p className="mt-1 text-sm leading-relaxed text-[var(--kt-text-strong)]">
        {needs}
      </p>
      <p className="mt-1 flex items-start gap-1.5 text-sm leading-relaxed">
        {view.on_fire.total > 0 && (
          <Flame size={13} className="mt-0.5 shrink-0 text-[var(--kt-warn)]" />
        )}
        <span className={view.on_fire.total > 0 ? KT.sev.warn : KT.body}>
          {g.on_fire}
        </span>
      </p>
      {/* THE HALT IS THREE-VALUED AND IS RENDERED THAT WAY. `null` is the risk
          control being unreachable, and a desk that printed "not halted"
          because it could not reach the monitor would be the absence-as-zero
          error on the one control that stops losses. */}
      {halted === null && (
        <p className={`mt-1 text-[11px] italic ${KT.sev.warn}`}>
          The risk control could not be read, so whether trading is halted is
          UNKNOWN — not &ldquo;running&rdquo;.
        </p>
      )}
      {halted === true && (
        <p className={`mt-1 text-[11px] ${KT.sev.warn}`}>Trading is HALTED.</p>
      )}
      {g.hygiene && (
        <p className={`mt-2 text-[11px] leading-relaxed ${KT.muted}`}>{g.hygiene}</p>
      )}
      {(!view.readable.recommendations || !view.readable.supersessions
        || !view.readable.intray) && (
        <p className={`mt-2 flex items-start gap-1.5 text-[11px] ${KT.sev.warn}`}>
          <TriangleAlert size={12} className="mt-0.5 shrink-0" />
          <span>
            Part of the desk could not be read
            {!view.readable.recommendations && " · recommendations"}
            {!view.readable.supersessions && " · supersession lineage"}
            {!view.readable.intray && " · in-trays"}
            . What is below is incomplete, not empty.
          </span>
        </p>
      )}
    </div>
  );
}

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

/* ------------------------------------------------------------ hygiene ---- */

export function HygieneLine({ report }: { report: DeskHygieneReport | null }) {
  const line = hygieneLine(report);
  if (!line) return null;
  return <p className={`text-[11px] leading-relaxed ${KT.muted}`}>{line}</p>;
}

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
