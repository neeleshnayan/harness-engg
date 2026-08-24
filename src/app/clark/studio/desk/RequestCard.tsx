"use client";

/**
 * The request card — the four questions, in order, without scrolling.
 *
 * Spec: `docs/design/REQUEST_CARD_2026-08-24.md`, CEO-ratified, written after
 * request `0c295ec7` rendered as a wall of prose: *"it could have been
 * designed in a far more intuitive and cleaner way"*.
 *
 *   1. WHAT IS THIS — a headline, not the first line of a dump.
 *   2. WHERE DOES IT STAND — the lifecycle rail, current stage hot, carrying
 *      its AGE. `0c295ec7`'s real story is "approved 22 minutes after filing,
 *      then idle 2.5 days"; the old card rendered that as gray footer text.
 *   3. WHAT IS OWED — `wanted` as a tracked checklist. Partial progress must
 *      be visible; a card is not binary.
 *   4. WHOSE MOVE IS IT — actor AND act. The old "CEO-APPROVED — TRIGGER IT"
 *      chip named an owner and left the obligation to be guessed, and it named
 *      the wrong owner.
 *
 * VISUAL GRAMMAR (theme.ts's ILLUMINATION PRINCIPLE): calm surfaces, hierarchy
 * from type and space, never colour. The ONLY colour here is semantic — the
 * hot lifecycle stage. Kind chips stay neutral, sentence case, mono for ids.
 *
 * PROSE-ONLY IS NOT A DEGRADED MODE. All 109 requests filed before the schema
 * existed render through the fallback and always will; there is no migration
 * and rewriting an old subject to look structured would invent a headline the
 * filer never wrote.
 */

import React from "react";

import type { AskCard, AskLifecycle } from "./execDesk";
import { KT } from "../theme";
/* `ageLabel` and the stage labels live in `cardState.ts`, not here, and the
   reason is mechanical rather than aesthetic: this repo's test runner is
   node's own type stripper, which REFUSES a `.tsx` file. A pure function in a
   component file is a pure function no test can reach — which is how an
   untested branch gets written by accident. */
import { STAGE_LABEL, ageLabel } from "./cardState";

function Rail({ lifecycle }: { lifecycle: AskLifecycle }) {
  const age = ageLabel(lifecycle.ageHours);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
      {lifecycle.stages.map((s, i) => {
        const label = STAGE_LABEL[s.stage] ?? s.stage;
        return (
          <React.Fragment key={s.stage}>
            {i > 0 && (
              <span className={`font-mono text-[10px] ${KT.muted}`} aria-hidden>
                ›
              </span>
            )}
            <span
              className={`font-mono text-[10px] ${
                s.current
                  ? "text-[var(--kt-warn)]"
                  : s.reached
                    ? KT.body
                    : KT.muted
              }`}
            >
              {label}
              {/* THE AGE RIDES THE HOT STAGE, and only it. An age on every
                  stage would be five numbers where the reader needs one: how
                  long has this been stuck HERE. */}
              {s.current && age ? ` · ${age}` : ""}
            </span>
          </React.Fragment>
        );
      })}
      {lifecycle.declined && (
        <span className={`font-mono text-[10px] ${KT.muted}`}>· declined</span>
      )}
    </div>
  );
}

function Wanted({ items }: { items: AskCard["wanted"] }) {
  return (
    <ul className="mt-2 space-y-1">
      {items.map((w, i) => (
        <li key={i} className="flex items-baseline gap-2 text-[12px]">
          {/* A TICK, A HALF, OR AN EMPTY BOX — three states, because partial
              progress is the entire reason this is a checklist and not a
              sentence. Glyphs rather than colour: the design language says
              hierarchy comes from type and space. */}
          <span className={`font-mono text-[10px] ${
            w.state === "done" ? KT.accent : KT.muted}`}>
            {w.state === "done" ? "✓" : w.state === "in_progress" ? "◐" : "○"}
          </span>
          <span className={`min-w-0 flex-1 ${
            w.state === "done" ? KT.muted : KT.body}`}>
            {w.text}
            {w.note ? (
              <span className={`${KT.muted}`}> — {w.note}</span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function RequestCardBody({ card, subject, open, onToggle }: {
  card: AskCard;
  /** The raw subject, for the prose fallback and the details section. */
  subject: string;
  open: boolean;
  onToggle: () => void;
}) {
  const detail = card.incident ?? (card.structured ? null : subject);
  /* The details toggle is offered only when the collapsed body says something
     the card face does not. For a prose ask whose whole subject IS the
     headline, a toggle onto a repeat of the headline is a control that lies
     about having content. */
  const hasMore = !!detail && detail.trim() !== (card.headline ?? "").trim();

  return (
    <>
      {card.summary && (
        <p className={`mt-1 text-[12px] leading-relaxed ${KT.muted}`}>
          {card.summary}
        </p>
      )}

      {card.lifecycle && <Rail lifecycle={card.lifecycle} />}

      {card.wanted.length > 0 && <Wanted items={card.wanted} />}

      {card.nextMove && (
        /* BOTH THE ACTOR AND THE ACT. The spine refuses a half-named move, so
           if this renders at all it names an obligation. */
        <p className={`mt-2 text-[12px] ${KT.body}`}>
          <span className={`font-mono text-[10px] uppercase tracking-[0.1em] ${KT.muted}`}>
            next move ·{" "}
          </span>
          {card.nextMove.actor} {card.nextMove.act}
        </p>
      )}

      {hasMore && (
        <button type="button" onClick={onToggle} aria-expanded={open}
                className={`mt-2 font-mono text-[10px] ${KT.accent} hover:underline`}>
          {open ? "− the incident" : "+ the incident"}
        </button>
      )}
      {open && hasMore && (
        <p className={`mt-2 whitespace-pre-wrap border-t border-[var(--kt-border)] pt-2 text-[12px] leading-relaxed ${KT.body}`}>
          {detail}
        </p>
      )}
    </>
  );
}
