"use client";

import React, { useState } from "react";
import { KT } from "../theme";
import { briefingOf, fmtDuration, type Briefing, type NextActor } from "./briefing.ts";
import { contextOf, type ContextView } from "./contextInspector.ts";
import type { DeskRequest, DeskRun } from "./seatLib.ts";

/**
 * THE BRIEFING CONTRACT, rendered — headline, chips, rows, the fold.
 *
 * The CEO approved the SeatOffice board with *"Cool lets get this"*. Every seat
 * delivery renders this way, everywhere: **a run record rendered as paragraphs
 * is a defect.** The measured precedent is the engine page's first version —
 * nine paragraphs of honest prose, and the verdict *"too much text; we need
 * analytics and graphs and meaningful and minimal UI"*.
 *
 * DOES THIS FORM SERVE THIS CONTENT BETTER THAN A GENERIC LIST WOULD? The
 * content is one claim, a few figures, and a set of asks with different owners.
 * A generic list flattens all three into one column of equal-weight lines, so
 * the reader has to find the claim, find the numbers, and work out which rows
 * are theirs. This form answers those three questions in three glances — one
 * sentence at heading weight, a strip of `tabular-nums`, and rows whose LAST
 * column is always the owner, so "which of these are mine" is a single
 * downward scan. The prose that justifies all of it is behind one caret.
 *
 * PLAIN ENGLISH (CEO, same day). Every sentence this card writes is checked by
 * `plainEnglish.test.ts`. The record's own words — the verdict, the asks, the
 * reasoning — are passed through untouched; the direction governs what WE
 * write around them, and the technical detail lives one tap down.
 */

/* ---------------------------------------------------------------- chips --- */

function Chips({ b }: { b: Briefing }) {
  if (b.chips.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {b.chips.map((c) => (
        <span key={c.label}
              className={`${KT.inset} flex items-baseline gap-1.5 px-2.5 py-1.5`}>
          <span className={`font-mono text-[13px] tabular-nums ${
            c.tone === "warn" ? "text-[var(--kt-warn)]" : "text-[var(--kt-text-strong)]"}`}>
            {c.value}
          </span>
          <span className={`text-[11px] ${KT.muted}`}>{c.label}</span>
          {c.sub && <span className={`text-[10px] ${KT.muted}`}>· {c.sub}</span>}
        </span>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------- rows --- */

/** The owner column. `ceo` is the only value that takes a tone — it is the one
 *  that can be overdue, and colour here is state, never decoration. */
const ACTOR_WORD: Record<NextActor, string> = {
  ceo: "you", chair: "the chair", seat: "a seat", nobody: "nobody",
  unstated: "unstated",
};

function Rows({ b }: { b: Briefing }) {
  if (b.rows.length === 0) {
    return <p className={`text-[12px] ${KT.muted}`}>{b.rowsNote}</p>;
  }
  return (
    <div className="flex flex-col border-t border-[var(--kt-border)]">
      {b.rows.map((r, i) => (
        <div key={r.recId ?? i}
             className={`flex items-baseline gap-3 py-2.5 ${
               i === b.rows.length - 1 ? "" : "border-b border-[var(--kt-border)]/60"}`}>
          {r.kind && (
            <span className={`shrink-0 rounded-full border border-[var(--kt-border-strong)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.1em] ${KT.muted}`}>
              {r.kind}
            </span>
          )}
          <span className="min-w-0 flex-1 text-[13px] leading-snug text-[var(--kt-text)]">
            {r.text}
          </span>
          {r.dueDate && (
            <span className="shrink-0 font-mono text-[10px] tabular-nums text-[var(--kt-warn)]">
              {r.dueDate}
            </span>
          )}
          <span className={`w-[68px] shrink-0 text-right font-mono text-[10px] uppercase tracking-[0.12em] ${
            r.nextActor === "ceo" ? "text-[var(--kt-warn)]" : KT.muted}`}>
            {ACTOR_WORD[r.nextActor]}
          </span>
        </div>
      ))}
    </div>
  );
}

/* --------------------------------------------------- the context inspector */

function ContextFold({ c }: { c: ContextView }) {
  const [open, setOpen] = useState(false);
  if (c.empty) return <p className={`text-[11px] ${KT.muted}`}>{c.note}</p>;
  return (
    <div className="flex flex-col gap-2">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
              className={`self-start font-mono text-[10px] uppercase tracking-[0.14em] ${KT.agent.text} hover:underline`}>
        {open ? "hide what this seat was told" : "what this seat was told"}
      </button>
      {open && (
        <div className={`${KT.inset} flex flex-col gap-3 p-3.5`}>
          {c.task && (
            <div className="flex flex-col gap-1">
              <span className={KT.label}>The line it was given</span>
              <p className="text-[12px] leading-snug text-[var(--kt-text)]">{c.task}</p>
            </div>
          )}
          {c.served.map((s) => (
            <div key={s.requestId} className="flex flex-col gap-1">
              <span className={KT.label}>
                {s.subject ?? "an ask with no headline on the record"}
              </span>
              {s.missing ? (
                <p className={`text-[11px] ${KT.muted}`}>
                  Named by this job and not in the batch this page read — it
                  exists, we did not look far enough.
                </p>
              ) : s.brief ? (
                <p className={`max-h-64 overflow-y-auto whitespace-pre-wrap text-[12px] leading-relaxed ${KT.body}`}>
                  {s.brief}
                </p>
              ) : (
                <p className={`text-[11px] ${KT.muted}`}>
                  This ask carries a headline and no written brief.
                </p>
              )}
            </div>
          ))}
          <p className={`text-[11px] leading-snug ${KT.muted}`}>{c.note}</p>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- card --- */

export function BriefingCard({ run, requests }: {
  run: DeskRun;
  /** For the context fold — the asks this job was fired against. */
  requests?: readonly DeskRequest[] | null;
}) {
  const [open, setOpen] = useState(false);
  const [saidMore, setSaidMore] = useState(false);
  const b = briefingOf(run);
  const c = contextOf(run, requests ?? null);
  const hasFold = Boolean(b.fold.reasoning || b.fold.artifactPath);

  return (
    <div className={`${KT.panel} flex flex-col gap-4 p-6`}>
      {/* HEADLINE. `text-wrap: balance` so a two-line claim breaks evenly
          rather than leaving one orphan word — the board's typographic
          moment, and the only place on the card with heading weight. */}
      <div className="flex flex-col gap-1.5">
        {b.headline ? (
          <>
            {/* CLAMPED TO TWO LINES, and this is a look-pass repair. The
                contract's headline slot expects ONE claim; the record supplies
                whatever the seat wrote, and a real one on the live record is
                five semicolon-joined clauses. At heading weight that rendered
                as three bold lines dominating the card — the exact "too much
                text" the CEO named on the engine page.
                Nothing is hidden: the clamp only bites when there is more, and
                the control below says so and opens it in place. Truncating
                without an affordance would be worse than the wall. */}
            <p onClick={() => setSaidMore((v) => !v)}
               className={`cursor-pointer text-[17px] font-semibold leading-snug text-[var(--kt-text-strong)] [text-wrap:balance] ${
                 saidMore ? "" : "line-clamp-2"}`}>
              {b.headline}
            </p>
            {b.headline.length > 150 && (
              <button type="button" onClick={() => setSaidMore((v) => !v)}
                      className={`self-start font-mono text-[10px] uppercase tracking-[0.14em] ${KT.muted} hover:text-[var(--kt-text)]`}>
                {saidMore ? "shorten" : "read the whole verdict"}
              </button>
            )}
          </>
        ) : null}
        {b.headlineNote && (
          <p className={`text-[12px] leading-snug ${
            b.outcome === "aborted" ? KT.sev.warn : KT.muted}`}>
            {b.headlineNote}
          </p>
        )}
      </div>

      <Chips b={b} />
      <Rows b={b} />

      {/* THE FOLD. One line, one caret, and the count of what is behind it —
          a disclosure that does not say how much it hides is a disclosure the
          reader learns not to open. */}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-[var(--kt-border)] pt-3">
        <ContextFold c={c} />
        {hasFold ? (
          <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
                  className={`font-mono text-[11px] ${KT.accent} hover:underline`}>
            {open ? "close the detail ↑" : "the detail ↓"}
          </button>
        ) : (
          <span className={`text-[11px] ${KT.muted}`}>
            This job filed no reasoning and no document.
          </span>
        )}
      </div>

      {open && hasFold && (
        <div className="flex flex-col gap-3">
          {b.fold.reasoning && (
            <p className={`whitespace-pre-wrap text-[12.5px] leading-relaxed ${KT.body}`}>
              {b.fold.reasoning}
            </p>
          )}
          <p className={`flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] ${KT.muted}`}>
            {b.fold.artifactPath && <span>{b.fold.artifactPath}</span>}
            {b.fold.model ? <span>{b.fold.model}</span>
              : <span>no model recorded</span>}
            {b.fold.tokens != null && (
              <span className="tabular-nums">
                {b.fold.tokens.toLocaleString("en-US")} tokens
              </span>
            )}
            {b.fold.toolUses != null && (
              <span className="tabular-nums">{b.fold.toolUses} tool calls</span>
            )}
            <span>{fmtDuration(b.fold.ranMinutes) ?? "how long it ran is not on the record"}</span>
            <span>{b.runId}</span>
          </p>
        </div>
      )}
    </div>
  );
}
